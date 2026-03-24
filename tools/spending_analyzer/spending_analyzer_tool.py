"""Spending Analyzer — group by category, show patterns, top spenders."""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import TransactionService
from tools.finance_service.finance_base import make_header, BarChart, MiniChart, StatCard, TEAL, ORANGE, RED, GREEN, PALETTE, CARD


class SpendingAnalyzerTool(QWidget):
    name = "Spending Analyzer"
    description = "Harcama kalıpları ve kategori bazlı analiz"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = TransactionService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("🔍 Harcama Analizi")
        self._period_cb = QComboBox()
        self._period_cb.addItems(["This Month","Last 3 Months","Last 6 Months","This Year","All"])
        self._period_cb.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;")
        self._period_cb.currentIndexChanged.connect(self._refresh)
        hl.addWidget(self._period_cb)
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(14)

        stats = QHBoxLayout()
        self._total_card = StatCard("Toplam Harcama", "₺0", RED)
        self._avg_card   = StatCard("Aylık Ortalama", "₺0", ORANGE)
        self._top_card   = StatCard("En Yüksek Kategori", "—", TEAL)
        for c in (self._total_card, self._avg_card, self._top_card):
            stats.addWidget(c)
        ll.addLayout(stats)

        self._bar_chart = BarChart()
        self._bar_chart.setMinimumHeight(200)
        ll.addWidget(self._bar_chart, 1)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Category","Amount","Pay (%)"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setMaximumHeight(220)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        ll.addWidget(self._table)
        body.addWidget(left, 2)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self._trend_chart = MiniChart()
        rl.addWidget(self._trend_chart, 1)
        body.addWidget(right, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _date_range(self):
        today = datetime.date.today()
        idx = self._period_cb.currentIndex()
        if idx == 0: return today.strftime("%Y-%m") + "-01", today.isoformat()
        if idx == 1: return (today - datetime.timedelta(days=90)).isoformat(), today.isoformat()
        if idx == 2: return (today - datetime.timedelta(days=180)).isoformat(), today.isoformat()
        if idx == 3: return f"{today.year}-01-01", today.isoformat()
        return "", ""

    def _refresh(self):
        if not self._svc: return
        fd, td = self._date_range()
        totals = self._svc.totals_by_category("expense", from_date=fd, to_date=td)
        if not totals:
            self._total_card.update_value("₺0")
            return

        grand = sum(totals.values())
        sorted_cats = sorted(totals.items(), key=lambda x: -x[1])
        self._total_card.update_value(f"₺{grand:,.0f}")
        months = len(set(t["tx_date"][:7] for t in self._svc.get_all(tx_type="expense", from_date=fd, to_date=td))) or 1
        self._avg_card.update_value(f"₺{grand/months:,.0f}")
        self._top_card.update_value(sorted_cats[0][0] if sorted_cats else "—")

        bars = [(cat, val, PALETTE[i % len(PALETTE)]) for i, (cat, val) in enumerate(sorted_cats[:8])]
        self._bar_chart.set_data(bars, "Kategoriye Göre Harcama", "₺")

        self._table.setRowCount(0)
        for cat, val in sorted_cats:
            r = self._table.rowCount(); self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(cat))
            self._table.setItem(r, 1, QTableWidgetItem(f"₺{val:,.2f}"))
            self._table.setItem(r, 2, QTableWidgetItem(f"%{val/grand*100:.1f}"))

        monthly = self._svc.monthly_totals("expense")
        if monthly:
            labels = [m["month"][5:] for m in monthly]
            vals   = [m["total"] for m in monthly]
            self._trend_chart.set_data([(RED, vals)], labels, "Aylık Trend", "₺")
