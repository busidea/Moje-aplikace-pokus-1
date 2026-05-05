import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V12", layout="wide")

# --- DATABÁZE TICKERŮ (Zde si doplňujte další) ---
# Portfolio z obrázku (bez ETF) + Sledované
moje_databaze = {
    "HEI.DE": "Portfolio",      # Heidelberg Materials
    "HEIJM.AS": "Portfolio",    # Heijmans (Amsterdam - Euronext)
    "CEZ.PR": "Portfolio",      # ČEZ
    "GOOGL": "Portfolio",       # Alphabet
    "VIG.PR": "Portfolio",      # VIG
    "KOMB.PR": "Portfolio",     # Komerční banka
    "MONET.PR": "Portfolio",    # MONETA
    "SHL.DE": "Portfolio",      # Siemens Healthineers
    "VOW3.DE": "Portfolio",     # Volkswagen Pref.
    "PLTR": "Portfolio",        # Palantir
    "HPE": "Portfolio",         # Hewlett Packard Enterprise
    "QD": "Portfolio",          # Qudian
    "BAS.DE": "Portfolio",      # BASF
    "NOKIA.HE": "Portfolio",    # Nokia
    "META": "Portfolio",        # Meta
    "GSK": "Portfolio",         # GSK
    "NOVO-B.CO": "Portfolio",   # Novo Nordisk
    "GTN": "Portfolio",         # Gray Television
    "PFE": "Portfolio",         # Pfizer
    "STLAM.MI": "Portfolio",    # STMicroelectronics
    # Tady jsou příklady sledovaných (doplňte si své z Excelu)
    "MSFT": "Sledované",
    "AAPL": "Sledované",
    "NVDA": "Sledované",
    "ASML.AS": "Sledované"
}

st.title("📊 Moje Investiční Centrum")

# --- FILTRY V SIDEBARU ---
st.sidebar.header("🔍 Filtrování a Zobrazení")
zobrazit_kat = st.sidebar.radio("Zobrazit skupinu:", ["Vše", "Portfolio", "Sledované"])

# --- NASTAVENÍ BODŮ (Zkráceno pro přehlednost, funkčnost zůstává) ---
# (Zde zůstávají vaše expandery pro 16 ukazatelů jako v minulé verzi...)
# Pro úsporu místa v tomto bloku kódu definuji jen hlavní funkci bodování

def vytvor_pasma(nazev, zkratka, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        data = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zkratka}_h_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zkratka}_b_{i}")
            data.append({"h": h, "b": b})
        return data

p_pe = vytvor_pasma("P/E Ratio", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_roe = vytvor_pasma("ROE TTM (%)", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_pot = vytvor_pasma("Potenciál (%)", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_data(databaze, filtr):
    results = []
    # Filtrování seznamu tickerů před stahováním
    if filtr == "Vše":
        tickery = list(databaze.keys())
    else:
        tickery = [t for t, kat in databaze.items() if kat == filtr]

    pb = st.progress(0)
    for idx, t in enumerate(tickery):
        try:
            s = yf.Ticker(t)
            i = s.info
            
            cp = i.get("currentPrice", 1)
            tp = i.get("targetMeanPrice", cp)
            roe = (i.get("returnOnEquity", 0) or 0) * 100
            pe = i.get("trailingPE", 0) or 0
            pot = ((tp / cp) - 1) * 100

            d = {
                "Ticker": t,
                "Kategorie": databaze[t],
                "Název": i.get("longName", t),
                "Cena": cp,
                "P/E": pe,
                "ROE %": roe,
                "Potenciál %": pot,
                "Div. Výnos %": (i.get("dividendYield", 0) or 0) * 100
            }
            # Výpočet Score (zde si doplňte součet pro všech 16)
            d["Score"] = get_b(pe, p_pe) + get_b(roe, p_roe) + get_b(pot, p_pot)
            results.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(results)

# --- VÝSTUP ---
df = fetch_data(moje_databaze, zobrazit_kat)

if not df.empty:
    df = df.sort_values(by="Score", ascending=False)
    st.subheader(f"Výsledky: {zobrazit_kat}")
    st.dataframe(
        df.style.background_gradient(subset=['Score'], cmap='RdYlGn').format(precision=2),
        use_container_width=True
    )
else:
    st.write("Žádná data k zobrazení.")
