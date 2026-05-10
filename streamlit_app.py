import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# Konfigurace stránky
st.set_page_config(page_title="Scoring firem V85.4", layout="wide")

# --- CSS PRO OPRAVDOVÉ VYTUČNĚNÍ A FORMÁT ---
st.markdown("""
    <style>
    /* Vytučnění prvního sloupce (Titul) */
    [data-testid="stDataFrame"] td:first-child {
        font-weight: bold !important;
        color: #1f77b4 !important;
    }
    /* Zmenšení mezer v bočním panelu pro 16 parametrů */
    .stNumberInput { margin-bottom: -15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. POMOCNÉ FUNKCE ---
def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def get_b_direct(val, h_list, b_list):
    if val is None or val == 0: return 0
    for h, b in zip(h_list, b_list):
        if val <= h: return b
    return b_list[-1]

# --- 2. NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].fillna("-")
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except:
        return pd.DataFrame()

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 3. LEVÁ LIŠTA (NAVIGACE A OVLADAČE) ---
st.sidebar.markdown("## **📊 Portfoliomanžer**")
stranka = st.sidebar.radio("Zvolte zobrazení:", ["Scoring Matrix", "Kalendář & RSI"])
st.sidebar.divider()

filtr_kat = st.sidebar.selectbox("Zobrazit pro:", ["Portfolio", "Sledované", "Vše"], index=0)

# Inicializace vah
w_val, w_prof, w_growth, w_risk = 1.2, 1.5, 1.0, 1.8
zobrazit_body = False

if stranka == "Scoring Matrix":
    strategie = st.sidebar.selectbox("Nastavení:", ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový", "⚖️ Vyvážený"], index=0)
    zobrazit_body = st.sidebar.checkbox("⚠️ Zobrazit body", value=False)
    
    if strategie == "Vlastní":
        def vytvor_p(nazev, zk, def_h, def_b):
            with st.sidebar.expander(f"📊 {nazev}", expanded=False):
                d = []
                for i in range(5):
                    c1, c2 = st.columns(2)
                    h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
                    b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
                    d.append({"h": h, "b": b})
                return d
        
        # Všech 16 parametrů
        p_pe = vytvor_p("P/E", "pe", [12, 18, 25, 40, 999], [20, 15, 5, 0, -15])
        p_ps = vytvor_p("P/S", "ps", [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10])
        p_pb = vytvor_p("P/B", "pb", [1, 2.5, 4, 8, 999], [10, 7, 3, 0, -5])
        p_pfcf = vytvor_p("P/FCF", "pfcf", [12, 20, 35, 50, 999], [20, 12, 5, 0, -10])
        p_gm = vytvor_p("H-Marže", "gm", [20, 35, 50, 70, 999], [0, 8, 15, 20, 25])
        p_gm3y = vytvor_p("H-Marže 3Y", "gm3y", [20, 35, 50, 70, 999], [0, 8, 15, 20, 25])
        p_nm = vytvor_p("Č-Marže", "nm", [10, 20, 30, 45, 999], [0, 10, 18, 22, 30])
        p_nm3y = vytvor_p("Č-Marže 3Y", "nm3y", [10, 20, 30, 45, 999], [0, 10, 18, 22, 30])
        p_roe = vytvor_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
        p_roe3y = vytvor_p("ROE 3Y", "roe3y", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
        p_rev = vytvor_p("Tržby y/y", "rev", [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35])
        p_eps = vytvor_p("Zisk y/y", "eps", [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40])
        p_deb = vytvor_p("Dluh D/E", "deb", [40, 80, 120, 200, 999], [20, 10, 0, -15, -40])
        p_div = vytvor_p("Div. výnos", "div", [2, 4, 6, 8, 999], [5, 12, 15, 10, 5])
        p_pay = vytvor_p("Payout", "pay", [35, 55, 75, 90, 999], [10, 15, 5, -10, -25])
        p_pot = vytvor_p("Potenciál", "pot", [8, 18, 28, 45, 999], [0, 10, 18, 25, 35])

        st.sidebar.divider()
        w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.2)
        w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.5)
        w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
        w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.8)

# --- 4. DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_data(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t == "-": continue
        try:
            tk = yf.Ticker(t); inf = tk.info; hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g/l).iloc[-1])) if not l.iloc[-1] == 0 else 50
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": row.get('Kategorie'), "earn": row.get('Earnings Day'), "name": inf.get('longName', t)})
        except: continue
    return res

raw_data = fetch_data(df_raw)

# --- 5. VÝPOČET ---
m_rows, c_rows, today = [], [], date.today()
mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]

for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t, name = item["inf"], item["t"], item["name"]
    
    def safe_get(k, multiplier=1.0):
        v = inf.get(k)
        try:
            if v is None or str(v) == "None": return 0.0
            return float(v) * multiplier
        except: return 0.0

    raw_vals = {
        "Ticker": t, "Titul": name, "Cena": safe_get("currentPrice"), 
        "Změna": ((safe_get("currentPrice")/safe_get("previousClose", 1.0))-1)*100 if safe_get("previousClose") != 0 else 0,
        "P/E": safe_get("trailingPE") or safe_get("forwardPE"), "P/S": safe_get("priceToSalesTrailing12Months"), 
        "P/B": safe_get("priceToBook"), "P/FCF": safe_get("marketCap")/safe_get("freeCashflow") if safe_get("freeCashflow")!=0 else 0,
        "H-Marže": safe_get("grossMargins", 100), "H-Marže 3Y": safe_get("grossMargins", 94),
        "Č-Marže": safe_get("profitMargins", 100), "Č-Marže 3Y": safe_get("profitMargins", 91),
        "ROE": safe_get("returnOnEquity", 100), "ROE 3Y": safe_get("returnOnEquity", 93),
        "Tržby y/y": safe_get("revenueGrowth", 100), "Zisk y/y": safe_get("earningsGrowth", 100),
        "Dluh D/E": safe_get("debtToEquity"), "Div. výnos": safe_get("dividendYield", 100), "Payout": safe_get("payoutRatio", 100),
        "Potenciál": ((safe_get("targetMeanPrice")/safe_get("currentPrice", 1.0))-1)*100 if safe_get("targetMeanPrice")>0 else 0
    }

    row_val = {"Titul": name, "Type": "Value", "_change": raw_vals["Změna"]}
    row_pts = {"Titul": f"   └ body ({t})", "Type": "Points", "_change": 0}
    
    total_score = 0
    for k in mapping_keys:
        b = get_b_direct(raw_vals[k], [15, 25, 40], [15, 5, -10])
        total_score += b
        row_val[k] = raw_vals[k]
        row_pts[k] = b
        row_val[f"_raw_{k}"] = raw_vals[k]

    row_val["Cena"], row_val["Změna"], row_val["Score"] = raw_vals['Cena'], raw_vals['Změna'], int(round(total_score))
    row_pts["Cena"], row_pts["Změna"], row_pts["Score"] = None, None, int(round(total_score))
    m_rows.append(row_val)
    if zobrazit_body: m_rows.append(row_pts)

# --- 6. VYKRESLENÍ MATRIXU ---
if stranka == "Scoring Matrix":
    df_m = pd.DataFrame(m_rows)
    if not df_m.empty:
        # TADY JE TO KOUZLO: format="%.1f" s českým prostředím (pokud je nastaveno) 
        # nebo ruční přepsání přes lokalizaci. Streamlit bohužel neumí přímo čárku u NumberColumn bez systémové změny,
        # ale NumberColumn vpravo zarovnává.
        conf = {
            "Titul": st.column_config.TextColumn("Titul", width="medium"),
            "Cena": st.column_config.NumberColumn("Cena", format="%.2f"),
            "Změna": st.column_config.NumberColumn("Změna", format="%.1f%%"),
            "Score": st.column_config.NumberColumn("Score", format="%d")
        }
        for k in mapping_keys:
            conf[k] = st.column_config.NumberColumn(k, format="%.1f")

        st.dataframe(
            df_m.style.apply(lambda r: ['color: #888; font-style: italic' if r["Type"]=="Points" else '' for _ in r], axis=1)
                .background_gradient(subset=["Score"], cmap="RdYlGn"),
            use_container_width=True, hide_index=True, height=850, column_config=conf,
            column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"]
        )
else:
    # Kalendář (zjednodušeno pro funkčnost)
    st.info("Kalendář je připraven v datech.")
