import json
import os
import io
import shutil
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
st_autorefresh(interval=60_000, key="auto_refresh")

logger = logging.getLogger(__name__)

KOLOR_ZYSK = "#4ade80"
KOLOR_STRATA = "#f87171"
KOLOR_NEUTRAL = "#9ca3af"
KOLOR_ZOLTY = "#fbbf24"
KOLOR_RYNEK = "#38bdf8"
KOLOR_TLA_KART = "#262730"

TZ_WARSAW = ZoneInfo("Europe/Warsaw")
PLIK_USTAWIEN = "portfel.json"
PLIK_LOGU = "log_zmian.json"


# =============================================
# ====== FUNKCJE POMOCNICZE (HELPERY) =========
# =============================================

def wczytaj_dane_statyczne():
    try:
        with open("dane_statyczne.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Brak pliku dane_statyczne.json!")
        return {"TICKERY": {}, "MAPOWANIE_PDF": {}, "DANE_GRUP": {}}
    except json.JSONDecodeError as e:
        st.error(f"Błąd parsowania dane_statyczne.json: {e}")
        return {"TICKERY": {}, "MAPOWANIE_PDF": {}, "DANE_GRUP": {}}


def wczytaj_ustawienia():
    if os.path.exists(PLIK_USTAWIEN):
        try:
            with open(PLIK_USTAWIEN, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("portfel.json: %s", e)
    return {}


def backup_portfela():
    """Kopia zapasowa portfel.json przed nadpisaniem."""
    if os.path.exists(PLIK_USTAWIEN):
        ts = datetime.now(TZ_WARSAW).strftime('%Y%m%d_%H%M%S')
        shutil.copy2(PLIK_USTAWIEN, f"portfel_backup_{ts}.json")


def zapisz_ustawienia(dane):
    with open(PLIK_USTAWIEN, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False, indent=2)


def zapisz_log(grupa, stare, nowe):
    """Timestamped diff do log_zmian.json."""
    log = []
    if os.path.exists(PLIK_LOGU):
        try:
            with open(PLIK_LOGU, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    log.append({
        "timestamp": datetime.now(TZ_WARSAW).isoformat(),
        "grupa": grupa, "poprzednie": stare, "nowe": nowe,
    })
    with open(PLIK_LOGU, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def render_karta(label, value, color):
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
    txt = f"{label_prefix}{ost_y:+.2f}" if label_prefix else f"<b>{ost_y:+.2f}</b>"
    fig.add_annotation(
        x=index[-1], y=ost_y, text=txt, showarrow=True, arrowhead=0,
        arrowcolor=color, ax=ax, ay=ay,
        font=dict(color=color, size=11 if label_prefix else 13),
        bgcolor="rgba(38,39,48,0.8)" if not label_prefix else "rgba(38,39,48,0.6)",
        bordercolor=color if not label_prefix else None,
        borderpad=3 if not label_prefix else 0)
    fig.add_trace(go.Scatter(
        x=[index[-1]], y=[ost_y], mode='markers',
        marker=dict(color=color, size=marker_size), showlegend=False))


def oblicz_max_drawdown(seria):
    if seria.empty:
        return 0.0
    return float((seria - seria.cummax()).min())


def buduj_historie_z_serii(wagi, historie):
    serie = []
    for n, w in wagi.items():
        if w != 0 and n in historie:
            serie.append((historie[n] * w).rename(n))
    return pd.concat(serie, axis=1).ffill().fillna(0) if serie else pd.DataFrame()


def czy_gielda_zamknieta(czas):
    d = czas.weekday()
    return d in (5, 6) or (d == 4 and czas.hour >= 22)


def znajdz_grupy_w_cashu(portfele):
    return [n for n, d in portfele.items()
            if all(v == 0 for v in d.get("pozycje", {}).values())]


def render_overlay_zamkniecia(ranking, grupy_cash, wybrana, teraz, portfele):
    """Overlay: podium z pozycjami TOP 3, pozycja wybranej grupy, cash warning."""
    medale = ["🥇", "🥈", "🥉"]
    top3_html = ""
    for i in range(min(3, len(ranking))):
        row = ranking.iloc[i]
        nazwa, wynik = row["Grupa"], row["Wynik"]
        zm = wynik - 100
        kol = KOLOR_ZYSK if zm >= 0 else KOLOR_STRATA

        poz = portfele.get(nazwa, {}).get("pozycje", {})
        poz_html = ""
        for inst, waga in poz.items():
            if waga != 0:
                skr = inst.replace("S&P 500","SPX").replace("Złoto (Gold)","GOLD") \
                          .replace("US10Y Yield","10Y").replace("EUR/USD","EUR")
                kp = KOLOR_ZYSK if waga > 0 else KOLOR_STRATA
                kier = "L" if waga > 0 else "S"
                poz_html += (f'<span style="display:inline-block;padding:2px 6px;margin:2px;'
                             f'border-radius:4px;font-size:10px;background:rgba(255,255,255,0.06);'
                             f'color:{kp};">{skr} {kier}{abs(waga):.0f}</span>')

        top3_html += f"""
            <div style="padding:12px 16px;margin:6px 0;background:rgba(255,255,255,0.05);
                        border-radius:8px;border-left:3px solid {kol};">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:18px;">{medale[i]} <b>{nazwa}</b></span>
                    <span style="color:{kol};font-weight:700;font-size:16px;">{wynik:.2f}
                        <span style="font-size:12px;">({zm:+.2f}%)</span></span>
                </div>
                <div style="margin-top:6px;">{poz_html}</div>
            </div>"""

    poz_wybranej = ""
    if wybrana in ranking["Grupa"].values:
        idx = ranking[ranking["Grupa"]==wybrana].index[0]
        wr = ranking.loc[idx]
        wz = wr["Wynik"]-100
        wk = KOLOR_ZYSK if wz >= 0 else KOLOR_STRATA
        poz_wybranej = f"""
            <div style="margin-top:16px;padding:14px 16px;background:rgba(251,191,36,0.1);
                        border:1px solid {KOLOR_ZOLTY};border-radius:8px;text-align:center;">
                <div style="color:{KOLOR_NEUTRAL};font-size:11px;text-transform:uppercase;
                            letter-spacing:1px;">Twoja grupa</div>
                <div style="font-size:20px;margin:4px 0;"><b>{wybrana}</b> —
                    miejsce <b style="color:{KOLOR_ZOLTY};">#{idx}</b> / {len(ranking)}</div>
                <div style="color:{wk};font-size:16px;font-weight:600;">
                    Wynik: {wr['Wynik']:.2f} ({wz:+.2f}%)</div>
            </div>"""

    cash_html = ""
    if grupy_cash:
        lista = ", ".join(f"<b>{g}</b>" for g in sorted(grupy_cash))
        cash_html = f"""
            <div style="margin-top:16px;padding:14px 16px;background:rgba(248,113,113,0.1);
                        border:1px solid {KOLOR_STRATA};border-radius:8px;">
                <div style="font-size:14px;color:{KOLOR_STRATA};margin-bottom:6px;">
                    ⚠️ <b>Grupy bez pozycji (100% CASH):</b></div>
                <div style="color:#e5e7eb;font-size:13px;line-height:1.6;">{lista}</div>
                <div style="color:{KOLOR_NEUTRAL};font-size:12px;margin-top:8px;">
                    Pamiętajcie o zgłoszeniu rebalansu przed niedzielą 23:00!</div>
            </div>"""

    dl = ""
    if teraz.weekday() in (4, 5):
        nd = teraz + timedelta(days=(6 - teraz.weekday()))
        dl = f'<div style="margin-top:14px;text-align:center;color:{KOLOR_ZOLTY};font-size:13px;">🕐 Okno rebalansu: <b>niedziela {nd.strftime("%d.%m")}, do 23:00</b></div>'
    elif teraz.weekday() == 6 and teraz.hour < 23:
        dl = f'<div style="margin-top:14px;text-align:center;padding:10px;background:rgba(74,222,128,0.1);border:1px solid {KOLOR_ZYSK};border-radius:8px;"><span style="color:{KOLOR_ZYSK};font-size:14px;">🟢 <b>Okno rebalansu OTWARTE</b> — {23-teraz.hour}h do zamknięcia</span></div>'
    elif teraz.weekday() == 6:
        dl = f'<div style="margin-top:14px;text-align:center;color:{KOLOR_STRATA};font-size:13px;">🔒 Okno rebalansu zamknięte.</div>'

    st.markdown(f"""
        <div id="overlay-zamkniecie" style="position:fixed;top:0;left:0;width:100vw;height:100vh;
            z-index:99999;background:rgba(0,0,0,0.75);backdrop-filter:blur(8px);
            display:flex;align-items:center;justify-content:center;">
            <div style="background:#1a1b23;border:1px solid rgba(255,255,255,0.1);
                border-radius:16px;padding:32px 36px;max-width:560px;width:90%;
                max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.5);
                position:relative;">
                <button onclick="document.getElementById('overlay-zamkniecie').style.display='none'"
                    style="position:absolute;top:12px;right:16px;background:none;border:none;
                    color:{KOLOR_NEUTRAL};font-size:22px;cursor:pointer;padding:4px 8px;
                    border-radius:6px;" title="Zamknij">✕</button>
                <div style="text-align:center;margin-bottom:20px;">
                    <div style="font-size:28px;margin-bottom:4px;">🔔</div>
                    <div style="font-size:22px;font-weight:700;color:#ffffff;">Giełda zamknięta</div>
                    <div style="color:{KOLOR_NEUTRAL};font-size:13px;margin-top:4px;">
                        Podsumowanie tygodnia — {teraz.strftime('%d.%m.%Y, %H:%M')}</div>
                </div>
                <div style="color:{KOLOR_NEUTRAL};font-size:11px;text-transform:uppercase;
                    letter-spacing:1px;margin-bottom:8px;">🏆 Podium (pozycje ujawnione)</div>
                {top3_html}{poz_wybranej}{cash_html}{dl}
                <button onclick="document.getElementById('overlay-zamkniecie').style.display='none'"
                    style="display:block;width:100%;margin-top:20px;padding:12px;
                    background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);
                    border-radius:8px;color:#ffffff;font-size:14px;cursor:pointer;">
                    Przejdź do Terminala →</button>
            </div>
        </div>""", unsafe_allow_html=True)


def render_banner_cash(grupy_cash):
    if not grupy_cash:
        return
    lista = ", ".join(grupy_cash[:8])
    reszta = f" i {len(grupy_cash)-8} więcej..." if len(grupy_cash) > 8 else ""
    st.markdown(f"""
        <div style="padding:10px 16px;background:rgba(251,191,36,0.1);
                    border:1px solid {KOLOR_ZOLTY};border-radius:8px;
                    margin-bottom:12px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:20px;">💤</span>
            <div>
                <div style="color:{KOLOR_ZOLTY};font-size:13px;font-weight:600;">
                    Grupy w 100% CASH (brak otwartych pozycji)</div>
                <div style="color:{KOLOR_NEUTRAL};font-size:12px;">
                    {lista}{reszta} — zgłoście rebalans do obsługi konkursu!</div>
            </div>
        </div>""", unsafe_allow_html=True)


# =============================================
# ====== ŁADOWANIE DANYCH ====================
# =============================================

dane_stat = wczytaj_dane_statyczne()
TICKERY = dane_stat.get("TICKERY", {})
MAPOWANIE_PDF = dane_stat.get("MAPOWANIE_PDF", {})
DANE_GRUP = dane_stat.get("DANE_GRUP", {})
ustawienia = wczytaj_ustawienia()

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


# === LOGIKA CZASU ===
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


# === POBIERANIE DANYCH ===
@st.cache_data(ttl=60)
def pobierz_dane_rynkowe(ticker, data_startu):
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
        logger.error("yfinance %s: %s", ticker, e)
        return pd.DataFrame()

zmiany_rynkowe = {}
wszystkie_historie_zmian = {}
dane_rynkowe_cache = {}

with st.spinner('Synchronizacja danych rynkowych...'):
    for nazwa, ticker in TICKERY.items():
        hist = pobierz_dane_rynkowe(ticker, data_startu_str)
        dane_rynkowe_cache[nazwa] = hist
        if not hist.empty:
            cena_otw = hist['Open'].iloc[0]
            cena_live = hist['Close'].iloc[-1]
            if cena_otw != 0:
                zmiany_rynkowe[nazwa] = (cena_live - cena_otw) / cena_otw
                wszystkie_historie_zmian[nazwa] = (hist['Close'] - cena_otw) / cena_otw

if not zmiany_rynkowe:
    st.warning("⚠️ Brak danych rynkowych. Wyniki mogą być nieaktualne.")


# === RANKING (jednorazowe przejście) ===
wyniki_rankingu = []
sentyment = {k: {"LONG": 0, "SHORT": 0} for k in TICKERY}
srednie_wagi = {k: 0.0 for k in TICKERY}
liczba_grup = len(aktywne_portfele)

for g_nazwa, g_dane in aktywne_portfele.items():
    wynik_g = g_dane["kapital_startowy"]
    for inst, waga in g_dane["pozycje"].items():
        if inst in zmiany_rynkowe:
            wynik_g += waga * zmiany_rynkowe[inst]
        if inst in sentyment:
            if waga > 0: sentyment[inst]["LONG"] += waga
            elif waga < 0: sentyment[inst]["SHORT"] += abs(waga)
        if inst in srednie_wagi:
            srednie_wagi[inst] += waga / liczba_grup if liczba_grup > 0 else 0
    wyniki_rankingu.append({"Grupa": g_nazwa, "Wynik": round(wynik_g, 4)})

ranking_df = (pd.DataFrame(wyniki_rankingu)
              .sort_values(by="Wynik", ascending=False).reset_index(drop=True))
ranking_df.index += 1

# Dystans do lidera
wynik_lidera = ranking_df.iloc[0]["Wynik"] if not ranking_df.empty else 100.0
ranking_df["Dystans do #1"] = round(ranking_df["Wynik"] - wynik_lidera, 4)
lider_konkursu = ranking_df.iloc[0]["Grupa"] if not ranking_df.empty else "Grupa 13"


# === UI: WYBÓR GRUPY ===
lista_grup = sorted(list(aktywne_portfele.keys()))
idx_domyslny = lista_grup.index(lider_konkursu) if lider_konkursu in lista_grup else 0

col_t, col_w = st.columns([2, 1])
with col_w:
    wybrana_grupa = st.selectbox("Wybór portfela:", lista_grup, index=idx_domyslny)
with col_t:
    st.title(f"Widok portfela: {wybrana_grupa}")

# === OVERLAY ===
gielda_zamknieta = czy_gielda_zamknieta(teraz)
grupy_cash = znajdz_grupy_w_cashu(aktywne_portfele)

if gielda_zamknieta:
    wk = ostatni_poniedzialek.strftime('%Y-%m-%d')
    if st.session_state.get("_overlay_week") != wk:
        st.session_state["_overlay_ukryty"] = False
        st.session_state["_overlay_week"] = wk
    if not st.session_state.get("_overlay_ukryty", False):
        render_overlay_zamkniecia(ranking_df, grupy_cash, wybrana_grupa, teraz, aktywne_portfele)


# === OBLICZENIA DLA WYBRANEJ GRUPY ===
kapital_poczatkowy = float(aktywne_portfele[wybrana_grupa]["kapital_startowy"])
pozycje_z_panelu = aktywne_portfele[wybrana_grupa]["pozycje"]

zysk_laczny = 0.0
dane_do_tabeli = []
wklady_instrumentow = {}

for nazwa, wielkosc in pozycje_z_panelu.items():
    if wielkosc != 0 and nazwa in zmiany_rynkowe:
        wynik_poz = wielkosc * zmiany_rynkowe[nazwa]
        zysk_laczny += wynik_poz
        wklady_instrumentow[nazwa] = wynik_poz

        hist = dane_rynkowe_cache.get(nazwa, pd.DataFrame())
        c_start = hist['Open'].iloc[0] if not hist.empty else 0
        c_live = hist['Close'].iloc[-1] if not hist.empty else 0
        dane_do_tabeli.append({
            "Instrument": nazwa,
            "Kierunek": "LONG" if wielkosc > 0 else "SHORT",
            "Wielkość": wielkosc,
            "Cena Start": c_start, "Cena LIVE": c_live, "Wynik": wynik_poz,
        })

stan_konta = kapital_poczatkowy + zysk_laczny
zmiana_proc = (zysk_laczny / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0

historia_portfela = buduj_historie_z_serii(pozycje_z_panelu, wszystkie_historie_zmian)
historia_sredniej = buduj_historie_z_serii(srednie_wagi, wszystkie_historie_zmian)
historia_rynku = buduj_historie_z_serii(
    {n: 25.0 for n in TICKERY}, wszystkie_historie_zmian)

zysk_rynku = sum(25.0 * z for z in zmiany_rynkowe.values())
alfa_proc = zmiana_proc - zysk_rynku

zwyciestwa = sum(1 for p in dane_do_tabeli if p["Wynik"] > 0)
wszystkie_pozycje = len(dane_do_tabeli)
skutecznosc = (zwyciestwa / wszystkie_pozycje * 100) if wszystkie_pozycje > 0 else 0.0

if not historia_portfela.empty:
    s_total = historia_portfela.sum(axis=1) + kapital_poczatkowy
    mdd_proc = (oblicz_max_drawdown(s_total) / kapital_poczatkowy * 100) if kapital_poczatkowy != 0 else 0.0
else:
    mdd_proc = 0.0

# Pozycja w rankingu
moje_miejsce = (ranking_df[ranking_df['Grupa']==wybrana_grupa].index[0]
                if wybrana_grupa in ranking_df['Grupa'].values else 0)

klucz_sesji = f"pop_m_{wybrana_grupa}"
if klucz_sesji not in st.session_state:
    st.session_state[klucz_sesji] = moje_miejsce
else:
    if moje_miejsce < st.session_state[klucz_sesji]:
        st.toast(f"📈 Awans: {wybrana_grupa} → #{moje_miejsce}")
    elif moje_miejsce > st.session_state[klucz_sesji]:
        st.toast(f"📉 Spadek: {wybrana_grupa} → #{moje_miejsce}")
    st.session_state[klucz_sesji] = moje_miejsce

# Historia pozycji w rankingu (do wykresu w sesji)
hk = f"hist_poz_{wybrana_grupa}"
if hk not in st.session_state:
    st.session_state[hk] = []
st.session_state[hk].append({"czas": teraz.strftime('%H:%M'), "miejsce": moje_miejsce})
if len(st.session_state[hk]) > 120:
    st.session_state[hk] = st.session_state[hk][-120:]


# ==========================================
# ====== SIDEBAR ===========================
# ==========================================

with st.sidebar:
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
        st.info(f"Otwarcie za: {roznica.days}d {roznica.seconds//3600}h")
    else:
        st.success("Sesja rebalansu otwarta")
        haslo = st.secrets.get("ADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", ""))
        if not haslo:
            st.warning("Brak skonfigurowanego hasła (st.secrets / env).")
        elif st.text_input("Hasło:", type="password") == haslo:
            st.divider()
            tryb = st.radio("Tryb:", ["Pojedyncza grupa", "Batch (tabela)"], horizontal=True)

            if tryb == "Pojedyncza grupa":
                gr = st.selectbox("Grupa:", sorted(aktywne_portfele.keys()))
                kap = aktywne_portfele[gr]["kapital_startowy"]
                poz = aktywne_portfele[gr]["pozycje"]
                wypr = kap + sum(poz.get(i,0)*zmiany_rynkowe.get(i,0) for i in poz)

                nk = st.number_input(f"Kapitał ({gr})", value=float(round(wypr, 2)))
                np_ = {k: st.number_input(k, value=float(poz.get(k,0)), step=5.0) for k in TICKERY}

                if sum(abs(v) for v in np_.values()) > nk:
                    st.error("Limit zaangażowania przekroczony.")
                elif st.button("Zapisz"):
                    stare = aktywne_portfele.get(gr, {})
                    nowe = {"kapital_startowy": nk, "pozycje": np_}
                    backup_portfela()
                    ustawienia[gr] = nowe
                    zapisz_ustawienia(ustawienia)
                    zapisz_log(gr, stare, nowe)
                    st.cache_data.clear()
                    st.success(f"✅ {gr} zapisana + backup + log")
                    st.rerun()

            else:  # BATCH
                st.markdown("#### Batch Edit")
                st.caption("Edytuj tabelę, kliknij 'Zapisz batch'.")

                rows = []
                for gn in sorted(aktywne_portfele.keys()):
                    g = aktywne_portfele[gn]
                    k = g["kapital_startowy"]
                    wypr = k + sum(g["pozycje"].get(i,0)*zmiany_rynkowe.get(i,0)
                                   for i in g["pozycje"])
                    rows.append({
                        "Grupa": gn, "Kapitał": round(wypr, 2),
                        "SPX": g["pozycje"].get("S&P 500", 0.0),
                        "GOLD": g["pozycje"].get("Złoto (Gold)", 0.0),
                        "10Y": g["pozycje"].get("US10Y Yield", 0.0),
                        "EUR": g["pozycje"].get("EUR/USD", 0.0),
                    })

                ed = st.data_editor(
                    pd.DataFrame(rows),
                    column_config={
                        "Grupa": st.column_config.TextColumn(disabled=True),
                        "Kapitał": st.column_config.NumberColumn(step=0.01),
                        "SPX": st.column_config.NumberColumn(step=5),
                        "GOLD": st.column_config.NumberColumn(step=5),
                        "10Y": st.column_config.NumberColumn(step=5),
                        "EUR": st.column_config.NumberColumn(step=5),
                    },
                    use_container_width=True, hide_index=True, key="batch_ed")

                errs = []
                for _, r in ed.iterrows():
                    z = abs(r["SPX"])+abs(r["GOLD"])+abs(r["10Y"])+abs(r["EUR"])
                    if z > r["Kapitał"]:
                        errs.append(f'{r["Grupa"]}: {z:.0f} > {r["Kapitał"]:.0f}')
                for e in errs:
                    st.error(e)

                if not errs and st.button("💾 Zapisz batch"):
                    backup_portfela()
                    cnt = 0
                    for _, r in ed.iterrows():
                        gn = r["Grupa"]
                        stare = aktywne_portfele.get(gn, {})
                        nowe = {"kapital_startowy": r["Kapitał"], "pozycje": {
                            "S&P 500": r["SPX"], "Złoto (Gold)": r["GOLD"],
                            "US10Y Yield": r["10Y"], "EUR/USD": r["EUR"],
                        }}
                        if nowe != stare:
                            zapisz_log(gn, stare, nowe)
                            cnt += 1
                        ustawienia[gn] = nowe
                    zapisz_ustawienia(ustawienia)
                    st.cache_data.clear()
                    st.success(f"✅ {cnt} grup zmienionych, backup + log OK")
                    st.rerun()

    # === EKSPORT XLSX ===
    st.divider()
    st.markdown("### Eksport danych")
    if st.button("📊 Pobierz ranking (.xlsx)"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as wr:
            ranking_df.to_excel(wr, sheet_name='Ranking', index=True)
            pr = []
            for gn in sorted(aktywne_portfele.keys()):
                g = aktywne_portfele[gn]
                row = {"Grupa": gn, "Kapitał": g["kapital_startowy"]}
                row.update(g["pozycje"])
                pr.append(row)
            pd.DataFrame(pr).to_excel(wr, sheet_name='Pozycje', index=False)

            if os.path.exists(PLIK_LOGU):
                try:
                    with open(PLIK_LOGU, "r", encoding="utf-8") as f:
                        ld = json.load(f)
                    lf = [{"Timestamp": w["timestamp"], "Grupa": w["grupa"],
                           "Nowy Kap": w["nowe"].get("kapital_startowy",""),
                           "SPX": w["nowe"].get("pozycje",{}).get("S&P 500",""),
                           "GOLD": w["nowe"].get("pozycje",{}).get("Złoto (Gold)",""),
                           "10Y": w["nowe"].get("pozycje",{}).get("US10Y Yield",""),
                           "EUR": w["nowe"].get("pozycje",{}).get("EUR/USD",""),
                           } for w in ld]
                    pd.DataFrame(lf).to_excel(wr, sheet_name='Log zmian', index=False)
                except Exception:
                    pass

        st.download_button("⬇️ Pobierz Excel", data=buf.getvalue(),
            file_name=f"ranking_{teraz.strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Informacje o systemie")
    st.markdown("**Autor:** Antoni Bulsiewicz")
    st.markdown("[GitHub](https://github.com/dvmesh/uek_konkurs-portfelowy)")


# ==========================================
# ====== UI LAYOUT =========================
# ==========================================

if grupy_cash:
    render_banner_cash(grupy_cash)

# 1. KARTY
karty = [
    ("Stan konta", f"{stan_konta:.2f}", "#ffffff"),
    ("Zysk", f"{zysk_laczny:+.2f}", KOLOR_ZYSK if zysk_laczny >= 0 else KOLOR_STRATA),
    ("Stopa zwrotu", f"{zmiana_proc:+.2f}%",
     KOLOR_ZYSK if zmiana_proc >= 0 else KOLOR_STRATA),
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
kols = st.columns(len(karty))
for i, (l, v, c) in enumerate(karty):
    with kols[i]:
        render_karta(l, v, c)

st.markdown("<br>", unsafe_allow_html=True)
st.divider()


# 2. WYKRES PORTFELA
st.subheader("Stopa Zwrotu (vs Benchmark)")
fig = go.Figure()
if not historia_portfela.empty:
    tm = historia_portfela.sum(axis=1)
    dodaj_serie_z_etykieta(fig, tm.index, tm, wybrana_grupa,
                           color='#e5e7eb', width=2.5, fill=True)
if not historia_sredniej.empty:
    ta = historia_sredniej.sum(axis=1)
    dodaj_serie_z_etykieta(fig, ta.index, ta, 'Średnia Konkursu',
                           color='rgba(251,191,36,0.6)', width=1.5, dash='dot',
                           ax=45, ay=-25, marker_size=5, label_prefix="Śr: ")
if not historia_rynku.empty:
    tr = historia_rynku.sum(axis=1)
    dodaj_serie_z_etykieta(fig, tr.index, tr, 'Rynek (Równa Alokacja)',
                           color='#38bdf8', width=1.5, dash='dash',
                           ax=45, ay=25, marker_size=5, label_prefix="Rynek: ")
fig.update_layout(
    template="plotly_dark", height=450,
    margin=dict(l=10, r=80, t=10, b=10),
    yaxis=dict(zeroline=True, zerolinecolor='rgba(255,255,255,0.1)',
               gridcolor='rgba(255,255,255,0.05)'),
    xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(0,0,0,0)'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig, use_container_width=True)
st.divider()


# 3. TABELE + SENTYMENT (LEWA) | RANKING (PRAWA)
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
            }, use_container_width=True, hide_index=True)
    else:
        st.info("Brak otwartych pozycji.")

    st.write("")
    st.subheader("Analiza Sentymentu")
    fig_pie = make_subplots(rows=2, cols=2,
        specs=[[{"type":"domain"},{"type":"domain"}],[{"type":"domain"},{"type":"domain"}]],
        subplot_titles=list(sentyment.keys()))
    for i, (inst, ds) in enumerate(sentyment.items()):
        r, c = (i//2)+1, (i%2)+1
        if ds['LONG']==0 and ds['SHORT']==0:
            fig_pie.add_trace(go.Pie(labels=['Brak'], values=[1],
                marker_colors=[KOLOR_NEUTRAL], hole=.5, textinfo='none'), row=r, col=c)
        else:
            fig_pie.add_trace(go.Pie(labels=['LONG','SHORT'],
                values=[ds['LONG'], ds['SHORT']],
                marker_colors=[KOLOR_ZYSK, KOLOR_STRATA],
                textinfo='percent', hole=.5,
                textfont=dict(color='#fff')), row=r, col=c)
    for a in fig_pie['layout']['annotations']:
        a['font'] = dict(size=13, color=KOLOR_NEUTRAL)
    fig_pie.update_layout(template="plotly_dark", height=400,
        margin=dict(l=10,r=10,t=40,b=10), showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_pie, use_container_width=True)

    # Net Exposure
    st.subheader("Net Exposure")
    ne = {i: ds["LONG"]-ds["SHORT"] for i, ds in sentyment.items()}
    fig_ne = go.Figure(go.Bar(
        x=list(ne.keys()), y=list(ne.values()),
        marker_color=[KOLOR_ZYSK if v>=0 else KOLOR_STRATA for v in ne.values()],
        text=[f"{v:+.0f}" for v in ne.values()],
        textposition='outside', textfont=dict(color='#e5e7eb')))
    fig_ne.update_layout(template="plotly_dark", height=250,
        margin=dict(l=10,r=10,t=10,b=10),
        yaxis=dict(zeroline=True, zerolinecolor='rgba(255,255,255,0.2)',
                   gridcolor='rgba(255,255,255,0.05)', title="j. netto"),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_ne, use_container_width=True)

with col_right:
    st.subheader("Ranking Konkursowy")
    st.dataframe(ranking_df,
        column_config={
            "Wynik": st.column_config.NumberColumn(format="%.4f"),
            "Dystans do #1": st.column_config.NumberColumn(format="%.4f",
                help="Różnica w j.p. do lidera. Lider = 0."),
        },
        height=600, use_container_width=True, hide_index=False)

st.divider()


# 4. WATERFALL — DEKOMPOZYCJA WYNIKU (zamiast wykresu notowań)
st.subheader("Dekompozycja wyniku — wkład instrumentów")

kolory_inst = {"S&P 500":"#3b82f6","US10Y Yield":"#a855f7",
               "Złoto (Gold)":"#eab308","EUR/USD":"#06b6d4"}

if wklady_instrumentow:
    posort = dict(sorted(wklady_instrumentow.items(), key=lambda x: abs(x[1]), reverse=True))

    fig_wf = go.Figure()
    running = 0
    nazwy_all = list(posort.keys()) + ["RAZEM"]
    for nazwa, wartosc in posort.items():
        kol = kolory_inst.get(nazwa, "#fff")
        fig_wf.add_trace(go.Bar(
            x=[nazwa], y=[wartosc], base=[running],
            marker_color=kol, marker_opacity=0.85,
            text=[f"{wartosc:+.2f}"], textposition='outside',
            textfont=dict(color=kol, size=13), showlegend=False,
            hovertemplate=f"<b>{nazwa}</b><br>Wkład: {wartosc:+.2f}<extra></extra>"))
        running += wartosc

    # Connector lines
    run2 = 0
    keys = list(posort.keys())
    for i, (n, v) in enumerate(posort.items()):
        run2 += v
        nxt = keys[i+1] if i < len(keys)-1 else "RAZEM"
        fig_wf.add_trace(go.Scatter(
            x=[n, nxt], y=[run2, run2], mode='lines',
            line=dict(color='rgba(255,255,255,0.15)', width=1, dash='dot'),
            showlegend=False, hoverinfo='skip'))

    # Słupek RAZEM
    kt = KOLOR_ZYSK if zysk_laczny >= 0 else KOLOR_STRATA
    fig_wf.add_trace(go.Bar(
        x=["RAZEM"], y=[zysk_laczny],
        marker_color=kt, marker_opacity=1.0,
        marker_line=dict(color="#fff", width=1),
        text=[f"<b>{zysk_laczny:+.2f}</b>"], textposition='outside',
        textfont=dict(color=kt, size=14), showlegend=False))

    fig_wf.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.2)")
    fig_wf.update_layout(
        template="plotly_dark", height=350,
        margin=dict(l=10,r=20,t=10,b=10), barmode='overlay',
        yaxis=dict(zeroline=True, zerolinecolor='rgba(255,255,255,0.2)',
                   gridcolor='rgba(255,255,255,0.05)', title="Wkład (j.p.)"),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_wf, use_container_width=True)
else:
    st.info("Brak otwartych pozycji — nie ma czego dekomponować.")


# 5. HISTORIA POZYCJI W RANKINGU
hp = st.session_state.get(f"hist_poz_{wybrana_grupa}", [])
if len(hp) > 1:
    st.subheader(f"Pozycja w rankingu — {wybrana_grupa} (sesja)")
    df_hp = pd.DataFrame(hp)
    fig_hp = go.Figure()
    fig_hp.add_trace(go.Scatter(
        x=df_hp["czas"], y=df_hp["miejsce"],
        mode='lines+markers', line=dict(color=KOLOR_ZOLTY, width=2.5),
        marker=dict(color=KOLOR_ZOLTY, size=6), name="Pozycja"))
    fig_hp.update_layout(
        template="plotly_dark", height=250,
        margin=dict(l=10,r=20,t=10,b=10),
        yaxis=dict(autorange="reversed", dtick=1,
                   gridcolor='rgba(255,255,255,0.05)', title="Miejsce"),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_hp, use_container_width=True)

st.caption(f"Stan: {teraz.strftime('%H:%M:%S')} (Warsaw) | Auto-odświeżanie: 60s")
