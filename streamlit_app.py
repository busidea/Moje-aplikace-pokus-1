import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2.2rem; padding-bottom: 0rem; }
    .stExpander { margin-top: 4px !important; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { font-weight: bold !important; color: #004080 !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]: return 999
    try: return (pd.to_datetime(earn_val, dayfirst=True).date() - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. NAČTENÍ SEZNAMU Z GOOGLE TABULKY ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
    try:
        df = pd.read_csv(csv_url)
        # Odstranění neviditelných mezer z názvů sloupců
        df.columns = [c.strip() for c in df.columns]
        
        if 'Ticker' not in df.columns:
            st.error(f"❌ V Google tabulce chybí sloupec s názvem 'Ticker'! Nalezené sloupce: {list(df.columns)}")
            return pd.DataFrame()
            
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        if 'Kategorie' in df.columns:
            df['Kategorie'] = df['Kategorie'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error("❌ Kritická chyba při stahování Google tabulky ze strany Streamlitu!")
        st.info(f"Technický detail chyby: {e}")
        st.info(f"Zkoušené exportní URL: {csv_url}")
        return pd.DataFrame()

# --- 🧠 UNIFIKOVANÁ DATA Z YAHOO FINANCE ---
@st.cache_data(ttl=3600)
def fetch_all_stock_data(tickers):
    stock_data = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            inf = tk.info if tk.info else {}
            
            try: fin = tk.financials
            except: fin = pd.DataFrame()
            try: bs = tk.balance_sheet
            except: bs = pd.DataFrame()
            
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            gm_3y = c_gm
            if fin is not None and not fin.empty and 'Gross Profit' in fin.index and 'Total Revenue' in fin.index:
                roky = fin.columns[:3]
                vals = [fin.loc['Gross Profit', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
                if vals: gm_3y = (sum(vals) / len(vals)) * 100

            nm_3y = c_nm
            if fin is not None and not fin.empty and 'Net Income' in fin.index and 'Total Revenue' in fin.index:
                roky = fin.columns[:3]
                vals = [fin.loc['Net Income', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
                if vals: nm_3y = (sum(vals) / len(vals)) * 100

            roe_3y = c_roe
            if fin is not None and not fin.empty and bs is not None and not bs.empty and 'Net Income' in fin.index and 'Stockholders Equity' in bs.index:
                roky = [r for r in fin.columns[:3] if r in bs.columns]
                vals = [fin.loc['Net Income', r] / bs.loc['Stockholders Equity', r] for r in roky if bs.loc['Stockholders Equity', r] > 0]
                if vals: roe_3y = (sum(vals) / len(vals)) * 100

            cena_act = safe_float(inf.get('currentPrice', inf.get('regularMarketPrice', inf.get('previousClose', 0))))
            cena_prev = safe_float(inf.get('previousClose', cena_act))
            zmena = ((cena_act / cena_prev) - 1) * 100 if cena_prev > 0 else 0.0

            ma50 = safe_float(inf.get('fiftyDayAverage', 0))
            vzdalenost_ma50 = ((cena_act / ma50) - 1) * 100 if ma50 > 0 else 0.0

            stock_data[t] = {
                "name": inf.get('longName', t), 
                "cena_zive": cena_act,
                "zmena_zive": zmena,
                "vzdalenost_ma50": vzdalenost_ma50,
                "trailingPE": safe_float(inf.get('trailingPE')), 
                "forwardPE": safe_float(inf.get('forwardPE')),
                "priceToSales": safe_float(inf.get('priceToSalesTrailing12Months')), 
                "priceToBook": safe_float(inf.get('priceToBook')),
                "marketCap": safe_float(inf.get('marketCap')), 
                "freeCashflow": safe_float(inf.get('freeCashflow')),
                "grossMargins": c_gm, "gm_3y": gm_3y, "profitMargins": c_nm, "nm_3y": nm_3y, "returnOnEquity": c_roe, "roe_3y": roe_3y,
                "revenueGrowth": safe_float(inf.get('revenueGrowth', 0)) * 100, "earningsGrowth": safe_float(inf.get('earningsGrowth', 0)) * 100,
                "debtToEquity": safe_float(inf.get('debtToEquity')), "dividendYield": safe_float(inf.get('dividendYield')),
                "dividendRate": safe_float(inf.get('dividendRate')), "currency": inf.get('currency', 'USD'),
                "targetMeanPrice": safe_float(inf.get('targetMeanPrice')), "exDividendDate": inf.get('exDividendDate'), "recommendationKey": inf.get('recommendationKey', '-'),
                "trailingEps": safe_float(inf.get('trailingEps')), "bookValue": safe_float(inf.get('bookValue')), "totalRevenue": safe_float(inf.get('totalRevenue')), "sharesOutstanding": safe_float(inf.get('sharesOutstanding'))
            }
        except Exception as e:
            stock_data[t] = {}
    return stock_data

# --- INICIALIZACE A DIAGNOSTIKA ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

if df_raw_list.empty:
    st.error("🚨 POZOR: Z Google tabulky se nepodařilo načíst žádná data!")
    st.markdown("""
    **Možná rychlá řešení:**
    1. Klikněte v aplikaci vpravo nahoře na **tři tečky -> Clear cache** a aktualizujte stránku klávesou F5.
    2. Ověřte v Google Sheets, že je zapnuté sdílení pro čtení komukoliv s odkazem.
    """)
    st.stop()

vsechny_tickery = [str(t).strip().upper() for t in df_raw_list['Ticker'].dropna().unique().tolist() if str(t).strip() not in ["-", "nan", "TICKER"]]

if not vsechny_tickery:
    st.warning("⚠️ V Google tabulce nebyly nalezeny žádné platné texty tickerů ve sloupci Ticker.")
    st.stop()

with st.spinner("🚀 Aktualizuji data z trhů..."):
    data_trhu = fetch_all_stock_data(vsechny_tickery)

raw_data = []
debug_chyby_yahoo = []

for row in df_raw_list.to_dict('records'):
    t = str(row.get('Ticker', '')).strip().upper()
    kat_hodnota = str(row.get('Kategorie', '')).strip()
    
    if t not in data_trhu or not data_trhu[t]:
        debug_chyby_yahoo.append({"Ticker": t, "Kategorie v tabulce": kat_hodnota, "Problém": "Yahoo Finance pro tento ticker dnes odmítlo vrátit data (Blokace IP / Výpadek)"})
        continue
        
    fund = data_trhu[t]
    
    # Pojistka pro případ, že Yahoo vrátí cenu, ale prázdný zbytek dat (Rate Limiting)
    if fund.get("marketCap", 0) == 0:
        debug_chyby_yahoo.append({"Ticker": t, "Kategorie v tabulce": kat_hodnota, "Problém": "Yahoo vrátilo živou cenu, ale zablokovalo stažení fundamentů (Tržní kapitalizace je 0)"})
        continue

    raw_data.append({
        "t": t, "inf": fund, "vzdalenost_ma50": fund["vzdalenost_ma50"], "cena_zive": fund["cena_zive"], "zmena_zive": fund["zmena_zive"],
        "kat": kat_hodnota, "earn": row.get('Earnings Day'), "name": fund["name"],
        "gm_3y": fund["gm_3y"], "nm_3y": fund["nm_3y"], "roe_3y": fund["roe_3y"]
    })

# --- 4. SIDEBAR NAVIGATION ---
st.sidebar.markdown("### **📊 Hlavní navigace**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & Technika"], label_visibility="collapsed")

zobrazit_body = False
if stranka == "Scoring Matrix":
    st.sidebar.divider()
    zobrazit_body = st.sidebar.checkbox
