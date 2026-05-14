import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- KONFIGURACE ---
st.set_page_config(page_title="Scoring firem V86.5", layout="wide")

# CSS pro vytučnění prvního sloupce a barvu názvů
st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { 
        text-align: left !important; 
        font-weight: bold !important;
        color: #003366 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. POMOCNÉ FUNKCE ---
def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]:
        return 999
    try:
        dt = pd.to_datetime(earn_val, dayfirst=True).date()
        return (dt - today).days
    except:
        return 999

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
    if val is None or val == 0: return "0.0" + ("%" if is_pct else "")
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

# --- 3. LEVÁ LIŠTA (OVLADAČE) ---
st.sidebar.markdown("## **📊 Portfoliomanžer**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Kalendář & RSI"])
st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

zobrazit_body = False
w_val, w_prof, w_growth, w_risk = 1.0, 1.0, 1.0, 1.0

if stranka == "Scoring Matrix":
    hodnoceni = st.sidebar.selectbox("Hodnocení:", ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový"], index=0)
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní body", value=False)
    
    def vytvor_p(nazev, zk, def_h, def_b, viditelne=True):
        if viditelne:
            with st.sidebar.expander(f"📊 {nazev}", expanded=False):
                d = []
                for i in range(5):
                    c1, c2 = st.columns(2)
                    h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
                    b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
                    d.append({"h": h, "b": b})
                return d
        return [{"h": h, "b": b} for h, b in zip(def_h, def_b)]

    is_vlastni = (hodnoceni == "Vlastní")
    p_pe = vytvor_p("P/E", "pe", [12, 18, 25, 40, 999], [20, 15, 5, 0, -15], is_vlastni)
    p_ps = vytvor_p("P/S", "ps", [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10], is_vlastni)
    p_pb = vytvor_p("P/B", "pb", [1, 2.5, 4, 8, 999], [10, 7, 3, 0, -5], is_vlastni)
    p_pfcf = vytvor_p("P/FCF", "pfcf", [12, 20, 35, 50, 999], [20, 12, 5, 0, -10], is_vlastni)
    p_gm = vytvor_p("H-Marže", "gm", [20, 35, 50, 70, 999], [0, 8, 15, 20, 25], is_vlastni)
    p_nm = vytvor_p("Č-Marže", "nm", [10, 20, 30, 45, 999], [0, 10, 18, 22, 30], is_vlastni)
    p_roe = vytvor_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25], is_vlastni)
    p_rev = vytvor_p("Tržby y/y", "rev", [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35], is_vlastni)
    p_eps = vytvor_p("Zisk y/y", "eps", [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40], is_vlastni)
    p_deb = vytvor_p("Dluh D/E", "deb", [40, 80, 120, 200, 999], [20, 10, 0, -15, -40], is_vlastni)
    p_div = vytvor_p("Div. výnos", "div", [2, 4, 6, 8, 999], [5, 12, 15, 10, 5], is_vlastni)
    p_pot = vytvor_p("Potenciál", "pot", [8, 18, 28, 45, 999], [0, 10, 18, 25, 35], is_vlastni)
    
    if is_vlastni:
        st.sidebar.divider()
        w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
        w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
        w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
        w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

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
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": str(row.get('Kategorie')), "earn": row.get('Earnings Day'), "name": inf.get('longName', t)})
        except: continue
    return res

raw_data = fetch_data(df_raw)

# --- 5. ZPRACOVÁNÍ ---
m_rows, c_rows, today = [], [], date.today()
mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
pct_cols = ["Změna", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"]

for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t, name = item["inf"], item["t"], item["name"]
    def sg(k, mult=1.0):
        v = inf.get(k); return float(v) * mult if v is not None and str(v) != "None" else 0.0

    div_val = (sg("dividendYield") * 100)
    if div_val > 50: div_val /= 100

    raw_vals = {
        "Cena": sg("currentPrice"), "Změna": ((sg("currentPrice")/sg("previousClose", 1.0))-1)*100 if sg("previousClose") else 0,
        "P/E": sg("trailingPE") or sg("forwardPE"), "P/S": sg("priceToSalesTrailing12Months"), 
        "P/B": sg("priceToBook"), "P/FCF": sg("marketCap")/sg("freeCashflow") if sg("freeCashflow") else 0,
        "H-Marže": sg("grossMargins", 100), "Č-Marže": sg("profitMargins", 100), "ROE": sg("returnOnEquity", 100), 
        "Tržby y/y": sg("revenueGrowth", 100), "Zisk y/y": sg("earningsGrowth", 100), "Dluh D/E": sg("debtToEquity"), 
        "Div. výnos": div_val, "Potenciál": ((sg("targetMeanPrice")/sg("currentPrice", 1.0))-1)*100 if sg("targetMeanPrice") else 0
    }

    total = 0
    row_p = {"Titul": f"   └ body ({t})", "Type": "Points"}
    p_map = {"P/E":p_pe,"P/S":p_ps,"P/B":p_pb,"P/FCF":p_pfcf,"H-Marže":p_gm,"Č-Marže":p_nm,"ROE":p_roe,"Tržby y/y":p_rev,"Zisk y/y":p_eps,"Dluh D/E":p_deb,"Div. výnos":p_div,"Potenciál":p_pot}
    w_map = {"v":w_val,"p":w_prof,"g":w_growth,"r":w_risk}
    
    for k in mapping_keys:
        vw = w_map["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
        b = get_b(raw_vals[k], p_map[k]) * vw
        total += b
        row_p[k] = str(int(round(b)))

    row_v = {"Titul": name, "Type": "Value", "_change": raw_vals["Změna"], "Score": int(total)}
    for k in mapping_keys:
        row_v[k] = fmt(raw_vals[k], 1, k in pct_cols)
        row_v[f"_raw_{k}"] = raw_vals[k]
    row_v["Cena"], row_v["Změna"] = fmt(raw_vals["Cena"], 2), fmt(raw_vals["Změna"], 1, True)
    
    m_rows.append(row_v)
    if zobrazit_body: m_rows.append(row_p)

    days_to = safe_date_diff(item["earn"], today)
    ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
    c_rows.append({
        "Titul": name, "Ticker": t, "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", "Dní do": days_to,
        "Dividenda": f"{sg('dividendRate'):.2f} {inf.get('currency', 'USD')}", "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", 
        "Doporučení": inf.get('recommendationKey', '-').replace('_', ' ').title(), "RSI": int(item['rsi']), "_rsi": item["rsi"]
    })

# --- 6. ZOBRAZENÍ ---
if stranka == "Scoring Matrix":
    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            s = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            for i, col in enumerate(r.index):
                if col in ["Cena", "Změna"]: s[i] = f"color: {'#1b5e20' if r['_change']>0 else '#b71c1c'}; font-weight: bold"
                val = r.get(f"_raw_{col}", 0)
                if col == "P/E" and val > 25: s[i] = 'background-color: #ffebee'
                if col == "Dluh D/E" and val > 120: s[i] = 'background-color: #ffcdd2'
            return s
        st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                     use_container_width=True, hide_index=True, height=800,
                     column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"])
else:
    df_c = pd.DataFrame(c_rows)
    if not df_c.empty:
        def style_calendar(r):
            s = [''] * len(r)
            d_idx = r.index.get_loc("Dní do")
            if r["Dní do"] < 0: s[d_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            elif r["Dní do"] < 14: s[d_idx] = 'background-color: #fff9c4; color: #f57f17; font-weight: bold'
            
            rec = str(r["Doporučení"]).lower(); rec_idx = r.index.get_loc("Doporučení")
            if "buy" in rec: s[rec_idx] = 'background-color: #e8f5e9; color: #1b5e20; font-weight: bold'
            elif "sell" in rec: s[rec_idx] = 'background-color: #ffebee; color: #b71c1c'
            elif "hold" in rec: s[rec_idx] = 'background-color: #f8f9fa'
            
            rsi_idx = r.index.get_loc("RSI")
            if r["_rsi"] < 35: s[rsi_idx] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold'
            elif r["_rsi"] > 65: s[rsi_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            return s
        st.dataframe(df_c.style.apply(style_calendar, axis=1), use_container_width=True, hide_index=True, height=800,
                     column_order=["Titul", "Ticker", "Earnings", "Dní do", "Dividenda", "Ex-Date", "Doporučení", "RSI"])
