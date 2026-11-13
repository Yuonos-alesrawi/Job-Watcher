import sqlite3
import time

from config import DB_PATH


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS seen (
            key TEXT PRIMARY KEY, title TEXT, company TEXT, url TEXT,
            decision TEXT, reasons TEXT, score INTEGER, first_seen REAL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS board_status (
            board TEXT PRIMARY KEY, status INTEGER, checked REAL)"""
    )
    return conn


def board_key(source, name):
    return f"{source}:{name.lower()}"


def dead_boards(conn, retry_days):
    """Boards that returned 404/410 recently; they are skipped until retry_days pass."""
    cutoff = time.time() - retry_days * 86400
    rows = conn.execute(
        "SELECT board FROM board_status WHERE status IN (404, 410) AND checked > ?", (cutoff,)
    ).fetchall()
    return {r[0] for r in rows}


def mark_board(conn, source, name, status):
    conn.execute(
        "INSERT OR REPLACE INTO board_status VALUES (?,?,?)",
        (board_key(source, name), status, time.time()),
    )
    conn.commit()


def _key(job):
    return f"{job.source}:{job.company}:{job.job_id}"


def is_new(conn, job):
    return conn.execute("SELECT 1 FROM seen WHERE key=?", (_key(job),)).fetchone() is None


def save(conn, job, result, commit=True):
    conn.execute(
        "INSERT OR IGNORE INTO seen VALUES (?,?,?,?,?,?,?,?)",
        (_key(job), job.title, job.company, job.url,
         "keep" if result.keep else "exclude", ",".join(result.reasons),
         result.score, time.time()),
    )
    if commit:
        conn.commit()
