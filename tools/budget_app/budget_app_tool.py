"""
Budget App — layout v3

New layout (top→bottom, full width at every level):

  ┌──────────────────────────────────────────────────────────────────┐
  │  HEADER  📊 Budget App          Period: [This Month ▾]   [↺]    │  48 px
  ├──────────────────────────────────────────────────────────────────┤
  │  KPI  │ Total Budget │ Total Spent │ Remaining │ Over Budget │   │  60 px
  ├─────────────────────────────┬────────────────────────────────────┤
  │  SET BUDGET (left half)     │  QUICK ADD EXPENSE (right half)    │  ~120 px fixed
  │  Category [  ] Limit [  ]   │  Amount [  ] Cat [  ] Note [  ]    │
  │  [💾 Save]   [🗑 Remove]     │  Date [  ]   [➕ Add Expense]      │
  ├─────────────────────────────┴────────────────────────────────────┤
  │  Category Spending vs Budget  (scrollable, fills remaining space) │  stretch
  │  ┌ Food ─────────────────── ₺684/₺1,000 ──────────────┐          │
  │  │ ████████████████████░░░░░░░░░░  68%                 │          │
  └──┴─────────────────────────────────────────────────────┘──────────┘

All colours set via QPalette on QWidget/QFrame — no stylesheet inheritance.
Stylesheets used ONLY on leaf input widgets (QComboBox, QSpinBox, etc.)
and isolated buttons where no children exist.
"""

import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QDoubleSpinBox, QComboBox,
    QScrollArea, QLineEdit, QDateEdit, QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

from core.auth_manager import auth_manager
from tools.finance_service.finance_service import (
    BudgetService, TransactionService,
    finance_bus, EVT_TRANSACTION, EVT_BUDGET,
)
from tools.finance_service.finance_base import (
    TEAL, ORANGE, RED, GREEN, CARD, fmt_currency,
)

# ── Palette ────────────────────────────────────────────────────────────────────
BG       = "#111111"
SURFACE  = "#1A1A1A"
SURFACE2 = "#212121"
BORDER   = "#2A2A2A"
BORDER_B = "#363636"
TEXT1    = "#ECECEC"
TEXT2    = "#7A7A7A"
TEXT3    = "#404040"

CATEGORIES = [
    "Food", "Transport", "Rent", "Bills", "Health",
    "Entertainment", "Clothing", "Education", "Shopping",
    "Subscriptions", "Savings", "Other",
]
PERIOD_OPTS = ["This Month", "Last Month", "Last 3 Months", "This Year"]


# ══════════════════════════════════════════════════════════════════════════════
# Pure helpers — no stylesheet leakage
# ══════════════════════════════════════════════════════════════════════════════

def _pal_widget(widget: QWidget, bg: str) -> QWidget:
    """Set background via QPalette — doesn't affect children."""
    widget.setAutoFillBackground(True)
    p = widget.palette()
    p.setColor(QPalette.Window, QColor(bg))
    widget.setPalette(p)
    return widget


def _lbl(text: str, color: str = TEXT1, pt: int = 10,
         bold: bool = False, italic: bool = False,
         align=Qt.AlignLeft | Qt.AlignVCenter) -> QLabel:
    """QLabel coloured via QPalette — never inherits parent stylesheet."""
    w = QLabel(text)
    f = QFont("Segoe UI", pt)
    f.setBold(bold)
    f.setItalic(italic)
    w.setFont(f)
    w.setAlignment(align)
    p = w.palette()
    p.setColor(QPalette.WindowText, QColor(color))
    w.setPalette(p)
    w.setAutoFillBackground(False)
    return w


def _rule(horizontal: bool = True) -> QFrame:
    """1 px divider line."""
    line = QFrame()
    line.setFrameShape(QFrame.HLine if horizontal else QFrame.VLine)
    line.setFrameShadow(QFrame.Plain)
    line.setFixedHeight(1) if horizontal else line.setFixedWidth(1)
    _pal_widget(line, BORDER)
    return line


def _inp(widget: QWidget, h: int = 28) -> QWidget:
    """Style a leaf input widget. Safe — widget has no styled children."""
    widget.setFixedHeight(h)
    widget.setStyleSheet(
        f"background:{SURFACE2}; border:1px solid {BORDER_B};"
        f"border-radius:4px; padding:0 7px;"
        f"color:{TEXT1}; font-size:9pt;"
        # sub-controls
        "QComboBox::drop-down{border:none;width:18px;}"
        "QDateEdit::drop-down{border:none;width:18px;}"
        "QAbstractSpinBox::up-button{width:14px;border:none;}"
        "QAbstractSpinBox::down-button{width:14px;border:none;}"
    )
    return widget


def _btn(text: str, bg: str, fg: str = TEXT1, h: int = 30) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(h)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{bg};color:{fg};border:none;"
        f"border-radius:5px;font-size:9pt;font-weight:bold;}}"
        f"QPushButton:hover{{background:{bg}CC;}}"
        f"QPushButton:pressed{{background:{bg}88;}}"
    )
    return b


def _section_title(text: str) -> QLabel:
    return _lbl(text, color=TEXT1, pt=9, bold=True)


def _caption(text: str) -> QLabel:
    return _lbl(text, color=TEXT2, pt=8)


def _period_dates(period: str):
    today = datetime.date.today()
    if period == "This Month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if period == "Last Month":
        last = today.replace(day=1) - datetime.timedelta(days=1)
        return last.replace(day=1).isoformat(), last.isoformat()
    if period == "Last 3 Months":
        start = (today.replace(day=1) - datetime.timedelta(days=60)).replace(day=1)
        return start.isoformat(), today.isoformat()
    return today.replace(month=1, day=1).isoformat(), today.isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# KPI tile
# ══════════════════════════════════════════════════════════════════════════════

class _KpiTile(QWidget):
    def __init__(self, label: str, value: str, accent: str, parent=None):
        super().__init__(parent)
        _pal_widget(self, SURFACE)
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 3 px accent strip
        strip = QFrame()
        strip.setFixedWidth(3)
        _pal_widget(strip, accent)
        lay.addWidget(strip)

        text = QVBoxLayout()
        text.setContentsMargins(10, 7, 10, 7)
        text.setSpacing(1)

        self._v = _lbl(value, color=accent, pt=13, bold=True)
        self._l = _lbl(label, color=TEXT2, pt=8)
        text.addWidget(self._v)
        text.addWidget(self._l)
        lay.addLayout(text)

    def set_value(self, v: str):
        self._v.setText(v)


# ══════════════════════════════════════════════════════════════════════════════
# Budget row
# ══════════════════════════════════════════════════════════════════════════════

class _BudgetRow(QWidget):
    def __init__(self, cat: str, spent: float, limit: float, parent=None):
        super().__init__(parent)
        _pal_widget(self, SURFACE)
        self.setFixedHeight(68)

        pct       = min(int(spent / limit * 100), 100) if limit else 0
        remaining = limit - spent
        over      = remaining < 0
        color     = GREEN if pct < 70 else (ORANGE if pct < 90 else RED)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 9, 14, 9)
        root.setSpacing(4)

        # Row 1: name ←→ amounts
        r1 = QHBoxLayout()
        r1.setSpacing(0)
        r1.addWidget(_lbl(cat, color=TEXT1, pt=10, bold=True))
        r1.addStretch()
        r1.addWidget(_lbl(
            f"{fmt_currency(spent)}  /  {fmt_currency(limit)}",
            color=color, pt=9, align=Qt.AlignRight | Qt.AlignVCenter,
        ))
        root.addLayout(r1)

        # Progress bar — stylesheet safe here (no label children)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(pct)
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(
            f"QProgressBar{{background:#252525;border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:2px;}}"
        )
        root.addWidget(bar)

        # Row 2: remaining ←→ pct
        r2 = QHBoxLayout()
        r2.setSpacing(0)
        if over:
            r2.addWidget(_lbl(
                f"⚠  Over by {fmt_currency(abs(remaining))}",
                color=RED, pt=8,
            ))
        else:
            r2.addWidget(_lbl(
                f"Remaining: {fmt_currency(remaining)}  ({100-pct}% left)",
                color=TEXT3, pt=8,
            ))
        r2.addStretch()
        r2.addWidget(_lbl(
            f"{pct}%", color=color, pt=8,
            align=Qt.AlignRight | Qt.AlignVCenter,
        ))
        root.addLayout(r2)


# ══════════════════════════════════════════════════════════════════════════════
# Main widget
# ══════════════════════════════════════════════════════════════════════════════

class BudgetAppTool(QWidget):
    name        = "Budget App"
    description = "Set category limits — see live spending and log expenses"

    def __init__(self, parent=None):
        super().__init__(parent)

        u = auth_manager.current_user
        self._uid   = u["id"] if u else None
        self._svc_b = BudgetService(self._uid)      if self._uid else None
        self._svc_t = TransactionService(self._uid) if self._uid else None
        self._period = "This Month"

        self._ok_timer = QTimer(self)
        self._ok_timer.setSingleShot(True)
        self._ok_timer.timeout.connect(lambda: self._status_lbl.setText(""))

        _pal_widget(self, BG)
        self._build()

        if self._uid:
            self._refresh()
            finance_bus.subscribe(self._on_bus)

    def _on_bus(self, event: str):
        if event in (EVT_TRANSACTION, EVT_BUDGET):
            self._refresh()

    # ══════════════════════════════════════════════════════════════════════════
    # Build
    # ══════════════════════════════════════════════════════════════════════════

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._mk_header())           # ① header bar
        root.addWidget(_rule())
        root.addWidget(self._mk_kpi_strip())        # ② KPI row
        root.addWidget(_rule())
        root.addWidget(self._mk_action_bar())       # ③ set-budget | quick-add  (side by side)
        root.addWidget(_rule())
        root.addWidget(self._mk_bars_area(), 1)     # ④ budget bars (stretches to fill)

    # ── ① Header ──────────────────────────────────────────────────────────────

    def _mk_header(self) -> QWidget:
        w = QWidget()
        _pal_widget(w, SURFACE)
        w.setFixedHeight(46)

        lay = QHBoxLayout(w)
        lay.setContentsMargins(18, 0, 14, 0)
        lay.setSpacing(8)

        lay.addWidget(_lbl("📊", pt=13))
        lay.addWidget(_lbl("Budget App", color=TEXT1, pt=11, bold=True))
        lay.addStretch()
        lay.addWidget(_lbl("Period:", color=TEXT2, pt=9))

        self._period_cb = QComboBox()
        self._period_cb.addItems(PERIOD_OPTS)
        self._period_cb.setFixedHeight(28)
        self._period_cb.setFixedWidth(130)
        self._period_cb.setStyleSheet(
            f"QComboBox{{background:{SURFACE2};border:1px solid {BORDER_B};"
            f"border-radius:4px;padding:0 7px;color:{TEXT1};font-size:9pt;}}"
            "QComboBox::drop-down{border:none;width:18px;}"
            f"QComboBox QAbstractItemView{{background:{SURFACE2};color:{TEXT1};"
            f"selection-background-color:{BORDER_B};}}"
        )
        self._period_cb.currentTextChanged.connect(self._on_period)
        lay.addWidget(self._period_cb)

        ref = _btn("↺", TEAL, "#000", h=28)
        ref.setFixedWidth(32)
        ref.clicked.connect(self._refresh)
        lay.addWidget(ref)
        return w

    # ── ② KPI strip ───────────────────────────────────────────────────────────

    def _mk_kpi_strip(self) -> QWidget:
        w = QWidget()
        _pal_widget(w, BG)
        w.setFixedHeight(60)

        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 4, 14, 4)
        lay.setSpacing(6)

        self._k_budget = _KpiTile("Total Budget",  "₺0",           TEAL)
        self._k_spent  = _KpiTile("Total Spent",   "₺0",           RED)
        self._k_remain = _KpiTile("Remaining",     "₺0",           GREEN)
        self._k_over   = _KpiTile("Over Budget",   "0 categories", ORANGE)

        for t in (self._k_budget, self._k_spent, self._k_remain, self._k_over):
            lay.addWidget(t)
        return w

    # ── ③ Action bar (Set Budget LEFT | Quick Add RIGHT) ──────────────────────

    def _mk_action_bar(self) -> QWidget:
        """
        Full-width strip split 50/50.
        Left  → Set Budget  (category, limit, save, remove)
        Right → Quick Add   (amount, category, note, date, add)
        Both panels are always fully visible — no scroll needed.
        """
        bar = QWidget()
        _pal_widget(bar, BG)

        outer = QHBoxLayout(bar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._mk_set_budget_panel(), 1)
        outer.addWidget(_rule(horizontal=False))        # vertical divider
        outer.addWidget(self._mk_quick_add_panel(), 1)

        return bar

    def _mk_set_budget_panel(self) -> QWidget:
        p = QWidget()
        _pal_widget(p, SURFACE)

        lay = QVBoxLayout(p)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(5)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.addWidget(_lbl("📋", pt=10))
        title_row.addWidget(_section_title("Set Budget Limit"))
        title_row.addStretch()
        lay.addLayout(title_row)

        # Inputs row — category + limit side by side
        inp_row = QHBoxLayout()
        inp_row.setSpacing(8)

        col1 = QVBoxLayout()
        col1.setSpacing(3)
        col1.addWidget(_caption("Category"))
        self._bcat_cb = QComboBox()
        self._bcat_cb.addItems(CATEGORIES)
        self._bcat_cb.setEditable(True)
        _inp(self._bcat_cb)
        col1.addWidget(self._bcat_cb)
        inp_row.addLayout(col1, 3)

        col2 = QVBoxLayout()
        col2.setSpacing(3)
        col2.addWidget(_caption("Monthly Limit (₺)"))
        self._blimit = QDoubleSpinBox()
        self._blimit.setRange(1, 9_999_999)
        self._blimit.setDecimals(2)
        self._blimit.setValue(1000)
        _inp(self._blimit)
        col2.addWidget(self._blimit)
        inp_row.addLayout(col2, 2)

        lay.addLayout(inp_row)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        save = _btn("💾  Save Budget", TEAL, "#000", h=28)
        save.clicked.connect(self._save_budget)
        btn_row.addWidget(save, 3)

        self._del_cb = QComboBox()
        _inp(self._del_cb)
        btn_row.addWidget(self._del_cb, 2)

        del_b = _btn("🗑", SURFACE2, RED, h=28)
        del_b.setFixedWidth(32)
        del_b.setToolTip("Remove selected budget")
        del_b.setStyleSheet(
            del_b.styleSheet() +
            f"QPushButton{{border:1px solid {BORDER_B};}}"
        )
        del_b.clicked.connect(self._delete_budget)
        btn_row.addWidget(del_b)

        lay.addLayout(btn_row)
        return p

    def _mk_quick_add_panel(self) -> QWidget:
        p = QWidget()
        _pal_widget(p, SURFACE2)

        lay = QVBoxLayout(p)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(5)

        # Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title_row.addWidget(_lbl("➕", pt=10))
        title_row.addWidget(_section_title("Quick Add Expense"))
        title_row.addStretch()
        lay.addLayout(title_row)

        # Inputs row 1 — amount + category
        r1 = QHBoxLayout()
        r1.setSpacing(8)

        c1 = QVBoxLayout(); c1.setSpacing(3)
        c1.addWidget(_caption("Amount (₺)"))
        self._eamt = QDoubleSpinBox()
        self._eamt.setRange(0.01, 9_999_999)
        self._eamt.setDecimals(2)
        self._eamt.setValue(100)
        _inp(self._eamt)
        c1.addWidget(self._eamt)
        r1.addLayout(c1, 2)

        c2 = QVBoxLayout(); c2.setSpacing(3)
        c2.addWidget(_caption("Category"))
        self._ecat_cb = QComboBox()
        self._ecat_cb.addItems(CATEGORIES)
        self._ecat_cb.setEditable(True)
        _inp(self._ecat_cb)
        c2.addWidget(self._ecat_cb)
        r1.addLayout(c2, 3)

        lay.addLayout(r1)

        # Inputs row 2 — note + date + button
        r2 = QHBoxLayout()
        r2.setSpacing(8)

        c3 = QVBoxLayout(); c3.setSpacing(3)
        c3.addWidget(_caption("Note (optional)"))
        self._enote = QLineEdit()
        self._enote.setPlaceholderText("e.g. Grocery run")
        _inp(self._enote)
        c3.addWidget(self._enote)
        r2.addLayout(c3, 3)

        c4 = QVBoxLayout(); c4.setSpacing(3)
        c4.addWidget(_caption("Date"))
        self._edate = QDateEdit()
        self._edate.setCalendarPopup(True)
        self._edate.setDate(QDate.currentDate())
        _inp(self._edate)
        c4.addWidget(self._edate)
        r2.addLayout(c4, 2)

        # Add button aligned to bottom of row
        add = _btn("➕  Add", RED, h=28)
        add.setMinimumWidth(70)
        add.clicked.connect(self._add_expense)
        btn_col = QVBoxLayout(); btn_col.setSpacing(3)
        btn_col.addWidget(_caption(""))  # spacer label to align with inputs
        btn_col.addWidget(add)
        r2.addLayout(btn_col, 0)

        lay.addLayout(r2)

        # Status
        self._status_lbl = QLabel("")
        self._status_lbl.setFont(QFont("Segoe UI", 8))
        self._status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._status_lbl.setWordWrap(False)
        sp = self._status_lbl.palette()
        sp.setColor(QPalette.WindowText, QColor(GREEN))
        self._status_lbl.setPalette(sp)
        self._status_lbl.setAutoFillBackground(False)
        lay.addWidget(self._status_lbl)

        return p

    # ── ④ Budget bars ─────────────────────────────────────────────────────────

    def _mk_bars_area(self) -> QWidget:
        w = QWidget()
        _pal_widget(w, BG)

        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        lay.addWidget(_lbl(
            "Category Spending vs Budget", color=TEXT2, pt=9,
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            f"QScrollBar:vertical{{background:{SURFACE};width:5px;border-radius:2px;}}"
            f"QScrollBar::handle:vertical{{background:{BORDER_B};border-radius:2px;min-height:20px;}}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        self._bars_inner = QWidget()
        _pal_widget(self._bars_inner, BG)
        self._bars_lay = QVBoxLayout(self._bars_inner)
        self._bars_lay.setContentsMargins(0, 0, 4, 0)
        self._bars_lay.setSpacing(5)

        scroll.setWidget(self._bars_inner)
        lay.addWidget(scroll, 1)
        return w

    # ══════════════════════════════════════════════════════════════════════════
    # Actions
    # ══════════════════════════════════════════════════════════════════════════

    def _on_period(self, text: str):
        self._period = text
        self._refresh()

    def _save_budget(self):
        if not self._svc_b:
            return
        self._svc_b.set_budget(self._bcat_cb.currentText(), self._blimit.value())
        finance_bus.emit_event(EVT_BUDGET)

    def _delete_budget(self):
        if not self._svc_b:
            return
        cat = self._del_cb.currentText()
        for b in self._svc_b.get_budgets():
            if b["category"] == cat:
                self._svc_b.delete_budget(b["id"])
                break
        finance_bus.emit_event(EVT_BUDGET)

    def _add_expense(self):
        if not self._svc_t:
            return
        amount   = self._eamt.value()
        category = self._ecat_cb.currentText()
        note     = self._enote.text().strip()
        date_str = self._edate.date().toString("yyyy-MM-dd")
        self._svc_t.add(amount, category, note, "expense", date_str)
        self._enote.clear()
        self._status_lbl.setText(f"✅  {fmt_currency(amount)} → {category}")
        self._ok_timer.start(4000)
        finance_bus.emit_event(EVT_TRANSACTION)

    # ══════════════════════════════════════════════════════════════════════════
    # Refresh
    # ══════════════════════════════════════════════════════════════════════════

    def _refresh(self):
        if not self._svc_b:
            return

        from_date, to_date = _period_dates(self._period)
        budgets   = self._svc_b.get_budgets()
        spent_map = {}
        if self._svc_t:
            spent_map = self._svc_t.totals_by_category(
                "expense", from_date=from_date, to_date=to_date,
            )

        total_budget = sum(b["amount"] for b in budgets)
        total_spent  = sum(spent_map.get(b["category"], 0) for b in budgets)
        remaining    = total_budget - total_spent
        over_count   = sum(
            1 for b in budgets
            if spent_map.get(b["category"], 0) > b["amount"]
        )

        self._k_budget.set_value(fmt_currency(total_budget))
        self._k_spent.set_value(fmt_currency(total_spent))
        self._k_remain.set_value(fmt_currency(remaining))
        self._k_over.set_value(
            f"{over_count} categor{'y' if over_count == 1 else 'ies'}"
        )

        self._del_cb.clear()
        self._del_cb.addItems([b["category"] for b in budgets])

        # Rebuild rows
        while self._bars_lay.count():
            item = self._bars_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not budgets:
            msg = _lbl(
                "No budgets set yet — use Set Budget Limit above.",
                color=TEXT3, pt=10,
                align=Qt.AlignCenter | Qt.AlignVCenter,
            )
            msg.setWordWrap(True)
            self._bars_lay.addStretch()
            self._bars_lay.addWidget(msg)
            self._bars_lay.addStretch()
            return

        def _key(b):
            s = spent_map.get(b["category"], 0)
            return -(s / b["amount"] * 100 if b["amount"] else 0)

        for b in sorted(budgets, key=_key):
            cat   = b["category"]
            spent = spent_map.get(cat, 0)
            self._bars_lay.addWidget(_BudgetRow(cat, spent, b["amount"]))

        budgeted = {b["category"] for b in budgets}
        for cat, spent in sorted(spent_map.items(), key=lambda x: -x[1]):
            if cat not in budgeted and spent > 0:
                ghost = QWidget()
                _pal_widget(ghost, SURFACE)
                ghost.setFixedHeight(40)
                gl = QHBoxLayout(ghost)
                gl.setContentsMargins(14, 0, 14, 0)
                gl.addWidget(_lbl(cat, color=TEXT2, pt=9))
                gl.addStretch()
                gl.addWidget(_lbl(
                    f"{fmt_currency(spent)} — no budget set",
                    color=TEXT3, pt=9, italic=True,
                    align=Qt.AlignRight | Qt.AlignVCenter,
                ))
                self._bars_lay.addWidget(ghost)

        self._bars_lay.addStretch()
