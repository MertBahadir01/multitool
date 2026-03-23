"""Debt Tracker — track loans, remaining balance, payoff timeline."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QLineEdit, QProgressBar
)
from PySide6.QtCore import Qt
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import DebtService
from tools.finance_service.finance_base import make_header, StatCard, TEAL, ORANGE, RED, GREEN, CARD


class DebtTrackerTool(QWidget):
    name = "Debt Tracker"
    description = "Borç takibi — kalan bakiye ve geri ödeme süresi"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = DebtService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("💳 Borç Takibi")
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        stats = QHBoxLayout()
        self._total_card   = StatCard("Toplam Borç", "₺0", RED)
        self._monthly_card = StatCard("Aylık Ödeme", "₺0", ORANGE)
        self._count_card   = StatCard("Aktif Borç", "0", TEAL)
        for c in (self._total_card, self._monthly_card, self._count_card):
            stats.addWidget(c)
        body.addLayout(stats)

        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(8)
        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"
        self._name_inp = QLineEdit(); self._name_inp.setPlaceholderText("Borç adı…"); self._name_inp.setStyleSheet(inp)
        self._prin_spin = QDoubleSpinBox(); self._prin_spin.setRange(1, 99_999_999); self._prin_spin.setDecimals(2); self._prin_spin.setPrefix("₺ "); self._prin_spin.setStyleSheet(inp); self._prin_spin.setToolTip("Toplam borç")
        self._rem_spin  = QDoubleSpinBox(); self._rem_spin.setRange(0, 99_999_999);  self._rem_spin.setDecimals(2); self._rem_spin.setPrefix("Kalan: ₺"); self._rem_spin.setStyleSheet(inp)
        self._rate_spin = QDoubleSpinBox(); self._rate_spin.setRange(0, 200); self._rate_spin.setDecimals(2); self._rate_spin.setSuffix("% yıllık"); self._rate_spin.setStyleSheet(inp)
        self._pmt_spin  = QDoubleSpinBox(); self._pmt_spin.setRange(0, 999_999); self._pmt_spin.setDecimals(2); self._pmt_spin.setPrefix("Aylık: ₺"); self._pmt_spin.setStyleSheet(inp)
        add_btn = QPushButton("➕ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        add_btn.clicked.connect(self._add)
        for w in (self._name_inp, self._prin_spin, self._rem_spin, self._rate_spin, self._pmt_spin, add_btn):
            fl.addWidget(w)
        body.addWidget(form)

        # Debt cards
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._debt_widget = QWidget()
        self._debt_lay = QVBoxLayout(self._debt_widget)
        self._debt_lay.setContentsMargins(0, 0, 0, 0)
        self._debt_lay.setSpacing(10)
        scroll.setWidget(self._debt_widget)
        body.addWidget(scroll, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _add(self):
        if not self._svc or not self._name_inp.text().strip(): return
        prin = self._prin_spin.value()
        self._svc.add(
            name=self._name_inp.text().strip(),
            principal=prin,
            interest_rate=self._rate_spin.value(),
            remaining=self._rem_spin.value() or prin,
            monthly_payment=self._pmt_spin.value()
        )
        self._name_inp.clear()
        self._refresh()

    def _refresh(self):
        if not self._svc: return
        while self._debt_lay.count():
            item = self._debt_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        debts = self._svc.get_all()
        total = sum(d["remaining"] for d in debts)
        monthly = sum(d["monthly_payment"] for d in debts)
        self._total_card.update_value(f"₺{total:,.0f}")
        self._monthly_card.update_value(f"₺{monthly:,.0f}")
        self._count_card.update_value(str(len(debts)))

        for d in debts:
            pct = int((1 - d["remaining"] / d["principal"]) * 100) if d["principal"] else 0
            months_left = int(d["remaining"] / d["monthly_payment"]) if d["monthly_payment"] > 0 else 0

            card = QFrame()
            card.setStyleSheet(f"QFrame{{background:{CARD};border-left:3px solid {RED};border-radius:8px;}}"
                               "QLabel{{border:none;background:transparent;}}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(6)

            top = QHBoxLayout()
            top.addWidget(QLabel(d["name"], styleSheet="color:#E0E0E0;font-weight:bold;font-size:13px;"))
            top.addStretch()
            top.addWidget(QLabel(f"Kalan: ₺{d['remaining']:,.0f}  |  {months_left} ay",
                                 styleSheet=f"color:{ORANGE};font-size:11px;"))
            del_btn = QPushButton("🗑"); del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("background:#3A3A3A;border:none;border-radius:4px;color:#888;")
            del_btn.clicked.connect(lambda _, did=d["id"]: (self._svc.delete(did), self._refresh()))
            top.addWidget(del_btn)
            cl.addLayout(top)

            bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedHeight(10)
            bar.setStyleSheet(f"QProgressBar{{background:#252525;border-radius:5px;border:none;}}"
                              f"QProgressBar::chunk{{background:{GREEN};border-radius:5px;}}")
            cl.addWidget(bar)

            upd_lay = QHBoxLayout()
            upd_spin = QDoubleSpinBox(); upd_spin.setRange(0, 99_999_999); upd_spin.setDecimals(2)
            upd_spin.setValue(d["remaining"]); upd_spin.setPrefix("Kalan: ₺")
            upd_spin.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:4px;padding:4px;color:#E0E0E0;max-width:160px;")
            upd_btn = QPushButton("Güncelle"); upd_btn.setFixedHeight(28)
            upd_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:4px;padding:0 10px;")
            upd_btn.clicked.connect(lambda _, did=d["id"], sp=upd_spin: (self._svc.update_remaining(did, sp.value()), self._refresh()))
            upd_lay.addWidget(upd_spin); upd_lay.addWidget(upd_btn); upd_lay.addStretch()
            cl.addLayout(upd_lay)
            self._debt_lay.addWidget(card)

        self._debt_lay.addStretch()
