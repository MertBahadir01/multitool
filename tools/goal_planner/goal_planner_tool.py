"""Goal Planner — set financial targets, track contributions, deadline countdown."""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDoubleSpinBox, QLineEdit, QDateEdit, QScrollArea, QProgressBar
)
from PySide6.QtCore import Qt, QDate
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import SavingsService
from tools.finance_service.finance_base import make_header, MiniChart, StatCard, TEAL, ORANGE, GREEN, RED, CARD, future_value


def future_value(present, rate, years, monthly=0):
    from tools.finance_service.finance_service import future_value as fv
    return fv(present, rate, years, monthly)


class GoalPlannerTool(QWidget):
    name = "Goal Planner"
    description = "Finansal hedefler, katkı planı ve geri sayım"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = SavingsService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🎯 Hedef Planlayıcı")
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        stats = QHBoxLayout()
        self._total_card  = StatCard("Toplam Hedef", "₺0", TEAL)
        self._saved_card  = StatCard("Toplam Birikim", "₺0", GREEN)
        self._remain_card = StatCard("Kalan", "₺0", ORANGE)
        for c in (self._total_card, self._saved_card, self._remain_card):
            stats.addWidget(c)
        body.addLayout(stats)

        # Add form
        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(8)
        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"
        self._name_inp  = QLineEdit(); self._name_inp.setPlaceholderText("Hedef adı…"); self._name_inp.setStyleSheet(inp)
        self._target    = QDoubleSpinBox(); self._target.setRange(1, 99_999_999); self._target.setDecimals(2); self._target.setPrefix("₺ "); self._target.setStyleSheet(inp)
        self._saved_sp  = QDoubleSpinBox(); self._saved_sp.setRange(0, 99_999_999); self._saved_sp.setDecimals(2); self._saved_sp.setPrefix("Birikim: ₺"); self._saved_sp.setStyleSheet(inp)
        self._monthly   = QDoubleSpinBox(); self._monthly.setRange(0, 999_999); self._monthly.setDecimals(2); self._monthly.setPrefix("Aylık: ₺"); self._monthly.setStyleSheet(inp)
        self._deadline  = QDateEdit(QDate.currentDate().addYears(2)); self._deadline.setCalendarPopup(True); self._deadline.setStyleSheet(inp)
        add_btn = QPushButton("➕ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        add_btn.clicked.connect(self._add)
        for w in (self._name_inp, self._target, self._saved_sp, self._monthly, self._deadline, add_btn):
            fl.addWidget(w)
        body.addWidget(form)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._goals_w = QWidget()
        self._goals_lay = QVBoxLayout(self._goals_w)
        self._goals_lay.setContentsMargins(0, 0, 0, 0)
        self._goals_lay.setSpacing(10)
        scroll.setWidget(self._goals_w)
        body.addWidget(scroll, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _add(self):
        if not self._svc or not self._name_inp.text().strip(): return
        self._svc.add_goal(
            name=self._name_inp.text().strip(),
            target=self._target.value(),
            saved=self._saved_sp.value(),
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
        total_target = sum(g["target"] for g in goals)
        total_saved  = sum(g["saved"]  for g in goals)
        self._total_card.update_value(f"₺{total_target:,.0f}")
        self._saved_card.update_value(f"₺{total_saved:,.0f}")
        self._remain_card.update_value(f"₺{total_target - total_saved:,.0f}")

        today = datetime.date.today()
        for g in goals:
            pct  = min(int(g["saved"] / g["target"] * 100), 100) if g["target"] else 0
            color = GREEN if pct >= 100 else (TEAL if pct >= 50 else ORANGE)

            # Days remaining
            days_left = ""
            if g.get("deadline"):
                try:
                    dl = datetime.date.fromisoformat(g["deadline"])
                    diff = (dl - today).days
                    days_left = f" · {diff} gün kaldı" if diff >= 0 else " · ⚠️ Geçti!"
                except Exception:
                    pass

            # Projection: will goal be met by deadline?
            projection = ""
            if g["monthly_add"] > 0 and g["target"] > g["saved"]:
                remaining = g["target"] - g["saved"]
                months_needed = int(remaining / g["monthly_add"])
                projection = f" · {months_needed} ay gerekli"

            card = QFrame()
            card.setStyleSheet(f"QFrame{{background:{CARD};border-left:3px solid {color};border-radius:8px;}}"
                               "QLabel{{border:none;background:transparent;}}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(6)

            top = QHBoxLayout()
            top.addWidget(QLabel(g["name"], styleSheet="color:#E0E0E0;font-weight:bold;font-size:13px;"))
            top.addStretch()
            top.addWidget(QLabel(f"{pct}%  ·  ₺{g['saved']:,.0f} / ₺{g['target']:,.0f}{days_left}{projection}",
                                 styleSheet=f"color:{color};font-size:11px;"))
            del_btn = QPushButton("🗑"); del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("background:#3A3A3A;border:none;border-radius:4px;color:#888;")
            del_btn.clicked.connect(lambda _, gid=g["id"]: (self._svc.delete_goal(gid), self._refresh()))
            top.addWidget(del_btn)
            cl.addLayout(top)

            bar = QProgressBar(); bar.setRange(0, 100); bar.setValue(pct); bar.setTextVisible(False); bar.setFixedHeight(10)
            bar.setStyleSheet(f"QProgressBar{{background:#252525;border-radius:5px;border:none;}}"
                              f"QProgressBar::chunk{{background:{color};border-radius:5px;}}")
            cl.addWidget(bar)

            upd = QHBoxLayout()
            sp = QDoubleSpinBox(); sp.setRange(0, 99_999_999); sp.setDecimals(2); sp.setValue(g["saved"]); sp.setPrefix("₺ ")
            sp.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:4px;padding:4px;color:#E0E0E0;max-width:140px;")
            ub = QPushButton("Güncelle"); ub.setFixedHeight(28)
            ub.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:4px;padding:0 10px;")
            ub.clicked.connect(lambda _, gid=g["id"], s=sp: (self._svc.update_saved(gid, s.value()), self._refresh()))
            upd.addWidget(sp); upd.addWidget(ub); upd.addStretch()
            cl.addLayout(upd)
            self._goals_lay.addWidget(card)
        self._goals_lay.addStretch()
