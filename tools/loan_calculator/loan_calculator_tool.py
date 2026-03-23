"""Loan Calculator — monthly payment, full amortization schedule, chart."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from tools.finance_service.finance_service import loan_monthly_payment, loan_schedule
from tools.finance_service.finance_base import (
    make_header, MiniChart, StatCard, TEAL, ORANGE, RED, GREEN, CARD, PALETTE
)


class LoanCalculatorTool(QWidget):
    name = "Loan Calculator"
    description = "Faizli kredi ödemesi ve amortisman planı"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._calculate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🏦 Kredi Hesaplayıcı")
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        # LEFT — inputs + stats
        left = QFrame()
        left.setFixedWidth(300)
        left.setStyleSheet(f"QFrame{{background:{CARD};border-radius:10px;}}"
                           "QLabel{border:none;background:transparent;}")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 20, 20, 20)
        ll.setSpacing(14)

        ll.addWidget(QLabel("💰 Kredi Tutarı (₺)", styleSheet="color:#888;font-size:11px;"))
        self._principal = QDoubleSpinBox()
        self._principal.setRange(1000, 99_999_999)
        self._principal.setDecimals(0)
        self._principal.setValue(100_000)
        self._principal.setSingleStep(5000)
        self._principal.setStyleSheet(self._inp())
        ll.addWidget(self._principal)

        ll.addWidget(QLabel("📈 Yıllık Faiz Oranı (%)", styleSheet="color:#888;font-size:11px;"))
        self._rate = QDoubleSpinBox()
        self._rate.setRange(0, 200)
        self._rate.setDecimals(2)
        self._rate.setValue(36)
        self._rate.setSingleStep(0.5)
        self._rate.setStyleSheet(self._inp())
        ll.addWidget(self._rate)

        ll.addWidget(QLabel("📅 Vade (Ay)", styleSheet="color:#888;font-size:11px;"))
        self._months = QSpinBox()
        self._months.setRange(1, 360)
        self._months.setValue(24)
        self._months.setStyleSheet(self._inp())
        ll.addWidget(self._months)

        calc_btn = QPushButton("Hesapla")
        calc_btn.setFixedHeight(38)
        calc_btn.setStyleSheet(
            f"background:{TEAL};color:#000;border:none;border-radius:8px;font-weight:bold;font-size:14px;")
        calc_btn.clicked.connect(self._calculate)
        ll.addWidget(calc_btn)
        ll.addSpacing(8)

        self._pmt_card  = StatCard("Aylık Ödeme", "₺0", TEAL)
        self._total_card= StatCard("Toplam Ödeme", "₺0", ORANGE)
        self._int_card  = StatCard("Toplam Faiz", "₺0", RED)
        for c in (self._pmt_card, self._total_card, self._int_card):
            ll.addWidget(c)
        ll.addStretch()
        body.addWidget(left)

        # RIGHT — chart + schedule
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(12)

        self._chart = MiniChart()
        self._chart.setMinimumHeight(200)
        rl.addWidget(self._chart, 1)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Ay","Ödeme","Faiz","Anapara","Kalan"])
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Ay","Ödeme (₺)","Faiz (₺)","Anapara (₺)","Kalan (₺)"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setMaximumHeight(280)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:11px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        rl.addWidget(self._table)
        body.addWidget(right, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)
        for spin in (self._principal, self._rate, self._months):
            spin.valueChanged.connect(self._calculate)

    def _inp(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:8px;font-size:14px;color:#E0E0E0;")

    def _calculate(self):
        p = self._principal.value()
        r = self._rate.value()
        m = self._months.value()
        pmt   = loan_monthly_payment(p, r, m)
        total = pmt * m
        interest = total - p
        self._pmt_card.update_value(f"₺{pmt:,.2f}")
        self._total_card.update_value(f"₺{total:,.2f}")
        self._int_card.update_value(f"₺{interest:,.2f}")

        sched = loan_schedule(p, r, m)
        self._table.setRowCount(0)
        for row in sched:
            ri = self._table.rowCount()
            self._table.insertRow(ri)
            for ci, val in enumerate([row["month"], row["payment"],
                                       row["interest"], row["principal"], row["balance"]]):
                item = QTableWidgetItem(str(val) if ci == 0 else f"₺{val:,.2f}")
                if ci == 2: item.setForeground(QColor(RED))
                self._table.setItem(ri, ci, item)

        # Chart: principal vs interest over time
        labels  = [str(s["month"]) for s in sched]
        balances= [s["balance"]   for s in sched]
        cum_int = []
        running = 0
        for s in sched:
            running += s["interest"]
            cum_int.append(round(running, 2))
        self._chart.set_data(
            [(TEAL, balances), (RED, cum_int)],
            labels, "Kalan Borç (teal) vs Birikimli Faiz (kırmızı)", "₺")
