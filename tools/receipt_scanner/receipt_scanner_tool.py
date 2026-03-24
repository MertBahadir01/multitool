"""Receipt Scanner — load receipt image, OCR with pytesseract or fallback."""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTextEdit, QDoubleSpinBox, QLineEdit, QComboBox, QFileDialog,
    QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import TransactionService
from tools.finance_service.finance_base import make_header, TEAL, ORANGE, RED, GREEN, CARD

CATEGORIES = ["Food","Transport","Bills","Rent","Health","Entertainment",
              "Clothing","Education","Shopping","Other"]


class ReceiptScannerTool(QWidget):
    name = "Receipt Scanner"
    description = "Fiş/makbuz görüntüsünden OCR ile gider çıkarma"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc  = TransactionService(u["id"]) if u else None
        self._img_path = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🧾 Fiş Tarayıcı", "Fotoğraftan gider kaydet")
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        # LEFT — image preview
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(10)

        self._img_lbl = QLabel("📷 Fiş görüntüsü yükleyin")
        self._img_lbl.setAlignment(Qt.AlignCenter)
        self._img_lbl.setStyleSheet(f"background:{CARD};border:1px dashed #3E3E3E;border-radius:8px;color:#555;font-size:14px;")
        self._img_lbl.setMinimumSize(300, 400)
        ll.addWidget(self._img_lbl, 1)

        btn_row = QHBoxLayout()
        load_btn = self._btn("📂 Görüntü Yükle")
        load_btn.clicked.connect(self._load_image)
        scan_btn = self._btn("🔍 OCR Tara")
        scan_btn.clicked.connect(self._scan)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(scan_btn)
        ll.addLayout(btn_row)
        body.addWidget(left, 1)

        # RIGHT — OCR output + save form
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)

        rl.addWidget(QLabel("OCR Sonucu:", styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        self._ocr_text = QTextEdit()
        self._ocr_text.setPlaceholderText("OCR metni burada görünecek…")
        self._ocr_text.setStyleSheet(
            "background:#1A1A1A;border:1px solid #3E3E3E;border-radius:8px;padding:10px;color:#E0E0E0;font-size:12px;")
        self._ocr_text.setMinimumHeight(200)
        rl.addWidget(self._ocr_text, 1)

        rl.addWidget(QLabel("Gider Olarak Kaydet:", styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        save_frame = QFrame()
        save_frame.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                                  "QLabel{{border:none;background:transparent;}}")
        sfl = QVBoxLayout(save_frame)
        sfl.setContentsMargins(16, 14, 16, 14)
        sfl.setSpacing(10)

        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Tutar (₺):"))
        self._amt_spin = QDoubleSpinBox()
        self._amt_spin.setRange(0.01, 999_999)
        self._amt_spin.setDecimals(2)
        self._amt_spin.setStyleSheet(inp)
        row1.addWidget(self._amt_spin)
        sfl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Kategori:"))
        self._cat_cb = QComboBox()
        self._cat_cb.addItems(CATEGORIES)
        self._cat_cb.setEditable(True)
        self._cat_cb.setStyleSheet(inp)
        row2.addWidget(self._cat_cb)
        sfl.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Not:"))
        self._note_inp = QLineEdit()
        self._note_inp.setPlaceholderText("İsteğe bağlı not…")
        self._note_inp.setStyleSheet(inp)
        row3.addWidget(self._note_inp)
        sfl.addLayout(row3)

        save_btn = self._btn("💾 Gider Olarak Kaydet")
        save_btn.clicked.connect(self._save_expense)
        sfl.addWidget(save_btn)

        self._save_status = QLabel("")
        self._save_status.setStyleSheet("color:#888;font-size:11px;")
        sfl.addWidget(self._save_status)

        rl.addWidget(save_frame)
        body.addWidget(right, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _btn(self, txt):
        b = QPushButton(txt)
        b.setFixedHeight(36)
        b.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        return b

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Fiş Görüntüsü Seç", "",
            "Görüntüler (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)")
        if not path: return
        self._img_path = path
        pix = QPixmap(path)
        if not pix.isNull():
            scaled = pix.scaled(300, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img_lbl.setPixmap(scaled)
            self._img_lbl.setText("")

    def _scan(self):
        if not self._img_path:
            self._ocr_text.setPlainText("⚠️ Önce bir görüntü yükleyin.")
            return
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(self._img_path)
            # Try Turkish first, fallback to English
            try:
                text = pytesseract.image_to_string(img, lang="tur+eng")
            except Exception:
                text = pytesseract.image_to_string(img)
            self._ocr_text.setPlainText(text)
            # Auto-extract total amount
            self._auto_extract(text)
        except ImportError:
            # No pytesseract — show manual entry prompt
            self._ocr_text.setPlainText(
                "⚠️ pytesseract kurulu değil.\n\n"
                "Otomatik OCR için:\n"
                "  pip install pytesseract pillow\n"
                "  + Tesseract-OCR uygulamasını yükleyin.\n\n"
                "Tutar ve kategoriyi aşağıda manuel girerek kaydedin."
            )

    def _auto_extract(self, text: str):
        """Try to parse a total amount from OCR text."""
        import re
        # Look for patterns like TOPLAM: 123.45 or TOTAL 99,50
        patterns = [
            r"(?:toplam|total|tutar|amount)[:\s]+[₺$€]?\s*(\d[\d.,]+)",
            r"[₺$€]\s*(\d[\d.,]+)",
            r"(\d{1,6}[.,]\d{2})\s*(?:tl|₺|lira)?",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val_str = m.group(1).replace(",", ".")
                try:
                    val = float(val_str)
                    if 0 < val < 100_000:
                        self._amt_spin.setValue(val)
                        break
                except ValueError:
                    pass

    def _save_expense(self):
        if not self._svc:
            self._save_status.setText("⚠️ Giriş yapılmamış")
            return
        amt  = self._amt_spin.value()
        cat  = self._cat_cb.currentText()
        note = self._note_inp.text().strip() or (
            f"Fiş tarayıcı: {os.path.basename(self._img_path)}" if self._img_path else "Fiş tarayıcı")
        self._svc.add(amount=amt, category=cat, note=note, tx_type="expense")
        self._save_status.setText(f"✅ ₺{amt:,.2f} '{cat}' olarak kaydedildi")
        self._amt_spin.setValue(0)
        self._note_inp.clear()
