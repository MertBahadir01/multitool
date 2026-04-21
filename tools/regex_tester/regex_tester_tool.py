"""Regex Tester — live regex testing with safe highlighting."""

import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QGroupBox, QCheckBox, QListWidget
)

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont, QTextCharFormat, QColor, QTextCursor
)


class RegexTesterTool(QWidget):
    name = "Regex Tester"
    description = "Test regex patterns with live match highlighting"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Pattern input
        pattern_box = QGroupBox("Regex Pattern")
        p_layout = QVBoxLayout(pattern_box)

        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText(r"Example: \b\w+@\w+\.\w+\b")
        self.pattern_input.setFont(QFont("Courier New", 11))
        self.pattern_input.textChanged.connect(self.run_regex)

        p_layout.addWidget(self.pattern_input)

        # Flags
        flags_layout = QHBoxLayout()

        self.flag_i = QCheckBox("IGNORECASE")
        self.flag_m = QCheckBox("MULTILINE")
        self.flag_s = QCheckBox("DOTALL")

        for f in (self.flag_i, self.flag_m, self.flag_s):
            f.toggled.connect(self.run_regex)
            flags_layout.addWidget(f)

        flags_layout.addStretch()
        p_layout.addLayout(flags_layout)

        layout.addWidget(pattern_box)

        # Text input
        text_box = QGroupBox("Test Text")
        t_layout = QVBoxLayout(text_box)

        self.text_input = QTextEdit()
        self.text_input.setFont(QFont("Courier New", 11))
        self.text_input.setPlainText(
            "Hello World\nfoo@bar.com\n123 test\nregex engine\nanother line"
        )
        self.text_input.textChanged.connect(self.run_regex)

        t_layout.addWidget(self.text_input)
        layout.addWidget(text_box)

        # Status
        self.status = QLabel("Enter a regex pattern")
        self.status.setStyleSheet("color: gray;")
        layout.addWidget(self.status)

        # Matches
        self.matches_list = QListWidget()
        self.matches_list.setFont(QFont("Courier New", 10))
        layout.addWidget(self.matches_list)

    # ---------------- Regex engine ----------------
    def get_flags(self):
        flags = 0
        if self.flag_i.isChecked():
            flags |= re.IGNORECASE
        if self.flag_m.isChecked():
            flags |= re.MULTILINE
        if self.flag_s.isChecked():
            flags |= re.DOTALL
        return flags

    def run_regex(self):
        pattern = self.pattern_input.text()
        text = self.text_input.toPlainText()

        self.matches_list.clear()
        self.clear_highlight()

        if not pattern:
            self.status.setText("Enter a regex pattern")
            self.status.setStyleSheet("color: gray;")
            return

        try:
            regex = re.compile(pattern, self.get_flags())
        except re.error as e:
            self.status.setText(f"Invalid regex: {e}")
            self.status.setStyleSheet("color: red;")
            return

        matches = list(regex.finditer(text))

        self.status.setText(f"{len(matches)} matches found")
        self.status.setStyleSheet("color: green;" if matches else "color: gray;")

        self.highlight(matches)

        for i, m in enumerate(matches):
            self.matches_list.addItem(
                f"{i+1}. {m.group()} ({m.start()}-{m.end()})"
            )

    # ---------------- Highlighting (SAFE Qt method) ----------------
    def highlight(self, matches):
        selections = []

        for m in matches:
            cursor = self.text_input.textCursor()
            cursor.setPosition(m.start())
            cursor.setPosition(m.end(), QTextCursor.KeepAnchor)

            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#1f6f4a"))
            fmt.setForeground(QColor("#ffffff"))

            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)

        self.text_input.setExtraSelections(selections)

    def clear_highlight(self):
        self.text_input.setExtraSelections([])