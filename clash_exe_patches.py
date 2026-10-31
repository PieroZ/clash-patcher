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
            UnitDwordList("port", "Port", 0x163E0C, 12, Instr(0x9952A, "BA")),
            UnitByteSet("forge", "Wymaga kuźni", 0x161F7C, 12),
            UnitByteSet("workshop", "Wymaga warsztatu", 0x161F88, 12),
            TechTable("tech", "Minimalny poziom zaawansowania", 0x15E7D4),
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
