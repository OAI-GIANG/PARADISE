from __future__ import annotations

from enum import Enum


class LifecycleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    PROPOSED = "PROPOSED"
    PROTOTYPED = "PROTOTYPED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    PROMOTED = "PROMOTED"
    DEGRADED = "DEGRADED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


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
    ALLOW = "ALLOW"
    HOLD = "HOLD"
    STOP = "STOP"
    REAUTHORIZE = "REAUTHORIZE"


class PromotionState(str, Enum):
    NOT_PROMOTED = "NOT_PROMOTED"
    PROMOTED = "PROMOTED"
    HELD = "HELD"
    INVALIDATED = "INVALIDATED"


def assert_state_separation(
    *,
    lifecycle: str | None = None,
    execution: str | None = None,
    verification: str | None = None,
    promotion: str | None = None,
) -> None:
    if lifecycle == "PROMOTED" and promotion != "PROMOTED":
        raise ValueError("PROMOTED lifecycle requires PROMOTED promotion state")
    if promotion == "PROMOTED" and lifecycle != "PROMOTED":
        raise ValueError("promotion state cannot self-promote lifecycle")
    if verification == "VERIFIED" and lifecycle == "PROMOTED" and promotion != "PROMOTED":
        raise ValueError("verification cannot imply promotion")
    if execution == "PASSED" and verification == "UNVERIFIED":
        raise ValueError("execution success cannot be treated as verification")
