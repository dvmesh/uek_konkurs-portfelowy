import json
import os
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

# === KONFIGURACJA UI ===
st.set_page_config(page_title="Terminal Konkursowy", layout="wide")

# Auto-odświeżanie co 60s (nie blokuje healthz jak time.sleep)
st_autorefresh(interval=60_000, key="auto_refresh")

logger = logging.getLogger(__name__)

KOLOR_ZYSK = "#4ade80"
KOLOR_STRATA = "#f87171"
KOLOR_NEUTRAL = "#9ca3af"
KOLOR_ZOLTY = "#fbbf24"
KOLOR_RYNEK = "#38bdf8"
KOLOR_TLA_KART = "#262730"

TZ_WARSAW = ZoneInfo("Europe/Warsaw")

# =============================================
# ====== FUNKCJE POMOCNICZE (HELPERY) =========
# =============================================

def wczytaj_dane_statyczne():
    """Wczytuje niezmienną bazę danych z definicjami tickerów i alokacjami grup."""
    try:
        with open("dane_statyczne.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Błąd krytyczny: Brak pliku dane_statyczne.json!")
        return {"TICKERY": {}, "MAPOWANIE_PDF": {}, "DANE_GRUP": {}}
    except json.JSONDecodeError as e:
        st.error(f"Błąd parsowania dane_statyczne.json: {e}")
        return {"TICKERY": {}, "MAPOWANIE_PDF": {}, "DANE_GRUP": {}}


def wczytaj_ustawienia():
    """Wczytuje dynamiczny plik portfel.json (nadpisania admina)."""
    if os.path.exists(PLIK_USTAWIEN):
        try:
            with open(PLIK_USTAWIEN, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Nie udało się wczytać portfel.json: %s", e)
    return {}


def zapisz_ustawienia(ustawienia):
    """Zapisuje dynamiczny stan portfeli do pliku."""
    with open(PLIK_USTAWIEN, "w", encoding="utf-8") as f:
        json.dump(ustawienia, f, ensure_ascii=False, indent=2)


def render_karta(label: str, value: str, color: str):
    """Renderuje pojedynczą kartę statystyk jako HTML."""
    st.markdown(f"""
        <div style="padding:15px; text-align:center; background:{KOLOR_TLA_KART};
                    border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.2);">
            <div style="color:{KOLOR_NEUTRAL}; font-size:11px;
                        text-transform:uppercase; letter-spacing:1px;">{label}</div>
            <div style="color:{color}; font-weight:600; font-size:24px;
                        margin-top:5px;">{value}</div>
        </div>
    """, unsafe_allow_html=True)


def dodaj_serie_z_etykieta(fig, index, values, name, color,
                           width=2.0, dash=None, ax=40, ay=0,
                           fill=False, marker_size=7, label_prefix=""):
    """Dodaje linię + końcowy marker + etykietę do wykresu Plotly."""
    line_style = dict(color=color, width=width)
    if dash:
        line_style["dash"] = dash

    if fill:
        fig.add_trace(go.Scatter(
            x=index, y=values.clip(lower=0), fill='tozeroy',
            fillcolor='rgba(74, 222, 128, 0.08)', line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(
            x=index, y=values.clip(upper=0), fill='tozeroy',
            fillcolor='rgba(248, 113, 113, 0.08)', line=dict(width=0), showlegend=False))

    fig.add_trace(go.Scatter(x=index, y=values, line=line_style, name=name))

    ost_y = values.iloc[-1]
    label_text = f"{label_prefix}{ost_y:+.2f}" if label_prefix else f"<b>{ost_y:+.2f}</b>"
    fig.add_annotation(
        x=index[-1], y=ost_y, text=label_text,
        showarrow=True, arrowhead=0, arrowcolor=color,
        ax=ax, ay=ay,
        font=dict(color=color, size=11 if label_prefix else 13),
        bgcolor="rgba(38, 39, 48, 0.8)" if not label_prefix else "rgba(38, 39, 48, 0.6)",
        bordercolor=color if not label_prefix else None,
        borderpad=3 if not label_prefix else 0)
    fig.add_trace(go.Scatter(
        x=[index[-1]], y=[ost_y], mode='markers',
        marker=dict(color=color, size=marker_size), showlegend=False))


def oblicz_max_drawdown(seria: pd.Series) -> float:
    """Oblicza maksymalne obsunięcie kapitału (MDD) z serii wartości portfela."""
    if seria.empty:
        return 0.0
    cummax = seria.cummax()
    drawdown = seria - cummax
    return float(drawdown.min())


def buduj_historie_z_serii(nazwy_i_wagi: dict, wszystkie_historie: dict) -> pd.DataFrame:
    """Buduje DataFrame historii portfela z wag i historii zmian (pd.concat zamiast iteracyjnego join)."""
    serie = []
    for nazwa, waga in nazwy_i_wagi.items():
        if waga != 0 and nazwa in wszystkie_historie:
            seria = wszystkie_historie[nazwa] * waga
            serie.append(seria.rename(nazwa))
    return pd.concat(serie, axis=1).ffill().fillna(0) if serie else pd.DataFrame()


def czy_gielda_zamknieta(czas: datetime) -> bool:
    """Sprawdza czy giełda US jest zamknięta (po piątkowym close lub weekend).
    US close = 22:00 Warsaw (16:00 ET w sezonie letnim)."""
    dzien = czas.weekday()  # 0=Pon, 4=Pią, 5=Sob, 6=Nie
    if dzien == 5:  # sobota
        return True
    if dzien == 6:  # niedziela
        return True
    if dzien == 4 and czas.hour >= 22:  # piątek po zamknięciu
        return True
    return False


def znajdz_grupy_w_cashu(portfele: dict) -> list:
    """Zwraca nazwy grup, które mają wszystkie pozycje = 0 (siedzą w cashu)."""
    grupy_cash = []
    for nazwa, dane in portfele.items():
        pozycje = dane.get("pozycje", {})
        if all(v == 0 for v in pozycje.values()):
            grupy_cash.append(nazwa)
    return grupy_cash


def render_overlay_zamkniecia(ranking: pd.DataFrame, grupy_cash: list,
                               wybrana: str, teraz: datetime):
    """Renderuje overlay z podsumowaniem tygodnia po zamknięciu giełdy."""

    # TOP 3 z rankingu
    top3_html = ""
    medale = ["🥇", "🥈", "🥉"]
    for i in range(min(3, len(ranking))):
        row = ranking.iloc[i]
        medal = medale[i]
        nazwa = row["Grupa"]
        wynik = row["Wynik"]
        zmiana = wynik - 100
        kolor = KOLOR_ZYSK if zmiana >= 0 else KOLOR_STRATA
        top3_html += f"""
            <div style="display:flex; justify-content:space-between; align-items:center;
                        padding:12px 16px; margin:6px 0; background:rgba(255,255,255,0.05);
                        border-radius:8px; border-left:3px solid {kolor};">
                <span style="font-size:18px;">{medal} <b>{nazwa}</b></span>
                <span style="color:{kolor}; font-weight:700; font-size:16px;">{wynik:.2f}
                    <span style="font-size:12px;">({zmiana:+.2f}%)</span>
                </span>
            </div>
        """

    # Pozycja wybranej grupy
    pozycja_wybranej = ""
    if wybrana in ranking["Grupa"].values:
        idx = ranking[ranking["Grupa"] == wybrana].index[0]
        w_row = ranking.loc[idx]
        w_zmiana = w_row["Wynik"] - 100
        w_kolor = KOLOR_ZYSK if w_zmiana >= 0 else KOLOR_STRATA
        pozycja_wybranej = f"""
            <div style="margin-top:16px; padding:14px 16px; background:rgba(251,191,36,0.1);
                        border:1px solid {KOLOR_ZOLTY}; border-radius:8px; text-align:center;">
                <div style="color:{KOLOR_NEUTRAL}; font-size:11px; text-transform:uppercase;
                            letter-spacing:1px;">Twoja grupa</div>
                <div style="font-size:20px; margin:4px 0;"><b>{wybrana}</b> —
                    miejsce <b style="color:{KOLOR_ZOLTY};">#{idx}</b> / {len(ranking)}</div>
                <div style="color:{w_kolor}; font-size:16px; font-weight:600;">
                    Wynik: {w_row['Wynik']:.2f} ({w_zmiana:+.2f}%)</div>
            </div>
        """

    # Cash warning
    cash_html = ""
    if grupy_cash:
        lista = ", ".join(f"<b>{g}</b>" for g in sorted(grupy_cash))
        cash_html = f"""
            <div style="margin-top:16px; padding:14px 16px; background:rgba(248,113,113,0.1);
                        border:1px solid {KOLOR_STRATA}; border-radius:8px;">
                <div style="font-size:14px; color:{KOLOR_STRATA}; margin-bottom:6px;">
                    ⚠️ <b>Grupy bez pozycji (100% CASH):</b>
                </div>
                <div style="color:#e5e7eb; font-size:13px; line-height:1.6;">
                    {lista}
                </div>
                <div style="color:{KOLOR_NEUTRAL}; font-size:12px; margin-top:8px;">
                    Pamiętajcie o zgłoszeniu rebalansu do obsługi konkursu
                    przed niedzielą 23:00!
                </div>
            </div>
        """

    # Deadline info
    deadline_info = ""
    if teraz.weekday() in (4, 5):  # piątek/sobota — niedziela tego weekendu
        nd = teraz + timedelta(days=(6 - teraz.weekday()))
        deadline_info = f"""
            <div style="margin-top:14px; text-align:center; color:{KOLOR_ZOLTY};
                        font-size:13px;">
                🕐 Okno rebalansu: <b>niedziela {nd.strftime('%d.%m')}, do 23:00</b>
            </div>
        """
    elif teraz.weekday() == 6:  # niedziela
        if teraz.hour < 23:
            deadline_info = f"""
                <div style="margin-top:14px; text-align:center;
                            padding:10px; background:rgba(74,222,128,0.1);
                            border:1px solid {KOLOR_ZYSK}; border-radius:8px;">
                    <span style="color:{KOLOR_ZYSK}; font-size:14px;">
                        🟢 <b>Okno rebalansu OTWARTE</b> — pozostało
                        {23 - teraz.hour}h do zamknięcia
                    </span>
                </div>
            """
        else:
            deadline_info = f"""
                <div style="margin-top:14px; text-align:center; color:{KOLOR_STRATA};
                            font-size:13px;">
                    🔒 Okno rebalansu zamknięte. Nowy tydzień startuje w poniedziałek.
                </div>
            """

    # Pełny overlay
    st.markdown(f"""
        <div id="overlay-zamkniecie" style="
            position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:99999;
            background:rgba(0,0,0,0.75); backdrop-filter:blur(8px);
            display:flex; align-items:center; justify-content:center;">
            <div style="
                background:#1a1b23; border:1px solid rgba(255,255,255,0.1);
                border-radius:16px; padding:32px 36px; max-width:520px; width:90%;
                max-height:85vh; overflow-y:auto; box-shadow:0 20px 60px rgba(0,0,0,0.5);
                position:relative;">

                <button onclick="document.getElementById('overlay-zamkniecie').style.display='none'"
                    style="position:absolute; top:12px; right:16px; background:none; border:none;
                           color:{KOLOR_NEUTRAL}; font-size:22px; cursor:pointer;
                           padding:4px 8px; border-radius:6px; transition:all 0.2s;"
                    onmouseover="this.style.color='#ffffff'; this.style.background='rgba(255,255,255,0.1)'"
                    onmouseout="this.style.color='{KOLOR_NEUTRAL}'; this.style.background='none'"
                    title="Zamknij">✕</button>

                <div style="text-align:center; margin-bottom:20px;">
                    <div style="font-size:28px; margin-bottom:4px;">🔔</div>
                    <div style="font-size:22px; font-weight:700; color:#ffffff;">
                        Giełda zamknięta</div>
                    <div style="color:{KOLOR_NEUTRAL}; font-size:13px; margin-top:4px;">
                        Podsumowanie tygodnia —
                        {teraz.strftime('%d.%m.%Y, %H:%M')}</div>
                </div>

                <div style="color:{KOLOR_NEUTRAL}; font-size:11px; text-transform:uppercase;
                            letter-spacing:1px; margin-bottom:8px;">🏆 Podium</div>
                {top3_html}
                {pozycja_wybranej}
                {cash_html}
                {deadline_info}

                <button onclick="document.getElementById('overlay-zamkniecie').style.display='none'"
                    style="display:block; width:100%; margin-top:20px; padding:12px;
                           background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15);
                           border-radius:8px; color:#ffffff; font-size:14px; cursor:pointer;
                           transition:all 0.2s;"
                    onmouseover="this.style.background='rgba(255,255,255,0.15)'"
                    onmouseout="this.style.background='rgba(255,255,255,0.08)'">
                    Przejdź do Terminala →</button>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_banner_cash(grupy_cash: list):
    """Renderuje stały banner u góry strony z przypomnieniem dla grup w cashu."""
    if not grupy_cash:
        return
    lista = ", ".join(grupy_cash[:8])
    reszta = f" i {len(grupy_cash) - 8} więcej..." if len(grupy_cash) > 8 else ""
    st.markdown(f"""
        <div style="padding:10px 16px; background:rgba(251,191,36,0.1);
                    border:1px solid {KOLOR_ZOLTY}; border-radius:8px;
                    margin-bottom:12px; display:flex; align-items:center; gap:10px;">
            <span style="font-size:20px;">💤</span>
            <div>
                <div style="color:{KOLOR_ZOLTY}; font-size:13px; font-weight:600;">
                    Grupy w 100% CASH (brak otwartych pozycji)</div>
                <div style="color:{KOLOR_NEUTRAL}; font-size:12px;">
                    {lista}{reszta} — zgłoście rebalans do obsługi konkursu!</div>
            </div>
        </div>
    """, unsafe_allow_html=True)


# =============================================
# ====== ŁADOWANIE DANYCH ====================
# =============================================

PLIK_USTAWIEN = "portfel.json"

dane_stat = wczytaj_dane_statyczne()
TICKERY = dane_stat.get("TICKERY", {})
MAPOWANIE_PDF = dane_stat.get("MAPOWANIE_PDF", {})
DANE_GRUP = dane_stat.get("DANE_GRUP", {})

ustawienia = wczytaj_ustawienia()

# --- SCALANIE DANYCH (z walidacją struktury) ---
aktywne_portfele = {}
for g_nazwa, g_poz in DANE_GRUP.items():
    aktywne_portfele[g_nazwa] = {
        "kapital_startowy": 100.0,
        "pozycje": {
            "S&P 500": g_poz.get("SPX", 0.0),
            "Złoto (Gold)": g_poz.get("GOLD", 0.0),
            "US10Y Yield": g_poz.get("RENT", 0.0),
            "EUR/USD": g_poz.get("EURUSD", 0.0),
        }
    }

for g_nazwa, g_dane in ustawienia.items():
    if isinstance(g_dane, dict) and "kapital_startowy" in g_dane and "pozycje" in g_dane:
        aktywne_portfele[g_nazwa] = g_dane
    else:
        logger.warning("Pominięto uszkodzony wpis w portfel.json dla grupy: %s", g_nazwa)


# === LOGIKA CZASU (z poprawną strefą czasową) ===
teraz = datetime.now(TZ_WARSAW)
ostatni_poniedzialek = teraz - timedelta(days=teraz.weekday())
data_startu_str = ostatni_poniedzialek.strftime('%Y-%m-%d')

dni_do_niedzieli = 6 - teraz.weekday()
najblizsza_niedziela = teraz + timedelta(days=dni_do_niedzieli)
deadline = najblizsza_niedziela.replace(hour=23, minute=0, second=0, microsecond=0)
if teraz > deadline:
    deadline += timedelta(days=7)

roznica = deadline - teraz
czy_mozna_rebalansowac = (teraz.weekday() == 6) and (teraz.hour < 23)


# === POBIERANIE DANYCH RYNKOWYCH ===
@st.cache_data(ttl=60)
def pobierz_dane_rynkowe(ticker: str, data_startu: str) -> pd.DataFrame:
    """Pobiera dane godzinowe z Yahoo Finance z fallbackiem na okres 5d."""
    try:
        hist = yf.Ticker(ticker).history(start=data_startu, interval="1h")
        if hist.empty:
            hist = yf.Ticker(ticker).history(period="5d", interval="1h")
        if not hist.empty:
            if hist.index.tz is not None:
                hist.index = hist.index.tz_convert('Europe/Warsaw')
            hist.index = hist.index.tz_localize(None)
        return hist
    except Exception as e:
        logger.error("Błąd pobierania danych dla %s: %s", ticker, e)
        return pd.DataFrame()


zmiany_rynkowe = {}
wszystkie_historie_zmian = {}
dane_rynkowe_cache = {}  # cache lokalny — bez podwójnego pobierania

with st.spinner('Synchronizacja danych rynkowych...'):
    for nazwa, ticker in TICKERY.items():
        hist = pobierz_dane_rynkowe(ticker, data_startu_str)
        dane_rynkowe_cache[nazwa] = hist
        if not hist.empty and len(hist) >= 1:
            cena_otw = hist['Open'].iloc[0]
            cena_live = hist['Close'].iloc[-1]
            if cena_otw != 0:
                zmiany_rynkowe[nazwa] = (cena_live - cena_otw) / cena_otw
                wszystkie_historie_zmian[nazwa] = (hist['Close'] - cena_otw) / cena_otw

# Walidacja: czy udało się pobrać jakiekolwiek dane
if not zmiany_rynkowe:
    st.warning(
        "⚠️ Brak danych rynkowych z Yahoo Finance. "
        "Wyniki mogą być nieaktualne (weekend / limit API)."
    )


# === WYLICZENIE RANKINGU (jednorazowe przejście po portfelach) ===
wyniki_rankingu = []
sentyment = {k: {"LONG": 0, "SHORT": 0} for k in TICKERY.keys()}
srednie_wagi = {k: 0.0 for k in TICKERY.keys()}
liczba_grup = len(aktywne_portfele)

for g_nazwa, g_dane in aktywne_portfele.items():
    wynik_g = g_dane["kapital_startowy"]
    for inst, waga in g_dane["pozycje"].items():
        # Ranking
        if inst in zmiany_rynkowe:
            wynik_g += waga * zmiany_rynkowe[inst]
        # Sentyment (agregacja LONG/SHORT)
        if inst in sentyment:
            if waga > 0:
                sentyment[inst]["LONG"] += waga
            elif waga < 0:
                sentyment[inst]["SHORT"] += abs(waga)
        # Średnie wagi do benchmarku
        if inst in srednie_wagi:
            srednie_wagi[inst] += waga / liczba_grup if liczba_grup > 0 else 0

    wyniki_rankingu.append({"Grupa": g_nazwa, "Wynik": round(wynik_g, 4)})

ranking_df = (
    pd.DataFrame(wyniki_rankingu)
    .sort_values(by="Wynik", ascending=False)
    .reset_index(drop=True)
)
ranking_df.index += 1
lider_konkursu = ranking_df.iloc[0]["Grupa"] if not ranking_df.empty else "Grupa 13"


# === UI: WYBÓR GRUPY ===
lista_grup = sorted(list(aktywne_portfele.keys()))
idx_domyslny = lista_grup.index(lider_konkursu) if lider_konkursu in lista_grup else 0

col_t, col_w = st.columns([2, 1])
with col_w:
    wybrana_grupa = st.selectbox("Wybór portfela:", lista_grup, index=idx_domyslny)
with col_t:
    st.title(f"Widok portfela: {wybrana_grupa}")


# === DETEKCJA ZAMKNIĘCIA GIEŁDY + GRUPY W CASHU ===
gielda_zamknieta = czy_gielda_zamknieta(teraz)
grupy_cash = znajdz_grupy_w_cashu(aktywne_portfele)

# Overlay po zamknięciu giełdy (piątek po 22:00, sobota, niedziela)
if gielda_zamknieta:
    # Reset flagi na nowy weekend (żeby overlay pojawił się ponownie w nowym tygodniu)
    aktualny_weekend_key = ostatni_poniedzialek.strftime('%Y-%m-%d')
    if st.session_state.get("_overlay_week") != aktualny_weekend_key:
        st.session_state["_overlay_ukryty"] = False
        st.session_state["_overlay_week"] = aktualny_weekend_key

    if not st.session_state.get("_overlay_ukryty", False):
        render_overlay_zamkniecia(ranking_df, grupy_cash, wybrana_grupa, teraz)


# === OBLICZENIA DLA WYBRANEJ GRUPY ===
kapital_poczatkowy = float(aktywne_portfele[wybrana_grupa]["kapital_startowy"])
pozycje_z_panelu = aktywne_portfele[wybrana_grupa]["pozycje"]

zysk_laczny = 0.0
dane_do_tabeli = []

for nazwa, wielkosc in pozycje_z_panelu.items():
    if wielkosc != 0 and nazwa in zmiany_rynkowe:
        zmiana_proc = zmiany_rynkowe[nazwa]
        wynik_poz = wielkosc * zmiana_proc
        zysk_laczny += wynik_poz

        # Czytamy z cache — bez ponownego hitu do yfinance
        hist = dane_rynkowe_cache.get(nazwa, pd.DataFrame())
        c_start = hist['Open'].iloc[0] if not hist.empty else 0
        c_live = hist['Close'].iloc[-1] if not hist.empty else 0

        dane_do_tabeli.append({
            "Instrument": nazwa,
            "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
            "Wielkość": wielkosc,
            "Cena Start": c_start,
            "Cena LIVE": c_live,
            "Wynik": wynik_poz,
        })

stan_konta_na_zywo = kapital_poczatkowy + zysk_laczny
zmiana_proc_total = (zysk_laczny / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0


# === HISTORIE BENCHMARKÓW (pd.concat zamiast iteracyjnego join) ===
historia_portfela = buduj_historie_z_serii(pozycje_z_panelu, wszystkie_historie_zmian)
historia_sredniej = buduj_historie_z_serii(srednie_wagi, wszystkie_historie_zmian)
historia_rynku = buduj_historie_z_serii(
    {nazwa: 25.0 for nazwa in TICKERY.keys()},
    wszystkie_historie_zmian
)


# === ALFA, SKUTECZNOŚĆ, MAX DRAWDOWN ===
zysk_rynku = sum(25.0 * zmiana for zmiana in zmiany_rynkowe.values())
zmiana_proc_rynku = zysk_rynku
alfa_proc = zmiana_proc_total - zmiana_proc_rynku

zwyciestwa = sum(1 for poz in dane_do_tabeli if poz["Wynik"] > 0)
wszystkie_pozycje = len(dane_do_tabeli)
skutecznosc = (zwyciestwa / wszystkie_pozycje * 100) if wszystkie_pozycje > 0 else 0.0

# Max Drawdown — obliczany z historii portfela
if not historia_portfela.empty:
    seria_portfela_total = historia_portfela.sum(axis=1) + kapital_poczatkowy
    mdd_abs = oblicz_max_drawdown(seria_portfela_total)
    mdd_proc = (mdd_abs / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0.0
else:
    mdd_proc = 0.0


# === POWIADOMIENIA ===
moje_miejsce = (
    ranking_df[ranking_df['Grupa'] == wybrana_grupa].index[0]
    if wybrana_grupa in ranking_df['Grupa'].values else 0
)
klucz_sesji = f"poprzednie_miejsce_{wybrana_grupa}"

if klucz_sesji not in st.session_state:
    st.session_state[klucz_sesji] = moje_miejsce
else:
    if moje_miejsce < st.session_state[klucz_sesji]:
        st.toast(f"📈 Awans: {wybrana_grupa} zajmuje {moje_miejsce} miejsce.")
    elif moje_miejsce > st.session_state[klucz_sesji]:
        st.toast(f"📉 Spadek: {wybrana_grupa} zajmuje {moje_miejsce} miejsce.")
    st.session_state[klucz_sesji] = moje_miejsce


# ==========================================
# ====== SIDEBAR (PANEL ADMINA) ============
# ==========================================

with st.sidebar:
    # Toggle overlay zamknięcia giełdy
    if gielda_zamknieta:
        if st.checkbox("Ukryj podsumowanie weekendowe",
                        value=st.session_state.get("_overlay_ukryty", False),
                        key="_chk_overlay"):
            st.session_state["_overlay_ukryty"] = True
        else:
            st.session_state["_overlay_ukryty"] = False
        st.divider()

    st.header("Panel Administratora")
    if not czy_mozna_rebalansowac:
        st.error("Zablokowane")
        st.info(f"Otwarcie za: {roznica.days}d {roznica.seconds // 3600}h")
    else:
        st.success("Sesja rebalansu otwarta")
        # Hasło z st.secrets (fallback na zmienną środowiskową)
        haslo_admina = st.secrets.get("ADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", ""))
        if not haslo_admina:
            st.warning("Brak skonfigurowanego hasła admina (st.secrets / env).")
        elif st.text_input("Hasło autoryzacyjne:", type="password") == haslo_admina:
            st.divider()
            grupa_do_edycji = st.selectbox(
                "Wybierz grupę do edycji:",
                sorted(list(aktywne_portfele.keys()))
            )

            aktualny_kap = aktywne_portfele[grupa_do_edycji]["kapital_startowy"]
            aktualne_poz = aktywne_portfele[grupa_do_edycji]["pozycje"]

            wypracowany_kapital = aktualny_kap
            for k_inst, w_poz in aktualne_poz.items():
                if k_inst in zmiany_rynkowe:
                    wypracowany_kapital += w_poz * zmiany_rynkowe[k_inst]

            nk = st.number_input(
                f"Kapitał wejściowy ({grupa_do_edycji})",
                value=float(round(wypracowany_kapital, 2))
            )
            nowe_pozycje = {
                k: st.number_input(k, value=float(aktualne_poz.get(k, 0)), step=5.0)
                for k in TICKERY.keys()
            }

            if sum(abs(v) for v in nowe_pozycje.values()) > nk:
                st.error("Limit zaangażowania przekroczony.")
            elif st.button("Zapisz konfigurację"):
                ustawienia[grupa_do_edycji] = {
                    "kapital_startowy": nk,
                    "pozycje": nowe_pozycje
                }
                zapisz_ustawienia(ustawienia)
                st.cache_data.clear()
                st.success("Dane zapisane pomyślnie.")
                st.rerun()

    # CREDITS
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Informacje o systemie")
    st.markdown("**Autor:** Antoni Bulsiewicz")
    st.markdown("[Repozytorium GitHub](https://github.com/dvmesh/uek_konkurs-portfelowy)")


# ==========================================
# ====== BUDOWA INTERFEJSU (UI LAYOUT) =====
# ==========================================

# 0. BANNER DLA GRUP W CASHU (zawsze widoczny jeśli są takie grupy)
if grupy_cash:
    render_banner_cash(grupy_cash)

# 1. KARTY STATYSTYK
karty = [
    ("Stan konta", f"{stan_konta_na_zywo:.2f}", "#ffffff"),
    ("Zysk", f"{zysk_laczny:+.2f}", KOLOR_ZYSK if zysk_laczny >= 0 else KOLOR_STRATA),
    ("Stopa zwrotu", f"{zmiana_proc_total:+.2f}%",
     KOLOR_ZYSK if zmiana_proc_total >= 0 else KOLOR_STRATA),
    ("Alfa (vs Rynek)", f"{alfa_proc:+.2f}%",
     KOLOR_ZYSK if alfa_proc > 0 else (KOLOR_STRATA if alfa_proc < 0 else KOLOR_NEUTRAL)),
    ("MDD (tyg.)", f"{mdd_proc:+.2f}%",
     KOLOR_STRATA if mdd_proc < -1 else (KOLOR_ZOLTY if mdd_proc < 0 else KOLOR_ZYSK)),
    ("Skuteczność", f"{skutecznosc:.0f}%",
     KOLOR_ZYSK if skutecznosc >= 50 else (
         KOLOR_STRATA if wszystkie_pozycje > 0 else KOLOR_NEUTRAL)),
    ("Pozycja", f"{moje_miejsce} / {len(ranking_df)}",
     KOLOR_ZOLTY if moje_miejsce <= 3 else "#ffffff"),
]

kolumny = st.columns(len(karty))
for i, (lab, val, col) in enumerate(karty):
    with kolumny[i]:
        render_karta(lab, val, col)

st.markdown("<br>", unsafe_allow_html=True)
st.divider()


# 2. GŁÓWNY WYKRES PORTFELA
st.subheader("Stopa Zwrotu (vs Benchmark)")
fig = go.Figure()

if not historia_portfela.empty:
    total_my = historia_portfela.sum(axis=1)
    dodaj_serie_z_etykieta(
        fig, total_my.index, total_my, wybrana_grupa,
        color='#e5e7eb', width=2.5, fill=True)

if not historia_sredniej.empty:
    total_avg = historia_sredniej.sum(axis=1)
    dodaj_serie_z_etykieta(
        fig, total_avg.index, total_avg, 'Średnia Konkursu',
        color='rgba(251, 191, 36, 0.6)', width=1.5, dash='dot',
        ax=45, ay=-25, marker_size=5, label_prefix="Śr: ")

if not historia_rynku.empty:
    total_rynek = historia_rynku.sum(axis=1)
    dodaj_serie_z_etykieta(
        fig, total_rynek.index, total_rynek, 'Rynek (Równa Alokacja)',
        color='#38bdf8', width=1.5, dash='dash',
        ax=45, ay=25, marker_size=5, label_prefix="Rynek: ")

fig.update_layout(
    template="plotly_dark", height=450,
    margin=dict(l=10, r=80, t=10, b=10),
    yaxis=dict(zeroline=True, zerolinecolor='rgba(255,255,255,0.1)',
               gridcolor='rgba(255,255,255,0.05)'),
    xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01,
                bgcolor='rgba(0,0,0,0)'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig, use_container_width=True)

st.divider()


# 3. TABELE I SENTYMENT (LEWA) VS RANKING (PRAWA)
col_left, col_right = st.columns([1.1, 1])

with col_left:
    st.subheader("Otwarte Pozycje")
    if dane_do_tabeli:
        st.dataframe(
            pd.DataFrame(dane_do_tabeli),
            column_config={
                "Cena Start": st.column_config.NumberColumn(format="%.4f"),
                "Cena LIVE": st.column_config.NumberColumn(format="%.4f"),
                "Wynik": st.column_config.ProgressColumn(
                    "Zysk/Strata", format="%f", min_value=-50, max_value=50),
            },
            use_container_width=True, hide_index=True)
    else:
        st.info("Brak otwartych pozycji.")

    st.write("")
    st.subheader("Analiza Sentymentu")

    # Donut charts
    fig_pie = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}],
               [{"type": "domain"}, {"type": "domain"}]],
        subplot_titles=list(sentyment.keys()))

    for i, (inst, dane_s) in enumerate(sentyment.items()):
        row = (i // 2) + 1
        col = (i % 2) + 1
        if dane_s['LONG'] == 0 and dane_s['SHORT'] == 0:
            fig_pie.add_trace(go.Pie(
                labels=['Brak pozycji'], values=[1],
                marker_colors=[KOLOR_NEUTRAL], hole=.5,
                textinfo='none'), row=row, col=col)
        else:
            fig_pie.add_trace(go.Pie(
                labels=['LONG', 'SHORT'],
                values=[dane_s['LONG'], dane_s['SHORT']],
                marker_colors=[KOLOR_ZYSK, KOLOR_STRATA],
                textinfo='percent', hole=.5,
                textfont=dict(color='#ffffff')), row=row, col=col)

    for ann in fig_pie['layout']['annotations']:
        ann['font'] = dict(size=13, color=KOLOR_NEUTRAL)
    fig_pie.update_layout(
        template="plotly_dark", height=400,
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_pie, use_container_width=True)

    # Net Exposure bar chart
    st.subheader("Net Exposure")
    net_exp = {inst: dane_s["LONG"] - dane_s["SHORT"] for inst, dane_s in sentyment.items()}
    kolory_bar = [KOLOR_ZYSK if v >= 0 else KOLOR_STRATA for v in net_exp.values()]
    fig_bar = go.Figure(go.Bar(
        x=list(net_exp.keys()), y=list(net_exp.values()),
        marker_color=kolory_bar, text=[f"{v:+.0f}" for v in net_exp.values()],
        textposition='outside', textfont=dict(color='#e5e7eb')))
    fig_bar.update_layout(
        template="plotly_dark", height=250,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(zeroline=True, zerolinecolor='rgba(255,255,255,0.2)',
                   gridcolor='rgba(255,255,255,0.05)', title="Jednostki netto"),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_bar, use_container_width=True)

with col_right:
    st.subheader("Ranking Konkursowy")
    st.dataframe(ranking_df, height=600, use_container_width=True, hide_index=False)

st.divider()


# 4. WYKRES INSTRUMENTÓW
st.subheader("Notowania Rynkowe")
fig_inst = go.Figure()

kolory_inst = {
    "S&P 500": "#3b82f6",
    "US10Y Yield": "#a855f7",
    "Złoto (Gold)": "#eab308",
    "EUR/USD": "#06b6d4",
}

for nazwa, seria in wszystkie_historie_zmian.items():
    if not seria.empty:
        seria_czysta = seria.ffill().fillna(0) * 100
        kolor = kolory_inst.get(nazwa, "#ffffff")
        fig_inst.add_trace(go.Scatter(
            x=seria_czysta.index, y=seria_czysta,
            mode='lines', name=nazwa,
            line=dict(color=kolor, width=2)))
        fig_inst.add_trace(go.Scatter(
            x=[seria_czysta.index[-1]], y=[seria_czysta.iloc[-1]],
            mode='markers', marker=dict(color=kolor, size=6),
            showlegend=False, hoverinfo='skip'))

fig_inst.update_layout(
    template="plotly_dark", height=350,
    margin=dict(l=10, r=20, t=10, b=10),
    yaxis=dict(zeroline=True, zerolinecolor='rgba(255,255,255,0.2)',
               gridcolor='rgba(255,255,255,0.05)', title="Zmiana (%)"),
    xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1, bgcolor='rgba(0,0,0,0)'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig_inst, use_container_width=True)

st.caption(f"Stan danych: {teraz.strftime('%H:%M:%S')} (Europe/Warsaw) | Auto-odświeżanie: 60s")
