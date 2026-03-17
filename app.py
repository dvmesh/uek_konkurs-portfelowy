import time
import json
import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from streamlit_elements import elements, mui, html

# === KONFIGURACJA ===
st.set_page_config(page_title="Aplikacja portfelowa", page_icon="🚀", layout="wide")

# === KOLORYSTYKA (Nowoczesna, stonowana) ===
KOLOR_ZYSK = "#4ade80"       # Szmaragdowy (Muted Green)
KOLOR_STRATA = "#f87171"     # Koralowy (Muted Red)
KOLOR_NEUTRAL = "#9ca3af"    # Szary (Gray)
KOLOR_ZOLTY = "#fbbf24"      # Bursztyn (Muted Gold)
KOLOR_TLA_KART = "#262730"   # Natywny ciemny szary Streamlita

st.markdown("""
    <style>
    [data-testid="collapsedControl"] { overflow: visible !important; }
    [data-testid="collapsedControl"]::after {
        content: "REBALANS"; position: absolute; top: 60px; left: 50%; transform: translateX(-50%);
        writing-mode: vertical-rl; text-orientation: upright;
        font-size: 11px; font-weight: 700; color: rgba(255, 255, 255, 0.3);
        letter-spacing: 4px; pointer-events: none;
    }
    </style>
    """, unsafe_allow_html=True)

PLIK_USTAWIEN = "portfel.json"

def wczytaj_ustawienia():
    if os.path.exists(PLIK_USTAWIEN):
        try:
            with open(PLIK_USTAWIEN, "r") as f:
                return json.load(f)
        except: pass
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

TICKERY = {"S&P 500": "^GSPC", "US10Y Yield": "^TNX", "Złoto (Gold)": "GC=F", "EUR/USD": "EURUSD=X"}
MAPOWANIE_PDF = {"SPX": "S&P 500", "GOLD": "Złoto (Gold)", "RENT": "US10Y Yield", "EURUSD": "EUR/USD"}

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
        if hist.empty: hist = ticker_obj.history(period="5d", interval="1h")
        if not hist.empty:
            if hist.index.tz is not None:
                hist.index = hist.index.tz_convert('Europe/Warsaw')
            hist.index = hist.index.tz_localize(None)
        return hist
    except: return pd.DataFrame()

zysk_laczny = 0.0
dane_do_tabeli = []
zmiany_rynkowe = {}
wszystkie_historie_zmian = {}

# === POBIERANIE DANYCH ===
with st.spinner('Synchronizacja z giełdą...'):
    for nazwa, ticker in TICKERY.items():
        hist = pobierz_dane_rynkowe(ticker, data_startu_str)
        if not hist.empty:
            cena_otw = hist['Open'].iloc[0]
            cena_live = hist['Close'].iloc[-1]
            zmiana_proc = (cena_live - cena_otw) / cena_otw
            zmiany_rynkowe[nazwa] = zmiana_proc
            wszystkie_historie_zmian[nazwa] = (hist['Close'] - cena_otw) / cena_otw
            
            wielkosc = pozycje_z_panelu.get(nazwa, 0.0)
            if wielkosc != 0:
                wynik_poz = wielkosc * zmiana_proc
                zysk_laczny += wynik_poz
                dane_do_tabeli.append({
                    "Instrument": nazwa,
                    "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
                    "Wielkość": wielkosc,
                    "Cena Start": cena_otw,
                    "Cena LIVE": cena_live,
                    "Wynik": wynik_poz
                })

stan_konta_na_zywo = kapital_poczatkowy + zysk_laczny
zmiana_proc_total = (zysk_laczny / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0

# === HISTORIE DO WYKRESÓW ===
historia_portfela = pd.DataFrame()
for nazwa, wielkosc in pozycje_z_panelu.items():
    if wielkosc != 0 and nazwa in wszystkie_historie_zmian:
        seria = wszystkie_historie_zmian[nazwa] * abs(wielkosc) * (1 if wielkosc > 0 else -1)
        historia_portfela = pd.DataFrame(seria) if historia_portfela.empty else historia_portfela.join(seria.rename(nazwa), how='outer')

historia_sredniej = pd.DataFrame()
nasze_obs = {"SPX": pozycje_z_panelu.get("S&P 500", 0.0), "GOLD": pozycje_z_panelu.get("Złoto (Gold)", 0.0), "RENT": pozycje_z_panelu.get("US10Y Yield", 0.0), "EURUSD": pozycje_z_panelu.get("EUR/USD", 0.0)}
wszystkie_grupy = list(DANE_GRUP.values()) + [nasze_obs]

for klucz_pdf, nazwa_inst in MAPOWANIE_PDF.items():
    srednia_waga = sum(g.get(klucz_pdf, 0) for g in wszystkie_grupy) / len(wszystkie_grupy)
    if srednia_waga != 0 and nazwa_inst in wszystkie_historie_zmian:
        seria_avg = wszystkie_historie_zmian[nazwa_inst] * abs(srednia_waga) * (1 if srednia_waga > 0 else -1)
        historia_sredniej = pd.DataFrame(seria_avg) if historia_sredniej.empty else historia_sredniej.join(seria_avg.rename(nazwa_inst), how='outer')

# === MAX DRAWDOWN ===
max_dd_proc = 0.0
if not historia_portfela.empty:
    historia_portfela = historia_portfela.bfill().ffill().fillna(0)
    wartosc_konta_historia = kapital_poczatkowy + historia_portfela.sum(axis=1)
    szczyt = wartosc_konta_historia.cummax()
    drawdown = (wartosc_konta_historia - szczyt) / szczyt * 100
    max_dd_proc = drawdown.min()

# === RANKING ===
wyniki_rankingu = [{"Grupa": "GRUPA 13 (MY)", "Wynik": stan_konta_na_zywo}]
for grupa, pozycje in DANE_GRUP.items():
    wynik_g = 100.0
    for inst, waga in pozycje.items():
        k_rynk = MAPOWANIE_PDF.get(inst)
        if k_rynk and k_rynk in zmiany_rynkowe: wynik_g += waga * zmiany_rynkowe[k_rynk]
    wyniki_rankingu.append({"Grupa": grupa, "Wynik": round(wynik_g, 4)})

ranking_df = pd.DataFrame(wyniki_rankingu).sort_values(by="Wynik", ascending=False).reset_index(drop=True)
ranking_df.index += 1
moje_miejsce = ranking_df[ranking_df['Grupa'] == "GRUPA 13 (MY)"].index[0]

if 'poprzednie_miejsce' not in st.session_state:
    st.session_state.poprzednie_miejsce = moje_miejsce
else:
    if moje_miejsce < st.session_state.poprzednie_miejsce:
        st.toast(f"🚀 Awans! Jesteśmy na {moje_miejsce} miejscu!", icon="🔥")
    elif moje_miejsce > st.session_state.poprzednie_miejsce:
        st.toast(f"⚠️ Spadek na {moje_miejsce} miejsce.", icon="📉")
    st.session_state.poprzednie_miejsce = moje_miejsce

# === SIDEBAR ===
with st.sidebar:
    st.header("⚙️ Panel Rebalansu")
    if not czy_mozna_rebalansowac:
        st.error("🔒 **Blokada do niedzieli**")
        st.info(f"Wygasa za: {roznica.days}d {roznica.seconds//3600}h")
    else:
        st.success("🔓 **Panel Otwarty**")
        if st.text_input("PIN:", type="password") == "2137":
            nk = st.number_input("Kapitał", value=float(round(stan_konta_na_zywo, 2)))
            np = {k: st.number_input(k, value=float(pozycje_z_panelu.get(k, 0)), step=5.0) for k in TICKERY.keys()}
            if sum(abs(v) for v in np.values()) > nk: st.error("Limit przekroczony!")
            elif st.button("💾 ZAPISZ USTAWIENIA"):
                zapisz_ustawienia({"kapital_startowy": nk, "pozycje": np})
                st.cache_data.clear()
                st.rerun()

# === GŁÓWNY INTERFEJS ===
st.title("Analiza Portfela - Grupa 13")

with elements("stats"):
    with mui.Grid(container=True, spacing=2):
        karty = [
            ("Start", f"{kapital_poczatkowy:.2f}", KOLOR_NEUTRAL),
            ("Zysk", f"{zysk_laczny:+.2f}", KOLOR_ZYSK if zysk_laczny >= 0 else KOLOR_STRATA),
            ("Konto", f"{stan_konta_na_zywo:.2f}", "#ffffff"),
            ("Wynik", f"{zmiana_proc_total:+.2f}%", KOLOR_ZYSK if zmiana_proc_total >= 0 else KOLOR_STRATA),
            ("MDD", f"{max_dd_proc:.2f}%", KOLOR_STRATA if max_dd_proc < 0 else KOLOR_NEUTRAL),
            ("Miejsce", f"{moje_miejsce} / {len(ranking_df)}", KOLOR_ZOLTY if moje_miejsce <=3 else "#ffffff")
        ]
        for lab, val, col in karty:
            with mui.Grid(item=True, xs=True):
                with mui.Paper(sx={"padding": "15px", "textAlign": "center", "background": KOLOR_TLA_KART, "color": "white", "borderRadius": "8px", "boxShadow": "0 2px 5px rgba(0,0,0,0.2)"}):
                    mui.Typography(lab, variant="overline", sx={"color": KOLOR_NEUTRAL, "lineHeight": 1, "letterSpacing": "1px"})
                    mui.Typography(val, variant="h5", sx={"color": col, "fontWeight": "600", "marginTop": "5px"})

st.divider()

# === WYKRES ===
fig = go.Figure()

if not historia_portfela.empty:
    total_my = historia_portfela.sum(axis=1)
    
    # Delikatne, przezroczyste tło wykresu (poświata)
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my.clip(lower=0), fill='tozeroy', fillcolor='rgba(74, 222, 128, 0.08)', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my.clip(upper=0), fill='tozeroy', fillcolor='rgba(248, 113, 113, 0.08)', line=dict(width=0), showlegend=False))
    
    # Główna linia portfela (jasnoszara/biała)
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my, line=dict(color='#e5e7eb', width=2.5), name='Nasz Portfel'))

    ost_x = total_my.index[-1]
    ost_y = total_my.iloc[-1]
    kol = KOLOR_ZYSK if ost_y >= 0 else KOLOR_STRATA
    
    fig.add_annotation(x=ost_x, y=ost_y, text=f"<b>{ost_y:+.2f}</b>", showarrow=True, arrowhead=0, arrowcolor=kol, ax=40, ay=0, font=dict(color=kol, size=13), bgcolor="rgba(38, 39, 48, 0.8)", bordercolor=kol, borderpad=3)
    fig.add_trace(go.Scatter(x=[ost_x], y=[ost_y], mode='markers', marker=dict(color=kol, size=7), showlegend=False))

if not historia_sredniej.empty:
    historia_sredniej = historia_sredniej.bfill().ffill().fillna(0)
    total_avg = historia_sredniej.sum(axis=1)
    
    fig.add_trace(go.Scatter(x=total_avg.index, y=total_avg, line=dict(color='rgba(251, 191, 36, 0.6)', width=1.5, dash='dot'), name='Benchmark Konkursu'))
    
    ost_x_a = total_avg.index[-1]
    ost_y_a = total_avg.iloc[-1]
    fig.add_annotation(x=ost_x_a, y=ost_y_a, text=f"Śr: {ost_y_a:+.2f}", showarrow=True, arrowhead=0, arrowcolor=KOLOR_ZOLTY, ax=45, ay=-25, font=dict(size=11, color=KOLOR_ZOLTY), bgcolor="rgba(38, 39, 48, 0.6)")
    fig.add_trace(go.Scatter(x=[ost_x_a], y=[ost_y_a], mode='markers', marker=dict(color=KOLOR_ZOLTY, size=5), showlegend=False))

fig.update_layout(
    template="plotly_dark", height=450, margin=dict(l=10, r=80, t=10, b=10), 
    yaxis=dict(zeroline=True, zerolinecolor='rgba(255, 255, 255, 0.1)', gridcolor='rgba(255, 255, 255, 0.05)'), 
    xaxis=dict(gridcolor='rgba(255, 255, 255, 0.05)'),
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(0,0,0,0)'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig, use_container_width=True)

# === RENTGEN I RANKING ===
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("Pozycje")
    if dane_do_tabeli:
        df_poz = pd.DataFrame(dane_do_tabeli)
        st.dataframe(
            df_poz,
            column_config={
                "Cena Start": st.column_config.NumberColumn(format="%.4f"),
                "Cena LIVE": st.column_config.NumberColumn(format="%.4f"),
                "Wynik": st.column_config.ProgressColumn("Zysk/Strata", format="%f", min_value=-50, max_value=50)
            },
            use_container_width=True, hide_index=True
        )
    else: st.info("Brak pozycji.")

with col_right:
    st.subheader("Ranking Konkursu")
    st.dataframe(ranking_df.head(10), use_container_width=True, hide_index=False)

# === RADAR TŁUMU (SENTYMENT) ===
st.divider()
st.subheader("Analiza Sentymentu Grup")

sentyment = {"S&P 500": {"LONG": 0, "SHORT": 0}, "Złoto (Gold)": {"LONG": 0, "SHORT": 0}, "US10Y Yield": {"LONG": 0, "SHORT": 0}, "EUR/USD": {"LONG": 0, "SHORT": 0}}
for obs in wszystkie_grupy:
    for inst, val in obs.items():
        k = MAPOWANIE_PDF.get(inst)
        if k:
            if val > 0: sentyment[k]["LONG"] += val
            elif val < 0: sentyment[k]["SHORT"] += abs(val)

fig_pie = make_subplots(rows=1, cols=4, specs=[[{"type": "domain"}, {"type": "domain"}, {"type": "domain"}, {"type": "domain"}]], subplot_titles=list(sentyment.keys()))
kolory_pie = [KOLOR_ZYSK, KOLOR_STRATA]

for i, (inst, dane) in enumerate(sentyment.items()):
    fig_pie.add_trace(go.Pie(labels=['LONG', 'SHORT'], values=[dane['LONG'], dane['SHORT']], marker_colors=kolory_pie, textinfo='percent', hole=.5, textfont=dict(color='#ffffff')), 1, i+1)

# Kolorowanie tytułów wykresów kołowych
for annotation in fig_pie['layout']['annotations']:
    annotation['font'] = dict(size=13, color=KOLOR_NEUTRAL)

fig_pie.update_layout(
    template="plotly_dark", height=250, margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig_pie, use_container_width=True)

st.caption(f"Ostatnie odświeżenie: {teraz.strftime('%H:%M:%S')} | Auto-odświeżanie: 60s")
time.sleep(60)
st.rerun()