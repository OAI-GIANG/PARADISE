from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

class RuntimeStore:
    """Single durable state/persistence owner for PARADISE."""
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
            conn.executescript("""
                PRAGMA journal_mode=DELETE;
                CREATE TABLE IF NOT EXISTS runtime_meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, operation TEXT NOT NULL,
                    status TEXT NOT NULL, request_json TEXT NOT NULL,
                    result_json TEXT, error TEXT, idempotency_key TEXT UNIQUE,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT, event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_records (
                    memory_id TEXT PRIMARY KEY, normalized_key TEXT NOT NULL,
                    scope TEXT NOT NULL, record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_key_scope
                    ON memory_records(normalized_key, scope);
                CREATE TABLE IF NOT EXISTS evidence_records (
                    evidence_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, record_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS replay_records (
                    replay_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, record_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_replay_task_sequence
                    ON replay_records(task_id, sequence);
                CREATE TABLE IF NOT EXISTS learning_observations (
                    observation_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    record_json TEXT NOT NULL, observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_cost_ledger (
                    request_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, provider_id TEXT NOT NULL,
                    model_id TEXT NOT NULL, estimated_cost REAL NOT NULL, actual_cost REAL,
                    currency TEXT NOT NULL, record_json TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
            """)

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
            conn.commit()

    def get_meta(self, key: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute("SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def create_task(self, task_id: str, operation: str, request: dict[str, Any], idempotency_key: str, now: str) -> dict[str, Any]:
        with self._lock, self._connection() as conn:
            existing = conn.execute("SELECT * FROM tasks WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                return self._row(existing)
            conn.execute("INSERT INTO tasks(task_id,operation,status,request_json,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                         (task_id, operation, "PENDING", json.dumps(request, sort_keys=True), idempotency_key, now, now))
            conn.commit()
        return self.get_task(task_id) or {}

    def update_task(self, task_id: str, status: str, now: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("UPDATE tasks SET status=?, result_json=?, error=?, updated_at=? WHERE task_id=?",
                         (status, json.dumps(result, sort_keys=True) if result is not None else None, error, now, task_id))
            conn.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return None if row is None else self._row(row)

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
        return [self._row(row) for row in rows]

    def add_event(self, task_id: str | None, event_type: str, payload: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT INTO audit_events(task_id,event_type,payload_json,occurred_at) VALUES(?,?,?,?)",
                         (task_id, event_type, json.dumps(payload, sort_keys=True), now))
            conn.commit()

    def save_memory(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO memory_records(memory_id,normalized_key,scope,record_json,created_at) VALUES(?,?,?,?,?)",
                         (record["memory_id"], record["normalized_key"], record["scope"], json.dumps(record, sort_keys=True), now))
            conn.commit()

    def load_memory(self, normalized_key: str, scope: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT record_json FROM memory_records WHERE normalized_key=? AND scope=? ORDER BY created_at",
                                (normalized_key, scope)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_evidence(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO evidence_records(evidence_id,task_id,event_type,record_json,occurred_at) VALUES(?,?,?,?,?)",
                         (record["evidence_id"], record["task_id"], record["event_type"], json.dumps(record, sort_keys=True), now))
            conn.commit()

    def list_evidence(self, task_id: str | None = None) -> list[dict[str, Any]]:
        with self._connection() as conn:
            if task_id:
                rows = conn.execute("SELECT record_json FROM evidence_records WHERE task_id=? ORDER BY occurred_at", (task_id,)).fetchall()
            else:
                rows = conn.execute("SELECT record_json FROM evidence_records ORDER BY occurred_at").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_replay(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO replay_records(replay_id,task_id,sequence,record_json,occurred_at) VALUES(?,?,?,?,?)",
                         (record["replay_id"], record["task_id"], record["sequence"], json.dumps(record, sort_keys=True), now))
            conn.commit()

    def list_replay(self, task_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT record_json FROM replay_records WHERE task_id=? ORDER BY sequence", (task_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_learning_observation(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO learning_observations(observation_id,task_id,record_json,observed_at) VALUES(?,?,?,?)",
                         (record["observation_id"], record["task_id"], json.dumps(record, sort_keys=True), now))
            conn.commit()

    def list_learning_observations(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT record_json FROM learning_observations ORDER BY observed_at").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_model_cost(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO model_cost_ledger(request_id,task_id,provider_id,model_id,estimated_cost,actual_cost,currency,record_json,occurred_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (record["request_id"], record["task_id"], record["provider_id"], record["model_id"],
                 float(record.get("estimated_cost", 0.0)), record.get("actual_cost"), record.get("currency", "USD"),
                 json.dumps(record, sort_keys=True), now),
            )
            conn.commit()

    def total_model_cost(self, currency: str = "USD") -> float:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN actual_cost IS NOT NULL THEN actual_cost ELSE estimated_cost END),0) FROM model_cost_ledger WHERE currency=?",
                (currency,),
            ).fetchone()
        return float(row[0] or 0.0)

    def list_model_costs(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT record_json FROM model_cost_ledger ORDER BY occurred_at").fetchall()
        return [json.loads(row[0]) for row in rows]

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
