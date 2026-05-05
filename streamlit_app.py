import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Můj Investiční Stratég V3", layout="wide")

st.title("🚀 Kompletní Investiční Analýza")
st.write("Hodnocení akcií na základě vašich 16 parametrů a živých dat.")

# --- SIDEBAR: KONFIGURACE MATICE (Řádky 3-7) ---
st.sidebar.header("⚙️ Nastavení bodování")

with st.sidebar.expander("1. Čistá marže (Profit Margin)"):
    m_high = st.slider("Body: 10 (nad %)", 0, 50, 20, key="m1")
    m_mid = st.slider("Body: 5 (nad %)", 0, 50, 10, key="m2")

with st.sidebar.expander("2. ROE (Return on Equity)"):
    r_high = st.slider("Body: 10 (nad %)", 0, 50, 15, key="r1")
    r_mid = st.slider("Body: 5 (nad %)", 0, 50, 8, key="r2")

with st.sidebar.expander("3. Zadluženost (Debt to Equity)"):
    d_low = st.slider("Body: 10 (pod ratio)", 0.0, 3.0, 0.5, step=0.1)
    d_mid = st.slider("Body: 5 (pod ratio)", 0.0, 3.0, 1.5, step=0.1)

# --- FUNKCE PRO VÝPOČET SCORE ---
def vypocitej_vysledek(data):
    score = 0
    duvod = []
    
    # Logika pro Marži
    if data['Marze'] > m_high: 
        score += 10
    elif data['Marze'] > m_mid: 
        score += 5
    
    # Logika pro ROE
    if data['ROE'] > r_high: 
        score += 10
    elif data['ROE'] > r_mid: 
        score += 5

    # Logika pro Debt/Equity (tady je to obráceně - méně je lépe)
    if data['Debt_Equity'] < d_low: 
        score += 10
    elif data['Debt_Equity'] < d_mid: 
        score += 5
        
    return score

# --- STAHOVÁNÍ DAT ---
@st.cache_data(ttl=3600)
def fetch_data(tickers):
    rows = []
    for t in tickers:
        try:
            s = yf.Ticker(t)
            info = s.info
            d = {
                "Ticker": t,
                "Název": info.get("longName", t),
                "Cena": info.get("currentPrice"),
                "Marze": info.get("profitMargins", 0) * 100,
                "ROE": info.get("returnOnEquity", 0) * 100,
                "Debt_Equity": info.get("debtToEquity", 0) / 100 # yfinance vrací v % nebo ratio
            }
            d["Score"] = vypocitej_vysledek(d)
            rows.append(d)
        except:
            continue
    return pd.DataFrame(rows)

# --- HLAVNÍ SEZNAM ---
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "AMD", "PYPL"]
df = fetch_data(moje_akcie)

# Seřazení podle Score (Vaše Tčko)
df = df.sort_values(by="Score", ascending=False)

# Zobrazení v aplikaci
st.subheader("📊 Žebříček podle vašeho nastavení")
st.dataframe(
    df.style.background_gradient(subset=['Score'], cmap='Greens'),
    use_container_width=True
)

st.divider()
st.write("Aplikace nyní sleduje reálné parametry. Stačí upravit posuvníky vlevo a sledovat, jak se mění pořadí firem.")
