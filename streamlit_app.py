import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, date

# --- KONFIGURACE ---
st.set_page_config(page_title="Valuační Portál V86.8", layout="wide")

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

# --- 2. DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_all_data(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t == "-": continue
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            # Pro RSI potřebujeme historii
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

# --- 3. NAČTENÍ A FILTR ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

st.sidebar.markdown("## **📊 Portfoliomanžer**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Kalendář & RSI", "Vnitřní hodnota (IV)"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

all_data = fetch_all_data(df_raw_list)
filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 4. STRÁNKA: VNITŘNÍ HODNOTA (IV) ---
if stranka == "Vnitřní hodnota (IV)":
    st.subheader("🎯 Odhad vnitřní hodnoty akcií (Intrinsic Value)")
    
    with st.sidebar.expander("⚙️ Nastavení modelů (IV)", expanded=True):
        g_pct = st.slider("Očekávaný růst (g) %", 0.0, 15.0, 3.0) / 100
        re_pct = st.slider("Požadovaná výnosnost (Re/WACC) %", 5.0, 15.0, 8.5) / 100
        y_bond = st.number_input("Výnos 20y dluhopisů (Y)", value=4.4)
        st.divider()
        w_graham = st.slider("Váha: Graham", 0.0, 1.0, 0.2)
        w_fcf = st.slider("Váha: FCF Model", 0.0, 1.0, 0.4)
        w_rim = st.slider("Váha: RIM Model", 0.0, 1.0, 0.4)

    iv_results = []
    for item in filtered_data:
        inf = item["inf"]
        price = safe_float(inf.get('currentPrice'))
        eps = safe_float(inf.get('trailingEps'))
        bvps = safe_float(inf.get('bookValue'))
        fcf = safe_float(inf.get('freeCashflow'))
        shares = safe_float(inf.get('sharesOutstanding'))
        
        # A) Graham Formula (Upravená)
        v_graham = (eps * (8.5 + 2 * (g_pct*100)) * 4.4) / y_bond if eps > 0 else 0
        
        # B) FCF Gordon Model
        v_fcf = 0
        if shares > 0 and re_pct > g_pct:
            v_fcf = ((fcf * (1 + g_pct)) / (re_pct - g_pct)) / shares
            
        # C) RIM (Residual Income Model) - zjednodušený z Excelu
        # V = BVPS + (EPS - Re * BVPS) / (Re - g)
        v_rim = 0
        if bvps > 0 and re_pct > g_pct:
            residual_income = eps - (re_pct * bvps)
            v_rim = bvps + (residual_income / (re_pct - g_pct))

        # Vážený průměr
        total_w = w_graham + w_fcf + w_rim
        if total_w > 0:
            fair_price = (v_graham * w_graham + v_fcf * w_fcf + v_rim * w_rim) / total_w
        else:
            fair_price = 0
            
        upside = ((fair_price / price) - 1) * 100 if price > 0 else 0
        
        iv_results.append({
            "Titul": item["name"],
            "Akt. Cena": price,
            "Graham F.": round(v_graham, 2),
            "FCF Model": round(v_fcf, 2),
            "RIM Model": round(v_rim, 2),
            "Férová cena": round(fair_price, 2),
            "Potenciál": round(upside, 1)
        })

    df_iv = pd.DataFrame(iv_results)
    if not df_iv.empty:
        def style_upside(val):
            color = '#1b5e20' if val > 10 else ('#b71c1c' if val < -10 else '#333')
            return f'color: {color}; font-weight: bold'

        # Použití map místo applymap pro kompatibilitu s novějším Pandas
        st.dataframe(
            df_iv.style.map(style_upside, subset=['Potenciál'])
            .background_gradient(subset=['Potenciál'], cmap='RdYlGn', vmin=-30, vmax=30),
            use_container_width=True, hide_index=True, height=600
        )
    else:
        st.warning("Žádná data pro výpočet vnitřní hodnoty.")

# --- 5. OSTATNÍ STRÁNKY (Zkráceně pro přehlednost) ---
elif stranka == "Scoring Matrix":
    st.subheader("📊 Scoring Matrix")
    # Zde by pokračoval váš kód pro Scoring Matrix (definice p_pe, atd.)
    st.info("Zde je prostor pro váš původní kód Scoring Matrixu.")

elif stranka == "Kalendář & RSI":
    st.subheader("📅 Kalendář událostí a RSI")
    # Zde by pokračoval váš kód pro Kalendář
    st.info("Zde je prostor pro váš původní kód Kalendáře.")
