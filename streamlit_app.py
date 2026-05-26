import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1.0rem; padding-bottom: 0rem; }
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
    try:
        df = pd.read_csv(odkaz.replace('/edit?usp=sharing', '/export?format=csv'))
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper().str.strip()
        return df
    except: return pd.DataFrame()

# --- 🧠 UNIFIKOVANÁ DATA ---
@st.cache_data(ttl=3600)
def fetch_all_stock_data(tickers):
    stock_data = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            inf = tk.info if tk.info else {}
            
            try: fin = tk.financials
            except: fin = pd.DataFrame()
            try: bs = tk.balance_sheet
            except: bs = pd.DataFrame()
            
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            gm_3y = c_gm
            if fin is not None and not fin.empty and 'Gross Profit' in fin.index and 'Total Revenue' in fin.index:
                roky = fin.columns[:3]
                vals = [fin.loc['Gross Profit', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
                if vals: gm_3y = (sum(vals) / len(vals)) * 100

            nm_3y = c_nm
            if fin is not None and not fin.empty and 'Net Income' in fin.index and 'Total Revenue' in fin.index:
                roky = fin.columns[:3]
                vals = [fin.loc['Net Income', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
                if vals: nm_3y = (sum(vals) / len(vals)) * 100

            roe_3y = c_roe
            if fin is not None and not fin.empty and bs is not None and not bs.empty and 'Net Income' in fin.index and 'Stockholders Equity' in bs.index:
                roky = [r for r in fin.columns[:3] if r in bs.columns]
                vals = [fin.loc['Net Income', r] / bs.loc['Stockholders Equity', r] for r in roky if bs.loc['Stockholders Equity', r] > 0]
                if vals: roe_3y = (sum(vals) / len(vals)) * 100

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
                "grossMargins": c_gm, "gm_3y": gm_3y, "profitMargins": c_nm, "nm_3y": nm_3y, "returnOnEquity": c_roe, "roe_3y": roe_3y,
                "revenueGrowth": safe_float(inf.get('revenueGrowth', 0)) * 100, "earningsGrowth": safe_float(inf.get('earningsGrowth', 0)) * 100,
                "debtToEquity": safe_float(inf.get('debtToEquity')), "dividendYield": safe_float(inf.get('dividendYield')),
                "dividendRate": safe_float(inf.get('dividendRate')), "currency": inf.get('currency', 'USD'),
                "targetMeanPrice": safe_float(inf.get('targetMeanPrice')), "exDividendDate": inf.get('exDividendDate'), "recommendationKey": inf.get('recommendationKey', '-'),
                "trailingEps": safe_float(inf.get('trailingEps')), "bookValue": safe_float(inf.get('bookValue')), "totalRevenue": safe_float(inf.get('totalRevenue')), "sharesOutstanding": safe_float(inf.get('sharesOutstanding'))
            }
        except:
            stock_data[t] = {}
    return stock_data

# --- INICIALIZACE DAT ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)
if df_raw_list.empty:
    st.error("Nepodařilo se načíst seznam z Google tabulky.")
    st.stop()

vsechny_tickery = [str(t).strip().upper() for t in df_raw_list['Ticker'].dropna().unique().tolist() if str(t).strip() not in ["-", "nan", "TICKER"]]

with st.spinner("🚀 Aktualizuji data z trhů..."):
    data_trhu = fetch_all_stock_data(vsechny_tickery)

raw_data = []
for row in df_raw_list.to_dict('records'):
    t = str(row.get('Ticker', '')).strip().upper()
    if t not in data_trhu or not data_trhu[t]: continue
    fund = data_trhu[t]
    
    raw_data.append({
        "t": t, "inf": fund, "vzdalenost_ma50": fund["vzdalenost_ma50"], "cena_zive": fund["cena_zive"], "zmena_zive": fund["zmena_zive"],
        "kat": str(row.get('Kategorie')), "earn": row.get('Earnings Day'), "name": fund["name"],
        "gm_3y": fund["gm_3y"], "nm_3y": fund["nm_3y"], "roe_3y": fund["roe_3y"]
    })

# --- 4. SIDEBAR MENU ---
st.sidebar.markdown("### **📊 Hlavní navigace**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & Technika"], label_visibility="collapsed")

zobrazit_body = False
if stranka == "Scoring Matrix":
    st.sidebar.divider()
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní přidělené body", value=False)

st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)

filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 5. LOGIKA STRÁNEK ČISTĚ BEZ NADPISŮ S STRUČNOU LEGENDOU ---
if not filtered_data:
    st.info(f"Pro filtr '{filtr_kat}' nebyly nalezeny žádné akcie.")
else:
    if stranka == "Scoring Matrix":
        # --- 💡 STRUČNÁ LEGENDA ---
        with st.expander("Legenda", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**🎨 Barevné buňky**")
                st.markdown("* 🟢 **Fwd P/E zelená:** Očekává se růst zisků (Fwd P/E je o >5 % nižší než P/E).")
                st.markdown("* 🔴 **Fwd P/E červená:** Hrozí pokles zisků (Fwd P/E je o >5 % vyšší než P/E).")
                st.markdown("* 🔴 **Dluh D/E červená:** Dluh přesahuje 120 % vlastního kapitálu.")
            with col2:
                st.markdown("**📈 Valuační a Růstové metriky**")
                st.markdown("* **Score:** Celkové ohodnocení (od červené po zelenou). Vyšší skóre = lepší fundament/cena.")
                st.markdown("* **Změna:** Denní pohyb akcie (zelená = růst, červená = pokles).")
                st.markdown("* **Potenciál:** Vzdálenost k průměrnému cíli (Target Price) analytiků.")
            with col3:
                st.markdown("**⚙️ Výpočet a Váhy**")
                st.markdown("* **P/E penalizace:** Pokud Forward P/E roste oproti Trailing P/E, model krátí body za valuaci o 50 %.")
                st.markdown("* **3Y Sloupce:** Ukazují tříletý historický průměr pro zachycení cykličnosti.")

        # Nastavení strategií v sidebaru
        st.sidebar.markdown("### ⚙️ Nastavení matice")
        strategie = st.sidebar.selectbox("Strategie:", ["Vlastní", "🛡️ Konzervativní", "⚖️ Vyvážená", "🚀 Růstová"])
        
        h_pe, b_pe = [12, 18, 25, 40, 999], [20, 15, 5, 0, -15]
        h_ps, b_ps = [1.5, 3, 6, 10, 999], [15, 10, 5, 0, -10]
        h_gm, b_gm = [20, 35, 50, 70, 999], [0, 8, 15, 20, 25]
        h_nm, b_nm = [10, 20, 30, 45, 999], [0, 10, 18, 22, 30]
        h_roe, b_roe = [12, 22, 35, 55, 999], [0, 10, 15, 20, 25]

        if strategie == "🛡️ Konzervativní":
            h_pe, b_pe = [10, 15, 20, 30, 999], [25, 15, 0, -10, -30]
            h_ps, b_ps = [1.0, 2, 4, 7, 999], [20, 10, 0, -10, -20]
        elif strategie == "🚀 Růstová":
            h_pe, b_pe = [20, 35, 50, 80, 999], [15, 25, 15, 5, -5]
            h_ps, b_ps = [3, 6, 12, 20, 999], [10, 15, 20, 5, -10]

        def vytvor_p(nazev, zk, def_h, def_b):
            with st.sidebar.expander(f"📊 {nazev}", expanded=False):
                d = []
                for i in range(5):
                    c1, c2 = st.columns(2)
                    h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
                    b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
                    d.append({"h": h, "b": b})
                return d

        p_pe = vytvor_p("P/E", "pe", h_pe, b_pe)
        p_ps = vytvor_p("P/S", "ps", h_ps, b_ps)
        p_pb = vytvor_p("P/B", "pb", [1, 2.5, 4, 8, 999], [10, 7, 3, 0, -5])
        p_pfcf = vytvor_p("P/FCF", "pfcf", [12, 20, 35, 50, 999], [20, 12, 5, 0, -10])
        p_gm = vytvor_p("H-Marže", "gm", h_gm, b_gm)
        p_gm_3y = vytvor_p("H-Marže 3Y", "gm3y", h_gm, b_gm)
        p_nm = vytvor_p("Č-Marže", "nm", h_nm, b_nm)
        p_nm_3y = vytvor_p("Č-Marže 3Y", "nm3y", h_nm, b_nm)
        p_roe = vytvor_p("ROE", "roe", h_roe, b_roe)
        p_roe_3y = vytvor_p("ROE 3Y", "roe3y", h_roe, b_roe)
        p_rev = vytvor_p("Tržby y/y", "rev", [0, 10, 20, 35, 999], [-10, 8, 15, 25, 35])
        p_eps = vytvor_p("Zisk y/y", "eps", [0, 10, 25, 45, 999], [-15, 10, 20, 28, 40])
        p_deb = vytvor_p("Dluh D/E", "deb", [40, 80, 120, 200, 999], [20, 10, 0, -15, -40])
        p_div = vytvor_p("Div. výnos", "div", [2, 4, 6, 8, 999], [5, 12, 15, 10, 5])
        p_pot = vytvor_p("Potenciál", "pot", [8, 18, 28, 45, 999], [0, 10, 18, 25, 35])

        w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
        w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
        w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
        w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

        mapping_keys = ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
        pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
        
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
            elif pe_tr > 0 and pe_fwd > 0 and (pe_fwd / pe_tr) < 0.95: adjusted_pe_points = base_pe_points * 1.25

            total = 0
            row_p = {"Titul": f"    └ body ({t})", "Type": "Points"}
            p_map = {"P/E": p_pe, "P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf, "H-Marže": p_gm, "H-Marže 3Y": p_gm_3y, "Č-Marže": p_nm, "Č-Marže 3Y": p_nm_3y, "ROE": p_roe, "ROE 3Y": p_roe_3y, "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Potenciál": p_pot}
            w_map = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}

            for sorted_k in mapping_keys:
                vw = w_map["v"] if sorted_k in ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF"] else (w_map["p"] if "Marže" in sorted_k or "ROE" in sorted_k else (w_map["g"] if sorted_k in ["Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"] else w_map["r"]))
                if sorted_k == "P/E":
                    b = adjusted_pe_points
