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
| | Dary: świątynia – gracz (16 wpisów × 24 B) | 0x16203C | — |
| | Dary: świątynia – komputer (14 wpisów) | 0x16233C | — |
| | Dary: miejsce kultu – gracz (14 wpisów) | 0x1621D4 | — |
| | Dary: miejsce kultu – komputer (12 wpisów) | 0x1624A4 | — |
| | Opisy darów: wspólny obszar tekstów czterech tabel (14 732 B) + wskaźniki wpisów i ich relokacje | 0x142C7A–0x146606 | — |
| | Siła darów: 17 liczb w kodzie (niżej) | 0x94B1F … 0x95499 | — |
| | Port (12 × 4 B) | 0x163E0C, 0x9952B | 0x115DA8, 0x42B0A |
| Kuźnia, warsztat, poziomy | Jednostki wymagające kuźni (bajty, koniec FF) | 0x161F7C | 0x113E80 |
| | Jednostki wymagające warsztatu | 0x161F88 | 0x113E90 |
| | Minimalny poziom: rekord typu jednostki + 0x4C / + 0x4B | 0x15E7D4 + ID×0x58 | 0x110768 + ID×0x58 |
| Mury | Czas rozbudowy muru do 2. i 3. poziomu (bajty +2 wpisów 1 i 2 tabeli murów) | 0x15FDDE, 0x15FDE2 | szukane po bajtach |
| | Koszt rozbudowy muru do 2. i 3. poziomu (bajty +3 tych samych wpisów) | 0x15FDDF, 0x15FDE3 | szukane po bajtach |
| Punkty akcji | Koszt dzielenia (+ 2 warunki minimum + kolor krzyżyka na ikonce jednostki) | 0x74DAD, 0x74A48, 0x74A9F, 0x751F3 | 0x225F2, 0x2239A, 0x223D2, 0x22AC9 |
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
- `GiftTable(klucz, tytuł, offset, przesunięcie_tekstów, czy_gracz)` – tabela losowania darów
  świątyni (zakładka „Świątynia i port”),
- `GiftTexts(klucz, tytuł, [GiftTable, …], (początek, koniec), przesunięcie_tekstów)` – teksty
  tych tabel jako jeden wspólny obszar bajtów; przy zapisie układa je od nowa i poprawia wskaźniki
  razem z wpisami relokacji (klasa pomocnicza `LeFixups`),
- `GiftAmounts(klucz, tytuł, [GiftAmount(...), …])` – zbiór liczb wpisanych w kod, pokazywany
  jako jedna lista; `GiftAmount` dostaje `Instr` (1 bajt) albo `Instr32` (4 bajty ze znakiem),
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

## Dary świątyń i miejsc kultu – jak to działa w grze (tylko DOS)

Armia, która wejdzie na pole świątyni (religia chrześcijańska) albo miejsca kultu (pogańska),
dostaje **jeden wylosowany dar**. Wejście do świątyni obcej religii zawsze kończy się zniszczeniem
armii, a odwiedzona świątynia daje tylko komunikat. Cała obsługa to trzy rzeczy:

| Co | Funkcja | Rola |
|---|---|---|
| Wybór tabeli | `Temple_UnitGetInto` 0x5C135 | po religii (`gracz+0x27`) i po tym, czy gracz jest człowiekiem (`+0x1B`) |
| Losowanie wpisu | `Temple_Random` 0x5BC2C | ważone, z przesunięciem o jeden (niżej) |
| Wykonanie efektu | `Temple_ProcessGift` 0x5BCDB | instrukcja wyboru z 16 przypadkami (numery darów 0–15) |

### Cztery tabele

Wpis ma 24 bajty: `{i32 numer daru, i32 waga, i32 obrazek, 3 × wskaźnik na tekst (PL, EN, DE)}`,
a lista kończy się wpisem z numerem daru `-1`.

| Tabela | Adres w pamięci | Offset w pliku | Wpisów | Suma wag |
|---|---|---|---|---|
| świątynia – gracz | 0x135C3C | **0x16203C** | 16 | 160 |
| świątynia – komputer | 0x135F3C | **0x16233C** | 14 | 140 |
| miejsce kultu – gracz | 0x135DD4 | **0x1621D4** | 14 | 140 |
| miejsce kultu – komputer | 0x1360A4 | **0x1624A4** | 12 | 120 |

Tabele leżą w pliku jedna za drugą, więc **liczby wpisów nie da się zmienić** bez przenoszenia
tabel i dopisywania relokacji. Edytowalne są numer daru, obrazek i waga każdego istniejącego wpisu;
waga 0 praktycznie wyłącza wpis.

Numer daru nie ma nic wspólnego z tekstem wpisu – po zmianie efektu komunikat w grze zostaje stary.
Dlatego ostatnia kolumna tabeli pokazuje tekst, który gra naprawdę wypisze, a przycisk „Zmień…”
pozwala go poprawić (jak – w następnym punkcie).

### Opisy darów (teksty)

Każdy wpis ma trzy wskaźniki na tekst: polski, angielski i trzeci. Gra wybiera je numerem języka,
a polska wersja ma język 0, więc pokazuje tekst polski; trzeci wskaźnik prowadzi w tym pliku zawsze
do tekstu pustego. **Offset tekstu w pliku = wskaźnik
z wpisu + 0x13C400** (loader DOS/4GW dolicza bazę obiektu danych). Kodowanie to Mazovia.

**Wspólny obszar.** Wszystkie 168 wskaźników (56 wpisów × 3) prowadzą w jeden ciągły obszar
**0x142C7A–0x146606**, czyli 14 732 bajty, wypełniony co do bajtu: tekst kończy się zerem, a zaraz
za nim zaczyna się następny. Żadnego tekstu nie da się więc wydłużyć w miejscu. Program traktuje
ten obszar jako pulę i przy zapisie układa go od nowa:

* teksty jeden za drugim, od 0x142C7A, każdy z bajtem zerowym na końcu;
* **takie same teksty zapisywane są raz** – w oryginale powtórzeń jest 56 (te same opisy mają np.
  tabele gracza i komputera), a same puste trzecie teksty to 56 bajtów. Dzięki temu oryginalne
  teksty zajmują po ułożeniu **6 978 z 14 732 bajtów**: na dłuższe opisy jest ponad dwa razy tyle
  miejsca, ile zajmują. Program pokazuje zajętość pod tabelą i w okienku edycji, a zapisu, który
  by się nie zmieścił, nie wykona (błąd zamiast uszkodzonego pliku);
* reszta puli jest zerowana, więc kolejne zapisy tych samych tekstów nie zmieniają już ani bajtu.

**Dlaczego trzeba ruszyć relokacje.** Wskaźnik w pliku to offset wewnątrz obiektu danych, ale
prawdziwy adres wpisuje do pamięci loader DOS/4GW i bierze go **nie z tych bajtów, a z wpisu
relokacji**: `{gdzie, obiekt, offset celu}`. Zmiana samego dworda we wpisie tabeli nic by nie dała –
loader nadpisałby go z powrotem. Program zmienia oba miejsca: dword we wpisie tabeli i 16-bitowy
offset celu w tablicy relokacji. Wszystkie 168 wskaźników mają tam wpis typu 7 (32-bitowy offset)
z 16-bitowym celem, a cała pula leży poniżej 0x10000 obiektu danych, więc rozmiary wpisów
relokacji się nie zmieniają i nic w pliku się nie przesuwa. Przy otwarciu pliku program
sprawdza to wszystko (każdy wskaźnik ma swój wpis relokacji o zgodnym celu, każdy tekst leży w puli,
a w samej puli loader nie wpisuje żadnego adresu) i przy pierwszej niezgodności wyłącza edycję tekstów,
zamiast psuć plik. **Pula nie jest przenoszona ani powiększana** – wyjście poza nią wymagałoby 32-bitowych
celów w relokacjach, czyli przesunięcia całej tablicy relokacji.

**Jak gra rysuje ten tekst.** `TempleWindow` (0x5B9DC) rysuje pergamin z `temple.s32` (klatka 0x16,
329×178 px, od y = 150, i klatka 0x17 obok niej, 311×168 px, od y = 156 – razem x 0–639,
y 150–327), obrazek daru (wszystkie klatki 58×39 px) w (294, 285), czyli x 294–351, y 285–323,
i tekst czcionką 0x11 między x = 0x46 i x = 0x239, od y = 0xD2, z wyrównaniem 6: zawijanie po słowach, każdy wiersz wyśrodkowany (`Text_DrawAligned` 0x208C7). Program liczy to dokładnie tak samo – ma w sobie szerokości klatek tej czcionki – i pokazuje gotowy podgląd wierszy. Stąd ostrzeżenia:

| Liczba wierszy | Co się stanie |
|---|---|
| 1–4 | jak w oryginale (najdłuższy tekst oryginału, MIECZ GŁUPCÓW, ma 226 znaków i 4 wiersze) |
| 5–6 | 5. wiersz zaczyna się na y = 290, a 6. na y = 310, więc przechodzą przez obrazek daru, a szósty wystaje poniżej dolnej krawędzi prawej połowy pergaminu (y 323) |
| 7 i dalsze | gra rysuje je poniżej okienka, a okienko przy zamykaniu odtwarza tylko y 150–327 – resztę widać na mapie, dopóki gra jej nie przerysuje |

Dwie pułapki, których program nie przepuszcza:

* **Znak `%`** – gra podaje tekst (i każdy złamany wiersz osobno) jako **wzorzec do `printf`**
  (`Text_PrintfAligned`), więc `%` byłby potraktowany jak polecenie formatowania: w okienku
  pojawiłaby się przypadkowa liczba albo gra by się wysypała.
* **Znaki bez klatki w tej czcionce** (0xE2–0xFF strony Mazovia) – gra czyta wtedy nagłówek klatki
  spod offsetu 0, dostaje szerokość 0x1000 i łamie wiersz na takim znaku, nic nie rysując.
  Wszystkie polskie litery klatki mają.

Enter w polu edycji wstawia bajt 0x0A, czyli wymusza złamanie wiersza. Słowa dłuższego od wiersza gra nie dzieli: wypisuje pusty wiersz i gubi po jednym znaku, aż słowo się zmieści – program o tym ostrzega.

Obrazek (pole +8) to numer klatki, a zarazem numer dźwięku
(przy `-1` gra bierze dźwięk 7 i nie rysuje obrazka). Lista w programie podaje 0–21 i 24, bo
tylko dla nich w grze są dźwięki; 23 to tło okienka daru (`S32_GetHeight(set, 0x17)`), a 22 nie ma
ani dźwięku, ani znanego zastosowania. Klatka 18 (okuta tarcza z czaszką) istnieje, ale w oryginale
nie jest używana.

### Losowanie i dokładne szanse

```
S = suma wag
r = Random(0, S-1)
acc = 0; i = 0
pętla: acc += waga[i]; jeśli acc >= r → wybrany jest wpis i; i++
```

`r = 0` zawsze trafia w pierwszy wpis, więc **pierwszy wpis ma o jedną szansę więcej**, niż wynika
z jego wagi, a **ostatni o jedną mniej** (`r` nie dochodzi do `S`). Program liczy to dokładnie tym
samym wzorem co gra – liczba szans wpisu *i* to
`max(0, min(suma(0..i), S-1) − suma(0..i-1))`, plus 1 dla wpisu pierwszego – i pokazuje ją
w kolumnie „Szansa”. (Sprawdzone przez porównanie z przejściem wszystkich wartości `r`.)

**Pułapka w misjach 2, 6, 12 i 16.** Dla gracza-człowieka `Temple_UnitGetInto` losuje tam
w pętli `while (dar != 0 && dar != 15)`, czyli do trafienia na „nowy oddział” albo „brak efektu”.
Jeśli w tabeli gracza żaden **osiągalny** wpis (szansa > 0) nie ma daru 0 ani 15, pętla nigdy się
nie skończy i gra się zawiesi. Program traktuje to jako błąd i nie pozwala zapisać takiego pliku.

### Numery darów i liczby wpisane w kod

`Temple_ProcessGift` nie czyta żadnej tabeli wartości – wszystkie liczby są operandami instrukcji.
Te same liczby obowiązują gracza i komputer (oba przechodzą przez tę funkcję) oraz zakopane skarby,
które korzystają z tych samych numerów darów.

| Dar | Efekt | Liczba w kodzie (offset w pliku) | Oryginalnie | Zakres w programie |
|---|---|---|---|---|
| 0 | nowy oddział (losowe jednostki z list powyżej) | `Random(min,max)`: 0x94B24 / 0x94B1F | 1–5 | 1–10 |
| 1 | grom – armia ginie | — | — | — |
| 2 | usunięcie zmęczenia | zmęczenie 0x95162 | −100 | −100…100 |
| 3 | wzrost morale (dar fabularny, tylko skarby) | morale 0x951A9 | +20 | −20…20 |
| 4 | uzdrowienie | zdrowie := 0x9521B | 100 | 0–100 |
| 5 | uzdrowienie i wypoczynek | zdrowie := 0x9528C, zmęczenie := 0x95297 | 100, 0 | 0–100 |
| 6 | doświadczenie (więcej) | liczba nożyków 0x952E9 | 3 | 0–99 |
| 7 | wzrost morale | morale 0x95331 | +2 | −20…20 |
| 8 | doświadczenie (mniej) | liczba nożyków 0x95384 | 2 | 0–99 |
| 9 | złoto | 0x953D5 | 100 | 1–1000 |
| 10 | złoto | 0x953F2 | 200 | 1–1000 |
| 11 | złoto | 0x9542C | 50 | 1–1000 |
| 12 | złoto | 0x9540F | 300 | 1–1000 |
| 13 | spadek morale | morale 0x95440 | −20 | −20…20 |
| 14 | klątwa | morale 0x95487, zmęczenie 0x95499 | −1, +50 | −20…20, −100…100 |
| 15 | brak efektu | — | — | — |

Skąd te zakresy:

* **Morale** mieści się w 0–20 (`SubUnit_AddMorale` 0x2899C dodaje do bajtu ze znakiem i przycina),
  więc ±20 to cały sensowny zakres i nie ma ryzyka przepełnienia.
* **Zmęczenie** mieści się w 0–100 (`SubUnit_AddTiredness` 0x2881D, tak samo). Dodanie więcej niż
  **27** przekręca bajt ze znakiem jednostkom, które są już zmęczone, i przycięcie daje im 0 zamiast
  100 – ten sam błąd ma oryginalna KSIĘGA PLAG z +50. Program o tym ostrzega, ale nie blokuje.
* **Zdrowie i zmęczenie daru 5** są wpisywane wprost w pola jednostki (bez przycinania), więc 0–100.
* **Złoto**: `Gift_Gold` 0x5B8CE tworzy oddział ze złotem po 100 sztuk na jednostkę, a oddział ma
  najwyżej 10 jednostek – stąd maksimum 1000. Wartość 0 dałaby pusty oddział.
* **Nożyki**: to liczba obrotów pętli `Unit_AddExperience`. 3 nożyki = 1 poziom, najwyższy poziom
  to 3, więc 9 wystarcza, żeby jednostka bez doświadczenia od razu doszła na szczyt.
* **Liczba jednostek** daru 0: bufor `Gift_NewTroops` i limit oddziału to 10 jednostek.

---

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
- Krzyżyk na ikonce zaznaczonej jednostki na dolnym pasku (DOS 0x3BDF1, Win 0x4236C7) ma osobne
  porównanie z 4: PA ≥ 4 → szary, mniej → czerwony. Program ustawia je razem z minimum dzielenia.
- Przejście części jednostek do sąsiedniego oddziału to dla gry rozdzielenie – kosztuje 0x74DAD,
  koszt łączenia 0x7485E nie jest wtedy naliczany.
- Wszystkich jednostek oddziału nie da się przenieść przez „rozdzielenie” – wtedy działa łączenie całego oddziału.
- Kara to zwykłe odejmowanie bajtu bez pilnowania zera. Jeśli minimum jest mniejsze niż koszt, jednostka
  z liczbą PA pomiędzy nimi przekręca się na ok. 250 PA i potem przechodzi każde kolejne sprawdzenie.
  (Wyjątek: łączenie w wersji Windows obcina karę do posiadanych PA.)
