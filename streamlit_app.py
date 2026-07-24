import streamlit as st
from g4f.client import Client

st.title("📋 Hloubková AI Analýza Společnosti")
st.caption("Generování komplexního fundamentálního rozboru dle metodiky Wall Street (Bez nutnosti API klíče)")

# Získání seznamu tickerů z vaší Google tabulky
if 'df_raw_list' in st.session_state and not st.session_state['df_raw_list'].empty:
    seznam_firem = st.session_state['df_raw_list']['Ticker'].dropna().unique().tolist()
    # Očistíme případné prázdné znaky
    seznam_firem = [str(t).strip().upper() for t in seznam_firem if str(t).strip() not in ["-", "nan", "TICKER"]]
else:
    # Záložní seznam pro testování
    seznam_firem = ["SHL.DE", "NOVO-B.CO", "META", "CZG.PR", "CEZ.PR", "MONET.PR", "PGN.WA"]

col1, col2 = st.columns([3, 1])

with col1:
    vybrana_firma = st.selectbox("Vyberte společnost pro analýzu:", seznam_firem)

with col2:
    st.write("") 
    st.write("")
    tlacitko_analyza = st.button("🚀 Vygenerovat analýzu", use_container_width=True)

if tlacitko_analyza:
    with st.spinner(f"🤖 Probíhá hloubková fundamentální analýza pro {vybrana_firma}... (může trvat cca 10–20 sekund)"):
        try:
            # Inicializace klienta bez API klíče
            client = Client()

            prompt = f"""
Jsi špičkový seniorní finanční analytik zaměřený na fundamentální analýzu akcií.
Vygeneruj detailní, rozsáhlou a profesně napsanou investiční analýzu v češtině pro společnost: **{vybrana_firma}**.

Dodrž PŘESNĚ následující strukturu a rozsah (buď velmi konkrétní, detailní a věcný, vyhni se obecným klišé):

Investiční Analýza: {vybrana_firma}

1. Základní profil a obchodní model
- Čím se firma zabývá, jak generuje tržby (popiš klíčové segmenty a produkty).
- Věcná a geografická struktura tržeb.

2. Konkurenční prostředí a tržní pozice
- Hlavní konkurenti a odhadovaný podíl na trhu.
- Ekonomický příkop (MOAT) a jeho pilíře (patenty, síťový efekt, switching costs, značka, R&D).
- Udržitelnost MOATu.

3. Finanční profil a ocenění
- Vývoj tržeb a marží (hrubá, provozní, čistá).
- Stav rozvahy, zadlužení (Dluh/EBITDA, D/E) a generování volného cashflow (FCF).
- Ziskové ukazatele (EPS, ROE) a valuační násobky (P/E, Forward P/E, EV/EBITDA, Div. výnos) ve srovnání s odvětvím.

4. Perspektiva oboru, pozice firmy a vnitřní procesy
- Hlavní odvětvové trendy (digitalizace, AI, demografie, regulace apod.).
- Jak si v nich firma vede a jaké vnitřní transformace či investice (R&D, M&A) realizuje.

5. Aktuální problematika a klíčové katalyzátory (Stock Price Drivers)
- Co aktuálně hýbe nebo může v nejbližších měsících hýbat cenou akcie (výsledková sezóna, schválení produktů, makro, geopolitika, M&A).

6. SWOT Analýza
- Silné stránky (Strengths)
- Slabé stránky (Weaknesses)
- Příležitosti (Opportunities)
- Hrozby (Threats)

7. Investiční teze a závěrečný verdikt
- Investiční teze pro dlouhodobého investora.
- Hlavní rizika vs. potenciál výnosu.
- Jasné závěrečné doporučení (např. Koupit / Držet / Prodat) s odůvodněním a horizontem 3–5 let.
"""

            # Volání AI modelu
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )

            analysa_text = response.choices[0].message.content

            st.success("✅ Analýza byla úspěšně vygenerována!")
            st.markdown("---")
            st.markdown(analysa_text)

            # Tlačítko pro stažení výstupu do textového souboru
            st.download_button(
                label="📥 Stáhnout analýzu jako TXT",
                data=analysa_text,
                file_name=f"Analýza_{vybrana_firma}.txt",
                mime="text/plain"
            )

        except Exception as e:
            st.error(f"❌ Chyba při generování: {e}. Zkuste to prosím znovu za chvíli.")
