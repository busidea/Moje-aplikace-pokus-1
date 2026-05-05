import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V9 - Trend Matrix", layout="wide")

st.title("🏛️ Investiční Matrix s trendy a potenciálem")

# --- KONFIGURACE TICKERŮ ---
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "V", "MA", "COST", "KO", "PEP", "MO"]

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

# Nastavení pásem (příklady - upravte si dle svého)
p_pe = vytvor_pasma("P/E Ratio", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_pfcf = vytvor_pasma("P/FCF Ratio", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_roe = vytvor_pasma("ROE (%)", "roe", [5, 15, 25, 40, 999], [-5, 5, 10, 15, 20])
p_trend = vytvor_pasma("Trend (ROE/Marže) %", "trnd", [-2, 0, 2, 5, 999], [-10, 0, 5, 10, 15], "Změna v procentních bodech za 3 roky")
p_poten = vytvor_pasma("Potenciál (%)", "pot", [0, 10, 20, 35, 999], [-10, 0, 10, 20, 30], "Rozdíl Target Price vs Aktuální cena")

# --- FUNKCE PRO VÝPOČET SCORE ---
def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- DATA FETCHING (Historie + Aktuální) ---
@st.cache_data(ttl=3600)
def fetch_comprehensive_data(tickers):
    results = []
    progress_bar = st.progress(0)
    for idx, t in enumerate(tickers):
        try:
            s = yf.Ticker(t)
            info = s.info
            hist_fin = s.financials # Výsledovka
            hist_bal = s.balance_sheet # Rozvaha

            # 1. Aktuální data
            curr_price = info.get("currentPrice", 1)
            target_price = info.get("targetMeanPrice", curr_price)
            potencial = ((target_price / curr_price) - 1) * 100
            
            # 2. Výpočet trendu (např. ROE před 3 lety vs dnes)
            # Zjednodušeně bereme Net Income a Equity z historie
            try:
                curr_roe = (info.get("returnOnEquity", 0) or 0) * 100
                # Pokus o historické ROE (velmi zjednodušeně pro stabilitu)
                old_net_income = hist_fin.iloc[:, -1].get("Net Income", 0)
                old_equity = hist_bal.iloc[:, -1].get("Stockholders Equity", 1)
                old_roe = (old_net_income / old_equity) * 100
                roe_trend = curr_roe - old_roe
            except:
                roe_trend = 0

            d = {
                "Ticker": t,
                "P/E": info.get("trailingPE", 0),
                "P/S": info.get("priceToSalesTrailing12Months", 0),
                "P/B": info.get("priceToBook", 0),
                "P/FCF": info.get("marketCap", 0) / info.get("freeCashflow", 1) if info.get("freeCashflow") else 0,
                "Čistá Marže %": (info.get("profitMargins", 0) or 0) * 100,
                "ROE %": curr_roe,
                "ROE Trend (3Y)": roe_trend,
                "Zadlužení (D/E)": (info.get("debtToEquity", 0) or 0) / 100,
                "Div. Výnos %": (info.get("dividendYield", 0) or 0) * 100,
                "Payout Ratio %": (info.get("payoutRatio", 0) or 0) * 100,
                "Potenciál %": potencial
            }
            
            # Výpočet celkového score
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/FCF"], p_pfcf) + 
                          get_b(d["ROE %"], p_roe) + get_b(d["ROE Trend (3Y)"], p_trend) +
                          get_b(d["Potenciál %"], p_poten))
            
            results.append(d)
        except Exception as e:
            st.warning(f"Chyba u {t}: {e}")
        progress_bar.progress((idx + 1) / len(tickers))
    
    return pd.DataFrame(results)

# Spuštění aplikace
df = fetch_comprehensive_data(moje_akcie)
df = df.sort_values(by="Score", ascending=False)

# --- ZOBRAZENÍ TABULKY ---
st.subheader("📊 Výsledná analýza podle vašeho pořadí")
st.dataframe(
    df.style.background_gradient(subset=['Score'], cmap='RdYlGn').format(precision=2),
    use_container_width=True
)

st.info("Aplikace nyní analyzuje tržní ocenění, ziskovost, trendy za 3 roky i analytický potenciál.")
