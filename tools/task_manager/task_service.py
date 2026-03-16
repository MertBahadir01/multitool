"""Task Manager data-access layer — follows vault_service.py pattern exactly."""

from database.database import get_connection


class TaskService:
    def __init__(self, user_id: int):
        self.user_id = user_id

    # ── Lists ──────────────────────────────────────────────────────────────────
    def get_lists(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM task_lists WHERE user_id=? ORDER BY position, created_at",
            (self.user_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_list(self, name: str, color: str = "#00BFA5") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO task_lists (user_id, name, color) VALUES (?,?,?)",
            (self.user_id, name, color)
        )
        conn.commit(); lid = cur.lastrowid; conn.close()
        return lid

    def rename_list(self, list_id: int, name: str, color: str):
        conn = get_connection()
        conn.execute(
            "UPDATE task_lists SET name=?, color=? WHERE id=? AND user_id=?",
            (name, color, list_id, self.user_id)
        )
        conn.commit(); conn.close()

    def delete_list(self, list_id: int):
        conn = get_connection()
        # cascade: subtasks → tasks → list
        conn.execute(
            """DELETE FROM task_subtasks WHERE task_id IN
               (SELECT id FROM tasks WHERE list_id=? AND user_id=?)""",
            (list_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM tasks WHERE list_id=? AND user_id=?",
            (list_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM task_lists WHERE id=? AND user_id=?",
            (list_id, self.user_id)
        )
        conn.commit(); conn.close()

    # ── Tasks ──────────────────────────────────────────────────────────────────
    def get_tasks(self, list_id: int = None, status: str = None,
                  priority: str = None, search: str = "") -> list:
        conn = get_connection()
        q = "SELECT * FROM tasks WHERE user_id=?"
        params: list = [self.user_id]
        if list_id is not None:
            q += " AND list_id=?"
            params.append(list_id)
        if status:
            q += " AND status=?"
            params.append(status)
        if priority:
            q += " AND priority=?"
            params.append(priority)
        if search:
            q += " AND (title LIKE ? OR description LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        q += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date, position"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_tasks_due_today(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE user_id=? AND status='pending'
                 AND due_date <= DATE('now')
                 AND due_date != ''
               ORDER BY due_date, priority""",
            (self.user_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_tasks_upcoming(self) -> list:
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE user_id=? AND status='pending'
                 AND due_date > DATE('now')
                 AND due_date != ''
               ORDER BY due_date""",
            (self.user_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_task(self, list_id: int, title: str, description: str = "",
                 due_date: str = "", priority: str = "medium",
                 reminder: str = "") -> int:
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO tasks
               (user_id, list_id, title, description, due_date, priority, reminder)
               VALUES (?,?,?,?,?,?,?)""",
            (self.user_id, list_id, title, description, due_date, priority, reminder)
        )
        conn.commit(); tid = cur.lastrowid; conn.close()
        return tid

    def update_task(self, task_id: int, title: str, description: str,
                    due_date: str, priority: str, reminder: str):
        conn = get_connection()
        conn.execute(
            """UPDATE tasks SET title=?, description=?, due_date=?,
               priority=?, reminder=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND user_id=?""",
            (title, description, due_date, priority, reminder, task_id, self.user_id)
        )
        conn.commit(); conn.close()

    def set_status(self, task_id: int, status: str):
        """status: 'pending' | 'completed'"""
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
            (status, task_id, self.user_id)
        )
        conn.commit(); conn.close()

    def delete_task(self, task_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM task_subtasks WHERE task_id=? AND user_id=?",
            (task_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM tasks WHERE id=? AND user_id=?",
            (task_id, self.user_id)
        )
        conn.commit(); conn.close()

    def move_task(self, task_id: int, new_list_id: int):
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET list_id=? WHERE id=? AND user_id=?",
            (new_list_id, task_id, self.user_id)
        )
        conn.commit(); conn.close()

    # ── Subtasks ───────────────────────────────────────────────────────────────
    def get_subtasks(self, task_id: int) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM task_subtasks WHERE task_id=? AND user_id=? ORDER BY position, id",
            (task_id, self.user_id)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_subtask(self, task_id: int, title: str) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO task_subtasks (task_id, user_id, title) VALUES (?,?,?)",
            (task_id, self.user_id, title)
        )
        conn.commit(); sid = cur.lastrowid; conn.close()
        return sid

    def set_subtask_done(self, subtask_id: int, done: bool):
        conn = get_connection()
        conn.execute(
            "UPDATE task_subtasks SET done=? WHERE id=? AND user_id=?",
            (1 if done else 0, subtask_id, self.user_id)
        )
        conn.commit(); conn.close()

    def delete_subtask(self, subtask_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM task_subtasks WHERE id=? AND user_id=?",
            (subtask_id, self.user_id)
        )
        conn.commit(); conn.close()

    # ── Stats ──────────────────────────────────────────────────────────────────
    def get_stats(self, list_id: int = None) -> dict:
        conn = get_connection()
        base = "SELECT COUNT(*) FROM tasks WHERE user_id=?"
        params = [self.user_id]
        if list_id:
            base += " AND list_id=?"; params.append(list_id)

        total     = conn.execute(base, params).fetchone()[0]
        completed = conn.execute(base + (" AND list_id=? AND " if list_id else " AND ") + "status='completed'"
                                 if list_id else base + " AND status='completed'",
                                 params + ([list_id] if list_id else [])).fetchone()[0]
        # simpler approach
        if list_id:
            total     = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND list_id=?",
                                     (self.user_id, list_id)).fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND list_id=? AND status='completed'",
                                     (self.user_id, list_id)).fetchone()[0]
            overdue   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id=? AND list_id=? AND status='pending' AND due_date<DATE('now') AND due_date!=''",
                (self.user_id, list_id)).fetchone()[0]
        else:
            total     = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (self.user_id,)).fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='completed'",
                                     (self.user_id,)).fetchone()[0]
            overdue   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id=? AND status='pending' AND due_date<DATE('now') AND due_date!=''",
                (self.user_id,)).fetchone()[0]
        conn.close()
        return {"total": total, "completed": completed,
                "pending": total - completed, "overdue": overdue}