"""Policy-only context-aware capability adaptation for OG."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

class FactState(str, Enum):
    OBSERVED = "OBSERVED"
    DECLARED = "DECLARED"
    UNKNOWN = "UNKNOWN"

class AdaptationStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"

@dataclass(frozen=True)
class ExecutionContext:
    platform: str | None = None
    device: str | None = None
    runtime: str | None = None
    network: str | None = None
    permissions: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    facts_state: FactState = FactState.UNKNOWN

    def missing_core(self) -> tuple[str, ...]:
        return tuple(k for k, v in {
            "platform": self.platform, "runtime": self.runtime,
            "network": self.network,
        }.items() if not v)

@dataclass(frozen=True)
class CapabilityRequirement:
    capability: str
    tools: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    networks: tuple[str, ...] = ()

@dataclass(frozen=True)
class SubstrateCandidate:
    name: str
    platforms: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()
    networks: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    available: bool = True

@dataclass(frozen=True)
class AdaptationDecision:
    status: AdaptationStatus
    selected_substrate: str | None
    capability: str
    score: int
    reasons: tuple[str, ...]
    missing: tuple[str, ...]
    verification_gaps: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {"status": self.status.value,
                "selected_substrate": self.selected_substrate,
                "capability": self.capability, "score": self.score,
                "reasons": self.reasons, "missing": self.missing,
                "verification_gaps": self.verification_gaps}

def _has(have: Iterable[str], need: Iterable[str]) -> bool:
    return set(need).issubset(set(have))

def adapt(context: ExecutionContext, requirement: CapabilityRequirement,
          candidates: Iterable[SubstrateCandidate]) -> AdaptationDecision:
    if context.facts_state is FactState.UNKNOWN:
        return AdaptationDecision(AdaptationStatus.INSUFFICIENT_CONTEXT, None,
            requirement.capability, 0, ("context_facts_unknown",),
            context.missing_core(), requirement.verification)
    missing_core = context.missing_core()
    if missing_core:
        return AdaptationDecision(AdaptationStatus.INSUFFICIENT_CONTEXT, None,
            requirement.capability, 0, ("required_context_missing",),
            missing_core, requirement.verification)
    ranked = []
    for c in candidates:
        if not c.available:
            continue
        missing = []
        if c.platforms and context.platform not in c.platforms: missing.append("platform")
        if c.runtimes and context.runtime not in c.runtimes: missing.append("runtime")
        if c.networks and context.network not in c.networks: missing.append("network")
        if requirement.platforms and context.platform not in requirement.platforms: missing.append("requirement_platform")
        if requirement.networks and context.network not in requirement.networks: missing.append("requirement_network")
        if not _has(c.tools, requirement.tools): missing.append("tools")
        if not _has(context.permissions, requirement.permissions): missing.append("permissions")
        if missing: continue
        score = (bool(c.platforms) + bool(c.runtimes) + bool(c.networks)
                 + len(requirement.tools) + len(requirement.permissions))
        gaps = tuple(x for x in requirement.verification
                     if x not in c.verification or x not in context.verification)
        ranked.append((score, c.name, gaps))
    if not ranked:
        return AdaptationDecision(AdaptationStatus.BLOCKED, None,
            requirement.capability, 0, ("no_compatible_substrate",),
            ("substrate_compatibility",), requirement.verification)
    ranked.sort(key=lambda x: (-x[0], x[1]))
    score, name, gaps = ranked[0]
    status = AdaptationStatus.BLOCKED if gaps else AdaptationStatus.READY
    reasons = ("verification_gap",) if gaps else ("context_fit",)
    return AdaptationDecision(status, name, requirement.capability, score,
        reasons, (), gaps)
