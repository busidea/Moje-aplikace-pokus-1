import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import date

# --- KONFIGURACE ---
st.set_page_config(page_title="Valuační Matrix V86.7", layout="wide")

# --- POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val) == "nan" or str(val) == "None": return 0.0
        return float(val)
    except: return 0.0

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_data(df_input):
    res = []
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t == "-" or t == "NAN": continue
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            res.append({"t": t, "inf": inf, "kat": str(row.get('Kategorie')), "name": inf.get('longName', t)})
        except: continue
    return res

# --- GLOBÁLNÍ DATA ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- SIDEBAR ---
st.sidebar.markdown("## **📈 Analýza Hodnoty**")
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Kalendář & RSI", "Vnitřní hodnota (IV)"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

# Globální parametry pro IV (vstupy z tvého Excelu)
with st.sidebar.expander("⚙️ Nastavení modelů (IV)", expanded=False):
    g_default = st.slider("Očekávaný růst (g) %", 0, 15, 3) / 100
    wacc_default = st.slider("Diskontní sazba (WACC) %", 5, 15, 8) / 100
    bond_yield = st.number_input("Výnos 20y dluhopisů (Y)", value=4.4)
    w_graham = st.slider("Váha: Graham", 0.0, 1.0, 0.3)
    w_dcf = st.slider("Váha: DCF/FCF", 0.0, 1.0, 0.4)
    w_mult = st.slider("Váha: Multiples", 0.0, 1.0, 0.3)

# --- LOGIKA VÝPOČTU VNITŘNÍ HODNOTY ---
raw_data = fetch_data(df_raw)
iv_rows = []

for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t = item["inf"], item["t"]
    
    curr_price = safe_float(inf.get('currentPrice'))
    eps = safe_float(inf.get('trailingEps'))
    bvps = safe_float(inf.get('bookValue'))
    fcf = safe_float(inf.get('freeCashflow'))
    shares = safe_float(inf.get('sharesOutstanding'))
    ps_hist = safe_float(inf.get('priceToSalesTrailing12Months')) # aktuální pro srovnání
    
    # 1. Grahamova Formule (V = (EPS * (8.5 + 2g) * 4.4) / Y)
    iv_graham_f = (eps * (8.5 + 2 * (g_default * 100)) * 4.4) / bond_yield if eps > 0 else 0
    
    # 2. Grahamovo číslo (sqrt(22.5 * EPS * BVPS))
    iv_graham_n = np.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else 0
    
    # 3. FCF Model (V = (FCF * (1+g)) / (WACC - g) / shares)
    iv_fcf = 0
    if shares > 0 and (wacc_default > g_default):
        total_fcf_val = (fcf * (1 + g_default)) / (wacc_default - g_default)
        iv_fcf = total_fcf_val / shares
    
    # 4. Multiples (P/E konzervativní odhad - např. 15x EPS)
    iv_mult = eps * 15 

    # Průměrná vnitřní hodnota (Vážená)
    # Pokud je některá metoda 0 (nejsou data), váha se přerozdělí nebo ignoruje
    methods = [iv_graham_f, iv_fcf, iv_mult]
    weights = [w_graham, w_dcf, w_mult]
    
    avg_iv = sum(m * w for m, w in zip(methods, weights)) / sum(weights)
    upside = ((avg_iv / curr_price) - 1) * 100 if curr_price > 0 else 0

    iv_rows.append({
        "Titul": item["name"],
        "Cena": curr_price,
        "Graham F.": round(iv_graham_f, 2),
        "Graham č.": round(iv_graham_n, 2),
        "FCF Model": round(iv_fcf, 2),
        "Multiples": round(iv_mult, 2),
        "Férová cena": round(avg_iv, 2),
        "Potenciál": round(upside, 1)
    })

# --- ZOBRAZENÍ ---
if stranka == "Vnitřní hodnota (IV)":
    st.subheader("🎯 Odhad vnitřní hodnoty akcií")
    st.info("Výpočet kombinuje Grahamovu formuli, FCF model a srovnávací multiples. Váhy a parametry lze upravit v levém panelu.")
    
    df_iv = pd.DataFrame(iv_rows)
    if not df_iv.empty:
        def style_iv(val):
            color = '#1b5e20' if val > 10 else ('#b71c1c' if val < -10 else '#333')
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            df_iv.style.applymap(style_iv, subset=['Potenciál'])
            .background_gradient(subset=['Potenciál'], cmap='RdYlGn', vmin=-50, vmax=50),
            use_container_width=True, hide_index=True
        )
        
elif stranka == "Scoring Matrix":
    st.write("Zde by byl váš původní Scoring Matrix kód...")
else:
    st.write("Zde by byl váš původní Kalendář kód...")
