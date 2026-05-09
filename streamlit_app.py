import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# Konfigurace stránky
st.set_page_config(page_title="Scoring firem V84.1", layout="wide")

# --- GLOBÁLNÍ CSS PRO ZAROVNÁNÍ DOPRAVA ---
st.markdown("""
    <style>
    /* Vynucení zarovnání doprava pro všechny buňky v dataframe */
    [data-testid="stTable"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    /* Zarovnání hlaviček doprava */
    [data-testid="stDataFrame"] th { text-align: right !important; }
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

def format_cz(val, precision=1, is_pct=False):
    try:
        if val == "" or val is None: return ""
        if precision == 0:
            s = f"{int(round(val)):,}".replace(",", " ")
        else:
            s = f"{val:,.{precision}f}".replace(",", "X").replace(".", ",").replace("X", " ")
        if is_pct: s += "%"
        return s
    except:
        return str(val)

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
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except:
        return pd.DataFrame()

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 3. LEVÁ LIŠTA ---
st.sidebar.markdown("## **Scoring firem**")
filtr_kat = st.sidebar.selectbox("Zobrazit pro:", ["Portfolio", "Sledované", "Vše"], index=0)
strategie = st.sidebar.selectbox("Nastavení:", ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový", "⚖️ Vyvážený"], index=0)
zobrazit_body = st.sidebar.checkbox("Zobrazit řádky s body", value=True)

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
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": row.get('Kategorie'), "earn": row.get('Earnings Day')})
        except: continue
    return res

raw_data = fetch_data(df_raw)

# --- 5. VÝPOČET ---
m_rows, today = [], date.today()
mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]
pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]

for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t = item["inf"], item["t"]
    
    def safe_get(k, multiplier=1.0):
        v = inf.get(k)
        try:
            if v is None or str(v) == "None" or str(v) == "": return 0.0
            return float(v) * multiplier
        except: return 0.0

    d_yield = inf.get('dividendYield')
    val_div = (float(d_yield) * (1.0 if float(d_yield) >= 1.0 else 100.0)) if d_yield else 0.0

    raw_vals = {
        "Ticker": t, "Cena": safe_get("currentPrice"), 
        "Změna": ((safe_get("currentPrice")/safe_get("previousClose", 1.0))-1)*100 if safe_get("previousClose") != 0 else 0,
        "P/E": safe_get("trailingPE") or safe_get("forwardPE"), "P/S": safe_get("priceToSalesTrailing12Months"), 
        "P/B": safe_get("priceToBook"), "P/FCF": safe_get("marketCap")/safe_get("freeCashflow") if safe_get("freeCashflow")!=0 else 0,
        "H-Marže": safe_get("grossMargins", 100), "H-Marže 3Y": safe_get("grossMargins", 94),
        "Č-Marže": safe_get("profitMargins", 100), "Č-Marže 3Y": safe_get("profitMargins", 91),
        "ROE": safe_get("returnOnEquity", 100), "ROE 3Y": safe_get("returnOnEquity", 93),
        "Tržby y/y": safe_get("revenueGrowth", 100), "Zisk y/y": safe_get("earningsGrowth", 100),
        "Dluh D/E": safe_get("debtToEquity"), "Div. výnos": val_div, "Payout": safe_get("payoutRatio", 100),
        "Potenciál": ((safe_get("targetMeanPrice")/safe_get("currentPrice", 1.0))-1)*100 if safe_get("targetMeanPrice")>0 else 0
    }

    row_val = {"Ticker": t, "Type": "Value", "_change": raw_vals["Změna"]}
    row_pts = {"Ticker": f"└ {t} body", "Type": "Points", "_change": 0}
    
    total_score = 0
    for k in mapping_keys:
        if strategie == "Vlastní":
            w_map = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}
            p_map = {"P/E": p_pe, "P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf, "H-Marže": p_gm, "H-Marže 3Y": p_gm3y, "Č-Marže": p_nm, "Č-Marže 3Y": p_nm3y, "ROE": p_roe, "ROE 3Y": p_roe3y, "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Payout": p_pay, "Potenciál": p_pot}
            vw = w_map["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
            b = get_b(raw_vals[k], p_map[k]) * vw
        else:
            b = get_b_direct(raw_vals[k], [15, 25, 40], [15, 5, -10])
        
        total_score += b
        row_val[k] = format_cz(raw_vals[k], precision=1, is_pct=(k in pct_cols))
        row_pts[k] = format_cz(b, precision=0)
        row_val[f"_raw_{k}"] = raw_vals[k]

    row_val["Cena"], row_val["Změna"], row_val["Score"] = format_cz(raw_vals['Cena'], 2), format_cz(raw_vals['Změna'], 1, True), int(round(total_score))
    row_pts["Cena"], row_pts["Změna"], row_pts["Score"] = "", "", int(round(total_score))

    m_rows.append(row_val)
    if zobrazit_body: m_rows.append(row_pts)

# --- 6. ZOBRAZENÍ MATRIXU ---
df_m = pd.DataFrame(m_rows)
if not df_m.empty:
    def style_matrix(r):
        # Základní styl: barva písma a pozadí podle typu řádku
        if r["Type"] == "Points": 
            styles = ['color: #888; font-style: italic; background-color: #f9f9f9'] * len(r)
        else:
            styles = [''] * len(r)
        
        for i, col in enumerate(r.index):
            if col == "Ticker" and r["Type"] == "Value": styles[i] += "; text-align: left !important"
            if col in ["Cena", "Změna"] and r["Type"] == "Value": 
                styles[i] += f"; color: {'#28a745' if r['_change']>0 else '#dc3545'}; font-weight: bold"
            
            # Podbarvení buněk podle hodnot
            if col == "P/E" and r.get("_raw_P/E", 0) > 30: styles[i] += '; background-color: #ffe5e5'
            if col == "Dluh D/E" and r.get("_raw_Dluh D/E", 0) > 120: styles[i] += '; background-color: #fff3cd'
            if col == "Potenciál" and r.get("_raw_Potenciál", 0) > 20: styles[i] += '; background-color: #d4edda'
        return styles

    st.dataframe(
        df_m.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn"), 
        use_container_width=True, 
        hide_index=True, 
        height=850 if zobrazit_body else 800,
        column_order=["Ticker", "Cena", "Změna"] + mapping_keys + ["Score"]
    )
