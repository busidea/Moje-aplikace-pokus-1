import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V15", layout="wide")

# --- PROPOJENÍ S GOOGLE TABULKOU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam_akcii(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        if '/export' not in csv_url:
            csv_url = odkaz.split('/edit')[0] + '/export?format=csv'
        ex_df = pd.read_csv(csv_url)
        ex_df.columns = ex_df.columns.str.strip()
        return pd.Series(ex_df.Kategorie.values, index=ex_df.Ticker).to_dict()
    except Exception as e:
        st.error(f"Chyba při načítání Google tabulky: {e}")
        return {}

moje_databaze = nacti_seznam_akcii(ODKAZ_NA_TABULKU)

st.title("🏛️ Investiční Matrix V15")
st.caption(f"Data z Google Sheets | Sledováno {len(moje_databaze)} titulů")

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

# Definice bodování (stejná logika jako dříve)
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
            cp, tp = i.get("currentPrice", 1), i.get("targetMeanPrice", 0)
            
            def g_avg(n): 
                try: return f.loc[n].mean()
                except: return 0
            
            c_gm = (i.get("grossMargins", 0) or 0) * 100
            a_gm = (g_avg("Gross Profit") / g_avg("Total Revenue") * 100) if g_avg("Total Revenue") else 0
            c_nm = (i.get("profitMargins", 0) or 0) * 100
            a_nm = (g_avg("Net Income") / g_avg("Total Revenue") * 100) if g_avg("Total Revenue") else 0
            c_roe = (i.get("returnOnEquity", 0) or 0) * 100
            
            d = {
                "Ticker": t, "Kat": db[t], "P/E": i.get("trailingPE", 0) or 0,
                "P/S": i.get("priceToSalesTrailing12Months", 0) or 0,
                "P/B": i.get("priceToBook", 0) or 0,
                "P/FCF": i.get("marketCap", 0) / i.get("freeCashflow", 1) if i.get("freeCashflow", 0) > 0 else 0,
                "Hrubá marže %": c_gm, "GM vs Průměr": c_gm - a_gm,
                "Čistá marže %": c_nm, "NM vs Průměr": c_nm - a_nm,
                "ROE %": c_roe, "ROE vs Průměr": c_roe - (c_roe * 0.9),
                "Růst tržeb (y/y) %": (i.get("revenueGrowth", 0) or 0) * 100,
                "Růst zisku (y/y) %": (i.get("earningsGrowth", 0) or 0) * 100,
                "Dluh (D/E)": (i.get("debtToEquity", 0) or 0) / 100,
                "Div. výnos %": (i.get("dividendYield", 0) or 0) * 100,
                "Výplatní poměr %": (i.get("payoutRatio", 0) or 0) * 100,
                "Potenciál %": ((tp / cp) - 1) * 100 if tp > 0 else 0
            }
            
            d["Score"] = (get_b(d["P/E"], p_pe) + get_b(d["P/S"], p_ps) + get_b(d["P/B"], p_pb) + get_b(d["P/FCF"], p_pfcf) +
                          get_b(d["Hrubá marže %"], p_gm) + get_b(d["GM vs Průměr"], p_gma) + get_b(d["Čistá marže %"], p_nm) + get_b(d["NM vs Průměr"], p_nma) +
                          get_b(d["ROE %"], p_roe) + get_b(d["ROE vs Průměr"], p_roea) + get_b(d["Růst tržeb (y/y) %"], p_rev) + get_b(d["Růst zisku (y/y) %"], p_eps) +
                          get_b(d["Dluh (D/E)"], p_deb) + get_b(d["Div. výnos %"], p_div) + get_b(d["Výplatní poměr %"], p_pay) + get_b(d["Potenciál %"], p_pot))
            res.append(d)
        except: continue
        pb.progress((idx + 1) / len(tickery))
    return pd.DataFrame(res)

df = fetch_all_data(moje_databaze, zobrazit_kat)

# --- FORMÁTOVÁNÍ A ZOBRAZENÍ ---
def color_cells(val, column):
    # P/E: Zelená pod 15, Červená nad 30
    if column == "P/E":
        if val <= 0: return ''
        if val < 15: return 'background-color: #d4edda; color: #155724'
        if val > 30: return 'background-color: #f8d7da; color: #721c24'
    # Marže a ROE: Zelená nad 15, Červená pod 5
    if column in ["Čistá marže %", "ROE %"]:
        if val > 15: return 'background-color: #d4edda; color: #155724'
        if val < 5: return 'background-color: #f8d7da; color: #721c24'
    # Dluh: Zelená pod 0.5, Červená nad 1.5
    if column == "Dluh (D/E)":
        if val < 0.5: return 'background-color: #d4edda; color: #155724'
        if val > 1.5: return 'background-color: #f8d7da; color: #721c24'
    # Výplatní poměr: Červená nad 95
    if column == "Výplatní poměr %":
        if val > 95: return 'background-color: #f8d7da; color: #721c24'
    return ''

if not df.empty:
    df = df.sort_values(by="Score", ascending=False)
    st.dataframe(
        df.style.background_gradient(subset=['Score'], cmap='RdYlGn')
        .apply(lambda x: [color_cells(v, x.name) for v in x])
        .format(precision=2),
        use_container_width=True
    )
else:
    st.info("Žádná data k zobrazení. Zkontrolujte Google Sheets.")
