import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import numpy as np

st.set_page_config(page_title="Investiční Matrix V71", layout="wide")

# --- 1. NAČTENÍ SEZNAMU ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

if st.sidebar.button("🔄 Vynutit aktualizaci z tabulky"):
    st.cache_data.clear()
    st.rerun()

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

# --- 2. SIDEBAR ---
st.sidebar.header("🔍 Globální filtry")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"], index=1)
show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=False) # Defaultně vypnuto pro čistý pohled

st.sidebar.divider()
st.sidebar.header("⚖️ Váhy kategorií")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# Definice parametrů
p_pe = vytvor_p("P/E", "pe", [15, 25, 35, 50, 999], [15, 10, 5, 0, -5])
p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
p_pb = vytvor_p("P/B", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
p_gm = vytvor_p("H-Marže", "gm", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_gm3y = vytvor_p("H-Marže 3Y", "gm3y", [10, 25, 40, 60, 999], [0, 5, 10, 15, 20])
p_nm = vytvor_p("Č-Marže", "nm", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_nm3y = vytvor_p("Č-Marže 3Y", "nm3y", [5, 10, 20, 30, 999], [0, 5, 10, 15, 20])
p_roe = vytvor_p("ROE", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_roe3y = vytvor_p("ROE 3Y", "roe3y", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
p_rev = vytvor_p("Tržby y/y", "rev", [0, 5, 10, 20, 999], [-5, 2, 7, 12, 18])
p_eps = vytvor_p("Zisk y/y", "eps", [0, 5, 15, 25, 999], [-5, 2, 8, 15, 25])
p_deb = vytvor_p("Dluh D/E", "deb", [50, 100, 150, 250, 999], [15, 10, 5, 0, -10])
p_div = vytvor_p("Div. výnos", "div", [1, 2, 4, 6, 999], [2, 5, 8, 10, 12])
p_pay = vytvor_p("Payout", "pay", [20, 50, 75, 90, 999], [5, 10, 5, 0, -10])
p_pot = vytvor_p("Potenciál", "pot", [0, 10, 20, 35, 999], [-5, 0, 10, 20, 30])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. VÝPOČETNÍ JÁDRO (Pouze data z Yahoo) ---
@st.cache_data(ttl=3600)
def fetch_v71(df_input, kat):
    if df_input.empty: return []
    df_active = df_input if kat == "Vše" else df_input[df_input['Kategorie'] == kat]
    
    results = []
    today = date.today()
    
    for idx, row in enumerate(df_active.to_dict('records')):
        t = str(row.get('Ticker', '')).strip().upper()
        try:
            tick = yf.Ticker(t)
            inf = tick.info
            hist = tick.history(period="1mo")
            
            # RSI
            rsi_status = "Neznámo"
            if len(hist) > 14:
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs.iloc[-1]))
                rsi_status = f"🔴 Překoup.({int(rsi)})" if rsi > 70 else (f"🟢 Levné({int(rsi)})" if rsi < 30 else f"⚪ Neutr.({int(rsi)})")

            # Earnings
            dni_do_num, earn_str = 999, "Nezadáno"
            if pd.notnull(row.get('Earnings Day')):
                dt = pd.to_datetime(row['Earnings Day'], dayfirst=True)
                dni_do_num = (dt.date() - today).days
                earn_str = dt.strftime('%d.%m.%Y') if dni_do_num >= 0 else f"Expirace ({dt.strftime('%d.%m.')})"

            results.append({
                "ticker": t, "info": inf, "rsi": rsi_status, 
                "earn_str": earn_str, "dni_do": dni_do_num
            })
        except: continue
    return results

# --- 4. ZPRACOVÁNÍ A ZOBRAZENÍ ---
raw_data = fetch_v71(df_raw, filtr_kat)

if raw_data:
    mapping = {
        "P/E": (p_pe, w_val), "P/S": (p_ps, w_val), "P/B": (p_pb, w_val), "P/FCF": (p_pfcf, w_val),
        "H-Marže": (p_gm, w_prof), "H-Marže 3Y": (p_gm3y, w_prof), "Č-Marže": (p_nm, w_prof), "Č-Marže 3Y": (p_nm3y, w_prof),
        "ROE": (p_roe, w_prof), "ROE 3Y": (p_roe3y, w_prof), "Tržby y/y": (p_rev, w_growth), "Zisk y/y": (p_eps, w_growth),
        "Div. výnos": (p_div, w_growth), "Potenciál": (p_pot, w_growth), "Dluh D/E": (p_deb, w_risk), "Payout": (p_pay, w_risk)
    }

    m_rows, c_rows = [], []
    today = date.today()

    for item in raw_data:
        inf = item["info"]
        t = item["ticker"]
        def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
        
        # Matrix Data
        d = {
            "Ticker": t, "Cena": g("currentPrice"), "Změna": ((g("currentPrice")/g("previousClose", 1))-1)*100,
            "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), "P/B": g("priceToBook"),
            "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
            "H-Marže": g("grossMargins", 100), "H-Marže 3Y": g("grossMargins", 94),
            "Č-Marže": g("profitMargins", 100), "Č-Marže 3Y": g("profitMargins", 91),
            "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
            "Tržby y/y": g("revenueGrowth", 100), "Zisk y/y": g("earningsGrowth", 100),
            "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Payout": g("payoutRatio", 100),
            "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
            "Type": "Val"
        }
        pts = {k: get_b(d[k], mapping[k][0])*mapping[k][1] for k in d if k in mapping}
        d["Score"] = sum(pts.values())
        m_rows.append(d)
        
        # Klíčová oprava: Body přidáváme jen pokud je checkbox ZAŠKRTNUTÝ
        if show_audit:
            a_row = {k: pts.get(k, 0) for k in d if k in mapping}
            a_row.update({"Ticker": "└─ body", "Score": d["Score"], "Type": "Pts"})
            m_rows.append(a_row)

        # Kalendář Data
        rec = inf.get('recommendationKey', 'Nezadáno').replace('_', ' ').title()
        ex_raw = inf.get('exDividendDate')
        ex_str = datetime.fromtimestamp(ex_raw).date().strftime('%d.%m.%Y') if ex_raw else "Není"
        
        c_rows.append({
            "Ticker": t, "Earnings Day": item["earn_str"], "Dní do": item["dni_do"] if item["dni_do"] < 400 else "-",
            "Dividenda": f"{g('dividendRate'):.2f} {'Kč' if inf.get('currency')=='CZK' else 'USD'}", "Ex-Date": ex_str,
            "Analytické hodnocení": f"📢 {rec}", "RSI": item["rsi"],
            "_alert_earn": 1 if (0 <= item["dni_do"] <= 14 or item["dni_do"] < 0) else 0,
            "_alert_buy": 1 if "Strong Buy" in rec else 0,
            "_alert_ex": 1 if ex_raw and 0 <= (datetime.fromtimestamp(ex_raw).date() - today).days <= 10 else 0
        })

    # Zobrazení Matrixu
    df_m = pd.DataFrame(m_rows)
    cols = ["Ticker", "Cena", "Změna", "P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál", "Score"]
    pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Div. výnos", "Payout", "Potenciál"]
    
    st.subheader(f"📊 Matrix Tržních Hodnot ({filtr_kat})")
    st.dataframe(df_m.style.apply(lambda row: ['background-color: #f8f9fa; color: #adb5bd; font-style: italic' if row["Type"]=="Pts" else '' for _ in row], axis=1)
                 .background_gradient(subset=["Score"], cmap="RdYlGn")
                 .format({c: "{:.1f}%" for c in pct_cols}, precision=1), 
                 use_container_width=True, hide_index=True, column_order=cols)

    # Zobrazení Kalendáře
    df_c = pd.DataFrame(c_rows)
    st.subheader("📅 Kalendář & Tržní Sentiment")
    st.dataframe(df_c.style.apply(lambda df: pd.DataFrame(
        np.where(df.columns == 'Dní do', np.where(df_c['_alert_earn']==1, 'background-color: #ffc107; color: black', ''),
        np.where(df.columns == 'Analytické hodnocení', np.where(df_c['_alert_buy']==1, 'background-color: #28a745; color: white', ''),
        np.where(df.columns == 'Ex-Date', np.where(df_c['_alert_ex']==1, 'background-color: #007bff; color: white', ''), ''))),
        index=df.index, columns=df.columns), axis=None), 
        use_container_width=True, hide_index=True, 
        column_order=["Ticker", "Earnings Day", "Dní do", "Dividenda", "Ex-Date", "Analytické hodnocení", "RSI"])
