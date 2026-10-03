from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable

from .ledger import EvidenceLedger


class EvidenceClass(str, Enum):
    INTEGRITY = "Integrity"
    EXECUTION = "Execution"
    OUTCOME = "Outcome"
    INDEPENDENT_VERIFICATION = "Independent Verification"
    EXTERNAL_WITNESS = "External Witness"


class EvidenceResolution(str, Enum):
    TRUSTED = "TRUSTED"
    TRUSTED_WITH_REVALIDATION = "TRUSTED_WITH_REVALIDATION"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    REFUTED = "REFUTED"
    INAPPLICABLE = "INAPPLICABLE"
    MISSING = "MISSING"
    CONFLICT = "CONFLICT"
    INTEGRITY_INVALID = "INTEGRITY_INVALID"


class InvalidationEvent(str, Enum):
    SOURCE_CHANGED = "INVALIDATION_SOURCE_CHANGED"
    ENV_CHANGED = "INVALIDATION_ENV_CHANGED"
    PROVIDER_CHANGED = "INVALIDATION_PROVIDER_CHANGED"
    POLICY_CHANGED = "INVALIDATION_POLICY_CHANGED"
    EXPLICIT_REFUTATION = "INVALIDATION_EXPLICIT_REFUTATION"
    VERIFICATION_EXPIRED = "INVALIDATION_VERIFICATION_EXPIRED"


class EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    claim_id: str
    subject_id: str
    assertion: str
    scope: str
    environment_id: str
    evidence_class: EvidenceClass
    occurred_at: str
    source_commit: str
    source_tree_sha: str
    payload: dict[str, Any]
    artifact_refs: tuple[str, ...] = ()
    replay_refs: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    refutes: tuple[str, ...] = ()
    invalidation_events: tuple[str, ...] = ()
    expires_at: str | None = None

    relation_type: str | None = None
    target_record_type: str | None = None
    claim_scope: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "LOVE-EVIDENCE-1.0",
            "evidence_id": self.evidence_id,
            "claim_id": self.claim_id,
            "subject_id": self.subject_id,
            "assertion": self.assertion,
            "scope": self.scope,
            "environment_id": self.environment_id,
            "evidence_class": self.evidence_class.value,
            "occurred_at": self.occurred_at,
            "source_commit": self.source_commit,
            "source_tree_sha": self.source_tree_sha,
            "payload": self.payload,
            "artifact_refs": list(self.artifact_refs),
            "replay_refs": list(self.replay_refs),
            "supersedes": list(self.supersedes),
            "refutes": list(self.refutes),
            "invalidation_events": list(self.invalidation_events),
            "expires_at": self.expires_at,
            "relation_type": self.relation_type,
            "target_record_type": self.target_record_type,
            "claim_scope": self.claim_scope,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EvidenceRecord":
        if payload.get("schema_version") != "LOVE-EVIDENCE-1.0":
            raise EvidenceError("unsupported evidence schema")
        try:
            record = cls(
                evidence_id=str(payload["evidence_id"]),
                claim_id=str(payload["claim_id"]),
                subject_id=str(payload["subject_id"]),
                assertion=str(payload["assertion"]),
                scope=str(payload["scope"]),
                environment_id=str(payload["environment_id"]),
                evidence_class=EvidenceClass(str(payload["evidence_class"])),
                occurred_at=str(payload["occurred_at"]),
                source_commit=str(payload["source_commit"]),
                source_tree_sha=str(payload["source_tree_sha"]),
                payload=dict(payload.get("payload") or {}),
                artifact_refs=tuple(payload.get("artifact_refs") or ()),
                replay_refs=tuple(payload.get("replay_refs") or ()),
                supersedes=tuple(payload.get("supersedes") or ()),
                refutes=tuple(payload.get("refutes") or ()),
                invalidation_events=tuple(payload.get("invalidation_events") or ()),
                expires_at=payload.get("expires_at"),
                relation_type=payload.get("relation_type"),
                target_record_type=payload.get("target_record_type"),
                claim_scope=payload.get("claim_scope"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise EvidenceError("malformed evidence record") from exc
        return record

def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise EvidenceError("invalid evidence timestamp") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _valid_git_sha(value: str) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdefABCDEF" for c in value)


class EvidenceCore:
    """Semantic evidence owner layered over EvidenceLedger integrity."""

    FORBIDDEN_AUTHORITY_KEYS = {
        "authorize_execution",
        "governance_decision",
        "permission_grant",
        "runtime_enabled",
        "promotion_state",
        "lifecycle_state",
    }

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    def append(self, record: EvidenceRecord):
        self.validate(record)
        return self.ledger.append(record.evidence_id, record.to_payload())

    def validate(self, record: EvidenceRecord) -> None:
        required = (
            record.evidence_id, record.claim_id, record.subject_id, record.assertion,
            record.scope, record.environment_id, record.source_commit, record.source_tree_sha,
        )
        if not all(str(value).strip() for value in required):
            raise EvidenceError("evidence record has missing required fields")
        if not _valid_git_sha(record.source_commit) or not _valid_git_sha(record.source_tree_sha):
            raise EvidenceError("evidence provenance must bind 40-hex source commit/tree")
        _parse_time(record.occurred_at)
        if record.expires_at:
            _parse_time(record.expires_at)
        if record.relation_type and record.relation_type not in {"SUPERSEDES", "REFUTES"}:
            raise EvidenceError("unsupported evidence relation")
        if record.relation_type and (not record.target_record_type or not record.claim_scope):
            raise EvidenceError("typed relations require target record type and claim scope")
        for key in self.FORBIDDEN_AUTHORITY_KEYS:
            if key in record.payload:
                raise EvidenceError(f"evidence cannot grant authority: {key}")

    def records(self) -> tuple[EvidenceRecord, ...]:
        self.ledger.verify()
        return tuple(EvidenceRecord.from_payload(entry.payload) for entry in self.ledger.entries())

    def resolve(
        self,
        claim_id: str,
        *,
        required_classes: Iterable[EvidenceClass] = (),
        expected_source_commit: str | None = None,
        expected_source_tree_sha: str | None = None,
        freshness_days: int | None = None,
        now: datetime | None = None,
    ) -> EvidenceResolution:
        try:
            records = [r for r in self.records() if r.claim_id == claim_id]
        except Exception:
            return EvidenceResolution.INTEGRITY_INVALID
        if not records:
            return EvidenceResolution.MISSING
        required = set(required_classes)
        supplied = {r.evidence_class for r in records}
        if not required.issubset(supplied):
            return EvidenceResolution.MISSING

        by_id = {r.evidence_id: r for r in records}
        refuted = set(ref for r in records for ref in r.refutes)
        if any(r.evidence_id in refuted for r in records):
            return EvidenceResolution.CONFLICT
        if any(target not in by_id for r in records for target in (*r.refutes, *r.supersedes)):
            return EvidenceResolution.CONFLICT

        for record in records:
            if expected_source_commit and record.source_commit != expected_source_commit:
                return EvidenceResolution.INAPPLICABLE
            if expected_source_tree_sha and record.source_tree_sha != expected_source_tree_sha:
                return EvidenceResolution.INAPPLICABLE

        # Refutation has precedence over supersession.
        current_ids = {r.evidence_id for r in records}
        superseded = {target for r in records for target in r.supersedes if target in current_ids}
        candidates = [r for r in records if r.evidence_id not in superseded]
        if not candidates:
            return EvidenceResolution.SUPERSEDED
        if any(r.invalidation_events for r in candidates):
            return EvidenceResolution.STALE

        current_time = now or datetime.now(timezone.utc)
        if freshness_days is not None:
            cutoff = current_time - timedelta(days=freshness_days)
            if any(_parse_time(r.occurred_at) < cutoff for r in candidates):
                return EvidenceResolution.STALE
        if any(r.expires_at and _parse_time(r.expires_at) <= current_time for r in candidates):
            return EvidenceResolution.STALE
        return EvidenceResolution.TRUSTED

    def satisfies(
        self,
        claim_id: str,
        *,
        required_classes: Iterable[EvidenceClass] = (),
        expected_source_commit: str | None = None,
        expected_source_tree_sha: str | None = None,
        freshness_days: int | None = None,
    ) -> bool:
        return self.resolve(
            claim_id,
            required_classes=required_classes,
            expected_source_commit=expected_source_commit,
            expected_source_tree_sha=expected_source_tree_sha,
            freshness_days=freshness_days,
        ) is EvidenceResolution.TRUSTED


REPLAY_CLASS_TO_EVIDENCE = {
    "TRACE_VALID": EvidenceClass.INTEGRITY,
    "RE_EXECUTED": EvidenceClass.EXECUTION,
    "RE_EXECUTION_FAILED": EvidenceClass.EXECUTION,
    "DETERMINISTIC_MATCH": EvidenceClass.INDEPENDENT_VERIFICATION,
    "DETERMINISTIC_MISMATCH": EvidenceClass.INDEPENDENT_VERIFICATION,
    "CROSS_HOST_MATCH": EvidenceClass.EXTERNAL_WITNESS,
    "CROSS_HOST_MISMATCH": EvidenceClass.EXTERNAL_WITNESS,
}


def replay_result_to_evidence_class(result_class: str) -> EvidenceClass:
    try:
        return REPLAY_CLASS_TO_EVIDENCE[str(result_class)]
    except KeyError as exc:
        raise EvidenceError("unknown replay result class") from exc
