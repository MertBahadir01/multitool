"""Subscription Tracker — recurring payments, monthly cost summary."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QLineEdit, QComboBox, QDateEdit
)
from PySide6.QtCore import Qt, QDate
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import SubscriptionService
from tools.finance_service.finance_base import make_header, StatCard, TEAL, ORANGE, RED, CARD


class SubscriptionTrackerTool(QWidget):
    name = "Subscription Tracker"
    description = "Abonelik giderlerini takip et, aylık toplam"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = SubscriptionService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🔔 Abonelik Takibi")
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        # Stat cards
        cards = QHBoxLayout()
        self._monthly_card = StatCard("Aylık Toplam", "₺0", RED)
        self._yearly_card  = StatCard("Yıllık Toplam", "₺0", ORANGE)
        self._count_card   = StatCard("Aktif Abonelik", "0", TEAL)
        for c in (self._monthly_card, self._yearly_card, self._count_card):
            cards.addWidget(c)
        body.addLayout(cards)

        # Form
        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(8)

        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"
        self._name_inp = QLineEdit(); self._name_inp.setPlaceholderText("Abonelik adı…"); self._name_inp.setStyleSheet(inp)
        self._amt      = QDoubleSpinBox(); self._amt.setRange(0.01, 99999); self._amt.setDecimals(2); self._amt.setPrefix("₺ "); self._amt.setStyleSheet(inp); self._amt.setMinimumWidth(110)
        self._cycle_cb = QComboBox(); self._cycle_cb.addItems(["monthly","yearly","weekly"]); self._cycle_cb.setStyleSheet(inp)
        self._due      = QDateEdit(QDate.currentDate().addDays(30)); self._due.setCalendarPopup(True); self._due.setStyleSheet(inp)

        add_btn = QPushButton("➕ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        add_btn.clicked.connect(self._add)

        for w in (self._name_inp, self._amt, self._cycle_cb, self._due, add_btn):
            fl.addWidget(w)
        fl.addStretch()
        body.addWidget(form)

        # Table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Abonelik","Tutar","Dönem","Aylık Karş.","Son Ödeme"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        del_btn = QPushButton("🗑 Seçili Sil")
        del_btn.setStyleSheet("background:#B71C1C;color:#fff;border:none;border-radius:6px;padding:6px 14px;")
        del_btn.clicked.connect(self._delete)
        body.addWidget(self._table, 1)
        body.addWidget(del_btn, 0, Qt.AlignRight)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _add(self):
        if not self._svc or not self._name_inp.text().strip(): return
        self._svc.add(
            name=self._name_inp.text().strip(),
            amount=self._amt.value(),
            billing_cycle=self._cycle_cb.currentText(),
            next_due=self._due.date().toString("yyyy-MM-dd")
        )
        self._name_inp.clear()
        self._refresh()

    def _delete(self):
        if not self._svc: return
        row = self._table.currentRow()
        if row < 0: return
        item = self._table.item(row, 0)
        if item and item.data(Qt.UserRole):
            self._svc.delete(item.data(Qt.UserRole))
            self._refresh()

    def _refresh(self):
        if not self._svc: return
        subs = self._svc.get_all()
        monthly = self._svc.monthly_cost()
        self._monthly_card.update_value(f"₺{monthly:,.2f}")
        self._yearly_card.update_value(f"₺{monthly*12:,.2f}")
        self._count_card.update_value(str(len(subs)))

        self._table.setRowCount(0)
        for s in subs:
            r = self._table.rowCount()
            self._table.insertRow(r)
            name_item = QTableWidgetItem(s["name"])
            name_item.setData(Qt.UserRole, s["id"])
            self._table.setItem(r, 0, name_item)
            self._table.setItem(r, 1, QTableWidgetItem(f"₺{s['amount']:,.2f}"))
            cycle_map = {"monthly":"Aylık","yearly":"Yıllık","weekly":"Haftalık"}
            self._table.setItem(r, 2, QTableWidgetItem(cycle_map.get(s["billing_cycle"], s["billing_cycle"])))
            # Monthly equivalent
            mc = s["amount"] if s["billing_cycle"]=="monthly" else (s["amount"]/12 if s["billing_cycle"]=="yearly" else s["amount"]*4.33)
            self._table.setItem(r, 3, QTableWidgetItem(f"₺{mc:,.2f}"))
            self._table.setItem(r, 4, QTableWidgetItem(s["next_due"]))
