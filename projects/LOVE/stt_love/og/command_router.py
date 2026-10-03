"""OG Command & Capability Router V1 integrated with the canonical registry."""
from dataclasses import dataclass
import re
from typing import Iterable, Mapping, Any
from .aegr import (
    AdaptiveExecutionGovernanceRouter,
    ExecutionRequest,
    OutcomeDecision,
    OutcomeEvidence,
    RouteDecision,
)
from .capability_registry import CapabilityRegistry

DEPENDENCIES = {
    "factcheck": ["/research"],
    "verify": ["/research"],
    "decision": ["/compare"],
    "strategy": ["/research", "/analyst"],
    "roadmap": ["/strategy"],
    "action": ["/roadmap"],
    "rootcause": ["/analyst"],
    "debug": ["/rootcause"],
}

@dataclass(frozen=True)
class Route:
    command: str
    capability: str
    provider: str
    prerequisites: tuple[str, ...]

class CommandRouter:
    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        governance_router: AdaptiveExecutionGovernanceRouter | None = None,
    ) -> None:
        self.registry = registry or CapabilityRegistry()
        self.governance_router = governance_router or AdaptiveExecutionGovernanceRouter()

    def normalize(self, value: str) -> str:
        value = value.strip().lower()
        if not value.startswith("/"):
            value = "/" + value
        return re.sub(r"[^a-z0-9_/+-]", "", value)

    def route(self, command: str) -> Route:
        normalized = self.normalize(command)
        try:
            capability = self.registry.capability_for(normalized)
        except KeyError as exc:
            raise ValueError(f"Unknown OG command: {normalized}") from exc
        key = normalized.lstrip("/")
        prerequisites = tuple(DEPENDENCIES.get(key, ()))
        return Route(normalized, capability.name, capability.provider, prerequisites)

    def governed_route(
        self,
        command: str,
        *,
        objective: str | None = None,
        mode: str = "read-only",
        risk_context: Mapping[str, Any] | None = None,
    ) -> tuple[Route, RouteDecision]:
        route = self.route(command)
        context = dict(risk_context or {})
        request = ExecutionRequest(
            objective=objective.strip() if objective else route.command,
            mode=mode,
            **context,
        )
        return route, self.governance_router.route(request)

    def decide_outcome(self, evidence: OutcomeEvidence) -> OutcomeDecision:
        """Expose AEGR's evidence-driven loop disposition at the command boundary."""
        return self.governance_router.decide_outcome(evidence)

    def build_plan(self, commands: Iterable[str]) -> list[Route]:
        seen: set[str] = set()
        ordered: list[Route] = []
        def add(route: Route) -> None:
            for prerequisite in route.prerequisites:
                add(self.route(prerequisite))
            if route.command not in seen:
                seen.add(route.command)
                ordered.append(route)
        for command in commands:
            add(self.route(command))
        return ordered

def normalize_command(value: str) -> str:
    return CommandRouter().normalize(value)

def route_command(command: str) -> Route:
    return CommandRouter().route(command)

def build_plan(commands: Iterable[str]) -> list[Route]:
    return CommandRouter().build_plan(commands)
