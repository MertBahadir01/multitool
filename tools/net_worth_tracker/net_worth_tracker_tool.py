"""Net Worth Tracker — assets minus liabilities."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import NetWorthService
from tools.finance_service.finance_base import make_header, StatCard, TEAL, ORANGE, RED, GREEN, CARD


class NetWorthTrackerTool(QWidget):
    name = "Net Worth Tracker"
    description = "Varlıklar eksi borçlar = net servet"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = NetWorthService(u["id"]) if u else None
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, _ = make_header("💎 Net Servet Takibi")
        root.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        stats = QHBoxLayout()
        self._asset_card = StatCard("Toplam Varlık", "₺0", GREEN)
        self._liab_card  = StatCard("Toplam Borç", "₺0", RED)
        self._net_card   = StatCard("Net Servet", "₺0", TEAL)
        for c in (self._asset_card, self._liab_card, self._net_card):
            stats.addWidget(c)
        body.addLayout(stats)

        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(8)
        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"
        self._name_inp  = QLineEdit(); self._name_inp.setPlaceholderText("Kalem adı (örn. Araba)"); self._name_inp.setStyleSheet(inp)
        self._val_spin  = QDoubleSpinBox(); self._val_spin.setRange(0, 999_999_999); self._val_spin.setDecimals(2); self._val_spin.setPrefix("₺ "); self._val_spin.setStyleSheet(inp)
        self._type_cb   = QComboBox(); self._type_cb.addItems(["asset","liability"]); self._type_cb.setStyleSheet(inp)
        add_btn = QPushButton("➕ Ekle")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        add_btn.clicked.connect(self._add)
        for w in (self._name_inp, self._val_spin, self._type_cb, add_btn):
            fl.addWidget(w)
        fl.addStretch()
        body.addWidget(form)

        body_h = QHBoxLayout()
        for title, attr, col in [("Varlıklar", "_asset_table", GREEN), ("Borçlar", "_liab_table", RED)]:
            col_w = QWidget()
            cl = QVBoxLayout(col_w)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(6)
            cl.addWidget(QLabel(title, styleSheet=f"color:{col};font-weight:bold;font-size:13px;"))
            tbl = QTableWidget(0, 3)
            tbl.setHorizontalHeaderLabels(["Kalem","Değer","Sil"])
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            tbl.setStyleSheet("QTableWidget{background:#111;border:none;font-size:12px;}"
                              "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
            setattr(self, attr, tbl)
            cl.addWidget(tbl, 1)
            body_h.addWidget(col_w)
        body.addLayout(body_h, 1)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _add(self):
        if not self._svc or not self._name_inp.text().strip(): return
        self._svc.add_item(self._name_inp.text().strip(), self._val_spin.value(), self._type_cb.currentText())
        self._name_inp.clear()
        self._refresh()

    def _refresh(self):
        if not self._svc: return
        items = self._svc.get_all()
        snap  = self._svc.snapshot()
        self._asset_card.update_value(f"₺{snap['assets']:,.0f}")
        self._liab_card.update_value(f"₺{snap['liabilities']:,.0f}")
        nw = snap["net_worth"]
        self._net_card.update_value(f"₺{nw:,.0f}")

        for tbl in (self._asset_table, self._liab_table):
            tbl.setRowCount(0)

        for item in items:
            tbl = self._asset_table if item["item_type"] == "asset" else self._liab_table
            r = tbl.rowCount(); tbl.insertRow(r)
            ni = QTableWidgetItem(item["name"]); ni.setData(Qt.UserRole, item["id"])
            tbl.setItem(r, 0, ni)
            tbl.setItem(r, 1, QTableWidgetItem(f"₺{item['value']:,.2f}"))
            del_btn = QPushButton("🗑")
            del_btn.setFixedSize(28, 28)
            del_btn.setStyleSheet("background:#3A3A3A;border:none;border-radius:4px;color:#888;")
            del_btn.clicked.connect(lambda _, iid=item["id"]: (self._svc.delete(iid), self._refresh()))
            tbl.setCellWidget(r, 2, del_btn)
