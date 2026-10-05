"""Canonical LOVE↔PARADISE integration contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class CognitiveRequest:
    task_id: str
    operation: str
    payload: Mapping[str, Any]
    commit: str
    tree: str
    environment: str

@dataclass(frozen=True)
class CognitiveAdvice:
    task_id: str
    recommendation: str
    memory_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    model_memory_ids: tuple[str, ...] = ()
    model_memory_context: tuple[Mapping[str, Any], ...] = ()
    authority: str = "none"

@dataclass(frozen=True)
class ModelRequest:
    task_id: str
    provider: str
    model: str
    operation: str
    payload: Mapping[str, Any]

@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str
    output: Mapping[str, Any]
    success: bool

@dataclass(frozen=True)
class EvidenceEnvelope:
    evidence_id: str
    task_id: str
    event_type: str
    claim: str
    source: str
    provenance: str
    integrity: str
    verification_status: str

@dataclass(frozen=True)
class ReplayEnvelope:
    replay_id: str
    task_id: str
    sequence: int
    event_type: str
    payload: Mapping[str, Any]
    previous_digest: str
    record_digest: str
