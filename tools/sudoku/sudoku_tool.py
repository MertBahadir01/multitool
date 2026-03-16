"""Sudoku — 9×9 puzzle with random generation, difficulty levels, validation."""
import random, copy
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QLineEdit, QComboBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QIntValidator
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score, get_user_best

GAME = "sudoku"

def _gen_board():
    b = [[0]*9 for _ in range(9)]
    _fill(b)
    return b

def _fill(b):
    nums = list(range(1,10))
    for i in range(9):
        for j in range(9):
            if b[i][j]==0:
                random.shuffle(nums)
                for n in nums:
                    if _ok(b,i,j,n):
                        b[i][j]=n
                        if _fill(b): return True
                        b[i][j]=0
                return False
    return True

def _ok(b,r,c,n):
    if n in b[r]: return False
    if n in [b[i][c] for i in range(9)]: return False
    br,bc = (r//3)*3,(c//3)*3
    for i in range(br,br+3):
        for j in range(bc,bc+3):
            if b[i][j]==n: return False
    return True

def _remove_cells(b, clues):
    cells = [(r,c) for r in range(9) for c in range(9)]
    random.shuffle(cells)
    removed = 0
    target = 81 - clues
    for r,c in cells:
        if removed >= target: break
        v = b[r][c]; b[r][c] = 0; removed += 1
    return b

DIFFICULTY = {"Easy":46,"Medium":36,"Hard":26,"Expert":20}

class SudokuTool(QWidget):
    name="Sudoku"; description="9×9 Sudoku with difficulty levels"
    def __init__(self,parent=None):
        super().__init__(parent)
        self._user = auth_manager.current_user
        self._cells = []
        self._solution = None
        self._fixed = set()
        self._timer_secs = 0
        self._running = False
        self._build()
        self._new_game()
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr = QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t = QLabel("🔢 Sudoku"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        self._diff = QComboBox(); self._diff.addItems(list(DIFFICULTY.keys()))
        self._diff.setCurrentText("Medium"); hl.addWidget(QLabel("Zorluk:")); hl.addWidget(self._diff)
        new_btn = QPushButton("🆕 Yeni"); new_btn.clicked.connect(self._new_game); hl.addWidget(new_btn)
        chk_btn = QPushButton("✅ Kontrol"); chk_btn.clicked.connect(self._check); hl.addWidget(chk_btn)
        sol_btn = QPushButton("💡 Çözüm"); sol_btn.clicked.connect(self._show_solution); sol_btn.setObjectName("secondary"); hl.addWidget(sol_btn)
        root.addWidget(hdr)
        body = QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        # grid
        grid_frame = QFrame(); grid_frame.setStyleSheet("background:#1A1A1A;border-radius:8px;")
        gf = QVBoxLayout(grid_frame)
        self._time_lbl = QLabel("⏱ 00:00"); self._time_lbl.setAlignment(Qt.AlignCenter)
        self._time_lbl.setStyleSheet("color:#888;font-size:13px;"); gf.addWidget(self._time_lbl)
        self._status_lbl = QLabel(""); self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet("font-size:13px;"); gf.addWidget(self._status_lbl)
        self._grid_lay = QGridLayout(); self._grid_lay.setSpacing(1)
        gf.addLayout(self._grid_lay); body.addWidget(grid_frame,2)
        # scoreboard
        self._sb = ScoreboardWidget(GAME); self._sb.refresh(); body.addWidget(self._sb)
        w = QWidget(); w.setLayout(body); root.addWidget(w,1)
        self._qtimer = QTimer(); self._qtimer.timeout.connect(self._tick); self._qtimer.start(1000)
    def _new_game(self):
        sol = _gen_board()
        self._solution = copy.deepcopy(sol)
        clues = DIFFICULTY.get(self._diff.currentText(),36)
        puzzle = _remove_cells(copy.deepcopy(sol), clues)
        self._fixed = set()
        # clear grid
        for i in reversed(range(self._grid_lay.count())):
            w = self._grid_lay.itemAt(i).widget()
            if w: w.deleteLater()
        self._cells = []
        for r in range(9):
            row=[]
            for c in range(9):
                cell = QLineEdit()
                cell.setFixedSize(46,46)
                cell.setAlignment(Qt.AlignCenter)
                cell.setMaxLength(1)
                cell.setValidator(QIntValidator(1,9))
                bw = "2px" if r%3==0 or c%3==0 else "1px"
                bc = "#555" if r%3==0 or c%3==0 else "#333"
                cell.setStyleSheet(f"background:#252525;border:{bw} solid {bc};font-size:16px;color:#E0E0E0;border-radius:2px;")
                if puzzle[r][c]:
                    cell.setText(str(puzzle[r][c])); cell.setReadOnly(True)
                    cell.setStyleSheet(cell.styleSheet()+"font-weight:bold;color:#00BFA5;")
                    self._fixed.add((r,c))
                self._grid_lay.addWidget(cell,r,c)
                row.append(cell)
            self._cells.append(row)
        self._timer_secs=0; self._running=True
        self._status_lbl.setText("")
        self._sb.refresh()
    def _tick(self):
        if self._running:
            self._timer_secs+=1
            m,s=divmod(self._timer_secs,60)
            self._time_lbl.setText(f"⏱ {m:02d}:{s:02d}")
    def _get_board(self):
        b=[]
        for r in range(9):
            row=[]
            for c in range(9):
                t=self._cells[r][c].text()
                row.append(int(t) if t else 0)
            b.append(row)
        return b
    def _check(self):
        b=self._get_board()
        errors=[]
        for r in range(9):
            for c in range(9):
                if b[r][c]!=0 and b[r][c]!=self._solution[r][c]:
                    errors.append((r,c))
        for r in range(9):
            for c in range(9):
                if (r,c) not in self._fixed:
                    color="#F44336" if (r,c) in errors else ("#4CAF50" if b[r][c]!=0 else "#252525")
                    self._cells[r][c].setStyleSheet(
                        f"background:{color};border:1px solid #333;font-size:16px;color:#E0E0E0;border-radius:2px;")
        if not errors and all(b[r][c]!=0 for r in range(9) for c in range(9)):
            self._running=False
            score = max(1, 3600-self._timer_secs)
            self._status_lbl.setText("🎉 Tebrikler! Tamamlandı!")
            self._status_lbl.setStyleSheet("color:#4CAF50;font-size:13px;")
            if self._user:
                post_score(GAME,self._user["id"],self._user["username"],score)
            self._sb.refresh()
        else:
            self._status_lbl.setText(f"❌ {len(errors)} hata var" if errors else "🔍 Henüz eksik hücreler var")
            self._status_lbl.setStyleSheet("color:#F44336;font-size:13px;")
    def _show_solution(self):
        self._running=False
        for r in range(9):
            for c in range(9):
                if (r,c) not in self._fixed:
                    self._cells[r][c].setText(str(self._solution[r][c]))
                    self._cells[r][c].setStyleSheet(
                        "background:#1A2A1A;border:1px solid #333;font-size:16px;color:#888;border-radius:2px;")