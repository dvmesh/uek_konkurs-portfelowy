import time
import json
import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# === KONFIGURACJA APLIKACJI ===
st.set_page_config(page_title="Grupa 13", page_icon="📈", layout="wide")

# === SYSTEM ZAPISU (Baza Danych w pliku JSON) ===
PLIK_USTAWIEN = "portfel.json"

def wczytaj_ustawienia():
    # Jeśli plik istnieje, ładujemy Wasze ustawienia. Jeśli nie, ładujemy startowe.
    if os.path.exists(PLIK_USTAWIEN):
        with open(PLIK_USTAWIEN, "r") as f:
            return json.load(f)
    return {
        "kapital_startowy": 100.0,
        "pozycje": {"S&P 500": 0.0, "US10Y Yield": 50.0, "Złoto (Gold)": -50.0, "EUR/USD": 0.0}
    }

def zapisz_ustawienia(ustawienia):
    with open(PLIK_USTAWIEN, "w") as f:
        json.dump(ustawienia, f)

# Wczytywanie aktualnych ustawień do zmiennych
ustawienia = wczytaj_ustawienia()
kapital_poczatkowy = ustawienia["kapital_startowy"]
pozycje_z_panelu = ustawienia["pozycje"]

# Słownik wszystkich dozwolonych instrumentów i ich tickerów
TICKERY = {
    "S&P 500": "^GSPC",
    "US10Y Yield": "^TNX",
    "Złoto (Gold)": "GC=F",
    "EUR/USD": "EURUSD=X"
}

# === PANEL ADMINISTRATORA (PASEK BOCZNY) ===
with st.sidebar:
    st.header("⚙️ Panel Rebalansu")
    st.markdown("Zaloguj się w niedzielę, by zaktualizować portfel.")
    
    # Proste zabezpieczenie PIN-em (możesz zmienić "1234" na co chcesz)
    haslo = st.text_input("Podaj PIN:", type="password")
    
    if haslo == "1234":
        st.success("Zalogowano pomyślnie.")
        
        nowy_kapital = st.number_input("Kapitał na start tygodnia (j.p.)", 
                                       value=float(kapital_poczatkowy), step=1.0)
        
        st.markdown("### Obstawienia (LONG > 0, SHORT < 0)")
        nowe_pozycje = {}
        suma_zaangazowania = 0.0
        
        # Generowanie inputów dla każdego instrumentu
        for aktywo in TICKERY.keys():
            wartosc = st.number_input(aktywo, value=float(pozycje_z_panelu.get(aktywo, 0.0)), step=10.0)
            nowe_pozycje[aktywo] = wartosc
            suma_zaangazowania += abs(wartosc) # Liczymy wartość bezwzględną dla regulaminu
            
        st.divider()
        st.write(f"Zainwestowany kapitał: **{suma_zaangazowania}** / {nowy_kapital}")
        
        # Walidacja zgodności z regulaminem (max 100% kapitału)
        if suma_zaangazowania > nowy_kapital:
            st.error("❌ Odrzucono: Zainwestowałeś więcej niż masz na koncie!")
        else:
            if st.button("💾 Zapisz na nowy tydzień"):
                nowe_ustawienia = {
                    "kapital_startowy": nowy_kapital,
                    "pozycje": nowe_pozycje
                }
                zapisz_ustawienia(nowe_ustawienia)
                st.cache_data.clear() # Czyścimy pamięć starych cen
                st.success("Zapisano! Odświeżam terminal...")
                time.sleep(1)
                st.rerun()

# === LOGIKA CZASU (Zawsze szuka ostatniego poniedziałku) ===
dzisiaj = datetime.today()
ostatni_poniedzialek = dzisiaj - timedelta(days=dzisiaj.weekday())
data_startu_str = ostatni_poniedzialek.strftime('%Y-%m-%d')

@st.cache_data(ttl=60)
def pobierz_dane_rynkowe(ticker, data_startu):
    hist = yf.Ticker(ticker).history(start=data_startu, interval="1h")
    if hist.empty:
        hist = yf.Ticker(ticker).history(period="5d", interval="1h")
    if not hist.empty:
        hist.index = hist.index.tz_localize(None) 
    return hist

# === GŁÓWNY INTERFEJS (DLA CAŁEJ GRUPY) ===
st.title("📈 Portfel grupy 13. LIVE")
st.markdown(f"**Start bieżącego tygodnia:** `{data_startu_str}` | **Ostatnia aktualizacja:** `{datetime.now().strftime('%H:%M:%S')}`")

zysk_laczny = 0.0
dane_do_tabeli = []
historia_portfela = pd.DataFrame()

# Pobieranie danych (tylko dla instrumentów, na których coś gramy!)
with st.spinner('Pobieram dane z giełdy...'):
    for nazwa, wielkosc in pozycje_z_panelu.items():
        if wielkosc == 0: 
            continue # Pomijamy aktywa, na które nie postawiliście kasy
            
        ticker = TICKERY[nazwa]
        try:
            hist = pobierz_dane_rynkowe(ticker, data_startu_str)
            if not hist.empty:
                cena_otwarcia = hist['Open'].iloc[0]
                cena_live = hist['Close'].iloc[-1]
                
                zmiana_procentowa = (cena_live - cena_otwarcia) / cena_otwarcia
                wynik_pozycji = wielkosc * zmiana_procentowa
                zysk_laczny += wynik_pozycji
                
                dane_do_tabeli.append({
                    "Instrument": nazwa,
                    "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
                    "Wielkość (j.p.)": wielkosc,
                    "Cena Start": f"{cena_otwarcia:.4f}",
                    "Cena LIVE": f"{cena_live:.4f}",
                    "Wynik": round(wynik_pozycji, 4)
                })
                
                kierunek_czynnik = 1 if wielkosc > 0 else -1
                seria_zysku = ((hist['Close'] - cena_otwarcia) / cena_otwarcia) * abs(wielkosc) * kierunek_czynnik
                seria_zysku.name = nazwa
                
                if historia_portfela.empty:
                    historia_portfela = pd.DataFrame(seria_zysku)
                else:
                    historia_portfela = historia_portfela.join(seria_zysku, how='outer')
                    
        except Exception as e:
            st.error(f"Błąd dla {nazwa}: {e}")

# Przygotowanie wykresu i metryk
if not historia_portfela.empty:
    historia_portfela = historia_portfela.bfill().ffill().fillna(0)
    historia_portfela['Zysk_Total'] = historia_portfela.sum(axis=1)
    zysk_pos = historia_portfela['Zysk_Total'].clip(lower=0) 
    zysk_neg = historia_portfela['Zysk_Total'].clip(upper=0) 

stan_konta = kapital_poczatkowy + zysk_laczny

st.divider()
col1, col2, col3 = st.columns(3)
col1.metric("Kapitał początkowy", f"{kapital_poczatkowy:.4f} j.p.")
col2.metric("Zysk / Strata", f"{zysk_laczny:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")
col3.metric("Stan Konta (LIVE)", f"{stan_konta:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")

st.divider()

if not historia_portfela.empty:
    fig_portfel = go.Figure()
    fig_portfel.add_trace(go.Scatter(x=historia_portfela.index, y=zysk_pos, mode='lines', line=dict(width=0), fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.15)', showlegend=False, hoverinfo='skip'))
    fig_portfel.add_trace(go.Scatter(x=historia_portfela.index, y=zysk_neg, mode='lines', line=dict(width=0), fill='tozeroy', fillcolor='rgba(255, 0, 0, 0.15)', showlegend=False, hoverinfo='skip'))
    fig_portfel.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Total'], mode='lines', line=dict(width=3, color="#ffffff"), name='Skumulowany wynik'))

    fig_portfel.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=30, b=20), height=400, yaxis=dict(zeroline=True, zerolinecolor='rgba(255, 255, 255, 0.5)', zerolinewidth=1))
    st.plotly_chart(fig_portfel, use_container_width=True)

st.subheader("Otwarte pozycje (Ten tydzień)")
if dane_do_tabeli:
    df = pd.DataFrame(dane_do_tabeli)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Brak otwartych pozycji w tym tygodniu (wszystko ustawione na 0).")

st.divider()

if st.button("🔄 Wymuś odświeżenie danych"):
    st.cache_data.clear()
    st.rerun()

time.sleep(60)
st.rerun()
