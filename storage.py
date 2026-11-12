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
    return conn


def _key(job):
    return f"{job.source}:{job.company}:{job.job_id}"


def is_new(conn, job):
    return conn.execute("SELECT 1 FROM seen WHERE key=?", (_key(job),)).fetchone() is None


def save(conn, job, result):
    conn.execute(
        "INSERT OR IGNORE INTO seen VALUES (?,?,?,?,?,?,?,?)",
        (_key(job), job.title, job.company, job.url,
         "keep" if result.keep else "exclude", ",".join(result.reasons),
         result.score, time.time()),
    )
    conn.commit()
