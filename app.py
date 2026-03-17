import time
import json
import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Grupa 13", page_icon="📈", layout="wide")

PLIK_USTAWIEN = "portfel.json"

def wczytaj_ustawienia():
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

ustawienia = wczytaj_ustawienia()
kapital_poczatkowy = ustawienia["kapital_startowy"]
pozycje_z_panelu = ustawienia["pozycje"]

TICKERY = {
    "S&P 500": "^GSPC",
    "US10Y Yield": "^TNX",
    "Złoto (Gold)": "GC=F",
    "EUR/USD": "EURUSD=X"
}

teraz = datetime.now()
ostatni_poniedzialek = teraz - timedelta(days=teraz.weekday())
data_startu_str = ostatni_poniedzialek.strftime('%Y-%m-%d')

dni_do_niedzieli = 6 - teraz.weekday()
najblizsza_niedziela = teraz + timedelta(days=dni_do_niedzieli)
deadline = najblizsza_niedziela.replace(hour=23, minute=0, second=0, microsecond=0)

if teraz > deadline:
    deadline += timedelta(days=7)

roznica = deadline - teraz
dni = roznica.days
godziny, reszta = divmod(roznica.seconds, 3600)
minuty, _ = divmod(reszta, 60)

czy_mozna_rebalansowac = (teraz.weekday() == 6) and (teraz.hour < 23)

@st.cache_data(ttl=60)
def pobierz_dane_rynkowe(ticker, data_startu):
    ticker_obj = yf.Ticker(ticker)
    hist = ticker_obj.history(start=data_startu, interval="1h")
    if hist.empty:
        hist = ticker_obj.history(period="5d", interval="1h")
    if not hist.empty:
        hist.index = hist.index.tz_localize(None)
    return hist

zysk_laczny = 0.0
dane_do_tabeli = []
historia_portfela = pd.DataFrame()

with st.spinner('Pobieram dane z giełdy...'):
    cache_hist = {}
    for nazwa, wielkosc in pozycje_z_panelu.items():
        if wielkosc == 0:
            continue
        ticker = TICKERY[nazwa]
        try:
            if ticker not in cache_hist:
                cache_hist[ticker] = pobierz_dane_rynkowe(ticker, data_startu_str)
            hist = cache_hist[ticker]
            if not hist.empty:
                cena_otwarcia = hist['Open'].iloc[0]
                cena_live = hist['Close'].iloc[-1]
                zmiana_procentowa = (cena_live - cena_otwarcia) / cena_otwarcia
                wynik_pozycji = wielkosc * zmiana_procentowa
                zysk_laczny += wynik_pozycji
                zmiana_proc_total = zmiana_procentowa * 100
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
            st.warning(f"Błąd pobierania danych dla {nazwa}: {e}")

stan_konta_na_zywo = kapital_poczatkowy + zysk_laczny

with st.sidebar:
    st.header("⚙️ Panel Rebalansu")
    
    if not czy_mozna_rebalansowac:
        st.error("🔒 **Panel Zablokowany**\n\nZgodnie z regulaminem, edycja portfela jest możliwa **tylko w niedzielę do godziny 23:00**.")
        st.info("Poczekaj do niedzieli, aby wprowadzić nowy formularz.")
    else:
        st.success("🔓 **Niedziela! Panel Otwarty**")
        haslo = st.text_input("Podaj PIN:", type="password")
        
        if haslo == "2137":
            st.markdown(f"**Twój wypracowany kapitał na start:** `{stan_konta_na_zywo:.2f} j.p.`")
            nowy_kapital = st.number_input("Zatwierdź kapitał startowy", value=float(round(stan_konta_na_zywo, 2)), step=1.0)
            
            st.markdown("### Nowe obstawienia (LONG > 0, SHORT < 0)")
            nowe_pozycje = {}
            suma_zaangazowania = 0.0
            
            for aktywo in TICKERY.keys():
                wartosc = st.number_input(aktywo, value=float(pozycje_z_panelu.get(aktywo, 0.0)), step=10.0)
                nowe_pozycje[aktywo] = wartosc
                suma_zaangazowania += abs(wartosc) 
                
            st.divider()
            st.write(f"Zainwestowano: **{suma_zaangazowania}** / {nowy_kapital} j.p.")
            
            if suma_zaangazowania > nowy_kapital:
                st.error("❌ Regulamin: Przekroczyłeś dostępny kapitał konta!")
            elif suma_zaangazowania < 20.0 and suma_zaangazowania > 0:
                st.error("❌ Regulamin: Minimalny zainwestowany kapitał to 20 j.p.!")
            else:
                if st.button("💾 ZAPISZ I WYŚLIJ FORMULARZ"):
                    nowe_ustawienia = {
                        "kapital_startowy": nowy_kapital,
                        "pozycje": nowe_pozycje
                    }
                    zapisz_ustawienia(nowe_ustawienia)
                    st.cache_data.clear() 
                    st.success("Zapisano na nowy tydzień!")
                    time.sleep(1)
                    st.rerun()

st.title("📈 Portfel grupy 13. LIVE")

if not historia_portfela.empty:
    historia_portfela = historia_portfela.bfill().ffill().fillna(0)
    historia_portfela['Zysk_Total'] = historia_portfela.sum(axis=1)
    zysk_pos = historia_portfela['Zysk_Total'].clip(lower=0) 
    zysk_neg = historia_portfela['Zysk_Total'].clip(upper=0) 

st.divider()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Kapitał na początku tyg.", f"{kapital_poczatkowy:.2f} j.p.")
col2.metric("Zysk / Strata", f"{zysk_laczny:.2f} j.p.", f"{zysk_laczny:.4f} j.p.")
col3.metric("Stan Konta", f"{stan_konta_na_zywo:.2f} j.p.", f"{zysk_laczny:.4f} j.p.")
col4.metric("Zmiana Procentowa", f"{zmiana_proc_total:.2f}%", f"{zmiana_proc_total:.5f}%")

st.divider()

if not historia_portfela.empty:
    fig_portfel = go.Figure()
    fig_portfel.add_trace(go.Scatter(x=historia_portfela.index, y=zysk_pos, mode='lines', line=dict(width=0), fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.15)', showlegend=False, hoverinfo='skip'))
    fig_portfel.add_trace(go.Scatter(x=historia_portfela.index, y=zysk_neg, mode='lines', line=dict(width=0), fill='tozeroy', fillcolor='rgba(255, 0, 0, 0.15)', showlegend=False, hoverinfo='skip'))
    fig_portfel.add_trace(go.Scatter(x=historia_portfela.index, y=historia_portfela['Zysk_Total'], mode='lines', line=dict(width=3, color="#ffffff"), name='Skumulowany wynik'))

    fig_portfel.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=30, b=20), height=400, yaxis=dict(zeroline=True, zerolinecolor='rgba(255, 255, 255, 0.5)', zerolinewidth=1))
    st.plotly_chart(fig_portfel, use_container_width=True)

st.subheader("Otwarte pozycje w tym tygodniu")
if dane_do_tabeli:
    df = pd.DataFrame(dane_do_tabeli)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Brak otwartych pozycji.")

st.divider()
st.caption("🟢 System Auto-odświeżania: 60 sek. Zgodność z Regulaminem Włączona.")

time.sleep(60)
st.rerun()
