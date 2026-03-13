"""
File Manager & Cleaner — browse, duplicate scan, large-file finder,
extension breakdown, folder size tree, quick delete/open.
"""

import os
import hashlib
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QFrame, QFileDialog,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QMessageBox, QLineEdit, QAbstractItemView,
    QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor


# ── Worker threads ─────────────────────────────────────────────────────────────
class DupeScanWorker(QThread):
    progress  = Signal(int, int)   # (done, total)
    found     = Signal(list)       # list of groups [[path, path, ...], ...]
    finished_ = Signal()

    def __init__(self, root_path):
        super().__init__()
        self.root_path = root_path
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        # 1) group by size
        size_map = {}
        all_files = []
        for dirpath, _, filenames in os.walk(self.root_path):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    sz = os.path.getsize(p)
                    size_map.setdefault(sz, []).append(p)
                    all_files.append(p)
                except Exception:
                    pass
        # 2) for size groups > 1, hash
        candidates = [paths for paths in size_map.values() if len(paths) > 1]
        total = sum(len(g) for g in candidates)
        done = 0
        hash_map = {}
        for group in candidates:
            for path in group:
                if self._stop:
                    return
                try:
                    h = self._md5(path)
                    hash_map.setdefault(h, []).append(path)
                except Exception:
                    pass
                done += 1
                self.progress.emit(done, total)
        dupes = [g for g in hash_map.values() if len(g) > 1]
        self.found.emit(dupes)
        self.finished_.emit()

    def _md5(self, path):
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()


class FolderSizeWorker(QThread):
    done = Signal(dict)   # {path: size_bytes}

    def __init__(self, root_path):
        super().__init__()
        self.root_path = root_path

    def run(self):
        result = {}
        try:
            for entry in os.scandir(self.root_path):
                if entry.is_dir(follow_symlinks=False):
                    result[entry.path] = self._du(entry.path)
                else:
                    result[entry.path] = entry.stat(follow_symlinks=False).st_size
        except Exception:
            pass
        self.done.emit(result)

    def _du(self, path):
        total = 0
        try:
            for dirpath, _, files in os.walk(path):
                for fn in files:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, fn))
                    except Exception:
                        pass
        except Exception:
            pass
        return total


def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# ── Tab: File Browser ─────────────────────────────────────────────────────────
class FileBrowserTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = str(Path.home())
        self._build_ui()
        self._browse(self._current_path)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        nav = QHBoxLayout()
        up_btn = QPushButton("⬆ Up")
        up_btn.clicked.connect(self._go_up)
        nav.addWidget(up_btn)
        home_btn = QPushButton("🏠 Home")
        home_btn.clicked.connect(lambda: self._browse(str(Path.home())))
        nav.addWidget(home_btn)
        self._path_edit = QLineEdit()
        self._path_edit.returnPressed.connect(lambda: self._browse(self._path_edit.text()))
        nav.addWidget(self._path_edit, 1)
        choose_btn = QPushButton("📁 Choose")
        choose_btn.clicked.connect(self._choose_dir)
        nav.addWidget(choose_btn)
        root.addLayout(nav)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Size", "Type", "Modified"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tree.setColumnWidth(1, 90)
        self._tree.setColumnWidth(2, 80)
        self._tree.setSortingEnabled(True)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        root.addWidget(self._tree, 1)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("🔗 Open")
        open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(open_btn)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet("color:#888; font-size:11px;")
        btn_row.addWidget(self._status)
        root.addLayout(btn_row)

    def _browse(self, path):
        if not os.path.isdir(path):
            return
        self._current_path = path
        self._path_edit.setText(path)
        self._tree.clear()
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            self._status.setText("⛔ Permission denied")
            return
        total_size = 0
        for e in entries:
            item = QTreeWidgetItem()
            item.setText(0, ("📁 " if e.is_dir() else "📄 ") + e.name)
            item.setData(0, Qt.UserRole, e.path)
            try:
                stat = e.stat(follow_symlinks=False)
                sz = stat.st_size
                total_size += sz
                item.setText(1, _fmt_size(sz) if not e.is_dir() else "—")
                import datetime
                item.setText(3, datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"))
            except Exception:
                pass
            ext = Path(e.name).suffix.upper().lstrip(".") or "DIR"
            item.setText(2, ext)
            self._tree.addTopLevelItem(item)
        self._status.setText(f"{self._tree.topLevelItemCount()} items  |  {_fmt_size(total_size)}")

    def _go_up(self):
        parent = str(Path(self._current_path).parent)
        self._browse(parent)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder", self._current_path)
        if d:
            self._browse(d)

    def _on_double_click(self, item, _):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isdir(path):
            self._browse(path)

    def _open_selected(self):
        item = self._tree.currentItem()
        if not item:
            return
        path = item.data(0, Qt.UserRole)
        import subprocess, sys
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _delete_selected(self):
        item = self._tree.currentItem()
        if not item:
            return
        path = item.data(0, Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Permanently delete:\n{path}?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            self._browse(self._current_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ── Tab: Duplicate Finder ──────────────────────────────────────────────────────
class DupesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        hdr = QHBoxLayout()
        self._path_lbl = QLabel("No folder selected")
        self._path_lbl.setStyleSheet("color:#888;")
        hdr.addWidget(self._path_lbl, 1)
        choose_btn = QPushButton("📁 Select Folder")
        choose_btn.clicked.connect(self._choose)
        hdr.addWidget(choose_btn)
        self._scan_btn = QPushButton("🔍 Scan for Duplicates")
        self._scan_btn.clicked.connect(self._scan)
        hdr.addWidget(self._scan_btn)
        root.addLayout(hdr)

        self._progress = QProgressBar()
        self._progress.hide()
        root.addWidget(self._progress)

        self._result_tree = QTreeWidget()
        self._result_tree.setHeaderLabels(["File", "Size"])
        self._result_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        root.addWidget(self._result_tree, 1)

        btn_row = QHBoxLayout()
        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        self._summary = QLabel("")
        self._summary.setStyleSheet("color:#888; font-size:11px;")
        btn_row.addWidget(self._summary)
        root.addLayout(btn_row)
        self._scan_path = None

    def _choose(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d:
            self._scan_path = d
            self._path_lbl.setText(d)

    def _scan(self):
        if not self._scan_path:
            QMessageBox.information(self, "Select Folder", "Choose a folder first.")
            return
        self._result_tree.clear()
        self._progress.show()
        self._progress.setRange(0, 0)
        self._scan_btn.setEnabled(False)
        self._worker = DupeScanWorker(self._scan_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.found.connect(self._on_found)
        self._worker.finished_.connect(lambda: (self._scan_btn.setEnabled(True), self._progress.hide()))
        self._worker.start()

    def _on_progress(self, done, total):
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_found(self, groups):
        self._result_tree.clear()
        total_waste = 0
        for group in groups:
            try:
                sz = os.path.getsize(group[0])
            except Exception:
                sz = 0
            waste = sz * (len(group) - 1)
            total_waste += waste
            parent = QTreeWidgetItem([f"🔄 {len(group)} duplicates  ({_fmt_size(sz)} each)", _fmt_size(sz)])
            parent.setForeground(0, QColor("#FF9800"))
            for path in group:
                child = QTreeWidgetItem([path, _fmt_size(sz)])
                child.setData(0, Qt.UserRole, path)
                parent.addChild(child)
            self._result_tree.addTopLevelItem(parent)
            parent.setExpanded(True)
        self._summary.setText(f"{len(groups)} duplicate groups  |  {_fmt_size(total_waste)} wasted")

    def _delete_selected(self):
        items = self._result_tree.selectedItems()
        paths = [i.data(0, Qt.UserRole) for i in items if i.data(0, Qt.UserRole)]
        if not paths:
            return
        if QMessageBox.question(self, "Delete", f"Delete {len(paths)} file(s)?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        for path in paths:
            try:
                os.remove(path)
            except Exception:
                pass
        self._scan()


# ── Tab: Large Files ───────────────────────────────────────────────────────────
class LargeFilesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        hdr = QHBoxLayout()
        self._path_lbl = QLabel("No folder selected")
        self._path_lbl.setStyleSheet("color:#888;")
        hdr.addWidget(self._path_lbl, 1)
        choose_btn = QPushButton("📁 Select Folder")
        choose_btn.clicked.connect(self._choose)
        hdr.addWidget(choose_btn)
        scan_btn = QPushButton("🔍 Find Large Files")
        scan_btn.clicked.connect(self._scan)
        hdr.addWidget(scan_btn)
        root.addLayout(hdr)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["File Path", "Size", "Extension"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self._table, 1)

        btn_row = QHBoxLayout()
        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)
        self._scan_path = None

    def _choose(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d:
            self._scan_path = d
            self._path_lbl.setText(d)

    def _scan(self):
        if not self._scan_path:
            return
        files = []
        for dirpath, _, filenames in os.walk(self._scan_path):
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    sz = os.path.getsize(p)
                    files.append((p, sz))
                except Exception:
                    pass
        files.sort(key=lambda x: -x[1])
        top = files[:200]
        self._table.setRowCount(0)
        for path, sz in top:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(path))
            size_item = QTableWidgetItem(_fmt_size(sz))
            size_item.setData(Qt.UserRole, sz)
            self._table.setItem(r, 1, size_item)
            self._table.setItem(r, 2, QTableWidgetItem(Path(path).suffix.upper().lstrip(".") or "—"))

    def _delete_selected(self):
        rows = set(i.row() for i in self._table.selectedIndexes())
        paths = [self._table.item(r, 0).text() for r in rows]
        if not paths:
            return
        if QMessageBox.question(self, "Delete", f"Delete {len(paths)} file(s)?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        for p in paths:
            try:
                os.remove(p)
            except Exception:
                pass
        self._scan()


# ── Main Tool ──────────────────────────────────────────────────────────────────
class FileManagerTool(QWidget):
    name = "File Manager"
    description = "Browse files, find duplicates, locate large files"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("🗂️ File Manager & Cleaner")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        root.addWidget(hdr)

        tabs = QTabWidget()
        tabs.addTab(FileBrowserTab(),  "📁 Browser")
        tabs.addTab(DupesTab(),        "🔄 Duplicate Finder")
        tabs.addTab(LargeFilesTab(),   "📦 Large Files")
        root.addWidget(tabs, 1)
