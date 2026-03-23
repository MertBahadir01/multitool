"""Savings Tracker — goals, progress bars, timeline estimates."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDoubleSpinBox, QLineEdit, QDateEdit, QProgressBar, QScrollArea
)
from PySide6.QtCore import Qt, QDate
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import SavingsService
from tools.finance_service.finance_base import (
    make_header, StatCard, TEAL, ORANGE, GREEN, RED, CARD
)


class SavingsTrackerTool(QWidget):
    name = "Savings Tracker"
    description = "Birikim hedefi belirle, ilerlemeyi takip et"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = SavingsService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🎯 Birikim Hedefleri")
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        # Form
        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{border:none;background:transparent;}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(16, 12, 16, 12)
        fl.setSpacing(10)

        self._name_inp = QLineEdit(); self._name_inp.setPlaceholderText("Hedef adı…")
        self._target   = QDoubleSpinBox(); self._target.setRange(1, 99_999_999); self._target.setDecimals(2); self._target.setPrefix("₺ ")
        self._saved    = QDoubleSpinBox(); self._saved.setRange(0, 99_999_999);  self._saved.setDecimals(2);  self._saved.setPrefix("₺ ")
        self._monthly  = QDoubleSpinBox(); self._monthly.setRange(0, 999_999);   self._monthly.setDecimals(2); self._monthly.setPrefix("₺ "); self._monthly.setToolTip("Aylık katkı")
        self._deadline = QDateEdit(QDate.currentDate().addYears(1)); self._deadline.setCalendarPopup(True)

        for w in (self._name_inp, self._target, self._saved, self._monthly, self._deadline):
            w.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;")
            fl.addWidget(w)

        add_btn = QPushButton("➕ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        add_btn.clicked.connect(self._add)
        fl.addWidget(add_btn)
        body.addWidget(form)

        # Goals area
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._goals_widget = QWidget()
        self._goals_lay = QVBoxLayout(self._goals_widget)
        self._goals_lay.setContentsMargins(0, 0, 0, 0)
        self._goals_lay.setSpacing(10)
        scroll.setWidget(self._goals_widget)
        body.addWidget(scroll, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _add(self):
        if not self._svc or not self._name_inp.text().strip(): return
        self._svc.add_goal(
            name=self._name_inp.text().strip(),
            target=self._target.value(),
            saved=self._saved.value(),
            deadline=self._deadline.date().toString("yyyy-MM-dd"),
            monthly_add=self._monthly.value()
        )
        self._name_inp.clear()
        self._refresh()

    def _refresh(self):
        if not self._svc: return
        while self._goals_lay.count():
            item = self._goals_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        goals = self._svc.get_goals()
        if not goals:
            self._goals_lay.addWidget(QLabel("Henüz hedef yok.", styleSheet="color:#555;"))
            self._goals_lay.addStretch()
            return

        for g in goals:
            pct = min(int(g["saved"] / g["target"] * 100), 100) if g["target"] else 0
            remaining = g["target"] - g["saved"]
            color = GREEN if pct >= 100 else (TEAL if pct >= 50 else ORANGE)

            # Estimate months
            months_est = ""
            if g["monthly_add"] > 0 and remaining > 0:
                m = int(remaining / g["monthly_add"])
                months_est = f" · Tahminen {m} ay"

            card = QFrame()
            card.setStyleSheet(f"QFrame{{background:{CARD};border-left:3px solid {color};border-radius:8px;}}"
                               "QLabel{border:none;background:transparent;}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(6)

            top = QHBoxLayout()
            top.addWidget(QLabel(g["name"], styleSheet=f"color:#E0E0E0;font-weight:bold;font-size:13px;"))
            top.addStretch()
            top.addWidget(QLabel(f"{pct}%  ·  ₺{g['saved']:,.0f} / ₺{g['target']:,.0f}{months_est}",
                                 styleSheet=f"color:{color};font-size:11px;"))
            cl.addLayout(top)

            bar = QProgressBar()
            bar.setRange(0, 100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedHeight(10)
            bar.setStyleSheet(f"QProgressBar{{background:#252525;border-radius:5px;border:none;}}"
                              f"QProgressBar::chunk{{background:{color};border-radius:5px;}}")
            cl.addWidget(bar)

            # Update saved + delete
            btns = QHBoxLayout()
            upd_spin = QDoubleSpinBox(); upd_spin.setRange(0, 99_999_999); upd_spin.setDecimals(2)
            upd_spin.setValue(g["saved"]); upd_spin.setPrefix("₺ ")
            upd_spin.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:4px;padding:4px;color:#E0E0E0;max-width:130px;")
            upd_btn = QPushButton("Güncelle")
            upd_btn.setFixedHeight(28)
            upd_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:4px;padding:0 10px;")
            upd_btn.clicked.connect(lambda _, gid=g["id"], sp=upd_spin: (self._svc.update_saved(gid, sp.value()), self._refresh()))
            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("background:#3A3A3A;border:none;border-radius:4px;color:#888;")
            del_btn.clicked.connect(lambda _, gid=g["id"]: (self._svc.delete_goal(gid), self._refresh()))
            btns.addWidget(QLabel("Birikmiş:", styleSheet="color:#666;font-size:11px;"))
            btns.addWidget(upd_spin); btns.addWidget(upd_btn); btns.addStretch(); btns.addWidget(del_btn)
            cl.addLayout(btns)
            self._goals_lay.addWidget(card)

        self._goals_lay.addStretch()
