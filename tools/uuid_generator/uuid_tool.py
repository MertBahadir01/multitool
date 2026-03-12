import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QTextEdit, QGroupBox)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

class UUIDGeneratorTool(QWidget):
    name = "UUID Generator"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🔗 UUID Generator")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        grp = QGroupBox("Settings")
        gl = QHBoxLayout(grp)
        gl.addWidget(QLabel("Version:"))
        self.ver = QComboBox(); self.ver.addItems(["UUID v1", "UUID v4"])
        gl.addWidget(self.ver)
        gl.addWidget(QLabel("Count:"))
        self.count = QSpinBox(); self.count.setRange(1, 100); self.count.setValue(1)
        gl.addWidget(self.count)
        gl.addStretch()
        layout.addWidget(grp)

        row = QHBoxLayout()
        gen = QPushButton("Generate"); gen.clicked.connect(self._generate)
        row.addWidget(gen)
        copy = QPushButton("Copy All"); copy.setObjectName("secondary"); copy.clicked.connect(self._copy)
        row.addWidget(copy)
        row.addStretch()
        layout.addLayout(row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Courier New", 13))
        layout.addWidget(self.output)
        layout.addStretch()

    def _generate(self):
        ver = self.ver.currentIndex()
        n = self.count.value()
        results = [str(uuid.uuid1() if ver == 0 else uuid.uuid4()) for _ in range(n)]
        self.output.setPlainText("\n".join(results))

    def _copy(self):
        text = self.output.toPlainText()
        if text: QApplication.clipboard().setText(text)
