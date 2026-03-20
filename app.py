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

# === KONFIGURACJA ===
st.set_page_config(page_title="Terminal Konkursowy", layout="wide")
st_autorefresh(interval=60_000, key="auto_refresh")
logger = logging.getLogger(__name__)

TZ_WARSAW = ZoneInfo("Europe/Warsaw")
PLIK_USTAWIEN = "portfel.json"
PLIK_LOGU = "log_zmian.json"

# === PALETA KOLORÓW ===
C = {
    "gain": "#22c55e", "loss": "#ef4444", "warn": "#f59e0b", "info": "#3b82f6",
    "muted": "#64748b", "text": "#e2e8f0", "text2": "#94a3b8",
    "bg1": "#0f172a", "bg2": "#1e293b", "bg3": "#334155",
    "border": "rgba(148,163,184,0.12)", "glow_g": "rgba(34,197,94,0.15)",
    "glow_r": "rgba(239,68,68,0.12)",
}
# Kolory instrumentów
CI = {"S&P 500": "#3b82f6", "US10Y Yield": "#a855f7",
      "Złoto (Gold)": "#eab308", "EUR/USD": "#06b6d4"}

# === GLOBAL CSS ===
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');
:root {{
    --gain: {C["gain"]}; --loss: {C["loss"]}; --warn: {C["warn"]};
    --muted: {C["muted"]}; --bg2: {C["bg2"]}; --bg3: {C["bg3"]};
    --border: {C["border"]}; --text: {C["text"]}; --text2: {C["text2"]};
    --font-mono: 'JetBrains Mono', monospace;
    --font-sans: 'DM Sans', -apple-system, sans-serif;
}}
.stApp {{ font-family: var(--font-sans) !important; }}
.stApp [data-testid="stHeader"] {{ display: none; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border: none !important; background: none !important;
}}
.stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px; margin-bottom: 20px; }}
.stat-card {{
    background: var(--bg2); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px 18px; position: relative; overflow: hidden; transition: transform 0.15s;
}}
.stat-card:hover {{ transform: translateY(-2px); }}
.stat-card::before {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: var(--accent, var(--muted));
}}
.stat-label {{
    font-size: 10.5px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 1.2px; color: var(--text2); margin-bottom: 8px;
    display: flex; align-items: center; gap: 6px;
}}
.stat-value {{
    font-family: var(--font-mono); font-size: 22px; font-weight: 700;
    color: var(--text); line-height: 1.1;
}}
.stat-sub {{
    font-family: var(--font-mono); font-size: 11px; color: var(--text2);
    margin-top: 6px;
}}
.section-label {{
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 13px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 1.5px; color: var(--text2);
    padding: 6px 0; margin: 28px 0 14px 0; border-bottom: 1px solid var(--border);
    width: 100%;
}}
.ticker-strip {{
    display: flex; gap: 24px; padding: 10px 0;
    border-bottom: 1px solid var(--border); margin-bottom: 18px;
    overflow-x: auto; flex-wrap: nowrap;
}}
.ticker-item {{
    display: flex; align-items: center; gap: 10px; flex-shrink: 0;
}}
.ticker-name {{
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.5px; color: var(--text2);
}}
.ticker-price {{
    font-family: var(--font-mono); font-size: 13px; font-weight: 600; color: var(--text);
}}
.ticker-change {{
    font-family: var(--font-mono); font-size: 11px; font-weight: 600;
    padding: 2px 6px; border-radius: 4px;
}}
.ticker-dot {{
    width: 6px; height: 6px; border-radius: 50%;
}}
.rank-row {{
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; border-radius: 8px;
    background: var(--bg2); border: 1px solid var(--border);
    margin-bottom: 6px; transition: background 0.15s;
}}
.rank-row:hover {{ background: var(--bg3); }}
.rank-pos {{
    font-family: var(--font-mono); font-size: 13px; font-weight: 700;
    width: 32px; height: 32px; display: flex; align-items: center;
    justify-content: center; border-radius: 8px; flex-shrink: 0;
}}
.rank-name {{ font-size: 13px; font-weight: 600; color: var(--text); flex: 1; }}
.rank-score {{ font-family: var(--font-mono); font-size: 14px; font-weight: 700; }}
.rank-dist {{
    font-family: var(--font-mono); font-size: 10px; color: var(--muted);
    min-width: 60px; text-align: right;
}}
.sent-row {{
    display: flex; align-items: center; gap: 12px;
    padding: 10px 0; border-bottom: 1px solid var(--border);
}}
.sent-row:last-child {{ border-bottom: none; }}
.sent-name {{
    font-size: 12px; font-weight: 600; color: var(--text2);
    min-width: 80px;
}}
.sent-bar-wrap {{
    flex: 1; height: 22px; border-radius: 6px; overflow: hidden;
    display: flex; background: rgba(255,255,255,0.04);
}}
.sent-bar {{
    height: 100%; display: flex; align-items: center;
    justify-content: center; font-family: var(--font-mono);
    font-size: 10px; font-weight: 600; transition: width 0.4s;
}}
.sent-net {{
    font-family: var(--font-mono); font-size: 12px; font-weight: 600;
    min-width: 50px; text-align: right;
}}
.pos-tag {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 6px; font-family: var(--font-mono);
    font-size: 12px; font-weight: 600; border: 1px solid var(--border);
    background: var(--bg2);
}}
.pos-tag .dir {{ font-size: 10px; font-weight: 700; letter-spacing: 0.5px; }}
</style>
""", unsafe_allow_html=True)


# =============================================
# ====== HELPERY ==============================
# =============================================

def wczytaj_dane_statyczne():
    try:
        with open("dane_statyczne.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Brak pliku dane_statyczne.json!")
        return {"TICKERY": {}, "MAPOWANIE_PDF": {}, "DANE_GRUP": {}}
    except json.JSONDecodeError as e:
        st.error(f"Błąd parsowania: {e}")
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
    if os.path.exists(PLIK_USTAWIEN):
        ts = datetime.now(TZ_WARSAW).strftime('%Y%m%d_%H%M%S')
        shutil.copy2(PLIK_USTAWIEN, f"portfel_backup_{ts}.json")

def zapisz_ustawienia(dane):
    with open(PLIK_USTAWIEN, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False, indent=2)

def zapisz_log(grupa, stare, nowe):
    log = []
    if os.path.exists(PLIK_LOGU):
        try:
            with open(PLIK_LOGU, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    log.append({"timestamp": datetime.now(TZ_WARSAW).isoformat(),
                "grupa": grupa, "poprzednie": stare, "nowe": nowe})
    with open(PLIK_LOGU, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def dodaj_serie_z_etykieta(fig, index, values, name, color,
                           width=2.0, dash=None, ax=40, ay=0,
                           fill=False, marker_size=7, label_prefix=""):
    ls = dict(color=color, width=width)
    if dash: ls["dash"] = dash
    if fill:
        fig.add_trace(go.Scatter(x=index, y=values.clip(lower=0), fill='tozeroy',
            fillcolor=C["glow_g"], line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=index, y=values.clip(upper=0), fill='tozeroy',
            fillcolor=C["glow_r"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=index, y=values, line=ls, name=name))
    oy = values.iloc[-1]
    txt = f"{label_prefix}{oy:+.2f}" if label_prefix else f"<b>{oy:+.2f}</b>"
    fig.add_annotation(x=index[-1], y=oy, text=txt, showarrow=True, arrowhead=0,
        arrowcolor=color, ax=ax, ay=ay,
        font=dict(color=color, size=11 if label_prefix else 13),
        bgcolor=C["bg2"], bordercolor=color if not label_prefix else None,
        borderpad=3 if not label_prefix else 0)
    fig.add_trace(go.Scatter(x=[index[-1]], y=[oy], mode='markers',
        marker=dict(color=color, size=marker_size), showlegend=False))

def oblicz_max_drawdown(s):
    return float((s - s.cummax()).min()) if not s.empty else 0.0

def buduj_historie_z_serii(wagi, hist):
    sr = [(hist[n]*w).rename(n) for n, w in wagi.items() if w != 0 and n in hist]
    return pd.concat(sr, axis=1).ffill().fillna(0) if sr else pd.DataFrame()

def czy_gielda_zamknieta(t):
    return t.weekday() in (5, 6) or (t.weekday() == 4 and t.hour >= 22)

def znajdz_grupy_w_cashu(p):
    return [n for n, d in p.items() if all(v == 0 for v in d.get("pozycje", {}).values())]

def skrot_inst(nazwa):
    return nazwa.replace("S&P 500","SPX").replace("Złoto (Gold)","GOLD") \
                .replace("US10Y Yield","10Y").replace("EUR/USD","EUR")


# === UI RENDERERS ===

def section_label(icon, text):
    st.markdown(f'<div class="section-label">{icon}&nbsp;&nbsp;{text}</div>',
                unsafe_allow_html=True)

def render_ticker_strip(cache, zmiany):
    """Pasek z cenami live na górze."""
    items = ""
    for nazwa in ["S&P 500", "Złoto (Gold)", "US10Y Yield", "EUR/USD"]:
        h = cache.get(nazwa, pd.DataFrame())
        if h.empty: continue
        price = h['Close'].iloc[-1]
        zmiana = zmiany.get(nazwa, 0) * 100
        kol = C["gain"] if zmiana >= 0 else C["loss"]
        bg = C["glow_g"] if zmiana >= 0 else C["glow_r"]
        dot_col = CI.get(nazwa, C["muted"])
        # Format price
        if price > 500: p_fmt = f"{price:,.0f}"
        elif price > 10: p_fmt = f"{price:,.2f}"
        else: p_fmt = f"{price:,.4f}"
        items += f"""
            <div class="ticker-item">
                <div class="ticker-dot" style="background:{dot_col};"></div>
                <div>
                    <div class="ticker-name">{skrot_inst(nazwa)}</div>
                    <div class="ticker-price">{p_fmt}</div>
                </div>
                <div class="ticker-change" style="color:{kol};background:{bg};">
                    {"▲" if zmiana >= 0 else "▼"} {abs(zmiana):.2f}%
                </div>
            </div>"""
    st.markdown(f'<div class="ticker-strip">{items}</div>', unsafe_allow_html=True)


def render_stat_cards(karty):
    """Grid kart statystyk z ikonami i akcentami."""
    html = '<div class="stat-grid">'
    for icon, label, value, sub, accent in karty:
        html += f"""
            <div class="stat-card" style="--accent:{accent};">
                <div class="stat-label">{icon} {label}</div>
                <div class="stat-value" style="color:{accent};">{value}</div>
                {'<div class="stat-sub">' + sub + '</div>' if sub else ''}
            </div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_pozycje_tagi(dane_tabeli):
    """Pozycje jako kolorowe tagi zamiast tabeli."""
    if not dane_tabeli:
        st.markdown(f'<div style="color:{C["muted"]};font-size:13px;padding:12px;">Brak otwartych pozycji — portfel w gotówce.</div>', unsafe_allow_html=True)
        return
    html = '<div style="display:flex;flex-wrap:wrap;gap:8px;padding:4px 0;">'
    for p in dane_tabeli:
        kol = C["gain"] if p["Wynik"] > 0 else (C["loss"] if p["Wynik"] < 0 else C["muted"])
        dir_txt = "LONG" if p["Kierunek"] == "LONG" else "SHORT"
        dir_col = C["gain"] if dir_txt == "LONG" else C["loss"]
        html += f"""
            <div class="pos-tag" style="border-color:{kol}40;">
                <span class="dir" style="color:{dir_col};">{dir_txt}</span>
                <span style="color:{C["text"]};">{skrot_inst(p["Instrument"])}</span>
                <span style="color:{C["muted"]};">×{abs(p["Wielkość"]):.0f}</span>
                <span style="color:{kol};margin-left:4px;font-size:11px;">{p["Wynik"]:+.2f}</span>
            </div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_sentyment_bars(sentyment):
    """Horizontal stacked bars zamiast pie chartów."""
    html = '<div style="padding:4px 0;">'
    for inst, ds in sentyment.items():
        total = ds["LONG"] + ds["SHORT"]
        l_pct = (ds["LONG"] / total * 100) if total > 0 else 0
        s_pct = 100 - l_pct if total > 0 else 0
        net = ds["LONG"] - ds["SHORT"]
        net_col = C["gain"] if net > 0 else (C["loss"] if net < 0 else C["muted"])

        bar_html = ""
        if total == 0:
            bar_html = f'<div class="sent-bar" style="width:100%;color:{C["muted"]};">—</div>'
        else:
            if l_pct > 0:
                bar_html += f'<div class="sent-bar" style="width:{l_pct}%;background:{C["gain"]}30;color:{C["gain"]};">{l_pct:.0f}% L</div>'
            if s_pct > 0:
                bar_html += f'<div class="sent-bar" style="width:{s_pct}%;background:{C["loss"]}30;color:{C["loss"]};">{s_pct:.0f}% S</div>'

        dot = CI.get(inst, C["muted"])
        html += f"""
            <div class="sent-row">
                <span class="sent-name"><span style="color:{dot};">●</span> {skrot_inst(inst)}</span>
                <div class="sent-bar-wrap">{bar_html}</div>
                <span class="sent-net" style="color:{net_col};">{net:+.0f}</span>
            </div>"""
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_ranking_html(ranking_df, wybrana, portfele):
    """Custom HTML ranking z podium i position badges."""
    html = ''
    for i, (idx, row) in enumerate(ranking_df.iterrows()):
        nazwa = row["Grupa"]
        wynik = row["Wynik"]
        dystans = row["Dystans do #1"]
        zm = wynik - 100
        kol = C["gain"] if zm >= 0 else C["loss"]
        is_selected = nazwa == wybrana

        # Position badge
        if i == 0: bg, fg = C["warn"], "#000"
        elif i == 1: bg, fg = C["bg3"], C["text"]
        elif i == 2: bg, fg = "#92400e", "#fbbf24"
        else: bg, fg = C["bg2"], C["muted"]

        _cw = C["warn"]
        sel_border = f"border-color:{_cw};" if is_selected else ""
        sel_bg = f"background:{_cw}08;" if is_selected else ""

        dist_txt = "" if i == 0 else f"{dystans:+.2f}"

        html += f"""
            <div class="rank-row" style="{sel_border}{sel_bg}">
                <div class="rank-pos" style="background:{bg};color:{fg};">{idx}</div>
                <div class="rank-name">{nazwa}{'  ◄' if is_selected else ''}</div>
                <div class="rank-score" style="color:{kol};">{wynik:.2f}</div>
                <div class="rank-dist">{dist_txt}</div>
            </div>"""

    st.markdown(html, unsafe_allow_html=True)


def render_overlay_zamkniecia(ranking, grupy_cash, wybrana, teraz, portfele):
    medale = ["🥇", "🥈", "🥉"]
    top3_html = ""
    for i in range(min(3, len(ranking))):
        row = ranking.iloc[i]
        n, w = row["Grupa"], row["Wynik"]
        zm = w - 100
        kol = C["gain"] if zm >= 0 else C["loss"]
        poz = portfele.get(n, {}).get("pozycje", {})
        tags = ""
        for inst, waga in poz.items():
            if waga != 0:
                kp = C["gain"] if waga > 0 else C["loss"]
                d = "L" if waga > 0 else "S"
                tags += f'<span style="display:inline-block;padding:2px 6px;margin:2px;border-radius:4px;font-size:10px;background:rgba(255,255,255,0.06);color:{kp};font-family:var(--font-mono);">{skrot_inst(inst)} {d}{abs(waga):.0f}</span>'
        top3_html += f"""
            <div style="padding:12px 16px;margin:6px 0;background:rgba(255,255,255,0.04);border-radius:10px;border-left:3px solid {kol};">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:17px;">{medale[i]} <b>{n}</b></span>
                    <span style="color:{kol};font-weight:700;font-size:15px;font-family:var(--font-mono);">{w:.2f} <span style="font-size:11px;">({zm:+.2f}%)</span></span>
                </div>
                <div style="margin-top:6px;">{tags}</div>
            </div>"""

    poz_w = ""
    if wybrana in ranking["Grupa"].values:
        idx = ranking[ranking["Grupa"]==wybrana].index[0]
        wr = ranking.loc[idx]
        wz = wr["Wynik"]-100
        wk = C["gain"] if wz >= 0 else C["loss"]
        poz_w = f'<div style="margin-top:16px;padding:14px 16px;background:{C["warn"]}10;border:1px solid {C["warn"]}40;border-radius:10px;text-align:center;"><div style="color:{C["text2"]};font-size:10px;text-transform:uppercase;letter-spacing:1px;">Twoja grupa</div><div style="font-size:18px;margin:4px 0;"><b>{wybrana}</b> — #{idx} / {len(ranking)}</div><div style="color:{wk};font-size:15px;font-weight:600;font-family:var(--font-mono);">{wr["Wynik"]:.2f} ({wz:+.2f}%)</div></div>'

    cash_h = ""
    if grupy_cash:
        lista = ", ".join(f"<b>{g}</b>" for g in sorted(grupy_cash))
        cash_h = f'<div style="margin-top:16px;padding:14px 16px;background:{C["loss"]}10;border:1px solid {C["loss"]}40;border-radius:10px;"><div style="font-size:13px;color:{C["loss"]};margin-bottom:4px;">⚠️ <b>Grupy w CASH:</b></div><div style="color:{C["text2"]};font-size:12px;">{lista}</div><div style="color:{C["muted"]};font-size:11px;margin-top:6px;">Zgłoście rebalans przed niedzielą 23:00!</div></div>'

    dl = ""
    if teraz.weekday() in (4,5):
        nd = teraz + timedelta(days=(6-teraz.weekday()))
        dl = f'<div style="margin-top:14px;text-align:center;color:{C["warn"]};font-size:12px;">🕐 Okno rebalansu: <b>niedziela {nd.strftime("%d.%m")}, do 23:00</b></div>'
    elif teraz.weekday() == 6 and teraz.hour < 23:
        dl = f'<div style="margin-top:14px;text-align:center;padding:10px;background:{C["gain"]}10;border:1px solid {C["gain"]}40;border-radius:8px;"><span style="color:{C["gain"]};font-size:13px;">🟢 <b>Rebalans OTWARTY</b> — {23-teraz.hour}h</span></div>'

    st.markdown(f"""
        <div id="overlay-zamkniecie" style="position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:99999;background:rgba(0,0,0,0.8);backdrop-filter:blur(12px);display:flex;align-items:center;justify-content:center;">
            <div style="background:{C["bg1"]};border:1px solid {C["border"]};border-radius:16px;padding:32px 36px;max-width:560px;width:90%;max-height:85vh;overflow-y:auto;box-shadow:0 25px 80px rgba(0,0,0,0.6);position:relative;font-family:var(--font-sans);">
                <button onclick="document.getElementById('overlay-zamkniecie').style.display='none'" style="position:absolute;top:14px;right:18px;background:none;border:none;color:{C["muted"]};font-size:20px;cursor:pointer;">✕</button>
                <div style="text-align:center;margin-bottom:20px;">
                    <div style="font-size:32px;margin-bottom:6px;">🏁</div>
                    <div style="font-size:20px;font-weight:700;color:{C["text"]};">Giełda zamknięta</div>
                    <div style="color:{C["muted"]};font-size:12px;margin-top:4px;">Podsumowanie — {teraz.strftime('%d.%m.%Y, %H:%M')}</div>
                </div>
                <div style="color:{C["text2"]};font-size:10px;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;">Podium — pozycje ujawnione</div>
                {top3_html}{poz_w}{cash_h}{dl}
                <button onclick="document.getElementById('overlay-zamkniecie').style.display='none'" style="display:block;width:100%;margin-top:22px;padding:12px;background:rgba(255,255,255,0.06);border:1px solid {C["border"]};border-radius:10px;color:{C["text"]};font-size:13px;cursor:pointer;font-family:var(--font-sans);font-weight:600;">Przejdź do Terminala →</button>
            </div>
        </div>""", unsafe_allow_html=True)


def render_banner_cash(grupy_cash):
    if not grupy_cash: return
    lista = ", ".join(grupy_cash[:8])
    reszta = f" +{len(grupy_cash)-8}" if len(grupy_cash) > 8 else ""
    st.markdown(f"""
        <div style="padding:10px 16px;background:{C["warn"]}0D;border:1px solid {C["warn"]}30;
                    border-radius:10px;margin-bottom:14px;display:flex;align-items:center;gap:10px;">
            <span style="font-size:18px;">💤</span>
            <div>
                <div style="color:{C["warn"]};font-size:12px;font-weight:600;">Grupy w 100% CASH</div>
                <div style="color:{C["text2"]};font-size:11px;">{lista}{reszta} — zgłoście rebalans!</div>
            </div>
        </div>""", unsafe_allow_html=True)


# plotly layout helper
def dark_layout(**kw):
    base = dict(
        template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="DM Sans, sans-serif"),
        yaxis=dict(gridcolor='rgba(148,163,184,0.06)', zerolinecolor='rgba(148,163,184,0.12)'),
        xaxis=dict(gridcolor='rgba(148,163,184,0.06)'),
        margin=dict(l=10, r=20, t=10, b=10),
    )
    base.update(kw)
    return base


# =============================================
# ====== DATA LOADING ========================
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
        "pozycje": {"S&P 500": g_poz.get("SPX", 0.0), "Złoto (Gold)": g_poz.get("GOLD", 0.0),
                    "US10Y Yield": g_poz.get("RENT", 0.0), "EUR/USD": g_poz.get("EURUSD", 0.0)}
    }
for g_nazwa, g_dane in ustawienia.items():
    if isinstance(g_dane, dict) and "kapital_startowy" in g_dane and "pozycje" in g_dane:
        aktywne_portfele[g_nazwa] = g_dane

teraz = datetime.now(TZ_WARSAW)
ostatni_pon = teraz - timedelta(days=teraz.weekday())
data_startu_str = ostatni_pon.strftime('%Y-%m-%d')
dni_do_nd = 6 - teraz.weekday()
nd = teraz + timedelta(days=dni_do_nd)
deadline = nd.replace(hour=23, minute=0, second=0, microsecond=0)
if teraz > deadline: deadline += timedelta(days=7)
roznica = deadline - teraz
czy_rebalans = (teraz.weekday() == 6) and (teraz.hour < 23)

@st.cache_data(ttl=60)
def pobierz(ticker, start):
    try:
        h = yf.Ticker(ticker).history(start=start, interval="1h")
        if h.empty: h = yf.Ticker(ticker).history(period="5d", interval="1h")
        if not h.empty:
            if h.index.tz is not None: h.index = h.index.tz_convert('Europe/Warsaw')
            h.index = h.index.tz_localize(None)
        return h
    except Exception as e:
        logger.error("yf %s: %s", ticker, e)
        return pd.DataFrame()

zmiany = {}
hist_all = {}
cache_rynk = {}

with st.spinner('Synchronizacja...'):
    for nazwa, ticker in TICKERY.items():
        h = pobierz(ticker, data_startu_str)
        cache_rynk[nazwa] = h
        if not h.empty:
            o = h['Open'].iloc[0]
            if o != 0:
                zmiany[nazwa] = (h['Close'].iloc[-1] - o) / o
                hist_all[nazwa] = (h['Close'] - o) / o

if not zmiany:
    st.warning("⚠️ Brak danych rynkowych.")

# === RANKING ===
wyniki = []
sentyment = {k: {"LONG": 0, "SHORT": 0} for k in TICKERY}
sr_wagi = {k: 0.0 for k in TICKERY}
n_grup = len(aktywne_portfele)

for gn, gd in aktywne_portfele.items():
    w = gd["kapital_startowy"]
    for inst, waga in gd["pozycje"].items():
        if inst in zmiany: w += waga * zmiany[inst]
        if inst in sentyment:
            if waga > 0: sentyment[inst]["LONG"] += waga
            elif waga < 0: sentyment[inst]["SHORT"] += abs(waga)
        if inst in sr_wagi: sr_wagi[inst] += waga / n_grup if n_grup > 0 else 0
    wyniki.append({"Grupa": gn, "Wynik": round(w, 4)})

ranking_df = pd.DataFrame(wyniki).sort_values("Wynik", ascending=False).reset_index(drop=True)
ranking_df.index += 1
w_lidera = ranking_df.iloc[0]["Wynik"] if not ranking_df.empty else 100.0
ranking_df["Dystans do #1"] = round(ranking_df["Wynik"] - w_lidera, 4)
lider = ranking_df.iloc[0]["Grupa"] if not ranking_df.empty else "Grupa 13"


# === UI: SELEKTOR ===
lista_grup = sorted(aktywne_portfele.keys())
idx_def = lista_grup.index(lider) if lider in lista_grup else 0
col_t, col_w = st.columns([2, 1])
with col_w:
    wybrana = st.selectbox("Wybór portfela:", lista_grup, index=idx_def, label_visibility="collapsed")
with col_t:
    st.markdown(f'<div style="font-size:26px;font-weight:700;color:{C["text"]};padding:6px 0;">{wybrana}</div>', unsafe_allow_html=True)

# === OVERLAY ===
gielda_off = czy_gielda_zamknieta(teraz)
grupy_cash = znajdz_grupy_w_cashu(aktywne_portfele)
if gielda_off:
    wk = ostatni_pon.strftime('%Y-%m-%d')
    if st.session_state.get("_ow") != wk:
        st.session_state["_oh"] = False; st.session_state["_ow"] = wk
    if not st.session_state.get("_oh", False):
        render_overlay_zamkniecia(ranking_df, grupy_cash, wybrana, teraz, aktywne_portfele)

# === OBLICZENIA PORTFELA ===
kap = float(aktywne_portfele[wybrana]["kapital_startowy"])
poz = aktywne_portfele[wybrana]["pozycje"]
zysk = 0.0; dane_tab = []; wklady = {}

for nazwa, wiel in poz.items():
    if wiel != 0 and nazwa in zmiany:
        wp = wiel * zmiany[nazwa]
        zysk += wp; wklady[nazwa] = wp
        h = cache_rynk.get(nazwa, pd.DataFrame())
        dane_tab.append({"Instrument": nazwa, "Kierunek": "LONG" if wiel > 0 else "SHORT",
                         "Wielkość": wiel,
                         "Cena Start": h['Open'].iloc[0] if not h.empty else 0,
                         "Cena LIVE": h['Close'].iloc[-1] if not h.empty else 0,
                         "Wynik": wp})

stan = kap + zysk
zm_prc = (zysk / kap * 100) if kap != 0 else 0
hp = buduj_historie_z_serii(poz, hist_all)
ha = buduj_historie_z_serii(sr_wagi, hist_all)
hr = buduj_historie_z_serii({n: 25.0 for n in TICKERY}, hist_all)
alfa = zm_prc - sum(25.0*z for z in zmiany.values())
wins = sum(1 for p in dane_tab if p["Wynik"] > 0)
n_poz = len(dane_tab)
hit = (wins/n_poz*100) if n_poz > 0 else 0.0
mdd = (oblicz_max_drawdown(hp.sum(axis=1)+kap)/kap*100) if not hp.empty and kap!=0 else 0.0

moje_m = ranking_df[ranking_df['Grupa']==wybrana].index[0] if wybrana in ranking_df['Grupa'].values else 0
ks = f"pm_{wybrana}"
if ks not in st.session_state: st.session_state[ks] = moje_m
else:
    if moje_m < st.session_state[ks]: st.toast(f"📈 Awans: {wybrana} → #{moje_m}")
    elif moje_m > st.session_state[ks]: st.toast(f"📉 Spadek: {wybrana} → #{moje_m}")
    st.session_state[ks] = moje_m

hk = f"hp_{wybrana}"
if hk not in st.session_state: st.session_state[hk] = []
st.session_state[hk].append({"t": teraz.strftime('%H:%M'), "m": moje_m})
if len(st.session_state[hk]) > 120: st.session_state[hk] = st.session_state[hk][-120:]


# ==========================================
# ====== SIDEBAR ===========================
# ==========================================

with st.sidebar:
    if gielda_off:
        if st.checkbox("Ukryj overlay", value=st.session_state.get("_oh", False), key="_co"):
            st.session_state["_oh"] = True
        else: st.session_state["_oh"] = False
        st.divider()

    st.header("Panel Administratora")
    if not czy_rebalans:
        st.error("Zablokowane")
        st.info(f"Otwarcie za: {roznica.days}d {roznica.seconds//3600}h")
    else:
        st.success("Sesja rebalansu otwarta")
        haslo = st.secrets.get("ADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", ""))
        if not haslo: st.warning("Brak hasła (st.secrets).")
        elif st.text_input("Hasło:", type="password") == haslo:
            st.divider()
            tryb = st.radio("Tryb:", ["Pojedyncza", "Batch"], horizontal=True)
            if tryb == "Pojedyncza":
                gr = st.selectbox("Grupa:", sorted(aktywne_portfele.keys()))
                gkap = aktywne_portfele[gr]["kapital_startowy"]
                gpoz = aktywne_portfele[gr]["pozycje"]
                wypr = gkap + sum(gpoz.get(i,0)*zmiany.get(i,0) for i in gpoz)
                nk = st.number_input(f"Kapitał ({gr})", value=float(round(wypr, 2)))
                np_ = {k: st.number_input(k, value=float(gpoz.get(k,0)), step=5.0) for k in TICKERY}
                if sum(abs(v) for v in np_.values()) > nk: st.error("Limit przekroczony.")
                elif st.button("Zapisz"):
                    backup_portfela()
                    ustawienia[gr] = {"kapital_startowy": nk, "pozycje": np_}
                    zapisz_ustawienia(ustawienia); zapisz_log(gr, aktywne_portfele.get(gr,{}), ustawienia[gr])
                    st.cache_data.clear(); st.success(f"✅ {gr}"); st.rerun()
            else:
                st.caption("Edytuj, kliknij Zapisz batch.")
                rows = []
                for gn in sorted(aktywne_portfele.keys()):
                    g = aktywne_portfele[gn]; k = g["kapital_startowy"]
                    wypr = k+sum(g["pozycje"].get(i,0)*zmiany.get(i,0) for i in g["pozycje"])
                    rows.append({"Grupa":gn,"Kap":round(wypr,2),"SPX":g["pozycje"].get("S&P 500",0.0),
                                 "GOLD":g["pozycje"].get("Złoto (Gold)",0.0),
                                 "10Y":g["pozycje"].get("US10Y Yield",0.0),
                                 "EUR":g["pozycje"].get("EUR/USD",0.0)})
                ed = st.data_editor(pd.DataFrame(rows),
                    column_config={"Grupa":st.column_config.TextColumn(disabled=True)},
                    use_container_width=True, hide_index=True, key="be")
                errs = [f'{r["Grupa"]}' for _,r in ed.iterrows() if abs(r["SPX"])+abs(r["GOLD"])+abs(r["10Y"])+abs(r["EUR"])>r["Kap"]]
                for e in errs: st.error(f"Limit: {e}")
                if not errs and st.button("💾 Zapisz batch"):
                    backup_portfela(); cnt=0
                    for _,r in ed.iterrows():
                        n={"kapital_startowy":r["Kap"],"pozycje":{"S&P 500":r["SPX"],"Złoto (Gold)":r["GOLD"],"US10Y Yield":r["10Y"],"EUR/USD":r["EUR"]}}
                        if n!=aktywne_portfele.get(r["Grupa"],{}): zapisz_log(r["Grupa"],aktywne_portfele.get(r["Grupa"],{}),n); cnt+=1
                        ustawienia[r["Grupa"]]=n
                    zapisz_ustawienia(ustawienia); st.cache_data.clear()
                    st.success(f"✅ {cnt} zmian"); st.rerun()

    st.divider()
    if st.button("📊 Eksport .xlsx"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as wr:
            ranking_df.to_excel(wr, sheet_name='Ranking', index=True)
            pr=[{"Grupa":gn,"Kapitał":g["kapital_startowy"],**g["pozycje"]} for gn,g in sorted(aktywne_portfele.items())]
            pd.DataFrame(pr).to_excel(wr, sheet_name='Pozycje', index=False)
            if os.path.exists(PLIK_LOGU):
                try:
                    with open(PLIK_LOGU,"r",encoding="utf-8") as f: ld=json.load(f)
                    pd.DataFrame([{"Czas":w["timestamp"],"Grupa":w["grupa"],**{k:w["nowe"].get("pozycje",{}).get(k,"") for k in TICKERY}} for w in ld]).to_excel(wr, sheet_name='Log', index=False)
                except: pass
        st.download_button("⬇️ Pobierz", data=buf.getvalue(),
            file_name=f"ranking_{teraz.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown(f'<div style="margin-top:40px;padding-top:12px;border-top:1px solid {C["border"]};"><div style="color:{C["muted"]};font-size:11px;">Antoni Bulsiewicz · <a href="https://github.com/dvmesh/uek_konkurs-portfelowy" style="color:{C["info"]};">GitHub</a></div></div>', unsafe_allow_html=True)


# ==========================================
# ====== MAIN UI ===========================
# ==========================================

# 0. TICKER STRIP
render_ticker_strip(cache_rynk, zmiany)

# 0.5 CASH BANNER
if grupy_cash:
    render_banner_cash(grupy_cash)

# 1. STAT CARDS
pos_label = f"#{moje_m}" if moje_m <= 3 else f"#{moje_m}"
pos_sub = "z " + str(len(ranking_df))
dist = ranking_df.loc[ranking_df["Grupa"]==wybrana, "Dystans do #1"].values
dist_val = dist[0] if len(dist) else 0

render_stat_cards([
    ("💰", "Stan konta", f"{stan:.2f}", f"start: {kap:.0f}", C["text"]),
    ("📊", "P&L tygodnia", f"{zysk:+.2f}", f"{zm_prc:+.2f}%", C["gain"] if zysk >= 0 else C["loss"]),
    ("⚡", "Alfa vs rynek", f"{alfa:+.2f}%", "vs 4×25 benchmark", C["gain"] if alfa > 0 else (C["loss"] if alfa < 0 else C["muted"])),
    ("📉", "Max Drawdown", f"{mdd:+.2f}%", "tygodniowe MDD", C["loss"] if mdd < -1 else (C["warn"] if mdd < 0 else C["gain"])),
    ("🎯", "Hit Rate", f"{hit:.0f}%", f"{wins}/{n_poz} pozycji", C["gain"] if hit >= 50 else (C["loss"] if n_poz > 0 else C["muted"])),
    ("🏆", "Pozycja", pos_label, f"{pos_sub} · dystans {dist_val:+.2f}", C["warn"] if moje_m <= 3 else C["text"]),
])


# 2. POZYCJE (tagi)
section_label("📋", "Otwarte pozycje")
render_pozycje_tagi(dane_tab)

# 3. WYKRES PORTFELA
section_label("📈", "Stopa zwrotu vs benchmark")
fig = go.Figure()
if not hp.empty:
    tm = hp.sum(axis=1)
    dodaj_serie_z_etykieta(fig, tm.index, tm, wybrana, color=C["text"], width=2.5, fill=True)
if not ha.empty:
    ta = ha.sum(axis=1)
    dodaj_serie_z_etykieta(fig, ta.index, ta, 'Średnia', color=f'{C["warn"]}99',
                           width=1.5, dash='dot', ax=45, ay=-25, marker_size=5, label_prefix="Śr: ")
if not hr.empty:
    tr = hr.sum(axis=1)
    dodaj_serie_z_etykieta(fig, tr.index, tr, 'Rynek (4×25)', color=C["info"],
                           width=1.5, dash='dash', ax=45, ay=25, marker_size=5, label_prefix="Mkt: ")
fig.update_layout(**dark_layout(height=420, margin=dict(l=10, r=80, t=10, b=10),
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(0,0,0,0)')))
st.plotly_chart(fig, use_container_width=True)


# 4. TRZY KOLUMNY: WATERFALL | SENTYMENT | RANKING
c1, c2, c3 = st.columns([1.1, 0.9, 1])

with c1:
    section_label("🔬", "Dekompozycja wyniku")
    if wklady:
        pos = dict(sorted(wklady.items(), key=lambda x: abs(x[1]), reverse=True))
        fig_wf = go.Figure()
        run = 0
        keys = list(pos.keys())
        for n, v in pos.items():
            k = CI.get(n, C["text"])
            fig_wf.add_trace(go.Bar(x=[skrot_inst(n)], y=[v], base=[run], marker_color=k,
                marker_opacity=0.9, text=[f"{v:+.2f}"], textposition='outside',
                textfont=dict(color=k, size=12, family="JetBrains Mono"), showlegend=False))
            run += v
        # connectors
        run2 = 0
        for i, (n, v) in enumerate(pos.items()):
            run2 += v
            nxt = skrot_inst(keys[i+1]) if i < len(keys)-1 else "NETTO"
            fig_wf.add_trace(go.Scatter(x=[skrot_inst(n), nxt], y=[run2, run2], mode='lines',
                line=dict(color='rgba(148,163,184,0.12)', width=1, dash='dot'),
                showlegend=False, hoverinfo='skip'))
        kt = C["gain"] if zysk >= 0 else C["loss"]
        fig_wf.add_trace(go.Bar(x=["NETTO"], y=[zysk], marker_color=kt,
            marker_line=dict(color=kt, width=1.5),
            text=[f"<b>{zysk:+.2f}</b>"], textposition='outside',
            textfont=dict(color=kt, size=13, family="JetBrains Mono"), showlegend=False))
        fig_wf.add_hline(y=0, line_dash="dot", line_color="rgba(148,163,184,0.15)")
        fig_wf.update_layout(**dark_layout(height=380, barmode='overlay',
            yaxis=dict(gridcolor='rgba(148,163,184,0.06)', title=None)))
        st.plotly_chart(fig_wf, use_container_width=True)
    else:
        st.markdown(f'<div style="color:{C["muted"]};font-size:13px;padding:20px;">100% cash</div>', unsafe_allow_html=True)

with c2:
    section_label("🧭", "Sentyment rynku")
    render_sentyment_bars(sentyment)

with c3:
    section_label("🏅", "Ranking")
    render_ranking_html(ranking_df, wybrana, aktywne_portfele)


# 5. HISTORIA POZYCJI
hpd = st.session_state.get(f"hp_{wybrana}", [])
if len(hpd) > 1:
    section_label("📍", f"Pozycja {wybrana} — live tracking")
    df_hp = pd.DataFrame(hpd)
    fig_hp = go.Figure()
    fig_hp.add_trace(go.Scatter(x=df_hp["t"], y=df_hp["m"], mode='lines+markers',
        line=dict(color=C["warn"], width=2), marker=dict(color=C["warn"], size=5)))
    fig_hp.update_layout(**dark_layout(height=200,
        yaxis=dict(autorange="reversed", dtick=1, gridcolor='rgba(148,163,184,0.06)', title=None)))
    st.plotly_chart(fig_hp, use_container_width=True)

# FOOTER
st.markdown(f'<div style="text-align:center;padding:16px 0;color:{C["muted"]};font-size:11px;font-family:var(--font-mono);">◉ LIVE · {teraz.strftime("%H:%M:%S")} Warsaw · 60s refresh</div>', unsafe_allow_html=True)
