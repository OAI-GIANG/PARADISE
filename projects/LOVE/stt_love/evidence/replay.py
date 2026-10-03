"""Append-only execution replay log with hash chaining."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class ReplayIntegrityError(RuntimeError):
    pass


class ExecutionReplay:
    GENESIS = "GENESIS"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        previous = self.GENESIS
        if self.path.exists():
            rows = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
            if rows:
                previous = rows[-1]["digest"]
        seq = (rows[-1]["seq"] + 1) if self.path.exists() and rows else 1
        record = {"seq": seq, "previous_digest": previous, "event": event}
        payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        record["digest"] = hashlib.sha256(payload).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return record

    def verify(self) -> None:
        if not self.path.exists():
            return
        previous = self.GENESIS
        expected_seq = 1
        for raw in self.path.read_text().splitlines():
            if not raw.strip():
                continue
            row = json.loads(raw)
            if row["seq"] != expected_seq:
                raise ReplayIntegrityError("sequence_gap")
            if row["previous_digest"] != previous:
                raise ReplayIntegrityError("hash_chain_break")
            supplied = row.pop("digest")
            payload = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            if hashlib.sha256(payload).hexdigest() != supplied:
                raise ReplayIntegrityError("digest_mismatch")
            previous = supplied
            expected_seq += 1

    def load(self) -> list[dict]:
        self.verify()
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
