# Clash – konfigurator pliku .exe

Narzędzie z interfejsem graficznym (PySide6) do zmiany ustawień zaszytych w pliku wykonywalnym gry
Clash (LONGSOFT) – bez ręcznego grzebania w edytorze hex.

Obsługiwane wersje (rozpoznawane po rozmiarze pliku):

| Wersja | Plik | Rozmiar |
|---|---|---|
| DOS, polska (GOG) | `LONGSOFT\CLASH\CLASH.EXE` | 1 481 338 B |
| Windows | `clash95.exe` | 1 232 384 B |

## Co można zmienić

- **Świątynia i port** – jakie jednostki można wylosować (także wariant świątyni z wybranych misji).
- **Kuźnia, warsztat, poziomy** – które jednostki wymagają kuźni / warsztatu i jaki minimalny poziom zamku.
- **Punkty akcji** – koszt i wymagane minimum PA przy dzieleniu i łączeniu oddziałów.
- **Walka** – premia za okopanie (oryginalne ×1,25 albo stałe +N).
- **Poprawki** – poprawki błędów gry, np. blokada exploita z dołączaniem jednostek naziemnych
  do latających stojących nad wodą / kraterem.
- **Kody** – treść 11 kodów (cheatów) wbudowanych w grę.

## Uruchomienie

**Najprościej (Windows):** zainstaluj Pythona z https://www.python.org/downloads/ (w instalatorze zaznacz
„Add python.exe to PATH”), pobierz to repozytorium (Code → Download ZIP, rozpakuj) i kliknij dwa razy
`uruchom.bat`. Za pierwszym razem doinstaluje się PySide6 (chwilę to trwa). Plik `CLASH.EXE` można też
przeciągnąć myszką na `uruchom.bat` – otworzy się od razu.

**Ręcznie:** w **wierszu poleceń Windows** (Start → wpisz `cmd`), nie w oknie Pythona `>>>`:

```
cd ŚCIEŻKA\DO\clash-patcher
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python clash_exe_config.py "C:\Games\Clash\Clash\LONGSOFT\CLASH\CLASH.EXE"
```

Ścieżkę do gry można pominąć i otworzyć plik przyciskiem „Otwórz”.

Przed pierwszym zapisem program tworzy kopię `NAZWA.EXE.bak` (przycisk „Przywróć oryginał” ją odtwarza).
Przy otwarciu każde ustawienie jest weryfikowane – jeśli bajty w pliku nie wyglądają jak w znanej wersji gry,
ustawienie zostaje wyłączone zamiast uszkodzić plik.

## Pliki

| Plik | Opis |
|---|---|
| `uruchom.bat` | uruchamianie dwuklikiem (tworzy venv i instaluje zależności) |
| `clash_exe_config.py` | interfejs graficzny |
| `clash_exe_patches.py` | wszystkie adresy i rodzaje danych (`PROFILES`), odczyt/zapis |
| `CLASH_EXE_CONFIG.md` | tabela adresów, opis poprawek, jak dodać nowe znalezisko |
| `tools/build_nofly_patch.py` | źródło asemblerowe poprawki „naziemne nie dołączają do latających” (`pip install -r requirements-dev.txt`) |

Repozytorium nie zawiera plików gry (`.exe`, zapisów `.DAT`).
