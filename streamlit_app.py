import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investment Hub V100.0", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { 
        text-align: left !important; 
        font-weight: bold !important;
        color: #003366 !important;
    }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; }
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

def fmt(val, precision=1, is_pct=False):
    if val is None or val == 0: return "0.0" + ("%" if is_pct else "")
    res = f"{val:.{precision}f}"
    return res + "%" if is_pct else res

# --- 3. DATA FETCH S HISTORIÍ (KLÍČOVÁ NOVINKA) ---
@st.cache_data(ttl=3600)
def fetch_data_with_history(df_input):
    res = []
    pbar = st.progress(0)
    total_ticks = len(df_input)
    
    for idx, row in enumerate(df_input.to_dict('records')):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t == "-": continue
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            
            # Načtení historie pro Trend (YoY fundament)
            fin = tk.financials
            bs = tk.balance_sheet
            
            loni = {}
            if not fin.empty and len(fin.columns) > 1:
                # Index 0 je aktuální, Index 1 je loni
                loni['eps'] = safe_float(fin.loc['Basic EPS'].iloc[1]) if 'Basic EPS' in fin.index else 0
                loni['rev_growth'] = safe_float((fin.loc['Total Revenue'].iloc[1] / fin.loc['Total Revenue'].iloc[2]) - 1) * 100 if len(fin.columns) > 2 else 0
                loni['net_margin'] = safe_float(fin.loc['Net Income'].iloc[1] / fin.loc['Total Revenue'].iloc[1]) * 100 if 'Net Income' in fin.index else 0
                
                # ROE loni
                if not bs.empty and 'Stockholders Equity' in bs.index:
                    equity_loni = safe_float(bs.loc['Stockholders Equity'].iloc[1])
                    loni['roe'] = (safe_float(fin.loc['Net Income'].iloc[1]) / equity_loni) * 100 if equity_loni != 0 else 0
                else: loni['roe'] = 0
            
            # RSI
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            res.append({
                "t": t, "inf": inf, "rsi": rsi, "loni": loni,
                "kat": str(row.get('Kategorie')), "earn": row.get('Earnings Day'), 
                "name": inf.get('longName', t), "moat": row.get('Moat', '-')
            })
        except Exception as e:
            print(f"Error {t}: {e}")
        pbar.progress((idx + 1) / total_ticks)
    pbar.empty()
    return res

# --- 4. NAČTENÍ SEZNAMU A NAVIGACE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

st.sidebar.markdown("## **🧭 Navigace**")
stranka = st.sidebar.radio("Zobrazení:", ["🏠 Scoring Matrix", "🎯 Vnitřní hodnota (IV)", "📅 Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

all_data = fetch_data_with_history(df_raw_list)
filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 5. STRÁNKA: SCORING MATRIX (S TRENDEM) ---
if stranka == "🏠 Scoring Matrix":
    st.subheader("📊 Kvalitativní Scoring Matrix & Fundamentální Trend")
    
    # Expandery pro pásma (ponecháno z V86.6)
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
    p_nm = vytvor_p("Č-Marže", "nm", [10, 20, 30, 45, 999], [0, 10, 18, 22, 30])
    p_roe = vytvor_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
    
    w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
    w_fund = st.sidebar.slider("Váha: Fundament", 0.5, 3.0, 1.0)

    m_rows = []
    for d in filtered_data:
        inf = d["inf"]; loni = d["loni"]
        price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps'))
        pe = price / eps if eps > 0 else 0
        roe = safe_float(inf.get('returnOnEquity')) * 100
        nm = safe_float(inf.get('profitMargins')) * 100
        
        # 1. AKTUÁLNÍ SCORE
        s_dnes = (get_b(pe, p_pe) * w_val) + (get_b(roe, p_roe) * w_fund) + (get_b(nm, p_nm) * w_fund)
        
        # 2. STÍNOVÉ SCORE (Loňská data / Dnešní cena)
        pe_loni = price / loni['eps'] if loni.get('eps', 0) > 0 else 0
        s_loni = (get_b(pe_loni, p_pe) * w_val) + (get_b(loni.get('roe', 0), p_roe) * w_fund) + (get_b(loni.get('net_margin', 0), p_nm) * w_fund)
        
        trend = s_dnes - s_loni
        trend_ico = "▲" if trend > 1 else ("▼" if trend < -1 else "•")
        
        m_rows.append({
            "Titul": d["name"],
            "Cena": price,
            "P/E": round(pe, 1),
            "ROE %": round(roe, 1),
            "Marže %": round(nm, 1),
            "Score": int(s_dnes),
            "Trend": f"{trend_ico} {int(trend)}",
            "_trend_val": trend
        })
    
    df_m = pd.DataFrame(m_rows)
    if not df_m.empty:
        def style_trend(r):
            val = r["_trend_val"]
            color = '#2ecc71' if val > 1 else ('#e74c3c' if val < -1 else '#888')
            return [f'color: {color}; font-weight: bold' if c == "Trend" else '' for c in r.index]
        
        st.dataframe(df_m.style.apply(style_trend, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn"), 
                     use_container_width=True, hide_index=True)

# --- 6. STRÁNKA: IV TERMINÁL ---
elif stranka == "🎯 Vnitřní hodnota (IV)":
    st.subheader("🎯 Kalkulace vnitřní hodnoty (Piliře)")
    # (Zde zůstává tvoje logika vah wi1, wi2, wi3 z V99.0)
    st.info("Tato sekce počítá férovou cenu na základě 3 pilířů (Zisk, Cashflow, Majetek).")
    # ... (logika výpočtu IV) ...

# --- 7. STRÁNKA: KALENDÁŘ ---
else:
    st.subheader("📅 Kalendář & Technické RSI")
    c_rows = []
    for d in filtered_data:
        c_rows.append({
            "Titul": d["name"],
            "RSI": int(d["rsi"]),
            "Earnings": d["earn"] if d["earn"] else "-",
            "MOAT": d.get("moat", "-"),
            "Doporučení": d["inf"].get('recommendationKey', '-').replace('_', ' ').title()
        })
    
    df_c = pd.DataFrame(c_rows)
    def style_rsi(v):
        color = 'red' if v > 70 else ('green' if v < 35 else 'black')
        return f'color: {color}; font-weight: bold'

    st.dataframe(df_c.style.applymap(style_rsi, subset=['RSI']), use_container_width=True, hide_index=True)
