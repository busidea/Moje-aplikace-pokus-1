import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Matrix V40", layout="wide")

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

st.title("🏛️ Investiční Matrix V40 - Dvouřádkový Audit")

# --- SIDEBAR (Zůstává stejný pro váhy a pásma) ---
st.sidebar.header("⚖️ Globální Váhy")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

show_audit = st.sidebar.checkbox("Zobrazit bodové řádky (Audit)", value=True)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# Definice pásem (všech 16 prvků)
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_nm = vytvor_p("Čistá marže %", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_deb = vytvor_p("Dluh D/E %", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
# ... (ostatní pásma zůstávají v paměti aplikace)

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
            
            # Surová data
            d = {"Ticker": t, "P/E": g("trailingPE"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                 "Čistá marže": g("profitMargins", 100), "Dluh D/E": g("debtToEquity"), "Potenciál": g("targetMeanPrice")}
            
            # Výpočet bodů (vážený)
            b_pe = get_b(d["P/E"], p_pe)*w_val
            b_fcf = get_b(d["P/FCF"], p_pfcf)*w_val
            b_nm = get_b(d["Čistá marže"], p_nm)*w_prof
            b_deb = get_b(d["Dluh D/E"], p_deb)*w_risk
            score = b_pe + b_fcf + b_nm + b_deb
            
            # Hlavní řádek (Hodnoty)
            res.append({
                "Ticker": t, "Typ": "Hodnota", "P/E": d["P/E"], "P/FCF": d["P/FCF"], 
                "Čistá marže": d["Čistá marže"], "Dluh D/E": d["Dluh D/E"], "Score": score
            })
            
            # Auditní řádek (Body)
            if show_audit:
                res.append({
                    "Ticker": f"└─ body:", "Typ": "Body", "P/E": b_pe, "P/FCF": b_fcf, 
                    "Čistá marže": b_nm, "Dluh D/E": b_deb, "Score": score
                })
        except: continue
        pb.progress((idx+1)/len(tickery))
    return pd.DataFrame(res)

df_raw = fetch_data(moje_databaze)

if not df_raw.empty:
    # --- STYLING ---
    def styler(row):
        if row["Typ"] == "Body":
            return ['background-color: #f1f3f5; color: #6c757d; font-style: italic'] * len(row)
        return [''] * len(row)

    # Formátování hodnot vs body
    def format_val(v, row_type):
        if row_type == "Body":
            return f"pts: {v:+.1f}"
        return f"{v:.1f}"

    # Zobrazení
    st.dataframe(
        df_raw.style.apply(styler, axis=1)
        .background_gradient(subset=['Score'], cmap='RdYlGn')
        .format(precision=1),
        use_container_width=True, height=850, hide_index=True
    )
