from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from paradise.server import ParadiseApplication, RuntimeConfig, create_server


class ParadiseRuntimeTests(unittest.TestCase):
    def _config(self, path: Path) -> RuntimeConfig:
        cfg = RuntimeConfig()
        cfg.api_token = "secret"
        cfg.data_path = path
        return cfg

    def test_authentication_is_required_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = ParadiseApplication(self._config(Path(tmp) / "state.sqlite3"))
            self.assertFalse(app.authenticate(None))
            self.assertTrue(app.authenticate("secret"))
            self.assertFalse(app.authenticate("wrong"))

    def test_idempotent_task_is_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            app = ParadiseApplication(self._config(path))
            first = app.submit({"operation": "echo", "payload": {"message": "hello"}, "idempotency_key": "K1"})
            second = app.submit({"operation": "echo", "payload": {"message": "different"}, "idempotency_key": "K1"})
            self.assertEqual(first["task_id"], second["task_id"])
            self.assertEqual(first["result"]["echo"], "hello")

    def test_restart_recovers_durable_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            app1 = ParadiseApplication(self._config(path))
            first = app1.submit({"operation": "echo", "payload": {"message": "survive"}, "idempotency_key": "restart-1"})
            self.assertEqual(first["status"], "SUCCEEDED")
            app2 = ParadiseApplication(self._config(path))
            recovered = app2.store.get_task(first["task_id"])
            self.assertIsNotNone(recovered)
            self.assertEqual(recovered["status"], "SUCCEEDED")
            self.assertEqual(recovered["result"]["echo"], "survive")

    def test_unsupported_operation_is_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = ParadiseApplication(self._config(Path(tmp) / "state.sqlite3"))
            task = app.submit({"operation": "shell", "payload": {}, "idempotency_key": "K2"})
            self.assertEqual(task["status"], "FAILED")
            self.assertIn("unsupported operation", task["error"])

    def test_http_health_and_authenticated_task_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._config(Path(tmp) / "state.sqlite3")
            cfg.host = "127.0.0.1"
            cfg.port = 0
            server = create_server(cfg)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request("GET", "/healthz")
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["status"], "ok")

                conn.request("GET", "/v1/status")
                response = conn.getresponse()
                self.assertEqual(response.status, 401)
                response.read()

                body = json.dumps({
                    "task_id": "T-HTTP",
                    "operation": "echo",
                    "payload": {"message": "runtime works"},
                    "idempotency_key": "T-HTTP",
                })
                conn.request("POST", "/v1/tasks", body=body, headers={
                    "Authorization": "Bearer secret",
                    "Content-Type": "application/json",
                })
                response = conn.getresponse()
                data = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(data["status"], "SUCCEEDED")
                self.assertEqual(data["result"]["echo"], "runtime works")
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
