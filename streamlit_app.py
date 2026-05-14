import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime

# --- 1. KONFIGURACE (Převzato z V86.6) ---
st.set_page_config(page_title="Investment Hub V107", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 0.5rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { text-align: left !important; font-weight: bold !important; color: #1f4e79 !important; }
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE (Standard pro oba scripty) ---
def safe_f(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

@st.cache_data(ttl=86400)
def nacti_seznam(odkaz):
    try:
        u = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(u)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. DATA FETCH (Sjednocený základ) ---
@st.cache_data(ttl=3600)
def fetch_data(df_in):
    res = []
    if df_in.empty: return []
    bar = st.progress(0); msg = st.empty()
    ticks = df_in.to_dict('records')
    for i, row in enumerate(ticks):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t == "NAN": continue
        msg.text(f"Stahuji data: {t}")
        bar.progress((i + 1) / len(ticks))
        try:
            tk = yf.Ticker(t); inf = tk.info; time.sleep(0.4)
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d>0,0).rolling(14).mean(); l = -d.where(d<0,0).rolling(14).mean()
                rsi = 100-(100/(1+(g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            res.append({
                "t": t, "inf": inf, "rsi": rsi, "kat": str(row.get('Kategorie', 'Vše')), 
                "earn": str(row.get('Earnings Day', '-')), "name": inf.get('longName', t)
            })
        except: continue
    msg.empty(); bar.empty()
    return res

# --- 4. SIDEBAR (Mechanické spojení ovladačů) ---
URL = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(URL)

st.sidebar.title("💎 INVEST HUB")
stranka = st.sidebar.radio("Navigace:", ["Scoring Matrix", "Vnitřní hodnota", "Kalendář & RSI"])
filtr = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"])

# --- Ovladače pro Scoring (z V86.6) ---
if stranka == "Scoring Matrix":
    st.sidebar.subheader("Nastavení Matrixu")
    show_points = st.sidebar.checkbox("Zobrazit body pod daty", value=False)
    # Zde by byly expandery pro 16 ukazatelů (zkráceno pro funkčnost, doplní se dle potřeby)
    ukazatele = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "ROA", "Růst Tržeb", "Růst Zisku", "Dluh D/E", "Likvidita", "Div. Výnos", "Div. Payout", "Potenciál", "RSI"]
    p_map = {}
    for u in ukazatele:
        with st.sidebar.expander(f"Parametry {u}", expanded=False):
            p_map[u] = [{"h": st.number_input(f"{u} do {j}", value=15.0+j*10, key=f"{u}{j}"), 
                         "b": st.number_input(f"{u} bod {j}", value=20-j*5, key=f"{u}b{j}")} for j in range(5)]

# --- Ovladače pro Vnitřní hodnotu (Kompletně z V96.3) ---
if stranka == "Vnitřní hodnota":
    st.sidebar.subheader("Nastavení Vnitřní Hodnoty")
    with st.sidebar.expander("⚖️ Váhy pilířů (V96.3)", expanded=True):
        w1 = st.slider("Váha Pilíř I (Analytici)", 0.0, 1.0, 0.3)
        w2 = st.slider("Váha Pilíř II (Zisk/Graham)", 0.0, 1.0, 0.4)
        w3 = st.slider("Váha Pilíř III (Výnos/Cash)", 0.0, 1.0, 0.3)
    with st.sidebar.expander("🌐 Globální parametry", expanded=True):
        req_ret = st.number_input("Požadovaná výnosnost (%)", value=9.0) / 100
        term_g = st.number_input("Terminální růst (%)", value=3.0) / 100
    show_detail_iv = st.sidebar.checkbox("Zobrazit detailní metody výpočtu")

# --- 5. LOGIKA STRÁNEK ---
if not df_raw.empty:
    data = fetch_data(df_raw)
    f_data = [d for d in data if filtr == "Vše" or d["kat"] == filtr]

    if stranka == "Scoring Matrix":
        # Logika Matrixu z V86.6
        m_rows = []
        for d in f_data:
            inf = d["inf"]; p = safe_f(inf.get('currentPrice'))
            v = {
                "P/E": p/safe_f(inf.get("trailingEps")) if safe_f(inf.get("trailingEps")) != 0 else 0,
                "P/S": safe_f(inf.get("priceToSalesTrailing12Months")),
                "P/B": safe_f(inf.get("priceToBook")),
                "P/FCF": safe_f(inf.get("marketCap"))/safe_f(inf.get("freeCashflow")) if safe_f(inf.get("freeCashflow")) else 0,
                "H-Marže": safe_f(inf.get("grossMargins", 0))*100, "Č-Marže": safe_f(inf.get("profitMargins", 0))*100,
                "ROE": safe_f(inf.get("returnOnEquity", 0))*100, "ROA": safe_f(inf.get("returnOnAssets", 0))*100,
                "Růst Tržeb": safe_f(inf.get("revenueGrowth", 0))*100, "Růst Zisku": safe_f(inf.get("earningsGrowth", 0))*100,
                "Dluh D/E": safe_f(inf.get("debtToEquity", 0)), "Likvidita": safe_f(inf.get("currentRatio", 0)),
                "Div. Výnos": safe_f(inf.get("dividendYield", 0))*100, "Div. Payout": safe_f(inf.get("payoutRatio", 0))*100,
                "Potenciál": ((safe_f(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0, "RSI": d["rsi"]
            }
            sc = sum([get_b(v[u], p_map[u]) for u in ukazatele])
            row = {"Společnost": d["name"], "Ticker": d["t"], "Cena": f"{p:.2f}", "Score": int(sc)}
            for u in ukazatele: row[u] = f"{v[u]:.1f}"
            m_rows.append(row)
            if show_points:
                row_p = {"Společnost": f"   └ body ({d['t']})"}
                for u in ukazatele: row_p[u] = str(get_b(v[u], p_map[u]))
                m_rows.append(row_p)
        
        df_m = pd.DataFrame(m_rows)
        st.dataframe(df_m.style.background_gradient(subset=["Score"], cmap="RdYlGn").map(lambda x: 'color: #2ecc71; font-weight: bold' if x and not str(x).startswith(" ") else '', subset=["Cena"]), use_container_width=True, hide_index=True)

    elif stranka == "Vnitřní hodnota":
        # Logika Vnitřní hodnoty PŘESNĚ z V96.3
        iv_rows = []
        for d in f_data:
            inf = d["inf"]; p = safe_f(inf.get('currentPrice'))
            eps = safe_f(inf.get('trailingEps')); bvps = safe_f(inf.get('bookValue'))
            div = safe_f(inf.get('dividendYield', 0)) * p; fcf = safe_f(inf.get('freeCashflow'))
            shares = safe_f(inf.get('sharesOutstanding', 1))
            
            # 5 Metod z V96.3
            m1 = safe_f(inf.get('targetMeanPrice', p))
            m2 = (22.5 * eps * bvps)**0.5 if eps > 0 and bvps > 0 else 0
            m3 = eps * (8.5 + 2 * 5) if eps > 0 else 0
            m4 = div / (req_ret - term_g) if req_ret > term_g and div > 0 else 0
            m5 = (fcf / shares) * 15 if fcf > 0 else 0

            # Seskupení do pilířů
            p1 = m1
            p2 = (m2 + m3) / 2 if m2 > 0 and m3 > 0 else (m2 or m3)
            p3 = (m4 + m5) / 2 if m4 > 0 and m5 > 0 else (m4 or m5)
            
            fair = (p1*w1 + p2*w2 + p3*w3) / ((bool(p1)*w1 + bool(p2)*w2 + bool(p3)*w3) or 1)
            up = ((fair/p)-1)*100 if p > 0 else 0

            row = {"Společnost": d["name"], "Tržní": p, "Pilíř I (Analytici)": int(p1), "Pilíř II (Zisk)": int(p2), "Pilíř III (Cash)": int(p3), "Férová Cena": int(fair), "Potenciál %": f"{up:.1f}%", "_up": up}
            if show_detail_iv:
                row.update({"Analytici": int(m1), "Graham #": int(m2), "Graham Růst": int(m3), "DDM": int(m4), "DCF": int(m5)})
            iv_rows.append(row)
        
        df_iv = pd.DataFrame(iv_rows)
        st.dataframe(df_iv.style.background_gradient(subset=["_up"], cmap="RdYlGn"), use_container_width=True, hide_index=True)
        st.info("💡 Legenda k pilířům a metodám dle V96.3 aktivní.")

    elif stranka == "Kalendář & RSI":
        # Logika Kalendáře z V86.6
        c_rows = []
        for d in f_data:
            dni = "-"
            try:
                diff = (datetime.strptime(d["earn"], "%d.%m.%Y") - datetime.now()).days
                dni = f"{diff} dní" if diff >= 0 else "Proběhlo"
            except: pass
            rec = d["inf"].get("recommendationKey", "N/A").replace("_", " ").title()
            c_rows.append({"Společnost": d["name"], "Ticker": d["t"], "Earnings": d["earn"], "Dní do": dni, "RSI": int(d["rsi"]), "Analytici": rec})
        
        df_c = pd.DataFrame(c_rows)
        st.dataframe(df_c.style.map(lambda x: 'background-color: #ffeb3b; color: black' if x < 30 else ('background-color: #ff9800; color: white' if x > 70 else ''), subset=['RSI'])
                     .map(lambda x: 'background-color: #2ecc71' if x in ['Buy', 'Strong Buy'] else '', subset=['Analytici']), use_container_width=True, hide_index=True)
