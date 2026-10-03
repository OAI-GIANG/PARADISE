"""Canonical task-intent and submission contracts for LOVE.

TaskContract owns immutable intent only. Submission represents one submitted
instance of that intent. Neither contract owns governance authority or runtime
execution state; DurableExecution owns execution state and persistence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping
from types import MappingProxyType


class TaskContractError(ValueError):
    pass


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class TaskContract:
    """Immutable task intent; no submission lifecycle or execution state."""

    goal: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def validate(self) -> "TaskContract":
        if not self.goal.strip():
            raise TaskContractError("goal_required")
        return self

    def submit(
        self,
        *,
        submission_id: str,
        idempotency_key: str,
        idempotency_scope: str = "TASK_SUBMISSION",
        delay_s: int = 0,
        execution_mode: str = "ASYNC",
        metadata: Mapping[str, Any] | None = None,
    ) -> "Submission":
        self.validate()
        return Submission(
            submission_id=submission_id,
            goal=self.goal,
            idempotency_key=idempotency_key,
            idempotency_scope=idempotency_scope,
            delay_s=delay_s,
            execution_mode=execution_mode,
            metadata={**self.metadata, **dict(metadata or {})},
        ).validate()


@dataclass(frozen=True)
class Submission:
    """Immutable submitted work item; no authorization or execution state."""

    submission_id: str
    goal: str
    idempotency_key: str
    idempotency_scope: str = "TASK_SUBMISSION"
    delay_s: int = 0
    execution_mode: str = "ASYNC"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def validate(self) -> "Submission":
        if not self.submission_id.strip():
            raise TaskContractError("submission_id_required")
        if not self.goal.strip():
            raise TaskContractError("goal_required")
        if not self.idempotency_key.strip():
            raise TaskContractError("idempotency_key_required")
        if self.delay_s < 0:
            raise TaskContractError("delay_s_must_be_nonnegative")
        if self.execution_mode not in {"SYNC", "ASYNC"}:
            raise TaskContractError("invalid_execution_mode")
        return self

    @property
    def task_id(self) -> str:
        return self.submission_id

    @property
    def digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": "LOVE-SUBMISSION-1.0",
            "id": self.submission_id,
            "goal": self.goal,
            "idempotency_key": self.idempotency_key,
            "idempotency_scope": self.idempotency_scope,
            "delay_s": self.delay_s,
            "execution_mode": self.execution_mode,
            "metadata": dict(self.metadata),
        }
