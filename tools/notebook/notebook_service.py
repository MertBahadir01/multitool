"""Notebook data-access layer.

Schema:
    notebook_categories    (id, user_id, name, created_at)
    notebook_people        (id, category_id, user_id, name, created_at)
    notebook_notes         (id, person_id, user_id,
                            encrypted_content BLOB,
                            created_at, updated_at)
    notebook_note_images   (id, note_id, user_id,
                            filename TEXT,
                            mime_type TEXT,
                            encrypted_image BLOB,     ← raw bytes encrypted
                            created_at)

Only `encrypted_content` and `encrypted_image` are encrypted.
Everything else (names, dates, user_id) is stored in plain text.
"""

import base64
from database.database import get_connection
from services.encryption_service import encrypt, decrypt


class NotebookService:
    def __init__(self, user_id: int, master_password: str):
        self.user_id = user_id
        self.master_password = master_password

    # ── categories ────────────────────────────────────────────────────────────
    def get_categories(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM notebook_categories WHERE user_id=? ORDER BY name",
            (self.user_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_category(self, name: str) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO notebook_categories (user_id, name) VALUES (?,?)",
            (self.user_id, name)
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    def delete_category(self, cat_id: int):
        conn = get_connection()
        # cascade: images → notes → people → category
        conn.execute(
            """DELETE FROM notebook_note_images WHERE note_id IN (
                SELECT n.id FROM notebook_notes n
                JOIN notebook_people p ON n.person_id = p.id
                WHERE p.category_id=? AND p.user_id=?
            )""",
            (cat_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_notes WHERE person_id IN "
            "(SELECT id FROM notebook_people WHERE category_id=? AND user_id=?)",
            (cat_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_people WHERE category_id=? AND user_id=?",
            (cat_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_categories WHERE id=? AND user_id=?",
            (cat_id, self.user_id)
        )
        conn.commit()
        conn.close()

    # ── people ────────────────────────────────────────────────────────────────
    def get_people(self, cat_id: int) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM notebook_people WHERE category_id=? AND user_id=? ORDER BY name",
            (cat_id, self.user_id)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_person(self, cat_id: int, name: str) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO notebook_people (category_id, user_id, name) VALUES (?,?,?)",
            (cat_id, self.user_id, name)
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    def delete_person(self, person_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM notebook_note_images WHERE note_id IN "
            "(SELECT id FROM notebook_notes WHERE person_id=? AND user_id=?)",
            (person_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_notes WHERE person_id=? AND user_id=?",
            (person_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_people WHERE id=? AND user_id=?",
            (person_id, self.user_id)
        )
        conn.commit()
        conn.close()

    # ── notes ─────────────────────────────────────────────────────────────────
    def get_notes(self, person_id: int) -> list[dict]:
        """Return notes with content decrypted."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM notebook_notes WHERE person_id=? AND user_id=? ORDER BY created_at",
            (person_id, self.user_id)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["content"] = decrypt(d["encrypted_content"], self.master_password)
            except Exception:
                d["content"] = "⚠️  Could not decrypt this note."
            result.append(d)
        return result

    def add_note(self, person_id: int, content: str = "") -> int:
        enc = encrypt(content, self.master_password)
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO notebook_notes (person_id, user_id, encrypted_content) VALUES (?,?,?)",
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
        conn.commit()
        conn.close()

    def delete_note(self, note_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM notebook_note_images WHERE note_id=? AND user_id=?",
            (note_id, self.user_id)
        )
        conn.execute(
            "DELETE FROM notebook_notes WHERE id=? AND user_id=?",
            (note_id, self.user_id)
        )
        conn.commit()
        conn.close()

    # ── images ────────────────────────────────────────────────────────────────
    def get_images(self, note_id: int) -> list[dict]:
        """Return list of {id, filename, mime_type, data_b64} — decrypted."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, filename, mime_type, encrypted_image "
            "FROM notebook_note_images WHERE note_id=? AND user_id=? ORDER BY id",
            (note_id, self.user_id)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            try:
                raw_bytes = decrypt(r[3], self.master_password)
                # decrypt returns str; we stored as base64-encoded string then encrypted
                data_b64 = raw_bytes
            except Exception:
                data_b64 = ""
            result.append({
                "id":        r[0],
                "filename":  r[1],
                "mime_type": r[2],
                "data_b64":  data_b64,
            })
        return result

    def add_image(self, note_id: int, filename: str,
                  mime_type: str, raw_bytes: bytes) -> int:
        # Convert raw bytes → base64 string → encrypt
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        enc = encrypt(b64, self.master_password)
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO notebook_note_images "
            "(note_id, user_id, filename, mime_type, encrypted_image) VALUES (?,?,?,?,?)",
            (note_id, self.user_id, filename, mime_type, enc)
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    def delete_image(self, image_id: int):
        conn = get_connection()
        conn.execute(
            "DELETE FROM notebook_note_images WHERE id=? AND user_id=?",
            (image_id, self.user_id)
        )
        conn.commit()
        conn.close()

    def get_image_count(self, note_id: int) -> int:
        conn = get_connection()
        count = conn.execute(
            "SELECT COUNT(*) FROM notebook_note_images WHERE note_id=? AND user_id=?",
            (note_id, self.user_id)
        ).fetchone()[0]
        conn.close()
        return count