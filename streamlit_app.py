import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 3.5rem; padding-bottom: 0rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    
    /* Vynucené zvýraznění prvního sloupce - Modrá a Tučná */
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { 
        font-weight: bold !important;
        color: #004080 !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]:
        return 999
    try:
        dt = pd.to_datetime(earn_val, dayfirst=True).date()
        return (dt - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. NAČTENÍ DAT A HISTORICKÁ CACHE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=86400)
def fetch_historical_averages(ticker_symbol, current_gm, current_nm, current_roe):
    try:
        tk = yf.Ticker(ticker_symbol)
        fin = tk.financials
        bs = tk.balance_sheet
        
        # Hrubá marže 3Y
        gm_3y = current_gm
        if fin is not None and not fin.empty and 'Gross Profit' in fin.index and 'Total Revenue' in fin.index:
            roky = fin.columns[:3]
            vals = [fin.loc['Gross Profit', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
            if vals: gm_3y = (sum(vals) / len(vals)) * 100

        # Čistá marže 3Y
        nm_3y = current_nm
        if fin is not None and not fin.empty and 'Net Income' in fin.index and 'Total Revenue' in fin.index:
            roky = fin.columns[:3]
            vals = [fin.loc['Net Income', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
            if vals: nm_3y = (sum(vals) / len(vals)) * 100

        # ROE 3Y
        roe_3y = current_roe
        if fin is not None and not fin.empty and bs is not None and not bs.empty and 'Net Income' in fin.index and 'Stockholders Equity' in bs.index:
            roky = [r for r in fin.columns[:3] if r in bs.columns]
            vals = [fin.loc['Net Income', r] / bs.loc['Stockholders Equity', r] for r in roky if bs.loc['Stockholders Equity', r] > 0]
            if vals: roe_3y = (sum(vals) / len(vals)) * 100
            
        return safe_float(gm_3y), safe_float(nm_3y), safe_float(roe_3y)
    except:
        return current_gm, current_nm, current_roe

@st.cache_data(ttl=3600)
def fetch_all_data(df_input):
    res = []
    if df_input.empty: return res
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t in ["-", "nan", "NAN", "TICKER"]: continue
        try:
            tk = yf.Ticker(t); inf = tk.info; hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                # OCHRANA PROTI ČASOVÝM ZÓNÁM YAHOO
                if hi.index.tz is not None:
                    hi.index = hi.index.tz_localize(None)
                
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            gm_3y, nm_3y, roe_3y = fetch_historical_averages(t, c_gm, c_nm, c_roe)

            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie')), 
                "earn": row.get('Earnings Day'),
                "name": inf.get('longName', t),
                "gm_3y": gm_3y, "nm_3y": nm_3y, "roe_3y": roe_3y
            })
        except: continue
    return res

# --- BEZPEČNÉ NAČTENÍ S INDIKÁTOREM ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

if df_raw_list.empty:
    st.error("❌ Nepodařilo se načíst data z Google tabulky. Zkontroluj odkaz nebo připojení.")
    st.stop()

with st.spinner("🔄 Načítám živá data z Yahoo Finance... Prosím strpení."):
    raw_data = fetch_all_data(df_raw_list)

if not raw_data:
    st.warning("⚠️ Žádná data nebyla z Yahoo Finance stažena. Zkontroluj tickery v tabulce nebo zkus Clear Cache.")
    st.stop()

# --- 4. SIDEBAR ---
st.sidebar.markdown("### **📊 Menu**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & RSI"], label_visibility="collapsed")
st.sidebar.divider()

filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)
