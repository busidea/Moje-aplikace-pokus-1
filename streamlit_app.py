import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# --- 1. KONFIGURACE A STYL ---
st.set_page_config(page_title="Investiční Terminál", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 3.5rem; padding-bottom: 0rem; }
    [data-testid="stDataFrame"] td { text-align: right !important; }
    
    /* Vynucené zvýraznění prvního sloupce - Modrá a Tučná */
    [data-testid="stDataFrame"] [role="gridcell"]:first-child { 
        font-weight: bold !important;
        color: #004080 !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. POMOCNÉ FUNKCE ---
def safe_float(val):
    try:
        if val is None or str(val).lower() in ["nan", "none", "-", ""]: return 0.0
        return float(val)
    except: return 0.0

def safe_date_diff(earn_val, today):
    if pd.isna(earn_val) or str(earn_val).strip() in ["", "-", "nan", "None"]:
        return 999
    try:
        dt = pd.to_datetime(earn_val, dayfirst=True).date()
        return (dt - today).days
    except: return 999

def get_b(val, pasma):
    if val is None or val == 0: return 0
    for p in pasma:
        if val <= p["h"]: return p["b"]
    return pasma[-1]["b"]

# --- 3. NAČTENÍ DAT A HISTORICKÁ CACHE ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=300)
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        df.columns = [c.strip() for c in df.columns]
        df['Ticker'] = df['Ticker'].astype(str).str.upper()
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=86400)
def fetch_historical_averages(ticker_symbol, current_gm, current_nm, current_roe):
    try:
        tk = yf.Ticker(ticker_symbol)
        fin = tk.financials
        bs = tk.balance_sheet
        
        # Hrubá marže 3Y
        gm_3y = current_gm
        if fin is not None and not fin.empty and 'Gross Profit' in fin.index and 'Total Revenue' in fin.index:
            roky = fin.columns[:3]
            vals = [fin.loc['Gross Profit', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
            if vals: gm_3y = (sum(vals) / len(vals)) * 100

        # Čistá marže 3Y
        nm_3y = current_nm
        if fin is not None and not fin.empty and 'Net Income' in fin.index and 'Total Revenue' in fin.index:
            roky = fin.columns[:3]
            vals = [fin.loc['Net Income', r] / fin.loc['Total Revenue', r] for r in roky if fin.loc['Total Revenue', r] > 0]
            if vals: nm_3y = (sum(vals) / len(vals)) * 100

        # ROE 3Y
        roe_3y = current_roe
        if fin is not None and not fin.empty and bs is not None and not bs.empty and 'Net Income' in fin.index and 'Stockholders Equity' in bs.index:
            roky = [r for r in fin.columns[:3] if r in bs.columns]
            vals = [fin.loc['Net Income', r] / bs.loc['Stockholders Equity', r] for r in roky if bs.loc['Stockholders Equity', r] > 0]
            if vals: roe_3y = (sum(vals) / len(vals)) * 100
            
        return safe_float(gm_3y), safe_float(nm_3y), safe_float(roe_3y)
    except:
        return current_gm, current
