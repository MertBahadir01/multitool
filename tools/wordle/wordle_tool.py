"""Wordle — 5-harfli kelimeyi 6 denemede bul.
Türkçe (varsayılan) ve İngilizce dil desteği.
"""
import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME = "wordle"

# ── Word lists ────────────────────────────────────────────────────────────────
WORDS_TR = sorted(set([
    "ARABA","KALEM","ELMAS","YÜZÜK","KÖPEK","KİTAP","ÇIÇEK","BULUT","GÜNEŞ","DENİZ",
    "ORMAN","SOKAK","KAPAK","TAHTA","KOLTUK","DUVAR","TAVAN","KAPI","BAHÇE","BODRUM",
    "OKUL","KÖPRÜ","TÜNEL","LİMAN","HAVUZ","PLAJ","SAHİL","ELMA","ARMUT","ÜZÜM",
    "KAVUN","ÇİLEK","KİRAZ","AYVA","ERİK","ASLAN","KAPLAN","TİLKİ","KURT","TAVŞAN",
    "RENK","BEYAZ","SİYAH","MAVİ","YEŞİL","SARI","MOR","TURUNCU","PEMBE","BÜYÜK",
    "KÜÇÜK","HIZLI","YAVAŞ","GÜZEL","SERİN","SICAK","SOĞUK","SABAH","ÖĞLEN","AKŞAM",
    "GECE","YARIN","BUGÜN","HAFTA","ANNE","BABA","ABLA","DEDE","NİNE","TEYZE",
    "PARA","ALTIN","GÜMÜŞ","BAKIR","DEMİR","ÇELİK","KAYA","KUM","TOPRAK","BALIK",
    "YUNUS","MIDYE","UÇAK","GEMİ","TREN","MOTOR","KAMYON","MÜZİK","ŞARKI","DANS",
    "RESİM","SİİR","KALP","MASAL","PASTA","ZAFER","ZAMAN","KEMER","SABUN","TABLO",
    "YEMEK","ADRES","HABER","İNSAN","KADIN","KAĞIT","KARGA","KAVGA","KENDİ","KÖYLÜ",
    "MİRAS","ÖZGÜR","PİLOT","PLAKA","SEBZE","ŞEKER","ŞİMDİ","TAKSİ","TARAF","UMUT",
    "VAGON","YÜZDE","ŞEHIR","NEHIR","YILDIZ","ÇORBA","DOĞUM","FENER","GALİP","HAMUR",
    "İKİZ","JİMNAZ","KİRAZ","LAVUK","MEYVA","NAZAR","OYNAK","PİRİNÇ","RITIM","SÜRAT",
    "TURNA","UÇUŞ","VİRÜS","YEŞİM","ZEYTİN","AÇLIK","BİBER","CESUR","DÜRÜST","ENERJI",
]))
WORDS_TR = [w for w in WORDS_TR if len(w) == 5]

WORDS_EN = [
    "CRANE","SLATE","FLINT","STORM","BRAVE","GRIPE","SHOUT","PLUMB","TRACK","SWIFT",
    "BLAZE","CRIMP","DWARF","EPOCH","FROST","GLOOM","HIPPO","IRONY","JOUST","KNAVE",
    "LEMON","MOURN","NUDGE","OLIVE","PERCH","QUILL","RIDGE","SNOWY","THYME","ULTRA",
    "VAPOR","WHIRL","YACHT","ZEBRA","ACUTE","BLINK","CHANT","DRIVE","EMBER","FAINT",
    "GRASP","HAVEN","INFER","JEWEL","KNEEL","LIVER","MIRTH","NERVE","OUGHT","PIXEL",
    "QUALM","REPEL","STING","TROUT","UNIFY","VICAR","WALTZ","EXPEL","YODEL","ABBOT",
    "BLOAT","CLEFT","DEBUT","ETHOS","FLUKE","GRUEL","HEIST","INEPT","JUMBO","KUDOS",
    "LUSTY","MACRO","NICHE","OCTET","PRANK","QUOTA","RIVET","SCONE","TACIT","UNCUT",
    "VIGOR","WOKEN","EXTOL","YEARN","ZIPPY","AGILE","BRAWN","CLOAK","DELTA","ELUDE",
    "FINCH","GLARE","HASTE","IGLOO","JOKER","KEBAB","LATCH","MOCHA","AMPLE","BRINE",
    "CANDY","DITCH","ELDER","FLAIR","GUILE","HOUND","INLET","JAZZY","KNACK","LUNGE",
    "MAXIM","NEWLY","ONSET","PROXY","RANCH","SAVOR","TONIC","ULCER","VERSE","WINCH",
]

# Keyboard rows per language
KB_TR = ["ERTYUIОПASDFGHJKLZXCVBNM",
         "E R T Y U I O P",
         "A S D F G H J K L",
         "Z X C V B N M"]

KB_ROWS = {
    "TR": ["ERTYUIOPĞÜ", "ASDFGHJKLŞİ", "ZXCVBNMÖÇ"],
    "EN": ["QWERTYUIOP",  "ASDFGHJKL",   "ZXCVBNM"],
}

VALID_TR = set("ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ")
# Also accept lowercase mapped to uppercase in keyPressEvent
_TR_LOWER_MAP = {
    "a":"A","b":"B","c":"C","ç":"Ç","d":"D","e":"E","f":"F","g":"G",
    "ğ":"Ğ","h":"H","ı":"I","i":"İ","j":"J","k":"K","l":"L","m":"M",
    "n":"N","o":"O","ö":"Ö","p":"P","r":"R","s":"S","ş":"Ş","t":"T",
    "u":"U","ü":"Ü","v":"V","y":"Y","z":"Z",
}
VALID_EN = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

UI = {
    "TR": {
        "title":    "🟩 Wordle (TR)",
        "new":      "🆕 Yeni Oyun",
        "attempt":  lambda r: f"Deneme {r}/6",
        "short":    "5 harf girin!",
        "correct":  lambda s: f"🎉 Doğru! Skor: {s}",
        "fail":     lambda w: f"❌ Cevap: {w}",
    },
    "EN": {
        "title":    "🟩 Wordle (EN)",
        "new":      "🆕 New Game",
        "attempt":  lambda r: f"Attempt {r}/6",
        "short":    "Enter 5 letters!",
        "correct":  lambda s: f"🎉 Correct! Score: {s}",
        "fail":     lambda w: f"❌ Answer: {w}",
    },
}


# ── Tile ──────────────────────────────────────────────────────────────────────
class LetterTile(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Segoe UI", 20, QFont.Bold))
        self._set_empty()

    def _set_empty(self):
        self.setText("")
        self.setStyleSheet(
            "background:#252525; border:2px solid #3A3A3A;"
            "border-radius:4px; color:#E0E0E0;")

    def set_letter(self, ch):
        self.setText(ch)
        self.setStyleSheet(
            "background:#252525; border:2px solid #00BFA5;"
            "border-radius:4px; color:#E0E0E0;")

    def reveal(self, state):
        colors = {
            "correct": "#538D4E",
            "present": "#B59F3B",
            "absent":  "#3A3A3C",
        }
        c = colors[state]
        self.setStyleSheet(
            f"background:{c}; border:2px solid {c};"
            "border-radius:4px; color:#FFFFFF;")


# ── On-screen keyboard ────────────────────────────────────────────────────────
class _KeyTile(QFrame):
    """A single keyboard key: QFrame + QLabel so the global QPushButton
    stylesheet never hides the letter. Clickable via mousePressEvent."""

    _BASE  = "#818384"
    _HOVER = "#9A9B9C"

    def __init__(self, ch, on_key, wide=False, parent=None):
        super().__init__(parent)
        self._ch     = ch
        self._on_key = on_key
        self._color  = self._BASE
        w = 52 if wide else 34
        self.setFixedSize(w, 34)
        self.setCursor(Qt.PointingHandCursor)
        self._apply(self._BASE)

        inner = QHBoxLayout(self)
        inner.setContentsMargins(0, 0, 0, 0)
        self._lbl = QLabel(ch)
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setFont(QFont("Segoe UI", 11 if not wide else 13, QFont.Bold))
        self._lbl.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        inner.addWidget(self._lbl)

    def _apply(self, bg):
        self._color = bg
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 4px; border: none; }}"
        )

    def set_state(self, state):
        colors = {"correct": "#538D4E", "present": "#B59F3B", "absent": "#3A3A3C"}
        self._apply(colors[state])

    def reset(self):
        self._apply(self._BASE)

    def mousePressEvent(self, _):
        self._apply(self._HOVER)

    def mouseReleaseEvent(self, _):
        self._apply(self._color)   # restore (may be coloured after guess)
        self._on_key(self._ch)

    def enterEvent(self, _):
        if self._color == self._BASE:
            self.setStyleSheet(
                f"QFrame {{ background: {self._HOVER}; border-radius: 4px; border: none; }}"
            )

    def leaveEvent(self, _):
        self._apply(self._color)


class KeyboardWidget(QWidget):
    """One keyboard for one language. Replace the whole widget to change language."""

    def __init__(self, lang, on_key, parent=None):
        super().__init__(parent)
        self._on_key = on_key
        self._keys: dict[str, _KeyTile] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 4)
        lay.setSpacing(5)

        for row_str in KB_ROWS[lang]:
            rl = QHBoxLayout()
            rl.setSpacing(4)
            rl.setAlignment(Qt.AlignCenter)
            for ch in row_str:
                tile = _KeyTile(ch, on_key)
                rl.addWidget(tile)
                self._keys[ch] = tile
            if row_str == KB_ROWS[lang][-1]:
                for label, key in [("⌫", "\x08"), ("↵", "\r")]:
                    tile = _KeyTile(label, on_key, wide=True)
                    rl.addWidget(tile)
            lay.addLayout(rl)

    def update_key(self, ch, state):
        tile = self._keys.get(ch)
        if not tile:
            return
        # Don't downgrade: correct > present > absent
        cur = tile._color
        if cur == "#538D4E":
            return
        if cur == "#B59F3B" and state == "absent":
            return
        tile.set_state(state)

    def reset(self):
        for tile in self._keys.values():
            tile.reset()


# ── Main tool ─────────────────────────────────────────────────────────────────
class WordleTool(QWidget):
    name        = "Wordle"
    description = "5-harfli kelimeyi 6 denemede bul — TR/EN"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user    = auth_manager.current_user
        self._lang    = "TR"          # Turkish default
        self._word    = ""
        self._row     = 0
        self._col     = 0
        self._current: list[str] = []
        self._over    = False
        self._build_ui()
        self._new_game()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet("background:#1E1E1E; border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 10, 20, 10)

        self._title_lbl = QLabel(UI["TR"]["title"])
        self._title_lbl.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self._title_lbl.setStyleSheet("color:#00BFA5;")
        hl.addWidget(self._title_lbl)
        hl.addStretch()

        self._status = QLabel("")
        self._status.setStyleSheet("color:#888; font-size:13px;")
        hl.addWidget(self._status)

        # Language toggle button
        self._lang_btn = QPushButton("🇬🇧 English")
        self._lang_btn.setObjectName("secondary")
        self._lang_btn.clicked.connect(self._toggle_lang)
        hl.addWidget(self._lang_btn)

        self._new_btn = QPushButton(UI["TR"]["new"])
        self._new_btn.clicked.connect(self._new_game)
        hl.addWidget(self._new_btn)
        root.addWidget(hdr)

        # Body
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(20, 20, 20, 20)
        body_lay.setSpacing(24)

        # Centre column: grid + keyboard
        centre = QWidget()
        cl = QVBoxLayout(centre)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(14)
        cl.setAlignment(Qt.AlignCenter)

        # 6 × 5 tile grid
        grid_w = QWidget()
        self._grid_lay = QGridLayout(grid_w)
        self._grid_lay.setSpacing(6)
        self._tiles: list[list[LetterTile]] = []
        for r in range(6):
            row = []
            for c in range(5):
                tile = LetterTile()
                self._grid_lay.addWidget(tile, r, c)
                row.append(tile)
            self._tiles.append(row)
        cl.addWidget(grid_w, 0, Qt.AlignCenter)

        # On-screen keyboard
        self._kb = KeyboardWidget("TR", self._on_kb_key)
        cl.addWidget(self._kb, 0, Qt.AlignCenter)
        body_lay.addWidget(centre, 2)

        # Scoreboard
        self._sb = ScoreboardWidget(GAME)
        self._sb.refresh()
        body_lay.addWidget(self._sb, 1)

        root.addWidget(body, 1)
        self.setFocusPolicy(Qt.StrongFocus)

    # ── Language toggle ───────────────────────────────────────────────────────
    def _toggle_lang(self):
        self._lang = "EN" if self._lang == "TR" else "TR"
        self._lang_btn.setText("🇹🇷 Türkçe" if self._lang == "EN" else "🇬🇧 English")
        self._title_lbl.setText(UI[self._lang]["title"])
        self._new_btn.setText(UI[self._lang]["new"])
        # Replace keyboard widget entirely — cleanest way to change layout
        cl = self._kb.parent().layout()   # QVBoxLayout of centre widget
        idx = cl.indexOf(self._kb)
        self._kb.deleteLater()
        self._kb = KeyboardWidget(self._lang, self._on_kb_key)
        cl.insertWidget(idx, self._kb, 0, Qt.AlignCenter)
        self._new_game()

    # ── Game logic ────────────────────────────────────────────────────────────
    def _word_list(self):
        return WORDS_TR if self._lang == "TR" else WORDS_EN

    def _valid_letters(self):
        return VALID_TR if self._lang == "TR" else VALID_EN

    def _new_game(self):
        words = self._word_list()
        self._word    = random.choice(words)
        self._row     = 0
        self._col     = 0
        self._current = []
        self._over    = False
        for row in self._tiles:
            for tile in row:
                tile._set_empty()
        self._kb.reset()
        self._status.setText(UI[self._lang]["attempt"](1))
        self.setFocus()

    def _on_kb_key(self, key):
        if self._over:
            return
        if key == "\x08":
            self._backspace()
        elif key == "\r":
            self._submit()
        elif key in self._valid_letters() and len(self._current) < 5:
            self._type_letter(key)

    def keyPressEvent(self, e: QKeyEvent):
        if self._over:
            return
        key  = e.key()
        raw  = e.text()
        # Map Turkish lowercase → uppercase (e.g. "ş" → "Ş", "ı" → "I")
        if self._lang == "TR" and raw in _TR_LOWER_MAP:
            text = _TR_LOWER_MAP[raw]
        else:
            text = raw.upper()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._submit()
        elif key == Qt.Key_Backspace:
            self._backspace()
        elif text and text in self._valid_letters() and len(self._current) < 5:
            self._type_letter(text)

    def _type_letter(self, ch):
        self._tiles[self._row][self._col].set_letter(ch)
        self._current.append(ch)
        self._col += 1

    def _backspace(self):
        if self._current:
            self._current.pop()
            self._col -= 1
            self._tiles[self._row][self._col]._set_empty()

    def _submit(self):
        ui = UI[self._lang]
        if len(self._current) != 5:
            self._status.setText(ui["short"])
            return
        guess  = "".join(self._current)
        result = self._evaluate(guess, self._word)
        for c, (ch, state) in enumerate(zip(guess, result)):
            self._tiles[self._row][c].reveal(state)
            self._kb.update_key(ch, state)
        if guess == self._word:
            self._over = True
            score = max(1, (7 - self._row) * 100)
            self._status.setText(ui["correct"](score))
            if self._user:
                post_score(GAME, self._user["id"], self._user["username"], score)
                self._sb.refresh()
        else:
            self._row += 1
            self._col  = 0
            self._current = []
            if self._row == 6:
                self._over = True
                self._status.setText(ui["fail"](self._word))
            else:
                self._status.setText(ui["attempt"](self._row + 1))

    def _evaluate(self, guess, word):
        result     = ["absent"] * 5
        word_count: dict[str, int] = {}
        for i, (g, w) in enumerate(zip(guess, word)):
            if g == w:
                result[i] = "correct"
            else:
                word_count[w] = word_count.get(w, 0) + 1
        for i, g in enumerate(guess):
            if result[i] != "correct" and g in word_count and word_count[g] > 0:
                result[i] = "present"
                word_count[g] -= 1
        return result