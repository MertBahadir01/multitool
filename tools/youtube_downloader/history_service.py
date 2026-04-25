"""
YouTube Downloader — history service.
All data is stored in the central app database (youtube_download_history table).
The table is created by database/database.py on app startup.
"""

from database.database import get_connection


def add_entry(title: str, url: str, fmt: str, quality: str, size: str, status: str) -> int:
    """Insert a new download record. Returns the new row id."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """INSERT INTO youtube_download_history
               (title, url, format, quality, size, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, url, fmt, quality, size, status),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def update_status(row_id: int, status: str, size: str = None):
    """Update status (and optionally size) for an existing record."""
    conn = get_connection()
    if size is not None:
        conn.execute(
            "UPDATE youtube_download_history SET status=?, size=? WHERE id=?",
            (status, size, row_id),
        )
    else:
        conn.execute(
            "UPDATE youtube_download_history SET status=? WHERE id=?",
            (status, row_id),
        )
    conn.commit()
    conn.close()


def get_all(filter_status: str = None) -> list[dict]:
    """Return all rows, optionally filtered by status. Most recent first."""
    conn = get_connection()
    if filter_status and filter_status != "All":
        rows = conn.execute(
            "SELECT * FROM youtube_download_history WHERE status=? ORDER BY id DESC",
            (filter_status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM youtube_download_history ORDER BY id DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_entry(row_id: int):
    """Remove a single history entry."""
    conn = get_connection()
    conn.execute("DELETE FROM youtube_download_history WHERE id=?", (row_id,))
    conn.commit()
    conn.close()