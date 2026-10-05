from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from paradise.contracts import BudgetPolicy, GenerationPolicy, ModelContext, ModelIdentity, ModelRequest, ModelResult, ProviderFailure, TokenUsage
from paradise.cognitive import CognitiveService
from paradise.model_gateway import LocalEchoAdapter, ModelGateway, ProviderAdapter, ProviderError, OpenAICompatibleAdapter
from paradise.store import RuntimeStore


class FailingAdapter(ProviderAdapter):
    def invoke(self, request: ModelRequest) -> ModelResult:
        raise ProviderError(ProviderFailure("TIMEOUT", self.provider_id, self.model_id, request.request_id, True, True))


class ProductionIntelligenceTests(unittest.TestCase):
    def request(self, provider="local", model="local.echo.v1"):
        return ModelRequest("T1", provider, model, "echo", {"message": "hello"},
                            request_id="REQ-1", execution_id="EXE-1",
                            context=ModelContext(task_context=("hello",), context_digest="ctx"),
                            generation=GenerationPolicy(), budget=BudgetPolicy())

    def test_model_identity_and_witness(self):
        gateway = ModelGateway()
        result = gateway.invoke(self.request())
        self.assertTrue(result.success)
        self.assertEqual(result.witness.provider_id, "local")
        self.assertEqual(result.witness.model_id, "local.echo.v1")
        self.assertEqual(result.witness.context_digest, "ctx")
        self.assertTrue(result.usage.usage_source == "ESTIMATED")

    def test_unknown_provider_is_normalized(self):
        gateway = ModelGateway()
        with self.assertRaises(ProviderError) as caught:
            gateway.invoke(self.request("missing", "missing.v1"))
        self.assertEqual(caught.exception.failure.code, "MODEL_NOT_FOUND")

    def test_failing_provider_is_normalized(self):
        adapter = FailingAdapter("primary", "model.v1", ModelIdentity("primary", "model.v1"))
        gateway = ModelGateway({"primary": adapter})
        with self.assertRaises(ProviderError) as caught:
            gateway.invoke(self.request("primary", "model.v1"))
        failure = caught.exception.failure
        self.assertEqual(failure.code, "TIMEOUT")
        self.assertTrue(failure.retryable)
        self.assertTrue(failure.fallback_eligible)

    def test_budget_guard_blocks_before_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeStore(Path(tmp) / "state.sqlite3")
            service = CognitiveService(store, "sha", "tree", "test")
            old = os.environ.get("PARADISE_MAX_REQUEST_COST_USD")
            os.environ["PARADISE_MAX_REQUEST_COST_USD"] = "0.01"
            os.environ["PARADISE_ESTIMATED_COST_PER_REQUEST_USD"] = "0.02"
            try:
                with self.assertRaises(ProviderError) as caught:
                    service.invoke_model("T1", "echo", {"message": "hello"})
                self.assertEqual(caught.exception.failure.code, "BUDGET_EXCEEDED")
                self.assertEqual(store.total_model_cost(), 0.0)
            finally:
                if old is None:
                    os.environ.pop("PARADISE_MAX_REQUEST_COST_USD", None)
                else:
                    os.environ["PARADISE_MAX_REQUEST_COST_USD"] = old
                os.environ.pop("PARADISE_ESTIMATED_COST_PER_REQUEST_USD", None)

    def test_credential_boundary_resolves_env_and_redacts_witness(self):
        from unittest.mock import patch
        adapter = OpenAICompatibleAdapter("fake", "model.v1", "http://provider.test")
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                return b'{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}'
        with patch.dict(os.environ, {"PARADISE_FAKE_API_KEY": "boundary-secret"}, clear=False):
            with patch("paradise.model_gateway.urlrequest.urlopen", return_value=Response()) as call:
                result = adapter.invoke(self.request("fake", "model.v1"))
        req = call.call_args.args[0]
        self.assertEqual(req.headers.get("Authorization"), "Bearer boundary-secret")
        self.assertNotIn("boundary-secret", repr(result.witness))
        self.assertNotIn("boundary-secret", repr(result))

    def test_credential_boundary_fails_closed_without_secret(self):
        from unittest.mock import patch
        adapter = OpenAICompatibleAdapter("fake", "model.v1", "http://provider.test")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError) as caught:
                adapter.invoke(self.request("fake", "model.v1"))
        self.assertEqual(caught.exception.failure.code, "AUTH_FAILURE")
        self.assertFalse(caught.exception.failure.fallback_eligible)

    def test_secret_is_not_in_witness(self):
        gateway = ModelGateway()
        result = gateway.invoke(self.request())
        witness_text = repr(result.witness)
        self.assertNotIn("API_KEY", witness_text)
        self.assertNotIn("secret", witness_text.lower())

    def test_provider_timeout_is_normalized(self):
        from unittest.mock import patch
        adapter = OpenAICompatibleAdapter("fake", "model.v1", "http://provider.test")
        with patch.dict(os.environ, {"PARADISE_FAKE_API_KEY": "test-secret"}, clear=False):
            with patch("paradise.model_gateway.urlrequest.urlopen", side_effect=TimeoutError):
                with self.assertRaises(ProviderError) as caught:
                    adapter.invoke(self.request("fake", "model.v1"))
        self.assertEqual(caught.exception.failure.code, "NETWORK_FAILURE")
        self.assertTrue(caught.exception.failure.fallback_eligible)

    def test_malformed_provider_response_is_rejected(self):
        from unittest.mock import patch
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"choices": []}'
        adapter = OpenAICompatibleAdapter("fake", "model.v1", "http://provider.test")
        with patch.dict(os.environ, {"PARADISE_FAKE_API_KEY": "test-secret"}, clear=False):
            with patch("paradise.model_gateway.urlrequest.urlopen", return_value=Response()):
                with self.assertRaises(ProviderError) as caught:
                    adapter.invoke(self.request("fake", "model.v1"))
        self.assertEqual(caught.exception.failure.code, "MALFORMED_RESPONSE")
        self.assertFalse(caught.exception.failure.fallback_eligible)

    def test_fallback_denied_by_policy(self):
        class Failing(ProviderAdapter):
            def invoke(self, request):
                raise ProviderError(ProviderFailure("TIMEOUT", self.provider_id, self.model_id, request.request_id, True, True))
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeStore(Path(tmp) / "state.sqlite3")
            service = CognitiveService(store, "sha", "tree", "test")
            service.models = ModelGateway({"primary": Failing("primary", "model.v1", ModelIdentity("primary", "model.v1")), "local": LocalEchoAdapter("local", "local.echo.v1", ModelIdentity("local", "local.echo.v1"))})
            old = {k: os.environ.get(k) for k in ("PARADISE_PROVIDER", "PARADISE_MODEL", "PARADISE_ALLOW_FALLBACK")}
            os.environ.update({"PARADISE_PROVIDER": "primary", "PARADISE_MODEL": "model.v1", "PARADISE_ALLOW_FALLBACK": "false"})
            try:
                with self.assertRaises(ProviderError) as caught:
                    service.invoke_model("T1", "echo", {"message": "hello"})
                self.assertEqual(caught.exception.failure.code, "TIMEOUT")
                with store._connection() as conn:
                    rows = conn.execute("SELECT event_type FROM audit_events WHERE task_id=? ORDER BY occurred_at", ("T1",)).fetchall()
                self.assertEqual([r[0] for r in rows], ["PROVIDER_FAILURE"])
            finally:
                for k, v in old.items():
                    if v is None: os.environ.pop(k, None)
                    else: os.environ[k] = v

    def test_context_overflow_is_blocked_before_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeStore(Path(tmp) / "state.sqlite3")
            service = CognitiveService(store, "sha", "tree", "test")
            old = os.environ.get("PARADISE_CONTEXT_TOKEN_BUDGET")
            os.environ["PARADISE_CONTEXT_TOKEN_BUDGET"] = "1"
            try:
                with self.assertRaises(ProviderError) as caught:
                    service.invoke_model("T1", "echo", {"message": "x" * 100})
                self.assertEqual(caught.exception.failure.code, "CONTEXT_LIMIT")
                self.assertEqual(store.list_model_costs(), [])
            finally:
                if old is None: os.environ.pop("PARADISE_CONTEXT_TOKEN_BUDGET", None)
                else: os.environ["PARADISE_CONTEXT_TOKEN_BUDGET"] = old

    def test_replay_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeStore(Path(tmp) / "state.sqlite3")
            service = CognitiveService(store, "sha", "tree", "test")
            service.emit_replay("T1", "MODEL_EXECUTION", {"x": 1})
            self.assertTrue(service.verify_replay("T1"))
            with store._connection() as conn:
                row = conn.execute("SELECT replay_id, record_json FROM replay_records WHERE task_id=?", ("T1",)).fetchone()
                import json
                record = json.loads(row[1]); record["payload"] = {"x": 999}
                conn.execute("UPDATE replay_records SET record_json=? WHERE replay_id=?", (json.dumps(record, sort_keys=True), row[0]))
                conn.commit()
            self.assertFalse(service.verify_replay("T1"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

