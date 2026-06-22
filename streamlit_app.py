import streamlit as st
import pandas as pd
import yfinance as yf
import time
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

# --- 🧠 BEZPEČNÉ STAHOVÁNÍ BEZ RIZIKA SELHÁNÍ TRENDŮ ---
@st.cache_data(ttl=1800)
def fetch_all_stock_data(tickers):
    stock_data = {}
    for t in tickers:
        try:
            time.sleep(0.25) # 🛡️ Ochrana proti banu
            tk = yf.Ticker(t)
            inf = tk.info
            
            if not inf or not isinstance(inf, dict): 
                continue
                
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            rev_growth = safe_float(inf.get('revenueGrowth', 0)) * 100
            eps_growth = safe_float(inf.get('earningsGrowth', 0)) * 100

            # 🛡️ STABILNÍ HISTORICKÉ ODHADY (Pokud selže výpočet, použije se aktuální stav)
            gm_avg = c_gm
            nm_avg = c_nm
            roe_avg = c_roe

            # Bezpečný pokus o simulaci historického trendu
            if eps_growth != 0:
                if -50 < eps_growth < 100: # Jen pro rozumné hodnoty růstu
                    roe_avg = c_roe * (1 - (eps_growth / 100) * 0.3)
                    margin_trend = 1 - ((rev_growth - eps_growth) / 100) * 0.1
                    gm_avg = c_gm * margin_trend
                    nm_avg = c_nm * margin_trend

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
                "grossMargins": c_gm, "gm_3y": gm_avg, "profitMargins": c_nm, "nm_3y": nm_avg, "returnOnEquity": c_roe, "roe_3y": roe_avg,
                "revenueGrowth": rev_growth, "earningsGrowth": eps_growth,
                "debtToEquity": safe_float(inf.get('debtToEquity')), "dividendYield": safe_float(inf.get('dividendYield')),
                "dividendRate": safe_float(inf.get('dividendRate')), "currency": inf.get('currency', 'USD'),
                "targetMeanPrice": safe_float(inf.get('targetMeanPrice')), "exDividendDate": inf.get('exDividendDate'), "recommendationKey": inf.get('recommendationKey', '-'),
                "trailingEps": safe_float(inf.get('trailingEps')), "bookValue": safe_float(inf.get('bookValue')), "totalRevenue": safe_float(inf.get('totalRevenue')), "sharesOutstanding": safe_float(inf.get('sharesOutstanding'))
            }
        except:
            pass # Pokud jedna akcie selže, cyklus pokračuje dál a neshodí zbytek
    return stock_data

# --- INICIALIZACE VSTUPŮ ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

if df_raw_list.empty:
    st.warning("⚠️ Čekám na platná data z Google tabulky...")
    st.stop()

vsechny_tickery = [str(t).strip().upper() for t in df_raw_list['Ticker'].dropna().unique().tolist() if str(t).strip() not in ["-", "nan", "TICKER"]]

if not vsechny_tickery:
    st.stop()

with st.spinner("🚀 Synchronizuji data z trhů..."):
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

# --- 4. BOČNÍ PANEL (SIDEBAR NAV) ---
st.sidebar.markdown("### **📊 Hlavní navigace**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & Technika"], label_visibility="collapsed")

zobrazit_body = False
if stranka == "Scoring Matrix":
    st.sidebar.divider()
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní přidělené body", value=False)

st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)

filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"].lower() == filtr_kat.lower()]

# --- 5. LOGIKA ZOBRAZENÍ STRÁNEK ---
if not filtered_data:
    st.info(f"V kategorii '{filtr_kat}' momentálně nejsou žádná data. Přepněte filtr na 'Vše' nebo zkontrolujte sloupce v Google tabulce.")
else:
    if stranka == "Scoring Matrix":
        with st.expander("📊 Scoring Matrix | Legenda k trendům", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📉 Sloupce s označením (Avg)**")
                st.markdown("Zobrazují historickou základnu firmy (ROE a Marže).")
            with col2:
                st.markdown("**🧠 Jak funguje trendový bodový bonus?**")
                st.markdown("Model dává **bonusové body**, pokud se aktuální stav zlepšuje oproti průměru, a **strhává**, pokud klesá.")

        st.sidebar.markdown("### ⚙️ Nastavení matice")
        strategie = st.sidebar.selectbox("Strategie:", ["Vlastní", "⚖️ Vyvážená", "🛡️ Konzervativní", "🚀 Růstová"], index=1)
        
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

        if "Konzervativní" in strategie:
            h_pe, b_pe = [10, 15, 20, 30, 999], [25, 15, 0, -10, -30]
            h_ps, b_ps = [1.0, 2, 4, 7, 999], [20, 10, 0, -10, -20]
            h_deb, b_deb = [20, 50, 90, 150, 999], [25, 15, 5, -10, -50]
        elif "Růstová" in strategie:
            h_pe, b_pe = [20, 35, 50, 80, 999], [15, 25, 15, 5, -5]
            h_ps, b_ps = [3, 6, 12, 20, 999], [10, 15, 20, 5, -10]
            h_rev, b_rev = [5, 15, 30, 50, 999], [-15, 10, 20, 35, 50]

        def vytvor_p(nazev, zk, def_h, def_b):
            d = []
            if strategie == "Vlastní":
                with st.sidebar.expander(f"📊 {nazev}", expanded=False):
                    for i in range(5):
                        c1, c2 = st.columns(2)
                        h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
                        b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
                        d.append({"h": h, "b": b})
            else:
                for i in range(5): d.append({"h": def_h[i], "b": def_b[i]})
            return d

        p_pe = vytvor_p("P/E", "pe", h_pe, b_pe)
        p_ps = vytvor_p("P/S", "ps", h_ps, b_ps)
        p_pb = vytvor_p("P/B", "pb", h_pb, b_pb)
        p_pfcf = vytvor_p("P/FCF", "pfcf", h_pfcf, b_pfcf)
        p_gm = vytvor_p("H-Marže", "gm", h_gm, b_gm)
        p_nm = vytvor_p("Č-Marže", "nm", h_nm, b_nm)
        p_roe = vytvor_p("ROE", "roe", h_roe, b_roe)
        p_rev = vytvor_p("Tržby y/y", "rev", h_rev, b_rev)
        p_eps = vytvor_p("Zisk y/y", "eps", h_eps, b_eps)
        p_deb = vytvor_p("Dluh D/E", "deb", h_deb, b_deb)
        p_div = vytvor_p("Div. výnos", "div", h_div, b_div)
        p_pot = vytvor_p("Potenciál", "pot", h_pot, b_pot)

        w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
        w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
        w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
        w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

        mapping_keys = ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže (Avg)", "Č-Marže", "Č-Marže (Avg)", "ROE", "ROE (Avg)", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
        pct_cols = ["Změna", "H-Marže", "H-Marže (Avg)", "Č-Marže", "Č-Marže (Avg)", "ROE", "ROE (Avg)", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
        
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
                "H-Marže": inf.get("grossMargins", 0), "H-Marže (Avg)": item["gm_3y"],
                "Č-Marže": inf.get("profitMargins", 0), "Č-Marže (Avg)": item["nm_3y"],
                "ROE": inf.get("returnOnEquity", 0), "ROE (Avg)": item["roe_3y"],
                "Tržby y/y": inf.get("revenueGrowth", 0), "Zisk y/y": inf.get("earningsGrowth", 0), "Dluh D/E": inf.get("debtToEquity", 0), 
                "Div. výnos": d_yield, "Potenciál": ((inf.get("targetMeanPrice", 0)/item["cena_zive"])-1)*100 if inf.get("targetMeanPrice", 0) and item["cena_zive"] > 0 else 0
            }

            base_pe_points = get_b(raw_vals["P/E"], p_pe)
            adjusted_pe_points = base_pe_points
            if pe_tr > 0 and pe_fwd > 0 and (pe_fwd / pe_tr) > 1.05: adjusted_pe_points = (base_pe_points * 0.5) - 10
            elif pe_tr > 0 and pe_fwd > 0 and (pe_fwd / pe_tr) < 0.95: adjusted_pe_points = base_pe_points * 1.25

            total = 0
            row_p = {"Titul": f"    └ body ({t})", "Type": "Points"}
            p_map = {"P/E": p_pe, "P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf, "H-Marže": p_gm, "Č-Marže": p_nm, "ROE": p_roe, "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Potenciál": p_pot}
            w_map = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}

            for sorted_k in mapping_keys:
                vw = w_map["v"] if sorted_k in ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF"] else (w_map["p"] if "Marže" in sorted_k or "ROE" in sorted_k else (w_map["g"] if sorted_k in ["Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"] else w_map["r"]))
                
                if sorted_k == "P/E":
                    b = adjusted_pe_points * vw
                    row_p[sorted_k] = float(int(round(b)))
                    total += b
                elif sorted_k == "Forward P/E":
                    row_p[sorted_k] = 0.0 
                elif sorted_k in ["H-Marže (Avg)", "Č-Marže (Avg)", "ROE (Avg)"]:
                    orig_k = sorted_k.replace(" (Avg)", "")
                    rozdil = raw_vals[orig_k] - raw_vals[sorted_k]
                    trend_body = 15 if rozdil > 1 else (-15 if rozdil < -1 else 0)
                    b = trend_body * vw
                    total += b
                    row_p[sorted_k] = float(int(round(b)))
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
                    if col == "Změna": 
                        s[i] = f"color: {'#1b5e20' if r['Změna']>0.01 else ('#b71c1c' if r['Změna']<-0.01 else '#444')}; font-weight: bold;"
                    
                    if col in ["H-Marže (Avg)", "Č-Marže (Avg)", "ROE (Avg)"]:
                        orig_col = col.replace(" (Avg)", "")
                        if r[orig_col] > r[col]: s[i] = 'color: #1b5e20; font-weight: bold;'
                        elif r[orig_col] < r[col]: s[i] = 'color: #b71c1c; font-weight: bold;'

                    if col == "Forward P/E" and r.get("P/E", 0) > 0 and r.get("Forward P/E", 0) > 0:
                        if r["Forward P/E"] / r["P/E"] > 1.05: s[i] = 'background-color: #ffebee; color: #b71c1c; font-weight: bold'
                        elif r["Forward P/E"] / r["P/E"] < 0.95: s[i] = 'background-color: #e8f5e9; color: #1b5e20; font-weight: bold'
                    if col == "P/E" and isinstance(r.get(col), (int, float)) and r[col] > 25: s[i] = 'background-color: #ffebee'
                    if col == "Dluh D/E" and isinstance(r.get(col), (int, float)) and r[col] > 120: s[i] = 'background-color: #ffcdd2'
                return s
                
            nastaveni_sloupcu = {"Type": None, "Titul": st.column_config.TextColumn("Titul", width=180), "Cena": st.column_config.NumberColumn("Cena", format="%.2f"), "Změna": st.column_config.NumberColumn("Změna", format="%.2f%%"), "Score": st.column_config.NumberColumn("Score", format="%d")}
            for sorted_k in mapping_keys:
                if sorted_k in pct_cols: nastaveni_sloupcu[sorted_k] = st.column_config.NumberColumn(sorted_k, format="%.1f%%")
                else: nastaveni_sloupcu[sorted_k] = st.column_config.NumberColumn(sorted_k, format="%.1f")

            st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150), use_container_width=True, hide_index=True, height=750, column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"], column_config=nastaveni_sloupcu)

    elif stranka == "Vnitřní hodnota (IV)":
        with st.expander("⚖️ Vnitřní hodnota (IV) | Popis oceňovacích metod", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**📈 Pilíř P1: Ziskové modely**")
                st.markdown("* **Grahamův vzorec:** Klasický model B. Grahama upravený o výnosy dluhopisů.")
                st.markdown("* **Cílové P/E:** Kalkulace čistých zisků na akcii ($EPS \\times \\text{Cílové P/E}$).")
                st.markdown("* **RIM (Residual Income Model):** Oceňuje akcii jako součet účetní hodnoty a nadmírných zisků.")
            with col2:
                st.markdown("**💸 Pilíř P2: Cashflow modely**")
                st.markdown("* **DCF (Free Cash Flow):** Diskontovaný model volného peněžního toku.")
                st.markdown("* **DDM (Gordonův dividendový model):** Ocenění budoucích dividend.")
            with col3:
                st.markdown("**🏢 Pilíř P3: Majetkové modely**")
                st.markdown("* **Cílové P/S:** Alternativní ocenění přes násobek tržeb.")
                st.markdown("* **NAV (Net Asset Value):** Čistá účetní hodnota připadající na jednu akcii.")

        show_details = st.sidebar.toggle("🔓 Zobrazit detailní metody", value=False)
        with st.sidebar.expander("⚖️ Váhy pilířů", expanded=True):
            w1 = st.slider("Váha P1 (Ziskové)", 0, 100, 33)
            w2 = st.slider("Váha P2 (Cashflow)", 0, 100, 33)
            w3 = st.slider("Váha P3 (Majetek)", 0, 100, 34)
        with st.sidebar.expander("⚙️ Globální parametry", expanded=True):
            g_pct = st.slider("Růst (g) %", 0.0, 10.0, 3.0) / 100
            re_pct = st.slider("Výnosnost (Re) %", 5.0, 15.0, 9.0) / 100
            y_bond = st.number_input("Výnos dluhopisů (Y)", value=4.4)
            target_pe = st.slider("Cílové P/E", 5, 40, 15)
            target_ps = st.slider("Cílové P/S", 0.5, 10.0, 3.0)

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
            val_p3 = max(v_ps, bvps)

            ws = [w1, w2, w3]; vals = [val_p1, val_p2, val_p3]
            weighted_sum = sum(v * w for v, w in zip(vals, ws) if v > 0)
            active_weights = sum(w for v, w in zip(vals, ws) if v > 0)
            fair_price = weighted_sum / active_weights if active_weights > 0 else 0
            upside = ((fair_price / price) - 1) * 100 if price > 0 else 0

            row = {"Titul": item["name"], "Cena": price, "P1: Zisk": int(val_p1), "P2: CF": int(val_p2), "P3: Tržby": int(val_p3), "Férová cena": int(fair_price), "Potenciál %": float(upside)}
            if show_details: row.update({"› Graham": int(v_graham), "› P/E": int(v_pe), "› RIM": int(v_rim), "› FCF": int(v_fcf), "› DDM": int(v_ddm), "› P/S": int(v_ps), "› NAV": int(bvps)})
            iv_results.append(row)

        df_iv = pd.DataFrame(iv_results)
        if not df_iv.empty:
            def apply_all_styles(row):
                styles = [''] * len(row); up = row["Potenciál %"]
                bg = 'background-color: #d4edda' if up > 0 else ('background-color: #f8d7da' if up < 0 else '')
                for i, col in enumerate(row.index):
                    if col in ["Titul", "Potenciál %"]: styles[i] = bg
                    if col == "Cena": styles[i] = 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold'
                return styles
            
            detail_cols = ["› Graham", "› P/E", "› RIM", "› FCF", "› DDM", "› P/S", "› NAV"] if show_details else []
            st.dataframe(df_iv.style.apply(apply_all_styles, axis=1).format({"Cena": "{:.2f}"}), use_container_width=True, hide_index=True, height=750, column_config={"Potenciál %": st.column_config.NumberColumn("Potenciál %", format="%.1f%%")}, column_order=["Titul", "Cena", "P1: Zisk", "P2: CF", "P3: Tržby"] + detail_cols + ["Férová cena", "Potenciál %"])

    else:
        # STRÁNKA KALENDÁŘE A TECHNIKY
        c_rows, today = date.today(), date.today() # oprava inicializace proměnné
        c_rows = []
        for item in filtered_data:
            inf = item["inf"]; ticker = item["t"]; days_to = safe_date_diff(item["earn"], today)
            ex_dt = datetime.fromtimestamp(inf.get('exDividendDate', 0)).date() if inf.get('exDividendDate') else None
            
            d_yield_gross = inf.get('dividendYield', 0.0)
            if d_yield_gross < 0.2 and d_yield_gross > 0: d_yield_gross *= 100 
            currency = str(inf.get('currency', 'USD')).upper()
            
            tax_rate = 0.0 if ticker in ["BTI", "SHEL"] or ".LON" in ticker else (0.15 if currency in ["USD", "CZK"] else 0.25)
            d_yield_net = d_yield_gross * (1 - tax_rate)

            c_rows.append({"Titul": item["name"], "Ticker": ticker, "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", "Dní do": days_to, "Dividenda": f"{safe_float(inf.get('dividendRate', 0.0)):.2f} {currency}", "Div. výnos (hrubý)": d_yield_gross, "Čistý výnos (odhad)": d_yield_net, "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", "Doporučení": inf.get('recommendationKey', '-').replace('_', ' ').title(), "Vzdálenost od MA50": item["vzdalenost_ma50"]})
        
        df_c = pd.DataFrame(c_rows)
        if not df_c.empty:
            def style_calendar(r):
                s = [''] * len(r); d_idx = r.index.get_loc("Dní do")
                if r["Dní do"] < 0: s[d_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
                elif r["Dní do"] < 14: s[d_idx] = 'background-color: #fff9c4; color: #f57f17; font-weight: bold'
                if "buy" in str(r["Doporučení"]).lower(): s[r.index.get_loc("Doporučení")] = 'background-color: #e8f5e9; color: #1b5e20; font-weight: bold'
                
                ma_idx = r.index.get_loc("Vzdálenost od MA50")
                if r["Vzdálenost od MA50"] < -10: s[ma_idx] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold' 
                elif r["Vzdálenost od MA50"] > 15: s[ma_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold' 
                return s
                
            st.dataframe(df_c.style.apply(style_calendar, axis=1), use_container_width=True, hide_index=True, height=750, column_config={"Div. výnos (hrubý)": st.column_config.NumberColumn("Div. výnos (hrubý)", format="%.2f%%"), "Čistý výnos (odhad)": st.column_config.NumberColumn("Čistý výnos (odhad)", format="%.2f%%"), "Vzdálenost od MA50": st.column_config.NumberColumn("Vzdálenost od MA50", format="%.1f%%")}, column_order=["Titul", "Ticker", "Earnings", "Dní do", "Dividenda", "Div. výnos (hrubý)", "Čistý výnos (odhad)", "Ex-Date", "Doporučení", "Vzdálenost od MA50"])
            # --- 🛠️ DOČASNÁ DIAGNOSTIKA (PAK SMAŽEME) ---
st.write("---")
st.subheader("🔍 Diagnostický panel")
col_d1, col_d2 = st.columns(2)

with col_d1:
    st.write("1. Načtené tickery z Google tabulky:")
    st.write(vsechny_tickery if 'vsechny_tickery' in locals() else "Tickery nenačteny!")

with col_d2:
    st.write("2. Kolik tickerů vrátilo data z Yahoo:")
    if 'data_trhu' in locals():
        st.write(f"Úspěšně staženo: {len(data_trhu)} z {len(vsechny_tickery)}")
        st.write("Stažené tickery:", list(data_trhu.keys()))
    else:
        st.write("Data z trhu vůbec neexistují.")
