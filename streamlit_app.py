import streamlit as st
import pandas as pd
import yfinance as yf
import time

st.set_page_config(page_title="Investiční Matrix V27", layout="wide")

# --- KONFIGURACE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam_akcii(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        ex_df = pd.read_csv(csv_url)
        ex_df.columns = ex_df.columns.str.strip()
        return pd.Series(ex_df.Kategorie.values, index=ex_df.Ticker).to_dict()
    except:
        return {}

moje_databaze = nacti_seznam_akcii(ODKAZ_NA_TABULKU)

st.title("🏛️ Investiční Matrix V27 - Obnova stability")

# --- SIDEBAR NASTAVENÍ ---
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

# Bodovací systémy
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
            i = s.info
            
            # Bezpečné získání hodnoty (ošetření None)
            def sv(key, mult=1):
                v = i.get(key)
                return (v if v is not None else 0) * mult

            # Výpočty
            m_cap = sv("marketCap")
            fcf = sv("freeCashflow")
            pe = sv("trailingPE")
            # Pokud chybí P/E, zkusíme forward
            if pe == 0: pe = sv("forwardPE")

            d = {
                "Ticker": ticker_str,
                "P/E": pe,
                "P/S": sv("priceToSalesTrailing12Months"),
                "P/FCF": (m_cap / fcf) if fcf != 0 else 0,
                "Marže Čistá": sv("profitMargins", 100),
                "ROE": sv("returnOnEquity", 100),
                "Dluh D/E %": sv("debtToEquity"),
                "Div. Výnos": sv("dividendYield", 100),
                "Výpl. Poměr": sv("payoutRatio", 100),
                "Potenciál": ((sv("targetMeanPrice") / sv("currentPrice", 1)) - 1) * 100 if sv("targetMeanPrice") > 0 else 0
            }
            
            # Výpočet Score
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/FCF"], p_pfcf) +
                          get_b(d["Marže Čistá"], p_nm) + get_b(d["ROE"], p_roe) + 
                          get_b(d["Dluh D/E %"], p_deb) + get_b(d["Div. Výnos"], p_div) + get_b(d["Výpl. Poměr"], p_pay))
            
            res.append(d)
            # Drobná pauza pro stabilizaci API u evropských titulů
            if ".AS" in ticker_str or ".DE" in ticker_str:
                time.sleep(0.1)
                
        except Exception as e:
            continue
        pb.progress((idx + 1) / len(tickery))
    
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

# --- ZOBRAZENÍ A FORMÁTOVÁNÍ ---
def color_logic(val, col):
    if col == "P/E" and val > 35: return 'background-color: #f8d7da; color: #721c24'
    if col == "P/FCF" and val > 60: return 'background-color: #f8d7da; color: #721c24'
    if col == "Dluh D/E %" and val > 150: return 'background-color: #f8d7da; color: #721c24'
    if col == "Výpl. Poměr" and val > 100: return 'background-color: #f8d7da; color: #721c24'
    return ''

if not df.empty:
    df = df.sort_values("Score", ascending=False)
    
    # Sloupce pro formátování
    pct_cols = ["Marže Čistá", "ROE", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    num_cols = ["P/E", "P/S", "P/FCF"]
    
    fmt = {c: "{:.1f} %" for c in pct_cols}
    fmt.update({c: "{:.1f}" for c in num_cols})

    st.dataframe(
        df.style.apply(lambda x: [color_logic(v, x.name) for v in x])
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(fmt),
        use_container_width=True
    )
else:
    st.warning("Tabulka je prázdná. Zkontrolujte spojení s Google Sheets.")
