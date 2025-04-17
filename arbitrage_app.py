import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import time
from datetime import datetime

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
        "profit": profit
    }

def scrape_odds_oddsportal(match_url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
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

st.title("📊 Europese Voetbal Arbitrage Tool")

st.markdown("Vul meerdere competitie-URL's in, gescheiden door een ENTER:")
leagues_input = st.text_area("OddsPortal competitiepagina's", """
https://www.oddsportal.com/football/england/premier-league/
https://www.oddsportal.com/football/spain/laliga/
https://www.oddsportal.com/football/italy/serie-a/
https://www.oddsportal.com/football/netherlands/eredivisie/
""")

total_stake = st.number_input("Totale inzet (€)", min_value=10, max_value=1000, value=100, step=10)

if st.button("Start dagelijkse arbitrage check"):
    league_urls = [url.strip() for url in leagues_input.strip().splitlines() if url.strip()]
    all_output = []

    for league_url in league_urls:
        st.subheader(f"🔍 Analyse van: {league_url}")
        match_urls = scrape_matches_from_league(league_url)
        st.info(f"Gevonden {len(match_urls)} wedstrijden. Odds worden nu opgehaald...")

        output = []
        progress_bar = st.progress(0)

        for i, match_url in enumerate(match_urls):
            time.sleep(1)
            odds = scrape_odds_oddsportal(match_url)
            if not odds:
                continue

            max_odds = {}
            for result in ['Home', 'Draw', 'Away']:
                max_odds[result] = max([book[result] for book in odds.values() if result in book], default=0)

            result = calculate_arbitrage(max_odds, total_stake=total_stake)
            row = {"Competitie": league_url, "Wedstrijd URL": match_url, "Arbitrage?": result["arbitrage_possible"], "Total 1/Odds": round(result["total_inverse"], 4)}
            if result["arbitrage_possible"]:
                row.update({f"Inzet {k}": round(v, 2) for k, v in result["stakes"].items()})
                row.update({f"Winst {k}": round(v, 2) for k, v in result["profit"].items()})
            output.append(row)

            progress_bar.progress((i+1)/len(match_urls))

        df = pd.DataFrame(output)
        all_output.extend(output)

        st.success(f"✅ Analyse van {league_url} voltooid")
        st.dataframe(df)

    if all_output:
        final_df = pd.DataFrame(all_output)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv = final_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download alle resultaten als CSV", csv, f"arbitrage_{timestamp}.csv", "text/csv")
    else:
        st.warning("Geen bruikbare odds of arbitrage gevonden.")
