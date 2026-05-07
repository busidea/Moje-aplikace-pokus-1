import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V50", layout="wide")

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

st.title("🏛️ Investiční Matrix V50")

# --- SIDEBAR ---
st.sidebar.header("⚖️ Nastavení vah")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

st.sidebar.markdown("---")
show_audit = st.sidebar.checkbox("Zobrazit bodové řádky (Audit)", value=True)
hide_market = st.sidebar.checkbox("Skrýt tržní údaje", value=False)
show_calendar = st.sidebar.checkbox("📅 Zobrazit kalendář událostí", value=True)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# --- PÁSMA ---
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
p_rev = vytvor_p("Růst tržeb % (y/y)", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps = vytvor_p("Růst zisku % (y/y)", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb = vytvor_p("Dluh D/E %", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_div = vytvor_p("Div. výnos %", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pay = vytvor_p("Výpl. poměr %", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál %", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

@st.cache_data(ttl=3600)
def fetch_all_data(db, s_audit):
    matrix_res, cal_res = [], []
    pb = st.progress(0)
    today = date.today()
    
    for idx, t in enumerate(db.keys()):
        try:
            tick = yf.Ticker(str(t).strip())
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
                "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                "Hrubá marže %": g("grossMargins", 100), "Hrubá marže 3Y %": g("grossMargins", 94),
                "Čistá marže %": g("profitMargins", 100), "Čistá marže 3Y %": g("profitMargins", 91),
                "ROE %": g("returnOnEquity", 100), "ROE 3Y %": g("returnOnEquity", 93),
                "Růst tržeb % (y/y)": g("revenueGrowth", 100), "Růst zisku % (y/y)": g("earningsGrowth", 100),
                "Dluh D/E %": g("debtToEquity"), "Div. výnos %": g("dividendYield", 100), "Výpl. poměr %": g("payoutRatio", 100),
                "Potenciál %": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0
            }
            
            mapping = {
                "P/E": (p_pe, w_val), "P/S": (p_ps, w_val), "P/B": (p_pb, w_val), "P/FCF": (p_pfcf, w_val),
                "Hrubá marže %": (p_gm, w_prof), "Hrubá marže 3Y %": (p_gm3y, w_prof),
                "Čistá marže %": (p_nm, w_prof), "Čistá marže 3Y %": (p_nm3y, w_prof),
                "ROE %": (p_roe, w_prof), "ROE 3Y %": (p_roe3y, w_prof),
                "Růst tržeb % (y/y)": (p_rev, w_growth), "Růst zisku % (y/y)": (p_eps, w_growth),
                "Div. výnos %": (p_div, w_growth), "Potenciál %": (p_pot, w_growth),
                "Dluh D/E %": (p_deb, w_risk), "Výpl. poměr %": (p_pay, w_risk)
            }
            
            pts = {k: get_b(d[k], v[0])*v[1] for k,v in mapping.items()}
            score = sum(pts.values())
            matrix_res.append({**d, "Score": score, "RowType": "Val", "SortKey": score})
            if s_audit:
                a_row = {k: pts.get(k, 0) for k in d if k in pts}
                a_row.update({"Ticker": "└─ pts", "Score": score, "RowType": "Pts", "SortKey": score - 0.001})
                matrix_res.append(a_row)

            # --- KALENDÁŘ ---
            try: next_earn = tick.calendar['Earnings Date'][0].date()
            except: next_earn = None
            ex_date = inf.get('exDividendDate')
            ex_date_fmt = datetime.fromtimestamp(ex_date).date() if ex_date else None
            
            cal_res.append({
                "Ticker": t, "Next Earnings": next_earn or "Neznámé", 
                "Dní": (next_earn - today).days if next_earn else 999,
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD", "Ex-Date": ex_date_fmt or "Není"
            })
        except: continue
        pb.progress((idx+1)/len(db))
    return pd.DataFrame(matrix_res), pd.DataFrame(cal_res)

df_m, df_c = fetch_all_data(moje_databaze, show_audit)

if not df_m.empty:
    df_m = df_m.sort_values("SortKey", ascending=False)
    cols = ["Ticker", "Cena", "Změna %", "P/E", "P/S", "P/B", "Hrubá marže %", "Hrubá marže 3Y %", "ROE %", "Růst tržeb % (y/y)", "Růst zisku % (y/y)", "Dluh D/E %", "Div. výnos %", "Výpl. poměr %", "Potenciál %", "Score"]
    
    def apply_m_style(row):
        styles = [''] * len(row)
        if row.RowType == "Pts": return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        if not hide_market:
            c = 'color: #28a745' if row["Změna %"] > 0 else 'color: #dc3545' if row["Změna %"] < 0 else ''
            styles[cols.index("Cena")], styles[cols.index("Změna %")] = c, c
        return styles

    # Náhrada applymap za map (pro nové verze Pandas)
    st.dataframe(
        df_m.style.apply(apply_m_style, axis=1)
        .map(lambda v: 'background-color: #ffcccc' if isinstance(v, (int,float)) and v > 100 else '', subset=["P/E", "Dluh D/E %"])
        .background_gradient(subset=['Score'], cmap='RdYlGn').format(precision=1),
        use_container_width=True, hide_index=True, column_order=cols
    )

if show_calendar and not df_c.empty:
    st.markdown("### 📅 Kalendář událostí")
    def style_cal(row):
        styles = [''] * len(row)
        if 0 <= row["Dní"] <= 14: styles[1] = 'background-color: #ffeeba; font-weight: bold'
        if isinstance(row["Ex-Date"], date) and row["Ex-Date"] >= date.today(): 
            styles[4] = 'color: #007bff; font-weight: bold'
        return styles
    st.dataframe(df_c.style.apply(style_cal, axis=1), use_container_width=True, hide_index=True)
