import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Investiční Stratég V6", layout="wide")

st.title("⚖️ Pokročilé bodování v 5 pásmech")
st.write("Definujte si 5 pásem pro každý ukazatel. Nastavení ovlivní všechny firmy v seznamu.")

# --- SIDEBAR: NASTAVENÍ PÁSEM ---
st.sidebar.header("🎯 Definice bodovacích pásem")

def vytvor_pasma(nazev, zkratka, default_hranice, default_body):
    with st.sidebar.expander(f"Kritérium: {nazev}", expanded=False):
        st.write("Nastavte horní hranici pásma a počet bodů:")
        data = []
        for i in range(5):
            col1, col2 = st.columns(2)
            with col1:
                h = st.number_input(f"Pásmo {i+1} (do %)", value=default_hranice[i], key=f"{zkratka}_h_{i}")
            with col2:
                b = st.number_input(f"Body", value=default_body[i], key=f"{zkratka}_b_{i}")
            data.append({"hranice": h, "body": b})
        return data

# Definice pásem pro ROE (příklad: záporné, malé, střední, vysoké, extra)
pasma_roe = vytvor_pasma("ROE", "roe", [0.0, 10.0, 20.0, 30.0, 999.0], [-5, 0, 5, 10, 15])

# Definice pásem pro Marži
pasma_marze = vytvor_pasma("Čistá Marže", "mar", [0.0, 10.0, 20.0, 30.0, 999.0], [-5, 0, 5, 10, 15])

# --- FUNKCE PRO VÝPOČET SCORE ---
def pridel_body(hodnota, pasma):
    # Procházíme pásma od nejnižšího
    for p in pasma:
        if hodnota <= p["hranice"]:
            return p["body"]
    return pasma[-1]["body"] # Pokud přesáhne vše, dostane body z posledního pásma

def vypocitej_vysledek(row):
    score = 0
    score += pridel_body(row['ROE'], pasma_roe)
    score += pridel_body(row['Marze'], pasma_marze)
    return score

# --- DATA (Vaše tickery) ---
moje_akcie = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "V", "MA", "COST"]

@st.cache_data(ttl=3600)
def fetch_data(tickers):
    rows = []
    for t in tickers:
        try:
            s = yf.Ticker(t)
            info = s.info
            rows.append({
                "Ticker": t,
                "Název": info.get("longName", t),
                "ROE": (info.get("returnOnEquity", 0) or 0) * 100,
                "Marze": (info.get("profitMargins", 0) or 0) * 100
            })
        except: continue
    return pd.DataFrame(rows)

# Výpočet
df = fetch_data(moje_akcie)
df["Celkové Score"] = df.apply(vypocitej_vysledek, axis=1)
df = df.sort_values(by="Celkové Score", ascending=False)

# --- ZOBRAZENÍ ---
st.subheader("📊 Analýza firem")
st.dataframe(
    df.style.background_gradient(subset=['Celkové Score'], cmap='RdYlGn'),
    use_container_width=True
)

st.markdown("""
### Jak fungují pásma:
Aplikace vezme hodnotu ukazatele (např. ROE) a podívá se do vašich 5 pásem vlevo. 
Najde první pásmo, do kterého se hodnota vejde, a přidělí příslušné body. 
*Příklad: Pokud nastavíte Pásmo 1 'do 0 %' za -5 bodů a firma má ROE -2 %, dostane ihned -5 bodů.*
""")
