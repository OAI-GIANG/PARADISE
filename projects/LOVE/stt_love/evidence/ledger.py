"""Append-only evidence ledger for OG.

The ledger records evidence facts and integrity metadata. It never decides
policy, promotion or verification status.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


class EvidenceLedgerError(ValueError):
    pass


@dataclass(frozen=True)
class LedgerEntry:
    sequence: int
    evidence_id: str
    payload: dict[str, Any]
    prev_digest: str
    record_digest: str


class EvidenceLedger:
    schema_version = "OG-EVIDENCE-LEDGER-1.0"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _digest(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    def _read_raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise EvidenceLedgerError("ledger row must be an object")
                rows.append(row)
        return rows

    def entries(self) -> tuple[LedgerEntry, ...]:
        rows = self._read_raw()
        result = []
        seen_ids = set()
        previous = "GENESIS"
        for index, row in enumerate(rows, start=1):
            if row.get("schema_version") != self.schema_version:
                raise EvidenceLedgerError("unsupported ledger schema")
            if int(row.get("sequence", 0)) != index:
                raise EvidenceLedgerError("non-contiguous evidence ledger sequence")
            evidence_id = str(row.get("evidence_id", ""))
            if not evidence_id or evidence_id in seen_ids:
                raise EvidenceLedgerError("duplicate or empty evidence_id")
            payload = row.get("payload")
            if not isinstance(payload, dict):
                raise EvidenceLedgerError("ledger payload must be an object")
            if row.get("prev_digest") != previous:
                raise EvidenceLedgerError("evidence hash-chain predecessor mismatch")
            expected = self._digest(
                {
                    "sequence": index,
                    "evidence_id": evidence_id,
                    "payload": payload,
                    "prev_digest": previous,
                }
            )
            if row.get("record_digest") != expected:
                raise EvidenceLedgerError("evidence record digest mismatch")
            previous = expected
            seen_ids.add(evidence_id)
            result.append(LedgerEntry(index, evidence_id, payload, row["prev_digest"], row["record_digest"]))
        return tuple(result)

    def append(self, evidence_id: str, payload: dict[str, Any]) -> LedgerEntry:
        evidence_id = str(evidence_id).strip()
        if not evidence_id:
            raise EvidenceLedgerError("evidence_id is required")
        if not isinstance(payload, dict):
            raise EvidenceLedgerError("payload must be a dict")
        existing = self.entries()
        if any(row.evidence_id == evidence_id for row in existing):
            raise EvidenceLedgerError("evidence_id already exists")
        sequence = len(existing) + 1
        prev_digest = existing[-1].record_digest if existing else "GENESIS"
        record_digest = self._digest(
            {
                "sequence": sequence,
                "evidence_id": evidence_id,
                "payload": payload,
                "prev_digest": prev_digest,
            }
        )
        row = {
            "schema_version": self.schema_version,
            "sequence": sequence,
            "evidence_id": evidence_id,
            "payload": payload,
            "prev_digest": prev_digest,
            "record_digest": record_digest,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return LedgerEntry(sequence, evidence_id, payload, prev_digest, record_digest)

    def verify(self) -> tuple[LedgerEntry, ...]:
        return self.entries()
