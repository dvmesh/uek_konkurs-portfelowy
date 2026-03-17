import time
import json
import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from streamlit_elements import elements, mui, html

st.set_page_config(page_title="Grupa 13", page_icon="📈", layout="wide")

PLIK_USTAWIEN = "portfel.json"

def wczytaj_ustawienia():
    if os.path.exists(PLIK_USTAWIEN):
        try:
            with open(PLIK_USTAWIEN, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "kapital_startowy": 100.0,
        "pozycje": {"S&P 500": 0.0, "US10Y Yield": 50.0, "Złoto (Gold)": -50.0, "EUR/USD": 0.0}
    }

def zapisz_ustawienia(ustawienia):
    with open(PLIK_USTAWIEN, "w") as f:
        json.dump(ustawienia, f)

ustawienia = wczytaj_ustawienia()
kapital_poczatkowy = float(ustawienia.get("kapital_startowy", 100.0))
pozycje_z_panelu = ustawienia.get("pozycje", {})

TICKERY = {
    "S&P 500": "^GSPC",
    "US10Y Yield": "^TNX",
    "Złoto (Gold)": "GC=F",
    "EUR/USD": "EURUSD=X"
}

# === DANE KONKURENCJI Z PDF ===
DANE_GRUP = {
    "Grupa 1": {"SPX": -25, "GOLD": -25, "RENT": 0, "EURUSD": -50},
    "Grupa 2": {"SPX": -50, "GOLD": 30, "RENT": 20, "EURUSD": 0},
    "Grupa 3": {"SPX": -20, "GOLD": -10, "RENT": 45, "EURUSD": -25},
    "Grupa 4": {"SPX": -35, "GOLD": 0, "RENT": 45, "EURUSD": -20},
    "Grupa 5": {"SPX": -35, "GOLD": 35, "RENT": -15, "EURUSD": 15},
    "Grupa 6": {"SPX": 70, "GOLD": 0, "RENT": 0, "EURUSD": 30},
    "Grupa 7": {"SPX": -30, "GOLD": -30, "RENT": 0, "EURUSD": -40},
    "Grupa 8": {"SPX": 40, "GOLD": 20, "RENT": 20, "EURUSD": 20},
    "Grupa 9": {"SPX": 0, "GOLD": 0, "RENT": 20, "EURUSD": 0},
    "Grupa 10": {"SPX": 0, "GOLD": -30, "RENT": 40, "EURUSD": -30},
    "Grupa 11": {"SPX": 25, "GOLD": -25, "RENT": 25, "EURUSD": -25},
    "Grupa 12": {"SPX": -60, "GOLD": 0, "RENT": 40, "EURUSD": 0},
    "Grupa 14": {"SPX": 50, "GOLD": 0, "RENT": 0, "EURUSD": 0},
    "Grupa 15": {"SPX": 10, "GOLD": 40, "RENT": 50, "EURUSD": 0},
    "Grupa A": {"SPX": -30, "GOLD": 70, "RENT": 0, "EURUSD": 0},
    "Grupa B": {"SPX": 50, "GOLD": 0, "RENT": 0, "EURUSD": -50},
    "Grupa C": {"SPX": -30, "GOLD": -40, "RENT": -30, "EURUSD": 0},
    "Grupa D": {"SPX": 40, "GOLD": 60, "RENT": 0, "EURUSD": 0},
    "Grupa E": {"SPX": -70, "GOLD": 30, "RENT": 0, "EURUSD": 0},
    "Grupa F": {"SPX": -40, "GOLD": -25, "RENT": -10, "EURUSD": 25},
    "Grupa G": {"SPX": -50, "GOLD": -50, "RENT": 0, "EURUSD": 0},
    "Grupa H": {"SPX": 70, "GOLD": 15, "RENT": 0, "EURUSD": 0},
    "Grupa I": {"SPX": -50, "GOLD": 50, "RENT": 0, "EURUSD": 0},
    "Grupa J": {"SPX": -70, "GOLD": 30, "RENT": 0, "EURUSD": 0},
    "Grupa K": {"SPX": -50, "GOLD": -50, "RENT": 0, "EURUSD": 0},
    "Grupa L": {"SPX": -50, "GOLD": -50, "RENT": 0, "EURUSD": 0},
    "Grupa M": {"SPX": -40, "GOLD": -40, "RENT": 0, "EURUSD": 0},
    "Grupa N": {"SPX": 100, "GOLD": 0, "RENT": 0, "EURUSD": 0}
}

# === LOGIKA CZASU ===
teraz = datetime.now()
ostatni_poniedzialek = teraz - timedelta(days=teraz.weekday())
data_startu_str = ostatni_poniedzialek.strftime('%Y-%m-%d')

dni_do_niedzieli = 6 - teraz.weekday()
najblizsza_niedziela = teraz + timedelta(days=dni_do_niedzieli)
deadline = najblizsza_niedziela.replace(hour=23, minute=0, second=0, microsecond=0)
if teraz > deadline: deadline += timedelta(days=7)

roznica = deadline - teraz
czy_mozna_rebalansowac = (teraz.weekday() == 6) and (teraz.hour < 23)

@st.cache_data(ttl=60)
def pobierz_dane_rynkowe(ticker, data_startu):
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(start=data_startu, interval="1h")
        if hist.empty:
            hist = ticker_obj.history(period="5d", interval="1h")
        
        if not hist.empty:
            # 1. Jeśli Yahoo zwróciło strefę czasową (NY, GMT itd.)...
            if hist.index.tz is not None:
                # 2. Najpierw konwertujemy wszystko na czas polski!
                hist.index = hist.index.tz_convert('Europe/Warsaw')
            
            # 3. Dopiero gdy wszystko jest w naszym czasie, usuwamy znacznik dla Plotly
            hist.index = hist.index.tz_localize(None)
            
        return hist
    except:
        return pd.DataFrame()

zysk_laczny = 0.0
dane_do_tabeli = []
zmiany_rynkowe = {} 
wszystkie_historie_zmian = {} # Przechowuje pełne osie czasu wszystkich 4 aktywów

# === POBIERANIE DANYCH ===
with st.spinner('Aktualizacja danych rynkowych i rankingu...'):
    for nazwa, ticker in TICKERY.items():
        hist = pobierz_dane_rynkowe(ticker, data_startu_str)
        if not hist.empty:
            cena_otw = hist['Open'].iloc[0]
            cena_live = hist['Close'].iloc[-1]
            zmiana_proc = (cena_live - cena_otw) / cena_otw
            zmiany_rynkowe[nazwa] = zmiana_proc
            
            # Zapisujemy krzywą zwrotu do budowy wykresu benchmarku
            wszystkie_historie_zmian[nazwa] = (hist['Close'] - cena_otw) / cena_otw
            
            # Obliczenia DLA WASZEGO PORTFELA
            wielkosc = pozycje_z_panelu.get(nazwa, 0.0)
            if wielkosc != 0:
                wynik_poz = wielkosc * zmiana_proc
                zysk_laczny += wynik_poz
                
                dane_do_tabeli.append({
                    "Instrument": nazwa,
                    "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
                    "Wielkość (j.p.)": wielkosc,
                    "Cena Start": f"{cena_otw:.4f}",
                    "Cena LIVE": f"{cena_live:.4f}",
                    "Wynik": round(wynik_poz, 4)
                })

stan_konta_na_zywo = kapital_poczatkowy + zysk_laczny
zmiana_proc_total = (zysk_laczny / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0

# === BUDOWA OSI CZASU DLA WYKRESU ===
# 1. Historia Waszego Portfela
historia_portfela = pd.DataFrame()
for nazwa, wielkosc in pozycje_z_panelu.items():
    if wielkosc != 0 and nazwa in wszystkie_historie_zmian:
        seria = wszystkie_historie_zmian[nazwa] * abs(wielkosc) * (1 if wielkosc > 0 else -1)
        historia_portfela = pd.DataFrame(seria) if historia_portfela.empty else historia_portfela.join(seria.rename(nazwa), how='outer')

# 2. Historia Średniej (Benchmark)
historia_sredniej = pd.DataFrame()
nasze_obs = {
    "SPX": pozycje_z_panelu.get("S&P 500", 0.0),
    "GOLD": pozycje_z_panelu.get("Złoto (Gold)", 0.0),
    "RENT": pozycje_z_panelu.get("US10Y Yield", 0.0),
    "EURUSD": pozycje_z_panelu.get("EUR/USD", 0.0)
}
wszystkie_grupy = list(DANE_GRUP.values()) + [nasze_obs]
liczba_grup = len(wszystkie_grupy)

MAPOWANIE_PDF = {"SPX": "S&P 500", "GOLD": "Złoto (Gold)", "RENT": "US10Y Yield", "EURUSD": "EUR/USD"}

for klucz_pdf, nazwa_inst in MAPOWANIE_PDF.items():
    suma_wag = sum(g.get(klucz_pdf, 0) for g in wszystkie_grupy)
    srednia_waga = suma_wag / liczba_grup
    
    if srednia_waga != 0 and nazwa_inst in wszystkie_historie_zmian:
        seria_avg = wszystkie_historie_zmian[nazwa_inst] * abs(srednia_waga) * (1 if srednia_waga > 0 else -1)
        historia_sredniej = pd.DataFrame(seria_avg) if historia_sredniej.empty else historia_sredniej.join(seria_avg.rename(nazwa_inst), how='outer')


# === OBLICZANIE RANKINGU (Tabela na żywo) ===
wyniki_rankingu = []
wyniki_rankingu.append({"Grupa": "GRUPA 13 (MY)", "Wynik": stan_konta_na_zywo})

for grupa, pozycje in DANE_GRUP.items():
    wynik_grupy = 100.0
    for inst, waga in pozycje.items():
        klucz_rynkowy = MAPOWANIE_PDF.get(inst)
        if klucz_rynkowy and klucz_rynkowy in zmiany_rynkowe:
            wynik_grupy += waga * zmiany_rynkowe[klucz_rynkowy]
            
    wyniki_rankingu.append({"Grupa": grupa, "Wynik": round(wynik_grupy, 4)})

ranking_df = pd.DataFrame(wyniki_rankingu).sort_values(by="Wynik", ascending=False).reset_index(drop=True)
ranking_df.index += 1
moje_miejsce = ranking_df[ranking_df['Grupa'] == "GRUPA 13 (MY)"].index[0]

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Panel Rebalansu")
    if not czy_mozna_rebalansowac:
        st.error(f"🔒 **Blokada do niedzieli**")
        st.info(f"Formularz wygasa za: {roznica.days}d {roznica.seconds//3600}h")
    else:
        st.success("🔓 **Panel Otwarty**")
        if st.text_input("PIN:", type="password") == "2137":
            nowy_kapital = st.number_input("Kapitał startowy", value=float(round(stan_konta_na_zywo, 2)))
            nowe_pozycje = {}
            suma_zaang = 0.0
            for aktywo in TICKERY.keys():
                val = st.number_input(aktywo, value=float(pozycje_z_panelu.get(aktywo, 0.0)), step=5.0)
                nowe_pozycje[aktywo] = val
                suma_zaang += abs(val)
            
            st.divider()
            if suma_zaang > nowy_kapital:
                st.error(f"Limit przekroczony: {suma_zaang}/{nowy_kapital}")
            else:
                if st.button("💾 ZAPISZ USTAWIENIA"):
                    zapisz_ustawienia({"kapital_startowy": nowy_kapital, "pozycje": nowe_pozycje})
                    st.cache_data.clear()
                    st.success("Zapisano!")
                    time.sleep(1)
                    st.rerun()

# === MAIN UI ===
st.title("📈 Portfel grupy 13. LIVE")

with elements("dashboard_stats"):
    with mui.Grid(container=True, spacing=2):
        with mui.Grid(item=True, xs=True):
            with mui.Paper(sx={"padding": "15px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Kapitał Startowy", variant="overline", sx={"color": "#aaa"})
                mui.Typography(f"{kapital_poczatkowy:.2f} j.p.", variant="h5", sx={"color": "#00ff00", "fontWeight": "bold"})
        with mui.Grid(item=True, xs=True):
            with mui.Paper(sx={"padding": "15px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Zysk / Strata", variant="overline", sx={"color": "#aaa"})
                color = "#00ff00" if zysk_laczny >= 0 else "#ff0000"
                mui.Typography(f"{zysk_laczny:+.2f} j.p.", variant="h5", sx={"color": color, "fontWeight": "bold"})
        with mui.Grid(item=True, xs=True):
            with mui.Paper(sx={"padding": "15px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Stan Konta", variant="overline", sx={"color": "#aaa"})
                mui.Typography(f"{stan_konta_na_zywo:.2f} j.p.", variant="h5", sx={"fontWeight": "bold"})
        with mui.Grid(item=True, xs=True):
            with mui.Paper(sx={"padding": "15px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Wynik %", variant="overline", sx={"color": "#aaa"})
                color = "#00ff00" if zmiana_proc_total >= 0 else "#ff0000"
                mui.Typography(f"{zmiana_proc_total:+.2f}%", variant="h5", sx={"color": color, "fontWeight": "bold"})
        with mui.Grid(item=True, xs=True):
            with mui.Paper(sx={"padding": "15px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Miejsce", variant="overline", sx={"color": "#FFD700"})
                rank_color = "#FFD700" if moje_miejsce <= 3 else "#fff" 
                mui.Typography(f"{moje_miejsce} / {len(ranking_df)}", variant="h5", sx={"color": rank_color, "fontWeight": "bold"})

st.divider()

# === WYKRES ===
fig = go.Figure()

if not historia_portfela.empty:
    historia_portfela = historia_portfela.bfill().ffill().fillna(0)
    total_my = historia_portfela.sum(axis=1)
    
    # Rysowanie tła (poświaty)
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my.clip(lower=0), fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.1)', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my.clip(upper=0), fill='tozeroy', fillcolor='rgba(255, 0, 0, 0.1)', line=dict(width=0), showlegend=False))
    
    # Główna linia Waszego Portfela
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my, line=dict(color='white', width=3), name='Nasz Portfel'))

    # ADNOTACJA: Kropka i tekst dla Waszego portfela
    ostatni_czas_my = total_my.index[-1]
    ostatnia_wartosc_my = total_my.iloc[-1]
    kolor_tekstu_my = "#00ff00" if ostatnia_wartosc_my >= 0 else "#ff0000"
    
    fig.add_annotation(
        x=ostatni_czas_my,
        y=ostatnia_wartosc_my,
        text=f"<b>{ostatnia_wartosc_my:+.2f} j.p.</b>",
        showarrow=True,
        arrowhead=0, # Brak typowej strzałki, zrobimy tylko linię i punkt
        arrowwidth=1,
        arrowcolor="white",
        ax=40, # Przesunięcie w poziomie (w prawo)
        ay=0,  # Przesunięcie w pionie (na równo)
        font=dict(size=14, color=kolor_tekstu_my),
        bgcolor="rgba(30, 30, 30, 0.8)", # Ciemne tło dla lepszej czytelności
        bordercolor=kolor_tekstu_my,
        borderwidth=1,
        borderpad=4
    )
    # Dodanie wyraźnej kropki na końcu linii
    fig.add_trace(go.Scatter(
        x=[ostatni_czas_my], y=[ostatnia_wartosc_my],
        mode='markers', marker=dict(color='white', size=8, line=dict(color=kolor_tekstu_my, width=2)),
        showlegend=False, hoverinfo='skip'
    ))

if not historia_sredniej.empty:
    historia_sredniej = historia_sredniej.bfill().ffill().fillna(0)
    total_avg = historia_sredniej.sum(axis=1)
    
    # Linia Benchmarku (Średnia)
    fig.add_trace(go.Scatter(
        x=total_avg.index, 
        y=total_avg, 
        line=dict(color='rgba(255, 215, 0, 0.7)', width=2, dash='dot'), 
        name='Średnia Konkursu'
    ))
    
    # ADNOTACJA: Kropka i tekst dla Benchmarku
    ostatni_czas_avg = total_avg.index[-1]
    ostatnia_wartosc_avg = total_avg.iloc[-1]
    
    fig.add_annotation(
        x=ostatni_czas_avg,
        y=ostatnia_wartosc_avg,
        text=f"Średnia: {ostatnia_wartosc_avg:+.2f}",
        showarrow=True,
        arrowhead=0,
        arrowwidth=1,
        arrowcolor="gold",
        ax=45,
        ay=-25, # Lekko do góry, żeby nie nakładało się na Wasz wynik
        font=dict(size=11, color="gold"),
        bgcolor="rgba(0, 0, 0, 0.5)"
    )
    fig.add_trace(go.Scatter(
        x=[ostatni_czas_avg], y=[ostatnia_wartosc_avg],
        mode='markers', marker=dict(color='gold', size=6),
        showlegend=False, hoverinfo='skip'
    ))

# Aktualizacja układu (zrobimy trochę więcej miejsca po prawej stronie na te napisy)
fig.update_layout(
    template="plotly_dark", 
    height=450, 
    margin=dict(l=10, r=80, t=10, b=10), # Zwiększono prawy margines (r=80)
    yaxis=dict(zeroline=True, zerolinecolor='gray'),
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
)
st.plotly_chart(fig, use_container_width=True)

# Tabele pod spodem
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Otwarte pozycje")
    if dane_do_tabeli:
        st.dataframe(pd.DataFrame(dane_do_tabeli), use_container_width=True, hide_index=True)
    else:
        st.info("Portfel jest obecnie pusty.")

with col_right:
    st.subheader("🏆 Ranking LIVE (TOP 10)")
    st.dataframe(ranking_df.head(10), use_container_width=True, hide_index=False)

st.caption(f"Ostatnie odświeżenie: {teraz.strftime('%H:%M:%S')} | Auto-odświeżanie: 60s")
time.sleep(60)
st.rerun()