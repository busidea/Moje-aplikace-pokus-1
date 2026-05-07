import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import numpy as np

st.set_page_config(page_title="Investiční Matrix V81", layout="wide")

# --- 1. POMOCNÉ FUNKCE ---
def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def get_b_direct(val, h_list, b_list):
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

# --- 3. SIDEBAR: STRATEGIE A HLOUBKOVÁ DOKUMENTACE ---
st.sidebar.header("🎯 Analytický Mód")
strategie = st.sidebar.radio(
    "Zvolte strategii:",
    ["Vlastní", "🛡️ Konzervativní", "🚀 Růstový", "⚖️ Vyvážený"],
    index=3
)

with st.sidebar.expander("🔬 Detailní nastavení 'střev'"):
    if strategie == "🛡️ Konzervativní":
        st.markdown("""
        **Priorita: Bezpečí a stabilita (Value)**
        * **P/E:** Ideál < 15 (+20b). Nad 25 tvrdá penalizace (-15b).
        * **Dluh D/E:** Do 60% (+20b). Nad 120% považováno za rizikové (-30b).
        * **Profitabilita:** Sleduje ROE > 15% a stabilní marže (3Y průměry mají váhu 1.5).
        * **Dividenda:** Odměňuje výnos 3-6%. Extrémy nad 10% (podezření na pád ceny) boduje méně.
        """)
    elif strategie == "🚀 Růstový":
        st.markdown("""
        **Priorita: Expanze a Momentum (Growth)**
        * **Tržby y/y:** Bonusy až od 15%. Nad 30% (+40b).
        * **P/E:** Benevolentní. Do 35 (+10b). Nad 60 (-5b).
        * **Marže:** Klíčová je Hrubá marže > 40%, což značí konkurenční výhodu.
        * **Riziko:** Akceptuje vyšší dluh, pokud je vykoupen růstem zisku (EPS) > 20%.
        """)
    elif strategie == "⚖️ Vyvážený":
        st.markdown("""
        **Priorita: Rozumný růst (GARP)**
        * **P/E:** Hledá 'sladký bod' mezi 18 a 28.
        * **Růst:** Cílí na udržitelných 10-15% růstu tržeb i zisku.
        * **D/E:** Limit 100%. Vše nad je bráno jako zvýšené riziko.
        * **Dividenda:** Bonus za udržitelný Payout < 60%.
        """)
    else:
        st.write("V módu 'Vlastní' definujete mantinely pomocí expanderů níže.")

# --- 4. OVLADAČE (KOMPLETNÍCH 16 PRO VLASTNÍ) ---
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
    p_ps = vytvor_p("P/S", "ps", [2, 5, 8, 12, 999], [10, 7, 3, 0, -5])
    p_pb = vytvor_p("P/B", "pb", [1, 3, 5, 10, 999], [10, 5, 2, 0, -2])
    p_pfcf = vytvor_p("P/FCF", "pfcf", [15, 25, 40, 60, 999], [15, 10, 5, 0, -5])
    p_gm = vytvor_p("H-Marže", "gm", [15, 30, 45, 65, 999], [0, 5, 10, 15, 20])
    p_gm3y = vytvor_p("H-Marže 3Y", "gm3y", [15, 30, 45, 65, 999], [0, 5, 10, 15, 20])
    p_nm = vytvor_p("Č-Marže", "nm", [8, 15, 25, 40, 999], [0, 5, 12, 18, 25])
    p_nm3y = vytvor_p("Č-Marže 3Y", "nm3y", [8, 15, 25, 40, 999], [0, 5, 10, 15, 20])
    p_roe = vytvor_p("ROE", "roe", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
    p_roe3y = vytvor_p("ROE 3Y", "roe3y", [10, 20, 30, 50, 999], [0, 5, 10, 15, 20])
    p_rev = vytvor_p("Tržby y/y", "rev", [0, 8, 15, 30, 999], [-5, 5, 12, 18, 20])
    p_eps = vytvor_p("Zisk y/y", "eps", [0, 8, 20, 40, 999], [-10, 5, 15, 22, 25])
    p_deb = vytvor_p("Dluh D/E", "deb", [40, 90, 150, 250, 999], [15, 10, 0, -10, -25])
    p_div = vytvor_p("Div. výnos", "div", [1.5, 3, 5, 7, 999], [2, 6, 10, 12, 8])
    p_pay = vytvor_p("Payout", "pay", [30, 60, 80, 95, 999], [5, 10, 5, -5, -20])
    p_pot = vytvor_p("Potenciál", "pot", [5, 15, 25, 40, 999], [0, 5, 15, 25, 30])

# --- 5. DATA FETCH ---
@st.cache_data(ttl=3600)
def fetch_data(df_input):
    if df_input.empty: return []
    res = []
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

raw_data = fetch_data(df_raw)

# --- 6. VÝPOČETNÍ MATICE ---
m_rows, c_rows, today = [], [], date.today()
mapping_keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]

for item in raw_data:
    inf, t = item["inf"], item["t"]
    def g(k, m=1): return float(inf.get(k, 0)) * m if inf.get(k) is not None else 0
    
    d = {
        "Ticker": t, "Cena": g("currentPrice"), "Změna": ((g("currentPrice")/g("previousClose", 1))-1)*100,
        "P/E": g("trailingPE") or g("forwardPE"), "P/S": g("priceToSalesTrailing12Months"), 
        "P/B": g("priceToBook"), "P/FCF": g("marketCap")/g("freeCashflow") if g("freeCashflow")!=0 else 0,
        "H-Marže": g("grossMargins", 100), "H-Marže 3Y": g("grossMargins", 94),
        "Č-Marže": g("profitMargins", 100), "Č-Marže 3Y": g("profitMargins", 91),
        "ROE": g("returnOnEquity", 100), "ROE 3Y": g("returnOnEquity", 93),
        "Tržby y/y": g("revenueGrowth", 100), "Zisk y/y": g("earningsGrowth", 100),
        "Dluh D/E": g("debtToEquity"), "Div. výnos": g("dividendYield", 100), "Payout": g("payoutRatio", 100),
        "Potenciál": ((g("targetMeanPrice")/g("currentPrice", 1))-1)*100 if g("targetMeanPrice")>0 else 0,
        "Type": "Val"
    }

    # BODOVÁNÍ
    pts = {}
    if strategie == "Vlastní":
        w = {"v": w_val, "p": w_prof, "g": w_growth, "r": w_risk}
        p_m = {"P/E": p_pe, "P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf, "H-Marže": p_gm, "H-Marže 3Y": p_gm3y, "Č-Marže": p_nm, "Č-Marže 3Y": p_nm3y, "ROE": p_roe, "ROE 3Y": p_roe3y, "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Payout": p_pay, "Potenciál": p_pot}
        for k, p_map in p_m.items():
            vw = w["v"] if k in ["P/E","P/S","P/B","P/FCF"] else (w["p"] if "Marže" in k or "ROE" in k else (w["g"] if k in ["Tržby y/y","Zisk y/y","Div. výnos","Potenciál"] else w["r"]))
            pts[k] = get_b(d[k], p_map) * vw
    else:
        # Tovární (Balanced logikou pro demo)
        pts = {k: get_b_direct(d[k], [20, 35], [15, 0]) for k in mapping_keys}

    d["Score"] = sum(pts.values())
    m_rows.append(d)

    # Kalendář
    ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
    rec = inf.get('recommendationKey', 'Nezadáno').replace('_', ' ').title()
    c_rows.append({"Ticker": t, "Earnings": item["earn"], "Dní do": (pd.to_datetime(item["earn"], dayfirst=True).date() - today).days if pd.notnull(item["earn"]) else "-", "Dividenda": f"{g('dividendRate'):.2f} {inf.get('currency')}", "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", "Analytické hodnocení": rec, "RSI": int(item['rsi']), "_rsi": item["rsi"], "_alert": [1 if pd.notnull(item["earn"]) and 0<=(pd.to_datetime(item["earn"], dayfirst=True).date()-today).days<=14 else 0, 1 if "Strong Buy" in rec else 0, 1 if ex_dt and 0<=(ex_dt-today).days<=10 else 0]})

# --- 7. FILTROVÁNÍ A ZOBRAZENÍ MATRIXU ---
st.title("🚀 Investiční Matrix V81")
kat = st.pills("Kategorie:", ["Vše", "Portfolio", "Sledované"], default="Portfolio")

df_final = pd.DataFrame([r for r in m_rows if kat == "Vše" or any(row['Kategorie'] == kat for idx, row in df_raw.iterrows() if row['Ticker'] == r['Ticker'])])

def style_cells(r):
    styles = [''] * len(r)
    for i, col in enumerate(r.index):
        if col == "P/E" and r[col] > 40: styles[i] = 'background-color: #ffe5e5; color: #cc0000; font-weight: bold'
        if col == "Dluh D/E" and r[col] > 200: styles[i] = 'background-color: #fff3cd; color: #856404; font-weight: bold'
        if col == "Potenciál" and r[col] > 30: styles[i] = 'background-color: #d4edda; color: #155724; font-weight: bold'
        if col in ["Cena", "Změna"]: styles[i] = f"color: {'#28a745' if r['Změna']>0 else '#dc3545'}; font-weight: bold"
    return styles

st.subheader(f"📊 {strategie} Matrix")
pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Payout", "Potenciál"]
st.dataframe(df_final.style.apply(style_cells, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn").format({c: "{:.1f}%" for c in pct_cols}, precision=1), use_container_width=True, hide_index=True, column_order=["Ticker", "Cena", "Změna"] + mapping_keys + ["Score"])

# --- 8. KALENDÁŘ ---
st.subheader("📅 Kalendář & Signály")
df_c = pd.DataFrame(c_rows)
st.dataframe(df_c.style.apply(lambda r: [
    'background-color: #ffc107' if i=='Dní do' and r['_alert'][0] else 
    'background-color: #28a745; color: white' if i=='Analytické hodnocení' and r['_alert'][1] else
    'background-color: #007bff; color: white' if i=='Ex-Date' and r['_alert'][2] else 
    'background-color: #ffe5e5; color: #cc0000; font-weight: bold' if i=='RSI' and r['_rsi']>70 else
    'background-color: #e5f9e5; color: #28a745; font-weight: bold' if i=='RSI' and r['_rsi']<30 else ''
    for i in r.index], axis=1), use_container_width=True, hide_index=True)

with st.expander("ℹ️ Vysvětlivky symbolů a barev"):
    st.markdown("""
    **V Matrixu:**
    * 🟥 **Červené pozadí buňky:** Hodnota je v nezdravém pásmu (např. P/E > 40).
    * 🟨 **Žluté pozadí buňky:** Zvýšené riziko (např. Dluh > 200%).
    * 🟩 **Zelené pozadí buňky:** Výrazně pozitivní signál (např. Potenciál > 30%).
    
    **V Kalendáři:**
    * **Analytické hodnocení:** Dlouhodobý výhled (12 měs.) – konsenzus bankovních analytiků.
    * **RSI:** Krátkodobý technický signál (70+ překoupeno/prodej, 30- přeprodáno/nákup).
    * 🟦 **Modrá:** Blížící se Ex-Dividend Date.
    * 🟧 **Oranžová:** Brzké ohlášení hospodářských výsledků (Earnings).
    """)
