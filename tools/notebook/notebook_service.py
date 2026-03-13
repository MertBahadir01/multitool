"""Notebook data access layer — mirrors VaultService pattern."""

from database.database import get_connection
from services.encryption_service import encrypt, decrypt


class NotebookService:
    def __init__(self, user_id: int, master_password: str):
        self.user_id = user_id
        self.master_password = master_password

    # ── Categories ─────────────────────────────────────────────────────────────
    def get_categories(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM notebook_categories WHERE user_id=? ORDER BY name",
            (self.user_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_category(self, name: str):
        conn = get_connection()
        conn.execute(
            "INSERT INTO notebook_categories (user_id, name) VALUES (?, ?)",
            (self.user_id, name)
        )
        conn.commit(); conn.close()

    def delete_category(self, cat_id: int):
        conn = get_connection()
        people = conn.execute(
            "SELECT id FROM notebook_people WHERE category_id=? AND user_id=?",
            (cat_id, self.user_id)
        ).fetchall()
        for p in people:
            conn.execute(
                "DELETE FROM notebook_notes WHERE person_id=? AND user_id=?",
                (p["id"], self.user_id)
            )
        conn.execute(
            "DELETE FROM notebook_people WHERE category_id=? AND user_id=?",
            (cat_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_categories WHERE id=? AND user_id=?",
            (cat_id, self.user_id)
        )
        conn.commit(); conn.close()

    # ── People ─────────────────────────────────────────────────────────────────
    def get_people(self, cat_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM notebook_people WHERE category_id=? AND user_id=? ORDER BY name",
            (cat_id, self.user_id)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_person(self, cat_id: int, name: str):
        conn = get_connection()
        conn.execute(
            "INSERT INTO notebook_people (category_id, user_id, name) VALUES (?, ?, ?)",
            (cat_id, self.user_id, name)
        )
        conn.commit(); conn.close()

    def delete_person(self, person_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM notebook_notes WHERE person_id=? AND user_id=?",
            (person_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_people WHERE id=? AND user_id=?",
            (person_id, self.user_id)
        )
        conn.commit(); conn.close()

    # ── Notes ──────────────────────────────────────────────────────────────────
    def get_notes(self, person_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM notebook_notes WHERE person_id=? AND user_id=? ORDER BY updated_at DESC",
            (person_id, self.user_id)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["content"] = decrypt(d["encrypted_content"], self.master_password)
            except Exception:
                d["content"] = "[decryption error]"
            result.append(d)
        return result

    def add_note(self, person_id: int, content: str = "") -> int:
        enc = encrypt(content, self.master_password)
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO notebook_notes (person_id, user_id, encrypted_content) VALUES (?, ?, ?)",
            (person_id, self.user_id, enc)
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    def update_note(self, note_id: int, content: str):
        enc = encrypt(content, self.master_password)
        conn = get_connection()
        conn.execute(
            "UPDATE notebook_notes SET encrypted_content=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND user_id=?",
            (enc, note_id, self.user_id)
        )
        conn.commit(); conn.close()

    def delete_note(self, note_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM notebook_notes WHERE id=? AND user_id=?",
            (note_id, self.user_id)
        )
        conn.commit(); conn.close()