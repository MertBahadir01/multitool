"""Secure password generator."""

import secrets
import string
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QSpinBox, QGroupBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def generate_password(length=16, use_upper=True, use_lower=True, use_digits=True, use_symbols=True):
    chars = ""
    required = []
    if use_upper:
        chars += string.ascii_uppercase
        required.append(secrets.choice(string.ascii_uppercase))
    if use_lower:
        chars += string.ascii_lowercase
        required.append(secrets.choice(string.ascii_lowercase))
    if use_digits:
        chars += string.digits
        required.append(secrets.choice(string.digits))
    if use_symbols:
        syms = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        chars += syms
        required.append(secrets.choice(syms))
    if not chars:
        chars = string.ascii_letters + string.digits
    password = required + [secrets.choice(chars) for _ in range(length - len(required))]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


class PasswordGeneratorTool(QWidget):
    name = "Password Generator"
    description = "Generate cryptographically secure passwords"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("🔑 Password Generator")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        opts = QGroupBox("Options")
        ol = QVBoxLayout(opts)

        len_row = QHBoxLayout()
        len_row.addWidget(QLabel("Password Length:"))
        self.len_spin = QSpinBox()
        self.len_spin.setRange(6, 128)
        self.len_spin.setValue(16)
        len_row.addWidget(self.len_spin)
        len_row.addStretch()
        ol.addLayout(len_row)

        self.chk_upper = QCheckBox("Uppercase (A-Z)")
        self.chk_upper.setChecked(True)
        self.chk_lower = QCheckBox("Lowercase (a-z)")
        self.chk_lower.setChecked(True)
        self.chk_digits = QCheckBox("Digits (0-9)")
        self.chk_digits.setChecked(True)
        self.chk_symbols = QCheckBox("Symbols (!@#$...)")
        self.chk_symbols.setChecked(True)
        for chk in [self.chk_upper, self.chk_lower, self.chk_digits, self.chk_symbols]:
            ol.addWidget(chk)

        layout.addWidget(opts)

        btn_row = QHBoxLayout()
        gen_btn = QPushButton("Generate Password")
        gen_btn.clicked.connect(self._generate)
        btn_row.addWidget(gen_btn)

        gen_multi = QPushButton("Generate 5 Passwords")
        gen_multi.setObjectName("secondary")
        gen_multi.clicked.connect(self._generate_multi)
        btn_row.addWidget(gen_multi)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.result = QLineEdit()
        self.result.setReadOnly(True)
        self.result.setFont(QFont("Courier New", 14))
        self.result.setStyleSheet("padding: 10px; font-size: 14px;")
        layout.addWidget(self.result)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy)
        layout.addWidget(copy_btn)

        layout.addWidget(QLabel("Batch Results:"))
        self.batch_list = QListWidget()
        self.batch_list.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 6px;")
        layout.addWidget(self.batch_list)
        layout.addStretch()

    def _get_opts(self):
        return dict(
            length=self.len_spin.value(),
            use_upper=self.chk_upper.isChecked(),
            use_lower=self.chk_lower.isChecked(),
            use_digits=self.chk_digits.isChecked(),
            use_symbols=self.chk_symbols.isChecked(),
        )

    def _generate(self):
        pw = generate_password(**self._get_opts())
        self.result.setText(pw)

    def _generate_multi(self):
        self.batch_list.clear()
        for _ in range(5):
            pw = generate_password(**self._get_opts())
            item = QListWidgetItem(pw)
            item.setFont(QFont("Courier New", 12))
            self.batch_list.addItem(item)

    def _copy(self):
        text = self.result.text()
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
