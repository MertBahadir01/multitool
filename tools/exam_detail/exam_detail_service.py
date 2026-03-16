"""
exam_detail_service.py
======================
Append these two classes to:
    tools/study_lessons/study_service.py

They power:
  - ExamDetailTool  (detailed exam entry)
  - ExamProgressTool (progress analytics)

Import from either tool like:
    from tools.study_lessons.study_service import ExamDetailService

─── TYT / AYT / YDT subject + topic definitions ────────────────────────────
Subjects and question counts match current ÖSYM format.
Topics are the standard sub-categories used by Turkish prep courses.
"""

from database.database import get_connection
from services.encryption_service import encrypt, decrypt


def _key(user) -> str:
    return user["password_hash"]


# ════════════════════════════════════════════════════════════════════════════
# Exam definitions — subjects, question counts, topics
# ════════════════════════════════════════════════════════════════════════════

EXAM_DEFS = {
    "TYT": {
        "Türkçe": {
            "total_q": 40,
            "topics": [
                "Sözcükte Anlam", "Cümlede Anlam", "Paragraf Bilgisi",
                "Sözcük Türleri", "Cümlenin Öğeleri", "Cümle Türleri",
                "Fiil Çekimi", "Ses Bilgisi", "Yazım Kuralları",
                "Noktalama İşaretleri", "Anlatım Bozuklukları",
            ],
        },
        "Matematik": {
            "total_q": 40,
            "topics": [
                "Temel Kavramlar", "Sayı Basamakları", "Bölünebilme",
                "EBOB – EKOK", "Rasyonel Sayılar", "Üslü Sayılar",
                "Köklü Sayılar", "Çarpanlara Ayırma", "Oran Orantı",
                "Yüzdeler ve Faiz", "Kümeler", "Mantık",
                "Olasılık", "İstatistik", "Permütasyon – Kombinasyon",
                "Problemler",
            ],
        },
        "Fen Bilimleri": {
            "total_q": 20,
            "topics": [
                "Fizik – Hareket", "Fizik – Kuvvet", "Fizik – Enerji",
                "Fizik – Elektrik", "Kimya – Madde", "Kimya – Atom",
                "Kimya – Periyodik Sistem", "Kimya – Bağlar",
                "Biyoloji – Hücre", "Biyoloji – Canlılar",
            ],
        },
        "Sosyal Bilimler": {
            "total_q": 20,
            "topics": [
                "Tarih – İlk Çağ", "Tarih – Osmanlı", "Tarih – Cumhuriyet",
                "Coğrafya – Doğal", "Coğrafya – Beşeri",
                "Felsefe – Temel", "Din Kültürü",
            ],
        },
    },
    "AYT – Sayısal": {
        "Matematik": {
            "total_q": 40,
            "topics": [
                "Polinomlar", "2. Derece Denklemler", "Karmaşık Sayılar",
                "Trigonometri", "Logaritma", "Diziler", "Limit",
                "Türev", "İntegral", "Analitik Geometri",
                "Olasılık", "İstatistik", "Kombinasyon",
            ],
        },
        "Fizik": {
            "total_q": 14,
            "topics": [
                "Kuvvet ve Hareket", "Enerji ve Momentum",
                "Elektrik", "Manyetizma", "Dalgalar",
                "Optik", "Modern Fizik",
            ],
        },
        "Kimya": {
            "total_q": 13,
            "topics": [
                "Madde ve Özellikleri", "Atom Yapısı",
                "Periyodik Sistem", "Kimyasal Bağlar",
                "Mol Kavramı", "Çözeltiler",
                "Asit – Baz", "Kimyasal Tepkimeler", "Organik Kimya",
            ],
        },
        "Biyoloji": {
            "total_q": 13,
            "topics": [
                "Hücre", "Metabolizma", "Kalıtım",
                "Ekosistem", "İnsan Fizyolojisi",
                "Bitki Biyolojisi", "Evrim",
            ],
        },
    },
    "AYT – Eşit Ağırlık": {
        "Matematik": {
            "total_q": 40,
            "topics": [
                "Polinomlar", "2. Derece Denklemler", "Karmaşık Sayılar",
                "Trigonometri", "Logaritma", "Diziler", "Limit",
                "Türev", "İntegral", "Analitik Geometri",
                "Olasılık", "İstatistik", "Kombinasyon",
            ],
        },
        "Türk Dili ve Edebiyatı": {
            "total_q": 24,
            "topics": [
                "Şiir Bilgisi", "Halk Edebiyatı", "Divan Edebiyatı",
                "Tanzimat", "Servet-i Fünun", "Milli Edebiyat",
                "Cumhuriyet Dönemi", "Anlatım Biçimleri", "Paragraf",
            ],
        },
        "Tarih": {
            "total_q": 10,
            "topics": [
                "İlk Türk Devletleri", "Osmanlı Kuruluş",
                "Osmanlı Yükseliş", "Osmanlı Gerileme",
                "Osmanlı Çöküş", "Kurtuluş Savaşı",
                "Atatürk İlkeleri", "Yakın Dönem",
            ],
        },
        "Coğrafya": {
            "total_q": 6,
            "topics": [
                "Doğal Coğrafya", "Beşeri Coğrafya",
                "Türkiye Coğrafyası", "Küresel Ortam",
            ],
        },
    },
    "AYT – Sözel": {
        "Türk Dili ve Edebiyatı": {
            "total_q": 24,
            "topics": [
                "Şiir Bilgisi", "Halk Edebiyatı", "Divan Edebiyatı",
                "Tanzimat", "Servet-i Fünun", "Milli Edebiyat",
                "Cumhuriyet Dönemi", "Anlatım Biçimleri", "Paragraf",
            ],
        },
        "Tarih": {
            "total_q": 10,
            "topics": [
                "İlk Türk Devletleri", "Osmanlı Kuruluş",
                "Osmanlı Yükseliş", "Osmanlı Gerileme",
                "Osmanlı Çöküş", "Kurtuluş Savaşı",
                "Atatürk İlkeleri", "Yakın Dönem",
            ],
        },
        "Coğrafya": {
            "total_q": 6,
            "topics": [
                "Doğal Coğrafya", "Beşeri Coğrafya",
                "Türkiye Coğrafyası", "Küresel Ortam",
            ],
        },
        "Felsefe": {
            "total_q": 12,
            "topics": [
                "Felsefeye Giriş", "Bilgi Felsefesi",
                "Varlık Felsefesi", "Ahlak Felsefesi",
                "Sanat Felsefesi", "Din Felsefesi",
                "Siyaset Felsefesi", "Çağdaş Felsefe",
            ],
        },
    },
    "YDT": {
        "İngilizce": {
            "total_q": 80,
            "topics": [
                "Vocabulary", "Grammar – Tenses", "Grammar – Modals",
                "Grammar – Passive", "Grammar – Conditionals",
                "Reading Comprehension", "Dialogue Completion",
                "Paragraph Completion", "Irrelevant Sentence",
                "Translation",
            ],
        },
        "Almanca": {
            "total_q": 80,
            "topics": [
                "Wortschatz", "Grammatik – Zeiten", "Grammatik – Kasus",
                "Leseverstehen", "Dialoge", "Übersetzung",
            ],
        },
        "Fransızca": {
            "total_q": 80,
            "topics": [
                "Vocabulaire", "Grammaire", "Compréhension de lecture",
                "Dialogues", "Traduction",
            ],
        },
    },
    "Özel / Diğer": {},   # user defines subjects freely
}

EXAM_TYPE_KEYS = list(EXAM_DEFS.keys())


# ════════════════════════════════════════════════════════════════════════════
# Service class
# ════════════════════════════════════════════════════════════════════════════

class ExamDetailService:
    """
    Tables used:
        exam_detail_sessions      — one row per exam sitting
        exam_detail_section_scores — correct/incorrect/empty per subject
        exam_detail_topic_scores   — correct/incorrect/empty per topic within subject
        exam_detail_wrong_questions— photo + link to lesson/topic for wrong answers
    """

    def __init__(self, user):
        self.uid = user["id"]
        self._key = _key(user)

    # ── Exams ─────────────────────────────────────────────────────────────────
    def get_exams(self, exam_type: str = None):
        conn = get_connection()
        if exam_type and exam_type != "Tümü":
            rows = conn.execute(
                "SELECT * FROM exam_detail_sessions "
                "WHERE user_id=? AND exam_type=? ORDER BY exam_date DESC",
                (self.uid, exam_type)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM exam_detail_sessions "
                "WHERE user_id=? ORDER BY exam_date DESC",
                (self.uid,)
            ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["notes"] = decrypt(d["enc_notes"], self._key) if d["enc_notes"] else ""
            except Exception:
                d["notes"] = ""
            result.append(d)
        return result

    def add_exam(self, exam_type: str, exam_date: str,
                 source: str = "", notes: str = "") -> int:
        enc = encrypt(notes, self._key) if notes else None
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO exam_detail_sessions "
            "(user_id, exam_type, exam_date, source, enc_notes) VALUES (?,?,?,?,?)",
            (self.uid, exam_type, exam_date, source, enc)
        )
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid

    def update_exam_notes(self, exam_id: int, notes: str):
        enc = encrypt(notes, self._key) if notes else None
        conn = get_connection()
        conn.execute(
            "UPDATE exam_detail_sessions SET enc_notes=? WHERE id=? AND user_id=?",
            (enc, exam_id, self.uid)
        )
        conn.commit(); conn.close()

    def delete_exam(self, exam_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM exam_detail_topic_scores WHERE exam_id=? AND user_id=?",
                     (exam_id, self.uid))
        conn.execute("DELETE FROM exam_detail_section_scores WHERE exam_id=? AND user_id=?",
                     (exam_id, self.uid))
        conn.execute("DELETE FROM exam_detail_wrong_questions WHERE exam_id=? AND user_id=?",
                     (exam_id, self.uid))
        conn.execute("DELETE FROM exam_detail_sessions WHERE id=? AND user_id=?",
                     (exam_id, self.uid))
        conn.commit(); conn.close()

    # ── Section scores (per subject) ──────────────────────────────────────────
    def get_section_scores(self, exam_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM exam_detail_section_scores "
            "WHERE exam_id=? AND user_id=? ORDER BY subject",
            (exam_id, self.uid)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def upsert_section_score(self, exam_id: int, subject: str, total_q: int,
                              correct: int, incorrect: int, empty: int):
        conn = get_connection()
        conn.execute(
            """INSERT INTO exam_detail_section_scores
               (exam_id, user_id, subject, total_q, correct, incorrect, empty)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(exam_id, user_id, subject) DO UPDATE SET
               total_q=excluded.total_q, correct=excluded.correct,
               incorrect=excluded.incorrect, empty=excluded.empty""",
            (exam_id, self.uid, subject, total_q, correct, incorrect, empty)
        )
        conn.commit(); conn.close()

    # ── Topic scores ──────────────────────────────────────────────────────────
    def get_topic_scores(self, exam_id: int, subject: str = None):
        conn = get_connection()
        if subject:
            rows = conn.execute(
                "SELECT * FROM exam_detail_topic_scores "
                "WHERE exam_id=? AND user_id=? AND subject=? ORDER BY topic",
                (exam_id, self.uid, subject)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM exam_detail_topic_scores "
                "WHERE exam_id=? AND user_id=? ORDER BY subject, topic",
                (exam_id, self.uid)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def upsert_topic_score(self, exam_id: int, subject: str, topic: str,
                            correct: int, incorrect: int, empty: int):
        conn = get_connection()
        conn.execute(
            """INSERT INTO exam_detail_topic_scores
               (exam_id, user_id, subject, topic, correct, incorrect, empty)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(exam_id, user_id, subject, topic) DO UPDATE SET
               correct=excluded.correct, incorrect=excluded.incorrect, empty=excluded.empty""",
            (exam_id, self.uid, subject, topic, correct, incorrect, empty)
        )
        conn.commit(); conn.close()

    # ── Wrong question photos ─────────────────────────────────────────────────
    def get_wrong_questions(self, exam_id: int):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM exam_detail_wrong_questions "
            "WHERE exam_id=? AND user_id=? ORDER BY subject, topic",
            (exam_id, self.uid)
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["photo_b64"] = decrypt(d["enc_photo"], self._key) if d["enc_photo"] else ""
            except Exception:
                d["photo_b64"] = ""
            try:
                d["note"] = decrypt(d["enc_note"], self._key) if d["enc_note"] else ""
            except Exception:
                d["note"] = ""
            result.append(d)
        return result

    def add_wrong_question(self, exam_id: int, subject: str, topic: str,
                            lesson_id: int = None, lesson_name: str = "",
                            photo_b64: str = "", note: str = "") -> int:
        enc_photo = encrypt(photo_b64, self._key) if photo_b64 else None
        enc_note  = encrypt(note,      self._key) if note      else None
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO exam_detail_wrong_questions
               (exam_id, user_id, subject, topic, lesson_id, lesson_name, enc_photo, enc_note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (exam_id, self.uid, subject, topic, lesson_id, lesson_name, enc_photo, enc_note)
        )
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid

    def delete_wrong_question(self, wq_id: int):
        conn = get_connection()
        conn.execute("DELETE FROM exam_detail_wrong_questions WHERE id=? AND user_id=?",
                     (wq_id, self.uid))
        conn.commit(); conn.close()

    # ── Analytics ─────────────────────────────────────────────────────────────
    def get_subject_trend(self, subject: str, exam_type: str = None):
        """All section scores for a subject across exams, ordered by date."""
        conn = get_connection()
        base = """SELECT ss.*, es.exam_date, es.source, es.exam_type
                  FROM exam_detail_section_scores ss
                  JOIN exam_detail_sessions es ON ss.exam_id = es.id
                  WHERE ss.user_id=? AND ss.subject=?"""
        if exam_type and exam_type != "Tümü":
            rows = conn.execute(base + " AND es.exam_type=? ORDER BY es.exam_date",
                                (self.uid, subject, exam_type)).fetchall()
        else:
            rows = conn.execute(base + " ORDER BY es.exam_date",
                                (self.uid, subject)).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            d["net"] = round(d["correct"] - d["incorrect"] * 0.25, 2)
            d["pct"] = round(d["correct"] / max(d["total_q"], 1) * 100, 1)
            result.append(d)
        return result

    def get_topic_trend(self, subject: str, topic: str, exam_type: str = None):
        conn = get_connection()
        base = """SELECT ts.*, es.exam_date, es.source
                  FROM exam_detail_topic_scores ts
                  JOIN exam_detail_sessions es ON ts.exam_id = es.id
                  WHERE ts.user_id=? AND ts.subject=? AND ts.topic=?"""
        if exam_type and exam_type != "Tümü":
            rows = conn.execute(base + " AND es.exam_type=? ORDER BY es.exam_date",
                                (self.uid, subject, topic, exam_type)).fetchall()
        else:
            rows = conn.execute(base + " ORDER BY es.exam_date",
                                (self.uid, subject, topic)).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            d["net"] = round(d["correct"] - d["incorrect"] * 0.25, 2)
            result.append(d)
        return result

    def get_all_subjects_summary(self, exam_type: str = None):
        """Latest score + overall stats per subject.

        Strategy: one simple aggregate query for avg/best/count,
        then a second pass to fetch the most-recent row per subject.
        Avoids correlated-subquery parameter-count bugs entirely.
        """
        conn = get_connection()

        # ── Step 1: aggregate stats per subject ───────────────────────────────
        if exam_type and exam_type != "Tümü":
            agg_rows = conn.execute(
                """SELECT ss.subject,
                          COUNT(DISTINCT ss.exam_id)          AS n_exams,
                          AVG(ss.correct)                     AS avg_correct,
                          AVG(ss.incorrect)                   AS avg_incorrect,
                          AVG(ss.total_q)                     AS avg_total,
                          MAX(ss.correct - ss.incorrect*0.25) AS best_net
                   FROM exam_detail_section_scores ss
                   JOIN exam_detail_sessions es ON ss.exam_id = es.id
                   WHERE ss.user_id = ? AND es.exam_type = ?
                   GROUP BY ss.subject
                   ORDER BY ss.subject""",
                (self.uid, exam_type)
            ).fetchall()
        else:
            agg_rows = conn.execute(
                """SELECT ss.subject,
                          COUNT(DISTINCT ss.exam_id)          AS n_exams,
                          AVG(ss.correct)                     AS avg_correct,
                          AVG(ss.incorrect)                   AS avg_incorrect,
                          AVG(ss.total_q)                     AS avg_total,
                          MAX(ss.correct - ss.incorrect*0.25) AS best_net
                   FROM exam_detail_section_scores ss
                   JOIN exam_detail_sessions es ON ss.exam_id = es.id
                   WHERE ss.user_id = ?
                   GROUP BY ss.subject
                   ORDER BY ss.subject""",
                (self.uid,)
            ).fetchall()

        # ── Step 2: latest row per subject (most recent exam_date) ─────────────
        if exam_type and exam_type != "Tümü":
            latest_rows = conn.execute(
                """SELECT ss.subject, ss.correct, ss.incorrect, ss.total_q
                   FROM exam_detail_section_scores ss
                   JOIN exam_detail_sessions es ON ss.exam_id = es.id
                   WHERE ss.user_id = ? AND es.exam_type = ?
                     AND es.exam_date = (
                         SELECT MAX(es2.exam_date)
                         FROM exam_detail_section_scores ss2
                         JOIN exam_detail_sessions es2 ON ss2.exam_id = es2.id
                         WHERE ss2.user_id = ss.user_id
                           AND ss2.subject = ss.subject
                           AND es2.exam_type = ?
                     )""",
                (self.uid, exam_type, exam_type)
            ).fetchall()
        else:
            latest_rows = conn.execute(
                """SELECT ss.subject, ss.correct, ss.incorrect, ss.total_q
                   FROM exam_detail_section_scores ss
                   JOIN exam_detail_sessions es ON ss.exam_id = es.id
                   WHERE ss.user_id = ?
                     AND es.exam_date = (
                         SELECT MAX(es2.exam_date)
                         FROM exam_detail_section_scores ss2
                         JOIN exam_detail_sessions es2 ON ss2.exam_id = es2.id
                         WHERE ss2.user_id = ss.user_id
                           AND ss2.subject = ss.subject
                     )""",
                (self.uid,)
            ).fetchall()

        conn.close()

        # map subject → latest scores
        latest_map = {}
        for r in latest_rows:
            latest_map[r[0]] = {"last_correct": r[1], "last_incorrect": r[2], "last_total_q": r[3]}

        result = []
        for r in agg_rows:
            d = dict(r)
            latest = latest_map.get(d["subject"], {})
            d["last_correct"]   = latest.get("last_correct",   0) or 0
            d["last_incorrect"] = latest.get("last_incorrect", 0) or 0
            d["last_total_q"]   = latest.get("last_total_q",   0) or 0
            d["avg_net"]  = round((d["avg_correct"]  or 0) - (d["avg_incorrect"]  or 0) * 0.25, 2)
            d["last_net"] = round(d["last_correct"] - d["last_incorrect"] * 0.25, 2)
            d["avg_pct"]  = round((d["avg_correct"]  or 0) / max(d["avg_total"] or 1, 1) * 100, 1)
            result.append(d)
        return result

    def get_weak_topics(self, exam_type: str = None, min_exams: int = 1):
        """Topics ranked by lowest average correct rate."""
        conn = get_connection()
        base = """SELECT ts.subject, ts.topic,
                         COUNT(*)              AS n_exams,
                         SUM(ts.correct)       AS total_c,
                         SUM(ts.incorrect)     AS total_i,
                         SUM(ts.empty)         AS total_e
                  FROM exam_detail_topic_scores ts
                  JOIN exam_detail_sessions es ON ts.exam_id=es.id
                  WHERE ts.user_id=?"""
        if exam_type and exam_type != "Tümü":
            rows = conn.execute(
                base + " AND es.exam_type=? GROUP BY ts.subject, ts.topic "
                       "HAVING n_exams>=? "
                       "ORDER BY CAST(total_c AS REAL)/(total_c+total_i+total_e+0.001)",
                (self.uid, exam_type, min_exams)
            ).fetchall()
        else:
            rows = conn.execute(
                base + " GROUP BY ts.subject, ts.topic "
                       "HAVING n_exams>=? "
                       "ORDER BY CAST(total_c AS REAL)/(total_c+total_i+total_e+0.001)",
                (self.uid, min_exams)
            ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            total = (d["total_c"] or 0) + (d["total_i"] or 0) + (d["total_e"] or 0)
            d["pct"] = round((d["total_c"] or 0) / max(total, 1) * 100, 1)
            d["avg_net"] = round(
                (d["total_c"] or 0) / max(d["n_exams"], 1) -
                (d["total_i"] or 0) / max(d["n_exams"], 1) * 0.25, 2
            )
            result.append(d)
        return result

    def get_topic_averages_for_subject(self, subject: str, exam_type: str = None):
        """Per-topic average correct/incorrect across all exams for one subject."""
        conn = get_connection()
        base = """SELECT ts.topic,
                         COUNT(*)              AS n_exams,
                         AVG(ts.correct)       AS avg_c,
                         AVG(ts.incorrect)     AS avg_i,
                         AVG(ts.empty)         AS avg_e,
                         SUM(ts.correct)       AS total_c,
                         SUM(ts.correct+ts.incorrect+ts.empty) AS total_q
                  FROM exam_detail_topic_scores ts
                  JOIN exam_detail_sessions es ON ts.exam_id=es.id
                  WHERE ts.user_id=? AND ts.subject=?"""
        if exam_type and exam_type != "Tümü":
            rows = conn.execute(
                base + " AND es.exam_type=? GROUP BY ts.topic ORDER BY ts.topic",
                (self.uid, subject, exam_type)
            ).fetchall()
        else:
            rows = conn.execute(
                base + " GROUP BY ts.topic ORDER BY ts.topic",
                (self.uid, subject)
            ).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            d["avg_net"] = round(d["avg_c"] - d["avg_i"] * 0.25, 2)
            d["pct"]     = round(d["total_c"] / max(d["total_q"], 1) * 100, 1)
            result.append(d)
        return result

    def get_all_subjects_seen(self, exam_type: str = None):
        conn = get_connection()
        base = """SELECT DISTINCT ss.subject FROM exam_detail_section_scores ss
                  JOIN exam_detail_sessions es ON ss.exam_id=es.id
                  WHERE ss.user_id=?"""
        if exam_type and exam_type != "Tümü":
            rows = conn.execute(base + " AND es.exam_type=? ORDER BY ss.subject",
                                (self.uid, exam_type)).fetchall()
        else:
            rows = conn.execute(base + " ORDER BY ss.subject",
                                (self.uid,)).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_lesson_names(self):
        """Fetch user's lessons for linking wrong questions."""
        from tools.study_lessons.study_service import LessonsService
        # build a thin wrapper to reuse
        class _FakeUser:
            pass
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name FROM study_lessons WHERE user_id=? ORDER BY name",
            (self.uid,)
        ).fetchall()
        conn.close()
        return [{"id": r[0], "name": r[1]} for r in rows]