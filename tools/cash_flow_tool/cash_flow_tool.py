"""Cash Flow Tool — income minus expenses over months."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QFont
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import TransactionService
from tools.finance_service.finance_base import make_header, MiniChart, BarChart, StatCard, TEAL, ORANGE, RED, GREEN


class CashFlowTool(QWidget):
    name = "Cash Flow"
    description = "Aylık gelir-gider akışı ve net nakit grafiği"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = TransactionService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("💹 Nakit Akışı")
        btn = QPushButton("🔄 Yenile")
        btn.setFixedHeight(32)
        btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        btn.clicked.connect(self._refresh)
        hl.addWidget(btn)
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(16)

        stats = QHBoxLayout()
        self._inc_card  = StatCard("Toplam Gelir", "₺0", GREEN)
        self._exp_card  = StatCard("Toplam Gider", "₺0", RED)
        self._net_card  = StatCard("Net Nakit Akışı", "₺0", TEAL)
        for c in (self._inc_card, self._exp_card, self._net_card):
            stats.addWidget(c)
        body.addLayout(stats)

        self._chart_line = MiniChart()
        self._chart_line.setMinimumHeight(200)
        body.addWidget(self._chart_line, 1)

        self._chart_bar = BarChart()
        self._chart_bar.setMinimumHeight(180)
        body.addWidget(self._chart_bar, 1)

        w = __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget()
        w.setLayout(body)
        root.addWidget(w, 1)

    def _refresh(self):
        if not self._svc: return
        inc_monthly = self._svc.monthly_totals("income")
        exp_monthly = self._svc.monthly_totals("expense")
        months = sorted(set(m["month"] for m in inc_monthly + exp_monthly))
        inc_map = {m["month"]: m["total"] for m in inc_monthly}
        exp_map = {m["month"]: m["total"] for m in exp_monthly}
        inc_vals = [inc_map.get(m, 0) for m in months]
        exp_vals = [exp_map.get(m, 0) for m in months]
        net_vals = [inc_map.get(m, 0) - exp_map.get(m, 0) for m in months]
        labels   = [m[5:] for m in months]

        self._inc_card.update_value(f"₺{sum(inc_vals):,.0f}")
        self._exp_card.update_value(f"₺{sum(exp_vals):,.0f}")
        self._net_card.update_value(f"₺{sum(net_vals):,.0f}")

        self._chart_line.set_data(
            [(GREEN, inc_vals), (RED, exp_vals), (TEAL, net_vals)],
            labels, "Gelir / Gider / Net (aylık)", "₺")

        bar_data = [(m, net_vals[i], GREEN if net_vals[i] >= 0 else RED)
                    for i, m in enumerate(labels)]
        self._chart_bar.set_data(bar_data, "Aylık Net Nakit Akışı", "₺")
