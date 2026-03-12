"""QR Code Scanner (file-based)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QFont
import cv2

class QRScannerTool(QWidget):
    name = "QR Code Scanner"
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        title = QLabel("📷 QR Code Scanner")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)
        btn = QPushButton("📂 Open Image with QR Code")
        btn.clicked.connect(self._scan)
        layout.addWidget(btn)
        self.img_lbl = QLabel("Image preview")
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setStyleSheet("background: #1A1A1A; border: 1px solid #3E3E3E; border-radius: 8px; min-height: 280px;")
        layout.addWidget(self.img_lbl)
        layout.addWidget(QLabel("Decoded Content:"))
        self.result = QTextEdit(); self.result.setReadOnly(True)
        self.result.setMaximumHeight(100)
        layout.addWidget(self.result)
        layout.addStretch()

    def _scan(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Image", filter="Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All (*)")
        if not path: return
        frame = cv2.imread(path)
        if frame is None: self.result.setPlainText("Could not load image."); return
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(frame)
        if data:
            if bbox is not None:
                import numpy as np
                pts = bbox[0].astype(int)
                cv2.polylines(frame, [pts], True, (0, 191, 165), 3)
            self.result.setPlainText(data)
        else:
            self.result.setPlainText("No QR code found in image.")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * c, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(520, 380, Qt.KeepAspectRatio)
        self.img_lbl.setPixmap(pix)
