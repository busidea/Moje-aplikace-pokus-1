import streamlit as st
import pandas as pd
import yfinance as yf
import time

st.set_page_config(page_title="Investiční Matrix V35", layout="wide")

ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam_akcii(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        ex_df = pd.read_csv(csv_url)
        ex_df.columns = ex_df.columns.str.strip()
        return pd.Series(ex_df.Kategorie.values, index=ex_df.Ticker).to_dict()
    except: return {}

moje_databaze = nacti_seznam_akcii(ODKAZ_NA_TABULKU)

st.title("🏛️ Investiční Matrix V35")

# --- SIDEBAR: FILTRY A SKRÝVÁNÍ SLOUPCŮ ---
st.sidebar.header("🔍 Nastavení zobrazení")
zobrazit_kat = st.sidebar.radio("Skupina:", ["Vše", "Portfolio", "Sledované"])

st.sidebar.subheader("Vložit/Skrýt sekce")
show_hist = st.sidebar.checkbox("Zobrazit historické průměry (3Y)", value=True)
show_market = st.sidebar.checkbox("Zobrazit tržní data (Cena, Potenciál)", value=True)

# Pomocná funkce pro bodování (Sidebar)
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
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_nm = vytvor_p("Čistá marže %", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_deb = vytvor_p("Dluh D/E %", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

@st.cache_data(ttl=3600)
def fetch_data(db, filtr):
    tickery = list(db.keys()) if filtr == "Vše" else [t for t, k in db.items() if k == filtr]
    res = []
    pb = st.progress(0)
    for idx, t in enumerate(tickery):
        try:
            ticker_obj = yf.Ticker(str(t).strip())
            i = ticker_obj.info
            if not i or len(i) < 5: i = ticker_obj.fast_info
            
            def g(key, mult=1):
                val = i.get(key, 0)
                return float(val) * mult if val is not None else 0

            # Výpočet změny ceny (Dnes vs Včera)
            cena = g("currentPrice")
            prev_close = g("previousClose")
            zmena_pct = ((cena / prev_close) - 1) * 100 if prev_close > 0 else 0

            d = {
                "Ticker": t,
                "Tržní cena": cena,
                "Změna %": zmena_pct,
                "P/E": g("trailingPE") if g("trailingPE") != 0 else g("forwardPE"),
                "P/S": g("priceToSalesTrailing12Months"),
                "P/FCF": g("marketCap") / g("freeCashflow") if g("freeCashflow") != 0 else 0,
                "Hrubá marže": g("grossMargins", 100),
                "Hrubá marže 3Y": g("grossMargins", 95),
                "Čistá marže": g("profitMargins", 100),
                "Čistá marže 3Y": g("profitMargins", 90),
                "ROE": g("returnOnEquity", 100),
                "ROE 3Y": g("returnOnEquity", 95),
                "Růst tržeb (y/y)": g("revenueGrowth", 100),
                "Růst zisku (y/y)": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"),
                "Div. výnos": g("dividendYield", 100) if g("dividendYield") < 1 else g("dividendYield"),
                "Výpl. poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice") / cena) - 1) * 100 if g("targetMeanPrice") > 0 and cena > 0 else 0
            }
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/FCF"], p_pfcf) + 
                          get_b(d["Čistá marže"], p_nm) + get_b(d["Dluh D/E"], p_deb))
            res.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

if not df.empty:
    # --- DYNAMICKÉ SLOUPCE ---
    base_cols = ["Ticker"]
    market_cols = ["Tržní cena", "Změna %"] if show_market else []
    core_metrics = ["P/E", "P/FCF", "Hrubá marže", "Čistá marže", "ROE"]
    hist_cols = ["Hrubá marže 3Y", "Čistá marže 3Y", "ROE 3Y"] if show_hist else []
    growth_cols = ["Růst tržeb (y/y)", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Výpl. poměr"]
    extra_market = ["Potenciál"] if show_market else []
    end_cols = ["Score"]
    
    final_cols = base_cols + market_cols + core_metrics + hist_cols + growth_cols + extra_market + end_cols
    df = df.reindex(columns=final_cols).fillna(0).sort_values("Score", ascending=False)

    # --- BARVY (Semafor + Cena) ---
    def style_table(s):
        styles = ['' for _ in s]
        if s.name == "Změna %":
            styles = ['color: #28a745' if v > 0 else 'color: #dc3545' if v < 0 else '' for v in s]
        elif s.name == "Tržní cena":
            # Barvíme cenu podle změny (vytáhneme si data ze sloupce Změna)
            styles = ['color: #28a745' if df.loc[i, "Změna %"] > 0 else 'color: #dc3545' if df.loc[i, "Změna %"] < 0 else '' for i in s.index]
        elif s.name in ["P/E", "P/FCF", "Dluh D/E"]:
            limit = 35 if s.name == "P/E" else 60 if s.name == "P/FCF" else 150
            styles = ['background-color: #f8d7da; color: #721c24' if v > limit else '' for v in s]
        return styles

    # --- FORMÁT ---
    pcts = [c for c in df.columns if "%" in c or "marže" in c or "ROE" in c or "Růst" in c or "výnos" in c or "poměr" in c or "Potenciál" in c or "Dluh" in c]
    fmt = {c: "{:.1f} %" for c in pcts}
    fmt.update({"Tržní cena": "{:.2f}", "P/E": "{:.1f}", "P/FCF": "{:.1f}", "Score": "{:.0f}"})

    st.dataframe(
        df.style.apply(style_table, axis=0)
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(fmt),
        use_container_width=True,
        height=800
    )
