import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime, date

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="Investment Hub V102.1", layout="wide")

# CSS pro zarovnání a barvy
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

@st.cache_data(ttl=86400)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. DATA FETCH (Konzervativní) ---
@st.cache_data(ttl=3600)
def fetch_data_light(df_input):
    res = []
    if df_input.empty: return []
    
    progress_text = st.empty()
    bar = st.progress(0)
    
    tickers = df_input.to_dict('records')
    for i, row in enumerate(tickers):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t in ["-", "NAN"]: continue
        
        progress_text.text(f"Stahuji data pro: {t}")
        bar.progress((i + 1) / len(tickers))
        
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            
            if 'currentPrice' not in inf:
                continue
                
            time.sleep(0.3) # Pauza pro Yahoo
            
            # RSI historie
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff()
                g = d.where(d > 0, 0).rolling(14).mean()
                l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie', 'Vše')), 
                "earn": row.get('Earnings Day', '-'), 
                "name": inf.get('longName', t)
            })
        except: continue
        
    progress_text.empty()
    bar.empty()
    return res

# --- 4. NAČTENÍ DAT A MENU ---
URL = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(URL)

st.sidebar.title("Investment Hub V102.1")
stranka = st.sidebar.radio("Zobrazení:", ["🏠 Scoring Matrix", "🎯 Vnitřní hodnota (IV)", "📅 Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)

if not df_raw.empty:
    all_data = fetch_data_light(df_raw)
    filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

    if not filtered_data:
        st.warning("Čekám na data z Yahoo... Pokud se nic nezobrazí, zkuste Refresh.")
    else:
        # Pásma pro Matrix
        p_pe = [{"h": 12, "b": 20}, {"h": 18, "b": 15}, {"h": 25, "b": 5}, {"h": 40, "b": 0}, {"h": 999, "b": -15}]
        p_ps = [{"h": 1.5, "b": 15}, {"h": 3, "b": 10}, {"h": 6, "b": 5}, {"h": 10, "b": 0}, {"h": 999, "b": -10}]
        p_pb = [{"h": 1, "b": 10}, {"h": 2.5, "b": 7}, {"h": 4, "b": 3}, {"h": 8, "b": 0}, {"h": 999, "b": -5}]
        p_fcf = [{"h": 12, "b": 20}, {"h": 20, "b": 12}, {"h": 35, "b": 5}, {"h": 50, "b": 0}, {"h": 999, "b": -10}]
        p_gm = [{"h": 20, "b": 0}, {"h": 35, "b": 8}, {"h": 50, "b": 15}, {"h": 70, "b": 20}, {"h": 999, "b": 25}]
        p_nm = [{"h": 10, "b": 0}, {"h": 20, "b": 10}, {"h": 30, "b": 18}, {"h": 45, "b": 22}, {"h": 999, "b": 30}]
        p_roe = [{"h": 12, "b": 0}, {"h": 22, "b": 10}, {"h": 35, "b": 15}, {"h": 55, "b": 20}, {"h": 999, "b": 25}]
        p_rev = [{"h": 0, "b": -10}, {"h": 10, "b": 8}, {"h": 20, "b": 15}, {"h": 35, "b": 25}, {"h": 999, "b": 35}]
        p_eps = [{"h": 0, "b": -15}, {"h": 10, "b": 10}, {"h": 25, "b": 20}, {"h": 45, "b": 28}, {"h": 999, "b": 40}]
        p_deb = [{"h": 40, "b": 20}, {"h": 80, "b": 10}, {"h": 120, "b": 0}, {"h": 200, "b": -15}, {"h": 999, "b": -40}]
        p_div = [{"h": 2, "b": 5}, {"h": 4, "b": 12}, {"h": 6, "b": 15}, {"h": 8, "b": 10}, {"h": 999, "b": 5}]
        p_pot = [{"h": 8, "b": 0}, {"h": 18, "b": 10}, {"h": 28, "b": 18}, {"h": 45, "b": 25}, {"h": 999, "b": 35}]
        
        p_map = {"P/E":p_pe, "P/S":p_ps, "P/B":p_pb, "P/FCF":p_fcf, "H-Marže":p_gm, "Č-Marže":p_nm, "ROE":p_roe, "Tržby y/y":p_rev, "Zisk y/y":p_eps, "Dluh D/E":p_deb, "Div.":p_div, "Potenciál":p_pot}
        keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div.", "Potenciál"]

        # --- SCORING MATRIX ---
        if stranka == "🏠 Scoring Matrix":
            st.subheader("📊 Kvalitativní Scoring Matrix")
            m_rows = []

            for item in filtered_data:
                inf = item["inf"]
                p = safe_float(inf.get('currentPrice'))
                
                raw = {
                    "P/E": p/safe_float(inf.get("trailingEps")) if safe_float(inf.get("trailingEps")) != 0 else 0,
                    "P/S": safe_float(inf.get("priceToSalesTrailing12Months")),
                    "P/B": safe_float(inf.get("priceToBook")),
                    "P/FCF": safe_float(inf.get("marketCap"))/safe_float(inf.get("freeCashflow")) if safe_float(inf.get("freeCashflow")) else 0,
                    "H-Marže": safe_float(inf.get("grossMargins", 0))*100,
                    "Č-Marže": safe_float(inf.get("profitMargins", 0))*100,
                    "ROE": safe_float(inf.get("returnOnEquity", 0))*100,
                    "Tržby y/y": safe_float(inf.get("revenueGrowth", 0))*100,
                    "Zisk y/y": safe_float(inf.get("earningsGrowth", 0))*100,
                    "Dluh D/E": safe_float(inf.get("debtToEquity", 0)),
                    "Div.": safe_float(inf.get("dividendYield", 0))*100,
                    "Potenciál": ((safe_float(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0
                }

                total_score = 0
                for k in keys:
                    total_score += get_b(raw[k], p_map[k])

                row_v = {"Titul": item["name"], "Cena": f"{p:.2f}", "Score": int(total_score)}
                for k in keys:
                    row_v[k] = fmt(raw[k], 1, k in ["H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Div.", "Potenciál"])
                m_rows.append(row_v)

            df_m = pd.DataFrame(m_rows)
            st.dataframe(df_m.style.background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                         use_container_width=True, hide_index=True, 
                         column_order=["Titul", "Cena"] + keys + ["Score"])

        # --- IV TERMINÁL ---
        elif stranka == "🎯 Vnitřní hodnota (IV)":
            st.subheader("🎯 Vnitřní hodnota (Pilíře)")
            iv_rows = []
            for item in filtered_data:
                inf = item["inf"]
                p = safe_float(inf.get('currentPrice'))
                p1 = safe_float(inf.get('targetMeanPrice', p))
                p2 = (safe_float(inf.get('trailingEps')) * 15) if safe_float(inf.get('trailingEps')) > 0 else 0
                fair = (p1 + p2) / 2
                up = ((fair/p)-1)*100 if p > 0 else 0
                iv_rows.append({"Titul": item["name"], "Tržní cena": p, "Férová cena": int(fair), "Potenciál %": f"{up:.1f}%", "_up": up})
            
            st.dataframe(pd.DataFrame(iv_rows).style.background_gradient(subset=["_up"], cmap="RdYlGn"), 
                         use_container_width=True, hide_index=True, column_config={"_up": None})

        # --- KALENDÁŘ ---
        else:
            st.subheader("📅 Kalendář & RSI")
            c_rows = [{"Titul": d["name"], "Ticker": d["t"], "Earnings": d["earn"], "RSI": int(d["rsi"])} for d in filtered_data]
            st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)
else:
    st.error("Nepodařilo se načíst seznam tickerů. Zkontrolujte odkaz na Google Sheets.")
