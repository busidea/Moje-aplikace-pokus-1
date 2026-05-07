import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import numpy as np

st.set_page_config(page_title="Investiční Matrix V76", layout="wide")

# --- 1. POMOCNÉ FUNKCE ---
def get_b(val, pasma):
    """Vrací body podle zadaných pásem (pro Vlastní nastavení)."""
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def get_b_direct(val, h_list, b_list):
    """Vrací body podle seznamů (pro Tovární nastavení)."""
    for h, b in zip(h_list, b_list):
        if val <= h: return b
    return b_list[-1]

# --- 2. NAČTENÍ SEZNAMU ---
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

# --- 3. SIDEBAR: STRATEGIE ---
st.sidebar.header("🎯 Strategické nastavení")
strategie = st.sidebar.radio(
    "Zvolte mód analýzy:",
    ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový", "⚖️ Vyvážený"],
    index=3 # Defaultně Vyvážený
)

# Definice vah a pásem podle strategie
if strategie == "Vlastní":
    st.sidebar.divider()
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

    p_pe = vytvor_p("P/E", "pe", [15, 20, 30, 45, 999], [15, 10, 5, 0, -10])
    p_nm = vytvor_p("Č-Marže", "nm", [8, 15, 25, 40, 999], [0, 5, 12, 18, 25])
    p_rev = vytvor_p("Tržby y/y", "rev", [0, 8, 15, 30, 999], [-5, 5, 12, 18, 20])
    p_deb = vytvor_p("Dluh D/E", "deb", [40, 90, 150, 250, 999], [15, 10, 0, -10, -25])
    p_div = vytvor_p("Div. výnos", "div", [1.5, 3, 5, 7, 999], [2, 6, 10, 12, 8])
    p_pot = vytvor_p("Potenciál", "pot", [5, 15, 25, 40, 999], [0, 5, 15, 25, 30])
else:
    # Tovární nastavení "napevno"
    if strategie == "🛡️ Konzervativní":
        weights = {"val": 2.0, "prof": 1.5, "grow": 0.5, "risk": 2.0}
    elif strategie == "🚀 Růstový":
        weights = {"val": 0.5, "prof": 1.2, "grow": 2.5, "risk": 0.8}
    else: # Vyvážený
        weights = {"val": 1.2, "grow": 1.2, "prof": 1.5, "risk": 1.5}

# --- 4. DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_v76(df_input):
    if df_input.empty: return []
    res, today = [], date.today()
    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip().upper()
        try:
            tk = yf.Ticker(t); inf = tk.info; hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d > 0, 0).rolling(14).mean(); l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g/l).iloc[-1]))
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": row.get('Kategorie'), "earn": row.get('Earnings Day')})
        except: continue
    return res

raw_data = fetch_v76(df_raw)
filtr_kat = st.sidebar.selectbox("Filtrovat:", ["Vše", "Portfolio", "Sledované"], index=1)
show_audit = st.sidebar.checkbox("Zobrazit body (Audit)", value=False)

# --- 5. VÝPOČET SCORE ---
m_rows, c_rows, today = [], [], date.today()
for item in raw_data:
    if filtr_kat != "Vše" and item["kat"] != filtr_kat: continue
    inf, t = item["inf"], item["t"]
    def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
    
    d = {
        "Ticker": t, "Cena": g("currentPrice"), "Změna": ((g("currentPrice")/g("previousClose", 1))-1)*100,
        "P/E": g("trailingPE") or g("forwardPE"), "Č-Marže": g("profitMargins", 100),
        "Tržby y/y": g("revenueGrowth", 100), "Dluh D/E": g("debtToEquity"),
        "Div. výnos": g("dividendYield", 100), "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
        "Type": "Val"
    }

    # Aplikace bodování podle zvolené strategie
    if strategie == "Vlastní":
        w = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}
        pts = {
            "P/E": get_b(d["P/E"], p_pe)*w["v"], "Č-Marže": get_b(d["Č-Marže"], p_nm)*w["p"],
            "Tržby y/y": get_b(d["Tržby y/y"], p_rev)*w["g"], "Dluh D/E": get_b(d["Dluh D/E"], p_deb)*w["r"],
            "Div. výnos": get_b(d["Div. výnos"], p_div)*w["g"], "Potenciál": get_b(d["Potenciál"], p_pot)*w["g"]
        }
    else:
        w = {"v": weights["val"], "p": weights["prof"], "g": weights["grow"], "r": weights["risk"]}
        if strategie == "🛡️ Konzervativní":
            pts = {
                "P/E": get_b_direct(d["P/E"], [12, 18, 25, 35], [20, 10, 0, -20])*w["v"],
                "Č-Marže": get_b_direct(d["Č-Marže"], [5, 10, 15, 25], [0, 5, 10, 20])*w["p"],
                "Tržby y/y": get_b_direct(d["Tržby y/y"], [2, 5, 10, 15], [0, 5, 10, 15])*w["g"],
                "Dluh D/E": get_b_direct(d["Dluh D/E"], [30, 60, 100, 150], [25, 15, 0, -30])*w["r"],
                "Div. výnos": get_b_direct(d["Div. výnos"], [1, 3, 5, 7], [0, 10, 15, 5])*w["g"],
                "Potenciál": get_b_direct(d["Potenciál"], [5, 15, 25, 40], [0, 5, 10, 15])*w["g"]
            }
        elif strategie == "🚀 Růstový":
            pts = {
                "P/E": get_b_direct(d["P/E"], [25, 35, 45, 60], [10, 5, 0, -10])*w["v"],
                "Č-Marže": get_b_direct(d["Č-Marže"], [10, 20, 30, 40], [0, 10, 20, 30])*w["p"],
                "Tržby y/y": get_b_direct(d["Tržby y/y"], [10, 25, 45, 70], [0, 15, 30, 50])*w["g"],
                "Dluh D/E": get_b_direct(d["Dluh D/E"], [100, 200, 300, 400], [10, 5, 0, -10])*w["r"],
                "Div. výnos": 0, # Růstového investora dividenda nezajímá
                "Potenciál": get_b_direct(d["Potenciál"], [10, 25, 40, 60], [0, 10, 25, 40])*w["g"]
            }
        else: # Vyvážený
            pts = {
                "P/E": get_b_direct(d["P/E"], [15, 22, 30, 45], [15, 10, 5, -10])*w["v"],
                "Č-Marže": get_b_direct(d["Č-Marže"], [8, 15, 25, 35], [0, 8, 15, 25])*w["p"],
                "Tržby y/y": get_b_direct(d["Tržby y/y"], [5, 12, 25, 40], [0, 10, 20, 30])*w["g"],
                "Dluh D/E": get_b_direct(d["Dluh D/E"], [50, 100, 150, 250], [15, 10, 0, -20])*w["r"],
                "Div. výnos": get_b_direct(d["Div. výnos"], [1, 3, 5, 7], [2, 7, 10, 5])*w["g"],
                "Potenciál": get_b_direct(d["Potenciál"], [5, 15, 30, 50], [0, 10, 20, 30])*w["g"]
            }

    d["Score"] = sum(pts.values())
    m_rows.append(d)
    if show_audit:
        a = {k: pts.get(k, 0) for k in pts}; a.update({"Ticker": "└─ body", "Score": d["Score"], "Type": "Pts"})
        m_rows.append(a)

    # Kalendář Row
    ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
    rec = inf.get('recommendationKey', 'Nezadáno').replace('_', ' ').title()
    c_rows.append({
        "Ticker": t, "Earnings": item["earn"], "Dní do": (pd.to_datetime(item["earn"], dayfirst=True).date() - today).days if pd.notnull(item["earn"]) else "-",
        "Dividenda": f"{g('dividendRate'):.2f} {inf.get('currency')}", "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-",
        "Analytické hodnocení": f"📢 {rec}", "RSI": f"{int(item['rsi'])}", "_rsi": item["rsi"],
        "_alert_earn": 1 if pd.notnull(item["earn"]) and 0 <= (pd.to_datetime(item["earn"], dayfirst=True).date() - today).days <= 14 else 0,
        "_alert_buy": 1 if "Strong Buy" in rec else 0, "_alert_ex": 1 if ex_dt and 0 <= (ex_dt - today).days <= 10 else 0
    })

# --- 6. ZOBRAZENÍ ---
st.subheader(f"📊 {strategie} Matrix")
df_m = pd.DataFrame(m_rows)
st.dataframe(df_m.style.apply(lambda r: ['background-color: #f8f9fa; color: #adb5bd' if r["Type"]=="Pts" else '' for _ in r], axis=1).background_gradient(subset=["Score"], cmap="RdYlGn").format("{:.1f}%", subset=["Změna", "Č-Marže", "Tržby y/y", "Div. výnos", "Potenciál"]), use_container_width=True, hide_index=True)

st.subheader("📅 Kalendář")
df_c = pd.DataFrame(c_rows)
st.dataframe(df_c.style.apply(lambda r: [
    'background-color: #ffc107' if i=='Dní do' and r['_alert_earn'] else 
    'background-color: #28a745; color: white' if i=='Analytické hodnocení' and r['_alert_buy'] else
    'background-color: #007bff; color: white' if i=='Ex-Date' and r['_alert_ex'] else 
    'background-color: #ffe5e5' if i=='RSI' and r['_rsi']>70 else
    'background-color: #e5f9e5' if i=='RSI' and r['_rsi']<30 else ''
    for i in r.index], axis=1), use_container_width=True, hide_index=True, column_order=["Ticker", "Earnings", "Dní do", "Dividenda", "Ex-Date", "Analytické hodnocení", "RSI"])
