import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QSpinBox, QCheckBox, QListWidget, QGroupBox, QComboBox)
from PySide6.QtGui import QFont
from PIL import Image

class ImageResizerTool(QWidget):
    name = "Image Resizer"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("📐 Image Resizer")
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
        self.file_list.setMaximumHeight(160)
        self.file_list.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 6px;")
        layout.addWidget(self.file_list)

        grp = QGroupBox("Resize Settings")
        gl = QVBoxLayout(grp)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Width:"))
        self.width = QSpinBox(); self.width.setRange(1, 9999); self.width.setValue(800)
        r1.addWidget(self.width)
        r1.addWidget(QLabel("Height:"))
        self.height = QSpinBox(); self.height.setRange(1, 9999); self.height.setValue(600)
        r1.addWidget(self.height)
        r1.addStretch()
        gl.addLayout(r1)
        self.aspect = QCheckBox("Maintain aspect ratio"); self.aspect.setChecked(True)
        gl.addWidget(self.aspect)
        layout.addWidget(grp)

        btn = QPushButton("Resize All")
        btn.clicked.connect(self._resize)
        layout.addWidget(btn)
        self.status = QLabel("")
        layout.addWidget(self.status)
        layout.addStretch()

    def _add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", filter="Images (*.png *.jpg *.jpeg *.bmp *.webp);;All (*)")
        for f in files:
            if f not in self._files:
                self._files.append(f); self.file_list.addItem(os.path.basename(f))

    def _clear(self):
        self._files.clear(); self.file_list.clear()

    def _resize(self):
        if not self._files: return
        out_dir = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if not out_dir: return
        w, h = self.width.value(), self.height.value()
        done = 0
        for f in self._files:
            try:
                img = Image.open(f)
                if self.aspect.isChecked():
                    img.thumbnail((w, h), Image.LANCZOS)
                else:
                    img = img.resize((w, h), Image.LANCZOS)
                out = os.path.join(out_dir, os.path.basename(f))
                img.save(out)
                done += 1
            except: pass
        self.status.setText(f"✅ Resized {done}/{len(self._files)} images.")
        self.status.setStyleSheet("color: #4CAF50;")
