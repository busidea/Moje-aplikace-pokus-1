import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Investiční Matrix V46", layout="wide")

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

st.title("🏛️ Investiční Matrix V46")

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

# Pomocná funkce pro body (zkrácená verze pro funkčnost kódu)
def get_b(val, pasma):
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# Pásma PE (ukázka, doplňte si své kompletní seznamy)
p_pe = [{"h": 15, "b": 15}, {"h": 25, "b": 10}, {"h": 35, "b": 5}, {"h": 50, "b": 0}, {"h": 999, "b": -5}]

@st.cache_data(ttl=3600)
def fetch_all_data(db, s_audit):
    matrix_res = []
    cal_res = []
    tickery = list(db.keys())
    pb = st.progress(0)
    today = date.today()

    for idx, t in enumerate(tickery):
        try:
            ticker_clean = str(t).strip()
            tick = yf.Ticker(ticker_clean)
            i = tick.info
            
            # --- MATRIX DATA ---
            c_price = i.get('currentPrice', 0)
            p_close = i.get('previousClose', 1)
            chg = ((c_price / p_close) - 1) * 100 if p_close > 0 else 0
            
            pe = i.get('trailingPE') or i.get('forwardPE') or 0
            pts_pe = get_b(pe, p_pe) * w_val
            
            row = {
                "Ticker": ticker_clean, "Cena": c_price, "Změna %": chg,
                "P/E": pe, "Score": pts_pe, "RowType": "Val", "SortKey": pts_pe
            }
            matrix_res.append(row)
            
            if s_audit:
                matrix_res.append({
                    "Ticker": "└─ pts", "Cena": 0, "Změna %": 0, "P/E": pts_pe, 
                    "Score": pts_pe, "RowType": "Pts", "SortKey": pts_pe - 0.0001
                })

            # --- CALENDAR DATA ---
            # Pokus o získání datumu výsledků
            try:
                cal = tick.calendar
                next_earn = cal.get('Earnings Date', [None])[0].date() if cal else "Neznámé"
            except:
                next_earn = "Neznámé"

            ex_date = i.get('exDividendDate')
            ex_date_fmt = datetime.fromtimestamp(ex_date).date() if ex_date else "-"
            
            div_val = i.get('dividendRate', 0)
            days_to_earn = (next_earn - today).days if isinstance(next_earn, date) else 999
            
            cal_res.append({
                "Ticker": ticker_clean,
                "Next Earnings": next_earn,
                "Dní do akce": days_to_earn if days_to_earn != 999 else "-",
                "Dividenda": f"{div_val:.2f} USD" if div_val else "0",
                "Ex-Date": ex_date_fmt,
                "Poznámka": "⚠️ Blízko" if (isinstance(days_to_earn, int) and days_to_earn <= 14) else "Sledováno"
            })
        except:
            continue
        pb.progress((idx+1)/len(tickery))
    
    return pd.DataFrame(matrix_res), pd.DataFrame(cal_res)

df_matrix, df_cal = fetch_all_data(moje_databaze, show_audit)

# --- ZOBRAZENÍ MATRIXU ---
if not df_matrix.empty:
    st.subheader("📊 Investiční Matrix")
    df_m_plot = df_matrix.sort_values("SortKey", ascending=False)
    
    disp_cols = ["Ticker"]
    if not hide_market: disp_cols += ["Cena", "Změna %"]
    disp_cols += ["P/E", "Score"] # Zde přidejte všechny své sloupce (P/S, P/B...)

    def style_matrix(row):
        styles = [''] * len(row)
        if row["RowType"] == "Pts":
            return ['background-color: #f8f9fa; color: #adb5bd; font-style: italic'] * len(row)
        if not hide_market:
            color = 'color: #28a745' if row["Změna %"] > 0 else 'color: #dc3545' if row["Změna %"] < 0 else ''
            styles[disp_cols.index("Cena")] = color
            styles[disp_cols.index("Změna %")] = color
        return styles

    # Nastavení šířky sloupců (Zde je klíč k "roztaženým" sloupcům)
    col_cfg = {
        "Ticker": st.column_config.TextColumn("Ticker", width="small"),
        "Cena": st.column_config.NumberColumn("Cena", format="%.2f", width="small"),
        "Změna %": st.column_config.NumberColumn("Změna %", format="%.1f%%", width="small"),
        "Score": st.column_config.NumberColumn("Score", format="%.1f", width="small")
    }

    st.dataframe(
        df_m_plot.style.apply(style_matrix, axis=1).background_gradient(subset=['Score'], cmap='RdYlGn'),
        use_container_width=True,
        hide_index=True,
        column_order=disp_cols,
        column_config=col_cfg
    )

# --- ZOBRAZENÍ KALENDÁŘE ---
if show_calendar and not df_cal.empty:
    st.markdown("---")
    st.subheader("📅 Kalendář událostí")
    
    st.dataframe(
        df_cal.style.highlight_between(left=0, right=14, subset=["Dní do akce"], color="#fff3cd"),
        use_container_width=True,
        hide_index=True
    )
