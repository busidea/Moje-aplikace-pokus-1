import streamlit as st
import pandas as pd
import yfinance as yf
import time

st.set_page_config(page_title="Investiční Matrix V30", layout="wide")

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

st.title("🏛️ Investiční Matrix V30")

# --- SIDEBAR BODŮ ---
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

p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
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
            
            # Pokud info selže, zkusíme aspoň základní cenu pro výpočty
            hist = ticker_obj.history(period="1d")
            cena = hist['Close'].iloc[-1] if not hist.empty else i.get('currentPrice', 0)

            def g(key, mult=1):
                val = i.get(key)
                if val is None or val == "": return 0
                return float(val) * mult

            d = {
                "Ticker": t,
                "P/E": g("trailingPE") if g("trailingPE") != 0 else g("forwardPE"),
                "P/S": g("priceToSalesTrailing12Months"),
                "P/B": g("priceToBook"),
                "P/FCF": g("marketCap") / g("freeCashflow") if g("freeCashflow") != 0 else 0,
                "Marže Čistá": g("profitMargins", 100),
                "ROE": g("returnOnEquity", 100),
                "Dluh D/E %": g("debtToEquity"),
                "Div. Výnos": g("dividendYield", 100),
                "Výpl. Poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice") / cena) - 1) * 100 if g("targetMeanPrice") > 0 and cena > 0 else 0
            }

            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/FCF"], p_pfcf) +
                          get_b(d["Marže Čistá"], p_nm) + get_b(d["ROE"], p_roe) + 
                          get_b(d["Dluh D/E %"], p_deb) + get_b(d["Div. Výnos"], p_div) + get_b(d["Výpl. Poměr"], p_pay))
            res.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

# --- FORMÁTOVÁNÍ ---
if not df.empty:
    df = df.sort_values("Score", ascending=False)
    
    # Definice sloupců natvrdo (zajišťuje, že jich bude vždy 11)
    final_cols = ["Ticker", "Score", "P/E", "P/S", "P/B", "P/FCF", "Marže Čistá", "ROE", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    df = df.reindex(columns=final_cols).fillna(0)

    pct_cols = ["Marže Čistá", "ROE", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    fmt = {c: "{:.1f} %" for c in pct_cols}
    fmt.update({"P/E": "{:.1f}", "P/S": "{:.1f}", "P/B": "{:.1f}", "P/FCF": "{:.1f}", "Score": "{:.0f}"})

    st.dataframe(
        df.style.background_gradient(subset=['Score'], cmap='RdYlGn')
        .applymap(lambda v: 'background-color: #f8d7da' if isinstance(v, float) and v > 150 and "Dluh" in str(v) else '')
        .format(fmt),
        use_container_width=True
    )
