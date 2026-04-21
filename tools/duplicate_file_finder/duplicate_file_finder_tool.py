"""Duplicate File Finder — finds identical files via SHA-256."""
import os, hashlib
from collections import defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QProgressBar, QGroupBox
)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont, QColor

class _Worker(QThread):
    progress = Signal(int)
    result   = Signal(dict)

    def __init__(self, folder):
        super().__init__()
        self.folder = folder

    def run(self):
        hashes = defaultdict(list)
        all_files = []
        for root, _, files in os.walk(self.folder):
            for f in files:
                all_files.append(os.path.join(root, f))
        for i, path in enumerate(all_files):
            try:
                h = hashlib.sha256()
                with open(path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        h.update(chunk)
                hashes[h.hexdigest()].append(path)
            except Exception:
                pass
            self.progress.emit(int((i + 1) / max(len(all_files), 1) * 100))
        dupes = {k: v for k, v in hashes.items() if len(v) > 1}
        self.result.emit(dupes)


class DuplicateFileFinderTool(QWidget):
    name        = "Duplicate File Finder"
    description = "Find identical files using SHA-256 hashing"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder = ""
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        sub = QLabel("Scan a folder to find duplicate files by content (not name).")
        sub.setStyleSheet("color: #888888;")
        lay.addWidget(sub)

        fb = QGroupBox("Folder to Scan")
        fl = QHBoxLayout(fb)
        self.folder_lbl = QLabel("No folder selected")
        self.folder_lbl.setStyleSheet("color: #888888;")
        fl.addWidget(self.folder_lbl, 1)
        b = QPushButton("Browse")
        b.clicked.connect(self._browse)
        fl.addWidget(b)
        lay.addWidget(fb)

        row = QHBoxLayout()
        self.scan_btn = QPushButton("Scan for Duplicates")
        self.scan_btn.clicked.connect(self._scan)
        row.addWidget(self.scan_btn)
        self.del_btn = QPushButton("Delete Selected")
        self.del_btn.setObjectName("danger")
        self.del_btn.clicked.connect(self._delete_selected)
        self.del_btn.setEnabled(False)
        row.addWidget(self.del_btn)
        row.addStretch()
        lay.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        lay.addWidget(self.bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888888;")
        lay.addWidget(self.status_lbl)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["File", "Size", "Path"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 400)
        self.tree.setSelectionMode(QTreeWidget.MultiSelection)
        lay.addWidget(self.tree)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Folder")
        if f:
            self._folder = f
            self.folder_lbl.setText(f)
            self.folder_lbl.setStyleSheet("color: #CCCCCC;")

    def _scan(self):
        if not self._folder:
            self.status_lbl.setText("Please select a folder first.")
            return
        self.tree.clear()
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self.scan_btn.setEnabled(False)
        self.del_btn.setEnabled(False)
        self.status_lbl.setText("Scanning...")
        self._worker = _Worker(self._folder)
        self._worker.progress.connect(self.bar.setValue)
        self._worker.result.connect(self._show_results)
        self._worker.start()

    def _show_results(self, dupes):
        self.scan_btn.setEnabled(True)
        self.bar.setVisible(False)
        if not dupes:
            self.status_lbl.setText("No duplicates found.")
            return
        total = sum(len(v) - 1 for v in dupes.values())
        self.status_lbl.setText(f"Found {len(dupes)} duplicate groups ({total} redundant files).")
        self.del_btn.setEnabled(True)
        colors = ["#2D3A2D", "#2D2D3A", "#3A2D2D", "#2D3A3A"]
        for ci, (h, paths) in enumerate(dupes.items()):
            size = os.path.getsize(paths[0]) if os.path.exists(paths[0]) else 0
            group = QTreeWidgetItem([f"Group {ci+1}  ({len(paths)} files)", _fmt_size(size * len(paths)), ""])
            group.setBackground(0, QColor(colors[ci % len(colors)]))
            group.setBackground(1, QColor(colors[ci % len(colors)]))
            group.setBackground(2, QColor(colors[ci % len(colors)]))
            self.tree.addTopLevelItem(group)
            for path in paths:
                sz = os.path.getsize(path) if os.path.exists(path) else 0
                child = QTreeWidgetItem([os.path.basename(path), _fmt_size(sz), path])
                child.setData(0, 256, path)
                group.addChild(child)
        self.tree.expandAll()

    def _delete_selected(self):
        for item in self.tree.selectedItems():
            path = item.data(0, 256)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    item.setText(0, item.text(0) + " [DELETED]")
                    item.setForeground(0, QColor("#F44336"))
                except Exception as e:
                    item.setText(0, f"{item.text(0)} [ERROR: {e}]")


def _fmt_size(b):
    for unit in ["B","KB","MB","GB"]:
        if b < 1024: return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"
