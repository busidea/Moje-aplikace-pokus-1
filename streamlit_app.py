import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime

# --- 1. GLOBÁLNÍ KONFIGURACE (Čistý vizuál přes celou plochu) ---
st.set_page_config(page_title="Investment Hub V106 - Ultimate", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 0.5rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { text-align: left !important; font-weight: bold !important; color: #1f4e79 !important; }
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_f(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def get_b(val, pasma):
    if val is None or val == 0: return 0
    # Pro ukazatele jako P/E, P/S (čím nižší, tím lepší)
    # Tato funkce předpokládá vzestupná pásma v nastavení
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

@st.cache_data(ttl=86400)
def nacti_seznam(odkaz):
    try:
        u = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(u)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. KOMPLETNÍ DATA FETCH (Stabilní hloubková analýza) ---
@st.cache_data(ttl=3600)
def fetch_complete_data(df_in):
    res = []
    if df_in.empty: return []
    bar = st.progress(0); msg = st.empty()
    ticks = df_in.to_dict('records')
    
    for i, row in enumerate(ticks):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t == "NAN": continue
        msg.text(f"Hloubková analýza: {t}")
        bar.progress((i + 1) / len(ticks))
        try:
            tk = yf.Ticker(t); inf = tk.info; time.sleep(0.5)
            fin = tk.financials; bs = tk.balance_sheet
            
            # Výpočet 3Y průměrů pro fundamentální stabilitu
            a_roe, a_nm, a_gm = 0, 0, 0
            if not fin.empty and not bs.empty:
                try:
                    rev = fin.get('Total Revenue', pd.Series()); ni = fin.get('Net Income', pd.Series())
                    gp = fin.get('Gross Profit', pd.Series()); eq = bs.get('Stockholders Equity', pd.Series())
                    if not rev.empty and not ni.empty: a_nm = (ni / rev).head(3).mean() * 100
                    if not rev.empty and not gp.empty: a_gm = (gp / rev).head(3).mean() * 100
                    if not ni.empty and not eq.empty: a_roe = (ni / eq.head(len(ni))).head(3).mean() * 100
                except: pass

            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff(); g = d.where(d>0,0).rolling(14).mean(); l = -d.where(d<0,0).rolling(14).mean()
                rsi = 100-(100/(1+(g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            res.append({
                "t": t, "inf": inf, "rsi": rsi, "kat": str(row.get('Kategorie', 'Vše')), 
                "earn": str(row.get('Earnings Day', '-')), "name": inf.get('longName', t),
                "a_roe": a_roe, "a_nm": a_nm, "a_gm": a_gm, "moat": str(row.get('Moat', '-'))
            })
        except: continue
    msg.empty(); bar.empty()
    return res

# --- 4. SIDEBAR OVLÁDÁNÍ ---
URL = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(URL)

st.sidebar.title("💎 INVESTMENT HUB V106")
stranka = st.sidebar.radio("Navigace:", ["🏠 Scoring Matrix", "🎯 Vnitřní Hodnota", "📅 Kalendář & RSI"])
filtr = st.sidebar.selectbox("Zobrazit skupinu:", ["Portfolio", "Sledované", "Vše"])

# Nastavení bodování pro 16 ukazatelů
st.sidebar.subheader("⚙️ Parametry Scoringu")
show_p = st.sidebar.checkbox("Rozbalit řádky s body", value=False)

ukazatele = [
    "P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "ROA", 
    "Růst Tržeb", "Růst Zisku", "Dluh D/E", "Likvidita", "Div. Výnos", "Div. Payout", "Potenciál", "RSI"
]

p_map = {}
for u in ukazatele:
    with st.sidebar.expander(f"Nastavení: {u}"):
        # Výchozí hodnoty se liší podle typu ukazatele (konzervativní odhad)
        def_h = [15, 25, 40, 60, 999] if u in ["P/E", "P/FCF"] else [10, 20, 30, 40, 999]
        p_map[u] = [{"h": st.number_input(f"{u} limit {j}", value=float(def_h[j]), key=f"{u}{j}"), 
                     "b": st.number_input(f"{u} body {j}", value=20-j*5, key=f"{u}b{j}")} for j in range(5)]

# --- 5. LOGIKA A ZOBRAZENÍ ---
if not df_raw.empty:
    all_d = fetch_complete_data(df_raw)
    f_d = [d for d in all_d if filtr == "Vše" or d["kat"] == filtr]

    if stranka == "🏠 Scoring Matrix":
        rows = []
        for d in f_d:
            inf = d["inf"]; p = safe_f(inf.get('currentPrice'))
            v = {
                "P/E": p/safe_f(inf.get("trailingEps")) if safe_f(inf.get("trailingEps")) != 0 else 0,
                "P/S": safe_f(inf.get("priceToSalesTrailing12Months")),
                "P/B": safe_f(inf.get("priceToBook")),
                "P/FCF": safe_f(inf.get("marketCap"))/safe_f(inf.get("freeCashflow")) if safe_f(inf.get("freeCashflow")) else 0,
                "H-Marže": d["a_gm"] if d["a_gm"] != 0 else safe_f(inf.get("grossMargins", 0))*100,
                "Č-Marže": d["a_nm"] if d["a_nm"] != 0 else safe_f(inf.get("profitMargins", 0))*100,
                "ROE": d["a_roe"] if d["a_roe"] != 0 else safe_f(inf.get("returnOnEquity", 0))*100,
                "ROA": safe_f(inf.get("returnOnAssets", 0))*100,
                "Růst Tržeb": safe_f(inf.get("revenueGrowth", 0))*100,
                "Růst Zisku": safe_f(inf.get("earningsGrowth", 0))*100,
                "Dluh D/E": safe_f(inf.get("debtToEquity", 0)),
                "Likvidita": safe_f(inf.get("currentRatio", 0)),
                "Div. Výnos": safe_f(inf.get("dividendYield", 0))*100,
                "Div. Payout": safe_f(inf.get("payoutRatio", 0))*100,
                "Potenciál": ((safe_f(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0,
                "RSI": d["rsi"]
            }
            # Sumace score
            sc = sum([get_b(v[u], p_map[u]) for u in ukazatele])
            
            main_r = {"Společnost": d["name"], "Ticker": d["t"], "Cena": f"{p:.2f}", "Score": int(sc)}
            point_r = {"Společnost": f"   └ body ({d['t']})"}
            for u in ukazatele:
                main_r[u] = f"{v[u]:.1f}" + ("%" if any(x in u for x in ["Marže", "ROE", "ROA", "Růst", "Výnos", "Potenciál"]) else "")
                point_r[u] = str(get_b(v[u], p_map[u]))
            
            rows.append(main_r)
            if show_p: rows.append(point_r)

        df_m = pd.DataFrame(rows)
        cols = ["Společnost", "Ticker", "Cena"] + ukazatele + ["Score"]
        st.dataframe(df_m.style.background_gradient(subset=["Score"], cmap="RdYlGn", vmin=50, vmax=180)
                     .map(lambda x: 'color: #2ecc71; font-weight: bold' if x and not str(x).startswith(" ") else '', subset=["Cena"]), 
                     use_container_width=True, hide_index=True, column_order=cols)

    elif stranka == "🎯 Vnitřní Hodnota":
        iv_rows = []
        for d in f_d:
            inf = d["inf"]; p = safe_f(inf.get('currentPrice'))
            eps = safe_f(inf.get('trailingEps'))
            bvps = safe_f(inf.get('bookValue'))
            div_yield = safe_f(inf.get('dividendYield'))
            fcf = safe_f(inf.get('freeCashflow'))
            shares = safe_f(inf.get('sharesOutstanding', 1))
            
            metody = {}
            # 1. Analytici
            m_analyt = safe_f(inf.get('targetMeanPrice'))
            if m_analyt > 0: metody["Analytici"] = m_analyt
            
            # 2. Grahamovo číslo (Majetek + Zisk)
            if eps > 0 and bvps > 0:
                metody["Graham #"] = (22.5 * eps * bvps)**0.5
            
            # 3. Graham Růstová formule
            if eps > 0:
                metody["Graham Růst"] = eps * (8.5 + 2 * 5)
                
            # 4. DDM (Gordonův model - pouze pokud platí divi)
            if div_yield > 0:
                current_div = div_yield * p
                metody["DDM"] = current_div / (0.09 - 0.04) # r=9%, g=4%
                
            # 5. DCF (Zjednodušený Free Cash Flow model)
            if fcf > 0:
                metody["DCF"] = (fcf / shares) * 15 # 15x násobek FCF
            
            if metody:
                fair_price = sum(metody.values()) / len(metody)
                upside = ((fair_price / p) - 1) * 100 if p > 0 else 0
                
                # Seskupení do tvých 3 pilířů pro přehlednost
                pilir1 = metody.get("Analytici", 0)
                pilir2 = (metody.get("Graham #", 0) + metody.get("Graham Růst", 0)) / (sum([1 for k in ["Graham #", "Graham Růst"] if k in metody]) or 1)
                pilir3 = (metody.get("DDM", 0) + metody.get("DCF", 0)) / (sum([1 for k in ["DDM", "DCF"] if k in metody]) or 1)
                
                iv_rows.append({
                    "Společnost": d["name"], "Tržní": p, 
                    "Pilíř I (Analyt)": int(pilir1), "Pilíř II (Zisk)": int(pilir2), "Pilíř III (Cash/Div)": int(pilir3), 
                    "Férová Cena": int(fair_price), "Potenciál %": f"{upside:.1f}%", "_up": upside, "Metod": len(metody)
                })
        
        df_iv = pd.DataFrame(iv_rows)
        st.dataframe(df_iv.style.background_gradient(subset=["_up"], cmap="RdYlGn"), 
                     use_container_width=True, hide_index=True, 
                     column_order=["Společnost", "Tržní", "Pilíř I (Analyt)", "Pilíř II (Zisk)", "Pilíř III (Cash/Div)", "Férová Cena", "Potenciál %", "Metod"])
        st.info("💡 **Legenda:** Pilíř I (Analytické cíle), Pilíř II (Grahamovy metody), Pilíř III (DDM a FCF modely). Férová cena je průměrem všech validních metod.")

    else:
        c_rows = []
        for d in f_d:
            dni = "-"
            try:
                diff = (datetime.strptime(d["earn"], "%d.%m.%Y") - datetime.now()).days
                dni = f"{diff} dní" if diff >= 0 else "Proběhlo"
            except: pass
            rec = d["inf"].get("recommendationKey", "N/A").replace("_", " ").title()
            c_rows.append({"Společnost": d["name"], "Earnings": d["earn"], "Dní do": dni, "RSI": int(d["rsi"]), "Analytici": rec, "Moat": d["moat"]})
        
        df_c = pd.DataFrame(c_rows)
        st.dataframe(df_c.style.map(lambda x: 'background-color: #2ecc71' if x in ['Buy', 'Strong Buy'] else ('background-color: #e74c3c' if x in ['Sell'] else ''), subset=['Analytici'])
                     .map(lambda x: 'background-color: #ffeb3b; color: black' if x < 30 else ('background-color: #ff9800; color: white' if x > 70 else ''), subset=['RSI']), 
                     use_container_width=True, hide_index=True)
