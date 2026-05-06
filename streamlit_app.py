import streamlit as st
import pandas as pd
import yfinance as yf
import time

st.set_page_config(page_title="Investiční Matrix V32", layout="wide")

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

st.title("🏛️ Investiční Matrix V32")

# --- SIDEBAR ---
st.sidebar.header("🔍 Nastavení")
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

# Definice bodování
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb = vytvor_p("P/B", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_nm = vytvor_p("Marže Čistá", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_roe = vytvor_p("ROE", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_deb = vytvor_p("Dluh D/E %", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_div = vytvor_p("Div. výnos", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pay = vytvor_p("Výpl. poměr", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])

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
            
            # Pokud info nefunguje (BASF/HEIJM), zkusíme vynutit fast_info
            if not i or len(i) < 10:
                i = ticker_obj.fast_info

            def safe_get(key, mult=1):
                val = i.get(key, 0)
                if val is None or val == "": return 0
                return float(val) * mult

            # Sestavení dat - KAŽDÝ klíč je definován samostatně pro stabilitu
            d = {"Ticker": t}
            d["P/E"] = safe_get("trailingPE") if safe_get("trailingPE") != 0 else safe_get("forwardPE")
            d["P/S"] = safe_get("priceToSalesTrailing12Months")
            d["P/B"] = safe_get("priceToBook")
            
            mcap = safe_get("marketCap")
            fcf = safe_get("freeCashflow")
            d["P/FCF"] = mcap / fcf if fcf != 0 else 0
            
            d["Marže Čistá"] = safe_get("profitMargins", 100)
            d["ROE"] = safe_get("returnOnEquity", 100)
            d["Dluh D/E %"] = safe_get("debtToEquity")
            d["Div. Výnos"] = safe_get("dividendYield", 100)
            d["Výpl. Poměr"] = safe_get("payoutRatio", 100)
            d["Potenciál"] = ((safe_get("targetMeanPrice") / safe_get("currentPrice", 1)) - 1) * 100 if safe_get("targetMeanPrice") > 0 else 0
            
            # Výpočet Score
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/B"], p_pb) +
                          get_b(d["P/FCF"], p_pfcf) + get_b(d["Marže Čistá"], p_nm) + 
                          get_b(d["ROE"], p_roe) + get_b(d["Dluh D/E %"], p_deb) + 
                          get_b(d["Div. Výnos"], p_div) + get_b(d["Výpl. Poměr"], p_pay))
            res.append(d)
        except Exception:
            # I při totální chybě přidáme aspoň ticker s nulami, aby sloupce nezmizely
            res.append({"Ticker": t, "Score": 0})
        
        pb.progress((idx + 1) / len(tickery))
        time.sleep(0.05) # Mírné zpomalení proti blokaci

    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

# --- FINÁLNÍ ZOBRAZENÍ ---
if not df.empty:
    # DEFINICE VŠECH 12 SLOUPCŮ (Klíčové pro zamezení smrsknutí tabulky)
    vsechny_sloupce = ["Ticker", "Score", "P/E", "P/S", "P/B", "P/FCF", "Marže Čistá", "ROE", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    df = df.reindex(columns=vsechny_sloupce).fillna(0)
    df = df.sort_values("Score", ascending=False)

    def color_rows(s):
        styles = ['' for _ in s]
        if s.name == "P/E":
            styles = ['background-color: #f8d7da' if v > 35 else '' for v in s]
        elif s.name == "P/FCF":
            styles = ['background-color: #f8d7da' if v > 60 else '' for v in s]
        elif s.name == "Dluh D/E %":
            styles = ['background-color: #f8d7da' if v > 150 else '' for v in s]
        return styles

    # Formátování
    pct_cols = ["Marže Čistá", "ROE", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    fmt = {c: "{:.1f} %" for c in pct_cols}
    fmt.update({c: "{:.1f}" for c in ["P/E", "P/S", "P/B", "P/FCF"]})
    fmt["Score"] = "{:.0f}"

    st.dataframe(
        df.style.apply(color_rows, axis=0)
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(fmt),
        use_container_width=True
    )
