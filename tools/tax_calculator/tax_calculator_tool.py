"""Tax Calculator — Turkish income tax brackets 2024."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from tools.finance_service.finance_service import tr_income_tax
from tools.finance_service.finance_base import make_header, StatCard, BarChart, TEAL, ORANGE, RED, GREEN, CARD


class TaxCalculatorTool(QWidget):
    name = "Tax Calculator"
    description = "Türkiye gelir vergisi hesaplayıcı (2024 dilimleri)"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._calculate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🧾 Vergi Hesaplayıcı", "Türkiye 2024 Gelir Vergisi Dilimleri")
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        # Left — input + stats
        left = QFrame()
        left.setFixedWidth(280)
        left.setStyleSheet(f"QFrame{{background:{CARD};border-radius:10px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 20, 20, 20)
        ll.setSpacing(14)
        ll.addWidget(QLabel("Yıllık Brüt Gelir (₺)", styleSheet="color:#888;font-size:11px;"))
        self._income = QDoubleSpinBox()
        self._income.setRange(0, 999_999_999)
        self._income.setDecimals(0)
        self._income.setValue(500_000)
        self._income.setSingleStep(10_000)
        self._income.setStyleSheet(
            "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:8px;font-size:14px;color:#E0E0E0;")
        ll.addWidget(self._income)
        btn = QPushButton("Hesapla")
        btn.setFixedHeight(38)
        btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:8px;font-weight:bold;font-size:14px;")
        btn.clicked.connect(self._calculate)
        ll.addWidget(btn)
        ll.addSpacing(8)
        self._gross_card = StatCard("Brüt Gelir", "₺0", TEAL)
        self._tax_card   = StatCard("Toplam Vergi", "₺0", RED)
        self._net_card   = StatCard("Net Gelir", "₺0", GREEN)
        self._eff_card   = StatCard("Efektif Oran", "0%", ORANGE)
        for c in (self._gross_card, self._tax_card, self._net_card, self._eff_card):
            ll.addWidget(c)
        ll.addStretch()
        body.addWidget(left)

        # Right — bracket table + chart
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)
        rl.addWidget(QLabel("Vergi Dilimleri", styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Dilim (₺)","Oran","Vergi (₺)"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setMaximumHeight(220)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        rl.addWidget(self._table)
        self._chart = BarChart()
        rl.addWidget(self._chart, 1)
        body.addWidget(right, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)
        self._income.valueChanged.connect(self._calculate)

    def _calculate(self):
        res = tr_income_tax(self._income.value())
        self._gross_card.update_value(f"₺{res['gross']:,.0f}")
        self._tax_card.update_value(f"₺{res['tax']:,.0f}")
        self._net_card.update_value(f"₺{res['net']:,.0f}")
        eff = res["tax"] / res["gross"] * 100 if res["gross"] else 0
        self._eff_card.update_value(f"%{eff:.1f}")

        self._table.setRowCount(0)
        colors = ["#4CAF50","#8BC34A","#CDDC39","#FFC107","#FF9800","#FF5722","#F44336","#D32F2F"]
        bars = []
        for i, d in enumerate(res["detail"]):
            r = self._table.rowCount(); self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(d["bracket"]))
            self._table.setItem(r, 1, QTableWidgetItem(f"%{d['rate']*100:.0f}"))
            self._table.setItem(r, 2, QTableWidgetItem(f"₺{d['tax']:,.0f}"))
            if d["tax"] > 0:
                bars.append((f"%{d['rate']*100:.0f}", d["tax"], colors[i % len(colors)]))
        self._chart.set_data(bars, "Dilim Başına Vergi", "₺")
