"""Konfigurator pliku .exe gry Clash (PySide6).

Uruchomienie:  python clash_exe_config.py [sciezka/do/CLASH.EXE]
Znaleziska (adresy, rodzaje danych) sa w clash_exe_patches.py.
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QGroupBox, QLabel, QComboBox, QSpinBox, QCheckBox, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QFileDialog,
    QMessageBox, QToolBar, QScrollArea, QPlainTextEdit, QDialog, QDialogButtonBox,
)
from PySide6.QtGui import QAction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clash_exe_patches as cp


def unit_combo(current=None):
    cb = QComboBox()
    for uid in range(cp.UNIT_COUNT):
        cb.addItem(cp.unit_label(uid), uid)
    if current is not None:
        cb.setCurrentIndex(cb.findData(current))
    return cb


def scrolled(widget):
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(widget)
    return sa


def note_label(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: palette(mid);")
    return lbl


# ------------------------------------------------------------------ zakladki
class DwordListBox(QGroupBox):
    """Lista losowanych jednostek (swiatynia / port)."""

    def __init__(self, feature, on_change):
        super().__init__(feature.title)
        self.f = feature
        self.on_change = on_change
        lay = QVBoxLayout(self)
        if feature.note:
            lay.addWidget(note_label(feature.note))
        grid = QGridLayout()
        self.combos = []
        for i in range(feature.size):
            cb = unit_combo()
            cb.currentIndexChanged.connect(self._changed)
            num = QLabel(f"{i + 1}.")
            num.setToolTip(f"offset 0x{feature.offset + 4 * i:X}")
            cb.setMinimumWidth(220)
            grid.addWidget(num, i, 0)
            grid.addWidget(cb, i, 1)
            self.combos.append(cb)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        row = QHBoxLayout()
        row.addWidget(QLabel("Losowane pozycje:"))
        self.active = QSpinBox()
        self.active.setRange(1, feature.size)
        self.active.setToolTip("Gra losuje tylko spośród pierwszych N pozycji "
                               f"(wartość w kodzie pod 0x{feature.count_instr.value_offset:X})")
        self.active.valueChanged.connect(self._changed)
        row.addWidget(self.active)
        row.addStretch(1)
        lay.addLayout(row)
        self.chance = QLabel("")
        lay.addWidget(self.chance)
        self._loading = False

    def load(self, val):
        self._loading = True
        for cb, uid in zip(self.combos, val["units"]):
            cb.setCurrentIndex(cb.findData(uid))
        self.active.setValue(val["active"])
        self._loading = False
        self._update()

    def value(self):
        return {"units": [cb.currentData() for cb in self.combos], "active": self.active.value()}

    def _update(self):
        n = self.active.value()
        for i, cb in enumerate(self.combos):
            cb.setEnabled(i < n)
        counts = {}
        for cb in self.combos[:n]:
            counts[cb.currentData()] = counts.get(cb.currentData(), 0) + 1
        parts = [f"{cp.UNIT_NAMES[u]} {100 * c / n:.0f}%" for u, c in
                 sorted(counts.items(), key=lambda kv: -kv[1])]
        self.chance.setText("Szanse: " + ", ".join(parts))

    def _changed(self, *_):
        if self._loading:
            return
        self._update()
        self.on_change()


class RandomUnitsTab(QWidget):
    def __init__(self, exe, on_change):
        super().__init__()
        lay = QVBoxLayout(self)
        self.boxes = {}
        for key in ("temple", "temple_mission", "port"):
            if key in exe.features:
                box = DwordListBox(exe.features[key], on_change)
                lay.addWidget(box)
                self.boxes[key] = box
        lay.addStretch(1)

    def load(self, exe):
        for k, box in self.boxes.items():
            box.load(exe.get(k))

    def store(self, exe):
        for k, box in self.boxes.items():
            exe.set(k, box.value())


class ProductionTab(QWidget):
    """Kuznia / warsztat / minimalny poziom - tabela jednostek."""
    COL_FORGE, COL_WORKSHOP, COL_LVL_OTHER, COL_LVL_T2 = 2, 3, 4, 5

    def __init__(self, exe, on_change):
        super().__init__()
        self.exe = exe
        self.on_change = on_change
        self._loading = False
        lay = QVBoxLayout(self)
        lay.addWidget(note_label(
            "Zaznacz, które jednostki wymagają kuźni lub warsztatu, i ustaw minimalny poziom "
            "zaawansowania budynku. Poziom 5 oznacza „nigdy” (maksymalny poziom w grze to 4). "
            "Kolumny poziomu odpowiadają dwóm typom budynków: typ 2 w rekordzie budynku to wg "
            "DAT_FORMAT.md zamek, typ 1 – twierdza."))
        self.counter = QLabel("")
        lay.addWidget(self.counter)
        self.table = QTableWidget(cp.UNIT_COUNT, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Jednostka", "Kuźnia", "Warsztat", "Poziom – twierdza (typ 1)", "Poziom – zamek (typ 2)"])
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for c in (0, 2, 3, 4, 5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.checks = {}
        self.spins = {}
        tech = exe.features.get("tech")
        for uid in range(cp.UNIT_COUNT):
            self.table.setItem(uid, 0, QTableWidgetItem(f"{uid:02X}"))
            self.table.setItem(uid, 1, QTableWidgetItem(cp.UNIT_NAMES[uid]))
            for col, key in ((self.COL_FORGE, "forge"), (self.COL_WORKSHOP, "workshop")):
                cb = QCheckBox()
                cb.setEnabled(key in exe.features)
                cb.toggled.connect(self._changed)
                w = QWidget()
                l = QHBoxLayout(w)
                l.setContentsMargins(0, 0, 0, 0)
                l.setAlignment(Qt.AlignCenter)
                l.addWidget(cb)
                self.table.setCellWidget(uid, col, w)
                self.checks[(uid, key)] = cb
            for col, t2 in ((self.COL_LVL_OTHER, False), (self.COL_LVL_T2, True)):
                sp = QSpinBox()
                sp.setRange(0, 7)
                sp.setSpecialValueText("0")
                sp.setEnabled(tech is not None)
                if tech:
                    sp.setToolTip(f"offset 0x{tech.addr(uid, t2):X}")
                sp.valueChanged.connect(self._changed)
                self.table.setCellWidget(uid, col, sp)
                self.spins[(uid, t2)] = sp
        for item in (self.table.item(r, c) for r in range(cp.UNIT_COUNT) for c in (0, 1)):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        lay.addWidget(self.table)

    def load(self, exe):
        self._loading = True
        for key in ("forge", "workshop"):
            sel = set(exe.get(key)) if key in exe.features else set()
            for uid in range(cp.UNIT_COUNT):
                self.checks[(uid, key)].setChecked(uid in sel)
        if "tech" in exe.features:
            for uid, (other, t2) in exe.get("tech").items():
                self.spins[(uid, False)].setValue(other)
                self.spins[(uid, True)].setValue(t2)
        self._loading = False
        self._update_counter()

    def selected(self, key):
        return [uid for uid in range(cp.UNIT_COUNT) if self.checks[(uid, key)].isChecked()]

    def _update_counter(self):
        parts = []
        ok = True
        for key, name in (("forge", "kuźnia"), ("workshop", "warsztat")):
            if key in self.exe.features:
                n, mx = len(self.selected(key)), self.exe.features[key].max_units
                parts.append(f"{name}: {n} / {mx}")
                ok &= n <= mx
        self.counter.setText("Zajętość list: " + ", ".join(parts) +
                             ("" if ok else "  – za dużo jednostek, lista się nie zmieści!"))
        self.counter.setStyleSheet("" if ok else "color: #c0392b; font-weight: bold;")
        return ok

    def _changed(self, *_):
        if self._loading:
            return
        self._update_counter()
        self.on_change()

    def valid(self):
        return self._update_counter()

    def store(self, exe):
        for key in ("forge", "workshop"):
            if key in exe.features:
                # zachowaj kolejnosc oryginalnej listy, nowe dopisz na koncu
                old = exe.get(key)
                sel = self.selected(key)
                exe.set(key, [u for u in old if u in sel] + [u for u in sel if u not in old])
        if "tech" in exe.features:
            exe.set("tech", {uid: (self.spins[(uid, False)].value(), self.spins[(uid, True)].value())
                             for uid in range(cp.UNIT_COUNT)})


def turns_word(n):
    """tura / tury / tur - zeby suffiks w polu liczbowym nie brzmial jak '1 tur'."""
    if n == 1:
        return "tura"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "tury"
    return "tur"


class WallsTab(QWidget):
    """Mury: koszt i czas rozbudowy (tabela murow)."""
    EDITABLE = (1, 2)      # poziomy, do ktorych da sie rozbudowac mur (gra pokazuje je jako 2 i 3)

    def __init__(self, exe, on_change):
        super().__init__()
        self.ft = exe.features.get("walls")
        self.on_change = on_change
        self._loading = False
        self.base = self.ft.locate(exe.data) if self.ft else None
        self.turns, self.costs = {}, {}
        lay = QVBoxLayout(self)
        lay.addWidget(note_label(
            "Mur ma trzy poziomy – gra pokazuje je jako 1, 2 i 3 (zamek zaczyna na 1., twierdza na 2.). "
            "„Rozbuduj mury” w zamku podnosi mur o jeden poziom: gra pobiera koszt ze skarbca tego zamku "
            "i ustawia licznik tur. Licznik spada o 1 na początku każdej tury właściciela zamku, a gdy dojdzie do zera, "
            "poziom muru rośnie. Podczas trwającej rozbudowy nie można zlecić kolejnej, ale można ją zlecić "
            "już w tej turze, w której poprzednia się skończyła. Oryginalnie czasy to 5 i 10 tur, a oba koszty "
            "to 1 sztuka złota."))
        box = QGroupBox("Rozbudowa murów")
        bl = QVBoxLayout(box)
        grid = QGridLayout()
        for col, text in enumerate(("Rozbudowa", "Wymaga technologii", "Czas", "Koszt")):
            head = QLabel(text)
            head.setStyleSheet("font-weight: bold;")
            grid.addWidget(head, 0, col)
        for row, lvl in enumerate(self.EDITABLE, start=1):
            grid.addWidget(QLabel(f"do {lvl + 1}. poziomu"), row, 0)
            tech = QLabel(str(cp.WallTable.TECH_NEEDED[lvl]))
            tech.setToolTip("Building_CanUpgradeWall: poziom muru musi być mniejszy niż technologia zamku − 1")
            grid.addWidget(tech, row, 1)
            t = QSpinBox()
            t.setRange(cp.WallTable.MIN_TURNS, cp.WallTable.MAX_TURNS)
            t.setSuffix(" tur")
            t.setToolTip("Licznik tur zamku. Minimum to 1 – przy 0 gra pobrałaby złoto, licznik nigdy by nie "
                         "wystartował i mur nigdy by się nie podniósł."
                         + (f"\noffset 0x{self.ft.turns_offset(self.base, lvl):X}" if self.base is not None else ""))
            c = QSpinBox()
            c.setRange(cp.WallTable.MIN_COST, cp.WallTable.MAX_COST)
            c.setSuffix(" szt. złota")
            c.setToolTip("Koszt to jeden bajt bez znaku, więc maksimum to 255 sztuk złota."
                         + (f"\noffset 0x{self.ft.cost_offset(self.base, lvl):X}" if self.base is not None else ""))
            for sp in (t, c):
                sp.setMinimumWidth(130)
                sp.valueChanged.connect(self._changed)
            grid.addWidget(t, row, 2)
            grid.addWidget(c, row, 3)
            self.turns[lvl], self.costs[lvl] = t, c
        grid.setColumnStretch(4, 1)
        bl.addLayout(grid)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        bl.addWidget(self.summary)
        self.strength = note_label("")
        bl.addWidget(self.strength)
        if self.ft:
            where = f"Tabela murów w pliku: 0x{self.base:X}. " if self.base is not None else ""
            bl.addWidget(note_label(
                where + "Czas i koszt czyta tylko funkcja rozbudowy murów (0x379D4), a wywołuje ją zarówno "
                "menu zamku, jak i komputerowy przeciwnik (reguła „rozbudowa_murow”), więc nowe wartości "
                "obowiązują też jego. Komputer nie ma tu zniżki, jaką ma na licencje i budynki, i próbuje "
                "rozbudowy, gdy tylko może – przy wysokiej cenie będzie po prostu czekał, aż uzbiera złoto."
                + (self.ft.note or "")))
        else:
            box.setEnabled(False)
        lay.addWidget(box)
        if not self.ft:
            lay.addWidget(note_label("Niedostępne: " + exe.problems.get("walls", "brak w tej wersji gry")))
        lay.addStretch(1)

    def _update(self):
        for lvl in self.EDITABLE:
            sp = self.turns[lvl]
            sp.setSuffix(" " + turns_word(sp.value()))
        t = sum(self.turns[lvl].value() for lvl in self.EDITABLE)
        g = sum(self.costs[lvl].value() for lvl in self.EDITABLE)
        parts = ["Z 1. na 3. poziom muru: "
                 + " + ".join(str(self.turns[lvl].value()) for lvl in self.EDITABLE)
                 + f" = {t} {turns_word(t)} i "
                 + " + ".join(str(self.costs[lvl].value()) for lvl in self.EDITABLE)
                 + f" = {g} szt. złota (zamek potrzebuje do tego 3. poziomu technologicznego)."]
        if any(self.costs[lvl].value() == 0 for lvl in self.EDITABLE):
            parts.append("Koszt 0 oznacza rozbudowę za darmo.")
        self.summary.setText(" ".join(parts))

    def _changed(self, *_):
        self._update()
        if not self._loading:
            self.on_change()

    def load(self, exe):
        if not self.ft:
            return
        self._loading = True
        v = exe.get("walls")
        for lvl in self.EDITABLE:
            self.turns[lvl].setValue(v["turns"][lvl])
            self.costs[lvl].setValue(v["cost"][lvl])
        self.strength.setText(
            "Wytrzymałość murów (mnożnik obrażeń zadawanych murom w bitwie, ×/256 – im mniej, tym mocniejszy mur): "
            + ", ".join(f"{lvl + 1}. poziom {s}" for lvl, s in enumerate(v["strength"]))
            + ". Tego pola tabeli program nie zmienia.")
        self._loading = False
        self._update()

    def store(self, exe):
        if not self.ft:
            return
        exe.set("walls", {
            "turns": [0] + [self.turns[lvl].value() for lvl in self.EDITABLE],
            "cost": [0] + [self.costs[lvl].value() for lvl in self.EDITABLE],
        })


class ValuesTab(QWidget):
    """Punkty akcji: koszt i wymagane minimum osobno."""

    def __init__(self, exe, on_change):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(note_label(
            "Koszt – ile PA traci każda jednostka. Minimum – ile PA musi mieć każda jednostka, "
            "żeby gra w ogóle pozwoliła na operację. Oryginalnie oba wynoszą 4."))
        self.rows = {}
        for key in ("ap_split", "ap_join"):
            ft = exe.features.get(key)
            if not ft:
                continue
            box = QGroupBox(ft.title)
            bl = QVBoxLayout(box)
            if ft.note:
                bl.addWidget(note_label(ft.note))
            form = QFormLayout()
            cost, mn = QSpinBox(), QSpinBox()
            for sp in (cost, mn):
                sp.setRange(ft.lo, ft.hi)
                sp.setSuffix(" PA")
                sp.valueChanged.connect(on_change)
                sp.valueChanged.connect(self._validate)
            cost.setToolTip(f"offset 0x{ft.cost.value_offset:X}")
            mn.setToolTip("offset " + ", ".join(f"0x{i.value_offset:X}" for i in ft.minimums))
            form.addRow("Koszt:", cost)
            form.addRow("Wymagane minimum:", mn)
            bl.addLayout(form)
            warn = QLabel("")
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #c0392b;")
            bl.addWidget(warn)
            lay.addWidget(box)
            self.rows[key] = (ft, cost, mn, warn)
        lay.addStretch(1)

    def _validate(self, *_):
        ok = True
        for ft, cost, mn, warn in self.rows.values():
            if not ft.clamped and mn.value() < cost.value():
                warn.setText("Minimum mniejsze niż koszt: jednostka z małą liczbą PA zejdzie poniżej zera "
                             "i dostanie ok. 250 PA (gra tu nie pilnuje zera).")
                ok = False
            else:
                warn.setText("")
        return ok

    def valid(self):
        return self._validate()

    def load(self, exe):
        for key, (ft, cost, mn, warn) in self.rows.items():
            v = exe.get(key)
            for sp, x in ((cost, v["cost"]), (mn, v["min"])):
                sp.blockSignals(True)
                sp.setValue(x)
                sp.blockSignals(False)
        self._validate()

    def store(self, exe):
        for key, (ft, cost, mn, warn) in self.rows.items():
            exe.set(key, {"cost": cost.value(), "min": mn.value()})


class CombatTab(QWidget):
    """Okopanie: oryginalne x1,25 albo staly bonus."""

    def __init__(self, exe, on_change):
        super().__init__()
        self.ft = exe.features.get("entrench")
        self.on_change = on_change
        lay = QVBoxLayout(self)
        box = QGroupBox("Okopanie – premia do obrony")
        bl = QVBoxLayout(box)
        bl.addWidget(note_label(
            "Oryginalnie gra mnoży obronę okopanej jednostki przez 1,25 (z zaokrągleniem w dół): "
            "obrona 1–3 nic nie zyskuje, 4–7 dostaje +1, 8–11 +2, 12–15 +3. "
            "Zamiast tego można ustawić stałą premię dla wszystkich jednostek."))
        self.orig = QCheckBox("Oryginalna reguła (obrona × 1,25)")
        self.n = QSpinBox()
        self.n.setRange(0, 15)
        self.n.setPrefix("+")
        self.n.setSuffix(" do obrony")
        row = QHBoxLayout()
        row.addWidget(QLabel("Stała premia:"))
        row.addWidget(self.n)
        row.addStretch(1)
        bl.addWidget(self.orig)
        bl.addLayout(row)
        self.preview = QLabel("")
        self.preview.setWordWrap(True)
        bl.addWidget(self.preview)
        if self.ft:
            bl.addWidget(note_label("Zmieniany kod: " + ", ".join(f"0x{s[0]:X}" for s in self.ft.sites)))
        else:
            box.setEnabled(False)
        lay.addWidget(box)
        lay.addStretch(1)
        self.orig.toggled.connect(self._changed)
        self.n.valueChanged.connect(self._changed)
        self._loading = False

    def value(self):
        return {"mode": "orig" if self.orig.isChecked() else "fixed", "n": self.n.value()}

    def _update(self):
        self.n.setEnabled(not self.orig.isChecked())
        v = self.value()
        parts = [f"{d}→{d + cp.EntrenchBonus.bonus(d, v)}" for d in (1, 3, 4, 7, 8, 12, 15)]
        self.preview.setText("Obrona po okopaniu: " + ", ".join(parts))

    def _changed(self, *_):
        self._update()
        if not self._loading:
            self.on_change()

    def load(self, exe):
        if not self.ft:
            return
        self._loading = True
        v = exe.get("entrench")
        self.orig.setChecked(v["mode"] == "orig")
        self.n.setValue(v["n"])
        self._loading = False
        self._update()

    def store(self, exe):
        if self.ft:
            exe.set("entrench", self.value())


class FixesTab(QWidget):
    """Poprawki kodu gry (CodePatch) - kazda jako przelacznik."""

    def __init__(self, exe, on_change):
        super().__init__()
        self.on_change = on_change
        self._loading = False
        self.boxes = {}
        lay = QVBoxLayout(self)
        for ft in exe.profile["features"]:
            if getattr(ft, "kind", None) != "codepatch":
                continue
            box = QGroupBox(ft.title)
            bl = QVBoxLayout(box)
            if ft.description:
                bl.addWidget(QLabel(ft.description, wordWrap=True))
            cb = QCheckBox("Włączona")
            bl.addWidget(cb)
            if ft.key in exe.features:
                where = ", ".join(f"0x{off:X}" for off, *_ in ft.sites)
                bl.addWidget(note_label(f"Zmieniane miejsca w pliku: {where}. " + ft.note))
                cb.toggled.connect(self._changed)
                self.boxes[ft.key] = cb
            else:
                cb.setEnabled(False)
                bl.addWidget(note_label("Niedostępna: " + exe.problems[ft.key]))
            lay.addWidget(box)
        lay.addStretch(1)

    def _changed(self, *_):
        if not self._loading:
            self.on_change()

    def load(self, exe):
        self._loading = True
        for key, cb in self.boxes.items():
            cb.setChecked(exe.get(key))
        self._loading = False

    def store(self, exe):
        for key, cb in self.boxes.items():
            exe.set(key, cb.isChecked())


class CheatsTab(QWidget):
    def __init__(self, exe, on_change):
        super().__init__()
        self.ft = exe.features.get("cheats")
        lay = QVBoxLayout(self)
        lay.addWidget(note_label(
            "W grze: przytrzymaj C, puść, wpisz kod i naciśnij Enter (w wersji niemieckiej klawisz P "
            "i zamienione Y/Z). Dozwolone znaki: litery a-z, cyfry, spacja i ; ' , . - =. "
            "Nowy kod nie może być dłuższy niż oryginalny."))
        self.edits = []
        self.warn = QLabel("")
        self.warn.setStyleSheet("color: #c0392b;")
        if self.ft:
            form = QFormLayout()
            for off, ln, info in self.ft.entries:
                ed = QLineEdit()
                ed.setMaxLength(ln)
                ed.setToolTip(f"offset 0x{off:X}, maks. {ln} znaków")
                ed.textEdited.connect(lambda _t, e=ed: self._sanitize(e))
                ed.textChanged.connect(on_change)
                ed.textChanged.connect(self._validate)
                lbl = QLabel(info)
                lbl.setWordWrap(True)
                form.addRow(ed, lbl)
                self.edits.append(ed)
            lay.addLayout(form)
        lay.addWidget(self.warn)
        lay.addStretch(1)

    def _sanitize(self, ed):
        txt = "".join(c for c in ed.text().lower() if c in cp.CHEAT_CHARS)
        if txt != ed.text():
            pos = ed.cursorPosition()
            ed.setText(txt)
            ed.setCursorPosition(min(pos, len(txt)))

    def _validate(self, *_):
        codes = [e.text() for e in self.edits]
        msgs = []
        if any(not c for c in codes):
            msgs.append("Pusty kod – gra nie dopasuje go do niczego.")
        dup = {c for c in codes if c and codes.count(c) > 1}
        if dup:
            msgs.append("Powtórzone kody (zadziała tylko pierwszy): " + ", ".join(sorted(dup)))
        self.warn.setText(" ".join(msgs))
        return not msgs

    def valid(self):
        return self._validate()

    def load(self, exe):
        if self.ft:
            for ed, code in zip(self.edits, exe.get("cheats")):
                ed.blockSignals(True)
                ed.setText(code)
                ed.blockSignals(False)
            self._validate()

    def store(self, exe):
        if self.ft:
            exe.set("cheats", [e.text() for e in self.edits])


# ------------------------------------------------------------------ okno
class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.exe = None
        self.dirty = False
        self.resize(900, 760)
        tb = QToolBar("Plik")
        self.addToolBar(tb)
        for text, slot in (("Otwórz…", self.open_dialog), ("Zapisz", self.save),
                           ("Zapisz jako…", self.save_as), ("Pokaż zmiany", self.show_changes),
                           ("Cofnij niezapisane", self.reload),
                           ("Przywróć oryginał (.bak)", self.restore_backup)):
            act = QAction(text, self)
            act.triggered.connect(slot)
            tb.addAction(act)
            setattr(self, "act_" + slot.__name__, act)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._set_title()
        self._enable(False)
        if path:
            self.load(path)
        else:
            self.tabs.addTab(QLabel("  Otwórz plik CLASH.EXE (DOS, polska wersja) albo clash95.exe."), "Start")

    def _enable(self, on):
        for name in ("save", "save_as", "show_changes", "reload", "restore_backup"):
            getattr(self, "act_" + name).setEnabled(on)

    def _set_title(self):
        name = os.path.basename(self.exe.path) if self.exe else "brak pliku"
        self.setWindowTitle(f"Konfigurator Clash – {name}{' *' if self.dirty else ''}")

    def _mark(self, *_):
        if not self.dirty:
            self.dirty = True
            self._set_title()

    # --- plik
    def open_dialog(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Plik gry", "", "Pliki exe (*.exe *.EXE);;Wszystkie (*.*)")
        if path:
            self.load(path)

    def load(self, path):
        try:
            exe = cp.ExeFile(path)
        except Exception as e:
            QMessageBox.critical(self, "Nie można otworzyć", str(e))
            return
        self.exe = exe
        self.dirty = False
        self.tabs.clear()
        self.pages = [RandomUnitsTab(exe, self._mark), ProductionTab(exe, self._mark),
                      WallsTab(exe, self._mark), ValuesTab(exe, self._mark), CombatTab(exe, self._mark),
                      FixesTab(exe, self._mark), CheatsTab(exe, self._mark)]
        titles = ["Świątynia i port", "Kuźnia, warsztat, poziomy", "Mury", "Punkty akcji", "Walka",
                  "Poprawki", "Kody"]
        for page, title in zip(self.pages, titles):
            page.load(exe)
            self.tabs.addTab(page if isinstance(page, ProductionTab) else scrolled(page), title)
        info = QPlainTextEdit()
        info.setReadOnly(True)
        lines = [exe.profile["name"], exe.path, ""]
        for ft in exe.profile["features"]:
            state = "OK" if ft.key in exe.features else "WYŁĄCZONE – " + exe.problems[ft.key]
            lines.append(f"{ft.title}: {state}")
        info.setPlainText("\n".join(lines))
        self.tabs.addTab(info, "Informacje")
        self._enable(True)
        self.dirty = False
        self._set_title()
        if exe.problems:
            QMessageBox.warning(self, "Uwaga",
                                "Część ustawień wyłączono, bo bajty w pliku nie wyglądają jak w oryginale:\n\n"
                                + "\n".join(exe.problems.values()))
        self.statusBar().showMessage(exe.profile["name"])

    def _collect(self):
        for page in self.pages:
            if hasattr(page, "valid") and not page.valid():
                QMessageBox.warning(self, "Popraw dane", "Na jednej z zakładek są błędy (zaznaczone na czerwono).")
                return False
        for page in self.pages:
            page.store(self.exe)
        return True

    def _changes_text(self):
        ch = self.exe.changes()
        if not ch:
            return "Brak zmian względem pliku na dysku."
        lines = [f"Zmienione bajty: {len(ch)}", ""]
        lines += [f"0x{o:06X}: {a:02X} -> {b:02X}" for o, a, b in ch[:300]]
        if len(ch) > 300:
            lines.append("…")
        return "\n".join(lines)

    def show_changes(self):
        if not self.exe or not self._collect():
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Zmiany do zapisania")
        l = QVBoxLayout(dlg)
        t = QPlainTextEdit(self._changes_text())
        t.setReadOnly(True)
        l.addWidget(t)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        l.addWidget(bb)
        dlg.resize(420, 480)
        dlg.exec()

    def save(self, path=None):
        if not self.exe or not self._collect():
            return
        n = len(self.exe.changes())
        target = path or self.exe.path
        had_backup = os.path.exists(target + ".bak")
        try:
            self.exe.save(target)
        except OSError as e:
            QMessageBox.critical(self, "Błąd zapisu", str(e))
            return
        self.dirty = False
        self._set_title()
        msg = f"Zapisano {n} zmienionych bajtów do {target}."
        if not had_backup and os.path.exists(target + ".bak"):
            msg += f" Kopia oryginału: {os.path.basename(target)}.bak"
        self.statusBar().showMessage(msg)

    def save_as(self):
        if not self.exe:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako", self.exe.path, "Pliki exe (*.exe *.EXE)")
        if path:
            self.save(path)

    def reload(self):
        if self.exe:
            self.load(self.exe.path)

    def restore_backup(self):
        if not self.exe:
            return
        bak = self.exe.path + ".bak"
        if not os.path.exists(bak):
            QMessageBox.information(self, "Brak kopii", "Kopia .bak powstaje przy pierwszym zapisie.")
            return
        if QMessageBox.question(self, "Przywrócić?", f"Nadpisać {self.exe.path} kopią {bak}?") != QMessageBox.Yes:
            return
        import shutil
        shutil.copy2(bak, self.exe.path)
        self.load(self.exe.path)
        self.statusBar().showMessage("Przywrócono oryginał z kopii .bak")

    def _confirm_discard(self):
        if not self.dirty:
            return True
        return QMessageBox.question(self, "Niezapisane zmiany", "Porzucić niezapisane zmiany?") == QMessageBox.Yes

    def closeEvent(self, ev):
        if self._confirm_discard():
            ev.accept()
        else:
            ev.ignore()


def main():
    app = QApplication(sys.argv)
    win = MainWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
