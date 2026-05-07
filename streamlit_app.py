import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V48", layout="wide")

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

st.title("🏛️ Investiční Matrix V48")

# --- SIDEBAR ---
st.sidebar.header("⚖️ Globální Nastavení")
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

# --- PÁSMA (Seřazeno dle požadavku) ---
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
    tickery = list(db.keys())
    today = date.today()

    for idx, t in enumerate(tickery):
        try:
            tick = yf.Ticker(str(t).strip())
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            # --- MATRIX DATA ---
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
                "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                "Hrubá marže": g("grossMargins", 100), "Hrubá marže 3Y": g("grossMargins", 94),
                "Čistá marže": g("profitMargins", 100), "Čistá marže 3Y": g("profitMargins", 91),
                "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
                "Růst tržeb": g("revenueGrowth", 100), "Růst zisku": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Výpl. poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0
            }
            
            # Bodování
            pts = {
                "P/E": get_b(d["P/E"], p_pe)*w_val, "P/S": get_b(d["P/S"], p_ps)*w_val, "P/B": get_b(d["P/B"], p_pb)*w_val, "P/FCF": get_b(d["P/FCF"], p_pfcf)*w_val,
                "Hrubá marže": get_b(d["Hrubá marže"], p_gm)*w_prof, "Hrubá marže 3Y": get_b(d["Hrubá marže 3Y"], p_gm3y)*w_prof,
                "Čistá marže": get_b(d["Čistá marže"], p_nm)*w_prof, "Čistá marže 3Y": get_b(d["Čistá marže 3Y"], p_nm3y)*w_prof,
                "ROE": get_b(d["ROE"], p_roe)*w_prof, "ROE 3Y": get_b(d["ROE 3Y"], p_roe3y)*w_prof,
                "Růst tržeb": get_b(d["Růst tržeb"], p_rev)*w_growth, "Růst zisku": get_b(d["Růst zisku"], p_eps)*w_growth,
                "Div. výnos": get_b(d["Div. výnos"], p_div)*w_growth, "Potenciál": get_b(d["Potenciál"], p_pot)*w_growth,
                "Dluh D/E": get_b(d["Dluh D/E"], p_deb)*w_risk, "Výpl. poměr": get_b(d["Výpl. poměr"], p_pay)*w_risk
            }
            total_score = sum(pts.values())
            matrix_res.append({**d, "Score": total_score, "RowType": "Val", "SortKey": total_score})
            if s_audit:
                a_row = {k: pts.get(k, 0) for k in d if k in pts}
                a_row.update({"Ticker": "└─ pts", "Score": total_score, "RowType": "Pts", "SortKey": total_score - 0.001})
                matrix_res.append(a_row)

            # --- KALENDÁŘ DATA ---
            next_earn = None
            try:
                # Pokus č. 1: Standardní kalendář
                cal = tick.calendar
                if cal and 'Earnings Date' in cal:
                    next_earn = cal['Earnings Date'][0].date()
            except: pass
            
            ex_date = inf.get('exDividendDate')
            ex_date_fmt = datetime.fromtimestamp(ex_date).date() if ex_date else None
            days_to = (next_earn - today).days if next_earn else 999
            
            cal_res.append({
                "Ticker": t, "Next Earnings": next_earn or "Neznámé", "Dní": days_to,
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD", "Ex-Date": ex_date_fmt or "Není"
            })
        except: continue
        pb.progress((idx+1)/len(tickery))
    return pd.DataFrame(matrix_res), pd.DataFrame(cal_res)

df_m, df_c = fetch_all_data(moje_databaze, show_audit)

# --- ZOBRAZENÍ MATRIXU ---
if not df_m.empty:
    df_m = df_m.sort_values("SortKey", ascending=False)
    cols = ["Ticker"]
    if not hide_market: cols += ["Cena", "Změna %"]
    cols += ["P/E", "P/S", "P/B", "P/FCF", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb", "Dluh D/E", "Div. výnos", "Výpl. poměr", "Score"]
    
    def apply_m_style(row):
        styles = [''] * len(row)
        if row.RowType == "Pts": return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        if not hide_market:
            c = 'color: #28a745' if row["Změna %"] > 0 else 'color: #dc3545' if row["Změna %"] < 0 else ''
            styles[cols.index("Cena")], styles[cols.index("Změna %")] = c, c
        return styles

    st.dataframe(
        df_m.style.apply(apply_m_style, axis=1).background_gradient(subset=['Score'], cmap='RdYlGn').format(precision=1),
        use_container_width=True, hide_index=True, column_order=cols,
        column_config={c: st.column_config.Column(width="small") for c in cols}
    )

# --- ZOBRAZENÍ KALENDÁŘE ---
if show_calendar and not df_c.empty:
    st.markdown("### 📅 Kalendář událostí")
    st.dataframe(
        df_c.style.apply(lambda r: ['background-color: #fff3cd' if 0 <= r["Dní"] <= 14 else '' for _ in r], axis=1)
        .format({"Next Earnings": lambda x: x.strftime('%d.%m.%Y') if isinstance(x, date) else x}),
        use_container_width=True, hide_index=True
    )
