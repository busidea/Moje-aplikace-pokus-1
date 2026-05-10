import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# Konfigurace stránky
st.set_page_config(page_title="Scoring firem V85.2", layout="wide")

# --- GLOBÁLNÍ CSS PRO ZAROVNÁNÍ DOPRAVA A STYLING ---
st.markdown("""
    <style>
    /* Vynucení zarovnání doprava pro buňky v tabulkách */
    [data-testid="stTable"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    /* Zarovnání hlaviček doprava */
    [data-testid="stDataFrame"] th { text-align: right !important; }
    /* Levý sloupec (Titul) chceme nechat vlevo */
    [data-testid="stDataFrame"] td:first-child { text-align: left !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 1. POMOCNÉ FUNKCE ---
def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def get_b_direct(val, h_list, b_list):
    if val is None or val == 0: return 0
    for h, b in zip(h_list, b_list):
        if val <= h: return b
    return b_list[-1]

def format_cz(val, precision=1, is_pct=False):
    try:
        if val == "" or val is None: return ""
        if precision == 0:
            s = f"{int(round(val)):,}".replace(",", " ")
        else:
            s = f"{val:,.{precision}f}".replace(",", "X").replace(".", ",").replace("X", " ")
        if is_pct: s += "%"
        return s
    except:
        return str(val)

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

# --- 3. LEVÁ LIŠTA ---
st.sidebar.markdown("## **📊 Portfoliomanžer**")
stranka = st.sidebar.radio("Zvolte zobrazení:", ["Scoring Matrix", "Kalendář & RSI"])
st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Zobrazit pro:", ["Portfolio", "Sledované", "Vše"], index=0)

w_val, w_prof, w_growth, w_risk = 1.2, 1.5, 1.0, 1.8

if stranka == "Scoring Matrix":
    strategie = st.sidebar.selectbox("Nastavení:", ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový", "⚖️ Vyvážený"], index=0)
    st.sidebar.divider()
    status_text = "⚠️ Zobrazit detailní body" if "zobrazit_body" not in st.session_state or not st.session_state.zobrazit_body else "✅ Body jsou zobrazeny"
    zobrazit_body = st.sidebar.checkbox(status_text, value=False, key="zobrazit_body")
    
    if strategie == "Vlastní":
        with st.sidebar.expander("⚙️ Nastavení vah", expanded=False):
            w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.2)
            w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.5)
            w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
            w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.8)
else:
    zobrazit_body = False

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
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": row.get('Kategorie'), "earn": row.get('Earnings Day'), "name": inf.get('longName', t)})
        except: continue
    return res

raw_data = fetch_data(df_raw)

# --- 5. VÝPOČET ---
m_rows, c_rows, today = [], [], date.today()
mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]
pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]

for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t, name = item["inf"], item["t"], item["name"]
    
    def safe_get(k, multiplier=1.0):
        v = inf.get(k)
        try:
            if v is None or str(v) == "None" or str(v) == "": return 0.0
            return float(v) * multiplier
        except: return 0.0

    d_yield = inf.get('dividendYield')
    val_div = (float(d_yield) * (1.0 if float(d_yield) >= 1.0 else 100.0)) if d_yield else 0.0

    raw_vals = {
        "Ticker": t, "Titul": name, "Cena": safe_get("currentPrice"), 
        "Změna": ((safe_get("currentPrice")/safe_get("previousClose", 1.0))-1)*100 if safe_get("previousClose") != 0 else 0,
        "P/E": safe_get("trailingPE") or safe_get("forwardPE"), "P/S": safe_get("priceToSalesTrailing12Months"), 
        "P/B": safe_get("priceToBook"), "P/FCF": safe_get("marketCap")/safe_get("freeCashflow") if safe_get("freeCashflow")!=0 else 0,
        "H-Marže": safe_get("grossMargins", 100), "H-Marže 3Y": safe_get("grossMargins", 94),
        "Č-Marže": safe_get("profitMargins", 100), "Č-Marže 3Y": safe_get("profitMargins", 91),
        "ROE": safe_get("returnOnEquity", 100), "ROE 3Y": safe_get("returnOnEquity", 93),
        "Tržby y/y": safe_get("revenueGrowth", 100), "Zisk y/y": safe_get("earningsGrowth", 100),
        "Dluh D/E": safe_get("debtToEquity"), "Div. výnos": val_div, "Payout": safe_get("payoutRatio", 100),
        "Potenciál": ((safe_get("targetMeanPrice")/safe_get("currentPrice", 1.0))-1)*100 if safe_get("targetMeanPrice")>0 else 0
    }

    # Matrix řádky
    row_val = {"Titul": name, "Type": "Value", "_change": raw_vals["Změna"]}
    row_pts = {"Titul": f"   └ body ({t})", "Type": "Points", "_change": 0}
    
    total_score = 0
    for k in mapping_keys:
        b = get_b_direct(raw_vals[k], [15, 25, 40], [15, 5, -10])
        total_score += b
        row_val[k] = format_cz(raw_vals[k], precision=1, is_pct=(k in pct_cols))
        row_pts[k] = format_cz(b, precision=0)
        row_val[f"_raw_{k}"] = raw_vals[k]

    row_val["Cena"], row_val["Změna"], row_val["Score"] = format_cz(raw_vals['Cena'], 2), format_cz(raw_vals['Změna'], 1, True), int(round(total_score))
    row_pts["Cena"], row_pts["Změna"], row_pts["Score"] = "", "", int(round(total_score))
    m_rows.append(row_val)
    if zobrazit_body: m_rows.append(row_pts)

    # Kalendář řádky
    ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
    c_rows.append({
        "Titul": name, "Earnings": item["earn"], 
        "Dní do": (pd.to_datetime(item["earn"], dayfirst=True).date() - today).days if item["earn"] != "-" else "-", 
        "Dividenda": f"{safe_get('dividendRate'):.2f} {inf.get('currency')}", 
        "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", 
        "Analytické": inf.get('recommendationKey', '-').replace('_', ' ').title(), 
        "RSI": int(item['rsi']), "_rsi": item["rsi"], 
        "_alert": [1 if item["earn"] != "-" and 0<=(pd.to_datetime(item["earn"], dayfirst=True).date()-today).days<=14 else 0, 1 if "Strong Buy" in str(inf.get('recommendationKey','')) else 0, 1 if ex_dt and 0<=(ex_dt-today).days<=10 else 0]
    })

# --- 6. VYKRESLENÍ ---
if stranka == "Scoring Matrix":
    df_m = pd.DataFrame(m_rows)
    if not df_m.empty:
        conf = {"Titul": st.column_config.TextColumn("Titul", width="medium"), "Score": st.column_config.NumberColumn("Score", format="%d")}
        for k in ["Cena", "Změna"] + mapping_keys: conf[k] = st.column_config.TextColumn(k)

        def style_matrix(r):
            styles = [''] * len(r)
            is_pts = r["Type"] == "Points"
            for i, col in enumerate(r.index):
                if is_pts: styles[i] = 'color: #888; font-style: italic; background-color: #f8f9fa'
                else:
                    if col in ["Cena", "Změna"]: styles[i] = f"color: {'#28a745' if r['_change']>0 else '#dc3545'}; font-weight: bold"
                    if col == "P/E" and r.get("_raw_P/E", 0) > 30: styles[i] += '; background-color: #ffe5e5'
                    if col == "Dluh D/E" and r.get("_raw_Dluh D/E", 0) > 120: styles[i] += '; background-color: #fff3cd'
                    if col == "Potenciál" and r.get("_raw_Potenciál", 0) > 20: styles[i] += '; background-color: #d4edda'
            return styles

        st.dataframe(
            df_m.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn"),
            use_container_width=True, hide_index=True, height=850, column_config=conf,
            column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"]
        )

else:
    df_c = pd.DataFrame(c_rows)
    if not df_c.empty:
        st.dataframe(
            df_c.style.apply(lambda r: ['background-color: #ffc107; color: black' if col=='Dní do' and r['_alert'][0] else '' for col in r.index], axis=1), 
            use_container_width=True, hide_index=True, height=850,
            column_config={"Titul": st.column_config.TextColumn("Titul", width="medium")},
            column_order=["Titul", "Earnings", "Dní do", "Dividenda", "Ex-Date", "Analytické", "RSI"]
        )
