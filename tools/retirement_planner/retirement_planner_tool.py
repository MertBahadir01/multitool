"""Retirement Planner — project savings to retirement age with yearly growth."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from tools.finance_service.finance_service import future_value
from tools.finance_service.finance_base import make_header, MiniChart, StatCard, TEAL, ORANGE, GREEN, RED, CARD


class RetirementPlannerTool(QWidget):
    name = "Retirement Planner"
    description = "Emeklilik tasarrufu ve büyüme projeksiyonu"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._calculate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("🏖️ Emeklilik Planlayıcı")
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        left = QFrame()
        left.setFixedWidth(290)
        left.setStyleSheet(f"QFrame{{background:{CARD};border-radius:10px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(20, 20, 20, 20)
        ll.setSpacing(10)

        def add(label, widget):
            ll.addWidget(QLabel(label, styleSheet="color:#888;font-size:11px;"))
            widget.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:8px;font-size:13px;color:#E0E0E0;")
            ll.addWidget(widget)

        self._current_age   = QSpinBox(); self._current_age.setRange(18,90); self._current_age.setValue(30)
        self._retire_age    = QSpinBox(); self._retire_age.setRange(40,90);  self._retire_age.setValue(65)
        self._savings       = QDoubleSpinBox(); self._savings.setRange(0,99_999_999); self._savings.setDecimals(0); self._savings.setPrefix("₺ "); self._savings.setValue(50_000)
        self._monthly       = QDoubleSpinBox(); self._monthly.setRange(0,999_999); self._monthly.setDecimals(0); self._monthly.setPrefix("₺ "); self._monthly.setValue(2_000)
        self._rate          = QDoubleSpinBox(); self._rate.setRange(0,100); self._rate.setDecimals(2); self._rate.setSuffix("%"); self._rate.setValue(12)
        self._monthly_need  = QDoubleSpinBox(); self._monthly_need.setRange(0,999_999); self._monthly_need.setDecimals(0); self._monthly_need.setPrefix("₺ "); self._monthly_need.setValue(10_000); self._monthly_need.setToolTip("Aylık ihtiyaç")
        self._retire_years  = QSpinBox(); self._retire_years.setRange(1,50); self._retire_years.setValue(25)

        add("Mevcut Yaş", self._current_age)
        add("Emeklilik Yaşı", self._retire_age)
        add("Mevcut Birikim (₺)", self._savings)
        add("Aylık Katkı (₺)", self._monthly)
        add("Yıllık Getiri (%)", self._rate)
        add("Aylık Emeklilik İhtiyacı (₺)", self._monthly_need)
        add("Emeklilik Süresi (Yıl)", self._retire_years)

        btn = QPushButton("Hesapla")
        btn.setFixedHeight(38)
        btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:8px;font-weight:bold;font-size:14px;")
        btn.clicked.connect(self._calculate)
        ll.addWidget(btn)
        ll.addSpacing(6)

        self._accum_card  = StatCard("Birikmiş Tutar", "₺0", TEAL)
        self._need_card   = StatCard("İhtiyaç Tutarı", "₺0", ORANGE)
        self._gap_card    = StatCard("Fark", "₺0", GREEN)
        self._sustain_card= StatCard("Sürdürülebilirlik", "—", TEAL)
        for c in (self._accum_card, self._need_card, self._gap_card, self._sustain_card):
            ll.addWidget(c)
        ll.addStretch()
        body.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self._chart = MiniChart()
        rl.addWidget(self._chart, 1)
        body.addWidget(right, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _calculate(self):
        years_to_retire = max(1, self._retire_age.value() - self._current_age.value())
        accumulated = future_value(self._savings.value(), self._rate.value(),
                                   years_to_retire, self._monthly.value())
        total_need = self._monthly_need.value() * 12 * self._retire_years.value()
        gap = accumulated - total_need

        self._accum_card.update_value(f"₺{accumulated:,.0f}")
        self._need_card.update_value(f"₺{total_need:,.0f}")
        self._gap_card.update_value(f"₺{gap:,.0f}")
        if accumulated > 0:
            months = accumulated / self._monthly_need.value() if self._monthly_need.value() > 0 else 0
            self._sustain_card.update_value(f"{months/12:.1f} yıl")
        else:
            self._sustain_card.update_value("—")

        labels = [str(i) for i in range(0, years_to_retire + 1)]
        vals = [future_value(self._savings.value(), self._rate.value(), i, self._monthly.value())
                for i in range(0, years_to_retire + 1)]
        self._chart.set_data([(TEAL, vals)], labels, "Birikim Projeksiyonu", "₺")
