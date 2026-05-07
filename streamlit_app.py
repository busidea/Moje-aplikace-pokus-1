import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V59", layout="wide")

# --- NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=600)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip()
        # ČIŠTĚNÍ TICKERŮ: Odstranění mezer a převod na velká písmena
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        
        if 'Earnings Day' in df.columns:
            # Robustnější převod data
            df['Earnings Day'] = pd.to_datetime(df['Earnings Day'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

df_seznam = nacti_seznam(ODKAZ_NA_TABULKU)

# --- SIDEBAR (Všech 16 ovladačů) ---
st.sidebar.header("🔍 Filtry a Zobrazení")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"])

st.sidebar.markdown("---")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=True)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# Definice pásem (P/E, Dluh, Potenciál...)
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb = vytvor_p("P/B", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_gm = vytvor_p("Hrubá marže", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_gm3y = vytvor_p("Hrubá marže 3Y", "gm3y", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_nm = vytvor_p("Čistá marže", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_nm3y = vytvor_p("Čistá marže 3Y", "nm3y", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_roe = vytvor_p("ROE", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_roe3y = vytvor_p("ROE 3Y", "roe3y", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_rev = vytvor_p("Růst tržeb y/y", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps = vytvor_p("Růst zisku y/y", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb = vytvor_p("Dluh D/E", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_div = vytvor_p("Div. výnos", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pay = vytvor_p("Výplatní poměr", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def fetch_all(df_list, kat_filtr):
    if df_list.empty: return pd.DataFrame(), pd.DataFrame()
    
    # Filtrování seznamu dle kategorie
    active_list = df_list if kat_filtr == "Vše" else df_list[df_list['Kategorie'] == kat_filtr]
    
    m_res, c_res = [], []
    today = date.today()
    pb = st.progress(0)
    
    mapping = {
        "P/E": (p_pe, w_val), "P/S": (p_ps, w_val), "P/B": (p_pb, w_val), "P/FCF": (p_pfcf, w_val),
        "Hrubá marže": (p_gm, w_prof), "Hrubá marže 3Y": (p_gm3y, w_prof), "Čistá marže": (p_nm, w_prof), "Čistá marže 3Y": (p_nm3y, w_prof),
        "ROE": (p_roe, w_prof), "ROE 3Y": (p_roe3y, w_prof), "Růst tržeb (y/y)": (p_rev, w_growth), "Růst zisku (y/y)": (p_eps, w_growth),
        "Div. výnos": (p_div, w_growth), "Potenciál": (p_pot, w_growth), "Dluh D/E": (p_deb, w_risk), "Výplatní poměr": (p_pay, w_risk)
    }

    for idx, row in enumerate(active_list.itertuples()):
        t = str(row.Ticker).strip().upper()
        try:
            tick = yf.Ticker(t)
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            # --- MATRIX DATA ---
            d = {
                "Ticker": t, "Cena": g("currentPrice"), "Změna %": ((g("currentPrice")/g("previousClose", 1))-1)*100,
                "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), "P/B": g("priceToBook"),
                "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
                "Hrubá marže": g("grossMargins", 100), "Hrubá marže 3Y": g("grossMargins", 94),
                "Čistá marže": g("profitMargins", 100), "Čistá marže 3Y": g("profitMargins", 91),
                "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
                "Růst tržeb (y/y)": g("revenueGrowth", 100), "Růst zisku (y/y)": g("earningsGrowth", 100),
                "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Výplatní poměr": g("payoutRatio", 100),
                "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
                "Type": "Val"
            }
            pts = {k: get_b(d[k], v[0])*v[1] for k, v in mapping.items() if k in d}
            score = sum(pts.values())
            d["Score"] = score
            m_res.append(d)
            
            if show_audit:
                a_row = {k: pts.get(k, 0) for k in d if k in mapping}
                a_row.update({"Ticker": "└─ body", "Score": score, "Type": "Pts"})
                m_res.append(a_row)

            # --- KALENDÁŘ DATA ---
            dni_do_val = 999
            earn_str = "Nezadáno"
            
            # Kontrola Earnings Day ze sloupce
            if hasattr(row, 'Earnings_Day') and pd.notnull(row.Earnings_Day):
                target_dt = row.Earnings_Day.date()
                dni_do_val = (target_dt - today).days
                if dni_do_val >= 0:
                    earn_str = target_dt.strftime('%d.%m.%Y')
                else:
                    earn_str = f"Proběhlo ({target_dt.strftime('%d.%m.')})"

            news_trigger = ""
            try:
                for n in tick.news[:5]:
                    if any(kw in n['title'].lower() for kw in ["earnings", "results", "report"]):
                        news_trigger = "🚨 News report"
                        break
            except: pass
            
            ex_d = inf.get('exDividendDate')
            ex_date_obj = datetime.fromtimestamp(ex_d).date() if ex_d else None
            
            c_res.append({
                "Ticker": t,
                "Earnings Day": earn_str,
                "Dní do": dni_do_val if 0 <= dni_do_val < 400 else "-",
                "Zprávy": news_trigger or "Klid",
                "Dividenda": f"{inf.get('dividendRate', 0):.2f} USD",
                "Ex-Date": ex_date_obj or "Není",
                "Highlight": 1 if 0 <= dni_do_val <= 14 or news_trigger != "" else 0
            })
        except Exception as e:
            st.error(f"Chyba u tickeru {t}: {e}")
            continue
        pb.progress((idx+1)/len(active_list))
    
    return pd.DataFrame(m_res), pd.DataFrame(c_res)

df_m, df_c = fetch_all(df_seznam, filtr_kat)

# --- VYKRESLENÍ ---
if not df_m.empty:
    st.subheader(f"📊 Matrix Tržních Hodnot ({filtr_kat})")
    cols = ["Ticker", "Cena", "Změna %", "P/E", "P/S", "P/B", "P/FCF", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb (y/y)", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Výplatní poměr", "Potenciál", "Score"]
    pct_cols = ["Změna %", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb (y/y)", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Výplatní poměr", "Potenciál"]

    def style_matrix(row):
        if row.get("Type") == "Pts": return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        stls = [''] * len(row)
        c = 'color: #28a745; font-weight: bold' if row["Změna %"] > 0 else 'color: #dc3545; font-weight: bold'
        stls[cols.index("Cena")], stls[cols.index("Změna %")] = c, c
        if row["P/E"] > 30: stls[cols.index("P/E")] = 'background-color: #ffe5e5; color: #cc0000'
        if row["Potenciál"] > 20: stls[cols.index("Potenciál")] = 'background-color: #28a745; color: white; font-weight: bold'
        return stls

    st.dataframe(df_m.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn").format({c: "{:.1f} %" for c in pct_cols}, precision=1), use_container_width=True, hide_index=True, column_order=cols)

if not df_c.empty:
    st.subheader("📅 Kalendář událostí")
    def style_calendar(row):
        if row["Highlight"] == 1: return ['background-color: #ffc107; color: black; font-weight: bold'] * len(row)
        return [''] * len(row)
    
    st.dataframe(df_c.style.apply(style_calendar, axis=1), use_container_width=True, hide_index=True, column_order=["Ticker", "Earnings Day", "Dní do", "Zprávy", "Dividenda", "Ex-Date"])
