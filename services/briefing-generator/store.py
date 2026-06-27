"""
store.py — SQLite persistence for briefing-generator.

All connections are per-call (open → commit/rollback → close) so background
threads and the async event loop share the same DB file safely.
"""
import sqlite3
from contextlib import contextmanager

from config import DB_PATH


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
            CREATE TABLE IF NOT EXISTS briefings (
                id           TEXT PRIMARY KEY,
                status       TEXT NOT NULL,
                text         TEXT,
                created_at   TEXT NOT NULL,
                period_hours INTEGER NOT NULL,
                error        TEXT
            )
        """)


def upsert(briefing_id: str, data: dict) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO briefings "
            "(id, status, text, created_at, period_hours, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (briefing_id, data["status"], data.get("text"),
             data["created_at"], data["period_hours"], data.get("error")),
        )


def update_status(briefing_id: str, status: str,
                  text: str | None = None, error: str | None = None) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE briefings SET status = ?, text = ?, error = ? WHERE id = ?",
            (status, text, error, briefing_id),
        )


def get(briefing_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM briefings WHERE id = ?", (briefing_id,)
        ).fetchone()
    return dict(row) if row else None


def list_all() -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, status, created_at, period_hours "
            "FROM briefings ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
