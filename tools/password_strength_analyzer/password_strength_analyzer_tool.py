"""Password Strength Analyzer."""
import re, math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QGroupBox, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


def _analyze(pw):
    length = len(pw)
    has_lower  = bool(re.search(r'[a-z]', pw))
    has_upper  = bool(re.search(r'[A-Z]', pw))
    has_digit  = bool(re.search(r'\d', pw))
    has_symbol = bool(re.search(r'[^a-zA-Z0-9]', pw))
    has_space  = ' ' in pw

    pool = 0
    if has_lower:  pool += 26
    if has_upper:  pool += 26
    if has_digit:  pool += 10
    if has_symbol: pool += 32
    if has_space:  pool += 1
    if pool == 0:  pool = 1

    entropy = length * math.log2(pool)

    # Crack time estimate at 1 billion guesses/sec
    guesses = pool ** length
    seconds = guesses / 1_000_000_000
    crack   = _fmt_time(seconds)

    score = 0
    if length >= 8:  score += 1
    if length >= 12: score += 1
    if length >= 16: score += 1
    if has_lower:    score += 1
    if has_upper:    score += 1
    if has_digit:    score += 1
    if has_symbol:   score += 1

    if score <= 2:   label, color = "Very Weak",  "#F44336"
    elif score <= 3: label, color = "Weak",        "#FF9800"
    elif score <= 4: label, color = "Fair",        "#FFC107"
    elif score <= 5: label, color = "Strong",      "#8BC34A"
    else:            label, color = "Very Strong", "#00BFA5"

    tips = []
    if length < 12:             tips.append("Use at least 12 characters")
    if not has_upper:           tips.append("Add uppercase letters")
    if not has_lower:           tips.append("Add lowercase letters")
    if not has_digit:           tips.append("Add numbers")
    if not has_symbol:          tips.append("Add special characters (!@#$...)")
    common = ["password","123456","qwerty","abc123","letmein","admin"]
    if pw.lower() in common:    tips.append("Avoid common passwords!")

    return {
        "score": score, "max": 7, "label": label, "color": color,
        "entropy": entropy, "crack": crack, "tips": tips,
        "length": length, "pool": pool,
        "checks": {
            "Lowercase letters": has_lower,
            "Uppercase letters": has_upper,
            "Numbers":           has_digit,
            "Special characters":has_symbol,
            "Length >= 8":       length >= 8,
            "Length >= 12":      length >= 12,
            "Length >= 16":      length >= 16,
        }
    }


def _fmt_time(s):
    if s < 1:         return "< 1 second"
    if s < 60:        return f"{s:.0f} seconds"
    if s < 3600:      return f"{s/60:.0f} minutes"
    if s < 86400:     return f"{s/3600:.0f} hours"
    if s < 31536000:  return f"{s/86400:.0f} days"
    if s < 3.15e9:    return f"{s/31536000:.0f} years"
    return "centuries"


class PasswordStrengthAnalyzerTool(QWidget):
    name        = "Password Strength Analyzer"
    description = "Check password strength, entropy, and estimated crack time"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Input
        in_box = QGroupBox("Password Input")
        il = QVBoxLayout(in_box)
        row = QHBoxLayout()
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("Type or paste password...")
        self.pw_input.textChanged.connect(self._analyze)
        row.addWidget(self.pw_input)
        self.show_chk = QCheckBox("Show")
        self.show_chk.toggled.connect(lambda v: self.pw_input.setEchoMode(
            QLineEdit.Normal if v else QLineEdit.Password))
        row.addWidget(self.show_chk)
        il.addLayout(row)
        lay.addWidget(in_box)

        # Strength bar
        self.strength_lbl = QLabel("Strength: —")
        self.strength_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lay.addWidget(self.strength_lbl)
        self.bar = QProgressBar()
        self.bar.setRange(0, 7)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(18)
        lay.addWidget(self.bar)

        # Stats
        stats_box = QGroupBox("Analysis")
        sl = QVBoxLayout(stats_box)
        self.entropy_lbl  = QLabel("Entropy: —")
        self.crack_lbl    = QLabel("Est. crack time: —")
        self.pool_lbl     = QLabel("Character pool: —")
        for lbl in [self.entropy_lbl, self.crack_lbl, self.pool_lbl]:
            sl.addWidget(lbl)
        lay.addWidget(stats_box)

        # Checklist
        chk_box = QGroupBox("Checklist")
        self.chk_layout = QVBoxLayout(chk_box)
        self._check_labels = {}
        checks = ["Lowercase letters","Uppercase letters","Numbers",
                  "Special characters","Length >= 8","Length >= 12","Length >= 16"]
        for c in checks:
            lbl = QLabel(f"  {c}")
            self._check_labels[c] = lbl
            self.chk_layout.addWidget(lbl)
        lay.addWidget(chk_box)

        # Tips
        tips_box = QGroupBox("Tips")
        self.tips_layout = QVBoxLayout(tips_box)
        self.tips_lbl = QLabel("Enter a password to see tips.")
        self.tips_lbl.setStyleSheet("color: #888888;")
        self.tips_lbl.setWordWrap(True)
        self.tips_layout.addWidget(self.tips_lbl)
        lay.addWidget(tips_box)
        lay.addStretch()

    def _analyze(self, pw):
        if not pw:
            self.strength_lbl.setText("Strength: —")
            self.bar.setValue(0)
            return
        r = _analyze(pw)
        self.strength_lbl.setText(f"Strength: {r['label']}")
        self.strength_lbl.setStyleSheet(f"color: {r['color']};")
        self.bar.setValue(r["score"])
        self.bar.setStyleSheet(f"QProgressBar::chunk {{ background: {r['color']}; border-radius: 4px; }}")
        self.entropy_lbl.setText(f"Entropy: {r['entropy']:.1f} bits")
        self.crack_lbl.setText(f"Est. crack time (1B guesses/sec): {r['crack']}")
        self.pool_lbl.setText(f"Character pool size: {r['pool']}")
        for name, ok in r["checks"].items():
            lbl = self._check_labels[name]
            lbl.setText(f"  {'[OK]' if ok else '[  ]'}  {name}")
            lbl.setStyleSheet(f"color: {'#00BFA5' if ok else '#F44336'};")
        if r["tips"]:
            self.tips_lbl.setText("\n".join(f"• {t}" for t in r["tips"]))
            self.tips_lbl.setStyleSheet("color: #FFC107;")
        else:
            self.tips_lbl.setText("Looks good!")
            self.tips_lbl.setStyleSheet("color: #00BFA5;")
