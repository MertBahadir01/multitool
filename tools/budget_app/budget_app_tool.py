"""
budget_app_tool.py — Budget limits per category with remaining indicator.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QDoubleSpinBox, QProgressBar, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import BudgetService, TransactionService
from tools.finance_service.finance_base import (
    make_header, StatCard, TEAL, ORANGE, RED, GREEN, CARD, PALETTE
)

CATEGORIES = ["Yiyecek","Ulaşım","Faturalar","Kira","Sağlık","Eğlence",
              "Giyim","Eğitim","Alışveriş","Diğer"]


class BudgetAppTool(QWidget):
    name = "Budget App"
    description = "Kategori bütçesi belirle, kalan limiti takip et"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc_b = BudgetService(u["id"]) if u else None
        self._svc_t = TransactionService(u["id"]) if u else None
        self._build_ui()
        if self._svc_b: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("📊 Bütçe Yönetimi")
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(16)

        # Add budget form
        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{border:none;background:transparent;}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(10)
        fl.addWidget(QLabel("Kategori:"))
        self._cat_cb = QComboBox()
        self._cat_cb.addItems(CATEGORIES)
        self._cat_cb.setEditable(True)
        self._cat_cb.setStyleSheet(self._inp())
        fl.addWidget(self._cat_cb)
        fl.addWidget(QLabel("Limit (₺):"))
        self._amt = QDoubleSpinBox()
        self._amt.setRange(1, 9_999_999)
        self._amt.setDecimals(2)
        self._amt.setValue(1000)
        self._amt.setStyleSheet(self._inp())
        fl.addWidget(self._amt)
        add_btn = QPushButton("💾 Kaydet")
        add_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 16px;height:34px;")
        add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self._save)
        fl.addWidget(add_btn)
        fl.addStretch()
        body.addWidget(form)

        # Budget bars
        self._scroll_area = QWidget()
        self._bars_lay = QVBoxLayout(self._scroll_area)
        self._bars_lay.setContentsMargins(0, 0, 0, 0)
        self._bars_lay.setSpacing(10)
        body.addWidget(self._scroll_area, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _inp(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:6px;font-size:13px;color:#E0E0E0;")

    def _save(self):
        if not self._svc_b: return
        self._svc_b.set_budget(self._cat_cb.currentText(), self._amt.value())
        self._refresh()

    def _refresh(self):
        if not self._svc_b: return
        # Clear existing bars
        while self._bars_lay.count():
            item = self._bars_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        budgets = self._svc_b.get_budgets()
        if not budgets:
            self._bars_lay.addWidget(QLabel("Henüz bütçe tanımlanmadı.",
                                            styleSheet="color:#555;"))
            return

        import datetime
        ym = datetime.date.today().strftime("%Y-%m")
        spent_map = {}
        if self._svc_t:
            totals = self._svc_t.totals_by_category("expense",
                                                     from_date=ym+"-01")
            spent_map = totals

        for b in budgets:
            cat   = b["category"]
            limit = b["amount"]
            spent = spent_map.get(cat, 0)
            pct   = min(int(spent / limit * 100), 100) if limit else 0
            remaining = limit - spent

            row = QFrame()
            row.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                              "QLabel{border:none;background:transparent;}")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(16, 12, 16, 12)
            rl.setSpacing(6)

            top = QHBoxLayout()
            top.addWidget(QLabel(cat, styleSheet="color:#E0E0E0;font-weight:bold;font-size:13px;"))
            top.addStretch()
            color = GREEN if pct < 70 else (ORANGE if pct < 90 else RED)
            top.addWidget(QLabel(f"₺{spent:,.0f} / ₺{limit:,.0f}",
                                 styleSheet=f"color:{color};font-size:12px;"))
            rl.addLayout(top)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(pct)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            bar.setStyleSheet(f"""
                QProgressBar{{background:#252525;border-radius:5px;border:none;}}
                QProgressBar::chunk{{background:{color};border-radius:5px;}}
            """)
            rl.addWidget(bar)
            rl.addWidget(QLabel(f"Kalan: ₺{remaining:,.2f}  ({100-pct}%)",
                                styleSheet="color:#666;font-size:11px;"))

            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("background:#3A3A3A;border:none;border-radius:4px;color:#888;")
            del_btn.clicked.connect(lambda _, bid=b["id"]: self._delete(bid))
            top.addWidget(del_btn)

            self._bars_lay.addWidget(row)
        self._bars_lay.addStretch()

    def _delete(self, bid):
        if self._svc_b:
            self._svc_b.delete_budget(bid)
            self._refresh()
