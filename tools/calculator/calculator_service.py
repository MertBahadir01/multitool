"""Calculator data access layer — plain text, per-user history."""

from database.database import get_connection


class CalculatorService:
    def __init__(self, user_id: int):
        self.user_id = user_id

    def add_entry(self, expression: str, result: str):
        conn = get_connection()
        conn.execute(
            "INSERT INTO calculator_history (user_id, expression, result) VALUES (?, ?, ?)",
            (self.user_id, expression, result)
        )
        conn.commit(); conn.close()

    def get_history(self, limit: int = 100):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM calculator_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (self.user_id, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def clear_history(self):
        conn = get_connection()
        conn.execute(
            "DELETE FROM calculator_history WHERE user_id=?",
            (self.user_id,)
        )
        conn.commit(); conn.close()