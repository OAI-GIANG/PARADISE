from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

SCHEMA_VERSION = "LOVE-RECORD-ENVELOPE-1.0"
CONTRACT_VERSION = "LOVE-CANONICAL-SEMANTICS-1.0"
ACTOR_TYPES = {
    "HUMAN","STT","OG","RUNTIME","EVIDENCE","VERIFIER","LIFECYCLE",
    "EVOLUTION","PROVIDER","CLIENT","EXTERNAL_WITNESS","SYSTEM",
}
AUTHORITY_LEVELS = {f"A{i}" for i in range(10)}
TRUST_BOUNDARIES = {
    "TB-human","TB-stt","TB-og","TB-runtime","TB-evidence",
    "TB-verifier","TB-lifecycle","TB-evolution","TB-provider",
    "TB-client","TB-external","TB-system",
}


class EnvelopeError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rid(prefix: str = "REC") -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _nonempty(name: str, value: Any) -> str:
    value = str(value).strip()
    if not value:
        raise EnvelopeError(f"{name} is required")
    return value


@dataclass(frozen=True)
class Actor:
    type: str
    id: str

    def __post_init__(self) -> None:
        if self.type not in ACTOR_TYPES:
            raise EnvelopeError(f"unsupported actor type: {self.type}")
        _nonempty("actor.id", self.id)


@dataclass(frozen=True)
class Authority:
    level: str
    ref: str

    def __post_init__(self) -> None:
        if self.level not in AUTHORITY_LEVELS:
            raise EnvelopeError("unsupported authority level")
        _nonempty("authority.ref", self.ref)


@dataclass(frozen=True)
class Provenance:
    source_commit: str
    source_tree_sha: str
    component: str
    environment: str

    def __post_init__(self) -> None:
        _nonempty("provenance.source_commit", self.source_commit)
        _nonempty("provenance.source_tree_sha", self.source_tree_sha)
        _nonempty("provenance.component", self.component)
        _nonempty("provenance.environment", self.environment)


@dataclass(frozen=True)
class SecurityContext:
    principal: str
    authn: str
    scopes: tuple[str, ...]
    trust_boundary: str
    sensitivity: str = "internal"
    redacted: bool = True

    def __post_init__(self) -> None:
        _nonempty("security_context.principal", self.principal)
        _nonempty("security_context.authn", self.authn)
        if self.trust_boundary not in TRUST_BOUNDARIES:
            raise EnvelopeError("unsupported trust boundary")
        if not self.redacted:
            raise EnvelopeError("security context must be redacted")


@dataclass(frozen=True)
class RecordEnvelope:
    record_type: str
    actor: Actor
    authority: Authority
    correlation_id: str
    causation_id: str | None
    provenance: Provenance
    security_context: SecurityContext
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()
    record_id: str = field(default_factory=_rid)
    occurred_at: str = field(default_factory=_utc_now)
    run_id: str | None = None
    task_id: str | None = None
    idempotency_key: str | None = None
    relations: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nonempty("record_type", self.record_type)
        _nonempty("correlation_id", self.correlation_id)
        _nonempty("record_id", self.record_id)
        _nonempty("occurred_at", self.occurred_at)
        if self.causation_id == self.record_id:
            raise EnvelopeError("causation_id cannot reference self")
        if not isinstance(self.payload, dict):
            raise EnvelopeError("payload must be an object")
        if self.task_id and not str(self.task_id).strip():
            raise EnvelopeError("task_id cannot be empty")
        if self.idempotency_key is not None and not str(self.idempotency_key).strip():
            raise EnvelopeError("idempotency_key cannot be empty")

    @classmethod
    def create(
        cls,
        *,
        record_type: str,
        actor_type: str,
        actor_id: str,
        authority_level: str,
        authority_ref: str,
        correlation_id: str,
        causation_id: str | None,
        provenance: Provenance,
        security_context: SecurityContext,
        payload: dict[str, Any],
        evidence_refs: tuple[str, ...] = (),
        run_id: str | None = None,
        task_id: str | None = None,
        idempotency_key: str | None = None,
        relations: dict[str, tuple[str, ...]] | None = None,
    ) -> "RecordEnvelope":
        return cls(
            record_type=record_type,
            actor=Actor(actor_type, actor_id),
            authority=Authority(authority_level, authority_ref),
            correlation_id=correlation_id,
            causation_id=causation_id,
            provenance=provenance,
            security_context=security_context,
            payload=payload,
            evidence_refs=evidence_refs,
            run_id=run_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            relations=relations or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "contract_version": CONTRACT_VERSION,
            "record_id": self.record_id,
            "record_type": self.record_type,
            "occurred_at": self.occurred_at,
            "actor": {"type": self.actor.type, "id": self.actor.id},
            "authority": {"level": self.authority.level, "ref": self.authority.ref},
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "idempotency_key": self.idempotency_key,
            "provenance": {
                "source_commit": self.provenance.source_commit,
                "source_tree_sha": self.provenance.source_tree_sha,
                "component": self.provenance.component,
                "environment": self.provenance.environment,
            },
            "evidence_refs": list(self.evidence_refs),
            "security_context": {
                "principal": self.security_context.principal,
                "authn": self.security_context.authn,
                "scopes": list(self.security_context.scopes),
                "trust_boundary": self.security_context.trust_boundary,
                "sensitivity": self.security_context.sensitivity,
                "redacted": self.security_context.redacted,
            },
            "payload": self.payload,
            "relations": {
                key: list(value) for key, value in self.relations.items()
            },
        }


def validate_envelope_payload(payload: dict[str, Any]) -> RecordEnvelope:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise EnvelopeError("unsupported record envelope schema")
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise EnvelopeError("unsupported record envelope contract")
    actor = payload.get("actor") or {}
    auth = payload.get("authority") or {}
    provenance = payload.get("provenance") or {}
    security = payload.get("security_context") or {}
    return RecordEnvelope(
        record_type=payload["record_type"],
        actor=Actor(actor["type"], actor["id"]),
        authority=Authority(auth["level"], auth["ref"]),
        correlation_id=payload["correlation_id"],
        causation_id=payload.get("causation_id"),
        provenance=Provenance(
            provenance["source_commit"],
            provenance["source_tree_sha"],
            provenance["component"],
            provenance["environment"],
        ),
        security_context=SecurityContext(
            security["principal"],
            security["authn"],
            tuple(security.get("scopes", ())),
            security["trust_boundary"],
            security.get("sensitivity", "internal"),
            bool(security.get("redacted", True)),
        ),
        payload=payload.get("payload", {}),
        evidence_refs=tuple(payload.get("evidence_refs", ())),
        record_id=payload["record_id"],
        occurred_at=payload["occurred_at"],
        run_id=payload.get("run_id"),
        task_id=payload.get("task_id"),
        idempotency_key=payload.get("idempotency_key"),
        relations={
            key: tuple(value) for key, value in (payload.get("relations") or {}).items()
        },
    )
