"""Snake — classic snake with QPainter, food, score, speed increase."""
import random
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QKeyEvent
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget, post_score

GAME="snake"; CELL=20; COLS=25; ROWS=20
W=COLS*CELL; H=ROWS*CELL

class SnakeCanvas(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(W,H)
        self.setStyleSheet("background:#111;border-radius:6px;")
        self._reset()
    def _reset(self):
        self.snake=[(COLS//2,ROWS//2),(COLS//2-1,ROWS//2),(COLS//2-2,ROWS//2)]
        self.dir=(1,0); self.next_dir=(1,0)
        self.score=0; self.alive=True
        self._spawn_food()
    def _spawn_food(self):
        empty=[(x,y) for x in range(COLS) for y in range(ROWS) if (x,y) not in self.snake]
        self.food=random.choice(empty) if empty else (0,0)
    def step(self):
        if not self.alive: return
        self.dir=self.next_dir
        head=(self.snake[0][0]+self.dir[0], self.snake[0][1]+self.dir[1])
        if not(0<=head[0]<COLS and 0<=head[1]<ROWS) or head in self.snake:
            self.alive=False; self.update(); return
        self.snake.insert(0,head)
        if head==self.food:
            self.score+=10; self._spawn_food()
        else:
            self.snake.pop()
        self.update()
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(0,0,W,H,QColor("#111"))
        # grid dots
        p.setPen(QColor("#1A1A1A"))
        for x in range(0,W,CELL):
            p.drawLine(x,0,x,H)
        for y in range(0,H,CELL):
            p.drawLine(0,y,W,y)
        # food
        fx,fy=self.food
        p.setBrush(QColor("#F44336")); p.setPen(Qt.NoPen)
        p.drawEllipse(fx*CELL+3,fy*CELL+3,CELL-6,CELL-6)
        # snake
        for i,(x,y) in enumerate(self.snake):
            color=QColor("#00BFA5") if i==0 else QColor("#007A69" if i%2==0 else "#00968A")
            p.setBrush(color)
            p.drawRoundedRect(x*CELL+1,y*CELL+1,CELL-2,CELL-2,4,4)
        if not self.alive:
            p.fillRect(0,0,W,H,QColor(0,0,0,140))
            p.setPen(QColor("#F44336")); p.setFont(QFont("Segoe UI",28,QFont.Bold))
            p.drawText(0,0,W,H,Qt.AlignCenter,"GAME OVER")
        p.end()

class SnakeTool(QWidget):
    name="Snake"; description="Classic snake game"
    def __init__(self,parent=None):
        super().__init__(parent)
        self._user=auth_manager.current_user
        self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("🐍 Snake"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch()
        hl.addWidget(QLabel("WASD / Ok tuşları ile yön",styleSheet="color:#555;font-size:12px;"))
        root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        self._score_lbl=QLabel("Skor: 0"); self._score_lbl.setFont(QFont("Segoe UI",14,QFont.Bold))
        self._score_lbl.setStyleSheet("color:#FF9800;"); left.addWidget(self._score_lbl)
        self._canvas=SnakeCanvas(); left.addWidget(self._canvas)
        btn_row=QHBoxLayout()
        self._start_btn=QPushButton("▶ Başla"); self._start_btn.clicked.connect(self._start)
        btn_row.addWidget(self._start_btn)
        left.addLayout(btn_row); body.addLayout(left)
        self._sb=ScoreboardWidget(GAME); self._sb.refresh(); body.addWidget(self._sb)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
        self._timer=QTimer(); self._timer.timeout.connect(self._tick)
        self._speed=150; self.setFocusPolicy(Qt.StrongFocus)
    def _start(self):
        self._canvas._reset(); self._speed=150
        self._timer.start(self._speed); self._start_btn.setText("🔄 Yeniden Başla")
        self.setFocus()
    def _tick(self):
        self._canvas.step()
        self._score_lbl.setText(f"Skor: {self._canvas.score}")
        if not self._canvas.alive:
            self._timer.stop()
            if self._user and self._canvas.score>0:
                post_score(GAME,self._user["id"],self._user["username"],self._canvas.score)
                self._sb.refresh()
        else:
            new_speed=max(60,150-self._canvas.score//30*10)
            if new_speed!=self._speed:
                self._speed=new_speed; self._timer.setInterval(self._speed)
    def keyPressEvent(self,e:QKeyEvent):
        d={Qt.Key_Up:(0,-1),Qt.Key_Down:(0,1),Qt.Key_Left:(-1,0),Qt.Key_Right:(1,0),
           Qt.Key_W:(0,-1),Qt.Key_S:(0,1),Qt.Key_A:(-1,0),Qt.Key_D:(1,0)}
        if e.key() in d:
            nd=d[e.key()]
            if (nd[0]+self._canvas.dir[0],nd[1]+self._canvas.dir[1])!=(0,0):
                self._canvas.next_dir=nd
