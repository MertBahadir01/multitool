"""Reaction Time Test — millisecond precision, random delay, history, leaderboard."""
import random, time
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame,QTableWidget,QTableWidgetItem,QHeaderView
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QFont,QColor
from core.auth_manager import auth_manager
from tools.game_scores.game_scores import ScoreboardWidget,post_score,get_top_scores

GAME="reaction_time"

class ReactionTimeTool(QWidget):
    name="Reaction Time"; description="Measure your reaction speed in milliseconds"
    def __init__(self,parent=None):
        super().__init__(parent); self._user=auth_manager.current_user
        self._state="idle"; self._start_ms=0; self._results=[]; self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0)
        hdr=QFrame(); hdr.setStyleSheet("background:#1E1E1E;border-bottom:1px solid #3E3E3E;")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t=QLabel("⚡ Reaction Time"); t.setFont(QFont("Segoe UI",18,QFont.Bold)); t.setStyleSheet("color:#00BFA5;")
        hl.addWidget(t); hl.addStretch(); root.addWidget(hdr)
        body=QHBoxLayout(); body.setContentsMargins(20,20,20,20); body.setSpacing(20)
        left=QVBoxLayout()
        # big button
        self._btn=QPushButton("Başlamak için tıkla")
        self._btn.setFixedSize(380,280)
        self._btn.setFont(QFont("Segoe UI",18,QFont.Bold))
        self._btn.clicked.connect(self._on_click)
        self._set_idle_style(); left.addWidget(self._btn,0,Qt.AlignCenter)
        # result labels
        self._result_lbl=QLabel(""); self._result_lbl.setAlignment(Qt.AlignCenter)
        self._result_lbl.setFont(QFont("Segoe UI",14)); self._result_lbl.setStyleSheet("color:#888;"); left.addWidget(self._result_lbl)
        self._avg_lbl=QLabel(""); self._avg_lbl.setAlignment(Qt.AlignCenter)
        self._avg_lbl.setStyleSheet("color:#555;font-size:12px;"); left.addWidget(self._avg_lbl)
        # history table
        left.addWidget(QLabel("Son denemeler:",styleSheet="color:#888;font-size:12px;"))
        self._hist=QTableWidget(0,2); self._hist.setHorizontalHeaderLabels(["#","ms"])
        self._hist.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self._hist.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self._hist.setEditTriggers(QTableWidget.NoEditTriggers); self._hist.setMaximumHeight(160)
        self._hist.setStyleSheet("background:#1A1A1A;border:none;font-size:12px;")
        left.addWidget(self._hist)
        reset_btn=QPushButton("🔄 Sıfırla"); reset_btn.clicked.connect(self._reset_results); left.addWidget(reset_btn)
        body.addLayout(left)
        # leaderboard — for reaction time, LOWER = better, so we store negative score
        right=QVBoxLayout()
        right.addWidget(QLabel("🏆 En Hızlılar (ms)",styleSheet="color:#FFD700;font-size:12px;font-weight:bold;"))
        self._lb_tbl=QTableWidget(0,3); self._lb_tbl.setHorizontalHeaderLabels(["#","Oyuncu","ms"])
        self._lb_tbl.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self._lb_tbl.setEditTriggers(QTableWidget.NoEditTriggers); self._lb_tbl.setStyleSheet("background:#1A1A1A;border:none;font-size:12px;")
        right.addWidget(self._lb_tbl,1); body.addLayout(right)
        w=QWidget(); w.setLayout(body); root.addWidget(w,1)
        self._delay_timer=QTimer(); self._delay_timer.setSingleShot(True); self._delay_timer.timeout.connect(self._go_green)
        self._refresh_lb()
    def _set_idle_style(self):
        self._btn.setStyleSheet("background:#252525;border:2px solid #3A3A3A;border-radius:16px;color:#888;")
    def _on_click(self):
        if self._state=="idle":
            self._state="waiting"
            self._btn.setText("Bekle…")
            self._btn.setStyleSheet("background:#FF9800;border:none;border-radius:16px;color:#000;font-size:18px;font-weight:bold;")
            self._delay_timer.start(random.randint(1000,4000))
        elif self._state=="waiting":
            self._delay_timer.stop(); self._state="idle"
            self._btn.setText("Çok erken! Tekrar tıkla")
            self._btn.setStyleSheet("background:#F44336;border:none;border-radius:16px;color:#fff;font-size:16px;font-weight:bold;")
        elif self._state=="green":
            ms=int((time.perf_counter()-self._start_ms)*1000)
            self._state="idle"; self._results.append(ms)
            self._btn.setText(f"{ms} ms\n\nTekrar için tıkla")
            color="#4CAF50" if ms<200 else("#FF9800" if ms<350 else "#F44336")
            self._btn.setStyleSheet(f"background:{color};border:none;border-radius:16px;color:#fff;font-size:22px;font-weight:bold;")
            self._result_lbl.setText(self._rating(ms)); self._update_history()
            if self._user:
                post_score(GAME,self._user["id"],self._user["username"],10000-ms)
                self._refresh_lb()
    def _go_green(self):
        self._state="green"; self._start_ms=time.perf_counter()
        self._btn.setText("TIKLA!")
        self._btn.setStyleSheet("background:#4CAF50;border:none;border-radius:16px;color:#fff;font-size:28px;font-weight:bold;")
    def _rating(self,ms):
        if ms<150: return "⚡ İnanılmaz hız!"
        if ms<200: return "🚀 Çok hızlı"
        if ms<250: return "✅ Hızlı"
        if ms<350: return "👍 Ortalama"
        return "🐢 Yavaş"
    def _update_history(self):
        self._hist.setRowCount(0)
        for i,ms in enumerate(reversed(self._results[-10:])):
            r=self._hist.rowCount(); self._hist.insertRow(r)
            self._hist.setItem(r,0,QTableWidgetItem(str(len(self._results)-i)))
            item=QTableWidgetItem(f"{ms} ms")
            item.setForeground(QColor("#4CAF50" if ms<250 else("#FF9800" if ms<350 else "#F44336")))
            self._hist.setItem(r,1,item)
        if self._results:
            avg=sum(self._results)/len(self._results)
            self._avg_lbl.setText(f"Ortalama: {avg:.0f} ms  |  En iyi: {min(self._results)} ms  |  {len(self._results)} deneme")
    def _reset_results(self):
        self._results=[]; self._avg_lbl.setText(""); self._hist.setRowCount(0)
        self._result_lbl.setText(""); self._btn.setText("Başlamak için tıkla"); self._set_idle_style()
        self._state="idle"
    def _refresh_lb(self):
        # scores stored as 10000-ms, so higher = faster
        scores=get_top_scores(GAME,10)
        self._lb_tbl.setRowCount(0)
        medals=["🥇","🥈","🥉"]
        for i,s in enumerate(scores):
            ms=10000-s["score"]
            r=self._lb_tbl.rowCount(); self._lb_tbl.insertRow(r)
            self._lb_tbl.setItem(r,0,QTableWidgetItem(medals[i] if i<3 else str(i+1)))
            ni=QTableWidgetItem(s["username"])
            if i==0: ni.setForeground(QColor("#FFD700"))
            self._lb_tbl.setItem(r,1,ni)
            self._lb_tbl.setItem(r,2,QTableWidgetItem(f"{ms} ms"))