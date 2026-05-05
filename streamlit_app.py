import streamlit as st
import pandas as pd

st.set_page_config(page_title="Investiční Stratég", layout="wide")

st.title("📈 Můj Investiční Stratég")
st.write("Automatizované bodování akcií na základě vašich pravidel z Excelu.")

# --- SIDEBAR: NASTAVENÍ MANTINELŮ (Řádky 3-7 ve vašem Excelu) ---
st.sidebar.header("Nastavení bodování (Mantinely)")

with st.sidebar.expander("Čistá marže (AR)"):
    margin_high = st.slider("Body za 10 bodů (nad %)", 0, 50, 20)
    margin_mid = st.slider("Body za 5 bodů (nad %)", 0, 50, 10)

with st.sidebar.expander("ROE (5Y průměr)"):
    roe_high = st.slider("Body za 10 bodů (nad %)", 0, 50, 15)
    roe_mid = st.slider("Body za 5 bodů (nad %)", 0, 50, 8)

# --- SIMULACE DAT (Místo TIPY.ods) ---
# V budoucnu zde bude funkce pro automatické stahování z webu
data = {
    "Ticker": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
    "Cena": [170.5, 415.2, 145.1, 178.4, 485.1],
    "Cista_Marze_TTM": [26.4, 36.2, 24.0, 6.4, 28.9],
    "ROE_5Y": [150.0, 38.5, 25.4, 12.1, 22.0],  # Opraveno: Sleduje ROE, ne růst tržeb
    "Debt_Equity": [1.4, 0.4, 0.1, 0.4, 0.1]
}
df = pd.DataFrame(data)

# --- VÝPOČET SCORE (Váš sloupec T) ---
def spocti_score(row):
    score = 0
    # Bodování marže
    if row["Cista_Marze_TTM"] > margin_high: score += 10
    elif row["Cista_Marze_TTM"] > margin_mid: score += 5
    
    # Bodování ROE
    if row["ROE_5Y"] > roe_high: score += 10
    elif row["ROE_5Y"] > roe_mid: score += 5
    
    return score

df["Celkové Score (T)"] = df.apply(spocti_score, axis=1)

# --- ZOBRAZENÍ VÝSLEDKŮ ---
st.subheader("Žebříček akcií podle vašeho Score")
st.dataframe(df.sort_values(by="Celkové Score (T)", ascending=False), use_container_width=True)

st.info("Tip: Změňte mantinely v levém panelu a tabulka se okamžitě přepočítá.")
