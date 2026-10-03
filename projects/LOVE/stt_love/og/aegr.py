"""Adaptive Execution & Governance Router (AEGR).

AEGR selects the minimum execution/governance tier justified by task risk,
while enforcing hard gates for sensitive operations.  It is deliberately
policy-only: it decides routing and bounded controls, but does not execute
providers or promote verification state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ExecutionTier(str, Enum):
    L0_FAST = "L0_FAST"
    L1_CONTROLLED = "L1_CONTROLLED"
    L2_FULL_GOVERNANCE = "L2_FULL_GOVERNANCE"


class EvidenceLevel(str, Enum):
    NONE = "NONE"
    LIGHTWEIGHT = "LIGHTWEIGHT"
    FULL = "FULL"


class OutcomeDisposition(str, Enum):
    CONTINUE = "CONTINUE"
    CHANGE = "CHANGE"
    STOP = "STOP"


@dataclass(frozen=True)
class OutcomeEvidence:
    evidence_available: bool = False
    evidence_refs: tuple[str, ...] = ()
    objective_satisfied: bool = False
    progress_observed: bool = False
    learning_observed: bool = False
    capability_gap_identified: bool = False
    capability_creation_viable: bool = False
    experiment_ready: bool = False
    repeated_failure: bool = False
    goal_still_valid: bool = True
    viable_alternative: bool = False
    hard_gate_blocked: bool = False
    change_budget_exhausted: bool = False


@dataclass(frozen=True)
class OutcomeDecision:
    disposition: OutcomeDisposition
    reason: str
    next_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "disposition": self.disposition.value,
            "reason": self.reason,
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class PlanAssuranceFinding:
    finding_id: str
    severity: str
    category: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    impact: str = ""
    required_revision: str = ""
    verification_method: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanAssuranceResult:
    decision: str
    findings: tuple[PlanAssuranceFinding, ...]
    checks: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.decision not in {"PASS", "HOLD", "REAUTHORIZE", "REVIEW_ONLY"}:
            raise ValueError(f"unsupported plan assurance decision: {self.decision}")

    @property
    def passed(self) -> bool:
        return self.decision == "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "LOVE-PLAN-ASSURANCE-1.0",
            "decision": self.decision,
            "passed": self.passed,
            "checks": list(self.checks),
            "findings": [finding.as_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class ChangeBudget:
    max_files: int = 5
    max_loc: int = 100

    def validate(self) -> None:
        if self.max_files <= 0 or self.max_loc <= 0:
            raise ValueError("change budget bounds must be positive")


@dataclass(frozen=True)
class ExecutionRequest:
    objective: str
    mode: str = "read-only"
    code_change: bool = False
    runtime_change: bool = False
    broad_scope: bool = False
    security: bool = False
    production: bool = False
    canonical: bool = False
    governance: bool = False
    data_migration: bool = False
    execution_authority: bool = False
    self_healing: bool = False
    explicit_full_governance: bool = False
    change_files: int = 0
    change_loc: int = 0

    def validate(self) -> None:
        if not self.objective.strip():
            raise ValueError("objective is required")
        if self.mode not in {"read-only", "sandbox-write", "production-write"}:
            raise ValueError(f"unsupported execution mode: {self.mode}")
        if self.change_files < 0 or self.change_loc < 0:
            raise ValueError("change scope cannot be negative")


@dataclass(frozen=True)
class RouteDecision:
    tier: ExecutionTier
    risk_score: int
    factors: tuple[str, ...]
    hard_gates: tuple[str, ...]
    budget_exceeded: bool
    approval_required: bool
    evidence_level: EvidenceLevel
    required_steps: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    escalation_conditions: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tier"] = self.tier.value
        payload["evidence_level"] = self.evidence_level.value
        return payload


class AdaptiveExecutionGovernanceRouter:
    """Risk-aware router for STT/OG execution."""

    FACTOR_POINTS = {
        "mutating_action": 1,
        "code_change": 2,
        "runtime_change": 2,
        "broad_scope": 2,
        "security": 3,
        "production": 3,
        "canonical": 3,
        "governance": 3,
        "data_migration": 3,
        "execution_authority": 3,
        "self_healing": 3,
    }
    HARD_GATE_FIELDS = {
        "security": "SECURITY",
        "production": "PRODUCTION",
        "canonical": "CANONICAL_STATE",
        "governance": "GOVERNANCE",
        "data_migration": "DATA_MIGRATION",
        "execution_authority": "EXECUTION_AUTHORITY",
        "self_healing": "SELF_HEALING",
    }
    STEPS = {
        ExecutionTier.L0_FAST: ("intent", "answer_or_action"),
        ExecutionTier.L1_CONTROLLED: ("preflight", "execute", "test", "result"),
        ExecutionTier.L2_FULL_GOVERNANCE: (
            "finding", "root_cause", "plan", "authorization", "implement",
            "regression", "negative_test", "evidence", "checkpoint", "result",
        ),
    }
    EVIDENCE = {
        ExecutionTier.L0_FAST: EvidenceLevel.NONE,
        ExecutionTier.L1_CONTROLLED: EvidenceLevel.LIGHTWEIGHT,
        ExecutionTier.L2_FULL_GOVERNANCE: EvidenceLevel.FULL,
    }

    def __init__(self, change_budget: ChangeBudget | None = None) -> None:
        self.change_budget = change_budget or ChangeBudget()
        self.change_budget.validate()

    def route(self, request: ExecutionRequest) -> RouteDecision:
        request.validate()
        score = 0
        factors: list[str] = []
        hard_gates: list[str] = []

        if request.mode != "read-only":
            score += self.FACTOR_POINTS["mutating_action"]
            factors.append("mutating_action")

        for field, label in (
            ("code_change", "code_change"),
            ("runtime_change", "runtime_change"),
            ("broad_scope", "broad_scope"),
            ("security", "security"),
            ("production", "production"),
            ("canonical", "canonical"),
            ("governance", "governance"),
            ("data_migration", "data_migration"),
            ("execution_authority", "execution_authority"),
            ("self_healing", "self_healing"),
        ):
            if getattr(request, field):
                score += self.FACTOR_POINTS[label]
                factors.append(label)

        for field, gate in self.HARD_GATE_FIELDS.items():
            if getattr(request, field):
                hard_gates.append(gate)

        if request.mode == "production-write" and "PRODUCTION" not in hard_gates:
            hard_gates.append("PRODUCTION")
            if "production" not in factors:
                score += self.FACTOR_POINTS["production"]
                factors.append("production")

        budget_exceeded = (
            request.change_files > self.change_budget.max_files
            or request.change_loc > self.change_budget.max_loc
        )
        if budget_exceeded:
            factors.append("change_budget_exceeded")

        if request.explicit_full_governance:
            factors.append("explicit_full_governance")

        if hard_gates or budget_exceeded or request.explicit_full_governance or score >= 6:
            tier = ExecutionTier.L2_FULL_GOVERNANCE
        elif (
            request.mode != "read-only"
            or request.code_change
            or request.runtime_change
            or request.broad_scope
            or score >= 3
        ):
            tier = ExecutionTier.L1_CONTROLLED
        else:
            tier = ExecutionTier.L0_FAST

        reason_parts = [f"risk_score={score}"]
        if hard_gates:
            reason_parts.append("hard_gate=" + ",".join(hard_gates))
        if budget_exceeded:
            reason_parts.append("change_budget_exceeded")
        if request.explicit_full_governance:
            reason_parts.append("explicit_full_governance")

        return RouteDecision(
            tier=tier,
            risk_score=score,
            factors=tuple(factors),
            hard_gates=tuple(hard_gates),
            budget_exceeded=budget_exceeded,
            approval_required=tier is ExecutionTier.L2_FULL_GOVERNANCE,
            evidence_level=self.EVIDENCE[tier],
            required_steps=self.STEPS[tier],
            stop_conditions=self._stop_conditions(tier, budget_exceeded),
            escalation_conditions=self._escalation_conditions(tier),
            reason="; ".join(reason_parts),
        )

    def assure_plan(
        self,
        *,
        request: ExecutionRequest,
        decision: RouteDecision,
        planned_commands: tuple[str, ...] | list[str],
        declared_dependencies: dict[str, tuple[str, ...] | list[str]] | None,
        governance: Any,
        graph: Any,
        assumptions: tuple[str, ...] | list[str] = (),
    ) -> PlanAssuranceResult:
        """Run the minimum pre-EXECUTE assurance review inside AEGR.

        This remains policy-only: it does not execute, mutate, authorize
        promotion, or create a second governance authority.
        """
        findings: list[PlanAssuranceFinding] = []
        checks = (
            "assumption",
            "dependency",
            "risk",
            "failure_mode",
            "governance",
            "evidence",
            "recovery",
        )

        def add(
            category: str,
            *,
            severity: str,
            statement: str,
            impact: str,
            required_revision: str,
            verification_method: str,
            evidence_refs: tuple[str, ...] = (),
        ) -> None:
            findings.append(
                PlanAssuranceFinding(
                    finding_id=f"PLAN-{category.upper()}-{len(findings) + 1:02d}",
                    severity=severity,
                    category=category,
                    statement=statement,
                    evidence_refs=evidence_refs,
                    impact=impact,
                    required_revision=required_revision,
                    verification_method=verification_method,
                )
            )

        # 1. Assumption review.
        for assumption in assumptions:
            text = str(assumption).strip()
            if "unknown" in text.lower():
                add(
                    "assumption",
                    severity="HIGH",
                    statement=f"material assumption is unresolved: {text}",
                    impact="execution may proceed on an unsupported assumption",
                    required_revision="resolve the assumption or explicitly reframe the plan",
                    verification_method="provide OBSERVED/DECLARED state with supporting evidence",
                )

        # 2. Dependency review.
        commands = {str(command).strip().lower() for command in planned_commands if str(command).strip()}
        dependencies = declared_dependencies or {}
        for command, prereqs in dependencies.items():
            normalized_command = str(command).strip().lower()
            if normalized_command not in commands:
                continue
            missing = tuple(
                str(dep).strip().lower()
                for dep in prereqs
                if str(dep).strip().lower() not in commands
            )
            if missing:
                add(
                    "dependency",
                    severity="HIGH",
                    statement=(
                        f"planned command {normalized_command} omits declared prerequisites: "
                        + ", ".join(missing)
                    ),
                    impact="execution order and required capability coverage are incomplete",
                    required_revision="include all material prerequisites in the executable plan or remove the declaration with evidence",
                    verification_method="rebuild and revalidate the execution graph",
                )

        # 3. Risk review.
        task_risk = str(getattr(governance, "risk", "LOW"))
        if decision.tier is ExecutionTier.L2_FULL_GOVERNANCE and task_risk not in {"HIGH", "CRITICAL"}:
            add(
                "risk",
                severity="HIGH",
                statement="task risk is lower than the AEGR governance tier requires",
                impact="the plan understates material execution risk",
                required_revision="recompute task risk from actual plan effects and align it with AEGR",
                verification_method="re-route the revised task through AEGR",
            )
        if decision.tier is ExecutionTier.L0_FAST and task_risk in {"HIGH", "CRITICAL"}:
            add(
                "risk",
                severity="HIGH",
                statement="task risk is higher than the AEGR tier permits",
                impact="the plan may bypass required governance",
                required_revision="escalate the route and re-authorize the plan",
                verification_method="re-run AEGR with the corrected risk context",
            )

        # 4. Failure-mode review.
        failure_criteria = tuple(getattr(governance, "failure_criteria", ()) or ())
        if not failure_criteria:
            add(
                "failure_mode",
                severity="HIGH",
                statement="plan has no explicit failure criteria",
                impact="failure may not stop the execution lifecycle deterministically",
                required_revision="declare observable failure criteria",
                verification_method="rebuild the task contract and verify failure transitions",
            )
        if not decision.stop_conditions:
            add(
                "failure_mode",
                severity="HIGH",
                statement="plan has no governance stop conditions",
                impact="timeout/scope/verification failures have no enforced stop boundary",
                required_revision="recompute AEGR stop conditions",
                verification_method="assert required stop conditions are present",
            )

        # 5. Governance review.
        authority = str(getattr(governance, "authority", "")).strip()
        permissions = tuple(getattr(governance, "permissions", ()) or ())
        kill_switch = bool(getattr(governance, "kill_switch", False))
        if not authority:
            add(
                "governance",
                severity="HIGH",
                statement="plan has no execution authority",
                impact="execution ownership is undefined",
                required_revision="bind an explicit execution authority",
                verification_method="revalidate GovernanceSpec authority",
            )
        if not permissions:
            add(
                "governance",
                severity="HIGH",
                statement="plan declares no permissions",
                impact="execution scope cannot be bounded",
                required_revision="declare the minimum required permissions",
                verification_method="revalidate GovernanceSpec permissions",
            )
        if not kill_switch:
            add(
                "governance",
                severity="CRITICAL",
                statement="kill switch is disabled",
                impact="the plan is not safely interruptible",
                required_revision="restore the mandatory kill switch",
                verification_method="GovernanceSpec validation must reject disabled kill switch",
            )
        if decision.budget_exceeded:
            add(
                "governance",
                severity="HIGH",
                statement="change budget is already exceeded",
                impact="plan scope exceeds the existing execution budget",
                required_revision="reduce scope or obtain explicit scope change authorization",
                verification_method="re-run AEGR after budget correction",
            )

        # 6. Evidence review.
        success_criteria = tuple(getattr(governance, "success_criteria", ()) or ())
        evidence_requirements = tuple(getattr(governance, "evidence_requirements", ()) or ())
        if not success_criteria:
            add(
                "evidence",
                severity="HIGH",
                statement="plan has no observable success criteria",
                impact="execution cannot be conclusively evaluated",
                required_revision="declare observable success criteria",
                verification_method="revalidate GovernanceSpec success_criteria",
            )
        if decision.evidence_level is not EvidenceLevel.NONE and not evidence_requirements:
            add(
                "evidence",
                severity="HIGH",
                statement="governed plan has no evidence requirements",
                impact="required execution/verification proof cannot be collected",
                required_revision="declare evidence and independent verification requirements",
                verification_method="revalidate GovernanceSpec evidence_requirements",
            )

        # 7. Recovery review.
        retry_max = int(getattr(governance, "retry_max", 0) or 0)
        if retry_max < 0 or retry_max > 5:
            add(
                "recovery",
                severity="HIGH",
                statement="retry budget is outside the bounded range",
                impact="recovery could exceed the governed retry envelope",
                required_revision="set retry_max within the bounded range",
                verification_method="GovernanceSpec validation",
            )
        if not kill_switch:
            # Governance finding above is the authoritative failure; this keeps
            # the recovery review explicit without adding another authority.
            pass
        if getattr(governance, "mode", "read-only") != "read-only" and retry_max != 0:
            add(
                "recovery",
                severity="HIGH",
                statement="mutation plan permits automatic retries",
                impact="a failed mutation could repeat without a fresh review",
                required_revision="set retry_max=0 for mutation tasks",
                verification_method="GovernanceSpec mutation retry constraint",
            )

        # Graph validity is part of the existing dependency/recovery boundary.
        try:
            graph.validate()
        except Exception as exc:
            add(
                "dependency",
                severity="HIGH",
                statement=f"execution graph validation failed: {exc}",
                impact="execution order cannot be trusted",
                required_revision="repair the graph before authorization",
                verification_method="ExecutionGraph.validate()",
            )

        if findings:
            decision_name = "HOLD"
        elif decision.hard_gates or decision.approval_required:
            decision_name = "REAUTHORIZE"
        else:
            decision_name = "PASS"

        return PlanAssuranceResult(
            decision=decision_name,
            findings=tuple(findings),
            checks=checks,
        )

    def reassess(
        self,
        request: ExecutionRequest,
        *,
        additional: ExecutionRequest | None = None,
    ) -> RouteDecision:
        if additional is None:
            return self.route(request)
        return self.route(self._merge_requests(request, additional))

    @staticmethod
    def decide_outcome(evidence: OutcomeEvidence) -> OutcomeDecision:
        """Convert observed outcome evidence into the next loop disposition.

        This is policy-only. It does not infer evidence from executor status and
        does not execute a change. Missing evidence stops the current loop so
        OG cannot continue or mutate on an unsupported assumption.
        """
        if not evidence.evidence_available:
            return OutcomeDecision(
                OutcomeDisposition.STOP,
                "EVIDENCE_MISSING",
                "collect_or_request_evidence",
            )
        if not evidence.evidence_refs:
            return OutcomeDecision(
                OutcomeDisposition.STOP,
                "EVIDENCE_UNIDENTIFIED",
                "identify_or_record_evidence",
            )
        if evidence.objective_satisfied:
            return OutcomeDecision(
                OutcomeDisposition.STOP,
                "OBJECTIVE_SATISFIED",
                "close_task",
            )
        if not evidence.goal_still_valid:
            return OutcomeDecision(
                OutcomeDisposition.STOP,
                "GOAL_NO_LONGER_VALID",
                "close_or_reframe_task",
            )
        if evidence.hard_gate_blocked:
            return OutcomeDecision(
                OutcomeDisposition.STOP,
                "HARD_GATE_BLOCKED",
                "request_authorization_or_close_task",
            )
        if evidence.change_budget_exhausted:
            return OutcomeDecision(
                OutcomeDisposition.STOP,
                "CHANGE_BUDGET_EXHAUSTED",
                "authorize_scope_change_or_close_task",
            )
        if evidence.repeated_failure:
            if (
                evidence.capability_gap_identified
                and evidence.capability_creation_viable
                and evidence.experiment_ready
            ):
                return OutcomeDecision(
                    OutcomeDisposition.CHANGE,
                    "CAPABILITY_GAP_WITH_EXPERIMENT_READY",
                    "prototype_new_capability",
                )
            if evidence.viable_alternative:
                return OutcomeDecision(
                    OutcomeDisposition.CHANGE,
                    "REPEATED_FAILURE_WITH_ALTERNATIVE",
                    "replan_and_reassess",
                )
            return OutcomeDecision(
                OutcomeDisposition.STOP,
                "REPEATED_FAILURE_NO_ALTERNATIVE",
                "close_or_escalate",
            )
        if evidence.progress_observed:
            next_action = (
                "integrate_learning_and_continue"
                if evidence.learning_observed
                else "continue_current_plan"
            )
            return OutcomeDecision(
                OutcomeDisposition.CONTINUE,
                "PROGRESS_SUPPORTED_BY_EVIDENCE",
                next_action,
            )
        if (
            evidence.capability_gap_identified
            and evidence.capability_creation_viable
            and evidence.experiment_ready
        ):
            return OutcomeDecision(
                OutcomeDisposition.CHANGE,
                "CAPABILITY_GAP_WITH_EXPERIMENT_READY",
                "prototype_new_capability",
            )
        if evidence.viable_alternative:
            return OutcomeDecision(
                OutcomeDisposition.CHANGE,
                "NO_PROGRESS_WITH_ALTERNATIVE",
                "replan_and_reassess",
            )
        return OutcomeDecision(
            OutcomeDisposition.STOP,
            "NO_PROGRESS_NO_ALTERNATIVE",
            "close_or_request_human_direction",
        )

    @staticmethod
    def _merge_requests(base: ExecutionRequest, extra: ExecutionRequest) -> ExecutionRequest:
        objective = (
            f"{base.objective}; {extra.objective}"
            if extra.objective and extra.objective != base.objective
            else base.objective
        )
        fields = (
            "code_change", "runtime_change", "broad_scope", "security",
            "production", "canonical", "governance", "data_migration",
            "execution_authority", "self_healing", "explicit_full_governance",
        )
        kwargs = {field: getattr(base, field) or getattr(extra, field) for field in fields}
        mode = (
            "production-write"
            if "production-write" in {base.mode, extra.mode}
            else ("sandbox-write" if "sandbox-write" in {base.mode, extra.mode} else "read-only")
        )
        return ExecutionRequest(
            objective=objective,
            mode=mode,
            change_files=max(base.change_files, extra.change_files),
            change_loc=max(base.change_loc, extra.change_loc),
            **kwargs,
        )

    @staticmethod
    def _stop_conditions(tier: ExecutionTier, budget_exceeded: bool) -> tuple[str, ...]:
        base = ("success_condition_satisfied", "scope_exceeded", "timeout_or_kill_switch")
        if budget_exceeded:
            return ("change_budget_exceeded",) + base
        if tier is ExecutionTier.L2_FULL_GOVERNANCE:
            return base + ("verification_evidence_satisfied", "checkpoint_recorded")
        if tier is ExecutionTier.L1_CONTROLLED:
            return base + ("tests_passed",)
        return base

    @staticmethod
    def _escalation_conditions(tier: ExecutionTier) -> tuple[str, ...]:
        if tier is ExecutionTier.L2_FULL_GOVERNANCE:
            return ()
        return (
            "new_security_or_production_impact",
            "canonical_or_governance_impact",
            "scope_or_change_budget_growth",
            "execution_authority_expanded",
            "repeated_failure",
        )

    @staticmethod
    def can_fast_exit(
        decision: RouteDecision,
        *,
        success: bool,
        tests_passed: bool = False,
        broader_impact: bool = False,
        evidence_complete: bool = False,
        checkpoint_recorded: bool = False,
    ) -> bool:
        if not success or broader_impact or decision.budget_exceeded:
            return False
        if decision.tier is ExecutionTier.L0_FAST:
            return True
        if decision.tier is ExecutionTier.L1_CONTROLLED:
            return tests_passed
        return evidence_complete and checkpoint_recorded
