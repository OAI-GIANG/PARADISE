"""Durable execution primitives for the LOVE async task path.

Submission is the durable execution input; this module is the sole execution adapter;
Store remains the persistence owner; Runtime remains the executor;
Evidence/Replay remain integrity owners.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from .task_contract import Submission


TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT", "ABORTED_BY_KILL"}
RECOVERABLE_STATES = {"QUEUED", "RUNNING", "RECOVERING", "RECOVERY_PENDING"}
IDEMPOTENCY_SCOPES = {
    "SEMANTIC_REQUEST", "TASK_SUBMISSION", "EXECUTION_ATTEMPT", "STATE_TRANSITION",
    "EVIDENCE_APPEND", "MEMORY_WRITE", "SIDE_EFFECT",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_fingerprint(message: str, delay_s: int) -> str:
    raw = f"{message}\n{delay_s}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DurableExecutionError(ValueError):
    pass


class DurableExecution:
    """Sole execution-state adapter over the canonical Store."""

    def __init__(self, store: Any, worker_id: str | None = None, lease_seconds: int = 30):
        self.store = store
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"
        self.lease_seconds = max(5, int(lease_seconds))

    def backup(self, destination: Any) -> dict:
        destination = __import__("pathlib").Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        names = ["tasks.json", "memory.json", "learning.json", "metrics.json", "experiments.json", "capabilities.json", "evolution_runs.json", "provider_performance.json", "discoveries.json", "observations.json", "publications.json"]
        manifest = {"backup_id": f"BKP-{uuid.uuid4().hex}", "created_at": now_iso(), "files": {}}
        for name in names:
            source = self.store.root / name
            if not source.exists():
                continue
            target = destination / name
            shutil.copy2(source, target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest["files"][name] = {"sha256": digest, "size": target.stat().st_size}
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return manifest

    @staticmethod
    def verify_backup(backup_root: Any) -> dict:
        root = __import__("pathlib").Path(backup_root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for name, meta in manifest.get("files", {}).items():
            path = root / name
            if not path.is_file():
                raise DurableExecutionError(f"backup_missing:{name}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
                raise DurableExecutionError(f"backup_hash_mismatch:{name}")
        return manifest

    @staticmethod
    def restore_backup(backup_root: Any, target_root: Any) -> dict:
        manifest = DurableExecution.verify_backup(backup_root)
        target_root = __import__("pathlib").Path(target_root)
        target_root.mkdir(parents=True, exist_ok=True)
        for name in manifest.get("files", {}):
            shutil.copy2(__import__("pathlib").Path(backup_root) / name, target_root / name)
        return manifest

    def enqueue_submission(self, submission: Submission) -> tuple[dict, bool]:
        """Accept only a canonical Submission; execution state remains owned here."""
        if not isinstance(submission, Submission):
            raise DurableExecutionError("submission_required")
        submission.validate()
        return self.enqueue(
            task_id=submission.submission_id,
            goal=submission.goal,
            delay_s=submission.delay_s,
            idempotency_key=submission.idempotency_key,
            idempotency_scope=submission.idempotency_scope,
            execution_mode=submission.execution_mode,
        )

    def enqueue(self, *, task_id: str, goal: str, delay_s: int = 0,
                idempotency_key: str, idempotency_scope: str = "TASK_SUBMISSION",
                execution_mode: str = "ASYNC") -> tuple[dict, bool]:
        if execution_mode not in {"SYNC", "ASYNC"}:
            raise DurableExecutionError("invalid_execution_mode")
        if idempotency_scope not in IDEMPOTENCY_SCOPES:
            raise DurableExecutionError("invalid_idempotency_scope")
        if not idempotency_key:
            raise DurableExecutionError("idempotency_key_required")
        fingerprint = request_fingerprint(goal, delay_s)
        with self.store.lock:
            rows = self.store.tasks()
            for row in rows:
                if row.get("idempotency_key") == idempotency_key and row.get("idempotency_scope") == idempotency_scope:
                    if row.get("request_fingerprint") != fingerprint:
                        raise DurableExecutionError("idempotency_conflict")
                    return row, True
            now = now_iso()
            task = {
                "id": task_id,
                "goal": goal,
                "state": "QUEUED",
                "async": execution_mode == "ASYNC",
                "execution_mode": execution_mode,
                "queue_eligibility": "DISPATCHABLE",
                "attempt_no": 0,
                "attempt": 0,
                "run_id": None,
                "attempt_id": None,
                "parent_run_id": None,
                "worker_id": None,
                "lease_id": None,
                "lease_until": None,
                "fence_token": 0,
                "revision": 1,
                "idempotency_key": idempotency_key,
                "idempotency_scope": idempotency_scope,
                "request_fingerprint": fingerprint,
                "recovery_count": 0,
                "delay_s": delay_s,
                "created_at": now,
                "updated_at": now,
                "last_heartbeat_at": None,
                "timeout_deadline": None,
                "recovery_reason": None,
                "evidence_refs": [],
                "provenance": {},
            }
            self.store.upsert_task(task)
            return task, False

    @contextmanager
    def _claim_lock(self):
        lock_dir = self.store.root / ".durable_claim.lock"
        deadline = time.monotonic() + 10
        while True:
            try:
                lock_dir.mkdir()
                (lock_dir / "owner").write_text(self.worker_id, encoding="utf-8")
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise DurableExecutionError("claim_lock_timeout")
                time.sleep(0.01)
        try:
            yield
        finally:
            try:
                (lock_dir / "owner").unlink(missing_ok=True)
                lock_dir.rmdir()
            except FileNotFoundError:
                pass

    def claim(self, task_id: str) -> dict | None:
        with self._claim_lock(), self.store.lock:
            task = self.store.task_by_id(task_id)
            if task is None or task.get("execution_mode", "ASYNC" if task.get("async") else None) not in {"SYNC", "ASYNC"}:
                return None
            if task.get("state") not in {"QUEUED", "RECOVERY_PENDING", "RECOVERING"}:
                return None
            if task.get("queue_eligibility") not in {"DISPATCHABLE", "RECOVERY"}:
                return None
            lease_until = task.get("lease_until")
            if lease_until and lease_until > now_iso():
                return None
            task["attempt_no"] = int(task.get("attempt_no", task.get("attempt", 0))) + 1
            task["attempt"] = task["attempt_no"]
            task["attempt_id"] = f"ATT-{uuid.uuid4().hex}"
            task["run_id"] = f"RUN-{uuid.uuid4().hex}"
            task["worker_id"] = self.worker_id
            task["lease_id"] = f"LEASE-{uuid.uuid4().hex}"
            task["fence_token"] = int(task.get("fence_token", 0)) + 1
            task["revision"] = int(task.get("revision", 0)) + 1
            task["lease_until"] = (datetime.now(timezone.utc) + timedelta(seconds=self.lease_seconds)).isoformat()
            task["last_heartbeat_at"] = now_iso()
            task["state"] = "RUNNING"
            task["queue_eligibility"] = "CLAIMED"
            task["updated_at"] = now_iso()
            self.store.upsert_task(task)
            return dict(task)

    def heartbeat(self, task_id: str, fence_token: int) -> bool:
        with self.store.lock:
            task = self.store.task_by_id(task_id)
            if not task or task.get("worker_id") != self.worker_id or int(task.get("fence_token", -1)) != int(fence_token):
                return False
            if task.get("state") != "RUNNING" or (task.get("lease_until") and task["lease_until"] <= now_iso()):
                return False
            task["last_heartbeat_at"] = now_iso()
            task["lease_until"] = (datetime.now(timezone.utc) + timedelta(seconds=self.lease_seconds)).isoformat()
            task["revision"] = int(task.get("revision", 0)) + 1
            task["updated_at"] = now_iso()
            self.store.upsert_task(task)
            return True

    def finalize(self, task_id: str, fence_token: int, state: str, *, report: dict | None = None,
                 error: dict | None = None) -> dict:
        if state not in TERMINAL_STATES:
            raise DurableExecutionError("invalid_terminal_state")
        with self.store.lock:
            task = self.store.task_by_id(task_id)
            if not task:
                raise DurableExecutionError("task_not_found")
            if int(task.get("fence_token", -1)) != int(fence_token) or task.get("worker_id") != self.worker_id:
                raise DurableExecutionError("stale_fence_token")
            if task.get("state") in TERMINAL_STATES:
                return task
            task["state"] = state
            task["queue_eligibility"] = "TERMINAL"
            task["lease_until"] = None
            task["updated_at"] = now_iso()
            task["revision"] = int(task.get("revision", 0)) + 1
            if report is not None:
                task["report"] = report
            if error is not None:
                task["error"] = error
            self.store.upsert_task(task)
            return task

    def request_recovery(self, task_id: str, *, reason: str = "manual_recovery") -> dict:
        """Move one failed/orphaned task into the canonical recovery path."""
        with self.store.lock:
            task = self.store.task_by_id(task_id)
            if task is None:
                raise DurableExecutionError("task_not_found")
            if not task.get("async"):
                raise DurableExecutionError("not_async_task")
            if task.get("state") not in {"FAILED", "RECOVERY_PENDING"}:
                raise DurableExecutionError("task_not_recoverable")
            recovery_count = int(task.get("recovery_count", 0))
            if recovery_count >= 1:
                raise DurableExecutionError("recovery_limit_reached")
            task["state"] = "RECOVERING"
            task["queue_eligibility"] = "RECOVERY"
            task["recovery_count"] = recovery_count + 1
            task["recovery_reason"] = reason
            task["revision"] = int(task.get("revision", 0)) + 1
            task["updated_at"] = now_iso()
            self.store.upsert_task(task)
            return dict(task)

    def recover_orphans(self) -> list[dict]:
        recovered = []
        with self.store.lock:
            for task in self.store.tasks():
                if not task.get("async"):
                    continue
                if task.get("state") not in {"QUEUED", "RUNNING", "RECOVERING"}:
                    continue
                if task.get("state") == "RUNNING":
                    task["parent_run_id"] = task.get("run_id")
                    task["recovery_reason"] = "server_restart_or_worker_loss"
                    # Orphan detection is not a retry attempt; recovery budget
                    # is consumed only when request_recovery() is accepted.
                    task["worker_id"] = None
                    task["lease_id"] = None
                    task["lease_until"] = None
                    task["queue_eligibility"] = "RECOVERY"
                    task["state"] = "RECOVERY_PENDING"
                    task["revision"] = int(task.get("revision", 0)) + 1
                    task["updated_at"] = now_iso()
                    self.store.upsert_task(task)
                    recovered.append(dict(task))
                elif task.get("state") in {"QUEUED", "RECOVERING"}:
                    task["queue_eligibility"] = "DISPATCHABLE"
                    task["updated_at"] = now_iso()
                    self.store.upsert_task(task)
        return recovered
