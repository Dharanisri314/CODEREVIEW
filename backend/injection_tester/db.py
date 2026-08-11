"""
Prompt Injection Testing — SQLite storage
Stores every test run so results persist across restarts.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.getenv("PIT_DB_PATH", "injection_tester/pit_results.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                run_id        TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL,
                prompt_text   TEXT NOT NULL,
                agent_reply   TEXT NOT NULL,
                verdict       TEXT NOT NULL,
                reasons       TEXT NOT NULL,
                overlap_ratio REAL,
                refusal       INTEGER,
                started_at    TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_run(run_id: str, user_id: str, prompt_text: str, agent_reply: str, evaluation: dict):
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO test_runs
               (run_id, user_id, prompt_text, agent_reply, verdict, reasons,
                overlap_ratio, refusal, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, user_id, prompt_text, agent_reply,
                evaluation["verdict"], json.dumps(evaluation["reasons"]),
                evaluation["overlap_ratio"], int(evaluation["refusal_detected"]),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def get_run(run_id: str) -> dict:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM test_runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else {}


def get_history(user_id: str, limit: int = 20) -> list:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM test_runs WHERE user_id = ? ORDER BY started_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]