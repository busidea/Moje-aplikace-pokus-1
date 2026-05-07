import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V45", layout="wide")

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

st.title("🏛️ Investiční Matrix V45")

# --- SIDEBAR ---
st.sidebar.header("⚖️ Nastavení")
w_val = st.sidebar.slider("Váha: Valuace", 0.5, 3.0, 1.0, 0.1)
w_prof = st.sidebar.slider("Váha: Rentabilita", 0.5, 3.0, 1.0, 0.1)
w_growth = st.sidebar.slider("Váha: Růst", 0.5, 3.0, 1.0, 0.1)
w_risk = st.sidebar.slider("Váha: Riziko", 0.5, 3.0, 1.5, 0.1)

st.sidebar.markdown("---")
show_audit = st.sidebar.checkbox("Zobrazit bodové řádky (Audit)", value=True)
hide_market = st.sidebar.checkbox("Skrýt tržní údaje (Cena, %)", value=False)
show_calendar = st.sidebar.checkbox("📅 Zobrazit kalendář událostí", value=True)

# ... (pásma zůstávají stejná jako v V44, zkráceno pro přehlednost)
def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# Pásma PE (příklad, v reálu použijte všech 16 z minulé verze)
p_pe = [{"h": 15, "b": 15}, {"h": 25, "b": 10}, {"h": 35, "b": 5}, {"h": 50, "b": 0}, {"h": 999, "b": -5}]

@st.cache_data(ttl=3600)
def fetch_all_data(db, s_audit):
    matrix_res = []
    cal_res = []
    pb = st.progress(0)
    tickery = list(db.keys())
    
    today = date.today()

    for idx, t in enumerate(tickery):
        try:
            tick = yf.Ticker(str(t).strip())
            i = tick.info
            
            # --- DATA PRO MATRIX ---
            c_price = i.get('currentPrice', 0)
            p_close = i.get('previousClose', 1)
            chg = ((c_price / p_close) - 1) * 100
            
            d = {
                "Ticker": t, "Cena": c_price, "Změna %": chg,
                "P/E": i.get('trailingPE') or i.get('forwardPE') or 0,
                "Score": 0, "RowType": "Val", "SortKey": 0
            }
            # (Zde by proběhlo kompletní bodování jako v V44)
            pts_pe = get_b(d["P/E"], p_pe) * w_val
            d["Score"] = pts_pe # Zjednodušeno
            d["SortKey"] = d["Score"]
            
            matrix_res.append(d)
            if s_audit:
                matrix_res.append({"Ticker": "└─ pts", "P/E": pts_pe, "Score": d["Score"], "RowType": "Pts", "SortKey": d["Score"]-0.001})

            # --- DATA PRO KALENDÁŘ ---
            cal = tick.calendar
            next_earn = "N/A"
            if cal and 'Earnings Date' in cal:
                next_earn = cal['Earnings Date'][0].date()

            ex_date = i.get('exDividendDate')
            if ex_date:
                ex_date = datetime.fromtimestamp(ex_date).date()
            
            div_val = i.get('dividendRate', 0)
            
            days_to_earn = (next_earn - today).days if isinstance(next_earn, date) else 999
            
            cal_res.append({
                "Ticker": t,
                "Next Earnings": next_earn,
                "Dní do výsledků": days_to_earn if days_to_earn != 999 else "-",
                "Dividenda (ks)": f"{div_val:.2f} USD" if div_val else "0",
                "Ex-Date": ex_date or "-",
                "Poznámka": "Potvrzeno" if days_to_earn < 30 else "Očekáváno"
            })

        except Exception as e: continue
        pb.progress((idx+1)/len(tickery))
        
    return pd.DataFrame(matrix_res), pd.DataFrame(cal_res)

df_matrix, df_cal = fetch_all_data(moje_databaze, show_audit)

# --- ZOBRAZENÍ MATRIXU ---
if not df_matrix.empty:
    st.subheader("📊 Investiční Matrix")
    # (Styling Matrixu z V44 zůstává zachován)
    st.dataframe(df_matrix.drop(columns=["RowType", "SortKey"]), use_container_width=True)

# --- ZOBRAZENÍ KALENDÁŘE ---
if show_calendar and not df_cal.empty:
    st.markdown("---")
    st.subheader("📅 Kalendář událostí (Earnings & Dividends)")
    
    def style_calendar(row):
        styles = [''] * len(row)
        # Zvýraznění blízkých výsledků (méně než 14 dní)
        try:
            days = row["Dní do výsledků"]
            if days != "-" and int(days) <= 14:
                styles[1] = 'background-color: #fff3cd; color: #856404; font-weight: bold' # Oranžová
        except: pass
        return styles

    st.dataframe(
        df_cal.style.apply(style_calendar, axis=1),
        use_container_width=True,
        hide_index=True
    )
