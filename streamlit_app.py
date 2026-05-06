import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Investiční Matrix V29 - Alpha Vantage", layout="wide")

# --- SEM VLOŽTE SVŮJ KLÍČ ---
API_KEY = "3KG016FF0QUKXML7" 
# ---------------------------

ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam_akcii(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        ex_df = pd.read_csv(csv_url)
        ex_df.columns = ex_df.columns.str.strip()
        return pd.Series(ex_df.Kategorie.values, index=ex_df.Ticker).to_dict()
    except: return {}

moje_databaze = nacti_seznam_akcii(ODKAZ_NA_TABULKU)

st.title("🏛️ Investiční Matrix V29 - Zdroj Alpha Vantage")
st.info("Bezplatná verze Alpha Vantage dovoluje 5 volání za minutu. Pro více akcií je třeba trpělivost nebo placený tarif.")

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# Definujeme sloupce, které CHCEME vidět (natvrdo)
COLS = ["Ticker", "Score", "P/E", "P/S", "P/B", "Marže Čistá", "ROE", "Div. Výnos", "Potenciál"]

@st.cache_data(ttl=3600)
def fetch_alpha_data(ticker):
    # Alpha Vantage používá jiné formáty tickerů (HEI.AMS místo HEI.AS)
    # Pro jednoduchost zkusíme standardní ticker
    url = f'https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={API_KEY}'
    r = requests.get(url)
    data = r.json()
    
    if not data or "Symbol" not in data:
        return None
        
    def f(k): return float(data.get(k, 0)) if data.get(k) != 'None' else 0

    return {
        "Ticker": ticker,
        "P/E": f("TrailingPE"),
        "P/S": f("PriceToSalesRatioTTM"),
        "P/B": f("PriceToBookRatio"),
        "Marže Čistá": f("ProfitMargin") * 100,
        "ROE": f("ReturnOnEquityTTM") * 100,
        "Div. Výnos": f("DividendYield") * 100,
        "Potenciál": f("AnalystTargetPrice") # Jen pro ilustraci
    }

# --- ZOBRAZENÍ ---
if moje_databaze:
    res = []
    tickery = list(moje_databaze.keys())
    
    # Omezení pro free verzi (jen prvních pár pro test)
    st.warning("Provádím test pro prvních 5 akcií kvůli limitu API (5/min).")
    for t in tickery[:5]: 
        data = fetch_alpha_data(t)
        if data:
            # Jednoduché skóre pro test
            data["Score"] = (15 if 0 < data["P/E"] < 15 else 5) + (10 if data["Marže Čistá"] > 10 else 0)
            res.append(data)
    
    if res:
        df = pd.DataFrame(res)
        st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)
    else:
        st.error("API Alpha Vantage vrátilo prázdná data. Pravděpodobně chybný klíč nebo limit.")
