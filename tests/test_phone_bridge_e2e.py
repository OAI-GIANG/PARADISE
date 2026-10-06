from __future__ import annotations

import concurrent.futures
import tempfile
import time
import uuid
from pathlib import Path

from phone_bridge.bridge import GateOutcome
from runtime.paradise.server import ParadiseApplication, RuntimeConfig


def make_config(db: Path) -> RuntimeConfig:
    c = RuntimeConfig()
    c.api_token = "T"
    c.data_path = db
    c.commit = "phone-bridge-e2e"
    c.tree = "test-tree"
    c.environment = "test"
    return c


def request(*, request_id=None, nonce=None, operation="echo"):
    return {
        "protocol_version": "1.1",
        "request_id": request_id or str(uuid.uuid4()),
        "operation": operation,
        "timestamp": int(time.time()),
        "nonce": nonce or str(uuid.uuid4()),
        "payload": {"message": "hello"},
    }


def test_phone_bridge_end_to_end_persistence_and_governance():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "bridge.db"
        app = ParadiseApplication(make_config(db))
        raw = request()

        first = app.handle_phone_bridge(raw, "T")
        assert first.status == "SUBMITTED"
        assert first.payload["evidence_id"].startswith("EVD-")

        duplicate = app.handle_phone_bridge(raw, "T")
        assert duplicate.error["code"] == "REQUEST_REPLAYED"

        restarted = ParadiseApplication(make_config(db))
        assert restarted.handle_phone_bridge(raw, "T").error["code"] == "REQUEST_REPLAYED"

        unauthorized = app.handle_phone_bridge(request(), "wrong")
        assert unauthorized.error["code"] == "AUTHENTICATION_FAILED"

        denied = app.handle_phone_bridge(request(operation="unsupported"), "T")
        assert denied.error["code"] == "AUTHORIZATION_DENY"

        task = app.store.get_task(raw["request_id"])
        assert task["state"] == "COMPLETED"
        assert task["attempt_no"] == 1
        assert app.cognitive.verify_replay(raw["request_id"])


def test_phone_bridge_concurrent_same_submission_executes_once():
    with tempfile.TemporaryDirectory() as td:
        app = ParadiseApplication(make_config(Path(td) / "bridge.db"))
        request_id = str(uuid.uuid4())

        def invoke(i):
            return app.handle_phone_bridge(
                request(request_id=request_id, nonce=f"nonce-{i}"), "T"
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(invoke, range(8)))

        assert all(result.status == "SUBMITTED" for result in results)
        task = app.store.get_task(request_id)
        assert task["state"] == "COMPLETED"
        assert task["attempt_no"] == 1


def test_phone_bridge_raw_ingress_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        app = ParadiseApplication(make_config(Path(td) / "bridge.db"))
        malformed = request()
        malformed.pop("nonce")
        result = app.handle_phone_bridge(malformed, "T")
        assert result.error["code"] == "REQUEST_SCHEMA_INVALID"
