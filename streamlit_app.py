import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

st.set_page_config(page_title="Matrix Diagnostika V82.3", layout="wide")

# --- 1. ODKAZ - ZDE ZKONTROLUJTE, ZDA JE AKTUÁLNÍ ---
ODKAZ_NA_TABULKU = "https://docs.google.com/spreadsheets/d/1q90ZZ4EjYCqyrReOgm6j_nmJlXEs2aaU6YWHAw7aoZg/edit?usp=sharing"

@st.cache_data(ttl=60) # Sníženo pro účely testování
def nacti_seznam(odkaz):
    try:
        csv_url = odkaz.replace('/edit?usp=sharing', '/export?format=csv')
        df = pd.read_csv(csv_url)
        # Odstranění neviditelných znaků
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception as e:
        return f"CHYBA PŘIPOJENÍ: {e}"

st.title("🔍 Diagnostika spojení s tabulkou")

data_test = nacti_seznam(ODKAZ_NA_TABULKU)

if isinstance(data_test, str):
    st.error(data_test)
    st.info("Pravděpodobně neplatný odkaz nebo uzavřené sdílení tabulky.")
else:
    st.success("Tabulka úspěšně načtena!")
    st.write("Nalezené sloupce v tabulce:", list(data_test.columns))
    
    with st.expander("Zobrazit syrová data z Google Sheetu"):
        st.dataframe(data_test)

    # Kontrola sloupce Kategorie
    if 'Kategorie' in data_test.columns:
        unikatni_kat = data_test['Kategorie'].unique()
        st.write(f"Nalezené kategorie v tabulce: {unikatni_kat}")
        
        if 'Portfolio' not in unikatni_kat:
            st.warning("POZOR: Text 'Portfolio' (s velkým P) nebyl ve sloupci Kategorie nalezen!")
    else:
        st.error("CHYBA: Sloupec s názvem 'Kategorie' v tabulce vůbec neexistuje!")

st.divider()
st.info("Pokud v tabulce nahoře vidíte svá data, chyba byla jen v překlepu v kategorii. Pokud je tabulka prázdná, musíte aktualizovat ODKAZ_NA_TABULKU.")
