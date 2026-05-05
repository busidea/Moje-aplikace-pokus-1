import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V10 - Kompletní Matrix", layout="wide")

st.title("🏛️ Finální Investiční Matrix")
st.write("Kompletní přehled všech 12+ ukazatelů včetně historických trendů a potenciálu.")

# --- KONFIGURACE TICKERŮ ---
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "V", "MA", "COST", "KO", "PEP", "MO", "PM", "INTC", "AMD"]

# --- SIDEBAR: NASTAVENÍ BODŮ ---
st.sidebar.header("🎯 Nastavení bodovacích pásem")

def vytvor_pasma(nazev, zkratka, def_h, def_b, info=""):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        st.caption(info)
        data = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zkratka}_h_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zkratka}_b_{i}")
            data.append({"h": h, "b": b})
        return data

# Definice pásem pro všechny ukazatele (Všechny jsou v levém panelu k dispozici)
p_pe    = vytvor_pasma("P/E Ratio", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps    = vytvor_pasma("P/S Ratio", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb    = vytvor_pasma("P/B Ratio", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf  = vytvor_pasma("P/FCF Ratio", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_mar   = vytvor_pasma("Čistá Marže (%)", "mar", [0, 10, 20, 30, 999], [-5, 0, 5, 10, 15])
p_roe   = vytvor_pasma("ROE (%)", "roe", [5, 15, 25, 40, 999], [-5, 5, 10, 15, 20])
p_trend = vytvor_pasma("Trend ROE (3Y bp)", "trnd", [-2, 0, 2, 5, 999], [-10, 0, 5, 10, 15])
p_deb   = vytvor_pasma("Debt/Equity", "deb", [0.5, 1.0, 1.5, 2.5, 999], [10, 7, 3, 0, -5])
p_div   = vytvor_pasma("Dividendový výnos (%)", "div", [0, 1, 3, 5, 999], [0, 2, 5, 8, 10])
p_pay   = vytvor_pasma("Payout Ratio (%)", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])
p_poten = vytvor_pasma("Potenciál (%)", "pot", [0, 10, 20, 35, 999], [-10, 0, 10, 20, 30])

# --- POMOCNÁ FUNKCE PRO BODY ---
def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_complete_data(tickers):
    results = []
    progress_bar = st.progress(0)
    for idx, t in enumerate(tickers):
        try:
            s = yf.Ticker(t)
            i = s.info
            
            # Trend výpočet (ROE teď vs před 3-4 lety)
            curr_roe = (i.get("returnOnEquity", 0) or 0) * 100
            try:
                hist_bal = s.balance_sheet
                hist_fin = s.financials
                old_net_income = hist_fin.iloc[:, -1].get("Net Income", 0)
                old_equity = hist_bal.iloc[:, -1].get("Stockholders Equity", 1)
                old_roe = (old_net_income / old_equity) * 100
                roe_trend = curr_roe - old_roe
            except:
                roe_trend = 0

            # Výpočet P/FCF a Potenciálu
            curr_price = i.get("currentPrice", 1)
            target = i.get("targetMeanPrice", curr_price)
            fcf = i.get("freeCashflow", 0)
            p_fcf = (i.get("marketCap", 0) / fcf) if fcf > 0 else 0

            d = {
                "Ticker": t,
                "P/E": i.get("trailingPE", 0) or 0,
                "P/S": i.get("priceToSalesTrailing12Months", 0) or 0,
                "P/B": i.get("priceToBook", 0) or 0,
                "P/FCF": p_fcf,
                "Marže %": (i.get("profitMargins", 0) or 0) * 100,
                "ROE %": curr_roe,
                "ROE Trend": roe_trend,
                "D/E": (i.get("debtToEquity", 0) or 0) / 100,
                "Div. Výnos %": (i.get("dividendYield", 0) or 0) * 100,
                "Payout %": (i.get("payoutRatio", 0) or 0) * 100,
                "Potenciál %": ((target / curr_price) - 1) * 100
            }
            
            # Celkové Score - součet bodů ze všech pásem
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/B"], p_pb) + 
                          get_b(d["P/FCF"], p_pfcf) + get_b(d["Marže %"], p_mar) + 
                          get_b(d["ROE %"], p_roe) + get_b(d["ROE Trend"], p_trend) + 
                          get_b(d["D/E"], p_deb) + get_b(d["Div. Výnos %"], p_div) + 
                          get_b(d["Payout %"], p_pay) + get_b(d["Potenciál %"], p_poten))
            
            results.append(d)
        except: continue
        progress_bar.progress((idx + 1) / len(tickers))
    return pd.DataFrame(results)

df = fetch_complete_data(moje_akcie)
df = df.sort_values(by="Score", ascending=False)

# --- ZOBRAZENÍ ---
st.subheader("📊 Kompletní žebříček firem")
st.dataframe(
    df.style.background_gradient(subset=['Score'], cmap='RdYlGn').format(precision=2),
    use_container_width=True
)
