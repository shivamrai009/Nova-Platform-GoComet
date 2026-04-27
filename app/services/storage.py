from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models import PipelineRun


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    customer_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    overall_status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS field_results (
                    run_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    found TEXT,
                    expected TEXT,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
                """
            )

    def save_run(self, run: PipelineRun) -> None:
        payload = run.model_dump(mode="json")
        created_at = payload["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.astimezone(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(run_id, created_at, customer_id, decision, overall_status, payload_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    str(created_at),
                    run.customer_id,
                    run.decision.decision,
                    run.validation.overall_status,
                    json.dumps(payload),
                ),
            )

            for _, field in run.validation.field_results.items():
                conn.execute(
                    """
                    INSERT INTO field_results(run_id, field_name, status, confidence, found, expected)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run.run_id,
                        field.field,
                        field.status,
                        field.confidence,
                        field.found,
                        field.expected,
                    ),
                )

    def get_run(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            return json.loads(row["payload_json"])

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, created_at, customer_id, decision, overall_status
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
