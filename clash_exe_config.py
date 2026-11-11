"""Konfigurator pliku .exe gry Clash (PySide6).

Uruchomienie:  python clash_exe_config.py [sciezka/do/CLASH.EXE]
Znaleziska (adresy, rodzaje danych) sa w clash_exe_patches.py.
"""
import os
import sys
import textwrap
from html import escape

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QGroupBox, QLabel, QComboBox, QSpinBox, QCheckBox, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QFileDialog,
    QMessageBox, QToolBar, QScrollArea, QPlainTextEdit, QDialog, QDialogButtonBox,
    QToolButton, QTextBrowser, QStyle, QStyleOptionGroupBox,
)
from PySide6.QtGui import QAction, QColor, QPalette

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clash_exe_patches as cp
from version import __version__

APP_NAME = "Clash Patcher"


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


def secondary_style():
    """Styl szarego tekstu pomocniczego.

    W jasnym motywie to palette(mid), ale w ciemnym ten kolor jest prawie taki sam jak tlo
    (Windows 11: #282828 na #1e1e1e), wiec tam bierzemy kolor posredni miedzy tekstem a tlem."""
    pal = QApplication.palette()
    fg, bg = pal.color(QPalette.WindowText), pal.color(QPalette.Window)
    if bg.lightness() >= fg.lightness():
        return "color: palette(mid);"
    mix = QColor(*(round(0.6 * f + 0.4 * b) for f, b in zip(fg.getRgb()[:3], bg.getRgb()[:3])))
    return f"color: {mix.name()};"


def note_label(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(secondary_style())
    return lbl


class InfoDialog(QDialog):
    """Okno "szczegoly techniczne": offsety, instrukcje i nazwy funkcji gry."""

    def __init__(self, parent, title, html):
        super().__init__(parent)
        self.setWindowTitle("Szczegóły techniczne: " + title)
        self.resize(700, 560)
        lay = QVBoxLayout(self)
        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setHtml(html)
        lay.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("Zamknij")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)


def paras(*texts):
    """Zwykly tekst -> akapity HTML okna opisu (puste pomijane)."""
    return "".join(f"<p>{escape(t)}</p>" for t in texts if t)


def info_button(title, html, label=""):
    """Ikona "i" otwierajaca okno opisu. None, gdy nie ma czego pokazac."""
    if not html:
        return None
    btn = QToolButton()
    btn.setIcon(btn.style().standardIcon(QStyle.SP_MessageBoxInformation))
    btn.setAutoRaise(True)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip("Opis i szczegóły techniczne: co to zmienia w grze, offsety w pliku, instrukcje")
    btn.setAccessibleName("Opis: " + title)
    if label:
        btn.setText(" " + label)
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    btn.clicked.connect(lambda: InfoDialog(btn.window(), title, html).exec())
    return btn


class _InfoCorner(QObject):
    """Trzyma ikone "i" w prawym gornym rogu ramki, na wysokosci jej tytulu."""

    def __init__(self, box, btn):
        super().__init__(box)          # zyje tak dlugo jak ramka
        self.box, self.btn = box, btn
        btn.setParent(box)
        box.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest):
            self.btn.adjustSize()
            # tuz za tytulem ramki, a nie przy prawej krawedzi: ramka bywa szersza
            # niz widoczny obszar (zakladka w przewijanym panelu) i ikona by uciekla
            opt = QStyleOptionGroupBox()
            self.box.initStyleOption(opt)
            label = self.box.style().subControlRect(
                QStyle.CC_GroupBox, opt, QStyle.SC_GroupBoxLabel, self.box)
            self.btn.move(label.right() + 6,
                          label.center().y() - self.btn.height() // 2)
            self.btn.raise_()
        return False


def pin_info(box, title, html):
    """Przypina ikone "i" do rogu ramki zamiast zajmowac osobny wiersz."""
    btn = info_button(title, html)
    if btn is not None:
        _InfoCorner(box, btn)
    return btn


def pin_feature_info(box, ft, intro=None, extra=""):
    """pin_info dla znaleziska: opis + szczegoly techniczne, wszystko w oknie."""
    note = ft.note if intro is None else intro
    return pin_info(box, ft.title, paras(note) + extra + cp.feature_details(ft))


def info_row(title, html, label=""):
    """Wiersz z ikona "i" przy prawej krawedzi. Caly opis jest w oknie, nie przy polu."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.addStretch(1)
    btn = info_button(title, html, label)
    if btn is not None:
        row.addWidget(btn, 0, Qt.AlignTop)
    return row


# ------------------------------------------------------------------ zakladki
class DwordListBox(QGroupBox):
    """Lista losowanych jednostek (swiatynia / port)."""

    def __init__(self, feature, on_change):
        super().__init__(feature.title)
        self.f = feature
        self.on_change = on_change
        lay = QVBoxLayout(self)
        pin_feature_info(self, feature)
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


def fit_table_height(table):
    """Tabela pokazuje wszystkie wiersze naraz - przewija ja dopiero zakladka.
    Wiersze maja zwykla wysokosc (jak w tabeli kuzni): bez resizeRowsToContents, bo przed pokazaniem
    okna kolumna tekstu jest waska i zawiniety tekst robil wiersze kilka razy wyzsze.
    Bez gornego ograniczenia: gdy wyliczona wysokosc okaze sie za mala, zostanie puste miejsce,
    a nie obciety wiersz."""
    h = table.horizontalHeader().height() + 2 * table.frameWidth() + 2
    for r in range(table.rowCount()):
        h += table.rowHeight(r)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    table.setMinimumHeight(h)


def read_only_item(text=""):
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


def pct(part, total):
    if total <= 0:
        return "–"
    return f"{100.0 * part / total:.1f}".replace(".", ",") + "%"


class GiftTextPane(QWidget):
    """Jeden tekst daru: pole do pisania, podglad zlamania wierszy i ostrzezenia."""

    def __init__(self, on_change):
        super().__init__()
        self.on_change = on_change
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        self.edit = QPlainTextEdit()
        self.edit.setTabChangesFocus(True)
        self.edit.textChanged.connect(self._changed)
        lay.addWidget(self.edit, 3)
        lay.addWidget(QLabel("Tak gra złamie wiersze w okienku daru:"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        lay.addWidget(self.preview, 2)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.warn = QLabel("")
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet("color: #b9770e;")
        lay.addWidget(self.warn)
        self.err = QLabel("")
        self.err.setWordWrap(True)
        self.err.setStyleSheet("color: #c0392b;")
        lay.addWidget(self.err)

    def text(self):
        return self.edit.toPlainText()

    def load(self, text):
        self._loading = True
        self.edit.setPlainText(text)
        self._loading = False
        self.update_view()

    def errors(self, with_sprite=True):
        return cp.gift_text_problems(self.text(), with_sprite)[0]

    def update_view(self, with_sprite=True):
        raw, _ = cp.mazovia_encode(self.text())
        lines, _ = cp.gift_wrap(raw)
        out = []
        for i, ln in enumerate(lines):
            mark = " ←" if i >= cp.GIFT_LINES_CLEAN else ""
            out.append(f"{i + 1}. {cp.mazovia_decode(ln)}{mark}")
        self.preview.setPlainText("\n".join(out))
        widest = max((cp.gift_text_width(ln) for ln in lines), default=0)
        self.info.setText(f"{len(lines)} {cp.lines_word(len(lines))}, najszerszy "
                          f"{widest} z {cp.GIFT_TEXT_WIDTH} px, {len(raw)} B.")
        errors, warnings = cp.gift_text_problems(self.text(), with_sprite)
        self.warn.setText(" ".join(warnings))
        self.warn.setVisible(bool(warnings))
        self.err.setText(" ".join(errors))
        self.err.setVisible(bool(errors))

    def _changed(self):
        if not self._loading:
            self.on_change()


class GiftTextDialog(QDialog):
    """Edytor obu tekstow jednego wpisu tabeli darow."""

    def __init__(self, parent, title, texts, original, with_sprite, used, pool):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.original = original
        self.with_sprite = with_sprite
        self.used, self.pool = used, pool
        lay = QVBoxLayout(self)
        lay.addLayout(info_row(title, paras(
            "Zakładka „Tekst polski” to tekst, który zobaczy gracz w polskiej wersji gry "
            "(numer języka 0). Zakładka „Tekst angielski” w polskiej wersji nigdy się nie "
            "pokaże, ale zajmuje miejsce w tej samej puli bajtów, więc jego skrócenie zwalnia "
            "miejsce na dłuższy tekst polski.",
            "Enter wymusza złamanie wiersza, a znak % jest zakazany."), label="Opis"))
        self.tabs = QTabWidget()
        self.panes = [GiftTextPane(self._changed), GiftTextPane(self._changed)]
        self.tabs.addTab(self.panes[0], "Tekst polski")
        self.tabs.addTab(self.panes[1], "Tekst angielski")
        lay.addWidget(self.tabs)
        self.budget = QLabel("")
        self.budget.setWordWrap(True)
        lay.addWidget(self.budget)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.restore = bb.addButton("Przywróć", QDialogButtonBox.ResetRole)
        self.restore.setToolTip("Wstawia teksty z pliku na dysku")
        self.restore.clicked.connect(self._restore)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.ok = bb.button(QDialogButtonBox.Ok)
        lay.addWidget(bb)
        for pane, text in zip(self.panes, texts):
            pane.load(text)
        self.resize(820, 620)
        self._changed()

    def texts(self):
        return [pane.text() for pane in self.panes]

    def _restore(self):
        for pane, text in zip(self.panes, self.original):
            pane.load(text)
        self._changed()

    def _changed(self):
        self.panes[0].update_view(self.with_sprite)
        self.panes[1].update_view(self.with_sprite)
        used = self.used(self.texts())
        over = used - self.pool
        self.budget.setText(f"Wszystkie teksty darów zajmą {used} z {self.pool} bajtów."
                            + (f" Trzeba skrócić teksty o {over} B." if over > 0 else
                               f" Wolne: {-over} B."))
        self.budget.setStyleSheet("color: #c0392b;" if over > 0 else "")
        bad = self.panes[0].errors(self.with_sprite) or self.panes[1].errors(self.with_sprite)
        self.ok.setEnabled(not bad and over <= 0)


class GiftTableBox(QWidget):
    """Jedna z czterech tabel losowania darow: numer daru, przedmiot i waga kazdego wpisu."""
    COL_NO, COL_MOVE, COL_GIFT, COL_SPRITE, COL_WEIGHT, COL_CHANCE, COL_TEXT, COL_EDIT = range(8)

    def __init__(self, feature, entries, on_change, owner=None):
        super().__init__()
        self.f = feature
        self.on_change = on_change
        self.owner = owner            # GiftsBox, gdy teksty da sie zmieniac (inaczej None)
        self._loading = False
        self.n = len(entries)
        self.texts = [list(e["texts"]) for e in entries]
        self.orig_texts = [list(e["texts"]) for e in entries]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(self.n, 8)
        self.table.setHorizontalHeaderLabels(
            ["#", "Kolejność", "Dar (co się stanie)", "Przedmiot (obrazek i dźwięk)", "Waga",
             "Szansa", "Tekst w grze (polski)", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)   # tekst w jednym wierszu (skrocony „…”), calosc w podpowiedzi
        self.table.cellDoubleClicked.connect(self._cell_double_clicked)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_TEXT, QHeaderView.Stretch)
        for c in (self.COL_NO, self.COL_MOVE, self.COL_GIFT, self.COL_SPRITE, self.COL_WEIGHT,
                  self.COL_CHANCE, self.COL_EDIT):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.gifts, self.sprites, self.weights, self.movers = [], [], [], []
        for i in range(self.n):
            off = feature.entry_offset(i)
            num = read_only_item(str(i + 1))
            num.setToolTip(f"offsety w pliku: dar 0x{off:X}, waga 0x{off + 4:X}, "
                           f"obrazek 0x{off + 8:X}, wskaźniki tekstów 0x{off + 12:X}")
            self.table.setItem(i, self.COL_NO, num)
            self.table.setCellWidget(i, self.COL_MOVE, self._move_cell(i))
            cb_gift = QComboBox()
            for gid in sorted(cp.GIFT_EFFECTS):
                cb_gift.addItem(cp.gift_label(gid), gid)
            cb_gift.setMinimumWidth(260)
            cb_gift.currentIndexChanged.connect(self._changed)
            self.table.setCellWidget(i, self.COL_GIFT, cb_gift)
            self.gifts.append(cb_gift)
            cb_spr = QComboBox()
            for sid in sorted(cp.ARTEFACT_NAMES):
                cb_spr.addItem(cp.artefact_label(sid), sid)
            cb_spr.setMinimumWidth(240)
            cb_spr.setToolTip("Obrazek z temple.s32 pokazywany w okienku i jednocześnie numer "
                              "dźwięku sfx\\artefakt\\N.wav (przy „bez obrazka” gra odtwarza "
                              "dźwięk 7 i nie rysuje nic).")
            cb_spr.currentIndexChanged.connect(self._changed)
            self.table.setCellWidget(i, self.COL_SPRITE, cb_spr)
            self.sprites.append(cb_spr)
            sp = QSpinBox()
            sp.setRange(0, cp.GiftTable.MAX_WEIGHT)
            sp.valueChanged.connect(self._changed)
            self.table.setCellWidget(i, self.COL_WEIGHT, sp)
            self.weights.append(sp)
            self.table.setItem(i, self.COL_CHANCE, read_only_item())
            self.table.setItem(i, self.COL_TEXT, read_only_item())
            btn = QPushButton("Zmień…")
            btn.setToolTip("Zmienia tekst, który gra pokaże w okienku tego daru")
            btn.setEnabled(owner is not None)
            btn.clicked.connect(lambda _=False, row=i: self.edit_text(row))
            self.table.setCellWidget(i, self.COL_EDIT, btn)
        lay.addWidget(self.table)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.warn = QLabel("")
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet("color: #c0392b;")
        lay.addWidget(self.warn)

    def _move_cell(self, i):
        """Przyciski w gore / w dol: zamieniaja wpis z sasiednim."""
        what = ("dar, przedmiot, wagę i tekst" if self.owner is not None else
                "dar, przedmiot i wagę (tekstów w tym pliku zmienić nie można, więc zostają "
                "na swoich miejscach)")
        cell = QWidget()
        cl = QHBoxLayout(cell)
        cl.setContentsMargins(2, 0, 2, 0)
        cl.setSpacing(2)
        cl.setAlignment(Qt.AlignCenter)
        pair = []
        for arrow, step, name, where in ((Qt.UpArrow, -1, "w górę", "powyżej"),
                                         (Qt.DownArrow, 1, "w dół", "poniżej")):
            btn = QToolButton()
            btn.setArrowType(arrow)
            btn.setToolTip(f"Zamienia ten wpis z wpisem {where}: {what}")
            btn.setAccessibleName(f"Wpis {i + 1}: przesuń {name}")
            btn.setEnabled(0 <= i + step < self.n)
            btn.clicked.connect(lambda _=False, row=i, s=step: self.move(row, s))
            cl.addWidget(btn)
            pair.append(btn)
        self.movers.append(pair)
        return cell

    # --- dane
    def _row(self, i):
        return self.gifts[i].currentData(), self.sprites[i].currentData(), self.weights[i].value()

    def _set_row(self, i, gift, sprite, weight):
        self.gifts[i].setCurrentIndex(self.gifts[i].findData(gift))
        idx = self.sprites[i].findData(sprite)
        if idx < 0:                          # obrazek, ktorego nie ma na liscie - dopisz go
            self.sprites[i].addItem(cp.artefact_label(sprite), sprite)
            idx = self.sprites[i].findData(sprite)
        self.sprites[i].setCurrentIndex(idx)
        self.weights[i].setValue(weight)

    def load(self, entries):
        self._loading = True
        for i, e in enumerate(entries[:self.n]):
            self._set_row(i, e["gift"], e["sprite"], e["weight"])
            self.texts[i] = list(e["texts"])
            self.orig_texts[i] = list(e["texts"])
            self.show_text(i)
        self._loading = False
        self._update()

    def move(self, i, step):
        """Zamienia wpis `i` z sasiednim (`step` -1: z wyzszym, +1: z nizszym).

        Tekst przechodzi razem z wpisem tylko wtedy, gdy teksty da sie zapisac - inaczej zostaje
        na miejscu, bo ostatnia kolumna ma pokazywac to, co gra naprawde wypisze."""
        j = i + step
        if not 0 <= j < self.n:
            return
        a, b = self._row(i), self._row(j)
        self._loading = True
        self._set_row(i, *b)
        self._set_row(j, *a)
        if self.owner is not None:
            for rows in (self.texts, self.orig_texts):
                rows[i], rows[j] = rows[j], rows[i]
            self.show_text(i)
            self.show_text(j)
        self._loading = False
        self._update()
        # zaznaczenie i fokus ida za przesunietym wpisem, wiec kolejne naciskanie spacji
        # przesuwa go dalej
        self.table.selectRow(j)
        btn = self.movers[j][0 if step < 0 else 1]
        (btn if btn.isEnabled() else self.movers[j][1 if step < 0 else 0]).setFocus()
        self.on_change()

    def show_text(self, i):
        pl, en = self.texts[i][0], self.texts[i][1]
        item = self.table.item(i, self.COL_TEXT)
        item.setText(" ".join(pl.split())[:70])
        # podpowiedzi Qt nie zawijaja zwyklego tekstu same - lamiemy go recznie
        item.setToolTip("\n\n".join(textwrap.fill(" ".join(t.split()), 90)
                                    for t in (pl, en) if t.strip()))

    def edit_text(self, i):
        if self.owner is not None:
            self.owner.edit_text(self, i)

    def _cell_double_clicked(self, row, col):
        if col == self.COL_TEXT:
            self.edit_text(row)

    def value(self):
        return [{"gift": self.gifts[i].currentData(),
                 "sprite": self.sprites[i].currentData(),
                 "weight": self.weights[i].value()} for i in range(self.n)]

    def refresh_effects(self, amounts):
        """Odswieza opisy darow po zmianie liczb w sekcji „Siła darów”."""
        for cb in self.gifts:
            for pos in range(cb.count()):
                cb.setItemText(pos, cp.gift_label(cb.itemData(pos), amounts))

    # --- liczenie szans i kontrola
    def _update(self):
        ws = [sp.value() for sp in self.weights]
        total = sum(ws)
        chances = cp.GiftTable.chances(ws)
        for i, c in enumerate(chances):
            self.table.item(i, self.COL_CHANCE).setText(f"{c} / {total} = {pct(c, total)}"
                                                        if total else str(c))
        self.summary.setText(
            f"Suma wag: {total}. Gra losuje liczbę od 0 do {max(total - 1, 0)}, więc pierwszy wpis "
            f"ma o jedną szansę więcej, niż wynika z jego wagi, a ostatni o jedną mniej.")
        msgs, ok = [], True
        if total <= 0:
            msgs.append("Suma wag musi być większa od zera. Przy zerze gra losuje z pustego "
                        "zakresu i wynik jest nieprzewidywalny.")
            ok = False
        dead = [i + 1 for i, c in enumerate(chances) if c <= 0]
        if dead:
            msgs.append("Wpisy, których gra nigdy nie wylosuje: " + ", ".join(map(str, dead)) + ".")
        if self.f.human and not self._has_reroll_gift(chances):
            msgs.append("W misjach 2, 6, 12 i 16 gra losuje dla gracza tak długo, aż trafi na dar "
                        "„nowy oddział” albo „brak efektu”, a w tej tabeli żaden osiągalny wpis nie "
                        "ma takiego daru, więc gra zawiesiłaby się w tych misjach.")
            ok = False
        self.warn.setText(" ".join(msgs))
        return ok

    def _has_reroll_gift(self, chances):
        return any(self.gifts[i].currentData() in cp.GIFT_REROLL_OK and chances[i] > 0
                   for i in range(self.n))

    def valid(self):
        return self._update()

    def _changed(self, *_):
        self._update()
        if not self._loading:
            self.on_change()


class GiftsBox(QGroupBox):
    """Cztery tabele darow w zagniezdzonych zakladkach."""

    def __init__(self, exe, on_change):
        super().__init__("Dary świątyń i miejsc kultu: co i jak często można wylosować")
        self.boxes = {}
        self.on_change = on_change
        self.exe = exe
        self.texts_ft = exe.features.get("gift_texts")
        lay = QVBoxLayout(self)
        pin_info(
            self, "Dary świątyń i miejsc kultu",
            paras(cp.DESC_GIFTS,
                  "Liczba wpisów jest stała, bo tabele leżą w pliku jedna za drugą, więc nie da się "
                  "dopisać nowej pozycji. Można jednak zmienić każdemu wpisowi dar (efekt), "
                  "przedmiot, wagę i tekst, a waga 0 praktycznie go wyłącza. Jednostki, które "
                  "daje dar „nowy oddział”, ustawia się w dwóch listach powyżej.",
                  "Strzałki w kolumnie „Kolejność” zamieniają wpis z sąsiednim, razem z jego "
                  "tekstem. Kolejność zmienia szanse tylko na brzegach tabeli: pierwszy wpis ma "
                  "o jedną szansę więcej, niż wynika z jego wagi, a ostatni o jedną mniej.")
            + (paras(cp.DESC_GIFT_TEXTS) if self.texts_ft else "")
            + cp.DETAILS_GIFT_TABLES)
        if not self.texts_ft:
            lay.addWidget(note_label(
                "Tekstów w tym pliku zmienić nie można: "
                + exe.problems.get("gift_texts", "brak w tej wersji gry")
                + ". Ostatnia kolumna pokazuje, co gra wypisze."))
        self.tabs = QTabWidget()
        for key in ("gifts_christian_human", "gifts_christian_ai",
                    "gifts_pagan_human", "gifts_pagan_ai"):
            ft = exe.features.get(key)
            if not ft:
                continue
            box = GiftTableBox(ft, ft.read(exe.data), on_change,
                               self if self.texts_ft else None)
            self.tabs.addTab(box, ft.title)
            self.boxes[key] = box
        if self.boxes:
            lay.addWidget(self.tabs)
        else:
            lay.addWidget(note_label("Niedostępne: " + "; ".join(
                exe.problems.get(k, "brak w tej wersji gry") for k in
                ("gifts_christian_human", "gifts_pagan_human"))))
            self.setEnabled(False)
        self.budget = QLabel("")
        self.budget.setWordWrap(True)
        self.budget.setVisible(bool(self.texts_ft))
        lay.addWidget(self.budget)

    # --- teksty (wspolna pula bajtow czterech tabel)
    def texts(self, override=None):
        """{klucz tabeli: [[polski, angielski, trzeci], ...]} - stan pol w programie."""
        out = {}
        for key, box in self.boxes.items():
            rows = [list(row) for row in box.texts]
            if override and override[0] is box:
                rows[override[1]] = list(override[2]) + rows[override[1]][2:]
            out[key] = rows
        return out

    def used_bytes(self, override=None):
        return self.texts_ft.used(self.exe.data, self.texts(override))

    def edit_text(self, box, i):
        dlg = GiftTextDialog(
            self, f"{box.f.title}, wpis {i + 1}: tekst daru",
            box.texts[i][:2], box.orig_texts[i][:2],
            box.sprites[i].currentData() != -1,
            lambda texts: self.used_bytes((box, i, texts)), self.texts_ft.pool_size)
        if dlg.exec() != QDialog.Accepted:
            return
        new = dlg.texts()
        if new == box.texts[i][:2]:
            return
        box.texts[i][:2] = new
        box.show_text(i)
        self._update_budget()
        self.on_change()

    def _update_budget(self):
        if not self.texts_ft:
            return True
        used, pool = self.used_bytes(), self.texts_ft.pool_size
        self.budget.setText(
            f"Teksty darów zajmują {used} z {pool} bajtów wspólnego obszaru w pliku"
            + (f", trzeba skrócić je o {used - pool} B." if used > pool else
               f" (wolne {pool - used} B)."))
        self.budget.setStyleSheet("color: #c0392b;" if used > pool else secondary_style())
        return used <= pool

    def load(self, exe):
        self.exe = exe
        for key, box in self.boxes.items():
            box.load(exe.get(key))
        self._update_budget()

    def store(self, exe):
        for key, box in self.boxes.items():
            exe.set(key, box.value())
        if self.texts_ft:
            exe.set("gift_texts", self.texts())

    def refresh_effects(self, amounts):
        for box in self.boxes.values():
            box.refresh_effects(amounts)

    def valid(self):
        # bez skrotu logicznego - kazda zakladka ma odswiezyc swoje ostrzezenia
        return all([box.valid() for box in self.boxes.values()] + [self._update_budget()])


class GiftAmountsBox(QGroupBox):
    """Sila darow - liczby wpisane w kod gry, wspolne dla wszystkich czterech tabel."""

    def __init__(self, exe, on_change, on_amounts_changed):
        super().__init__("Siła darów: ile dokładnie dają")
        self.ft = exe.features.get("gift_amounts")
        self.on_change = on_change
        self.on_amounts_changed = on_amounts_changed
        # ustawiane przez okno glowne na stan przelacznika z zakladki "Poprawki": gdy poprawka
        # zmeczenia jest wlaczona, bajt sie nie przekreca i nie ma o czym ostrzegac
        self.tiredness_fixed = lambda: False
        self._loading = False
        self.spins = {}
        lay = QVBoxLayout(self)
        intro = ("Te liczby gra ma wpisane wprost w kodzie, a nie w tabeli, więc są wspólne dla "
                 "świątyń, miejsc kultu i zakopanych skarbów, i obowiązują zarówno gracza, jak i "
                 "komputer. Dotyczą każdej jednostki armii, która weszła do świątyni (poza złotem, "
                 "chłopami i dowódcami, których gra pomija).")
        if self.ft:
            pin_feature_info(self, self.ft, intro, extra=paras(self.ft.note))
        else:
            pin_info(self, "Siła darów świątyń i miejsc kultu", paras(intro))
        if not self.ft:
            lay.addWidget(note_label("Niedostępne: " + exe.problems.get(
                "gift_amounts", "w tej wersji gry nie są znane adresy tych liczb")))
            self.setEnabled(False)
            return
        grid = QGridLayout()
        for col, text in enumerate(("Dar", "Co robi", "Wartości")):
            head = QLabel(text)
            head.setStyleSheet("font-weight: bold;")
            grid.addWidget(head, 0, col)
        row = 1
        for gid in sorted(cp.GIFT_EFFECTS):
            amounts = self.ft.by_gift(gid)
            name = cp.GIFT_EFFECTS[gid][0]
            grid.addWidget(QLabel(f"{gid:02d}"), row, 0)
            grid.addWidget(QLabel(name), row, 1)
            if not amounts:
                none = QLabel("—")
                none.setToolTip("Ten dar nie ma w kodzie żadnej liczby do zmiany.")
                grid.addWidget(none, row, 2)
                row += 1
                continue
            cell = QWidget()
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(0, 0, 0, 0)
            for a in amounts:
                cl.addWidget(QLabel(a.label + ":"))
                sp = QSpinBox()
                sp.setRange(a.lo, a.hi)
                tip = f"offset 0x{a.instr.value_offset:X}, zakres {a.lo}–{a.hi}"
                if a.note:
                    tip = a.note + "\n" + tip
                sp.setToolTip(tip)
                sp.valueChanged.connect(self._changed)
                cl.addWidget(sp)
                self.spins[a.key] = sp
            cl.addStretch(1)
            grid.addWidget(cell, row, 2)
            row += 1
        grid.setColumnStretch(3, 1)
        lay.addLayout(grid)
        self.warn = QLabel("")
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet("color: #c0392b;")
        lay.addWidget(self.warn)

    def value(self):
        return {k: sp.value() for k, sp in self.spins.items()}

    def _validate(self):
        if not self.ft:
            return True
        msgs, ok = [], True
        lo, hi = self.spins.get("troops_min"), self.spins.get("troops_max")
        if lo is not None and hi is not None and lo.value() > hi.value():
            msgs.append("Dar „nowy oddział”: najmniejsza liczba jednostek jest większa od "
                        "największej, więc gra losowałaby z odwróconego zakresu.")
            ok = False
        big = [k for k in ("tired2", "tired14")
               if k in self.spins and self.spins[k].value() > cp.GiftAmounts.TIREDNESS_SAFE_ADD]
        if big and not self.tiredness_fixed():
            msgs.append(f"Dodanie więcej niż {cp.GiftAmounts.TIREDNESS_SAFE_ADD} zmęczenia przekręca "
                        "bajt ze znakiem: jednostki, które są już zmęczone,\nzamiast kary dostaną "
                        "zerowe zmęczenie (ten błąd ma też oryginalna KSIĘGA PLAG z +50).\n"
                        f"Naprawia to poprawka „{cp.TITLE_TIREDNESS_ADD}” na zakładce „Poprawki”.")
        self.warn.setText(" ".join(msgs))
        return ok

    def refresh_warnings(self):
        """Przeliczenie ostrzezen po zmianie, ktora nie jest zmiana tych pol (stan poprawek)."""
        self._validate()

    def valid(self):
        return self._validate()

    def _changed(self, *_):
        self._validate()
        if not self._loading:
            self.on_change()
            self.on_amounts_changed(self.value())

    def load(self, exe):
        if not self.ft:
            return
        self._loading = True
        for key, v in exe.get("gift_amounts").items():
            if key in self.spins:
                self.spins[key].setValue(v)
        self._loading = False
        self._validate()

    def store(self, exe):
        if self.ft:
            exe.set("gift_amounts", self.value())


class RandomUnitsTab(QWidget):
    def __init__(self, exe, on_change):
        super().__init__()
        lay = QVBoxLayout(self)
        self.boxes = {}
        for key in ("temple", "temple_mission"):
            if key in exe.features:
                box = DwordListBox(exe.features[key], on_change)
                lay.addWidget(box)
                self.boxes[key] = box
        self.gifts = GiftsBox(exe, on_change)
        self.amounts = GiftAmountsBox(exe, on_change, self.gifts.refresh_effects)
        lay.addWidget(self.amounts)
        lay.addWidget(self.gifts)
        for key in ("port",):
            if key in exe.features:
                box = DwordListBox(exe.features[key], on_change)
                lay.addWidget(box)
                self.boxes[key] = box
        lay.addStretch(1)

    def load(self, exe):
        for k, box in self.boxes.items():
            box.load(exe.get(k))
        self.amounts.load(exe)
        if "gift_amounts" in exe.features:
            self.gifts.refresh_effects(exe.get("gift_amounts"))
        self.gifts.load(exe)
        for box in self.gifts.boxes.values():
            fit_table_height(box.table)

    def store(self, exe):
        for k, box in self.boxes.items():
            exe.set(k, box.value())
        self.amounts.store(exe)
        self.gifts.store(exe)

    def valid(self):
        ok_amounts = self.amounts.valid()
        ok_gifts = self.gifts.valid()
        return ok_amounts and ok_gifts


class ProductionTab(QWidget):
    """Kuznia / warsztat / minimalny poziom - tabela jednostek."""
    COL_FORGE, COL_WORKSHOP, COL_LVL_OTHER, COL_LVL_T2 = 2, 3, 4, 5

    def __init__(self, exe, on_change):
        super().__init__()
        self.exe = exe
        self.on_change = on_change
        self._loading = False
        lay = QVBoxLayout(self)
        lay.addLayout(info_row("Kuźnia, warsztat, poziomy", paras(
            "Zaznacz, które jednostki wymagają kuźni lub warsztatu, i ustaw minimalny poziom "
            "zaawansowania budynku. Poziom 5 oznacza „nigdy” (maksymalny poziom w grze to 4).",
            "Kolumny poziomu odpowiadają dwóm typom budynków: typ 2 w rekordzie budynku to "
            "zamek, a typ 1 to twierdza."), label="Opis"))
        self.counter = QLabel("")
        lay.addWidget(self.counter)
        self.table = QTableWidget(cp.UNIT_COUNT, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Jednostka", "Kuźnia", "Warsztat", "Poziom: twierdza (typ 1)", "Poziom: zamek (typ 2)"])
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
                             ("" if ok else "  (za dużo jednostek, lista się nie zmieści!)"))
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


def places_word(n):
    """miejsce / miejsca / miejsc - odmiana po liczbie zmienianych miejsc w pliku."""
    if n == 1:
        return "miejsce"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "miejsca"
    return "miejsc"


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
        self.intro = (
            "Mur ma trzy poziomy, w grze pokazywane jako 1, 2 i 3 (zamek zaczyna na 1., twierdza "
            "na 2.). „Rozbuduj mury” w zamku podnosi mur o jeden poziom: gra pobiera koszt ze "
            "skarbca tego zamku i ustawia licznik tur. Licznik spada o 1 na początku każdej tury "
            "właściciela zamku, a gdy dojdzie do zera, poziom muru rośnie. Podczas trwającej "
            "rozbudowy nie można zlecić kolejnej, ale można ją zlecić już w tej turze, w której "
            "poprzednia się skończyła.",
            "Oryginalnie czasy to 5 i 10 tur, a oba koszty to 1 sztuka złota. Wygląda to na błąd "
            "w danych gry: bajty 05 01 / 0A 01 wyglądają na zamierzone 16-bitowe 261 i 266, "
            "ale gra czyta z nich po jednym bajcie.")
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
            tech.setToolTip("Warunek rozbudowy: poziom muru musi być mniejszy niż technologia zamku − 1")
            grid.addWidget(tech, row, 1)
            t = QSpinBox()
            t.setRange(cp.WallTable.MIN_TURNS, cp.WallTable.MAX_TURNS)
            t.setSuffix(" tur")
            t.setToolTip("Licznik tur zamku. Minimum to 1, bo przy 0 gra pobrałaby złoto, licznik nigdy by nie "
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
        self.strength = QLabel("")
        self.strength.setWordWrap(True)
        bl.addWidget(self.strength)
        if self.ft:
            where = f" Tabela murów w pliku: 0x{self.base:X}." if self.base is not None else ""
            pin_feature_info(
                box, self.ft, None,
                extra=paras(
                    *self.intro,
                    "Nowe wartości obowiązują też komputerowego przeciwnika (reguła "
                    "„rozbudowa_murow”). Nie ma on tu zniżki, jaką ma na licencje i budynki, "
                    "i próbuje rozbudowy, gdy tylko może. Przy wysokiej cenie będzie po prostu "
                    "czekał, aż uzbiera złoto. Kliknięcie „Rozbuduj mury” bez dość złota nic nie "
                    "robi, tak samo jak w oryginale." + where))
        else:
            box.setEnabled(False)
            lay.addLayout(info_row("Mury: koszt i czas rozbudowy", paras(*self.intro),
                                   label="Opis"))
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
            "Wytrzymałość murów: "
            + ", ".join(f"{lvl + 1}. poziom {s}" for lvl, s in enumerate(v["strength"])) + ".")
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
        lay.addLayout(info_row("Punkty akcji", paras(
            "Koszt to liczba PA, którą traci każda jednostka. Minimum to liczba PA, jaką każda "
            "jednostka musi mieć, żeby gra w ogóle pozwoliła na operację. "
            "Oryginalnie obie wynoszą 4.",
            "Szczegóły każdej z dwóch operacji są pod ikoną przy jej ramce."), label="Opis"))
        self.rows = {}
        for key in ("ap_split", "ap_join"):
            ft = exe.features.get(key)
            if not ft:
                continue
            box = QGroupBox(ft.title)
            bl = QVBoxLayout(box)
            pin_feature_info(box, ft)
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
        box = QGroupBox("Okopanie: premia do obrony")
        bl = QVBoxLayout(box)
        intro = paras(
            "Oryginalnie gra mnoży obronę okopanej jednostki przez 1,25 (z zaokrągleniem w dół): "
            "obrona 1–3 nic nie zyskuje, 4–7 dostaje +1, 8–11 +2, 12–15 +3. "
            "Zamiast tego można ustawić stałą premię dla wszystkich jednostek.")
        if self.ft:
            sites = ", ".join(f"<code>0x{s[0]:X}</code>" for s in self.ft.sites)
            pin_info(box, "Okopanie: premia do obrony", intro + (
                "<p><b>Gdzie to jest w pliku</b></p>"
                f"<p>Zmieniany kod: {sites}. Program podmienia tam mnożenie przez 1,25 na "
                "dodanie stałej liczby i krótki skok; rozpoznaje oba stany, więc potrafi wrócić "
                "do oryginalnej reguły.</p>"))
        else:
            pin_info(box, "Okopanie: premia do obrony", intro)
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
        if not self.ft:
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
        # funkcje wolane po kazdej zmianie przelacznika: inne zakladki pokazuja ostrzezenia
        # zalezne od tego, czy dana poprawka jest wlaczona
        self.listeners = []
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
                pin_feature_info(
                    box, ft, f"Poprawka zmienia {len(ft.sites)} {places_word(len(ft.sites))} "
                             "w pliku gry.")
                cb.toggled.connect(self._changed)
                self.boxes[ft.key] = cb
            else:
                cb.setEnabled(False)
                bl.addWidget(note_label("Niedostępna: " + exe.problems[ft.key]))
            lay.addWidget(box)
        lay.addStretch(1)

    def is_on(self, key):
        """Czy poprawka `key` jest w tej chwili zaznaczona (False, gdy jej tu nie ma)."""
        cb = self.boxes.get(key)
        return cb.isChecked() if cb is not None else False

    def _notify(self):
        for fn in self.listeners:
            fn()

    def _changed(self, *_):
        self._notify()
        if not self._loading:
            self.on_change()

    def load(self, exe):
        self._loading = True
        for key, cb in self.boxes.items():
            cb.setChecked(exe.get(key))
        self._loading = False
        self._notify()

    def store(self, exe):
        for key, cb in self.boxes.items():
            exe.set(key, cb.isChecked())


class CheatsTab(QWidget):
    def __init__(self, exe, on_change):
        super().__init__()
        self.ft = exe.features.get("cheats")
        lay = QVBoxLayout(self)
        lay.addLayout(info_row("Kody", paras(
            "W grze: przytrzymaj C, puść, wpisz kod i naciśnij Enter (w wersji niemieckiej "
            "klawisz P i zamienione Y/Z).",
            "Dozwolone znaki: litery a-z, cyfry, spacja i ; ' , . - =. Nowy kod nie może być "
            "dłuższy niż oryginalny, bo każdy leży w pliku w miejscu o stałej długości.")
            + (f"<p><b>Gdzie to jest w pliku</b></p><p>Pierwszy kod leży pod "
               f"<code>0x{self.ft.entries[0][0]:X}</code>, każdy następny w swoim stałym miejscu. "
               "Tekst jest zapisany znak po znaku z każdym bajtem XOR 0x32 i zakończony zerem, "
               "dlatego w pliku kody nie wyglądają jak zwykły tekst.</p>" if self.ft else ""),
            label="Opis"))
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
            msgs.append("Pusty kod nie zostanie dopasowany do niczego.")
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
        self.resize(1280, 864)
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
            self.tabs.addTab(QLabel(f"  {APP_NAME} {__version__}\n\n"
                                    "  Otwórz plik CLASH.EXE (DOS, polska wersja) albo clash95.exe."), "Start")

    def _enable(self, on):
        for name in ("save", "save_as", "show_changes", "reload", "restore_backup"):
            getattr(self, "act_" + name).setEnabled(on)

    def _set_title(self):
        name = os.path.basename(self.exe.path) if self.exe else "brak pliku"
        self.setWindowTitle(f"{APP_NAME} {__version__}: {name}{' *' if self.dirty else ''}")

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
        self._link_tiredness_fix(*(next(p for p in self.pages if isinstance(p, t))
                                   for t in (RandomUnitsTab, FixesTab)))
        for page, title in zip(self.pages, titles):
            page.load(exe)
            self.tabs.addTab(page if isinstance(page, ProductionTab) else scrolled(page), title)
        info = QPlainTextEdit()
        info.setReadOnly(True)
        lines = [f"{APP_NAME} {__version__}", "", exe.profile["name"], exe.path, ""]
        for ft in exe.profile["features"]:
            state = "OK" if ft.key in exe.features else "WYŁĄCZONE: " + exe.problems[ft.key]
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

    @staticmethod
    def _link_tiredness_fix(units, fixes):
        """Ostrzezenie o przekrecaniu zmeczenia znika, gdy poprawka zmeczenia jest wlaczona.

        Wolane przed `load` kazdej zakladki, bo FixesTab po wczytaniu stanu z pliku sam odswieza
        ostrzezenie przez `listeners`."""
        units.amounts.tiredness_fixed = lambda: fixes.is_on("tiredness_add")
        fixes.listeners.append(units.amounts.refresh_warnings)

    def _collect(self):
        for page in self.pages:
            if hasattr(page, "valid") and not page.valid():
                QMessageBox.warning(self, "Popraw dane", "Na jednej z zakładek są błędy (zaznaczone na czerwono).")
                return False
        for page in self.pages:
            try:
                page.store(self.exe)
            except ValueError as e:        # znalezisko odmawia zapisu takiej wartosci
                self.exe.data = bytearray(self.exe.original)
                QMessageBox.critical(self, "Nie można zapisać", str(e))
                return False
        return True

    def _changes_text(self):
        ch = self.exe.changes()
        if not ch:
            return "Brak zmian względem pliku na dysku."
        # sasiadujace bajty w jedno miejsce - inaczej jedna zmiana tekstu daru (kilkanascie
        # tysiecy bajtow) nadpisalaby wszystkie pozostale
        runs = []
        for o, a, b in ch:
            if runs and runs[-1][0] + len(runs[-1][1]) == o:
                runs[-1][1].append(a)
                runs[-1][2].append(b)
            else:
                runs.append((o, [a], [b]))
        lines = [f"Zmienione bajty: {len(ch)} w {len(runs)} miejscach", ""]
        for o, old, new in runs[:300]:
            if len(old) <= 8:
                lines.append(f"0x{o:06X}: {bytes(old).hex(' ').upper()} -> "
                             f"{bytes(new).hex(' ').upper()}")
            else:
                lines.append(f"0x{o:06X}–0x{o + len(old) - 1:06X}: {len(old)} bajtów")
        if len(runs) > 300:
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
    if len(sys.argv) > 1 and sys.argv[1] in ("--version", "-V"):
        print(f"{APP_NAME} {__version__}")
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    win = MainWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
