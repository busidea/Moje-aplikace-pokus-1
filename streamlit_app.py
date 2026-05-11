import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Valuační Terminál V92.1", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { 
        text-align: left !important; font-weight: bold !important; color: #003366 !important;
    }
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
            # RSI pro technický náhled
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie')), 
                "earn": row.get('Earnings Day'), 
                "name": inf.get('longName', t)
            })
        except: continue
    return res

# --- 3. NAČTENÍ DAT A NAVIGACE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

st.sidebar.markdown("## **📈 Valuační Model**")
stranka = st.sidebar.radio("Stránka:", ["Vnitřní hodnota (IV)", "Scoring Matrix", "Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr titulů:", ["Portfolio", "Sledované", "Vše"], index=0)

all_data = fetch_all_data(df_raw_list)
filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 4. LOGIKA: VNITŘNÍ HODNOTA (IV) ---
if stranka == "Vnitřní hodnota (IV)":
    st.subheader("🎯 Komplexní ocenění společností (Intrinsic Value)")
    
    with st.sidebar.expander("⚙️ Nastavení globálních parametrů", expanded=True):
        g_pct = st.slider("Dlouhodobý růst (g) %", 0.0, 10.0, 3.0) / 100
        re_pct = st.slider("Požadovaná výnosnost (Re) %", 5.0, 15.0, 9.0) / 100
        y_bond = st.number_input("Výnos 20y dluhopisů (pro Grahamův vzorec)", value=4.4)
        st.divider()
        st.write("**Cílové násobky (Multiples):**")
        target_pe = st.slider("Cílové P/E (pro ziskové firmy)", 5, 40, 15)
        target_ps = st.slider("Cílové P/S (pro růstové/ztrátové)", 0.5, 15.0, 3.0)
        
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

        # 1. PILÍŘ: ZISKOVÉ METODY (Graham, Multiples P/E, EVA základ)
        v_graham = (eps * (8.5 + 2 * (g_pct*100)) * 4.4) / y_bond if eps > 0 else 0
        v_pe = eps * target_pe if eps > 0 else 0
        # EVA zjednodušeně: (EPS - (Re * BVPS)) / (Re - g) + BVPS (podobné RIM)
        v_eva = bvps + ((eps - (re_pct * bvps)) / (re_pct - g_pct)) if (bvps > 0 and re_pct > g_pct) else 0
        
        val_profit = max(v_graham, v_pe, v_eva) if (v_graham > 0 or v_pe > 0 or v_eva > 0) else 0

        # 2. PILÍŘ: CASHFLOW METODY (DCF/FCF, DDM)
        v_fcf = ((fcf * (1 + g_pct)) / (re_pct - g_pct)) / shares if (shares > 0 and re_pct > g_pct and fcf > 0) else 0
        v_ddm = (div * (1 + g_pct)) / (re_pct - g_pct) if (div > 0 and re_pct > g_pct) else 0
        
        val_cash = max(v_fcf, v_ddm) if (v_fcf > 0 or v_ddm > 0) else 0

        # 3. PILÍŘ: TRŽEBNÍ A MAJETKOVÉ (P/S Multiples, NAV) - KLÍČOVÉ PRO EHANG
        v_ps = (rev / shares) * target_ps if (shares > 0 and rev > 0) else 0
        v_nav = bvps if bvps > 0 else 0
        
        val_assets = max(v_ps, v_nav) if (v_ps > 0 or v_nav > 0) else 0

        # FINÁLNÍ VÁŽENÝ PRŮMĚR (Dynamický - bere jen ty pilíře, co mají data)
        pillars = [p for p in [val_profit, val_cash, val_assets] if p > 0]
        fair_price = sum(pillars) / len(pillars) if pillars else 0
        upside = ((fair_price / price) - 1) * 100 if price > 0 else 0

        iv_results.append({
            "Titul": item["name"],
            "Cena": round(price, 2),
            "Ziskové (P/E, EVA)": int(val_profit) if val_profit > 0 else 0,
            "Cashflow (FCF)": int(val_cash) if val_cash > 0 else 0,
            "Tržby/Majetek (P/S)": int(val_assets) if val_assets > 0 else 0,
            "Férová cena": int(fair_price),
            "Potenciál": round(upside, 1),
            "Potenciál %": f"{round(upside, 1)}%"
        })

    df_iv = pd.DataFrame(iv_results)
    if not df_iv.empty:
        # Přeformátování nul na pomlčky pro čistý vzhled
        for col in ["Ziskové (P/E, EVA)", "Cashflow (FCF)", "Tržby/Majetek (P/S)"]:
            df_iv[col] = df_iv[col].apply(lambda x: "-" if x == 0 else x)

        st.dataframe(
            df_iv.style.map(lambda x: f'color: {"#1b5e20" if x > 10 else ("#b71c1c" if x < -10 else "#333")}; font-weight: bold', subset=['Potenciál'])
            .background_gradient(subset=['Potenciál'], cmap='RdYlGn', vmin=-40, vmax=40),
            use_container_width=True, hide_index=True, height=600,
            column_order=["Titul", "Cena", "Ziskové (P/E, EVA)", "Cashflow (FCF)", "Tržby/Majetek (P/S)", "Férová cena", "Potenciál %"]
        )
    else:
        st.info("Žádná data k zobrazení. Zkontrolujte filtry.")

# --- 5. OSTATNÍ STRÁNKY ---
elif stranka == "Scoring Matrix":
    st.subheader("📊 Scoring Matrix")
    st.info("Zde bude váš bodovací systém.")

elif stranka == "Kalendář & RSI":
    st.subheader("📅 Kalendář událostí a RSI")
    st.info("Přehled termínů výsledků a technického stavu akcií.")
