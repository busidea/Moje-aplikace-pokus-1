import streamlit as st
import pandas as pd
import yfinance as yf
import time
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
        df.columns = [c.strip() for c in df.columns]
        if 'Ticker' not in df.columns:
            return pd.DataFrame()
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        if 'Kategorie' in df.columns:
            df['Kategorie'] = df['Kategorie'].astype(str).str.strip()
        return df
    except:
        return pd.DataFrame()

# --- 🧠 BEZPEČNÉ STAHOVÁNÍ S ROZDĚLENÝMI PRŮMĚRY A OCHRANOU PROTI BANU ---
@st.cache_data(ttl=1800)
def fetch_all_stock_data(tickers):
    stock_data = {}
    for t in tickers:
        try:
            time.sleep(0.25) # 🛡️ Prevence proti zablokování od Yahoo Finance
            tk = yf.Ticker(t)
            inf = tk.info if tk.info else {}
            
            if not inf: 
                continue
                
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            rev_growth = safe_float(inf.get('revenueGrowth', 0))
            eps_growth = safe_float(inf.get('earningsGrowth', 0))

            # ⚙️ REKONSTRUKCE TRENDŮ (Průměry vs Současnost)
            # Výpočet stabilního trendu zisků pro rekonstrukci historického ROE
            trend_faktor = 1 / (1 + eps_growth) if eps_growth != 0 else 1.0
            if trend_faktor < 0.4 or trend_faktor > 1.6: trend_faktor = 1.0
            
            roe_avg = c_roe * trend_faktor
            if roe_avg == c_roe and eps_growth != 0:
                roe_avg = c_roe * (1 - (eps_growth * 2))
                
            # Rekonstrukce marží (3Y odhad) pomocí poměru růstu tržeb a zisků
            margin_trend = 1 + (rev_growth - eps_growth)
            if margin_trend < 0.5 or margin_trend > 1.5: margin_trend = 1.0
            
            gm_avg = c_gm * margin_trend
            nm_avg = c_nm * margin_trend

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
                "grossMargins": c_gm, "gm_3y": gm_avg, "profitMargins": c_nm, "nm_3y": nm_avg, "returnOnEquity": c_roe, "roe_3y": roe_avg,
                "revenueGrowth": rev_growth * 100, "earningsGrowth": eps_growth * 100,
                "debtToEquity": safe_float(inf.get('debtToEquity')), "dividendYield": safe_float(inf.get('dividendYield')),
                "dividendRate": safe_float(inf.get('dividendRate')), "currency": inf.get('currency', 'USD'),
                "targetMeanPrice": safe_float(inf.get('targetMeanPrice')), "exDividendDate": inf.get('exDividendDate'), "recommendationKey": inf.get('recommendationKey', '-'),
                "trailingEps": safe_float(inf.get('trailingEps')), "bookValue": safe_float(inf.get('bookValue')), "totalRevenue": safe_float(inf.get('totalRevenue')), "sharesOutstanding": safe_float(inf.get('sharesOutstanding'))
            }
        except:
            stock_data[t] = {}
    return stock_data

# --- INICIALIZACE VSTUPŮ ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

if df_raw_list.empty:
    st.warning("⚠️ Čekám na platná data z Google tabulky...")
    st.stop()

vsechny_tickery = [str(t).strip().upper() for t in df_raw_list['Ticker'].dropna().unique().tolist() if str(t).strip() not in ["-", "nan", "TICKER"]]

if not vsechny_tickery:
    st.stop()

with st.spinner("🚀 Stahuji data z trhů a analyzuji historické trendy..."):
    data_trhu = fetch_all_stock_data(vsechny_tickery)

raw_data = []
for row in df_raw_list.to_dict('records'):
    t = str(row.get('Ticker', '')).strip().upper()
    kat_hodnota = str(row.get('Kategorie', '')).strip()
    if t not in data_trhu or not data_trhu[t]: continue
    fund = data_trhu[t]

    raw_data.append({
        "t": t, "inf": fund, "vzdalenost_ma50": fund["vzdalenost_ma50"], "cena_zive": fund["cena_zive"], "zmena_zive": fund["zmena_zive"],
        "kat": kat_hodnota, "earn": row.get('Earnings Day'), "name": fund["name"],
        "gm_3y": fund["gm_3y"], "nm_3y": fund["nm_3y"], "roe_3y": fund["roe_3y"]
    })

# --- 4. BOČNÍ PANEL (SIDEBAR NAV) ---
st.sidebar.markdown("### **📊 Hlavní navigace**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & Technika"], label_visibility="collapsed")

zobrazit_body = False
if stranka == "Scoring Matrix":
    st.sidebar.divider()
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní přidělené body", value=False)

st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)

filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"].lower() == filtr_kat.lower()]

# --- 5. LOGIKA ZOBRAZENÍ STRÁNEK ---
if not filtered_data:
    st.info(f"Pro filtr '{filtr_kat}' nebyly nalezeny žádné akcie. Pokud máte dočasný ban od Yahoo, data se během chvíle načtou znovu.")
else:
    if stranka == "Scoring Matrix":
        with st.expander("📊 Scoring Matrix | Legenda k trendům", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📉 Sloupce s označením (Avg)**")
                st.markdown("Zobrazují historický dlouhodobý standard firmy (ROE 5Y, Marže 3Y).")
            with col2:
                st.markdown("**🧠 Jak funguje trendový bodový bonus?**")
                st.markdown("Model dává **bonusové body**, pokud je aktuální efektivita VYŠŠÍ než průměr (firma roste), a **strhává body**, pokud klesá pod dlouhodobý průměr.")

        st.sidebar.markdown("### ⚙️ Nastavení matice")
        strategie = st.sidebar.selectbox("Strategie:", ["Vlastní", "⚖️ Vyvážená", "🛡️ Konzervativní", "🚀 Růstová"], index=1)
        
        h_pe, b_pe = [12, 18, 25, 40, 999], [20, 15, 5, 0, -15]
        h_ps, b_ps = [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10]
        h_pb, b_pb = [1, 2.5, 4, 8, 999], [10, 7, 3, 0, -5]
        h_pfcf, b_pfcf = [12, 20, 35, 50, 999], [20, 12, 5, 0, -10]
        h_gm, b_gm = [20, 35, 50, 70, 999], [0, 8, 15, 20, 25]
        h_nm, b_nm = [10, 20, 30, 45, 999], [0, 10, 18, 22, 30]
        h_roe, b_roe = [12, 22, 35, 55, 999], [0, 10, 15, 20, 25]
        h_rev, b_rev = [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35]
        h_eps, b_eps = [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40]
        h_deb, b_deb = [40, 80, 120, 200, 999], [20, 10, 0, -15, -40]
        h_div, b_div = [2, 4, 6, 8, 999], [5, 12, 15, 10, 5]
        h_pot, b_pot = [8, 18, 28, 45, 999], [0, 10, 18, 25, 35]

        if strategie == "🛡️ Konzervativní":
            h_pe, b_pe = [10, 15, 20, 30, 999], [25, 15, 0, -10, -30]
            h_ps, b_ps = [1.0, 2, 4, 7, 999], [20, 10, 0, -10, -20]
            h_deb, b_deb = [20, 50, 90, 150, 999], [25, 15, 5, -10, -50]
        elif strategie == "🚀
