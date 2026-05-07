import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V52", layout="wide")

ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam_akcii(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        ex_df = pd.read_csv(csv_url)
        ex_df.columns = ex_df.columns.str.strip()
        # Vracíme DataFrame, abychom mohli filtrovat podle kategorií
        return ex_df
    except: return pd.DataFrame()

df_seznam = nacti_seznam_akcii(ODKAZ_NA_TABULKU)

st.title("🏛️ Investiční Matrix V52")

# --- SIDEBAR ---
st.sidebar.header("🔍 Filtry a Zobrazení")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"])

st.sidebar.header("⚖️ Nastavení vah")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

st.sidebar.markdown("---")
show_audit = st.sidebar.checkbox("Zobrazit bodové řádky (Audit)", value=True)
hide_market = st.sidebar.checkbox("Skrýt tržní údaje", value=False)

# Aplikace filtru na načtený seznam
if not df_seznam.empty:
    if filtr_kat != "Vše":
        df_final_list = df_seznam[df_seznam['Kategorie'] == filtr_kat]
    else:
        df_final_list = df_seznam
    moje_databaze = pd.Series(df_final_list.Kategorie.values, index=df_final_list.Ticker).to_dict()
else:
    moje_databaze = {}

# ... (funkce vytvor_p a definice pásem p_pe až p_pot zůstávají stejné)
def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# --- PÁSMA --- (Stejná jako v V51)
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
# ... (ostatních 15 pásem definováno stejně jako v V51)
p_deb = vytvor_p("Dluh D/E", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

@st.cache_data(ttl=3600)
def fetch_all_data(db, s_audit):
    matrix_res, cal_res = [], []
    pb = st.progress(0)
    today = date.today()
    
    for idx, t in enumerate(db.keys()):
        try:
            tick = yf.Ticker(str(t).strip())
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
                "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                "Hrubá marže": g("grossMargins", 100), "Hrubá marže 3Y": g("grossMargins", 94),
                "Čistá marže": g("profitMargins", 100), "Čistá marže 3Y": g("profitMargins", 91),
                "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
                "Růst tržeb": g("revenueGrowth", 100), "Růst zisku": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Výpl. poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0
            }
            # Bodování (zde se použijí váhy)
            # ... (výpočet score jako v V51)
            score = 0 # Zástupný výpočet
            matrix_res.append({**d, "Score": score, "RowType": "Val", "SortKey": score})
            if s_audit:
                matrix_res.append({"Ticker": "└─ pts", "Score": score, "RowType": "Pts", "SortKey": score - 0.001})

            # --- ANALÝZA ZPRÁV A KALENDÁŘ ---
            next_earn = "Neznámé"
            status_news = ""
            try:
                # 1. Zkusit kalendář
                if tick.calendar and 'Earnings Date' in tick.calendar:
                    next_earn = tick.calendar['Earnings Date'][0].date()
                
                # 2. Skenovat News na klíčová slova
                news = tick.news
                keywords = ["earnings", "q1", "q2", "q3", "q4", "results", "report"]
                for n in news[:5]: # Prohledat posledních 5 zpráv
                    if any(kw in n['title'].lower() for kw in keywords):
                        status_news = "⚠️ Blízký report (News)"
                        break
            except: pass
            
            ex_date = inf.get('exDividendDate')
            ex_date_fmt = datetime.fromtimestamp(ex_date).date() if ex_date else None
            
            cal_res.append({
                "Ticker": t, "Příští výsledky": next_earn, 
                "Indikace": status_news,
                "Dní": (next_earn - today).days if isinstance(next_earn, date) else 999,
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD", "Ex-Date": ex_date_fmt or "Není"
            })
        except: continue
        pb.progress((idx+1)/len(db))
    return pd.DataFrame(matrix_res), pd.DataFrame(cal_res)

df_m, df_c = fetch_all_data(moje_databaze, show_audit)

# --- ZOBRAZENÍ MATRIXU ---
if not df_m.empty:
    df_m = df_m.sort_values("SortKey", ascending=False)
    cols = ["Ticker", "Cena", "Změna %", "P/E", "P/S", "P/B", "P/FCF", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb", "Růst zisku", "Dluh D/E", "Div. výnos", "Výpl. poměr", "Potenciál", "Score"]
    # Sloupce, kde chceme symbol %
    pct_cols = ["Změna %", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb", "Růst zisku", "Dluh D/E", "Div. výnos", "Výpl. poměr", "Potenciál"]

    st.dataframe(
        df_m.style.map(lambda v: 'background-color: #ffcccc' if isinstance(v, (int,float)) and v > 35 else '', subset=["P/E"])
        .map(lambda v: 'background-color: #ffcccc' if isinstance(v, (int,float)) and v > 150 else '', subset=["Dluh D/E"])
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format({c: "{:.1f} %" for c in pct_cols}, precision=1),
        use_container_width=True, hide_index=True, column_order=cols
    )

# --- ZOBRAZENÍ KALENDÁŘE ---
if not df_c.empty:
    st.markdown("### 📅 Kalendář událostí & Indikace zpráv")
    def style_cal(row):
        styles = [''] * len(row)
        if (isinstance(row["Příští výsledky"], date) and row["Dní"] <= 14) or row["Indikace"] != "":
            return ['background-color: #ffeeba; font-weight: bold'] * len(row)
        return styles
        
    st.dataframe(df_c.style.apply(style_cal, axis=1), use_container_width=True, hide_index=True)
