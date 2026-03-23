#!/usr/bin/env python3
"""
Ustaw nowe pozycje na bieżący tydzień w dane_statyczne.json.

UŻYCIE:
1. Edytuj NOWE_POZYCJE poniżej
2. Uruchom: python ustaw_pozycje.py
"""
import json

PLIK = "dane_statyczne.json"

# Wpisz nowe pozycje. Tylko te grupy które podały pozycje.
# Grupy których tu nie ma → zostają z pozycje: null (cash).
NOWE_POZYCJE = {
    # "Grupa 13": {"SPX": -30, "GOLD": -40, "RENT": 30, "EURUSD": 0},
    # "Grupa 7":  {"SPX": -25, "GOLD": -25, "RENT": 0, "EURUSD": -50},
}

def main():
    with open(PLIK, "r", encoding="utf-8") as f:
        dane = json.load(f)

    cnt = 0
    for g_nazwa, poz in NOWE_POZYCJE.items():
        if g_nazwa not in dane["GRUPY"]:
            print(f"  ⚠️  {g_nazwa} nie istnieje!")
            continue
        tyg = dane["GRUPY"][g_nazwa]["tygodnie"][-1]
        kap = tyg["kapital_startowy"]
        suma = sum(abs(v) for v in poz.values())
        if suma > kap + 0.01:
            print(f"  ⚠️  {g_nazwa}: suma|wag|={suma:.2f} > kapitał={kap:.2f}")
            continue
        tyg["pozycje"] = poz
        cnt += 1
        print(f"  ✓ {g_nazwa}: {poz} (kap={kap:.2f})")

    with open(PLIK, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Zaktualizowano {cnt} grup w {PLIK}")

if __name__ == "__main__":
    main()
