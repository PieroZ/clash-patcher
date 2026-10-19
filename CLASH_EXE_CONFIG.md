# Konfigurator pliku .exe gry Clash

```
python clash_exe_config.py "C:\Games\Clash\Clash\LONGSOFT\CLASH\CLASH.EXE"
```

Obsługiwane wersje (rozpoznawane po rozmiarze pliku):

| Wersja | Plik | Rozmiar |
|---|---|---|
| DOS, polska (GOG) | `LONGSOFT\CLASH\CLASH.EXE` | 1 481 338 B |
| Windows | `clash95.exe` | 1 232 384 B |

Przed pierwszym zapisem program robi kopię `NAZWA.EXE.bak` (przycisk „Przywróć oryginał” ją odtwarza).
Przy otwarciu każde znalezisko jest sprawdzane – jeśli bajty pod adresem nie wyglądają jak w grze
(np. inna wersja pliku), to ustawienie jest wyłączane zamiast psuć plik.

## Co można ustawić

| Zakładka | Ustawienie | DOS (offset w pliku) | Windows |
|---|---|---|---|
| Świątynia i port | Lista świątyni (5 × 4 B) + liczba losowanych pozycji | 0x161FFC, 0x94C42 | 0x113F10, 0x3F17E |
| | Świątynia w wybranych misjach (7 × 4 B) | 0x162010, 0x94C14 | 0x113F24, 0x3F14A |
| | Port (12 × 4 B) | 0x163E0C, 0x9952B | 0x115DA8, 0x42B0A |
| Kuźnia, warsztat, poziomy | Jednostki wymagające kuźni (bajty, koniec FF) | 0x161F7C | 0x113E80 |
| | Jednostki wymagające warsztatu | 0x161F88 | 0x113E90 |
| | Minimalny poziom: rekord typu jednostki + 0x4C / + 0x4B | 0x15E7D4 + ID×0x58 | 0x110768 + ID×0x58 |
| Punkty akcji | Koszt dzielenia (+ 2 warunki minimum) | 0x74DAD, 0x74A48, 0x74A9F | 0x225F2, 0x2239A, 0x223D2 |
| | Koszt łączenia (+ warunek minimum) | 0x7485E, 0x74851 | 0x22142, 0x22126 |
| Walka | Okopanie: oryginalnie obrona × 1,25, po zmianie obrona + N (kod `add …, N` + skok) | 0x5FE74, 0x5FF29 | 0x105DC |
| Poprawki | Naziemne nie dołączają do latających nad niedostępnym terenem (nowy kod + 2–3 wstawki) | 0x2D54, 0x74847, 0x74A92, kod 0x13B820 | 0x22076, 0x2211B, 0x223C9, kod 0xE8C20 |
| Kody | 11 kodów (XOR 0x32, stała maks. długość) | od 0x14CCE3 | od 0xFDA3A |

ID jednostek jak na http://clash.y0.pl/adresy-jednostek/ (00 Pospolite ruszenie … 1D Ważka, 1E Smok).

## Jak dodać nowe znalezisko

Wszystkie adresy są w `clash_exe_patches.py` w słowniku `PROFILES` – osobno dla każdej wersji gry.
Wystarczy dopisać wpis jednego z gotowych rodzajów:

- `UnitDwordList(klucz, tytuł, offset, liczba_pozycji, Instr(adres_instrukcji, "BA"))` – lista ID po 4 bajty z losowaniem,
- `UnitByteSet(klucz, tytuł, offset, pojemność_w_bajtach)` – lista ID po 1 bajcie zakończona FF,
- `LinkedValue(klucz, tytuł, [Instr(...), ...], min, max)` – jedna liczba wpisana w kilka instrukcji,
- `TechTable`, `CheatTable` – jak w istniejących wpisach,
- `CodePatch(klucz, tytuł, [(offset, oryginał_hex | None, nowe_hex), ...], description=…)` – poprawka kodu
  włączana jednym przełącznikiem (zakładka „Poprawki”); `None` = w oryginale same zera (wolne miejsce na nowy kod),
- `EntrenchBonus` – podmiana fragmentu kodu: oryginalne bajty + szablon nowego kodu (`NN` = wartość); program rozpoznaje oba stany i umie wrócić do oryginału.

`Instr(adres, "prefiks")` oznacza instrukcję zaczynającą się pod `adres`, której pierwsze bajty muszą
być równe `prefiks`; wartość leży zaraz za nim (np. `BA 04 00 00 00` → prefiks `BA`, wartość `04`).
Nowy rodzaj danych to nowa klasa z metodami `check`, `read`, `write` i zakładka w `clash_exe_config.py`.

## Poprawka „naziemne nie dołączają do latających”

W oryginale łączenie oddziałów (`Unit_AddToGroup`, DOS 0x3B2EB / Win 0x422BE0) i przenoszenie części
jednostek do sąsiedniego oddziału (DOS 0x3B4CE / Win 0x422DC0) sprawdza tylko PA i limit 10 jednostek –
nie sprawdza terenu. Poprawka dokłada procedurę, która liczy koszt wejścia dołączanych jednostek na pole
docelowego oddziału dokładnie tak jak zwykły ruch (profil ruchu oddziału: DOS 0x29E22 / Win 0x413920,
droga albo klasa terenu kafelka). Koszt 0 = teren niedostępny → akcja odrzucona (wstawka zwraca −1 zamiast
minimum PA, więc warunek „PA ≥ N” zawsze zawodzi, niezależnie od ustawionego minimum).
Łączenie podczas rozstawiania armii na starcie scenariusza (parametr `ebx ≠ 0`) jest pomijane.

W wersji DOS kod czyta adresy zmiennych gry z operandów istniejących instrukcji (0x2AC03, 0x2AC31, 0x2AC45),
bo DOS/4GW relokuje dane, a nowy kod nie ma własnych wpisów relokacji. Źródło asemblerowe:
`tools/build_nofly_patch.py` (wymaga `pip install keystone-engine`).
