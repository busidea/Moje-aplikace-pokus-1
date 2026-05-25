import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date
import requests
import time
import random

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 0rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { font-weight: bold !important; color: #004080 !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]: return 999
    try: return (pd.to_datetime(earn_val, dayfirst=True).date() - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. NAČTENÍ DAT S AUTENTIZACÍ YAHOO ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        df = pd.read_csv(odkaz.replace('/edit?usp=sharing', '/export?format=csv'))
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except Exception as e:
        st.error(f"Chyba tabulky: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def fetch_historical_averages(ticker_symbol, session, c_gm, c_nm, c_roe):
    try:
        tk = yf.Ticker(ticker_symbol, session=session)
        fin, bs = tk.financials, tk.balance_sheet
        gm_3y, nm_3y, roe_3y = c_gm, c_nm, c_roe
        
        if fin is not None and not fin.empty and 'Gross Profit' in fin.index and 'Total Revenue' in fin.index:
            v = [fin.loc['Gross Profit', r] / fin.loc['Total Revenue', r] for r in fin.columns[:3] if fin.loc['Total Revenue', r] > 0]
            if v: gm_3y = (sum(v) / len(v)) * 100
        if fin is not None and not fin.empty and 'Net Income' in fin.index and 'Total Revenue' in fin.index:
            v = [fin.loc['Net Income', r] / fin.loc['Total Revenue', r] for r in fin.columns[:3] if fin.loc['Total Revenue', r] > 0]
            if v: nm_3y = (sum(v) / len(v)) * 100
        if fin is not None and not fin.empty and bs is not None and not bs.empty and 'Net Income' in fin.index and 'Stockholders Equity' in bs.index:
            r = [ro for ro in fin.columns[:3] if ro in bs.columns]
            v = [fin.loc['Net Income', ro] / bs.loc['Stockholders Equity', ro] for ro in r if bs.loc['Stockholders Equity', ro] > 0]
            if v: roe_3y = (sum(v) / len(v)) * 100
        return safe_float(gm_3y), safe_float(nm_3y), safe_float(roe_3y)
    except: 
        return c_gm, c_nm, c_roe

@st.cache_data(ttl=3600)
def fetch_all_data(df_input):
    res, chyby = [], []
    if df_input.empty: return res
    
    # Inicializace čisté session a pokus o stažení autentizačních prvků přímo přes yfinance mechanismus
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    
    # Tento trik donutí yfinance interně vygenerovat platné cookies pro danou session
    try:
        yf.utils.get_html("https://fc.yahoo.com", session=session)
    except:
        pass

    for row in df_input.to_dict('records'):
        t = str(row.get('Ticker', '')).strip()
        if not t or t in ["-", "nan", "TICKER"]: continue
        
        time.sleep(0.3) # Bezpečný rozestup
        
        try:
            tk = yf.Ticker(t, session=session)
            inf = tk.info
            
            if not inf or 'longName' not in inf:
                chyby.append(f"{t}: Bez odezvy")
                continue
            
            hi = tk.history(period="1mo")
            rsi = 50
            if len(hi) > 14:
                hi.index = hi.index.tz_localize(None) if hi.index.tz is not None else hi.index
                d = hi['Close'].diff()
                g, l = d.where(d > 0, 0).rolling(14).mean(), -d.where(d < 0, 0).rolling(14).mean()
                rsi = 100 - (100 / (1 + (g.iloc[-1]/l.iloc[-1]))) if l.iloc[-1] != 0 else 50
            
            c_gm, c_nm, c_roe = safe_float(inf.get('grossMargins'))*100, safe_float(inf.get('profitMargins'))*100, safe_float(inf.get('returnOnEquity'))*100
            gm_3y, nm_3y, roe_3y = fetch_historical_averages(t, session, c_gm, c_nm, c_roe)
            
            res.append({"t": t, "inf": inf, "rsi": rsi, "kat": str(row.get('Kategorie')), "earn": row.get('Earnings Day'), "name": inf.get('longName', t), "gm_3y": gm_3y, "nm_3y": nm_3y, "roe_3y": roe_3y})
        except Exception as e:
            chyby.append(f"{t}: {e}")
            
    return res

# --- NAČTENÍ DAT SPUŠTĚNÍ ---
df_raw_list = nacti_seznam(ODKAZ_NA_TABULKU)
if df_raw_list.empty: st.stop()

with st.spinner("🔒 Generuji autorizační token Yahoo a stahuji data..."):
    raw_data = fetch_all_data(df_raw_list)

if not raw_data:
    st.error("❌ Yahoo Finance požadavky přes tento cloudový server jsou stále zablokované.")
    st.info("Zkus nyní vpravo nahoře kliknout na tři tečky -> **Clear cache** a poté **Rerun**. Vyčištění cache může vynutit změnu uzlu serveru.")
    st.stop()

# --- 4. SIDEBAR ---
stranka = st.sidebar.radio("Zobrazení:", ["Scoring Matrix", "Vnitřní hodnota (IV)", "Kalendář & RSI"])
filtr_kat = st.sidebar.selectbox("Filtr kategorií:", ["Portfolio", "Sledované", "Vše"], index=0)
filtered_data = [d for d in raw_data if filtr_kat == "Vše" or d["kat"] == filtr_kat]

# --- 5. STRÁNKY LOGIKA ---
if stranka == "Scoring Matrix":
    zobrazit_body = st.sidebar.checkbox(" Detailní body", value=False)
    p_pe = [{"h": 12, "b": 20}, {"h": 18, "b": 15}, {"h": 25, "b": 5}, {"h": 40, "b": 0}, {"h": 999, "b": -15}]
    p_ps = [{"h": 1.5, "b": 15}, {"h": 3, "b": 10}, {"h": 6, "b": 5}, {"h": 10, "b": 0}, {"h": 999, "b": -10}]
    p_pb = [{"h": 1, "b": 10}, {"h": 2.5, "b": 7}, {"h": 4, "b": 3}, {"h": 8, "b": 0}, {"h": 999, "b": -5}]
    p_pfcf = [{"h": 12, "b": 20}, {"h": 20, "b": 12}, {"h": 35, "b": 5}, {"h": 50, "b": 0}, {"h": 999, "b": -10}]
    p_gm = [{"h": 20, "b": 0}, {"h": 35, "b": 8}, {"h": 50, "b": 15}, {"h": 70, "b": 20}, {"h": 999, "b": 25}]
    p_nm = [{"h": 10, "b": 0}, {"h": 20, "b": 10}, {"h": 30, "b": 18}, {"h": 45, "b": 22}, {"h": 999, "b": 30}]
    p_roe = [{"h": 12, "b": 0}, {"h": 22, "b": 10}, {"h": 35, "b": 15}, {"h": 55, "b": 20}, {"h": 999, "b": 25}]
    p_rev = [{"h": 0, "b": -10}, {"h": 10, "b": 8}, {"h": 20, "b": 15}, {"h": 35, "b": 25}, {"h": 999, "b": 35}]
    p_eps = [{"h": 0, "b": -15}, {"h": 10, "b": 10}, {"h": 25, "b": 20}, {"h": 45, "b": 28}, {"h": 999, "b": 40}]
    p_deb = [{"h": 40, "b": 20}, {"h": 80, "b": 10}, {"h": 120, "b": 0}, {"h": 200, "b": -15}, {"h": 999, "b": -40}]
    p_div = [{"h": 2, "b": 5}, {"h": 4, "b": 12}, {"h": 6, "b": 15}, {"h": 8, "b": 10}, {"h": 999, "b": 5}]
    p_pot = [{"h": 8, "b": 0}, {"h": 18, "b": 10}, {"h": 28, "b": 18}, {"h": 45, "b": 25}, {"h": 999, "b": 35}]

    keys = ["P/E", "Forward P/E", "P/S", "P/B", "P/FCF", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    pct_cols = ["Změna", "H-Marže", "H-Marže 3Y", "Č-Marže", "Č-Marže 3Y", "ROE", "ROE 3Y", "Tržby y/y", "Zisk y/y", "Dluh D/E", "Div. výnos", "Potenciál"]
    m_rows = []

    for item in filtered_data:
        inf, t, name = item["inf"], item["t"], item["name"]
        def sg(k, m=1.0): v = inf.get(k); return float(v)*m if v is not None and str(v) != "None" else 0.0
        
        pe_tr = sg("trailingPE") or sg("forwardPE")
        pe_fwd = sg("forwardPE") or pe_tr
        dy = sg("dividendYield"); dy = dy*100 if 0 < dy < 0.2 else dy

        raw = {
            "Cena": sg("currentPrice"), "Změna": ((sg("currentPrice")/sg("previousClose", 1.0))-1)*100 if sg("previousClose") else 0,
            "P/E": pe_tr, "Forward P/E": pe_fwd, "P/S": sg("priceToSalesTrailing12Months"), "P/B": sg("priceToBook"),
            "P/FCF": sg("marketCap")/sg("freeCashflow") if sg("freeCashflow") else 0, "H-Marže": sg("grossMargins", 100),
            "H-Marže 3Y": item["gm_3y"], "Č-Marže": sg("profitMargins", 100), "Č-Marže 3Y": item["nm_3y"], "ROE": sg("returnOnEquity", 100),
            "ROE 3Y": item["roe_3y"], "Tržby y/y": sg("revenueGrowth", 100), "Zisk y/y": sg("earningsGrowth", 100), "Dluh D/E": sg("debtToEquity"),
            "Div. výnos": dy, "Potenciál": ((sg("targetMeanPrice")/sg("currentPrice", 1.0))-1)*100 if sg("targetMeanPrice") else 0
        }

        b_pe_pts = get_b(raw["P/E"], p_pe)
        if pe_tr > 0 and pe_fwd > 0:
            if pe_fwd / pe_tr > 1.05: b_pe_pts = (b_pe_pts * 0.5) - 10
            elif pe_fwd / pe_tr < 0.95: b_pe_pts = b_pe_pts * 1.25

        total = b_pe_pts
        row_p = {"Titul": f"    └ body ({t})", "Type": "Points", "P/E": float(int(round(b_pe_pts))), "Forward P/E": 0.0}
        p_map = {"P/S": p_ps, "P/B": p_pb, "P/FCF": p_pfcf, "H-Marže": p_gm, "H-Marže 3Y": p_gm, "Č-Marže": p_nm, "Č-Marže 3Y": p_nm, "ROE": p_roe, "ROE 3Y": p_roe, "Tržby y/y": p_rev, "Zisk y/y": p_eps, "Dluh D/E": p_deb, "Div. výnos": p_div, "Potenciál": p_pot}
        
        for k in keys:
            if k not in ["P/E", "Forward P/E"]:
                b = get_b(raw[k], p_map[k]); total += b; row_p[k] = float(int(round(b)))

        row_v = {"Titul": name, "Type": "Value", "Změna": raw["Změna"], "Cena": raw["Cena"], "Score": int(total)}
        for k in keys: row_v[k] = raw[k]
        m_rows.append(row_v)
        if zobrazit_body: m_rows.append(row_p)

    df = pd.DataFrame(m_rows)
    if not df.empty:
        def style_m(r):
            s = [''] * len(r)
            if r.get("Type") == "Points": return ['color: #888; font-style: italic; background-color: #f8f9fa'] * len(r)
            for i, col in enumerate(r.index):
                if col in ["Cena", "Změna"]: s[i] = f"color: {'#1b5e20' if r['Změna']>0 else '#b71c1c'}; font-weight: bold"
                if col == "Forward P/E" and r.get("P/E", 0) > 0 and r.get("Forward P/E", 0) > 0:
                    if r["Forward P/E"]/r["P/E"] > 1.05: s[i] = 'background-color: #ffebee; color: #b71c1c'
                    elif r["Forward P/E"]/r["P/E"] < 0.95: s[i] = 'background-color: #e8f5e9; color: #1b5e20'
            return s
        
        cf = {"Type": None, "Titul": st.column_config.TextColumn("Titul", width=180), "Cena": st.column_config.NumberColumn("Cena", format="%.2f"), "Změna": st.column_config.NumberColumn("Změna", format="%.1f%%"), "Score": st.column_config.NumberColumn("Score", format="%d")}
        for k in keys: cf[k] = st.column_config.NumberColumn(k, format="%.1f%%" if k in pct_cols else "%.1f")
        st.dataframe(df.style.apply(style_m, axis=1).background_gradient(subset=["Score"], cmap="RdYlGn", vmin=0, vmax=150), use_container_width=True, hide_index=True, height=600, column_order=["Titul", "Cena", "Změna"] + keys + ["Score"], column_config=cf)

elif stranka == "Vnitřní hodnota (IV)":
    g_pct, re_pct, y_bond, target_pe, target_ps = 0.03, 0.09, 4.4, 15, 3.0
    iv_res = []
    for item in filtered_data:
        inf = item["inf"]; pr = safe_float(inf.get('currentPrice'))
        ep, bv, fc, rv = safe_float(inf.get('trailingEps')), safe_float(inf.get('bookValue')), safe_float(inf.get('freeCashflow')), safe_float(inf.get('totalRevenue'))
        sh, di = safe_float(inf.get('sharesOutstanding')), safe_float(inf.get('dividendRate'))

        v_g = (ep * (8.5 + 2 * 3.0) * 4.4) / y_bond if ep > 0 else 0
        v_p = ep * target_pe
        v_r = bv + ((ep - (re_pct * bv)) / (re_pct - g_pct)) if (bv > 0 and re_pct > g_pct) else 0
        p1 = max(v_g, v_p, v_r)
        
        v_f = ((fc * (1 + g_pct)) / (re_pct - g_pct)) / sh if (sh > 0 and re_pct > g_pct and fc > 0) else 0
        v_d = (di * (1 + g_pct)) / (re_pct - g_pct) if (di > 0 and re_pct > g_pct) else 0
        p2 = max(v_f, v_d)
        
        v_s = (rv / sh) * target_ps if (sh > 0 and rv > 0) else 0
        p3 = max(v_s, bv if bv > 0 else 0)

        v_list = [v for v in [p1, p2, p3] if v > 0]
        fair = sum(v_list)/len(v_list) if v_list else 0
        up = ((fair / pr) - 1) * 100 if pr > 0 else 0
        iv_res.append({"Titul": item["name"], "Cena": pr, "P1: Zisková": int(p1), "P2: Cashflow": int(p2), "P3: Majetková": int(p3), "Férová cena": int(fair), "Potenciál %": float(up)})

    df_iv = pd.DataFrame(iv_res)
    if not df_iv.empty:
        st.dataframe(df_iv.style.apply(lambda r: ['background-color: #d4edda' if r["Potenciál %"] > 0 else 'background-color: #f8d7da' if r["Potenciál %"] < 0 else '']*len(r), axis=1).format({"Cena": "{:.2f}"}), use_container_width=True, hide_index=True, height=600, column_config={"Potenciál %": st.column_config.NumberColumn("Potenciál %", format="%.1f%%")})

else:
    c_rows, today = [], date.today()
    for item in filtered_data:
        inf, ticker = item["inf"], item["t"]
        ex_dt = datetime.fromtimestamp(inf.get('exDividendDate')).date() if inf.get('exDividendDate') else None
        dg = safe_float(inf.get('dividendYield')); dg = dg*100 if 0 < dg < 0.2 else dg
        cur = str(inf.get('currency', 'USD')).upper()
        
        tx = 0.0 if (ticker in ["BTI", "SHEL"] or ".LON" in ticker) else (0.15 if cur in ["USD", "CZK"] else 0.25)
        dn = dg * (1 - tx)

        c_rows.append({"Titul": item["name"], "Ticker": ticker, "Earnings": item["earn"] if not pd.isna(item["earn"]) else "-", "Dní do": safe_date_diff(item["earn"], today), "Dividenda": f"{safe_float(inf.get('dividendRate')):.2f} {cur}", "Div. výnos (hrubý)": dg, "Čistý výnos (odhad)": dn, "Ex-Date": ex_dt.strftime('%d.%m.%Y') if ex_dt else "-", "Doporučení": inf.get('recommendationKey', '-').replace('_', ' ').title(), "RSI": int(item['rsi']), "_rsi": item["rsi"]})
    
    df_c = pd.DataFrame(c_rows)
    if not df_c.empty:
        def style_c(r):
            s = [''] * len(r)
            idx = r.index.get_loc("Dní do")
            if r["Dní do"] < 0: s[idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            elif r["Dní do"] < 14: s[idx] = 'background-color: #fff9c4; color: #f57f17'
            
            rsi_idx = r.index.get_loc("RSI")
            if r["_rsi"] < 35: s[rsi_idx] = 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold'
            elif r["_rsi"] > 65: s[rsi_idx] = 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold'
            return s
        st.dataframe(df_c.style.apply(style_c, axis=1), use_container_width=True, hide_index=True, height=600, column_config={"_rsi": None, "Div. výnos (hrubý)": st.column_config.NumberColumn("Div. výnos (hrubý)", format="%.2f%%"), "Čistý výnos (odhad)": st.column_config.NumberColumn("Čistý výnos (odhad)", format="%.2f%%")}, column_order=["Titul", "Ticker", "Earnings", "Dní do", "Dividenda", "Div. výnos (hrubý)", "Čistý výnos (odhad)", "Ex-Date", "Doporučení", "RSI"])
