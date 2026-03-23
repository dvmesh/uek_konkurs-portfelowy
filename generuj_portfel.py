#!/usr/bin/env python3
"""
Skrypt do ręcznego generowania portfel.json po opuszczonym rebalansie.

Używa DOKŁADNYCH wartości z Excela profesora jako kapitałów końcowych tygodnia 1.
Te kapitały stają się kapitałami startowymi tygodnia 2.

UŻYCIE:
1. Edytuj sekcję NOWE_POZYCJE_TYG2 poniżej — wpisz nowe wagi dla każdej grupy.
   Format: {"SPX": waga, "GOLD": waga, "RENT": waga, "EURUSD": waga}
   Jeśli grupa nie zmienia pozycji — zostaw None.
2. Uruchom: python generuj_portfel.py
3. Skopiuj wygenerowany portfel.json do repo.
"""

import json
import os
import shutil
from datetime import datetime

# ============================================================
# KAPITAŁY KOŃCOWE TYGODNIA 1 (z Excela profesora)
# ============================================================
# Oficjalne stany portfeli po tygodniu 16.03-20.03.2026
# Źródło: arkusz "I rok - wyniki" i "II rok wyniki"

KAPITALY_PO_TYG1 = {
    "Grupa 1":  102.650501,
    "Grupa 2":   98.660416,
    "Grupa 3":  102.537886,
    "Grupa 4":  101.920587,
    "Grupa 5":   96.938881,
    "Grupa 6":   98.611109,
    "Grupa 7":  103.428548,
    "Grupa 8":   97.701065,
    "Grupa 9":  100.572501,
    "Grupa 10": 103.942890,
    "Grupa 11": 102.418339,
    "Grupa 12": 102.654268,
    "Grupa 13": 106.714265,
    "Grupa 14":  98.742278,
    "Grupa 15":  96.953299,
    "Grupa A":   93.358417,
    "Grupa B":   98.122413,
    "Grupa C":  104.609123,
    "Grupa D":   92.654209,
    "Grupa E":   98.591003,
    "Grupa F":  104.239337,
    "Grupa G":  106.540733,
    "Grupa H":   96.654286,
    "Grupa I":   95.974710,
    "Grupa J":   98.591003,
    "Grupa K":  106.540733,
    "Grupa L":  106.540733,
    "Grupa M":  105.232587,
    "Grupa N":   97.484557,
}

# ============================================================
# POZYCJE Z TYGODNIA 1 (fallback jeśli grupa nie zmienia)
# ============================================================
POZYCJE_TYG1 = {
    "Grupa 1":  {"SPX": -25, "GOLD": -25, "RENT": 0, "EURUSD": -50},
    "Grupa 2":  {"SPX": -50, "GOLD": 30, "RENT": 20, "EURUSD": 0},
    "Grupa 3":  {"SPX": -20, "GOLD": -10, "RENT": 45, "EURUSD": -25},
    "Grupa 4":  {"SPX": -35, "GOLD": 0, "RENT": 45, "EURUSD": -20},
    "Grupa 5":  {"SPX": -35, "GOLD": 35, "RENT": -15, "EURUSD": 15},
    "Grupa 6":  {"SPX": 70, "GOLD": 0, "RENT": 0, "EURUSD": 30},
    "Grupa 7":  {"SPX": -30, "GOLD": -30, "RENT": 0, "EURUSD": -40},
    "Grupa 8":  {"SPX": 40, "GOLD": 20, "RENT": 20, "EURUSD": 20},
    "Grupa 9":  {"SPX": 0, "GOLD": 0, "RENT": 20, "EURUSD": 0},
    "Grupa 10": {"SPX": 0, "GOLD": -30, "RENT": 40, "EURUSD": -30},
    "Grupa 11": {"SPX": 25, "GOLD": -25, "RENT": 25, "EURUSD": -25},
    "Grupa 12": {"SPX": -60, "GOLD": 0, "RENT": 40, "EURUSD": 0},
    "Grupa 13": {"SPX": 0, "GOLD": -50, "RENT": 50, "EURUSD": 0},
    "Grupa 14": {"SPX": 50, "GOLD": 0, "RENT": 0, "EURUSD": 0},
    "Grupa 15": {"SPX": 10, "GOLD": 40, "RENT": 50, "EURUSD": 0},
    "Grupa A":  {"SPX": -30, "GOLD": 70, "RENT": 0, "EURUSD": 0},
    "Grupa B":  {"SPX": 50, "GOLD": 0, "RENT": 0, "EURUSD": -50},
    "Grupa C":  {"SPX": -30, "GOLD": -40, "RENT": 0, "EURUSD": -30},
    "Grupa D":  {"SPX": 40, "GOLD": 60, "RENT": 0, "EURUSD": 0},
    "Grupa E":  {"SPX": -70, "GOLD": 30, "RENT": 0, "EURUSD": 0},
    "Grupa F":  {"SPX": -40, "GOLD": -25, "RENT": 25, "EURUSD": -10},
    "Grupa G":  {"SPX": -50, "GOLD": -50, "RENT": 0, "EURUSD": 0},
    "Grupa H":  {"SPX": 70, "GOLD": 15, "RENT": 0, "EURUSD": 0},
    "Grupa I":  {"SPX": -50, "GOLD": 50, "RENT": 0, "EURUSD": 0},
    "Grupa J":  {"SPX": -70, "GOLD": 30, "RENT": 0, "EURUSD": 0},
    "Grupa K":  {"SPX": -50, "GOLD": -50, "RENT": 0, "EURUSD": 0},
    "Grupa L":  {"SPX": -50, "GOLD": -50, "RENT": 0, "EURUSD": 0},
    "Grupa M":  {"SPX": -40, "GOLD": -40, "RENT": 0, "EURUSD": 0},
    "Grupa N":  {"SPX": 100, "GOLD": 0, "RENT": 0, "EURUSD": 0},
}

# ============================================================
# NOWE POZYCJE NA TYDZIEŃ 2 (23.03 - 27.03.2026)
# ============================================================
# Wpisz nowe wagi dla każdej grupy.
# None = te same pozycje co tydzień 1.
# Pamiętaj: suma |wag| nie może przekroczyć kapitału!
#
# PRZYKŁAD:
# "Grupa 13": {"SPX": -30, "GOLD": -40, "RENT": 30, "EURUSD": 0},

NOWE_POZYCJE_TYG2 = {
    "Grupa 1":  None,
    "Grupa 2":  None,
    "Grupa 3":  None,
    "Grupa 4":  None,
    "Grupa 5":  None,
    "Grupa 6":  None,
    "Grupa 7":  None,
    "Grupa 8":  None,
    "Grupa 9":  None,
    "Grupa 10": None,
    "Grupa 11": None,
    "Grupa 12": None,
    "Grupa 13": {"SPX": 106.71, "GOLD": 0, "RENT": 0, "EURUSD": 0},
    "Grupa 14": None,
    "Grupa 15": None,
    "Grupa A":  None,
    "Grupa B":  None,
    "Grupa C":  None,
    "Grupa D":  None,
    "Grupa E":  None,
    "Grupa F":  None,
    "Grupa G":  None,
    "Grupa H":  None,
    "Grupa I":  None,
    "Grupa J":  None,
    "Grupa K":  None,
    "Grupa L":  None,
    "Grupa M":  None,
    "Grupa N":  None,
}


# ============================================================
# LOGIKA
# ============================================================

MAP_SKROT_DO_APP = {
    "SPX": "S&P 500",
    "GOLD": "Złoto (Gold)",
    "RENT": "US10Y Yield",
    "EURUSD": "EUR/USD",
}


def main():
    portfel = {}
    errors = []

    for g_nazwa in sorted(KAPITALY_PO_TYG1.keys()):
        kap = KAPITALY_PO_TYG1[g_nazwa]

        nowe = NOWE_POZYCJE_TYG2.get(g_nazwa)
        if nowe is not None:
            pozycje = {
                "S&P 500": float(nowe.get("SPX", 0)),
                "Złoto (Gold)": float(nowe.get("GOLD", 0)),
                "US10Y Yield": float(nowe.get("RENT", 0)),
                "EUR/USD": float(nowe.get("EURUSD", 0)),
            }
        else:
            stare = POZYCJE_TYG1.get(g_nazwa, {})
            pozycje = {
                "S&P 500": float(stare.get("SPX", 0)),
                "Złoto (Gold)": float(stare.get("GOLD", 0)),
                "US10Y Yield": float(stare.get("RENT", 0)),
                "EUR/USD": float(stare.get("EURUSD", 0)),
            }

        suma_wag = sum(abs(v) for v in pozycje.values())
        if suma_wag > kap + 0.01:
            errors.append(f"  ⚠️  {g_nazwa}: suma|wag|={suma_wag:.2f} > kapitał={kap:.2f}")

        portfel[g_nazwa] = {
            "kapital_startowy": round(kap, 6),
            "pozycje": pozycje,
        }

    if os.path.exists("portfel.json"):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy2("portfel.json", f"portfel_backup_{ts}.json")

    with open("portfel.json", "w", encoding="utf-8") as f:
        json.dump(portfel, f, ensure_ascii=False, indent=2)

    print(f"✅ Zapisano portfel.json ({len(portfel)} grup)")

    if errors:
        print(f"\n⚠️  PROBLEMY Z LIMITAMI:")
        for e in errors:
            print(e)

    ranking = sorted(KAPITALY_PO_TYG1.items(), key=lambda x: x[1], reverse=True)
    print(f"\n{'='*55}")
    print(f" RANKING PO TYGODNIU 1 (oficjalne dane profesora)")
    print(f"{'='*55}")
    for i, (g, s) in enumerate(ranking, 1):
        marker = " ← NOWE POZ." if NOWE_POZYCJE_TYG2.get(g) is not None else ""
        print(f"  #{i:2d}  {g:12s}  {s:10.6f}{marker}")

    zmienione = [g for g, p in NOWE_POZYCJE_TYG2.items() if p is not None]
    if zmienione:
        print(f"\n📝 Zmienione pozycje: {', '.join(zmienione)}")
    else:
        print(f"\n📝 Brak zmian pozycji — edytuj NOWE_POZYCJE_TYG2 i uruchom ponownie.")


if __name__ == "__main__":
    main()
