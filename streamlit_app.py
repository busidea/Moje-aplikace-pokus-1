import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL (V86.6 ORIGINÁL) ---
st.set_page_config(page_title="Investment Terminal V100.0", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { 
        text-align: left !important; 
        font-weight: bold !important;
        color: #003366 !important;
    }
    /* Styl pro řádky s body */
    .points-row { color: #888 !important; font-style: italic !important; background-color: #f8f9fa !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE (V86.6) ---
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
    try: return float(val) if val is not None else 0.0
    except: return 0.0

# --- 3. DATA FETCH S TRENDEM ---
@st.cache_data(ttl=3600)
def fetch_data_full(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t == "-": continue
        try:
            tk = yf.Ticker(t); inf = tk.info
            fin = tk.financials; bs = tk.balance_sheet
            
            # Loňská data pro trend
            loni = {}
            if not fin.empty and len(fin.columns) > 1:
                loni['eps'] = safe_float(fin.loc['Basic EPS'].iloc[1]) if 'Basic EPS' in fin.index else 0
                loni['rev'] = safe_float(fin.loc['Total Revenue'].iloc[1]) if 'Total Revenue' in fin.index else 0
                if not bs.empty and 'Stockholders Equity' in bs.index:
                    equity_loni = safe_float(bs.loc['Stockholders Equity'].iloc[1])
                    loni['roe'] = (safe_float(fin.loc['Net Income'].iloc[1]) / equity_loni * 100) if equity_loni != 0 else 0
                else: loni['roe'] = 0
            
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
                
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": str(row.get('Kategorie')), "earn": row.get('Earnings Day'), "name": inf.get('longName', t), "loni": loni})
        except: continue
    return res

# --- 4. NAČTENÍ A SIDEBAR ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(ODKAZ_NA_TABULKU) # (funkce nacti_seznam zůstává stejná)

st.sidebar.markdown("## **📊 Portfoliomanžer V100**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Kalendář & RSI", "Vnitřní hodnota (IV)"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

raw_data = fetch_data_full(df_raw)

# --- 5. SCORING MATRIX STRÁNKA ---
if stranka == "Scoring Matrix":
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní body", value=False)
    
    # ... (zde jsou tvé definice expanderů p_pe, p_ps, p_gm atd. z V86.6) ...
    # Pro stručnost je zde neuvádím celé, ale v kódu musí být zachovány.
    
    m_rows = []
    mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    
    for item in raw_data:
        if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
        inf, loni = item["inf"], item["loni"]
        price = safe_float(inf.get('currentPrice'))
        
        # Aktuální hodnoty
        raw_vals = {
            "Cena": price, "Změna": ((price/safe_float(inf.get("previousClose", 1)))-1)*100,
            "P/E": safe_float(inf.get("trailingPE") or inf.get("forwardPE")), 
            "P/S": safe_float(inf.get("priceToSalesTrailing12Months")),
            "ROE": safe_float(inf.get("returnOnEquity", 0)) * 100,
            # ... (další hodnoty jako v V86.6)
        }
        
        # VÝPOČET SCORE (Dnešní)
        total_dnes = 0
        p_map = {"P/E":p_pe, "P/S":p_ps, "ROE":p_roe} # atd.
        for k in mapping_keys:
            if k in p_map: total_dnes += get_b(raw_vals.get(k, 0), p_map[k])

        # VÝPOČET SCORE (Stínové YoY)
        total_loni = 0
        if loni:
            pe_loni = price / loni['eps'] if loni.get('eps', 0) > 0 else 0
            total_loni += get_b(pe_loni, p_pe)
            total_loni += get_b(loni.get('roe', 0), p_roe)
            # ... atd pro marže
        
        trend_val = total_dnes - total_loni
        trend_str = f"{'▲' if trend_val > 0 else '▼'} {abs(int(trend_val))}" if abs(trend_val) > 0 else "• 0"

        row_v = {"Titul": item["name"], "Type": "Value", "Score": int(total_dnes), "Fund. Trend": trend_str, "_trend": trend_val, "_change": raw_vals["Změna"]}
        # ... (naplnění row_v hodnotami fmt() jako v V86.6)
        m_rows.append(row_v)
        
        if zobrazit_body:
            m_rows.append({"Titul": f"   └ body ({item['t']})", "Type": "Points", "Score": "", "Fund. Trend": ""})

    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            s = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            
            # Formátování Trendu
            t_idx = r.index.get_loc("Fund. Trend")
            s[t_idx] = f"color: {'#2ecc71' if r['_trend'] > 0 else '#e74c3c'}; font-weight: bold"
            
            # Ostatní tvé styly (Cena, Změna atd.) z V86.6
            return s

        st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                     use_container_width=True, hide_index=True, height=800)

# --- 6. KALENDÁŘ (V86.6 ORIGINÁL) ---
elif stranka == "Kalendář & RSI":
    # ... (Zde je tvůj kompletní kód sekce Kalendář z V86.6 bez jediné změny) ...
    st.subheader("📅 Kalendář událostí & RSI")
    # ...
