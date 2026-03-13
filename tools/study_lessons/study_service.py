"""Shared data-access layer for all Study tools.

Encryption key = user's password_hash (already stored, unique per user).
No separate master-password prompt needed.

All sensitive content columns are encrypted BLOBs.
Plain-text columns: names, dates, user_id, subject, numeric scores.
"""

import json
from database.database import get_connection
from services.encryption_service import encrypt, decrypt


def _key(user) -> str:
    """Derive a stable per-user key from the stored password hash."""
    return user["password_hash"]


# ── Lessons ────────────────────────────────────────────────────────────────────

class LessonsService:
    def __init__(self, user):
        self.uid = user["id"]
        self._key = _key(user)

    def get_lessons(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_lessons WHERE user_id=? ORDER BY name",
            (self.uid,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_lesson(self, name: str) -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_lessons (user_id, name) VALUES (?,?)",
            (self.uid, name)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def delete_lesson(self, lesson_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_lesson_resources WHERE lesson_id=? AND user_id=?", (lesson_id, self.uid))
        conn.execute("DELETE FROM study_lessons WHERE id=? AND user_id=?", (lesson_id, self.uid))
        conn.commit(); conn.close()

    def set_completed(self, lesson_id: int, completed: bool):
        conn = get_connection()
        conn.execute(
            "UPDATE study_lessons SET completed=? WHERE id=? AND user_id=?",
            (1 if completed else 0, lesson_id, self.uid)
        )
        conn.commit(); conn.close()

    # resources
    def get_resources(self, lesson_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_lesson_resources WHERE lesson_id=? AND user_id=? ORDER BY created_at",
            (lesson_id, self.uid)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["content"] = decrypt(d["encrypted_content"], self._key)
            except Exception:
                d["content"] = ""
            result.append(d)
        return result

    def add_resource(self, lesson_id: int, rtype: str, content: str) -> int:
        """rtype: 'text' | 'image' | 'file'"""
        enc = encrypt(content, self._key)
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_lesson_resources (lesson_id, user_id, resource_type, encrypted_content) VALUES (?,?,?,?)",
            (lesson_id, self.uid, rtype, enc)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def delete_resource(self, res_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_lesson_resources WHERE id=? AND user_id=?", (res_id, self.uid))
        conn.commit(); conn.close()


# ── Exam Logs ──────────────────────────────────────────────────────────────────

class ExamService:
    def __init__(self, user):
        self.uid = user["id"]
        self._key = _key(user)

    def get_sessions(self, exam_type: str = None):
        conn = get_connection()
        if exam_type:
            rows = conn.execute(
                "SELECT * FROM study_exam_sessions WHERE user_id=? AND exam_type=? ORDER BY session_date DESC",
                (self.uid, exam_type)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM study_exam_sessions WHERE user_id=? ORDER BY session_date DESC",
                (self.uid,)
            ).fetchall()
        conn.close()
        sessions = []
        for r in rows:
            d = dict(r)
            try:
                d["notes"] = decrypt(d["encrypted_notes"], self._key) if d["encrypted_notes"] else ""
            except Exception:
                d["notes"] = ""
            sessions.append(d)
        return sessions

    def add_session(self, exam_type: str, session_date: str, notes: str = "") -> int:
        enc_notes = encrypt(notes, self._key) if notes else None
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_exam_sessions (user_id, exam_type, session_date, encrypted_notes) VALUES (?,?,?,?)",
            (self.uid, exam_type, session_date, enc_notes)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def delete_session(self, session_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_exam_scores WHERE session_id=? AND user_id=?", (session_id, self.uid))
        conn.execute("DELETE FROM study_exam_sessions WHERE id=? AND user_id=?", (session_id, self.uid))
        conn.commit(); conn.close()

    def get_scores(self, session_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_exam_scores WHERE session_id=? AND user_id=? ORDER BY subject",
            (session_id, self.uid)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_score(self, session_id: int, subject: str, correct: int, incorrect: int, empty: int = 0):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO study_exam_scores (session_id, user_id, subject, correct, incorrect, empty) VALUES (?,?,?,?,?,?)",
            (session_id, self.uid, subject, correct, incorrect, empty)
        )
        conn.commit(); conn.close()

    def get_subject_history(self, subject: str, exam_type: str = None):
        """Returns all scores for a subject across sessions, ordered by date."""
        conn = get_connection()
        if exam_type:
            rows = conn.execute(
                """SELECT sc.*, ss.session_date, ss.exam_type
                   FROM study_exam_scores sc
                   JOIN study_exam_sessions ss ON sc.session_id = ss.id
                   WHERE sc.user_id=? AND sc.subject=? AND ss.exam_type=?
                   ORDER BY ss.session_date""",
                (self.uid, subject, exam_type)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT sc.*, ss.session_date, ss.exam_type
                   FROM study_exam_scores sc
                   JOIN study_exam_sessions ss ON sc.session_id = ss.id
                   WHERE sc.user_id=? AND sc.subject=?
                   ORDER BY ss.session_date""",
                (self.uid, subject)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestService:
    def __init__(self, user):
        self.uid = user["id"]
        self._key = _key(user)

    def get_tests(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_tests WHERE user_id=? ORDER BY created_at DESC",
            (self.uid,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_test(self, title: str, subject: str = "") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_tests (user_id, title, subject) VALUES (?,?,?)",
            (self.uid, title, subject)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def delete_test(self, test_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_test_questions WHERE test_id=? AND user_id=?", (test_id, self.uid))
        conn.execute("DELETE FROM study_tests WHERE id=? AND user_id=?", (test_id, self.uid))
        conn.commit(); conn.close()

    def get_questions(self, test_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_test_questions WHERE test_id=? AND user_id=? ORDER BY position",
            (test_id, self.uid)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["question_text"] = decrypt(d["enc_question"], self._key) if d["enc_question"] else ""
            except Exception:
                d["question_text"] = ""
            try:
                d["solution_text"] = decrypt(d["enc_solution"], self._key) if d["enc_solution"] else ""
            except Exception:
                d["solution_text"] = ""
            # image data is already base64 string, stored encrypted
            try:
                d["question_image"] = decrypt(d["enc_question_image"], self._key) if d["enc_question_image"] else ""
            except Exception:
                d["question_image"] = ""
            try:
                d["solution_image"] = decrypt(d["enc_solution_image"], self._key) if d["enc_solution_image"] else ""
            except Exception:
                d["solution_image"] = ""
            result.append(d)
        return result

    def add_question(self, test_id: int, position: int, question_text: str = "",
                     solution_text: str = "", question_image_b64: str = "",
                     solution_image_b64: str = "") -> int:
        enc_q  = encrypt(question_text, self._key) if question_text else None
        enc_s  = encrypt(solution_text, self._key) if solution_text else None
        enc_qi = encrypt(question_image_b64, self._key) if question_image_b64 else None
        enc_si = encrypt(solution_image_b64, self._key) if solution_image_b64 else None
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_test_questions (test_id, user_id, position, enc_question, enc_solution, enc_question_image, enc_solution_image) VALUES (?,?,?,?,?,?,?)",
            (test_id, self.uid, position, enc_q, enc_s, enc_qi, enc_si)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def update_question(self, q_id: int, question_text: str, solution_text: str,
                        question_image_b64: str, solution_image_b64: str):
        enc_q  = encrypt(question_text, self._key) if question_text else None
        enc_s  = encrypt(solution_text, self._key) if solution_text else None
        enc_qi = encrypt(question_image_b64, self._key) if question_image_b64 else None
        enc_si = encrypt(solution_image_b64, self._key) if solution_image_b64 else None
        conn = get_connection()
        conn.execute(
            "UPDATE study_test_questions SET enc_question=?, enc_solution=?, enc_question_image=?, enc_solution_image=? WHERE id=? AND user_id=?",
            (enc_q, enc_s, enc_qi, enc_si, q_id, self.uid)
        )
        conn.commit(); conn.close()

    def delete_question(self, q_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_test_questions WHERE id=? AND user_id=?", (q_id, self.uid))
        conn.commit(); conn.close()


# ── Flashcards ─────────────────────────────────────────────────────────────────

class FlashcardService:
    def __init__(self, user):
        self.uid = user["id"]
        self._key = _key(user)

    def get_decks(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_flashcard_decks WHERE user_id=? ORDER BY name",
            (self.uid,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_deck(self, name: str, subject: str = "") -> int:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_flashcard_decks (user_id, name, subject) VALUES (?,?,?)",
            (self.uid, name, subject)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def delete_deck(self, deck_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_flashcards WHERE deck_id=? AND user_id=?", (deck_id, self.uid))
        conn.execute("DELETE FROM study_flashcard_decks WHERE id=? AND user_id=?", (deck_id, self.uid))
        conn.commit(); conn.close()

    def get_cards(self, deck_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_flashcards WHERE deck_id=? AND user_id=? ORDER BY next_review",
            (deck_id, self.uid)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try: d["front"] = decrypt(d["enc_front"], self._key)
            except: d["front"] = ""
            try: d["back"] = decrypt(d["enc_back"], self._key)
            except: d["back"] = ""
            try: d["image_b64"] = decrypt(d["enc_image"], self._key) if d["enc_image"] else ""
            except: d["image_b64"] = ""
            result.append(d)
        return result

    def add_card(self, deck_id: int, front: str, back: str, image_b64: str = "") -> int:
        enc_f = encrypt(front, self._key)
        enc_b = encrypt(back, self._key)
        enc_i = encrypt(image_b64, self._key) if image_b64 else None
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_flashcards (deck_id, user_id, enc_front, enc_back, enc_image) VALUES (?,?,?,?,?)",
            (deck_id, self.uid, enc_f, enc_b, enc_i)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def update_review(self, card_id: int, ease: int):
        """ease: 1=again, 2=hard, 3=good, 4=easy — simple SM-2 like interval."""
        intervals = {1: 1, 2: 2, 3: 4, 4: 7}
        days = intervals.get(ease, 1)
        conn = get_connection()
        conn.execute(
            "UPDATE study_flashcards SET ease_factor=?, review_count=review_count+1, "
            "next_review=DATE('now', ? || ' days') WHERE id=? AND user_id=?",
            (ease, f"+{days}", card_id, self.uid)
        )
        conn.commit(); conn.close()

    def delete_card(self, card_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_flashcards WHERE id=? AND user_id=?", (card_id, self.uid))
        conn.commit(); conn.close()


# ── Timer ──────────────────────────────────────────────────────────────────────

class TimerService:
    def __init__(self, user):
        self.uid = user["id"]

    def log_session(self, subject: str, duration_minutes: int, session_type: str = "focus"):
        conn = get_connection()
        conn.execute(
            "INSERT INTO study_timer_sessions (user_id, subject, duration_minutes, session_type) VALUES (?,?,?,?)",
            (self.uid, subject, duration_minutes, session_type)
        )
        conn.commit(); conn.close()

    def get_sessions(self, limit: int = 200):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_timer_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (self.uid, limit)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_totals_by_subject(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT subject, SUM(duration_minutes) as total_minutes FROM study_timer_sessions "
            "WHERE user_id=? AND session_type='focus' GROUP BY subject ORDER BY total_minutes DESC",
            (self.uid,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# ── Resources ──────────────────────────────────────────────────────────────────

class ResourceService:
    def __init__(self, user):
        self.uid = user["id"]
        self._key = _key(user)

    def get_resources(self, search: str = "", tag: str = ""):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_resources WHERE user_id=? ORDER BY created_at DESC",
            (self.uid,)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try: d["title"] = decrypt(d["enc_title"], self._key)
            except: d["title"] = ""
            try: d["url_or_path"] = decrypt(d["enc_url"], self._key) if d["enc_url"] else ""
            except: d["url_or_path"] = ""
            if search and search.lower() not in d["title"].lower() and search.lower() not in (d.get("tags") or "").lower():
                continue
            if tag and tag not in (d.get("tags") or ""):
                continue
            result.append(d)
        return result

    def add_resource(self, title: str, rtype: str, url_or_path: str, tags: str = "") -> int:
        enc_t = encrypt(title, self._key)
        enc_u = encrypt(url_or_path, self._key) if url_or_path else None
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_resources (user_id, enc_title, resource_type, enc_url, tags) VALUES (?,?,?,?,?)",
            (self.uid, enc_t, rtype, enc_u, tags)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def delete_resource(self, res_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_resources WHERE id=? AND user_id=?", (res_id, self.uid))
        conn.commit(); conn.close()


# ── Goals ──────────────────────────────────────────────────────────────────────

class GoalService:
    def __init__(self, user):
        self.uid = user["id"]
        self._key = _key(user)

    def get_goals(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_goals WHERE user_id=? ORDER BY deadline",
            (self.uid,)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try: d["title"] = decrypt(d["enc_title"], self._key)
            except: d["title"] = ""
            try: d["description"] = decrypt(d["enc_description"], self._key) if d["enc_description"] else ""
            except: d["description"] = ""
            result.append(d)
        return result

    def add_goal(self, title: str, description: str, deadline: str, goal_type: str = "short") -> int:
        enc_t = encrypt(title, self._key)
        enc_d = encrypt(description, self._key) if description else None
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO study_goals (user_id, enc_title, enc_description, deadline, goal_type) VALUES (?,?,?,?,?)",
            (self.uid, enc_t, enc_d, deadline, goal_type)
        )
        conn.commit(); row_id = cur.lastrowid; conn.close()
        return row_id

    def set_completed(self, goal_id: int, completed: bool):
        conn = get_connection()
        conn.execute(
            "UPDATE study_goals SET completed=? WHERE id=? AND user_id=?",
            (1 if completed else 0, goal_id, self.uid)
        )
        conn.commit(); conn.close()

    def delete_goal(self, goal_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM study_goals WHERE id=? AND user_id=?", (goal_id, self.uid))
        conn.commit(); conn.close()
