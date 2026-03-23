"""Portfolio Tracker — stock/ETF holdings, live prices, P&L, chart."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QLineEdit, QComboBox, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import PortfolioService, fetch_stock_price, fetch_stock_history
from tools.finance_service.finance_base import (
    make_header, MiniChart, StatCard, fetch_async, TEAL, ORANGE, RED, GREEN, CARD, PALETTE
)


class PortfolioTrackerTool(QWidget):
    name = "Portfolio Tracker"
    description = "Hisse senedi portföyü, anlık fiyat ve kâr/zarar"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc = PortfolioService(u["id"]) if u else None
        self._live = {}   # symbol → current price
        self._build_ui()
        if self._svc: self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("📈 Portföy Takibi")
        self._refresh_btn = self._btn("🔄 Fiyatları Güncelle")
        self._refresh_btn.clicked.connect(self._fetch_prices)
        hl.addWidget(self._refresh_btn)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#888;font-size:11px;")
        hl.addWidget(self._status_lbl)
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        # LEFT
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)

        stats = QHBoxLayout()
        self._val_card  = StatCard("Portföy Değeri", "₺0", TEAL)
        self._cost_card = StatCard("Maliyet", "₺0", ORANGE)
        self._pnl_card  = StatCard("Kâr / Zarar", "₺0", GREEN)
        for c in (self._val_card, self._cost_card, self._pnl_card):
            stats.addWidget(c)
        ll.addLayout(stats)

        # Add form
        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(8)
        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"

        self._sym_inp  = QLineEdit(); self._sym_inp.setPlaceholderText("Sembol (AAPL)"); self._sym_inp.setStyleSheet(inp); self._sym_inp.setMaximumWidth(100)
        self._name_inp = QLineEdit(); self._name_inp.setPlaceholderText("Şirket adı"); self._name_inp.setStyleSheet(inp)
        self._qty_spin = QDoubleSpinBox(); self._qty_spin.setRange(0.0001, 999999); self._qty_spin.setDecimals(4); self._qty_spin.setPrefix("Adet: "); self._qty_spin.setStyleSheet(inp)
        self._price_spin = QDoubleSpinBox(); self._price_spin.setRange(0.0001, 999999); self._price_spin.setDecimals(4); self._price_spin.setPrefix("Alış: ₺"); self._price_spin.setStyleSheet(inp)
        self._type_cb = QComboBox(); self._type_cb.addItems(["stock","etf","fund","bond","other"]); self._type_cb.setStyleSheet(inp)

        add_btn = self._btn("➕ Ekle")
        add_btn.clicked.connect(self._add)

        for w in (self._sym_inp, self._name_inp, self._qty_spin, self._price_spin, self._type_cb, add_btn):
            fl.addWidget(w)
        ll.addWidget(form)

        # Table
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(["Sembol","Ad","Adet","Alış","Güncel","Değer","K/Z"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setStyleSheet(
            "QTableWidget{background:#111;border:none;font-size:12px;}"
            "QHeaderView::section{background:#1E1E1E;color:#888;border:none;padding:4px;}")
        del_btn = QPushButton("🗑 Sil")
        del_btn.setStyleSheet("background:#B71C1C;color:#fff;border:none;border-radius:6px;padding:6px 14px;")
        del_btn.clicked.connect(self._delete)
        ll.addWidget(self._table, 1)
        ll.addWidget(del_btn, 0, Qt.AlignRight)
        body.addWidget(left, 3)

        # RIGHT — chart
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        rl.addWidget(QLabel("Geçmiş Fiyat Grafiği",
                            styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        self._sym_cb = QComboBox()
        self._sym_cb.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;")
        self._sym_cb.currentTextChanged.connect(self._load_chart)
        rl.addWidget(self._sym_cb)
        self._chart = MiniChart()
        rl.addWidget(self._chart, 1)
        body.addWidget(right, 2)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)

    def _btn(self, txt):
        b = QPushButton(txt)
        b.setFixedHeight(34)
        b.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        return b

    def _add(self):
        if not self._svc or not self._sym_inp.text().strip(): return
        self._svc.add_asset(
            symbol=self._sym_inp.text().strip().upper(),
            name=self._name_inp.text().strip(),
            qty=self._qty_spin.value(),
            buy_price=self._price_spin.value(),
            asset_type=self._type_cb.currentText()
        )
        self._sym_inp.clear(); self._name_inp.clear()
        self._refresh()

    def _delete(self):
        if not self._svc: return
        row = self._table.currentRow()
        if row < 0: return
        item = self._table.item(row, 0)
        if item and item.data(Qt.UserRole):
            self._svc.delete_asset(item.data(Qt.UserRole))
            self._refresh()

    def _fetch_prices(self):
        if not self._svc: return
        assets = self._svc.get_assets()
        symbols = list(set(a["symbol"] for a in assets))
        self._status_lbl.setText("⏳ Fiyatlar alınıyor…")
        def _fetch_all():
            result = {}
            for s in symbols:
                d = fetch_stock_price(s)
                if d: result[s] = d.get("price", 0)
            return result
        fetch_async(_fetch_all, self._on_prices)

    def _on_prices(self, prices):
        if prices:
            self._live = prices
            self._status_lbl.setText(f"✅ {len(prices)} hisse güncellendi")
        else:
            self._status_lbl.setText("⚠️ Fiyat alınamadı")
        self._refresh()

    def _refresh(self):
        if not self._svc: return
        assets = self._svc.get_assets()
        self._table.setRowCount(0)
        total_val = total_cost = 0

        syms = []
        for a in assets:
            sym = a["symbol"]
            if sym not in syms: syms.append(sym)
            cur = self._live.get(sym, 0)
            val  = a["quantity"] * cur if cur else 0
            cost = a["quantity"] * a["buy_price"]
            pnl  = val - cost if cur else None
            total_val  += val
            total_cost += cost

            r = self._table.rowCount()
            self._table.insertRow(r)
            sym_item = QTableWidgetItem(sym)
            sym_item.setData(Qt.UserRole, a["id"])
            self._table.setItem(r, 0, sym_item)
            self._table.setItem(r, 1, QTableWidgetItem(a.get("name","")))
            self._table.setItem(r, 2, QTableWidgetItem(f"{a['quantity']:.4f}"))
            self._table.setItem(r, 3, QTableWidgetItem(f"₺{a['buy_price']:,.4f}"))
            self._table.setItem(r, 4, QTableWidgetItem(f"₺{cur:,.4f}" if cur else "—"))
            self._table.setItem(r, 5, QTableWidgetItem(f"₺{val:,.2f}" if cur else "—"))
            if pnl is not None:
                pnl_item = QTableWidgetItem(f"₺{pnl:,.2f}")
                pnl_item.setForeground(QColor("#4CAF50" if pnl >= 0 else "#F44336"))
                self._table.setItem(r, 6, pnl_item)

        pnl_total = total_val - total_cost
        self._val_card.update_value(f"₺{total_val:,.2f}")
        self._cost_card.update_value(f"₺{total_cost:,.2f}")
        self._pnl_card.update_value(f"₺{pnl_total:,.2f}")

        # Update symbol combobox
        cur_sym = self._sym_cb.currentText()
        self._sym_cb.blockSignals(True)
        self._sym_cb.clear()
        self._sym_cb.addItems(syms)
        if cur_sym in syms:
            self._sym_cb.setCurrentText(cur_sym)
        self._sym_cb.blockSignals(False)
        if syms:
            self._load_chart(self._sym_cb.currentText())

    def _load_chart(self, sym):
        if not sym: return
        fetch_async(lambda s=sym: fetch_stock_history(s, "6mo"),
                    lambda hist, s=sym: self._on_chart(hist, s))

    def _on_chart(self, hist, sym):
        if not hist: return
        labels = [h["date"][5:] for h in hist]
        vals   = [h["close"] for h in hist]
        color  = "#4CAF50" if (len(vals) > 1 and vals[-1] >= vals[0]) else "#F44336"
        self._chart.set_data([(color, vals)], labels, f"{sym} — 6 Aylık", "₺")
