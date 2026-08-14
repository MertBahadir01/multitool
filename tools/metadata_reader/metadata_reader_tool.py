"""Metadata Reader — inspect file metadata (EXIF, document properties,
audio/video stream info, PDF info, plus basic file-system details)."""

import os
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QApplication, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent

from .metadata_service import read_metadata


class MetadataReaderTool(QWidget):
    name = "Metadata Reader"
    description = "View EXIF, document, audio/video & file metadata"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = None
        self._last_sections = {}
        self.setAcceptDrops(True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("🔎 Metadata Reader")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        hint = QLabel("Select a file or drag & drop it here — images, documents (docx/xlsx/pptx), PDFs, audio and video are all supported.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888888;")
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select or drop a file...")
        self.path_edit.setReadOnly(True)
        row.addWidget(self.path_edit)

        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)

        read_btn = QPushButton("Read Metadata")
        read_btn.clicked.connect(self._read_current)
        row.addWidget(read_btn)
        layout.addLayout(row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Property", "Value"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree, 1)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy as Text")
        copy_btn.setObjectName("secondary")
        copy_btn.clicked.connect(self._copy_text)
        btn_row.addWidget(copy_btn)

        export_btn = QPushButton("Export as JSON")
        export_btn.setObjectName("secondary")
        export_btn.clicked.connect(self._export_json)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self._load(path)

    def _read_current(self):
        path = self.path_edit.text().strip()
        if path:
            self._load(path)
        else:
            QMessageBox.information(self, "Metadata Reader", "Select a file first.")

    def _load(self, path):
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Metadata Reader", "That path is not a valid file.")
            return
        self._current_path = path
        self.path_edit.setText(path)
        self._populate(path)

    # ------------------------------------------------------------------
    # Metadata display
    # ------------------------------------------------------------------

    def _display_value(self, value):
        """Tree/text view formatting only — JSON export uses the raw value
        (e.g. a real list for Keywords) unchanged, so arrays aren't flattened
        away, they're just joined here for human-readable display."""
        if isinstance(value, list):
            return "; ".join(str(v) for v in value)
        return str(value)

    def _populate(self, path):
        self.tree.clear()
        try:
            sections = read_metadata(path)
        except Exception as e:
            QMessageBox.critical(self, "Metadata Reader", f"Could not read metadata:\n{e}")
            return

        self._last_sections = sections
        for section_name, fields in sections.items():
            section_item = QTreeWidgetItem([section_name, ""])
            font = section_item.font(0)
            font.setBold(True)
            section_item.setFont(0, font)
            self.tree.addTopLevelItem(section_item)
            for key, value in fields.items():
                child = QTreeWidgetItem([str(key), self._display_value(value)])
                section_item.addChild(child)
            section_item.setExpanded(True)

        self.tree.resizeColumnToContents(0)

    def _as_text(self):
        lines = []
        for section_name, fields in self._last_sections.items():
            lines.append(f"[{section_name}]")
            for key, value in fields.items():
                lines.append(f"  {key}: {self._display_value(value)}")
            lines.append("")
        return "\n".join(lines)

    def _copy_text(self):
        if not self._last_sections:
            return
        QApplication.clipboard().setText(self._as_text())

    def _export_json(self):
        if not self._last_sections:
            QMessageBox.information(self, "Metadata Reader", "Read a file's metadata first.")
            return
        default_name = os.path.splitext(os.path.basename(self._current_path or "metadata"))[0] + "_metadata.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export as JSON", default_name, "JSON Files (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._last_sections, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Metadata Reader", f"Could not export:\n{e}")

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self._load(path)
