"""Definicje znalezisk w pliku .exe gry Clash i ich odczyt/zapis.

Kazde znalezisko to obiekt z metodami:
    read(data)        -> wartosc (struktura Pythona)
    write(data, val)  -> zapisuje wartosc do bytearray
    check(data)       -> None gdy bajty pod adresem wygladaja poprawnie, inaczej opis bledu

Nowe znalezisko = nowy wpis w PROFILES (ewentualnie nowa klasa, jesli to nowy rodzaj danych).
Wszystkie adresy to offsety w pliku (te same, ktore pokazuje HxD).
"""
import struct

# ---------------------------------------------------------------- jednostki
UNIT_NAMES = [
    "Pospolite ruszenie", "Lekka piechota", "Ciężka piechota", "Pikinier", "Halabardnik",
    "Lekka jazda", "Ciężka jazda", "Rycerstwo", "Dragon", "Łucznik",
    "Kusznik", "Muszkieter", "Katapulta", "Taran", "Armata",
    "Leśnik", "Góral", "Budowniczy", "Czerw", "Słoń",
    "Cyklop", "Troll", "Skorpion", "Szkielet", "Mag",
    "Duch", "Orzeł", "Pegaz", "Skrzydlak", "Ważka",
    "Smok",
]
UNIT_COUNT = len(UNIT_NAMES)          # 0x00..0x1E - jednostki bojowe


def unit_label(uid):
    if 0 <= uid < UNIT_COUNT:
        return f"{uid:02X} – {UNIT_NAMES[uid]}"
    return f"{uid:02X} – ?"


# ---------------------------------------------------------------- teksty gry (Mazovia)
# Bajty 0x80-0xFF strony kodowej Mazovia.
MAZOVIA_HIGH = (
    "ÇüéâäàąçêëèïîćÄĄ"   # 0x80
    "ĘęłôöĆûùŚÖÜ¢Ł¥śƒ"   # 0x90
    "ŹŻóÓńŃźż¿⌐¬½¼¡«»"   # 0xA0
    "░▒▓│┤╡╢╖╕╣║╗╝╜╛┐"   # 0xB0
    "└┴┬├─┼╞╟╚╔╩╦╠═╬╧"   # 0xC0
    "╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀"   # 0xD0
    "αßΓπΣσµτΦΘΩδ∞φε∩"   # 0xE0
    "≡±≥≤⌠⌡÷≈°∙·√ⁿ²■ "   # 0xF0
)


def mazovia_text(data, offset, limit=400):
    """Tekst gry (kodowanie Mazovia, zakonczony zerem) spod offsetu w pliku."""
    if not 0 <= offset < len(data):
        return ""
    out = []
    for i in range(offset, min(offset + limit, len(data))):
        b = data[i]
        if b == 0:
            break
        out.append(chr(b) if b < 0x80 else MAZOVIA_HIGH[b - 0x80])
    return "".join(out)


# ---------------------------------------------------------------- dary swiatyn
# Numer daru = przypadek instrukcji wyboru w Temple_ProcessGift (0x5BCDB), 0..15.
# Opis liczy sie z aktualnych wartosci w kodzie, bo one sa edytowalne.
def _knives(n):
    if n == 1:
        return "1 nożyk"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} nożyki"
    return f"{n} nożyków"


def _signed(n):
    return f"{n:+d}"


GIFT_EFFECTS = {
    0:  ("nowy oddział", lambda a: f"{a['troops_min']}–{a['troops_max']} losowych jednostek "
                                   f"dołącza jako nowa armia"),
    1:  ("grom z jasnego nieba", lambda a: "armia ginie"),
    2:  ("usunięcie zmęczenia", lambda a: f"zmęczenie {_signed(a['tired2'])}"),
    3:  ("wzrost morale (dar fabularny)", lambda a: f"morale {_signed(a['morale3'])}"),
    4:  ("uzdrowienie", lambda a: f"zdrowie := {a['health4']}"),
    5:  ("uzdrowienie i wypoczynek", lambda a: f"zdrowie := {a['health5']}, zmęczenie := {a['tired5']}"),
    6:  ("doświadczenie (więcej)", lambda a: _knives(a['exp6'])),
    7:  ("wzrost morale", lambda a: f"morale {_signed(a['morale7'])}"),
    8:  ("doświadczenie (mniej)", lambda a: _knives(a['exp8'])),
    9:  ("złoto", lambda a: f"{a['gold9']} szt. złota"),
    10: ("złoto", lambda a: f"{a['gold10']} szt. złota"),
    11: ("złoto", lambda a: f"{a['gold11']} szt. złota"),
    12: ("złoto", lambda a: f"{a['gold12']} szt. złota"),
    13: ("spadek morale", lambda a: f"morale {_signed(a['morale13'])}"),
    14: ("klątwa", lambda a: f"morale {_signed(a['morale14'])}, zmęczenie {_signed(a['tired14'])}"),
    15: ("brak efektu", lambda a: "nic się nie dzieje"),
}
GIFT_COUNT = len(GIFT_EFFECTS)

# Dary, ktore gra przyjmuje w misjach 2, 6, 12 i 16 dla gracza: Temple_UnitGetInto losuje tam
# w petli, dopoki nie trafi na dar 0 albo 15. Tabela gracza bez takiego osiagalnego wpisu
# zawiesilaby gre w tych misjach.
GIFT_REROLL_OK = (0, 15)


def gift_label(gid, amounts=None):
    name, describe = GIFT_EFFECTS.get(gid, ("?", lambda a: ""))
    if amounts:
        try:
            desc = describe(amounts)
        except KeyError:
            desc = ""
    else:
        desc = ""
    return f"{gid:02d} – {name}" + (f" ({desc})" if desc else "")


# Obrazek z temple.s32 (jednoczesnie numer dzwieku sfx\artefakt\N.wav, przy -1 gra bierze 7).
# Pominiete 22 i 23: nie maja dzwieku, a 23 to tlo okna daru (S32_GetHeight(set, 0x17)).
ARTEFACT_NAMES = {
    -1: "(bez obrazka – szczera modlitwa)",
    0: "(grom z jasnego nieba / gniew bogów)",
    1: "(nowy oddział)",
    2: "pierścień zawinięty w chustę",
    3: "medalion Tureoka",
    4: "kielich ze świętym nektarem",
    5: "RĘKAWICA SIŁY",
    6: "MIECZ PALLADYNÓW",
    7: "KSIĘGA WYZNAŃ",
    8: "HEŁM ZDOBYWCÓW",
    9: "ZŁOTY TOPÓR",
    10: "TARCZA TREGÓW / ORĘŻ TREGÓW",
    11: "CUDOWNE CIŻEMKI",
    12: "KLEPSYDRA",
    13: "mieszek diamentów",
    14: "diament",
    15: "szkatuła z kosztownościami / mieszek monet",
    16: "szkatuła / zbutwiała skrzynia",
    17: "szczątki pradawnego władcy",
    18: "okuta tarcza z czaszką (w oryginale nieużywana)",
    19: "CZARNY DIAMENT",
    20: "MIECZ GŁUPCÓW",
    21: "KSIĘGA PLAG",
    24: "magiczny diament Dahar'khu / Xye",
}


def artefact_label(sid):
    return f"{sid:>2} – {ARTEFACT_NAMES.get(sid, '?')}"


# ---------------------------------------------------------------- rodzaje danych
class Instr:
    """Wartosc natychmiastowa w instrukcji maszynowej (np. 'BA 04 00 00 00' = mov edx,4).
    `at` - offset poczatku instrukcji, `prefix` - oczekiwane bajty kodu operacji,
    wartosc lezy zaraz za prefiksem (1 bajt)."""

    def __init__(self, at, prefix):
        self.at = at
        self.prefix = bytes.fromhex(prefix)

    @property
    def value_offset(self):
        return self.at + len(self.prefix)

    def check(self, data):
        got = bytes(data[self.at:self.at + len(self.prefix)])
        if got != self.prefix:
            return f"0x{self.at:X}: oczekiwano {self.prefix.hex(' ').upper()}, jest {got.hex(' ').upper()}"
        return None

    def read(self, data):
        return data[self.value_offset]

    def write(self, data, v):
        data[self.value_offset] = v & 0xFF


class Instr32:
    """Wartosc 32-bitowa ze znakiem w instrukcji (np. 'BA 9C FF FF FF' = mov edx,-100).
    Jak Instr, ale wartosc zajmuje 4 bajty - potrzebne przy liczbach ujemnych i wiekszych od 255."""

    def __init__(self, at, prefix):
        self.at = at
        self.prefix = bytes.fromhex(prefix)

    @property
    def value_offset(self):
        return self.at + len(self.prefix)

    def check(self, data):
        got = bytes(data[self.at:self.at + len(self.prefix)])
        if got != self.prefix:
            return f"0x{self.at:X}: oczekiwano {self.prefix.hex(' ').upper()}, jest {got.hex(' ').upper()}"
        return None

    def read(self, data):
        return struct.unpack_from("<i", data, self.value_offset)[0]

    def write(self, data, v):
        struct.pack_into("<i", data, self.value_offset, int(v))


class UnitDwordList:
    """Tablica ID jednostek po 4 bajty (jak w swiatyni / porcie) + liczba losowanych pozycji
    zapisana w kodzie jako 'mov edx, N-1'."""
    kind = "dword_list"

    def __init__(self, key, title, offset, size, count_instr, note="", expected=None):
        self.key, self.title, self.note = key, title, note
        self.offset, self.size, self.count_instr = offset, size, count_instr
        self.expected = expected   # oryginalne wartosci (do kontroli i przywracania)

    def check(self, data):
        err = self.count_instr.check(data) if self.count_instr else None
        if err:
            return err
        for i in range(self.size):
            v = struct.unpack_from("<I", data, self.offset + 4 * i)[0]
            if v >= UNIT_COUNT:
                return f"0x{self.offset + 4 * i:X}: wartość {v} nie jest ID jednostki"
        return None

    def read(self, data):
        units = [struct.unpack_from("<I", data, self.offset + 4 * i)[0] for i in range(self.size)]
        active = self.count_instr.read(data) + 1 if self.count_instr else self.size
        return {"units": units, "active": active}

    def write(self, data, val):
        for i, u in enumerate(val["units"][:self.size]):
            struct.pack_into("<I", data, self.offset + 4 * i, u)
        if self.count_instr:
            active = max(1, min(self.size, val["active"]))
            self.count_instr.write(data, active - 1)


class UnitByteSet:
    """Lista ID jednostek po 1 bajcie zakonczona 0xFF (kuznia / warsztat).
    `capacity` - liczba bajtow, ktore mozna zajac lacznie z 0xFF."""
    kind = "byte_set"

    def __init__(self, key, title, offset, capacity, note=""):
        self.key, self.title, self.note = key, title, note
        self.offset, self.capacity = offset, capacity

    @property
    def max_units(self):
        return self.capacity - 1

    def check(self, data):
        chunk = bytes(data[self.offset:self.offset + self.capacity])
        if 0xFF not in chunk:
            return f"0x{self.offset:X}: brak znacznika końca listy (FF)"
        for b in chunk[:chunk.index(0xFF)]:
            if b >= UNIT_COUNT:
                return f"0x{self.offset:X}: bajt {b:02X} nie jest ID jednostki"
        return None

    def read(self, data):
        out = []
        for i in range(self.capacity):
            b = data[self.offset + i]
            if b == 0xFF:
                break
            out.append(b)
        return out

    def write(self, data, units):
        units = list(dict.fromkeys(units))[:self.max_units]
        buf = bytes(units) + b"\xFF"
        buf += b"\x00" * (self.capacity - len(buf))
        data[self.offset:self.offset + self.capacity] = buf


class LinkedValue:
    """Jedna liczba zapisana w kilku instrukcjach naraz (np. koszt PA i warunek 'ma co najmniej PA')."""
    kind = "linked_value"

    def __init__(self, key, title, instrs, lo, hi, note=""):
        self.key, self.title, self.note = key, title, note
        self.instrs, self.lo, self.hi = instrs, lo, hi

    def check(self, data):
        for ins in self.instrs:
            err = ins.check(data)
            if err:
                return err
        return None

    def read(self, data):
        return self.instrs[0].read(data)

    def write(self, data, v):
        for ins in self.instrs:
            ins.write(data, v)


class CostWithMinimum:
    """Koszt (odejmowana liczba) + wymagane minimum (warunki 'cmp eax, N').
    `clamped` - czy gra sama pilnuje, zeby nie zejsc ponizej zera. Tylko laczenie w wersji Windows
    (0x410130 obcina kare do PA jednostki); w DOS (0x25B8C) i przy dzieleniu jest zwykle 'sub byte',
    wiec PA mniejsze od kosztu przekreca sie na ok. 250."""
    kind = "cost_min"

    def __init__(self, key, title, cost, minimums, clamped, lo=0, hi=100, note=""):
        self.key, self.title, self.note = key, title, note
        self.cost, self.minimums, self.clamped = cost, minimums, clamped
        self.lo, self.hi = lo, hi

    @property
    def instrs(self):
        return [self.cost] + self.minimums

    def check(self, data):
        for ins in self.instrs:
            err = ins.check(data)
            if err:
                return err
        return None

    def read(self, data):
        return {"cost": self.cost.read(data), "min": self.minimums[0].read(data)}

    def write(self, data, val):
        self.cost.write(data, val["cost"])
        for ins in self.minimums:
            ins.write(data, val["min"])


class EntrenchBonus:
    """Premia do obrony za okopanie (bit 1 bajtu +0x16 jednostki).

    Oryginal: obrona = obrona * 320 / 256 (x1,25 w dol) -> 1-3: +0, 4-7: +1, 8-11: +2, 12-15: +3.
    Wariant:  obrona = obrona + N - w miejscu mnozenia wpisujemy 'add ..., N' i skok za stary kod.
    sites: lista (offset, oryginalne_bajty_hex, szablon_hex z 'NN' w miejscu N)."""
    kind = "entrench"

    def __init__(self, key, title, sites, note=""):
        self.key, self.title, self.note = key, title, note
        self.sites = [(off, bytes.fromhex(orig), tpl) for off, orig, tpl in sites]

    @staticmethod
    def _build(tpl, n):
        return bytes.fromhex(tpl.replace("NN", f"{n & 0xFF:02X}"))

    def _site_state(self, data, off, orig, tpl):
        cur = bytes(data[off:off + len(orig)])
        if cur == orig:
            return ("orig", None)
        probe = self._build(tpl, 0)
        nn = tpl.replace(" ", "").index("NN") // 2
        if cur[:nn] == probe[:nn] and cur[nn + 1:len(probe)] == probe[nn + 1:]:
            return ("fixed", cur[nn])
        return None

    def check(self, data):
        states = [self._site_state(data, *s) for s in self.sites]
        if any(s is None for s in states):
            bad = self.sites[states.index(None)][0]
            return f"0x{bad:X}: kod nie wygląda ani jak oryginał, ani jak znana poprawka"
        if len(set(states)) > 1:
            return "miejsca liczenia okopania mają różne ustawienia"
        return None

    def read(self, data):
        mode, n = self._site_state(data, *self.sites[0])
        return {"mode": mode, "n": n if n is not None else 1}

    def write(self, data, val):
        for off, orig, tpl in self.sites:
            if val["mode"] == "orig":
                data[off:off + len(orig)] = orig
            else:
                patch = self._build(tpl, max(0, min(15, val["n"])))
                data[off:off + len(orig)] = orig          # najpierw czysty stan
                data[off:off + len(patch)] = patch

    @staticmethod
    def bonus(defense, val):
        if val["mode"] == "orig":
            return defense * 320 // 256 - defense
        return val["n"]


class TechTable:
    """Minimalny poziom zaawansowania do produkcji - 2 bajty w rekordzie typu jednostki.
    rekord = base + typ * stride; bajt +off_castle (budynek typu 2), +off_other (pozostale)."""
    kind = "tech_table"

    def __init__(self, key, title, base, stride=0x58, off_type2=0x4B, off_other=0x4C, note=""):
        self.key, self.title, self.note = key, title, note
        self.base, self.stride = base, stride
        self.off_type2, self.off_other = off_type2, off_other

    def addr(self, uid, type2):
        return self.base + uid * self.stride + (self.off_type2 if type2 else self.off_other)

    def check(self, data):
        for uid in range(UNIT_COUNT):
            for t2 in (True, False):
                if data[self.addr(uid, t2)] > 7:
                    return f"0x{self.addr(uid, t2):X}: wartość spoza zakresu poziomów"
        return None

    def read(self, data):
        return {uid: (data[self.addr(uid, False)], data[self.addr(uid, True)]) for uid in range(UNIT_COUNT)}

    def write(self, data, val):
        for uid, (other, type2) in val.items():
            data[self.addr(uid, False)] = other & 0xFF
            data[self.addr(uid, True)] = type2 & 0xFF


class GiftTable:
    """Jedna z czterech tabel losowania darow swiatyni / miejsca kultu.

    Wpis ma 24 bajty: {i32 numer daru, i32 waga, i32 obrazek, 3 wskazniki na tekst (PL, EN, DE)}.
    Lista konczy sie wpisem, ktorego numer daru to -1. Cztery tabele leza w pliku jedna za druga,
    wiec liczby wpisow nie da sie zmienic bez przenoszenia tabel - edytowalne sa numer daru,
    waga i obrazek kazdego istniejacego wpisu.

    Tabele wybiera Temple_UnitGetInto (0x5C135) po religii gracza i po tym, czy jest czlowiekiem.
    Losowanie: Temple_Random (0x5BC2C) sumuje wagi (S), bierze r = Random(0, S-1) i wybiera
    pierwszy wpis, dla ktorego suma wag do niego wlacznie jest >= r. Dlatego r = 0 zawsze trafia
    w pierwszy wpis (ma o jedna szanse wiecej, niz wynika z wagi), a ostatni wpis traci jedna
    szanse - metoda `chances` liczy to dokladnie tak samo jak gra.

    Tekstow nie zmieniamy: kazdy wpis ma wlasne napisy o stalej dlugosci, a numer daru nie ma
    z nimi nic wspolnego, wiec po zmianie efektu komunikat w grze zostaje stary."""
    kind = "gift_table"
    STRIDE = 24
    MAX_ENTRIES = 32
    MAX_WEIGHT = 999
    MIN_SPRITE, MAX_SPRITE = -1, 63

    def __init__(self, key, title, offset, text_delta, human, note=""):
        self.key, self.title, self.note = key, title, note
        self.offset, self.text_delta = offset, text_delta
        self.human = human     # czy to tabela gracza (dotyczy jej przelosowanie w misjach 2/6/12/16)

    def entry_offset(self, i):
        return self.offset + i * self.STRIDE

    def count(self, data):
        """Liczba wpisow przed znacznikiem konca (-1)."""
        n = 0
        while n <= self.MAX_ENTRIES:
            off = self.entry_offset(n)
            if off + 4 > len(data) or struct.unpack_from("<i", data, off)[0] == -1:
                break
            n += 1
        return n

    def check(self, data):
        n = 0
        while True:
            off = self.entry_offset(n)
            if n > self.MAX_ENTRIES:
                return f"0x{self.offset:X}: brak końca listy (-1) w pierwszych {self.MAX_ENTRIES} wpisach"
            if off + self.STRIDE > len(data):
                return f"0x{self.offset:X}: tabela wychodzi za koniec pliku"
            gift, weight, sprite = struct.unpack_from("<iii", data, off)
            if gift == -1:
                break
            if not 0 <= gift < GIFT_COUNT:
                return f"0x{off:X}: {gift} nie jest numerem daru (0–{GIFT_COUNT - 1})"
            if not 0 <= weight <= self.MAX_WEIGHT:
                return f"0x{off + 4:X}: waga {weight} poza zakresem 0–{self.MAX_WEIGHT}"
            if not self.MIN_SPRITE <= sprite <= self.MAX_SPRITE:
                return f"0x{off + 8:X}: obrazek {sprite} poza zakresem " \
                       f"{self.MIN_SPRITE}–{self.MAX_SPRITE}"
            n += 1
        if n == 0:
            return f"0x{self.offset:X}: tabela jest pusta"
        return None

    def texts(self, data, i):
        """Trzy teksty wpisu (polski, angielski, niemiecki)."""
        off = self.entry_offset(i) + 12
        out = []
        for k in range(3):
            ptr = struct.unpack_from("<I", data, off + 4 * k)[0]
            out.append(mazovia_text(data, ptr + self.text_delta) if ptr else "")
        return out

    def read(self, data):
        entries = []
        for i in range(self.count(data)):
            gift, weight, sprite = struct.unpack_from("<iii", data, self.entry_offset(i))
            entries.append({"gift": gift, "weight": weight, "sprite": sprite,
                            "texts": self.texts(data, i)})
        return entries

    def write(self, data, entries):
        for i in range(min(len(entries), self.count(data))):
            e = entries[i]
            struct.pack_into(
                "<iii", data, self.entry_offset(i),
                max(0, min(GIFT_COUNT - 1, e["gift"])),
                max(0, min(self.MAX_WEIGHT, e["weight"])),
                max(self.MIN_SPRITE, min(self.MAX_SPRITE, e["sprite"])))

    @staticmethod
    def chances(weights):
        """Ile z S losowan trafia w kazdy wpis - dokladnie jak w Temple_Random.

        Wpis i jest wybrany dla r = 0 (zawsze wpis 0) oraz dla
        suma(0..i-1) < r <= suma(0..i), przy r z zakresu 0..S-1."""
        total = sum(weights)
        out, acc = [], 0
        for w in weights:
            out.append(max(0, min(acc + w, total - 1) - acc))
            acc += w
        if out:
            out[0] += 1
        return out


class GiftAmount:
    """Jedna liczba wpisana wprost w kod obslugi darow (Temple_ProcessGift / Gift_NewTroops)."""

    def __init__(self, key, gift, label, instr, lo, hi, unit="", note=""):
        self.key, self.gift, self.label = key, gift, label
        self.instr, self.lo, self.hi = instr, lo, hi
        self.unit, self.note = unit, note


class GiftAmounts:
    """Sila darow: liczby, ktore gra ma wpisane w kodzie.

    Gra nie trzyma ich w zadnej tabeli - sa to operandy instrukcji w Temple_ProcessGift
    (0x5BCDB, instrukcja wyboru z 16 przypadkami) i w Gift_NewTroops (0x5B6FF, Random(1,5)).
    Te same liczby obowiazuja gracza i komputer, bo oba przechodza przez te funkcje; dotycza tez
    zakopanych skarbow, ktore korzystaja z tych samych numerow darow."""
    kind = "gift_amounts"
    # SubUnit_AddTiredness (0x2881D) dodaje do bajtu ze znakiem i dopiero potem przycina do 0..100,
    # wiec dodanie wiecej niz 27 przekreca bajt jednostkom o duzym zmeczeniu i zeruje im zmeczenie.
    TIREDNESS_SAFE_ADD = 27

    def __init__(self, key, title, amounts, note=""):
        self.key, self.title, self.note = key, title, note
        self.amounts = amounts

    def by_gift(self, gift):
        return [a for a in self.amounts if a.gift == gift]

    def get(self, key):
        for a in self.amounts:
            if a.key == key:
                return a
        return None

    def check(self, data):
        for a in self.amounts:
            err = a.instr.check(data)
            if err:
                return f"{a.key}: {err}"
        return None

    def read(self, data):
        return {a.key: a.instr.read(data) for a in self.amounts}

    def write(self, data, val):
        for a in self.amounts:
            if a.key in val:
                a.instr.write(data, max(a.lo, min(a.hi, val[a.key])))


class WallTable:
    """Tabela murow (0x1339D8 w pamiesci gry) - 3 wpisy po 4 bajty:
    {u16 wytrzymalosc x256, u8 tury rozbudowy, u8 koszt rozbudowy}.

    Building_UpgradeWall (0x379D4) przy rozbudowie z poziomu L czyta wpis L+1, a poziom muru
    jest zawsze < 2, wiec gra czyta tylko tury i koszt wpisow 1 i 2 (bajty +0x06/+0x07 i
    +0x0A/+0x0B tabeli). Tury i koszt wpisu 0 nie sa czytane nigdy - nie da sie "rozbudowac
    do poziomu 0". Poza ta jedna funkcja zadne inne miejsce w kodzie nie czyta tych bajtow,
    a menu "Rozbuduj mury" (inaczej niz menu budowy) nie pokazuje ceny, wiec nie ma tekstu,
    ktory trzeba by zmieniac razem z liczbami.

    Koszt jest odczytywany jako bajt bez znaku i porownywany ze skarbcem zamku rowniez bez
    znaku, wiec caly zakres 0-255 dziala poprawnie. Licznik tur (budynek +0x1AD) Building_WallsTick
    (0x36519) zmniejsza o 1 na poczatku kazdej tury i podnosi poziom muru, gdy dojdzie do zera -
    dlatego 0 tur nie ma sensu (zloto pobrane, licznik nigdy nie wystartuje).

    Pole wytrzymalosci (427, 341, 256 - mnoznik obrazen zadawanych murom w bitwie) nie jest
    zmieniane; sluzy za znacznik rozpoznawczy tabeli."""
    kind = "wall_table"
    LEVELS = 3
    STRIDE = 4
    # oryginal: AB 01 00 00 | 55 01 05 01 | 00 01 0A 01
    # stale: trzy wytrzymalosci i zerowe tury/koszt wpisu 0; zmienne: tury i koszt wpisow 1 i 2
    SIG_HEAD = bytes.fromhex("AB010000" "5501")   # caly wpis 0 + wytrzymalosc wpisu 1
    SIG_TAIL_AT = 8
    SIG_TAIL = bytes.fromhex("0001")              # wytrzymalosc wpisu 2
    MIN_TURNS, MAX_TURNS = 1, 255
    MIN_COST, MAX_COST = 0, 255
    # wymagany poziom technologiczny zamku (Building_CanUpgradeWall: poziom muru < technologia - 1)
    TECH_NEEDED = {1: 2, 2: 3}

    def __init__(self, key, title, offset=None, note=""):
        self.key, self.title, self.note = key, title, note
        self.offset = offset       # None = szukaj tabeli po bajtach rozpoznawczych

    @property
    def size(self):
        return self.LEVELS * self.STRIDE

    def turns_offset(self, base, level):
        return base + level * self.STRIDE + 2

    def cost_offset(self, base, level):
        return base + level * self.STRIDE + 3

    def _fits(self, data, off):
        tail = off + self.SIG_TAIL_AT
        return (0 <= off and off + self.size <= len(data)
                and bytes(data[off:off + len(self.SIG_HEAD)]) == self.SIG_HEAD
                and bytes(data[tail:tail + len(self.SIG_TAIL)]) == self.SIG_TAIL)

    def _scan(self, data):
        found, i = [], data.find(self.SIG_HEAD)
        while i >= 0:
            if self._fits(data, i):
                found.append(i)
            i = data.find(self.SIG_HEAD, i + 1)
        return found

    def locate(self, data):
        """Offset tabeli w pliku albo None, gdy jej tam nie ma."""
        if self.offset is not None:
            return self.offset if self._fits(data, self.offset) else None
        found = self._scan(data)
        return found[0] if len(found) == 1 else None

    def check(self, data):
        if self.offset is not None:
            if not self._fits(data, self.offset):
                got = bytes(data[self.offset:self.offset + self.size]).hex(" ").upper()
                return f"0x{self.offset:X}: tabela murów nie wygląda jak w grze (jest {got})"
            return None
        found = self._scan(data)
        if not found:
            return "nie znaleziono tabeli murów (AB 01 00 00 55 01 .. .. 00 01 .. ..)"
        if len(found) > 1:
            return "bajty tabeli murów pasują do kilku miejsc: " + ", ".join(f"0x{o:X}" for o in found)
        return None

    def read(self, data):
        off = self.locate(data)
        val = {"offset": off, "strength": [], "turns": [], "cost": []}
        for lvl in range(self.LEVELS):
            val["strength"].append(struct.unpack_from("<H", data, off + lvl * self.STRIDE)[0])
            val["turns"].append(data[self.turns_offset(off, lvl)])
            val["cost"].append(data[self.cost_offset(off, lvl)])
        return val

    def write(self, data, val):
        off = self.locate(data)
        if off is None:
            return
        for lvl in range(1, self.LEVELS):      # wpis 0 nie jest przez gre czytany
            data[self.turns_offset(off, lvl)] = max(self.MIN_TURNS, min(self.MAX_TURNS, val["turns"][lvl]))
            data[self.cost_offset(off, lvl)] = max(self.MIN_COST, min(self.MAX_COST, val["cost"][lvl]))


# znaki, ktore gra potrafi odczytac z klawiatury podczas wpisywania kodu
CHEAT_CHARS = set("qwertyuiopasdfghjkl;'zxcvbnm,.1234567890-= ")


class CheatTable:
    """Kody - tekst XOR 0x32, kazdy w stalym miejscu o stalej maks. dlugosci."""
    kind = "cheats"
    XOR = 0x32

    def __init__(self, key, title, entries, note=""):
        self.key, self.title, self.note = key, title, note
        self.entries = entries     # lista (offset, maks_dlugosc, opis)

    def check(self, data):
        for off, ln, _ in self.entries:
            raw = bytes(data[off:off + ln + 1])
            if raw[-1] != 0:
                return f"0x{off:X}: brak zera kończącego kod"
            txt = bytes(c ^ self.XOR for c in raw[:-1]).rstrip(b"\x32")
            if not all(chr(c) in CHEAT_CHARS for c in txt):
                return f"0x{off:X}: nie wygląda na zakodowany kod"
        return None

    def read(self, data):
        out = []
        for off, ln, _ in self.entries:
            raw = bytes(data[off:off + ln])
            raw = raw.split(b"\x00", 1)[0]
            out.append(bytes(c ^ self.XOR for c in raw).decode("latin-1"))
        return out

    def write(self, data, codes):
        for (off, ln, _), code in zip(self.entries, codes):
            code = code.lower()[:ln]
            enc = bytes(ord(c) ^ self.XOR for c in code)
            data[off:off + ln + 1] = enc + b"\x00" * (ln + 1 - len(enc))


CHEAT_INFO = [
    "Zamienia jednostki zaznaczonego oddziału w armaty",
    "Odkrywa całą mapę",
    "Ustawia bity statusu jednostek oddziału (prawdopodobnie doświadczenie)",
    "Zamienia jednostki zaznaczonego oddziału w pegazy",
    "Pokazuje zdjęcie autorów (team1.gfx)",
    "Ustawia jednej ze statystyk jednostek oddziału 100 (prawdopodobnie HP lub energia)",
    "Pułapka: komunikat „hehe, no bonus” i wyjście z gry",
    "Ustawia graczowi i wszystkim jego zamkom poziom 3",
    "Niszczy oddział lub budynek pod kursorem",
    "Przenosi zaznaczony oddział pod kursor",
    "Wygrywa bieżącą misję",
]


class CodePatch:
    """Poprawka kodu wlaczana/wylaczana jednym przelacznikiem.

    sites: lista (offset, oryginalne_bajty_hex | None, nowe_bajty_hex).
    None = w oryginale same zera (wolne miejsce na koncu sekcji kodu, gdzie trafia nowy kod).
    Kazde miejsce musi miec albo oryginalne, albo nowe bajty - wszystkie w tym samym stanie."""
    kind = "codepatch"

    def __init__(self, key, title, sites, description="", note=""):
        self.key, self.title, self.description, self.note = key, title, description, note
        self.sites = []
        for off, orig, new in sites:
            new = bytes.fromhex(new)
            orig = bytes(len(new)) if orig is None else bytes.fromhex(orig)
            assert len(orig) == len(new), hex(off)
            self.sites.append((off, orig, new))

    def _states(self, data):
        out = []
        for off, orig, new in self.sites:
            cur = bytes(data[off:off + len(orig)])
            out.append("orig" if cur == orig else "new" if cur == new else None)
        return out

    def check(self, data):
        st = self._states(data)
        if None in st:
            return f"0x{self.sites[st.index(None)][0]:X}: bajty nie wyglądają ani jak oryginał, ani jak poprawka"
        if len(set(st)) > 1:
            return "poprawka jest wgrana tylko częściowo"
        return None

    def read(self, data):
        return self._states(data)[0] == "new"

    def write(self, data, on):
        for off, orig, new in self.sites:
            data[off:off + len(orig)] = new if on else orig


def _cheats(start_offsets_lengths):
    return [(off, ln, info) for (off, ln), info in zip(start_offsets_lengths, CHEAT_INFO)]


# ---------------------------------------------------------------- profile wersji gry
DESC_NO_GROUND_ON_FLY = (
    'Blokuje exploit: dołączanie jednostek naziemnych do oddziału latającego, który stoi nad wodą, k'
    'raterem lub innym terenem niedostępnym dla piechoty. Przy łączeniu oddziałów i przy przenoszeni'
    'u części jednostek do sąsiedniego oddziału gra sprawdza teraz, czy dołączane jednostki mogłyby '
    'wejść na pole docelowego oddziału (tak samo jak przy zwykłym ruchu). Jeśli nie – akcja jest odr'
    'zucana jak przy braku punktów akcji. Łączenie przy rozstawianiu armii na starcie scenariusza ni'
    'e jest sprawdzane.'
)

# Teksty darow leza w pliku pod "wskaznik + DOS_TEXT_DELTA" (loader DOS/4GW dolicza baze).
DOS_TEXT_DELTA = 0x13C400

DESC_GIFTS = (
    'Co i z jakim prawdopodobieństwem można dostać w świątyni (religia chrześcijańska) i w miejsc'
    'u kultu (religia pogańska). Gra ma cztery osobne tabele – dla każdej religii inną dla gracz'
    'a i inną dla komputera – i wybiera je po religii właściciela armii, która weszła do świątyni.'
)


def _dos_gift_amounts():
    """Liczby darow wpisane w kod wersji DOS (offsety w pliku; kod = adres w pamieci + 0x39400)."""
    return GiftAmounts("gift_amounts", "Siła darów świątyń i miejsc kultu", [
        # Gift_NewTroops 0x5B6FF: Random(1,5) -> mov edx,5 / mov eax,1
        GiftAmount("troops_max", 0, "najwięcej jednostek", Instr32(0x94B1E, "BA"), 1, 10),
        GiftAmount("troops_min", 0, "najmniej jednostek", Instr32(0x94B23, "B8"), 1, 10),
        # Temple_ProcessGift 0x5BCDB, kolejne przypadki instrukcji wyboru
        GiftAmount("tired2", 2, "zmęczenie", Instr32(0x95161, "BA"), -100, 100,
                   note="Unit_AddTiredness: wartość dodawana, wynik przycięty do 0–100."),
        GiftAmount("morale3", 3, "morale", Instr32(0x951A8, "BA"), -20, 20,
                   note="Unit_AddMorale: wartość dodawana, wynik przycięty do 0–20."),
        GiftAmount("health4", 4, "zdrowie", Instr(0x95218, "C6400F"), 0, 100,
                   note="Wpisywane wprost w pole zdrowia każdej jednostki (nie dodawane)."),
        GiftAmount("health5", 5, "zdrowie", Instr(0x95289, "C6400F"), 0, 100),
        GiftAmount("tired5", 5, "zmęczenie", Instr(0x95294, "C64010"), 0, 100,
                   note="Wpisywane wprost w pole zmęczenia (nie dodawane)."),
        GiftAmount("exp6", 6, "nożyki", Instr(0x952E6, "837DE0"), 0, 99,
                   note="Liczba obrotów pętli Unit_AddExperience. 3 nożyki = 1 poziom, "
                        "najwyższy poziom to 3, więc 9 wystarcza na pełne doświadczenie."),
        GiftAmount("morale7", 7, "morale", Instr32(0x95330, "BA"), -20, 20),
        GiftAmount("exp8", 8, "nożyki", Instr(0x95381, "837DDC"), 0, 99),
        GiftAmount("gold9", 9, "złoto", Instr32(0x953D4, "B8"), 1, 1000),
        GiftAmount("gold10", 10, "złoto", Instr32(0x953F1, "B8"), 1, 1000),
        GiftAmount("gold11", 11, "złoto", Instr32(0x9542B, "B8"), 1, 1000),
        GiftAmount("gold12", 12, "złoto", Instr32(0x9540E, "B8"), 1, 1000),
        GiftAmount("morale13", 13, "morale", Instr32(0x9543F, "BA"), -20, 20),
        GiftAmount("morale14", 14, "morale", Instr32(0x95486, "BA"), -20, 20),
        GiftAmount("tired14", 14, "zmęczenie", Instr32(0x95498, "BA"), -100, 100),
    ], note="Złoto: Gift_Gold (0x5B8CE) tworzy oddział ze złotem po 100 sztuk na jednostkę, "
            "a oddział ma najwyżej 10 jednostek – dlatego maksimum to 1000. "
            "Morale mieści się w 0–20, zdrowie i zmęczenie w 0–100, więc wartości poza tymi "
            "zakresami nic by nie dawały.")


PROFILES = {
    "dos_pl": {
        "name": "Clash – wersja DOS (CLASH.EXE, polska)",
        "size": 1481338,
        "features": [
            UnitDwordList("temple", "Świątynia / miejsce kultu", 0x161FFC, 5,
                          Instr(0x94C41, "BA"),
                          note="Losowana jest jedna z aktywnych pozycji (każda z równą szansą)."),
            UnitDwordList("temple_mission", "Świątynia – wariant w wybranych misjach", 0x162010, 7,
                          Instr(0x94C13, "BA"),
                          note="Używany zamiast zwykłej listy, gdy pole gry 0x222F1 ma wartość 2, 6, 12 lub 16 "
                               "(najpewniej numer/typ misji)."),
            GiftTable("gifts_christian_human", "Świątynia – gracz", 0x16203C, DOS_TEXT_DELTA, True),
            GiftTable("gifts_christian_ai", "Świątynia – komputer", 0x16233C, DOS_TEXT_DELTA, False),
            GiftTable("gifts_pagan_human", "Miejsce kultu – gracz", 0x1621D4, DOS_TEXT_DELTA, True),
            GiftTable("gifts_pagan_ai", "Miejsce kultu – komputer", 0x1624A4, DOS_TEXT_DELTA, False),
            _dos_gift_amounts(),
            UnitDwordList("port", "Port", 0x163E0C, 12, Instr(0x9952A, "BA")),
            UnitByteSet("forge", "Wymaga kuźni", 0x161F7C, 12),
            UnitByteSet("workshop", "Wymaga warsztatu", 0x161F88, 12),
            TechTable("tech", "Minimalny poziom zaawansowania", 0x15E7D4),
            WallTable("walls", "Mury – koszt i czas rozbudowy", 0x15FDD8,
                      note="Tabela 0x1339D8 w pamięci gry. Zmieniane są tylko cztery bajty: "
                           "czas 0x15FDDE i 0x15FDE2, koszt 0x15FDDF i 0x15FDE3."),
            CostWithMinimum("ap_split", "Dzielenie oddziału / przenoszenie części jednostek",
                            Instr(0x74DAA, "806808"), [Instr(0x74A46, "83F8"), Instr(0x74A9D, "83F8")],
                            clamped=False),
            CostWithMinimum("ap_join", "Dołączenie całego oddziału do innego",
                            Instr(0x7485D, "BA"), [Instr(0x7484F, "83F8")], clamped=False,
                            note="Tej samej funkcji gra używa przy budowaniu armii na starcie scenariusza, "
                                 "dlatego koszt łączenia odejmuje PA także jednostkom startowym."),
            EntrenchBonus("entrench", "Premia do obrony za okopanie", [
                # add dword [ebp-0Ch], N ; jmp short +11h  (zamiast mnozenia x1,25)
                (0x5FE74, "6955F440010000 89D0 C1FA1F C1E208 1BC2 C1F808 8945F4", "8345F4NN EB11"),
                (0x5FF29, "6955F440010000 89D0 C1FA1F C1E208 1BC2 C1F808 8945F4", "8345F4NN EB11"),
            ]),
            CodePatch("no_ground_on_fly", "Naziemne nie dołączają do latających nad niedostępnym terenem", [
                (0x2D54, "1A240F00", "00260F00"),                       # rozmiar obiektu kodu w LE
                (0x74847, "8B45E4E8A5A4FEFF", "E854700C00909090"),      # Unit_AddToGroup
                (0x74A92, "8D85FCFCFFFFE857A2FEFF", "E8396E0C00909090909090"),  # przenoszenie do sasiada
                (0x13B820, None,
                 "51525356575583EC6089D689DF89C289E0E8EC79F2FFE8000000005D69C6780500006BCF0E01C88B8DC887F2FF"
                 "030166837804FF74070FB644241DEB2B0FB7088B85F687F2FF833800740F5189F089FAE8E5A7F3FF5985C075"
                 "0E8B850A88F2FF8B0C880FB6440C1E83C4605D5F5E5B5A59C30000000000000000000000000000837DFC0075"
                 "1C538B45E80FBF100FBF58028B45E4E867FFFFFF5B85C0750483C8FFC38B45E4E92A34F2FF00000000000053"
                 "8D85FCFCFFFF8B55F88B5DFCE83EFFFFFF5B85C0750483C8FFC38D85FCFCFFFFE9FE33F2FF"),
            ], description=DESC_NO_GROUND_ON_FLY, note='Nowy kod (procedura liczenia kosztu terenu + 2 wstawki) leży w wolnym miejscu na końcu sekcji kodu (0x13B820); rozmiar sekcji w nagłówku LE (0x2D54) jest powiększany, żeby DOS/4GW go wczytał.'),
            CheatTable("cheats", "Kody", _cheats([
                (0x14CCE3, 6), (0x14CCEA, 10), (0x14CCF5, 10), (0x14CD00, 7), (0x14CD08, 10),
                (0x14CD13, 12), (0x14CD20, 15), (0x14CD30, 7), (0x14CD38, 8), (0x14CD41, 4), (0x14CD46, 4)])),
        ],
    },
    "win95": {
        "name": "Clash – wersja Windows (clash95.exe)",
        "size": 1232384,
        "features": [
            UnitDwordList("temple", "Świątynia / miejsce kultu", 0x113F10, 5, Instr(0x3F17D, "BA"),
                          note="Losowana jest jedna z aktywnych pozycji (każda z równą szansą)."),
            UnitDwordList("temple_mission", "Świątynia – wariant w wybranych misjach", 0x113F24, 7,
                          Instr(0x3F149, "BA"),
                          note="Używany zamiast zwykłej listy, gdy pole gry 0x222F1 ma wartość 2, 6, 12 lub 16."),
            UnitDwordList("port", "Port", 0x115DA8, 12, Instr(0x42B09, "BA")),
            UnitByteSet("forge", "Wymaga kuźni", 0x113E80, 16),
            UnitByteSet("workshop", "Wymaga warsztatu", 0x113E90, 12),
            TechTable("tech", "Minimalny poziom zaawansowania", 0x110768),
            WallTable("walls", "Mury – koszt i czas rozbudowy",
                      note="Adres tabeli murów w wersji Windows nie był sprawdzony na pliku, dlatego program "
                           "szuka jej po bajtach rozpoznawczych (AB 01 00 00 55 01 .. .. 00 01 .. ..) – "
                           "wytrzymałości murów są w obu wersjach te same. Jeśli znajdzie więcej niż jedno "
                           "takie miejsce, ustawienie zostaje wyłączone."),
            CostWithMinimum("ap_split", "Dzielenie oddziału / przenoszenie części jednostek",
                            Instr(0x225EF, "806808"), [Instr(0x22398, "83F8"), Instr(0x223D0, "83F8")],
                            clamped=False),
            CostWithMinimum("ap_join", "Dołączenie całego oddziału do innego",
                            Instr(0x22141, "BA"), [Instr(0x22124, "83F8")], clamped=True,
                            note="Tej samej funkcji gra używa przy budowaniu armii na starcie scenariusza, "
                                 "dlatego koszt łączenia odejmuje PA także jednostkom startowym."),
            EntrenchBonus("entrench", "Premia do obrony za okopanie", [
                # add ebx, N ; jmp short +16h
                (0x105DC, "8D149D00000000 01DA C1E206 89D0 C1FA1F C1E208 1BC2 C1F808 89C3", "83C3NN EB16"),
            ]),
            CodePatch("no_ground_on_fly", "Naziemne nie dołączają do latających nad niedostępnym terenem", [
                (0x22076, "85DB0F859D000000", "E8756C0C00909090"),      # Unit_AddToGroup: start scenariusza
                (0x2211B, "8B442408E8ECD2FEFF", "E8706B0C0090909090"),  # Unit_AddToGroup: sprawdzenie
                (0x223C9, "89E0E840D0FEFF", "E8F2680C009090"),          # przenoszenie do sasiada
                (0xE8C20, None,
                 "515253565783EC6089D689DF89C289E0E8EBA0F2FF69C6780500006BCF0E01C80305E402520066837804FF74"
                 "070FB644241DEB270FB708833D6C55520000740F5189F089FAE806ABF3FF5985C0750C8B0C8D6C4552000FB6"
                 "440C1E83C4605F5E5B5A59C3000000000000000000000000530FBF55000FBF5D028B442410E87EFFFFFF5B85"
                 "C0750483C8FFC38B44240CE95C67F2FF000000000000000000000000538D4424088B9424EC0200008B9C24E8"
                 "020000E848FFFFFF5B85C0750483C8FFC38D442404E92667F2FF00000000000085DB741183C4048B442408E8"
                 "1067F2FFE91F94F3FFC3"),
            ], description=DESC_NO_GROUND_ON_FLY, note='Nowy kod leży w wolnym miejscu na końcu sekcji kodu AUTO (0xE8C20, adres 0x4E9820).'),
            CheatTable("cheats", "Kody", _cheats([
                (0xFDA3A, 6), (0xFDA41, 10), (0xFDA4C, 10), (0xFDA57, 7), (0xFDA5F, 10),
                (0xFDA6A, 12), (0xFDA77, 15), (0xFDA87, 7), (0xFDA8F, 8), (0xFDA98, 4), (0xFDA9D, 4)])),
        ],
    },
}


class ExeFile:
    """Wczytany plik .exe + rozpoznany profil + odczytane wartosci znalezisk."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.original = f.read()
        self.data = bytearray(self.original)
        self.profile_key = self._detect()
        self.profile = PROFILES[self.profile_key]
        self.problems = {}
        self.features = {}
        for ft in self.profile["features"]:
            err = ft.check(self.data)
            if err:
                self.problems[ft.key] = err
            else:
                self.features[ft.key] = ft

    def _detect(self):
        for key, p in PROFILES.items():
            if len(self.original) == p["size"]:
                return key
        raise ValueError(
            f"Nieznana wersja pliku ({len(self.original)} bajtów). Obsługiwane: "
            + ", ".join(f"{p['name']} ({p['size']} B)" for p in PROFILES.values()))

    def get(self, key):
        return self.features[key].read(self.data)

    def set(self, key, value):
        self.features[key].write(self.data, value)

    def changes(self):
        """Lista (offset, stary, nowy) zmienionych bajtow."""
        return [(i, self.original[i], self.data[i]) for i in range(len(self.data))
                if self.original[i] != self.data[i]]

    def save(self, path=None, backup=True):
        import os
        import shutil
        path = path or self.path
        if backup and os.path.exists(path) and not os.path.exists(path + ".bak"):
            shutil.copy2(path, path + ".bak")
        with open(path, "wb") as f:
            f.write(self.data)
        self.original = bytes(self.data)
        self.path = path
