"""Invoice Tool — line items, tax calculation, total, export to PDF."""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QLineEdit, QSpinBox, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt
from tools.finance_service.finance_base import make_header, StatCard, TEAL, ORANGE, GREEN, RED, CARD


class InvoiceTool(QWidget):
    name = "Invoice Tool"
    description = "Fatura oluştur — kalemler, vergi, toplam, PDF çıktı"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🧾 Fatura Aracı")
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        # LEFT — invoice details
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)

        # Header info
        info_frame = QFrame()
        info_frame.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                                  "QLabel{{border:none;background:transparent;}}")
        ifl = QHBoxLayout(info_frame)
        ifl.setContentsMargins(14, 10, 14, 10)
        ifl.setSpacing(12)
        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"
        self._from_inp  = QLineEdit(); self._from_inp.setPlaceholderText("Faturayı Kesen…"); self._from_inp.setStyleSheet(inp)
        self._to_inp    = QLineEdit(); self._to_inp.setPlaceholderText("Fatura Kesilen…");   self._to_inp.setStyleSheet(inp)
        self._inv_no    = QLineEdit(); self._inv_no.setPlaceholderText("Fatura No"); self._inv_no.setStyleSheet(inp); self._inv_no.setMaximumWidth(120)
        self._inv_no.setText(f"INV-{datetime.date.today().strftime('%Y%m%d')}")
        for w in (self._from_inp, self._to_inp, self._inv_no):
            ifl.addWidget(w)
        ll.addWidget(info_frame)

        # Add item row
        item_frame = QFrame()
        item_frame.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                                  "QLabel{{border:none;background:transparent;}}")
        iff = QHBoxLayout(item_frame)
        iff.setContentsMargins(14, 10, 14, 10)
        iff.setSpacing(8)
        self._item_desc = QLineEdit(); self._item_desc.setPlaceholderText("Kalem açıklaması…"); self._item_desc.setStyleSheet(inp)
        self._item_qty  = QSpinBox(); self._item_qty.setRange(1, 9999); self._item_qty.setPrefix("Adet: "); self._item_qty.setStyleSheet(inp); self._item_qty.setMaximumWidth(110)
        self._item_price= QDoubleSpinBox(); self._item_price.setRange(0.01, 9_999_999); self._item_price.setDecimals(2); self._item_price.setPrefix("₺ "); self._item_price.setStyleSheet(inp)
        add_item_btn = QPushButton("➕")
        add_item_btn.setFixedSize(34, 34)
        add_item_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;")
        add_item_btn.clicked.connect(self._add_item)
        for w in (self._item_desc, self._item_qty, self._item_price, add_item_btn):
            iff.addWidget(w)
        ll.addWidget(item_frame)

        # Items table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Açıklama","Adet","Birim Fiyat","Toplam"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        del_item_btn = QPushButton("🗑 Seçili Sil")
        del_item_btn.setStyleSheet("background:#B71C1C;color:#fff;border:none;border-radius:6px;padding:6px 14px;")
        del_item_btn.clicked.connect(self._del_item)
        ll.addWidget(self._table, 1)
        ll.addWidget(del_item_btn, 0, Qt.AlignRight)
        body.addWidget(left, 3)

        # RIGHT — totals + notes + export
        right = QFrame()
        right.setFixedWidth(260)
        right.setStyleSheet(f"QFrame{{background:{CARD};border-radius:10px;}}"
                            "QLabel{{border:none;background:transparent;}}")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 20, 20, 20)
        rl.setSpacing(12)

        rl.addWidget(QLabel("Vergi Oranı (%)", styleSheet="color:#888;font-size:11px;"))
        self._tax_rate = QDoubleSpinBox()
        self._tax_rate.setRange(0, 100)
        self._tax_rate.setDecimals(1)
        self._tax_rate.setValue(18)
        self._tax_rate.setSuffix("%")
        self._tax_rate.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:8px;color:#E0E0E0;")
        self._tax_rate.valueChanged.connect(self._update_totals)
        rl.addWidget(self._tax_rate)

        self._sub_card  = StatCard("Ara Toplam", "₺0", ORANGE)
        self._tax_card  = StatCard("KDV", "₺0", RED)
        self._total_card= StatCard("Genel Toplam", "₺0", TEAL)
        for c in (self._sub_card, self._tax_card, self._total_card):
            rl.addWidget(c)

        rl.addWidget(QLabel("Notlar / Ödeme Koşulları:", styleSheet="color:#888;font-size:11px;"))
        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Ödeme vadesi, banka bilgileri…")
        self._notes.setFixedHeight(80)
        self._notes.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;font-size:12px;")
        rl.addWidget(self._notes)

        export_btn = QPushButton("📄 PDF Olarak Kaydet")
        export_btn.setFixedHeight(38)
        export_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:8px;font-weight:bold;font-size:13px;")
        export_btn.clicked.connect(self._export_pdf)
        rl.addWidget(export_btn)
        rl.addStretch()
        body.addWidget(right)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _add_item(self):
        desc  = self._item_desc.text().strip()
        if not desc: return
        qty   = self._item_qty.value()
        price = self._item_price.value()
        self._items.append({"desc": desc, "qty": qty, "price": price})
        self._item_desc.clear()
        self._refresh_table()

    def _del_item(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._items):
            self._items.pop(row)
            self._refresh_table()

    def _refresh_table(self):
        self._table.setRowCount(0)
        for item in self._items:
            r = self._table.rowCount(); self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(item["desc"]))
            self._table.setItem(r, 1, QTableWidgetItem(str(item["qty"])))
            self._table.setItem(r, 2, QTableWidgetItem(f"₺{item['price']:,.2f}"))
            self._table.setItem(r, 3, QTableWidgetItem(f"₺{item['qty']*item['price']:,.2f}"))
        self._update_totals()

    def _update_totals(self):
        subtotal = sum(i["qty"] * i["price"] for i in self._items)
        tax      = subtotal * self._tax_rate.value() / 100
        total    = subtotal + tax
        self._sub_card.update_value(f"₺{subtotal:,.2f}")
        self._tax_card.update_value(f"₺{tax:,.2f}")
        self._total_card.update_value(f"₺{total:,.2f}")

    def _export_pdf(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getSaveFileName(self, "PDF Kaydet", f"fatura_{self._inv_no.text()}.pdf", "PDF (*.pdf)")
        if not path: return
        try:
            from PySide6.QtGui import QPdfWriter, QPageSize
            from PySide6.QtCore import QSizeF
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.A4))
            writer.setTitle(f"Fatura {self._inv_no.text()}")
            from PySide6.QtGui import QPainter
            from PySide6.QtCore import QRectF
            painter = QPainter(writer)
            painter.setFont(__import__("PySide6.QtGui", fromlist=["QFont"]).QFont("Segoe UI", 10))
            y = 100
            def line(text, x=100, bold=False, size=10, color=None):
                nonlocal y
                from PySide6.QtGui import QFont, QColor
                f = QFont("Segoe UI", size)
                f.setBold(bold)
                painter.setFont(f)
                if color: painter.setPen(QColor(color))
                painter.drawText(x, y, text)
                y += size * 2 + 4
                painter.setPen(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#000000"))
            line("FATURA", bold=True, size=18, color="#00BFA5")
            line(f"No: {self._inv_no.text()}")
            line(f"Tarih: {datetime.date.today().isoformat()}")
            line(f"Kesen: {self._from_inp.text()}")
            line(f"Kesilen: {self._to_inp.text()}")
            y += 20
            line("KALEMLER", bold=True)
            for item in self._items:
                line(f"  {item['desc']}  |  {item['qty']} adet  x  ₺{item['price']:,.2f}  =  ₺{item['qty']*item['price']:,.2f}")
            y += 10
            subtotal = sum(i["qty"] * i["price"] for i in self._items)
            tax = subtotal * self._tax_rate.value() / 100
            line(f"Ara Toplam: ₺{subtotal:,.2f}")
            line(f"KDV (%{self._tax_rate.value():.0f}): ₺{tax:,.2f}")
            line(f"GENEL TOPLAM: ₺{subtotal+tax:,.2f}", bold=True, size=12, color="#00BFA5")
            if self._notes.toPlainText():
                y += 20
                line("Notlar:", bold=True)
                line(self._notes.toPlainText())
            painter.end()
            QMessageBox.information(self, "Başarılı", f"PDF kaydedildi:\n{path}")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Hata", f"PDF oluşturulamadı:\n{e}")
