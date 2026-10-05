"""Canonical LOVE↔PARADISE production intelligence contracts."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

@dataclass(frozen=True)
class ModelIdentity:
    provider_id: str
    model_id: str
    model_revision: str = "unknown"
    capability_profile: tuple[str, ...] = ()
    modality_profile: tuple[str, ...] = ("text",)
    context_limit: int = 0
    pricing_reference: str = "unknown"
    identity_source: str = "configuration"
    identity_digest: str = ""

@dataclass(frozen=True)
class ModelContext:
    system_context: tuple[str, ...] = ()
    conversation_context: tuple[str, ...] = ()
    task_context: tuple[str, ...] = ()
    memory_context: tuple[str, ...] = ()
    evidence_context: tuple[str, ...] = ()
    learning_context: tuple[str, ...] = ()
    policy_context: tuple[str, ...] = ()
    token_budget: int = 0
    context_digest: str = ""
    provenance: tuple[str, ...] = ()

@dataclass(frozen=True)
class GenerationPolicy:
    temperature: float = 0.0
    max_output_tokens: int = 1024
    timeout_seconds: float = 30.0

@dataclass(frozen=True)
class BudgetPolicy:
    max_request_cost: float = 0.0
    currency: str = "USD"
    allow_fallback: bool = True

@dataclass(frozen=True)
class ModelRequest:
    task_id: str
    provider: str
    model: str
    operation: str
    payload: Mapping[str, Any]
    request_id: str = ""
    execution_id: str = ""
    context: ModelContext = field(default_factory=ModelContext)
    generation: GenerationPolicy = field(default_factory=GenerationPolicy)
    budget: BudgetPolicy = field(default_factory=BudgetPolicy)

@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    total_tokens: int = 0
    usage_source: str = "UNKNOWN"
    usage_verified: bool = False

@dataclass(frozen=True)
class CostRecord:
    request_id: str
    provider_id: str
    model_id: str
    estimated_cost: float = 0.0
    actual_cost: float | None = None
    currency: str = "USD"
    pricing_reference: str = "unknown"
    pricing_version: str = "unknown"

@dataclass(frozen=True)
class ModelWitness:
    request_id: str
    execution_id: str
    provider_id: str
    model_id: str
    model_revision: str
    context_digest: str
    request_digest: str
    response_digest: str
    policy_digest: str
    usage_digest: str
    evidence_id: str = ""

@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str
    output: Mapping[str, Any]
    success: bool
    request_id: str = ""
    response_id: str = ""
    finish_reason: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostRecord | None = None
    witness: ModelWitness | None = None

@dataclass(frozen=True)
class ProviderFailure:
    code: str
    provider_id: str
    model_id: str
    request_id: str
    retryable: bool
    fallback_eligible: bool
    safe_to_expose: bool = True
    detail: str = ""

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
    authority: str = "none"

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
