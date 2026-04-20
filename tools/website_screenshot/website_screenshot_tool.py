"""Website Screenshot — capture any URL as an image using screenshotapi.net (free tier)."""
import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QFileDialog, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap, QImage


class _Worker(QThread):
    result = Signal(bytes)
    error  = Signal(str)
    def __init__(self, url, width, full): super().__init__(); self._url=url; self._w=width; self._full=full
    def run(self):
        try:
            # Use screenshotapi.net free tier (no key needed for basic)
            params = {
                "url": self._url,
                "width": self._w,
                "height": 800,
                "fullpage": "true" if self._full else "false",
                "output": "image",
                "delay": "1000",
            }
            r = requests.get("https://shot.screenshotapi.net/screenshot", params=params, timeout=30)
            r.raise_for_status()
            if r.headers.get("content-type","").startswith("image"):
                self.result.emit(r.content)
            else:
                # Fallback: use thum.io (completely free, no key)
                thumb_url = f"https://image.thum.io/get/width/{self._w}/{self._url}"
                r2 = requests.get(thumb_url, timeout=20)
                r2.raise_for_status()
                self.result.emit(r2.content)
        except Exception as e:
            # Final fallback: thum.io
            try:
                thumb_url = f"https://image.thum.io/get/width/{self._w}/{self._url}"
                r3 = requests.get(thumb_url, timeout=20)
                r3.raise_for_status()
                self.result.emit(r3.content)
            except Exception as e2:
                self.error.emit(str(e2))


class WebsiteScreenshotTool(QWidget):
    name        = "Website Screenshot"
    description = "Capture a screenshot of any website URL"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._img_data = None
        self._worker   = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 14, 24, 14)
        t = QLabel("📸 Website Screenshot")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        root.addWidget(hdr)

        body = QWidget(); body.setStyleSheet("background:#151515;")
        bl = QVBoxLayout(body); bl.setContentsMargins(24, 20, 24, 20); bl.setSpacing(12)

        # Controls
        ctrl = QHBoxLayout()
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://example.com")
        self._url_edit.setStyleSheet(self._inp())
        self._url_edit.setFixedHeight(38)
        self._url_edit.returnPressed.connect(self._capture)
        ctrl.addWidget(self._url_edit)

        ctrl.addWidget(QLabel("Width:", styleSheet="color:#888;"))
        self._width_cb = QComboBox()
        self._width_cb.addItems(["1280", "1920", "1024", "768", "480"])
        self._width_cb.setFixedWidth(90); self._width_cb.setStyleSheet(self._inp())
        ctrl.addWidget(self._width_cb)

        self._capture_btn = QPushButton("📷  Capture")
        self._capture_btn.setFixedHeight(38)
        self._capture_btn.setStyleSheet(
            "background:#00BFA5;color:#000;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;padding:0 18px;")
        self._capture_btn.clicked.connect(self._capture)
        ctrl.addWidget(self._capture_btn)
        bl.addLayout(ctrl)

        self._status_lbl = QLabel("Enter a URL and click Capture")
        self._status_lbl.setStyleSheet("color:#555;font-size:12px;")
        bl.addWidget(self._status_lbl)

        # Preview
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:1px solid #2A2A2A;background:#0D0D0D;border-radius:8px;}")
        self._img_lbl = QLabel("Screenshot will appear here")
        self._img_lbl.setAlignment(Qt.AlignCenter)
        self._img_lbl.setStyleSheet("color:#333;font-size:14px;padding:60px;")
        scroll.setWidget(self._img_lbl)
        bl.addWidget(scroll, 1)

        # Save button
        save_btn = QPushButton("💾  Save Image")
        save_btn.setFixedHeight(34)
        save_btn.setStyleSheet("background:#3A3A3A;color:#E0E0E0;border:none;border-radius:6px;font-size:12px;padding:0 16px;")
        save_btn.clicked.connect(self._save)
        bl.addWidget(save_btn, 0, Qt.AlignLeft)

        root.addWidget(body, 1)

    def _inp(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:5px 10px;color:#E0E0E0;font-size:13px;")

    def _capture(self):
        url = self._url_edit.text().strip()
        if not url: return
        if not url.startswith("http"): url = "https://" + url
        width = int(self._width_cb.currentText())
        self._capture_btn.setEnabled(False)
        self._status_lbl.setText("📡 Capturing…"); self._status_lbl.setStyleSheet("color:#FF9800;font-size:12px;")
        self._img_lbl.setText("Capturing screenshot…")
        self._worker = _Worker(url, width, False)
        self._worker.result.connect(self._on_image)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_image(self, data: bytes):
        self._img_data = data
        pixmap = QPixmap(); pixmap.loadFromData(data)
        if pixmap.isNull():
            self._status_lbl.setText("❌ Invalid image received"); return
        scaled = pixmap.scaledToWidth(min(pixmap.width(), 900), Qt.SmoothTransformation)
        self._img_lbl.setPixmap(scaled)
        self._img_lbl.setStyleSheet("")
        self._status_lbl.setText(f"✅ Screenshot captured  ({pixmap.width()}×{pixmap.height()}px)")
        self._status_lbl.setStyleSheet("color:#4CAF50;font-size:12px;")
        self._capture_btn.setEnabled(True)

    def _on_error(self, err):
        self._status_lbl.setText(f"❌ {err}")
        self._status_lbl.setStyleSheet("color:#F44336;font-size:12px;")
        self._capture_btn.setEnabled(True)

    def _save(self):
        if not self._img_data:
            QMessageBox.information(self, "No image", "Capture a screenshot first."); return
        path, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "screenshot.png",
                                              "Images (*.png *.jpg)")
        if path:
            with open(path, "wb") as f: f.write(self._img_data)
            self._status_lbl.setText(f"💾 Saved: {path}")
