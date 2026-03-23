"""Crypto Tracker — track holdings, live CoinGecko prices, P&L, chart."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from core.auth_manager import auth_manager
from tools.finance_service.finance_service import (
    PortfolioService, fetch_crypto_prices, fetch_crypto_history
)
from tools.finance_service.finance_base import (
    make_header, MiniChart, StatCard, fetch_async, TEAL, ORANGE, RED, GREEN, CARD, PALETTE
)

COINS = [
    ("bitcoin","BTC"),("ethereum","ETH"),("solana","SOL"),("ripple","XRP"),
    ("dogecoin","DOGE"),("cardano","ADA"),("avalanche-2","AVAX"),
    ("polkadot","DOT"),("chainlink","LINK"),("litecoin","LTC"),
]
ID_TO_SYM = {c[0]: c[1] for c in COINS}
SYM_TO_ID = {c[1]: c[0] for c in COINS}


class CryptoTrackerTool(QWidget):
    name = "Crypto Tracker"
    description = "Kripto para varlıkları, anlık fiyat ve kâr/zarar"

    def __init__(self, parent=None):
        super().__init__(parent)
        u = auth_manager.current_user
        self._svc  = PortfolioService(u["id"]) if u else None
        self._live = {}   # coin_id → price_usd
        self._usd_try = 32.0   # fallback
        self._build_ui()
        if self._svc:
            self._refresh()
            self._fetch_prices()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        hdr, hl = make_header("₿ Kripto Takibi")
        self._refresh_btn = self._btn("🔄 Güncelle")
        self._refresh_btn.clicked.connect(self._fetch_prices)
        hl.addWidget(self._refresh_btn)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#888;font-size:11px;")
        hl.addWidget(self._status_lbl)
        root.addWidget(hdr)

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(20)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)

        stats = QHBoxLayout()
        self._val_card  = StatCard("Toplam Değer", "₺0", TEAL)
        self._cost_card = StatCard("Maliyet", "₺0", ORANGE)
        self._pnl_card  = StatCard("K/Z", "₺0", GREEN)
        for c in (self._val_card, self._cost_card, self._pnl_card):
            stats.addWidget(c)
        ll.addLayout(stats)

        # Form
        form = QFrame()
        form.setStyleSheet(f"QFrame{{background:{CARD};border-radius:8px;}}"
                           "QLabel{{border:none;background:transparent;}}")
        fl = QHBoxLayout(form)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(8)
        inp = "background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;"

        self._coin_cb = QComboBox()
        for cid, sym in COINS:
            self._coin_cb.addItem(f"{sym} ({cid})", cid)
        self._coin_cb.setStyleSheet(inp)
        self._qty_spin  = QDoubleSpinBox(); self._qty_spin.setRange(0.00001, 999999); self._qty_spin.setDecimals(6); self._qty_spin.setPrefix("Adet: "); self._qty_spin.setStyleSheet(inp)
        self._cost_spin = QDoubleSpinBox(); self._cost_spin.setRange(0.01, 9999999); self._cost_spin.setDecimals(2); self._cost_spin.setPrefix("Alış ₺: "); self._cost_spin.setStyleSheet(inp)

        add_btn = self._btn("➕ Ekle")
        add_btn.clicked.connect(self._add)
        for w in (self._coin_cb, self._qty_spin, self._cost_spin, add_btn):
            fl.addWidget(w)
        fl.addStretch()
        ll.addWidget(form)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Coin","Adet","Alış","Güncel","Değer","K/Z"])
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

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("Fiyat Grafiği (USD)",
                            styleSheet="color:#888;font-size:12px;font-weight:bold;"))
        self._chart_cb = QComboBox()
        self._chart_cb.setStyleSheet("background:#252525;border:1px solid #3E3E3E;border-radius:6px;padding:6px;color:#E0E0E0;")
        for cid, sym in COINS:
            self._chart_cb.addItem(f"{sym}", cid)
        self._chart_cb.currentIndexChanged.connect(lambda _: self._load_chart())
        rl.addWidget(self._chart_cb)
        self._chart = MiniChart()
        rl.addWidget(self._chart, 1)
        body.addWidget(right, 2)

        w = QWidget(); w.setLayout(body)
        root.addWidget(w, 1)
        self._load_chart()

    def _btn(self, txt):
        b = QPushButton(txt)
        b.setFixedHeight(34)
        b.setStyleSheet(f"background:{TEAL};color:#000;border:none;border-radius:6px;font-weight:bold;padding:0 14px;")
        return b

    def _add(self):
        if not self._svc: return
        cid = self._coin_cb.currentData()
        sym = ID_TO_SYM.get(cid, cid.upper())
        self._svc.add_asset(symbol=sym, name=cid, qty=self._qty_spin.value(),
                            buy_price=self._cost_spin.value(), asset_type="crypto")
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
        self._status_lbl.setText("⏳ Fiyatlar alınıyor…")
        coin_ids = [c[0] for c in COINS]
        def _fetch():
            from tools.finance_service.finance_service import fetch_exchange_rates
            rates = fetch_exchange_rates("USD")
            usd_try = 1 / rates.get("USD", 0.031) if rates else 32.0
            prices = fetch_crypto_prices(coin_ids)
            return {"prices": prices, "usd_try": usd_try}
        fetch_async(_fetch, self._on_prices)

    def _on_prices(self, data):
        if data:
            self._live = data.get("prices", {})
            self._usd_try = data.get("usd_try", 32.0)
            self._status_lbl.setText(f"✅ Güncellendi  (1 USD = ₺{self._usd_try:.2f})")
        else:
            self._status_lbl.setText("⚠️ Bağlanamadı")
        self._refresh()

    def _refresh(self):
        if not self._svc: return
        assets = [a for a in self._svc.get_assets() if a["asset_type"] == "crypto"]
        self._table.setRowCount(0)
        total_val = total_cost = 0

        for a in assets:
            sym = a["symbol"]
            cid = SYM_TO_ID.get(sym, a.get("name",""))
            price_usd = (self._live.get(cid, {}) or {}).get("usd", 0)
            price_try = price_usd * self._usd_try if price_usd else 0
            val  = a["quantity"] * price_try if price_try else 0
            cost = a["quantity"] * a["buy_price"]
            pnl  = val - cost if price_try else None
            total_val  += val
            total_cost += cost

            r = self._table.rowCount()
            self._table.insertRow(r)
            si = QTableWidgetItem(sym)
            si.setData(Qt.UserRole, a["id"])
            self._table.setItem(r, 0, si)
            self._table.setItem(r, 1, QTableWidgetItem(f"{a['quantity']:.6f}"))
            self._table.setItem(r, 2, QTableWidgetItem(f"₺{a['buy_price']:,.2f}"))
            self._table.setItem(r, 3, QTableWidgetItem(f"₺{price_try:,.2f}" if price_try else "—"))
            self._table.setItem(r, 4, QTableWidgetItem(f"₺{val:,.2f}" if val else "—"))
            if pnl is not None:
                pi = QTableWidgetItem(f"₺{pnl:,.2f}")
                pi.setForeground(QColor("#4CAF50" if pnl >= 0 else "#F44336"))
                self._table.setItem(r, 5, pi)

        pnl_total = total_val - total_cost
        self._val_card.update_value(f"₺{total_val:,.2f}")
        self._cost_card.update_value(f"₺{total_cost:,.2f}")
        self._pnl_card.update_value(f"₺{pnl_total:,.2f}")

    def _load_chart(self):
        cid = self._chart_cb.currentData()
        if not cid: return
        fetch_async(lambda c=cid: fetch_crypto_history(c, 90),
                    lambda hist, c=cid: self._on_chart(hist, c))

    def _on_chart(self, hist, cid):
        if not hist: return
        labels = [h["date"][5:] for h in hist]
        vals   = [h["price"] for h in hist]
        sym    = ID_TO_SYM.get(cid, cid)
        color  = "#4CAF50" if (len(vals) > 1 and vals[-1] >= vals[0]) else "#F44336"
        self._chart.set_data([(color, vals)], labels, f"{sym}/USD — 90 Gün", "$")
