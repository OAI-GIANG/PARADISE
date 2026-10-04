from __future__ import annotations

import json
import os
import threading
import tempfile
from pathlib import Path
from typing import Any


class StoreError(ValueError):
    pass


class Store:
    """Single durable persistence owner for LOVE state records."""

    FILES = {
        "tasks": "tasks.json",
        "records": "records.json",
        "lifecycle": "lifecycle.json",
        "decisions": "decisions.json",
        "evidence_refs": "evidence_refs.json",
    }

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _path(self, kind: str) -> Path:
        try:
            name = self.FILES[kind]
        except KeyError as exc:
            raise StoreError(f"unknown_store_collection:{kind}") from exc
        return self.root / name

    def _read(self, kind: str) -> list[dict[str, Any]]:
        path = self._path(kind)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"malformed_store:{kind}") from exc
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise StoreError(f"invalid_store_shape:{kind}")
        return payload

    def _write(self, kind: str, rows: list[dict[str, Any]]) -> None:
        path = self._path(kind)
        fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(rows, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def tasks(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._read("tasks")

    def task_by_id(self, task_id: str) -> dict[str, Any] | None:
        with self.lock:
            for row in self._read("tasks"):
                if row.get("id") == task_id:
                    return dict(row)
        return None

    def upsert_task(self, task: dict[str, Any]) -> None:
        if not isinstance(task, dict) or not str(task.get("id", "")).strip():
            raise StoreError("task_id_required")
        with self.lock:
            rows = self._read("tasks")
            found = False
            for index, row in enumerate(rows):
                if row.get("id") == task["id"]:
                    rows[index] = dict(task)
                    found = True
                    break
            if not found:
                rows.append(dict(task))
            self._write("tasks", rows)

    def append_record(self, record: dict[str, Any], *, collection: str = "records") -> None:
        if not isinstance(record, dict):
            raise StoreError("record_must_be_object")
        with self.lock:
            rows = self._read(collection)
            record_id = record.get("record_id") or record.get("id")
            if record_id and any((row.get("record_id") or row.get("id")) == record_id for row in rows):
                raise StoreError("duplicate_record_id")
            rows.append(dict(record))
            self._write(collection, rows)

    def records(self, *, collection: str = "records") -> list[dict[str, Any]]:
        with self.lock:
            return self._read(collection)

    def replace_collection(self, collection: str, rows: list[dict[str, Any]]) -> None:
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise StoreError("collection_must_be_list_of_objects")
        with self.lock:
            self._write(collection, rows)
