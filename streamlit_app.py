import streamlit as st
import pandas as pd
import yfinance as yf

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Valuační Terminál V96.3", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { text-align: left !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
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

@st.cache_data(ttl=3600)
def fetch_all_data(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t in ["-", "nan", "NAN"]: continue
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            res.append({"t": t, "inf": inf, "kat": str(row.get('Kategorie')), "name": inf.get('longName', t)})
        except: continue
    return res

# --- 3. DATA A NAVIGACE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

st.sidebar.markdown("## **📊 Nastavení analýzy**")
stranka = st.sidebar.radio("Zobrazení:", ["Vnitřní hodnota (IV)", "Scoring Matrix"])
show_details = st.sidebar.toggle("🔓 Zobrazit detailní metody", value=False)
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

all_data = fetch_all_data(df_raw_list)
filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 4. LOGIKA: VNITŘNÍ HODNOTA (IV) ---
if stranka == "Vnitřní hodnota (IV)":
    st.subheader("🎯 Komplexní ocenění společností")
    
    with st.expander("ℹ️ Jak se počítá férová cena?"):
        st.write("**Férová cena = (P1 × w1 + P2 × w2 + P3 × w3) / (součet aktivních vah)**")
        st.caption("Modrá barva označuje tržní cenu (TC). Titul a Potenciál se barví podle toho, zda je akcie podhodnocená (zelená) nebo nadhodnocená (červená).")

    # --- BOČNÍ PANEL: VÁHY ---
    with st.sidebar.expander("⚖️ Nastavení vah pilířů", expanded=False):
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
        inf = item["inf"]
        price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps'))
        bvps = safe_float(inf.get('bookValue'))
        fcf = safe_float(inf.get('freeCashflow'))
        rev = safe_float(inf.get('totalRevenue'))
        shares = safe_float(inf.get('sharesOutstanding'))
        div = safe_float(inf.get('dividendRate'))

        # VÝPOČTY PILÍŘŮ
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

        # DYNAMICKÝ VÁŽENÝ PRŮMĚR
        vals = [val_p1, val_p2, val_p3]
        ws = [w1, w2, w3]
        weighted_sum = sum(v * w for v, w in zip(vals, ws) if v > 0)
        active_weights = sum(w for v, w in zip(vals, ws) if v > 0)
        
        fair_price = weighted_sum / active_weights if active_weights > 0 else 0
        upside = ((fair_price / price) - 1) * 100 if price > 0 else 0

        row = {
            "Titul": item["name"],
            "Cena": price,
            "P1: Zisk": int(val_p1) if val_p1 > 0 else 0,
            "P2: CF": int(val_p2) if val_p2 > 0 else 0,
            "P3: Tržby": int(val_p3) if val_p3 > 0 else 0,
            "Férová cena": int(fair_price),
            "Potenciál_num": upside,
            "Potenciál %": f"{upside:.1f}%"
        }
        if show_details:
            row.update({"› Graham": int(v_graham), "› P/E": int(v_pe), "› RIM": int(v_rim), "› FCF": int(v_fcf), "› DDM": int(v_ddm), "› P/S": int(v_ps), "› NAV": int(v_nav)})
        iv_results.append(row)

    df_iv = pd.DataFrame(iv_results)
    if not df_iv.empty:
        # STYLOVÁNÍ TABULKY
        def apply_all_styles(row):
            styles = [''] * len(row)
            up = row["Potenciál_num"]
            bg = 'background-color: #d4edda' if up > 0 else ('background-color: #f8d7da' if up < 0 else '')
            tc = 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold'
            
            for i, col in enumerate(row.index):
                if col in ["Titul", "Potenciál %"]: styles[i] = bg
                if col == "Cena": styles[i] = tc
            return styles

        cols_to_dash = [c for c in df_iv.columns if c not in ["Titul", "Cena", "Potenciál_num", "Potenciál %"]]
        for c in cols_to_dash: df_iv[c] = df_iv[c].apply(lambda x: "-" if x <= 0 else x)

        column_order = ["Titul", "Cena"]
        if show_details: column_order += ["› Graham", "› P/E", "› RIM", "P1: Zisk", "› FCF", "› DDM", "P2: CF", "› P/S", "› NAV", "P3: Tržby"]
        else: column_order += ["P1: Zisk", "P2: CF", "P3: Tržby"]
        column_order += ["Férová cena", "Potenciál %"]

        st.dataframe(
            df_iv.style.apply(apply_all_styles, axis=1).format({"Cena": "{:.2f}"}),
            use_container_width=True, hide_index=True, height=600, column_order=column_order
        )

elif stranka == "Scoring Matrix":
    st.subheader("📊 Scoring Matrix")
    st.info("Zde bude váš kvalitativní model.")
