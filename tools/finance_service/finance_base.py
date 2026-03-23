"""
finance_base.py — shared UI helpers for every finance tool.
  FinanceBase   : QWidget subclass with standard header + body layout
  MiniChart     : QPainter line/bar chart widget
  fetch_async   : run API call in background thread, call callback on finish
"""
import threading
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QLinearGradient


TEAL   = "#00BFA5"
ORANGE = "#FF9800"
RED    = "#F44336"
GREEN  = "#4CAF50"
BLUE   = "#2196F3"
PURPLE = "#9C27B0"
BG     = "#151515"
CARD   = "#1E1E1E"

PALETTE = [TEAL, ORANGE, RED, GREEN, BLUE, PURPLE,
           "#FF5722", "#607D8B", "#E91E63", "#00ACC1"]


def fmt_currency(v: float, symbol: str = "₺") -> str:
    if abs(v) >= 1_000_000:
        return f"{symbol}{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{symbol}{v:,.0f}"
    return f"{symbol}{v:.2f}"


class _Signal(QObject):
    done = Signal(object)


def fetch_async(fn, callback):
    """Run fn() in a thread; call callback(result) on the Qt main thread."""
    sig = _Signal()
    sig.done.connect(callback)
    def _run():
        try:
            result = fn()
        except Exception as e:
            result = None
        sig.done.emit(result)
        # keep sig alive until done
    t = threading.Thread(target=_run, daemon=True)
    t._sig = sig   # prevent GC
    t.start()
    return t


class MiniChart(QWidget):
    """Responsive line chart. set_data(points, labels, title)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(180)
        self._series: list[tuple[str, list[float]]] = []   # [(color, values)]
        self._labels: list[str] = []
        self._title  = ""
        self._y_sym  = ""

    def set_data(self, series: list, labels: list, title: str = "", y_sym: str = ""):
        """series = [(color, [v1,v2,...]), ...] or [(color, [(label,v), ...])]"""
        self._series = series
        self._labels = labels
        self._title  = title
        self._y_sym  = y_sym
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        PL, PR, PT, PB = 64, 16, 28, 44
        p.fillRect(0, 0, W, H, QColor(BG))

        if not self._series:
            p.setPen(QColor("#333"))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(QRectF(0, 0, W, H), Qt.AlignCenter, "Veri yok")
            p.end(); return

        cw, ch = W - PL - PR, H - PT - PB
        all_vals = [v for _, vals in self._series for v in vals if v is not None]
        if not all_vals: p.end(); return

        y_min, y_max = min(all_vals), max(all_vals)
        if y_max == y_min: y_max = y_min + 1
        pad = (y_max - y_min) * 0.1
        y_min -= pad; y_max += pad
        y_rng = y_max - y_min
        n = max(len(self._labels), max(len(v) for _, v in self._series))

        # Grid
        for i in range(5):
            yf = PT + ch * (1 - i / 4)
            p.setPen(QPen(QColor("#222"), 1))
            p.drawLine(PL, int(yf), PL + cw, int(yf))
            val = y_min + y_rng * i / 4
            p.setPen(QColor("#444"))
            p.setFont(QFont("Segoe UI", 8))
            label = f"{self._y_sym}{val:,.0f}"
            p.drawText(QRectF(0, yf - 8, PL - 4, 16),
                       Qt.AlignRight | Qt.AlignVCenter, label)

        # X labels
        step = max(1, n // 8)
        for i in range(0, n, step):
            if i < len(self._labels):
                x = PL + (i / max(n - 1, 1)) * cw
                p.setPen(QColor("#444"))
                p.setFont(QFont("Segoe UI", 8))
                lbl = str(self._labels[i])[-7:]
                p.drawText(QRectF(x - 24, H - PB + 4, 48, 14),
                           Qt.AlignCenter, lbl)

        # Series lines
        for color, vals in self._series:
            pts = []
            for i, v in enumerate(vals):
                if v is None: continue
                x = PL + (i / max(n - 1, 1)) * cw
                y = PT + ch * (1 - (v - y_min) / y_rng)
                pts.append(QPointF(x, y))

            # Gradient fill under line
            if len(pts) > 1:
                path_pts = pts + [QPointF(pts[-1].x(), PT + ch),
                                  QPointF(pts[0].x(), PT + ch)]
                from PySide6.QtGui import QPolygonF
                grad = QLinearGradient(0, PT, 0, PT + ch)
                c = QColor(color); c.setAlpha(60)
                c0 = QColor(color); c0.setAlpha(0)
                grad.setColorAt(0, c); grad.setColorAt(1, c0)
                p.setBrush(grad); p.setPen(Qt.NoPen)
                p.drawPolygon(QPolygonF(path_pts))

            p.setPen(QPen(QColor(color), 2))
            p.setBrush(Qt.NoBrush)
            for j in range(len(pts) - 1):
                p.drawLine(pts[j], pts[j + 1])

            # Dots at ends
            if pts:
                p.setBrush(QColor(color))
                p.drawEllipse(pts[-1], 4, 4)

        # Title
        if self._title:
            p.setPen(QColor("#888"))
            p.setFont(QFont("Segoe UI", 9, QFont.Bold))
            p.drawText(QRectF(PL, 4, cw, 20), Qt.AlignCenter, self._title)

        p.end()


class BarChart(QWidget):
    """Simple vertical bar chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(160)
        self._data: list[tuple[str, float, str]] = []  # (label, value, color)
        self._title = ""
        self._y_sym = ""

    def set_data(self, data, title="", y_sym=""):
        self._data  = data
        self._title = title
        self._y_sym = y_sym
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        PL, PR, PT, PB = 60, 12, 28, 44
        p.fillRect(0, 0, W, H, QColor(BG))

        if not self._data:
            p.setPen(QColor("#333"))
            p.drawText(QRectF(0, 0, W, H), Qt.AlignCenter, "Veri yok")
            p.end(); return

        cw, ch = W - PL - PR, H - PT - PB
        max_v = max(abs(v) for _, v, _ in self._data) or 1
        slot  = cw / len(self._data)
        bw    = max(6, slot * 0.65)

        if self._title:
            p.setPen(QColor("#888")); p.setFont(QFont("Segoe UI", 9, QFont.Bold))
            p.drawText(QRectF(PL, 4, cw, 20), Qt.AlignCenter, self._title)

        for i, (label, value, color) in enumerate(self._data):
            bh = int(abs(value) / max_v * ch)
            x  = int(PL + i * slot + (slot - bw) / 2)
            y  = PT + ch - bh
            p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(x, y, int(bw), bh, 3, 3)
            p.setPen(QColor("#AAA")); p.setFont(QFont("Segoe UI", 8))
            p.drawText(QRectF(x - 4, y - 14, bw + 8, 13), Qt.AlignCenter,
                       f"{self._y_sym}{value:,.0f}")
            p.setPen(QColor("#666"))
            p.drawText(QRectF(x - 4, PT + ch + 4, bw + 8, 14), Qt.AlignCenter,
                       label[:10])
        p.end()


class StatCard(QFrame):
    """Small KPI card: big number + label."""
    def __init__(self, title: str, value: str, color: str = TEAL, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet(
            f"QFrame{{background:{CARD};border:1px solid {color};"
            "border-radius:8px;}"
            "QLabel{{border:none;background:transparent;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        self._val_lbl = QLabel(value)
        self._val_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self._val_lbl.setStyleSheet(f"color:{color};")
        lay.addWidget(self._val_lbl)
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet("color:#666; font-size:11px;")
        lay.addWidget(self._title_lbl)

    def update_value(self, value: str):
        self._val_lbl.setText(value)

    def update_title(self, title: str):
        self._title_lbl.setText(title)


def make_header(title: str, subtitle: str = "") -> QFrame:
    hdr = QFrame()
    hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
    hl = QHBoxLayout(hdr)
    hl.setContentsMargins(24, 12, 24, 12)
    t = QLabel(title)
    t.setFont(QFont("Segoe UI", 18, QFont.Bold))
    t.setStyleSheet("color:#00BFA5;")
    hl.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet("color:#666; font-size:12px;")
        hl.addWidget(s)
    hl.addStretch()
    return hdr, hl