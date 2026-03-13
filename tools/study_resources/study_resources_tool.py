"""Resource Library Tool — books, PDFs, links, videos. Tagged and searchable."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QTextEdit, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from core.auth_manager import auth_manager
from tools.study_lessons.study_service import ResourceService

RESOURCE_TYPES = ["📚 Book", "📄 PDF", "🎥 Video", "🔗 Link", "📝 Note", "Other"]
TYPE_ICONS = {"📚 Book": "📚", "📄 PDF": "📄", "🎥 Video": "🎥", "🔗 Link": "🔗", "📝 Note": "📝", "Other": "📦"}


class ResourceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Resource")
        self.setFixedWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Resource title…")
        form.addRow("Title:", self.title_edit)
        self.type_combo = QComboBox()
        self.type_combo.addItems(RESOURCE_TYPES)
        form.addRow("Type:", self.type_combo)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("URL, file path, or reference…")
        form.addRow("URL / Path:", self.url_edit)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("e.g. math, tyt, physics (comma-separated)")
        form.addRow("Tags:", self.tags_edit)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return {
            "title": self.title_edit.text().strip(),
            "type": self.type_combo.currentText(),
            "url": self.url_edit.text().strip(),
            "tags": self.tags_edit.text().strip(),
        }


class StudyResourcesTool(QWidget):
    name = "Resource Library"
    description = "Central library for books, PDFs, videos and links"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = ResourceService(user) if user else None
        self._resources = []
        self._build_ui()
        if self._svc:
            self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📚 Resource Library")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        add_btn = QPushButton("➕ Add Resource")
        add_btn.clicked.connect(self._add_resource)
        hl.addWidget(add_btn)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.setObjectName("secondary")
        del_btn.clicked.connect(self._delete_resource)
        hl.addWidget(del_btn)
        root.addWidget(hdr)

        # Filter bar
        filter_bar = QFrame()
        filter_bar.setStyleSheet("background:#252526; padding:4px;")
        fl = QHBoxLayout(filter_bar)
        fl.setContentsMargins(16, 8, 16, 8)
        fl.addWidget(QLabel("🔍"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search title or tags…")
        self.search_edit.textChanged.connect(self._refresh)
        fl.addWidget(self.search_edit, 1)
        fl.addWidget(QLabel("Filter tag:"))
        self.tag_filter = QLineEdit()
        self.tag_filter.setPlaceholderText("e.g. math")
        self.tag_filter.setFixedWidth(120)
        self.tag_filter.textChanged.connect(self._refresh)
        fl.addWidget(self.tag_filter)
        fl.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All"] + RESOURCE_TYPES)
        self.type_filter.currentTextChanged.connect(self._refresh)
        fl.addWidget(self.type_filter)
        root.addWidget(filter_bar)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Title", "Type", "URL / Path", "Tags"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_url)
        root.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color:#555; font-size:12px; padding:8px 16px;")
        footer.addWidget(self.count_lbl)
        footer.addStretch()
        open_btn = QPushButton("🔗 Open Selected")
        open_btn.clicked.connect(self._open_url)
        footer.addWidget(open_btn)
        root.addLayout(footer)

    def _refresh(self):
        if not self._svc:
            return
        search = self.search_edit.text().strip()
        tag = self.tag_filter.text().strip()
        type_f = self.type_filter.currentText()
        self._resources = self._svc.get_resources(search, tag)
        if type_f != "All":
            self._resources = [r for r in self._resources if r.get("resource_type") == type_f]
        self.table.setRowCount(0)
        for r in self._resources:
            row = self.table.rowCount()
            self.table.insertRow(row)
            icon = TYPE_ICONS.get(r.get("resource_type", ""), "📦")
            self.table.setItem(row, 0, QTableWidgetItem(f"{icon} {r['title']}"))
            self.table.setItem(row, 1, QTableWidgetItem(r.get("resource_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(r.get("url_or_path", "")))
            self.table.setItem(row, 3, QTableWidgetItem(r.get("tags", "") or ""))
        self.count_lbl.setText(f"{len(self._resources)} resource(s)")

    def _add_resource(self):
        dlg = ResourceDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        d = dlg.get_data()
        if not d["title"]:
            QMessageBox.warning(self, "Error", "Title is required.")
            return
        self._svc.add_resource(d["title"], d["type"], d["url"], d["tags"])
        self._refresh()

    def _delete_resource(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._resources):
            return
        r = self._resources[row]
        if QMessageBox.question(self, "Delete", f"Delete '{r['title']}'?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._svc.delete_resource(r["id"])
            self._refresh()

    def _open_url(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._resources):
            return
        r = self._resources[row]
        url = r.get("url_or_path", "")
        if not url:
            return
        import subprocess, sys
        try:
            if sys.platform == "win32":
                import os
                os.startfile(url)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", url])
            else:
                subprocess.Popen(["xdg-open", url])
        except Exception as e:
            QMessageBox.information(self, "URL", url)
