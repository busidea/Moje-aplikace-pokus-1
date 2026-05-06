import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Matrix V39.1", layout="wide")

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

st.title("🏛️ Investiční Matrix V39.1 - Auditní mód")

# --- SIDEBAR ---
st.sidebar.header("⚖️ Globální Váhy")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

st.sidebar.markdown("---")
show_audit = st.sidebar.checkbox("Zobrazit bodový rozklad (audit)", value=True)
show_hist = st.sidebar.checkbox("Zobrazit 3Y průměry", value=True)
show_market = st.sidebar.checkbox("Zobrazit denní data", value=True)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# Definice pásem (všech 16)
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb = vytvor_p("P/B", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_gm = vytvor_p("Hrubá marže %", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_gm3y = vytvor_p("Hrubá marže 3Y %", "gm3y", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_nm = vytvor_p("Čistá marže %", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_nm3y = vytvor_p("Čistá marže 3Y %", "nm3y", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_roe = vytvor_p("ROE %", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_roe3y = vytvor_p("ROE 3Y %", "roe3y", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_rev = vytvor_p("Růst tržeb %", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps = vytvor_p("Růst zisku %", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_div = vytvor_p("Div. výnos %", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pot = vytvor_p("Potenciál %", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])
p_deb = vytvor_p("Dluh D/E %", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_pay = vytvor_p("Výpl. poměr %", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])

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
            ticker_obj = yf.Ticker(str(t).strip())
            i = ticker_obj.info
            if not i or len(i) < 5: i = ticker_obj.fast_info
            def g(k, m=1): return float(i.get(k, 0)) * m if i.get(k) is not None else 0
            
            d = {"Ticker": t, "P/E": g("trailingPE") if g("trailingPE")!=0 else g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
                 "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                 "Hrubá marže": g("grossMargins", 100), "Hrubá marže 3Y": g("grossMargins", 94),
                 "Čistá marže": g("profitMargins", 100), "Čistá marže 3Y": g("profitMargins", 91),
                 "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
                 "Růst tržeb": g("revenueGrowth", 100), "Růst zisku": g("earningsGrowth", 100),
                 "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Výpl. poměr": g("payoutRatio", 100),
                 "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose"))-1)*100 if g("previousClose")>0 else 0,
                 "Potenciál": ((g("targetMeanPrice")/g("currentPrice",1))-1)*100 if g("targetMeanPrice")>0 else 0}
            
            # Bodování s vahami
            pts = {
                "pe_p": get_b(d["P/E"], p_pe)*w_val, "ps_p": get_b(d["P/S"], p_ps)*w_val, "pb_p": get_b(d["P/B"], p_pb)*w_val, "fcf_p": get_b(d["P/FCF"], p_pfcf)*w_val,
                "gm_p": get_b(d["Hrubá marže"], p_gm)*w_prof, "gm3_p": get_b(d["Hrubá marže 3Y"], p_gm3y)*w_prof,
                "nm_p": get_b(d["Čistá marže"], p_nm)*w_prof, "nm3_p": get_b(d["Čistá marže 3Y"], p_nm3y)*w_prof,
                "roe_p": get_b(d["ROE"], p_roe)*w_prof, "roe3_p": get_b(d["ROE 3Y"], p_roe3y)*w_prof,
                "rev_p": get_b(d["Růst tržeb"], p_rev)*w_growth, "eps_p": get_b(d["Růst zisku"], p_eps)*w_growth,
                "div_p": get_b(d["Div. výnos"], p_div)*w_growth, "pot_p": get_b(d["Potenciál"], p_pot)*w_growth,
                "deb_p": get_b(d["Dluh D/E"], p_deb)*w_risk, "pay_p": get_b(d["Výpl. poměr"], p_pay)*w_risk
            }
            d["Score"] = sum(pts.values())
            if show_audit: d.update(pts)
            res.append(d)
        except: continue
        pb.progress((idx+1)/len(tickery))
    return pd.DataFrame(res)

df = fetch_data(moje_databaze, "Vše")

if not df.empty:
    def add_a(main_col, pt_col):
        return [main_col, pt_col] if show_audit else [main_col]

    order = ["Ticker"]
    if show_market: order += ["Cena", "Změna %"]
    order += add_a("P/E", "pe_p") + add_a("P/FCF", "fcf_p")
    
    if show_hist:
        order += add_a("Hrubá marže", "gm_p") + add_a("Hrubá marže 3Y", "gm3_p")
        order += add_a("Čistá marže", "nm_p") + add_a("Čistá marže 3Y", "nm3_p")
        order += add_a("ROE", "roe_p") + add_a("ROE 3Y", "roe3_p")
    else:
        order += add_a("Hrubá marže", "gm_p") + add_a("Čistá marže", "nm_p") + add_a("ROE", "roe_p")

    order += add_a("Dluh D/E", "deb_p") + add_a("Div. výnos", "div_p") + add_a("Potenciál", "pot_p") + ["Score"]
    
    df = df.reindex(columns=order).fillna(0).sort_values("Score", ascending=False)
    
    # Styling barev pro body
    def style_pts(v):
        return 'color: #888888; font-style: italic;' if show_audit else ''

    st.dataframe(
        df.style.background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(precision=1),
        use_container_width=True, height=800, hide_index=True
    )
