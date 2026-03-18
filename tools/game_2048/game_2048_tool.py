"""2048 — sliding number puzzle, merge logic, win/loss detection."""
import random
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter,QColor,QFont,QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget,post_score

GAME="2048"; SZ=4; CS=100

TILE_COLORS={
    0:("#cdc1b4","#776e65"),2:("#eee4da","#776e65"),4:("#ede0c8","#776e65"),
    8:("#f2b179","#f9f6f2"),16:("#f59563","#f9f6f2"),32:("#f67c5f","#f9f6f2"),
    64:("#f65e3b","#f9f6f2"),128:("#edcf72","#f9f6f2"),256:("#edcc61","#f9f6f2"),
    512:("#edc850","#f9f6f2"),1024:("#edc53f","#f9f6f2"),2048:("#edc22e","#f9f6f2"),
}

class Board2048(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(SZ*CS+10,SZ*CS+10); self._reset()
    def _reset(self):
        self.grid=[[0]*SZ for _ in range(SZ)]; self.score=0
        self.won=False; self.lost=False; self._add_tile(); self._add_tile()
    def _add_tile(self):
        empty=[(r,c) for r in range(SZ) for c in range(SZ) if self.grid[r][c]==0]
        if empty:
            r,c=random.choice(empty); self.grid[r][c]=4 if random.random()<0.1 else 2
    def _slide_row(self,row):
        nums=[x for x in row if x]; merged=[]; skip=False; pts=0
        for i,n in enumerate(nums):
            if skip: skip=False; continue
            if i+1<len(nums) and nums[i+1]==n: merged.append(n*2); pts+=n*2; skip=True
            else: merged.append(n)
        merged+=[0]*(SZ-len(merged)); return merged,pts
    def move(self,dr,dc):
        old=[row[:] for row in self.grid]; pts=0
        for r in range(SZ):
            for c in range(SZ):
                if dr==0:
                    row=self.grid[r] if dc==-1 else self.grid[r][::-1]
                    new,p=self._slide_row(row); pts+=p
                    if dc==1: new=new[::-1]
                    self.grid[r]=new
                else:
                    col=[self.grid[i][c] for i in range(SZ)]
                    if dr==1: col=col[::-1]
                    new,p=self._slide_row(col); pts+=p
                    if dr==1: new=new[::-1]
                    for i in range(SZ): self.grid[i][c]=new[i]
        if self.grid!=old:
            self.score+=pts; self._add_tile()
            if any(2048 in row for row in self.grid): self.won=True
            elif not any(self.grid[r][c]==0 for r in range(SZ) for c in range(SZ)):
                can=False
                for r in range(SZ):
                    for c in range(SZ):
                        if(c+1<SZ and self.grid[r][c]==self.grid[r][c+1])or(r+1<SZ and self.grid[r][c]==self.grid[r+1][c]):
                            can=True
                if not can: self.lost=True
            self.update()
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0,0,self.width(),self.height(),QColor("#bbada0"))
        for r in range(SZ):
            for c in range(SZ):
                v=self.grid[r][c]; bg,fg=TILE_COLORS.get(v,("#3c3a32","#f9f6f2"))
                x,y=c*CS+5,r*CS+5
                p.setBrush(QColor(bg)); p.setPen(Qt.NoPen)
                p.drawRoundedRect(x,y,CS-4,CS-4,6,6)
                if v:
                    p.setPen(QColor(fg))
                    fs=28 if v<100 else(22 if v<1000 else 16)
                    p.setFont(QFont("Segoe UI",fs,QFont.Bold))
                    p.drawText(x,y,CS-4,CS-4,Qt.AlignCenter,str(v))
        if self.won or self.lost:
            p.fillRect(0,0,self.width(),self.height(),QColor(0,0,0,150))
            p.setPen(QColor("#FFD700" if self.won else "#F44336"))
            p.setFont(QFont("Segoe UI",26,QFont.Bold))
            p.drawText(0,0,self.width(),self.height(),Qt.AlignCenter,"🎉 2048!" if self.won else "GAME OVER")
        p.end()

class Game2048Tool(QWidget):
    name="2048"; description="Sliding number puzzle"
    def __init__(self,parent=None):
        super().__init__(parent); self._user=auth_manager.current_user; self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("🔢 2048"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        hl.addWidget(QLabel("Ok tuşları ile kaydır",styleSheet="color:#555;font-size:12px;"))
        root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        self._score_lbl=QLabel("Skor: 0"); self._score_lbl.setFont(QFont("Segoe UI",16,QFont.Bold))
        self._score_lbl.setStyleSheet("color:#FF9800;"); left.addWidget(self._score_lbl)
        self._board=Board2048(); left.addWidget(self._board)
        rb=QPushButton("🆕 Yeni Oyun"); rb.clicked.connect(self._restart); left.addWidget(rb)
        body.addLayout(left)
        self._sb=ScoreboardWidget(GAME); self._sb.refresh(); body.addWidget(self._sb)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
        self.setFocusPolicy(Qt.StrongFocus)
    def _restart(self):
        self._board._reset(); self._score_lbl.setText("Skor: 0"); self.setFocus()
    def keyPressEvent(self,e:QKeyEvent):
        b=self._board
        if b.won or b.lost: return
        dirs={Qt.Key_Left:(0,-1),Qt.Key_Right:(0,1),Qt.Key_Up:(-1,0),Qt.Key_Down:(1,0)}
        if e.key() in dirs:
            b.move(*dirs[e.key()]); self._score_lbl.setText(f"Skor: {b.score}")
            if(b.won or b.lost) and self._user and b.score>0:
                post_score(GAME,self._user["id"],self._user["username"],b.score)
                self._sb.refresh()
