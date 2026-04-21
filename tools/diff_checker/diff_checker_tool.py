"""Diff Checker — compare two texts side by side with color highlighting."""
import difflib
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QGroupBox, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCharFormat, QColor


ADD_BG  = QColor("#1a3a1a")
DEL_BG  = QColor("#3a1a1a")
EQL_FG  = QColor("#888888")


class DiffCheckerTool(QWidget):
    name        = "Diff Checker"
    description = "Compare two texts and highlight added/removed lines"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        sub = QLabel("Paste two texts to compare. Green = added, Red = removed, Grey = unchanged.")
        sub.setStyleSheet("color: #888888;")
        lay.addWidget(sub)

        compare_btn = QPushButton("Compare")
        compare_btn.clicked.connect(self._compare)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self._clear)
        btn_row = QHBoxLayout()
        btn_row.addWidget(compare_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        splitter = QSplitter(Qt.Horizontal)

        left_box = QGroupBox("Text A (Original)")
        ll = QVBoxLayout(left_box)
        self.left_in = QTextEdit()
        self.left_in.setFont(QFont("Courier New", 11))
        self.left_in.setPlaceholderText("Paste original text here...")
        ll.addWidget(self.left_in)
        splitter.addWidget(left_box)

        right_box = QGroupBox("Text B (Modified)")
        rl = QVBoxLayout(right_box)
        self.right_in = QTextEdit()
        self.right_in.setFont(QFont("Courier New", 11))
        self.right_in.setPlaceholderText("Paste modified text here...")
        rl.addWidget(self.right_in)
        splitter.addWidget(right_box)

        lay.addWidget(splitter, 2)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888888;")
        lay.addWidget(self.status_lbl)

        result_box = QGroupBox("Diff Result")
        resl = QVBoxLayout(result_box)
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setFont(QFont("Courier New", 11))
        resl.addWidget(self.result)
        lay.addWidget(result_box, 3)

    def _compare(self):
        a = self.left_in.toPlainText().splitlines(keepends=True)
        b = self.right_in.toPlainText().splitlines(keepends=True)
        diff = list(difflib.ndiff(a, b))

        self.result.clear()
        cursor = self.result.textCursor()

        added = removed = unchanged = 0
        for line in diff:
            fmt = QTextCharFormat()
            if line.startswith("+ "):
                fmt.setBackground(ADD_BG)
                fmt.setForeground(QColor("#8BC34A"))
                added += 1
            elif line.startswith("- "):
                fmt.setBackground(DEL_BG)
                fmt.setForeground(QColor("#F44336"))
                removed += 1
            elif line.startswith("? "):
                continue
            else:
                fmt.setForeground(EQL_FG)
                unchanged += 1
            cursor.insertText(line, fmt)

        self.status_lbl.setText(
            f"+{added} added   -{removed} removed   {unchanged} unchanged"
        )

    def _clear(self):
        self.left_in.clear()
        self.right_in.clear()
        self.result.clear()
        self.status_lbl.setText("")
