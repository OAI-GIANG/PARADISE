from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from paradise.server import ParadiseApplication, RuntimeConfig

class LoveIntegrationTests(unittest.TestCase):
    def cfg(self, path: Path) -> RuntimeConfig:
        c = RuntimeConfig(); c.api_token = "secret"; c.data_path = path
        return c

    def test_cognitive_execution_creates_evidence_replay_and_learning(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = ParadiseApplication(self.cfg(Path(tmp) / "state.sqlite3"))
            task = app.submit({"operation":"echo","payload":{"message":"hello"},"idempotency_key":"c1"})
            self.assertEqual(task["status"], "SUCCEEDED")
            result = task["result"]
            self.assertTrue(result["evidence_id"].startswith("EVD-"))
            self.assertTrue(result["replay_id"].startswith("RPL-"))
            self.assertEqual(len(app.store.list_evidence(task["task_id"])), 1)
            self.assertEqual(len(app.store.list_replay(task["task_id"])), 2)
            self.assertTrue(app.cognitive.verify_replay(task["task_id"]))
            self.assertEqual(len(app.store.list_learning_observations()), 1)

    def test_verified_memory_persists_and_is_retrievable_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            app = ParadiseApplication(self.cfg(path))
            task = app.submit({"operation":"echo","payload":{
                "message":"remember", "memory":{"claim":"user prefers evidence first","trust":"VERIFIED","scope":"conversation"}
            },"idempotency_key":"m1"})
            self.assertEqual(task["status"], "SUCCEEDED")
            memory_key = task["result"]["memory_key"]
            rows0 = app.store.load_memory(memory_key, "conversation")
            self.assertEqual(rows0[0]["trust_status"], "OBSERVED")
            app.cognitive.promote_memory(task["task_id"], rows0[0]["memory_id"], task["result"]["evidence_id"], target=__import__("projects.LOVE.stt_love.memory_trust", fromlist=["MemoryTrustStatus"]).MemoryTrustStatus.VERIFIED)
            app2 = ParadiseApplication(self.cfg(path))
            rows = app2.store.load_memory(memory_key, "conversation")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["trust_status"], "VERIFIED")
            follow = app2.submit({"operation":"echo","payload":{"message":"use memory","memory_key":memory_key,"memory_scope":"conversation"},"idempotency_key":"m2"})
            self.assertEqual(follow["result"]["cognitive"]["memory_ids"], [rows[0]["memory_id"]])
            self.assertIn(rows[0]["evidence_refs"][0], follow["result"]["cognitive"]["evidence_ids"])
            del app2
            del app

    def test_invalid_memory_is_rejected_without_memory_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = ParadiseApplication(self.cfg(Path(tmp) / "state.sqlite3"))
            task = app.submit({"operation":"echo","payload":{"message":"bad","memory":{"scope":"conversation"}},"idempotency_key":"m2"})
            self.assertEqual(task["status"], "FAILED")
            self.assertIn("claim", task["error"])
            self.assertEqual(app.store.list_tasks()[0]["status"], "FAILED")

    def test_unsupported_operation_never_reaches_model_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = ParadiseApplication(self.cfg(Path(tmp) / "state.sqlite3"))
            task = app.submit({"operation":"shell","payload":{"message":"no"},"idempotency_key":"n1"})
            self.assertEqual(task["status"], "FAILED")
            self.assertEqual(app.store.list_learning_observations(), [])

    def test_restart_keeps_evidence_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            app = ParadiseApplication(self.cfg(path))
            task = app.submit({"operation":"echo","payload":{"message":"restart"},"idempotency_key":"r1"})
            app2 = ParadiseApplication(self.cfg(path))
            self.assertEqual(len(app2.store.list_evidence(task["task_id"])), 1)
            self.assertEqual(len(app2.store.list_replay(task["task_id"])), 2)
            self.assertTrue(app2.cognitive.verify_replay(task["task_id"]))
            del app2
            del app

if __name__ == "__main__":
    unittest.main(verbosity=2)
