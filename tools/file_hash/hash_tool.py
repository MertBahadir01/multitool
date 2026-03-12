import hashlib, os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QGroupBox, QTextEdit)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

class FileHashTool(QWidget):
    name = "File Hash Generator"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("#️⃣ File Hash Generator")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.path_edit = QLineEdit(); self.path_edit.setPlaceholderText("Select file...")
        row.addWidget(self.path_edit)
        browse = QPushButton("Browse"); browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)

        hash_btn = QPushButton("Compute Hashes")
        hash_btn.clicked.connect(self._compute)
        layout.addWidget(hash_btn)

        self.result = QTextEdit(); self.result.setReadOnly(True)
        self.result.setFont(QFont("Courier New", 12))
        layout.addWidget(self.result)

        copy = QPushButton("Copy Results"); copy.setObjectName("secondary")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.result.toPlainText()))
        layout.addWidget(copy)
        layout.addStretch()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path: self.path_edit.setText(path)

    def _compute(self):
        path = self.path_edit.text().strip()
        if not path or not os.path.isfile(path):
            self.result.setPlainText("Invalid file path."); return
        size = os.path.getsize(path)
        algos = {"MD5": hashlib.md5(), "SHA-1": hashlib.sha1(),
                 "SHA-256": hashlib.sha256(), "SHA-512": hashlib.sha512()}
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                for h in algos.values(): h.update(chunk)
        lines = [f"File: {os.path.basename(path)}", f"Size: {size:,} bytes", ""]
        for name, h in algos.items():
            lines.append(f"{name}:\n{h.hexdigest()}\n")
        self.result.setPlainText("\n".join(lines))
