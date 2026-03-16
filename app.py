import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Konfiguracja wyglądu
st.set_page_config(page_title="GRUPA 13.", page_icon="📈", layout="wide")
st.title("📈 TWyniki portfela gr.13 LIVE")

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

@st.cache_data(ttl=300)
def pobierz_dane_rynkowe(ticker, data_startu):
    hist = yf.Ticker(ticker).history(start=data_startu, interval="1h")
    if hist.empty:
        hist = yf.Ticker(ticker).history(period="5d", interval="1h")
    if not hist.empty:
        hist.index = hist.index.tz_localize(None) # Usuwamy strefy czasowe do wykresu
    return hist

st.markdown(f"**Tydzień startowy:** `{data_startu_str}` | **Ostatnie dane:** `{datetime.now().strftime('%H:%M:%S')}`")

zysk_laczny = 0.0
dane_do_tabeli = []
historia_portfela = pd.DataFrame()

# === POBIERANIE I ŁĄCZENIE DANYCH ===
for nazwa, dane_poz in pozycje.items():
    ticker = dane_poz["ticker"]
    wielkosc = dane_poz["wielkosc"]
    
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
                "Wielkość": wielkosc,
                "Cena Start": f"{cena_otwarcia:.4f}",
                "Cena LIVE": f"{cena_live:.4f}",
                "Wynik (j.p.)": round(wynik_pozycji, 4)
            })
            
            # Tworzenie bezpiecznej serii danych do wykresu portfela
            kierunek_czynnik = 1 if wielkosc > 0 else -1
            seria_zysku = ((hist['Close'] - cena_otwarcia) / cena_otwarcia) * abs(wielkosc) * kierunek_czynnik
            seria_zysku.name = nazwa
            
            if historia_portfela.empty:
                historia_portfela = pd.DataFrame(seria_zysku)
            else:
                # Outer join zapobiega błędom, gdy rynki mają inne godziny otwarcia
                historia_portfela = historia_portfela.join(seria_zysku, how='outer')
                
    except Exception as e:
        st.error(f"Błąd dla {nazwa}: {e}")

# Łatanie dziur czasowych i obliczanie skumulowanego wyniku
historia_portfela = historia_portfela.ffill().fillna(0)
historia_portfela['Zysk_Total'] = historia_portfela.sum(axis=1)

# Przygotowanie danych do warunkowego kolorowania
# Tworzymy dwie nowe kolumny: jedną dla zysku > 0, drugą dla straty <= 0
historia_portfela['Zysk_Pos'] = historia_portfela['Zysk_Total'].where(historia_portfela['Zysk_Total'] > 0)
historia_portfela['Zysk_Neg'] = historia_portfela['Zysk_Total'].where(historia_portfela['Zysk_Total'] <= 0)

stan_konta = kapital_poczatkowy + zysk_laczny

# === METRYKI GŁÓWNE ===
st.divider()
col1, col2, col3 = st.columns(3)
col1.metric("Kapitał początkowy", f"{kapital_poczatkowy:.4f} j.p.")
col2.metric("Zysk / Strata", f"{zysk_laczny:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")
col3.metric("Stan Konta (LIVE)", f"{stan_konta:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")

# === WYKRES SKUMULOWANEGO ZYSKU Z POŚWIATĄ ===
st.divider()
st.subheader("Wykres zyskowności portfela z poświatą (H1)")

fig_zysk = go.Figure()

# Efekt poświaty dla zysku (zielona)
fig_zysk.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Pos'],
                    mode='lines', line=dict(color='lightgreen', width=10),
                    opacity=0.3, showlegend=False)) # Grubsza, półprzezroczysta linia pod spodem

# Główna linia dla zysku (zielona)
fig_zysk.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Pos'],
                    mode='lines', line=dict(color='green', width=3),
                    name='Zysk > 0'))

# Efekt poświaty dla straty (czerwona)
fig_zysk.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Neg'],
                    mode='lines', line=dict(color='salmon', width=10),
                    opacity=0.3, showlegend=False)) # Grubsza, półprzezroczysta linia pod spodem

# Główna linia dla straty (czerwona)
fig_zysk.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Neg'],
                    mode='lines', line=dict(color='red', width=3),
                    name='Strata <= 0'))

fig_zysk.update_layout(template="plotly_dark", xaxis_title="Czas", yaxis_title="Skumulowany Zysk (j.p.)",
                      margin=dict(l=20, r=20, t=30, b=20), height=400)
st.plotly_chart(fig_zysk, use_container_width=True)

# === TABELA I KONTROLKI ===
st.divider()
st.subheader("Szczegóły otwartych pozycji")
df = pd.DataFrame(dane_do_tabeli)
st.dataframe(df, use_container_width=True, hide_index=True)

if st.button("🔄 Wymuś odświeżenie danych z giełdy"):
    st.cache_data.clear()
    st.rerun()

st.caption("System Cache: 5 min. Interwał H1. Wykres z efektem poświaty.")
