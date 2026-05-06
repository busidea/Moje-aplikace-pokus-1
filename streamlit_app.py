import streamlit as st
import pandas as pd
import yfinance as yf
import time

st.set_page_config(page_title="Investiční Matrix V28", layout="wide")

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

st.title("🏛️ Investiční Matrix V28 - Hard-Fix")

st.sidebar.header("🔍 Zobrazení")
zobrazit_kat = st.sidebar.radio("Skupina:", ["Vše", "Portfolio", "Sledované"])

# Bodování (ponecháno pro výpočet Score)
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
            ticker_str = str(t).strip().upper()
            s = yf.Ticker(ticker_str)
            
            # AGRESIVNÍ STAŽENÍ INFO
            i = s.info
            if not i or len(i) < 5:
                # Pokud standardní info selže, zkusíme fast_info (mnohem stabilnější v cloudu)
                i = s.fast_info
            
            # Pomocná funkce pro bezpečný sběr (vždy vrátí číslo)
            def g(k, mult=1):
                try:
                    val = i.get(k, 0)
                    if val is None: return 0
                    return float(val) * mult
                except: return 0

            # Manuální výpočet P/E pokud chybí
            pe_val = g("trailingPE") or g("forwardPE")
            if pe_val == 0 and g("lastPrice") > 0 and g("epsTrailing12Months") > 0:
                pe_val = g("lastPrice") / g("epsTrailing12Months")

            d = {
                "Ticker": ticker_str,
                "P/E": pe_val,
                "P/S": g("priceToSalesTrailing12Months"),
                "P/FCF": g("marketCap") / g("freeCashflow") if g("freeCashflow") > 0 else 0,
                "Marže Čistá": g("profitMargins", 100),
                "ROE": g("returnOnEquity", 100),
                "Dluh D/E %": g("debtToEquity"),
                "Div. Výnos": g("dividendYield", 100) if g("dividendYield") < 1 else g("dividendYield"),
                "Výpl. Poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice") / g("currentPrice", 1)) - 1) * 100 if g("targetMeanPrice") > 0 else 0
            }
            
            # FIX: Pokud jsou marže None/0, zkusíme je vytáhnout z fast_info
            if d["Marže Čistá"] == 0 and "net_income" in i:
                d["Marže Čistá"] = (i["net_income"] / i["total_revenue"]) * 100 if i.get("total_revenue", 0) > 0 else 0

            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/FCF"], p_pfcf) +
                          get_b(d["Marže Čistá"], p_nm) + get_b(d["ROE"], p_roe) + 
                          get_b(d["Dluh D/E %"], p_deb) + get_b(d["Div. Výnos"], p_div) + get_b(d["Výpl. Poměr"], p_pay))
            
            res.append(d)
            time.sleep(0.05) # Prevence blokace
        except: continue
        pb.progress((idx + 1) / len(tickery))
    
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

# --- FORMÁTOVÁNÍ ---
def style_val(v, col):
    if col == "P/E" and v > 35: return 'background-color: #f8d7da'
    if col == "Dluh D/E %" and v > 150: return 'background-color: #f8d7da'
    return ''

if not df.empty:
    df = df.sort_values("Score", ascending=False)
    
    # Definice VŠECH sloupců (aby žádný nechyběl)
    columns_to_show = ["Ticker", "Score", "P/E", "P/S", "P/FCF", "Marže Čistá", "ROE", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    df = df.reindex(columns=columns_to_show).fillna(0)

    pct_cols = ["Marže Čistá", "ROE", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    fmt = {c: "{:.1f} %" for c in pct_cols}
    fmt.update({"P/E": "{:.1f}", "P/S": "{:.1f}", "P/FCF": "{:.1f}", "Score": "{:.0f}"})

    st.dataframe(
        df.style.apply(lambda x: [style_val(v, x.name) for v in x])
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(fmt),
        use_container_width=True
    )
else:
    st.error("Chyba spojení. Yahoo Finance momentálně blokuje požadavky.")
