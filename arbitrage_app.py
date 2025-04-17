
import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import time
from datetime import datetime

st.set_page_config(page_title="Arbitrage Radar", layout="wide")

def calculate_arbitrage(odds_dict, total_stake=100):
    inv_odds = {result: 1/odd for result, odd in odds_dict.items()}
    inv_sum = sum(inv_odds.values())

    if inv_sum >= 1:
        return {
            "arbitrage_possible": False,
            "message": "Geen arbitrage mogelijk met deze quoteringen.",
            "total_inverse": inv_sum
        }

    stakes = {result: (inv / inv_sum) * total_stake for result, inv in inv_odds.items()}
    payout = {result: stake * odds_dict[result] for result, stake in stakes.items()}
    profit = {result: payout[result] - total_stake for result in payout}

    return {
        "arbitrage_possible": True,
        "total_inverse": inv_sum,
        "stakes": stakes,
        "payouts": payout,
        "profit": profit,
        "max_profit": max(profit.values())
    }

def scrape_odds_oddsportal(match_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(match_url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    odds_table = soup.select_one('.table-main')
    odds_data = {}

    if odds_table:
        rows = odds_table.select('tr')
        for row in rows:
            cells = row.select('td.odds-nowrp')
            if len(cells) == 3:
                bookmaker = row.select_one('td.bookmaker-name')
                if not bookmaker:
                    continue
                bookmaker_name = bookmaker.get_text(strip=True)
                try:
                    home = float(cells[0].get_text(strip=True))
                    draw = float(cells[1].get_text(strip=True))
                    away = float(cells[2].get_text(strip=True))
                    odds_data[bookmaker_name] = {
                        'Home': home,
                        'Draw': draw,
                        'Away': away
                    }
                except ValueError:
                    continue
    return odds_data

def scrape_matches_from_league(league_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(league_url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    match_links = []
    for link in soup.select('a[href*="/football/"]'):
        href = link.get('href')
        if href and '/match/' in href and href not in match_links:
            match_links.append("https://www.oddsportal.com" + href.strip())

    return match_links

st.title("📊 Arbitrage Radar – Voetbalweddenschappen")
st.markdown("Analyseer meerdere competities voor gegarandeerde winst.")

with st.sidebar:
    st.header("⚙️ Instellingen")
    leagues_input = st.text_area("Voeg OddsPortal competitie-URL's toe (1 per regel):", """
https://www.oddsportal.com/football/england/premier-league/
https://www.oddsportal.com/football/netherlands/eredivisie/
https://www.oddsportal.com/football/spain/laliga/
""")
    total_stake = st.number_input("Totale inzet (€)", min_value=10, max_value=1000, value=100, step=10)
    show_only_profitable = st.checkbox("🔍 Toon alleen arbitrage met winst", value=True)
    min_profit = st.slider("📈 Minimale winst (€)", 0.0, 100.0, 1.0, 0.5)

if st.button("Start Arbitrage Analyse"):
    league_urls = [url.strip() for url in leagues_input.strip().splitlines() if url.strip()]
    all_output = []

    for league_url in league_urls:
        st.subheader(f"🔎 {league_url}")
        match_urls = scrape_matches_from_league(league_url)
        st.info(f"Gevonden {len(match_urls)} wedstrijden. Odds worden nu opgehaald...")

        output = []
        progress_bar = st.progress(0)

        for i, match_url in enumerate(match_urls):
            time.sleep(1)
            odds = scrape_odds_oddsportal(match_url)
            if not odds:
                continue

            max_odds = {r: max([book[r] for book in odds.values() if r in book], default=0) for r in ['Home', 'Draw', 'Away']}
            result = calculate_arbitrage(max_odds, total_stake=total_stake)

            if result["arbitrage_possible"] and result["max_profit"] >= min_profit:
                row = {
                    "Competitie": league_url,
                    "Wedstrijd URL": match_url,
                    "Arbitrage?": True,
                    "Max winst (€)": round(result["max_profit"], 2),
                    **{f"Inzet {k}": round(v, 2) for k, v in result["stakes"].items()},
                    **{f"Winst {k}": round(v, 2) for k, v in result["profit"].items()},
                    "Total 1/Odds": round(result["total_inverse"], 4),
                    "🔖 Bookmark": f"[🔗 Open]({match_url})"
                }
                output.append(row)

            progress_bar.progress((i+1)/len(match_urls))

        df = pd.DataFrame(output)
        all_output.extend(output)

        if not df.empty:
            df_sorted = df.sort_values(by="Max winst (€)", ascending=False)
            st.dataframe(df_sorted.reset_index(drop=True), use_container_width=True)
        else:
            st.warning("Geen winstgevende arbitrage gevonden in deze competitie.")

    if all_output:
        final_df = pd.DataFrame(all_output).sort_values(by="Max winst (€)", ascending=False)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv = final_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download alle resultaten als CSV", csv, f"arbitrage_{timestamp}.csv", "text/csv")
    else:
        st.info("Geen arbitrage gevonden die voldoet aan de filterinstellingen.")
