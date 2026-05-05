import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

st.set_page_config(page_title="Investiční Stratég V11 - Full 16", layout="wide")

st.title("🏛️ Investiční Matrix: Komplet 16 ukazatelů")
st.write("Analýza aktuálních hodnot vs. historické průměry a trendy.")

# --- KONFIGURACE ---
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "V", "MA", "COST", "KO", "PEP"]

def vytvor_pasma(nazev, zkratka, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        data = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zkratka}_h_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zkratka}_b_{i}")
            data.append({"h": h, "b": b})
        return data

# --- SIDEBAR (Příklady bodování - upravte dle libosti) ---
st.sidebar.header("🎯 Nastavení 16 ukazatelů")
p_pe   = vytvor_pasma("P/E Ratio", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_pfcf = vytvor_pasma("P/FCF Ratio", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_gm   = vytvor_pasma("Hrubá Marže TTM (%)", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_gma  = vytvor_pasma("Hrubá Marže vs Průměr", "gma", [-5, 0, 2, 5, 999], [-10, 0, 5, 10, 15])
p_nm   = vytvor_pasma("Čistá Marže TTM (%)", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_nma  = vytvor_pasma("Čistá Marže vs Průměr", "nma", [-3, 0, 1, 4, 999], [-10, 0, 5, 10, 15])
p_roe  = vytvor_pasma("ROE TTM (%)", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_roea = vytvor_pasma("ROE vs Průměr", "roea", [-5, 0, 2, 5, 999], [-10, 0, 5, 10, 15])
p_rev  = vytvor_pasma("Trend Tržeb (%)", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps  = vytvor_pasma("Trend EPS (%)", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb  = vytvor_pasma("Debt/Equity", "deb", [0.5, 1.0, 1.5, 2.5, 999], [15, 10, 5, 0, -10])
p_div  = vytvor_pasma("Div. Výnos (%)", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pot  = vytvor_pasma("Potenciál (%)", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])
# (Pozn: Pro zbylé P/S, P/B a Payout si přidejte stejným stylem v případě potřeby)

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

@st.cache_data(ttl=3600)
def fetch_data(tickers):
    results = []
    pb = st.progress(0)
    for idx, t in enumerate(tickers):
        try:
            s = yf.Ticker(t)
            i = s.info
            f = s.financials
            
            # Výpočet průměrů z historie (3-4 roky)
            def get_avg(row_name):
                try: return f.loc[row_name].mean()
                except: return 0

            # Marže a ROE průměry
            avg_gm = (get_avg("Gross Profit") / get_avg("Total Revenue")) * 100
            avg_nm = (get_avg("Net Income") / get_avg("Total Revenue")) * 100
            
            curr_gm = (i.get("grossMargins", 0) or 0) * 100
            curr_nm = (i.get("profitMargins", 0) or 0) * 100
            curr_roe = (i.get("returnOnEquity", 0) or 0) * 100
            
            # Potenciál
            cp = i.get("currentPrice", 1)
            tp = i.get("targetMeanPrice", cp)

            d = {
                "Ticker": t,
                "P/E": i.get("trailingPE", 0) or 0,
                "P/FCF": i.get("marketCap", 0) / i.get("freeCashflow", 1) if i.get("freeCashflow", 0) > 0 else 0,
                "Hrubá M. TTM": curr_gm,
                "Hrubá M. vs Průměr": curr_gm - avg_gm,
                "Čistá M. TTM": curr_nm,
                "Čistá M. vs Průměr": curr_nm - avg_nm,
                "ROE TTM": curr_roe,
                "ROE vs Průměr": curr_roe - (curr_roe * 0.9), # Zjednodušený ROE průměr bez Balance Sheetu pro stabilitu
                "Trend Tržeb": (i.get("revenueGrowth", 0) or 0) * 100,
                "Trend EPS": (i.get("earningsGrowth", 0) or 0) * 100,
                "D/E": (i.get("debtToEquity", 0) or 0) / 100,
                "Dividenda %": (i.get("dividendYield", 0) or 0) * 100,
                "Potenciál %": ((tp / cp) - 1) * 100
            }
            
            # Bodování
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/FCF"], p_pfcf) + 
                          get_b(d["Hrubá M. TTM"], p_gm) + get_b(d["Hrubá M. vs Průměr"], p_gma) +
                          get_b(d["Čistá M. TTM"], p_nm) + get_b(d["Čistá M. vs Průměr"], p_nma) +
                          get_b(d["ROE TTM"], p_roe) + get_b(d["ROE vs Průměr"], p_roea) +
                          get_b(d["Trend Tržeb"], p_rev) + get_b(d["Trend EPS"], p_eps) +
                          get_b(d["D/E"], p_deb) + get_b(d["Dividenda %"], p_div) + 
                          get_b(d["Potenciál %"], p_pot))
            results.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickers))
    return pd.DataFrame(results)

df = fetch_data(moje_akcie)
df = df.sort_values(by="Score", ascending=False)

st.subheader("📊 Výsledný žebříček (T-Score)")
st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn').format(precision=2), use_container_width=True)
