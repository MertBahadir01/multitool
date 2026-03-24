"""Expense Tracker — add/delete transactions, category totals, monthly chart."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QDoubleSpinBox, QLineEdit, QDateEdit, QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import TransactionService
from tools.finance_service.finance_base import (
    make_header, BarChart, StatCard, TEAL, ORANGE, RED, GREEN, BG, CARD, PALETTE
)

CATEGORIES = ["Food","Transport","Bills","Rent","Health","Entertainment",
              "Clothing","Education","Shopping","Other"]


class ExpenseTrackerTool(QWidget):
    name = "Expense Tracker"
    description = "Track expenses, categorize, view totals"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = auth_manager.current_user
        self._svc  = TransactionService(self._user["id"]) if self._user else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("💸 Harcama Takibi")
        root.addWidget(hdr)

        body = QSplitter(Qt.Horizontal)
        body.setHandleWidth(2)
        body.setStyleSheet("QSplitter::handle{background:#2A2A2A;}")

        # LEFT — add form + table
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.setSpacing(12)

        # Stat cards
        stats = QHBoxLayout()
        self._total_card  = StatCard("Total This Month", "₺0", RED)
        self._income_card = StatCard("Income", "₺0", GREEN)
        self._net_card    = StatCard("Net", "₺0", TEAL)
        for c in (self._total_card, self._income_card, self._net_card):
            stats.addWidget(c)
        ll.addLayout(stats)

        # Add form
        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{border:none;background:transparent;}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(8)

        self._amt_spin = QDoubleSpinBox()
        self._amt_spin.setRange(0.01, 9_999_999)
        self._amt_spin.setDecimals(2)
        self._amt_spin.setPrefix("₺ ")
        self._amt_spin.setStyleSheet(self._inp_style())
        self._amt_spin.setMinimumWidth(120)

        self._cat_cb = QComboBox()
        self._cat_cb.addItems(CATEGORIES)
        self._cat_cb.setEditable(True)
        self._cat_cb.setStyleSheet(self._inp_style())

        self._type_cb = QComboBox()
        self._type_cb.addItems(["expense", "income"])
        self._type_cb.setStyleSheet(self._inp_style())

        self._note_inp = QLineEdit()
        self._note_inp.setPlaceholderText("Not (isteğe bağlı)…")
        self._note_inp.setStyleSheet(self._inp_style())

        self._date_inp = QDateEdit(QDate.currentDate())
        self._date_inp.setCalendarPopup(True)
        self._date_inp.setStyleSheet(self._inp_style())

        add_btn = QPushButton("➕ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(
            f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        add_btn.clicked.connect(self._add)

        for w in (self._amt_spin, self._cat_cb, self._type_cb,
                  self._note_inp, self._date_inp, add_btn):
            fl.addWidget(w)
        ll.addWidget(form)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Date","Type","Category","Amount","Note"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        del_btn = QPushButton("🗑 Seçili Sil")
        del_btn.setStyleSheet("background:#B71C1C;color:#fff;border:none;border-radius:6px;padding:6px 14px;")
        del_btn.clicked.connect(self._delete)
        ll.addWidget(self._table, 1)
        ll.addWidget(del_btn, 0, Qt.AlignRight)
        body.addWidget(left)

        # RIGHT — charts
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(12)
        rl.addWidget(QLabel("Kategori Bazlı Harcamalar",
                            styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        self._cat_chart = BarChart()
        rl.addWidget(self._cat_chart, 1)
        rl.addWidget(QLabel("Aylık Trend",
                            styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        from tools.finance_service.finance_base import MiniChart
        self._monthly_chart = MiniChart()
        rl.addWidget(self._monthly_chart, 1)
        body.addWidget(right)

        body.setSizes([600, 400])
        root.addWidget(body, 1)

    def _inp_style(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:6px;font-size:12px;color:#E0E0E0;")

    def _add(self):
        if not self._svc: return
        self._svc.add(
            amount=self._amt_spin.value(),
            category=self._cat_cb.currentText(),
            note=self._note_inp.text(),
            tx_type=self._type_cb.currentText(),
            tx_date=self._date_inp.date().toString("yyyy-MM-dd")
        )
        self._note_inp.clear()
        self._refresh()

    def _delete(self):
        if not self._svc: return
        row = self._table.currentRow()
        if row < 0: return
        tx_id = self._table.item(row, 0)
        if tx_id and tx_id.data(Qt.UserRole):
            self._svc.delete(tx_id.data(Qt.UserRole))
            self._refresh()

    def _refresh(self):
        if not self._svc: return
        txs = self._svc.get_all()
        self._table.setRowCount(0)
        for tx in txs:
            r = self._table.rowCount()
            self._table.insertRow(r)
            date_item = QTableWidgetItem(tx["tx_date"])
            date_item.setData(Qt.UserRole, tx["id"])
            self._table.setItem(r, 0, date_item)
            typ = QTableWidgetItem(tx["tx_type"])
            typ.setForeground(QColor(GREEN if tx["tx_type"] == "income" else RED))
            self._table.setItem(r, 1, typ)
            self._table.setItem(r, 2, QTableWidgetItem(tx["category"]))
            amt = QTableWidgetItem(f"₺ {tx['amount']:,.2f}")
            amt.setForeground(QColor(GREEN if tx["tx_type"] == "income" else RED))
            self._table.setItem(r, 3, amt)
            self._table.setItem(r, 4, QTableWidgetItem(tx.get("note","")))

        # Stats
        import datetime
        ym = datetime.date.today().strftime("%Y-%m")
        month_txs = [t for t in txs if str(t["tx_date"]).startswith(ym)]
        expenses = sum(t["amount"] for t in month_txs if t["tx_type"] == "expense")
        income   = sum(t["amount"] for t in month_txs if t["tx_type"] == "income")
        self._total_card.update_value(f"₺{expenses:,.0f}")
        self._income_card.update_value(f"₺{income:,.0f}")
        self._net_card.update_value(f"₺{income-expenses:,.0f}")

        # Category chart
        totals = self._svc.totals_by_category("expense")
        bar_data = [(k, v, PALETTE[i % len(PALETTE)])
                    for i, (k, v) in enumerate(sorted(totals.items(), key=lambda x: -x[1])[:8])]
        self._cat_chart.set_data(bar_data, "Kategori Harcamaları", "₺")

        # Monthly chart
        monthly = self._svc.monthly_totals("expense")
        if monthly:
            labels = [m["month"][5:] for m in monthly]
            vals   = [m["total"] for m in monthly]
            from tools.finance_service.finance_base import ORANGE
            self._monthly_chart.set_data([(ORANGE, vals)], labels, "Aylık Harcama", "₺")
