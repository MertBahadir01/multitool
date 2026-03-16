"""
Image ↔ Base64 Tool
====================
Tab 1 — Image → Base64
  • Browse or drag-and-drop an image file
  • Preview the image
  • Output: raw Base64 string or full data-URI  (data:image/png;base64,...)
  • Copy to clipboard or save as .txt / .b64

Tab 2 — Base64 → Image
  • Paste a Base64 string or data-URI
  • Preview the decoded image
  • Save decoded image to disk as PNG / JPG / original format
"""

import base64
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFileDialog, QFrame, QTabWidget, QCheckBox,
    QScrollArea, QSizePolicy, QApplication, QMessageBox
)
from PySide6.QtCore import Qt, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QFont, QPixmap, QImage, QDragEnterEvent, QDropEvent


# ── Shared preview widget ──────────────────────────────────────────────────────
class ImagePreview(QLabel):
    """Scalable image preview area, shows placeholder when empty."""

    PLACEHOLDER = "🖼️\nNo image loaded\nBrowse or paste Base64 below"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("""
            QLabel {
                background: #111;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                color: #444;
                font-size: 14px;
            }
        """)
        self._pix: QPixmap | None = None
        self.clear_image()

    def clear_image(self):
        self._pix = None
        self.setText(self.PLACEHOLDER)

    def set_pixmap_data(self, pix: QPixmap):
        self._pix = pix
        self._fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pix:
            self._fit()

    def _fit(self):
        if not self._pix:
            return
        scaled = self._pix.scaled(
            self.width() - 16, self.height() - 16,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.setPixmap(scaled)


# ── Tab 1: Image → Base64 ─────────────────────────────────────────────────────
class ImageToBase64Tab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_b64   = ""
        self._mime_type = "image/png"
        self._filename  = ""
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Input row ─────────────────────────────────────────────────────────
        input_row = QHBoxLayout()
        self._path_lbl = QLabel("No file selected — browse or drag & drop an image here")
        self._path_lbl.setStyleSheet("color:#666; font-size:12px;")
        self._path_lbl.setWordWrap(True)
        input_row.addWidget(self._path_lbl, 1)
        browse_btn = QPushButton("📂 Browse")
        browse_btn.setFixedWidth(110)
        browse_btn.clicked.connect(self._browse)
        input_row.addWidget(browse_btn)
        root.addLayout(input_row)

        # ── Preview ────────────────────────────────────────────────────────────
        self._preview = ImagePreview()
        root.addWidget(self._preview, 1)

        # ── Info strip ────────────────────────────────────────────────────────
        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet("color:#888; font-size:11px;")
        root.addWidget(self._info_lbl)

        # ── Options ───────────────────────────────────────────────────────────
        opt_row = QHBoxLayout()
        self._data_uri_chk = QCheckBox("Include data-URI prefix  (data:image/…;base64,…)")
        self._data_uri_chk.setChecked(True)
        self._data_uri_chk.toggled.connect(self._refresh_output)
        opt_row.addWidget(self._data_uri_chk)
        opt_row.addStretch()
        root.addLayout(opt_row)

        # ── Output ────────────────────────────────────────────────────────────
        root.addWidget(QLabel("Base64 output:", styleSheet="color:#888; font-size:11px;"))
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumHeight(110)
        self._output.setPlaceholderText("Base64 string will appear here…")
        self._output.setStyleSheet("""
            QTextEdit {
                background:#0D0D0D; border:1px solid #2A2A2A;
                border-radius:6px; color:#00BFA5;
                font-family:monospace; font-size:11px; padding:6px;
            }
        """)
        root.addWidget(self._output)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)
        save_btn = QPushButton("💾 Save as .txt")
        save_btn.setObjectName("secondary")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        clear_btn = QPushButton("✕ Clear")
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

    # ── Drag & drop ───────────────────────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            self._load_file(urls[0].toLocalFile())

    # ── Logic ─────────────────────────────────────────────────────────────────
    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.ico *.svg)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        if not os.path.isfile(path):
            return
        ext       = path.rsplit(".", 1)[-1].lower()
        mime_map  = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
                     "bmp": "bmp", "webp": "webp", "tiff": "tiff",
                     "ico": "x-icon", "svg": "svg+xml"}
        self._mime_type = "image/" + mime_map.get(ext, ext)
        self._filename  = os.path.basename(path)

        try:
            with open(path, "rb") as f:
                raw = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._raw_b64 = base64.b64encode(raw).decode("ascii")

        pix = QPixmap(path)
        if not pix.isNull():
            self._preview.set_pixmap_data(pix)

        size_kb = len(raw) / 1024
        b64_kb  = len(self._raw_b64) / 1024
        self._path_lbl.setText(path)
        self._info_lbl.setText(
            f"File: {self._filename}   "
            f"Original: {size_kb:.1f} KB   "
            f"Base64: {b64_kb:.1f} KB   "
            f"{pix.width()}×{pix.height()} px"
        )
        self._refresh_output()

    def _refresh_output(self):
        if not self._raw_b64:
            return
        if self._data_uri_chk.isChecked():
            self._output.setPlainText(f"data:{self._mime_type};base64,{self._raw_b64}")
        else:
            self._output.setPlainText(self._raw_b64)

    def _copy(self):
        text = self._output.toPlainText()
        if not text:
            QMessageBox.information(self, "Nothing to copy", "Load an image first.")
            return
        QApplication.clipboard().setText(text)

    def _save(self):
        text = self._output.toPlainText()
        if not text:
            QMessageBox.information(self, "Nothing to save", "Load an image first.")
            return
        default = (self._filename or "image") + ".b64.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Base64", default, "Text files (*.txt *.b64)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def _clear(self):
        self._raw_b64 = ""
        self._mime_type = "image/png"
        self._filename = ""
        self._path_lbl.setText("No file selected — browse or drag & drop an image here")
        self._info_lbl.setText("")
        self._output.clear()
        self._preview.clear_image()


# ── Tab 2: Base64 → Image ─────────────────────────────────────────────────────
class Base64ToImageTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix: QPixmap | None = None
        self._decoded_bytes: bytes | None = None
        self._detected_ext = "png"
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Input ─────────────────────────────────────────────────────────────
        root.addWidget(QLabel("Paste Base64 string or data-URI:",
                              styleSheet="color:#888; font-size:11px;"))
        self._input = QTextEdit()
        self._input.setPlaceholderText(
            "data:image/png;base64,iVBORw0KGgo…\n"
            "— or just the raw Base64 string —"
        )
        self._input.setMaximumHeight(110)
        self._input.setStyleSheet("""
            QTextEdit {
                background:#0D0D0D; border:1px solid #2A2A2A;
                border-radius:6px; color:#CCCCCC;
                font-family:monospace; font-size:11px; padding:6px;
            }
        """)
        root.addWidget(self._input)

        # ── Decode button ─────────────────────────────────────────────────────
        decode_row = QHBoxLayout()
        decode_btn = QPushButton("🔍 Decode & Preview")
        decode_btn.setFixedHeight(36)
        decode_btn.clicked.connect(self._decode)
        decode_row.addWidget(decode_btn)
        paste_btn = QPushButton("📋 Paste from Clipboard")
        paste_btn.setObjectName("secondary")
        paste_btn.clicked.connect(self._paste)
        decode_row.addWidget(paste_btn)
        clear_btn = QPushButton("✕ Clear")
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self._clear)
        decode_row.addWidget(clear_btn)
        decode_row.addStretch()
        root.addLayout(decode_row)

        # ── Status ────────────────────────────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size:11px;")
        root.addWidget(self._status_lbl)

        # ── Preview ───────────────────────────────────────────────────────────
        self._preview = ImagePreview()
        root.addWidget(self._preview, 1)

        # ── Save buttons ──────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_png_btn = QPushButton("💾 Save as PNG")
        save_png_btn.clicked.connect(lambda: self._save("png"))
        save_row.addWidget(save_png_btn)
        save_jpg_btn = QPushButton("💾 Save as JPG")
        save_jpg_btn.setObjectName("secondary")
        save_jpg_btn.clicked.connect(lambda: self._save("jpg"))
        save_row.addWidget(save_jpg_btn)
        save_orig_btn = QPushButton("💾 Save (original format)")
        save_orig_btn.setObjectName("secondary")
        save_orig_btn.clicked.connect(lambda: self._save(self._detected_ext))
        save_row.addWidget(save_orig_btn)
        save_row.addStretch()
        root.addLayout(save_row)

    # ── Logic ─────────────────────────────────────────────────────────────────
    def _paste(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self._input.setPlainText(text)

    def _decode(self):
        raw_text = self._input.toPlainText().strip()
        if not raw_text:
            self._set_status("⚠️ Paste a Base64 string first.", error=True)
            return

        # Strip data-URI prefix if present
        b64_data  = raw_text
        mime_hint = ""
        if raw_text.startswith("data:"):
            try:
                header, b64_data = raw_text.split(",", 1)
                mime_hint = header.split(":")[1].split(";")[0]   # e.g. image/png
            except Exception:
                pass

        # Decode
        try:
            # Remove whitespace that might have crept in
            b64_data = b64_data.replace("\n", "").replace("\r", "").replace(" ", "")
            raw_bytes = base64.b64decode(b64_data)
        except Exception as e:
            self._set_status(f"❌ Invalid Base64: {e}", error=True)
            self._preview.clear_image()
            return

        # Try to load as image
        pix = QPixmap()
        ok  = pix.loadFromData(raw_bytes)
        if not ok or pix.isNull():
            self._set_status("❌ Decoded successfully but could not render as image. "
                             "Make sure this is an image, not another file type.", error=True)
            self._preview.clear_image()
            self._pix = None
            self._decoded_bytes = None
            return

        self._pix          = pix
        self._decoded_bytes = raw_bytes

        # Detect format from mime or magic bytes
        self._detected_ext = self._detect_ext(raw_bytes, mime_hint)

        size_kb = len(raw_bytes) / 1024
        self._set_status(
            f"✅ Decoded  {pix.width()}×{pix.height()} px  "
            f"|  {size_kb:.1f} KB  |  format: {self._detected_ext.upper()}",
            error=False
        )
        self._preview.set_pixmap_data(pix)

    def _detect_ext(self, raw: bytes, mime_hint: str) -> str:
        # Magic bytes
        if raw[:8] == b"\x89PNG\r\n\x1a\n": return "png"
        if raw[:3] == b"\xff\xd8\xff":      return "jpg"
        if raw[:6] in (b"GIF87a", b"GIF89a"): return "gif"
        if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP": return "webp"
        if raw[:2] == b"BM":                return "bmp"
        if raw[:4] == b"\x00\x00\x01\x00":  return "ico"
        # Fall back to mime hint
        if mime_hint:
            return mime_hint.split("/")[-1].replace("jpeg", "jpg").replace("svg+xml", "svg")
        return "png"

    def _save(self, ext: str):
        if self._pix is None or self._decoded_bytes is None:
            QMessageBox.information(self, "No Image", "Decode an image first.")
            return
        ext = ext.lower().lstrip(".")
        fmt_filter = f"{ext.upper()} files (*.{ext});;All files (*)"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save as {ext.upper()}", f"image.{ext}", fmt_filter)
        if not path:
            return
        # For PNG/JPG use Qt's save (ensures correct encoding);
        # for others write raw bytes if we have them
        if ext in ("png", "jpg", "jpeg", "bmp"):
            qt_fmt = "JPEG" if ext in ("jpg", "jpeg") else ext.upper()
            if not self._pix.save(path, qt_fmt):
                QMessageBox.critical(self, "Error", f"Could not save as {ext.upper()}.")
        else:
            with open(path, "wb") as f:
                f.write(self._decoded_bytes)

    def _set_status(self, msg: str, error: bool = False):
        color = "#F44336" if error else "#4CAF50"
        self._status_lbl.setStyleSheet(f"color:{color}; font-size:11px;")
        self._status_lbl.setText(msg)

    def _clear(self):
        self._input.clear()
        self._status_lbl.setText("")
        self._preview.clear_image()
        self._pix = None
        self._decoded_bytes = None


# ── Main Tool ──────────────────────────────────────────────────────────────────
class ImageBase64Tool(QWidget):
    name        = "Image ↔ Base64"
    description = "Convert images to Base64 strings and decode Base64 back to images"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("🖼️  Image ↔ Base64")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        sub = QLabel("Convert images to Base64 strings and back")
        sub.setStyleSheet("color:#666; font-size:12px;")
        hl.addWidget(sub)
        root.addWidget(hdr)

        tabs = QTabWidget()
        tabs.addTab(ImageToBase64Tab(), "🖼️ → 🔤  Image to Base64")
        tabs.addTab(Base64ToImageTab(), "🔤 → 🖼️  Base64 to Image")
        root.addWidget(tabs, 1)
