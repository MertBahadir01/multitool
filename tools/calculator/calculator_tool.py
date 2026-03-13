"""Calculator Tool — DB-backed per-user history. Mirrors PasswordVaultTool pattern."""

import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeyEvent

from core.auth_manager import auth_manager
from tools.calculator.calculator_service import CalculatorService


# ── Button grid ────────────────────────────────────────────────────────────────
# Each row: list of (label, col_span, style_key)
BUTTON_ROWS = [
    [("AC", 1, "func"), ("±",  1, "func"), ("%",  1, "func"), ("÷", 1, "op")],
    [("7",  1, "num"),  ("8",  1, "num"),  ("9",  1, "num"),  ("×", 1, "op")],
    [("4",  1, "num"),  ("5",  1, "num"),  ("6",  1, "num"),  ("−", 1, "op")],
    [("1",  1, "num"),  ("2",  1, "num"),  ("3",  1, "num"),  ("+", 1, "op")],
    [("0",  2, "num"),  (".",  1, "num"),                     ("=", 1, "eq")],
]

STYLES = {
    "num":  ("#2D2D2D", "#3D3D3D", "#E0E0E0"),
    "func": ("#505050", "#606060", "#E0E0E0"),
    "op":   ("#00897B", "#00BFA5", "#ffffff"),
    "eq":   ("#00BFA5", "#26C6B0", "#000000"),
}

KEY_MAP = {
    Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2", Qt.Key_3: "3",
    Qt.Key_4: "4", Qt.Key_5: "5", Qt.Key_6: "6", Qt.Key_7: "7",
    Qt.Key_8: "8", Qt.Key_9: "9", Qt.Key_Period: ".", Qt.Key_Comma: ".",
    Qt.Key_Plus: "+", Qt.Key_Minus: "−", Qt.Key_Asterisk: "×",
    Qt.Key_Slash: "÷", Qt.Key_Return: "=", Qt.Key_Enter: "=",
    Qt.Key_Escape: "AC", Qt.Key_Percent: "%",
}


def _btn_css(kind):
    nb, hb, fg = STYLES[kind]
    return (f"QPushButton {{ background:{nb}; color:{fg}; border-radius:10px; "
            f"font-size:20px; font-weight:bold; border:none; }}"
            f"QPushButton:hover {{ background:{hb}; }}"
            f"QPushButton:pressed {{ background:#111111; }}")


class CalculatorTool(QWidget):
    name = "Calculator"
    description = "Calculator with per-user history"

    def __init__(self, parent=None):
        super().__init__(parent)
        user = auth_manager.current_user
        self._svc = CalculatorService(user["id"]) if user else None
        self._expr = ""
        self._result = ""
        self._new_num = False
        self._build_ui()
        self.setFocusPolicy(Qt.StrongFocus)
        self._load_history()

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(32, 32, 32, 32)
        main.setSpacing(24)

        # ── Left: keypad ───────────────────────────────────────────────────────
        calc_frame = QFrame()
        calc_frame.setFixedWidth(360)
        calc_frame.setStyleSheet("background:#1A1A1A; border-radius:20px;")
        c_lay = QVBoxLayout(calc_frame)
        c_lay.setContentsMargins(20, 20, 20, 20)
        c_lay.setSpacing(10)

        # Display
        disp = QFrame()
        disp.setStyleSheet("background:#111111; border-radius:12px;")
        d_lay = QVBoxLayout(disp)
        d_lay.setContentsMargins(16, 12, 16, 12)

        self.expr_lbl = QLabel("")
        self.expr_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.expr_lbl.setStyleSheet("color:#777777; font-size:14px;")
        self.expr_lbl.setWordWrap(True)
        d_lay.addWidget(self.expr_lbl)

        self.result_lbl = QLabel("0")
        self.result_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.result_lbl.setStyleSheet("color:#E0E0E0; font-size:38px; font-weight:bold;")
        self.result_lbl.setMinimumHeight(60)
        d_lay.addWidget(self.result_lbl)

        c_lay.addWidget(disp)

        # Buttons
        for row in BUTTON_ROWS:
            row_lay = QHBoxLayout()
            row_lay.setSpacing(10)
            for cell in row:
                label, span, kind = cell
                btn = QPushButton(label)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn.setFixedHeight(70)
                btn.setStyleSheet(_btn_css(kind))
                row_lay.addWidget(btn, span)
                btn.clicked.connect(lambda _checked, l=label: self._on_button(l))
            c_lay.addLayout(row_lay)

        main.addWidget(calc_frame)

        # ── Right: history ─────────────────────────────────────────────────────
        hist_frame = QFrame()
        hist_frame.setStyleSheet("background:#1A1A1A; border-radius:20px;")
        h_lay = QVBoxLayout(hist_frame)
        h_lay.setContentsMargins(20, 20, 20, 20)
        h_lay.setSpacing(12)

        hdr = QHBoxLayout()
        h_title = QLabel("🕘  History")
        h_title.setStyleSheet("font-size:16px; font-weight:bold; color:#E0E0E0;")
        hdr.addWidget(h_title)
        hdr.addStretch()

        clr_btn = QPushButton("Clear All")
        clr_btn.setFixedSize(80, 28)
        clr_btn.setObjectName("secondary")
        clr_btn.clicked.connect(self._clear_history)
        hdr.addWidget(clr_btn)
        h_lay.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        self.hist_container = QWidget()
        self.hist_container.setStyleSheet("background:transparent;")
        self.hist_vlay = QVBoxLayout(self.hist_container)
        self.hist_vlay.setContentsMargins(0, 0, 0, 0)
        self.hist_vlay.setSpacing(8)
        self.hist_vlay.addStretch()

        scroll.setWidget(self.hist_container)
        h_lay.addWidget(scroll, 1)
        main.addWidget(hist_frame, 1)

    # ── History ────────────────────────────────────────────────────────────────
    def _load_history(self):
        if not self._svc:
            return
        # clear all rows except the trailing stretch
        while self.hist_vlay.count() > 1:
            item = self.hist_vlay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for entry in self._svc.get_history():
            self._add_history_row(
                entry["expression"], entry["result"],
                str(entry.get("created_at", ""))[:16]
            )

    def _add_history_row(self, expression, result, timestamp):
        row_frame = QFrame()
        row_frame.setStyleSheet(
            "QFrame { background:#252525; border-radius:8px; }"
            "QFrame:hover { background:#2D2D2D; }"
        )
        row_frame.setCursor(Qt.PointingHandCursor)

        rl = QVBoxLayout(row_frame)
        rl.setContentsMargins(12, 8, 12, 8)
        rl.setSpacing(2)

        expr_lbl = QLabel(f"{expression} = {result}")
        expr_lbl.setStyleSheet("color:#C0C0C0; font-size:13px;")
        expr_lbl.setWordWrap(True)
        rl.addWidget(expr_lbl)

        ts_lbl = QLabel(timestamp)
        ts_lbl.setStyleSheet("color:#555555; font-size:10px;")
        rl.addWidget(ts_lbl)

        clean = result.replace(",", "")
        row_frame.mousePressEvent = lambda e, r=clean: self._reuse(r)

        # Insert before the trailing stretch (index count-1)
        self.hist_vlay.insertWidget(self.hist_vlay.count() - 1, row_frame)

    def _clear_history(self):
        if not self._svc:
            return
        if QMessageBox.question(self, "Clear History", "Delete all history?",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._svc.clear_history()
        while self.hist_vlay.count() > 1:
            item = self.hist_vlay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _reuse(self, value: str):
        self._expr = value
        self._result = value
        self._new_num = False
        self._update_display(value, "reused ↑")

    # ── Calculator logic ───────────────────────────────────────────────────────
    def _on_button(self, label: str):
        if label == "AC":
            self._expr = ""
            self._result = ""
            self._new_num = False
            self._update_display("0", "")
            return

        if label == "±":
            if self._result:
                try:
                    val = -float(self._result.replace(",", ""))
                    self._result = self._fmt(val)
                    self._expr = self._result
                    self._update_display(self._result, "")
                except Exception:
                    pass
            return

        if label == "%":
            if self._result:
                try:
                    val = float(self._result.replace(",", "")) / 100
                    self._result = self._fmt(val)
                    self._expr = self._result
                    self._update_display(self._result, "")
                except Exception:
                    pass
            return

        if label == "=":
            if not self._expr:
                return
            try:
                raw = self._expr
                for sym, ch in {"÷": "/", "×": "*", "−": "-"}.items():
                    raw = raw.replace(sym, ch)
                val = eval(raw, {"__builtins__": {}},
                           {"sqrt": math.sqrt, "pi": math.pi, "e": math.e})
                result_str = self._fmt(val)
                if self._svc:
                    self._svc.add_entry(self._expr, result_str)
                    self._load_history()
                self._result = result_str
                self._update_display(result_str, self._expr + " =")
                self._new_num = True
            except Exception:
                self._update_display("Error", self._expr)
                self._expr = ""
            return

        if label in ("÷", "×", "+", "−"):
            if self._expr and self._expr[-1] in "÷×+−":
                self._expr = self._expr[:-1]
            if self._result and not self._expr:
                self._expr = self._result.replace(",", "")
            self._expr += label
            self._new_num = False
            self._update_display(self._expr, "")
            return

        # digit or dot
        if self._new_num:
            self._expr = label
            self._result = label
            self._new_num = False
        else:
            self._expr += label
            self._result = label
        self._update_display(self._expr, "")

    def _update_display(self, main_txt, sub_txt):
        self.result_lbl.setText(main_txt)
        self.expr_lbl.setText(sub_txt)

    @staticmethod
    def _fmt(val) -> str:
        if isinstance(val, float) and val.is_integer():
            v = int(val)
            return f"{v:,}" if abs(v) < 1_000_000_000_000_000 else str(v)
        return f"{val:,.10g}"

    # ── Keyboard ───────────────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Backspace:
            self._expr = self._expr[:-1] if self._expr else ""
            self._update_display(self._expr or "0", "")
            return
        label = KEY_MAP.get(event.key())
        if label:
            self._on_button(label)
        else:
            super().keyPressEvent(event)