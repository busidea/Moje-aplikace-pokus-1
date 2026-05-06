import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Matrix V41.1", layout="wide")

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

st.title("🏛️ Investiční Matrix V41.1")

# --- SIDEBAR ---
st.sidebar.header("⚖️ Globální Váhy")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

st.sidebar.markdown("---")
show_audit = st.sidebar.checkbox("Zobrazit bodové řádky (Audit)", value=True)
show_hist = st.sidebar.checkbox("Zobrazit 3Y průměry", value=True)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# Načtení všech 16 bodovacích pásem
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
def fetch_data(db):
    res = []
    tickery = list(db.keys())
    pb = st.progress(0)
    for idx, t in enumerate(tickery):
        try:
            ticker_obj = yf.Ticker(str(t).strip())
            i = ticker_obj.info
            def g(k, m=1): return float(i.get(k, 0)) * m if i.get(k) is not None else 0
            
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose"))-1)*100 if g("previousClose")>0 else 0,
                "P/E": g("trailingPE") if g("trailingPE")!=0 else g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
                "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                "GM": g("grossMargins", 100), "GM3Y": g("grossMargins", 94),
                "NM": g("profitMargins", 100), "NM3Y": g("profitMargins", 91),
                "ROE": g("returnOnEquity", 100), "ROE3Y": g("returnOnEquity", 93),
                "Růst tržeb": g("revenueGrowth", 100), "Růst zisku": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Výpl. poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0
            }
            
            pts = {
                "P/E": get_b(d["P/E"], p_pe)*w_val, "P/S": get_b(d["P/S"], p_ps)*w_val, "P/B": get_b(d["P/B"], p_pb)*w_val, "P/FCF": get_b(d["P/FCF"], p_pfcf)*w_val,
                "GM": get_b(d["GM"], p_gm)*w_prof, "GM3Y": get_b(d["GM3Y"], p_gm3y)*w_prof, "NM": get_b(d["NM"], p_nm)*w_prof, "NM3Y": get_b(d["NM3Y"], p_nm3y)*w_prof,
                "ROE": get_b(d["ROE"], p_roe)*w_prof, "ROE3Y": get_b(d["ROE3Y"], p_roe3y)*w_prof,
                "Růst tržeb": get_b(d["Růst tržeb"], p_rev)*w_growth, "Růst zisku": get_b(d["Růst zisku"], p_eps)*w_growth,
                "Div. výnos": get_b(d["Div. výnos"], p_div)*w_growth, "Potenciál": get_b(d["Potenciál"], p_pot)*w_growth,
                "Dluh D/E": get_b(d["Dluh D/E"], p_deb)*w_risk, "Výpl. poměr": get_b(d["Výpl. poměr"], p_pay)*w_risk
            }
            total_score = sum(pts.values())
            res.append({**d, "Score": total_score, "RowType": "Val", "SortKey": total_score})
            if show_audit:
                audit_row = {k: pts.get(k, 0) for k in d.keys() if k in pts}
                audit_row.update({"Ticker": "└─ pts", "Score": total_score, "RowType": "Pts", "SortKey": total_score - 0.0001})
                res.append(audit_row)
        except: continue
        pb.progress((idx+1)/len(tickery))
    return pd.DataFrame(res)

df_raw = fetch_data(moje_databaze)

if not df_raw.empty:
    df_raw = df_raw.sort_values("SortKey", ascending=False)
    
    # Sloupce pro zobrazení
    disp_cols = ["Ticker", "Cena", "P/E", "P/FCF", "GM", "GM3Y", "NM", "NM3Y", "ROE", "ROE3Y", "Růst tržeb", "Dluh D/E", "Div. výnos", "Potenciál", "Score"]
    if not show_hist:
        disp_cols = [c for c in disp_cols if "3Y" not in c]
    
    # Nejdříve připravíme tabulku VČETNĚ RowType pro barvení
    # Ale uživateli ukážeme jen vybrané sloupce pomocí column_order
    def style_rows(row):
        if row["RowType"] == "Pts":
            return ['background-color: #f1f3f5; color: #868e96; font-style: italic'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df_raw.style.apply(style_rows, axis=1)
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(precision=1),
        use_container_width=True, 
        height=900, 
        hide_index=True,
        column_order=disp_cols # TADY se definuje, co uživatel uvidí (RowType zůstane skrytý)
    )
