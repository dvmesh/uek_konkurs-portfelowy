import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Konfiguracja wyglądu
st.set_page_config(page_title="Dashboard Konkursowy", page_icon="📈", layout="wide")
st.title("📈 Terminal Konkursowy LIVE")

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
        hist.index = hist.index.tz_localize(None) 
    return hist

st.markdown(f"**Tydzień startowy:** `{data_startu_str}` | **Ostatnie dane:** `{datetime.now().strftime('%H:%M:%S')}`")

zysk_laczny = 0.0
dane_do_tabeli = []
historia_portfela = pd.DataFrame()

# === POBIERANIE I ŁĄCZENIE DANYCH ===
with st.spinner('Pobieram dane z giełdy...'):
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
                
                kierunek_czynnik = 1 if wielkosc > 0 else -1
                seria_zysku = ((hist['Close'] - cena_otwarcia) / cena_otwarcia) * abs(wielkosc) * kierunek_czynnik
                seria_zysku.name = nazwa
                
                if historia_portfela.empty:
                    historia_portfela = pd.DataFrame(seria_zysku)
                else:
                    historia_portfela = historia_portfela.join(seria_zysku, how='outer')
                    
        except Exception as e:
            st.error(f"Błąd dla {nazwa}: {e}")

# Łatanie dziur czasowych
historia_portfela = historia_portfela.bfill().ffill().fillna(0)
historia_portfela['Zysk_Total'] = historia_portfela.sum(axis=1)

# === PRZYGOTOWANIE WIZUALIZACJI (BEZ BŁĘDÓW PLOTLY) ===
# Rozdzielamy zysk matematycznie, aby poświata działała idealnie
zysk_pos = historia_portfela['Zysk_Total'].clip(lower=0) # Obcina wszystko poniżej 0
zysk_neg = historia_portfela['Zysk_Total'].clip(upper=0) # Obcina wszystko powyżej 0

stan_konta = kapital_poczatkowy + zysk_laczny

# === METRYKI ===
st.divider()
col1, col2, col3 = st.columns(3)
col1.metric("Kapitał początkowy", f"{kapital_poczatkowy:.4f} j.p.")
col2.metric("Zysk / Strata", f"{zysk_laczny:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")
col3.metric("Stan Konta (LIVE)", f"{stan_konta:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")

# === WYKRES PORTFELA ===
st.divider()
st.subheader("Wykres zyskowności (H1)")

if not historia_portfela.empty:
    fig_portfel = go.Figure()

    # 1. Zielona poświata (dla wartości > 0)
    fig_portfel.add_trace(go.Scatter(
        x=historia_portfela.index, y=zysk_pos,
        mode='lines', line=dict(width=0), # Brak samej linii, tylko wypełnienie
        fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.15)', # Lekko przezroczysty zielony
        showlegend=False, hoverinfo='skip'
    ))

    # 2. Czerwona poświata (dla wartości < 0)
    fig_portfel.add_trace(go.Scatter(
        x=historia_portfela.index, y=zysk_neg,
        mode='lines', line=dict(width=0),
        fill='tozeroy', fillcolor='rgba(255, 0, 0, 0.15)', # Lekko przezroczysty czerwony
        showlegend=False, hoverinfo='skip'
    ))

    # 3. Ciągła linia (która ostatecznie zakrywa "dziurę")
    # Zmienia kolor w zależności od tego, czy aktualnie wygrywacie czy przegrywacie
    kolor_linii = "#00ffcc" if historia_portfela['Zysk_Total'].iloc[-1] >= 0 else "#ff4d4d"
    
    fig_portfel.add_trace(go.Scatter(
        x=historia_portfela.index, y=historia_portfela['Zysk_Total'],
        mode='lines', line=dict(width=3, color=kolor_linii),
        name='Skumulowany wynik'
    ))

    fig_portfel.update_layout(
        template="plotly_dark", 
        xaxis_title="Czas", 
        yaxis_title="Wynik (j.p.)",
        margin=dict(l=20, r=20, t=30, b=20), 
        height=400,
        yaxis=dict(zeroline=True, zerolinecolor='rgba(255, 255, 255, 0.5)', zerolinewidth=1)
    )
    st.plotly_chart(fig_portfel, use_container_width=True)

# === TABELA ===
st.divider()
st.subheader("Szczegóły otwartych pozycji")
df = pd.DataFrame(dane_do_tabeli)
st.dataframe(df, use_container_width=True, hide_index=True)

if st.button("🔄 Wymuś odświeżenie danych z giełdy"):
    st.cache_data.clear()
    st.rerun()
