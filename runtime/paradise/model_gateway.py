"""Canonical model/provider boundary.

The default adapter is deterministic and local. External providers can be
added behind this interface without becoming state or policy owners.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .contracts import ModelRequest, ModelResult

@dataclass(frozen=True)
class ProviderAdapter:
    provider_id: str
    model_id: str

    def invoke(self, request: ModelRequest) -> ModelResult:
        if request.operation != "echo":
            raise ValueError("provider adapter supports only bounded echo")
        message = request.payload.get("message")
        if not isinstance(message, str):
            raise ValueError("model payload.message must be a string")
        if len(message) > 10000:
            raise ValueError("model payload.message exceeds 10000 characters")
        return ModelResult(
            provider=self.provider_id,
            model=self.model_id,
            output={"echo": message, "task_id": request.task_id},
            success=True,
        )

class ModelGateway:
    """Single execution boundary for model/provider calls."""
    def __init__(self, adapter: ProviderAdapter | None = None):
        self.adapter = adapter or ProviderAdapter("local", "local.echo.v1")

    def invoke(self, request: ModelRequest) -> ModelResult:
        if request.provider != self.adapter.provider_id:
            raise ValueError("provider is not registered with the canonical gateway")
        if request.model != self.adapter.model_id:
            raise ValueError("model is not registered with the canonical gateway")
        return self.adapter.invoke(request)
