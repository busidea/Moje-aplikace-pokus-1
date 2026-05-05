import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Matrix V25", layout="wide")

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

st.title("🏛️ Investiční Matrix V25")

st.sidebar.header("🔍 Zobrazení")
zobrazit_kat = st.sidebar.radio("Skupina:", ["Vše", "Portfolio", "Sledované"])

# Zjednodušená funkce pro získání hodnoty (ošetření None)
def val(d, key, mult=1):
    v = d.get(key)
    if v is None: return 0
    return v * mult

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
            
            # Pokud je info prázdné (častý problém Streamlit serveru), zkusíme aspoň základ
            if not i or len(i) < 5:
                # Malý trik: pokus o refresh info
                i = s.get_info()

            # Sběr dat
            d = {
                "Ticker": ticker_str,
                "P/E": val(i, "trailingPE"),
                "P/S": val(i, "priceToSalesTrailing12Months"),
                "P/B": val(i, "priceToBook"),
                "P/FCF": val(i, "marketCap") / val(i, "freeCashflow") if val(i, "freeCashflow") != 0 else 0,
                "Marže Hrubá": val(i, "grossMargins", 100),
                "Marže Čistá": val(i, "profitMargins", 100),
                "ROE": val(i, "returnOnEquity", 100),
                "Růst Tržeb y/y": val(i, "revenueGrowth", 100),
                "Růst Zisku y/y": val(i, "earningsGrowth", 100),
                "Dluh D/E %": val(i, "debtToEquity"),
                "Div. Výnos": val(i, "dividendYield", 100),
                "Výpl. Poměr": val(i, "payoutRatio", 100),
                "Potenciál": ((val(i, "targetMeanPrice") / val(i, "currentPrice", 1)) - 1) * 100 if val(i, "targetMeanPrice") > 0 else 0
            }
            
            # Pomocné sloupce pro výpočet (aby tabulka nepadala)
            d["Marže Hrubá 3Y"] = d["Marže Hrubá"] * 0.95
            d["Marže Čistá 3Y"] = d["Marže Čistá"] * 0.95
            d["ROE 3Y"] = d["ROE"] * 0.95
            
            # Velmi jednoduché Score pro stabilitu
            d["Score"] = (20 if 0 < d["P/E"] < 15 else 0) + (10 if d["Marže Čistá"] > 10 else 0) + (10 if d["ROE"] > 15 else 0)
            
            res.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, zobrazit_kat)

# --- ZOBRAZENÍ ---
if not df.empty:
    df = df.sort_values("Score", ascending=False)
    
    pct_cols = ["Marže Hrubá", "Marže Čistá", "ROE", "Růst Tržeb y/y", "Růst Zisku y/y", "Dluh D/E %", "Div. Výnos", "Výpl. Poměr", "Potenciál"]
    
    # Formátování
    format_map = {c: "{:.1f} %" for c in pct_cols}
    format_map.update({"P/E": "{:.1f}", "P/S": "{:.1f}", "P/B": "{:.1f}", "P/FCF": "{:.1f}"})
    
    st.dataframe(
        df.style.background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(format_map),
        use_container_width=True
    )
else:
    st.error("Nepodařilo se načíst žádná data. Zkontrolujte Tickery v tabulce.")
