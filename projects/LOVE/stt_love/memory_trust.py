from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from typing import Any


class MemoryTrustError(ValueError):
    pass


class MemoryTrustStatus(str, Enum):
    UNTRUSTED = "UNTRUSTED"
    OBSERVED = "OBSERVED"
    CORROBORATED = "CORROBORATED"
    VERIFIED = "VERIFIED"
    QUALIFIED = "QUALIFIED"
    SUPERSEDED = "SUPERSEDED"
    REFUTED = "REFUTED"
    EXPIRED = "EXPIRED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class TrustCertificate:
    certificate_id: str
    evaluator_id: str
    evaluator_kind: str
    method: str
    artifact_digest: str
    source_commit: str
    source_tree_sha: str
    result: str
    evidence_refs: tuple[str, ...]
    issued_at: str

    def validate(self) -> "TrustCertificate":
        required = (
            self.certificate_id, self.evaluator_id, self.evaluator_kind,
            self.method, self.artifact_digest, self.source_commit,
            self.source_tree_sha, self.result, self.issued_at,
        )
        if not all(str(value).strip() for value in required):
            raise MemoryTrustError("verification certificate is incomplete")
        if self.result not in {"VERIFIED", "QUALIFIED"}:
            raise MemoryTrustError("certificate result must be VERIFIED or QUALIFIED")
        if not self.evidence_refs:
            raise MemoryTrustError("verification certificate requires evidence refs")
        return self


VerificationCertificate = TrustCertificate


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    memory_class: str
    normalized_key: str
    claim: str
    scope: str
    source_actor: str
    authority: str
    created_at: str
    observed_at: str
    trust_status: MemoryTrustStatus
    confidence: float
    freshness_days: int
    evidence_refs: tuple[str, ...]
    provenance_commit: str
    provenance_tree_sha: str
    environment_id: str
    supersedes: tuple[str, ...] = ()
    refutes: tuple[str, ...] = ()
    issue_id: str | None = None
    task_id: str | None = None
    decision_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    idempotency_key: str | None = None
    support_group_ids: tuple[str, ...] = ()

    def to_dict(self):
        return {**self.__dict__, "trust_status": self.trust_status.value,
                "evidence_refs": list(self.evidence_refs),
                "supersedes": list(self.supersedes), "refutes": list(self.refutes),
                "support_group_ids": list(self.support_group_ids)}

    @property
    def fresh_until(self):
        observed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        return (observed + timedelta(days=self.freshness_days)).isoformat()


def normalize_key(subject: str, predicate: str, scope: str, environment_id: str) -> str:
    raw = "|".join(v.strip().lower() for v in (subject, predicate, scope, environment_id))
    if not raw:
        raise MemoryTrustError("memory identity cannot be empty")
    return "MEM-" + sha256(raw.encode()).hexdigest()[:24]


def memory_artifact_digest(record: MemoryRecord) -> str:
    """Digest the immutable memory payload excluding mutable trust status."""
    payload = {
        "memory_id": record.memory_id,
        "memory_class": record.memory_class,
        "normalized_key": record.normalized_key,
        "claim": record.claim,
        "scope": record.scope,
        "source_actor": record.source_actor,
        "authority": record.authority,
        "created_at": record.created_at,
        "observed_at": record.observed_at,
        "confidence": record.confidence,
        "freshness_days": record.freshness_days,
        "evidence_refs": list(record.evidence_refs),
        "provenance_commit": record.provenance_commit,
        "provenance_tree_sha": record.provenance_tree_sha,
        "environment_id": record.environment_id,
        "supersedes": list(record.supersedes),
        "refutes": list(record.refutes),
        "support_group_ids": list(record.support_group_ids),
    }
    return sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()


class MemoryCore:
    """Canonical trust semantics layered over raw Store memory."""

    def validate(self, record: MemoryRecord) -> None:
        required = (
            record.memory_id, record.memory_class, record.normalized_key,
            record.claim, record.scope, record.source_actor, record.authority,
            record.provenance_commit, record.provenance_tree_sha,
            record.environment_id,
        )
        if not all(str(v).strip() for v in required):
            raise MemoryTrustError("memory record missing required fields")
        if record.confidence < 0 or record.confidence > 1:
            raise MemoryTrustError("memory confidence must be within 0..1")
        if record.freshness_days <= 0:
            raise MemoryTrustError("freshness_days must be positive")
        if record.trust_status in {MemoryTrustStatus.VERIFIED, MemoryTrustStatus.QUALIFIED} and not record.evidence_refs:
            raise MemoryTrustError("trusted memory requires evidence refs")
        if record.trust_status is MemoryTrustStatus.CORROBORATED and len(set(record.support_group_ids)) < 2:
            raise MemoryTrustError("CORROBORATED memory requires two independent support groups")
        for relation in (*record.supersedes, *record.refutes):
            if not str(relation).strip():
                raise MemoryTrustError("empty memory relation")

    def observe(self, *, memory_id, memory_class, claim, scope, source_actor,
                authority, provenance_commit, provenance_tree_sha, environment_id,
                evidence_refs=(), freshness_days=7, confidence=0.0,
                normalized_key=None, task_id=None, issue_id=None, decision_id=None,
                correlation_id=None, causation_id=None, idempotency_key=None,
                support_group_ids=(), observed_at=None) -> MemoryRecord:
        when = observed_at or datetime.now(timezone.utc).isoformat()
        key = normalized_key or normalize_key(claim.split(" ", 1)[0], claim, scope, environment_id)
        record = MemoryRecord(
            memory_id=str(memory_id),
            memory_class=str(memory_class),
            normalized_key=key,
            claim=str(claim),
            scope=str(scope),
            source_actor=str(source_actor),
            authority=str(authority),
            created_at=when,
            observed_at=when,
            trust_status=MemoryTrustStatus.OBSERVED,
            confidence=float(confidence),
            freshness_days=int(freshness_days),
            evidence_refs=tuple(evidence_refs),
            provenance_commit=str(provenance_commit),
            provenance_tree_sha=str(provenance_tree_sha),
            environment_id=str(environment_id),
            task_id=task_id, issue_id=issue_id, decision_id=decision_id,
            correlation_id=correlation_id, causation_id=causation_id,
            idempotency_key=idempotency_key,
            support_group_ids=tuple(sorted(set(str(x).strip() for x in support_group_ids if str(x).strip()))),
        )
        self.validate(record)
        return record

    def corroborate(
        self,
        record: MemoryRecord,
        supporting_ids: tuple[str, ...],
        *,
        supporting_groups: tuple[str, ...] = (),
    ) -> MemoryRecord:
        support_ids = tuple(sorted(set(str(x).strip() for x in supporting_ids if str(x).strip())))
        groups = tuple(sorted(set(str(x).strip() for x in supporting_groups if str(x).strip())))
        if len(support_ids) < 2 or len(groups) < 2:
            raise MemoryTrustError(
                "corroboration requires at least two evidence items from two independent support groups"
            )
        self.validate(record)
        return MemoryRecord(**{
            **record.__dict__,
            "trust_status": MemoryTrustStatus.CORROBORATED,
            "support_group_ids": groups,
        })

    def verified(
        self,
        record: MemoryRecord,
        *,
        certificate: TrustCertificate,
    ) -> MemoryRecord:
        certificate.validate()
        if certificate.result != "VERIFIED":
            raise MemoryTrustError("verification requires VERIFIED certificate")
        if certificate.artifact_digest != memory_artifact_digest(record):
            raise MemoryTrustError("verification certificate artifact does not match memory")
        if certificate.source_commit != record.provenance_commit:
            raise MemoryTrustError("verification certificate source commit does not match memory")
        if certificate.source_tree_sha != record.provenance_tree_sha:
            raise MemoryTrustError("verification certificate source tree does not match memory")
        if not record.evidence_refs:
            raise MemoryTrustError("VERIFIED memory requires evidence")
        if not set(certificate.evidence_refs).issubset(set(record.evidence_refs)):
            raise MemoryTrustError("verification certificate references unknown evidence")
        return MemoryRecord(**{
            **record.__dict__,
            "trust_status": MemoryTrustStatus.VERIFIED,
        })

    def qualified(
        self,
        record: MemoryRecord,
        *,
        certificate: TrustCertificate,
    ) -> MemoryRecord:
        certificate.validate()
        if certificate.result != "QUALIFIED":
            raise MemoryTrustError("qualification requires QUALIFIED certificate")
        if certificate.artifact_digest != memory_artifact_digest(record):
            raise MemoryTrustError("qualification certificate artifact does not match memory")
        if certificate.source_commit != record.provenance_commit:
            raise MemoryTrustError("qualification certificate source commit does not match memory")
        if certificate.source_tree_sha != record.provenance_tree_sha:
            raise MemoryTrustError("qualification certificate source tree does not match memory")
        if not record.evidence_refs:
            raise MemoryTrustError("QUALIFIED memory requires evidence")
        return MemoryRecord(**{
            **record.__dict__,
            "trust_status": MemoryTrustStatus.QUALIFIED,
        })

    def supersede(self, current: MemoryRecord, prior: MemoryRecord) -> MemoryRecord:
        if current.normalized_key != prior.normalized_key or current.scope != prior.scope:
            raise MemoryTrustError("supersedes requires same semantic claim scope")
        return MemoryRecord(**{
            **current.__dict__,
            "supersedes": tuple(sorted(set(current.supersedes + (prior.memory_id,)))),
        })

    def refute(self, refuter: MemoryRecord, target: MemoryRecord) -> MemoryRecord:
        if refuter.normalized_key != target.normalized_key or refuter.scope != target.scope:
            raise MemoryTrustError("refutes requires same semantic claim scope")
        return MemoryRecord(**{
            **target.__dict__,
            "trust_status": MemoryTrustStatus.REFUTED,
            "refutes": tuple(sorted(set(target.refutes + (refuter.memory_id,)))),
        })

    def refute_with_evidence(self, record: MemoryRecord, evidence_refs: tuple[str, ...]) -> MemoryRecord:
        refs = tuple(sorted(set(str(x).strip() for x in evidence_refs if str(x).strip())))
        if not refs:
            raise MemoryTrustError("refutation requires evidence refs")
        self.validate(record)
        return MemoryRecord(**{
            **record.__dict__,
            "trust_status": MemoryTrustStatus.REFUTED,
            "evidence_refs": tuple(sorted(set(record.evidence_refs + refs))),
            "refutes": tuple(record.refutes),
        })

    def evaluate_freshness(self, record: MemoryRecord, now=None) -> MemoryTrustStatus:
        current = now or datetime.now(timezone.utc)
        observed = datetime.fromisoformat(record.observed_at.replace("Z", "+00:00"))
        if current - observed > timedelta(days=record.freshness_days):
            return MemoryTrustStatus.EXPIRED
        return record.trust_status


    def resolve(self, records: list[MemoryRecord], normalized_key: str, scope: str) -> MemoryRecord | None:
        candidates = [
            record for record in records
            if record.normalized_key == normalized_key
            and record.scope == scope
            and record.trust_status not in {
                MemoryTrustStatus.REFUTED,
                MemoryTrustStatus.SUPERSEDED,
                MemoryTrustStatus.EXPIRED,
            }
        ]
        if not candidates:
            return None
        refs = {target for record in candidates for target in record.refutes}
        superseded = {target for record in candidates for target in record.supersedes}
        active = [record for record in candidates if record.memory_id not in refs and record.memory_id not in superseded]
        if not active:
            return None
        qualified = [record for record in active if record.trust_status in {
            MemoryTrustStatus.VERIFIED, MemoryTrustStatus.QUALIFIED
        }]
        if len(qualified) > 1:
            commits = {record.provenance_commit for record in qualified}
            claims = {record.claim for record in qualified}
            if len(commits) > 1 or len(claims) > 1:
                return MemoryRecord(**{
                    **qualified[0].__dict__, "trust_status": MemoryTrustStatus.CONFLICT,
                })
        active.sort(
            key=lambda record: (
                record.trust_status in {MemoryTrustStatus.QUALIFIED, MemoryTrustStatus.VERIFIED},
                record.confidence,
                record.observed_at,
                record.memory_id,
            ),
            reverse=True,
        )
        result = active[0]
        freshness = self.evaluate_freshness(result)
        return result if freshness is not MemoryTrustStatus.EXPIRED else MemoryRecord(
            **{**result.__dict__, "trust_status": MemoryTrustStatus.EXPIRED}
        )

    @staticmethod
    def routing_allowed(record: MemoryRecord, *, min_status=MemoryTrustStatus.VERIFIED) -> bool:
        return record.trust_status in {
            MemoryTrustStatus.VERIFIED, MemoryTrustStatus.QUALIFIED
        } and min_status in {
            MemoryTrustStatus.OBSERVED, MemoryTrustStatus.CORROBORATED,
            MemoryTrustStatus.VERIFIED, MemoryTrustStatus.QUALIFIED,
        }
