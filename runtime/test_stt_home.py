from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
SERVER = HERE / "stt_home" / "server.py"
PORT = 18788
TOKEN = "test-home-token"


def request_json(url: str, payload=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload or {}).encode() if payload is not None else None
    req = Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urlopen(req, timeout=3) as r:
            return r.status, json.loads(r.read().decode())
    except HTTPError as exc:
        body = json.loads(exc.read().decode())
        return exc.code, body


class STTHomeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "home.sqlite3"
        env = os.environ.copy()
        env.update({
            "PARADISE_HOME_DATA": str(self.db),
            "PARADISE_HOME_PORT": str(PORT),
            "PARADISE_HOME_HOST": "127.0.0.1",
            "PARADISE_HOME_REQUIRE_AUTH": "1",
            "PARADISE_HOME_API_TOKEN": TOKEN,
        })
        self.proc = subprocess.Popen([sys.executable, str(SERVER)], cwd=str(HERE / "stt_home"), env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                request_json(f"http://127.0.0.1:{PORT}/api/health")
                break
            except Exception:
                time.sleep(0.05)
        else:
            self.tearDown()
            raise RuntimeError("server did not become ready")

    def tearDown(self):
        if getattr(self, "proc", None) and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "tmp", None):
            self.tmp.cleanup()

    def test_health_is_public_but_state_requires_auth(self):
        status, health = request_json(f"http://127.0.0.1:{PORT}/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["home"], "PARADISE")
        status, body = request_json(f"http://127.0.0.1:{PORT}/api/state")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "authentication required")
        status, state = request_json(f"http://127.0.0.1:{PORT}/api/state", token=TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(state["identity"]["home"], "PARADISE")

    def test_session_chat_memory_and_evidence(self):
        _, created = request_json(f"http://127.0.0.1:{PORT}/api/session", {}, TOKEN)
        sid = created["session_id"]
        _, chat = request_json(f"http://127.0.0.1:{PORT}/api/chat", {"session_id": sid, "message": "hello"}, TOKEN)
        self.assertTrue(chat["evidence_id"])
        _, mem = request_json(f"http://127.0.0.1:{PORT}/api/memory", {"content": "PARADISE is home", "trust": "verified"}, TOKEN)
        self.assertTrue(mem["memory_id"])
        _, session = request_json(f"http://127.0.0.1:{PORT}/api/session/{sid}", token=TOKEN)
        self.assertEqual(len(session["messages"]), 2)
        _, state = request_json(f"http://127.0.0.1:{PORT}/api/state", token=TOKEN)
        self.assertGreaterEqual(state["evidence_count"], 4)

    def test_invalid_task_transition_is_rejected(self):
        _, task = request_json(f"http://127.0.0.1:{PORT}/api/task", {"title": "bounded"}, TOKEN)
        result = request_json(f"http://127.0.0.1:{PORT}/api/task/transition",
                              {"task_id": task["task_id"], "expected_status": "CREATED", "new_status": "COMPLETED"}, TOKEN)
        self.assertEqual(result[0], 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
