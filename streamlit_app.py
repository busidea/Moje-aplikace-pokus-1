import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investment Hub V100.8", layout="wide")

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

# --- 2. POMOCNÉ FUNKCE ---
def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]: return 999
    try:
        dt = pd.to_datetime(earn_val, dayfirst=True).date()
        return (dt - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def fmt(val, precision=1, is_pct=False):
    if val is None or val == 0: return "0.0" + ("%" if is_pct else "")
    res = f"{val:.{precision}f}"
    return res + "%" if is_pct else res

def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except Exception as e:
        st.error(f"Chyba při načítání tabulky: {e}")
        return pd.DataFrame()

# --- 3. DATA FETCH (S ROZŠÍŘENÍM PRO TREND) ---
@st.cache_data(ttl=3600)
def fetch_data_full(df_input):
    res = []
    if df_input.empty: return []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t == "-" or t == "NAN": continue
        try:
            tk = yf.Ticker(t); inf = tk.info
            fin = tk.financials; bs = tk.balance_sheet
            
            loni = {'eps': 0, 'roe': 0}
            if not fin.empty and 'Basic EPS' in fin.index and len(fin.columns) > 1:
                loni['eps'] = safe_float(fin.loc['Basic EPS'].iloc[1])
                if not bs.empty and 'Stockholders Equity' in bs.index:
                    eq_loni = safe_float(bs.loc['Stockholders Equity'].iloc[1])
                    loni['roe'] = (safe_float(fin.loc['Net Income'].iloc[1]) / eq_loni * 100) if eq_loni != 0 else 0
            
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
                
            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie', 'Vše')), 
                "earn": row.get('Earnings Day'), 
                "name": inf.get('longName', t), 
                "loni": loni, "moat": row.get('Moat', '-')
            })
        except: continue
    return res

# --- 4. NAČTENÍ DAT A NAVIGACE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

st.sidebar.markdown("## **🧭 Navigace**")
stranka = st.sidebar.radio("Zobrazení:", ["🏠 Scoring Matrix", "🎯 Vnitřní hodnota (IV)", "📅 Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

raw_data = fetch_data_full(df_raw)
filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 5. LOGIKA STRÁNEK ---

if stranka == "🏠 Scoring Matrix":
    st.subheader("📊 Kvalitativní Scoring Matrix")
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní body", value=False)
    
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
    p_nm = vytvor_p("Č-Marže", "nm", [10, 20, 30, 45, 999], [0, 10, 18, 22, 30])
    p_roe = vytvor_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
    p_rev = vytvor_p("Tržby y/y", "rev", [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35])
    p_eps = vytvor_p("Zisk y/y", "eps", [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40])
    p_deb = vytvor_p("Dluh D/E", "deb", [40, 80, 120, 200, 999], [20, 10, 0, -15, -40])
    p_div = vytvor_p("Div. výnos", "div", [2, 4, 6, 8, 999], [5, 12, 15, 10, 5])
    p_pot = vytvor_p("Potenciál", "pot", [8, 18, 28, 45, 999], [0, 10, 18, 25, 35])
    
    w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
    w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
    w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
    w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

    m_rows = []
    mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    p_map = {"P/E":p_pe,"P/S":p_ps,"P/B":p_pb,"P/FCF":p_pfcf,"H-Marže":p_gm,"Č-Marže":p_nm,"ROE":p_roe,"Tržby y/y":p_rev,"Zisk y/y":p_eps,"Dluh D/E":p_deb,"Div. výnos":p_div,"Potenciál":p_pot}

    for item in filtered_data:
        inf, loni = item["inf"], item["loni"]
        p = safe_float(inf.get('currentPrice'))
        raw_vals = {
            "Cena": p, "Změna": ((p/safe_float(inf.get("previousClose", 1)))-1)*100,
            "P/E": p/safe_float(inf.get("trailingEps")) if safe_float(inf.get("trailingEps")) != 0 else 0,
            "P/S": safe_float(inf.get("priceToSalesTrailing12Months")), "P/B": safe_float(inf.get("priceToBook")),
            "P/FCF": safe_float(inf.get("marketCap"))/safe_float(inf.get("freeCashflow")) if safe_float(inf.get("freeCashflow")) else 0,
            "H-Marže": safe_float(inf.get("grossMargins", 0))*100, "Č-Marže": safe_float(inf.get("profitMargins", 0))*100, "ROE": safe_float(inf.get("returnOnEquity", 0))*100,
            "Tržby y/y": safe_float(inf.get("revenueGrowth", 0))*100, "Zisk y/y": safe_float(inf.get("earningsGrowth", 0))*100, "Dluh D/E": safe_float(inf.get("debtToEquity", 0)),
            "Div. výnos": safe_float(inf.get("dividendYield", 0))*100, "Potenciál": ((safe_float(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0
        }

        total_dnes = 0
        row_p = {"Titul": f"   └ body ({item['t']})", "Type": "Points"}
        w_map = {"v":w_val,"p":w_prof,"g":w_growth,"r":w_risk}
        for k in mapping_keys:
            vw = w_map["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
            b = get_b(raw_vals[k], p_map[k]) * vw
            total_dnes += b
            row_p[k] = str(int(round(b)))

        # Trend (Zisk a ROE loni vs dnes)
        pe_loni = p / loni['eps'] if loni['eps'] != 0 else 0
        total_loni = (get_b(pe_loni, p_pe) * w_val) + (get_b(loni['roe'], p_roe) * w_prof)
        # Pro srovnání trendu udržíme ostatní dnešní body
        for k in [m for m in mapping_keys if m not in ["P/E", "ROE"]]:
            vw = w_map["v"] if k in ["P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
            total_loni += get_b(raw_vals[k], p_map[k]) * vw
        
        diff = total_dnes - total_loni
        trend_str = f"{'▲' if diff > 0 else ('▼' if diff < 0 else '•')} {abs(int(diff))}"

        row_v = {"Titul": item["name"], "Type": "Value", "Cena": fmt(p, 2), "Změna": fmt(raw_vals["Změna"], 1, True), "Score": int(total_dnes), "Fund. Trend": trend_str, "_trend": diff, "_change": raw_vals["Změna"]}
        for k in mapping_keys:
            row_v[k] = fmt(raw_vals[k], 1, k in ["H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"])
        
        m_rows.append(row_v)
        if zobrazit_body: m_rows.append(row_p)

    df = pd.DataFrame(m_rows)
    if not df.empty:
        col_order = ["Titul", "Cena", "Změna"] + mapping_keys + ["Score", "Fund. Trend"]
        st.dataframe(df.style.apply(lambda r: [f"color: {'#2ecc71' if r['_trend']>0 else '#e74c3c' if r['_trend']<0 else '#888'}; font-weight: bold" if c == "Fund. Trend" else "" for c in r.index], axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                     use_container_width=True, hide_index=True, column_order=col_order, column_config={"_trend": None, "Type": None, "_change": None})

elif stranka == "🎯 Vnitřní hodnota (IV)":
    st.subheader("🎯 Kalkulace vnitřní hodnoty")
    wi1 = st.sidebar.slider("P1: Ziskové", 0, 100, 33)
    wi2 = st.sidebar.slider("P2: Cashflow", 0, 100, 33)
    wi3 = st.sidebar.slider("P3: Majetek", 0, 100, 34)
    
    iv_rows = []
    for item in filtered_data:
        inf = item["inf"]; p = safe_float(inf.get('currentPrice'))
        p1 = safe_float(inf.get('targetMeanPrice', p))
        p2 = (safe_float(inf.get('trailingEps')) * 15) if safe_float(inf.get('trailingEps')) > 0 else 0
        iv = (p1*wi1 + p2*wi2 + p*wi3)/100 # Zjednodušený příklad pro stabilitu
        up = ((iv/p)-1)*100 if p else 0
        iv_rows.append({"Titul": item["name"], "Cena": p, "Férová cena": int(iv), "Potenciál %": f"{up:.1f}%", "_up": up})
    
    df_iv = pd.DataFrame(iv_rows)
    st.dataframe(df_iv.style.background_gradient(subset=["_up"], cmap="RdYlGn"), use_container_width=True, hide_index=True, column_config={"_up": None})

else:
    st.subheader("📅 Kalendář & RSI")
    c_rows = []
    for item in filtered_data:
        c_rows.append({"Titul": item["name"], "Ticker": item["t"], "Earnings": item["earn"], "RSI": int(item["rsi"])})
    st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)
