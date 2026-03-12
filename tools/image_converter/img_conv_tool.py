import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QListWidget, QMessageBox, QGroupBox)
from PySide6.QtGui import QFont
from PIL import Image

FORMATS = ["PNG", "JPEG", "BMP", "WEBP", "GIF", "TIFF", "ICO"]

class ImageConverterTool(QWidget):
    name = "Image Converter"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("🖼️ Image Converter")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        row = QHBoxLayout()
        add = QPushButton("Add Images"); add.clicked.connect(self._add)
        row.addWidget(add)
        clr = QPushButton("Clear"); clr.setObjectName("secondary"); clr.clicked.connect(self._clear)
        row.addWidget(clr)
        row.addStretch()
        layout.addLayout(row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(200)
        self.file_list.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 6px;")
        layout.addWidget(self.file_list)

        grp = QGroupBox("Output Settings")
        gl = QHBoxLayout(grp)
        gl.addWidget(QLabel("Output Format:"))
        self.fmt = QComboBox(); self.fmt.addItems(FORMATS)
        gl.addWidget(self.fmt)
        gl.addStretch()
        layout.addWidget(grp)

        conv = QPushButton("Convert All")
        conv.clicked.connect(self._convert)
        layout.addWidget(conv)
        self.status = QLabel("")
        layout.addWidget(self.status)
        layout.addStretch()

    def _add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", filter="Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.ico);;All (*)")
        for f in files:
            if f not in self._files:
                self._files.append(f); self.file_list.addItem(os.path.basename(f))

    def _clear(self):
        self._files.clear(); self.file_list.clear()

    def _convert(self):
        if not self._files: return
        out_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if not out_dir: return
        fmt = self.fmt.currentText()
        ext = fmt.lower() if fmt != "JPEG" else "jpg"
        done = 0
        for f in self._files:
            try:
                img = Image.open(f)
                if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                base = os.path.splitext(os.path.basename(f))[0]
                out = os.path.join(out_dir, f"{base}.{ext}")
                img.save(out, format=fmt)
                done += 1
            except Exception as e:
                pass
        self.status.setText(f"✅ Converted {done}/{len(self._files)} images to {fmt}")
        self.status.setStyleSheet("color: #4CAF50;")
