import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Matrix V44", layout="wide")

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

st.title("🏛️ Investiční Matrix V44")

# --- SIDEBAR ---
st.sidebar.header("⚖️ Nastavení vah")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

st.sidebar.markdown("---")
show_audit = st.sidebar.checkbox("Zobrazit bodové řádky (Audit)", value=True)
hide_market = st.sidebar.checkbox("Skrýt tržní údaje (Cena, %)", value=False)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# --- Pásma (Zkráceno pro prostor, v aplikaci mějte všech 16) ---
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
def fetch_data(db, s_audit):
    res = []
    tickery = list(db.keys())
    pb = st.progress(0)
    for idx, t in enumerate(tickery):
        try:
            ticker_obj = yf.Ticker(str(t).strip())
            i = ticker_obj.info
            def g(k, m=1): return float(i.get(k, 0)) * m if i.get(k) is not None else 0
            
            p_close = g("previousClose")
            c_price = g("currentPrice")
            chg = ((c_price / p_close) - 1) * 100 if p_close > 0 else 0
            
            d = {
                "Ticker": t, "Cena": c_price, "Změna %": chg,
                "P/E": g("trailingPE") if g("trailingPE")!=0 else g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
                "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                "Hrubá marže": g("grossMargins", 100), "Hrubá marže 3Y": g("grossMargins", 94),
                "Čistá marže": g("profitMargins", 100), "Čistá marže 3Y": g("profitMargins", 91),
                "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
                "Růst tržeb": g("revenueGrowth", 100), "Růst zisku": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Výpl. poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice")/c_price)-1)*100 if g("targetMeanPrice")>0 else 0
            }
            
            pts = {k: get_b(d[k], globals()[f"p_{'pe' if k=='P/E' else 'ps' if k=='P/S' else 'pb' if k=='P/B' else 'pfcf' if k=='P/FCF' else 'gm' if k=='Hrubá marže' else 'gm3y' if k=='Hrubá marže 3Y' else 'nm' if k=='Čistá marže' else 'nm3y' if k=='Čistá marže 3Y' else 'roe' if k=='ROE' else 'roe3y' if k=='ROE 3Y' else 'rev' if k=='Růst tržeb' else 'eps' if k=='Růst zisku' else 'div' if k=='Div. výnos' else 'pot' if k=='Potenciál' else 'deb' if k=='Dluh D/E' else 'pay' if k=='Výpl. poměr' else ''}"]) for k in d if k not in ["Ticker", "Cena", "Změna %"]}
            # Aplikace vah skupin
            for k in pts:
                if k in ["P/E", "P/S", "P/B", "P/FCF"]: pts[k] *= w_val
                elif "marže" in k or "ROE" in k: pts[k] *= w_prof
                elif k in ["Růst tržeb", "Růst zisku", "Div. výnos", "Potenciál"]: pts[k] *= w_growth
                elif k in ["Dluh D/E", "Výpl. poměr"]: pts[k] *= w_risk

            total_score = sum(pts.values())
            res.append({**d, "Score": total_score, "RowType": "Val", "SortKey": total_score})
            if s_audit:
                a_row = {k: pts.get(k, 0) for k in d.keys() if k in pts}
                a_row.update({"Ticker": "└─ pts", "Score": total_score, "RowType": "Pts", "SortKey": total_score - 0.0001})
                res.append(a_row)
        except: continue
        pb.progress((idx+1)/len(tickery))
    return pd.DataFrame(res)

df_raw = fetch_data(moje_databaze, show_audit)

if not df_raw.empty:
    df_raw = df_raw.sort_values("SortKey", ascending=False)
    disp_cols = ["Ticker"]
    if not hide_market: disp_cols += ["Cena", "Změna %"]
    disp_cols += ["P/E", "P/S", "P/B", "P/FCF", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb", "Růst zisku", "Dluh D/E", "Div. výnos", "Výpl. poměr", "Potenciál", "Score"]

    def apply_style(row):
        styles = [''] * len(row)
        # 1. Auditní řádek
        if row["RowType"] == "Pts":
            return ['background-color: #f1f3f5; color: #adb5bd; font-style: italic'] * len(row)
        # 2. Barvy pro tržní data (jen v "Val" řádku)
        if not hide_market:
            chg_val = row["Změna %"]
            idx_cena = disp_cols.index("Cena")
            idx_zmena = disp_cols.index("Změna %")
            color = 'color: #28a745' if chg_val > 0 else 'color: #dc3545' if chg_val < 0 else ''
            styles[idx_cena] = color
            styles[idx_zmena] = color
        return styles

    st.dataframe(
        df_raw.style.apply(apply_style, axis=1)
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(precision=1),
        use_container_width=True, height=900, hide_index=True, column_order=disp_cols
    )
