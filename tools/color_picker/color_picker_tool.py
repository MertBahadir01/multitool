"""Color Picker + Palette Generator — HEX/RGB/HSL conversion and palette generation."""
import colorsys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QSlider, QGridLayout, QApplication,
    QColorDialog, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QBrush


# ── Color math helpers ────────────────────────────────────────────────────────

def rgb_to_hsl(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
    return round(h*360), round(s*100), round(l*100)

def hsl_to_rgb(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h/360, l/100, s/100)
    return int(r*255), int(g*255), int(b*255)

def hex_to_rgb(hex_str):
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"

def complementary(h, s, l):
    return [((h + 180) % 360, s, l)]

def analogous(h, s, l):
    return [((h + 30) % 360, s, l), ((h - 30) % 360, s, l)]

def triadic(h, s, l):
    return [((h + 120) % 360, s, l), ((h + 240) % 360, s, l)]

def split_complementary(h, s, l):
    return [((h + 150) % 360, s, l), ((h + 210) % 360, s, l)]

def tetradic(h, s, l):
    return [((h + 90) % 360, s, l), ((h + 180) % 360, s, l), ((h + 270) % 360, s, l)]

def shades(h, s, l):
    return [(h, s, max(0, l - 20)), (h, s, max(0, l - 40)),
            (h, s, min(100, l + 20)), (h, s, min(100, l + 40))]

PALETTES = {
    "Complementary": complementary,
    "Analogous":     analogous,
    "Triadic":       triadic,
    "Split-Comp":    split_complementary,
    "Tetradic":      tetradic,
    "Shades":        shades,
}


# ── Color swatch ──────────────────────────────────────────────────────────────

class _Swatch(QFrame):
    clicked = Signal(str)  # hex color

    def __init__(self, hex_color="#000000", size=64, parent=None):
        super().__init__(parent)
        self._hex = hex_color
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            f"QFrame{{background:{self._hex};border-radius:8px;"
            f"border:2px solid rgba(255,255,255,0.1);}}"
            f"QFrame:hover{{border:2px solid #00BFA5;}}")

    def set_color(self, hex_color):
        self._hex = hex_color; self._apply()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self._hex)
            QApplication.clipboard().setText(self._hex)


class ColorPickerTool(QWidget):
    name        = "Color Picker"
    description = "Pick colors, convert formats, generate palettes"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#00BFA5")
        self._updating = False
        self._build_ui()
        self._update_all(self._color)

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 14, 24, 14)
        t = QLabel("🎨 Color Picker"); t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;"); hl.addWidget(t); hl.addStretch()
        root.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#151515;}")
        content = QWidget(); content.setStyleSheet("background:#151515;")
        cl = QVBoxLayout(content); cl.setContentsMargins(24, 20, 24, 20); cl.setSpacing(20)

        # ── Top: picker + preview ─────────────────────────────────────────────
        top = QHBoxLayout(); top.setSpacing(24)

        # Big color preview + picker button
        left = QVBoxLayout(); left.setSpacing(10)
        self._preview = _Swatch("#00BFA5", 120)
        left.addWidget(self._preview, 0, Qt.AlignCenter)
        pick_btn = QPushButton("🎨  Choose Color")
        pick_btn.setFixedHeight(36)
        pick_btn.setStyleSheet(
            "background:#00BFA5;color:#000;border:none;border-radius:7px;"
            "font-weight:bold;font-size:13px;")
        pick_btn.clicked.connect(self._pick_dialog)
        left.addWidget(pick_btn)
        left.addWidget(QLabel("Click swatch to copy HEX",
                              styleSheet="color:#555;font-size:11px;"), 0, Qt.AlignCenter)
        top.addLayout(left)

        # Format inputs
        fmt = QGridLayout(); fmt.setSpacing(10); fmt.setColumnMinimumWidth(1, 160)

        fmt.addWidget(QLabel("HEX:", styleSheet="color:#888;font-size:13px;"), 0, 0)
        self._hex_edit = QLineEdit()
        self._hex_edit.setPlaceholderText("#RRGGBB")
        self._hex_edit.setFixedWidth(160); self._hex_edit.setStyleSheet(self._inp())
        self._hex_edit.textChanged.connect(self._on_hex_changed)
        fmt.addWidget(self._hex_edit, 0, 1)
        copy_hex = self._copy_btn(lambda: self._hex_edit.text())
        fmt.addWidget(copy_hex, 0, 2)

        fmt.addWidget(QLabel("RGB:", styleSheet="color:#888;font-size:13px;"), 1, 0)
        self._rgb_edit = QLineEdit(); self._rgb_edit.setReadOnly(True)
        self._rgb_edit.setFixedWidth(160); self._rgb_edit.setStyleSheet(self._inp())
        fmt.addWidget(self._rgb_edit, 1, 1)
        fmt.addWidget(self._copy_btn(lambda: self._rgb_edit.text()), 1, 2)

        fmt.addWidget(QLabel("HSL:", styleSheet="color:#888;font-size:13px;"), 2, 0)
        self._hsl_edit = QLineEdit(); self._hsl_edit.setReadOnly(True)
        self._hsl_edit.setFixedWidth(160); self._hsl_edit.setStyleSheet(self._inp())
        fmt.addWidget(self._hsl_edit, 2, 1)
        fmt.addWidget(self._copy_btn(lambda: self._hsl_edit.text()), 2, 2)

        fmt.addWidget(QLabel("CSS:", styleSheet="color:#888;font-size:13px;"), 3, 0)
        self._css_edit = QLineEdit(); self._css_edit.setReadOnly(True)
        self._css_edit.setFixedWidth(200); self._css_edit.setStyleSheet(self._inp())
        fmt.addWidget(self._css_edit, 3, 1)
        fmt.addWidget(self._copy_btn(lambda: self._css_edit.text()), 3, 2)
        top.addLayout(fmt)

        # RGB sliders
        sliders = QVBoxLayout(); sliders.setSpacing(8)
        self._r_slider = self._make_slider("R", 255, "#F44336", sliders)
        self._g_slider = self._make_slider("G", 255, "#4CAF50", sliders)
        self._b_slider = self._make_slider("B", 255, "#2196F3", sliders)
        top.addLayout(sliders)
        top.addStretch()
        cl.addLayout(top)

        # ── Palette section ───────────────────────────────────────────────────
        pal_lbl = QLabel("🎨 Color Palettes")
        pal_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        pal_lbl.setStyleSheet("color:#888;")
        cl.addWidget(pal_lbl)

        self._palette_rows = {}
        for name in PALETTES:
            row_frame = QFrame()
            row_frame.setStyleSheet("background:#1A1A1A;border-radius:8px;")
            rl = QHBoxLayout(row_frame); rl.setContentsMargins(12, 10, 12, 10); rl.setSpacing(8)
            rl.addWidget(QLabel(name, styleSheet=f"color:#888;font-size:12px;min-width:110px;"))
            swatches = []
            for _ in range(5):
                sw = _Swatch("#333333", 48)
                sw.clicked.connect(lambda hex_, e=self._hex_edit: (e.setText(hex_),))
                rl.addWidget(sw)
                swatches.append(sw)
            rl.addStretch()
            cl.addWidget(row_frame)
            self._palette_rows[name] = swatches

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    def _inp(self):
        return ("background:#252525;border:1px solid #3E3E3E;border-radius:6px;"
                "padding:5px 10px;color:#E0E0E0;font-size:13px;")

    def _copy_btn(self, get_text):
        btn = QPushButton("📋")
        btn.setFixedSize(32, 32)
        btn.setStyleSheet("background:#252525;color:#888;border:none;border-radius:5px;font-size:13px;")
        btn.clicked.connect(lambda: QApplication.clipboard().setText(get_text()))
        return btn

    def _make_slider(self, label, max_val, color, parent_layout):
        row = QHBoxLayout()
        row.addWidget(QLabel(label, styleSheet=f"color:{color};font-size:12px;min-width:14px;"))
        sl = QSlider(Qt.Horizontal)
        sl.setRange(0, max_val); sl.setValue(0)
        sl.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background:#252525; height:6px; border-radius:3px; }}
            QSlider::handle:horizontal {{ background:{color}; width:14px; height:14px;
                margin:-4px 0; border-radius:7px; }}
            QSlider::sub-page:horizontal {{ background:{color}; border-radius:3px; }}
        """)
        sl.valueChanged.connect(self._on_slider_changed)
        val_lbl = QLabel("0"); val_lbl.setFixedWidth(30)
        val_lbl.setStyleSheet("color:#555;font-size:11px;")
        sl.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
        row.addWidget(sl); row.addWidget(val_lbl)
        parent_layout.addLayout(row)
        return sl

    def _pick_dialog(self):
        c = QColorDialog.getColor(self._color, self, "Choose Color")
        if c.isValid():
            self._update_all(c)

    def _on_hex_changed(self, text):
        if self._updating: return
        text = text.strip()
        if not text.startswith("#"): text = "#" + text
        if len(text) == 7:
            try:
                c = QColor(text)
                if c.isValid(): self._update_all(c, skip_hex=True)
            except Exception: pass

    def _on_slider_changed(self):
        if self._updating: return
        r = self._r_slider.value(); g = self._g_slider.value(); b = self._b_slider.value()
        self._update_all(QColor(r, g, b), skip_sliders=True)

    def _update_all(self, color: QColor, skip_hex=False, skip_sliders=False):
        self._updating = True
        self._color = color
        r, g, b = color.red(), color.green(), color.blue()
        h, s, l  = rgb_to_hsl(r, g, b)
        hex_str  = rgb_to_hex(r, g, b)

        self._preview.set_color(hex_str)
        if not skip_hex:   self._hex_edit.setText(hex_str)
        self._rgb_edit.setText(f"rgb({r}, {g}, {b})")
        self._hsl_edit.setText(f"hsl({h}, {s}%, {l}%)")
        self._css_edit.setText(f"color: {hex_str};")
        if not skip_sliders:
            self._r_slider.setValue(r); self._g_slider.setValue(g); self._b_slider.setValue(b)

        # Update palettes
        for name, fn in PALETTES.items():
            palette_colors = fn(h, s, l)
            swatches = self._palette_rows[name]
            # First swatch = base color
            swatches[0].set_color(hex_str)
            for i, (ph, ps, pl) in enumerate(palette_colors[:4], start=1):
                if i < len(swatches):
                    pr, pg, pb = hsl_to_rgb(ph, ps, pl)
                    swatches[i].set_color(rgb_to_hex(pr, pg, pb))

        self._updating = False
