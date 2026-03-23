"""Bill Reminder — upcoming bills, overdue alerts, paid/unpaid toggle."""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QLineEdit, QDateEdit, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import BillService
from tools.finance_service.finance_base import make_header, StatCard, TEAL, ORANGE, RED, GREEN, CARD


class BillReminderTool(QWidget):
    name = "Bill Reminder"
    description = "Ödeme hatırlatıcı — vadesi yaklaşan ve geciken faturalar"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = BillService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("📅 Fatura Hatırlatıcı")
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        stats = QHBoxLayout()
        self._due_card      = StatCard("Bu Ay Vadeli", "₺0", ORANGE)
        self._overdue_card  = StatCard("Geciken", "₺0", RED)
        self._paid_card     = StatCard("Ödenen", "₺0", GREEN)
        for c in (self._due_card, self._overdue_card, self._paid_card):
            stats.addWidget(c)
        body.addLayout(stats)

        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(8)
        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"
        self._name_inp = QLineEdit(); self._name_inp.setPlaceholderText("Fatura adı…"); self._name_inp.setStyleSheet(inp)
        self._amt_spin = QDoubleSpinBox(); self._amt_spin.setRange(0, 999_999); self._amt_spin.setDecimals(2); self._amt_spin.setPrefix("₺ "); self._amt_spin.setStyleSheet(inp)
        self._due_inp  = QDateEdit(QDate.currentDate().addDays(30)); self._due_inp.setCalendarPopup(True); self._due_inp.setStyleSheet(inp)
        self._recur_cb = QCheckBox("Tekrar eden"); self._recur_cb.setStyleSheet("color:#888;")
        add_btn = QPushButton("➕ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        add_btn.clicked.connect(self._add)
        for w in (self._name_inp, self._amt_spin, self._due_inp, self._recur_cb, add_btn):
            fl.addWidget(w)
        fl.addStretch()
        body.addWidget(form)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Fatura","Tutar","Vade","Durum","Ödendi?","Sil"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        body.addWidget(self._table, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _add(self):
        if not self._svc or not self._name_inp.text().strip(): return
        self._svc.add(
            name=self._name_inp.text().strip(),
            amount=self._amt_spin.value(),
            due_date=self._due_inp.date().toString("yyyy-MM-dd"),
            recurring=self._recur_cb.isChecked()
        )
        self._name_inp.clear()
        self._refresh()

    def _refresh(self):
        if not self._svc: return
        bills = self._svc.get_all()
        today = datetime.date.today()
        ym = today.strftime("%Y-%m")

        due_total = overdue = paid_total = 0
        self._table.setRowCount(0)
        for b in bills:
            due_d = datetime.date.fromisoformat(b["due_date"]) if b["due_date"] else today
            is_overdue = due_d < today and not b["paid"]
            is_due_month = b["due_date"].startswith(ym)

            if b["paid"]:          paid_total += b["amount"]
            elif is_overdue:       overdue    += b["amount"]
            elif is_due_month:     due_total  += b["amount"]

            r = self._table.rowCount(); self._table.insertRow(r)
            ni = QTableWidgetItem(b["name"]); ni.setData(Qt.UserRole, b["id"])
            self._table.setItem(r, 0, ni)
            self._table.setItem(r, 1, QTableWidgetItem(f"₺{b['amount']:,.2f}"))
            self._table.setItem(r, 2, QTableWidgetItem(b["due_date"]))

            status = "✅ Ödendi" if b["paid"] else ("🔴 Gecikti!" if is_overdue else "🟡 Bekliyor")
            si = QTableWidgetItem(status)
            si.setForeground(QColor(GREEN if b["paid"] else (RED if is_overdue else ORANGE)))
            self._table.setItem(r, 3, si)

            paid_chk = QCheckBox()
            paid_chk.setChecked(bool(b["paid"]))
            paid_chk.setStyleSheet("margin-left:10px;")
            paid_chk.toggled.connect(lambda checked, bid=b["id"]: (self._svc.set_paid(bid, checked), self._refresh()))
            self._table.setCellWidget(r, 4, paid_chk)

            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("background:#3A3A3A;border:none;border-radius:4px;color:#888;")
            del_btn.clicked.connect(lambda _, bid=b["id"]: (self._svc.delete(bid), self._refresh()))
            self._table.setCellWidget(r, 5, del_btn)

        self._due_card.update_value(f"₺{due_total:,.0f}")
        self._overdue_card.update_value(f"₺{overdue:,.0f}")
        self._paid_card.update_value(f"₺{paid_total:,.0f}")


from tools.finance_service.finance_base import ORANGE, RED, GREEN  # noqa
