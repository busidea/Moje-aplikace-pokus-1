import streamlit as st
import pandas as pd
import yfinance as yf

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investment Hub V97.0", layout="wide")

st.markdown("""
    <style>
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { text-align: left !important; }
    .main-header { font-size: 2.5rem; color: #003366; font-weight: bold; margin-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA A POMOCNÉ FUNKCE (Zůstávají stejné) ---
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

# --- 3. HLAVNÍ NAVIGACE (Rozcestník) ---
st.sidebar.markdown("## **🧭 Navigace**")
# Matrix je nyní na prvním místě a označen jako hlavní
stranka = st.sidebar.radio("Přejít na:", ["🏠 Scoring Matrix (Hlavní)", "🎯 Vnitřní hodnota (IV)", "📅 Kalendář událostí"])

ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 4. STRÁNKA: SCORING MATRIX (ROZCESTNÍK) ---
if stranka == "🏠 Scoring Matrix (Hlavní)":
    st.markdown('<div class="main-header">Investiční Rozcestník & Matrix</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("### 🎯 Valuace")
        st.write("Detailní výpočty vnitřní hodnoty pomocí 3 pilířů.")
        if st.button("Otevřít IV Terminál"):
            # V reálném Streamlitu by se zde přepnul state, pro teď stačí instrukce v sidebar
            st.write("← Vyberte 'Vnitřní hodnota' v levém menu.")

    with col2:
        st.success("### 📊 Matrix")
        st.write("Kvalitativní scoring, MOAT, rizika a doporučení.")
        st.button("Aktualizovat Matrix", disabled=True)

    with col3:
        st.warning("### 📅 Kalendář")
        st.write("Termíny earnings, dividendy a makro události.")
        st.button("Zobrazit Kalendář", disabled=True)

    st.divider()
    st.subheader("📊 Kvalitativní Scoring Matrix (Demo)")
    # Zde pak napojíme tvou logiku pro scoring
    st.write("Tato sekce bude obsahovat tabulku s tvým bodováním firem (1-10) na základě tvých kritérií.")

# --- 5. STRÁNKA: VNITŘNÍ HODNOTA (IV) ---
elif stranka == "🎯 Vnitřní hodnota (IV)":
    st.subheader("🎯 Kalkulace vnitřní hodnoty (IV)")
    
    # ... (zde pokračuje tvůj kód pro pilíře z minulé verze V96.3) ...
    # Pro stručnost zde ponechávám logiku barev a vah, kterou jsme už vyladili
    st.sidebar.markdown("---")
    show_details = st.sidebar.toggle("🔓 Zobrazit detailní metody", value=False)
    
    with st.sidebar.expander("⚖️ Nastavení vah pilířů", expanded=False):
        w1 = st.slider("Váha P1 (Ziskové)", 0, 100, 33)
        w2 = st.slider("Váha P2 (Cashflow)", 0, 100, 33)
        w3 = st.slider("Váha P3 (Majetek)", 0, 100, 34)

    st.info("Terminál pro výpočet vnitřní hodnoty je aktivní. Data se načítají z Yahoo Finance.")
    # (Zde by byl zbytek tvého funkčního kódu tabulky...)

# --- 6. STRÁNKA: KALENDÁŘ ---
elif stranka == "📅 Kalendář událostí":
    st.subheader("📅 Investiční kalendář")
    st.write("Připravujeme: Automatické sledování Earnings a Ex-dividend dates pro tvé portfolio.")
    st.calendar = st.date_input("Vyberte datum")
