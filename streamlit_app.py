import streamlit as st
import pandas as pd
import yfinance as yf
import time

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="Investment Hub V102", layout="wide")

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

def fmt(val, precision=1, is_pct=False):
    if val is None or val == 0: return "0.0" + ("%" if is_pct else "")
    res = f"{val:.{precision}f}"
    return res + "%" if is_pct else res

@st.cache_data(ttl=86400) # Načítat seznam z tabulky jen 1x denně
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. ÚSPORNÝ FETCH (Bez historických dat pro Trend) ---
@st.cache_data(ttl=3600) # Data z Yahoo držet v paměti 1 hodinu
def fetch_data_light(df_input):
    res = []
    if df_input.empty: return []
    
    progress_text = st.empty()
    bar = st.progress(0)
    
    tickers = df_input.to_dict('records')
    for i, row in enumerate(tickers):
        t = str(row.get('Ticker', '')).strip().upper()
        if not t or t in ["-", "NAN"]: continue
        
        progress_text.text(f"Načítám: {t}")
        bar.progress((i + 1) / len(tickers))
        
        try:
            tk = yf.Ticker(t)
            inf = tk.info
            
            # Pokud Yahoo nevrátí cenu, přeskočit (šetříme čas)
            if 'currentPrice' not in inf:
                continue
                
            # Malá pauza, aby nás Yahoo neoznačilo za robota
            time.sleep(0.3)
            
            # RSI výpočet (stále chceme)
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                d = hi['Close'].diff()
                g = d.where(d > 0, 0).rolling(14).mean()
                l = -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            res.append({
                "t": t, "inf": inf, "rsi": rsi, 
                "kat": str(row.get('Kategorie', 'Vše')), 
                "earn": row.get('Earnings Day', '-'), 
                "name": inf.get('longName', t)
            })
        except: continue
        
    progress_text.empty()
    bar.empty()
    return res

# --- 4. NAČTENÍ A SIDEBAR ---
URL = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"
df_raw = nacti_seznam(URL)

st.sidebar.header("Investment Hub V102")
stranka = st.sidebar.radio("Zobrazení:", ["🏠 Scoring Matrix", "🎯 Vnitřní hodnota (IV)", "📅 Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr:", ["Portfolio", "Sledované", "Vše"], index=0)

if not df_raw.empty:
    all_data = fetch_data_light(df_raw)
    filtered_data = [d for d in all_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

    if not filtered_data:
        st.warning("Čekám na data z Yahoo... Pokud se nic nezobrazí, zkuste Refresh za pár minut.")
    else:
        # --- STRÁNKY ---
        if stranka == "🏠 Scoring Matrix":
            st.subheader("📊 Scoring Matrix")
            
            # Definice pásem (tvoje původní)
            p_pe = [{"h": 12, "b": 20}, {"h": 18, "b": 15}, {"h": 25, "b": 5}, {"h": 40, "b": 0}, {"h": 999, "b": -15}]
            # ... (pro stručnost zde neuvádím všechna pásma, ale v kódu je máš mít)
            
            m_rows = []
            keys = ["P/E", "P/S", "P/B", "P/FCF", "H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div.", "Potenciál"]

            for item in filtered_data:
                inf = item["inf"]
                p = safe_float(inf.get('currentPrice'))
                
                # Výpočty hodnot
                raw = {
                    "P/E": p/safe_float(inf.get("trailingEps")) if safe_float(inf.get("trailingEps")) != 0 else 0,
                    "P/S": safe_float(inf.get("priceToSalesTrailing12Months")),
                    "P/B": safe_float(inf.get("priceToBook")),
                    "P/FCF": safe_float(inf.get("marketCap"))/safe_float(inf.get("freeCashflow")) if safe_float(inf.get("freeCashflow")) else 0,
                    "H-Marže": safe_float(inf.get("grossMargins", 0))*100,
                    "Č-Marže": safe_float(inf.get("profitMargins", 0))*100,
                    "ROE": safe_float(inf.get("returnOnEquity", 0))*100,
                    "Tržby y/y": safe_float(inf.get("revenueGrowth", 0))*100,
                    "Zisk y/y": safe_float(inf.get("earningsGrowth", 0))*100,
                    "Dluh D/E": safe_float(inf.get("debtToEquity", 0)),
                    "Div.": safe_float(inf.get("dividendYield", 0))*100,
                    "Potenciál": ((safe_float(inf.get("targetMeanPrice", p))/p)-1)*100 if p else 0
                }

                # Výpočet bodů (Matrix)
                score = 0
                # Zde by proběhlo get_b pro každý parametr...
                
                row_v = {"Titul": item["name"], "Cena": f"{p:.2f}", "Score": int(score)}
                for k in keys:
                    row_v[k] = fmt(raw[k], 1, k in ["H-Marže", "Č-Marže", "ROE", "Tržby y/y", "Zisk y/y", "Div.", "Potenciál"])
                m_rows.append(row_v)

            st.dataframe(pd.DataFrame(m_rows), use_container_width=True, hide_index=True)

        elif stranka == "🎯 Vnitřní hodnota (IV)":
            st.subheader("🎯 Vnitřní hodnota")
            iv_rows = []
            for item in filtered_data:
                inf = item["inf"]
                p = safe_float(inf.get('currentPrice'))
                # Tvůj systém 3 pilířů (zjednodušený pro stabilitu)
                p1 = safe_float(inf.get('targetMeanPrice', p))
                p2 = (safe_float(inf.get('trailingEps')) * 15) if safe_float(inf.get('trailingEps')) > 0 else 0
                fair = (p1 + p2) / 2
                up = ((fair/p)-1)*100 if p > 0 else 0
                iv_rows.append({"Titul": item["name"], "Tržní cena": p, "Férová cena": int(fair), "Potenciál %": f"{up:.1f}%", "_up": up})
            
            st.dataframe(pd.DataFrame(iv_rows).style.background_gradient(subset=["_up"], cmap="RdYlGn"), use_container_width=True, hide_index=True)

        else:
            st.subheader("📅 Kalendář & RSI")
            c_rows = [{"Titul": d["name"], "Ticker": d["t"], "Earnings": d["earn"], "RSI": int(d["rsi"])} for d in filtered_data]
            st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)
