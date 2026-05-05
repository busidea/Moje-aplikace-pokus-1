import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V7 - Kompletní", layout="wide")

st.title("🏆 Profesionální Investiční Matrix")
st.write("Nastavte si 5 bodovacích pásem pro každý ukazatel. Celkové score určí vítěze.")

# --- SEZNAM AKCIÍ ---
# Zde si upravte své tickery
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "V", "MA", "COST", "KO", "PEP", "MO", "PM", "INTC", "AMD"]

# --- SIDEBAR: NASTAVENÍ PÁSEM ---
st.sidebar.header("🎯 Nastavení bodování")

def vytvor_pasma(nazev, zkratka, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        data = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Pásmo {i+1} do:", value=float(def_h[i]), key=f"{zkratka}_h_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zkratka}_b_{i}")
            data.append({"h": h, "b": b})
        return data

# Definice pásem pro všechny ukazatele
p_roe = vytvor_pasma("ROE (%)", "roe", [0, 10, 20, 35, 999], [-5, 0, 5, 10, 15])
p_mar = vytvor_pasma("Čistá Marže (%)", "mar", [0, 10, 20, 30, 999], [-5, 0, 5, 10, 15])
p_pe  = vytvor_pasma("P/E Ratio (krát)", "pe", [10, 20, 30, 50, 999], [15, 10, 5, 0, -5])
p_ps  = vytvor_pasma("P/S Ratio (krát)", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb  = vytvor_pasma("P/B Ratio (krát)", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_div = vytvor_pasma("Dividenda (%)", "div", [0, 1, 3, 5, 999], [0, 2, 5, 8, 10])
p_deb = vytvor_pasma("Debt/Equity (ratio)", "deb", [0.5, 1.0, 1.5, 2.5, 999], [10, 7, 3, 0, -5])
p_cur = vytvor_pasma("Current Ratio", "cur", [0.5, 1.0, 1.5, 2.5, 999], [-10, 0, 5, 8, 10])
p_sg  = vytvor_pasma("Růst tržeb 3Y (%)", "sg", [0, 5, 10, 20, 999], [-5, 2, 5, 10, 15])
p_eg  = vytvor_pasma("Růst zisku 3Y (%)", "eg", [0, 5, 15, 25, 999], [-5, 2, 8, 12, 20])
p_pay = vytvor_pasma("Payout Ratio (%)", "pay", [20, 40, 60, 80, 999], [5, 10, 7, 2, -10])
p_fcf = vytvor_pasma("FCF Yield (%)", "fcf", [0, 2, 4, 7, 999], [-5, 2, 6, 10, 15])

# --- VÝPOČET ---
def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

@st.cache_data(ttl=3600)
def fetch_all(tickers):
    data = []
    for t in tickers:
        try:
            s = yf.Ticker(t)
            i = s.info
            d = {
                "Ticker": t,
                "ROE": (i.get("returnOnEquity", 0) or 0) * 100,
                "Marze": (i.get("profitMargins", 0) or 0) * 100,
                "PE": i.get("trailingPE", 0) or 0,
                "PS": i.get("priceToSalesTrailing12Months", 0) or 0,
                "PB": i.get("priceToBook", 0) or 0,
                "Div": (i.get("dividendYield", 0) or 0) * 100,
                "Debt_Eq": (i.get("debtToEquity", 0) or 0) / 100,
                "Current": i.get("currentRatio", 0) or 0,
                "Sales_Gr": (i.get("revenueGrowth", 0) or 0) * 100,
                "Earn_Gr": (i.get("earningsGrowth", 0) or 0) * 100,
                "Payout": (i.get("payoutRatio", 0) or 0) * 100,
                "FCF_Yield": ((i.get("freeCashflow", 0) or 0) / (i.get("marketCap", 1))) * 100
            }
            # Výpočet celkového score
            d["Score"] = (get_b(d["ROE"], p_roe) + get_b(d["Marze"], p_mar) + get_b(d["PE"], p_pe) + 
                          get_b(d["PS"], p_ps) + get_b(d["PB"], p_pb) + get_b(d["Div"], p_div) + 
                          get_b(d["Debt_Eq"], p_deb) + get_b(d["Current"], p_cur) + get_b(d["Sales_Gr"], p_sg) + 
                          get_b(d["Earn_Gr"], p_eg) + get_b(d["Payout"], p_pay) + get_b(d["FCF_Yield"], p_fcf))
            data.append(d)
        except: continue
    return pd.DataFrame(data)

df = fetch_all(moje_akcie)
df = df.sort_values(by="Score", ascending=False)

# --- ZOBRAZENÍ ---
st.subheader("📊 Komplexní žebříček firem")
st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn'), use_container_width=True)

st.write("Tip: Rozbalte si vlevo jakýkoliv ukazatel a upravte si pásma. Tabulka se okamžitě přepočítá.")
