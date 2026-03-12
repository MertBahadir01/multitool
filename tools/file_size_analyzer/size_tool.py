import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QProgressBar)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

def fmt_size(b):
    for u in ['B','KB','MB','GB']:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

class FileSizeAnalyzerTool(QWidget):
    name = "File Size Analyzer"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("📊 File Size Analyzer")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        row = QHBoxLayout()
        btn = QPushButton("Select Folder"); btn.clicked.connect(self._select)
        row.addWidget(btn)
        self.path_lbl = QLabel("No folder selected")
        self.path_lbl.setStyleSheet("color: #888888;")
        row.addWidget(self.path_lbl)
        row.addStretch()
        layout.addLayout(row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Size", "Items"])
        self.tree.setColumnWidth(0, 380)
        self.tree.setColumnWidth(1, 100)
        self.tree.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 6px;")
        layout.addWidget(self.tree)
        layout.addStretch()

    def _select(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder: return
        self.path_lbl.setText(folder)
        self.tree.clear()
        self._scan(folder, self.tree.invisibleRootItem())

    def _scan(self, path, parent_item):
        total = 0
        count = 0
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name)
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    item = QTreeWidgetItem([entry.name, "", ""])
                    item.setForeground(0, Qt.yellow)
                    parent_item.addChild(item)
                    sub_size, sub_count = self._scan(entry.path, item)
                    item.setText(1, fmt_size(sub_size))
                    item.setText(2, str(sub_count))
                    total += sub_size; count += sub_count
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat().st_size
                    item = QTreeWidgetItem([entry.name, fmt_size(size), "1"])
                    parent_item.addChild(item)
                    total += size; count += 1
        except PermissionError:
            pass
        return total, count
