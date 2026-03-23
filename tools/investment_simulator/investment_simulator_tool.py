"""Investment Simulator — compound growth with contributions."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from tools.finance_service.finance_service import future_value
from tools.finance_service.finance_base import make_header, MiniChart, StatCard, TEAL, ORANGE, GREEN, RED, CARD


class InvestmentSimulatorTool(QWidget):
    name = "Investment Simulator"
    description = "Bileşik faiz büyüme simülatörü"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._simulate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("📊 Yatırım Simülatörü")
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        left = QFrame()
        left.setFixedWidth(290)
        left.setStyleSheet(f"QFrame{{background:{CARD};border-radius:10px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 20, 20, 20)
        ll.setSpacing(12)

        def spin(label, val, mn, mx, step=None, suffix=""):
            ll.addWidget(QLabel(label, styleSheet="color:#888;font-size:11px;"))
            s = QDoubleSpinBox()
            s.setRange(mn, mx)
            s.setValue(val)
            if step: s.setSingleStep(step)
            if suffix: s.setSuffix(suffix)
            s.setDecimals(2)
            s.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:8px;font-size:13px;color:#E0E0E0;")
            ll.addWidget(s)
            return s

        self._initial  = spin("Başlangıç Yatırımı (₺)", 10_000, 0, 99_999_999, 1000)
        self._monthly  = spin("Aylık Katkı (₺)", 1_000, 0, 999_999, 100)
        self._rate     = spin("Yıllık Getiri (%)", 15, 0, 200, 0.5, "%")
        ll.addWidget(QLabel("Süre (Yıl)", styleSheet="color:#888;font-size:11px;"))
        self._years = QSpinBox()
        self._years.setRange(1, 50)
        self._years.setValue(10)
        self._years.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:8px;font-size:13px;color:#E0E0E0;")
        ll.addWidget(self._years)

        btn = QPushButton("Simüle Et")
        btn.setFixedHeight(38)
        btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:8px;font-weight:bold;font-size:14px;")
        btn.clicked.connect(self._simulate)
        ll.addWidget(btn)
        ll.addSpacing(8)

        self._fv_card     = StatCard("Gelecek Değer", "₺0", TEAL)
        self._contrib_card= StatCard("Toplam Katkı", "₺0", ORANGE)
        self._profit_card = StatCard("Yatırım Kazancı", "₺0", GREEN)
        for c in (self._fv_card, self._contrib_card, self._profit_card):
            ll.addWidget(c)
        ll.addStretch()
        body.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        self._chart = MiniChart()
        self._chart.setMinimumHeight(220)
        rl.addWidget(self._chart, 2)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Yıl","Toplam Değer","Katkılar","Kazanç"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setMaximumHeight(200)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:11px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        rl.addWidget(self._table, 1)
        body.addWidget(right, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)
        for spin in (self._initial, self._monthly, self._rate, self._years):
            if hasattr(spin, "valueChanged"): spin.valueChanged.connect(self._simulate)

    def _simulate(self):
        initial  = self._initial.value()
        monthly  = self._monthly.value()
        rate     = self._rate.value()
        years    = self._years.value()
        total_contrib = initial + monthly * 12 * years
        fv = future_value(initial, rate, years, monthly)
        profit = fv - total_contrib

        self._fv_card.update_value(f"₺{fv:,.0f}")
        self._contrib_card.update_value(f"₺{total_contrib:,.0f}")
        self._profit_card.update_value(f"₺{profit:,.0f}")

        labels = []; vals_total = []; vals_contrib = []
        self._table.setRowCount(0)
        for y in range(1, years + 1):
            fvy  = future_value(initial, rate, y, monthly)
            cont = initial + monthly * 12 * y
            gain = fvy - cont
            labels.append(str(y))
            vals_total.append(fvy)
            vals_contrib.append(cont)
            r = self._table.rowCount(); self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(f"Yıl {y}"))
            self._table.setItem(r, 1, QTableWidgetItem(f"₺{fvy:,.0f}"))
            self._table.setItem(r, 2, QTableWidgetItem(f"₺{cont:,.0f}"))
            self._table.setItem(r, 3, QTableWidgetItem(f"₺{gain:,.0f}"))

        self._chart.set_data(
            [(TEAL, vals_total), (ORANGE, vals_contrib)],
            labels, "Büyüme (Teal) vs Katkı (Turuncu)", "₺")
