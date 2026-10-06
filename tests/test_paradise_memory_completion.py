from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from paradise.server import ParadiseApplication, RuntimeConfig
from projects.LOVE.stt_love.memory_trust import MemoryTrustStatus

class ParadiseMemoryCompletionTests(unittest.TestCase):
    def cfg(self, path: Path) -> RuntimeConfig:
        c = RuntimeConfig(); c.api_token = "secret"; c.data_path = path; return c

    def test_observed_memory_never_self_promotes_from_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = ParadiseApplication(self.cfg(Path(tmp) / "state.sqlite3"))
            task = app.submit({"operation":"echo","payload":{"message":"x","memory":{"claim":"user prefers concise answers","trust":"VERIFIED"}},"idempotency_key":"m-self"})
            self.assertEqual(task["status"], "SUCCEEDED")
            rows = app.store.load_memory(task["result"]["memory_key"], "conversation")
            self.assertEqual(rows[0]["trust_status"], MemoryTrustStatus.OBSERVED.value)

    def test_memory_lifecycle_qualifies_only_through_canonical_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            app = ParadiseApplication(self.cfg(path))
            task = app.submit({"operation":"echo","payload":{"message":"x","memory":{"claim":"user prefers evidence first"}},"idempotency_key":"m-life"})
            result = task["result"]
            memory = app.store.load_memory(result["memory_key"], "conversation")[0]
            self.assertEqual(memory["trust_status"], "OBSERVED")
            promoted = app.cognitive.promote_memory(task["task_id"], memory["memory_id"], result["evidence_id"], target=MemoryTrustStatus.QUALIFIED)
            self.assertEqual(promoted["trust_status"], "QUALIFIED")
            advice = app.cognitive.advise(__import__("runtime.paradise.contracts", fromlist=["CognitiveRequest"]).CognitiveRequest("t2","echo",{"memory_key":result["memory_key"]},app.config.commit,app.config.tree,app.config.environment))
            self.assertEqual(advice.memory_ids, (memory["memory_id"],))

    def test_memory_idempotency_is_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            app = ParadiseApplication(self.cfg(path))
            p={"operation":"echo","payload":{"message":"x","memory":{"claim":"same claim","idempotency_key":"mem-idem"}},"idempotency_key":"m-idem-task"}
            a=app.submit(p); b=app.submit({**p,"task_id":"OTHER"})
            self.assertEqual(a["task_id"], b["task_id"])
            self.assertEqual(len(app.store.load_memory(a["result"]["memory_key"], "conversation")), 1)
            app2=ParadiseApplication(self.cfg(path))
            rows=app2.store.find_memory_by_idempotency("mem-idem")
            self.assertEqual(len(rows),1)

    def test_supersede_and_refute_and_replay_block_memory_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"state.sqlite3"; app=ParadiseApplication(self.cfg(path))
            task=app.submit({"operation":"echo","payload":{"message":"x","memory":{"claim":"old preference"}},"idempotency_key":"m-ref"})
            result=task["result"]; mem=app.store.load_memory(result["memory_key"],"conversation")[0]
            app.cognitive.promote_memory(task["task_id"],mem["memory_id"],result["evidence_id"],target=MemoryTrustStatus.QUALIFIED)
            ref=app.cognitive.refute_memory(task["task_id"],mem["memory_id"],result["evidence_id"])
            self.assertEqual(ref["trust_status"],"REFUTED")
            advice=app.cognitive.advise(__import__("runtime.paradise.contracts", fromlist=["CognitiveRequest"]).CognitiveRequest("t3","echo",{"memory_key":result["memory_key"]},app.config.commit,app.config.tree,app.config.environment))
            self.assertEqual(advice.memory_ids,())
            self.assertTrue(app.cognitive.verify_replay(task["task_id"]))
            self.assertEqual([r["event_type"] for r in app.store.list_replay(task["task_id"])], ["MODEL_EXECUTION","MEMORY_OBSERVED","LEARNING_ARTIFACT_RECORDED","MEMORY_PROMOTED","MEMORY_REFUTED"])

    def test_supersession_removes_prior_memory_from_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"state.sqlite3"; app=ParadiseApplication(self.cfg(path))
            a=app.submit({"operation":"echo","payload":{"message":"a","memory":{"claim":"preferred mode","normalized_key":"MEM-SAME"}},"idempotency_key":"m-s1"})
            b=app.submit({"operation":"echo","payload":{"message":"b","memory":{"claim":"preferred mode","normalized_key":"MEM-SAME"}},"idempotency_key":"m-s2"})
            ma=app.store.load_memory("MEM-SAME","conversation")[0]; mb=app.store.load_memory("MEM-SAME","conversation")[1]
            app.cognitive.promote_memory(a["task_id"],ma["memory_id"],a["result"]["evidence_id"],target=MemoryTrustStatus.QUALIFIED)
            app.cognitive.promote_memory(b["task_id"],mb["memory_id"],b["result"]["evidence_id"],target=MemoryTrustStatus.QUALIFIED)
            app.cognitive.supersede_memory(b["task_id"],mb["memory_id"],ma["memory_id"],b["result"]["evidence_id"])
            advice=app.cognitive.advise(__import__("runtime.paradise.contracts", fromlist=["CognitiveRequest"]).CognitiveRequest("t4","echo",{"memory_key":"MEM-SAME"},app.config.commit,app.config.tree,app.config.environment))
            self.assertEqual(advice.memory_ids,(mb["memory_id"],))

    def test_learning_hint_is_observational_and_non_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=ParadiseApplication(self.cfg(Path(tmp)/"state.sqlite3"))
            app.submit({"operation":"echo","payload":{"message":"learn"},"idempotency_key":"learn-1"})
            hint=app.cognitive.learning_hint()
            self.assertTrue(hint["observed_only"]); self.assertEqual(hint["authority"],"none")

    def test_learning_artifact_v3_is_canonical_record_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"state.sqlite3"; app=ParadiseApplication(self.cfg(path))
            task=app.submit({"operation":"echo","payload":{"message":"artifact"},"idempotency_key":"la3-1"})
            aid=task["result"]["learning_artifact_id"]
            rows=app.store.list_learning_artifacts(task["task_id"])
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["artifact_id"],aid)
            self.assertEqual(rows[0]["learning_state"],"OBSERVED")
            self.assertEqual(len(rows[0]),18)
            self.assertIsNone(rows[0]["model_eligibility_ref"])
            app2=ParadiseApplication(self.cfg(path))
            self.assertEqual(app2.store.list_learning_artifacts(task["task_id"])[0]["artifact_id"],aid)
            self.assertTrue(app2.cognitive.verify_replay(task["task_id"]))

if __name__ == "__main__": unittest.main(verbosity=2)
