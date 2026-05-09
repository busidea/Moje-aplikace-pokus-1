import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import numpy as np

# Konfigurace stránky
st.set_page_config(page_title="Scoring firem V83.2", layout="wide")

# --- 1. POMOCNÉ FUNKCE ---
def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def get_b_direct(val, h_list, b_list):
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
            if df[col].dtype == 'object':
                df[col] = df[col].str.strip()
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except:
        return pd.DataFrame()

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 3. LEVÁ LIŠTA (SIDEBAR) ---
st.sidebar.markdown("## **Scoring firem**")

filtr_kat = st.sidebar.selectbox("Zobrazit pro:", ["Portfolio", "Sledované", "Vše"], index=0)
strategie = st.sidebar.selectbox("Nastavení:", ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový", "⚖️ Vyvážený"], index=0)
zobrazit_body = st.sidebar.checkbox("Zobrazit řádky s body", value=False)

st.sidebar.divider()

# Příprava parametrů
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
    st.sidebar.markdown("**Váhy skupin**")
    w_val, w_prof, w_growth, w_risk = st.sidebar.slider("Valuace", 0.5, 3.0, 1.2), st.sidebar.slider("Rentabilita", 0.5, 3.0, 1.5), st.sidebar.slider("Růst", 0.5, 3.0, 1.0), st.sidebar.slider("Riziko", 0.5, 3.0, 1.8)

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
m_rows, c_rows, today = [], [], date.today()
mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]

for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t = item["inf"], item["t"]
    def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
    
    # OPRAVA DIVIDENDY (Yahoo vrací 0.03 pro 3%)
    d_raw = inf.get('dividendYield')
    val_div = (d_raw * 100) if d_raw is not None else 0
    
    vals = {
        "Ticker": t, "Cena": g("currentPrice"), "Změna": ((g("currentPrice")/g("previousClose", 1))-1)*100,
        "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
        "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
        "H-Marže": g("grossMargins", 100), "H-Marže 3Y": g("grossMargins", 94),
        "Č-Marže": g("profitMargins", 100), "Č-Marže 3Y": g("profitMargins", 91),
        "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
        "Tržby y/y": g("revenueGrowth", 100), "Zisk y/y": g("earningsGrowth", 100),
        "Dluh D/E": g("debtToEquity"), "Div. výnos": val_div, "Payout": g("payoutRatio", 100),
        "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
        "Score": 0, "Type": "Value"
    }

    pts = {"Ticker": f"└ {t} body", "Type": "Points"}
    total = 0
    for k in mapping_keys:
        if strategie == "Vlastní":
            w_map = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}
            p_map = {"P/E": p_pe, "P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf, "H-Marže": p_gm, "H-Marže 3Y": p_gm3y, "Č-Marže": p_nm, "Č-Marže 3Y": p_nm3y, "ROE": p_roe, "ROE 3Y": p_roe3y, "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Payout": p_pay, "Potenciál": p_pot}
            vw = w_map["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w_map["r"]))
            b = get_b(vals[k], p_map[k]) * vw
        else:
            b = get_b_direct(vals[k], [15, 25, 40], [15, 5, -10])
        pts[k] = b
        total += b
    
    vals["Score"], pts["Score"] = total, total
    m_rows.append(vals)
    if zobrazit_body: m_rows.append(pts)

    # Kalendář
    ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
    c_rows.append({
        "Ticker": t, "Earnings": item["earn"], "Dní do": (pd.to_datetime(item["earn"], dayfirst=True).date() - today).days if item["earn"] != "-" else "-",
        "Dividenda": f"{g('dividendRate'):.2f} {inf.get('currency')}", "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-",
        "Analytické hodnocení": inf.get('recommendationKey', '-').replace('_', ' ').title(), "RSI": int(item['rsi']), "_rsi": item["rsi"], "_alert": [1 if item["earn"] != "-" and 0<=(pd.to_datetime(item["earn"], dayfirst=True).date()-today).days<=14 else 0, 1 if "Strong Buy" in str(inf.get('recommendationKey','')) else 0, 1 if ex_dt and 0<=(ex_dt-today).days<=10 else 0]
    })

# --- 6. ZOBRAZENÍ ---
df_m = pd.DataFrame(m_rows)
if df_m.empty:
    st.warning("Žádná data. Zkontrolujte Google Sheet.")
else:
    def style_matrix(r):
        styles = [''] * len(r)
        if r["Type"] == "Points":
            return ['color: #888; font-style: italic; background-color: #f9f9f9'] * len(r)
        for i, col in enumerate(r.index):
            if col == "P/E" and r[col] > 30: styles[i] = 'background-color: #ffe5e5;'
            if col == "Dluh D/E" and r[col] > 120: styles[i] = 'background-color: #fff3cd;'
            if col == "Potenciál" and r[col] > 20: styles[i] = 'background-color: #d4edda;'
            if col in ["Cena", "Změna"]: styles[i] = f"color: {'#28a745' if r['Změna']>0 else '#dc3545'}; font-weight: bold"
        return styles

    pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]
    st.dataframe(df_m.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn").format({c: "{:.1f}%" for c in pct_cols}, precision=1), use_container_width=True, hide_index=True, height=850 if zobrazit_body else 800, column_order=["Ticker", "Cena", "Změna"] + mapping_keys + ["Score"])

st.write("---")
df_c = pd.DataFrame(c_rows)
if not df_c.empty:
    st.dataframe(df_c.style.apply(lambda r: ['background-color: #ffc107' if i=='Dní do' and r['_alert'][0] else 'background-color: #28a745; color: white' if i=='Analytické hodnocení' and r['_alert'][1] else 'background-color: #007bff; color: white' if i=='Ex-Date' and r['_alert'][2] else 'background-color: #ffe5e5; color: #cc0000; font-weight: bold' if i=='RSI' and r['_rsi']>70 else 'background-color: #e5f9e5; color: #28a745; font-weight: bold' if i=='RSI' and r['_rsi']<30 else '' for i in r.index], axis=1), use_container_width=True, hide_index=True, height=800, column_order=["Ticker", "Earnings", "Dní do", "Dividenda", "Ex-Date", "Analytické hodnocení", "RSI"])
