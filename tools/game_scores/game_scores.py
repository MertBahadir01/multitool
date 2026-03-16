"""Shared scoreboard service + widget — used by every game tool."""
from database.database import get_connection
from core.auth_manager import auth_manager

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtGui import QFont


# ── DB helpers ────────────────────────────────────────────────────────────────

def post_score(game_id: str, user_id: int, username: str, score: int):
    conn = get_connection()
    conn.execute(
        "INSERT INTO game_scores (game_id, user_id, username, score) VALUES (?,?,?,?)",
        (game_id, user_id, username, score)
    )
    conn.commit(); conn.close()


def get_top_scores(game_id: str, limit: int = 10) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT username, score, created_at FROM game_scores "
        "WHERE game_id=? ORDER BY score DESC LIMIT ?",
        (game_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_best(game_id: str, user_id: int):
    conn = get_connection()
    row = conn.execute(
        "SELECT MAX(score) FROM game_scores WHERE game_id=? AND user_id=?",
        (game_id, user_id)
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None


# ── Reusable leaderboard widget ───────────────────────────────────────────────

class ScoreboardWidget(QWidget):
    """
    Drop-in leaderboard panel for any game.
    Usage:
        self._sb = ScoreboardWidget("snake")
        self._sb.refresh()
        layout.addWidget(self._sb)

    Call self._sb.refresh() after posting a new score.
    """

    def __init__(self, game_id: str, limit: int = 10, parent=None):
        super().__init__(parent)
        self._game_id = game_id
        self._limit   = limit
        self._build_ui()
        self.setMaximumWidth(260)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        self.setStyleSheet("background:#1A1A1A; border-radius:8px;")

        title = QLabel("🏆 Leaderboard")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color:#FF9800; background:transparent;")
        lay.addWidget(title)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Player", "Score", "Date"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget { background:#111; border:none; font-size:12px; }
            QHeaderView::section { background:#252525; color:#888; border:none; padding:4px; }
            QTableWidget::item { padding:3px 6px; }
        """)
        lay.addWidget(self._table, 1)

        self._your_best_lbl = QLabel("")
        self._your_best_lbl.setStyleSheet(
            "color:#888; font-size:11px; background:transparent;")
        lay.addWidget(self._your_best_lbl)

    def refresh(self):
        scores = get_top_scores(self._game_id, self._limit)
        self._table.setRowCount(0)
        medals = ["🥇", "🥈", "🥉"]
        for i, s in enumerate(scores):
            r = self._table.rowCount()
            self._table.insertRow(r)
            prefix = medals[i] if i < 3 else f"{i+1}."
            self._table.setItem(r, 0, QTableWidgetItem(f"{prefix} {s['username']}"))
            self._table.setItem(r, 1, QTableWidgetItem(str(s["score"])))
            self._table.setItem(r, 2, QTableWidgetItem(str(s["created_at"])[:10]))

        user = auth_manager.current_user
        if user:
            best = get_user_best(self._game_id, user["id"])
            self._your_best_lbl.setText(
                f"Your best: {best}" if best is not None else "No score yet"
            )