import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V64", layout="wide")

# --- 1. NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
        return df
    except: return pd.DataFrame()

df_raw = nacti_seznam(ODKAZ_NA_TABULKU)

# --- 2. SIDEBAR (Všech 16 ovladačů zachováno) ---
st.sidebar.header("🔍 Nastavení")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"])
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5)
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

# Definice pásem (zkráceno pro ukázku, v app nechte všech 16)
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

# --- 3. HLAVNÍ VÝPOČET ---
@st.cache_data(ttl=3600)
def fetch_v64(df_input, kat):
    if df_input.empty: return pd.DataFrame(), pd.DataFrame()
    df_active = df_input if kat == "Vše" else df_input[df_input['Kategorie'] == kat]
    
    m_list, c_list = [], []
    today = date.today()
    pb = st.progress(0)
    
    mapping = {
        "P/E": (p_pe, w_val), "P/S": (p_ps, w_val), "P/B": (p_pb, w_val), "P/FCF": (p_pfcf, w_val),
        "Hrubá marže": (p_gm, w_prof), "Hrubá marže 3Y": (p_gm3y, w_prof), "Čistá marže": (p_nm, w_prof), "Čistá marže 3Y": (p_nm3y, w_prof),
        "ROE": (p_roe, w_prof), "ROE 3Y": (p_roe3y, w_prof), "Růst tržeb (y/y)": (p_rev, w_growth), "Růst zisku (y/y)": (p_eps, w_growth),
        "Div. výnos": (p_div, w_growth), "Potenciál": (p_pot, w_growth), "Dluh D/E": (p_deb, w_risk), "Výplatní poměr": (p_pay, w_risk)
    }

    for idx, row in enumerate(df_active.to_dict('records')):
        t = str(row.get('Ticker', '')).strip().upper()
        
        # --- ZÁKLAD KALENDÁŘE ---
        dni_do_num = 999
        earn_str = "Nezadáno"
        raw_earn = row.get('Earnings Day')
        if pd.notnull(raw_earn):
            try:
                dt = pd.to_datetime(raw_earn, dayfirst=True)
                dni_do_num = (dt.date() - today).days
                earn_str = dt.strftime('%d.%m.%Y') if dni_do_num >= 0 else f"Expirace ({dt.strftime('%d.%m.')})"
            except: pass

        # --- YAHOO DATA ---
        try:
            tick = yf.Ticker(t)
            inf = tick.info
            def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
            
            # Matrix Data
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
            d["Score"] = sum(pts.values())
            m_list.append(d)
            if show_audit:
                a_row = {k: pts.get(k, 0) for k in d if k in mapping}
                a_row.update({"Ticker": "└─ body", "Score": d["Score"], "Type": "Pts"})
                m_list.append(a_row)

            # Kalendář doplňky
            news_w = ""
            try:
                for n in tick.news[:5]:
                    if any(kw in n['title'].lower() for kw in ["earnings", "results", "report"]):
                        news_w = "🚨 News report"
                        break
            except: pass
            
            div_val = inf.get('dividendRate') or inf.get('trailingAnnualDividendRate') or 0
            ex_date_val = datetime.fromtimestamp(inf.get('exDividendDate')).date().strftime('%d.%m.%Y') if inf.get('exDividendDate') else "Není"

            c_list.append({
                "Ticker": t, "Earnings Day": earn_str, 
                "Dní do": dni_do_num if dni_do_num < 400 else "-",
                "Zprávy": news_w or "Klid", "Dividenda": f"{div_val:.2f} USD",
                "Ex-Date": ex_date_val,
                "Alert": 1 if dni_do_num <= 14 or news_w != "" else 0
            })
        except:
            m_list.append({"Ticker": t, "Type": "Val", "Score": 0})
            c_list.append({"Ticker": t, "Earnings Day": earn_str, "Dní do": dni_do_num if dni_do_num < 400 else "-", "Zprávy": "Chyba", "Dividenda": "-", "Ex-Date": "-", "Alert": 0})
        
        pb.progress((idx+1)/len(df_active))
    return pd.DataFrame(m_list), pd.DataFrame(c_list)

df_m, df_c = fetch_v64(df_raw, filtr_kat)

# --- 4. ZOBRAZENÍ MATRIXU ---
if not df_m.empty:
    st.subheader(f"📊 Matrix Tržních Hodnot ({filtr_kat})")
    cols = ["Ticker", "Cena", "Změna %", "P/E", "P/S", "P/B", "P/FCF", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb (y/y)", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Výplatní poměr", "Potenciál", "Score"]
    pct_cols = ["Změna %", "Hrubá marže", "Hrubá marže 3Y", "Čistá marže", "Čistá marže 3Y", "ROE", "ROE 3Y", "Růst tržeb (y/y)", "Růst zisku (y/y)", "Dluh D/E", "Div. výnos", "Výplatní poměr", "Potenciál"]

    def style_matrix(row):
        if row.get("Type") == "Pts": return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        stls = [''] * len(row)
        color = 'color: #28a745; font-weight: bold' if row["Změna %"] > 0 else 'color: #dc3545; font-weight: bold'
        stls[cols.index("Cena")], stls[cols.index("Změna %")] = color, color
        if row["P/E"] > 30: stls[cols.index("P/E")] = 'background-color: #ffe5e5; color: #cc0000'
        if row["Potenciál"] > 20: stls[cols.index("Potenciál")] = 'background-color: #28a745; color: white; font-weight: bold'
        return stls

    st.dataframe(df_m.style.apply(style_matrix, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn").format({c: "{:.1f} %" for c in pct_cols}, precision=1), use_container_width=True, hide_index=True, column_order=cols)

# --- 5. ZOBRAZENÍ KALENDÁŘE (S cíleným barvením) ---
if not df_c.empty:
    st.subheader("📅 Kalendář událostí")
    
    def style_calendar_target(df):
        # Vytvoříme prázdnou tabulku stylů
        style_df = pd.DataFrame('', index=df.index, columns=df.columns)
        # Podmínka: Pokud je Alert == 1, obarvíme pouze sloupec "Dní do"
        # Používáme barvu #ffc107 (žlutá) pro varování
        mask = df['Alert'] == 1
        style_df.loc[mask, 'Dní do'] = 'background-color: #ffc107; color: black; font-weight: bold'
        # Pokud je hodnota záporná (Expirace), dáme červené písmo pro "Dní do"
        for idx, val in df['Dní do'].items():
            if isinstance(val, (int, float)) and val < 0:
                style_df.loc[idx, 'Dní do'] += '; color: #cc0000'
        return style_df

    st.dataframe(
        df_c.style.apply(style_calendar_target, axis=None),
        use_container_width=True, hide_index=True, 
        column_order=["Ticker", "Earnings Day", "Dní do", "Zprávy", "Dividenda", "Ex-Date"]
    )
