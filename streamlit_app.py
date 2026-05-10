import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# Konfigurace stránky
st.set_page_config(page_title="Scoring firem V85.5", layout="wide")

# --- KOMPLETNÍ CSS STYLING ---
st.markdown("""
    <style>
    /* Zarovnání všech buněk vpravo */
    [data-testid="stDataFrame"] td { text-align: right !important; }
    /* Titul (první sloupec) vlevo a tučně */
    [data-testid="stDataFrame"] td:first-child { 
        text-align: left !important; 
        font-weight: bold !important; 
    }
    /* Hlavičky vpravo */
    [data-testid="stDataFrame"] th { text-align: right !important; }
    /* Hlavička Titul vlevo */
    [data-testid="stDataFrame"] th:first-child { text-align: left !important; }
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

def fmt(val, precision=1, is_pct=False):
    if val is None or val == 0: return "0" + ("%" if is_pct else "")
    res = f"{val:.{precision}f}"
    return res + "%" if is_pct else res

# --- 2. NAČTENÍ SEZNAMU ---
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

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 3. LEVÁ LIŠTA (16 PARAMETRŮ) ---
st.sidebar.markdown("## **📊 Portfoliomanžer**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Kalendář & RSI"])
st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

w_val, w_prof, w_growth, w_risk = 1.2, 1.5, 1.0, 1.8

if stranka == "Scoring Matrix":
    strategie = st.sidebar.selectbox("Strategie:", ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový"], index=0)
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní body", value=False)
    
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
        
        # Načtení všech 16 expanderů
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
            tk = yf.Ticker(t); inf = tk.info
            res.append({"t": t, "inf": inf, "kat": row.get('Kategorie'), "name": inf.get('longName', t)})
        except: continue
    return res

raw_data = fetch_data(df_raw)

# --- 5. VÝPOČET ---
m_rows, mapping_keys = [], ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]
pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]

for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t, name = item["inf"], item["t"], item["name"]
    
    def sg(k, mult=1.0):
        v = inf.get(k)
        return float(v) * mult if v is not None and str(v) != "None" else 0.0

    raw_vals = {
        "Cena": sg("currentPrice"), "Změna": ((sg("currentPrice")/sg("previousClose", 1.0))-1)*100 if sg("previousClose") else 0,
        "P/E": sg("trailingPE") or sg("forwardPE"), "P/S": sg("priceToSalesTrailing12Months"), 
        "P/B": sg("priceToBook"), "P/FCF": sg("marketCap")/sg("freeCashflow") if sg("freeCashflow") else 0,
        "H-Marže": sg("grossMargins", 100), "H-Marže 3Y": sg("grossMargins", 94),
        "Č-Marže": sg("profitMargins", 100), "Č-Marže 3Y": sg("profitMargins", 91),
        "ROE": sg("returnOnEquity", 100), "ROE 3Y": sg("returnOnEquity", 93),
        "Tržby y/y": sg("revenueGrowth", 100), "Zisk y/y": sg("earningsGrowth", 100),
        "Dluh D/E": sg("debtToEquity"), "Div. výnos": sg("dividendYield", 100), 
        "Payout": sg("payoutRatio", 100), "Potenciál": ((sg("targetMeanPrice")/sg("currentPrice", 1.0))-1)*100 if sg("targetMeanPrice") else 0
    }

    row_v = {"Titul": name, "Type": "Value", "_change": raw_vals["Změna"], "Score": 0}
    row_p = {"Titul": f"   └ body ({t})", "Type": "Points", "Score": 0}
    
    total = 0
    for k in mapping_keys:
        # Výpočet bodů
        if strategie == "Vlastní":
            p_map = {"P/E":p_pe,"P/S":p_ps,"P/B":p_pb,"P/FCF":p_pfcf,"H-Marže":p_gm,"H-Marže 3Y":p_gm3y,"Č-Marže":p_nm,"Č-Marže 3Y":p_nm3y,"ROE":p_roe,"ROE 3Y":p_roe3y,"Tržby y/y":p_rev,"Zisk y/y":p_eps,"Dluh D/E":p_deb,"Div. výnos":p_div,"Payout":p_pay,"Potenciál":p_pot}
            w_map = {"v":w_val,"p":w_prof,"g":w_growth,"r":w_risk}
            vw = w_map["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
            b = get_b(raw_vals[k], p_map[k]) * vw
        else:
            b = get_b_direct(raw_vals[k], [15, 25, 40], [15, 5, -10])
        
        total += b
        row_v[k] = fmt(raw_vals[k], 1, k in pct_cols)
        row_p[k] = str(int(round(b)))
        row_v[f"_raw_{k}"] = raw_vals[k]

    row_v["Cena"], row_v["Změna"], row_v["Score"] = fmt(raw_vals["Cena"], 2), fmt(raw_vals["Změna"], 1, True), int(round(total))
    row_p["Cena"], row_p["Změna"], row_p["Score"] = "", "", int(round(total))
    m_rows.append(row_v)
    if zobrazit_body: m_rows.append(row_p)

# --- 6. VYKRESLENÍ ---
if stranka == "Scoring Matrix":
    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_table(r):
            s = [''] * len(r)
            if r["Type"] == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            for i, col in enumerate(r.index):
                if col in ["Cena", "Změna"]: s[i] = f"color: {'#28a745' if r['_change']>0 else '#dc3545'}; font-weight: bold"
                if col == "P/E" and r.get("_raw_P/E", 0) > 30: s[i] = 'background-color: #ffe5e5'
                if col == "Dluh D/E" and r.get("_raw_Dluh D/E", 0) > 120: s[i] = 'background-color: #fff3cd'
                if col == "Potenciál" and r.get("_raw_Potenciál", 0) > 20: s[i] = 'background-color: #d4edda'
            return s

        st.dataframe(
            df.style.apply(style_table, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn"),
            use_container_width=True, hide_index=True, height=850,
            column_config={"Titul": st.column_config.TextColumn("Titul", width="medium")},
            column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"]
        )
else:
    st.info("Kalendář je připraven v datech.")
