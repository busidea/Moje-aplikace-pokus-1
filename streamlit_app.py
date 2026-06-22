import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2.2rem; padding-bottom: 0rem; }
    .stExpander { margin-top: 4px !important; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { font-weight: bold !important; color: #004080 !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]: return 999
    try: return (pd.to_datetime(earn_val, dayfirst=True).date() - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. NAČTENÍ SEZNAMU Z GOOGLE TABULKY ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
    try:
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        if 'Ticker' not in df.columns:
            return pd.DataFrame()
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        if 'Kategorie' in df.columns:
            df['Kategorie'] = df['Kategorie'].astype(str).str.strip()
        return df
    except:
        return pd.DataFrame()

# --- 🧠 SUPER-RYCHLÉ STAHOVÁNÍ DATA Z YAHOO ---
@st.cache_data(ttl=1800)
def fetch_all_stock_data(tickers):
    stock_data = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            inf = tk.info if tk.info else {}
            
            # Použijeme rychlé info, abychom nezatěžovali server hlubokým stahováním
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            cena_act = safe_float(inf.get('currentPrice', inf.get('regularMarketPrice', inf.get('previousClose', 0))))
            cena_prev = safe_float(inf.get('previousClose', cena_act))
            zmena = ((cena_act / cena_prev) - 1) * 100 if cena_prev > 0 else 0.0

            ma50 = safe_float(inf.get('fiftyDayAverage', 0))
            vzdalenost_ma50 = ((cena_act / ma50) - 1) * 100 if ma50 > 0 else 0.0

            stock_data[t] = {
                "name": inf.get('longName', t), 
                "cena_zive": cena_act,
                "zmena_zive": zmena,
                "vzdalenost_ma50": vzdalenost_ma50,
                "trailingPE": safe_float(inf.get('trailingPE')), 
                "forwardPE": safe_float(inf.get('forwardPE')),
                "priceToSales": safe_float(inf.get('priceToSalesTrailing12Months')), 
                "priceToBook": safe_float(inf.get('priceToBook')),
                "marketCap": safe_float(inf.get('marketCap')), 
                "freeCashflow": safe_float(inf.get('freeCashflow')),
                "grossMargins": c_gm, "gm_3y": c_gm, "profitMargins": c_nm, "nm_3y": c_nm, "returnOnEquity": c_roe, "roe_3y": c_roe,
                "revenueGrowth": safe_float(inf.get('revenueGrowth', 0)) * 100, "earningsGrowth": safe_float(inf.get('earningsGrowth', 0)) * 100,
                "debtToEquity": safe_float(inf.get('debtToEquity')), "dividendYield": safe_float(inf.get('dividendYield')),
                "dividendRate": safe_float(inf.get('dividendRate')), "currency": inf.get('currency', 'USD'),
                "targetMeanPrice": safe_float(inf.get('targetMeanPrice')), "exDividendDate": inf.get('exDividendDate'), "recommendationKey": inf.get('recommendationKey', '-'),
                "trailingEps": safe_float(inf.get('trailingEps')), "bookValue": safe_float(inf.get('bookValue')), "totalRevenue": safe_float(inf.get('totalRevenue')), "sharesOutstanding": safe_float(inf.get('sharesOutstanding'))
            }
        except:
            stock_data[t] = {}
    return stock_data

# --- INICIALIZACE ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

if df_raw_list.empty:
    st.warning("⚠️ Načítám nebo čekám na stabilizaci Google tabulky...")
    st.stop()

vsechny_tickery = [str(t).strip().upper() for t in df_raw_list['Ticker'].dropna().unique().tolist() if str(t).strip() not in ["-", "nan", "TICKER"]]

if not vsechny_tickery:
    st.stop()

data_trhu = fetch_all_stock_data(vsechny_tickery)

raw_data = []
for row in df_raw_list.to_dict('records'):
    t = str(row.get('Ticker', '')).strip().upper()
    kat_hodnota = str(row.get('Kategorie', '')).strip()
    if t not in data_trhu or not data_trhu[t]: continue
    fund = data_trhu[t]

    raw_data.append({
        "t": t, "inf": fund, "vzdalenost_ma50": fund["vzdalenost_ma50"], "cena_zive": fund["cena_zive"], "zmena_zive": fund["zmena_zive"],
        "kat": kat_hodnota, "earn": row.get('Earnings Day'), "name": fund["name"],
        "gm_3y": fund["gm_3y"], "nm_3y": fund["nm_3y"], "roe_3y": fund["roe_3y"]
    })

# --- 4. SIDEBAR ---
st.sidebar.markdown("### **📊 Hlavní navigace**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & Technika"], label_visibility="collapsed")

zobrazit_body = False
if stranka == "Scoring Matrix":
    st.sidebar.divider()
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní body", value=False)

st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)

filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"].lower() == filtr_kat.lower()]

# --- 5. STRÁNKY ---
if not filtered_data:
    st.info(f"Pro filtr '{filtr_kat}' nebyly nalezeny žádné akcie. Zkuste změnit filtr nebo vyčistit Cache v menu vpravo nahoře.")
else:
    if stranka == "Scoring Matrix":
        st.sidebar.markdown("### ⚙️ Nastavení matice")
        strategie = st.sidebar.selectbox("Strategie:", ["⚖️ Vyvážená", "🛡️ Konzervativní", "🚀 Růstová"])
        
        h_pe, b_pe = [12, 18, 25, 40, 999], [20, 15, 5, 0, -15]
        h_ps, b_ps = [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10]
        h_pb, b_pb = [1, 2.5, 4, 8, 999], [10, 7, 3, 0, -5]
        h_pfcf, b_pfcf = [12, 20, 35, 50, 999], [20, 12, 5, 0, -10]
        h_gm, b_gm = [20, 35, 50, 70, 999], [0, 8, 15, 20, 25]
        h_nm, b_nm = [10, 20, 30, 45, 999], [0, 10, 18, 22, 30]
        h_roe, b_roe = [12, 22, 35, 55, 999], [0, 10, 15, 20, 25]
        h_rev, b_rev = [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35]
        h_eps, b_eps = [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40]
        h_deb, b_deb = [40, 80, 120, 200, 999], [20, 10, 0, -15, -40]
        h_div, b_div = [2, 4, 6, 8, 999], [5, 12, 15, 10, 5]
        h_pot, b_pot = [8, 18, 28, 45, 999], [0, 10, 18, 25, 35]

        if strategie == "🛡️ Konzervativní":
            h_pe, b_pe = [10, 15, 20, 30, 999], [25, 15, 0, -10, -30]
            h_ps, b_ps = [1.0, 2, 4, 7, 999], [20, 10, 0, -10, -20]
            h_deb, b_deb = [20, 50, 90, 150, 999], [25, 15, 5, -10, -50]
        elif strategie == "🚀 Růstová":
            h_pe, b_pe = [20, 35, 50, 80, 999], [15, 25, 15, 5, -5]
            h_ps, b_ps = [3, 6, 12, 20, 999], [10, 15, 20, 5, -10]
            h_rev, b_rev = [5, 15, 30, 50, 999], [-15, 10, 20, 35, 50]

        p_pe = [{"h": h_pe[i], "b": b_pe[i]} for i in range(5)]
        p_ps = [{"h": h_ps[i], "b": b_ps[i]} for i in range(5)]
        p_pb = [{"h": h_pb[i], "b": b_pb[i]} for i in range(5)]
        p_pfcf = [{"h": h_pfcf[i], "b": b_pfcf[i]} for i in range(5)]
        p_gm = [{"h": h_gm[i], "b": b_gm[i]} for i in range(5)]
        p_gm_3y = p_gm
        p_nm = [{"h": h_nm[i], "b": b_nm[i]} for i in range(5)]
        p_nm_3y = p_nm
        p_roe = [{"h": h_roe[i], "b": b_roe[i]} for i in range(5)]
        p_roe_3y = p_roe
        p_rev = [{"h": h_rev[i], "b": b_rev[i]} for i in range(5)]
        p_eps = [{"h": h_eps[i], "b": b_eps[i]} for i in range(5)]
        p_deb = [{"h": h_deb[i], "b": b_deb[i]} for i in range(5)]
        p_div = [{"h": h_div[i], "b": b_div[i]} for i in range(5)]
        p_pot = [{"h": h_pot[i], "b": b_pot[i]} for i in range(5)]

        w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
        w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
        w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
        w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

        mapping_keys = ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
        m_rows = []
        for item in filtered_data:
            inf = item["inf"]; t = item["t"]; name = item["name"]
            pe_tr = inf.get("trailingPE", 0) or inf.get("forwardPE", 0)
            pe_fwd = inf.get("forwardPE", 0) or pe_tr
            d_yield = inf.get("dividendYield", 0)
            if d_yield < 0.2 and d_yield > 0: d_yield *= 100 

            raw_vals = {
                "Cena": item["cena_zive"], "Změna": item["zmena_zive"],
                "P/E": pe_tr, "Forward P/E": pe_fwd, "P/S": inf.get("priceToSales", 0), 
                "P/B": inf.get("priceToBook", 0), "P/FCF": inf.get("marketCap", 0)/inf.get("freeCashflow", 1) if inf.get("freeCashflow", 0) else 0,
                "H-Marže": inf.get("grossMargins", 0), "H-Marže 3Y": item["gm_3y"],
                "Č-Marže": inf.get("profitMargins", 0), "Č-Marže 3Y": item["nm_3y"],
                "ROE": inf.get("returnOnEquity", 0), "ROE 3Y": item["roe_3y"],
                "Tržby y/y": inf.get("revenueGrowth", 0), "Zisk y/y": inf.get("earningsGrowth", 0), "Dluh D/E": inf.get("debtToEquity", 0), 
                "Div. výnos": d_yield, "Potenciál": ((inf.get("targetMeanPrice", 0)/item["cena_zive"])-1)*100 if inf.get("targetMeanPrice", 0) and item["cena_zive"] > 0 else 0
            }

            base_pe_points = get_b(raw_vals["P/E"], p_pe)
            adjusted_pe_points = base_pe_points
            if pe_tr > 0 and pe_fwd > 0 and (pe_fwd / pe_tr) > 1.05: adjusted_pe_points = (base_pe_points * 0.5) - 10

            total = 0
            row_p = {"Titul": f"    └ body ({t})", "Type": "Points"}
            p_map = {"P/E": p_pe, "P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf, "H-Marže": p_gm, "H-Marže 3Y": p_gm_3y, "Č-Marže": p_nm, "Č-Marže 3Y": p_nm_3y, "ROE": p_roe, "ROE 3Y": p_roe_3y, "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Potenciál": p_pot}
            w_map = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}

            for sorted_k in mapping_keys:
                vw = w_map["v"] if sorted_k in ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF"] else (w_map["p"] if "Marže" in sorted_k or "ROE" in sorted_k else (w_map["g"] if sorted_k in ["Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"] else w_map["r"]))
                if sorted_k == "P/E":
                    b = adjusted_pe_points * vw
                    row_p[sorted_k] = float(int(round(b)))
                    total += b
                elif sorted_k == "Forward P/E":
                    row_p[sorted_k] = 0.0 
                else:
                    b = get_b(raw_vals[sorted_k], p_map[sorted_k]) * vw
                    total += b
                    row_p[sorted_k] = float(int(round(b)))

            row_v = {"Titul": name, "Type": "Value", "Změna": raw_vals["Změna"], "Cena": raw_vals["Cena"], "Score": int(total)}
            for sorted_k in mapping_keys: row_v[sorted_k] = raw_vals[sorted_k]
            m_rows.append(row_v)
            if zobrazit_body: m_rows.append(row_p)

        df = pd.DataFrame(m_rows)
        if not df.empty:
            def style_matrix(r):
                s = [''] * len(r)
                if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
                for i, col in enumerate(r.index):
                    if col == "Cena": s[i] = "font-weight: bold; color: #004080; background-color: #e3f2fd;"
                    if col == "Score": s[i] = "font-weight: bold; color: #1b5e20; background-color: #e8f5e9;"
                    if col == "Změna": s[i] = f"color: {'#1b5e20' if r['Změna']>0.01 else ('#b71c1c' if r['Změna']<-0.01 else '#444')}; font-weight: bold;"
                return s
            st.dataframe(df.style.apply(style_matrix, axis=1), use_container_width=True, hide_index=True, height=600)

    elif stranka == "Vnitřní hodnota (IV)":
        g_pct, re_pct, y_bond, target_pe, target_ps = 0.03, 0.09, 4.4, 15, 3.0
        iv_results = []
        for item in filtered_data:
            inf = item["inf"]; price = item["cena_zive"]
            eps = inf.get('trailingEps', 0.0); bvps = inf.get('bookValue', 0.0)
            fcf = inf.get('freeCashflow', 0.0); rev = inf.get('totalRevenue', 0.0)
            shares = inf.get('sharesOutstanding', 1.0); div = inf.get('dividendRate', 0.0)
            if shares == 0: shares = 1.0

            v_graham = (eps * (8.5 + 2 * (g_pct*100)) * 4.4) / y_bond if eps > 0 else 0
            v_pe = eps * target_pe if eps > 0 else 0
            v_rim = bvps + ((eps - (re_pct * bvps)) / (re_pct - g_pct)) if (bvps > 0 and re_pct > g_pct) else 0
            val_p1 = max(v_graham, v_pe, v_rim)
            v_fcf = ((fcf * (1 + g_pct)) / (re_pct - g_pct)) / shares if (shares > 0 and re_pct > g_pct and fcf > 0) else 0
            v_ddm = (div * (1 + g_pct)) / (re_pct - g_pct) if (div > 0 and re_pct > g_pct) else 0
            val_p2 = max(v_fcf, v_ddm)
            v_ps = (rev / shares) * target_ps if (shares > 0 and rev > 0) else 0
            val_p3 = max(v_ps, v_nav) if 'v_nav' in locals() else v_ps

            fair_price = (val_p1 + val_p2 + val_p3) / 3 if (val_p1 > 0 and val_p2 > 0) else price
            upside = ((fair_price / price) - 1) * 100 if price > 0 else 0
            iv_results.append({"Titul": item["name"], "Cena": price, "Férová cena": int(fair_price), "Potenciál %": float(upside)})

        df_iv = pd.DataFrame(iv_results)
        if not df_iv.empty:
            st.dataframe(df_iv, use_container_width=True, hide_index=True)

    else:
        c_rows, today = [], date.today()
        for item in filtered_data:
            inf = item["inf"]; ticker = item["t"]; days_to = safe_date_diff(item["earn"], today)
            d_yield_gross = inf.get('dividendYield', 0.0)
            if d_yield_gross < 0.2 and d_yield_gross > 0: d_yield_gross *= 100 
            currency = str(inf.get('currency', 'USD')).upper()
            c_rows.append({"Titul": item["name"], "Ticker": ticker, "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", "Dní do": days_to, "Dividenda": f"{safe_float(inf.get('dividendRate', 0.0)):.2f} {currency}", "Div. výnos (hrubý)": d_yield_gross, "Vzdálenost od MA50": item["vzdalenost_ma50"]})
        df_c = pd.DataFrame(c_rows)
        if not df_c.empty:
            st.dataframe(df_c, use_container_width=True, hide_index=True)
