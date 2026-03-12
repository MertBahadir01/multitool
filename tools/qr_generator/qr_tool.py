"""QR Code Generator tool."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QSpinBox, QFileDialog, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtGui import QFont
import qrcode
from PIL import Image
import io


class QRGeneratorTool(QWidget):
    name = "QR Code Generator"
    description = "Generate QR codes from text or URLs"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qr_image = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("📱 QR Code Generator")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #00BFA5;")
        layout.addWidget(title)

        group = QGroupBox("Input")
        gl = QVBoxLayout(group)

        gl.addWidget(QLabel("Text / URL to encode:"))
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("https://example.com or any text...")
        gl.addWidget(self.text_input)

        opts = QHBoxLayout()
        opts.addWidget(QLabel("Error correction:"))
        self.ec_combo = QComboBox()
        self.ec_combo.addItems(["L (7%)", "M (15%)", "Q (25%)", "H (30%)"])
        self.ec_combo.setCurrentIndex(1)
        opts.addWidget(self.ec_combo)

        opts.addSpacing(16)
        opts.addWidget(QLabel("Box size:"))
        self.box_spin = QSpinBox()
        self.box_spin.setRange(4, 20)
        self.box_spin.setValue(10)
        opts.addWidget(self.box_spin)
        opts.addStretch()
        gl.addLayout(opts)

        layout.addWidget(group)

        btn_row = QHBoxLayout()
        gen_btn = QPushButton("Generate QR Code")
        gen_btn.clicked.connect(self._generate)
        btn_row.addWidget(gen_btn)
        save_btn = QPushButton("Save PNG")
        save_btn.setObjectName("secondary")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.preview = QLabel("QR code preview will appear here")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: #2D2D2D; border: 1px solid #3E3E3E; border-radius: 8px; min-height: 280px;")
        layout.addWidget(self.preview)
        layout.addStretch()

    def _generate(self):
        text = self.text_input.text().strip()
        if not text:
            self.preview.setText("Please enter text or URL.")
            return
        ec_map = {0: qrcode.constants.ERROR_CORRECT_L, 1: qrcode.constants.ERROR_CORRECT_M,
                  2: qrcode.constants.ERROR_CORRECT_Q, 3: qrcode.constants.ERROR_CORRECT_H}
        ec = ec_map[self.ec_combo.currentIndex()]
        qr = qrcode.QRCode(error_correction=ec, box_size=self.box_spin.value(), border=4)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        self._qr_image = img
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        qimage = QImage.fromData(buf.read())
        pix = QPixmap.fromImage(qimage).scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(pix)

    def _save(self):
        if not self._qr_image:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save QR Code", "qrcode.png", "PNG Files (*.png)")
        if path:
            self._qr_image.save(path)
