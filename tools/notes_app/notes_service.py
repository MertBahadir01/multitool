"""
Notes Service — DB-backed data layer for Quick Notes.
Follows vault_service.py pattern exactly.
No QSettings — everything lives in SQLite per user.
Images stored as BLOBs (raw bytes) in note_images table.
"""

import base64
import datetime
from database.database import get_connection


class NotesService:
    def __init__(self, user_id: int):
        self.user_id = user_id

    # ── Notes ──────────────────────────────────────────────────────────────────
    def get_notes(self, search: str = "") -> list[dict]:
        conn = get_connection()
        if search:
            q = search.lstrip("#").lower()
            rows = conn.execute(
                """SELECT * FROM quick_notes
                   WHERE user_id=?
                     AND (LOWER(title) LIKE ? OR LOWER(body) LIKE ? OR LOWER(tags) LIKE ?)
                   ORDER BY pinned DESC, updated_at DESC""",
                (self.user_id, f"%{q}%", f"%{q}%", f"%{q}%")
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM quick_notes
                   WHERE user_id=?
                   ORDER BY pinned DESC, updated_at DESC""",
                (self.user_id,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_note(self, note_id: int) -> dict | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM quick_notes WHERE id=? AND user_id=?",
            (note_id, self.user_id)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def add_note(self, title: str = "", body: str = "") -> int:
        now = datetime.datetime.now().isoformat()
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO quick_notes (user_id, title, body, tags, pinned, created_at, updated_at)
               VALUES (?,?,?,'',0,?,?)""",
            (self.user_id, title, body, now, now)
        )
        conn.commit()
        nid = cur.lastrowid
        conn.close()
        return nid

    def update_note(self, note_id: int, title: str, body: str):
        now = datetime.datetime.now().isoformat()
        conn = get_connection()
        conn.execute(
            "UPDATE quick_notes SET title=?, body=?, updated_at=? WHERE id=? AND user_id=?",
            (title, body, now, note_id, self.user_id)
        )
        conn.commit()
        conn.close()

    def set_pinned(self, note_id: int, pinned: bool):
        conn = get_connection()
        conn.execute(
            "UPDATE quick_notes SET pinned=? WHERE id=? AND user_id=?",
            (1 if pinned else 0, note_id, self.user_id)
        )
        conn.commit()
        conn.close()

    def set_tags(self, note_id: int, tags: list[str]):
        tag_str = ",".join(tags)
        conn = get_connection()
        conn.execute(
            "UPDATE quick_notes SET tags=? WHERE id=? AND user_id=?",
            (tag_str, note_id, self.user_id)
        )
        conn.commit()
        conn.close()

    def delete_note(self, note_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM note_images WHERE note_id=? AND user_id=?",
            (note_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM quick_notes WHERE id=? AND user_id=?",
            (note_id, self.user_id)
        )
        conn.commit()
        conn.close()

    # ── Images ─────────────────────────────────────────────────────────────────
    def get_images(self, note_id: int) -> list[dict]:
        """Returns list of {id, filename, mime_type, data_b64}."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, filename, mime_type, image_data FROM note_images "
            "WHERE note_id=? AND user_id=? ORDER BY id",
            (note_id, self.user_id)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                "id":        r[0],
                "filename":  r[1],
                "mime_type": r[2],
                "data_b64":  base64.b64encode(r[3]).decode() if r[3] else "",
            })
        return result

    def add_image(self, note_id: int, filename: str,
                  mime_type: str, raw_bytes: bytes) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO note_images (note_id, user_id, filename, mime_type, image_data) "
            "VALUES (?,?,?,?,?)",
            (note_id, self.user_id, filename, mime_type, raw_bytes)
        )
        conn.commit()
        iid = cur.lastrowid
        conn.close()
        return iid

    def delete_image(self, image_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM note_images WHERE id=? AND user_id=?",
            (image_id, self.user_id)
        )
        conn.commit()
        conn.close()

    def get_image_count(self, note_id: int) -> int:
        conn = get_connection()
        count = conn.execute(
            "SELECT COUNT(*) FROM note_images WHERE note_id=? AND user_id=?",
            (note_id, self.user_id)
        ).fetchone()[0]
        conn.close()
        return count