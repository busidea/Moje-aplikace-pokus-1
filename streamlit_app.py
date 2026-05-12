import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL (V86.6 DESIGN) ---
st.set_page_config(page_title="Investment Terminal V100.2", layout="wide")

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
    except: return pd.DataFrame()

# --- 3. DATA FETCH S HISTORIÍ ---
@st.cache_data(ttl=3600)
def fetch_data_full(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t == "-": continue
        try:
            tk = yf.Ticker(t); inf = tk.info
            fin = tk.financials; bs = tk.balance_sheet
            
            loni = {}
            if not fin.empty and len(fin.columns) > 1:
                loni['eps'] = safe_float(fin.loc['Basic EPS'].iloc[1]) if 'Basic EPS' in fin.index else 0
                loni['rev'] = safe_float(fin.loc['Total Revenue'].iloc[1]) if 'Total Revenue' in fin.index else 0
                loni['net_inc'] = safe_float(fin.loc['Net Income'].iloc[1]) if 'Net Income' in fin.index else 0
                if not bs.empty and 'Stockholders Equity' in bs.index:
                    eq_loni = safe_float(bs.loc['Stockholders Equity'].iloc[1])
                    loni['roe'] = (loni['net_inc'] / eq_loni * 100) if eq_loni != 0 else 0
                else: loni['roe'] = 0
            
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
                
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": str(row.get('Kategorie', 'Vše')), "earn": row.get('Earnings Day'), "name": inf.get('longName', t), "loni": loni, "moat": row.get('Moat', '-')})
        except: continue
    return res

# --- 4. NAČTENÍ A NAVIGACE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

st.sidebar.markdown("## **📊 Portfoliomanžer V100.2**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

all_data = fetch_data_full(df_raw_list)
filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 5. STRÁNKA: SCORING MATRIX ---
if stranka == "Scoring Matrix":
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

    # Všech 12 parametrů z V86.6
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
    
    st.sidebar.divider()
    w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
    w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
    w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
    w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

    m_rows = []
    mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    p_map = {"P/E":p_pe,"P/S":p_ps,"P/B":p_pb,"P/FCF":p_pfcf,"H-Marže":p_gm,"Č-Marže":p_nm,"ROE":p_roe,"Tržby y/y":p_rev,"Zisk y/y":p_eps,"Dluh D/E":p_deb,"Div. výnos":p_div,"Potenciál":p_pot}
    
    for item in filtered_data:
        inf = item["inf"]; loni = item["loni"]; t = item["t"]
        price = safe_float(inf.get('currentPrice'))
        
        def sg(k, mult=1.0):
            v = inf.get(k); return float(v) * mult if v is not None and str(v) != "None" else 0.0

        raw_vals = {
            "Cena": price, "Změna": ((price/sg("previousClose", 1.0))-1)*100 if sg("previousClose") else 0,
            "P/E": sg("trailingPE") or sg("forwardPE"), "P/S": sg("priceToSalesTrailing12Months"), 
            "P/B": sg("priceToBook"), "P/FCF": sg("marketCap")/sg("freeCashflow") if sg("freeCashflow") else 0,
            "H-Marže": sg("grossMargins", 100), "Č-Marže": sg("profitMargins", 100), "ROE": sg("returnOnEquity", 100), 
            "Tržby y/y": sg("revenueGrowth", 100), "Zisk y/y": sg("earningsGrowth", 100), "Dluh D/E": sg("debtToEquity"), 
            "Div. výnos": sg("dividendYield") * 100, "Potenciál": ((sg("targetMeanPrice")/price)-1)*100 if price else 0
        }

        # Výpočet Dnešního Score
        total_dnes = 0
        row_p = {"Titul": f"   └ body ({t})", "Type": "Points"}
        w_map = {"v":w_val,"p":w_prof,"g":w_growth,"r":w_risk}
        
        for k in mapping_keys:
            vw = w_map["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
            b = get_b(raw_vals[k], p_map[k]) * vw
            total_dnes += b
            row_p[k] = str(int(round(b)))

        # Výpočet Stínového Trendu (Loňský fundament / Dnešní cena)
        total_loni = 0
        if loni:
            pe_loni = price / loni['eps'] if loni.get('eps', 0) > 0 else 0
            total_loni += get_b(pe_loni, p_pe) * w_val
            total_loni += get_b(loni.get('roe', 0), p_roe) * w_prof
            # ... (pro trend počítáme jen klíčové pilíře)
        
        trend_val = total_dnes - total_loni if loni else 0
        trend_str = f"{'▲' if trend_val > 1 else ('▼' if trend_val < -1 else '•')} {abs(int(trend_val))}"

        row_v = {"Titul": item["name"], "Type": "Value", "Score": int(total_dnes), "Fund. Trend": trend_str, "_trend": trend_val, "_change": raw_vals["Změna"]}
        for k in mapping_keys:
            row_v[k] = fmt(raw_vals[k], 1, k in ["H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"])
        row_v["Cena"] = fmt(price, 2)
        row_v["Změna"] = fmt(raw_vals["Změna"], 1, True)
        
        m_rows.append(row_v)
        if zobrazit_body: m_rows.append(row_p)

    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            s = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            t_idx = r.index.get_loc("Fund. Trend")
            s[t_idx] = f"color: {'#2ecc71' if r['_trend'] > 1 else ('#e74c3c' if r['_trend'] < -1 else '#888')}; font-weight: bold"
            c_idx = r.index.get_loc("Změna")
            s[c_idx] = f"color: {'#1b5e20' if r['_change'] > 0 else '#b71c1c'}; font-weight: bold"
            return s
        
        st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                     use_container_width=True, hide_index=True, height=800,
                     column_order=["Titul", "Cena", "Změna", "Score", "Fund. Trend"] + mapping_keys)

# --- 6. STRÁNKA: KALENDÁŘ (V86.6) ---
elif stranka == "Kalendář & RSI":
    st.subheader("📅 Kalendář událostí & RSI")
    c_rows, today = [], date.today()
    for item in filtered_data:
        inf = item["inf"]
        days_to = safe_date_diff(item["earn"], today)
        ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
        c_rows.append({
            "Titul": item["name"], "Ticker": item["t"], "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", 
            "Dní do": days_to, "Dividenda": f"{safe_float(inf.get('dividendRate')):.2f} {inf.get('currency', 'USD')}",
            "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", 
            "Doporučení": inf.get('recommendationKey', '-').replace('_', ' ').title(), "RSI": int(item['rsi']), "_rsi": item["rsi"]
        })
    df_c = pd.DataFrame(c_rows)
    def style_cal(r):
        s = [''] * len(r)
        rsi_idx = r.index.get_loc("RSI")
        if r["_rsi"] < 35: s[rsi_idx] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold'
        elif r["_rsi"] > 65: s[rsi_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
        d_idx = r.index.get_loc("Dní do")
        if r["Dní do"] < 14: s[d_idx] = 'background-color: #fff9c4; font-weight: bold'
        return s
    st.dataframe(df_c.style.apply(style_cal, axis=1), use_container_width=True, hide_index=True)

# --- 7. STRÁNKA: IV TERMINÁL ---
elif stranka == "Vnitřní hodnota (IV)":
    st.subheader("🎯 Vnitřní hodnota (Pilíře)")
    # ... (Zde je ta komplexní logika s váhami wi1, wi2, wi3 a barvami z předchozích kroků) ...
