"""
Exam Progress Tool
==================
5 analytics tabs, all charts drawn with QPainter (no external libs):

  1. 🏠 Genel Bakış     — summary cards per subject + bar chart of latest nets
  2. 📉 Trend Grafikleri — line chart: pick subject → net over time; pick topic → topic trend
  3. 🌡️ Konu Haritası    — heatmap: topics × exams → success % per cell
  4. 🎯 Zayıf Konular   — ranked weakness table + bar chart
  5. 📚 Ders Detayı      — deep dive: one subject, all stats, topic table, lesson link count
"""

import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QGridLayout, QSizePolicy, QSplitter
)
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush

from core.auth_manager import auth_manager
from tools.exam_detail.exam_detail_service import ExamDetailService, EXAM_DEFS

PALETTE = [
    "#00BFA5", "#FF9800", "#9C27B0", "#F44336",
    "#2196F3", "#4CAF50", "#FF5722", "#607D8B",
    "#E91E63", "#00ACC1", "#8BC34A", "#FFC107",
]


def _net(c, i):  return round(c - i * 0.25, 2)
def _pct(c, t):  return round(c / max(t, 1) * 100, 1)
def _col_net(n): return "#4CAF50" if n > 0 else ("#F44336" if n < 0 else "#888")
def _col_pct(p): return "#4CAF50" if p >= 70 else ("#FF9800" if p >= 45 else "#F44336")


# ════════════════════════════════════════════════════════════════════════════
# Reusable chart widgets
# ════════════════════════════════════════════════════════════════════════════

class LineChart(QWidget):
    """Multi-series line chart. series = {label: [float|None, ...]}"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300)
        self._series:   dict[str, list] = {}
        self._x_labels: list[str]       = []
        self._title     = ""

    def set_data(self, series: dict, x_labels: list, title=""):
        self._series   = series
        self._x_labels = x_labels
        self._title    = title
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        PL, PR, PT, PB = 58, 18, 38, 54
        painter.fillRect(0, 0, W, H, QColor("#151515"))

        if not self._series or not self._x_labels:
            painter.setPen(QColor("#444"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(QRectF(0, 0, W, H), Qt.AlignCenter, "Henüz veri yok")
            painter.end(); return

        cw   = W - PL - PR
        ch   = H - PT - PB
        n    = len(self._x_labels)
        vals = [v for series in self._series.values() for v in series if v is not None]
        if not vals: painter.end(); return

        y_min, y_max = min(vals), max(vals)
        if y_max == y_min: y_max = y_min + 1
        y_pad = (y_max - y_min) * 0.08
        y_min -= y_pad; y_max += y_pad
        y_rng = y_max - y_min

        # grid + y labels
        LINES = 5
        for i in range(LINES + 1):
            yf = PT + ch * (1 - i / LINES)
            painter.setPen(QPen(QColor("#222"), 1))
            painter.drawLine(PL, int(yf), PL + cw, int(yf))
            val = y_min + y_rng * i / LINES
            painter.setPen(QColor("#555"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(0, yf - 8, PL - 4, 16),
                             Qt.AlignRight | Qt.AlignVCenter, f"{val:.1f}")

        # x labels
        for i, lbl in enumerate(self._x_labels):
            x = PL + (i / max(n - 1, 1)) * cw
            painter.setPen(QColor("#555"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(x - 26, H - PB + 6, 52, 14),
                             Qt.AlignCenter, str(lbl)[-5:])

        # title
        if self._title:
            painter.setPen(QColor("#CCCCCC"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(QRectF(PL, 8, cw, 22), Qt.AlignCenter, self._title)

        # series
        for ci, (label, values) in enumerate(self._series.items()):
            color = QColor(PALETTE[ci % len(PALETTE)])
            painter.setPen(QPen(color, 2))
            pts = []
            for i, v in enumerate(values):
                if v is None: continue
                x = PL + (i / max(n - 1, 1)) * cw
                y = PT + ch * (1 - (v - y_min) / y_rng)
                pts.append(QPointF(x, y))
            for j in range(len(pts) - 1):
                painter.drawLine(pts[j], pts[j + 1])
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            for pt in pts:
                painter.drawEllipse(pt, 4, 4)

        # legend
        lx, ly = PL, H - 14
        for ci, label in enumerate(self._series):
            color = QColor(PALETTE[ci % len(PALETTE)])
            painter.fillRect(lx, ly - 8, 10, 10, color)
            painter.setPen(QColor("#BBBBBB"))
            painter.setFont(QFont("Segoe UI", 8))
            tw = painter.fontMetrics().horizontalAdvance(label) + 20
            painter.drawText(lx + 12, ly, label)
            lx += tw
            if lx > W - 80: break

        painter.end()


class BarChart(QWidget):
    """Horizontal or vertical bar chart."""

    def __init__(self, horizontal=False, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self._horiz     = horizontal
        self._data:      dict[str, float] = {}
        self._colors:    dict[str, str]   = {}
        self._title     = ""

    def set_data(self, data: dict, title="", colors: dict = None):
        self._data   = data
        self._title  = title
        self._colors = colors or {}
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        PL, PR, PT, PB = 60, 16, 32, 48
        painter.fillRect(0, 0, W, H, QColor("#151515"))

        if not self._data:
            painter.setPen(QColor("#444"))
            painter.drawText(QRectF(0, 0, W, H), Qt.AlignCenter, "Veri yok")
            painter.end(); return

        items = list(self._data.items())
        max_v = max(abs(v) for _, v in items) or 1
        cw, ch = W - PL - PR, H - PT - PB

        if self._title:
            painter.setPen(QColor("#CCCCCC"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(QRectF(PL, 6, cw, 22), Qt.AlignCenter, self._title)

        if not self._horiz:
            slot_w = cw / max(len(items), 1)
            bw     = max(8, int(slot_w * 0.65))
            zero_y = PT + ch
            for i, (label, value) in enumerate(items):
                x   = int(PL + i * slot_w + (slot_w - bw) / 2)
                bh  = int(abs(value) / max_v * ch)
                y   = zero_y - bh
                col = QColor(self._colors.get(label, PALETTE[i % len(PALETTE)]))
                # gradient fill
                painter.fillRect(x, y, bw, bh, col)
                # value
                painter.setPen(QColor("#E0E0E0"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(QRectF(x - 4, y - 16, bw + 8, 14),
                                 Qt.AlignCenter, f"{value:.1f}")
                # label
                painter.setPen(QColor("#777"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(QRectF(x - 6, zero_y + 4, bw + 12, 20),
                                 Qt.AlignCenter, label[:12])
        else:
            slot_h = ch / max(len(items), 1)
            bh     = max(8, int(slot_h * 0.6))
            for i, (label, value) in enumerate(items):
                y   = int(PT + i * slot_h + (slot_h - bh) / 2)
                bw2 = int(abs(value) / max_v * (cw - 60))
                col = QColor(self._colors.get(label, PALETTE[i % len(PALETTE)]))
                painter.fillRect(PL, y, bw2, bh, col)
                painter.setPen(QColor("#E0E0E0"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(QRectF(0, y, PL - 4, bh),
                                 Qt.AlignRight | Qt.AlignVCenter, label[:14])
                painter.drawText(QRectF(PL + bw2 + 4, y, 40, bh),
                                 Qt.AlignVCenter, f"{value:.1f}")

        painter.end()


class HeatmapChart(QWidget):
    """topics × exams heatmap, cell colour = success %."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[str]              = []
        self._cols: list[str]              = []
        self._data: dict[tuple, float|None] = {}

    def set_data(self, rows, cols, data):
        self._rows = rows; self._cols = cols; self._data = data
        cell_h = max(22, 500 // max(len(rows), 1))
        self.setMinimumHeight(cell_h * max(len(rows), 1) + 50)
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        painter.fillRect(0, 0, W, H, QColor("#151515"))

        if not self._rows or not self._cols:
            painter.setPen(QColor("#444"))
            painter.drawText(QRectF(0, 0, W, H), Qt.AlignCenter, "Veri yok")
            painter.end(); return

        LBL_W = 190; HDR_H = 44
        nr, nc = len(self._rows), len(self._cols)
        cw = max(28, (W - LBL_W) // max(nc, 1))
        rh = max(20, (H - HDR_H) // max(nr, 1))

        # col headers
        painter.setFont(QFont("Segoe UI", 8))
        for j, col in enumerate(self._cols):
            x = LBL_W + j * cw
            painter.setPen(QColor("#888"))
            painter.drawText(QRectF(x, 2, cw, HDR_H - 2), Qt.AlignCenter | Qt.TextWordWrap,
                             str(col)[-10:])

        # cells
        for i, row in enumerate(self._rows):
            y = HDR_H + i * rh
            painter.setPen(QColor("#AAAAAA"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(4, y, LBL_W - 8, rh),
                             Qt.AlignVCenter | Qt.AlignLeft, row[:30])
            for j, col in enumerate(self._cols):
                val = self._data.get((row, col))
                x = LBL_W + j * cw
                if val is None:
                    cell_color = QColor("#1A1A1A")
                else:
                    r2 = max(0, min(255, int((100 - val) * 2.2)))
                    g2 = max(0, min(255, int(val * 2.0)))
                    cell_color = QColor(r2, g2, 60, 210)
                painter.fillRect(x + 1, y + 1, cw - 2, rh - 2, cell_color)
                if val is not None:
                    painter.setPen(QColor("#FFFFFF"))
                    painter.setFont(QFont("Segoe UI", 8))
                    painter.drawText(QRectF(x, y, cw, rh), Qt.AlignCenter,
                                     f"{val:.0f}%")

        painter.end()


# ════════════════════════════════════════════════════════════════════════════
# Summary card widget
# ════════════════════════════════════════════════════════════════════════════
class SubjectCard(QFrame):
    def __init__(self, d: dict, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(210, 150)
        self.setStyleSheet(f"""
            QFrame {{ background:#1E1E1E; border:1px solid {color};
                     border-radius:10px; }}
            QLabel {{ border:none; background:transparent; }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        subj = QLabel(d["subject"])
        subj.setFont(QFont("Segoe UI", 12, QFont.Bold))
        subj.setStyleSheet(f"color:{color};")
        lay.addWidget(subj)

        n_exams = d.get("n_exams", 0)
        avg_net = d.get("avg_net", 0)
        last_net = d.get("last_net", 0)
        best_net = d.get("best_net", 0)
        avg_pct  = d.get("avg_pct", 0)

        lay.addWidget(QLabel(
            f"Son net: <b style='color:{_col_net(last_net)}'>{last_net:.2f}</b>",
            styleSheet="color:#CCC; font-size:12px;"))
        lay.addWidget(QLabel(
            f"Ort. net: {avg_net:.2f}  |  En iyi: {best_net:.2f}",
            styleSheet="color:#888; font-size:11px;"))
        lay.addWidget(QLabel(
            f"Ort. başarı: <b style='color:{_col_pct(avg_pct)}'>{avg_pct:.1f}%</b>  "
            f"({n_exams} sınav)",
            styleSheet="color:#888; font-size:11px;"))


# ════════════════════════════════════════════════════════════════════════════
# Main tool
# ════════════════════════════════════════════════════════════════════════════
class ExamProgressTool(QWidget):
    name        = "Exam Progress"
    description = "Sınav ilerleme: bölüm/konu bazlı grafikler ve analiz"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = ExamDetailService(user) if user else None
        self._build_ui()
        if self._svc:
            QTimer.singleShot(150, self._refresh_all)

    # ── UI skeleton ───────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📈 Sınav İlerleme")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        hl.addWidget(QLabel("Tür:"))
        self._type_combo = QComboBox()
        self._type_combo.addItem("Tümü")
        self._type_combo.addItems(list(EXAM_DEFS.keys()))
        self._type_combo.currentTextChanged.connect(self._refresh_all)
        hl.addWidget(self._type_combo)
        ref_btn = QPushButton("🔄 Yenile")
        ref_btn.clicked.connect(self._refresh_all)
        hl.addWidget(ref_btn)
        root.addWidget(hdr)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_change)

        # ── Tab 1: Overview ────────────────────────────────────────────────────
        self._ov_tab = QWidget()
        ovl = QVBoxLayout(self._ov_tab)
        ovl.setContentsMargins(16, 16, 16, 16); ovl.setSpacing(12)

        ovl.addWidget(QLabel("Son sınav durumu — her bölüm için hesaplanan net ve başarı:",
                             styleSheet="color:#888; font-size:12px;"))
        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(QFrame.NoFrame)
        self._cards_container = QWidget()
        self._cards_grid = QGridLayout(self._cards_container)
        self._cards_grid.setSpacing(12)
        self._cards_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._cards_scroll.setWidget(self._cards_container)
        ovl.addWidget(self._cards_scroll)

        ovl.addWidget(QLabel("Ortalama net (tüm sınavlar):",
                             styleSheet="color:#888; font-size:12px;"))
        self._ov_bar = BarChart()
        self._ov_bar.setMinimumHeight(200)
        ovl.addWidget(self._ov_bar)
        self._tabs.addTab(self._ov_tab, "🏠 Genel Bakış")

        # ── Tab 2: Trend Charts ────────────────────────────────────────────────
        trend_tab = QWidget()
        tl = QVBoxLayout(trend_tab)
        tl.setContentsMargins(16, 12, 16, 12); tl.setSpacing(10)

        tr_bar = QHBoxLayout()
        tr_bar.addWidget(QLabel("Bölüm:"))
        self._tr_subj = QComboBox(); self._tr_subj.setMinimumWidth(160)
        self._tr_subj.currentTextChanged.connect(self._on_trend_subject_change)
        tr_bar.addWidget(self._tr_subj)
        tr_bar.addWidget(QLabel("Konu:"))
        self._tr_topic = QComboBox(); self._tr_topic.setMinimumWidth(180)
        self._tr_topic.addItem("Tüm Konular")
        self._tr_topic.currentTextChanged.connect(self._refresh_trend)
        tr_bar.addWidget(self._tr_topic)
        tr_bar.addStretch()
        tl.addLayout(tr_bar)

        self._trend_chart = LineChart()
        tl.addWidget(self._trend_chart, 2)

        self._trend_tbl = QTableWidget(0, 5)
        self._trend_tbl.setHorizontalHeaderLabels(["Tarih", "Kaynak", "Doğru", "Yanlış", "Net"])
        self._trend_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._trend_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self._trend_tbl.setMaximumHeight(150)
        tl.addWidget(self._trend_tbl)
        self._tabs.addTab(trend_tab, "📉 Trend")

        # ── Tab 3: Heatmap ─────────────────────────────────────────────────────
        heat_tab = QWidget()
        hl2 = QVBoxLayout(heat_tab)
        hl2.setContentsMargins(16, 12, 16, 12); hl2.setSpacing(8)

        hbar = QHBoxLayout()
        hbar.addWidget(QLabel("Bölüm:"))
        self._hm_subj = QComboBox(); self._hm_subj.setMinimumWidth(160)
        self._hm_subj.currentTextChanged.connect(self._refresh_heatmap)
        hbar.addWidget(self._hm_subj); hbar.addStretch()
        hl2.addLayout(hbar)

        self._hm_scroll = QScrollArea()
        self._hm_scroll.setWidgetResizable(True)
        self._hm_scroll.setFrameShape(QFrame.NoFrame)
        self._hm_chart  = HeatmapChart()
        self._hm_scroll.setWidget(self._hm_chart)
        hl2.addWidget(self._hm_scroll, 1)
        hl2.addWidget(QLabel("  🟢 Yeşil = yüksek başarı   🔴 Kırmızı = düşük başarı   ⬛ Gri = veri yok",
                             styleSheet="color:#555; font-size:11px;"))
        self._tabs.addTab(heat_tab, "🌡️ Konu Haritası")

        # ── Tab 4: Weak Topics ─────────────────────────────────────────────────
        weak_tab = QWidget()
        wl = QVBoxLayout(weak_tab)
        wl.setContentsMargins(16, 12, 16, 12); wl.setSpacing(8)

        wbar = QHBoxLayout()
        wbar.addWidget(QLabel("Min. sınav:"))
        self._wk_min = QComboBox()
        self._wk_min.addItems(["1", "2", "3"])
        self._wk_min.currentTextChanged.connect(self._refresh_weak)
        wbar.addWidget(self._wk_min); wbar.addStretch()
        wl.addLayout(wbar)

        self._wk_bar = BarChart(horizontal=True)
        self._wk_bar.setMinimumHeight(240)
        wl.addWidget(self._wk_bar)

        self._wk_tbl = QTableWidget(0, 7)
        self._wk_tbl.setHorizontalHeaderLabels(
            ["Bölüm", "Konu", "Top. D", "Top. Y", "% Başarı", "Ort. Net", "Sınav #"])
        self._wk_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._wk_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        wl.addWidget(self._wk_tbl, 1)
        self._tabs.addTab(weak_tab, "🎯 Zayıf Konular")

        # ── Tab 5: Subject Detail ──────────────────────────────────────────────
        sd_tab = QWidget()
        sdl = QVBoxLayout(sd_tab)
        sdl.setContentsMargins(16, 12, 16, 12); sdl.setSpacing(8)

        sdbar = QHBoxLayout()
        sdbar.addWidget(QLabel("Bölüm:"))
        self._sd_subj = QComboBox(); self._sd_subj.setMinimumWidth(160)
        self._sd_subj.currentTextChanged.connect(self._refresh_subject_detail)
        sdbar.addWidget(self._sd_subj); sdbar.addStretch()
        sdl.addLayout(sdbar)

        # Stats strip
        self._sd_stats = QHBoxLayout()
        sdl.addLayout(self._sd_stats)

        self._sd_line = LineChart()
        self._sd_line.setMinimumHeight(240)
        sdl.addWidget(self._sd_line)

        sdl.addWidget(QLabel("Konulara Göre Ortalama:",
                             styleSheet="color:#888; font-size:12px;"))
        self._sd_topic_tbl = QTableWidget(0, 6)
        self._sd_topic_tbl.setHorizontalHeaderLabels(
            ["Konu", "Ort. D", "Ort. Y", "Ort. Net", "% Başarı", "Durum"])
        self._sd_topic_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._sd_topic_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        sdl.addWidget(self._sd_topic_tbl, 1)
        self._tabs.addTab(sd_tab, "📚 Ders Detayı")

        root.addWidget(self._tabs, 1)

    # ── Orchestrator ──────────────────────────────────────────────────────────
    def _exam_type(self):
        v = self._type_combo.currentText()
        return None if v == "Tümü" else v

    def _refresh_all(self):
        if not self._svc: return
        et = self._exam_type()
        subjects = self._svc.get_all_subjects_seen(et)
        for combo in (self._tr_subj, self._hm_subj, self._sd_subj):
            combo.blockSignals(True)
            prev = combo.currentText()
            combo.clear()
            combo.addItems(subjects)
            idx = combo.findText(prev)
            if idx >= 0: combo.setCurrentIndex(idx)
            combo.blockSignals(False)
        self._on_tab_change(self._tabs.currentIndex())

    def _on_tab_change(self, idx):
        if not self._svc: return
        et = self._exam_type()
        if   idx == 0: self._refresh_overview(et)
        elif idx == 1: self._refresh_trend()
        elif idx == 2: self._refresh_heatmap()
        elif idx == 3: self._refresh_weak()
        elif idx == 4: self._refresh_subject_detail()

    # ── Tab 1 ─────────────────────────────────────────────────────────────────
    def _refresh_overview(self, et):
        while self._cards_grid.count():
            w = self._cards_grid.takeAt(0).widget()
            if w: w.deleteLater()

        summaries = self._svc.get_all_subjects_summary(et)
        bar_data, bar_cols = {}, {}
        for i, d in enumerate(summaries):
            color = PALETTE[i % len(PALETTE)]
            card = SubjectCard(d, color)
            self._cards_grid.addWidget(card, i // 4, i % 4)
            bar_data[d["subject"]] = d["avg_net"]
            bar_cols[d["subject"]] = _col_net(d["avg_net"])

        self._ov_bar.set_data(bar_data, "Bölüm Ortalama Net Puanları", bar_cols)

    # ── Tab 2 ─────────────────────────────────────────────────────────────────
    def _on_trend_subject_change(self):
        subj = self._tr_subj.currentText()
        et   = self._exam_type()
        self._tr_topic.blockSignals(True)
        self._tr_topic.clear()
        self._tr_topic.addItem("Tüm Konular")
        # get topics seen for this subject
        exams = self._svc.get_exams(et)
        seen  = set()
        for ex in exams:
            for ts in self._svc.get_topic_scores(ex["id"], subj):
                seen.add(ts["topic"])
        for t in sorted(seen):
            self._tr_topic.addItem(t)
        self._tr_topic.blockSignals(False)
        self._refresh_trend()

    def _refresh_trend(self):
        if not self._svc: return
        subj  = self._tr_subj.currentText()
        topic = self._tr_topic.currentText()
        et    = self._exam_type()
        if not subj: return

        self._trend_tbl.setRowCount(0)

        if topic == "Tüm Konular":
            rows = self._svc.get_subject_trend(subj, et)
            x_labels = [str(r["exam_date"])[:10] for r in rows]
            series = {
                "Net":     [r["net"]  for r in rows],
                "Doğru":   [float(r["correct"])   for r in rows],
                "Yanlış":  [float(r["incorrect"])  for r in rows],
            }
            for r in rows:
                rx = self._trend_tbl.rowCount(); self._trend_tbl.insertRow(rx)
                for ci, val in enumerate([str(r["exam_date"])[:10], r.get("source",""),
                                          str(r["correct"]), str(r["incorrect"]),
                                          str(r["net"])]):
                    self._trend_tbl.setItem(rx, ci, QTableWidgetItem(val))
        else:
            rows = self._svc.get_topic_trend(subj, topic, et)
            x_labels = [str(r["exam_date"])[:10] for r in rows]
            series = {
                "Doğru":  [float(r["correct"])   for r in rows],
                "Yanlış": [float(r["incorrect"])  for r in rows],
                "Net":    [r["net"]  for r in rows],
            }
            for r in rows:
                rx = self._trend_tbl.rowCount(); self._trend_tbl.insertRow(rx)
                for ci, val in enumerate([str(r["exam_date"])[:10], r.get("source",""),
                                          str(r["correct"]), str(r["incorrect"]),
                                          str(r["net"])]):
                    self._trend_tbl.setItem(rx, ci, QTableWidgetItem(val))

        self._trend_chart.set_data(
            series, x_labels,
            f"{subj}{' — ' + topic if topic != 'Tüm Konular' else ''}"
        )

    # ── Tab 3 ─────────────────────────────────────────────────────────────────
    def _refresh_heatmap(self):
        if not self._svc: return
        subj = self._hm_subj.currentText()
        et   = self._exam_type()
        if not subj: return

        exams = self._svc.get_exams(et)
        cols, cell_data = [], {}
        for ex in exams:
            lbl = f"{str(ex['exam_date'])[:10]}\n{(ex.get('source','') or '')[:8]}"
            cols.append(lbl)
            for ts in self._svc.get_topic_scores(ex["id"], subj):
                total = ts["correct"] + ts["incorrect"] + ts["empty"]
                if total > 0:
                    cell_data[(ts["topic"], lbl)] = _pct(ts["correct"], total)

        rows = sorted(set(r for (r, _) in cell_data))
        data = {(r, c): cell_data.get((r, c)) for r in rows for c in cols}
        self._hm_chart.set_data(rows, cols, data)

    # ── Tab 4 ─────────────────────────────────────────────────────────────────
    def _refresh_weak(self):
        if not self._svc: return
        et      = self._exam_type()
        min_ex  = int(self._wk_min.currentText())
        weak    = self._svc.get_weak_topics(et, min_ex)

        self._wk_tbl.setRowCount(0)
        bar_data, bar_cols = {}, {}

        for w in weak[:25]:
            r = self._wk_tbl.rowCount(); self._wk_tbl.insertRow(r)
            self._wk_tbl.setItem(r, 0, QTableWidgetItem(w["subject"]))
            self._wk_tbl.setItem(r, 1, QTableWidgetItem(w["topic"]))
            self._wk_tbl.setItem(r, 2, QTableWidgetItem(str(w["total_c"])))
            yi = QTableWidgetItem(str(w["total_i"]))
            if (w["total_i"] or 0) > (w["total_c"] or 0):
                yi.setForeground(QColor("#F44336"))
            self._wk_tbl.setItem(r, 3, yi)
            pi = QTableWidgetItem(f"{w['pct']:.1f}%")
            pi.setForeground(QColor(_col_pct(w["pct"])))
            self._wk_tbl.setItem(r, 4, pi)
            ni = QTableWidgetItem(f"{w['avg_net']:.2f}")
            ni.setForeground(QColor(_col_net(w["avg_net"])))
            self._wk_tbl.setItem(r, 5, ni)
            self._wk_tbl.setItem(r, 6, QTableWidgetItem(str(w["n_exams"])))

            lbl = f"{w['subject'][:5]}/{w['topic'][:10]}"
            bar_data[lbl] = w["pct"]
            bar_cols[lbl] = _col_pct(w["pct"])

        self._wk_bar.set_data(bar_data, "Zayıf Konular — % Başarı (düşükten yükseğe)", bar_cols)

    # ── Tab 5 ─────────────────────────────────────────────────────────────────
    def _refresh_subject_detail(self):
        if not self._svc: return
        subj = self._sd_subj.currentText()
        et   = self._exam_type()
        if not subj: return

        trend = self._svc.get_subject_trend(subj, et)

        # stats strip
        while self._sd_stats.count():
            w = self._sd_stats.takeAt(0).widget()
            if w: w.deleteLater()

        if trend:
            n  = len(trend)
            avg_net  = sum(r["net"] for r in trend) / n
            best_net = max(r["net"] for r in trend)
            last_net = trend[-1]["net"]
            change   = last_net - trend[0]["net"] if n > 1 else 0
            avg_pct  = sum(r["pct"] for r in trend) / n

            for label, value, color in [
                ("Sınav #",     str(n),               "#00BFA5"),
                ("Ort. Net",    f"{avg_net:.2f}",      "#FF9800"),
                ("En İyi Net",  f"{best_net:.2f}",     "#4CAF50"),
                ("Son Net",     f"{last_net:.2f}",     _col_net(last_net)),
                ("Değişim",     f"{change:+.2f}",      _col_net(change)),
                ("Ort. Başarı", f"{avg_pct:.1f}%",     _col_pct(avg_pct)),
            ]:
                card = QFrame()
                card.setStyleSheet(
                    f"background:#1E1E1E; border:1px solid {color}; border-radius:8px;")
                cl = QVBoxLayout(card)
                cl.setContentsMargins(10, 8, 10, 8)
                vl = QLabel(value)
                vl.setFont(QFont("Segoe UI", 15, QFont.Bold))
                vl.setStyleSheet(f"color:{color}; border:none; background:transparent;")
                cl.addWidget(vl)
                ll = QLabel(label)
                ll.setStyleSheet("color:#666; font-size:10px; border:none; background:transparent;")
                cl.addWidget(ll)
                self._sd_stats.addWidget(card)

        # line chart
        x_labels = [str(r["exam_date"])[:10] for r in trend]
        series = {
            "Net":    [r["net"]  for r in trend],
            "Doğru":  [float(r["correct"])  for r in trend],
            "% × 0.4": [r["pct"] * 0.4 for r in trend],   # scaled to compare
        }
        self._sd_line.set_data(series, x_labels, f"{subj} — Sınav Geçmişi")

        # topic table
        topic_avgs = self._svc.get_topic_averages_for_subject(subj, et)
        self._sd_topic_tbl.setRowCount(0)
        for ta in topic_avgs:
            r = self._sd_topic_tbl.rowCount(); self._sd_topic_tbl.insertRow(r)
            self._sd_topic_tbl.setItem(r, 0, QTableWidgetItem(ta["topic"]))
            self._sd_topic_tbl.setItem(r, 1, QTableWidgetItem(f"{ta['avg_c']:.1f}"))
            self._sd_topic_tbl.setItem(r, 2, QTableWidgetItem(f"{ta['avg_i']:.1f}"))
            ni = QTableWidgetItem(f"{ta['avg_net']:.2f}")
            ni.setForeground(QColor(_col_net(ta["avg_net"])))
            self._sd_topic_tbl.setItem(r, 3, ni)
            pi = QTableWidgetItem(f"{ta['pct']:.1f}%")
            pi.setForeground(QColor(_col_pct(ta["pct"])))
            self._sd_topic_tbl.setItem(r, 4, pi)
            status = "🟢 İyi" if ta["pct"] >= 70 else ("🟡 Orta" if ta["pct"] >= 45 else "🔴 Zayıf")
            self._sd_topic_tbl.setItem(r, 5, QTableWidgetItem(status))