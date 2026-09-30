"""
Persistence layer for maintenance requests.

Uses SQLite locally (zero setup, ships with Python) so the project runs
out of the box. The schema and query patterns mirror how this would be
modeled in Supabase/Postgres in production -- swapping the connection
for `psycopg2`/the Supabase client is the only change needed there.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "maintenance.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS maintenance_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    from_phone TEXT,
    raw_message TEXT NOT NULL,
    category TEXT NOT NULL,
    urgency TEXT NOT NULL,
    summary TEXT NOT NULL,
    unit_number TEXT,
    backend TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);
"""


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_request(request_dict: dict, from_phone: str | None = None, db_path: str = DEFAULT_DB_PATH) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO maintenance_requests
                (created_at, from_phone, raw_message, category, urgency, summary, unit_number, backend)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                from_phone,
                request_dict["raw_message"],
                request_dict["category"],
                request_dict["urgency"],
                request_dict["summary"],
                request_dict.get("unit_number"),
                request_dict["backend"],
            ),
        )
        return cursor.lastrowid


def list_requests(status: str | None = None, db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM maintenance_requests WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM maintenance_requests ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def update_status(request_id: int, status: str, db_path: str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("UPDATE maintenance_requests SET status = ? WHERE id = ?", (status, request_id))
