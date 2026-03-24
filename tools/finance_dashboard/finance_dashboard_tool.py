"""Finance Dashboard — combined overview of all finance data."""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import (
    TransactionService, BudgetService, SavingsService,
    SubscriptionService, DebtService
)
from tools.finance_service.finance_base import (
    make_header, MiniChart, BarChart, StatCard, fetch_async,
    TEAL, ORANGE, GREEN, RED, CARD, BG
)


class FinanceDashboardTool(QWidget):
    name = "Finance Dashboard"
    description = "Central overview of all your finances"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._uid = u["id"] if u else None
        self._tx_svc   = TransactionService(self._uid) if self._uid else None
        self._bud_svc  = BudgetService(self._uid) if self._uid else None
        self._sav_svc  = SavingsService(self._uid) if self._uid else None
        self._sub_svc  = SubscriptionService(self._uid) if self._uid else None
        self._debt_svc = DebtService(self._uid) if self._uid else None
        self._build_ui()
        if self._uid: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("🏠 Finansal Gösterge Paneli")
        refresh_btn = QPushButton("🔄 Yenile")
        refresh_btn.setFixedHeight(32)
        refresh_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        refresh_btn.clicked.connect(self._refresh)
        hl.addWidget(refresh_btn)
        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        content = QWidget()
        content.setStyleSheet(f"background:{BG};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(20, 20, 20, 20)
        cl.setSpacing(20)

        # ── Row 1: KPI cards ──────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        self._income_card  = StatCard("Income This Month",  "₺0", GREEN)
        self._expense_card = StatCard("Expenses This Month",  "₺0", RED)
        self._net_card     = StatCard("Net",           "₺0", TEAL)
        self._sub_card     = StatCard("Aylık Abonelik","₺0", ORANGE)
        self._debt_card    = StatCard("Toplam Borç",   "₺0", RED)
        self._sav_card     = StatCard("Toplam Birikim","₺0", GREEN)
        for c in (self._income_card, self._expense_card, self._net_card,
                  self._sub_card, self._debt_card, self._sav_card):
            kpi_row.addWidget(c)
        cl.addLayout(kpi_row)

        # ── Row 2: Charts ─────────────────────────────────────────────────────
        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        self._cashflow_chart = MiniChart()
        self._cashflow_chart.setMinimumHeight(200)
        cfl = QVBoxLayout()
        cfl.addWidget(QLabel("Aylık Nakit Akışı", styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        cfl.addWidget(self._cashflow_chart, 1)
        charts_row.addLayout(cfl, 2)

        self._cat_chart = BarChart()
        self._cat_chart.setMinimumHeight(200)
        catl = QVBoxLayout()
        catl.addWidget(QLabel("Harcama Dağılımı", styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        catl.addWidget(self._cat_chart, 1)
        charts_row.addLayout(catl, 1)
        cl.addLayout(charts_row)

        # ── Row 3: Budget overview ────────────────────────────────────────────
        self._budget_frame = QFrame()
        self._budget_frame.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                                          "QLabel{{border:none;background:transparent;}}")
        self._budget_lay = QVBoxLayout(self._budget_frame)
        self._budget_lay.setContentsMargins(16, 14, 16, 14)
        self._budget_lay.setSpacing(8)
        self._budget_lay.addWidget(QLabel("Bütçe Durumu",
                                          styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        cl.addWidget(self._budget_frame)

        # ── Row 4: Savings overview ────────────────────────────────────────────
        self._savings_frame = QFrame()
        self._savings_frame.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                                           "QLabel{{border:none;background:transparent;}}")
        self._savings_lay = QVBoxLayout(self._savings_frame)
        self._savings_lay.setContentsMargins(16, 14, 16, 14)
        self._savings_lay.setSpacing(8)
        self._savings_lay.addWidget(QLabel("Birikim Hedefleri",
                                           styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        cl.addWidget(self._savings_frame)

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _refresh(self):
        if not self._uid: return

        today = datetime.date.today()
        ym = today.strftime("%Y-%m")

        # ── KPI cards ─────────────────────────────────────────────────────────
        if self._tx_svc:
            income  = sum(t["amount"] for t in self._tx_svc.get_all("income",  from_date=ym+"-01"))
            expense = sum(t["amount"] for t in self._tx_svc.get_all("expense", from_date=ym+"-01"))
            self._income_card.update_value(f"₺{income:,.0f}")
            self._expense_card.update_value(f"₺{expense:,.0f}")
            self._net_card.update_value(f"₺{income - expense:,.0f}")

        if self._sub_svc:
            self._sub_card.update_value(f"₺{self._sub_svc.monthly_cost():,.0f}")

        if self._debt_svc:
            debt = sum(d["remaining"] for d in self._debt_svc.get_all())
            self._debt_card.update_value(f"₺{debt:,.0f}")

        if self._sav_svc:
            saved = sum(g["saved"] for g in self._sav_svc.get_goals())
            self._sav_card.update_value(f"₺{saved:,.0f}")

        # ── Cash flow chart ───────────────────────────────────────────────────
        if self._tx_svc:
            inc_m = {m["month"]: m["total"] for m in self._tx_svc.monthly_totals("income")}
            exp_m = {m["month"]: m["total"] for m in self._tx_svc.monthly_totals("expense")}
            months = sorted(set(list(inc_m) + list(exp_m)))[-12:]
            labels = [m[5:] for m in months]
            inc_v  = [inc_m.get(m, 0) for m in months]
            exp_v  = [exp_m.get(m, 0) for m in months]
            net_v  = [inc_m.get(m, 0) - exp_m.get(m, 0) for m in months]
            self._cashflow_chart.set_data(
                [(GREEN, inc_v), (RED, exp_v), (TEAL, net_v)],
                labels, "Gelir / Gider / Net", "₺")

            totals = self._tx_svc.totals_by_category("expense")
            from tools.finance_service.finance_base import PALETTE
            bar_data = [(k, v, PALETTE[i % len(PALETTE)])
                        for i, (k, v) in enumerate(sorted(totals.items(), key=lambda x: -x[1])[:6])]
            self._cat_chart.set_data(bar_data, "Kategori Dağılımı", "₺")

        # ── Budget rows ───────────────────────────────────────────────────────
        while self._budget_lay.count() > 1:
            item = self._budget_lay.takeAt(1)
            if item.widget(): item.widget().deleteLater()

        if self._bud_svc:
            from PySide6.QtWidgets import QProgressBar
            spent_map = self._tx_svc.totals_by_category("expense", from_date=ym+"-01") if self._tx_svc else {}
            for b in self._bud_svc.get_budgets()[:5]:
                pct   = min(int(spent_map.get(b["category"], 0) / b["amount"] * 100), 100) if b["amount"] else 0
                color = GREEN if pct < 70 else (ORANGE if pct < 90 else RED)
                row = QHBoxLayout()
                row.addWidget(QLabel(b["category"], styleSheet="color:#E0E0E0;font-size:12px;"))
                bar = QProgressBar(); bar.setRange(0,100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedHeight(8)
                bar.setStyleSheet(f"QProgressBar{{background:#252525;border-radius:4px;border:none;}}"
                                  f"QProgressBar::chunk{{background:{color};border-radius:4px;}}")
                row.addWidget(bar, 1)
                row.addWidget(QLabel(f"₺{spent_map.get(b['category'],0):,.0f} / ₺{b['amount']:,.0f}",
                                     styleSheet=f"color:{color};font-size:11px;"))
                self._budget_lay.addLayout(row)

        # ── Savings rows ──────────────────────────────────────────────────────
        while self._savings_lay.count() > 1:
            item = self._savings_lay.takeAt(1)
            if item.widget(): item.widget().deleteLater()

        if self._sav_svc:
            from PySide6.QtWidgets import QProgressBar
            for g in self._sav_svc.get_goals()[:5]:
                pct   = min(int(g["saved"] / g["target"] * 100), 100) if g["target"] else 0
                color = GREEN if pct >= 100 else (TEAL if pct >= 50 else ORANGE)
                row = QHBoxLayout()
                row.addWidget(QLabel(g["name"], styleSheet="color:#E0E0E0;font-size:12px;"))
                bar = QProgressBar(); bar.setRange(0,100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedHeight(8)
                bar.setStyleSheet(f"QProgressBar{{background:#252525;border-radius:4px;border:none;}}"
                                  f"QProgressBar::chunk{{background:{color};border-radius:4px;}}")
                row.addWidget(bar, 1)
                row.addWidget(QLabel(f"{pct}%", styleSheet=f"color:{color};font-size:11px;"))
                self._savings_lay.addLayout(row)
