import streamlit as st
import pandas as pd
import yfinance as yf

# Nastavení stránky
st.set_page_config(page_title="Investiční Stratég V5", layout="wide")

st.title("💎 Investiční Analýza s Matrix Editorem")
st.write("Upravte body a hranice v levém panelu a sledujte přepočet v reálném čase.")

# --- SIDEBAR: NASTAVENÍ MATICE BODŮ ---
st.sidebar.header("📊 Bodovací Matice")

# Sekce Čistá Marže
with st.sidebar.expander("1. Čistá Marže (Profit Margin)", expanded=True):
    m_h_val = st.number_input("Hranice pro max body (%)", value=20.0, key="m_h_v")
    m_h_pts = st.number_input("Body za max hranici", value=10, key="m_h_p")
    m_m_val = st.number_input("Hranice pro stř. body (%)", value=10.0, key="m_m_v")
    m_m_pts = st.number_input("Body za stř. hranici", value=5, key="m_m_p")

# Sekce ROE
with st.sidebar.expander("2. ROE (Return on Equity)", expanded=True):
    r_h_val = st.number_input("Hranice pro max body (ROE %)", value=15.0, key="r_h_v")
    r_h_pts = st.number_input("Body za max hranici (ROE)", value=10, key="r_h_p")
    r_m_val = st.number_input("Hranice pro stř. body (ROE %)", value=8.0, key="r_m_v")
    r_m_pts = st.number_input("Body za stř. hranici (ROE)", value=5, key="r_m_p")

# Sekce Debt to Equity (zde je méně lépe!)
with st.sidebar.expander("3. Zadluženost (Debt/Equity)", expanded=True):
    d_l_val = st.number_input("Hranice pro max body (Dluh pod)", value=0.5, key="d_l_v")
    d_l_pts = st.number_input("Body za nízký dluh", value=10, key="d_l_p")
    d_m_val = st.number_input("Hranice pro stř. body (Dluh pod)", value=1.5, key="d_m_v")
    d_m_pts = st.number_input("Body za stř. dluh", value=5, key="d_m_p")

# --- FUNKCE PRO VÝPOČET SCORE ---
def vypocitej_score(row):
    score = 0
    
    # Bodování Marže
    if row['Marze'] >= m_h_val: score += m_h_pts
    elif row['Marze'] >= m_m_val: score += m_m_pts
    
    # Bodování ROE
    if row['ROE'] >= r_h_val: score += r_h_pts
    elif row['ROE'] >= r_m_val: score += r_m_pts
    
    # Bodování Dluhu (méně je lépe)
    if row['Debt_Equity'] <= d_l_val: score += d_l_pts
    elif row['Debt_Equity'] <= d_m_val: score += d_m_pts
        
    return score

# --- STAHOVÁNÍ DAT ---
# Sem si doplňte své tickery ze sloupce B ve vašem Excelu
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "V", "MA", "COST", "KO", "PEP"]

@st.cache_data(ttl=3600)
def fetch_data(tickers):
    rows = []
    for t in tickers:
        try:
            s = yf.Ticker(t)
            info = s.info
            # Převod dat z yfinance na standardní formát
            d = {
                "Ticker": t,
                "Název": info.get("longName", t),
                "Cena": info.get("currentPrice"),
                "Marze": info.get("profitMargins", 0) * 100,
                "ROE": info.get("returnOnEquity", 0) * 100,
                "Debt_Equity": info.get("debtToEquity", 0) / 100 if info.get("debtToEquity") else 0
            }
            rows.append(d)
        except:
            continue
    return pd.DataFrame(rows)

# Získání dat a výpočet score
df = fetch_data(moje_akcie)
df["Score"] = df.apply(vypocitej_score, axis=1)

# Seřazení
df = df.sort_values(by="Score", ascending=False)

# --- ZOBRAZENÍ ---
st.subheader("📊 Výsledky analýzy")
st.dataframe(
    df.style.background_gradient(subset=['Score'], cmap='YlGn'), # Žluto-zelená škála
    use_container_width=True
)

st.info("Tip: Změňte hodnoty v políčkách vlevo (např. zvyšte body za ROE) a tabulka se okamžitě přerovná.")
