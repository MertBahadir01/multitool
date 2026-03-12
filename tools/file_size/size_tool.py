"""
File Size Analyzer Tool
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFileDialog, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from core.plugin_manager import ToolInterface


class ScanWorker(QThread):
    progress = Signal(str)
    result = Signal(list)
    finished = Signal()

    def __init__(self, path, depth=3):
        super().__init__()
        self.path = path
        self.depth = depth

    def run(self):
        results = []
        self._scan(self.path, 0, results)
        results.sort(key=lambda x: x[2], reverse=True)
        self.result.emit(results[:1000])
        self.finished.emit()

    def _scan(self, path, level, results):
        if level > self.depth:
            return
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            size = entry.stat().st_size
                            results.append((entry.path, "File", size, level))
                        elif entry.is_dir(follow_symlinks=False):
                            dir_size = self._get_dir_size(entry.path)
                            results.append((entry.path, "Folder", dir_size, level))
                            self.progress.emit(f"Scanning: {entry.name}")
                            self._scan(entry.path, level + 1, results)
                    except PermissionError:
                        pass
        except PermissionError:
            pass

    def _get_dir_size(self, path):
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, f))
                    except Exception:
                        pass
        except Exception:
            pass
        return total


def format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class FileSizeTool(ToolInterface):
    name = "File Size Analyzer"
    description = "Analyze and visualize file and folder sizes"
    icon = "📊"
    category = "File Tools"

    def get_widget(self):
        return FileSizeWidget()


class FileSizeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("📊 File Size Analyzer")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Path selection
        path_group = QGroupBox("Location")
        path_layout = QHBoxLayout(path_group)
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select a folder to analyze...")
        self.path_input.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse)
        scan_btn = QPushButton("Scan")
        scan_btn.clicked.connect(self._scan)
        path_layout.addWidget(self.path_input, 1)
        path_layout.addWidget(browse_btn)
        path_layout.addWidget(scan_btn)
        layout.addWidget(path_group)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #777777;")
        layout.addWidget(self.progress_label)

        # Summary
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #00BFA5; font-size: 13px;")
        layout.addWidget(self.summary_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Size", "Path"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 70)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 100)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_input.setText(folder)

    def _scan(self):
        path = self.path_input.text()
        if not path or not os.path.isdir(path):
            return
        self.table.setRowCount(0)
        self.progress_label.setText("🔍 Scanning...")
        self._worker = ScanWorker(path)
        self._worker.progress.connect(lambda msg: self.progress_label.setText(f"🔍 {msg}"))
        self._worker.result.connect(self._show_results)
        self._worker.finished.connect(lambda: self.progress_label.setText("✓ Scan complete"))
        self._worker.start()

    def _show_results(self, results):
        self.table.setRowCount(0)
        total_size = 0
        for path, type_, size, level in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name = os.path.basename(path)
            indent = "  " * level
            self.table.setItem(row, 0, QTableWidgetItem(f"{indent}{name}"))
            type_item = QTableWidgetItem(type_)
            type_item.setForeground(QColor("#00BFA5" if type_ == "Folder" else "#AAAAAA"))
            self.table.setItem(row, 1, type_item)
            size_item = QTableWidgetItem(format_size(size))
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, size_item)
            self.table.setItem(row, 3, QTableWidgetItem(path))
            if type_ == "File":
                total_size += size
        count = len([r for r in results if r[1] == "File"])
        self.summary_label.setText(
            f"Found {count:,} files in {len(results) - count:,} folders | Total: {format_size(total_size)}"
        )
