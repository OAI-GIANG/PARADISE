"""Minimal PARADISE kernel implementation for semantic kernel V1."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import FrozenSet, Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class GateResult(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    BLOCKED = "BLOCKED"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Authority:
    authority_id: str
    subject: str
    scope: FrozenSet[str]
    actions: FrozenSet[str]
    issuer: str
    valid_from: datetime
    valid_until: datetime
    contexts: FrozenSet[str] = frozenset()
    status: str = "ACTIVE"
    provenance: str = ""

    def permits(self, subject: str, action: str, scope: str, context: str, at: datetime) -> bool:
        return (
            self.status == "ACTIVE"
            and self.subject == subject
            and action in self.actions
            and scope in self.scope
            and context in self.contexts
            and self.valid_from <= at <= self.valid_until
            and bool(self.provenance)
        )


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    subject: str
    scope: str
    source: str
    captured_at: datetime
    provenance: str
    integrity: str
    verification_status: str
    claim: str = ""

    def canonical_payload(self) -> str:
        return "|".join((self.evidence_id, self.subject, self.scope, self.source,
                         self.captured_at.isoformat(), self.provenance))

    def expected_integrity(self) -> str:
        return sha256(self.canonical_payload().encode("utf-8")).hexdigest()

    def is_verified(self, subject: str, scope: str) -> bool:
        return (
            self.subject == subject
            and self.scope == scope
            and bool(self.source)
            and bool(self.provenance)
            and self.integrity == self.expected_integrity()
            and self.verification_status == "VERIFIED"
        )


@dataclass(frozen=True)
class State:
    entity_id: str
    value: str
    version: int
    lifecycle: str = "ACTIVE"


@dataclass(frozen=True)
class Advisory:
    advisory_id: str
    recommendation: str
    evidence_ids: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class Authorization:
    authority_id: str
    subject: str
    action: str
    scope: str
    context: str
    issued_at: datetime
    expires_at: datetime

    def fresh(self, at: datetime) -> bool:
        return self.issued_at <= at <= self.expires_at


@dataclass(frozen=True)
class Execution:
    execution_id: str
    action: str
    subject: str
    scope: str
    input_version: int
    authorization: Authorization
    idempotent: bool = False
    result_witness: str = ""


@dataclass(frozen=True)
class ChangeRequest:
    change_id: str
    requester: str
    target: str
    requested_scope: FrozenSet[str]
    authorized_scope: FrozenSet[str]
    authority_subject: str = ""
    self_modification: bool = False
    verification_required: bool = True
    recovery_ref: str = ""

    def bounded(self) -> bool:
        if not self.requested_scope.issubset(self.authorized_scope):
            return False
        if self.self_modification and self.authority_subject == self.target:
            return False
        if self.verification_required and not self.recovery_ref:
            return False
        return True


@dataclass
class Kernel:
    """Enforcement facade for PARADISE semantic kernel V1."""
    trusted_evidence_sources: FrozenSet[str] = frozenset()
    consumed_executions: set[str] = field(default_factory=set)

    def authorize(
        self,
        authority: Authority,
        subject: str,
        action: str,
        scope: str,
        context: str,
        at: Optional[datetime] = None,
    ) -> tuple[GateResult, Optional[Authorization]]:
        at = at or now_utc()
        if not authority.permits(subject, action, scope, context, at):
            return GateResult.DENY, None
        return GateResult.ALLOW, Authorization(
            authority.authority_id, subject, action, scope, context, at, authority.valid_until
        )

    def verify_evidence(self, evidence: Evidence, subject: str, scope: str) -> GateResult:
        if evidence.source not in self.trusted_evidence_sources:
            return GateResult.BLOCKED
        return GateResult.ALLOW if evidence.is_verified(subject, scope) else GateResult.BLOCKED

    def evaluate_evidence(self, evidence_items: list[Evidence], subject: str, scope: str) -> GateResult:
        verified = [e for e in evidence_items if self.verify_evidence(e, subject, scope) == GateResult.ALLOW]
        claims = {e.claim for e in verified if e.claim}
        if len(claims) > 1:
            return GateResult.CONFLICT
        return GateResult.ALLOW if verified else GateResult.UNKNOWN

    def evaluate_unknown(self) -> GateResult:
        return GateResult.UNKNOWN

    def advisory_to_authorization(self, advisory: Advisory) -> GateResult:
        return GateResult.DENY

    def evidence_to_authorization(self, evidence: Evidence) -> GateResult:
        return GateResult.DENY

    def transition(self, current: State, expected_version: int, new_value: str) -> tuple[GateResult, Optional[State]]:
        if current.lifecycle != "ACTIVE":
            return GateResult.BLOCKED, None
        if expected_version != current.version:
            return GateResult.CONFLICT, None
        if not new_value:
            return GateResult.DENY, None
        return GateResult.ALLOW, State(current.entity_id, new_value, current.version + 1, current.lifecycle)

    def execute_external(self, execution: Execution, at: Optional[datetime] = None) -> GateResult:
        at = at or now_utc()
        if not execution.authorization.fresh(at):
            return GateResult.DENY
        if execution.authorization.subject != execution.subject:
            return GateResult.DENY
        if execution.authorization.action != execution.action:
            return GateResult.DENY
        if execution.authorization.scope != execution.scope:
            return GateResult.DENY
        if not execution.result_witness:
            return GateResult.BLOCKED
        if execution.execution_id in self.consumed_executions and not execution.idempotent:
            return GateResult.DENY
        self.consumed_executions.add(execution.execution_id)
        return GateResult.ALLOW

    def change_allowed(self, change: ChangeRequest) -> GateResult:
        return GateResult.ALLOW if change.bounded() else GateResult.DENY