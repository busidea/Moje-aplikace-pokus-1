import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V57", layout="wide")

# --- NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip()
        # Převod sloupce Earnings Day na formát data
        if 'Earnings Day' in df.columns:
            df['Earnings Day'] = pd.to_datetime(df['Earnings Day'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

df_seznam = nacti_seznam(ODKAZ_NA_TABULKU)

# --- SIDEBAR ---
st.sidebar.header("🔍 Filtry a Zobrazení")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"])

st.sidebar.markdown("---")
st.sidebar.header("⚖️ Globální Váhy")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=True)

# ... (všechny definice p_pe až p_pot zůstávají stejné jako v V56)
def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
# ... (v reálném kódu by zde byly všechny ostatní ukazatele)
p_deb = vytvor_p("Dluh D/E", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_all(df_list, kat_filtr):
    if df_list.empty: return pd.DataFrame(), pd.DataFrame()
    if kat_filtr != "Vše":
        df_list = df_list[df_list['Kategorie'] == kat_filtr]
    
    m_res, c_res = [], []
    today = date.today()
    pb = st.progress(0)
    
    for idx, row in enumerate(df_list.itertuples()):
        t = str(row.Ticker).strip()
        try:
            tick = yf.Ticker(t)
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
                "Hrubá marže": g("grossMargins", 100), "Čistá marže": g("profitMargins", 100),
                "ROE": g("returnOnEquity", 100), "Růst zisku (y/y)": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100),
                "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
                "Type": "Val"
            }
            
            # Bodování (zjednodušený příklad)
            score = (get_b(d["P/E"], p_pe) * w_val) + (get_b(d["Dluh D/E"], p_deb) * w_risk)
            d["Score"] = score
            m_res.append(d)
            
            if show_audit:
                m_res.append({"Ticker": "└─ body", "Score": score, "Type": "Pts"})

            # --- KALENDÁŘ LOGIKA (MANUÁLNÍ + NEWS) ---
            dni_do = 999
            earn_text = "Nezadáno"
            
            # 1. Priorita: Vaše data z Google Sheets
            if hasattr(row, 'Earnings_Day') and pd.notnull(row.Earnings_Day):
                target_date = row.Earnings_Day.date()
                dni_do = (target_date - today).days
                if dni_do < 0:
                    earn_text = f"Proběhlo ({target_date.strftime('%d.%m.')})"
                    dni_do = 999 # Aby nám to nesvítilo jako blízké
                else:
                    earn_text = target_date.strftime('%d.%m.%Y')
            
            # 2. Skenování News (jako záloha/bonus)
            news_warn = ""
            for n in tick.news[:5]:
                if any(kw in n['title'].lower() for kw in ["earnings", "results", "report"]):
                    news_warn = "🚨 Zmínka v News"
                    break
            
            ex_d = inf.get('exDividendDate')
            ex_date = datetime.fromtimestamp(ex_d).date() if ex_d else None
            
            c_res.append({
                "Ticker": t,
                "Earnings Day": earn_text,
                "Dní do": dni_do if dni_do != 999 else "-",
                "Zprávy/SEC": news_warn or "Klid",
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD",
                "Ex-Date": ex_date or "Není",
                "Highlight": 1 if 0 <= dni_do <= 14 or news_warn != "" else 0
            })
        except: continue
        pb.progress((idx+1)/len(df_list))
    
    return pd.DataFrame(m_res), pd.DataFrame(c_res)

df_m, df_c = fetch_all(df_seznam, filtr_kat)

# --- ZOBRAZENÍ MATRIXU ---
if not df_m.empty:
    st.subheader(f"📊 Matrix Tržních Hodnot ({filtr_kat})")
    cols = ["Ticker", "Cena", "Změna %", "P/E", "Hrubá marže", "Čistá marže", "ROE", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Potenciál", "Score"]
    
    def style_matrix(row):
        stls = [''] * len(row)
        if row.get("Type") == "Pts":
            return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        
        # Aktivnější barvy odchylek
        if row["P/E"] > 30: stls[cols.index("P/E")] = 'background-color: #ffe5e5; color: #cc0000'
        if row["P/E"] < 12: stls[cols.index("P/E")] = 'background-color: #e5f9e5; color: #008000'
        if row["Dluh D/E"] > 120: stls[cols.index("Dluh D/E")] = 'background-color: #fff0f0; color: #ff4b4b; font-weight: bold'
        if row["Potenciál"] > 20: stls[cols.index("Potenciál")] = 'background-color: #28a745; color: white; font-weight: bold'
        return stls

    st.dataframe(
        df_m.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn")
        .format({c: "{:.1f} %" for c in ["Změna %", "Hrubá marže", "Čistá marže", "ROE", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Potenciál"]}, precision=1),
        use_container_width=True, hide_index=True, column_order=cols
    )

# --- ZOBRAZENÍ KALENDÁŘE ---
if not df_c.empty:
    st.subheader("📅 Kalendář událostí (Vaše termíny + News)")
    
    def style_cal(row):
        # Jasné varování, pokud se blíží výsledky (do 14 dní)
        if row["Highlight"] == 1:
            return ['background-color: #ffc107; color: black; font-weight: bold'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df_c.drop(columns=["Highlight"]).style.apply(style_cal, axis=1),
        use_container_width=True, hide_index=True
    )
