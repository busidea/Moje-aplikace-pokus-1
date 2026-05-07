import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V54", layout="wide")

ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam_akcii(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        ex_df = pd.read_csv(csv_url)
        ex_df.columns = ex_df.columns.str.strip()
        return ex_df
    except: return pd.DataFrame()

df_seznam = nacti_seznam_akcii(ODKAZ_NA_TABULKU)

st.title("🏛️ Investiční Matrix V54")

# --- SIDEBAR ---
st.sidebar.header("🔍 Filtry")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"])

st.sidebar.header("⚖️ Váhy")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

show_audit = st.sidebar.checkbox("Zobrazit bodové řádky (Audit)", value=True)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# Definice pásem (výběr nejdůležitějších pro přehlednost kódu, v app budou všechna)
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_gm = vytvor_p("Hrubá marže", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_rev = vytvor_p("Růst tržeb y/y", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps = vytvor_p("Růst zisku y/y", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb = vytvor_p("Dluh D/E", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])
# ... (ostatní p_xx definice zůstávají stejné)

if not df_seznam.empty:
    df_f = df_seznam if filtr_kat == "Vše" else df_seznam[df_seznam['Kategorie'] == filtr_kat]
    moje_databaze = pd.Series(df_f.Kategorie.values, index=df_f.Ticker).to_dict()
else: moje_databaze = {}

@st.cache_data(ttl=3600)
def fetch_all_data(db, s_audit):
    m_res, c_res = [], []
    today = date.today()
    pb = st.progress(0)
    
    for idx, t in enumerate(db.keys()):
        try:
            tick = yf.Ticker(str(t).strip())
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"), "Hrubá marže": g("grossMargins", 100),
                "Čistá marže": g("profitMargins", 100), "ROE": g("returnOnEquity", 100),
                "Růst tržeb (y/y)": g("revenueGrowth", 100), "Růst zisku (y/y)": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100),
                "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
                "RowType": "Val"
            }
            
            # Bodování (zjednodušený příklad, v app bude plný mapping)
            score = get_b(d["P/E"], p_pe)*w_val + get_b(d["Dluh D/E"], p_deb)*w_risk
            d["Score"] = score
            d["SortKey"] = score
            m_res.append(d)

            # --- AGRESIVNÍ SKENOVÁNÍ UDÁLOSTÍ ---
            news_warn = ""
            recent_news = tick.news
            for n in recent_news[:10]:
                title = n['title'].lower()
                if any(kw in title for kw in ["earnings", "q1", "q2", "q3", "q4", "results", "report"]):
                    news_warn = f"🚨 {n['title'][:50]}..."
                    break
            
            ex_date = inf.get('exDividendDate')
            ex_date_fmt = datetime.fromtimestamp(ex_date).date() if ex_date else None
            
            c_res.append({
                "Ticker": t, "Zprávy/SEC": news_warn or "Beze zpráv",
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD",
                "Ex-Date": ex_date_fmt or "Není",
                "Sort": 0 if news_warn else 1
            })
        except: continue
        pb.progress((idx+1)/len(db))
    return pd.DataFrame(m_res), pd.DataFrame(c_res)

df_m, df_c = fetch_all_data(moje_databaze, show_audit)

# --- VYKRESLENÍ MATRIXU ---
if not df_m.empty:
    cols = ["Ticker", "Cena", "Změna %", "P/E", "Hrubá marže", "Čistá marže", "ROE", "Růst tržeb (y/y)", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Potenciál", "Score"]
    pct_cols = ["Změna %", "Hrubá marže", "Čistá marže", "ROE", "Růst tržeb (y/y)", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Potenciál"]

    def highlight_vals(row):
        stls = [''] * len(row)
        if row.get("RowType") == "Val":
            # Barvy pohybu ceny
            c = 'color: #28a745' if row["Změna %"] > 0 else 'color: #dc3545'
            stls[cols.index("Cena")], stls[cols.index("Změna %")] = c, c
            # Agresivní varování
            if row["P/E"] > 40: stls[cols.index("P/E")] = 'background-color: #ff4b4b; color: white'
            if row["Dluh D/E"] > 150: stls[cols.index("Dluh D/E")] = 'background-color: #ff9b9b'
            if row["Potenciál"] > 25: stls[cols.index("Potenciál")] = 'background-color: #d4edda; color: #155724; font-weight: bold'
        return stls

    st.dataframe(
        df_m.sort_values("SortKey", ascending=False).style.apply(highlight_vals, axis=1)
        .format({c: "{:.1f} %" for c in pct_cols}, precision=1),
        use_container_width=True, hide_index=True, column_order=cols
    )

# --- VYKRESLENÍ KALENDÁŘE ---
if not df_c.empty:
    st.markdown("### 📅 Monitoring tržních zpráv (News & Results)")
    st.dataframe(
        df_c.sort_values("Sort").style.apply(lambda r: ['background-color: #fff3cd; font-weight: bold' if "🚨" in r["Zprávy/SEC"] else '' for _ in r], axis=1),
        use_container_width=True, hide_index=True
    )
