import time
import json
import os
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from streamlit_elements import elements, mui

# === KONFIGURACJA UI ===
st.set_page_config(page_title="Terminal Konkursowy", layout="wide")

KOLOR_ZYSK = "#4ade80"
KOLOR_STRATA = "#f87171"
KOLOR_NEUTRAL = "#9ca3af"
KOLOR_ZOLTY = "#fbbf24"
KOLOR_RYNEK = "#38bdf8"
KOLOR_TLA_KART = "#262730"

# === SYSTEM ZAPISU I DANYCH ===
PLIK_USTAWIEN = "portfel.json"

def wczytaj_dane_statyczne():
    try:
        with open("dane_statyczne.json", "r") as f:
            return json.load(f)
    except:
        st.error("Błąd: Brak pliku dane_statyczne.json!")
        return {"TICKERY": {}, "MAPOWANIE_PDF": {}, "DANE_GRUP": {}}

def wczytaj_ustawienia():
    if os.path.exists(PLIK_USTAWIEN):
        try:
            with open(PLIK_USTAWIEN, "r") as f:
                return json.load(f)
        except: pass
    return {}

def zapisz_ustawienia(ustawienia):
    with open(PLIK_USTAWIEN, "w") as f:
        json.dump(ustawienia, f)

dane_stat = wczytaj_dane_statyczne()
TICKERY = dane_stat.get("TICKERY", {})
MAPOWANIE_PDF = dane_stat.get("MAPOWANIE_PDF", {})
DANE_GRUP = dane_stat.get("DANE_GRUP", {})

ustawienia = wczytaj_ustawienia()

# --- SCALANIE DANYCH ---
aktywne_portfele = {}
for g_nazwa, g_poz in DANE_GRUP.items():
    aktywne_portfele[g_nazwa] = {
        "kapital_startowy": 100.0,
        "pozycje": {
            "S&P 500": g_poz.get("SPX", 0.0), "Złoto (Gold)": g_poz.get("GOLD", 0.0),
            "US10Y Yield": g_poz.get("RENT", 0.0), "EUR/USD": g_poz.get("EURUSD", 0.0)
        }
    }

for g_nazwa, g_dane in ustawienia.items():
    aktywne_portfele[g_nazwa] = g_dane 

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
        hist = yf.Ticker(ticker).history(start=data_startu, interval="1h")
        if hist.empty: hist = yf.Ticker(ticker).history(period="5d", interval="1h")
        if not hist.empty:
            if hist.index.tz is not None:
                hist.index = hist.index.tz_convert('Europe/Warsaw')
            hist.index = hist.index.tz_localize(None)
        return hist
    except: return pd.DataFrame()

# === 1. POBIERANIE DANYCH RYNKOWYCH ===
zmiany_rynkowe = {}
wszystkie_historie_zmian = {}

with st.spinner('Synchronizacja danych rynkowych...'):
    for nazwa, ticker in TICKERY.items():
        hist = pobierz_dane_rynkowe(ticker, data_startu_str)
        if not hist.empty:
            cena_otw = hist['Open'].iloc[0]
            cena_live = hist['Close'].iloc[-1]
            zmiany_rynkowe[nazwa] = (cena_live - cena_otw) / cena_otw
            wszystkie_historie_zmian[nazwa] = (hist['Close'] - cena_otw) / cena_otw

# === 2. WYLICZENIE RANKINGU ===
wyniki_rankingu = []
for g_nazwa, g_dane in aktywne_portfele.items():
    wynik_g = g_dane["kapital_startowy"]
    for inst, waga in g_dane["pozycje"].items():
        if inst in zmiany_rynkowe:
            wynik_g += waga * zmiany_rynkowe[inst]
    wyniki_rankingu.append({"Grupa": g_nazwa, "Wynik": round(wynik_g, 4)})

ranking_df = pd.DataFrame(wyniki_rankingu).sort_values(by="Wynik", ascending=False).reset_index(drop=True)
ranking_df.index += 1
lider_konkursu = ranking_df.iloc[0]["Grupa"] if not ranking_df.empty else "Grupa 13"

# === 3. UI: WYBÓR GRUPY NA GÓRZE ===
lista_grup = sorted(list(aktywne_portfele.keys()))
idx_domyslny = lista_grup.index(lider_konkursu) if lider_konkursu in lista_grup else 0

col_t, col_w = st.columns([2, 1])
with col_w:
    wybrana_grupa = st.selectbox("Wybór portfela:", lista_grup, index=idx_domyslny)
with col_t:
    st.title(f"Widok portfela: {wybrana_grupa}")

# === 4. OBLICZENIA DLA WYBRANEJ GRUPY ===
kapital_poczatkowy = float(aktywne_portfele[wybrana_grupa]["kapital_startowy"])
pozycje_z_panelu = aktywne_portfele[wybrana_grupa]["pozycje"]

zysk_laczny = 0.0
dane_do_tabeli = []
historia_portfela = pd.DataFrame()

for nazwa, wielkosc in pozycje_z_panelu.items():
    if wielkosc != 0 and nazwa in zmiany_rynkowe:
        zmiana_proc = zmiany_rynkowe[nazwa]
        wynik_poz = wielkosc * zmiana_proc
        zysk_laczny += wynik_poz
        
        hist = pobierz_dane_rynkowe(TICKERY[nazwa], data_startu_str)
        c_start = hist['Open'].iloc[0] if not hist.empty else 0
        c_live = hist['Close'].iloc[-1] if not hist.empty else 0
        
        dane_do_tabeli.append({
            "Instrument": nazwa, "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
            "Wielkość": wielkosc, "Cena Start": c_start, "Cena LIVE": c_live, "Wynik": wynik_poz
        })
        
        seria = wszystkie_historie_zmian[nazwa] * abs(wielkosc) * (1 if wielkosc > 0 else -1)
        historia_portfela = pd.DataFrame(seria) if historia_portfela.empty else historia_portfela.join(seria.rename(nazwa), how='outer')

stan_konta_na_zywo = kapital_poczatkowy + zysk_laczny
zmiana_proc_total = (zysk_laczny / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0

# === 5. HISTORIE BENCHMARKÓW ===
historia_sredniej = pd.DataFrame()
liczba_grup = len(aktywne_portfele)
for nazwa_inst in TICKERY.keys():
    suma_wag = sum(g["pozycje"].get(nazwa_inst, 0.0) for g in aktywne_portfele.values())
    srednia_waga = suma_wag / liczba_grup if liczba_grup > 0 else 0
    if srednia_waga != 0 and nazwa_inst in wszystkie_historie_zmian:
        seria_avg = wszystkie_historie_zmian[nazwa_inst] * abs(srednia_waga) * (1 if srednia_waga > 0 else -1)
        historia_sredniej = pd.DataFrame(seria_avg) if historia_sredniej.empty else historia_sredniej.join(seria_avg.rename(nazwa_inst), how='outer')

historia_rynku = pd.DataFrame()
for nazwa_inst in TICKERY.keys():
    if nazwa_inst in wszystkie_historie_zmian:
        seria_rynek = wszystkie_historie_zmian[nazwa_inst] * 25.0
        historia_rynku = pd.DataFrame(seria_rynek) if historia_rynku.empty else historia_rynku.join(seria_rynek.rename(nazwa_inst), how='outer')

# === 6. RYZYKO I DYWERSYFIKACJA ===
zmiennosc_proc = 0.0
if not historia_portfela.empty and kapital_poczatkowy > 0:
    total_my = historia_portfela.ffill().fillna(0).sum(axis=1)
    ret_h = total_my.diff().fillna(0) / kapital_poczatkowy
    # Skalowanie zmienności godzinowej do tygodniowej (ok. 120 godzin handlu)
    zmiennosc_proc = ret_h.std() * np.sqrt(120) * 100

suma_pozycji = sum(abs(w) for w in pozycje_z_panelu.values())
max_pozycja = max((abs(w) for w in pozycje_z_panelu.values()), default=0)
koncentracja = (max_pozycja / suma_pozycji * 100) if suma_pozycji > 0 else 0.0

# === POWIADOMIENIA ===
moje_miejsce = ranking_df[ranking_df['Grupa'] == wybrana_grupa].index[0] if wybrana_grupa in ranking_df['Grupa'].values else 0
klucz_sesji = f"poprzednie_miejsce_{wybrana_grupa}"

if klucz_sesji not in st.session_state: 
    st.session_state[klucz_sesji] = moje_miejsce
else:
    if moje_miejsce < st.session_state[klucz_sesji]: 
        st.toast(f"Awans: {wybrana_grupa} zajmuje {moje_miejsce} miejsce.")
    elif moje_miejsce > st.session_state[klucz_sesji]: 
        st.toast(f"Spadek: {wybrana_grupa} zajmuje {moje_miejsce} miejsce.")
    st.session_state[klucz_sesji] = moje_miejsce

# === SIDEBAR (PANEL ADMINA & CREDITS) ===
with st.sidebar:
    st.header("Panel Administratora")
    if not czy_mozna_rebalansowac:
        st.error("Zablokowane")
        st.info(f"Otwarcie za: {roznica.days}d {roznica.seconds//3600}h")
    else:
        st.success("Sesja rebalansu otwarta")
        if st.text_input("Hasło autoryzacyjne:", type="password") == "asdqwe123":
            st.divider()
            grupa_do_edycji = st.selectbox("Wybierz grupę do edycji:", sorted(list(aktywne_portfele.keys())))
            
            aktualny_kap = aktywne_portfele[grupa_do_edycji]["kapital_startowy"]
            aktualne_poz = aktywne_portfele[grupa_do_edycji]["pozycje"]
            
            wypracowany_kapital = aktualny_kap
            for k_inst, w_poz in aktualne_poz.items():
                if k_inst in zmiany_rynkowe:
                    wypracowany_kapital += w_poz * zmiany_rynkowe[k_inst]
                    
            nk = st.number_input(f"Kapitał wejściowy ({grupa_do_edycji})", value=float(round(wypracowany_kapital, 2)))
            np = {k: st.number_input(k, value=float(aktualne_poz.get(k, 0)), step=5.0) for k in TICKERY.keys()}
            
            if sum(abs(v) for v in np.values()) > nk: 
                st.error("Limit zaangażowania przekroczony.")
            elif st.button("Zapisz konfigurację"):
                ustawienia[grupa_do_edycji] = {"kapital_startowy": nk, "pozycje": np}
                zapisz_ustawienia(ustawienia)
                st.cache_data.clear()
                st.success("Dane zapisane pomyślnie.")
                time.sleep(1)
                st.rerun()
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Informacje o systemie")
    st.markdown("**Autor:** Antoni Bulsiewicz")
    st.markdown("[Repozytorium GitHub](https://github.com/dvmesh/uek_konkurs-portfelowy)")

# ==========================================
# ====== BUDOWA INTERFEJSU (UI LAYOUT) =====
# ==========================================

# 1. KARTY STATYSTYK (Responsywny CSS Grid)
kolor_koncentracji = KOLOR_STRATA if koncentracja >= 75 else (KOLOR_ZOLTY if koncentracja >= 40 else KOLOR_NEUTRAL)

karty = [
    ("Stan konta", f"{stan_konta_na_zywo:.2f}", "#ffffff"),
    ("Zysk netto", f"{zysk_laczny:+.2f}", KOLOR_ZYSK if zysk_laczny >= 0 else KOLOR_STRATA),
    ("Stopa zwrotu", f"{zmiana_proc_total:+.2f}%", KOLOR_ZYSK if zmiana_proc_total >= 0 else KOLOR_STRATA),
    ("Zmienność (Vol)", f"{zmiennosc_proc:.2f}%", KOLOR_NEUTRAL),
    ("Koncentracja", f"{koncentracja:.0f}%", kolor_koncentracji),
    ("Pozycja", f"{moje_miejsce} / {len(ranking_df)}", KOLOR_ZOLTY if moje_miejsce <=3 else "#ffffff")
]

html_karty = f'<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 20px;">'
for lab, val, col in karty:
    html_karty += f"""
    <div style="padding: 15px; text-align: center; background: {KOLOR_TLA_KART}; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
        <div style="color: {KOLOR_NEUTRAL}; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">{lab}</div>
        <div style="color: {col}; font-weight: 600; font-size: 24px; margin-top: 5px;">{val}</div>
    </div>
    """
html_karty += '</div>'
st.markdown(html_karty, unsafe_allow_html=True)

# 2. GŁÓWNY WYKRES PORTFELA
st.subheader("Stopa Zwrotu (vs Benchmark)")
fig = go.Figure()
if not historia_portfela.empty:
    total_my = historia_portfela.ffill().fillna(0).sum(axis=1)
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my.clip(lower=0), fill='tozeroy', fillcolor='rgba(74, 222, 128, 0.08)', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my.clip(upper=0), fill='tozeroy', fillcolor='rgba(248, 113, 113, 0.08)', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=total_my.index, y=total_my, line=dict(color='#e5e7eb', width=2.5), name=wybrana_grupa))

    ost_y, kol = total_my.iloc[-1], KOLOR_ZYSK if total_my.iloc[-1] >= 0 else KOLOR_STRATA
    fig.add_annotation(x=total_my.index[-1], y=ost_y, text=f"<b>{ost_y:+.2f}</b>", showarrow=True, arrowhead=0, arrowcolor=kol, ax=30, ay=-20, font=dict(color=kol, size=13), bgcolor="rgba(38, 39, 48, 0.8)", bordercolor=kol, borderpad=3)
    fig.add_trace(go.Scatter(x=[total_my.index[-1]], y=[ost_y], mode='markers', marker=dict(color=kol, size=7), showlegend=False))

if not historia_sredniej.empty:
    total_avg = historia_sredniej.ffill().fillna(0).sum(axis=1)
    fig.add_trace(go.Scatter(x=total_avg.index, y=total_avg, line=dict(color='rgba(251, 191, 36, 0.6)', width=1.5, dash='dot'), name='Średnia Konkursu'))
    ost_y_a = total_avg.iloc[-1]
    fig.add_annotation(x=total_avg.index[-1], y=ost_y_a, text=f"Śr: {ost_y_a:+.2f}", showarrow=True, arrowhead=0, arrowcolor=KOLOR_ZOLTY, ax=30, ay=10, font=dict(size=11, color=KOLOR_ZOLTY), bgcolor="rgba(38, 39, 48, 0.6)")
    fig.add_trace(go.Scatter(x=[total_avg.index[-1]], y=[ost_y_a], mode='markers', marker=dict(color=KOLOR_ZOLTY, size=5), showlegend=False))

if not historia_rynku.empty:
    total_rynek = historia_rynku.ffill().fillna(0).sum(axis=1)
    fig.add_trace(go.Scatter(x=total_rynek.index, y=total_rynek, line=dict(color='#38bdf8', width=1.5, dash='dash'), name='Rynek (Równa Alokacja)'))
    ost_y_r = total_rynek.iloc[-1]
    fig.add_annotation(x=total_rynek.index[-1], y=ost_y_r, text=f"Rynek: {ost_y_r:+.2f}", showarrow=True, arrowhead=0, arrowcolor="#38bdf8", ax=30, ay=35, font=dict(size=11, color="#38bdf8"), bgcolor="rgba(38, 39, 48, 0.6)")
    fig.add_trace(go.Scatter(x=[total_rynek.index[-1]], y=[ost_y_r], mode='markers', marker=dict(color="#38bdf8", size=5), showlegend=False))

fig.update_layout(
    template="plotly_dark", height=450, margin=dict(l=10, r=50, t=10, b=10), 
    yaxis=dict(zeroline=True, zerolinecolor='rgba(255, 255, 255, 0.1)', gridcolor='rgba(255, 255, 255, 0.05)'), 
    xaxis=dict(gridcolor='rgba(255, 255, 255, 0.05)'),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor='rgba(0,0,0,0)'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# 3. TABELE I SENTYMENT (LEWA) VS RANKING (PRAWA)
col_left, col_right = st.columns([1.1, 1])

with col_left:
    st.subheader("Otwarte Pozycje")
    if dane_do_tabeli:
        st.dataframe(pd.DataFrame(dane_do_tabeli), column_config={"Cena Start": st.column_config.NumberColumn(format="%.4f"), "Cena LIVE": st.column_config.NumberColumn(format="%.4f"), "Wynik": st.column_config.ProgressColumn("Zysk/Strata", format="%f", min_value=-50, max_value=50)}, use_container_width=True, hide_index=True)
    else: st.info("Brak otwartych pozycji.")
    
    st.write("") 
    st.subheader("Analiza Sentymentu")
    sentyment = {k: {"LONG": 0, "SHORT": 0} for k in TICKERY.keys()}
    
    for g_dane in aktywne_portfele.values():
        for inst, val in g_dane["pozycje"].items():
            if inst in sentyment: 
                if val > 0: sentyment[inst]["LONG"] += val
                elif val < 0: sentyment[inst]["SHORT"] += abs(val)

    fig_pie = make_subplots(rows=2, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}], [{"type": "domain"}, {"type": "domain"}]], subplot_titles=list(sentyment.keys()))
    
    for i, (inst, dane) in enumerate(sentyment.items()):
        row = (i // 2) + 1
        col = (i % 2) + 1
        if dane['LONG'] == 0 and dane['SHORT'] == 0:
            fig_pie.add_trace(go.Pie(labels=['Brak pozycji'], values=[1], marker_colors=[KOLOR_NEUTRAL], hole=.5, textinfo='none'), row=row, col=col)
        else:
            fig_pie.add_trace(go.Pie(labels=['LONG', 'SHORT'], values=[dane['LONG'], dane['SHORT']], marker_colors=[KOLOR_ZYSK, KOLOR_STRATA], textinfo='percent', hole=.5, textfont=dict(color='#ffffff')), row=row, col=col)
    
    for ann in fig_pie['layout']['annotations']: ann['font'] = dict(size=12, color=KOLOR_NEUTRAL)
    fig_pie.update_layout(template="plotly_dark", height=350, margin=dict(l=0, r=0, t=30, b=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.subheader("Ranking Konkursowy")
    st.dataframe(ranking_df, height=600, use_container_width=True, hide_index=False)

st.divider()

# 4. WYKRES INSTRUMENTÓW
st.subheader("Notowania Rynkowe")
fig_inst = go.Figure()

kolory_inst = {"S&P 500": "#3b82f6", "US10Y Yield": "#a855f7", "Złoto (Gold)": "#eab308", "EUR/USD": "#06b6d4"}

for nazwa, seria in wszystkie_historie_zmian.items():
    if not seria.empty:
        seria_czysta = seria.ffill().fillna(0) * 100 
        kolor = kolory_inst.get(nazwa, "#ffffff")
        fig_inst.add_trace(go.Scatter(x=seria_czysta.index, y=seria_czysta, mode='lines', name=nazwa, line=dict(color=kolor, width=2)))
        
        ost_y_inst = seria_czysta.iloc[-1]
        fig_inst.add_trace(go.Scatter(x=[seria_czysta.index[-1]], y=[ost_y_inst], mode='markers', marker=dict(color=kolor, size=6), showlegend=False, hoverinfo='skip'))

fig_inst.update_layout(
    template="plotly_dark", height=350, margin=dict(l=10, r=20, t=10, b=10),
    yaxis=dict(zeroline=True, zerolinecolor='rgba(255, 255, 255, 0.2)', gridcolor='rgba(255, 255, 255, 0.05)', title="Zmiana (%)"),
    xaxis=dict(gridcolor='rgba(255, 255, 255, 0.05)'),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor='rgba(0,0,0,0)'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig_inst, use_container_width=True)

st.caption(f"Stan danych: {teraz.strftime('%H:%M:%S')} | Częstotliwość odświeżania: 60s")
time.sleep(60)
st.rerun()