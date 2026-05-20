import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 3.5rem; padding-bottom: 0rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    
    /* Vynucené zvýraznění prvního sloupce - Modrá a Tučná */
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { 
        font-weight: bold !important;
        color: #004080 !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]:
        return 999
    try:
        dt = pd.to_datetime(earn_val, dayfirst=True).date()
        return (dt - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. NAČTENÍ DAT A HISTORICKÁ CACHE ---
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

@st.cache_data(ttl=86400)
def fetch_historical_averages(ticker_symbol, current_gm, current_nm, current_roe):
    try:
        tk = yf.Ticker(ticker_symbol)
        fin = tk.financials
        bs = tk.balance_sheet
        
        # Hrubá marže 3Y
        gm_3y = current_gm
        if fin is not None and not fin.empty and 'Gross Profit' in fin.index and 'Total Revenue' in fin.index:
            roky = fin.columns[:3]
            vals = [fin.loc['Gross Profit', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
            if vals: gm_3y = (sum(vals) / len(vals)) * 100

        # Čistá marže 3Y
        nm_3y = current_nm
        if fin is not None and not fin.empty and 'Net Income' in fin.index and 'Total Revenue' in fin.index:
            roky = fin.columns[:3]
            vals = [fin.loc['Net Income', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
            if vals: nm_3y = (sum(vals) / len(vals)) * 100

        # ROE 3Y
        roe_3y = current_roe
        if fin is not None and not fin.empty and bs is not None and not bs.empty and 'Net Income' in fin.index and 'Stockholders Equity' in bs.index:
            roky = [r for r in fin.columns[:3] if r in bs.columns]
            vals = [fin.loc['Net Income', r] / bs.loc['Stockholders Equity', r] for r in roky if bs.loc['Stockholders Equity', r] > 0]
            if vals: roe_3y = (sum(vals) / len(vals)) * 100
            
        return safe_float(gm_3y), safe_float(nm_3y), safe_float(roe_3y)
    except:
        return current_gm, current_nm, current_roe

@st.cache_data(ttl=3600)
def fetch_all_data(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t in ["-", "nan", "NAN"]: continue
        try:
            tk = yf.Ticker(t); inf = tk.info; hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            c_gm = safe_float(inf.get('grossMargins', 0)) * 100
            c_nm = safe_float(inf.get('profitMargins', 0)) * 100
            c_roe = safe_float(inf.get('returnOnEquity', 0)) * 100
            
            gm_3y, nm_3y, roe_3y = fetch_historical_averages(t, c_gm, c_nm, c_roe)

            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie')), 
                "earn": row.get('Earnings Day'),
                "name": inf.get('longName', t),
                "gm_3y": gm_3y, "nm_3y": nm_3y, "roe_3y": roe_3y
            })
        except: continue
    return res

df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)
raw_data = fetch_all_data(df_raw_list)

# --- 4. SIDEBAR ---
st.sidebar.markdown("### **📊 Menu**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & RSI"], label_visibility="collapsed")
st.sidebar.divider()

filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)
filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 5. LOGIKA STRÁNEK ---
if stranka == "Scoring Matrix":
    strategie = st.sidebar.selectbox("Strategie:", ["Vlastní", "🛡️ Konzervativní", "⚖️ Vyvážená", "🚀 Růstová"])
    zobrazit_body = st.sidebar.checkbox("⚠️ Detailní body", value=False)
    
    # Výchozí konfigurace pásem
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

    # --- ENCYKLOPEDICKÁ LEGENDA UKAZATELŮ ---
    napovedy = {
        "P/E": "**Price-to-Earnings (Trailing 12M)**\n\n• **Optimální (pod 15):** Podhodnocená nebo stabilní firma.\n• **Kritické (nad 40):** Extrémně drahá akcie.\n\n🚨 **Vztah k Forward P/E:** Pokud Forward P/E stoupne oproti Trailing o >5 % (zisk klesá), základní body se **sráží na polovinu a uděluje se penalizace -10 bodů**. Pokud klesne o >5 % (zisk roste), body se **navyšují o 25 %**.",
        "P/S": "**Price-to-Sales (Cena / Tržby)**\n\n• **Optimální (pod 2.0):** Levné z pohledu generovaných tržeb.\n• **Kritické (nad 10.0):** Extrémně vysoké ocenění, firma musí masivně růst.",
        "P/B": "**Price-to-Book (Cena / Účetní hodnota)**\n\n• **Optimální (pod 1.5):** Akcie se prodává blízko hodnoty svého čistého majetku.\n• **Kritické (nad 6.0):** Vysoká prémie za nehmotný majetek.",
        "P/FCF": "**Price-to-Free Cash Flow (Cena / Skutečné peníze)**\n\n• **Optimální (pod 15):** Firma generuje hromady čisté hotovosti. Nejdůležitější valuační metrika.\n• **Kritické (nad 45):** Hotovostní toky neodpovídají valuaci na burze.",
        "H-Marže": "**Hrubá marže (Gross Margin)**\n\n• **Optimální (nad 50 %):** Silná konkurenční výhoda (moat), vysoká ziskovost výroby/služeb.",
        "H-Marže 3Y": "**3letý průměr hrubé marže**\n\n• Ověřuje stabilitu byznysu. Pokud je 3Y průměr výrazně vyšší než aktuální marže, firma ztrácí svou maržovou sílu.",
        "Č-Marže": "**Čistá marže (Net Margin)**\n\n• **Optimální (nad 20 %):** Vysoce efektivní byznys, kterému zbývá hodně peněz po zaplacení všech nákladů.",
        "Č-Marže 3Y": "**3letý průměr čistá marže**\n\n• Filtruje jednorázové účetní triky. Stabilní čistá marže v čase je znakem zdravého managementu.",
        "ROE": "**Return on Equity (Návratnost vlastního kapitálu)**\n\n• **Optimální (nad 20 %):** Management dokáže skvěle zhodnocovat peníze akcionářů.",
        "ROE 3Y": "**3letý průměr ROE**\n\n• Ukazuje, zda je vysoká ziskovost kapitálu udržitelná dlouhodobě.",
        "Tržby y/y": "**Meziroční růst tržeb (Revenue Growth)**\n\n• **Optimální (nad 15 %):** Růstová firma získávající tržní podíl.",
        "Zisk y/y": "**Meziroční růst zisku na akcii (EPS Growth)**\n\n• **Optimální (nad 20 %):** Zisk roste rychleji než tržby (provozní páka funguje skvěle).",
        "Dluh D/E": "**Debt-to-Equity (Celkový dluh / Vlastní kapitál)**\n\n• **Optimální (pod 50 %):** Bezpečné, nízké zadlužení.\n• **Kritické (nad 150 %):** Vysoké riziko při růstu úrokových sazeb.",
        "Div. výnos": "**Dividendový výnos (Dividend Yield)**\n\n• **Optimální (2 % až 5 %):** Zdravá dividenda krytá zisky.\n• **Varovné (nad 8 %):** Často signalizuje trhem očekávané snížení dividendy (Dividend Trap).",
        "Potenciál": "**Analytický potenciál (Target Price vs Aktuální cena)**\n\n• Výpočet průměrného cíle analytiků z Wall Street na 12 měsíců dopředu."
    }

    def vytvor_p(nazev, zk, def_h, def_b):
        with st.sidebar.expander(f"📊 {nazev}", expanded=False):
            st.markdown(napovedy.get(nazev, ""))
            st.divider()
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

    st.sidebar.divider()
    w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
    w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
    w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
    w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.0)

    mapping_keys = ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    m_rows = []

    for item in filtered_data:
        inf = item["inf"]; t = item["t"]; name = item["name"]
        def sg(k, mult=1.0):
            v = inf.get(k); return float(v) * mult if v is not None and str(v) != "None" else 0.0
        
        pe_tr = sg("trailingPE") or sg("forwardPE")
        pe_fwd = sg("forwardPE") or pe_tr

        d_yield = sg("dividendYield")
        if d_yield < 0.2 and d_yield > 0: d_yield *= 100 

        raw_vals = {
            "Cena": sg("currentPrice"), "Změna": ((sg("currentPrice")/sg("previousClose", 1.0))-1)*100 if sg("previousClose") else 0,
            "P/E": pe_tr, "Forward P/E": pe_fwd, "P/S": sg("priceToSalesTrailing12Months"), 
            "P/B": sg("priceToBook"), "P/FCF": sg("marketCap")/sg("freeCashflow") if sg("freeCashflow") else 0,
            "H-Marže": sg("grossMargins", 100), "H-Marže 3Y": item["gm_3y"],
            "Č-Marže": sg("profitMargins", 100), "Č-Marže 3Y": item["nm_3y"],
            "ROE": sg("returnOnEquity", 100), "ROE 3Y": item["roe_3y"],
            "Tržby y/y": sg("revenueGrowth", 100), "Zisk y/y": sg("earningsGrowth", 100), "Dluh D/E": sg("debtToEquity"), 
            "Div. výnos": d_yield, "Potenciál": ((sg("targetMeanPrice")/sg("currentPrice", 1.0))-1)*100 if sg("targetMeanPrice") else 0
        }

        base_pe_points = get_b(raw_vals["P/E"], p_pe)
        adjusted_pe_points = base_pe_points
        
        if pe_tr > 0 and pe_fwd > 0:
            pomer = pe_fwd / pe_tr
            if pomer > 1.05:     
                adjusted_pe_points = (base_pe_points * 0.5) - 10
            elif pomer < 0.95:   
                adjusted_pe_points = base_pe_points * 1.25

        total = 0
        row_p = {"Titul": f"   └ body ({t})", "Type": "Points"}
        
        p_map = {
            "P/E": p_pe, "P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf,
            "H-Marže": p_gm, "H-Marže 3Y": p_gm_3y, 
            "Č-Marže": p_nm, "Č-Marže 3Y": p_nm_3y, 
            "ROE": p_roe, "ROE 3Y": p_roe_3y,
            "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Potenciál": p_pot
        }
        w_map = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}

        for k in mapping_keys:
            vw = w_map["v"] if k in ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF"] else (w_map["p"] if "Marže" in k or "ROE" in k else (w_map["g"] if k in ["Tržby y/y", "Zisk y/y", "Div. výnos", "Potenciál"] else w_map["r"]))
            
            if k == "P/E":
                b = adjusted_pe_points * vw
                row_p[k] = float(int(round(b)))
                total += b
            elif k == "Forward P/E":
                row_p[k] = 0.0 
            else:
                b = get_b(raw_vals[k], p_map[k]) * vw
                total += b
                row_p[k] = float(int(round(b)))

        row_v = {"Titul": name, "Type": "Value", "Změna": raw_vals["Změna"], "Cena": raw_vals["Cena"], "Score": int(total)}
        for k in mapping_keys:
            row_v[k] = raw_vals[k]
        
        m_rows.append(row_v)
        if zobrazit_body: m_rows.append(row_p)

    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_matrix(r):
            s = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            
            for i, col in enumerate(r.index):
                if col in ["Cena", "Změna"]: 
                    s[i] = f"color: {'#1b5e20' if r['Změna']>0 else '#b71c1c'}; font-weight: bold"
                
                if col == "Forward P/E":
                    pe = r.get("P/E", 0)
                    fwd = r.get("Forward P/E", 0)
                    if pe > 0 and fwd > 0:
                        if fwd / pe > 1.05: s[i] = 'background-color: #ffebee; color: #b71c1c; font-weight: bold' 
                        elif fwd / pe < 0.95: s[i] = 'background-color: #e8f5e9; color: #1b5e20; font-weight: bold' 

                val = r.get(col, 0)
                if col == "P/E" and isinstance(val, (int, float)) and val > 25: s[i] = 'background-color: #ffebee'
                if col == "Dluh D/E" and isinstance(val, (int, float)) and val > 120: s[i] = 'background-color: #ffcdd2'
            return s
        
        nastaveni_sloupcu = {
            "Type": None,
            "Titul": st.column_config.TextColumn("Titul", width=180),
            "Cena": st.column_config.NumberColumn("Cena", format="%.2f"),
            "Změna": st.column_config.NumberColumn("Změna", format="%.1f%%"),
            "Score": st.column_config.NumberColumn("Score", format="%d")
        }
        for k in mapping_keys:
            if k in pct_cols: nastaveni_sloupcu[k] = st.column_config.NumberColumn(k, format="%.1f%%")
            else: nastaveni_sloupcu[k] = st.column_config.NumberColumn(k, format="%.1f")

        st.dataframe(df.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150),
                    hide_index=True, height=750, width="stretch",
                    column_order=["Titul", "Cena", "Změna"] + mapping_keys + ["Score"],
                    column_config=nastaveni_sloupcu)

elif stranka == "Vnitřní hodnota (IV)":
    with st.expander("ℹ️ Metodická příručka: 3 Pilíře Vnitřní Hodnoty (IV)", expanded=False):
        st.markdown("Tato sekce kombinuje **7 klasických a moderních oceňovacích modelů** rozdělených do tří základních investičních logik (Pilířů). Výsledná férová cena kalkuluje konzervativní **maximum uvnitř každého pilíře** a následně provádí **vážený průměr** podle tebou zvolených vah v sidebaru.")
        st.divider()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 📈 Pilíř 1: Ziskové modely\n• **Grahamova formule:** Hodnota na základě současného EPS, očekávaného růstu a výnosu dluhopisů.\n• **P/E Multiplier Model:** Vynásobení EPS cílovým P/E ze sidebaru.\n• **RIM (Residual Income Model):** Účetní hodnota navýšená o budoucí nadbytečné zisky nad požadovanou výnosností (Re).")
        with c2:
            st.markdown("### 💸 Pilíř 2: Cashflow modely\n• **DCF / FCF Model:** Diskontuje budoucí generované Free Cash Flow (reálnou hotovost) zpět do současnosti.\n• **DDM (Dividend Discount Model):** Gordonův model. Oceňuje akcii výhradně na základě budoucích diskontovaných dividend.")
        with c3:
            st.markdown("### 🧱 Pilíř 3: Majetkově-Tržní\n• **P/S Multiplier Model:** Vynásobí tržby na akcii cílovým P/S ze sidebaru. Klíčové pro růstové tech/SaaS firmy.\n• **NAV Model (Net Asset Value):** Čistá účetní hodnota (Book Value). Likvidační hodnota firmy.")

    show_details = st.sidebar.toggle("🔓 Zobrazit detailní metody", value=False)
    with st.sidebar.expander("⚖️ Váhy pilířů", expanded=False):
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
        inf = item["inf"]; price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps')); bvps = safe_float(inf.get('bookValue'))
        fcf = safe_float(inf.get('freeCashflow')); rev = safe_float(inf.get('totalRevenue'))
        shares = safe_float(inf.get('sharesOutstanding')); div = safe_float(inf.get('dividendRate'))

        v_graham = (eps * (8.5 + 2 * (g_pct*100)) * 4.4) / y_bond if eps > 0 else 0
        v_pe = eps * target_pe if eps > 0 else 0
        v_rim = bvps + ((eps - (re_pct * bvps)) / (re_pct - g_pct)) if (bvps > 0 and re_pct > g_pct) else 0
        val_p1 = max(v_graham, v_pe, v_rim)
        v_fcf = ((fcf * (1 + g_pct)) / (re_pct - g_pct)) / shares if (shares > 0 and re_pct > g_pct and fcf > 0) else 0
        v_ddm = (div * (1 + g_pct)) / (re_pct - g_pct) if (div > 0 and re_pct > g_pct) else 0
        val_p2 = max(v_fcf, v_ddm)
        v_ps = (rev / shares) * target_ps if (shares > 0 and rev > 0) else 0
        v_nav = bvps if bvps > 0 else 0
        val_p3 = max(v_ps, v_nav)

        ws = [w1, w2, w3]; vals = [val_p1, val_p2, val_p3]
        weighted_sum = sum(v * w for v, w in zip(vals, ws) if v > 0)
        active_weights = sum(w for v, w in zip(vals, ws) if v > 0)
        fair_price = weighted_sum / active_weights if active_weights > 0 else 0
        upside = ((fair_price / price) - 1) * 100 if price > 0 else 0

        row = {
            "Titul": item["name"], "Cena": price, 
            "P1: Zisk": int(val_p1), "P2: CF": int(val_p2), "P3: Tržby": int(val_p3), 
            "Férová cena": int(fair_price), "Potenciál %": float(upside)
        }
        if show_details: row.update({"› Graham": int(v_graham), "› P/E": int(v_pe), "› RIM": int(v_rim), "› FCF": int(v_fcf), "› DDM": int(v_ddm), "› P/S": int(v_ps), "› NAV": int(v_nav)})
        iv_results.append(row)

    df_iv = pd.DataFrame(iv_results)
    if not df_iv.empty:
        def apply_all_styles(row):
            styles = [''] * len(row)
            up = row["Potenciál %"]
            bg = 'background-color: #d4edda' if up > 0 else ('background-color: #f8d7da' if up < 0 else '')
            tc = 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold'
            for i, col in enumerate(row.index):
                if col in ["Titul", "Potenciál %"]: styles[i] = bg
                if col == "Cena": styles[i] = tc
            return styles
            
        st.dataframe(df_iv.style.apply(apply_all_styles, axis=1).format({"Cena": "{:.2f}"}), 
                    hide_index=True, height=850, width="stretch",
                    column_config={"Potenciál %": st.column_config.NumberColumn("Potenciál %", format="%.1f%%")})

else:
    with st.expander("ℹ️ Legenda k RSI, doporučením a výpočtu ČISTÉ dividendy", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 📈 Konsenzus z Wall Street\n• Agregované střednědobé doporučení investičních bank (Goldman Sachs atd.).\n• **Strong Buy / Buy:** Očekává se silný růst.\n• **Hold:** Neutrální výhled.\n• **Sell:** Nadhodnocený titul.")
        with c2:
            st.markdown("### 📊 Technický indikátor RSI\n• Měří rychlost pohybů cen za 14 dní (0 až 100).\n• **RSI < 35 (Zelená):** Přeprodáno (silný výprodej, technická příležitost k nákupu).\n• **RSI > 65 (Červená):** Překoupeno (tržní euforie, hrozí krátkodobá korekce).")
        with c3:
            st.markdown("### 🧮 Odhad čistého výnosu\n• **UK Tituly (BTI, SHEL):** Automaticky 0% srážková daň.\n• **USA (USD) & ČR (CZK):** Srážková daň 15 %.\n• **Evropa (EUR) & Ostatní:** Konzervativní odhad 25 % (daňový průměr EU).\n\n*Scoring Matrix záměrně využívá hrubý výnos pro hodnocení čistého fundamentu firmy.*")

    c_rows, today = [], date.today()
    for item in filtered_data:
        inf = item["inf"]; ticker = item["t"]
        days_to = safe_date_diff(item["earn"], today)
        ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
        
        # Sběr dat o dividendách
        d_yield_gross = safe_float(inf.get('dividendYield'))
        if d_yield_gross < 0.2 and d_yield_gross > 0: d_yield_gross *= 100 
        
        currency = str(inf.get('currency', 'USD')).upper()
        
        # --- INTELIGENTNÍ DAŇOVÁ LOGIKA ---
        if ticker in ["BTI", "SHEL"] or ".LON" in ticker:
            tax_rate = 0.0  
        elif currency == "USD":
            tax_rate = 0.15 
        elif currency == "CZK":
            tax_rate = 0.15 
        else:
            tax_rate = 0.25 
            
        d_yield_net = d_yield_gross * (1 - tax_rate)

        c_rows.append({
            "Titul": item["name"], "Ticker": ticker, 
            "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", "Dní do": days_to,
            "Dividenda": f"{safe_float(inf.get('dividendRate')):.2f} {currency}", 
            "Div. výnos (hrubý)": d_yield_gross,
            "Čistý výnos (odhad)": d_yield_net,
            "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", 
            "Doporučení": inf.get('recommendationKey', '-').replace('_', ' ').title(), 
            "RSI": int(item['rsi']), "_rsi": item["rsi"]
        })
    df_c = pd.DataFrame(c_rows)
    if not df_c.empty:
        def style_calendar(r):
            s = [''] * len(r)
            d_idx = r.index.get_loc("Dní do")
            if r["Dní do"] < 0: s[d_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            elif r["Dní do"] < 14: s[d_idx] = 'background-color: #fff9c4; color: #f57f17; font-weight: bold'
            
            rec = str(r["Doporučení"]).lower(); rec_idx = r.index.get_loc("Doporučení")
            if "buy" in rec: s[rec_idx] = 'background-color: #e8f5e9; color: #1b5e20; font-weight: bold'
            elif "sell" in rec: s[rec_idx] = 'background-color: #ffebee; color: #b71c1c'
            
            rsi_idx = r.index.get_loc("RSI")
            if r["_rsi"] < 35: s[rsi_idx] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold'
            elif r["_rsi"] > 65: s[rsi_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            return s
            
        st.dataframe(df_c.style.apply(style_calendar, axis=1), 
                    hide_index=True, height=850, width="stretch",
                    column_config={
                        "_rsi": None,
                        "Div. výnos (hrubý)": st.column_config.NumberColumn("Div. výnos (hrubý)", format="%.2f%%"),
                        "Čistý výnos (odhad)": st.column_config.NumberColumn("Čistý výnos (odhad)", format="%.2f%%")
                    },
                    column_order=["Titul", "Ticker", "Earnings", "Dní do", "Dividenda", "Div. výnos (hrubý)", "Čistý výnos (odhad)", "Ex-Date", "Doporučení", "RSI"])
