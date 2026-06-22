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

# --- 🧠 BEZPEČNÉ STAHOVÁNÍ BEZ RIZIKA SELHÁNÍ TRENDŮ ---
@st.cache_data(ttl=1800)
def fetch_all_stock_data(tickers):
    stock_data = {}
    for t in tickers:
        try:
            time.sleep(0.25) # 🛡️ Ochrana proti banu
            tk = yf.Ticker(t)
            inf = tk.info
            
            if not inf or not isinstance(inf, dict): 
                continue
                
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            rev_growth = safe_float(inf.get('revenueGrowth', 0)) * 100
            eps_growth = safe_float(inf.get('earningsGrowth', 0)) * 100

            # 🛡️ STABILNÍ HISTORICKÉ ODHADY (Pokud selže výpočet, použije se aktuální stav)
            gm_avg = c_gm
            nm_avg = c_nm
            roe_avg = c_roe

            # Bezpečný pokus o simulaci historického trendu
            if eps_growth != 0:
                if -50 < eps_growth < 100: # Jen pro rozumné hodnoty růstu
                    roe_avg = c_roe * (1 - (eps_growth / 100) * 0.3)
                    margin_trend = 1 - ((rev_growth - eps_growth) / 100) * 0.1
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
                "revenueGrowth": rev_growth, "earningsGrowth": eps_growth,
                "debtToEquity": safe_float(inf.get('debtToEquity')), "dividendYield": safe_float(inf.get('dividendYield')),
                "dividendRate": safe_float(inf.get('dividendRate')), "currency": inf.get('currency', 'USD'),
                "targetMeanPrice": safe_float(inf.get('targetMeanPrice')), "exDividendDate": inf.get('exDividendDate'), "recommendationKey": inf.get('recommendationKey', '-'),
                "trailingEps": safe_float(inf.get('trailingEps')), "bookValue": safe_float(inf.get('bookValue')), "totalRevenue": safe_float(inf.get('totalRevenue')), "sharesOutstanding": safe_float(inf.get('sharesOutstanding'))
            }
        except:
            pass # Pokud jedna akcie selže, cyklus pokračuje dál a neshodí zbytek
    return stock_data

# --- INICIALIZACE VSTUPŮ ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

if df_raw_list.empty:
    st.warning("⚠️ Čekám na platná data z Google tabulky...")
    st.stop()

vsechny_tickery = [str(t).strip().upper() for t in df_raw_list['Ticker'].dropna().unique().tolist() if str(t).strip() not in ["-", "nan", "TICKER"]]

if not vsechny_tickery:
    st.stop()

with st.spinner("🚀 Synchronizuji data z trhů..."):
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
    st.info(f"V kategorii '{filtr_kat}' momentálně nejsou žádná data. Přepněte filtr na 'Vše' nebo zkontrolujte sloupce v Google tabulce.")
else:
    if stranka == "Scoring Matrix":
        with st.expander("📊 Scoring Matrix | Legenda k trendům", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📉 Sloupce s označením (Avg)**")
                st.markdown("Zobrazují historickou základnu firmy (ROE a Marže).")
            with col2:
                st.markdown("**🧠 Jak funguje trendový bodový bonus?**")
                st.markdown("Model dává **bonusové body**, pokud se aktuální stav zlepšuje oproti průměru, a **strhává**, pokud klesá.")

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

        if "Konzervativní" in strategie:
            h_pe, b_pe = [10, 15, 20, 30, 999], [25, 15, 0, -10, -30]
            h_ps, b_ps = [1.0, 2, 4, 7, 999], [20, 10, 0, -10, -20]
            h_deb, b_deb = [20, 50, 90, 150, 999], [25, 15, 5, -10, -50]
        elif "Růstová" in strategie:
            h_pe, b_pe = [20, 35, 50, 80, 999], [15, 25, 15, 5, -5]
            h_ps, b_ps = [3, 6, 12, 20, 999], [10, 15, 20, 5, -10]
            h_rev, b_rev = [5, 15, 30, 50, 999], [-15, 10, 20, 35, 50]

        def vytvor_p(nazev, zk, def_h, def_b):
            d = []
            if strategie == "Vlastní":
                with st.sidebar.expander(f"📊 {nazev}", expanded=False):
                    for i in range(5):
                        c1, c2 = st.columns(2)
                        h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
                        b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
                        d.append({"h": h, "b": b})
            else:
                for i in range(5): d.append({"h": def_h[i], "b": def_b[i]})
            return d

        p_pe = vytvor_p("P/E", "pe", h_pe, b_pe)
        p_ps = vytvor_p("P/S", "ps", h_ps, b_ps)
        p_pb = vytvor_p("P/B", "pb", h_pb, b_pb)
        p_pfcf = vytvor_p("P/FCF", "pfcf", h_pfcf, b_pfcf)
        p_gm = vytvor_p("H-Marže", "gm", h_gm, b_gm)
        p_nm = vytvor_p("Č-Marže", "nm", h_nm, b_nm)
        p_roe = vytvor_p("ROE", "roe", h_roe, b_roe)
        p_rev = vytvor_p("Tržby y/y", "rev", h_rev, b_rev)
        p_eps = vytvor_p("Zisk y/y", "eps", h_eps, b_eps)
        p_deb = vytvor_p("Dluh D/E", "deb", h_deb, b_deb)
        p_div = vytvor_p("Div. výnos", "div", h_div, b_div)
        p_pot = vytvor_p("Potenciál", "pot", h_pot, b_pot)

        w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
        w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
        w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
        w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

        mapping_keys = ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže (Avg)", "Č-Marže", "Č-Marže (Avg)", "ROE", "ROE (Avg)", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
        pct_cols = ["Změna", "H-Marže", "H-Marže (Avg)", "Č-Marže", "Č-Marže (Avg)", "ROE", "ROE (Avg)", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
        
        m_rows = []
        for item in filtered_data:
            inf = item["inf"]; t = item["t"]; name = item["name"]
            pe_tr = inf.get("trailingPE", 0) or inf.get("forwardPE", 0)
            pe_fwd = inf.get("forwardPE", 0) or pe_tr
            d_yield = inf.get("dividendYield", 0)
            if d_yield < 0.2 and d_yield > 0: d_yield *= 100 

            raw_vals = {
                "Cena": item["cena_zive"], "Změna": item["zmena_zive"],
                "P/E": pe_tr, "Forward P/E": pe_fwd, "P/S": inf.get("priceToSales", 0), 
                "P/B": inf.get("priceToBook", 0), "P/FCF": inf.get("marketCap", 0)/inf.get("freeCashflow", 1) if inf.get("freeCashflow", 0) else 0,
                "H-Marže": inf.get("grossMargins", 0), "H-Marže (Avg)": item["gm_3y"],
                "Č-Marže": inf.get("profitMargins", 0), "Č-Marže (Avg)": item["nm_3y"],
                "ROE": inf.get("returnOnEquity", 0), "ROE (Avg)": item["roe_3y"],
                "Tržby y/y": inf.get("revenueGrowth", 0), "Zisk y/y": inf.get("earningsGrowth", 0), "Dluh D/E": inf.get("debtToEquity", 0), 
                "Div. výnos": d_yield, "Potenciál": ((inf.get("targetMeanPrice", 0)/item["cena_zive"])-1)*100 if inf.get("targetMeanPrice", 0) and item["cena_zive"] > 0 else 0
            }

            base_pe_points = get_b(raw_vals["P/E"], p_pe)
            adjusted_pe_points = base_pe_points
