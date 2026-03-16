# 📈 Terminal Konkursowy LIVE - Grupa 13

Zaawansowana aplikacja webowa stworzona w Pythonie (framework **Streamlit**) na potrzeby uczelnianego konkursu inwestycyjnego. System śledzi wyniki portfela w czasie rzeczywistym, wizualizuje skumulowany zysk i pozwala na bezpieczny, zgodny z regulaminem rebalans portfela co tydzień.

## 🚀 Główne funkcje

* **Wizualizacja LIVE (Interwał H1):** Skumulowany wykres wyników portfela z dynamicznym kolorowaniem (zielony dla zysku, czerwony dla straty) i profesjonalnym efektem "neonowej poświaty" (powered by Plotly).
* **Automatyczne pobieranie danych:** Połączenie z API Yahoo Finance (`yfinance`). Aplikacja sama aktualizuje ceny instrumentów (S&P 500, US10Y Yield, Złoto, EUR/USD) co 60 sekund.
* **Smart Panel Rebalansu:** Ukryty, boczny panel administratora do ustawiania pozycji na nowy tydzień.
* **Strażnik Regulaminu:** Aplikacja automatycznie pilnuje twardych zasad konkursu:
* **Blokada czasowa:** Panel rebalansu otwiera się wyłącznie w niedziele i zamyka punktualnie o 23:00. Przez resztę tygodnia wisi "kłódka".
* **Limit kapitału:** Blokuje możliwość zainwestowania większej ilości kapitału, niż wynosi aktualny stan konta.
* **Minimalny wkład:** Pilnuje zasady minimalnej inwestycji na poziomie 20 j.p.


* **Lokalna Baza Danych:** Automatyczny zapis ustawień do pliku `portfel.json`, dzięki czemu portfel jest odporny na restarty serwera.

## 🛠️ Technologie

* **Python 3.9+**
* **Streamlit** (Frontend / Web Framework)
* **yfinance** (Pobieranie danych rynkowych)
* **Pandas** (Przetwarzanie danych i czyszczenie luk czasowych)
* **Plotly** (Interaktywne wykresy finansowe)

## 📦 Instalacja i uruchomienie lokalne

Jeśli chcesz odpalić ten terminal na swoim komputerze, wykonaj poniższe kroki w terminalu/konsoli:

1. **Pobierz repozytorium:**
```bash
git clone <link-do-twojego-repozytorium>
cd <nazwa-folderu>

```


2. **Zainstaluj wymagane biblioteki:**
Upewnij się, że masz zainstalowanego Pythona, a następnie zainstaluj paczki z pliku `requirements.txt`:
```bash
pip install -r requirements.txt

```


3. **Uruchom aplikację:**
```bash
streamlit run app.py

```


Aplikacja automatycznie otworzy się w Twojej domyślnej przeglądarce pod adresem `http://localhost:8501`.

## 👨‍💻 Instrukcja obsługi (Dla zarządzających portfelem)

1. **Obserwacja w tygodniu:** Od poniedziałku rano do piątku wieczorem aplikacja działa w trybie "Tylko do odczytu". Oglądacie, jak rośnie/spada Wasz kapitał.
2. **Rebalans (Niedziela):**
* Wejdź na stronę aplikacji.
* Rozwiń boczny panel z lewej strony (kliknij ikonę strzałki lub najeżdżając na napis "REBALANS").
* Wpisz kod PIN (domyślnie: `1234`).
* Aplikacja wskaże wypracowany kapitał startowy.
* Wpisz nowe wagi dla instrumentów (Pamiętaj: wartości ujemne dla pozycji SHORT, np. `-50`).
* Kliknij **Zapisz i wyślij formularz**. Wykres zresetuje się i przygotuje do startu w poniedziałek rano.



## 📁 Struktura plików

* `app.py` - Główny silnik aplikacji, logika interfejsu i pobierania danych.
* `requirements.txt` - Lista zależności dla serwerów Streamlit Cloud.
* `portfel.json` - Plik bazy danych przechowujący aktualne pozycje i kapitał bazowy (generuje się automatycznie).

---

*Stworzone z myślą o wygranej. Powodzenia dla Grupy 13!* 🏆
