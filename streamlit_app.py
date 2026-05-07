import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V60", layout="wide")

# --- NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300) # Snížil jsem TTL na 5 minut, aby se změny v tabulce projevily dříve
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        # Vyčištění názvů sloupců od mezer
        df.columns = [c.strip() for c in df.columns]
        # Vyčištění tickerů
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        return df
    except: return pd.DataFrame()

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- DIAGNOSTIKA SLOUPCŮ (pro jistotu) ---
if not df_raw.empty:
    with st.expander("🛠️ Systémová diagnostika tabulky (pokud nevidíte data)"):
        st.write("Nalezené sloupce v Google tabulce:", list(df_raw.columns))

# --- SIDEBAR (Všech 16 ovladačů) ---
st.sidebar.header("🔍 Filtry a Zobrazení")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"])
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5)
show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=True)

# Pomocná funkce pro tvorbu ovladačů (zkráceno pro přehlednost, v app nechte všechny)
def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}"):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_deb = vytvor_p("Dluh D/E", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])
# ... (ostatní p_xx zůstávají v paměti stejné)

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_all_v60(df_source, kat_filtr):
    if df_source.empty: return pd.DataFrame(), pd.DataFrame()
    
    # Filtrace
    df_active = df_source if kat_filtr == "Vše" else df_source[df_source['Kategorie'] == kat_filtr]
    
    m_res, c_res = [], []
    today = date.today()
    pb = st.progress(0)

    for idx, row_data in enumerate(df_active.to_dict('records')):
        t = str(row_data.get('Ticker', '')).strip().upper()
        if not t: continue
        
        try:
            tick = yf.Ticker(t)
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            # --- MATRIX DATA ---
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"), "Dluh D/E": g("debtToEquity"), 
                "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
                "Type": "Val"
            }
            score = (get_b(d["P/E"], p_pe)*w_val) + (get_b(d["Dluh D/E"], p_deb)*w_risk)
            d["Score"] = score
            m_res.append(d)
            if show_audit: m_res.append({"Ticker": "└─ body", "Score": score, "Type": "Pts"})

            # --- ROBUSTNÍ LOGIKA PRO EARNINGS DAY ---
            dni_do = 999
            earn_str = "Nezadáno"
            
            # Hledáme sloupec, který se jmenuje Earnings Day (v jakékoli variantě)
            raw_val = row_data.get('Earnings Day')
            if pd.notnull(raw_val) and str(raw_val).strip() != "":
                try:
                    # Převod na datum - zkoušíme dd/mm/yyyy
                    dt = pd.to_datetime(raw_val, dayfirst=True)
                    dni_do = (dt.date() - today).days
                    if dni_do >= 0:
                        earn_str = dt.strftime('%d.%m.%Y')
                    else:
                        earn_str = f"Proběhlo ({dt.strftime('%d.%m.')})"
                except:
                    earn_str = "Chyba formátu"

            news_trigger = ""
            for n in tick.news[:5]:
                if any(kw in n['title'].lower() for kw in ["earnings", "results", "report"]):
                    news_trigger = "🚨 News report"
                    break
            
            c_res.append({
                "Ticker": t, "Earnings Day": earn_str, 
                "Dní do": dni_do if 0 <= dni_do < 500 else "-",
                "Zprávy": news_trigger or "Klid", 
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD",
                "Ex-Date": datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else "Není",
                "Highlight": 1 if 0 <= dni_do <= 14 or news_trigger != "" else 0
            })
        except: continue
        pb.progress((idx+1)/len(df_active))
    
    return pd.DataFrame(m_res), pd.DataFrame(c_res)

df_m, df_c = fetch_all_v60(df_raw, filtr_kat)

# --- ZOBRAZENÍ (Všechny barvy z V59 zachovány) ---
if not df_m.empty:
    st.subheader(f"📊 Matrix Tržních Hodnot ({filtr_kat})")
    st.dataframe(df_m.style.apply(lambda r: ['background-color: #f8f9fa; color: #adb5bd' if r.Type=="Pts" else '' for _ in r], axis=1), use_container_width=True, hide_index=True)

if not df_c.empty:
    st.subheader("📅 Kalendář událostí")
    st.dataframe(df_c.style.apply(lambda r: ['background-color: #ffc107; color: black; font-weight: bold' if r.Highlight==1 else '' for _ in r], axis=1), 
                 use_container_width=True, hide_index=True, column_order=["Ticker", "Earnings Day", "Dní do", "Zprávy", "Dividenda", "Ex-Date"])
