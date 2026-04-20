"""
Number Prefix — 3 modes in one tool:

  1. Add Prefix      — add sequential numbers to filenames (001_photo.jpg)
  2. Increase All    — bump every existing prefix by N  (003_ → 008_ when +5)
  3. Increase After  — bump only files whose prefix >= threshold  (insert gap)

All modes share: live preview table, sort options, undo, progress bar.
"""
import os
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QSpinBox, QCheckBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QMessageBox, QProgressBar, QSizePolicy, QTabWidget,
    QScrollArea, QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor


# ── Constants ─────────────────────────────────────────────────────────────────

SEPARATORS    = ["_", "-", ". ", " "]
SEP_LABELS    = ["_  (underscore)", "-  (dash)", ".  (dot+space)", "   (space)"]
SORT_OPTIONS  = [
    "Name (A → Z)", "Name (Z → A)",
    "Date modified (oldest first)", "Date modified (newest first)",
    "Size (smallest first)", "Size (largest first)",
    "Keep current order",
]

_NUM_RE = re.compile(r"^(\d+)([_\-\s\.]+)(.*)", re.DOTALL)   # captures prefix+sep+rest


def _parse_prefix(stem: str):
    """
    Returns (number, separator, rest) if stem starts with a numeric prefix,
    else (None, '', stem).
    """
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
    done     = Signal(list)   # [(old_path, new_path, ok, err_str)]
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
                        raise FileExistsError(f"Target already exists")
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
    """
    rows = [(number_label, original_name, new_name, changed: bool)]
    """
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

        # Folder
        self._folder_bar = _FolderBar(self._reload)
        lay.addWidget(self._folder_bar)

        # Options
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

    # ── helpers ───────────────────────────────────────────────────────────────
    def _sep_char(self): return SEPARATORS[self._sep.currentIndex()]

    def _sorted(self, files):
        idx = self._sort.currentIndex()
        folder = self._folder_bar.folder
        mt = lambda f: os.path.getmtime(os.path.join(folder, f)) if os.path.exists(os.path.join(folder, f)) else 0
        sz = lambda f: os.path.getsize(os.path.join(folder, f)) if os.path.exists(os.path.join(folder, f)) else 0
        ops = [lambda f: f.lower(), lambda f: f.lower(),
               mt, mt, sz, sz, lambda f: 0]
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

        # Help text
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
                if skip_no_prefix:
                    rows.append(("—", fn, fn, False)); continue
                else:
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
    """
    Only bumps files whose prefix >= a threshold.
    Use case: you want to insert a new file as #005, so you shift
    everything from 005 upwards by 1 to make room.
    """
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

        # Visual example
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

        # Connect spinboxes to update example
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
        # When shifting up, rename highest numbers first to avoid conflicts
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


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_progress():
    p = QProgressBar()
    p.setRange(0, 100); p.setValue(0); p.setFixedHeight(8); p.setTextVisible(False)
    p.setStyleSheet("QProgressBar{background:#252525;border-radius:4px;border:none;}"
                    "QProgressBar::chunk{background:#00BFA5;border-radius:4px;}")
    return p


def _run_worker(tab, jobs):
    """Shared rename runner — attaches to the tab's progress/status/apply_btn."""
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
        tabs.addTab(_AddPrefixTab(),    "➕  Add Prefix")
        tabs.addTab(_IncreaseAllTab(),  "⬆  Increase All Numbers")
        tabs.addTab(_IncreaseAfterTab(),"🎯  Increase From Number")
        root.addWidget(tabs, 1)