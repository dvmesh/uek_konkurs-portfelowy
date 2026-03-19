```markdown
# Terminal Konkursowy - Analiza Portfeli Inwestycyjnych

Aplikacja analityczna oparta na frameworku Streamlit, zaprojektowana do monitorowania i zarządzania portfelami inwestycyjnymi w czasie rzeczywistym. System śledzi notowania czterech głównych instrumentów finansowych, oblicza stopy zwrotu, wskaźniki ryzyka oraz generuje ranking wszystkich grup biorących udział w konkursie.

## Główne funkcjonalności

* **Monitoring na żywo (Live Feed):** Integracja z API Yahoo Finance (`yfinance`) pobierająca aktualne kwotowania dla S&P 500, US10Y Yield, Złota oraz EUR/USD. Dane są automatycznie konwertowane do strefy czasowej `Europe/Warsaw`.
* **Architektura Multi-Portfolio:** Możliwość przełączania widoku pomiędzy wszystkimi zarejestrowanymi grupami. Aplikacja domyślnie ładuje profil aktualnego lidera rankingu (Leaderboard Auto-Focus).
* **Wskaźniki efektywności i ryzyka:** System na żywo oblicza zysk/stratę netto, całkowitą stopę zwrotu oraz maksymalne obsunięcie kapitału (Max Drawdown - MDD) dla bieżącego tygodnia.
* **Porównanie z Benchmarkami:** Główny wykres portfela nakłada na siebie trzy krzywe:
  * Indywidualny wynik wybranej grupy.
  * Średnią rynkową (agregacja pozycji wszystkich grup w konkursie).
  * Rynek (teoretyczny portfel o równej alokacji 4x25%).
* **Analiza Sentymentu (Pozycjonowanie):** Agregacja danych ze wszystkich portfeli w celu wskazania stosunku pozycji LONG do SHORT dla każdego z instrumentów.
* **Panel Administratora:** Moduł zabezpieczony hasłem, pozwalający na weekendową relokację kapitału (od niedzieli do północy).

## Struktura projektu

* `app.py` - Główny silnik aplikacji (UI, logika biznesowa, pobieranie danych).
* `dane_statyczne.json` - Niezmienna baza danych zawierająca definicje tickerów giełdowych, mapowania nazw oraz początkowe alokacje wszystkich grup.
* `portfel.json` - Plik generowany automatycznie przez aplikację po użyciu panelu administratora. Przechowuje zaktualizowane stany kont i pozycje na bieżący tydzień. (Uwaga: plik ten nie powinien być edytowany ręcznie).
* `requirements.txt` - Lista zależności środowiskowych.

## Wymagania systemowe i instalacja

Projekt wymaga środowiska Python w wersji 3.8 lub nowszej. 

1. Klonowanie repozytorium:
   ```bash
   git clone [https://github.com/twoja-nazwa/twoje-repozytorium.git](https://github.com/twoja-nazwa/twoje-repozytorium.git)
   cd twoje-repozytorium
   ```

2. Instalacja wymaganych bibliotek:
   ```bash
   pip install -r requirements.txt
   ```

3. Uruchomienie aplikacji lokalnie:
   ```bash
   streamlit run app.py
   ```

## Zależności (requirements.txt)

Przed wdrożeniem na serwer produkcyjny (np. Streamlit Community Cloud), upewnij się, że plik `requirements.txt` zawiera następujące pakiety:
```text
streamlit
yfinance
pandas
plotly
```

## Instrukcja obsługi (Panel Administratora)

Rebalans portfela (zmiana pozycji) jest zablokowana przez większość tygodnia i otwiera się automatycznie na podstawie zegara systemowego (w niedzielę). 

Aby dokonać relokacji:
1. Rozwiń pasek boczny po lewej stronie ekranu.
2. Wprowadź hasło autoryzacyjne.
3. Wybierz grupę docelową z listy rozwijanej.
4. System automatycznie podpowie wypracowany do piątkowego zamknięcia kapitał.
5. Wprowadź nowe zaangażowanie dla instrumentów i kliknij "Zapisz konfigurację". System automatycznie zaktualizuje plik stanowy.

## Zastrzeżenia

Aplikacja ma charakter akademicki/konkursowy. Wykorzystuje darmowe API Yahoo Finance, które może podlegać opóźnieniom lub limitom zapytań (Rate Limiting). System implementuje mechanizm pamięci podręcznej (Cache z TTL = 60s) w celu minimalizacji obciążenia sieciowego.
```
