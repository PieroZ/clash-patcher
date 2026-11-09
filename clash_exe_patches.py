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
        return f"{uid:02X}: {UNIT_NAMES[uid]}"
    return f"{uid:02X}: ?"


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


def mazovia_decode(raw):
    """Bajty w kodowaniu Mazovia -> tekst."""
    return "".join(chr(b) if b < 0x80 else MAZOVIA_HIGH[b - 0x80] for b in raw)


def mazovia_text(data, offset, limit=400):
    """Tekst gry (kodowanie Mazovia, zakonczony zerem) spod offsetu w pliku."""
    if not 0 <= offset < len(data):
        return ""
    end = offset
    while end < min(offset + limit, len(data)) and data[end] != 0:
        end += 1
    return mazovia_decode(data[offset:end])


# Odwrotnosc tablicy wyzej. setdefault, bo niektore znaki sa w niej po dwa razy (0xFF to druga
# spacja, 0xFA drugi znak ·) - zapisujemy zawsze ten o nizszym kodzie, czyli ten z oryginalu.
MAZOVIA_ENCODE = {chr(b): b for b in range(0x20, 0x7F)}
for _i, _ch in enumerate(MAZOVIA_HIGH):
    MAZOVIA_ENCODE.setdefault(_ch, 0x80 + _i)
MAZOVIA_ENCODE["\n"] = 0x0A           # w tekstach gry wymusza zlamanie wiersza


def mazovia_encode(text):
    """Tekst -> (bajty w kodowaniu Mazovia, lista znakow, ktorych ta strona kodowa nie ma)."""
    out, bad = bytearray(), []
    for ch in text.replace("\r\n", "\n").replace("\r", "\n"):
        b = MAZOVIA_ENCODE.get(ch)
        if b is None:
            if ch not in bad:
                bad.append(ch)
        else:
            out.append(b)
    return bytes(out), bad


# ---------------------------------------------------------------- dary swiatyn
# Numer daru = przypadek instrukcji wyboru w kodzie wykonujacym dar (0x950DB), 0..15.
# Opis liczy sie z aktualnych wartosci w kodzie, bo one sa edytowalne.
def _knives(n):
    if n == 1:
        return "1 nożyk"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} nożyki"
    return f"{n} nożyków"


def _signed(n):
    return f"{n:+d}"


def lines_word(n):
    if n == 1:
        return "wiersz"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "wiersze"
    return "wierszy"


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

# Dary, ktore gra przyjmuje w misjach 2, 6, 12 i 16 dla gracza: kod wejscia do swiatyni (0x95535) losuje tam
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
    return f"{gid:02d}: {name}" + (f" ({desc})" if desc else "")


# Obrazek z temple.s32 (jednoczesnie numer dzwieku sfx\artefakt\N.wav, przy -1 gra bierze 7).
# Pominiete 22 i 23: nie maja dzwieku, a 23 to tlo okna daru (wysokosc tla okna daru).
ARTEFACT_NAMES = {
    -1: "(bez obrazka, czyli szczera modlitwa)",
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
    return f"{sid:>2}: {ARTEFACT_NAMES.get(sid, '?')}"


# ---------------------------------------------------------------- okienko daru
# Tekst daru rysuje TempleWindow (0x5B9DC): pergamin z temple.s32 (klatka 0x16, 329x178 px,
# od y = 150, i klatka 0x17 obok niej, 311x168 px, od y = 156 - razem y 150..327), obrazek daru
# (kazda klatka 58x39 px) w (294, 285), czyli x 294..351 i y 285..323,
# i tekst czcionka 0x11 (gfx\BUD_INFO.SFN, odstep 1 px za znakiem, wiersz co 20 px) miedzy
# x = 0x46 i x = 0x239, od y = 0xD2, z wyrownaniem 6 - zawijanie po slowach, kazdy wiersz
# wysrodkowany (kod rysujacy tekst, 0x59CC7).
GIFT_TEXT_WIDTH = 0x239 - 0x46        # 499 px - tyle miesci sie w wierszu
GIFT_FONT_SPACING = 1
GIFT_LINES_CLEAN = 4                  # tyle wierszy miesci sie nad obrazkiem daru (jak w oryginale)
GIFT_LINES_MAX = 6                    # tyle jeszcze miesci sie na pergaminie (ostatni y = 310)

# Szerokosci klatek czcionki BUD_INFO.SFN dla znakow 0x20..0xE1, odczytane z pliku gry
# (gfx\BUD_INFO.SFN w DATA\MINIMUM.RES, naglowek klatki znak-0x20: u16 szerokosc, u16 wysokosc).
# Znaki 0xE2..0xFF nie maja w tej czcionce klatki: gra czyta wtedy naglowek spod offsetu 0
# i dostaje szerokosc 0x1000, czyli jeden taki znak od razu przepelnia wiersz.
GIFT_GLYPH_WIDTHS = bytes((
    4,  3,  6,  4,  4,  4, 10,  3,  4,  4,  4,  4,  4,  4,  2,  4,   # 0x20
    8,  5,  7,  7,  7,  7,  8,  7,  7,  8,  4,  4,  4,  4,  4,  5,   # 0x30
    4,  7,  8,  7,  7,  7,  5,  7,  7,  4,  6,  7,  7, 10,  7,  8,   # 0x40
    7,  8,  7,  6,  6,  7,  7, 12,  8,  8,  8,  4,  4,  4,  4,  4,   # 0x50
    4,  7,  8,  7,  8,  7,  5,  7,  7,  2,  3,  7,  2, 12,  7,  8,   # 0x60
    7,  7,  5,  5,  5,  7,  7, 12,  6,  7,  8,  4,  4,  4,  4,  4,   # 0x70
    4,  7,  4,  4,  7,  4,  7,  4,  4,  4,  4,  4,  4,  7,  7,  7,   # 0x80
    7,  7,  6,  4,  8,  7,  4,  4,  6,  8,  7,  4,  7,  4,  5,  4,   # 0x90
    8,  8,  8,  8,  7,  7,  8,  8,  4,  4,  4,  4,  4,  4,  4,  4,   # 0xA0
    4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,   # 0xB0
    4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,   # 0xC0
    4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,   # 0xD0
    4,  7,                                                           # 0xE0
))
GIFT_GLYPH_FIRST, GIFT_GLYPH_LAST = 0x20, 0x20 + len(GIFT_GLYPH_WIDTHS) - 1
GIFT_NO_GLYPH_WIDTH = 0x1000


def gift_glyph_width(b):
    if GIFT_GLYPH_FIRST <= b <= GIFT_GLYPH_LAST:
        return GIFT_GLYPH_WIDTHS[b - GIFT_GLYPH_FIRST]
    return GIFT_NO_GLYPH_WIDTH


def gift_text_width(raw):
    """Szerokosc tekstu w pikselach, tak jak liczy to gra (0x59AD0): znaki nowego wiersza pomijane,
    za kazdym pozostalym jeden piksel odstepu, wynik obcinany do 16 bitow."""
    w = 0
    for b in raw:
        if b != 0x0A:
            w += gift_glyph_width(b) + GIFT_FONT_SPACING
    return w & 0xFFFF


def gift_find_wrap(raw):
    """Zawijanie wiersza, tak jak w grze (0x59B52): indeks znaku nowego wiersza, albo gdy tekst przekroczy
    szerokosc wiersza - indeks ostatniej spacji przed przekroczeniem (0, gdy spacji nie bylo),
    albo -1 na koncu tekstu."""
    acc, last = 0, 0
    for i, b in enumerate(raw):
        if b == 0x0A:
            return i
        if b == 0x20:
            last = i
        acc += gift_glyph_width(b) + GIFT_FONT_SPACING
        if acc > GIFT_TEXT_WIDTH:
            return last
    return -1


def gift_wrap(raw):
    """Wiersze, na jakie gra podzieli tekst daru, tak jak kod rysujacy tekst (0x59CC7) dla
    wyrownania 6, oraz czy przy tym gubi znaki.

    Zwraca (wiersze, gubi_znaki). Gra nie dzieli slow: gdy w wierszu nie ma ani jednej spacji,
    zawijanie zwraca 0, wiec gra wypisuje pusty wiersz i wyrzuca pierwszy znak reszty
    (`rest = rest[p+1:]`) - i tak az slowo sie zmiesci."""
    lines, rest, lost = [], bytes(raw), False
    while gift_text_width(rest) > GIFT_TEXT_WIDTH or 0x0A in rest:
        p = gift_find_wrap(rest)
        if p < 0:                     # w grze nie moze sie zdarzyc (petla sprawdza to samo)
            break
        if p == 0 and rest[:1] != b"\n":
            lost = True
        lines.append(rest[:p])
        rest = rest[p + 1:]
    lines.append(rest)
    return lines, lost


def gift_text_problems(text, with_sprite=True):
    """(bledy, ostrzezenia) tekstu daru. Blad = pliku nie wolno zapisac."""
    raw, bad = mazovia_encode(text)
    errors, warnings = [], []
    if bad:
        errors.append("Znaki, których gra nie ma w swojej stronie kodowej: "
                      + " ".join(bad) + ".")
    if b"%" in raw:
        errors.append("Znak % jest zakazany: gra podaje tekst daru jako wzorzec do printf, "
                      "więc % zostałby potraktowany jak polecenie formatowania i okienko "
                      "pokazałoby przypadkową liczbę albo gra by się wysypała.")
    no_glyph = sorted({b for b in raw if gift_glyph_width(b) == GIFT_NO_GLYPH_WIDTH and b != 0x0A})
    if no_glyph:
        errors.append("Znaki, których nie ma w czcionce okienka daru (gra nie narysuje ich, "
                      "a w dodatku złamie na nich wiersz): "
                      + " ".join(mazovia_decode(bytes([b])) for b in no_glyph) + ".")
    lines, lost = gift_wrap(raw)
    if not raw.strip():
        warnings.append("Tekst jest pusty, więc gra pokaże okienko z samym obrazkiem.")
    if lost:
        warnings.append("Jedno ze słów nie mieści się w wierszu. Gra nie dzieli słów: "
                        "wypisuje pusty wiersz i gubi po jednym znaku, aż słowo się zmieści.")
    if len(lines) > GIFT_LINES_MAX:
        warnings.append(f"Tekst zajmie {len(lines)} wierszy, a na pergaminie mieści się "
                        f"{GIFT_LINES_MAX}. Wiersze od {GIFT_LINES_MAX + 1}. gra narysuje poniżej "
                        "okienka i zostaną na mapie, dopóki gra jej nie przerysuje.")
    elif len(lines) > GIFT_LINES_CLEAN:
        msg = (f"Tekst zajmie {len(lines)} wierszy, a bez kłopotu mieszczą się "
               f"{GIFT_LINES_CLEAN} (tyle ma najdłuższy tekst oryginału). ")
        msg += ("Dalsze przejdą przez obrazek daru." if with_sprite else
                "Dalsze wejdą w dolny pas okienka, gdzie zwykle jest obrazek daru.")
        if len(lines) == GIFT_LINES_MAX:
            msg += f" {GIFT_LINES_MAX}. wiersz wystaje też poniżej prawej połowy pergaminu."
        warnings.append(msg)
    return errors, warnings


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

    def __init__(self, key, title, offset, size, count_instr, note="", expected=None, details=""):
        self.key, self.title, self.note, self.details = key, title, note, details
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

    def __init__(self, key, title, cost, minimums, clamped, lo=0, hi=100, note="", details=""):
        self.key, self.title, self.note, self.details = key, title, note, details
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


class LeFixups:
    """Tablica relokacji (fixupow) pliku LE - potrzebna, zeby zmienic wskaznik w danych gry.

    W pliku .exe wskaznik jest zapisany jako offset wewnatrz obiektu (sekcji). Prawdziwy adres
    wpisuje do pamieci loader DOS/4GW i bierze go NIE z tych bajtow, a z wpisu relokacji:
    dla kazdego wskaznika jest w tablicy relokacji wpis {gdzie, w ktorym obiekcie, jaki offset}.
    Zmiana samych bajtow w danych nic by wiec nie dala - loader nadpisalby je z powrotem.
    Dlatego program zmienia oba miejsca.

    Format naglowka LE: naglowek lezy pod offsetem z dworda 0x3C pliku,
    strony plikowe od pola 0x80, tablica relokacji stron od 0x68 (liczba_stron+1 dwordow,
    offsety w tablicy wpisow od 0x6C). Wpis:
        u8  typ         (dolne 4 bity; 0x20 = dalej lista zrodel)
        u8  flagi       (0x10 = 32-bitowy offset celu, 0x40 = 16-bitowy numer obiektu)
        s16 offset zrodla w stronie (albo u8 licznik + tyle s16, gdy typ & 0x20)
        u8/u16 numer obiektu
        u16/u32 offset celu (brak przy typie 2 - relokacji selektora)
    Wpis relokacji wskaznika lezacego na granicy stron jest wymieniony w obu stronach, dlatego
    `find` przeglada takze strone przed i po."""
    SRC_LIST = 0x20
    FLAG_TARGET32 = 0x10
    FLAG_OBJ16 = 0x40
    TYPE_SELECTOR = 0x02
    TYPE_OFFSET32 = 0x07
    # ile bajtow pod offsetem zrodla wpisuje loader (typ relokacji -> rozmiar)
    SRC_SIZE = {0x02: 2, 0x05: 2, 0x06: 6, 0x07: 4, 0x08: 4}

    def __init__(self, data):
        self.error = None
        self._cache = {}
        try:
            self._parse(data)
        except (struct.error, IndexError, ValueError) as e:
            self.error = f"nie udało się odczytać tablicy relokacji pliku: {e}"

    def _parse(self, data):
        le = struct.unpack_from("<I", data, 0x3C)[0]
        if bytes(data[le:le + 2]) != b"LE":
            raise ValueError(f"brak nagłówka LE pod 0x{le:X}")
        def field(off):
            return struct.unpack_from("<I", data, le + off)[0]

        self.pages = field(0x14)
        self.obj_page_table = le + field(0x48)
        self.fixup_page_table = le + field(0x68)
        self.fixup_records = le + field(0x6C)
        self.first_page = field(0x80)
        if self.pages < 1 or self.first_page >= len(data):
            raise ValueError("puste albo niespójne pola nagłówka")
        # strona logiczna (indeks w tablicy relokacji) -> strona plikowa i odwrotnie
        self.phys = [0] * (self.pages + 1)
        self.logical = {}
        for n in range(1, self.pages + 1):
            e = self.obj_page_table + (n - 1) * 4
            ph = (data[e] << 16) | (data[e + 1] << 8) | data[e + 2]
            self.phys[n] = ph
            self.logical.setdefault(ph, n)

    def page_offset(self, page):
        """Offset w pliku, pod ktory loader wczytuje strone logiczna `page`."""
        return self.first_page + (self.phys[page] - 1) * 0x1000

    def records(self, data, page):
        """Wpisy relokacji strony logicznej `page` jako lista slownikow.

        Wynik jest zapamietywany: rozmiary i pozycje wpisow sie nie zmieniaja (program zmienia
        tylko offsety celow, w miejscu), wiec raz odczytana lista pozostaje wazna."""
        if page in self._cache:
            return self._cache[page]
        start = struct.unpack_from("<I", data, self.fixup_page_table + (page - 1) * 4)[0]
        end = struct.unpack_from("<I", data, self.fixup_page_table + page * 4)[0]
        out, o, stop = [], self.fixup_records + start, self.fixup_records + end
        while o < stop:
            at = o
            typ, flags = data[o], data[o + 1]
            o += 2
            if typ & self.SRC_LIST:
                count = data[o]
                o += 1
                srcs = list(struct.unpack_from(f"<{count}h", data, o))
                o += 2 * count
            else:
                srcs = [struct.unpack_from("<h", data, o)[0]]
                o += 2
            if flags & self.FLAG_OBJ16:
                obj = struct.unpack_from("<H", data, o)[0]
                o += 2
            else:
                obj = data[o]
                o += 1
            target_at, target = None, None
            if (typ & 0x0F) != self.TYPE_SELECTOR:
                target_at = o
                if flags & self.FLAG_TARGET32:
                    target = struct.unpack_from("<I", data, o)[0]
                    o += 4
                else:
                    target = struct.unpack_from("<H", data, o)[0]
                    o += 2
            if o > stop:
                raise ValueError(f"wpis relokacji pod 0x{at:X} wychodzi za koniec listy strony {page}")
            out.append({"at": at, "type": typ & 0x0F, "flags": flags, "obj": obj,
                        "srcs": srcs, "target_at": target_at, "target": target})
        self._cache[page] = out
        return out

    def find(self, data, offset):
        """Wpisy relokacji, ktore wpisuja adres pod `offset` (offset w pliku)."""
        if self.error:
            return []
        page = self.logical.get((offset - self.first_page) // 0x1000 + 1)
        if page is None:
            return []
        out = []
        try:
            for p in (page - 1, page, page + 1):
                if not 1 <= p <= self.pages:
                    continue
                base = self.page_offset(p)
                for rec in self.records(data, p):
                    if any(base + src == offset for src in rec["srcs"]):
                        out.append(rec)
        except (struct.error, IndexError, ValueError) as e:
            self.error = f"nie udało się odczytać tablicy relokacji pliku: {e}"
            return []
        return out

    def sources_in(self, data, start, end):
        """Offsety w pliku z zakresu [start, end), pod ktore loader wpisuje jakis adres."""
        if self.error:
            return []
        first = self.logical.get((start - self.first_page) // 0x1000 + 1)
        last = self.logical.get((end - 1 - self.first_page) // 0x1000 + 1)
        if first is None or last is None:
            self.error = f"obszar 0x{start:X}–0x{end:X} nie leży w stronach pliku"
            return []
        out = []
        try:
            for p in range(max(1, first - 1), min(self.pages, last + 1) + 1):
                base = self.page_offset(p)
                for rec in self.records(data, p):
                    size = self.SRC_SIZE.get(rec["type"], 4)
                    for src in rec["srcs"]:
                        if base + src + size > start and base + src < end:
                            out.append(base + src)
        except (struct.error, IndexError, ValueError) as e:
            self.error = f"nie udało się odczytać tablicy relokacji pliku: {e}"
            return []
        return sorted(set(out))

    def write_target(self, data, rec, target):
        """Nowy offset celu we wpisie relokacji."""
        if rec["flags"] & self.FLAG_TARGET32:
            struct.pack_into("<I", data, rec["target_at"], target)
        else:
            if not 0 <= target <= 0xFFFF:
                raise ValueError(f"offset 0x{target:X} nie zmieści się w 16-bitowym wpisie "
                                 f"relokacji pod 0x{rec['at']:X}")
            struct.pack_into("<H", data, rec["target_at"], target)


class GiftTable:
    """Jedna z czterech tabel losowania darow swiatyni / miejsca kultu.

    Wpis ma 24 bajty: {i32 numer daru, i32 waga, i32 obrazek, 3 wskazniki na tekst (PL, EN, DE)}.
    Lista konczy sie wpisem, ktorego numer daru to -1. Cztery tabele leza w pliku jedna za druga,
    wiec liczby wpisow nie da sie zmienic bez przenoszenia tabel - edytowalne sa numer daru,
    waga i obrazek kazdego istniejacego wpisu.

    Tabele wybiera kod wejscia do swiatyni (0x95535) po religii gracza i po tym, czy jest czlowiekiem.
    Losowanie (0x9502C) sumuje wagi (S), bierze r = Random(0, S-1) i wybiera
    pierwszy wpis, dla ktorego suma wag do niego wlacznie jest >= r. Dlatego r = 0 zawsze trafia
    w pierwszy wpis (ma o jedna szanse wiecej, niz wynika z wagi), a ostatni wpis traci jedna
    szanse - metoda `chances` liczy to dokladnie tak samo jak gra.

    Numer daru nie ma nic wspolnego z tekstem wpisu, wiec po zmianie efektu komunikat w grze
    zostaje stary. Same teksty edytuje GiftTexts - wszystkie cztery tabele dziela jeden obszar
    bajtow, wiec jest to jedno osobne znalezisko."""
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
        """Ile z S losowan trafia w kazdy wpis - dokladnie jak w kodzie gry (0x9502C).

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


class GiftTexts:
    """Teksty darow wszystkich czterech tabel - jeden wspolny obszar bajtow w pliku.

    Wpis tabeli ma trzy wskazniki na tekst: polski, angielski i trzeci (w tym pliku zawsze
    pusty - gra wybiera go po numerze jezyka, a polska wersja ma numer 0, czyli tekst polski).
    Wszystkie 168 wskaznikow prowadza w jeden ciagly obszar, ktory w oryginale jest wypelniony
    co do bajtu: zadnego tekstu nie da sie wydluzyc w miejscu.

    Dlatego przy zapisie program uklada cala pule od nowa: teksty jeden za drugim, powtarzajace
    sie tylko raz (w oryginale powtorzen jest 56, same puste trzecie teksty to 56 bajtow -
    po ulozeniu oryginal zajmuje 6 978 z 14 732 bajtow, czyli na dluzsze teksty jest ponad
    dwa razy tyle miejsca, ile zajmuja). Kazdy wskaznik to dwa miejsca do zmiany: dword we
    wpisie tabeli i offset celu w tablicy relokacji LE (patrz LeFixups).

    Czego program nie robi: nie przenosi puli ani jej nie powieksza. Offsety w relokacjach tych
    wskaznikow sa 16-bitowe, a cala pula lezy ponizej 0x10000 obiektu danych - wyjscie poza nia
    wymagaloby 32-bitowych wpisow, czyli przesuniecia calej tablicy relokacji."""
    kind = "gift_texts"
    LANG_COUNT = 3

    def __init__(self, key, title, tables, pool, text_delta, note=""):
        self.key, self.title, self.note = key, title, note
        self.tables = tables                      # lista GiftTable korzystajacych z tej puli
        self.pool_start, self.pool_end = pool      # offsety w pliku: [start, end)
        self.text_delta = text_delta

    @property
    def pool_size(self):
        return self.pool_end - self.pool_start

    def pointers(self, data):
        """Lista (tabela, numer wpisu, numer jezyka, offset wskaznika w pliku, wskaznik)."""
        out = []
        for t in self.tables:
            for i in range(t.count(data)):
                for k in range(self.LANG_COUNT):
                    at = t.entry_offset(i) + 12 + 4 * k
                    out.append((t, i, k, at, struct.unpack_from("<I", data, at)[0]))
        return out

    def text_at(self, data, ptr):
        """(offset w pliku, bajty) tekstu, na ktory pokazuje wskaznik `ptr`."""
        off = ptr + self.text_delta
        end = off
        while end < len(data) and data[end] != 0:
            end += 1
        return off, bytes(data[off:end])

    def check(self, data):
        if self.pool_end > len(data):
            return f"0x{self.pool_start:X}: obszar tekstów wychodzi za koniec pliku"
        fx = LeFixups(data)
        if fx.error:
            return fx.error
        for t, i, k, at, ptr in self.pointers(data):
            if ptr == 0:
                return f"0x{at:X}: wpis {i + 1} tabeli „{t.title}” nie ma tekstu {k + 1}"
            off, raw = self.text_at(data, ptr)
            if not (self.pool_start <= off and off + len(raw) + 1 <= self.pool_end):
                return (f"0x{at:X}: tekst {k + 1} wpisu {i + 1} tabeli „{t.title}” leży pod "
                        f"0x{off:X}, poza obszarem tekstów darów "
                        f"(0x{self.pool_start:X}–0x{self.pool_end:X})")
            recs = fx.find(data, at)
            if fx.error:
                return fx.error
            if not recs:
                return f"0x{at:X}: brak wpisu relokacji dla wskaźnika tekstu"
            for rec in recs:
                if rec["type"] != LeFixups.TYPE_OFFSET32 or rec["target"] != ptr:
                    return (f"0x{at:X}: wpis relokacji pod 0x{rec['at']:X} nie wygląda jak "
                            f"32-bitowy wskaźnik na ten tekst")
        used = fx.sources_in(data, self.pool_start, self.pool_end)
        if fx.error:
            return fx.error
        if used:
            return (f"0x{used[0]:X}: w obszarze tekstów darów loader wpisuje adres "
                    f"(tekst zostałby nadpisany)")
        return None

    def read(self, data):
        """{klucz tabeli: [[tekst polski, angielski, trzeci], ...]}"""
        out = {t.key: [] for t in self.tables}
        for t, i, k, at, ptr in self.pointers(data):
            row = out[t.key]
            if k == 0:
                row.append([])
            row[i].append(mazovia_decode(self.text_at(data, ptr)[1]))
        return out

    def layout(self, data, texts):
        """(offset w pliku kazdego tekstu, ile bajtow zajmie cala pula) dla podanych tekstow.

        Teksty takie same dostaja jeden wspolny offset - gra ich nie zapisuje, wiec dzielenie
        bajtow jest dla niej niewidoczne."""
        offsets, off = {}, self.pool_start
        for t, i, k, at, ptr in self.pointers(data):
            raw = self._raw(texts, t, i, k, data, ptr)
            if raw not in offsets:
                offsets[raw] = off
                off += len(raw) + 1               # + bajt zerowy koncza tekst
        return offsets, off - self.pool_start

    def _raw(self, texts, t, i, k, data, ptr):
        """Bajty tekstu do zapisania: z podanych tekstow, a gdy ich tam nie ma - z pliku."""
        rows = texts.get(t.key) if texts else None
        if rows is not None and i < len(rows) and k < len(rows[i]):
            return mazovia_encode(rows[i][k])[0]
        return self.text_at(data, ptr)[1]

    def used(self, data, texts):
        return self.layout(data, texts)[1]

    def write(self, data, texts):
        if self.read(data) == texts:
            return                                # nic nie zmieniono - nie ruszamy pliku
        offsets, used = self.layout(data, texts)
        if used > self.pool_size:
            raise ValueError(f"Teksty darów zajmują {used} bajtów, a w pliku jest na nie miejsce "
                             f"na {self.pool_size} bajtów. Trzeba skrócić któryś tekst.")
        fx = LeFixups(data)
        if fx.error:
            raise ValueError(fx.error)
        plan = [(at, self._raw(texts, t, i, k, data, ptr))
                for t, i, k, at, ptr in self.pointers(data)]
        data[self.pool_start:self.pool_end] = bytes(self.pool_size)
        for raw, off in offsets.items():
            data[off:off + len(raw)] = raw        # bajt zerowy jest juz na swoim miejscu
        for at, raw in plan:
            ptr = offsets[raw] - self.text_delta
            struct.pack_into("<I", data, at, ptr)
            for rec in fx.find(data, at):
                fx.write_target(data, rec, ptr)


class GiftAmount:
    """Jedna liczba wpisana wprost w kod obslugi darow (0x950DB i 0x94AFF)."""

    def __init__(self, key, gift, label, instr, lo, hi, unit="", note=""):
        self.key, self.gift, self.label = key, gift, label
        self.instr, self.lo, self.hi = instr, lo, hi
        self.unit, self.note = unit, note


class GiftAmounts:
    """Sila darow: liczby, ktore gra ma wpisane w kodzie.

    Gra nie trzyma ich w zadnej tabeli - sa to operandy instrukcji w kodzie
    wykonujacym dar (0x950DB, instrukcja wyboru z 16 przypadkami) i w kodzie tworzacym nowy
    oddzial (0x94AFF, losowanie 1-5 jednostek).
    Te same liczby obowiazuja gracza i komputer, bo oba przechodza przez te funkcje; dotycza tez
    zakopanych skarbow, ktore korzystaja z tych samych numerow darow."""
    kind = "gift_amounts"
    # Kod dodajacy zmeczenie (0x61C1D jedna jednostka, 0x61CAF caly oddzial) dodaje do bajtu ze
    # znakiem i dopiero potem przycina do 0..100, wiec dodanie wiecej niz 27 przekreca bajt
    # jednostkom o duzym zmeczeniu i zeruje im zmeczenie. Naprawia to CodePatch "tiredness_add",
    # dlatego gdy jest wgrany, program nie ostrzega przy wiekszych wartosciach.
    TIREDNESS_SAFE_ADD = 27

    def __init__(self, key, title, amounts, note="", details=""):
        self.key, self.title, self.note, self.details = key, title, note, details
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

    Kod rozbudowy murow (0x70DD4) przy rozbudowie z poziomu L czyta wpis L+1, a poziom muru
    jest zawsze < 2, wiec gra czyta tylko tury i koszt wpisow 1 i 2 (bajty +0x06/+0x07 i
    +0x0A/+0x0B tabeli). Tury i koszt wpisu 0 nie sa czytane nigdy - nie da sie "rozbudowac
    do poziomu 0". Poza ta jedna funkcja zadne inne miejsce w kodzie nie czyta tych bajtow,
    a menu "Rozbuduj mury" (inaczej niz menu budowy) nie pokazuje ceny, wiec nie ma tekstu,
    ktory trzeba by zmieniac razem z liczbami.

    Koszt jest odczytywany jako bajt bez znaku i porownywany ze skarbcem zamku rowniez bez
    znaku, wiec caly zakres 0-255 dziala poprawnie. Kod poczatku tury (0x6F919) zmniejsza licznik
    tur (budynek +0x1AD) o 1 na poczatku kazdej tury wlasciciela i podnosi poziom muru, gdy ten
    dojdzie do zera - dlatego 0 tur nie ma sensu (zloto pobrane, licznik nigdy nie wystartuje).

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
    # wymagany poziom technologiczny zamku (warunek rozbudowy: poziom muru < technologia - 1)
    TECH_NEEDED = {1: 2, 2: 3}

    def __init__(self, key, title, offset=None, note="", details=""):
        self.key, self.title, self.note, self.details = key, title, note, details
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

    def __init__(self, key, title, sites, description="", note="", details=""):
        self.key, self.title, self.description, self.note = key, title, description, note
        self.details = details
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
NOTE_SPLIT_ICON = (
    "To samo minimum steruje kolorem krzyżyka na ikonce zaznaczonej jednostki na dolnym pasku "
    "(czerwony = za mało PA, żeby ją odłączyć)."
)

DESC_NO_GROUND_ON_FLY = (
    'Blokuje exploit: dołączanie jednostek naziemnych do oddziału latającego, który stoi nad wodą, k'
    'raterem lub innym terenem niedostępnym dla piechoty. Przy łączeniu oddziałów i przy przenoszeni'
    'u części jednostek do sąsiedniego oddziału gra sprawdza teraz, czy dołączane jednostki mogłyby '
    'wejść na pole docelowego oddziału (tak samo jak przy zwykłym ruchu). Jeśli nie, akcja jest odr'
    'zucana tak jak przy braku punktów akcji. Łączenie przy rozstawianiu armii na starcie scenariusza ni'
    'e jest sprawdzane.'
)

TITLE_TIREDNESS_ADD = "Zmęczenie zatrzymuje się na 100, a nie przekręca na zero"

DESC_TIREDNESS_ADD = (
    'Poprawia błąd: gra dodaje zmęczenie w bajcie ze znakiem i dopiero wynik przycina do 0–100, '
    f'więc dodanie więcej niż {GiftAmounts.TIREDNESS_SAFE_ADD} przekręca bajt jednostkom, które są '
    'już zmęczone, i zamiast kary daje im zerowe zmęczenie. Trafia w to oryginalna KSIĘGA PLAG '
    '(dar 14, +50 zmęczenia): oddział o zmęczeniu 78 lub większym dostaje po niej pełny wypoczynek '
    'zamiast klątwy. Po włączeniu poprawki gra liczy sumę na liczbach 32-bitowych i dopiero ją '
    'przycina, więc zmęczenie dochodzi najwyżej do 100 i nie spada. Poza tym jednym przypadkiem '
    'nic się nie zmienia: każda wartość, która i tak nie przekręcała bajtu, daje dokładnie ten sam '
    'wynik co w oryginale. Poprawka obejmuje oba miejsca kodu, które dodają zmęczenie, więc działa '
    'na dary świątyń, miejsc kultu i zakopanych skarbów, a także na zmęczenie z walki, z początku '
    'tury i z odpoczynku oddziału w zamku.'
)

HOW_TIREDNESS_ADD = (
    '<p>Zmęczenie leży w rekordzie jednostki pod <code>+0x0A</code> jako bajt ze znakiem i w całej '
    'grze mieści się w 0–100. Dodają je dwa miejsca w kodzie o takiej samej treści: kod dodający '
    'zmęczenie jednej jednostce (funkcja od <code>0x61C1D</code>, wskaźnik jednostki trzyma '
    'w <code>[ebp-0x0C]</code>) i kod robiący to samo po kolei każdej jednostce oddziału (funkcja '
    'od <code>0x61CAF</code>, wskaźnik w <code>[ebp-0x14]</code>). Zmieniany fragment ma w obu '
    '46 bajtów; w pierwszym leży pod <code>0x61C7A</code> i wygląda tak:</p>'
    '<pre>'
    '8A 45 F8       mov   al, [ebp-0x08]        ; liczba do dodania\n'
    '8B 55 F4       mov   edx, [ebp-0x0C]\n'
    '00 42 0A       add   [edx+0x0A], al        ; tu przekręca się bajt\n'
    '8B 55 F4       mov   edx, [ebp-0x0C]\n'
    '0F BE 52 0A    movsx edx, byte [edx+0x0A]\n'
    '85 D2          test  edx, edx\n'
    '7D 07          jge   0x61C95\n'
    '8B 45 F4       mov   eax, [ebp-0x0C]\n'
    'C6 40 0A 00    mov   byte [eax+0x0A], 0    ; poniżej zera -&gt; 0\n'
    '8B 45 F4       mov   eax, [ebp-0x0C]\n'
    '0F BE 40 0A    movsx eax, byte [eax+0x0A]\n'
    '83 F8 64       cmp   eax, 0x64\n'
    '7E 07          jle   0x61CA8\n'
    '8B 45 F4       mov   eax, [ebp-0x0C]\n'
    'C6 40 0A 64    mov   byte [eax+0x0A], 0x64 ; powyżej 100 -&gt; 100'
    '</pre>'
    '<p>Suma wychodzi z <code>add</code> jako bajt ze znakiem, więc powyżej 127 jest ujemna '
    'i pierwsze przycięcie zapisuje 0. Poprawka wstawia w te 46 bajtów kod, który dodaje '
    'w 32 bitach i przycina sumę, zanim zapisze bajt:</p>'
    '<pre>'
    '8B 45 F8       mov   eax, [ebp-0x08]       ; liczba do dodania, całym dwordem\n'
    '8B 55 F4       mov   edx, [ebp-0x0C]\n'
    '0F BE 52 0A    movsx edx, byte [edx+0x0A]  ; zmęczenie 0..100\n'
    '01 D0          add   eax, edx              ; suma w 32 bitach, bez przekręcania\n'
    '85 C0          test  eax, eax\n'
    '7D 02          jge   0x61C8C\n'
    '31 C0          xor   eax, eax              ; poniżej zera -&gt; 0\n'
    '83 F8 64       cmp   eax, 0x64\n'
    '7E 02          jle   0x61C93\n'
    'B0 64          mov   al, 0x64              ; powyżej 100 -&gt; 100\n'
    '8B 55 F4       mov   edx, [ebp-0x0C]\n'
    '88 42 0A       mov   [edx+0x0A], al        ; dopiero teraz zapis\n'
    '90 (×15)       nop                         ; do 46 bajtów'
    '</pre>'
    '<p>Liczba jest brana całym dwordem, bo w tym samym slocie sprawdza ją instrukcja '
    '<code>83 7D F8 00</code> (<code>cmp dword [ebp-0x08], 0</code>) z początku funkcji dla '
    'oddziału, a więc wołający podają ją z rozszerzonym znakiem.</p>'
    '<p>W drugim miejscu (fragment pod <code>0x61D5A</code>) te same instrukcje adresują jednostkę '
    'przez <code>[ebp-0x14]</code>, więc bajt <code>F4</code> w operandach jest tam bajtem '
    '<code>EC</code>; poza tym i poza adresami skoków nic się nie różni.</p>'
    '<p>Żadnych adresów w pliku nie trzeba przy tym poprawiać. Jedyny skok z zewnątrz, '
    '<code>EB 2E</code> pod <code>0x61C78</code> (i <code>0x61D58</code>), omija cały fragment '
    'i celuje w pierwszy bajt za nim; do środka fragmentu nie skacze nic poza nim samym; tablica '
    'relokacji pliku nie ma w tym zakresie ani jednego wpisu, bo wszystko jest adresowane przez '
    '<code>ebp</code>. Nowy kod zmienia tylko <code>eax</code> i <code>edx</code>, dokładnie jak '
    'oryginalny, więc <code>ecx</code>, <code>esi</code>, <code>edi</code> i <code>ebp</code> '
    'zostają nietknięte.</p>'
)

# Bajty poprawki dla obu miejsc kodu dodajacych zmeczenie. Zmieniany fragment ma 46 bajtow
# i w obu miejscach jest taki sam; rozni go tylko bajt operandu ze slotem ramki, w ktorym
# funkcja trzyma wskaznik na jednostke, wiec {s} w zapisie hex nizej to wlasnie ten bajt.
# Skoki sa wzgledne i nie wychodza poza fragment, a dane adresowane przez ebp, wiec poza tym
# jednym bajtem kod nie zalezy od offsetu w pliku i jedno zrodlo wystarczy na oba miejsca.
# Listing obu wersji kodu z komentarzami jest w HOW_TIREDNESS_ADD.
_TIREDNESS_SITES = {
    0x61C7A: 0x0C,   # SubUnit_AddTiredness (kod 0x2881D, plik 0x61C1D): wskaznik w [ebp-0x0C]
    0x61D5A: 0x14,   # Unit_AddTiredness    (kod 0x288AF, plik 0x61CAF): wskaznik w [ebp-0x14]
}
_TIREDNESS_FRAGMENT = 46   # dlugosc fragmentu; nowy kod jest krotszy, reszta to nop-y

# Oryginal: dodanie w bajcie ze znakiem (tu przekreca sie bajt), przyciecie dopiero po zapisie.
_TIREDNESS_ORIG = (
    "8a45f8 8b55{s} 00420a"           # mov al,[ebp-8]; mov edx,[ebp-slot]; add [edx+0x0A],al
    " 8b55{s} 0fbe520a 85d2 7d07"     # mov edx,[ebp-slot]; movsx edx,[edx+0x0A]; test; jge +7
    " 8b45{s} c6400a00"               # mov eax,[ebp-slot]; mov [eax+0x0A],0     (ponizej zera)
    " 8b45{s} 0fbe400a 83f864 7e07"   # mov eax,[ebp-slot]; movsx eax,..; cmp eax,100; jle +7
    " 8b45{s} c6400a64"               # mov eax,[ebp-slot]; mov [eax+0x0A],100   (powyzej 100)
)

# Poprawka: suma liczona w 32 bitach, przyciecie przed zapisem bajtu. Zrodlo asemblerowe
# (keystone, KS_ARCH_X86 / KS_MODE_32; {slot} to 0x0C albo 0x14):
#      mov   eax, dword ptr [ebp - 8]       ; delta calym dwordem - tak czyta ja sam kod gry
#      mov   edx, dword ptr [ebp - {slot}]
#      movsx edx, byte ptr [edx + 0xa]      ; zmeczenie 0..100
#      add   eax, edx                       ; suma bez przekrecania bajtu
#      test  eax, eax
#      jge   HI
#      xor   eax, eax                       ; ponizej zera -> 0
# HI:  cmp   eax, 0x64
#      jle   PUT
#      mov   al, 0x64                       ; powyzej 100 -> 100
# PUT: mov   edx, dword ptr [ebp - {slot}]
#      mov   byte ptr [edx + 0xa], al       ; dopiero teraz zapis
_TIREDNESS_NEW = (
    "8b45f8 8b55{s} 0fbe520a 01d0"    # mov eax,[ebp-8]; mov edx,[ebp-slot]; movsx; add eax,edx
    " 85c0 7d02 31c0"                 # test eax,eax; jge +2; xor eax,eax
    " 83f864 7e02 b064"               # cmp eax,100; jle +2; mov al,100
    " 8b55{s} 88420a"                 # mov edx,[ebp-slot]; mov [edx+0x0A],al
)


def _tiredness_code(pattern, slot, pad=False):
    """Bajty fragmentu dla podanego slotu ramki; krotszy kod jest dopelniony nop-ami."""
    code = bytes.fromhex(pattern.format(s=f"{-slot & 0xFF:02x}"))
    assert len(code) <= _TIREDNESS_FRAGMENT, len(code)
    assert pad or len(code) == _TIREDNESS_FRAGMENT, len(code)
    return (code + b"\x90" * (_TIREDNESS_FRAGMENT - len(code))).hex()


def _tiredness_sites():
    """Lista (offset, oryginalne bajty, nowe bajty) dla CodePatch "tiredness_add"."""
    return [(off, _tiredness_code(_TIREDNESS_ORIG, slot),
             _tiredness_code(_TIREDNESS_NEW, slot, pad=True))
            for off, slot in _TIREDNESS_SITES.items()]


# Teksty darow leza w pliku pod "wskaznik + DOS_TEXT_DELTA" (loader DOS/4GW dolicza baze).
DOS_TEXT_DELTA = 0x13C400

# Caly obszar tekstow czterech tabel darow: od pierwszego bajtu tekstu pierwszego wpisu tabeli
# swiatyni gracza (0x142C7A, wskaznik 0x687A) do bajtu za ostatnim tekstem tabeli miejsca kultu
# komputera (0x146606, wskaznik 0xA206) - 14 732 bajty wypelnione co do jednego.
DOS_GIFT_POOL = (0x142C7A, 0x146606)

DESC_GIFTS = (
    'Co i z jakim prawdopodobieństwem można dostać w świątyni (religia chrześcijańska) i w miejsc'
    'u kultu (religia pogańska). Gra ma cztery osobne tabele: dla każdej religii inną dla gracz'
    'a i inną dla komputera. Wybiera je po religii właściciela armii, która weszła do świątyni.'
)

TITLE_TEMPLE_MISSION = 'Świątynia: wariant z misji 3 i 7 obu kampanii'

NOTE_TEMPLE_MISSION = (
    'Używany zamiast zwykłej listy w misjach 3 i 7 obu kampanii, dlatego dar „nowy oddział” '
    'daje w nich ludzi, a w pozostałych misjach i w grze poza kampanią potwory.'
)

# Misje, w ktorych kod tworzacy nowy oddzial bierze liste ludzi zamiast listy potworow. Kolumny: wartosc
# pola gry 0x222F1 (numer misji kampanii liczony od zera), kampania, numer pokazywany graczowi
# (numer % 10 + 1), plik mapy, cel misji z g_missionObjectives (0x137F20 w pamieci gry).
TEMPLE_MISSION_ROWS = (
    (2, "chrześcijańska", 3, "k_mapa3l.map", "Zdobyć zamek przeciwnika"),
    (6, "chrześcijańska", 7, "k_mapa7z.map", "Odbić królową"),
    (12, "pogańska", 3, "p_mapa3z.map", "Zdobyć zamek przeciwnika"),
    (16, "pogańska", 7, "p_mapa7j.map",
     "Zdobyć najbardziej zaawansowany technologicznie zamek władcy Kalev"),
)

# Cztery porownania pola 0x222F1 w kodzie tworzacym nowy oddzial (0x94AFF) - offsety w pliku wersji DOS (odczytane
# z CLASH.EXE). W wersji Windows nie byly sprawdzane, wiec tam ta sekcja sie nie pokazuje.
TEMPLE_MISSION_CMP_DOS = ((0x94BD4, 2), (0x94BE4, 6), (0x94BF4, 12), (0x94C04, 16))

# Zrodlo opisow misji i znaczenia pola 0x222F1 - rozpracowany kod gry obok tego projektu.
SRC_MISSIONS = (
    "Cztery numery misji odczytane wprost z pliku gry, z porównań wymienionych wyżej. "
    "Nazwy map leżą w pliku jako zwykły tekst, pod <code>0x14DE11</code>, <code>0x14DF03</code>, "
    "<code>0x14E0D2</code> i <code>0x14E1B7</code>. Cele misji są takie, jakie gra pokazuje "
    "w okienku „Misja N” na początku każdej z nich."
)


# ------------------------------------------------- szczegoly techniczne (ikona "i" obok opisu)
# `details` znaleziska to fragment HTML pokazywany w osobnym oknie po nacisnieciu ikony "i".
# Trafia tu to, co przy zwyklym korzystaniu z programu jest szumem: offsety w pliku, instrukcje,
# nazwy funkcji gry i to, skad informacja pochodzi. Opis obok pola ma zostac krotki i mowic
# przede wszystkim, co ustawienie zmienia w grze.
#
# Wartoscia moze byc gotowy tekst albo funkcja f(znalezisko) -> tekst. Druga postac pozwala
# wypisac offsety samego znaleziska zamiast powtarzac je w tekscie, dzieki czemu wersja DOS
# i Windows moga korzystac z tego samego opisu.

_TBL = "<table border='1' cellpadding='4' cellspacing='0' width='100%'>"


def feature_details(ft):
    """Tekst okna szczegolow znaleziska ('' = znalezisko nie ma szczegolow)."""
    d = getattr(ft, "details", "")
    return d(ft) if callable(d) else (d or "")


def _details_temple(ft):
    return (
        "<p>Z tej listy gra losuje jednostki daru <b>„nowy oddział”</b> (dar 0), tak samo "
        "w świątyni, w miejscu kultu i w zakopanym skarbie, bo wszystkie trzy trafiają w ten sam "
        "kod tworzący nowy oddział (zaczyna się pod <code>0x94AFF</code>). Powstaje oddział "
        "z 1–5 jednostek, a typ każdej z nich jest losowany osobno, więc typy mogą się w jednym "
        "oddziale powtarzać.</p>"
        "<p><b>Gdzie to jest w pliku</b></p>"
        + _TBL +
        "<tr><th align='left'>Co</th><th align='left'>Offset</th></tr>"
        f"<tr><td>lista: {ft.size} pozycji po 4 bajty, ID jednostki jako <code>int</code></td>"
        f"<td><code>0x{ft.offset:X}</code></td></tr>"
        "<tr><td>liczba losowanych pozycji: operand instrukcji <code>mov edx, N-1</code></td>"
        f"<td><code>0x{ft.count_instr.value_offset:X}</code></td></tr>"
        "</table>"
        "<p>W kodzie leży <b>N-1</b>, bo gra woła <code>Random(0, N-1)</code>; program pokazuje "
        "i zapisuje zwykłe N. Pozycje powyżej N zostają w pliku nietknięte, więc można je trzymać "
        "jako zapas i włączyć później, podnosząc „Losowane pozycje”.</p>"
        "<p><b>Kiedy ta lista nie działa</b></p>"
        f"<p>W misjach 3 i 7 obu kampanii gra sięga po osobną listę, czyli ustawienie "
        f"„{TITLE_TEMPLE_MISSION}” poniżej. Zmiany zrobione tutaj nie dotyczą tamtych czterech "
        "misji.</p>"
        "<p>Dwie świątynie mają ponadto skład daru wpisany na sztywno. Zawsze jest to taran "
        "i trzech budowniczych, niezależnie od obu list: w 3. misji kampanii chrześcijańskiej na polu "
        "(95, 16) i w 3. misji kampanii pogańskiej na polu (58, 77). Tej listy program nie "
        "udostępnia do zmiany.</p>"
    )


def _details_temple_mission(cmp_offsets=()):
    """Buduje opis wariantu misyjnego; `cmp_offsets` = porownania w kodzie, jesli sa znane."""
    def build(ft):
        rows = "".join(
            f"<tr><td align='center'><code>{value}</code></td><td>{camp}</td>"
            f"<td align='center'>{shown}</td><td><code>{mapfile}</code></td><td>{goal}</td></tr>"
            for value, camp, shown, mapfile, goal in TEMPLE_MISSION_ROWS)
        code = ""
        if cmp_offsets:
            where = ", ".join(f"<code>0x{off:X}</code> (z {v})" for off, v in cmp_offsets)
            code = ("<p><b>Jak to wygląda w kodzie</b></p>"
                    f"<p>Cztery kolejne porównania pola <code>0x222F1</code> na początku kodu "
                    f"tworzącego nowy oddział (<code>0x94AFF</code>): {where}. "
                    "Trafienie któregokolwiek z nich "
                    "przestawia losowanie na tę listę; jeśli żadne nie trafi, gra bierze zwykłą "
                    "listę („Świątynia / miejsce kultu” powyżej).</p>")
        return (
            "<p>Gra ma dwie listy jednostek dla daru „nowy oddział” i wybiera między nimi "
            "<b>po numerze misji</b>, a nie po tym, czyja armia weszła do świątyni. Ta lista "
            "obowiązuje więc tak samo gracza, jak i komputer.</p>"
            "<p><b>Pole gry 0x222F1</b></p>"
            "<p>Trzyma numer misji kampanii <b>liczony od zera</b>: 0–9 to kampania "
            "chrześcijańska (mapy <code>k_*</code>), 10–19 pogańska (mapy <code>p_*</code>), "
            "a <code>-1</code> oznacza grę poza kampanią (potyczka albo gra wieloosobowa). "
            "Numer pokazywany graczowi to <code>numer % 10 + 1</code>, dlatego cztery wartości, "
            "na które patrzy gra, to misje 3 i 7 obu kampanii:</p>"
            + _TBL +
            "<tr><th align='left'>0x222F1</th><th align='left'>Kampania</th>"
            "<th align='left'>Misja</th><th align='left'>Mapa</th>"
            "<th align='left'>Cel misji</th></tr>"
            + rows +
            "</table>"
            + code +
            "<p><b>Gdzie to jest w pliku</b></p>"
            + _TBL +
            "<tr><th align='left'>Co</th><th align='left'>Offset</th></tr>"
            f"<tr><td>lista: {ft.size} pozycji po 4 bajty, ID jednostki jako <code>int</code></td>"
            f"<td><code>0x{ft.offset:X}</code></td></tr>"
            "<tr><td>liczba losowanych pozycji: operand instrukcji <code>mov edx, N-1</code></td>"
            f"<td><code>0x{ft.count_instr.value_offset:X}</code></td></tr>"
            "</table>"
            "<p><b>Pułapka przy tabelach darów</b></p>"
            "<p>W tych samych czterech misjach gracz-człowiek dostaje wyłącznie dar „nowy "
            "oddział” albo „brak efektu”: gra losuje w pętli, aż trafi na jeden z nich. Jeśli "
            "w tabeli darów gracza żaden osiągalny wpis nie ma daru 0 ani 15, pętla nigdy się nie "
            "skończy i gra się zawiesi, dlatego program nie pozwala zapisać takiego pliku.</p>"
            f"<p>{SRC_MISSIONS}</p>"
        )
    return build


DETAILS_GIFT_TABLES = (
    "<p><b>Budowa tabeli</b></p>"
    "<p>Każdy wpis to 24 bajty: <code>{i32 numer daru, i32 waga, i32 obrazek, 3 × wskaźnik na "
    "tekst (PL, EN, DE)}</code>, a lista kończy się wpisem z numerem daru <code>-1</code>. "
    "Cztery tabele leżą w pliku jedna za drugą, dlatego liczby wpisów nie da się zmienić bez "
    "przenoszenia tabel. Edytowalne są numer daru, waga i obrazek każdego istniejącego wpisu.</p>"
    "<p><b>Gdzie to jest w pliku</b></p>"
    "<p>Świątynia (gracz): <code>0x16203C</code> (16 wpisów), świątynia (komputer): "
    "<code>0x16233C</code> (14), miejsce kultu (gracz): <code>0x1621D4</code> (14), "
    "miejsce kultu (komputer): <code>0x1624A4</code> (12). Tabelę wybiera kod wejścia do "
    "świątyni (<code>0x95535</code>) po religii właściciela armii i po tym, czy gracz jest "
    "człowiekiem.</p>"
    "<p><b>Jak liczona jest szansa</b></p>"
    "<p>Losowanie (<code>0x9502C</code>) sumuje wagi wszystkich wpisów (S), bierze "
    "<code>r = Random(0, S-1)</code> i wybiera pierwszy wpis, dla którego suma wag do niego "
    "włącznie jest ≥ r. <b>Oryginalny błąd:</b> <code>r = 0</code> zawsze trafia w pierwszy wpis, "
    "więc ma on o jedną szansę więcej, niż wynika z wagi, a ostatni o jedną mniej "
    "(<code>r</code> nigdy nie dochodzi do S). Kolumna „Szansa” liczy to dokładnie tym samym "
    "wzorem co gra.</p>"
    "<p><b>Numer daru a tekst</b></p>"
    "<p>Tekst należy do wpisu tabeli, a nie do numeru daru. Po zmianie samego efektu komunikat "
    "w grze zostaje stary. Dlatego ostatnia kolumna pokazuje, co gra naprawdę wypisze.</p>"
)


def _details_gift_amounts(ft):
    rows = "".join(
        f"<tr><td align='center'>{a.gift:02d}</td><td>{GIFT_EFFECTS[a.gift][0]}</td>"
        f"<td>{a.label}</td><td align='center'>{a.lo}&nbsp;…&nbsp;{a.hi}</td>"
        f"<td><code>0x{a.instr.value_offset:X}</code></td></tr>"
        for a in sorted(ft.amounts, key=lambda a: (a.gift, a.key)))
    return (
        "<p>Gra nie trzyma tych liczb w żadnej tabeli. Są to <b>operandy instrukcji</b> "
        "w kodzie wykonującym dar (<code>0x950DB</code>: instrukcja wyboru z 16 przypadkami, "
        "po jednym na numer daru) i w kodzie tworzącym nowy oddział (<code>0x94AFF</code>). "
        "Dlatego jedna liczba obowiązuje naraz świątynie, miejsca kultu i zakopane skarby, "
        "a także gracza i komputer.</p>"
        "<p><b>Co dokładnie jest zmieniane</b></p>"
        + _TBL +
        "<tr><th align='left'>Dar</th><th align='left'>Efekt</th><th align='left'>Liczba</th>"
        "<th align='left'>Zakres</th><th align='left'>Offset</th></tr>"
        + rows +
        "</table>"
        "<p><b>Skąd takie zakresy</b></p>"
        "<ul>"
        "<li><b>Złoto</b>: kod pod <code>0x94CCE</code> tworzy oddział ze złotem po 100 sztuk "
        "na jednostkę, a oddział ma najwyżej 10 jednostek, więc powyżej 1000 reszta przepada.</li>"
        "<li><b>Morale</b> mieści się w 0–20, a <b>zdrowie</b> i <b>zmęczenie</b> w 0–100. "
        "Wartości spoza tych zakresów nic by nie dały, bo gra i tak przycina wynik.</li>"
        "<li><b>Nożyki</b> to liczba obrotów pętli dodającej doświadczenie. Trzy nożyki "
        "to jeden poziom, a najwyższy poziom to 3, więc 9 wystarcza na pełne doświadczenie.</li>"
        "</ul>"
        "<p><b>Dodawane czy wpisywane</b></p>"
        "<p>Część liczb gra <i>dodaje</i> do obecnej wartości (morale, zmęczenie daru 2 i 14), "
        "a część <i>wpisuje wprost</i> w pole jednostki (zdrowie i zmęczenie darów 4 i 5). "
        "Podpowiedź przy każdym polu mówi, który to przypadek.</p>"
        f"<p><b>Uwaga na zmęczenie.</b> Kod dodający zmęczenie (<code>0x61C1D</code> dla jednej "
        f"jednostki, <code>0x61CAF</code> dla całego oddziału) dodaje do bajtu ze znakiem "
        f"i dopiero potem przycina wynik do 0–100, więc dodanie więcej niż "
        f"{GiftAmounts.TIREDNESS_SAFE_ADD} przekręca bajt jednostkom, które są już zmęczone, "
        "i zamiast kary daje im zerowe zmęczenie. Ten sam błąd ma oryginalna KSIĘGA PLAG "
        f"z wartością +50. Poprawka „{TITLE_TIREDNESS_ADD}” na zakładce „Poprawki” to naprawia: "
        "po jej włączeniu zmęczenie dochodzi do 100 i się zatrzymuje, więc cały zakres tych "
        "pól działa tak, jak mówi liczba.</p>"
    )


def _details_walls(ft):
    if ft.offset is None:
        where = (
            "<p>Adres tabeli w wersji Windows nie był sprawdzony na pliku, dlatego program szuka "
            "jej po bajtach rozpoznawczych, czyli trzech wytrzymałościach murów, które w obu wersjach "
            "gry są takie same (<code>AB 01 00 00 55 01 .. .. 00 01 .. ..</code>). Jeśli znajdzie "
            "więcej niż jedno takie miejsce, ustawienie zostaje wyłączone.</p>")
    else:
        turns = ", ".join(f"<code>0x{ft.turns_offset(ft.offset, l):X}</code>"
                          for l in sorted(ft.TECH_NEEDED))
        costs = ", ".join(f"<code>0x{ft.cost_offset(ft.offset, l):X}</code>"
                          for l in sorted(ft.TECH_NEEDED))
        where = (
            f"<p>Tabela zaczyna się w pliku pod <code>0x{ft.offset:X}</code>. Program zmienia "
            f"tylko cztery bajty: czas pod {turns} i koszt pod {costs}.</p>")
    return (
        "<p><b>Budowa tabeli</b></p>"
        "<p>Trzy wpisy po 4 bajty, po jednym na poziom muru: "
        "<code>{u16 wytrzymałość x256, u8 tury rozbudowy, u8 koszt rozbudowy}</code>. "
        "Wytrzymałość, czyli mnożnik obrażeń zadawanych murom w bitwie (427, 341, 256), "
        "nie jest zmieniana; służy programowi za znacznik rozpoznawczy tabeli.</p>"
        + where +
        "<p><b>Które bajty gra w ogóle czyta</b></p>"
        "<p>Przy rozbudowie z poziomu L kod rozbudowy murów (<code>0x70DD4</code>) czyta wpis "
        "L+1, a poziom muru jest zawsze mniejszy niż 2, więc gra czyta tylko tury i koszt "
        "wpisów 1 i 2. Tury i koszt wpisu 0 nie są czytane nigdy, bo nie da się „rozbudować do "
        "poziomu 0”. Poza tym jednym miejscem żadne inne nie rusza tych bajtów.</p>"
        "<p><b>Zakresy</b></p>"
        "<p>Koszt to bajt bez znaku, porównywany ze skarbcem zamku również bez znaku, więc całe "
        f"{ft.MIN_COST}–{ft.MAX_COST} działa poprawnie. Kod początku tury (<code>0x6F919</code>) "
        "zmniejsza licznik tur (bajt <code>+0x1AD</code> budynku) o 1 i podnosi "
        f"poziom muru, gdy dojdzie do zera. Dlatego minimum to {ft.MIN_TURNS} tura, a nie 0: "
        "przy zerze gra pobrałaby złoto, licznik nigdy by nie wystartował i mur nigdy by się nie "
        "podniósł.</p>"
        "<p><b>Bez zmiany tekstów</b></p>"
        "<p>Menu „Rozbuduj mury”, inaczej niż menu budowy, nie pokazuje ceny, więc nigdzie "
        "w grze nie zostaje stara liczba i nie trzeba poprawiać żadnego tekstu.</p>"
    )


def _places(n):
    """miejsce / miejsca / miejsc - odmiana po liczbie miejsc w kodzie."""
    if n == 1:
        return "miejscu"
    return "miejscach"


def _details_cost_min(ft):
    n = len(ft.minimums)
    mins = ", ".join(f"<code>0x{i.value_offset:X}</code>" for i in ft.minimums)
    min_label = ("wymagane minimum: operand warunku <code>cmp</code>" if n == 1 else
                 f"wymagane minimum: {n} × operand warunku <code>cmp</code>")
    many = ("" if n == 1 else
            f"<p>Warunek jest sprawdzany w {n} {_places(n)} kodu (gra pyta o to samo w kilku "
            "miejscach); program zapisuje we wszystkich tę samą liczbę.</p>")
    if ft.clamped:
        clamp = ("<p>W tej wersji gry odjęcie jest <b>przycinane</b>, bo gra sama pilnuje, żeby "
                 "jednostka nie zeszła poniżej zera punktów akcji, więc minimum mniejsze od "
                 "kosztu jest tu bezpieczne.</p>")
    else:
        clamp = ("<p>Gra <b>nie pilnuje tu zera</b>: jeśli ustawisz minimum mniejsze od kosztu, "
                 "jednostka z małą liczbą punktów akcji zejdzie poniżej zera, bajt się przekręci "
                 "i zamiast kary dostanie ok. 250 PA. Dlatego program ostrzega przy takim "
                 "ustawieniu.</p>")
    extra = ""
    if ft.key == "ap_join":
        extra = ("<p><b>Skutek uboczny</b></p>"
                 "<p>Tej samej funkcji gra używa przy budowaniu armii na starcie scenariusza, "
                 "dlatego koszt łączenia odejmuje punkty akcji także jednostkom startowym.</p>")
    return (
        "<p><b>Dwie różne liczby</b></p>"
        "<p><b>Koszt</b> to liczba odejmowana od punktów akcji każdej jednostki. "
        "<b>Wymagane minimum</b> to warunek sprawdzany, zanim gra w ogóle pozwoli na operację. "
        "W oryginale obie wynoszą 4, ale są to osobne liczby w osobnych miejscach kodu "
        "i można je ustawić różnie.</p>"
        "<p><b>Gdzie to jest w pliku</b></p>"
        + _TBL +
        "<tr><th align='left'>Co</th><th align='left'>Offset</th></tr>"
        "<tr><td>koszt: operand instrukcji, z której gra bierze tę liczbę</td>"
        f"<td><code>0x{ft.cost.value_offset:X}</code></td></tr>"
        f"<tr><td>{min_label}</td><td>{mins}</td></tr>"
        "</table>"
        + many +
        "<p><b>Co się dzieje przy zbyt małym minimum</b></p>"
        + clamp + extra +
        f"<p>Dopuszczalny zakres obu liczb: {ft.lo}–{ft.hi}.</p>"
    )


def _details_codepatch(how=""):
    """Buduje opis poprawki kodu; `how` = o tym, jak poprawka jest zrobiona.

    `how` moze byc zwyklym tekstem jednego akapitu albo gotowym HTML-em (gdy zaczyna sie od
    znacznika) - wtedy wchodzi bez zmian, zeby zmiescic takze listingi bajtow w <pre>."""
    how_html = how if how.lstrip().startswith("<") else f"<p>{how}</p>"

    def build(ft):
        rows = "".join(
            f"<tr><td><code>0x{off:X}</code></td><td align='center'>{len(new)} B</td>"
            f"<td>{'wolne miejsce (w oryginale same zera)' if not any(orig) else 'bajty oryginalnego pliku'}</td>"
            "</tr>"
            for off, orig, new in ft.sites)
        return (
            "<p><b>Zmieniane miejsca w pliku</b></p>"
            + _TBL +
            "<tr><th align='left'>Offset</th><th align='left'>Długość</th>"
            "<th align='left'>Co tam jest w oryginale</th></tr>"
            + rows +
            "</table>"
            "<p>Przełącznik wpisuje nowe bajty albo przywraca oryginalne, zawsze wszystkie miejsca "
            "naraz. Przy wczytaniu pliku program sprawdza, czy każde z nich jest w tym samym "
            "stanie; jeśli nie, poprawka zostaje wyłączona, żeby nie nadpisać cudzych zmian.</p>"
            + (f"<p><b>Jak to jest zrobione</b></p>{how_html}" if how else "")
        )
    return build

DESC_GIFT_TEXTS = (
    'Tekst pokazywany w okienku daru należy do wpisu tabeli, nie do numeru daru: po zmianie efektu '
    'komunikat zostaje stary, więc trzeba go poprawić tutaj. Wszystkie teksty czterech tabel leżą '
    'w pliku w jednym ciągu, jeden za drugim, dlatego mają wspólny limit miejsca, a nie własną '
    'długość każdy. Program ułoży je przy zapisie od nowa (powtarzające się zapisze raz) '
    'i poprawi wskaźniki wpisów razem z wpisami relokacji, z których loader gry bierze adresy.'
)


def _dos_gift_tables():
    return [
        GiftTable("gifts_christian_human", "Świątynia (gracz)", 0x16203C, DOS_TEXT_DELTA, True),
        GiftTable("gifts_christian_ai", "Świątynia (komputer)", 0x16233C, DOS_TEXT_DELTA, False),
        GiftTable("gifts_pagan_human", "Miejsce kultu (gracz)", 0x1621D4, DOS_TEXT_DELTA, True),
        GiftTable("gifts_pagan_ai", "Miejsce kultu (komputer)", 0x1624A4, DOS_TEXT_DELTA, False),
    ]


_DOS_GIFT_TABLES = _dos_gift_tables()


def _dos_gift_amounts():
    """Liczby darow wpisane w kod wersji DOS (offsety w pliku; kod = adres w pamieci + 0x39400)."""
    return GiftAmounts("gift_amounts", "Siła darów świątyń i miejsc kultu", [
        # Kod tworzacy nowy oddzial 0x94AFF: losowanie 1-5 -> mov edx,5 / mov eax,1
        GiftAmount("troops_max", 0, "najwięcej jednostek", Instr32(0x94B1E, "BA"), 1, 10),
        GiftAmount("troops_min", 0, "najmniej jednostek", Instr32(0x94B23, "B8"), 1, 10),
        # Kod wykonujacy dar 0x950DB, kolejne przypadki instrukcji wyboru
        GiftAmount("tired2", 2, "zmęczenie", Instr32(0x95161, "BA"), -100, 100,
                   note="Wartość dodawana, wynik przycięty do 0–100."),
        GiftAmount("morale3", 3, "morale", Instr32(0x951A8, "BA"), -20, 20,
                   note="Wartość dodawana, wynik przycięty do 0–20."),
        GiftAmount("health4", 4, "zdrowie", Instr(0x95218, "C6400F"), 0, 100,
                   note="Wpisywane wprost w pole zdrowia każdej jednostki (nie dodawane)."),
        GiftAmount("health5", 5, "zdrowie", Instr(0x95289, "C6400F"), 0, 100),
        GiftAmount("tired5", 5, "zmęczenie", Instr(0x95294, "C64010"), 0, 100,
                   note="Wpisywane wprost w pole zmęczenia (nie dodawane)."),
        GiftAmount("exp6", 6, "nożyki", Instr(0x952E6, "837DE0"), 0, 99,
                   note="Liczba obrotów pętli dodającej doświadczenie. 3 nożyki = 1 poziom, "
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
    ], note="Zakresy są dobrane tak, żeby wartość dało się w grze naprawdę osiągnąć, "
            "bo wyżej gra i tak przycina wynik.",
       details=_details_gift_amounts)


PROFILES = {
    "dos_pl": {
        "name": "Clash: wersja DOS (CLASH.EXE, polska)",
        "size": 1481338,
        "features": [
            UnitDwordList("temple", "Świątynia / miejsce kultu", 0x161FFC, 5,
                          Instr(0x94C41, "BA"),
                          note="Losowana jest jedna z aktywnych pozycji (każda z równą szansą).",
                          details=_details_temple),
            UnitDwordList("temple_mission", TITLE_TEMPLE_MISSION, 0x162010, 7,
                          Instr(0x94C13, "BA"), note=NOTE_TEMPLE_MISSION,
                          details=_details_temple_mission(TEMPLE_MISSION_CMP_DOS)),
            *_DOS_GIFT_TABLES,
            GiftTexts("gift_texts", "Teksty darów świątyń i miejsc kultu", _DOS_GIFT_TABLES,
                      DOS_GIFT_POOL, DOS_TEXT_DELTA),
            _dos_gift_amounts(),
            UnitDwordList("port", "Port", 0x163E0C, 12, Instr(0x9952A, "BA")),
            UnitByteSet("forge", "Wymaga kuźni", 0x161F7C, 12),
            UnitByteSet("workshop", "Wymaga warsztatu", 0x161F88, 12),
            TechTable("tech", "Minimalny poziom zaawansowania", 0x15E7D4),
            WallTable("walls", "Mury: koszt i czas rozbudowy", 0x15FDD8,
                      details=_details_walls),
            CostWithMinimum("ap_split", "Dzielenie oddziału / przenoszenie części jednostek",
                            Instr(0x74DAA, "806808"),
                            [Instr(0x74A46, "83F8"), Instr(0x74A9D, "83F8"),
                             Instr(0x751F1, "83F8")],  # kolor krzyzyka na ikonce jednostki (dolny pasek)
                            clamped=False, note=NOTE_SPLIT_ICON,
                            details=_details_cost_min),
            CostWithMinimum("ap_join", "Dołączenie całego oddziału do innego",
                            Instr(0x7485D, "BA"), [Instr(0x7484F, "83F8")], clamped=False,
                            note="Tej samej funkcji gra używa przy budowaniu armii na starcie scenariusza, "
                                 "dlatego koszt łączenia odejmuje PA także jednostkom startowym.",
                            details=_details_cost_min),
            EntrenchBonus("entrench", "Premia do obrony za okopanie", [
                # add dword [ebp-0Ch], N ; jmp short +11h  (zamiast mnozenia x1,25)
                (0x5FE74, "6955F440010000 89D0 C1FA1F C1E208 1BC2 C1F808 8945F4", "8345F4NN EB11"),
                (0x5FF29, "6955F440010000 89D0 C1FA1F C1E208 1BC2 C1F808 8945F4", "8345F4NN EB11"),
            ]),
            CodePatch("no_ground_on_fly", "Naziemne nie dołączają do latających nad niedostępnym terenem", [
                (0x2D54, "1A240F00", "00260F00"),                       # rozmiar obiektu kodu w LE
                (0x74847, "8B45E4E8A5A4FEFF", "E854700C00909090"),      # dolaczanie do oddzialu
                (0x74A92, "8D85FCFCFFFFE857A2FEFF", "E8396E0C00909090909090"),  # przenoszenie do sasiada
                (0x13B820, None,
                 "51525356575583EC6089D689DF89C289E0E8EC79F2FFE8000000005D69C6780500006BCF0E01C88B8DC887F2FF"
                 "030166837804FF74070FB644241DEB2B0FB7088B85F687F2FF833800740F5189F089FAE8E5A7F3FF5985C075"
                 "0E8B850A88F2FF8B0C880FB6440C1E83C4605D5F5E5B5A59C30000000000000000000000000000837DFC0075"
                 "1C538B45E80FBF100FBF58028B45E4E867FFFFFF5B85C0750483C8FFC38B45E4E92A34F2FF00000000000053"
                 "8D85FCFCFFFF8B55F88B5DFCE83EFFFFFF5B85C0750483C8FFC38D85FCFCFFFFE9FE33F2FF"),
            ], description=DESC_NO_GROUND_ON_FLY, details=_details_codepatch(
                'Nowy kod, czyli procedura liczenia kosztu terenu i dwie wstawki wołające ją z miejsc, '
                'w których gra dołącza jednostki do oddziału, leży w wolnym miejscu na końcu '
                'sekcji kodu (<code>0x13B820</code>). Rozmiar sekcji w nagłówku LE '
                '(<code>0x2D54</code>) jest powiększany, żeby DOS/4GW wczytał ją razem z nowym '
                'kodem. Adresy zmiennych gry nowy kod czyta z operandów istniejących instrukcji '
                '(<code>0x2AC03</code>, <code>0x2AC31</code>, <code>0x2AC45</code>), bo DOS/4GW '
                'relokuje dane, a dopisany kod nie ma własnych wpisów relokacji. Źródło '
                'asemblerowe: <code>tools/build_nofly_patch.py</code>.')),
            # bajtowy add + dwa przyciecia -> suma w 32 bitach; bajty: _TIREDNESS_SITES wyzej
            CodePatch("tiredness_add", TITLE_TIREDNESS_ADD, _tiredness_sites(),
                      description=DESC_TIREDNESS_ADD, details=_details_codepatch(HOW_TIREDNESS_ADD)),
            CheatTable("cheats", "Kody", _cheats([
                (0x14CCE3, 6), (0x14CCEA, 10), (0x14CCF5, 10), (0x14CD00, 7), (0x14CD08, 10),
                (0x14CD13, 12), (0x14CD20, 15), (0x14CD30, 7), (0x14CD38, 8), (0x14CD41, 4), (0x14CD46, 4)])),
        ],
    },
    "win95": {
        "name": "Clash: wersja Windows (clash95.exe)",
        "size": 1232384,
        "features": [
            UnitDwordList("temple", "Świątynia / miejsce kultu", 0x113F10, 5, Instr(0x3F17D, "BA"),
                          note="Losowana jest jedna z aktywnych pozycji (każda z równą szansą).",
                          details=_details_temple),
            UnitDwordList("temple_mission", TITLE_TEMPLE_MISSION, 0x113F24, 7,
                          Instr(0x3F149, "BA"), note=NOTE_TEMPLE_MISSION,
                          details=_details_temple_mission()),
            UnitDwordList("port", "Port", 0x115DA8, 12, Instr(0x42B09, "BA")),
            UnitByteSet("forge", "Wymaga kuźni", 0x113E80, 16),
            UnitByteSet("workshop", "Wymaga warsztatu", 0x113E90, 12),
            TechTable("tech", "Minimalny poziom zaawansowania", 0x110768),
            WallTable("walls", "Mury: koszt i czas rozbudowy",
                      note="W tej wersji gry program sam odnajduje tabelę murów w pliku.",
                      details=_details_walls),
            CostWithMinimum("ap_split", "Dzielenie oddziału / przenoszenie części jednostek",
                            Instr(0x225EF, "806808"),
                            [Instr(0x22398, "83F8"), Instr(0x223D0, "83F8"),
                             Instr(0x22AC7, "83F8")],  # kolor krzyzyka na ikonce jednostki (dolny pasek)
                            clamped=False, note=NOTE_SPLIT_ICON,
                            details=_details_cost_min),
            CostWithMinimum("ap_join", "Dołączenie całego oddziału do innego",
                            Instr(0x22141, "BA"), [Instr(0x22124, "83F8")], clamped=True,
                            note="Tej samej funkcji gra używa przy budowaniu armii na starcie scenariusza, "
                                 "dlatego koszt łączenia odejmuje PA także jednostkom startowym.",
                            details=_details_cost_min),
            EntrenchBonus("entrench", "Premia do obrony za okopanie", [
                # add ebx, N ; jmp short +16h
                (0x105DC, "8D149D00000000 01DA C1E206 89D0 C1FA1F C1E208 1BC2 C1F808 89C3", "83C3NN EB16"),
            ]),
            CodePatch("no_ground_on_fly", "Naziemne nie dołączają do latających nad niedostępnym terenem", [
                (0x22076, "85DB0F859D000000", "E8756C0C00909090"),      # dolaczanie do oddzialu: start scenariusza
                (0x2211B, "8B442408E8ECD2FEFF", "E8706B0C0090909090"),  # dolaczanie do oddzialu: sprawdzenie
                (0x223C9, "89E0E840D0FEFF", "E8F2680C009090"),          # przenoszenie do sasiada
                (0xE8C20, None,
                 "515253565783EC6089D689DF89C289E0E8EBA0F2FF69C6780500006BCF0E01C80305E402520066837804FF74"
                 "070FB644241DEB270FB708833D6C55520000740F5189F089FAE806ABF3FF5985C0750C8B0C8D6C4552000FB6"
                 "440C1E83C4605F5E5B5A59C3000000000000000000000000530FBF55000FBF5D028B442410E87EFFFFFF5B85"
                 "C0750483C8FFC38B44240CE95C67F2FF000000000000000000000000538D4424088B9424EC0200008B9C24E8"
                 "020000E848FFFFFF5B85C0750483C8FFC38D442404E92667F2FF00000000000085DB741183C4048B442408E8"
                 "1067F2FFE91F94F3FFC3"),
            ], description=DESC_NO_GROUND_ON_FLY, details=_details_codepatch(
                'Nowy kod leży w wolnym miejscu na końcu sekcji kodu AUTO '
                '(<code>0xE8C20</code> w pliku, adres <code>0x4E9820</code> w pamięci gry).')),
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
