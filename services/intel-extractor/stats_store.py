"""
stats_store.py — SQLite-backed telemetry counter for intel-extractor.

Tracks total documents processed and total IOCs extracted across all runs,
surviving container restarts via a named Docker volume at DB_PATH.

STATS-02: single-row counter table (id=1), INSERT OR REPLACE upsert pattern.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "/data/stats.db")


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id         INTEGER PRIMARY KEY,
                total_docs INTEGER NOT NULL DEFAULT 0,
                total_iocs INTEGER NOT NULL DEFAULT 0,
                last_run   TEXT
            )
        """)


def increment(docs: int, iocs: int) -> None:
    """Atomically add docs and iocs to the running totals and stamp last_run."""
    with _conn() as con:
        con.execute(
            """
            INSERT INTO stats (id, total_docs, total_iocs, last_run)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                total_docs = total_docs + excluded.total_docs,
                total_iocs = total_iocs + excluded.total_iocs,
                last_run   = excluded.last_run
            """,
            (docs, iocs, datetime.now(timezone.utc).isoformat()),
        )


def get_stats() -> dict:
    with _conn() as con:
        row = con.execute("SELECT * FROM stats WHERE id = 1").fetchone()
    return dict(row) if row else {"total_docs": 0, "total_iocs": 0, "last_run": None}
