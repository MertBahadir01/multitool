"""Tetris — full mechanics: pieces, rotation, line clear, levels, score."""
import random, copy
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QPainter,QColor,QFont,QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget,post_score

GAME="tetris"; COLS=10; ROWS=20; CS=30

PIECES=[
    [[1,1,1,1]],
    [[1,1],[1,1]],
    [[0,1,0],[1,1,1]],
    [[1,0],[1,0],[1,1]],
    [[0,1],[0,1],[1,1]],
    [[1,1,0],[0,1,1]],
    [[0,1,1],[1,1,0]],
]
COLORS=["#00BCD4","#FFD700","#9C27B0","#FF9800","#2196F3","#F44336","#4CAF50"]

def rotate(piece): return [list(row) for row in zip(*piece[::-1])]

class TetrisCanvas(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(COLS*CS,ROWS*CS)
        self._reset()
    def _reset(self):
        self.board=[[None]*COLS for _ in range(ROWS)]
        self.score=self.lines=self.level=0; self.alive=True
        self._new_piece()
    def _new_piece(self):
        i=random.randint(0,len(PIECES)-1)
        self.piece=copy.deepcopy(PIECES[i]); self.color=COLORS[i]
        self.px=COLS//2-len(self.piece[0])//2; self.py=0
        if self._collides(self.piece,self.px,self.py): self.alive=False
    def _collides(self,p,px,py):
        for r,row in enumerate(p):
            for c,v in enumerate(row):
                if v:
                    nx,ny=px+c,py+r
                    if nx<0 or nx>=COLS or ny>=ROWS: return True
                    if ny>=0 and self.board[ny][nx]: return True
        return False
    def move(self,dx,dy):
        if not self._collides(self.piece,self.px+dx,self.py+dy):
            self.px+=dx; self.py+=dy; return True
        return False
    def rotate_piece(self):
        r=rotate(self.piece)
        if not self._collides(r,self.px,self.py): self.piece=r
    def drop(self):
        if not self.move(0,1):
            self._lock()
    def hard_drop(self):
        while self.move(0,1): pass
        self._lock()
    def _lock(self):
        for r,row in enumerate(self.piece):
            for c,v in enumerate(row):
                if v and self.py+r>=0: self.board[self.py+r][self.px+c]=self.color
        cleared=0
        new_board=[row for row in self.board if any(x is None for x in row)]
        cleared=ROWS-len(new_board)
        self.board=[[None]*COLS for _ in range(cleared)]+new_board
        pts=[0,100,300,500,800]
        self.score+=pts[cleared]*(self.level+1); self.lines+=cleared
        self.level=self.lines//10; self._new_piece()
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0,0,COLS*CS,ROWS*CS,QColor("#0D0D0D"))
        # grid
        p.setPen(QColor("#1A1A1A"))
        for x in range(0,COLS*CS,CS): p.drawLine(x,0,x,ROWS*CS)
        for y in range(0,ROWS*CS,CS): p.drawLine(0,y,COLS*CS,y)
        # board
        for r in range(ROWS):
            for c in range(COLS):
                if self.board[r][c]:
                    self._draw_cell(p,c,r,self.board[r][c])
        # current piece
        if self.alive:
            # ghost
            gy=self.py
            while not self._collides(self.piece,self.px,gy+1): gy+=1
            for r,row in enumerate(self.piece):
                for c,v in enumerate(row):
                    if v: self._draw_cell(p,self.px+c,gy+r,self.color,ghost=True)
            for r,row in enumerate(self.piece):
                for c,v in enumerate(row):
                    if v: self._draw_cell(p,self.px+c,self.py+r,self.color)
        if not self.alive:
            p.fillRect(0,0,COLS*CS,ROWS*CS,QColor(0,0,0,170))
            p.setPen(QColor("#F44336")); p.setFont(QFont("Segoe UI",20,QFont.Bold))
            p.drawText(0,ROWS*CS//2-30,COLS*CS,40,Qt.AlignCenter,"GAME OVER")
        p.end()
    def _draw_cell(self,p,x,y,color,ghost=False):
        c=QColor(color); c.setAlpha(60 if ghost else 255)
        p.fillRect(x*CS+1,y*CS+1,CS-2,CS-2,c)
        if not ghost:
            p.setPen(QColor(min(c.red()+40,255),min(c.green()+40,255),min(c.blue()+40,255)))
            p.drawLine(x*CS+1,y*CS+1,x*CS+CS-2,y*CS+1)
            p.drawLine(x*CS+1,y*CS+1,x*CS+1,y*CS+CS-2)

class TetrisTool(QWidget):
    name="Tetris"; description="Classic Tetris with levels and scoring"
    def __init__(self,parent=None):
        super().__init__(parent); self._user=auth_manager.current_user; self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("🧩 Tetris"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        hl.addWidget(QLabel("←→ hareket  ↑ döndür  ↓ hızlı  Space hard drop",styleSheet="color:#555;font-size:11px;"))
        root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        self._canvas=TetrisCanvas(); left.addWidget(self._canvas)
        rb=QPushButton("▶ Başla / Yeniden"); rb.clicked.connect(self._restart); left.addWidget(rb)
        body.addLayout(left)
        # stats + scoreboard
        right=QVBoxLayout()
        self._score_lbl=QLabel("Skor\n0"); self._score_lbl.setAlignment(Qt.AlignCenter)
        self._score_lbl.setFont(QFont("Segoe UI",14,QFont.Bold)); self._score_lbl.setStyleSheet("color:#FF9800;")
        right.addWidget(self._score_lbl)
        self._level_lbl=QLabel("Seviye: 0"); self._level_lbl.setAlignment(Qt.AlignCenter)
        self._level_lbl.setStyleSheet("color:#888;"); right.addWidget(self._level_lbl)
        self._lines_lbl=QLabel("Satır: 0"); self._lines_lbl.setAlignment(Qt.AlignCenter)
        self._lines_lbl.setStyleSheet("color:#888;"); right.addWidget(self._lines_lbl)
        self._sb=ScoreboardWidget(GAME); self._sb.refresh(); right.addWidget(self._sb)
        body.addLayout(right)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
        self._timer=QTimer(); self._timer.timeout.connect(self._tick)
        self.setFocusPolicy(Qt.StrongFocus)
    def _restart(self):
        self._canvas._reset(); self._timer.start(500); self.setFocus()
    def _tick(self):
        self._canvas.drop(); self._update_labels()
        if not self._canvas.alive:
            self._timer.stop()
            if self._user and self._canvas.score>0:
                post_score(GAME,self._user["id"],self._user["username"],self._canvas.score)
                self._sb.refresh()
        else:
            interval=max(100,500-self._canvas.level*40)
            self._timer.setInterval(interval)
    def _update_labels(self):
        self._score_lbl.setText(f"Skor\n{self._canvas.score}")
        self._level_lbl.setText(f"Seviye: {self._canvas.level}")
        self._lines_lbl.setText(f"Satır: {self._canvas.lines}")
    def keyPressEvent(self,e:QKeyEvent):
        k=e.key()
        if k==Qt.Key_Left: self._canvas.move(-1,0)
        elif k==Qt.Key_Right: self._canvas.move(1,0)
        elif k==Qt.Key_Down: self._canvas.drop()
        elif k==Qt.Key_Up: self._canvas.rotate_piece()
        elif k==Qt.Key_Space: self._canvas.hard_drop()
        self._canvas.update(); self._update_labels()