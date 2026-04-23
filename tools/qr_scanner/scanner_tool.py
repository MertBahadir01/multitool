"""
QR Code Scanner Tool
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTextEdit, QGroupBox, QListWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from core.plugin_manager import ToolInterface

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

try:
    from pyzbar import pyzbar
    HAS_PYZBAR = True
except ImportError:
    pyzbar = None
    HAS_PYZBAR = False


class QRScannerTool(ToolInterface):
    name = "QR Scanner"
    description = "Scan and decode QR codes from images or webcam"
    icon = "🔍"
    category = "Utility Tools"

    def get_widget(self):
        return QRScannerWidget()


class QRScannerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("🔍 QR Code Scanner")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        if not HAS_CV2:
            warn = QLabel("⚠️ OpenCV required: pip install opencv-python")
            warn.setStyleSheet("color: #FF9800;")
            layout.addWidget(warn)
        if not HAS_PYZBAR:
            note = QLabel(
                "⚠️ pyzbar required for QR scanning: pip install pyzbar\n"
                "On Windows, also install: https://github.com/NaturalHistoryMuseum/pyzbar"
            )
            note.setStyleSheet("color: #FF9800;")
            layout.addWidget(note)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Image")
        open_btn.clicked.connect(self._open_image)
        cam_btn = QPushButton("Scan from Webcam")
        cam_btn.setObjectName("btn_secondary")
        cam_btn.clicked.connect(self._scan_webcam)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(cam_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        content = QHBoxLayout()

        self.image_label = QLabel("Open an image containing a QR code")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(300, 300)
        self.image_label.setStyleSheet("background: #252526; border-radius: 8px; color: #555555;")
        content.addWidget(self.image_label, 1)

        right = QVBoxLayout()
        result_group = QGroupBox("Decoded Results")
        result_layout = QVBoxLayout(result_group)
        self.result_list = QListWidget()
        result_layout.addWidget(self.result_list)
        right.addWidget(result_group, 1)

        self.decoded_text = QTextEdit()
        self.decoded_text.setPlaceholderText("Decoded content will appear here...")
        self.decoded_text.setMaximumHeight(150)
        right.addWidget(self.decoded_text)
        content.addLayout(right, 1)
        layout.addLayout(content, 1)

    def _show_cv_frame(self, frame_bgr):
        """Convert a BGR numpy frame to a QPixmap and show it in image_label."""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        pixmap = pixmap.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)

    def _scan_image(self, img_bgr):
        """Decode QR/barcodes from a BGR numpy image. Returns list of decoded strings."""
        self.result_list.clear()
        self.decoded_text.clear()

        if not HAS_CV2:
            self.result_list.addItem("OpenCV not installed — cannot scan")
            return []

        if HAS_PYZBAR:
            decoded = pyzbar.decode(img_bgr)
            results = []
            for obj in decoded:
                data = obj.data.decode("utf-8")
                self.result_list.addItem(f"{obj.type}: {data[:60]}")
                results.append(data)
            if results:
                self.decoded_text.setPlainText("\n\n".join(results))
            else:
                self.result_list.addItem("No QR code or barcode detected")
            return results
        else:
            # Fall back to OpenCV's built-in QR detector
            qr_detector = cv2.QRCodeDetector()
            data, _, _ = qr_detector.detectAndDecode(img_bgr)
            if data:
                self.result_list.addItem(f"QR Code: {data[:60]}")
                self.decoded_text.setPlainText(data)
                return [data]
            else:
                self.result_list.addItem("No QR code detected (install pyzbar for better results)")
                return []

    def _open_image(self):
        if not HAS_CV2:
            self.result_list.clear()
            self.result_list.addItem("OpenCV not installed — cannot open image")
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            self.result_list.clear()
            self.result_list.addItem("Failed to load image")
            return

        self._scan_image(img)

        # Show preview using Qt directly (no cv2 conversion needed for display)
        pixmap = QPixmap(path)
        pixmap = pixmap.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)

    def _scan_webcam(self):
        if not HAS_CV2:
            self.result_list.clear()
            self.result_list.addItem("OpenCV not installed — cannot access webcam")
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.result_list.clear()
            self.result_list.addItem("No webcam found")
            return

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            self.result_list.clear()
            self.result_list.addItem("Failed to capture frame from webcam")
            return

        self._scan_image(frame)
        self._show_cv_frame(frame)