import streamlit as st
import pandas as pd
import yfinance as yf
import time

st.set_page_config(page_title="Investiční Matrix V33", layout="wide")

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

st.title("🏛️ Investiční Matrix V33 (Plná verze)")

# --- SIDEBAR NASTAVENÍ BODŮ ---
st.sidebar.header("🔍 Filtry a Body")
zobrazit_kat = st.sidebar.radio("Skupina:", ["Vše", "Portfolio", "Sledované"])

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# Definice bodovacích škál (15 kategorií pro výpočet Score)
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb = vytvor_p("P/B", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_gm = vytvor_p("Hrubá marže %", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_nm = vytvor_p("Čistá marže %", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_roe = vytvor_p("ROE %", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_rev = vytvor_p("Růst tržeb %", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps = vytvor_p("Růst zisku %", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb = vytvor_p("Dluh D/E %", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_div = vytvor_p("Div. výnos %", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pay = vytvor_p("Výpl. poměr %", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál %", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

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
                if val is None or val == "": return 0
                return float(val) * mult

            # Sestavení dat
            d = {
                "Ticker": t,
                "P/E": g("trailingPE") if g("trailingPE") != 0 else g("forwardPE"),
                "P/S": g("priceToSalesTrailing12Months"),
                "P/B": g("priceToBook"),
                "P/FCF": g("marketCap") / g("freeCashflow") if g("freeCashflow") != 0 else 0,
                "Hrubá marže": g("grossMargins", 100),
                "Čistá marže": g("profitMargins", 100),
                "ROE": g("returnOnEquity", 100),
                "Růst tržeb": g("revenueGrowth", 100),
                "Růst zisku": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"),
                "Div. výnos": g("dividendYield", 100) if g("dividendYield") < 1 else g("dividendYield"),
                "Výpl. poměr": g("payoutRatio", 100),
                "Cena": g("currentPrice"),
                "Potenciál": ((g("targetMeanPrice") / g("currentPrice", 1)) - 1) * 100 if g("targetMeanPrice") > 0 else 0
            }
            
            # Výpočet Score
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/B"], p_pb) +
                          get_b(d["P/FCF"], p_pfcf) + get_b(d["Hrubá marže"], p_gm) +
                          get_b(d["Čistá marže"], p_nm) + get_b(d["ROE"], p_roe) +
                          get_b(d["Růst tržeb"], p_rev) + get_b(d["Růst zisku"], p_eps) +
                          get_b(d["Dluh D/E"], p_deb) + get_b(d["Div. výnos"], p_div) +
                          get_b(d["Výpl. poměr"], p_pay) + get_b(d["Potenciál"], p_pot))
            res.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

# --- STYLING A ZOBRAZENÍ ---
if not df.empty:
    # 1. Pořadí sloupců (všech 15 požadovaných)
    cols = ["Ticker", "Score", "P/E", "P/S", "P/B", "P/FCF", "Hrubá marže", "Čistá marže", "ROE", "Růst tržeb", "Růst zisku", "Dluh D/E", "Div. výnos", "Výpl. poměr", "Potenciál"]
    df = df.reindex(columns=cols).fillna(0).sort_values("Score", ascending=False)

    # 2. Semafor (červená barva pro extrémy)
    def semafor(s):
        styles = ['' for _ in s]
        if s.name == "P/E": styles = ['background-color: #f8d7da' if v > 35 else '' for v in s]
        elif s.name == "P/FCF": styles = ['background-color: #f8d7da' if v > 60 else '' for v in s]
        elif s.name == "Dluh D/E": styles = ['background-color: #f8d7da' if v > 150 else '' for v in s]
        elif s.name == "Výpl. poměr": styles = ['background-color: #f8d7da' if v > 100 else '' for v in s]
        return styles

    # 3. Formátování čísel a procent
    pct_cols = ["Hrubá marže", "Čistá marže", "ROE", "Růst tržeb", "Růst zisku", "Dluh D/E", "Div. výnos", "Výpl. poměr", "Potenciál"]
    fmt = {c: "{:.1f} %" for c in pct_cols}
    fmt.update({c: "{:.1f}" for c in ["P/E", "P/S", "P/B", "P/FCF"]})
    fmt["Score"] = "{:.0f}"

    st.dataframe(
        df.style.apply(semafor, axis=0)
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(fmt),
        use_container_width=True
    )
else:
    st.error("Nepodařilo se načíst data.")
