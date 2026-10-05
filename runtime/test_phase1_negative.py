from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from paradise.store import RuntimeStore
from projects.LOVE.stt_love.task_contract import TaskContract
from projects.LOVE.stt_love.durable_execution import DurableExecution, DurableExecutionError

class Phase1NegativeTests(unittest.TestCase):
    def test_durable_execution_rejects_non_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            durable=DurableExecution(RuntimeStore(Path(tmp)/"state.sqlite3"))
            with self.assertRaises(DurableExecutionError):
                durable.enqueue_submission({})

    def test_idempotency_conflict_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=RuntimeStore(Path(tmp)/"state.sqlite3")
            durable=DurableExecution(store)
            first=TaskContract("echo", {"operation":"echo","payload":{"message":"a"}}).submit(submission_id="T1",idempotency_key="K")
            durable.enqueue_submission(first)
            second=TaskContract("different", {"operation":"echo","payload":{"message":"b"}}).submit(submission_id="T2",idempotency_key="K")
            with self.assertRaises(DurableExecutionError): durable.enqueue_submission(second)

    def test_stale_fence_cannot_finalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=RuntimeStore(Path(tmp)/"state.sqlite3")
            durable=DurableExecution(store)
            sub=TaskContract("echo", {"operation":"echo","payload":{}}).submit(submission_id="T1",idempotency_key="K")
            durable.enqueue_submission(sub)
            claimed=durable.claim("T1")
            with self.assertRaises(DurableExecutionError): durable.finalize("T1", claimed["fence_token"]+1, "COMPLETED", report={})

if __name__ == "__main__": unittest.main()
