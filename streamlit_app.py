import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V14 - Google Sheets", layout="wide")

# --- PROPOJENÍ S GOOGLE TABULKOU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600) # Data o seznamu akcií se obnoví každých 10 minut
def nacti_seznam_akcii(odkaz):
    try:
        # Úprava URL pro přímé stažení CSV
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        # Odstranění případných parametrů na konci a vynucení exportu
        if '/export' not in csv_url:
            csv_url = odkaz.split('/edit')[0] + '/export?format=csv'
        
        ex_df = pd.read_csv(csv_url)
        # Očištění názvů sloupců od mezer
        ex_df.columns = ex_df.columns.str.strip()
        # Vytvoření slovníku {Ticker: Kategorie}
        return pd.Series(ex_df.Kategorie.values, index=ex_df.Ticker).to_dict()
    except Exception as e:
        st.error(f"Chyba při načítání Google tabulky. Zkontrolujte názvy sloupců 'Ticker' a 'Kategorie'. Detail: {e}")
        return {}

# Načtení databáze z vašeho odkazu
moje_databaze = nacti_seznam_akcii(ODKAZ_NA_TABULKU)

st.title("🏛️ Profesionální Investiční Matrix")
st.caption(f"Data načtena z Google Sheets. Aktuálně sledujete {len(moje_databaze)} titulů.")

# --- SIDEBAR: FILTRY A 16 UKAZATELŮ ---
st.sidebar.header("🔍 Zobrazení")
zobrazit_kat = st.sidebar.radio("Skupina k analýze:", ["Vše", "Portfolio", "Sledované"])

st.sidebar.header("🎯 Nastavení bodování")
def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_h_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_b_{i}")
            d.append({"h": h, "b": b})
        return d

# Definice 16 ukazatelů (pásma a body)
p_pe   = vytvor_p("P/E Ratio", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps   = vytvor_p("P/S Ratio", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb   = vytvor_p("P/B Ratio", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf = vytvor_p("P/FCF Ratio", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_gm   = vytvor_p("Hrubá Marže %", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_gma  = vytvor_p("Hrubá M. vs Průměr", "gma", [-5, 0, 2, 5, 999], [-10, 0, 5, 10, 15])
p_nm   = vytvor_p("Čistá Marže %", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_nma  = vytvor_p("Čistá M. vs Průměr", "nma", [-3, 0, 1, 4, 999], [-10, 0, 5, 10, 15])
p_roe  = vytvor_p("ROE %", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_roea = vytvor_p("ROE vs Průměr", "roea", [-5, 0, 2, 5, 999], [-10, 0, 5, 10, 15])
p_rev  = vytvor_p("Trend Tržeb %", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps  = vytvor_p("Trend EPS %", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb  = vytvor_p("Debt/Equity", "deb", [0.5, 1.0, 1.5, 2.5, 999], [15, 10, 5, 0, -10])
p_div  = vytvor_p("Div. Výnos %", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pay  = vytvor_p("Payout Ratio %", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])
p_pot  = vytvor_p("Potenciál %", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_all_data(db, filtr):
    if not db: return pd.DataFrame()
    
    tickery = list(db.keys()) if filtr == "Vše" else [t for t, k in db.items() if k == filtr]
    res = []
    pb = st.progress(0)
    for idx, t in enumerate(tickery):
        try:
            s = yf.Ticker(str(t).strip())
            i, f = s.info, s.financials
            cp, tp = i.get("currentPrice", 1), i.get("targetMeanPrice", 1)
            
            def g_avg(n): 
                try: return f.loc[n].mean()
                except: return 0
            
            curr_gm = (i.get("grossMargins", 0) or 0) * 100
            avg_gm = (g_avg("Gross Profit") / g_avg("Total Revenue") * 100) if g_avg("Total Revenue") else 0
            curr_nm = (i.get("profitMargins", 0) or 0) * 100
            avg_nm = (g_avg("Net Income") / g_avg("Total Revenue") * 100) if g_avg("Total Revenue") else 0
            curr_roe = (i.get("returnOnEquity", 0) or 0) * 100
            
            d = {
                "Ticker": t, "Kat": db[t], "P/E": i.get("trailingPE", 0) or 0,
                "P/S": i.get("priceToSalesTrailing12Months", 0) or 0,
                "P/B": i.get("priceToBook", 0) or 0,
                "P/FCF": i.get("marketCap", 0) / i.get("freeCashflow", 1) if i.get("freeCashflow", 0) > 0 else 0,
                "GM TTM %": curr_gm, "GM vs Avg": curr_gm - avg_gm,
                "NM TTM %": curr_nm, "NM vs Avg": curr_nm - avg_nm,
                "ROE TTM %": curr_roe, "ROE vs Avg": curr_roe - (curr_roe * 0.9),
                "Rev Trend %": (i.get("revenueGrowth", 0) or 0) * 100,
                "EPS Trend %": (i.get("earningsGrowth", 0) or 0) * 100,
                "D/E": (i.get("debtToEquity", 0) or 0) / 100,
                "Div %": (i.get("dividendYield", 0) or 0) * 100,
                "Payout %": (i.get("payoutRatio", 0) or 0) * 100,
                "Potenciál %": ((tp / cp) - 1) * 100 if tp else 0
            }
            
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/B"], p_pb) + get_b(d["P/FCF"], p_pfcf) +
                          get_b(d["GM TTM %"], p_gm) + get_b(d["GM vs Avg"], p_gma) + get_b(d["NM TTM %"], p_nm) + get_b(d["NM vs Avg"], p_nma) +
                          get_b(d["ROE TTM %"], p_roe) + get_b(d["ROE vs Avg"], p_roea) + get_b(d["Rev Trend %"], p_rev) + get_b(d["EPS Trend %"], p_eps) +
                          get_b(d["D/E"], p_deb) + get_b(d["Div %"], p_div) + get_b(d["Payout %"], p_pay) + get_b(d["Potenciál %"], p_pot))
            res.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(res)

df = fetch_all_data(moje_databaze, zobrazit_kat)

if not df.empty:
    df = df.sort_values(by="Score", ascending=False)
    st.dataframe(df.style.background_gradient(subset=['Score'], cmap='RdYlGn').format(precision=2), use_container_width=True)
else:
    st.info("Tabulka je prázdná. Zkontrolujte Google Sheets nebo zkuste jiný filtr.")
