import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V2", layout="wide")

st.title("📈 Můj Investiční Stratég - Živá Data")

# --- SIDEBAR NASTAVENÍ ---
st.sidebar.header("Nastavení bodování")
margin_high = st.sidebar.slider("Čistá marže pro 10 bodů (%)", 0, 50, 20)
margin_mid = st.sidebar.slider("Čistá marže pro 5 bodů (%)", 0, 50, 10)

# --- FUNKCE PRO STAHOVÁNÍ DAT ---
@st.cache_data(ttl=3600)  # Data se uloží na hodinu do paměti, aby se to nespouštělo pořád
def get_stock_data(tickers):
    results = []
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            info = stock.info
            results.append({
                "Ticker": t,
                "Cena": info.get("currentPrice"),
                "Marze_TTM": info.get("profitMargins", 0) * 100,
                "ROE_TTM": info.get("returnOnEquity", 0) * 100
            })
        except:
            st.error(f"Nepodařilo se stáhnout data pro {t}")
    return pd.DataFrame(results)

# --- SEZNAM AKCIÍ ---
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]
df = get_stock_data(moje_akcie)

# --- VÝPOČET SCORE ---
def spocti_score(row):
    score = 0
    if row["Marze_TTM"] > margin_high: score += 10
    elif row["Marze_TTM"] > margin_mid: score += 5
    return score

df["Celkové Score (T)"] = df.apply(spocti_score, axis=1)

# --- ZOBRAZENÍ ---
st.dataframe(df.sort_values(by="Celkové Score (T)", ascending=False))
st.success("Data byla úspěšně stažena z burzy!")
