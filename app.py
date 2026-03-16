import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Konfiguracja wyglądu strony
st.set_page_config(page_title="Portfel gr.13", page_icon="📈", layout="wide")
st.title("📈 Bulsiewicz, Hussakowski, Jackowski")

# === TWOJA STRATEGIA ===
kapital_poczatkowy = 100.0
pozycje = {
    "Złoto (Gold)": {"ticker": "GC=F", "wielkosc": -50},
    "Rentowności (US10Y)": {"ticker": "^TNX", "wielkosc": 50}
}

# === LOGIKA CZASU ===
dzisiaj = datetime.today()
ostatni_poniedzialek = dzisiaj - timedelta(days=dzisiaj.weekday())
data_startu_str = ostatni_poniedzialek.strftime('%Y-%m-%d')

# === ZABEZPIECZENIE (CACHE) + INTERWAŁ GODZINOWY ===
@st.cache_data(ttl=300)
def pobierz_dane_rynkowe(ticker, data_startu):
    # Dodany parametr interval="1h" pobiera świece godzinowe
    historia = yf.Ticker(ticker).history(start=data_startu, interval="1h")
    if historia.empty:
        historia = yf.Ticker(ticker).history(period="5d", interval="1h")
    
    # Czyszczenie stref czasowych, żeby wykres Streamlita się nie zaciął
    if not historia.empty:
        historia.index = historia.index.tz_localize(None)
        
    return historia

st.markdown(f"**Tydzień startowy:** `{data_startu_str}` | **Stan danych na:** `{datetime.now().strftime('%H:%M:%S')}` | **Interwał:** `1H`")

zysk_laczny = 0.0
dane_do_tabeli = []
dane_historyczne_df = pd.DataFrame()

# === POBIERANIE I PRZETWARZANIE DANYCH ===
for nazwa, dane_poz in pozycje.items():
    ticker = dane_poz["ticker"]
    wielkosc = dane_poz["wielkosc"]
    
    try:
        historia = pobierz_dane_rynkowe(ticker, data_startu_str)
        
        if not historia.empty:
            cena_otwarcia = historia['Open'].iloc[0]
            cena_live = historia['Close'].iloc[-1]
            
            # Obliczenia na bieżącą chwilę
            zmiana_procentowa = (cena_live - cena_otwarcia) / cena_otwarcia
            wynik_pozycji = wielkosc * zmiana_procentowa
            zysk_laczny += wynik_pozycji
            
            dane_do_tabeli.append({
                "Instrument": nazwa,
                "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
                "Wielkość": wielkosc,
                "Cena Startowa": f"{cena_otwarcia:.4f}",
                "Cena LIVE": f"{cena_live:.4f}",
                "Wynik (j.p.)": round(wynik_pozycji, 4)
            })
            
            # Generowanie danych dla wykresu (symulacja kapitału w czasie)
            historia_zmiany = (historia['Close'] - cena_otwarcia) / cena_otwarcia
            kierunek_czynnik = 1 if wielkosc > 0 else -1
            
            if dane_historyczne_df.empty:
                dane_historyczne_df = pd.DataFrame(index=historia.index)
            
            # Wartość zysku z tej konkretnej pozycji w danym momencie (H1)
            dane_historyczne_df[nazwa] = historia_zmiany * abs(wielkosc) * kierunek_czynnik
            
    except Exception as e:
        st.error(f"Problem z pobraniem danych dla {nazwa}: {e}")

stan_konta = kapital_poczatkowy + zysk_laczny

# === INTERFEJS GRAFICZNY (KAFELKI) ===
st.divider()
col1, col2, col3 = st.columns(3)

col1.metric("Kapitał początkowy", f"{kapital_poczatkowy:.4f} j.p.")
col2.metric("Zysk / Strata", f"{zysk_laczny:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")
col3.metric("Stan Konta (LIVE)", f"{stan_konta:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")

# === WYKRES WYDAJNOŚCI H1 ===
st.divider()
st.subheader("Wykres zyskowności (Interwał H1)")

if not dane_historyczne_df.empty:
    # Uzupełniamy ewentualne luki w danych (np. gdy jedna giełda była zamknięta, a inna otwarta)
    dane_historyczne_df = dane_historyczne_df.ffill().fillna(0)
    
    # Dodajemy kolumnę z łącznym wynikiem portfela w danej godzinie
    dane_historyczne_df['Skumulowany Wynik (j.p.)'] = dane_historyczne_df.sum(axis=1)
    
    # Rysujemy na wykresie tylko zieloną/czerwoną linię łącznego zysku
    st.line_chart(dane_historyczne_df['Skumulowany Wynik (j.p.)'])

st.divider()

# === TABELA SZCZEGÓŁÓW ===
st.subheader("Szczegóły otwartych pozycji")
df = pd.DataFrame(dane_do_tabeli)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# Przycisk odświeżania czyszczący pamięć podręczną
if st.button("🔄 Wymuś odświeżenie danych"):
    st.cache_data.clear()
    st.rerun()

st.caption("System Cache: 5 min. Wykres oparty na interwale 1-godzinnym (H1).")
