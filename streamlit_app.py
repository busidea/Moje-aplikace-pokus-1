import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import numpy as np

st.set_page_config(page_title="Investiční Matrix V75", layout="wide")

# --- 1. NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        return df
    except: return pd.DataFrame()

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 2. STRATEGICKÝ PŘEPÍNAČ V SIDEBARU ---
st.sidebar.header("🎯 Investiční Strategie")
strategie = st.sidebar.radio(
    "Zvolte mód nastavení:",
    ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový", "⚖️ Vyvážený"],
    index=0,
    help="Tovární nastavení přepnou váhy a bodová pásma podle dané investiční filozofie."
)

with st.sidebar.expander("📖 Popis vybrané strategie"):
    if strategie == "Vlastní":
        st.write("Máte plnou kontrolu nad každým parametrem níže.")
    elif strategie == "🛡️ Konzervativní":
        st.write("**Filozofie:** Priorita je ochrana kapitálu. Hledáme nízké P/E, nízký dluh a solidní dividendu. Vysoké valuace jsou penalizovány.")
    elif strategie == "🚀 Růstový":
        st.write("**Filozofie:** Priorita je dravost. Hledáme vysoký růst tržeb a zisků. Tolerujeme vysoké P/E i absenci dividendy.")
    elif strategie == "⚖️ Vyvážený":
        st.write("**Filozofie:** Rozumný kompromis. Hledáme kvalitní firmy s mírným růstem za férovou cenu.")

# Pomocná funkce pro vracení bodů (pro tovární nastavení)
def get_b_direct(val, pasma_h, pasma_b):
    for h, b in zip(pasma_h, pasma_b):
        if val <= h: return b
    return pasma_b[-1]

# --- 3. DEFINICE PARAMETRŮ (PODLE STRATEGIE) ---
# Pokud je "Vlastní", zobrazíme klasické posuvníky a inputy
if strategie == "Vlastní":
    st.sidebar.divider()
    w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.2)
    w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.5)
    w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
    w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.8)

    def vytvor_p(nazev, zk, def_h, def_b):
        with st.sidebar.expander(f"📊 {nazev}", expanded=False):
            d = []
            for i in range(5):
                c1, c2 = st.columns(2)
                h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
                b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
                d.append({"h": h, "b": b})
            return d

    # Výchozí analytické nastavení (jako v V74)
    p_pe = vytvor_p("P/E", "pe", [15, 20, 30, 45, 999], [15, 10, 5, 0, -10])
    p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 22, 35, 50, 999], [15, 10, 5, 0, -10])
    p_nm = vytvor_p("Č-Marže", "nm", [8, 15, 25, 40, 999], [0, 5, 12, 18, 25])
    p_rev = vytvor_p("Tržby y/y", "rev", [0, 8, 15, 30, 999], [-5, 5, 12, 18, 20])
    p_deb = vytvor_p("Dluh D/E", "deb", [40, 90, 150, 250, 999], [15, 10, 0, -10, -25])
    p_pot = vytvor_p("Potenciál", "pot", [5, 15, 25, 40, 999], [0, 5, 15, 25, 30])
    # Ostatní parametry by se definovaly podobně...

# --- 4. VÝPOČETNÍ JÁDRO ---
@st.cache_data(ttl=3600)
def fetch_v75(df_input):
    if df_input.empty: return []
    results, today = [], date.today()
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        try:
            tick = yf.Ticker(t)
            inf = tick.info
            hist = tick.history(period="1mo")
            rsi = 50
            if len(hist) > 14:
                delta = hist['Close'].diff(); gain = delta.where(delta > 0, 0).rolling(14).mean(); loss = -delta.where(delta < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
            results.append({"ticker": t, "info": inf, "rsi": rsi, "kat": row.get('Kategorie', 'Vše'), "earn": row.get('Earnings Day')})
        except: continue
    return results

raw_data_all = fetch_v75(df_raw)
filtr_kat = st.sidebar.selectbox("Kategorie:", ["Vše", "Portfolio", "Sledované"], index=1)
show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=False)

# --- 5. APLIKACE STRATEGIE NA DATA ---
m_rows, c_rows = [], []
for item in raw_data_all:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t = item["info"], item["ticker"]
    def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
    
    # Data Tickeru
    d = {
        "Ticker": t, "Cena": g("currentPrice"), "Změna": ((g("currentPrice")/g("previousClose", 1))-1)*100,
        "P/E": g("trailingPE") or g("forwardPE"), "Č-Marže": g("profitMargins", 100),
        "Tržby y/y": g("revenueGrowth", 100), "Dluh D/E": g("debtToEquity"),
        "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0, "Type": "Val"
    }

    # BODOVÁNÍ PODLE STRATEGIE
    if strategie == "🛡️ Konzervativní":
        w_v, w_p, w_g, w_r = 2.0, 1.5, 0.5, 2.0
        b_pe = get_b_direct(d["P/E"], [12, 18, 25, 35, 999], [20, 10, 0, -10, -30])
        b_nm = get_b_direct(d["Č-Marže"], [5, 10, 15, 25, 999], [0, 5, 10, 20, 30])
        b_rev = get_b_direct(d["Tržby y/y"], [2, 5, 10, 15, 999], [0, 5, 10, 15, 20])
        b_deb = get_b_direct(d["Dluh D/E"], [30, 60, 100, 150, 999], [25, 15, 0, -20, -50])
    elif strategie == "🚀 Růstový":
        w_v, w_p, w_g, w_r = 0.5, 1.0, 2.5, 1.0
        b_pe = get_b_direct(d["P/E"], [25, 35, 45, 60, 999], [10, 5, 0, -5, -15])
        b_nm = get_b_direct(d["Č-Marže"], [5, 12, 20, 30, 999], [0, 5, 10, 15, 20])
        b_rev = get_b_direct(d["Tržby y/y"], [10, 20, 40, 60, 999], [0, 10, 20, 30, 40])
        b_deb = get_b_direct(d["Dluh D/E"], [100, 200, 300, 400, 999], [10, 5, 0, -10, -20])
    elif strategie == "⚖️ Vyvážený":
        w_v, w_p, w_g, w_r = 1.2, 1.5, 1.2, 1.5
        b_pe = get_b_direct(d["P/E"], [15, 22, 30, 40, 999], [15, 10, 5, 0, -10])
        b_nm = get_b_direct(d["Č-Marže"], [8, 15, 25, 35, 999], [0, 8, 15, 20, 25])
        b_rev = get_b_direct(d["Tržby y/y"], [5, 12, 20, 35, 999], [0, 8, 15, 22, 28])
        b_deb = get_b_direct(d["Dluh D/E"], [50, 100, 150, 200, 999], [15, 10, 0, -10, -25])
    else: # Vlastní
        w_v, w_p, w_g, w_r = w_val, w_prof, w_growth, w_risk
        # (Zde by se použily hodnoty z manuálních inputů - pro stručnost zkráceno)
        b_pe = get_b(d["P/E"], p_pe); b_nm = get_b(d["Č-Marže"], p_nm)
        b_rev = get_b(d["Tržby y/y"], p_rev); b_deb = get_b(d["Dluh D/E"], p_deb)

    pts = {"P/E": b_pe * w_v, "Č-Marže": b_nm * w_p, "Tržby y/y": b_rev * w_g, "Dluh D/E": b_deb * w_r}
    d["Score"] = sum(pts.values())
    m_rows.append(d)
    if show_audit:
        a_row = {k: pts.get(k, 0) for k in pts}; a_row.update({"Ticker": "└─ body", "Score": d["Score"], "Type": "Pts"})
        m_rows.append(a_row)

# --- ZOBRAZENÍ TABULEK ---
st.subheader(f"📊 {strategie} Matrix ({filtr_kat})")
df_m = pd.DataFrame(m_rows)
st.dataframe(df_m.style.apply(lambda row: ['background-color: #f8f9fa; color: #adb5bd' if row["Type"]=="Pts" else '' for _ in row], axis=1).background_gradient(subset=["Score"], cmap="RdYlGn"), use_container_width=True, hide_index=True)
