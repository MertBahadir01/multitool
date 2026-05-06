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
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor


# ── Helpers ────────────────────────────────────────────────────────────────────
def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# ── Worker: duplicate scanner ──────────────────────────────────────────────────
class DupeScanWorker(QThread):
    progress  = Signal(int, int)   # (done, total)
    found     = Signal(list)       # list of groups [[path, path, ...], ...]
    finished_ = Signal()

    def __init__(self, root_paths, ignored=None, cross_only=False):
        """
        root_paths : str | list[str]  — one or more folders to walk
        ignored    : list[str]        — subpaths to skip entirely
        cross_only : bool             — only emit groups that span >1 root
        """
        super().__init__()
        if isinstance(root_paths, str):
            root_paths = [root_paths]
        self.root_paths  = [os.path.normpath(r) for r in root_paths]
        self._stop       = False
        self._ignored    = [os.path.normpath(p) for p in (ignored or [])]
        self._cross_only = cross_only

    def stop(self):
        self._stop = True

    def _is_ignored(self, path):
        norm = os.path.normpath(path)
        for ig in self._ignored:
            if norm == ig or norm.startswith(ig + os.sep):
                return True
        return False

    def _root_of(self, path):
        norm = os.path.normpath(path)
        for r in self.root_paths:
            if norm == r or norm.startswith(r + os.sep):
                return r
        return None

    def run(self):
        # 1) collect by size across all roots
        size_map = {}
        for root in self.root_paths:
            for dirpath, dirs, filenames in os.walk(root):
                dirs[:] = [d for d in dirs
                           if not self._is_ignored(os.path.join(dirpath, d))]
                if self._is_ignored(dirpath):
                    continue
                for fn in filenames:
                    p = os.path.join(dirpath, fn)
                    try:
                        sz = os.path.getsize(p)
                        size_map.setdefault(sz, []).append(p)
                    except Exception:
                        pass

        # 2) hash candidates
        candidates = [paths for paths in size_map.values() if len(paths) > 1]
        total = sum(len(g) for g in candidates)
        done  = 0
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

        # 3) cross-only filter — keep groups that touch more than one root
        if self._cross_only and len(self.root_paths) > 1:
            filtered = []
            for group in dupes:
                roots_seen = {self._root_of(p) for p in group}
                if len(roots_seen) > 1:
                    filtered.append(group)
            dupes = filtered

        self.found.emit(dupes)
        self.finished_.emit()

    def _md5(self, path):
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()


# ── Worker: folder sizes ───────────────────────────────────────────────────────
class FolderSizeWorker(QThread):
    done = Signal(dict)

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


# ── Tab: File Browser ──────────────────────────────────────────────────────────
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
                import datetime
                stat = e.stat(follow_symlinks=False)
                sz = stat.st_size
                total_size += sz
                item.setText(1, _fmt_size(sz) if not e.is_dir() else "—")
                item.setText(3, datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"))
            except Exception:
                pass
            ext = Path(e.name).suffix.upper().lstrip(".") or "DIR"
            item.setText(2, ext)
            self._tree.addTopLevelItem(item)
        self._status.setText(f"{self._tree.topLevelItemCount()} items  |  {_fmt_size(total_size)}")

    def _go_up(self):
        self._browse(str(Path(self._current_path).parent))

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


# ── Shared results panel ───────────────────────────────────────────────────────
class _ResultsPanel(QWidget):
    """
    Reusable panel: progress bar + checkable results tree + action bar.
    root_color_map: {norm_root_str: QColor} — colour rows by origin folder.
    Pass None for single-folder mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked_items = set()
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._progress = QProgressBar()
        self._progress.hide()
        lay.addWidget(self._progress)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["File", "Size"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tree.setColumnWidth(1, 100)
        self._tree.setSelectionMode(QAbstractItemView.NoSelection)
        self._tree.setStyleSheet(
            "QTreeWidget { font-size: 13px; }"
            "QTreeWidget::item { padding: 5px 2px; min-height: 28px; }"
            "QTreeWidget::item:has-children { color: #FF9800; font-weight: bold; padding: 6px 2px; }"
        )
        self._tree.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self._tree, 1)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("☑ Select All",         self._select_all),
            ("☐ Deselect All",       self._deselect_all),
            ("⚡ Select Dupes Only",  self._select_dupes_only),
        ]:
            b = QPushButton(label)
            b.setMinimumHeight(32)
            b.clicked.connect(slot)
            btn_row.addWidget(b)

        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.setMinimumHeight(32)
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()

        self._sel_label = QLabel("")
        self._sel_label.setStyleSheet("color:#00BFA5; font-size:12px; font-weight:bold;")
        btn_row.addWidget(self._sel_label)

        self._summary = QLabel("")
        self._summary.setStyleSheet("color:#888; font-size:12px; margin-left:12px;")
        btn_row.addWidget(self._summary)

        lay.addLayout(btn_row)

    def progress_bar(self):
        return self._progress

    def populate(self, groups, root_color_map=None):
        self._tree.blockSignals(True)
        self._tree.clear()
        self._checked_items.clear()
        total_waste = 0
        for group in groups:
            try:
                sz = os.path.getsize(group[0])
            except Exception:
                sz = 0
            total_waste += sz * (len(group) - 1)
            parent = QTreeWidgetItem([f"🔄  {len(group)} duplicates  ·  {_fmt_size(sz)} each", _fmt_size(sz)])
            parent.setForeground(0, QColor("#FF9800"))
            parent.setFlags(parent.flags() & ~Qt.ItemIsUserCheckable)
            parent.setData(0, Qt.UserRole, None)
            parent.setData(1, Qt.UserRole, sz)
            for path in group:
                child = QTreeWidgetItem([path, _fmt_size(sz)])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Unchecked)
                child.setData(0, Qt.UserRole, path)
                child.setData(1, Qt.UserRole, sz)
                if root_color_map:
                    norm = os.path.normpath(path)
                    for root, color in root_color_map.items():
                        if norm == root or norm.startswith(root + os.sep):
                            child.setForeground(0, color)
                            break
                parent.addChild(child)
            self._tree.addTopLevelItem(parent)
            parent.setExpanded(True)
        self._tree.blockSignals(False)
        self._summary.setText(f"{len(groups)} duplicate groups  |  {_fmt_size(total_waste)} wasted")
        self._update_sel_label()

    def clear(self):
        self._tree.blockSignals(True)
        self._tree.clear()
        self._checked_items.clear()
        self._tree.blockSignals(False)
        self._summary.setText("")
        self._update_sel_label()

    def _on_item_changed(self, item, column):
        if column != 0 or item.data(0, Qt.UserRole) is None:
            return
        if item.checkState(0) == Qt.Checked:
            self._checked_items.add(item)
        else:
            self._checked_items.discard(item)
        self._update_sel_label()

    def _all_leaf_items(self):
        leaves = []
        for i in range(self._tree.topLevelItemCount()):
            p = self._tree.topLevelItem(i)
            for j in range(p.childCount()):
                leaves.append(p.child(j))
        return leaves

    def _select_all(self):
        self._tree.blockSignals(True)
        for item in self._all_leaf_items():
            item.setCheckState(0, Qt.Checked)
            self._checked_items.add(item)
        self._tree.blockSignals(False)
        self._update_sel_label()

    def _deselect_all(self):
        self._tree.blockSignals(True)
        for item in self._checked_items:
            item.setCheckState(0, Qt.Unchecked)
        self._checked_items.clear()
        self._tree.blockSignals(False)
        self._update_sel_label()

    def _select_dupes_only(self):
        self._tree.blockSignals(True)
        for item in self._checked_items:
            item.setCheckState(0, Qt.Unchecked)
        self._checked_items.clear()
        for i in range(self._tree.topLevelItemCount()):
            p = self._tree.topLevelItem(i)
            for j in range(1, p.childCount()):
                item = p.child(j)
                item.setCheckState(0, Qt.Checked)
                self._checked_items.add(item)
        self._tree.blockSignals(False)
        self._update_sel_label()

    def _update_sel_label(self):
        count = len(self._checked_items)
        if count == 0:
            self._sel_label.setText("")
            return
        total_sz = sum(i.data(1, Qt.UserRole) or 0 for i in self._checked_items)
        self._sel_label.setText(f"✔ {count} selected  ·  {_fmt_size(total_sz)}")

    def _delete_selected(self):
        if not self._checked_items:
            return
        count    = len(self._checked_items)
        total_sz = sum(i.data(1, Qt.UserRole) or 0 for i in self._checked_items)
        if QMessageBox.question(
            self, "Delete",
            f"Permanently delete {count} file(s)  ({_fmt_size(total_sz)})?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        self._tree.blockSignals(True)
        failed = []
        for item in list(self._checked_items):
            path = item.data(0, Qt.UserRole)
            try:
                os.remove(path)
                parent = item.parent()
                parent.removeChild(item)
                self._checked_items.discard(item)
                if parent.childCount() <= 1:
                    idx = self._tree.indexOfTopLevelItem(parent)
                    self._tree.takeTopLevelItem(idx)
                    if parent.childCount() == 1:
                        self._checked_items.discard(parent.child(0))
            except Exception as e:
                failed.append(f"{path}: {e}")
        self._tree.blockSignals(False)

        total_waste = 0
        groups_left = 0
        for i in range(self._tree.topLevelItemCount()):
            p  = self._tree.topLevelItem(i)
            sz = p.data(1, Qt.UserRole) or 0
            n  = p.childCount()
            if n > 1:
                groups_left += 1
                total_waste += sz * (n - 1)
        self._summary.setText(f"{groups_left} duplicate groups  |  {_fmt_size(total_waste)} wasted")
        self._update_sel_label()

        if failed:
            QMessageBox.warning(self, "Some deletions failed", "\n".join(failed))


# ── Tab: Duplicate Finder ──────────────────────────────────────────────────────
class DupesTab(QWidget):
    _COMPARE_COLORS = [
        QColor("#4FC3F7"), QColor("#CE93D8"), QColor("#81C784"), QColor("#FFB74D"),
        QColor("#E57373"), QColor("#64B5F6"), QColor("#BA68C8"), QColor("#4DB6AC"),
        QColor("#FFD54F"), QColor("#A1887F"), QColor("#90A4AE"), QColor("#F06292"),
        QColor("#9575CD"), QColor("#DCE775"), QColor("#FF8A65"), QColor("#7986CB"),
        QColor("#AED581"), QColor("#4DD0E1"), QColor("#FFCA28"), QColor("#E0E0E0"),
    
        QColor("#26C6DA"), QColor("#AB47BC"), QColor("#66BB6A"), QColor("#FFA726"),
        QColor("#EF5350"), QColor("#42A5F5"), QColor("#7E57C2"), QColor("#26A69A"),
        QColor("#FFEE58"), QColor("#8D6E63"), QColor("#78909C"), QColor("#EC407A"),
        QColor("#5C6BC0"), QColor("#C0CA33"), QColor("#FF7043"), QColor("#9FA8DA"),
        QColor("#9CCC65"), QColor("#26C6DA"), QColor("#FFB300"), QColor("#BDBDBD"),
    
        QColor("#00ACC1"), QColor("#8E24AA"), QColor("#43A047"), QColor("#FB8C00"),
        QColor("#E53935"), QColor("#1E88E5"), QColor("#5E35B1"), QColor("#00897B"),
        QColor("#FDD835"), QColor("#6D4C41"), QColor("#546E7A"), QColor("#D81B60"),
        QColor("#3949AB"), QColor("#AFB42B"), QColor("#F4511E"), QColor("#7986CB"),
        QColor("#7CB342"), QColor("#00BCD4"), QColor("#FFA000"), QColor("#9E9E9E"),
    
        QColor("#0097A7"), QColor("#6A1B9A"), QColor("#2E7D32"), QColor("#EF6C00"),
        QColor("#C62828"), QColor("#1565C0"), QColor("#4527A0"), QColor("#00695C"),
        QColor("#F9A825"), QColor("#5D4037"), QColor("#455A64"), QColor("#AD1457"),
        QColor("#283593"), QColor("#9E9D24"), QColor("#D84315"), QColor("#5C6BC0"),
        QColor("#558B2F"), QColor("#00838F"), QColor("#FF8F00"), QColor("#757575"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker          = None
        self._scan_path       = None
        self._ignored_folders = []
        self._compare_folders = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── top bar ────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._path_lbl = QLabel("No folder selected")
        self._path_lbl.setStyleSheet("color:#888; font-size:13px;")
        hdr.addWidget(self._path_lbl, 1)

        choose_btn = QPushButton("📁 Select Folder")
        choose_btn.setMinimumHeight(34)
        choose_btn.clicked.connect(self._choose)
        hdr.addWidget(choose_btn)

        self._scan_btn = QPushButton("🔍 Scan for Duplicates")
        self._scan_btn.setMinimumHeight(34)
        self._scan_btn.clicked.connect(self._scan_single)
        hdr.addWidget(self._scan_btn)
        root.addLayout(hdr)

        # ── splitter: side panel | results ────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # ── Left: tabbed side panel ────────────────────────────────────────
        side_tabs = QTabWidget()
        side_tabs.setMinimumWidth(210)
        side_tabs.setMaximumWidth(300)
        side_tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #3A3A3A; border-radius:4px; background:#1A1A1A; }"
            "QTabBar::tab { padding:6px 10px; font-size:11px; }"
            "QTabBar::tab:selected { color:#FF9800; border-bottom:2px solid #FF9800; }"
        )

        # ── Side tab 1: Ignored Folders ────────────────────────────────────
        ignore_widget = QWidget()
        ign_lay = QVBoxLayout(ignore_widget)
        ign_lay.setContentsMargins(8, 8, 8, 8)
        ign_lay.setSpacing(6)

        ign_hint = QLabel("Subfolders listed here are\nskipped entirely during scan.")
        ign_hint.setStyleSheet("color:#666; font-size:11px;")
        ign_lay.addWidget(ign_hint)

        self._ignore_list = QTreeWidget()
        self._ignore_list.setHeaderHidden(True)
        self._ignore_list.setRootIsDecorated(False)
        self._ignore_list.setStyleSheet(
            "QTreeWidget { background:#111; border:1px solid #333; border-radius:4px; font-size:12px; }"
            "QTreeWidget::item { padding: 4px 2px; }"
        )
        ign_lay.addWidget(self._ignore_list, 1)

        ign_btn_row = QHBoxLayout()
        add_ign = QPushButton("+ Add")
        add_ign.setMinimumHeight(30)
        add_ign.clicked.connect(self._add_ignore)
        ign_btn_row.addWidget(add_ign)
        rem_ign = QPushButton("− Remove")
        rem_ign.setMinimumHeight(30)
        rem_ign.setObjectName("secondary")
        rem_ign.clicked.connect(self._remove_ignore)
        ign_btn_row.addWidget(rem_ign)
        ign_lay.addLayout(ign_btn_row)

        side_tabs.addTab(ignore_widget, "🚫 Ignored")

        # ── Side tab 2: Compare Folders ────────────────────────────────────
        compare_widget = QWidget()
        cmp_lay = QVBoxLayout(compare_widget)
        cmp_lay.setContentsMargins(8, 8, 8, 8)
        cmp_lay.setSpacing(6)

        cmp_hint = QLabel(
            "Add 2+ folders.\n"
            "Scan finds duplicates that exist\n"
            "across the listed folders.\n\n"
            "Results are colour-coded:"
        )
        cmp_hint.setStyleSheet("color:#666; font-size:11px;")
        cmp_lay.addWidget(cmp_hint)

        # colour legend — rebuilt dynamically
        self._legend_frame = QFrame()
        self._legend_lay   = QVBoxLayout(self._legend_frame)
        self._legend_lay.setContentsMargins(0, 0, 0, 0)
        self._legend_lay.setSpacing(2)
        cmp_lay.addWidget(self._legend_frame)

        self._compare_list = QTreeWidget()
        self._compare_list.setHeaderHidden(True)
        self._compare_list.setRootIsDecorated(False)
        self._compare_list.setStyleSheet(
            "QTreeWidget { background:#111; border:1px solid #333; border-radius:4px; font-size:12px; }"
            "QTreeWidget::item { padding: 4px 2px; }"
        )
        cmp_lay.addWidget(self._compare_list, 1)

        cmp_btn_row = QHBoxLayout()
        add_cmp = QPushButton("+ Add Folder")
        add_cmp.setMinimumHeight(30)
        add_cmp.clicked.connect(self._add_compare)
        cmp_btn_row.addWidget(add_cmp)
        rem_cmp = QPushButton("− Remove")
        rem_cmp.setMinimumHeight(30)
        rem_cmp.setObjectName("secondary")
        rem_cmp.clicked.connect(self._remove_compare)
        cmp_btn_row.addWidget(rem_cmp)
        cmp_lay.addLayout(cmp_btn_row)

        self._cmp_scan_btn = QPushButton("🔀 Scan Across Folders")
        self._cmp_scan_btn.setMinimumHeight(34)
        self._cmp_scan_btn.setStyleSheet(
            "QPushButton { background:#1565C0; color:white; border-radius:5px; font-weight:bold; }"
            "QPushButton:hover { background:#1976D2; }"
            "QPushButton:disabled { background:#333; color:#666; }"
        )
        self._cmp_scan_btn.clicked.connect(self._scan_compare)
        cmp_lay.addWidget(self._cmp_scan_btn)

        side_tabs.addTab(compare_widget, "🔀 Compare")

        splitter.addWidget(side_tabs)

        # ── Right: shared results panel ────────────────────────────────────
        self._results = _ResultsPanel()
        splitter.addWidget(self._results)
        splitter.setSizes([240, 580])

        root.addWidget(splitter, 1)

    # ── ignored folders ──────────────────────────────────────────────────────
    def _add_ignore(self):
        base = self._scan_path or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Select Folder to Ignore", base)
        if not d:
            return
        if self._scan_path and not d.startswith(self._scan_path):
            QMessageBox.warning(self, "Warning",
                "That folder is not inside the selected scan root.\n"
                "It will have no effect unless it is a subfolder of the scan path.")
        if d not in self._ignored_folders:
            self._ignored_folders.append(d)
            item = QTreeWidgetItem([d])
            item.setToolTip(0, d)
            item.setForeground(0, QColor("#FF9800"))
            self._ignore_list.addTopLevelItem(item)

    def _remove_ignore(self):
        item = self._ignore_list.currentItem()
        if not item:
            return
        path = item.text(0)
        if path in self._ignored_folders:
            self._ignored_folders.remove(path)
        self._ignore_list.takeTopLevelItem(
            self._ignore_list.indexOfTopLevelItem(item))

    # ── compare folders ──────────────────────────────────────────────────────
    def _color_for_index(self, i):
        return self._COMPARE_COLORS[i] if i < len(self._COMPARE_COLORS) else QColor("#AAAAAA")

    def _add_compare(self):
        d = QFileDialog.getExistingDirectory(self, "Add Folder to Compare", str(Path.home()))
        if not d or d in self._compare_folders:
            return
        self._compare_folders.append(d)
        color = self._color_for_index(len(self._compare_folders) - 1)
        item  = QTreeWidgetItem([d])
        item.setToolTip(0, d)
        item.setForeground(0, color)
        self._compare_list.addTopLevelItem(item)
        self._rebuild_legend()

    def _remove_compare(self):
        item = self._compare_list.currentItem()
        if not item:
            return
        path = item.text(0)
        if path in self._compare_folders:
            self._compare_folders.remove(path)
        self._compare_list.takeTopLevelItem(
            self._compare_list.indexOfTopLevelItem(item))
        # Re-colour remaining list items to stay in sync
        for i in range(self._compare_list.topLevelItemCount()):
            self._compare_list.topLevelItem(i).setForeground(0, self._color_for_index(i))
        self._rebuild_legend()

    def _rebuild_legend(self):
        while self._legend_lay.count():
            child = self._legend_lay.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for i, path in enumerate(self._compare_folders):
            color = self._color_for_index(i)
            name  = os.path.basename(path) or path
            lbl   = QLabel(f"<span style='color:{color.name()}'>■</span>  {name}")
            lbl.setStyleSheet("font-size:11px;")
            lbl.setToolTip(path)
            self._legend_lay.addWidget(lbl)

    # ── single-folder scan ───────────────────────────────────────────────────
    def _choose(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d:
            self._scan_path = d
            self._path_lbl.setText(d)

    def _scan_single(self):
        if not self._scan_path:
            QMessageBox.information(self, "Select Folder", "Choose a folder first.")
            return
        self._run_worker(root_paths=[self._scan_path], cross_only=False, root_color_map=None)

    # ── compare scan ─────────────────────────────────────────────────────────
    def _scan_compare(self):
        if len(self._compare_folders) < 2:
            QMessageBox.information(self, "Compare Folders",
                "Add at least two folders to compare.")
            return
        color_map = {
            os.path.normpath(path): self._color_for_index(i)
            for i, path in enumerate(self._compare_folders)
        }
        self._run_worker(
            root_paths=self._compare_folders,
            cross_only=True,
            root_color_map=color_map
        )

    # ── shared worker launcher ───────────────────────────────────────────────
    def _run_worker(self, root_paths, cross_only, root_color_map):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()

        self._results.clear()
        pb = self._results.progress_bar()
        pb.setRange(0, 0)
        pb.show()
        self._scan_btn.setEnabled(False)
        self._cmp_scan_btn.setEnabled(False)

        self._worker = DupeScanWorker(
            root_paths=root_paths,
            ignored=self._ignored_folders,
            cross_only=cross_only
        )
        self._worker.progress.connect(lambda d, t: (pb.setRange(0, t), pb.setValue(d)))
        self._worker.found.connect(lambda groups: self._results.populate(groups, root_color_map))
        self._worker.finished_.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self):
        self._results.progress_bar().hide()
        self._scan_btn.setEnabled(True)
        self._cmp_scan_btn.setEnabled(True)


# ── Tab: Large Files ───────────────────────────────────────────────────────────
class LargeFilesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_path = None
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
        self._table.setRowCount(0)
        for path, sz in files[:200]:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(path))
            size_item = QTableWidgetItem(_fmt_size(sz))
            size_item.setData(Qt.UserRole, sz)
            self._table.setItem(r, 1, size_item)
            self._table.setItem(r, 2, QTableWidgetItem(
                Path(path).suffix.upper().lstrip(".") or "—"))

    def _delete_selected(self):
        rows  = set(i.row() for i in self._table.selectedIndexes())
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
    name        = "File Manager"
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
        tabs.addTab(FileBrowserTab(), "📁 Browser")
        tabs.addTab(DupesTab(),       "🔄 Duplicate Finder")
        tabs.addTab(LargeFilesTab(),  "📦 Large Files")
        root.addWidget(tabs, 1)