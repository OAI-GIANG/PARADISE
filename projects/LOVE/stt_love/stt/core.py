from dataclasses import dataclass
from typing import Any, Iterable

from .capability_selector import CapabilitySelection, CapabilitySelector, TaskProfile

@dataclass(frozen=True)
class Goal:
    text: str

@dataclass(frozen=True)
class Intent:
    goal: Goal
    outcome: str

class STTCore:
    def __init__(self, provider_performance: Iterable[dict[str, Any]] | None = None):
        self.capabilities = CapabilitySelector(
            provider_performance=provider_performance
        )

    def normalize_goal(self, text: str) -> Intent:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            raise ValueError("goal must not be empty")
        return Intent(goal=Goal(cleaned), outcome=cleaned)

    def select_capability(
        self,
        intent: Intent,
        *,
        risk: str = "LOW",
        memory=None,
        constraints: Iterable[str] = (),
    ) -> CapabilitySelection:
        return self.capabilities.select(
            TaskProfile(intent.goal.text, risk=risk, constraints=tuple(constraints)),
            memory=memory,
        )

    def report(self, intent: Intent, result: dict) -> dict:
        return {
            "actor": "STT",
            "goal": intent.goal.text,
            "result": result,
        }
