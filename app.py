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

# === ZABEZPIECZENIE PRZED BLOKADĄ (CACHE na 5 minut) ===
@st.cache_data(ttl=300)
def pobierz_dane_rynkowe(ticker, data_startu):
    # Pobieramy pełną historię od początku tygodnia
    historia = yf.Ticker(ticker).history(start=data_startu)
    if historia.empty:
        historia = yf.Ticker(ticker).history(period="5d")
    return historia

st.markdown(f"**Tydzień startowy:** `{data_startu_str}` | **Stan danych na:** `{datetime.now().strftime('%H:%M:%S')}`")

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
            
            # Obliczenia z precyzją
            zmiana_procentowa = (cena_live - cena_otwarcia) / cena_otwarcia
            wynik_pozycji = wielkosc * zmiana_procentowa
            zysk_laczny += wynik_pozycji
            
            dane_do_tabeli.append({
                "Instrument": nazwa,
                "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
                "Wielkość": wielkosc,
                "Cena Otwarcia": f"{cena_otwarcia:.4f}",
                "Cena LIVE": f"{cena_live:.4f}",
                "Wynik (j.p.)": round(wynik_pozycji, 4)
            })
            
            # Przygotowanie danych do wykresu
            # Obliczamy skumulowaną zmianę dla każdego punktu w czasie
            historia_zmiany = (historia['Close'] - cena_otwarcia) / cena_otwarcia
            
            # Dodajemy do wspólnego DataFrame dla wykresu
            if dane_historyczne_df.empty:
                # Inicjalizujemy z poprawnymi datami
                dane_historyczne_df = pd.DataFrame(index=historia.index)
            
            # Dodajemy serię danych dla danego instrumentu, uwzględniając kierunek pozycji
            # Dla SHORT (-50), spadek ceny (historia_zmiany < 0) daje zysk (dodatnia wartość na wykresie)
            kierunek_czynnik = 1 if wielkosc > 0 else -1
            dane_historyczne_df[nazwa] = historia_zmiany * abs(wielkosc) * kierunek_czynnik
            
    except Exception as e:
        st.error(f"Przeciążenie serwerów Yahoo przy pobieraniu {nazwa}. Spróbuj za chwilę.")

stan_konta = kapital_poczatkowy + zysk_laczny

# === INTERFEJS GRAFICZNY (KAFELKI) ===
st.divider()
col1, col2, col3 = st.columns(3)

col1.metric("Kapitał początkowy", f"{kapital_poczatkowy:.4f} j.p.")
col2.metric("Zysk / Strata", f"{zysk_laczny:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")
col3.metric("Stan Konta (LIVE)", f"{stan_konta:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")

# === NOWY SEKCJA: WYKRES WYDAJNOŚCI ===
st.divider()
st.subheader("Historia wydajności portfela w tym tygodniu")

# Obliczamy skumulowaną zmianę całego portfela
if not dane_historyczne_df.empty:
    dane_historyczne_df['Skumulowany Wynik (j.p.)'] = dane_historyczne_df.sum(axis=1)
    
    # Wyświetlamy wykres
    # Możesz pokazać tylko wynik całkowity...
    st.line_chart(dane_historyczne_df['Skumulowany Wynik (j.p.)'])
    
    # ...lub wyniki poszczególnych pozycji (odkomentuj poniższą linię)
    # st.line_chart(dane_historyczne_df.drop('Skumulowany Wynik (j.p.)', axis=1))

st.divider()

# === TABELA SZCZEGÓŁÓW ===
st.subheader("Szczegóły otwartych pozycji")
df = pd.DataFrame(dane_do_tabeli)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# Ręczny przycisk odświeżania czyszczący pamięć podręczną
if st.button("🔄 Odśwież dane z giełdy"):
    st.cache_data.clear()
    st.rerun()

st.caption("System zoptymalizowany pod kątem limitów API (Cache: 5 min). Użyj przycisku powyżej, aby wymusić nowe pobranie.")
