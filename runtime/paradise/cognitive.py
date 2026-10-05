"""Canonical integration of LOVE cognitive capabilities into PARADISE."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import uuid
from typing import Any

from projects.LOVE.stt_love.memory_trust import (
    MemoryCore, MemoryRecord, MemoryTrustStatus, TrustCertificate, memory_artifact_digest,
)
from projects.LOVE.stt_love.learning import (
    build_knowledge_hint, compute_learning, compute_metrics, select_provider_from_performance,
)
from runtime.paradise_kernel import Authority, Evidence, GateResult, Kernel
from .contracts import CognitiveAdvice, CognitiveRequest, ModelRequest
from .model_gateway import ModelGateway
from .store import RuntimeStore
from .cognitive_lifecycle import CognitiveLifecycle

class CognitiveService:
    """Cognitive facade; it never owns runtime state or persistence."""
    def __init__(self, store: RuntimeStore, commit: str, tree: str, environment: str):
        self.store = store
        self.commit = commit
        self.tree = tree
        self.environment = environment
        self.memory = MemoryCore()
        self.kernel = Kernel(trusted_evidence_sources=frozenset({"paradise.runtime"}))
        self.models = ModelGateway()
        self.lifecycle = CognitiveLifecycle(store, commit, tree, environment)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def advise(self, request: CognitiveRequest) -> CognitiveAdvice:
        payload = dict(request.payload)
        memory_ids: list[str] = []
        evidence_ids: list[str] = []
        model_memory_ids: list[str] = []
        model_memory_context: list[dict[str, Any]] = []
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
            for derived in self.store.load_model_memory(str(memory_key)):
                if derived.get("trust_status") == "DERIVED_NOT_VERIFIED":
                    model_memory_ids.append(str(derived["model_memory_id"]))
                    model_memory_context.append({"model_memory_id": derived["model_memory_id"], "content": derived["content"], "evidence_refs": list(derived.get("evidence_refs", [])), "authority": "none"})
                    evidence_ids.extend(derived.get("evidence_refs", []))
        return CognitiveAdvice(request.task_id, "use_verified_context_only", tuple(memory_ids), tuple(evidence_ids), tuple(model_memory_ids), tuple(model_memory_context))

    def authorize(self, task_id: str, operation: str) -> None:
        now = datetime.now(timezone.utc)
        authority = Authority(
            authority_id="paradise-runtime", subject=task_id,
            scope=frozenset({"runtime"}), actions=frozenset({"execute"}), issuer="paradise",
            valid_from=now - timedelta(seconds=1), valid_until=now + timedelta(seconds=60),
            contexts=frozenset({"runtime"}), provenance=self.commit,
        )
        result, authorization = self.kernel.authorize(authority, task_id, "execute", "runtime", "runtime", now)
        if result is not GateResult.ALLOW or authorization is None:
            raise PermissionError("PARADISE kernel denied execution")

    def _route(self, task_id: str) -> tuple[str, str, dict[str, Any]]:
        observations = self.store.list_learning_observations()
        routed = select_provider_from_performance("reasoning", "local", observations)
        return str(routed["provider"]), "local.echo.v1", routed

    def invoke_model(self, task_id: str, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        provider, model, routing = self._route(task_id)
        result = self.models.invoke(ModelRequest(task_id, provider, model, operation, payload))
        output = dict(result.output)
        output.update({"provider": result.provider, "model": result.model, "routing": routing})
        observation = {
            "observation_id": f"OBS-{uuid.uuid4().hex}", "task_id": task_id,
            "capability_id": "reasoning", "provider_id": result.provider, "model_id": result.model,
            "risk_class": "LOW", "metrics": {"success_rate": 1.0 if result.success else 0.0, "latency_ms_p95": 0.0},
            "qualification": {"qualification": "G7"},
            "evidence": {"source_commit": self.commit, "evidence_refs": []}, "observed_at": self._now(),
        }
        self.store.save_learning_observation(observation, observation["observed_at"])
        return output

    def emit_evidence(self, task_id: str, event_type: str, claim: str) -> dict[str, Any]:
        evidence_id = f"EVD-{uuid.uuid4().hex}"
        captured = datetime.now(timezone.utc)
        source = "paradise.runtime"
        provenance = f"{self.commit}:{self.tree}:{self.environment}"
        canonical = "|".join((evidence_id, task_id, "runtime", source, captured.isoformat(), provenance))
        integrity = sha256(canonical.encode()).hexdigest()
        evidence = Evidence(evidence_id, task_id, "runtime", source, captured, provenance, integrity, "VERIFIED", claim)
        if self.kernel.verify_evidence(evidence, task_id, "runtime") is not GateResult.ALLOW:
            raise RuntimeError("canonical evidence failed kernel verification")
        record = {"evidence_id": evidence_id, "task_id": task_id, "event_type": event_type,
                  "claim": claim, "source": source, "provenance": provenance, "integrity": integrity,
                  "verification_status": "VERIFIED", "captured_at": captured.isoformat()}
        self.store.save_evidence(record, captured.isoformat())
        return record

    def emit_replay(self, task_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        records = self.store.list_replay(task_id)
        sequence = len(records) + 1
        previous = records[-1]["record_digest"] if records else "GENESIS"
        replay_id = f"RPL-{uuid.uuid4().hex}"
        canonical = json.dumps({"replay_id": replay_id, "task_id": task_id, "sequence": sequence,
                                "event_type": event_type, "payload": payload, "previous_digest": previous},
                               sort_keys=True, separators=(",", ":"))
        digest = sha256(canonical.encode()).hexdigest()
        record = {"replay_id": replay_id, "task_id": task_id, "sequence": sequence,
                  "event_type": event_type, "payload": payload, "previous_digest": previous,
                  "record_digest": digest}
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
            memory_id=str(item.get("memory_id") or f"MEM-{uuid.uuid4().hex}"),
            memory_class=str(item.get("memory_class", "experience")), claim=str(item["claim"]),
            scope=str(item.get("scope", "conversation")), source_actor=str(item.get("source_actor", "user")),
            authority=str(item.get("authority", "user")), provenance_commit=self.commit,
            provenance_tree_sha=self.tree, environment_id=self.environment, evidence_refs=(evidence_id,),
            task_id=task_id, confidence=float(item.get("confidence", 0.5)),
            freshness_days=int(item.get("freshness_days", 7)), normalized_key=item.get("normalized_key"), observed_at=self._now(),
        )
        if str(item.get("trust", "")).upper() == "VERIFIED":
            certificate = TrustCertificate(
                certificate_id=f"CERT-{uuid.uuid4().hex}", evaluator_id="paradise-runtime",
                evaluator_kind="runtime", method="canonical-execution-evidence",
                artifact_digest=memory_artifact_digest(record), source_commit=self.commit,
                source_tree_sha=self.tree, result="VERIFIED", evidence_refs=(evidence_id,), issued_at=self._now(),
            )
            record = self.memory.verified(record, certificate=certificate)
        raw = record.to_dict()
        self.store.save_memory(raw, record.created_at)
        lifecycle = self.lifecycle.ingest_memory(task_id=task_id, memory=raw, evidence_refs=[evidence_id])
        raw["lifecycle"] = lifecycle.__dict__
        return raw

    def learning_hint(self) -> dict[str, Any]:
        tasks = self.store.list_tasks()
        task_view = [{"state": "COMPLETED" if t["status"] == "SUCCEEDED" else "FAILED",
                      "report": {"result": t.get("result") or {}}} for t in tasks]
        metrics = compute_metrics(task_view, [])
        learning = compute_learning(task_view, [], metrics)
        return build_knowledge_hint(learning, metrics)
