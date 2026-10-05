"""Canonical integration of LOVE cognitive capabilities into PARADISE."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import uuid
from typing import Any

from projects.LOVE.stt_love.memory_trust import (
    MemoryCore, MemoryRecord, MemoryTrustStatus, TrustCertificate, memory_artifact_digest,
)
from projects.LOVE.stt_love.learning import (
    build_knowledge_hint, compute_learning, compute_metrics, select_provider_from_performance,
)
from runtime.paradise_kernel import Authority, Evidence, GateResult, Kernel
from .contracts import (
    BudgetPolicy, CognitiveAdvice, CognitiveRequest, GenerationPolicy, ModelContext, ModelRequest,
    ModelResult, ProviderFailure,
)
from .model_gateway import ModelGateway, ProviderError
from .store import RuntimeStore

class CognitiveService:
    """Cognitive facade; it never owns canonical runtime state or persistence."""
    def __init__(self, store: RuntimeStore, commit: str, tree: str, environment: str):
        self.store = store
        self.commit = commit
        self.tree = tree
        self.environment = environment
        self.memory = MemoryCore()
        self.kernel = Kernel(trusted_evidence_sources=frozenset({"paradise.runtime"}))
        self.models = ModelGateway.from_environment()
        self.monthly_budget = float(os.getenv("PARADISE_MONTHLY_BUDGET_USD", "0"))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def advise(self, request: CognitiveRequest) -> CognitiveAdvice:
        payload = dict(request.payload)
        memory_ids: list[str] = []
        evidence_ids: list[str] = []
        memory_key = payload.get("memory_key")
        scope = str(payload.get("memory_scope", "conversation"))
        if memory_key:
            records = self.store.load_memory(str(memory_key), scope)
            parsed: list[MemoryRecord] = []
            for raw in records:
                try:
                    parsed.append(MemoryRecord(
                        **{**raw, "trust_status": MemoryTrustStatus(raw["trust_status"]),
                           "evidence_refs": tuple(raw.get("evidence_refs", [])),
                           "supersedes": tuple(raw.get("supersedes", [])),
                           "refutes": tuple(raw.get("refutes", [])),
                           "support_group_ids": tuple(raw.get("support_group_ids", []))}))
                except (KeyError, ValueError, TypeError):
                    continue
            resolved = self.memory.resolve(parsed, str(memory_key), scope) if parsed else None
            if resolved and resolved.trust_status in {MemoryTrustStatus.VERIFIED, MemoryTrustStatus.QUALIFIED}:
                memory_ids.append(resolved.memory_id)
                evidence_ids.extend(resolved.evidence_refs)
        return CognitiveAdvice(request.task_id, "use_verified_context_only", tuple(memory_ids), tuple(evidence_ids))

    def authorize(self, task_id: str, operation: str) -> None:
        now = datetime.now(timezone.utc)
        authority = Authority(
            authority_id="paradise-runtime", subject=task_id, scope=frozenset({"runtime"}),
            actions=frozenset({"execute"}), issuer="paradise", valid_from=now - timedelta(seconds=1),
            valid_until=now + timedelta(seconds=60), contexts=frozenset({"runtime"}), provenance=self.commit,
        )
        result, authorization = self.kernel.authorize(authority, task_id, "execute", "runtime", "runtime", now)
        if result is not GateResult.ALLOW or authorization is None:
            raise PermissionError("PARADISE kernel denied execution")

    def _route(self, task_id: str) -> tuple[str, str, dict[str, Any]]:
        observations = self.store.list_learning_observations()
        configured_provider = os.getenv("PARADISE_PROVIDER", "local").strip() or "local"
        configured_model = os.getenv("PARADISE_MODEL", "local.echo.v1").strip() or "local.echo.v1"
        routed = select_provider_from_performance("reasoning", configured_provider, observations)
        provider = str(routed.get("provider") or configured_provider)
        if provider not in {identity.provider_id for identity in self.models.identities()}:
            provider = configured_provider
        model = configured_model if provider != "local" else "local.echo.v1"
        return provider, model, routed

    def _assemble_context(self, task_id: str, payload: dict[str, Any], advice: CognitiveAdvice) -> ModelContext:
        task_text = payload.get("message") if isinstance(payload.get("message"), str) else json.dumps(payload, sort_keys=True)
        memory_context: list[str] = []
        for memory_id in advice.memory_ids:
            for record in self.store.load_memory(str(payload.get("memory_key")), str(payload.get("memory_scope", "conversation"))):
                if record.get("memory_id") == memory_id:
                    memory_context.append(str(record.get("claim", "")))
        evidence_context = [str(e) for e in advice.evidence_ids]
        policy = ("Only use verified memory/evidence; provider cannot mutate canonical state.",)
        token_budget = int(os.getenv("PARADISE_CONTEXT_TOKEN_BUDGET", "4096"))
        estimated_input_tokens = max(1, len(task_text) // 4 + sum(len(x) // 4 for x in memory_context + evidence_context + list(policy)))
        if estimated_input_tokens > token_budget:
            raise ProviderError(ProviderFailure("CONTEXT_LIMIT", "context", "assembly", "", False, False))
        canonical = {
            "task": [task_text], "memory": memory_context, "evidence": evidence_context,
            "policy": list(policy), "task_id": task_id,
        }
        digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return ModelContext(task_context=(task_text,), memory_context=tuple(memory_context),
                            evidence_context=tuple(evidence_context), policy_context=policy,
                            token_budget=token_budget,
                            context_digest=digest, provenance=(self.commit, self.tree, self.environment))

    def _estimate_cost(self, provider: str, model: str, payload: dict[str, Any]) -> float:
        price = float(os.getenv("PARADISE_ESTIMATED_COST_PER_REQUEST_USD", "0"))
        return max(0.0, price)

    def _budget_check(self, estimated: float, policy: BudgetPolicy) -> None:
        if policy.max_request_cost and estimated > policy.max_request_cost:
            raise ProviderError(ProviderFailure("BUDGET_EXCEEDED", "budget", "guard", "", False, False))
        if self.monthly_budget > 0 and self.store.total_model_cost(policy.currency) + estimated > self.monthly_budget:
            raise ProviderError(ProviderFailure("BUDGET_EXCEEDED", "budget", "monthly", "", False, False))

    def _save_cost(self, task_id: str, result: ModelResult) -> None:
        if result.cost is None:
            return
        record = {
            "request_id": result.cost.request_id, "task_id": task_id, "provider_id": result.cost.provider_id,
            "model_id": result.cost.model_id, "estimated_cost": result.cost.estimated_cost,
            "actual_cost": result.cost.actual_cost, "currency": result.cost.currency,
            "pricing_reference": result.cost.pricing_reference, "pricing_version": result.cost.pricing_version,
        }
        self.store.save_model_cost(record, self._now())

    def invoke_model(self, task_id: str, operation: str, payload: dict[str, Any], advice: CognitiveAdvice | None = None) -> dict[str, Any]:
        advice = advice or CognitiveAdvice(task_id, "use_verified_context_only")
        provider, model, routing = self._route(task_id)
        request_id = f"REQ-{uuid.uuid4().hex}"
        execution_id = f"EXE-{uuid.uuid4().hex}"
        context = self._assemble_context(task_id, payload, advice)
        generation = GenerationPolicy(
            temperature=float(os.getenv("PARADISE_TEMPERATURE", "0")),
            max_output_tokens=int(os.getenv("PARADISE_MAX_OUTPUT_TOKENS", "1024")),
            timeout_seconds=float(os.getenv("PARADISE_PROVIDER_TIMEOUT_SECONDS", "30")),
        )
        budget = BudgetPolicy(
            max_request_cost=float(os.getenv("PARADISE_MAX_REQUEST_COST_USD", "0")),
            currency="USD", allow_fallback=os.getenv("PARADISE_ALLOW_FALLBACK", "true").lower() in {"1", "true", "yes"},
        )
        estimated = self._estimate_cost(provider, model, payload)
        self._budget_check(estimated, budget)
        request = ModelRequest(task_id, provider, model, operation, payload, request_id, execution_id, context, generation, budget)
        try:
            result = self.models.invoke(request)
        except ProviderError as primary:
            self.store.add_event(task_id, "PROVIDER_FAILURE", {
                "request_id": request_id, "code": primary.failure.code, "provider": primary.failure.provider_id,
                "fallback_eligible": primary.failure.fallback_eligible,
            }, self._now())
            if not (primary.failure.fallback_eligible and budget.allow_fallback):
                raise
            fallback_provider = os.getenv("PARADISE_FALLBACK_PROVIDER", "local").strip()
            fallback_model = "local.echo.v1"
            if fallback_provider == provider or fallback_provider not in {i.provider_id for i in self.models.identities()}:
                raise
            self._budget_check(0.0, budget)
            self.store.add_event(task_id, "PROVIDER_FALLBACK", {
                "request_id": request_id, "primary_provider": provider, "fallback_provider": fallback_provider,
            }, self._now())
            result = self.models.invoke(ModelRequest(task_id, fallback_provider, fallback_model, operation,
                                                     payload, request_id, execution_id, context, generation, budget))
        self._save_cost(task_id, result)
        output = dict(result.output)
        output.update({"provider": result.provider, "model": result.model, "routing": routing,
                       "request_id": result.request_id, "response_id": result.response_id,
                       "usage": {"input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens,
                                  "total_tokens": result.usage.total_tokens, "source": result.usage.usage_source},
                       "witness": result.witness.__dict__ if result.witness else None})
        observation = {
            "observation_id": f"OBS-{uuid.uuid4().hex}", "task_id": task_id, "capability_id": "reasoning",
            "provider_id": result.provider, "model_id": result.model, "risk_class": "LOW",
            "metrics": {"success_rate": 1.0 if result.success else 0.0, "latency_ms_p95": 0.0},
            "qualification": {"qualification": "G7"}, "evidence": {"source_commit": self.commit, "evidence_refs": []},
            "observed_at": self._now(),
        }
        self.store.save_learning_observation(observation, observation["observed_at"])
        return output

    def emit_evidence(self, task_id: str, event_type: str, claim: str, witness: dict[str, Any] | None = None) -> dict[str, Any]:
        evidence_id = f"EVD-{uuid.uuid4().hex}"
        captured = datetime.now(timezone.utc)
        source = "paradise.runtime"
        provenance = f"{self.commit}:{self.tree}:{self.environment}"
        canonical = "|".join((evidence_id, task_id, "runtime", source, captured.isoformat(), provenance))
        integrity = sha256(canonical.encode()).hexdigest()
        evidence = Evidence(evidence_id, task_id, "runtime", source, captured, provenance, integrity, "VERIFIED", claim)
        if self.kernel.verify_evidence(evidence, task_id, "runtime") is not GateResult.ALLOW:
            raise RuntimeError("canonical evidence failed kernel verification")
        record = {"evidence_id": evidence_id, "task_id": task_id, "event_type": event_type, "claim": claim,
                  "source": source, "provenance": provenance, "integrity": integrity,
                  "verification_status": "VERIFIED", "captured_at": captured.isoformat(), "model_witness": witness or {}}
        self.store.save_evidence(record, captured.isoformat())
        return record

    def emit_replay(self, task_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        records = self.store.list_replay(task_id)
        sequence = len(records) + 1
        previous = records[-1]["record_digest"] if records else "GENESIS"
        replay_id = f"RPL-{uuid.uuid4().hex}"
        safe_payload = json.loads(json.dumps(payload, sort_keys=True, default=str))
        canonical = json.dumps({"replay_id": replay_id, "task_id": task_id, "sequence": sequence,
                                "event_type": event_type, "payload": safe_payload, "previous_digest": previous},
                               sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical.encode()).hexdigest()
        record = {"replay_id": replay_id, "task_id": task_id, "sequence": sequence,
                  "event_type": event_type, "payload": safe_payload, "previous_digest": previous, "record_digest": digest}
        self.store.save_replay(record, self._now())
        return record

    def verify_replay(self, task_id: str) -> bool:
        records = self.store.list_replay(task_id)
        previous = "GENESIS"
        for record in records:
            canonical = json.dumps({"replay_id": record["replay_id"], "task_id": task_id,
                                    "sequence": record["sequence"], "event_type": record["event_type"],
                                    "payload": record["payload"], "previous_digest": previous},
                                   sort_keys=True, separators=(",", ":"))
            if record["previous_digest"] != previous or record["record_digest"] != sha256(canonical.encode()).hexdigest():
                return False
            previous = record["record_digest"]
        return True

    def observe_memory(self, task_id: str, payload: dict[str, Any], evidence_id: str) -> dict[str, Any] | None:
        item = payload.get("memory")
        if not isinstance(item, dict):
            return None
        record = self.memory.observe(
            memory_id=str(item.get("memory_id") or f"MEM-{uuid.uuid4().hex}"), memory_class=str(item.get("memory_class", "experience")),
            claim=str(item["claim"]), scope=str(item.get("scope", "conversation")), source_actor=str(item.get("source_actor", "user")),
            authority=str(item.get("authority", "user")), provenance_commit=self.commit, provenance_tree_sha=self.tree,
            environment_id=self.environment, evidence_refs=(evidence_id,), task_id=task_id,
            confidence=float(item.get("confidence", 0.5)), freshness_days=int(item.get("freshness_days", 7)),
            normalized_key=item.get("normalized_key"), observed_at=self._now(),
        )
        if str(item.get("trust", "")).upper() == "VERIFIED":
            certificate = TrustCertificate(
                certificate_id=f"CERT-{uuid.uuid4().hex}", evaluator_id="paradise-runtime", evaluator_kind="runtime",
                method="canonical-execution-evidence", artifact_digest=memory_artifact_digest(record), source_commit=self.commit,
                source_tree_sha=self.tree, result="VERIFIED", evidence_refs=(evidence_id,), issued_at=self._now(),
            )
            record = self.memory.verified(record, certificate=certificate)
        raw = record.to_dict()
        self.store.save_memory(raw, record.created_at)
        return raw

    def learning_hint(self) -> dict[str, Any]:
        tasks = self.store.list_tasks()
        task_view = [{"state": "COMPLETED" if t["status"] == "SUCCEEDED" else "FAILED", "report": {"result": t.get("result") or {}}} for t in tasks]
        metrics = compute_metrics(task_view, [])
        learning = compute_learning(task_view, [], metrics)
        return build_knowledge_hint(learning, metrics)
