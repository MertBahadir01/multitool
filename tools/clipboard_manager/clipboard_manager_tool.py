"""Clipboard Manager — tracks clipboard history."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QApplication, QGroupBox, QLineEdit
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class ClipboardManagerTool(QWidget):
    name        = "Clipboard Manager"
    description = "Save and restore clipboard history"

    MAX_HISTORY = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history = []
        self._last = ""
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(500)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        sub = QLabel("Monitors clipboard automatically. Click any entry to copy it back.")
        sub.setStyleSheet("color: #888888;")
        lay.addWidget(sub)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search history...")
        self.search.textChanged.connect(self._filter)
        search_row.addWidget(self.search)
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._clear)
        search_row.addWidget(clear_btn)
        lay.addLayout(search_row)

        self.count_lbl = QLabel("0 items")
        self.count_lbl.setStyleSheet("color: #888888;")
        lay.addWidget(self.count_lbl)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._restore)
        lay.addWidget(self.list)

        hint = QLabel("Double-click an item to restore it to the clipboard.")
        hint.setStyleSheet("color: #555555; font-size: 11px;")
        lay.addWidget(hint)

    def _poll(self):
        cb = QApplication.clipboard()
        text = cb.text().strip()
        if text and text != self._last:
            self._last = text
            if text not in self._history:
                self._history.insert(0, text)
                if len(self._history) > self.MAX_HISTORY:
                    self._history.pop()
                self._refresh()

    def _refresh(self):
        query = self.search.text().lower()
        self.list.clear()
        for entry in self._history:
            if query and query not in entry.lower():
                continue
            preview = entry[:120].replace("\n", " ")
            item = QListWidgetItem(preview)
            item.setData(Qt.UserRole, entry)
            item.setToolTip(entry[:500])
            self.list.addItem(item)
        self.count_lbl.setText(f"{len(self._history)} items")

    def _filter(self):
        self._refresh()

    def _restore(self, item):
        text = item.data(Qt.UserRole)
        QApplication.clipboard().setText(text)
        self._last = text.strip()

    def _clear(self):
        self._history.clear()
        self.list.clear()
        self.count_lbl.setText("0 items")

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self._timer.start(500)
        super().showEvent(event)
