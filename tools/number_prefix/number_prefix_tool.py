"""
Number Prefix — 4 modes in one tool:

  1. Add Prefix      — add sequential numbers to filenames (001_photo.jpg)
  2. Increase All    — bump every existing prefix by N  (003_ → 008_ when +5)
  3. Increase After  — bump only files whose prefix >= threshold  (insert gap)
  4. Ordering        — visually reorder & renumber files with drag-drop, inline
                       editing and Move Up / Move Down controls.

All modes share: live preview table, sort options, undo, progress bar.
"""
import os
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QSpinBox, QCheckBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QMessageBox, QProgressBar, QSizePolicy, QTabWidget,
    QScrollArea, QGroupBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QMimeData, QModelIndex
from PySide6.QtGui import QFont, QColor, QDrag


# ── Constants ─────────────────────────────────────────────────────────────────

SEPARATORS    = ["_", "-", ". ", " "]
SEP_LABELS    = ["_  (underscore)", "-  (dash)", ".  (dot+space)", "   (space)"]
SORT_OPTIONS  = [
    "Name (A → Z)", "Name (Z → A)",
    "Date modified (oldest first)", "Date modified (newest first)",
    "Size (smallest first)", "Size (largest first)",
    "Keep current order",
]

_NUM_RE = re.compile(r"^(\d+)([_\-\s\.]+)(.*)", re.DOTALL)


def _parse_prefix(stem: str):
    m = _NUM_RE.match(stem)
    if m:
        return int(m.group(1)), m.group(2), m.group(3)
    return None, "", stem


def _strip_prefix(stem: str) -> str:
    m = _NUM_RE.match(stem)
    return m.group(3) if m else stem


def _fmt(n: int, digits: int) -> str:
    return f"{n:0{digits}d}"


# ── Worker thread ─────────────────────────────────────────────────────────────

class _RenameWorker(QThread):
    progress = Signal(int)
    done     = Signal(list)
    log      = Signal(str)

    def __init__(self, jobs):
        super().__init__()
        self._jobs = jobs

    def run(self):
        results = []
        total = len(self._jobs)
        for i, (old, new) in enumerate(self._jobs):
            try:
                if old != new:
                    if os.path.exists(new):
                        raise FileExistsError("Target already exists")
                    os.rename(old, new)
                results.append((old, new, True, ""))
                self.log.emit(f"✅ {os.path.basename(old)}  →  {os.path.basename(new)}")
            except Exception as e:
                results.append((old, new, False, str(e)))
                self.log.emit(f"❌ {os.path.basename(old)}: {e}")
            self.progress.emit(int((i + 1) / total * 100))
        self.done.emit(results)


# ── Shared preview table builder ──────────────────────────────────────────────

def _make_table() -> QTableWidget:
    t = QTableWidget(0, 3)
    t.setHorizontalHeaderLabels(["#", "Original name", "New name"])
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
    t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    t.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.verticalHeader().setVisible(False)
    t.setStyleSheet("""
        QTableWidget { background:#1A1A1A; border:none; font-size:12px; }
        QHeaderView::section { background:#252525; color:#888; border:none; padding:6px; }
        QTableWidget::item { padding:4px 8px; }
    """)
    return t


def _fill_table(table: QTableWidget, rows: list):
    table.setRowCount(0)
    for num_lbl, orig, new, changed in rows:
        r = table.rowCount()
        table.insertRow(r)
        n = QTableWidgetItem(str(num_lbl))
        n.setTextAlignment(Qt.AlignCenter)
        n.setForeground(QColor("#555"))
        table.setItem(r, 0, n)
        o = QTableWidgetItem(orig)
        o.setForeground(QColor("#888"))
        table.setItem(r, 1, o)
        v = QTableWidgetItem(new)
        v.setForeground(QColor("#00BFA5") if changed else QColor("#555"))
        table.setItem(r, 2, v)


# ── Shared folder + filter widget ─────────────────────────────────────────────

class _FolderBar(QWidget):
    def __init__(self, on_change, parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self.folder = ""
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit()
        self._edit.setReadOnly(True)
        self._edit.setPlaceholderText("No folder selected…")
        self._edit.setStyleSheet(_inp())
        lay.addWidget(self._edit)
        btn = QPushButton("📂  Browse…")
        btn.setFixedHeight(34)
        btn.setStyleSheet("background:#00BFA5;color:#000;border:none;"
                          "border-radius:6px;font-weight:bold;padding:0 14px;")
        btn.clicked.connect(self._browse)
        lay.addWidget(btn)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Folder")
        if f:
            self.folder = f
            self._edit.setText(f)
            self._on_change()


def _inp():
    return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
            "padding:5px 10px;color:#E0E0E0;font-size:13px;")


def _lbl(text, color="#888", size=12):
    l = QLabel(text)
    l.setStyleSheet(f"color:{color};font-size:{size}px;")
    return l


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Add Prefix
# ══════════════════════════════════════════════════════════════════════════════

class _AddPrefixTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files      = []
        self._last_jobs  = []
        self._worker     = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        self._folder_bar = _FolderBar(self._reload)
        lay.addWidget(self._folder_bar)

        row1 = QHBoxLayout(); row1.setSpacing(16)
        row1.addWidget(_lbl("Start at:"))
        self._start  = QSpinBox(); self._start.setRange(0, 99999)
        self._start.setValue(1); self._start.setFixedWidth(70)
        self._start.setStyleSheet(_inp()); self._start.valueChanged.connect(self._preview)
        row1.addWidget(self._start)

        row1.addWidget(_lbl("Digits:"))
        self._digits = QSpinBox(); self._digits.setRange(1, 6)
        self._digits.setValue(3); self._digits.setFixedWidth(60)
        self._digits.setStyleSheet(_inp()); self._digits.valueChanged.connect(self._preview)
        row1.addWidget(self._digits)

        row1.addWidget(_lbl("Separator:"))
        self._sep = QComboBox(); self._sep.addItems(SEP_LABELS)
        self._sep.setFixedWidth(160); self._sep.setStyleSheet(_inp())
        self._sep.currentIndexChanged.connect(self._preview)
        row1.addWidget(self._sep)

        row1.addWidget(_lbl("Sort by:"))
        self._sort = QComboBox(); self._sort.addItems(SORT_OPTIONS)
        self._sort.setFixedWidth(220); self._sort.setStyleSheet(_inp())
        self._sort.currentIndexChanged.connect(self._reload)
        row1.addWidget(self._sort)
        row1.addStretch()
        lay.addLayout(row1)

        row2 = QHBoxLayout(); row2.setSpacing(20)
        self._strip_chk = QCheckBox("Strip existing numeric prefix before adding")
        self._strip_chk.setChecked(True)
        self._strip_chk.setStyleSheet("color:#888;font-size:12px;")
        self._strip_chk.stateChanged.connect(self._preview)
        row2.addWidget(self._strip_chk)

        self._sub_chk = QCheckBox("Include subfolders")
        self._sub_chk.setStyleSheet("color:#888;font-size:12px;")
        self._sub_chk.stateChanged.connect(self._reload)
        row2.addWidget(self._sub_chk)

        row2.addWidget(_lbl("Extensions:"))
        self._ext_edit = QLineEdit(); self._ext_edit.setPlaceholderText(".jpg .mp3  — blank = all")
        self._ext_edit.setFixedWidth(240); self._ext_edit.setStyleSheet(_inp())
        self._ext_edit.textChanged.connect(self._reload)
        row2.addWidget(self._ext_edit)
        row2.addStretch()
        lay.addLayout(row2)

        lay.addWidget(_lbl("Preview  (reorder by Sort or drag rows)", "#555", 11))
        self._table = _make_table()
        self._table.setDragDropMode(QTableWidget.InternalMove)
        self._table.setDragEnabled(True); self._table.setAcceptDrops(True)
        self._table.setDropIndicatorShown(True)
        self._table.model().rowsMoved.connect(self._on_rows_moved)
        lay.addWidget(self._table, 1)

        self._progress = _make_progress()
        self._progress.hide()
        lay.addWidget(self._progress)

        self._status = _lbl("", "#888", 12)
        lay.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("✅  Apply Prefix to All Files")
        self._apply_btn.setFixedHeight(38); self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            "background:#00BFA5;color:#000;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;")
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)

        undo_btn = QPushButton("↩  Undo")
        undo_btn.setFixedHeight(38)
        undo_btn.setStyleSheet("background:#3A3A3A;color:#E0E0E0;border:none;"
                               "border-radius:7px;font-size:13px;")
        undo_btn.clicked.connect(self._undo)
        btn_row.addWidget(undo_btn)
        btn_row.addStretch()
        self._count_lbl = _lbl("0 files", "#555")
        btn_row.addWidget(self._count_lbl)
        lay.addLayout(btn_row)

    def _sep_char(self): return SEPARATORS[self._sep.currentIndex()]

    def _sorted(self, files):
        idx = self._sort.currentIndex()
        folder = self._folder_bar.folder
        mt = lambda f: os.path.getmtime(os.path.join(folder, f)) if os.path.exists(os.path.join(folder, f)) else 0
        sz = lambda f: os.path.getsize(os.path.join(folder, f)) if os.path.exists(os.path.join(folder, f)) else 0
        ops = [lambda f: f.lower(), lambda f: f.lower(), mt, mt, sz, sz, lambda f: 0]
        rev = [False, True, False, True, False, True, False]
        if idx < len(ops):
            return sorted(files, key=ops[idx], reverse=rev[idx])
        return files

    def _reload(self):
        folder = self._folder_bar.folder
        if not folder: return
        exts = set()
        for p in self._ext_edit.text().lower().split():
            exts.add(p if p.startswith(".") else "." + p)
        if self._sub_chk.isChecked():
            files = []
            for dp, _, fns in os.walk(folder):
                for f in fns:
                    files.append(os.path.relpath(os.path.join(dp, f), folder))
        else:
            files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if exts:
            files = [f for f in files if os.path.splitext(f)[1].lower() in exts]
        self._files = self._sorted(files)
        self._preview()

    def _preview(self):
        files = self._files
        if not files:
            self._table.setRowCount(0)
            self._count_lbl.setText("0 files")
            self._apply_btn.setEnabled(False)
            return
        start = self._start.value(); digits = self._digits.value()
        sep = self._sep_char(); strip = self._strip_chk.isChecked()
        rows = []
        for i, fn in enumerate(files):
            num = start + i
            stem, ext = os.path.splitext(fn)
            s = _strip_prefix(stem) if strip else stem
            new = f"{_fmt(num, digits)}{sep}{s}{ext}"
            rows.append((num, fn, new, new != fn))
        _fill_table(self._table, rows)
        self._count_lbl.setText(f"{len(files)} file(s)")
        self._apply_btn.setEnabled(True)

    def _on_rows_moved(self, *_):
        new_order = []
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 1)
            if item: new_order.append(item.text())
        self._files = new_order
        self._preview()

    def _build_jobs(self):
        start = self._start.value(); digits = self._digits.value()
        sep = self._sep_char(); strip = self._strip_chk.isChecked()
        folder = self._folder_bar.folder
        jobs = []
        for i, fn in enumerate(self._files):
            stem, ext = os.path.splitext(fn)
            s = _strip_prefix(stem) if strip else stem
            new = f"{_fmt(start + i, digits)}{sep}{s}{ext}"
            jobs.append((os.path.join(folder, fn), os.path.join(folder, new)))
        return jobs

    def _apply(self):
        if not self._files: return
        jobs = self._build_jobs()
        self._last_jobs = [(n, o) for o, n in jobs]
        _run_worker(self, jobs)

    def _undo(self):
        if not self._last_jobs:
            QMessageBox.information(self, "Undo", "Nothing to undo."); return
        if QMessageBox.question(self, "Undo", f"Reverse {len(self._last_jobs)} rename(s)?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
        jobs = self._last_jobs; self._last_jobs = []
        _run_worker(self, jobs)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Increase All Numbers
# ══════════════════════════════════════════════════════════════════════════════

class _IncreaseAllTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files     = []
        self._last_jobs = []
        self._worker    = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(12)

        self._folder_bar = _FolderBar(self._reload)
        lay.addWidget(self._folder_bar)

        info = QFrame()
        info.setStyleSheet("background:#1A2A1A;border-radius:6px;border:1px solid #2A4A2A;")
        il = QHBoxLayout(info); il.setContentsMargins(12, 8, 12, 8)
        il.addWidget(_lbl(
            "Increases the numeric prefix of EVERY file by the same amount.  "
            "e.g. +5 turns  003_photo.jpg → 008_photo.jpg", "#4CAF50", 12))
        lay.addWidget(info)

        row1 = QHBoxLayout(); row1.setSpacing(16)
        row1.addWidget(_lbl("Increase by:"))
        self._by = QSpinBox(); self._by.setRange(-9999, 9999)
        self._by.setValue(1); self._by.setFixedWidth(80)
        self._by.setStyleSheet(_inp()); self._by.valueChanged.connect(self._preview)
        row1.addWidget(self._by)

        row1.addWidget(_lbl("Min digits:"))
        self._digits = QSpinBox(); self._digits.setRange(1, 6)
        self._digits.setValue(3); self._digits.setFixedWidth(60)
        self._digits.setStyleSheet(_inp()); self._digits.valueChanged.connect(self._preview)
        row1.addWidget(self._digits)

        self._keep_sep_chk = QCheckBox("Keep original separator")
        self._keep_sep_chk.setChecked(True)
        self._keep_sep_chk.setStyleSheet("color:#888;font-size:12px;")
        self._keep_sep_chk.stateChanged.connect(self._preview)
        row1.addWidget(self._keep_sep_chk)

        row1.addWidget(_lbl("New separator:"))
        self._sep = QComboBox(); self._sep.addItems(SEP_LABELS)
        self._sep.setFixedWidth(160); self._sep.setStyleSheet(_inp())
        self._sep.currentIndexChanged.connect(self._preview)
        row1.addWidget(self._sep)

        row1.addWidget(_lbl("Extensions:"))
        self._ext_edit = QLineEdit(); self._ext_edit.setPlaceholderText("blank = all")
        self._ext_edit.setFixedWidth(180); self._ext_edit.setStyleSheet(_inp())
        self._ext_edit.textChanged.connect(self._reload)
        row1.addWidget(self._ext_edit)
        row1.addStretch()
        lay.addLayout(row1)

        self._skip_chk = QCheckBox("Skip files that have NO numeric prefix")
        self._skip_chk.setChecked(True)
        self._skip_chk.setStyleSheet("color:#888;font-size:12px;")
        self._skip_chk.stateChanged.connect(self._preview)
        lay.addWidget(self._skip_chk)

        lay.addWidget(_lbl("Preview", "#555", 11))
        self._table = _make_table()
        lay.addWidget(self._table, 1)

        self._progress = _make_progress(); self._progress.hide()
        lay.addWidget(self._progress)
        self._status = _lbl("", "#888", 12); lay.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("✅  Increase All Numbers")
        self._apply_btn.setFixedHeight(38); self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            "background:#FF9800;color:#000;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;")
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)
        undo_btn = QPushButton("↩  Undo")
        undo_btn.setFixedHeight(38)
        undo_btn.setStyleSheet("background:#3A3A3A;color:#E0E0E0;border:none;border-radius:7px;font-size:13px;")
        undo_btn.clicked.connect(self._undo)
        btn_row.addWidget(undo_btn)
        btn_row.addStretch()
        self._count_lbl = _lbl("0 files", "#555")
        btn_row.addWidget(self._count_lbl)
        lay.addLayout(btn_row)

    def _reload(self):
        folder = self._folder_bar.folder
        if not folder: return
        exts = set()
        for p in self._ext_edit.text().lower().split():
            exts.add(p if p.startswith(".") else "." + p)
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if exts:
            files = [f for f in files if os.path.splitext(f)[1].lower() in exts]
        self._files = sorted(files, key=str.lower)
        self._preview()

    def _preview(self):
        files = self._files
        if not files:
            self._table.setRowCount(0); self._apply_btn.setEnabled(False)
            self._count_lbl.setText("0 files"); return
        by = self._by.value(); digits = self._digits.value()
        keep_sep = self._keep_sep_chk.isChecked()
        new_sep = SEPARATORS[self._sep.currentIndex()]
        skip_no_prefix = self._skip_chk.isChecked()
        rows = []; affected = 0
        for fn in files:
            stem, ext = os.path.splitext(fn)
            num, orig_sep, rest = _parse_prefix(stem)
            if num is None:
                rows.append(("—", fn, fn, False)); continue
            new_num = num + by
            sep = orig_sep if keep_sep else new_sep
            new_fn = f"{_fmt(max(0, new_num), digits)}{sep}{rest}{ext}"
            rows.append((f"{num}→{max(0,new_num)}", fn, new_fn, new_fn != fn))
            if new_fn != fn: affected += 1
        _fill_table(self._table, rows)
        self._count_lbl.setText(f"{affected} file(s) will change")
        self._apply_btn.setEnabled(affected > 0)

    def _build_jobs(self):
        folder = self._folder_bar.folder
        by = self._by.value(); digits = self._digits.value()
        keep_sep = self._keep_sep_chk.isChecked()
        new_sep = SEPARATORS[self._sep.currentIndex()]
        skip = self._skip_chk.isChecked()
        jobs = []
        for fn in self._files:
            stem, ext = os.path.splitext(fn)
            num, orig_sep, rest = _parse_prefix(stem)
            if num is None and skip: continue
            if num is None: continue
            sep = orig_sep if keep_sep else new_sep
            new_fn = f"{_fmt(max(0, num + by), digits)}{sep}{rest}{ext}"
            if new_fn != fn:
                jobs.append((os.path.join(folder, fn), os.path.join(folder, new_fn)))
        return jobs

    def _apply(self):
        jobs = self._build_jobs()
        if not jobs: return
        self._last_jobs = [(n, o) for o, n in jobs]
        _run_worker(self, jobs)

    def _undo(self):
        if not self._last_jobs:
            QMessageBox.information(self, "Undo", "Nothing to undo."); return
        if QMessageBox.question(self, "Undo", f"Reverse {len(self._last_jobs)} rename(s)?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
        jobs = self._last_jobs; self._last_jobs = []
        _run_worker(self, jobs)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Increase Numbers After / From
# ══════════════════════════════════════════════════════════════════════════════

class _IncreaseAfterTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files     = []
        self._last_jobs = []
        self._worker    = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 16, 16, 16); lay.setSpacing(12)

        self._folder_bar = _FolderBar(self._reload)
        lay.addWidget(self._folder_bar)

        info = QFrame()
        info.setStyleSheet("background:#1A1A2A;border-radius:6px;border:1px solid #2A2A4A;")
        il = QHBoxLayout(info); il.setContentsMargins(12, 8, 12, 8)
        il.addWidget(_lbl(
            "Bumps only files whose prefix is ≥ the 'From number'.  "
            "Perfect for inserting a new file in the middle of a sequence — "
            "shift everything after it up by 1 to make a gap.", "#2196F3", 12))
        lay.addWidget(info)

        row1 = QHBoxLayout(); row1.setSpacing(16)

        row1.addWidget(_lbl("From number ≥:"))
        self._from = QSpinBox(); self._from.setRange(0, 99999)
        self._from.setValue(1); self._from.setFixedWidth(80)
        self._from.setStyleSheet(_inp()); self._from.valueChanged.connect(self._preview)
        row1.addWidget(self._from)

        row1.addWidget(_lbl("Increase by:"))
        self._by = QSpinBox(); self._by.setRange(-9999, 9999)
        self._by.setValue(1); self._by.setFixedWidth(80)
        self._by.setStyleSheet(_inp()); self._by.valueChanged.connect(self._preview)
        row1.addWidget(self._by)

        row1.addWidget(_lbl("Min digits:"))
        self._digits = QSpinBox(); self._digits.setRange(1, 6)
        self._digits.setValue(3); self._digits.setFixedWidth(60)
        self._digits.setStyleSheet(_inp()); self._digits.valueChanged.connect(self._preview)
        row1.addWidget(self._digits)

        self._keep_sep_chk = QCheckBox("Keep original separator")
        self._keep_sep_chk.setChecked(True)
        self._keep_sep_chk.setStyleSheet("color:#888;font-size:12px;")
        self._keep_sep_chk.stateChanged.connect(self._preview)
        row1.addWidget(self._keep_sep_chk)

        row1.addWidget(_lbl("Extensions:"))
        self._ext_edit = QLineEdit(); self._ext_edit.setPlaceholderText("blank = all")
        self._ext_edit.setFixedWidth(180); self._ext_edit.setStyleSheet(_inp())
        self._ext_edit.textChanged.connect(self._reload)
        row1.addWidget(self._ext_edit)
        row1.addStretch()
        lay.addLayout(row1)

        self._example_lbl = _lbl("", "#666", 11)
        lay.addWidget(self._example_lbl)

        lay.addWidget(_lbl("Preview  (green = will be renamed, gray = untouched)", "#555", 11))
        self._table = _make_table()
        lay.addWidget(self._table, 1)

        self._progress = _make_progress(); self._progress.hide()
        lay.addWidget(self._progress)
        self._status = _lbl("", "#888", 12); lay.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("✅  Apply — Shift Numbers From Here")
        self._apply_btn.setFixedHeight(38); self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            "background:#2196F3;color:#fff;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;")
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)
        undo_btn = QPushButton("↩  Undo")
        undo_btn.setFixedHeight(38)
        undo_btn.setStyleSheet("background:#3A3A3A;color:#E0E0E0;border:none;border-radius:7px;font-size:13px;")
        undo_btn.clicked.connect(self._undo)
        btn_row.addWidget(undo_btn)
        btn_row.addStretch()
        self._count_lbl = _lbl("0 files", "#555")
        btn_row.addWidget(self._count_lbl)
        lay.addLayout(btn_row)

        self._from.valueChanged.connect(self._update_example)
        self._by.valueChanged.connect(self._update_example)
        self._update_example()

    def _update_example(self):
        fr = self._from.value(); by = self._by.value()
        direction = "up" if by > 0 else "down"
        self._example_lbl.setText(
            f"Example:  files 001…{fr-1:03d} stay unchanged  |  "
            f"files {fr:03d}…end shift {direction} by {abs(by)}"
            f"  ({fr:03d}_ → {max(0, fr+by):03d}_)"
        )

    def _reload(self):
        folder = self._folder_bar.folder
        if not folder: return
        exts = set()
        for p in self._ext_edit.text().lower().split():
            exts.add(p if p.startswith(".") else "." + p)
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if exts:
            files = [f for f in files if os.path.splitext(f)[1].lower() in exts]
        self._files = sorted(files, key=str.lower)
        self._preview()

    def _preview(self):
        self._update_example()
        files = self._files
        if not files:
            self._table.setRowCount(0); self._apply_btn.setEnabled(False)
            self._count_lbl.setText("0 files"); return
        threshold = self._from.value(); by = self._by.value()
        digits = self._digits.value(); keep_sep = self._keep_sep_chk.isChecked()
        rows = []; affected = 0
        for fn in sorted(files, key=str.lower):
            stem, ext = os.path.splitext(fn)
            num, orig_sep, rest = _parse_prefix(stem)
            if num is None or num < threshold:
                rows.append(("—", fn, fn, False))
                continue
            new_num = max(0, num + by)
            sep = orig_sep if keep_sep else "_"
            new_fn = f"{_fmt(new_num, digits)}{sep}{rest}{ext}"
            rows.append((f"{num}→{new_num}", fn, new_fn, new_fn != fn))
            if new_fn != fn: affected += 1
        _fill_table(self._table, rows)
        self._count_lbl.setText(f"{affected} file(s) will shift")
        self._apply_btn.setEnabled(affected > 0)

    def _build_jobs(self):
        folder = self._folder_bar.folder
        threshold = self._from.value(); by = self._by.value()
        digits = self._digits.value(); keep_sep = self._keep_sep_chk.isChecked()
        jobs = []
        files = sorted(self._files, key=str.lower, reverse=(by > 0))
        for fn in files:
            stem, ext = os.path.splitext(fn)
            num, orig_sep, rest = _parse_prefix(stem)
            if num is None or num < threshold: continue
            sep = orig_sep if keep_sep else "_"
            new_fn = f"{_fmt(max(0, num + by), digits)}{sep}{rest}{ext}"
            if new_fn != fn:
                jobs.append((os.path.join(folder, fn), os.path.join(folder, new_fn)))
        return jobs

    def _apply(self):
        jobs = self._build_jobs()
        if not jobs: return
        self._last_jobs = [(n, o) for o, n in jobs]
        _run_worker(self, jobs)

    def _undo(self):
        if not self._last_jobs:
            QMessageBox.information(self, "Undo", "Nothing to undo."); return
        if QMessageBox.question(self, "Undo", f"Reverse {len(self._last_jobs)} rename(s)?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
        jobs = self._last_jobs; self._last_jobs = []
        _run_worker(self, jobs)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Ordering / Numbering
# ══════════════════════════════════════════════════════════════════════════════
#
# Design principles that fix the previous bugs:
#
#  1. Each item carries a stable integer _uid so drag-drop can never confuse
#     two files that share the same stem/ext.
#  2. The drag-drop table NEVER relies on rowsMoved (which fires mid-drag
#     before Qt has settled the model).  Instead we override dropEvent,
#     compute the new order ourselves from the settled table state, and
#     then fully repopulate the table from self._items.  This is the only
#     reliable way to sync after an InternalMove drop.
#  3. The editable column stores the UID as UserRole data so _on_cell_changed
#     can look up the item by identity, not by row position.
#  4. _populate_table() is the single source of truth — every operation
#     (move-up, move-down, inline-edit, drop) mutates self._items and then
#     calls _populate_table() + _refresh_display().  No partial syncs.
# ─────────────────────────────────────────────────────────────────────────────

_uid_counter = 0

def _next_uid():
    global _uid_counter
    _uid_counter += 1
    return _uid_counter


class _DragDropTable(QTableWidget):
    """
    QTableWidget with a corrected dropEvent.
    Qt's built-in InternalMove drops rows but the rowsMoved signal fires
    before the model is fully settled, making it unsafe to read back the
    new order.  We intercept dropEvent, extract the drop destination, and
    emit our own signal with the (source_row, dest_row) pair.  The parent
    tab then mutates self._items directly and repopulates the table.
    """
    row_dropped = Signal(int, int)   # (from_row, to_row)

    def __init__(self, cols, parent=None):
        super().__init__(0, cols, parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragDropOverwriteMode(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(False)

    def dropEvent(self, event):
        # Which row is being dragged?
        src_row = self.currentRow()
        if src_row < 0:
            event.ignore()
            return

        # Where is the drop indicator pointing?
        drop_row = self.rowAt(event.position().toPoint().y())
        if drop_row < 0:
            drop_row = self.rowCount() - 1   # dropped below last row

        # Clamp and skip no-ops
        drop_row = max(0, min(drop_row, self.rowCount() - 1))
        if drop_row == src_row:
            event.ignore()
            return

        event.accept()
        self.row_dropped.emit(src_row, drop_row)


class _OrderingTab(QWidget):
    """
    Tab 4 — drag/drop reorder with gap-free sequential numbering.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items     = []   # list of dicts; each has a unique _uid
        self._last_jobs = []
        self._worker    = None
        self._editing   = False
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        self._folder_bar = _FolderBar(self._reload)
        lay.addWidget(self._folder_bar)

        info = QFrame()
        info.setStyleSheet(
            "background:#1A1A2A;border-radius:6px;border:1px solid #2A2A4A;")
        il = QHBoxLayout(info); il.setContentsMargins(12, 8, 12, 8)
        il.addWidget(_lbl(
            "Drag rows to reorder  •  Edit the '№' column to jump an item  "
            "•  ↑ / ↓ buttons nudge one step  •  Numbers update automatically.",
            "#7986CB", 12))
        lay.addWidget(info)

        # Options
        opt = QHBoxLayout(); opt.setSpacing(16)
        opt.addWidget(_lbl("Start at:"))
        self._start = QSpinBox(); self._start.setRange(0, 99999)
        self._start.setValue(1); self._start.setFixedWidth(70)
        self._start.setStyleSheet(_inp())
        self._start.valueChanged.connect(self._refresh_display)
        opt.addWidget(self._start)

        opt.addWidget(_lbl("Digits:"))
        self._digits = QSpinBox(); self._digits.setRange(1, 6)
        self._digits.setValue(3); self._digits.setFixedWidth(60)
        self._digits.setStyleSheet(_inp())
        self._digits.valueChanged.connect(self._refresh_display)
        opt.addWidget(self._digits)

        opt.addWidget(_lbl("Separator:"))
        self._sep = QComboBox(); self._sep.addItems(SEP_LABELS)
        self._sep.setFixedWidth(160); self._sep.setStyleSheet(_inp())
        self._sep.currentIndexChanged.connect(self._refresh_display)
        opt.addWidget(self._sep)

        self._strip_chk = QCheckBox("Strip existing prefix")
        self._strip_chk.setChecked(True)
        self._strip_chk.setStyleSheet("color:#888;font-size:12px;")
        self._strip_chk.stateChanged.connect(self._reload)
        opt.addWidget(self._strip_chk)

        opt.addWidget(_lbl("Extensions:"))
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText("blank = all")
        self._ext_edit.setFixedWidth(180); self._ext_edit.setStyleSheet(_inp())
        self._ext_edit.textChanged.connect(self._reload)
        opt.addWidget(self._ext_edit)
        opt.addStretch()
        lay.addLayout(opt)

        # Toolbar
        ctrl = QHBoxLayout()
        ctrl.addWidget(_lbl(
            "Drag rows · edit № · or use buttons to reorder", "#555", 11))
        ctrl.addStretch()

        btn_style = ("background:#2A2A2A;color:#E0E0E0;border:1px solid #3E3E3E;"
                     "border-radius:6px;font-size:12px;padding:0 14px;")
        self._up_btn = QPushButton("▲  Move Up")
        self._up_btn.setFixedHeight(30)
        self._up_btn.setStyleSheet(btn_style)
        self._up_btn.clicked.connect(self._move_up)
        ctrl.addWidget(self._up_btn)

        self._down_btn = QPushButton("▼  Move Down")
        self._down_btn.setFixedHeight(30)
        self._down_btn.setStyleSheet(btn_style)
        self._down_btn.clicked.connect(self._move_down)
        ctrl.addWidget(self._down_btn)
        lay.addLayout(ctrl)

        # Main table  (cols: №editable | filename | ext | →new name)
        self._table = _DragDropTable(4)
        self._table.setHorizontalHeaderLabels(["№", "Current filename", "Ext", "New filename"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setStyleSheet("""
            QTableWidget {
                background:#1A1A1A; border:none; font-size:12px;
                gridline-color:#2A2A2A;
            }
            QHeaderView::section {
                background:#252525; color:#888; border:none;
                padding:6px; font-size:11px;
            }
            QTableWidget::item { padding:4px 8px; }
            QTableWidget::item:selected { background:#1E2A3A; }
        """)
        self._table.row_dropped.connect(self._on_drop)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.itemSelectionChanged.connect(self._update_btn_states)
        lay.addWidget(self._table, 1)

        # Progress + status
        self._progress = _make_progress(); self._progress.hide()
        lay.addWidget(self._progress)
        self._status = _lbl("", "#888", 12)
        lay.addWidget(self._status)

        # Buttons
        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("✅  Apply Ordering & Numbers")
        self._apply_btn.setFixedHeight(38); self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            "background:#7C4DFF;color:#fff;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;")
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)

        undo_btn = QPushButton("↩  Undo")
        undo_btn.setFixedHeight(38)
        undo_btn.setStyleSheet(
            "background:#3A3A3A;color:#E0E0E0;border:none;"
            "border-radius:7px;font-size:13px;")
        undo_btn.clicked.connect(self._undo)
        btn_row.addWidget(undo_btn)
        btn_row.addStretch()
        self._count_lbl = _lbl("0 files", "#555")
        btn_row.addWidget(self._count_lbl)
        lay.addLayout(btn_row)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _reload(self):
        folder = self._folder_bar.folder
        if not folder:
            return
        exts = set()
        for p in self._ext_edit.text().lower().split():
            exts.add(p if p.startswith(".") else "." + p)
        files = sorted(
            [f for f in os.listdir(folder)
             if os.path.isfile(os.path.join(folder, f))],
            key=str.lower
        )
        if exts:
            files = [f for f in files
                     if os.path.splitext(f)[1].lower() in exts]

        strip = self._strip_chk.isChecked()
        self._items = []
        for fn in files:
            stem, ext = os.path.splitext(fn)
            num, sep, rest = _parse_prefix(stem)
            display_stem = rest if (strip and num is not None) else stem
            self._items.append({
                "_uid":     _next_uid(),
                "filename": fn,
                "stem":     display_stem,
                "ext":      ext,
            })

        self._populate_table()

    # ── Table population (single source of truth) ─────────────────────────────

    def _populate_table(self):
        """
        Completely rebuild the table from self._items.
        Every mutation (drop, move-up/down, inline-edit) ends here.
        """
        self._editing = True
        self._table.setRowCount(0)

        start  = self._start.value()
        digits = self._digits.value()
        sep    = SEPARATORS[self._sep.currentIndex()]

        for i, item in enumerate(self._items):
            num = start + i
            r   = self._table.rowCount()
            self._table.insertRow(r)

            # Col 0 — editable number; UID stored as UserRole for lookup
            num_cell = QTableWidgetItem(str(num))
            num_cell.setData(Qt.UserRole, item["_uid"])
            num_cell.setTextAlignment(Qt.AlignCenter)
            num_cell.setForeground(QColor("#7C4DFF"))
            num_cell.setFont(QFont("Consolas", 11, QFont.Bold))
            self._table.setItem(r, 0, num_cell)

            # Col 1 — current filename (read-only)
            fn_cell = QTableWidgetItem(item["filename"])
            fn_cell.setForeground(QColor("#888"))
            fn_cell.setFlags(fn_cell.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(r, 1, fn_cell)

            # Col 2 — extension (read-only)
            ext_cell = QTableWidgetItem(item["ext"])
            ext_cell.setForeground(QColor("#444"))
            ext_cell.setFlags(ext_cell.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(r, 2, ext_cell)

            # Col 3 — new filename preview (read-only)
            new_fn = f"{_fmt(num, digits)}{sep}{item['stem']}{item['ext']}"
            changed = new_fn != item["filename"]
            prev_cell = QTableWidgetItem(new_fn)
            prev_cell.setForeground(QColor("#00BFA5") if changed else QColor("#444"))
            prev_cell.setFlags(prev_cell.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(r, 3, prev_cell)

        self._editing = False
        self._count_lbl.setText(f"{len(self._items)} file(s)")
        self._apply_btn.setEnabled(len(self._items) > 0)
        self._update_btn_states()

    def _refresh_display(self):
        """Re-render numbers/previews without touching the item order."""
        self._populate_table()

    # ── Drag-drop handler ─────────────────────────────────────────────────────

    def _on_drop(self, src_row: int, dst_row: int):
        """Move item at src_row to dst_row, shift everything in between."""
        item = self._items.pop(src_row)
        self._items.insert(dst_row, item)
        self._populate_table()
        self._table.selectRow(dst_row)

    # ── Inline number editing ─────────────────────────────────────────────────

    def _on_cell_changed(self, row: int, col: int):
        if self._editing or col != 0:
            return
        cell = self._table.item(row, col)
        if not cell:
            return

        # Parse the typed number
        try:
            new_num = int(cell.text())
        except ValueError:
            self._populate_table()
            return

        start      = self._start.value()
        target_idx = new_num - start
        target_idx = max(0, min(target_idx, len(self._items) - 1))

        if target_idx == row:
            self._populate_table()
            return

        # Move item to typed position (same logic as drag-drop)
        item = self._items.pop(row)
        self._items.insert(target_idx, item)
        self._populate_table()
        self._table.selectRow(target_idx)

    # ── Move Up / Down ────────────────────────────────────────────────────────

    def _selected_row(self) -> int:
        sel = self._table.selectedItems()
        return self._table.row(sel[0]) if sel else -1

    def _move_up(self):
        r = self._selected_row()
        if r <= 0:
            return
        self._items[r], self._items[r - 1] = self._items[r - 1], self._items[r]
        self._populate_table()
        self._table.selectRow(r - 1)

    def _move_down(self):
        r = self._selected_row()
        if r < 0 or r >= len(self._items) - 1:
            return
        self._items[r], self._items[r + 1] = self._items[r + 1], self._items[r]
        self._populate_table()
        self._table.selectRow(r + 1)

    def _update_btn_states(self):
        r = self._selected_row()
        n = len(self._items)
        self._up_btn.setEnabled(r > 0)
        self._down_btn.setEnabled(0 <= r < n - 1)

    # ── Apply & Undo ──────────────────────────────────────────────────────────

    def _build_jobs(self):
        folder = self._folder_bar.folder
        start  = self._start.value()
        digits = self._digits.value()
        sep    = SEPARATORS[self._sep.currentIndex()]
        jobs   = []
        for i, item in enumerate(self._items):
            num    = start + i
            new_fn = f"{_fmt(num, digits)}{sep}{item['stem']}{item['ext']}"
            old    = os.path.join(folder, item["filename"])
            new    = os.path.join(folder, new_fn)
            if old != new:
                jobs.append((old, new))
        return jobs

    def _apply(self):
        jobs = self._build_jobs()
        if not jobs:
            self._status.setText("Nothing to rename — already in order.")
            return
        self._last_jobs = [(n, o) for o, n in jobs]
        _run_worker(self, jobs)

    def _undo(self):
        if not self._last_jobs:
            QMessageBox.information(self, "Undo", "Nothing to undo.")
            return
        if QMessageBox.question(
            self, "Undo", f"Reverse {len(self._last_jobs)} rename(s)?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        jobs = self._last_jobs; self._last_jobs = []
        _run_worker(self, jobs)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Assign / Fill Numbers
# ══════════════════════════════════════════════════════════════════════════════
#
# Shows ALL files in the folder split into two groups:
#   • Already numbered — displayed with their current prefix
#   • Unprefixed — shown with a "—" slot that the user can fill in
#
# The user can:
#   1. Type a number in the "Assign №" spin next to any unprefixed file.
#      On confirm the file is inserted at that position and every file
#      at that position or later shifts up by 1.
#   2. Click "Fill All Gaps" to compact the whole sequence so it is
#      gapless starting from the configured start value.
#   3. Click "Auto-assign Unprefixed" to append all unprefixed files
#      after the highest existing number, keeping order.
# ─────────────────────────────────────────────────────────────────────────────

class _AssignNumbersTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        # Each entry: {filename, stem (bare), ext, num (int|None), _uid}
        self._entries   = []
        self._last_jobs = []
        self._worker    = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        self._folder_bar = _FolderBar(self._reload)
        lay.addWidget(self._folder_bar)

        info = QFrame()
        info.setStyleSheet(
            "background:#2A1A1A;border-radius:6px;border:1px solid #4A2A2A;")
        il = QHBoxLayout(info); il.setContentsMargins(12, 8, 12, 8)
        il.addWidget(_lbl(
            "Files without a number prefix are shown in orange.  "
            "Assign a number to slot them into the sequence — all later files shift up by 1.  "
            "Use 'Fill All Gaps' to compact a sequence with holes.",
            "#FF8A65", 12))
        lay.addWidget(info)

        # Options
        opt = QHBoxLayout(); opt.setSpacing(16)
        opt.addWidget(_lbl("Start at:"))
        self._start = QSpinBox(); self._start.setRange(0, 99999)
        self._start.setValue(1); self._start.setFixedWidth(70)
        self._start.setStyleSheet(_inp())
        self._start.valueChanged.connect(self._rebuild_table)
        opt.addWidget(self._start)

        opt.addWidget(_lbl("Digits:"))
        self._digits = QSpinBox(); self._digits.setRange(1, 6)
        self._digits.setValue(3); self._digits.setFixedWidth(60)
        self._digits.setStyleSheet(_inp())
        self._digits.valueChanged.connect(self._rebuild_table)
        opt.addWidget(self._digits)

        opt.addWidget(_lbl("Separator:"))
        self._sep = QComboBox(); self._sep.addItems(SEP_LABELS)
        self._sep.setFixedWidth(160); self._sep.setStyleSheet(_inp())
        self._sep.currentIndexChanged.connect(self._rebuild_table)
        opt.addWidget(self._sep)

        opt.addWidget(_lbl("Extensions:"))
        self._ext_edit = QLineEdit()
        self._ext_edit.setPlaceholderText("blank = all")
        self._ext_edit.setFixedWidth(180); self._ext_edit.setStyleSheet(_inp())
        self._ext_edit.textChanged.connect(self._reload)
        opt.addWidget(self._ext_edit)
        opt.addStretch()
        lay.addLayout(opt)

        # Action buttons
        act = QHBoxLayout(); act.setSpacing(10)

        self._fill_btn = QPushButton("🔧  Fill All Gaps")
        self._fill_btn.setFixedHeight(32)
        self._fill_btn.setStyleSheet(
            "background:#37474F;color:#E0E0E0;border:none;"
            "border-radius:6px;font-size:12px;padding:0 16px;")
        self._fill_btn.clicked.connect(self._fill_gaps)
        act.addWidget(self._fill_btn)

        self._append_btn = QPushButton("⬇  Auto-assign Unprefixed (append)")
        self._append_btn.setFixedHeight(32)
        self._append_btn.setStyleSheet(
            "background:#37474F;color:#E0E0E0;border:none;"
            "border-radius:6px;font-size:12px;padding:0 16px;")
        self._append_btn.clicked.connect(self._auto_append)
        act.addWidget(self._append_btn)
        act.addStretch()

        self._gap_lbl = _lbl("", "#FF8A65", 12)
        act.addWidget(self._gap_lbl)
        lay.addLayout(act)

        # Table: current№ | filename | assign-spin | →new name
        lay.addWidget(_lbl(
            "Current sequence  (orange = unprefixed / needs a number)", "#555", 11))

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Current №", "Filename", "Assign №", "New filename"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget {
                background:#1A1A1A; border:none; font-size:12px;
                gridline-color:#2A2A2A;
            }
            QHeaderView::section {
                background:#252525; color:#888; border:none; padding:6px;
            }
            QTableWidget::item { padding:2px 8px; }
        """)
        lay.addWidget(self._table, 1)

        # Progress + status
        self._progress = _make_progress(); self._progress.hide()
        lay.addWidget(self._progress)
        self._status = _lbl("", "#888", 12)
        lay.addWidget(self._status)

        # Bottom buttons
        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("✅  Apply All Assignments")
        self._apply_btn.setFixedHeight(38); self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            "background:#FF6D00;color:#fff;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;")
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)

        undo_btn = QPushButton("↩  Undo")
        undo_btn.setFixedHeight(38)
        undo_btn.setStyleSheet(
            "background:#3A3A3A;color:#E0E0E0;border:none;"
            "border-radius:7px;font-size:13px;")
        undo_btn.clicked.connect(self._undo)
        btn_row.addWidget(undo_btn)
        btn_row.addStretch()
        self._count_lbl = _lbl("0 files", "#555")
        btn_row.addWidget(self._count_lbl)
        lay.addLayout(btn_row)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _reload(self):
        folder = self._folder_bar.folder
        if not folder:
            return
        exts = set()
        for p in self._ext_edit.text().lower().split():
            exts.add(p if p.startswith(".") else "." + p)
        files = sorted(
            [f for f in os.listdir(folder)
             if os.path.isfile(os.path.join(folder, f))],
            key=str.lower
        )
        if exts:
            files = [f for f in files
                     if os.path.splitext(f)[1].lower() in exts]

        self._entries = []
        for fn in files:
            stem, ext = os.path.splitext(fn)
            num, _sep, rest = _parse_prefix(stem)
            bare = rest if num is not None else stem
            self._entries.append({
                "_uid":     _next_uid(),
                "filename": fn,
                "stem":     bare,
                "ext":      ext,
                "num":      num,   # None = unprefixed
            })

        self._rebuild_table()

    # ── Sequence helpers ──────────────────────────────────────────────────────

    def _sorted_entries(self):
        """
        Return entries sorted: numbered ones first (by their number),
        then unprefixed ones appended at the end in filename order.
        Within the numbered group, preserve relative order for ties.
        """
        numbered   = [e for e in self._entries if e["num"] is not None]
        unprefixed = [e for e in self._entries if e["num"] is None]
        numbered.sort(key=lambda e: e["num"])
        return numbered + unprefixed

    def _gaps_and_unprefixed(self):
        start    = self._start.value()
        numbered = sorted(
            [e for e in self._entries if e["num"] is not None],
            key=lambda e: e["num"]
        )
        unprefixed = [e for e in self._entries if e["num"] is None]
        nums = [e["num"] for e in numbered]
        expected = set(range(start, start + len(numbered)))
        gaps = sorted(expected - set(nums))
        return gaps, unprefixed

    # ── Table rebuild ─────────────────────────────────────────────────────────

    def _rebuild_table(self):
        self._table.setRowCount(0)
        digits = self._digits.value()
        sep    = SEPARATORS[self._sep.currentIndex()]

        entries   = self._sorted_entries()
        gaps, unp = self._gaps_and_unprefixed()

        gap_txt = []
        if gaps:
            gap_txt.append(f"{len(gaps)} gap(s): " +
                           ", ".join(_fmt(g, digits) for g in gaps[:6]) +
                           ("…" if len(gaps) > 6 else ""))
        if unp:
            gap_txt.append(f"{len(unp)} unprefixed file(s)")
        self._gap_lbl.setText("  •  ".join(gap_txt) if gap_txt else "✅  Sequence is complete")

        for entry in entries:
            r = self._table.rowCount()
            self._table.insertRow(r)

            has_num  = entry["num"] is not None
            num_str  = _fmt(entry["num"], digits) if has_num else "—"
            new_fn   = (f"{_fmt(entry['num'], digits)}{sep}{entry['stem']}{entry['ext']}"
                        if has_num else entry["filename"])
            changed  = has_num and new_fn != entry["filename"]

            # Col 0 — current number
            c0 = QTableWidgetItem(num_str)
            c0.setTextAlignment(Qt.AlignCenter)
            c0.setForeground(QColor("#888") if has_num else QColor("#FF8A65"))
            self._table.setItem(r, 0, c0)

            # Col 1 — filename
            c1 = QTableWidgetItem(entry["filename"])
            c1.setForeground(QColor("#E0E0E0") if has_num else QColor("#FF8A65"))
            self._table.setItem(r, 1, c1)

            # Col 2 — assign spinbox (only meaningful for unprefixed)
            spin = QSpinBox()
            spin.setRange(self._start.value(), 99999)
            if has_num:
                spin.setValue(entry["num"])
                spin.setEnabled(True)
                spin.setStyleSheet(_inp() + "color:#888;")
            else:
                # Default suggestion: first available gap or end of sequence
                suggestion = gaps[0] if gaps else (
                    (max((e["num"] for e in self._entries if e["num"] is not None),
                         default=self._start.value() - 1) + 1)
                )
                spin.setValue(suggestion)
                spin.setStyleSheet(_inp() + "color:#FF8A65;font-weight:bold;")
                if gaps:
                    gaps = gaps[1:]   # consume suggestion

            uid = entry["_uid"]
            spin.valueChanged.connect(lambda v, u=uid: self._on_spin_changed(u, v))
            self._table.setCellWidget(r, 2, spin)

            # Col 3 — new filename preview
            c3 = QTableWidgetItem(new_fn)
            c3.setForeground(QColor("#00BFA5") if changed else
                             (QColor("#FF8A65") if not has_num else QColor("#444")))
            self._table.setItem(r, 3, c3)

        n = len(self._entries)
        self._count_lbl.setText(f"{n} file(s)")
        self._apply_btn.setEnabled(n > 0)

    # ── Spin-box assignment logic ─────────────────────────────────────────────

    def _on_spin_changed(self, uid: int, new_num: int):
        """
        When the user changes the spin for an entry (identified by uid),
        insert it at new_num and push every entry at >= new_num up by 1.
        """
        # Find the entry
        entry = next((e for e in self._entries if e["_uid"] == uid), None)
        if entry is None:
            return

        old_num = entry["num"]

        # Shift all other numbered entries that are >= new_num up by 1
        # (only if the slot is actually occupied)
        occupied = {e["num"] for e in self._entries
                    if e["num"] is not None and e["_uid"] != uid}
        if new_num in occupied:
            for e in self._entries:
                if e["_uid"] != uid and e["num"] is not None and e["num"] >= new_num:
                    e["num"] += 1

        entry["num"] = new_num
        self._rebuild_table()

    # ── Batch actions ─────────────────────────────────────────────────────────

    def _fill_gaps(self):
        """Compact: renumber all numbered entries sequentially from start."""
        start    = self._start.value()
        numbered = sorted(
            [e for e in self._entries if e["num"] is not None],
            key=lambda e: e["num"]
        )
        for i, e in enumerate(numbered):
            e["num"] = start + i
        self._rebuild_table()

    def _auto_append(self):
        """Assign numbers to all unprefixed entries, appending after highest existing."""
        numbered = [e for e in self._entries if e["num"] is not None]
        start    = self._start.value()
        next_num = (max(e["num"] for e in numbered) + 1) if numbered else start
        for e in self._entries:
            if e["num"] is None:
                e["num"] = next_num
                next_num += 1
        self._rebuild_table()

    # ── Apply & Undo ──────────────────────────────────────────────────────────

    def _build_jobs(self):
        """
        Build rename jobs from the current spin-box state.
        Read the assigned number for each row from the spin widget.
        """
        folder = self._folder_bar.folder
        digits = self._digits.value()
        sep    = SEPARATORS[self._sep.currentIndex()]
        jobs   = []

        # First pass: collect assignments from spin widgets
        assignments = {}   # uid → assigned_num
        for r in range(self._table.rowCount()):
            spin = self._table.cellWidget(r, 2)
            fn_cell = self._table.item(r, 1)
            if spin and fn_cell:
                fn = fn_cell.text()
                entry = next(
                    (e for e in self._entries if e["filename"] == fn), None)
                if entry:
                    assignments[entry["_uid"]] = spin.value()

        for entry in self._entries:
            num = assignments.get(entry["_uid"], entry["num"])
            if num is None:
                continue   # still unassigned — skip
            new_fn  = f"{_fmt(num, digits)}{sep}{entry['stem']}{entry['ext']}"
            old_path = os.path.join(folder, entry["filename"])
            new_path = os.path.join(folder, new_fn)
            if old_path != new_path:
                jobs.append((old_path, new_path))
        return jobs

    def _apply(self):
        jobs = self._build_jobs()
        if not jobs:
            self._status.setText("Nothing to rename.")
            return
        self._last_jobs = [(n, o) for o, n in jobs]
        _run_worker(self, jobs)

    def _undo(self):
        if not self._last_jobs:
            QMessageBox.information(self, "Undo", "Nothing to undo.")
            return
        if QMessageBox.question(
            self, "Undo", f"Reverse {len(self._last_jobs)} rename(s)?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return
        jobs = self._last_jobs; self._last_jobs = []
        _run_worker(self, jobs)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_progress():
    p = QProgressBar()
    p.setRange(0, 100); p.setValue(0); p.setFixedHeight(8); p.setTextVisible(False)
    p.setStyleSheet("QProgressBar{background:#252525;border-radius:4px;border:none;}"
                    "QProgressBar::chunk{background:#00BFA5;border-radius:4px;}")
    return p


def _run_worker(tab, jobs):
    tab._apply_btn.setEnabled(False)
    tab._progress.setValue(0); tab._progress.show()
    tab._status.setText("Renaming…")
    w = _RenameWorker(jobs)
    w.progress.connect(tab._progress.setValue)
    w.log.connect(lambda m: tab._status.setText(m))

    def on_done(results):
        tab._progress.hide()
        ok  = sum(1 for *_, s, _ in results if s)
        err = sum(1 for *_, s, _ in results if not s)
        tab._status.setText(
            f"✅ Done — {ok} renamed" + (f", {err} error(s)" if err else ""))
        tab._status.setStyleSheet(
            "color:#4CAF50;font-size:12px;" if not err else "color:#FF9800;font-size:12px;")
        tab._apply_btn.setEnabled(True)
        tab._reload()

    w.done.connect(on_done)
    tab._worker = w
    w.start()


# ══════════════════════════════════════════════════════════════════════════════
# Main tool widget
# ══════════════════════════════════════════════════════════════════════════════

class NumberPrefixTool(QWidget):
    name        = "Number Prefix"
    description = "Add or shift numeric prefixes on filenames"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 14, 24, 14)
        t = QLabel("🔢 Number Prefix")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        root.addWidget(hdr)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane  { background:#151515; border:none; }
            QTabBar::tab      { background:#1E1E1E; color:#888; padding:10px 24px;
                                border:none; font-size:13px; }
            QTabBar::tab:selected { background:#151515; color:#00BFA5;
                                    border-bottom:2px solid #00BFA5; }
            QTabBar::tab:hover    { color:#E0E0E0; }
        """)
        tabs.addTab(_AddPrefixTab(),      "➕  Add Prefix")
        tabs.addTab(_IncreaseAllTab(),   "⬆  Increase All Numbers")
        tabs.addTab(_IncreaseAfterTab(), "🎯  Increase From Number")
        tabs.addTab(_OrderingTab(),      "⇅  Ordering / Numbering")
        tabs.addTab(_AssignNumbersTab(), "🔀  Assign / Fill Numbers")
        root.addWidget(tabs, 1)