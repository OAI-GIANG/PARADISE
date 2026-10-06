from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

_STATE_TO_STATUS = {
    "QUEUED": "PENDING", "RUNNING": "RUNNING", "RECOVERING": "RUNNING",
    "RECOVERY_PENDING": "RUNNING", "COMPLETED": "SUCCEEDED", "FAILED": "FAILED",
    "CANCELLED": "FAILED", "TIMED_OUT": "FAILED", "ABORTED_BY_KILL": "FAILED",
}

class RuntimeStore:
    """Single durable persistence owner; DurableExecution owns execution state transitions."""
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.root = self.path.parent
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init()

    @property
    def lock(self) -> RLock:
        return self._lock

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
                CREATE TABLE IF NOT EXISTS runtime_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY, operation TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'QUEUED',
                    status TEXT,
                    request_json TEXT NOT NULL,
                    result_json TEXT, error TEXT,
                    idempotency_key TEXT UNIQUE,
                    idempotency_scope TEXT,
                    request_fingerprint TEXT,
                    execution_mode TEXT,
                    async INTEGER NOT NULL DEFAULT 0,
                    queue_eligibility TEXT,
                    attempt_no INTEGER NOT NULL DEFAULT 0,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    run_id TEXT, attempt_id TEXT, parent_run_id TEXT,
                    worker_id TEXT, lease_id TEXT, lease_until TEXT,
                    fence_token INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1,
                    recovery_count INTEGER NOT NULL DEFAULT 0,
                    delay_s INTEGER NOT NULL DEFAULT 0,
                    last_heartbeat_at TEXT, timeout_deadline TEXT,
                    recovery_reason TEXT, evidence_refs_json TEXT,
                    provenance_json TEXT, metadata_json TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
                    event_type TEXT NOT NULL, payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_records (
                    memory_id TEXT PRIMARY KEY, normalized_key TEXT NOT NULL,
                    scope TEXT NOT NULL, record_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_key_scope ON memory_records(normalized_key, scope);
                CREATE TABLE IF NOT EXISTS evidence_records (
                    evidence_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, record_json TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS replay_records (
                    replay_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL, record_json TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_replay_task_sequence ON replay_records(task_id, sequence);
                CREATE TABLE IF NOT EXISTS learning_observations (
                    observation_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    record_json TEXT NOT NULL, observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS learning_artifacts (
                    artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL, record_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
            additions = {
                "state": "TEXT", "idempotency_scope": "TEXT", "request_fingerprint": "TEXT",
                "execution_mode": "TEXT", "async": "INTEGER NOT NULL DEFAULT 0", "queue_eligibility": "TEXT",
                "attempt_no": "INTEGER NOT NULL DEFAULT 0", "attempt": "INTEGER NOT NULL DEFAULT 0",
                "run_id": "TEXT", "attempt_id": "TEXT", "parent_run_id": "TEXT", "worker_id": "TEXT",
                "lease_id": "TEXT", "lease_until": "TEXT", "fence_token": "INTEGER NOT NULL DEFAULT 0",
                "revision": "INTEGER NOT NULL DEFAULT 1", "recovery_count": "INTEGER NOT NULL DEFAULT 0",
                "delay_s": "INTEGER NOT NULL DEFAULT 0", "last_heartbeat_at": "TEXT", "timeout_deadline": "TEXT",
                "recovery_reason": "TEXT", "evidence_refs_json": "TEXT", "provenance_json": "TEXT", "metadata_json": "TEXT",
            }
            for name, typ in additions.items():
                if name not in cols:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {typ}")
            if "status" in cols:
                conn.execute("UPDATE tasks SET state=CASE status WHEN 'SUCCEEDED' THEN 'COMPLETED' WHEN 'FAILED' THEN 'FAILED' WHEN 'RUNNING' THEN 'RUNNING' ELSE 'QUEUED' END WHERE state IS NULL")
            conn.execute("UPDATE tasks SET state=COALESCE(state,'QUEUED'), execution_mode=COALESCE(execution_mode, CASE WHEN async=1 THEN 'ASYNC' ELSE 'SYNC' END), queue_eligibility=COALESCE(queue_eligibility,'DISPATCHABLE'), evidence_refs_json=COALESCE(evidence_refs_json,'[]'), provenance_json=COALESCE(provenance_json,'{}'), metadata_json=COALESCE(metadata_json,'{}')")
            conn.commit()

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT INTO runtime_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value)); conn.commit()

    def get_meta(self, key: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute("SELECT value FROM runtime_meta WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def tasks(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
        return [self._row(row) for row in rows]

    def task_by_id(self, task_id: str) -> dict[str, Any] | None:
        return self.get_task(task_id)

    def upsert_task(self, task: dict[str, Any]) -> None:
        now = task.get("updated_at")
        state = task.get("state", "QUEUED")
        operation = task.get("operation", "echo")
        request = task.get("request") or {"operation": operation, "payload": task.get("metadata", {}).get("payload", {})}
        status = _STATE_TO_STATUS.get(state, "PENDING")
        values = (
            task["id"], operation, state, status, json.dumps(request, sort_keys=True),
            json.dumps(task.get("report"), sort_keys=True) if task.get("report") is not None else None,
            json.dumps(task.get("error"), sort_keys=True) if task.get("error") is not None else None,
            task.get("idempotency_key"), task.get("idempotency_scope"), task.get("request_fingerprint"),
            task.get("execution_mode"), 1 if task.get("async") else 0, task.get("queue_eligibility"),
            int(task.get("attempt_no", 0)), int(task.get("attempt", 0)), task.get("run_id"), task.get("attempt_id"),
            task.get("parent_run_id"), task.get("worker_id"), task.get("lease_id"), task.get("lease_until"),
            int(task.get("fence_token", 0)), int(task.get("revision", 1)), int(task.get("recovery_count", 0)),
            int(task.get("delay_s", 0)), task.get("last_heartbeat_at"), task.get("timeout_deadline"), task.get("recovery_reason"),
            json.dumps(task.get("evidence_refs", []), sort_keys=True), json.dumps(task.get("provenance", {}), sort_keys=True),
            json.dumps(task.get("metadata", {}), sort_keys=True), task.get("created_at", now), now,
        )
        sql = """INSERT INTO tasks(task_id,operation,state,status,request_json,result_json,error,idempotency_key,idempotency_scope,request_fingerprint,execution_mode,async,queue_eligibility,attempt_no,attempt,run_id,attempt_id,parent_run_id,worker_id,lease_id,lease_until,fence_token,revision,recovery_count,delay_s,last_heartbeat_at,timeout_deadline,recovery_reason,evidence_refs_json,provenance_json,metadata_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET operation=excluded.operation,state=excluded.state,status=excluded.status,request_json=excluded.request_json,result_json=excluded.result_json,error=excluded.error,idempotency_key=excluded.idempotency_key,idempotency_scope=excluded.idempotency_scope,request_fingerprint=excluded.request_fingerprint,execution_mode=excluded.execution_mode,async=excluded.async,queue_eligibility=excluded.queue_eligibility,attempt_no=excluded.attempt_no,attempt=excluded.attempt,run_id=excluded.run_id,attempt_id=excluded.attempt_id,parent_run_id=excluded.parent_run_id,worker_id=excluded.worker_id,lease_id=excluded.lease_id,lease_until=excluded.lease_until,fence_token=excluded.fence_token,revision=excluded.revision,recovery_count=excluded.recovery_count,delay_s=excluded.delay_s,last_heartbeat_at=excluded.last_heartbeat_at,timeout_deadline=excluded.timeout_deadline,recovery_reason=excluded.recovery_reason,evidence_refs_json=excluded.evidence_refs_json,provenance_json=excluded.provenance_json,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at"""
        with self._lock, self._connection() as conn:
            conn.execute(sql, values); conn.commit()

    def create_task(self, task_id: str, operation: str, request: dict[str, Any], idempotency_key: str, now: str) -> dict[str, Any]:
        existing = self.get_by_idempotency(idempotency_key)
        if existing: return existing
        task = {"id": task_id, "operation": operation, "state": "QUEUED", "execution_mode": "SYNC", "async": False,
                "queue_eligibility": "DISPATCHABLE", "attempt_no": 0, "attempt": 0, "fence_token": 0, "revision": 1,
                "idempotency_key": idempotency_key, "idempotency_scope": "TASK_SUBMISSION", "metadata": {"request": request},
                "created_at": now, "updated_at": now}
        self.upsert_task(task); return self.get_task(task_id) or {}

    def get_by_idempotency(self, key: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE idempotency_key=? ORDER BY created_at LIMIT 1", (key,)).fetchone()
        return None if row is None else self._row(row)

    def update_task(self, task_id: str, status: str, now: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        state = "COMPLETED" if status == "SUCCEEDED" else "FAILED" if status == "FAILED" else "RUNNING" if status == "RUNNING" else "QUEUED"
        task = self.get_task(task_id)
        if task is None: raise KeyError(task_id)
        task.update({"state": state, "report": result, "error": error, "updated_at": now})
        self.upsert_task(task)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return None if row is None else self._row(row)

    def list_tasks(self) -> list[dict[str, Any]]: return self.tasks()

    def add_event(self, task_id: str | None, event_type: str, payload: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT INTO audit_events(task_id,event_type,payload_json,occurred_at) VALUES(?,?,?,?)", (task_id,event_type,json.dumps(payload,sort_keys=True),now)); conn.commit()

    def save_memory(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO memory_records(memory_id,normalized_key,scope,record_json,created_at) VALUES(?,?,?,?,?)", (record["memory_id"],record["normalized_key"],record["scope"],json.dumps(record,sort_keys=True),now)); conn.commit()

    def load_memory(self, normalized_key: str, scope: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute("SELECT record_json FROM memory_records WHERE normalized_key=? AND scope=? ORDER BY created_at",(normalized_key,scope)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def all_memory_records(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute("SELECT record_json FROM memory_records ORDER BY created_at").fetchall()
        return [json.loads(row[0]) for row in rows]

    def find_memory_by_idempotency(self, idempotency_key: str) -> list[dict[str, Any]]:
        if not str(idempotency_key).strip():
            return []
        with self._connection() as conn:
            rows=conn.execute("SELECT record_json FROM memory_records ORDER BY created_at").fetchall()
        result=[]
        for row in rows:
            record=json.loads(row[0])
            if record.get("idempotency_key") == idempotency_key:
                result.append(record)
        return result

    def save_evidence(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO evidence_records(evidence_id,task_id,event_type,record_json,occurred_at) VALUES(?,?,?,?,?)", (record["evidence_id"],record["task_id"],record["event_type"],json.dumps(record,sort_keys=True),now)); conn.commit()

    def list_evidence(self, task_id: str | None = None) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute("SELECT record_json FROM evidence_records WHERE task_id=? ORDER BY occurred_at",(task_id,)).fetchall() if task_id else conn.execute("SELECT record_json FROM evidence_records ORDER BY occurred_at").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_replay(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO replay_records(replay_id,task_id,sequence,record_json,occurred_at) VALUES(?,?,?,?,?)", (record["replay_id"],record["task_id"],record["sequence"],json.dumps(record,sort_keys=True),now)); conn.commit()

    def list_replay(self, task_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute("SELECT record_json FROM replay_records WHERE task_id=? ORDER BY sequence",(task_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_learning_artifact(self, record: dict[str, Any], task_id: str, now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO learning_artifacts(artifact_id,task_id,artifact_revision,record_json,created_at) VALUES(?,?,?,?,?)", (record["artifact_id"],task_id,int(record["artifact_revision"]),json.dumps(record,sort_keys=True),now)); conn.commit()

    def list_learning_artifacts(self, task_id: str | None = None) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute("SELECT record_json FROM learning_artifacts WHERE task_id=? ORDER BY created_at",(task_id,)).fetchall() if task_id else conn.execute("SELECT record_json FROM learning_artifacts ORDER BY created_at").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_learning_observation(self, record: dict[str, Any], now: str) -> None:
        with self._lock, self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO learning_observations(observation_id,task_id,record_json,observed_at) VALUES(?,?,?,?)", (record["observation_id"],record["task_id"],json.dumps(record,sort_keys=True),now)); conn.commit()

    def list_learning_observations(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows=conn.execute("SELECT record_json FROM learning_observations ORDER BY observed_at").fetchall()
        return [json.loads(row[0]) for row in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result=dict(row)
        state=result.get("state") or "QUEUED"
        result["state"]=state
        result["status"]=_STATE_TO_STATUS.get(state,"PENDING")
        result["task_id"]=result.get("task_id")
        result["id"]=result.get("task_id")
        result["request"]=json.loads(result.pop("request_json"))
        result["result"]=json.loads(result.pop("result_json")) if result.get("result_json") is not None else None
        if result.get("result") is None and result.get("report") is not None:
            result["result"]=result.get("report")
        raw_error=result.get("error")
        if raw_error and isinstance(raw_error,str) and raw_error.startswith(("{","[")):
            try:
                detail=json.loads(raw_error); result["error_detail"]=detail; result["error"]=detail.get("message",raw_error) if isinstance(detail,dict) else raw_error
            except json.JSONDecodeError:
                result["error"]=raw_error
        else:
            result["error"]=raw_error
        for field, default in (("evidence_refs_json",[]),("provenance_json",{}),("metadata_json",{})):
            raw=result.pop(field,None)
            key=field[:-5] if field.endswith("_json") else field
            try: result[key]=json.loads(raw) if raw else default
            except (TypeError, json.JSONDecodeError): result[key]=default
        result.pop("status",None) if False else None
        return result
