from __future__ import annotations

from enum import Enum


class LifecycleState(str, Enum):
    """Canonical 16-state lifecycle; execution/verification/decision are separate."""
    DISCOVERED = "DISCOVERED"
    PROPOSED = "PROPOSED"
    PROTOTYPED = "PROTOTYPED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    HANDOVER = "HANDOVER"
    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    CONDITIONAL_ACCEPTANCE = "CONDITIONAL_ACCEPTANCE"
    REJECTED = "REJECTED"
    TRIAL = "TRIAL"
    REALITY_VALIDATED = "REALITY_VALIDATED"
    OPERATIONALIZED = "OPERATIONALIZED"
    PRODUCTION = "PRODUCTION"
    CLOSED = "CLOSED"


class ExecutionState(str, Enum):
    PENDING = "PENDING"
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    OBSERVED = "OBSERVED"
    VALIDATING = "VALIDATING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


class HealthState(str, Enum):
    UNKNOWN = "UNKNOWN"
    STARTING = "STARTING"
    BUSY = "BUSY"
    WAITING_USER = "WAITING_USER"
    IDLE = "IDLE"
    STALE = "STALE"
    FAILED = "FAILED"
    DISCONNECTED = "DISCONNECTED"
    TERMINATED = "TERMINATED"
    OTHER = "OTHER"


class VerificationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    EXPIRED = "EXPIRED"


class GovernanceDecision(str, Enum):
    NONE = "NONE"
    ALLOW = "ALLOW"
    HOLD = "HOLD"
    STOP = "STOP"
    REAUTHORIZE = "REAUTHORIZE"
    ACCEPT = "ACCEPT"
    CONDITIONAL_ACCEPT = "CONDITIONAL_ACCEPT"
    REJECT = "REJECT"


class PromotionState(str, Enum):
    NOT_PROMOTED = "NOT_PROMOTED"
    PROMOTED = "PROMOTED"
    HELD = "HELD"
    INVALIDATED = "INVALIDATED"


class Outcome(str, Enum):
    NONE = "NONE"
    ACCEPTED = "ACCEPTED"
    CONDITIONALLY_ACCEPTED = "CONDITIONALLY_ACCEPTED"
    REJECTED = "REJECTED"
    PASSED = "PASSED"
    FAILED = "FAILED"


class Recovery(str, Enum):
    NONE = "NONE"
    REWORK = "REWORK"
    RETRY_TRIAL = "RETRY_TRIAL"
    ROLLBACK_TO_VERIFIED = "ROLLBACK_TO_VERIFIED"
    ROLLBACK_TO_OPERATIONALIZED = "ROLLBACK_TO_OPERATIONALIZED"
    REMEDIATION = "REMEDIATION"


class RealityPhase(str, Enum):
    """Operational phases represented as events/conditions, not extra lifecycle states."""
    OBSERVATION = "OBSERVATION"
    STABILIZATION = "STABILIZATION"
    BASELINE = "BASELINE"


class LifecycleEvent(str, Enum):
    HANDOVER = "HANDOVER"
    RECEIPT = "RECEIPT"
    ACCEPTANCE = "ACCEPTANCE"
    CONDITIONAL_ACCEPTANCE = "CONDITIONAL_ACCEPTANCE"
    REJECTION = "REJECTION"
    OWNERSHIP_TRANSFER = "OWNERSHIP_TRANSFER"
    TRIAL = "TRIAL"
    REALITY_VALIDATION = "REALITY_VALIDATION"
    OPERATIONALIZATION = "OPERATIONALIZATION"
    PRODUCTION = "PRODUCTION"
    OBSERVATION = "OBSERVATION"
    STABILIZATION = "STABILIZATION"
    BASELINE = "BASELINE"
    CLOSURE = "CLOSURE"


def assert_state_separation(*, lifecycle: str | None = None, execution: str | None = None,
                            verification: str | None = None, promotion: str | None = None) -> None:
    if lifecycle == "PROMOTED":
        raise ValueError("PROMOTED is not a lifecycle state; promotion is separate")
    if promotion == "PROMOTED" and lifecycle not in {"PRODUCTION", "OPERATIONALIZED"}:
        raise ValueError("promotion cannot imply arbitrary lifecycle state")
    if verification == "VERIFIED" and execution == "PASSED" and lifecycle not in {"VERIFIED", "HANDOVER", "RECEIVED", "ACCEPTED", "CONDITIONAL_ACCEPTANCE", "TRIAL", "REALITY_VALIDATED", "OPERATIONALIZED", "PRODUCTION", "CLOSED"}:
        raise ValueError("execution success cannot independently establish lifecycle verification")
