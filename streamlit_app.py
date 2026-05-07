import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V55", layout="wide")

# --- NAČTENÍ DAT ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

df_seznam = nacti_seznam(ODKAZ_NA_TABULKU)

# --- SIDEBAR ---
st.sidebar.header("🔍 Nastavení a Filtry")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"])

st.sidebar.markdown("---")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5)

show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=True)

# Pomocná funkce pro body
def get_b(val, pasma_h, pasma_b):
    for i, h in enumerate(pasma_h):
        if val <= h: return pasma_b[i]
    return pasma_b[-1]

# --- HLAVNÍ LOGIKA VÝPOČTU ---
@st.cache_data(ttl=3600)
def stahni_data(df_list, kat_filtr):
    if df_list.empty: return pd.DataFrame(), pd.DataFrame()
    
    # Filtrace tickerů
    if kat_filtr != "Vše":
        df_list = df_list[df_list['Kategorie'] == kat_filtr]
    
    m_data, c_data = [], []
    today = date.today()
    pb = st.progress(0)
    
    for idx, row in enumerate(df_list.itertuples()):
        t = str(row.Ticker).strip()
        try:
            tick = yf.Ticker(t)
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            # 1. Tržní a fundamentální data
            d = {
                "Ticker": t,
                "Cena": g("currentPrice"),
                "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"),
                "P/S": g("priceToSalesTrailing12Months"),
                "P/B": g("priceToBook"),
                "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                "Hrubá marže %": g("grossMargins", 100),
                "Čistá marže %": g("profitMargins", 100),
                "ROE %": g("returnOnEquity", 100),
                "Růst tržeb y/y %": g("revenueGrowth", 100),
                "Růst zisku y/y %": g("earningsGrowth", 100),
                "Dluh D/E %": g("debtToEquity"),
                "Div. výnos %": g("dividendYield", 100),
                "Výplatní poměr %": g("payoutRatio", 100),
                "Potenciál %": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
                "Type": "Val"
            }
            
            # 2. Bodování (příklad fixních pásem pro stabilitu)
            s = get_b(d["P/E"], [15,25,35,50], [15,10,5,0])*w_val
            s += get_b(d["Dluh D/E %"], [50,100,150,200], [15,10,5,0])*w_risk
            s += get_b(d["ROE %"], [5,15,25,40], [0,5,10,20])*w_prof
            
            d["Score"] = s
            m_data.append(d)
            
            if show_audit:
                m_data.append({"Ticker": "└─ body", "Score": s, "Type": "Pts"})

            # 3. News / Kalendář
            news_warn = ""
            for n in tick.news[:5]:
                if any(kw in n['title'].lower() for kw in ["earnings", "results", "report", "dividend"]):
                    news_warn = f"🚨 {n['title'][:60]}..."
                    break
            
            ex_d = inf.get('exDividendDate')
            ex_date = datetime.fromtimestamp(ex_d).date() if ex_d else None
            
            c_data.append({
                "Ticker": t,
                "Zprávy / Výsledky": news_warn or "Klidné období",
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD",
                "Ex-Date": ex_date or "Není",
                "Status": 0 if news_warn else 1
            })
        except: continue
        pb.progress((idx+1)/len(df_list))
    
    return pd.DataFrame(m_data), pd.DataFrame(c_data)

df_m, df_c = stahni_data(df_seznam, filtr_kat)

# --- ZOBRAZENÍ ---
st.header(f"📊 Matrix: {filtr_kat}")

if not df_m.empty:
    # Definice barev pro buňky
    def styler(row):
        stls = [''] * len(row)
        if row.Type == "Pts":
            return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        
        # Barvy pro cenu a změnu
        idx_cena = df_m.columns.get_loc("Cena")
        idx_zmena = df_m.columns.get_loc("Změna %")
        c = 'color: #28a745; font-weight: bold' if row["Změna %"] > 0 else 'color: #dc3545; font-weight: bold'
        stls[idx_cena] = c
        stls[idx_zmena] = c
        
        # Agresivní varování (podbarvení buněk)
        if row["P/E"] > 35: stls[df_m.columns.get_loc("P/E")] = 'background-color: #ffcccc; color: #990000'
        if row["Dluh D/E %"] > 130: stls[df_m.columns.get_loc("Dluh D/E %")] = 'background-color: #ffe5e5; color: #cc0000'
        if row["Potenciál %"] > 20: stls[df_m.columns.get_loc("Potenciál %")] = 'background-color: #d4edda; color: #155724; font-weight: bold'
        
        return stls

    st.dataframe(
        df_m.style.apply(styler, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn").format(precision=1),
        use_container_width=True, hide_index=True
    )

if not df_c.empty:
    st.header("📅 Kalendář a Čerstvé zprávy")
    st.dataframe(
        df_c.style.apply(lambda r: ['background-color: #fff3cd; font-weight: bold' if "🚨" in r["Zprávy / Výsledky"] else '' for _ in r], axis=1),
        use_container_width=True, hide_index=True
    )
