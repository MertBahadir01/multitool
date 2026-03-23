"""Currency Converter — live rates based on TRY, historical line chart."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDoubleSpinBox, QFrame, QGridLayout, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QLinearGradient
from PySide6.QtCore import QRectF, QPointF
from core.auth_manager import auth_manager
from tools.finance_service.finance_base import (
    make_header, fetch_async, MiniChart, StatCard, TEAL, ORANGE, BG, CARD, PALETTE
)
from tools.finance_service.finance_service import fetch_exchange_rates, fetch_stock_history

POPULAR = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD",
           "CNY", "RUB", "SAR", "AED", "DKK", "SEK", "NOK",
           "PLN", "HUF", "CZK", "RON", "BGN", "HRK"]

NAMES = {
    "USD":"Amerikan Doları","EUR":"Euro","GBP":"İngiliz Sterlini",
    "JPY":"Japon Yeni","CHF":"İsviçre Frangı","CAD":"Kanada Doları",
    "AUD":"Avustralya Doları","CNY":"Çin Yuanı","RUB":"Rus Rublesi",
    "SAR":"Suudi Riyali","AED":"BAE Dirhemi","TRY":"Türk Lirası",
}


class CurrencyConverterTool(QWidget):
    name = "Currency Converter"
    description = "Döviz çevirici — TRY bazlı anlık kurlar + geçmiş grafik"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rates = {}
        self._history = []
        self._build_ui()
        self._load_rates()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("💱 Döviz Çevirici", "Kaynak: TRY bazlı anlık kur")
        self._refresh_btn = self._make_btn("🔄 Güncelle")
        self._refresh_btn.clicked.connect(self._load_rates)
        hl.addWidget(self._refresh_btn)
        self._status_lbl = QLabel("Kurlar yükleniyor…")
        self._status_lbl.setStyleSheet("color:#888;font-size:11px;")
        hl.addWidget(self._status_lbl)
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        # LEFT — converter + rate table
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(14)

        # Converter card
        conv = QFrame()
        conv.setStyleSheet(f"QFrame{{background:{CARD};border-radius:10px;}}"
                           "QLabel{border:none;background:transparent;}")
        cl = QVBoxLayout(conv)
        cl.setContentsMargins(20, 20, 20, 20)
        cl.setSpacing(12)
        cl.addWidget(QLabel("Miktar ve Para Birimi",
                            styleSheet="color:#888;font-size:12px;"))
        row1 = QHBoxLayout()
        self._amount = QDoubleSpinBox()
        self._amount.setRange(0, 999_999_999)
        self._amount.setValue(1000)
        self._amount.setDecimals(2)
        self._amount.setPrefix("  ")
        self._amount.setStyleSheet(
            "background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
            "padding:6px;font-size:15px;color:#E0E0E0;min-width:140px;")
        self._from_cb = QComboBox()
        self._to_cb   = QComboBox()
        for cb in (self._from_cb, self._to_cb):
            cb.addItems(["TRY"] + POPULAR)
            cb.setStyleSheet(
                "background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:6px;font-size:13px;color:#E0E0E0;min-width:90px;")
        self._from_cb.setCurrentText("USD")
        self._to_cb.setCurrentText("TRY")
        swap_btn = self._make_btn("⇄")
        swap_btn.setFixedWidth(40)
        swap_btn.clicked.connect(self._swap)
        row1.addWidget(self._amount, 2)
        row1.addWidget(self._from_cb, 1)
        row1.addWidget(swap_btn)
        row1.addWidget(self._to_cb, 1)
        cl.addLayout(row1)
        self._result_lbl = QLabel("—")
        self._result_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self._result_lbl.setStyleSheet(f"color:{TEAL};")
        cl.addWidget(self._result_lbl)
        self._rate_lbl = QLabel("")
        self._rate_lbl.setStyleSheet("color:#666;font-size:11px;")
        cl.addWidget(self._rate_lbl)
        convert_btn = self._make_btn("Hesapla")
        convert_btn.clicked.connect(self._convert)
        cl.addWidget(convert_btn)
        ll.addWidget(conv)

        # Chart
        self._chart = MiniChart()
        self._chart.setMinimumHeight(200)
        ll.addWidget(self._chart, 1)
        self._chart_lbl = QLabel("Geçmiş grafik: USD/TRY seçin")
        self._chart_lbl.setStyleSheet("color:#555;font-size:11px;")
        ll.addWidget(self._chart_lbl)
        self._from_cb.currentTextChanged.connect(self._load_chart)
        body.addWidget(left, 3)

        # RIGHT — rate table
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Tüm Kurlar (TRY bazlı)",
                            styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Döviz", "1 TRY =", "1 Birim = ₺"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        rl.addWidget(self._table, 1)
        body.addWidget(right, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

        for widget in (self._amount, self._from_cb, self._to_cb):
            if hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._convert)
            else:
                widget.currentTextChanged.connect(self._convert)

    def _make_btn(self, text):
        b = QPushButton(text)
        b.setFixedHeight(34)
        b.setStyleSheet(
            f"QPushButton{{background:{TEAL};color:#000;border:none;border-radius:6px;"
            "font-weight:bold;padding:0 14px;}}"
            f"QPushButton:hover{{background:#00D4B8;}}")
        return b

    def _load_rates(self):
        self._status_lbl.setText("⏳ Güncelleniyor…")
        fetch_async(lambda: fetch_exchange_rates("TRY"), self._on_rates)

    def _on_rates(self, rates):
        if rates:
            self._rates = rates
            self._status_lbl.setText("✅ Güncel")
            self._fill_table()
            self._convert()
            self._load_chart()
        else:
            self._status_lbl.setText("⚠️ Bağlanamadı (önbellek)")

    def _fill_table(self):
        self._table.setRowCount(0)
        try_rate = self._rates.get("TRY", 1.0)
        for cur in POPULAR:
            if cur == "TRY": continue
            rate = self._rates.get(cur, 0)
            if rate == 0: continue
            r = self._table.rowCount()
            self._table.insertRow(r)
            name = NAMES.get(cur, cur)
            self._table.setItem(r, 0, QTableWidgetItem(f"{cur}  {name}"))
            self._table.setItem(r, 1, QTableWidgetItem(f"{rate:.4f}"))
            self._table.setItem(r, 2, QTableWidgetItem(f"₺ {1/rate:.4f}" if rate else "—"))

    def _convert(self):
        if not self._rates: return
        amt  = self._amount.value()
        frm  = self._from_cb.currentText()
        to   = self._to_cb.currentText()
        rate_frm = self._rates.get(frm, 1)
        rate_to  = self._rates.get(to,  1)
        if rate_frm == 0: return
        result = amt / rate_frm * rate_to
        self._result_lbl.setText(f"{result:,.4f} {to}")
        cross = rate_to / rate_frm if rate_frm else 0
        self._rate_lbl.setText(f"1 {frm} = {cross:.6f} {to}")

    def _swap(self):
        f, t = self._from_cb.currentText(), self._to_cb.currentText()
        self._from_cb.setCurrentText(t)
        self._to_cb.setCurrentText(f)

    def _load_chart(self):
        sym = self._from_cb.currentText()
        if sym == "TRY": sym = "USD"
        ticker = f"{sym}TRY=X"
        self._chart_lbl.setText(f"⏳ {sym}/TRY geçmiş yükleniyor…")
        fetch_async(lambda: fetch_stock_history(ticker, "1y"), self._on_chart)

    def _on_chart(self, hist):
        if not hist:
            self._chart_lbl.setText("Geçmiş grafik yüklenemedi")
            return
        labels = [h["date"][5:] for h in hist]
        vals   = [h["close"] for h in hist]
        sym = self._from_cb.currentText()
        self._chart.set_data([(TEAL, vals)], labels,
                             title=f"{sym}/TRY — Son 1 Yıl", y_sym="₺")
        self._chart_lbl.setText(f"✅ {len(hist)} günlük veri")


from PySide6.QtWidgets import QPushButton
