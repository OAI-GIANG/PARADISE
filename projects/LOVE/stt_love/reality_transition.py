from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .state_semantics import LifecycleEvent, LifecycleState, RealityPhase


class ContractError(ValueError):
    pass


class DecisionOutcome(str, Enum):
    NONE = "NONE"
    ACCEPTED = "ACCEPTED"
    CONDITIONALLY_ACCEPTED = "CONDITIONALLY_ACCEPTED"
    REJECTED = "REJECTED"


class OwnershipStatus(str, Enum):
    UNCHANGED = "UNCHANGED"
    TRANSFERRED = "TRANSFERRED"


@dataclass(frozen=True)
class EvidenceBoundary:
    refs: tuple[str, ...] = ()
    sufficient: bool = False


@dataclass(frozen=True)
class AuthorityBoundary:
    actor: str
    scope: str
    authorized: bool


@dataclass(frozen=True)
class OwnershipTransfer:
    from_owner: str
    to_owner: str
    scope: str
    effective_condition: str
    authority_ref: str
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        for name, value in (("from_owner", self.from_owner), ("to_owner", self.to_owner), ("scope", self.scope), ("effective_condition", self.effective_condition), ("authority_ref", self.authority_ref)):
            if not str(value).strip():
                raise ContractError(f"{name}_required")
        if self.from_owner == self.to_owner:
            raise ContractError("ownership_transfer_requires_distinct_owners")


@dataclass(frozen=True)
class RecoveryDirective:
    target: LifecycleState
    reason: str
    evidence_refs: tuple[str, ...]
    policy_ref: str
    authority_ref: str

    def validate(self) -> None:
        if not self.reason.strip() or not self.policy_ref.strip() or not self.authority_ref.strip():
            raise ContractError("recovery_reason_policy_authority_required")
        if not self.evidence_refs:
            raise ContractError("recovery_evidence_required")


@dataclass(frozen=True)
class RealityTransition:
    current: LifecycleState
    event: LifecycleEvent
    target: LifecycleState | None
    decision: DecisionOutcome = DecisionOutcome.NONE
    evidence: EvidenceBoundary = EvidenceBoundary()
    authority: AuthorityBoundary | None = None
    ownership: OwnershipTransfer | None = None
    recovery: RecoveryDirective | None = None
    phase: RealityPhase | None = None


# Lifecycle transitions are intentionally explicit. Ownership transfer is not a state transition.
_ALLOWED: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.DISCOVERED: {LifecycleState.PROPOSED},
    LifecycleState.PROPOSED: {LifecycleState.PROTOTYPED, LifecycleState.REJECTED},
    LifecycleState.PROTOTYPED: {LifecycleState.IMPLEMENTED, LifecycleState.REJECTED},
    LifecycleState.IMPLEMENTED: {LifecycleState.TESTED, LifecycleState.REJECTED},
    LifecycleState.TESTED: {LifecycleState.VERIFIED, LifecycleState.REJECTED},
    LifecycleState.VERIFIED: {LifecycleState.HANDOVER},
    LifecycleState.HANDOVER: {LifecycleState.RECEIVED},
    LifecycleState.RECEIVED: {LifecycleState.ACCEPTED, LifecycleState.CONDITIONAL_ACCEPTANCE, LifecycleState.REJECTED},
    LifecycleState.ACCEPTED: {LifecycleState.TRIAL},
    LifecycleState.CONDITIONAL_ACCEPTANCE: {LifecycleState.TRIAL, LifecycleState.REJECTED},
    LifecycleState.REJECTED: {LifecycleState.PROPOSED, LifecycleState.PROTOTYPED, LifecycleState.IMPLEMENTED, LifecycleState.TESTED, LifecycleState.VERIFIED},
    LifecycleState.TRIAL: {LifecycleState.REALITY_VALIDATED, LifecycleState.REJECTED},
    LifecycleState.REALITY_VALIDATED: {LifecycleState.OPERATIONALIZED, LifecycleState.REJECTED},
    LifecycleState.OPERATIONALIZED: {LifecycleState.PRODUCTION},
    LifecycleState.PRODUCTION: {LifecycleState.CLOSED},
    LifecycleState.CLOSED: set(),
}


def allowed_targets(state: LifecycleState) -> frozenset[LifecycleState]:
    return frozenset(_ALLOWED[state])


def validate_transition(t: RealityTransition) -> None:
    if t.current not in _ALLOWED:
        raise ContractError("unknown_lifecycle_state")
    if t.target is not None and t.target not in _ALLOWED[t.current]:
        raise ContractError(f"forbidden_transition:{t.current.value}->{t.target.value}")
    if t.event == LifecycleEvent.HANDOVER and (t.current != LifecycleState.VERIFIED or t.target != LifecycleState.HANDOVER):
        raise ContractError("handover_requires_verified")
    if t.event == LifecycleEvent.RECEIPT and (t.current != LifecycleState.HANDOVER or t.target != LifecycleState.RECEIVED):
        raise ContractError("receipt_requires_handover")
    if t.event == LifecycleEvent.ACCEPTANCE:
        if t.current != LifecycleState.RECEIVED or t.target != LifecycleState.ACCEPTED or t.decision != DecisionOutcome.ACCEPTED:
            raise ContractError("acceptance_requires_receipt_and_accept_decision")
    if t.event == LifecycleEvent.CONDITIONAL_ACCEPTANCE:
        if t.current != LifecycleState.RECEIVED or t.target != LifecycleState.CONDITIONAL_ACCEPTANCE or t.decision != DecisionOutcome.CONDITIONALLY_ACCEPTED:
            raise ContractError("conditional_acceptance_requires_receipt_and_conditional_decision")
    if t.event == LifecycleEvent.REJECTION:
        if t.target != LifecycleState.REJECTED or t.decision != DecisionOutcome.REJECTED:
            raise ContractError("rejection_requires_rejected_outcome")
    if t.event == LifecycleEvent.OWNERSHIP_TRANSFER:
        if t.ownership is None:
            raise ContractError("ownership_transfer_contract_required")
        t.ownership.validate()
        if t.target is not None:
            raise ContractError("ownership_transfer_is_not_a_lifecycle_transition")
    if t.event in {LifecycleEvent.TRIAL, LifecycleEvent.REALITY_VALIDATION, LifecycleEvent.OPERATIONALIZATION, LifecycleEvent.PRODUCTION}:
        if not t.evidence.sufficient:
            raise ContractError("reality_transition_requires_sufficient_evidence")
        if t.authority is None or not t.authority.authorized:
            raise ContractError("reality_transition_requires_authority")
    if t.event in {LifecycleEvent.OBSERVATION, LifecycleEvent.STABILIZATION, LifecycleEvent.BASELINE}:
        if t.phase is None or t.phase.value != t.event.value:
            raise ContractError("reality_phase_event_mismatch")
    if t.event == LifecycleEvent.CLOSURE:
        if t.current != LifecycleState.PRODUCTION or t.target != LifecycleState.CLOSED:
            raise ContractError("closure_requires_production")
        if not t.evidence.sufficient or t.authority is None or not t.authority.authorized:
            raise ContractError("closure_requires_evidence_and_authority")


def validate_batch(transitions: Iterable[RealityTransition]) -> None:
    for transition in transitions:
        validate_transition(transition)
