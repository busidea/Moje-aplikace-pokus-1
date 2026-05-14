import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="Investment Hub V101", layout="wide")

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

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        return df
    except Exception as e:
        st.error(f"Chyba při načítání Google tabulky: {e}")
        return pd.DataFrame()

# --- 3. DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_data_full(df_input):
    res = []
    if df_input.empty: return []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t in ["-", "NAN", "None"]: continue
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
                "earn": row.get('Earnings Day', '-'), 
                "name": inf.get('longName', t), 
                "loni": loni, "moat": row.get('Moat', '-')
            })
        except: continue
    return res

# --- 4. NAČTENÍ A SIDEBAR ---
URL = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(URL)

st.sidebar.markdown("## **📊 Portfoliomanžer V101**")
stranka = st.sidebar.radio("Zobrazení:", ["🏠 Scoring Matrix", "🎯 Vnitřní hodnota (IV)", "📅 Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)

if df_raw.empty:
    st.warning("Seznam tickerů je prázdný. Zkontroluj Google tabulku.")
else:
    with st.spinner('Stahuji data z Yahoo Finance...'):
        all_data = fetch_data_full(df_raw)
    
    filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

    if not filtered_data:
        st.info(f"Žádná data pro kategorii: {filtr_kat}")
    
    # --- 5. STRÁNKY ---
    if stranka == "🏠 Scoring Matrix":
        zobrazit_body = st.sidebar.checkbox("Zobrazit body pod daty", value=False)
        
        # Parametry Matrixu
        def setup_p(nazev, zk, def_h, def_b):
            with st.sidebar.expander(f"Parametry {nazev}", expanded=False):
                return [{"h": st.number_input(f"Do {nazev} {i}", value=float(def_h[i]), key=f"{zk}{i}"), 
                         "b": st.number_input(f"Body {nazev} {i}", value=int(def_b[i]), key=f"{zk}b{i}")} for i in range(5)]

        p_pe = setup_p("P/E", "pe", [12, 18, 25, 40, 999], [20, 15, 5, 0, -15])
        p_ps = setup_p("P/S", "ps", [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10])
        p_pb = setup_p("P/B", "pb", [1, 2.5, 4, 8, 999], [10, 7, 3, 0, -5])
        p_fcf = setup_p("P/FCF", "fcf", [12, 20, 35, 50, 999], [20, 12, 5, 0, -10])
        p_gm = setup_p("H-Marže", "gm", [20, 35, 50, 70, 999], [0, 8, 15, 20, 25])
        p_nm = setup_p("Č-Marže", "nm", [10, 20, 30, 45, 999], [0, 10, 18, 22, 30])
        p_roe = setup_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
        p_rev = setup_p("Tržby y/y", "rev", [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35])
        p_eps = setup_p("Zisk y/y", "eps", [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40])
        p_deb = setup_p("Dluh D/E", "deb", [40, 80, 120, 200, 999], [20, 10, 0, -15, -40])
        p_div = setup_p("Div.", "div", [2, 4, 6, 8, 999], [5, 12, 15, 10, 5])
        p_pot = setup_p("Potenciál", "pot", [8, 18, 28, 45, 999], [0, 10, 18, 25, 35])

        w_val = st.sidebar.slider("Váha Valuace", 0.5, 3.0, 1.0)
        w_fund = st.sidebar.slider("Váha Fundament", 0.5, 3.0, 1.0)

        m_rows = []
        keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div.", "Potenciál"]
        p_map = {"P/E":p_pe,"P/S":p_ps,"P/B":p_pb,"P/FCF":p_fcf,"H-Marže":p_gm,"Č-Marže":p_nm,"ROE":p_roe,"Tržby y/y":p_rev,"Zisk y/y":p_eps,"Dluh D/E":p_deb,"Div.":p_div,"Potenciál":p_pot}

        for item in filtered_data:
            inf, loni = item["inf"], item["loni"]
            p = safe_float(inf.get('currentPrice'))
            raw = {
                "P/E": p/safe_float(inf.get("trailingEps")) if safe_float(inf.get("trailingEps")) != 0 else 0,
                "P/S": safe_float(inf.get("priceToSalesTrailing12Months")), "P/B": safe_float(inf.get("priceToBook")),
                "P/FCF": safe_float(inf.get("marketCap"))/safe_float(inf.get("freeCashflow")) if safe_float(inf.get("freeCashflow")) else 0,
                "H-Marže": safe_float(inf.get("grossMargins", 0))*100, "Č-Marže": safe_float(inf.get("profitMargins", 0))*100, "ROE": safe_float(inf.get("returnOnEquity", 0))*100,
                "Tržby y/y": safe_float(inf.get("revenueGrowth", 0))*100, "Zisk y/y": safe_float(inf.get("earningsGrowth", 0))*100, "Dluh D/E": safe_float(inf.get("debtToEquity", 0)),
                "Div.": safe_float(inf.get("dividendYield", 0))*100, "Potenciál": ((safe_float(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0
            }

            score_dnes = 0
            row_p = {"Titul": f"   └ body ({item['t']})", "Type": "Points"}
            for k in keys:
                vw = w_val if k in ["P/E","P/S","P/B","P/FCF"] else w_fund
                b = get_b(raw[k], p_map[k]) * vw
                score_dnes += b
                row_p[k] = str(int(round(b)))

            pe_loni = p / loni['eps'] if loni['eps'] != 0 else 0
            score_loni = (get_b(pe_loni, p_pe) * w_val) + (get_b(loni['roe'], p_roe) * w_fund)
            for k in [m for m in keys if m not in ["P/E", "ROE"]]:
                score_loni += get_b(raw[k], p_map[k]) * (w_val if k in ["P/S","P/B","P/FCF"] else w_fund)
            
            diff = score_dnes - score_loni
            trend = f"{'▲' if diff > 0 else ('▼' if diff < 0 else '•')} {abs(int(diff))}"

            row_v = {"Titul": item["name"], "Cena": f"{p:.2f}", "Score": int(score_dnes), "Trend": trend, "_t": diff, "Type": "Val"}
            for k in keys:
                row_v[k] = fmt(raw[k], 1, k in ["H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Div.", "Potenciál"])
            
            m_rows.append(row_v)
            if zobrazit_body: m_rows.append(row_p)

        df_m = pd.DataFrame(m_rows)
        st.dataframe(df_m.style.apply(lambda r: [f"color: {'#2ecc71' if r['_t']>0 else '#e74c3c' if r['_t']<0 else '#888'}; font-weight: bold" if c == "Trend" else "" for c in r.index], axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                     use_container_width=True, hide_index=True, column_order=["Titul", "Cena"] + keys + ["Score", "Trend"], column_config={"_t": None, "Type": None})

    elif stranka == "🎯 Vnitřní hodnota (IV)":
        st.subheader("🎯 Kalkulace vnitřní hodnoty (Pilíře)")
        iv_rows = []
        for item in filtered_data:
            inf = item["inf"]; p = safe_float(inf.get('currentPrice'))
            p1 = safe_float(inf.get('targetMeanPrice', p))
            p2 = (safe_float(inf.get('trailingEps')) * 15) if safe_float(inf.get('trailingEps')) > 0 else 0
            fair = (p1 + p2) / 2 if p2 > 0 else p1
            up = ((fair / p) - 1) * 100 if p > 0 else 0
            iv_rows.append({"Titul": item["name"], "Cena": p, "IV Analytici": p1, "IV Graham": p2, "Férová cena": int(fair), "Potenciál %": f"{up:.1f}%", "_up": up})
        st.dataframe(pd.DataFrame(iv_rows).style.background_gradient(subset=["_up"], cmap="RdYlGn"), use_container_width=True, hide_index=True, column_config={"_up": None})

    else:
        st.subheader("📅 Kalendář událostí & RSI")
        c_rows = [{"Titul": d["name"], "Ticker": d["t"], "Earnings": d["earn"], "RSI": int(d["rsi"]), "Moat": d["moat"]} for d in filtered_data]
        st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)
