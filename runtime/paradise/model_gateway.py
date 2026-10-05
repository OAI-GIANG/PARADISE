"""Canonical model/provider execution boundary.

External providers are adapters only. Secrets are resolved at invocation time and
never enter requests, evidence, replay, logs, or persistent state.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from typing import Any, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from .contracts import (
    BudgetPolicy, CostRecord, GenerationPolicy, ModelContext, ModelIdentity,
    ModelRequest, ModelResult, ModelWitness, ProviderFailure, TokenUsage,
)

class ProviderError(RuntimeError):
    def __init__(self, failure: ProviderFailure):
        super().__init__(failure.code)
        self.failure = failure

class CredentialResolver(Protocol):
    def resolve(self, provider_id: str) -> str | None: ...

class EnvironmentCredentialResolver:
    """Reads provider credentials from environment only; never persists them."""
    def resolve(self, provider_id: str) -> str | None:
        name = f"PARADISE_{provider_id.upper()}_API_KEY"
        return os.getenv(name)

@dataclass(frozen=True)
class ProviderAdapter:
    provider_id: str
    model_id: str
    identity: ModelIdentity

    def invoke(self, request: ModelRequest) -> ModelResult:
        raise NotImplementedError

class LocalEchoAdapter(ProviderAdapter):
    def invoke(self, request: ModelRequest) -> ModelResult:
        if request.operation != "echo":
            raise ProviderError(ProviderFailure("INVALID_REQUEST", self.provider_id, self.model_id,
                                                request.request_id, False, False))
        message = request.payload.get("message")
        if not isinstance(message, str) or len(message) > 10000:
            raise ProviderError(ProviderFailure("INVALID_REQUEST", self.provider_id, self.model_id,
                                                request.request_id, False, False))
        usage = TokenUsage(len(message), len(message), 0, len(message) * 2, "ESTIMATED", False)
        cost = CostRecord(request.request_id, self.provider_id, self.model_id, 0.0, 0.0, "USD", "local", "1")
        return ModelResult(self.provider_id, self.model_id,
                           {"echo": message, "task_id": request.task_id}, True,
                           request.request_id, f"local-{request.request_id}", "stop", usage, cost)

class OpenAICompatibleAdapter(ProviderAdapter):
    def __init__(self, provider_id: str, model_id: str, base_url: str,
                 credentials: CredentialResolver | None = None):
        identity = ModelIdentity(provider_id, model_id, "configured", ("chat",), ("text",),
                                 int(os.getenv("PARADISE_CONTEXT_LIMIT", "0")),
                                 os.getenv("PARADISE_PRICING_REFERENCE", "unknown"), "provider-config")
        super().__init__(provider_id, model_id, identity)
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials or EnvironmentCredentialResolver()

    def _messages(self, request: ModelRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for text in request.context.system_context:
            messages.append({"role": "system", "content": text})
        for text in request.context.conversation_context:
            messages.append({"role": "user", "content": text})
        for text in request.context.task_context:
            messages.append({"role": "user", "content": text})
        for text in request.context.memory_context:
            messages.append({"role": "system", "content": f"verified-memory: {text}"})
        for text in request.context.evidence_context:
            messages.append({"role": "system", "content": f"verified-evidence: {text}"})
        if not messages and isinstance(request.payload.get("message"), str):
            messages.append({"role": "user", "content": request.payload["message"]})
        return messages

    def invoke(self, request: ModelRequest) -> ModelResult:
        key = self.credentials.resolve(self.provider_id)
        if not key:
            raise ProviderError(ProviderFailure("AUTH_FAILURE", self.provider_id, self.model_id,
                                                request.request_id, False, False))
        body = {"model": self.model_id, "messages": self._messages(request),
                "temperature": request.generation.temperature,
                "max_tokens": request.generation.max_output_tokens}
        encoded = json.dumps(body, separators=(",", ":")).encode()
        req = urlrequest.Request(self.base_url + "/chat/completions", data=encoded,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                                 method="POST")
        try:
            with urlrequest.urlopen(req, timeout=request.generation.timeout_seconds) as response:
                raw = response.read()
        except urlerror.HTTPError as exc:
            code = "RATE_LIMIT" if exc.code == 429 else "AUTH_FAILURE" if exc.code in (401, 403) else "SERVER_FAILURE"
            raise ProviderError(ProviderFailure(code, self.provider_id, self.model_id, request.request_id,
                                                code in {"RATE_LIMIT", "SERVER_FAILURE"}, code in {"RATE_LIMIT", "SERVER_FAILURE"})) from None
        except (urlerror.URLError, TimeoutError):
            raise ProviderError(ProviderFailure("NETWORK_FAILURE", self.provider_id, self.model_id,
                                                request.request_id, True, True)) from None
        try:
            data = json.loads(raw.decode("utf-8"))
            choice = data["choices"][0]
            content = choice["message"]["content"]
            usage_raw = data.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError(ProviderFailure("MALFORMED_RESPONSE", self.provider_id, self.model_id,
                                                request.request_id, False, False)) from None
        usage = TokenUsage(int(usage_raw.get("prompt_tokens", 0)), int(usage_raw.get("completion_tokens", 0)),
                           int(usage_raw.get("prompt_tokens_details", {}).get("cached_tokens", 0) or 0),
                           int(usage_raw.get("total_tokens", 0)), "PROVIDER_REPORTED", True)
        response_id = str(data.get("id", ""))
        input_price = float(os.getenv("PARADISE_INPUT_PRICE_PER_1K_USD", "0"))
        output_price = float(os.getenv("PARADISE_OUTPUT_PRICE_PER_1K_USD", "0"))
        actual_cost = (usage.input_tokens / 1000.0) * input_price + (usage.output_tokens / 1000.0) * output_price
        cost = CostRecord(request.request_id, self.provider_id, self.model_id, actual_cost, actual_cost,
                          "USD", os.getenv("PARADISE_PRICING_REFERENCE", "configured"),
                          os.getenv("PARADISE_PRICING_VERSION", "configured"))
        return ModelResult(self.provider_id, self.model_id, {"text": content}, True,
                           request.request_id, response_id, str(choice.get("finish_reason", "")), usage, cost)

class ModelGateway:
    """Single execution boundary for model/provider calls."""
    def __init__(self, adapters: dict[str, ProviderAdapter] | None = None):
        self.adapters = adapters or {"local": LocalEchoAdapter(
            "local", "local.echo.v1", ModelIdentity("local", "local.echo.v1", "1", ("echo",), ("text",), 10000, "none", "built-in"))}

    @classmethod
    def from_environment(cls, credentials: CredentialResolver | None = None) -> "ModelGateway":
        adapters: dict[str, ProviderAdapter] = {"local": LocalEchoAdapter(
            "local", "local.echo.v1", ModelIdentity("local", "local.echo.v1", "1", ("echo",), ("text",), 10000, "none", "built-in"))}
        provider = os.getenv("PARADISE_PROVIDER", "local").strip()
        model = os.getenv("PARADISE_MODEL", "local.echo.v1").strip()
        if provider != "local":
            base = os.getenv("PARADISE_PROVIDER_BASE_URL", "").strip()
            if base:
                adapters[provider] = OpenAICompatibleAdapter(provider, model, base, credentials)
        return cls(adapters)

    def identities(self) -> tuple[ModelIdentity, ...]:
        return tuple(a.identity for a in self.adapters.values())

    @staticmethod
    def _digest(value: Any) -> str:
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

    def invoke(self, request: ModelRequest) -> ModelResult:
        adapter = self.adapters.get(request.provider)
        if adapter is None or adapter.model_id != request.model:
            raise ProviderError(ProviderFailure("MODEL_NOT_FOUND", request.provider, request.model,
                                                request.request_id, False, False))
        result = adapter.invoke(request)
        response_digest = self._digest(result.output)
        witness = ModelWitness(request.request_id, request.execution_id, adapter.provider_id, adapter.model_id,
                               adapter.identity.model_revision, request.context.context_digest,
                               self._digest(request.payload), response_digest,
                               self._digest({"generation": request.generation, "budget": request.budget}),
                               self._digest(result.usage))
        return ModelResult(result.provider, result.model, result.output, result.success,
                           result.request_id, result.response_id, result.finish_reason,
                           result.usage, result.cost, witness)
