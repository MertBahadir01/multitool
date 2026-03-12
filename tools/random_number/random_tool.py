import secrets, random
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QGroupBox, QTextEdit, QComboBox)
from PySide6.QtGui import QFont

class RandomNumberTool(QWidget):
    name = "Random Number Generator"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🎲 Random Number Generator")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        grp = QGroupBox("Settings")
        gl = QVBoxLayout(grp)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Min:"))
        self.min_spin = QSpinBox(); self.min_spin.setRange(-999999, 999999); self.min_spin.setValue(1)
        r1.addWidget(self.min_spin)
        r1.addWidget(QLabel("Max:"))
        self.max_spin = QSpinBox(); self.max_spin.setRange(-999999, 999999); self.max_spin.setValue(100)
        r1.addWidget(self.max_spin)
        r1.addStretch()
        gl.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Count:"))
        self.count_spin = QSpinBox(); self.count_spin.setRange(1, 1000); self.count_spin.setValue(1)
        r2.addWidget(self.count_spin)
        r2.addWidget(QLabel("Mode:"))
        self.mode = QComboBox(); self.mode.addItems(["Integer", "Float", "Crypto-Secure Int"])
        r2.addWidget(self.mode)
        r2.addStretch()
        gl.addLayout(r2)
        layout.addWidget(grp)

        btn = QPushButton("Generate")
        btn.clicked.connect(self._generate)
        layout.addWidget(btn)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Courier New", 13))
        layout.addWidget(self.output)
        layout.addStretch()

    def _generate(self):
        lo, hi, n = self.min_spin.value(), self.max_spin.value(), self.count_spin.value()
        if lo > hi: lo, hi = hi, lo
        mode = self.mode.currentText()
        results = []
        for _ in range(n):
            if mode == "Integer":
                results.append(str(random.randint(lo, hi)))
            elif mode == "Float":
                results.append(f"{random.uniform(lo, hi):.6f}")
            else:
                results.append(str(secrets.randbelow(hi - lo + 1) + lo))
        self.output.setPlainText("\n".join(results))
