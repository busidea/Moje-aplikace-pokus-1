import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Valuační Terminál V95.0", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    /* Zarovnání titulů doleva zůstává */
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
    
    with st.expander("ℹ️ Legenda: Co tvoří jednotlivé pilíře?"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**🔵 P1: Ziskové**")
            st.caption("Graham, P/E Multiples, RIM/EVA.")
        with col2:
            st.markdown("**🟢 P2: Cashflow**")
            st.caption("FCF Model, DDM.")
        with col3:
            st.markdown("**🟠 P3: Tržby/Majetek**")
            st.caption("P/S Multiples, NAV.")

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

        # Výpočty
        v_graham = (eps * (8.5 + 2 * (g_pct*100)) * 4.4) / y_bond if eps > 0 else 0
        v_pe = eps * target_pe if eps > 0 else 0
        v_rim = bvps + ((eps - (re_pct * bvps)) / (re_pct - g_pct)) if (bvps > 0 and re_pct > g_pct) else 0
        val_profit = max(v_graham, v_pe, v_rim)

        v_fcf = ((fcf * (1 + g_pct)) / (re_pct - g_pct)) / shares if (shares > 0 and re_pct > g_pct and fcf > 0) else 0
        v_ddm = (div * (1 + g_pct)) / (re_pct - g_pct) if (div > 0 and re_pct > g_pct) else 0
        val_cash = max(v_fcf, v_ddm)

        v_ps = (rev / shares) * target_ps if (shares > 0 and rev > 0) else 0
        v_nav = bvps if bvps > 0 else 0
        val_assets = max(v_ps, v_nav)

        pillars = [p for p in [val_profit, val_cash, val_assets] if p > 0]
        fair_price = sum(pillars) / len(pillars) if pillars else 0
        upside = ((fair_price / price) - 1) * 100 if price > 0 else 0

        row = {
            "Titul": item["name"],
            "Cena": f"{price:.2f}", # Formát na 2 desetinná místa jako text pro tabulku
            "P1: Ziskové": int(val_profit) if val_profit > 0 else 0,
            "P2: Cashflow": int(val_cash) if val_cash > 0 else 0,
            "P3: Tržby/Majetek": int(val_assets) if val_assets > 0 else 0,
            "Férová cena": int(fair_price),
            "Potenciál_num": upside, # Skryté číslo pro barvení
            "Potenciál %": f"{upside:.1f}%"
        }
        
        if show_details:
            row.update({
                "› Graham": int(v_graham), "› P/E": int(v_pe), "› RIM/EVA": int(v_rim),
                "› FCF": int(v_fcf), "› DDM": int(v_ddm), "› P/S": int(v_ps), "› NAV": int(v_nav)
            })
        iv_results.append(row)

    df_iv = pd.DataFrame(iv_results)
    if not df_iv.empty:
        # Pomocná funkce pro barvení řádků podle potenciálu
        def color_by_upside(row):
            val = row["Potenciál_num"]
            color = 'background-color: #d4edda' if val > 0 else ('background-color: #f8d7da' if val < 0 else '')
            return [color if (col == "Titul" or col == "Potenciál %") else '' for col in row.index]

        # Úklid nul na pomlčky
        cols_to_clean = [c for c in df_iv.columns if c not in ["Titul", "Cena", "Potenciál_num", "Potenciál %"]]
        for c in cols_to_clean: df_iv[c] = df_iv[c].apply(lambda x: "-" if x <= 0 else x)

        # Pořadí sloupců
        column_order = ["Titul", "Cena"]
        if show_details:
            column_order += ["› Graham", "› P/E", "› RIM/EVA", "P1: Ziskové", "› FCF", "› DDM", "P2: Cashflow", "› P/S", "› NAV", "P3: Tržby/Majetek"]
        else:
            column_order += ["P1: Ziskové", "P2: Cashflow", "P3: Tržby/Majetek"]
        column_order += ["Férová cena", "Potenciál %"]

        st.dataframe(
            df_iv.style.apply(color_by_upside, axis=1)
            .map(lambda x: 'font-weight: bold; color: #155724' if (isinstance(x, str) and '+' in x) else '', subset=['Potenciál %']),
            use_container_width=True, hide_index=True, height=600,
            column_order=column_order
        )

# --- 5. OSTATNÍ ---
elif stranka == "Scoring Matrix":
    st.subheader("📊 Scoring Matrix")
    st.info("Zde bude váš bodovací systém.")
