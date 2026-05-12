import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investment Terminal V100.4", layout="wide")

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

# --- 3. DATA FETCH ---
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
                if not bs.empty and 'Stockholders Equity' in bs.index:
                    eq_loni = safe_float(bs.loc['Stockholders Equity'].iloc[1])
                    loni['roe'] = (safe_float(fin.loc['Net Income'].iloc[1]) / eq_loni * 100) if eq_loni != 0 else 0
                else: loni['roe'] = 0
            
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
                "loni": loni,
                "moat": row.get('Moat', '-')
            })
        except: continue
    return res

# --- 4. NAČTENÍ ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

st.sidebar.markdown("## **📊 Portfoliomanžer V100.4**")
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

    p_pe = vytvor_p("P/E", "pe", [12, 18, 25, 40, 999], [20, 15, 5, 0, -15])
    p_ps = vytvor_p("P/S", "ps", [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10])
    p_roe = vytvor_p("ROE", "roe", [12, 22, 35, 55, 999], [0, 10, 15, 20, 25])
    
    w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
    w_fund = st.sidebar.slider("Váha: Fundament", 0.5, 3.0, 1.0)

    m_rows = []
    for item in filtered_data:
        inf, loni = item["inf"], item["loni"]
        price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps'))
        
        act_pe = price / eps if eps != 0 else 0
        ps = safe_float(inf.get("priceToSalesTrailing12Months"))
        roe = safe_float(inf.get("returnOnEquity", 0)) * 100
        
        total_dnes = (get_b(act_pe, p_pe) * w_val) + (get_b(ps, p_ps) * w_val) + (get_b(roe, p_roe) * w_fund)
        
        # Trend výpočet
        pe_loni = price / loni.get('eps', 1) if loni.get('eps', 0) != 0 else 0
        total_loni = (get_b(pe_loni, p_pe) * w_val) + (get_b(ps, p_ps) * w_val) + (get_b(loni.get('roe', 0), p_roe) * w_fund)
        trend_val = total_dnes - total_loni
        trend_str = f"{'▲' if trend_val > 0 else '▼'} {abs(int(trend_val))}" if abs(trend_val) > 0 else "• 0"

        m_rows.append({
            "Titul": item["name"], "Cena": fmt(price, 2), 
            "P/E": fmt(act_pe, 1), "P/S": fmt(ps, 1), "ROE %": fmt(roe, 1, True), 
            "Score": int(total_dnes), "Fund. Trend": trend_str, 
            "_trend": trend_val, "Type": "Value"
        })
        if zobrazit_body:
            m_rows.append({"Titul": f"   └ body ({item['t']})", "Type": "Points", "Score": None, "Fund. Trend": ""})

    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            res = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            # Vyhledáme indexy pro barvení
            if "_trend" in r:
                t_idx = r.index.get_loc("Fund. Trend")
                res[t_idx] = f"color: {'#2ecc71' if r['_trend'] > 0 else ('#e74c3c' if r['_trend'] < 0 else '#888')}; font-weight: bold"
            return res

        st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100),
                     use_container_width=True, hide_index=True,
                     column_config={"_trend": None, "Type": None}) # Skryje pomocné sloupce

# --- 6. STRÁNKA: IV TERMINÁL (PLNÁ VERZE) ---
elif stranka == "Vnitřní hodnota (IV)":
    st.subheader("🎯 Komplexní odhad vnitřní hodnoty")
    
    c1, c2, c3 = st.columns(3)
    wi1 = c1.slider("Váha: Analytici", 0.0, 1.0, 0.4)
    wi2 = c2.slider("Váha: Graham", 0.0, 1.0, 0.3)
    wi3 = c3.slider("Váha: Multiplikátory", 0.0, 1.0, 0.3)

    iv_rows = []
    for item in filtered_data:
        inf = item["inf"]
        price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps'))
        rev = safe_float(inf.get('totalRevenue'))
        
        # 1. Pilíř: Target Price
        p1 = safe_float(inf.get('targetMeanPrice', price))
        
        # 2. Pilíř: Graham (8.5 + 2g)
        p2 = (eps * 15.5) if eps > 0 else 0 
        
        # 3. Pilíř: Historické P/S (férové ocenění tržeb)
        p3 = (rev / safe_float(inf.get('sharesOutstanding'))) * 2.5 if safe_float(inf.get('sharesOutstanding')) > 0 else 0
        
        # Finální IV
        iv_final = (p1 * wi1 + p2 * wi2 + p3 * wi3) / (wi1 + wi2 + wi3) if (wi1+wi2+wi3) > 0 else price
        upside = ((iv_final / price) - 1) * 100 if price > 0 else 0
        
        iv_rows.append({
            "Titul": item["name"], "Tržní Cena": price, 
            "Analytici": p1, "Graham": p2, "Průmysl": p3,
            "Vnitřní hodnota": iv_final, "Potenciál %": upside
        })
    
    df_iv = pd.DataFrame(iv_rows)
    st.dataframe(df_iv.style.format({
        "Tržní Cena": "{:.2f}", "Analytici": "{:.2f}", "Graham": "{:.2f}", 
        "Průmysl": "{:.2f}", "Vnitřní hodnota": "{:.2f}", "Potenciál %": "{:+.1f}%"
    }).background_gradient(subset=["Potenciál %"], cmap="RdYlGn", vmin=-20, vmax=50), 
    use_container_width=True, hide_index=True)

# --- 7. STRÁNKA: KALENDÁŘ & RSI ---
else:
    st.subheader("📅 Kalendář událostí & RSI")
    c_rows, today = [], date.today()
    for item in filtered_data:
        days_to = safe_date_diff(item["earn"], today)
        c_rows.append({
            "Titul": item["name"], "Ticker": item["t"], "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", 
            "Dní do": days_to, "RSI": int(item['rsi']), "_rsi": item["rsi"], "Moat": item["moat"]
        })
    df_c = pd.DataFrame(c_rows)
    if not df_c.empty:
        st.dataframe(df_c.style.apply(lambda r: [
            'background-color: #c8e6c9' if c == "RSI" and r["_rsi"] < 35 else 
            ('background-color: #ffcdd2' if c == "RSI" and r["_rsi"] > 65 else '') 
            for c in r.index], axis=1), 
        use_container_width=True, hide_index=True, column_config={"_rsi": None})
