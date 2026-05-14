import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="Investment Hub V103", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { 
        text-align: left !important; font-weight: bold !important; color: #003366 !important;
    }
    .main .block-container { padding-top: 1rem; padding-bottom: 1rem; }
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
    return res + ("%" if is_pct else "")

@st.cache_data(ttl=86400)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. KOMPLETNÍ DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_all(df_input):
    res = []
    if df_input.empty: return []
    pb = st.progress(0)
    msg = st.empty()
    tickers = df_input.to_dict('records')
    for i, row in enumerate(tickers):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t in ["-", "NAN"]: continue
        msg.text(f"Načítám hloubková data: {t}")
        pb.progress((i + 1) / len(tickers))
        try:
            tk = yf.Ticker(t); inf = tk.info
            if 'currentPrice' not in inf: continue
            time.sleep(0.3)
            
            # Získání historických průměrů (3 roky)
            fin = tk.financials; bs = tk.balance_sheet
            avg_roe, avg_nm, avg_gm = 0, 0, 0
            if not fin.empty and not bs.empty:
                try:
                    # Ošetření různých názvů v Yahoo Finance
                    rev = fin.get('Total Revenue', fin.get('Total Operating Revenue', pd.Series()))
                    ni = fin.get('Net Income', pd.Series())
                    gp = fin.get('Gross Profit', pd.Series())
                    eq = bs.get('Stockholders Equity', bs.get('Total Equity Gross Minority Interest', pd.Series()))
                    
                    if not rev.empty and not ni.empty:
                        avg_nm = (ni / rev).head(3).mean() * 100
                    if not rev.empty and not gp.empty:
                        avg_gm = (gp / rev).head(3).mean() * 100
                    if not ni.empty and not eq.empty:
                        avg_roe = (ni / eq.head(len(ni))).head(3).mean() * 100
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
    pb.empty(); msg.empty()
    return res

# --- 4. SIDEBAR OVLADAČE ---
URL = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(URL)

st.sidebar.title("⚙️ Nastavení")
stranka = st.sidebar.radio("Zobrazení:", ["🏠 Scoring Matrix", "🎯 Vnitřní hodnota (IV)", "📅 Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

# Ovladače Matrixu
def setup_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"Parametry {nazev}", expanded=False):
        return [{"h": st.number_input(f"Do {nazev} {i}", value=float(def_h[i]), key=f"{zk}{i}"), 
                 "b": st.number_input(f"Body {nazev} {i}", value=int(def_b[i]), key=f"{zk}b{i}")} for i in range(5)]

p_pe = setup_p("P/E", "pe", [12, 18, 25, 40, 999], [20, 15, 5, 0, -15])
p_roe = setup_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
# ... (Zde si můžeš přidat další setup_p dle libosti)
w_val = st.sidebar.slider("Váha Valuace", 0.5, 3.0, 1.0)
w_fund = st.sidebar.slider("Váha Fundament", 0.5, 3.0, 1.0)
show_points = st.sidebar.checkbox("Zobrazit body pod daty", value=False)

if not df_raw.empty:
    data = fetch_all(df_raw)
    f_data = [d for d in data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

    if f_data:
        keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div.", "Potenciál"]
        
        if stranka == "🏠 Scoring Matrix":
            m_rows = []
            for item in f_data:
                inf = item["inf"]; p = safe_float(inf.get('currentPrice'))
                raw = {
                    "P/E": p/safe_float(inf.get("trailingEps")) if safe_float(inf.get("trailingEps")) != 0 else 0,
                    "P/S": safe_float(inf.get("priceToSalesTrailing12Months")),
                    "P/B": safe_float(inf.get("priceToBook")),
                    "P/FCF": safe_float(inf.get("marketCap"))/safe_float(inf.get("freeCashflow")) if safe_float(inf.get("freeCashflow")) else 0,
                    "H-Marže": item["avg_gm"] if item["avg_gm"] != 0 else safe_float(inf.get("grossMargins", 0))*100,
                    "Č-Marže": item["avg_nm"] if item["avg_nm"] != 0 else safe_float(inf.get("profitMargins", 0))*100,
                    "ROE": item["avg_roe"] if item["avg_roe"] != 0 else safe_float(inf.get("returnOnEquity", 0))*100,
                    "Tržby y/y": safe_float(inf.get("revenueGrowth", 0))*100,
                    "Zisk y/y": safe_float(inf.get("earningsGrowth", 0))*100,
                    "Dluh D/E": safe_float(inf.get("debtToEquity", 0)),
                    "Div.": safe_float(inf.get("dividendYield", 0))*100,
                    "Potenciál": ((safe_float(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0
                }

                score = 0
                row_p = {"Titul": f"   └ body ({item['t']})"}
                for k in keys:
                    # Příklad bodování (pro všechny klíče by se použilo get_b a příslušné p_map)
                    b = 10 # Dočasná konstanta, zde doplníš svůj get_b
                    score += b
                    row_p[k] = str(b)

                row_v = {"Titul": item["name"], "Cena": f"{p:.2f}", "Score": int(score)}
                for k in keys:
                    if k == "Dluh D/E": row_v[k] = f"{raw[k]:.0f}%"
                    elif k == "Div.": row_v[k] = f"{raw[k]:.1f}%"
                    else: row_v[k] = fmt(raw[k], 1, k in ["H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Potenciál"])
                
                m_rows.append(row_v)
                if show_points: m_rows.append(row_p)

            df_m = pd.DataFrame(m_rows)
            st.dataframe(df_m.style.background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True, hide_index=True)

        elif stranka == "🎯 Vnitřní hodnota (IV)":
            iv_rows = []
            for item in f_data:
                inf = item["inf"]; p = safe_float(inf.get('currentPrice'))
                p1 = safe_float(inf.get('targetMeanPrice', p))
                p2 = (safe_float(inf.get('trailingEps')) * 15) if safe_float(inf.get('trailingEps')) > 0 else 0
                p3 = safe_float(inf.get('bookValue', 0)) * 1.5
                fair = (p1 + p2 + p3) / 3
                up = ((fair/p)-1)*100
                iv_rows.append({"Titul": item["name"], "Tržní": p, "Pilíř I (Cíle)": int(p1), "Pilíř II (Zisk)": int(p2), "Pilíř III (Majetek)": int(p3), "Férová": int(fair), "Potenciál %": f"{up:.1f}%", "_up": up})
            st.dataframe(pd.DataFrame(iv_rows).style.background_gradient(subset=["_up"], cmap="RdYlGn"), use_container_width=True, hide_index=True)
            st.info("💡 **Pilíř I:** Analytici | **Pilíř II:** Graham (15x EPS) | **Pilíř III:** Majetek (1.5x BV)")

        else:
            c_rows = []
            for d in f_data:
                days = "-"
                try:
                    diff = (datetime.strptime(d["earn"], "%d.%m.%Y") - datetime.now()).days
                    days = f"{diff} dní"
                except: pass
                c_rows.append({"Titul": d["name"], "Earnings": d["earn"], "Dní do": days, "RSI": int(d["rsi"]), "Analytici": d["inf"].get("recommendationKey", "N/A").title()})
            
            df_c = pd.DataFrame(c_rows)
            # OPRAVA: Místo applymap používáme map
            st.dataframe(df_c.style.map(lambda x: 'background-color: #2ecc71' if x in ['Buy', 'Strong Buy'] else '', subset=['Analytici']), use_container_width=True, hide_index=True)
