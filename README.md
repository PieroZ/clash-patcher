# Clash: konfigurator pliku .exe

<img width="961" height="288" alt="Poprawki" src="https://github.com/user-attachments/assets/028c7666-b1b0-4882-9424-75e23c323a4b" />
<img width="902" height="792" alt="KuzniaWarsztatPoziomy" src="https://github.com/user-attachments/assets/797cfc1e-9ace-4ef8-817e-a5b58486003d" />
<img width="902" height="792" alt="SwiatyniaPort" src="https://github.com/user-attachments/assets/862baa32-1171-4fb3-9f31-eb832b57a8b4" />


Narzędzie z interfejsem graficznym (PySide6) do zmiany ustawień zaszytych w pliku wykonywalnym gry
Clash (LONGSOFT), bez ręcznego grzebania w edytorze hex.

Obsługiwane wersje (rozpoznawane po rozmiarze pliku):

| Wersja | Plik | Rozmiar |
|---|---|---|
| DOS, polska (GOG) | `LONGSOFT\CLASH\CLASH.EXE` | 1 481 338 B |
| Windows | `clash95.exe` | 1 232 384 B |

## Co można zmienić

- **Świątynia i port**: jakie jednostki można wylosować (także osobna lista, z której świątynie
  losują w misjach 3 i 7 obu kampanii),
  wszystkie dary świątyń i miejsc kultu (co, z jakim prawdopodobieństwem i z jakim przedmiotem –
  osobno dla obu religii oraz dla gracza i komputera, z możliwością przestawiania kolejności wpisów
  strzałkami) i siła każdego daru (złoto, morale, zmęczenie,
  zdrowie, doświadczenie, liczba jednostek w nowym oddziale).
- **Opisy darów**: treść komunikatu, który gra pokazuje w okienku daru świątyni i miejsca kultu
  (osobno polski i angielski, przycisk „Zmień…” w tabeli darów). Program pokazuje na bieżąco, jak gra
  złamie wiersze tą samą czcionką i szerokością co w grze, ostrzega, gdy tekst wyjdzie za pergamin
  albo na obrazek daru, i pilnuje wspólnego limitu miejsca, bo wszystkie opisy leżą w pliku w jednym
  ciągu, więc dłuższy opis trzeba opłacić skróceniem innego (albo tekstu angielskiego, którego polska
  wersja gry nie pokazuje).
- **Kuźnia, warsztat, poziomy**: które jednostki wymagają kuźni / warsztatu i jaki minimalny poziom zamku.
- **Mury**: koszt (0–255 sztuk złota) i czas (1–255 tur) rozbudowy muru do 2. i 3. poziomu.
- **Punkty akcji**: koszt i wymagane minimum PA przy dzieleniu i łączeniu oddziałów.
- **Walka**: premia za okopanie (oryginalne ×1,25 albo stałe +N).
- **Poprawki**: poprawki błędów gry: blokada exploita z dołączaniem jednostek naziemnych
  do latających stojących nad wodą / kraterem oraz przekręcanie się zmęczenia (dodanie więcej
  niż 27 zmęczenia daje zmęczonym jednostkom zerowe zmęczenie zamiast kary – trafia w to
  oryginalna KSIĘGA PLAG z +50).
- **Kody**: treść 11 kodów (cheatów) wbudowanych w grę.

Przy tytule każdej ramki (i w prawym górnym rogu niektórych zakładek) jest ikona **ⓘ**.
Otwiera okno z całym opisem danego ustawienia: co dokładnie zmienia w grze, a niżej szczegóły
techniczne: offsety w pliku, instrukcje i to, skąd dana informacja pochodzi. Przy świątyni jest
tam np. tabela czterech misji, w których gra losuje z innej listy jednostek.

Dzięki temu samo okno programu zostaje czyste, bo przy polach nie ma ścian szarego tekstu.
Do zmieniania wartości opisy nie są potrzebne, więc nie zaglądaj tam, jeśli wiesz, co ustawiasz.

## Wersje

Aktualny numer wersji jest w `version.py` (widać go też w tytule okna programu), lista zmian
w [CHANGELOG.md](CHANGELOG.md). Gotowy plik `.exe` każdej wersji jest w zakładce *Releases* na GitHubie.

## Uruchomienie

**Najprościej (Windows):** zainstaluj Pythona z https://www.python.org/downloads/ (w instalatorze zaznacz
„Add python.exe to PATH”), pobierz to repozytorium (Code → Download ZIP, rozpakuj) i kliknij dwa razy
`uruchom.bat`. Za pierwszym razem doinstaluje się PySide6 (chwilę to trwa). Plik `CLASH.EXE` można też
przeciągnąć myszką na `uruchom.bat`, a otworzy się od razu.

**Ręcznie:** w **wierszu poleceń Windows** (Start → wpisz `cmd`), nie w oknie Pythona `>>>`:

```
cd ŚCIEŻKA\DO\clash-patcher
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python clash_exe_config.py %SCIEZKA_DO_PLIKU% (np. "C:\Games\Clash\LONGSOFT\CLASH\CLASH.EXE")
```

Ścieżkę do gry można pominąć i otworzyć plik przyciskiem „Otwórz”.

Przed pierwszym zapisem program tworzy kopię `NAZWA.EXE.bak` (przycisk „Przywróć oryginał” ją odtwarza).
Przy otwarciu każde ustawienie jest weryfikowane. Jeśli bajty w pliku nie wyglądają jak w znanej wersji gry,
ustawienie zostaje wyłączone zamiast uszkodzić plik.

## Budowanie pliku .exe

Gotowy `.exe` nie wymaga od użytkownika ani Pythona, ani PySide6. Najnowszy buduje się na GitHubie przy każdej zmianie (zakładka **Actions** → „Build exe” → artefakt `clash-exe-config`), a po wypchnięciu tagu `v*` (np. `v1.0`) trafia dodatkowo do wydania
w **Releases**.

Lokalnie, w **wierszu poleceń Windows**:

```
cd ŚCIEŻKA\DO\clash-patcher
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt -r requirements-build.txt
python build_exe.py
```

Wynik: `dist\clash-exe-config.exe`, jeden plik, bez okna konsoli.

Przydatne opcje: `--onedir` (katalog z plikami zamiast jednego `.exe`, za to szybszy start),
`--console` (zostawia okno konsoli, widać wtedy komunikaty o błędach), `--icon PLIK.ICO`,
`--name NAZWA`. Pełna lista: `python build_exe.py --help`.

## Pliki

| Plik | Opis |
|---|---|
| `uruchom.bat` | uruchamianie dwuklikiem (tworzy venv i instaluje zależności) |
| `clash_exe_config.py` | interfejs graficzny |
| `clash_exe_patches.py` | wszystkie adresy i rodzaje danych (`PROFILES`), odczyt/zapis |
| `CLASH_EXE_CONFIG.md` | tabela adresów, opis poprawek, jak dodać nowe znalezisko |
| `tools/build_nofly_patch.py` | źródło asemblerowe poprawki „naziemne nie dołączają do latających” (`pip install -r requirements-dev.txt`) |
| `build_exe.py` | budowanie `clash-exe-config.exe` z `clash_exe_config.py` (PyInstaller) |
| `.github/workflows/build-exe.yml` | budowanie `.exe` na GitHub Actions przy każdej zmianie |

Repozytorium nie zawiera plików gry (`.exe`, zapisów `.DAT`).
