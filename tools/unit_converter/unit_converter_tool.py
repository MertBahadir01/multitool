"""
Unit Converter — Length · Weight · Temperature · Volume · Area · Speed ·
                  Cooking · Data · Pressure · Currency (static rates)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QFrame, QTabWidget, QGridLayout,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


# ── Conversion tables ─────────────────────────────────────────────────────────
# All values = factor to convert TO a base unit (1st unit in list)
# Temperature handled separately (non-linear)

CATEGORIES = {
    "📏 Length": {
        "base": "Meter",
        "units": {
            "Meter":       1.0,
            "Kilometer":   1000.0,
            "Centimeter":  0.01,
            "Millimeter":  0.001,
            "Mile":        1609.344,
            "Yard":        0.9144,
            "Foot":        0.3048,
            "Inch":        0.0254,
            "Nautical Mile": 1852.0,
            "Light Year":  9.461e15,
        }
    },
    "⚖️ Weight": {
        "base": "Kilogram",
        "units": {
            "Kilogram":    1.0,
            "Gram":        0.001,
            "Milligram":   1e-6,
            "Tonne":       1000.0,
            "Pound":       0.453592,
            "Ounce":       0.0283495,
            "Stone":       6.35029,
            "Carat":       0.0002,
        }
    },
    "🧪 Volume": {
        "base": "Liter",
        "units": {
            "Liter":          1.0,
            "Milliliter":     0.001,
            "Cubic Meter":    1000.0,
            "Gallon (US)":    3.78541,
            "Gallon (UK)":    4.54609,
            "Quart (US)":     0.946353,
            "Pint (US)":      0.473176,
            "Cup (US)":       0.236588,
            "Fluid Oz (US)":  0.0295735,
            "Tablespoon":     0.0147868,
            "Teaspoon":       0.00492892,
            "Cubic Inch":     0.0163871,
        }
    },
    "🏎️ Speed": {
        "base": "m/s",
        "units": {
            "m/s":         1.0,
            "km/h":        0.277778,
            "mph":         0.44704,
            "Knot":        0.514444,
            "ft/s":        0.3048,
            "Mach":        343.0,
        }
    },
    "📐 Area": {
        "base": "m²",
        "units": {
            "m²":           1.0,
            "km²":          1e6,
            "cm²":          0.0001,
            "mm²":          1e-6,
            "Acre":         4046.86,
            "Hectare":      10000.0,
            "ft²":          0.092903,
            "yd²":          0.836127,
            "mile²":        2.59e6,
            "inch²":        0.00064516,
        }
    },
    "⏱️ Time": {
        "base": "Second",
        "units": {
            "Second":      1.0,
            "Millisecond": 0.001,
            "Microsecond": 1e-6,
            "Minute":      60.0,
            "Hour":        3600.0,
            "Day":         86400.0,
            "Week":        604800.0,
            "Month (avg)": 2628000.0,
            "Year":        31536000.0,
        }
    },
    "💾 Data": {
        "base": "Byte",
        "units": {
            "Byte":      1.0,
            "Kilobyte":  1024.0,
            "Megabyte":  1024**2,
            "Gigabyte":  1024**3,
            "Terabyte":  1024**4,
            "Petabyte":  1024**5,
            "Bit":       0.125,
            "Kilobit":   125.0,
            "Megabit":   125000.0,
        }
    },
    "🔥 Pressure": {
        "base": "Pascal",
        "units": {
            "Pascal":      1.0,
            "Kilopascal":  1000.0,
            "Bar":         100000.0,
            "Millibar":    100.0,
            "PSI":         6894.76,
            "Atmosphere":  101325.0,
            "mmHg":        133.322,
        }
    },
    "💱 Currency": {
        "base": "USD",
        "note": "(static rates — for live rates use an API)",
        "units": {
            "USD":   1.0,
            "EUR":   1.08,
            "GBP":   1.27,
            "TRY":   0.031,
            "JPY":   0.0067,
            "CNY":   0.138,
            "INR":   0.012,
            "AUD":   0.65,
            "CAD":   0.74,
            "CHF":   1.12,
            "KRW":   0.00075,
            "SAR":   0.267,
            "AED":   0.272,
        }
    },
}

# Temperature is special — handled with functions
TEMP_UNITS = ["Celsius", "Fahrenheit", "Kelvin", "Rankine"]

def _temp_to_celsius(value, unit):
    if unit == "Celsius":    return value
    if unit == "Fahrenheit": return (value - 32) * 5 / 9
    if unit == "Kelvin":     return value - 273.15
    if unit == "Rankine":    return (value - 491.67) * 5 / 9
    return value

def _celsius_to(value, unit):
    if unit == "Celsius":    return value
    if unit == "Fahrenheit": return value * 9 / 5 + 32
    if unit == "Kelvin":     return value + 273.15
    if unit == "Rankine":    return (value + 273.15) * 9 / 5
    return value


class LinearConverterWidget(QWidget):
    """Reusable widget for any linear conversion category."""

    def __init__(self, category_key: str, parent=None):
        super().__init__(parent)
        data = CATEGORIES[category_key]
        self._units = data["units"]
        self._unit_names = list(self._unit_names_list(data))
        self._note = data.get("note", "")
        self._build_ui()

    def _unit_names_list(self, data):
        return data["units"].keys()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        if self._note:
            note = QLabel(f"ℹ️ {self._note}")
            note.setStyleSheet("color:#888; font-size:11px;")
            root.addWidget(note)

        # From row
        from_row = QHBoxLayout()
        self._from_val = QLineEdit("1")
        self._from_val.setFont(QFont("Segoe UI", 16))
        self._from_val.setStyleSheet("background:#252525; border-radius:8px; padding:10px; color:#E0E0E0; font-size:16px;")
        self._from_val.textChanged.connect(self._convert)
        from_row.addWidget(self._from_val, 1)
        self._from_unit = QComboBox()
        self._from_unit.addItems(self._unit_names)
        self._from_unit.setFixedWidth(180)
        self._from_unit.currentIndexChanged.connect(self._convert)
        from_row.addWidget(self._from_unit)
        root.addLayout(from_row)

        swap_btn = QPushButton("⇅  Swap")
        swap_btn.setObjectName("secondary")
        swap_btn.setFixedWidth(100)
        swap_btn.clicked.connect(self._swap)
        root.addWidget(swap_btn, alignment=Qt.AlignLeft)

        # To row
        to_row = QHBoxLayout()
        self._to_val = QLineEdit()
        self._to_val.setFont(QFont("Segoe UI", 16))
        self._to_val.setReadOnly(True)
        self._to_val.setStyleSheet("background:#1A3A35; border-radius:8px; padding:10px; color:#00BFA5; font-size:16px;")
        to_row.addWidget(self._to_val, 1)
        self._to_unit = QComboBox()
        self._to_unit.addItems(self._unit_names)
        self._to_unit.setFixedWidth(180)
        self._to_unit.setCurrentIndex(1)
        self._to_unit.currentIndexChanged.connect(self._convert)
        to_row.addWidget(self._to_unit)
        root.addLayout(to_row)

        # Quick reference table
        root.addWidget(QLabel("Quick reference (from current input):"))
        self._ref_grid = QGridLayout()
        self._ref_grid.setSpacing(6)
        self._ref_labels = {}
        for i, unit in enumerate(self._unit_names):
            name_lbl = QLabel(unit)
            name_lbl.setStyleSheet("color:#888; font-size:12px;")
            val_lbl = QLabel("")
            val_lbl.setStyleSheet("color:#E0E0E0; font-size:12px; font-weight:bold;")
            self._ref_labels[unit] = val_lbl
            self._ref_grid.addWidget(name_lbl, i // 2, (i % 2) * 2)
            self._ref_grid.addWidget(val_lbl,  i // 2, (i % 2) * 2 + 1)
        ref_widget = QWidget()
        ref_widget.setLayout(self._ref_grid)
        scroll = QScrollArea()
        scroll.setWidget(ref_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll, 1)
        self._convert()

    def _convert(self):
        try:
            val = float(self._from_val.text().replace(",", "."))
        except ValueError:
            self._to_val.setText("—")
            return
        from_unit = self._from_unit.currentText()
        to_unit   = self._to_unit.currentText()
        base_val  = val * self._units[from_unit]
        result    = base_val / self._units[to_unit]
        self._to_val.setText(self._fmt(result))
        for unit, lbl in self._ref_labels.items():
            lbl.setText(self._fmt(base_val / self._units[unit]))

    def _fmt(self, v):
        if abs(v) >= 1e9 or (abs(v) < 1e-4 and v != 0):
            return f"{v:.6e}"
        if v == int(v):
            return str(int(v))
        return f"{v:.8g}"

    def _swap(self):
        fi = self._from_unit.currentIndex()
        ti = self._to_unit.currentIndex()
        self._from_unit.setCurrentIndex(ti)
        self._to_unit.setCurrentIndex(fi)
        self._from_val.setText(self._to_val.text())


class TempConverterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        from_row = QHBoxLayout()
        self._from_val = QLineEdit("100")
        self._from_val.setFont(QFont("Segoe UI", 16))
        self._from_val.setStyleSheet("background:#252525; border-radius:8px; padding:10px; color:#E0E0E0; font-size:16px;")
        self._from_val.textChanged.connect(self._convert)
        from_row.addWidget(self._from_val, 1)
        self._from_unit = QComboBox()
        self._from_unit.addItems(TEMP_UNITS)
        self._from_unit.setFixedWidth(180)
        self._from_unit.currentIndexChanged.connect(self._convert)
        from_row.addWidget(self._from_unit)
        root.addLayout(from_row)

        swap_btn = QPushButton("⇅  Swap")
        swap_btn.setObjectName("secondary")
        swap_btn.setFixedWidth(100)
        swap_btn.clicked.connect(self._swap)
        root.addWidget(swap_btn, alignment=Qt.AlignLeft)

        to_row = QHBoxLayout()
        self._to_val = QLineEdit()
        self._to_val.setReadOnly(True)
        self._to_val.setFont(QFont("Segoe UI", 16))
        self._to_val.setStyleSheet("background:#1A3A35; border-radius:8px; padding:10px; color:#00BFA5; font-size:16px;")
        to_row.addWidget(self._to_val, 1)
        self._to_unit = QComboBox()
        self._to_unit.addItems(TEMP_UNITS)
        self._to_unit.setCurrentIndex(1)
        self._to_unit.setFixedWidth(180)
        self._to_unit.currentIndexChanged.connect(self._convert)
        to_row.addWidget(self._to_unit)
        root.addLayout(to_row)

        root.addWidget(QLabel("All temperatures:"))
        self._all_labels = {}
        for unit in TEMP_UNITS:
            row = QHBoxLayout()
            row.addWidget(QLabel(unit))
            lbl = QLabel("")
            lbl.setStyleSheet("color:#00BFA5; font-weight:bold;")
            row.addWidget(lbl)
            row.addStretch()
            self._all_labels[unit] = lbl
            root.addLayout(row)
        root.addStretch()
        self._convert()

    def _convert(self):
        try:
            val = float(self._from_val.text().replace(",", "."))
        except ValueError:
            return
        c = _temp_to_celsius(val, self._from_unit.currentText())
        result = _celsius_to(c, self._to_unit.currentText())
        self._to_val.setText(f"{result:.4g}")
        for unit, lbl in self._all_labels.items():
            lbl.setText(f"{_celsius_to(c, unit):.4g} °{unit[0]}")

    def _swap(self):
        fi = self._from_unit.currentIndex()
        ti = self._to_unit.currentIndex()
        self._from_unit.setCurrentIndex(ti)
        self._to_unit.setCurrentIndex(fi)
        self._from_val.setText(self._to_val.text())


class UnitConverterTool(QWidget):
    name = "Unit Converter"
    description = "Convert length, weight, temperature, currency and more"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 12, 24, 12)
        t = QLabel("📐 Unit Converter")
        t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t)
        hl.addStretch()
        root.addWidget(hdr)

        tabs = QTabWidget()
        for cat_key in CATEGORIES:
            tabs.addTab(LinearConverterWidget(cat_key), cat_key)
        tabs.addTab(TempConverterWidget(), "🌡️ Temperature")
        root.addWidget(tabs, 1)
