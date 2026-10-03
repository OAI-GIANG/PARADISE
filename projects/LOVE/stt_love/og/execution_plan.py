"""Canonical governed execution plan boundary for LOVE.

The contract deliberately separates:
- Submission: immutable user/work submission data;
- GovernanceSpec: immutable authorization/risk/constraint inputs;
- GovernedExecutionPlan: the approved plan joining those two domains;
- ExecutionState: runtime-owned and never stored here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping
from types import MappingProxyType

from .aegr import PlanAssuranceResult, RouteDecision
from .command_router import Route
from .execution_graph import ExecutionGraph
from ..task_contract import Submission


MODES = {"read-only", "workspace-write", "side-effecting"}
RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class GovernanceSpec:
    """Immutable governance inputs; it owns no execution lifecycle state."""

    plan_id: str
    intent: str
    task_type: str
    provider: str
    agent: str
    execution_target: str
    cwd: str | None
    permissions: tuple[str, ...]
    timeout_s: int
    retry_max: int
    confirmation_required: bool
    evidence_requirements: tuple[str, ...]
    mode: str
    parent_task_id: str | None = None
    context: Mapping[str, Any] | None = None
    constraints: tuple[str, ...] = ()
    risk: str = "LOW"
    authority: str = ""
    source_commit: str = ""
    target_branch: str = ""
    allowed_paths: tuple[str, ...] = ()
    success_criteria: tuple[str, ...] = ()
    failure_criteria: tuple[str, ...] = ()
    repair_policy: tuple[str, ...] = ()
    kill_switch: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context or {})))
        if not self.plan_id.strip():
            raise ValueError("plan_id is required")
        if not self.intent.strip():
            raise ValueError("intent is required")
        if self.mode not in MODES:
            raise ValueError("unsupported task mode")
        if self.risk not in RISK_LEVELS:
            raise ValueError("unsupported task risk")
        if not self.authority.strip():
            raise ValueError("authority is required")
        if not self.kill_switch:
            raise ValueError("kill_switch must remain enabled")
        if not 1 <= self.timeout_s <= 900:
            raise ValueError("timeout_s must be 1..900")
        if not 0 <= self.retry_max <= 5:
            raise ValueError("retry_max must be 0..5")
        if self.mode != "read-only" and self.retry_max != 0:
            raise ValueError("mutation tasks cannot retry automatically")

    @classmethod
    def from_submission(
        cls,
        submission: Submission,
        *,
        provider: str,
        agent: str,
        execution_target: str,
        mode: str,
        risk: str,
        permissions: tuple[str, ...],
        evidence_requirements: tuple[str, ...],
        success_criteria: tuple[str, ...],
        failure_criteria: tuple[str, ...],
        repair_policy: tuple[str, ...],
        timeout_s: int = 300,
        retry_max: int = 0,
        authority: str = "OG",
        task_type: str = "general",
        cwd: str | None = None,
        confirmation_required: bool = False,
        parent_task_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        constraints: tuple[str, ...] = (),
        source_commit: str = "",
        target_branch: str = "",
        allowed_paths: tuple[str, ...] = (),
        kill_switch: bool = True,
    ) -> "GovernanceSpec":
        return cls(
            plan_id=submission.submission_id,
            intent=submission.goal,
            task_type=task_type,
            provider=provider,
            agent=agent,
            execution_target=execution_target,
            cwd=cwd,
            permissions=permissions,
            timeout_s=timeout_s,
            retry_max=retry_max,
            confirmation_required=confirmation_required,
            evidence_requirements=evidence_requirements,
            mode=mode,
            parent_task_id=parent_task_id,
            context=context,
            constraints=constraints,
            risk=risk,
            authority=authority,
            source_commit=source_commit,
            target_branch=target_branch,
            allowed_paths=allowed_paths,
            success_criteria=success_criteria,
            failure_criteria=failure_criteria,
            repair_policy=repair_policy,
            kill_switch=kill_switch,
        )

    @property
    def digest(self) -> str:
        return _digest(self.to_dict(public=False))

    def to_dict(self, public: bool = True) -> dict[str, Any]:
        return {
            "schema_version": "LOVE-GOVERNANCE-SPEC-1.0",
            "plan_id": self.plan_id,
            "intent": self.intent,
            "task_type": self.task_type,
            "provider": self.provider,
            "agent": self.agent,
            "execution_target": self.execution_target,
            "cwd": self.cwd,
            "permissions": list(self.permissions),
            "timeout_s": self.timeout_s,
            "retry_max": self.retry_max,
            "confirmation_required": self.confirmation_required,
            "evidence_requirements": list(self.evidence_requirements),
            "mode": self.mode,
            "parent_task_id": self.parent_task_id,
            "context": dict(self.context or {}),
            "constraints": list(self.constraints),
            "risk": self.risk,
            "authority": self.authority,
            "source_commit": self.source_commit,
            "target_branch": self.target_branch,
            "allowed_paths": list(self.allowed_paths),
            "success_criteria": list(self.success_criteria),
            "failure_criteria": list(self.failure_criteria),
            "repair_policy": list(self.repair_policy),
            "kill_switch": self.kill_switch,
        }


@dataclass(frozen=True)
class Step:
    name: str
    command: str
    route: Route


@dataclass(frozen=True)
class GovernedExecutionPlan:
    """Immutable plan; execution state is deliberately absent."""

    submission: Submission
    steps: tuple[Step, ...]
    capability: str
    governance: RouteDecision
    governance_spec: GovernanceSpec
    graph: ExecutionGraph
    assurance: PlanAssuranceResult

    @property
    def goal(self) -> str:
        return self.submission.goal

    @property
    def digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "LOVE-GOVERNED-EXECUTION-PLAN-1.0",
            "submission": self.submission.to_dict(),
            "steps": [
                {"name": step.name, "command": step.command, "route": asdict(step.route)}
                for step in self.steps
            ],
            "capability": self.capability,
            "governance": self.governance.as_dict(),
            "governance_spec": self.governance_spec.to_dict(public=False),
            "graph": self.graph.to_dict(),
            "assurance": self.assurance.as_dict(),
        }
