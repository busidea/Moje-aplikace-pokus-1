import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import date

# --- KONFIGURACE ---
st.set_page_config(page_title="Valuační Portál V86.9", layout="wide")

# CSS pro zarovnání a vzhled
st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { 
        text-align: left !important; font-weight: bold !important; color: #003366 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. POMOCNÉ FUNKCE ---
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
        if not t or t == "-" or t == "nan": continue
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            # RSI výpočet
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

# --- 2. NAČTENÍ DAT ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 3. SIDEBAR (NAVIGACE) ---
st.sidebar.markdown("## **📊 Portfoliomanžer**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Kalendář & RSI", "Vnitřní hodnota (IV)"])
st.sidebar.divider()
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

all_data = fetch_all_data(df_raw_list)
filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 4. STRÁNKA: VNITŘNÍ HODNOTA (IV) ---
if stranka == "Vnitřní hodnota (IV)":
    st.subheader("🎯 Komplexní odhad vnitřní hodnoty")
    
    with st.sidebar.expander("⚙️ Nastavení modelů (IV)", expanded=True):
        g_pct = st.slider("Očekávaný růst (g) %", 0.0, 15.0, 3.0) / 100
        re_pct = st.slider("Požadovaná výnosnost (Re) %", 5.0, 15.0, 8.5) / 100
        y_bond = st.number_input("Výnos 20y dluhopisů (Y)", value=4.4)
        target_ps = st.slider("Cílový P/S násobek (pro firmy v růstu)", 1.0, 10.0, 3.5)
        st.caption("Váhy metod:")
        w_profit = st.slider("Váha: Ziskové modely (Graham, RIM)", 0.0, 1.0, 0.4)
        w_cash = st.slider("Váha: Cashflow modely (FCF, DDM)", 0.0, 1.0, 0.3)
        w_sales = st.slider("Váha: Majetkové a tržební (NAV, P/S)", 0.0, 1.0, 0.3)

    iv_results = []
    for item in filtered_data:
        inf = item["inf"]
        price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps'))
        bvps = safe_float(inf.get('bookValue'))
        fcf = safe_float(inf.get('freeCashflow'))
        shares = safe_float(inf.get('sharesOutstanding'))
        div = safe_float(inf.get('dividendRate'))
        rev = safe_float(inf.get('totalRevenue'))
        
        # 1. Ziskové metody (Graham, RIM)
        v_graham = (eps * (8.5 + 2 * (g_pct*100)) * 4.4) / y_bond if eps > 0 else 0
        v_rim = bvps + ((eps - (re_pct * bvps)) / (re_pct - g_pct)) if (bvps > 0 and re_pct > g_pct) else 0
        
        # 2. Cashflow metody (FCF, DDM)
        v_fcf = ((fcf * (1 + g_pct)) / (re_pct - g_pct)) / shares if (shares > 0 and re_pct > g_pct and fcf > 0) else 0
        v_ddm = (div * (1 + g_pct)) / (re_pct - g_pct) if (div > 0 and re_pct > g_pct) else 0
        
        # 3. Tržební a Majetkové (P/S, NAV) - FUNGUJE I PRO FIRMY VE ZTRÁTĚ
        v_ps = (rev / shares) * target_ps if (shares > 0 and rev > 0) else 0
        v_nav = bvps if bvps > 0 else 0

        # Dynamický vážený průměr
        # Rozdělíme metody do skupin podle vašich vah
        methods = [
            (v_graham, w_profit/2 if v_graham > 0 else 0),
            (v_rim, w_profit/2 if v_rim > 0 else 0),
            (v_fcf, w_cash/2 if v_fcf > 0 else 0),
            (v_ddm, w_cash/2 if v_ddm > 0 else 0),
            (v_ps, w_sales/2 if v_ps > 0 else 0),
            (v_nav, w_sales/2 if v_nav > 0 else 0)
        ]
        
        active_vals = [m[0] * m[1] for m in methods if m[1] > 0]
        active_weights = [m[1] for m in methods if m[1] > 0]
        
        fair_price = sum(active_vals) / sum(active_weights) if sum(active_weights) > 0 else 0
        upside = ((fair_price / price) - 1) * 100 if price > 0 else 0
        
        iv_results.append({
            "Titul": item["name"],
            "Cena": round(price, 2),
            "Graham/RIM": int(max(v_graham, v_rim)),
            "FCF/DDM": int(max(v_fcf, v_ddm)),
            "Tržby/NAV": int(max(v_ps, v_nav)), # Toto ukáže hodnotu i pro EHANG
            "Férová cena": int(fair_price),
            "Potenciál": round(upside, 1),
            "Potenciál %": f"{round(upside, 1)}%"
        })

    df_iv = pd.DataFrame(iv_results)
    if not df_iv.empty:
        # Formátování pro přehlednost
        for col in ["Graham/RIM", "FCF/DDM", "Tržby/NAV"]:
            df_iv[col] = df_iv[col].apply(lambda x: "-" if x <= 0 else x)

        st.dataframe(
            df_iv.style.map(lambda x: f'color: {"#1b5e20" if x > 10 else ("#b71c1c" if x < -10 else "#333")}; font-weight: bold', subset=['Potenciál'])
            .background_gradient(subset=['Potenciál'], cmap='RdYlGn', vmin=-30, vmax=30),
            use_container_width=True, hide_index=True, height=600,
            column_order=["Titul", "Cena", "Graham/RIM", "FCF/DDM", "Tržby/NAV", "Férová cena", "Potenciál %"]
        )
# --- 5. OSTATNÍ STRÁNKY (SCORING & KALENDÁŘ) ---
elif stranka == "Scoring Matrix":
    st.subheader("📊 Scoring Matrix")
    # Zde můžete nechat kód pro scoring z předchozích verzí...
    st.info("Zde je prostor pro váš původní Scoring Matrix.")

elif stranka == "Kalendář & RSI":
    st.subheader("📅 Kalendář událostí a RSI")
    # Zde můžete nechat kód pro kalendář z předchozích verzí...
    st.info("Zde je prostor pro váš původní Kalendář.")
