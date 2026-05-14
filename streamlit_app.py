import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="Investment Hub V104 - PRO", layout="wide")

# CSS pro čistý vzhled bez nadbytečných nadpisů
st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { text-align: left !important; font-weight: bold !important; }
    .block-container { padding-top: 0rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
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
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        return pd.read_csv(csv_url)
    except: return pd.DataFrame()

# --- 3. KOMPLETNÍ DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_data(df_input):
    res = []
    if df_input.empty: return []
    msg = st.empty(); pb = st.progress(0)
    ticks = df_input.to_dict('records')
    for i, row in enumerate(ticks):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t in ["-", "NAN"]: continue
        msg.text(f"Analyzuji: {t} (komplet data)")
        pb.progress((i + 1) / len(ticks))
        try:
            tk = yf.Ticker(t); inf = tk.info; time.sleep(0.4)
            fin = tk.financials; bs = tk.balance_sheet; cf = tk.cashflow
            
            # Výpočty 3Y průměrů pro stabilitu scoringu
            avg_roe, avg_nm, avg_gm = 0, 0, 0
            if not fin.empty and not bs.empty:
                try:
                    rev = fin.get('Total Revenue', pd.Series()); ni = fin.get('Net Income', pd.Series())
                    gp = fin.get('Gross Profit', pd.Series()); eq = bs.get('Stockholders Equity', pd.Series())
                    if not rev.empty and not ni.empty: avg_nm = (ni / rev).head(3).mean() * 100
                    if not rev.empty and not gp.empty: avg_gm = (gp / rev).head(3).mean() * 100
                    if not ni.empty and not eq.empty: avg_roe = (ni / eq.head(len(ni))).head(3).mean() * 100
                except: pass

            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            res.append({
                "t": t, "inf": inf, "rsi": rsi, "kat": str(row.get('Kategorie', 'Vše')), 
                "earn": str(row.get('Earnings Day', '-')), "name": inf.get('longName', t),
                "avg_roe": avg_roe, "avg_nm": avg_nm, "avg_gm": avg_gm, "moat": str(row.get('Moat', '-'))
            })
        except: continue
    msg.empty(); pb.empty()
    return res

# --- 4. SIDEBAR & PRESETY ---
URL = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(URL)

st.sidebar.title("📊 INVEST HUB PRO")
stranka = st.sidebar.radio("Zobrazení:", ["🏠 Matrix", "🎯 Hodnota", "📅 Kalendář"])
filtr_kat = st.sidebar.selectbox("Kategorie:", ["Portfolio", "Sledované", "Vše"])

# SYSTÉM PRESETŮ
st.sidebar.subheader("⚙️ Strategie")
preset = st.sidebar.selectbox("Nastavení vah:", ["Vlastní", "Růstová (Aggressive)", "Hodnotová (Safe)", "Balancovaná"])

# Definice všech 16 ukazatelů pro Matrix
ukazatele = [
    "P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "ROA",
    "Tržby y/y", "Zisk y/y", "Dluh D/E", "Pohotová likvidita", "Div. Výnos", "Div. Payout", "Potenciál", "RSI"
]

# Výchozí hodnoty (simulace továrního nastavení)
p_map = {}
for u in ukazatele:
    with st.sidebar.expander(f"Parametry {u}"):
        p_map[u] = [{"h": st.number_input(f"{u} limit {i}", value=10.0*i, key=f"{u}{i}"), 
                     "b": st.number_input(f"{u} body {i}", value=10-i, key=f"{u}b{i}")} for i in range(5)]

# --- 5. LOGIKA STRÁNEK ---
if not df_raw.empty:
    data = fetch_data(df_raw)
    f_data = [d for d in data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

    if stranka == "🏠 Matrix":
        m_rows = []
        for d in f_data:
            inf = d["inf"]; p = safe_float(inf.get('currentPrice'))
            # Sběr 16 hodnot
            vals = {
                "P/E": p/safe_float(inf.get("trailingEps")) if safe_float(inf.get("trailingEps")) != 0 else 0,
                "P/S": safe_float(inf.get("priceToSalesTrailing12Months")),
                "P/B": safe_float(inf.get("priceToBook")),
                "P/FCF": safe_float(inf.get("marketCap"))/safe_float(inf.get("freeCashflow")) if safe_float(inf.get("freeCashflow")) else 0,
                "H-Marže": d["avg_gm"] if d["avg_gm"] != 0 else safe_float(inf.get("grossMargins", 0))*100,
                "Č-Marže": d["avg_nm"] if d["avg_nm"] != 0 else safe_float(inf.get("profitMargins", 0))*100,
                "ROE": d["avg_roe"] if d["avg_roe"] != 0 else safe_float(inf.get("returnOnEquity", 0))*100,
                "ROA": safe_float(inf.get("returnOnAssets", 0))*100,
                "Tržby y/y": safe_float(inf.get("revenueGrowth", 0))*100,
                "Zisk y/y": safe_float(inf.get("earningsGrowth", 0))*100,
                "Dluh D/E": safe_float(inf.get("debtToEquity", 0)),
                "Pohotová likvidita": safe_float(inf.get("quickRatio", 0)),
                "Div. Výnos": safe_float(inf.get("dividendYield", 0))*100,
                "Div. Payout": safe_float(inf.get("payoutRatio", 0))*100,
                "Potenciál": ((safe_float(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0,
                "RSI": d["rsi"]
            }
            
            score = sum([get_b(vals[u], p_map[u]) for u in ukazatele])
            row = {"Titul": d["name"], "Ticker": d["t"], "TC": f"{p:.2f}", "Score": int(score)}
            for u in ukazatele:
                row[u] = f"{vals[u]:.1f}" + ("%" if "y/y" in u or "Marže" in u or "ROE" in u or "Výnos" in u else "")
            m_rows.append(row)

        df_m = pd.DataFrame(m_rows)
        st.dataframe(df_m.style.background_gradient(subset=["Score"], cmap="RdYlGn").map(lambda x: 'color: #2ecc71; font-weight: bold' if x else '', subset=["TC"]), use_container_width=True, hide_index=True)

    elif stranka == "🎯 Hodnota":
        iv_rows = []
        for d in f_data:
            inf = d["inf"]; p = safe_float(inf.get('currentPrice'))
            # 5 Metod vnitřní hodnoty
            m1 = safe_float(inf.get('targetMeanPrice', p))
            m2 = (safe_float(inf.get('trailingEps')) * 15)
            m3 = safe_float(inf.get('bookValue', 0)) * 1.5
            m4 = (safe_float(inf.get('freeCashflow')) / safe_float(inf.get('marketCap', 1))) * p * 10 if inf.get('freeCashflow') else 0
            
            fair = (m1+m2+m3)/3 if m3 > 0 else (m1+m2)/2
            up = ((fair/p)-1)*100
            iv_rows.append({"Titul": d["name"], "Tržní": p, "Analytici": int(m1), "Zisková": int(m2), "Majetková": int(m3), "Férová": int(fair), "Potenciál %": f"{up:.1f}%", "_up": up})
        st.dataframe(pd.DataFrame(iv_rows).style.background_gradient(subset=["_up"], cmap="RdYlGn"), use_container_width=True, hide_index=True)

    else:
        # Kalendář s "Dní do" a barevným doporučením
        c_rows = []
        for d in f_data:
            dni = "-"
            try:
                diff = (datetime.strptime(d["earn"], "%d.%m.%Y") - datetime.now()).days
                dni = f"{diff} dní"
            except: pass
            rec = d["inf"].get("recommendationKey", "N/A").replace("_", " ").title()
            c_rows.append({"Titul": d["name"], "Earnings": d["earn"], "Dní do": dni, "RSI": int(d["rsi"]), "Analytici": rec, "Moat": d["moat"]})
        st.dataframe(pd.DataFrame(c_rows).style.map(lambda x: 'background-color: #2ecc71' if x in ['Buy', 'Strong Buy'] else '', subset=['Analytici']), use_container_width=True, hide_index=True)
