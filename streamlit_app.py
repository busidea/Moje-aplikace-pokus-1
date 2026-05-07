import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import numpy as np

st.set_page_config(page_title="Investiční Matrix V74", layout="wide")

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

# --- 2. SIDEBAR (VÝCHOZÍ ANALYTICKÉ NASTAVENÍ) ---
st.sidebar.header("🔍 Globální filtry")
filtr_kat = st.sidebar.selectbox("Zobrazit tituly:", ["Vše", "Portfolio", "Sledované"], index=1)
show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=False)

st.sidebar.divider()
st.sidebar.header("⚖️ Váhy kategorií")
# Upravené váhy - Riziko a Rentabilita mají vyšší prioritu
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.2)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.5)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.8)

def vytvor_p(nazev, zk, def_h, def_b):
    with st.sidebar.expander(f"📊 {nazev}", expanded=False):
        d = []
        for i in range(5):
            c1, c2 = st.columns(2)
            h = c1.number_input(f"Do:", value=float(def_h[i]), key=f"{zk}_{i}")
            b = c2.number_input(f"Body", value=int(def_b[i]), key=f"{zk}_{i}b")
            d.append({"h": h, "b": b})
        return d

# ANALYTICKÁ KALIBRACE ROZMEZÍ A BODŮ
p_pe = vytvor_p("P/E", "pe", [15, 20, 30, 45, 999], [15, 10, 5, 0, -10])
p_ps = vytvor_p("P/S", "ps", [1.5, 3, 6, 10, 999], [10, 7, 3, 0, -5])
p_pb = vytvor_p("P/B", "pb", [1.2, 3, 5, 10, 999], [10, 5, 2, 0, -5])
p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 22, 35, 50, 999], [15, 10, 5, 0, -10])
p_gm = vytvor_p("H-Marže", "gm", [15, 30, 45, 65, 999], [0, 5, 10, 15, 20])
p_gm3y = vytvor_p("H-Marže 3Y", "gm3y", [15, 30, 45, 65, 999], [0, 5, 10, 15, 20])
p_nm = vytvor_p("Č-Marže", "nm", [8, 15, 25, 40, 999], [0, 5, 12, 18, 25])
p_nm3y = vytvor_p("Č-Marže 3Y", "nm3y", [8, 15, 25, 40, 999], [0, 5, 10, 15, 20])
p_roe = vytvor_p("ROE", "roe", [10, 15, 25, 40, 999], [0, 5, 12, 18, 25])
p_roe3y = vytvor_p("ROE 3Y", "roe3y", [10, 15, 25, 40, 999], [0, 5, 10, 15, 20])
p_rev = vytvor_p("Tržby y/y", "rev", [0, 8, 15, 30, 999], [-5, 5, 12, 18, 20])
p_eps = vytvor_p("Zisk y/y", "eps", [0, 8, 20, 40, 999], [-10, 5, 15, 22, 25])
p_deb = vytvor_p("Dluh D/E", "deb", [40, 90, 150, 250, 999], [15, 10, 0, -10, -25])
p_div = vytvor_p("Div. výnos", "div", [1.5, 3, 5, 7, 999], [2, 6, 10, 12, 8]) # Příliš vysoká div. je podezřelá
p_pay = vytvor_p("Payout", "pay", [30, 60, 80, 95, 999], [5, 10, 5, -5, -20])
p_pot = vytvor_p("Potenciál", "pot", [5, 15, 25, 40, 999], [0, 5, 15, 25, 30])

def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. VÝPOČETNÍ JÁDRO ---
@st.cache_data(ttl=3600)
def fetch_v74(df_input, kat):
    if df_input.empty: return []
    df_active = df_input if kat == "Vše" else df_input[df_input['Kategorie'] == kat]
    results, today = [], date.today()
    for row in df_active.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        try:
            tick = yf.Ticker(t)
            inf, hist = tick.info, tick.history(period="1mo")
            rsi_txt = "Neznámo"
            if len(hist) > 14:
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
                rsi_txt = f"🔴 Překoup.({int(rsi)})" if rsi > 70 else (f"🟢 Levné({int(rsi)})" if rsi < 30 else f"⚪ Neutr.({int(rsi)})")
            dni_do, earn_str = 999, "Nezadáno"
            if pd.notnull(row.get('Earnings Day')):
                dt = pd.to_datetime(row['Earnings Day'], dayfirst=True)
                dni_do = (dt.date() - today).days
                earn_str = dt.strftime('%d.%m.%Y')
            results.append({"ticker": t, "info": inf, "rsi": rsi_txt, "earn_str": earn_str, "dni_do": dni_do})
        except: continue
    return results

raw_data = fetch_v74(df_raw, filtr_kat)

# --- 4. LOGIKA A ZOBRAZENÍ ---
if raw_data:
    mapping = {
        "P/E": (p_pe, w_val), "P/S": (p_ps, w_val), "P/B": (p_pb, w_val), "P/FCF": (p_pfcf, w_val),
        "H-Marže": (p_gm, w_prof), "H-Marže 3Y": (p_gm3y, w_prof), "Č-Marže": (p_nm, w_prof), "Č-Marže 3Y": (p_nm3y, w_prof),
        "ROE": (p_roe, w_prof), "ROE 3Y": (p_roe3y, w_prof), "Tržby y/y": (p_rev, w_growth), "Zisk y/y": (p_eps, w_growth),
        "Div. výnos": (p_div, w_growth), "Potenciál": (p_pot, w_growth), "Dluh D/E": (p_deb, w_risk), "Payout": (p_pay, w_risk)
    }

    m_rows, c_rows, today = [], [], date.today()
    for item in raw_data:
        inf, t = item["info"], item["ticker"]
        def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
        
        d = {"Ticker": t, "Cena": g("currentPrice"), "Změna": ((g("currentPrice")/g("previousClose", 1))-1)*100, "Type": "Val"}
        d.update({
            "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), "P/B": g("priceToBook"),
            "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
            "H-Marže": g("grossMargins", 100), "H-Marže 3Y": g("grossMargins", 94),
            "Č-Marže": g("profitMargins", 100), "Č-Marže 3Y": g("profitMargins", 91),
            "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
            "Tržby y/y": g("revenueGrowth", 100), "Zisk y/y": g("earningsGrowth", 100),
            "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Payout": g("payoutRatio", 100),
            "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0
        })
        pts = {k: get_b(d[k], mapping[k][0])*mapping[k][1] for k in mapping if k in d}
        d["Score"] = sum(pts.values())
        m_rows.append(d)
        if show_audit:
            a_row = {k: pts.get(k, 0) for k in mapping if k in pts}
            a_row.update({"Ticker": "└─ body", "Score": d["Score"], "Type": "Pts"})
            m_rows.append(a_row)

        ex_raw = inf.get('exDividendDate')
        ex_dt = datetime.fromtimestamp(ex_raw).date() if ex_raw else None
        rec = inf.get('recommendationKey', 'Nezadáno').replace('_', ' ').title()
        c_rows.append({
            "Ticker": t, "Earnings Day": item["earn_str"], "Dní do": item["dni_do"] if item["dni_do"] < 400 else "-",
            "Dividenda": f"{g('dividendRate'):.2f} {inf.get('currency', 'USD')}", 
            "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "Není",
            "Analytické hodnocení": f"📢 {rec}", "RSI": item["rsi"],
            "_alert_earn": 1 if 0 <= item["dni_do"] <= 14 else 0,
            "_alert_buy": 1 if "Strong Buy" in rec else 0,
            "_alert_ex": 1 if ex_dt and 0 <= (ex_dt - today).days <= 10 else 0
        })

    # --- ZOBRAZENÍ MATRIXU ---
    st.subheader(f"📊 Analytický Matrix ({filtr_kat})")
    df_m = pd.DataFrame(m_rows)
    cols = ["Ticker", "Cena", "Změna", "P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál", "Score"]
    
    def style_final(row):
        styles = [''] * len(row)
        if row["Type"] == "Pts": return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        if row["Změna"] > 0: styles[row.index.get_loc("Cena")] = styles[row.index.get_loc("Změna")] = 'color: #28a745; font-weight: bold'
        elif row["Změna"] < 0: styles[row.index.get_loc("Cena")] = styles[row.index.get_loc("Změna")] = 'color: #dc3545; font-weight: bold'
        # Mluvící barvy
        if row["P/E"] > 35: styles[row.index.get_loc("P/E")] = 'background-color: #ffe5e5'
        if row["Potenciál"] > 20: styles[row.index.get_loc("Potenciál")] = 'background-color: #e5f9e5; font-weight: bold'
        if row["Č-Marže"] > 20: styles[row.index.get_loc("Č-Marže")] = 'background-color: #d4edda'
        if row["Dluh D/E"] > 150: styles[row.index.get_loc("Dluh D/E")] = 'background-color: #fff3cd'
        return styles

    st.dataframe(df_m.style.apply(style_final, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn").format({c: "{:.1f}%" for c in ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Div. výnos", "Payout", "Potenciál"]}, precision=1), use_container_width=True, hide_index=True, column_order=cols)

    # --- ZOBRAZENÍ KALENDÁŘE ---
    st.subheader("📅 Kalendář & Sentiment")
    df_c = pd.DataFrame(c_rows)
    st.dataframe(df_c.style.apply(lambda row: [
        'background-color: #ffc107' if i=='Dní do' and row['_alert_earn'] else 
        'background-color: #28a745; color: white' if i=='Analytické hodnocení' and row['_alert_buy'] else
        'background-color: #007bff; color: white' if i=='Ex-Date' and row['_alert_ex'] else '' 
        for i in row.index], axis=1), use_container_width=True, hide_index=True, column_order=["Ticker", "Earnings Day", "Dní do", "Dividenda", "Ex-Date", "Analytické hodnocení", "RSI"])
