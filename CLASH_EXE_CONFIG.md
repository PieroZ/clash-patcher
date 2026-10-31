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
| Mury | Czas rozbudowy muru do 2. i 3. poziomu (bajty +2 wpisów 1 i 2 tabeli murów) | 0x15FDDE, 0x15FDE2 | szukane po bajtach |
| | Koszt rozbudowy muru do 2. i 3. poziomu (bajty +3 tych samych wpisów) | 0x15FDDF, 0x15FDE3 | szukane po bajtach |
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
- `WallTable(klucz, tytuł, offset | None)` – tabela murów; `None` = program sam jej szuka
  po bajtach rozpoznawczych (zakładka „Mury”),
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

## Mury – jak to działa w grze (DOS, Windows analogicznie)

Mur ma trzy poziomy; gra pokazuje je graczowi jako 1–3 (`b+0x1a5` plus 1), zamek startuje na
poziomie 0, twierdza na 1. Wszystkie dane murów leżą w jednej tabeli pod adresem `0x1339D8`
w pamięci gry (**plik: 0x15FDD8** w wersji DOS) – trzy wpisy po 4 bajty:

| Pole | Rozmiar | Znaczenie |
|---|---|---|
| +0 | u16 | wytrzymałość: mnożnik ×/256 obrażeń **zadawanych murom** (427, 341, 256 – im mniej, tym mocniejszy mur) |
| +2 | u8 | liczba tur rozbudowy **do** tego poziomu |
| +3 | u8 | koszt rozbudowy **do** tego poziomu w sztukach złota |

Oryginalna zawartość: `AB 01 00 00 | 55 01 05 01 | 00 01 0A 01`.

| Operacja | Funkcja | Co robi |
|---|---|---|
| Czy można rozbudować | `Building_CanUpgradeWall` 0x37952 | `poziom < 2` **i** `poziom < technologia−1` **i** licznik `b+0x1ad` == 0 |
| Zlecenie rozbudowy | `Building_UpgradeWall` 0x379d4 | czyta wpis `poziom+1`: jeśli skarbiec ≥ koszt, to `b+0x1ad = tury` i `skarbiec −= koszt` |
| Odliczanie | `Building_WallsTick` 0x36519 | raz na turę właściciela: `b+0x1ad −= 1`, a przy zerze `poziom += 1` |

* Rozbudowa z poziomu L czyta wpis L+1, a poziom jest zawsze < 2, więc gra czyta tylko czas
  i koszt wpisów 1 i 2 – **cztery bajty**. Czasu i kosztu wpisu 0 nie czyta nigdy (nie da się
  „rozbudować do poziomu 0”), dlatego zakładka ich nie pokazuje.
* Poziom 2. wymaga 2., a poziom 3. – 3. poziomu technologicznego zamku.
* Koszt jest czytany jako bajt **bez znaku** i porównywany ze skarbcem też bez znaku, więc cały
  zakres 0–255 działa poprawnie (200 nie zamienia się w liczbę ujemną dodającą złoto).
* Licznik tur musi być ≥ 1. Przy 0 gra pobrałaby złoto, licznik od razu byłby zerowy, mur nigdy by
  się nie podniósł, a „Rozbuduj mury” dalej byłoby aktywne – czyli studnia bez dna. Dlatego pole
  czasu ma minimum 1.
* Tych bajtów nie czyta żadne inne miejsce w kodzie (sprawdzone na deasemblacji), a `Building_UpgradeWall`
  ma tylko dwóch wywołujących: `Castle_MenuUpgradeWalls` 0x39573 i `AI_CastleUpgradeWall` 0x708ac
  (reguła AI `rozbudowa_murow`). Nowe wartości obowiązują więc i gracza, i komputer – komputer nie ma
  tu zniżki, jaką ma na licencje i budynki.
* Menu „Rozbuduj mury” **nie pokazuje ceny** (inaczej niż menu budowy, gdzie podpowiedzi typu
  „400 sztuk zlota” są osobnymi tekstami w pliku), więc po zmianie ceny nigdzie w grze nie zostaje
  stara liczba. Kliknięcie przy zbyt małym skarbcu po prostu nic nie robi, bez komunikatu – tak samo
  jak w oryginale.
* Wytrzymałości (pole +0) program nie zmienia; służą mu za znacznik rozpoznawczy tabeli.
  W wersji Windows adres tabeli nie był sprawdzony na pliku, dlatego `WallTable` dostaje tam
  `offset=None` i szuka jej po bajtach `AB 01 00 00 55 01 ?? ?? 00 01 ?? ??` (w pliku DOS taki wzór
  występuje dokładnie raz). Gdy nie znajdzie albo znajdzie kilka miejsc, ustawienie się wyłącza.

---

## Łączenie i dzielenie – jak to działa w grze (DOS, Windows analogicznie)

„Oddział” w grze to dowolna grupa 1–10 jednostek stojąca na jednym polu – pojedyncza jednostka to oddział
z jedną jednostką. Gra nie rozróżnia „jednostki” i „oddziału”, rozróżnia tylko **rodzaj operacji**:

| Operacja | Funkcja | Minimum PA (sprawdzane) | Koszt PA (odejmowany) |
|---|---|---|---|
| Cały zaznaczony oddział (także 1-osobowy) dołącza do innego | `Unit_AddToGroup` 0x3B2EB | 0x74851 | 0x7485E |
| Część jednostek oddziału przechodzi na **puste** sąsiednie pole | `Unit_MoveFromGroup` 0x3B738 → 0x3B4CE | 0x74A48 | 0x74DAD |
| Część jednostek oddziału przechodzi do **sąsiedniego oddziału** | jw. | 0x74A9F | 0x74DAD |

- Minimum dotyczy najmniejszej liczby PA wśród **przenoszonych** jednostek; jednostki oddziału docelowego
  nie są sprawdzane ani karane.
- Przejście części jednostek do sąsiedniego oddziału to dla gry rozdzielenie – kosztuje 0x74DAD,
  koszt łączenia 0x7485E nie jest wtedy naliczany.
- Wszystkich jednostek oddziału nie da się przenieść przez „rozdzielenie” – wtedy działa łączenie całego oddziału.
- Kara to zwykłe odejmowanie bajtu bez pilnowania zera. Jeśli minimum jest mniejsze niż koszt, jednostka
  z liczbą PA pomiędzy nimi przekręca się na ok. 250 PA i potem przechodzi każde kolejne sprawdzenie.
  (Wyjątek: łączenie w wersji Windows obcina karę do posiadanych PA.)
