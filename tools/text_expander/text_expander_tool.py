"""Text Expander — define shortcuts that expand to full text."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit,
    QGroupBox, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence


class TextExpanderTool(QWidget):
    name        = "Text Expander"
    description = "Define shortcuts that expand into full text snippets"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snippets = {}
        self._build_ui()
        self._load_defaults()

    def _load_defaults(self):
        defaults = {
            "@@email":   "youremail@example.com",
            "@@phone":   "+1 (555) 000-0000",
            "@@addr":    "123 Main St, City, Country",
            "@@thanks":  "Thank you for your message. I will get back to you shortly.",
            "@@meet":    "Let's schedule a meeting at your earliest convenience.",
        }
        for k, v in defaults.items():
            self._snippets[k] = v
        self._refresh_table()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        sub = QLabel("Define shortcuts and expand them instantly in the test box below.")
        sub.setStyleSheet("color: #888888;")
        lay.addWidget(sub)

        # Add snippet
        add_box = QGroupBox("Add / Edit Snippet")
        al = QVBoxLayout(add_box)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Shortcut:"))
        self.shortcut_in = QLineEdit()
        self.shortcut_in.setPlaceholderText("e.g.  @@email")
        row1.addWidget(self.shortcut_in)
        al.addLayout(row1)
        al.addWidget(QLabel("Expands to:"))
        self.expand_in = QTextEdit()
        self.expand_in.setFixedHeight(70)
        self.expand_in.setPlaceholderText("Full text...")
        al.addWidget(self.expand_in)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Save Snippet")
        add_btn.clicked.connect(self._add)
        btn_row.addWidget(add_btn)
        del_btn = QPushButton("Delete Selected")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        al.addLayout(btn_row)
        lay.addWidget(add_box)

        # Table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Shortcut", "Expansion"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 160)
        self.table.itemClicked.connect(self._on_select)
        lay.addWidget(self.table)

        # Test area
        test_box = QGroupBox("Test Area — type a shortcut and press Tab or Space to expand")
        tl = QVBoxLayout(test_box)
        self.test_area = _ExpandingTextEdit(self._snippets)
        self.test_area.setPlaceholderText("Type a shortcut here to test...")
        tl.addWidget(self.test_area)
        lay.addWidget(test_box)

    def _add(self):
        sc = self.shortcut_in.text().strip()
        exp = self.expand_in.toPlainText().strip()
        if not sc or not exp:
            return
        self._snippets[sc] = exp
        self._refresh_table()
        self.shortcut_in.clear()
        self.expand_in.clear()

    def _delete(self):
        rows = set(i.row() for i in self.table.selectedItems())
        for r in sorted(rows, reverse=True):
            sc = self.table.item(r, 0).text()
            self._snippets.pop(sc, None)
            self.table.removeRow(r)

    def _refresh_table(self):
        self.table.setRowCount(0)
        for sc, exp in self._snippets.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(sc))
            self.table.setItem(r, 1, QTableWidgetItem(exp[:80] + ("..." if len(exp) > 80 else "")))

    def _on_select(self, item):
        sc = self.table.item(item.row(), 0).text()
        self.shortcut_in.setText(sc)
        self.expand_in.setPlainText(self._snippets.get(sc, ""))


class _ExpandingTextEdit(QTextEdit):
    def __init__(self, snippets_ref):
        super().__init__()
        self._snippets = snippets_ref

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key_Tab, Qt.Key_Space):
            cursor = self.textCursor()
            text   = self.toPlainText()
            pos    = cursor.position()
            # find last word
            start = max(text.rfind(" ", 0, pos), text.rfind("\n", 0, pos)) + 1
            word  = text[start:pos].rstrip()
            if word in self._snippets:
                expansion = self._snippets[word]
                cursor.setPosition(start)
                cursor.setPosition(pos, cursor.KeepAnchor)
                cursor.insertText(expansion)
