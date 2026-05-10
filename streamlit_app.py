import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- KONFIGURACE ---
st.set_page_config(page_title="Scoring firem V86.2", layout="wide")

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

# --- 1. POMOCNÉ FUNKCE ---
def safe_date_diff(earn_val, today):
    """Bezpečně vypočítá rozdíl dní, i když datum chybí nebo je neplatné."""
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]:
        return 999
    try:
        dt = pd.to_datetime(earn_val, dayfirst=True).date()
        return (dt - today).days
    except:
        return 999

def get_b_direct(val, h_list, b_list):
    if val is None or val == 0: return 0
    for h, b in zip(h_list, b_list):
        if val <= h: return b
    return b_list[-1]

def fmt(val, precision=1, is_pct=False):
    if val is None or val == 0: return "0.0" + ("%" if is_pct else "")
    res = f"{val:.{precision}f}"
    return res + "%" if is_pct else res

# --- 2. NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except: return pd.DataFrame()

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 3. UI A FILTRY ---
st.sidebar.markdown("## **📊 Portfoliomanžer**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Kalendář & RSI"])
st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr kategorie:", ["Portfolio", "Sledované", "Vše"], index=0)

# --- 4. DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_data(df_input):
    res = []
    # Předběžný filtr tickerů, aby se netahala zbytečná data
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t == "-": continue
        try:
            tk = yf.Ticker(t); inf = tk.info; hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff()
                g = d.where(d > 0, 0).rolling(14).mean()
                l = -d.where(d < 0, 0).rolling(14).mean()
                last_l = l.iloc[-1]
                rsi = 100 - (100 / (1 + (g.iloc[-1]/last_l))) if last_l != 0 else 50
            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie')), 
                "earn": row.get('Earnings Day'), 
                "name": inf.get('longName', t)
            })
        except: continue
    return res

raw_data = fetch_data(df_raw)

# --- 5. ZPRACOVÁNÍ DAT ---
m_rows, c_rows, today = [], [], date.today()
mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
pct_cols = ["Změna", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"]

for item in raw_data:
    # APLIKACE FILTRU
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    
    inf, t, name = item["inf"], item["t"], item["name"]
    def sg(k, mult=1.0):
        v = inf.get(k)
        return float(v) * mult if v is not None and str(v) != "None" else 0.0

    div_val = sg("dividendYield") * 100
    if div_val > 50: div_val /= 100

    raw_vals = {
        "Cena": sg("currentPrice"), 
        "Změna": ((sg("currentPrice")/sg("previousClose", 1.0))-1)*100 if sg("previousClose") else 0,
        "P/E": sg("trailingPE") or sg("forwardPE"), "P/S": sg("priceToSalesTrailing12Months"), 
        "P/B": sg("priceToBook"), "P/FCF": sg("marketCap")/sg("freeCashflow") if sg("freeCashflow") else 0,
        "H-Marže": sg("grossMargins", 100), "Č-Marže": sg("profitMargins", 100), 
        "ROE": sg("returnOnEquity", 100), "Tržby y/y": sg("revenueGrowth", 100), 
        "Zisk y/y": sg("earningsGrowth", 100), "Dluh D/E": sg("debtToEquity"), 
        "Div. výnos": div_val, "Potenciál": ((sg("targetMeanPrice")/sg("currentPrice", 1.0))-1)*100 if sg("targetMeanPrice") else 0
    }

    # Bodování (Konzervativní logika)
    total_score = 0
    for k in mapping_keys:
        total_score += get_b_direct(raw_vals[k], [15, 25, 40], [15, 5, -10])

    # Matrix řádek
    row = {"Titul": name, "_change": raw_vals["Změna"], "Score": int(total_score)}
    for k in mapping_keys:
        row[k] = fmt(raw_vals[k], 1, k in pct_cols)
        row[f"_raw_{k}"] = raw_vals[k]
    row["Cena"] = fmt(raw_vals["Cena"], 2)
    row["Změna"] = fmt(raw_vals["Změna"], 1, True)
    m_rows.append(row)

    # Kalendář řádek
    days_to = safe_date_diff(item["earn"], today)
    ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
    
    c_rows.append({
        "Titul": name, "Ticker": t, "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", 
        "Dní do": days_to, "Dividenda": f"{sg('dividendRate'):.2f} {inf.get('currency', 'USD')}", 
        "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", 
        "Doporučení": inf.get('recommendationKey', '-').replace('_', ' ').title(), 
        "RSI": int(item['rsi']), "_rsi": item["rsi"]
    })

# --- 6. ZOBRAZENÍ ---
if stranka == "Scoring Matrix":
    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            s = [''] * len(r)
            for i, col in enumerate(r.index):
                if col in ["Cena", "Změna"]: 
                    s[i] = f"color: {'#1b5e20' if r['_change']>0 else '#b71c1c'}; font-weight: bold"
                val = r.get(f"_raw_{col}", 0)
                if col == "P/E" and val > 25: s[i] = 'background-color: #ffebee'
                if col == "Dluh D/E" and val > 150: s[i] = 'background-color: #ffcdd2; color: #b71c1c'
            return s
        
        st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=100),
                     use_container_width=True, hide_index=True, height=800,
                     column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"])
else:
    df_c = pd.DataFrame(c_rows)
    if not df_c.empty:
        def style_calendar(r):
            s = [''] * len(r)
            d_idx = r.index.get_loc("Dní do")
            if r["Dní do"] < 0: s[d_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            elif r["Dní do"] < 10: s[d_idx] = 'background-color: #fff9c4; color: #f57f17; font-weight: bold'
            
            rec = str(r["Doporučení"]).lower()
            rec_idx = r.index.get_loc("Doporučení")
            if "buy" in rec: s[rec_idx] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold'
            elif "sell" in rec: s[rec_idx] = 'background-color: #ffcdd2; color: #b71c1c'
            elif "hold" in rec: s[rec_idx] = 'background-color: #fff9c4'
            
            rsi_idx = r.index.get_loc("RSI")
            if r["_rsi"] < 35: s[rsi_idx] = 'background-color: #c8e6c9; font-weight: bold'
            elif r["_rsi"] > 65: s[rsi_idx] = 'background-color: #ffcdd2; font-weight: bold'
            return s
            
        st.dataframe(df_c.style.apply(style_calendar, axis=1), use_container_width=True, hide_index=True, height=800,
                     column_order=["Titul", "Ticker", "Earnings", "Dní do", "Dividenda", "Ex-Date", "Doporučení", "RSI"])
