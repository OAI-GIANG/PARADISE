from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Iterator


class RuntimeStore:
    """Durable SQLite state for the bounded PARADISE runtime."""

    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=DELETE;
                CREATE TABLE IF NOT EXISTS runtime_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    idempotency_key TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                """
            )

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO runtime_meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            conn.commit()

    def get_meta(self, key: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute("SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def create_task(self, task_id: str, operation: str, request: dict[str, Any],
                    idempotency_key: str, now: str) -> dict[str, Any]:
        with self._lock, self._connection() as conn:
            existing = conn.execute(
                "SELECT * FROM tasks WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if existing:
                return self._row(existing)
            conn.execute(
                "INSERT INTO tasks(task_id,operation,status,request_json,idempotency_key,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (task_id, operation, "PENDING", json.dumps(request, sort_keys=True),
                 idempotency_key, now, now),
            )
            conn.commit()
        return self.get_task(task_id) or {}

    def update_task(self, task_id: str, status: str, now: str,
                    result: dict[str, Any] | None = None,
                    error: str | None = None) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                "UPDATE tasks SET status=?, result_json=?, error=?, updated_at=? WHERE task_id=?",
                (status, json.dumps(result, sort_keys=True) if result is not None else None,
                 error, now, task_id),
            )
            conn.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return None if row is None else self._row(row)

    def add_event(self, task_id: str | None, event_type: str,
                  payload: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO audit_events(task_id,event_type,payload_json,occurred_at) VALUES(?,?,?,?)",
                (task_id, event_type, json.dumps(payload, sort_keys=True), now),
            )
            conn.commit()

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        if result.get("result_json") is not None:
            result["result"] = json.loads(result.pop("result_json"))
        else:
            result.pop("result_json", None)
            result["result"] = None
        return result

