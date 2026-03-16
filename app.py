import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Konfiguracja wyglądu
st.set_page_config(page_title="GRUPA 13", page_icon="🏆", layout="wide")
st.title("📈 Terminal Konkursowy LIVE: Neonowa Zyskowność (H1)")

# === TWOJA STRATEGIA ===
kapital_poczatkowy = 100.0
pozycje = {
    "Złoto (Gold)": {"ticker": "GC=F", "wielkosc": -50},
    "Rentowności (US10Y)": {"ticker": "^TNX", "wielkosc": 50}
}

# === LOGIKA CZASU ===
dzisiaj = datetime.today()
# Jeśli dziś jest poniedziałek, ostatni poniedziałek to dzisiaj
dni_do_cofniecia = dzisiaj.weekday()
ostatni_poniedzialek = dzisiaj - timedelta(days=dni_do_cofniecia)
data_startu_str = ostatni_poniedzialek.strftime('%Y-%m-%d')

@st.cache_data(ttl=300)
def pobierz_dane_rynkowe(ticker, data_startu):
    hist = yf.Ticker(ticker).history(start=data_startu, interval="1h")
    if hist.empty:
        hist = yf.Ticker(ticker).history(period="5d", interval="1h")
    if not hist.empty:
        # Usuwamy strefy czasowe do wykresu, bo Plotly czasem na nie narzeka
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
                
                # Tworzenie bezpiecznej serii danych do wykresu portfela
                kierunek_czynnik = 1 if wielkosc > 0 else -1
                seria_zysku = ((hist['Close'] - cena_otwarcia) / cena_otwarcia) * abs(wielkosc) * kierunek_czynnik
                seria_zysku.name = nazwa
                
                if historia_portfela.empty:
                    historia_portfela = pd.DataFrame(seria_zysku)
                else:
                    # Outer join zapobiega błędom, gdy rynki mają inne godziny otwarcia (np. obligacje i złoto)
                    historia_portfela = historia_portfela.join(seria_zysku, how='outer')
                    
        except Exception as e:
            st.error(f"Błąd dla {nazwa}: {e}")

# Łatanie dziur czasowych i obliczanie skumulowanego wyniku
# bfill().ffill() zapewnia ciągłość danych od początku do końca, nawet jeśli jeden instrument otworzył się później
historia_portfela = historia_portfela.bfill().ffill().fillna(0)
historia_portfela['Zysk_Total'] = historia_portfela.sum(axis=1)

# === GŁÓWNA LINIA Z PROFEJONALNYM GRADIENTEM I POŚWIATĄ ===
if not historia_portfela.empty:
    fig_portfel = go.Figure()

    # Krok 1: Definiujemy gradient. Plotly nie pozwala na bezpośredni gradient na linii,
    # ale możemy go symulować za pomocą gradientowego wypełnienia.
    
    # 1.1: Dodajemy cień (poświatę) dla profesjonalnego efektu neonu
    # Rysujemy tę samą linię, ale grubszą i półprzezroczystą, co daje efekt poświaty.
    # Kolor jest stały (nie zmienia się na osi y), ale gradient wypełnienia doda dynamiki.
    fig_portfel.add_trace(go.Scatter(
        x=historia_portfela.index,
        y=historia_portfela['Zysk_Total'],
        mode='lines',
        name='Neon Glow',
        line=dict(width=10, color='lightgreen'), # Gruba linia poświaty
        fill='tozeroy',  # Wypełnienie do zera,
        opacity=0.3, # Duża przezroczystość dla efektu cienia
        hoverinfo='skip', # Ignorujemy przy najechaniu myszką
        showlegend=False
    ))

    # 1.2: Rysujemy główną, ciągłą linię (bez gradientu, ale ciągłą!)
    # To rozwiąże problem dziury.
    fig_portfel.add_trace(go.Scatter(
        x=historia_portfela.index,
        y=historia_portfela['Zysk_Total'],
        mode='lines',
        name='Wynik portfela',
        # Używamy jednego, stałego koloru dla całej linii (to rozwiąże problem dziury)
        line=dict(width=3, color='cyan'),
        hoverinfo='x+y',
        fill='tozeroy', # Wypełnienie do zera
    ))

    # Krok 2: Konfigurujemy gradient wypełnienia do zera.
    # Wymaga to zaawansowanego obiektu 'gradient' w definicji wypełnienia.
    
    # Używamy gradientu pionowego (vertical), który zmienia kolor na osi Y.
    fig_portfel.update_traces(
        fillcolor='transparent', # Domyślny kolor wypełnienia, zanim zadziała gradient
        gradient=dict(
            type='vertical', # Gradient góra-dół
            color='#00FF00', # Startowy kolor (zielony) w punkcie zero
            stops=[
                dict(offset=0, color='#00FF00'), # 0% (zero) to zielony
                dict(offset=0.2, color='#006400'), # 20% to ciemnozielony
                dict(offset=0.8, color='#8B0000'), # 80% to ciemnoczerwony
                dict(offset=1, color='#FF0000'), # 100% (góra/dół) to czerwony
            ]
        ),
        selector=dict(name='Wynik portfela') # Aplikujemy gradient tylko do głównej linii
    )

    fig_portfel.update_layout(
        template="plotly_dark", 
        xaxis_title="Czas", 
        yaxis_title="Skumulowany Zysk (j.p.)",
        margin=dict(l=20, r=20, t=30, b=20),
        height=450,
        yaxis=dict(zeroline=True, zerolinecolor='white', zerolinewidth=1), # Wyraźna biała linia zero
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    st.plotly_chart(fig_portfel, use_container_width=True)

# === METRYKI I TABELA ===
st.divider()
stan_konta = kapital_poczatkowy + zysk_laczny
col1, col2, col3 = st.columns(3)
col1.metric("Kapitał początkowy", f"{kapital_poczatkowy:.4f} j.p.")
col2.metric("Zysk / Strata", f"{zysk_laczny:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")
col3.metric("Stan Konta (LIVE)", f"{stan_konta:.4f} j.p.", f"{zysk_laczny:.4f} j.p.")

st.divider()
st.subheader("Szczegóły otwartych pozycji")
df = pd.DataFrame(dane_do_tabeli)
# Używamy profesionalnego stylu tabeli z wyśrodkowanymi danymi
st.dataframe(df.style.set_properties(**{'text-align': 'center'}), use_container_width=True, hide_index=True)

# Przycisk odświeżania czyszczący pamięć podręczną
if st.button("🔄 Wymuś odświeżenie danych z giełdy"):
    st.cache_data.clear()
    st.rerun()

st.caption("System Cache: 5 min. Interwał H1. Wykres z efektem poświaty neonowej.")
