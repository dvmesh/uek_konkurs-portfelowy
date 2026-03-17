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
            hist.index = hist.index.tz_localize(None)
        return hist
    except:
        return pd.DataFrame()

zysk_laczny = 0.0
dane_do_tabeli = []
historia_portfela = pd.DataFrame()

# === POBIERANIE DANYCH ===
with st.spinner('Aktualizacja danych rynkowych...'):
    cache_hist = {}
    for nazwa, wielkosc in pozycje_z_panelu.items():
        if wielkosc == 0: continue
        ticker = TICKERY[nazwa]
        hist = pobierz_dane_rynkowe(ticker, data_startu_str)
        if not hist.empty:
            cena_otw = hist['Open'].iloc[0]
            cena_live = hist['Close'].iloc[-1]
            zmiana_proc = (cena_live - cena_otw) / cena_otw
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
            
            seria = ((hist['Close'] - cena_otw) / cena_otw) * abs(wielkosc) * (1 if wielkosc > 0 else -1)
            seria.name = nazwa
            if historia_portfela.empty:
                historia_portfela = pd.DataFrame(seria)
            else:
                historia_portfela = historia_portfela.join(seria, how='outer')

stan_konta_na_zywo = kapital_poczatkowy + zysk_laczny
zmiana_proc_total = (zysk_laczny / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0

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

# Karty statystyk (Material UI)
with elements("dashboard_stats"):
    with mui.Grid(container=True, spacing=2):
        # Karta 1
        with mui.Grid(item=True, xs=3):
            with mui.Paper(sx={"padding": "20px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Kapitał Startowy", variant="overline", sx={"color": "#aaa"})
                mui.Typography(f"{kapital_poczatkowy:.2f} j.p.", variant="h5", sx={"color": "#00ff00", "fontWeight": "bold"})
        # Karta 2
        with mui.Grid(item=True, xs=3):
            with mui.Paper(sx={"padding": "20px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Zysk / Strata", variant="overline", sx={"color": "#aaa"})
                color = "#00ff00" if zysk_laczny >= 0 else "#ff0000"
                mui.Typography(f"{zysk_laczny:+.2f} j.p.", variant="h5", sx={"color": color, "fontWeight": "bold"})
        # Karta 3
        with mui.Grid(item=True, xs=3):
            with mui.Paper(sx={"padding": "20px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Stan Konta", variant="overline", sx={"color": "#aaa"})
                mui.Typography(f"{stan_konta_na_zywo:.2f} j.p.", variant="h5", sx={"fontWeight": "bold"})
        # Karta 4
        with mui.Grid(item=True, xs=3):
            with mui.Paper(sx={"padding": "20px", "textAlign": "center", "background": "#1e1e1e", "color": "white"}):
                mui.Typography("Wynik %", variant="overline", sx={"color": "#aaa"})
                color = "#00ff00" if zmiana_proc_total >= 0 else "#ff0000"
                mui.Typography(f"{zmiana_proc_total:+.2f}%", variant="h5", sx={"color": color, "fontWeight": "bold"})

st.divider()

# Wykres
if not historia_portfela.empty:
    historia_portfela = historia_portfela.bfill().ffill().fillna(0)
    historia_portfela['Zysk_Total'] = historia_portfela.sum(axis=1)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Total'].clip(lower=0), fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.1)', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Total'].clip(upper=0), fill='tozeroy', fillcolor='rgba(255, 0, 0, 0.1)', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Total'], line=dict(color='white', width=2), name='Portfel Total'))
    
    fig.update_layout(template="plotly_dark", height=450, margin=dict(l=10, r=10, t=10, b=10), 
                      yaxis=dict(zeroline=True, zerolinecolor='gray'))
    st.plotly_chart(fig, use_container_width=True)

# Tabela
st.subheader("Otwarte pozycje")
if dane_do_tabeli:
    st.dataframe(pd.DataFrame(dane_do_tabeli), use_container_width=True, hide_index=True)
else:
    st.info("Portfel jest obecnie pusty.")

st.caption(f"Ostatnie odświeżenie: {teraz.strftime('%H:%M:%S')} | Auto-odświeżanie: 60s")
time.sleep(60)
st.rerun()