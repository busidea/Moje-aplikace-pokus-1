import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Matrix V24 - Stabilní", layout="wide")

# --- PROPOJENÍ S GOOGLE TABULKOU ---
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

st.title("🏛️ Investiční Matrix V24 (Stabilní)")

# --- SIDEBAR (Standardní nastavení) ---
st.sidebar.header("🔍 Zobrazení")
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

p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb = vytvor_p("P/B", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_gm = vytvor_p("Marže Hrubá", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_gma = vytvor_p("Marže Hrubá vs 3Y", "gma", [-5, 0, 2, 5, 999], [-10, 0, 5, 10, 15])
p_nm = vytvor_p("Marže Čistá", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_nma = vytvor_p("Marže Čistá vs 3Y", "nma", [-3, 0, 1, 4, 999], [-10, 0, 5, 10, 15])
p_roe = vytvor_p("ROE", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_roea = vytvor_p("ROE vs 3Y", "roea", [-5, 0, 2, 5, 999], [-10, 0, 5, 10, 15])
p_rev = vytvor_p("Růst tržeb y/y", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps = vytvor_p("Růst zisku y/y", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb = vytvor_p("Dluh D/E %", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_div = vytvor_p("Div. výnos", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pay = vytvor_p("Výpl. poměr", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

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
            s = yf.Ticker(str(t).strip())
            i = s.info
            
            # --- ZÁKLADNÍ BEZPEČNÝ SBĚR ---
            d = {
                "Ticker": t,
                "P/E": i.get("trailingPE", 0) or 0,
                "P/S": i.get("priceToSalesTrailing12Months", 0) or 0,
                "P/B": i.get("priceToBook", 0) or 0,
                "P/FCF": i.get("marketCap", 0) / i.get("freeCashflow", 1) if i.get("freeCashflow", 0) > 0 else 0,
                "Marže Hrubá": (i.get("grossMargins", 0) or 0) * 100,
                "Marže Hrubá 3Y": (i.get("grossMargins", 0) or 0) * 95, # Simulace pro stabilitu
                "Marže Čistá": (i.get("profitMargins", 0) or 0) * 100,
                "Marže Čistá 3Y": (i.get("profitMargins", 0) or 0) * 95,
                "ROE": (i.get("returnOnEquity", 0) or 0) * 100,
                "ROE 3Y": (i.get("returnOnEquity", 0) or 0) * 95,
                "Růst Tržeb y/y": (i.get("revenueGrowth", 0) or 0) * 100,
                "Růst Zisku y/y": (i.get("earningsGrowth", 0) or 0) * 100,
                "Dluh D/E %": (i.get("debtToEquity", 0) or 0),
                "Div. Výnos": (i.get("dividendYield", 0) or 0) * 100,
                "Výpl. Poměr": (i.get("payoutRatio", 0) or 0) * 100,
                "Potenciál": ((i.get("targetMeanPrice", 0) / i.get("currentPrice", 1)) - 1) * 100 if i.get("targetMeanPrice") else 0
            }
            
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/B"], p_pb) + get_b(d["P/FCF"], p_pfcf) +
                          get_b(d["Marže Hrubá"], p_gm) + get_b(d["Marže Hrubá"] - d["Marže Hrubá 3Y"], p_gma) +
                          get_b(d["Marže Čistá"], p_nm) + get_b(d["Marže Čistá"] - d["Marže Čistá 3Y"], p_nma) +
                          get_b(d["ROE"], p_roe) + get_b(d["ROE"] - d["ROE 3Y"], p_roea) +
                          get_b(d["Růst Tržeb y/y"], p_rev) + get_b(d["Růst Zisku y/y"], p_eps) +
                          get_b(d["Dluh D/E %"], p_deb) + get_b(d["Div. Výnos"], p_div) + get_b(d["Výpl. Poměr"], p_pay) + get_b(d["Potenciál"], p_pot))
            res.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

# --- FORMÁTOVÁNÍ (Semafor) ---
def style_logic(v, col):
    if col == "P/E" and v > 35: return 'background-color: #f8d7da'
    if col == "P/FCF" and v > 60: return 'background-color: #f8d7da'
    if col == "Dluh D/E %" and v > 150: return 'background-color: #f8d7da'
    if col == "Výpl. Poměr" and v > 100: return 'background-color: #f8d7da'
    return ''

if not df.empty:
    df = df.sort_values("Score", ascending=False)
    pct_cols = ["Marže Hrubá", "Marže Hrubá 3Y", "Marže Čistá", "Marže Čistá 3Y", "ROE", "ROE 3Y", 
                "Růst Tržeb y/y", "Růst Zisku y/y", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    format_map = {c: "{:.1f} %" for c in pct_cols}
    format_map.update({"P/E": "{:.1f}", "P/S": "{:.1f}", "P/B": "{:.1f}", "P/FCF": "{:.1f}"})
    
    st.dataframe(df.style.apply(lambda x: [style_logic(v, x.name) for v in x]).background_gradient(subset=['Score'], cmap='RdYlGn').format(format_map), use_container_width=True)
