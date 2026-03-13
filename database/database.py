"""SQLite database initialization and connection management."""

import sqlite3
import os
from core.config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize all database tables."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS password_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            username TEXT NOT NULL,
            encrypted_password BLOB NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            UNIQUE(user_id, key)
        )
    """)

    # ── Notebook ──────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS notebook_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notebook_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, name),
            FOREIGN KEY (category_id) REFERENCES notebook_categories(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notebook_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            encrypted_content BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES notebook_people(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ── Calculator history ────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS calculator_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            expression TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # ── Study: Lessons ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_lesson_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            resource_type TEXT NOT NULL,
            encrypted_content BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lesson_id) REFERENCES study_lessons(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    # ── Study: Exam Sessions & Scores ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_exam_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exam_type TEXT NOT NULL,
            session_date TEXT NOT NULL,
            encrypted_notes BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_exam_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            correct INTEGER NOT NULL DEFAULT 0,
            incorrect INTEGER NOT NULL DEFAULT 0,
            empty INTEGER NOT NULL DEFAULT 0,
            UNIQUE(session_id, subject),
            FOREIGN KEY (session_id) REFERENCES study_exam_sessions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    # ── Study: Tests & Questions ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            subject TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_test_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            position INTEGER NOT NULL DEFAULT 1,
            enc_question BLOB,
            enc_solution BLOB,
            enc_question_image BLOB,
            enc_solution_image BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_id) REFERENCES study_tests(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    # ── Study: Flashcard Decks & Cards ────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_flashcard_decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            subject TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            enc_front BLOB NOT NULL,
            enc_back BLOB NOT NULL,
            enc_image BLOB,
            ease_factor INTEGER NOT NULL DEFAULT 2,
            review_count INTEGER NOT NULL DEFAULT 0,
            next_review TEXT DEFAULT (DATE('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deck_id) REFERENCES study_flashcard_decks(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    # ── Study: Timer Sessions ─────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_timer_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            session_type TEXT NOT NULL DEFAULT 'focus',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    # ── Study: Resources ──────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            enc_title BLOB NOT NULL,
            resource_type TEXT NOT NULL,
            enc_url BLOB,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
 
    # ── Study: Goals ──────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            enc_title BLOB NOT NULL,
            enc_description BLOB,
            deadline TEXT NOT NULL,
            goal_type TEXT NOT NULL DEFAULT 'short',
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def user_exists():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count > 0
