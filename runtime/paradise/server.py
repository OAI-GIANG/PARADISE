from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import sys
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .store import RuntimeStore


VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "runtime" / "data" / "paradise.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class RuntimeConfig:
    def __init__(self) -> None:
        self.host = os.getenv("PARADISE_HOST", "127.0.0.1")
        self.port = int(os.getenv("PARADISE_PORT", "8787"))
        self.api_token = os.getenv("PARADISE_API_TOKEN", "")
        self.allow_anonymous = env_bool("PARADISE_ALLOW_ANONYMOUS", False)
        self.data_path = Path(os.getenv("PARADISE_DATA", str(DEFAULT_DATA))).resolve()
        self.commit = os.getenv("PARADISE_COMMIT", "unknown")
        self.tree = os.getenv("PARADISE_TREE_SHA", "unknown")
        self.environment = os.getenv("PARADISE_ENV", "local")

    def validate(self) -> None:
        if self.port < 0 or self.port > 65535:
            raise ValueError("PARADISE_PORT must be 0..65535")
        if not self.allow_anonymous and not self.api_token:
            raise ValueError("PARADISE_API_TOKEN is required unless anonymous mode is explicitly enabled")


class ParadiseApplication:
    """Bounded runtime application around the existing PARADISE kernel contracts."""

    def __init__(self, config: RuntimeConfig):
        config.validate()
        self.config = config
        self.store = RuntimeStore(config.data_path)
        self.store.set_meta("version", VERSION)
        self.store.set_meta("commit", config.commit)
        self.store.set_meta("tree", config.tree)
        self.store.set_meta("started_at", utc_now())

    def authenticate(self, token: str | None) -> bool:
        if self.config.allow_anonymous:
            return True
        if not token or not self.config.api_token:
            return False
        return secrets.compare_digest(token, self.config.api_token)

    def status(self) -> dict[str, Any]:
        return {
            "name": "PARADISE",
            "version": VERSION,
            "status": "RUNNING",
            "host": socket.gethostname(),
            "commit": self.config.commit,
            "tree": self.config.tree,
            "environment": self.config.environment,
            "data_path": str(self.config.data_path),
            "started_at": self.store.get_meta("started_at"),
            "operations": ["echo"],
        }

    def execute(self, task_id: str, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation != "echo":
            raise ValueError("unsupported operation; allowed operations: echo")
        message = payload.get("message")
        if not isinstance(message, str):
            raise ValueError("echo requires string payload.message")
        if len(message) > 10000:
            raise ValueError("payload.message exceeds 10000 characters")
        return {"echo": message, "task_id": task_id}

    def submit(self, body: dict[str, Any]) -> dict[str, Any]:
        task_id = str(body.get("task_id") or f"TASK-{uuid.uuid4().hex}")
        operation = str(body.get("operation") or "").strip().lower()
        payload = body.get("payload")
        idempotency_key = str(body.get("idempotency_key") or task_id)
        if not operation:
            raise ValueError("operation is required")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if len(idempotency_key) > 200:
            raise ValueError("idempotency_key too long")
        now = utc_now()
        task = self.store.create_task(task_id, operation, body, idempotency_key, now)
        if task["status"] == "SUCCEEDED":
            return task
        self.store.add_event(task_id, "TASK_RECEIVED", {"operation": operation}, now)
        self.store.update_task(task_id, "RUNNING", utc_now())
        try:
            result = self.execute(task_id, operation, payload)
        except Exception as exc:
            self.store.update_task(task_id, "FAILED", utc_now(), error=str(exc))
            self.store.add_event(task_id, "TASK_FAILED", {"error": str(exc)}, utc_now())
            return self.store.get_task(task_id) or {}
        self.store.update_task(task_id, "SUCCEEDED", utc_now(), result=result)
        self.store.add_event(task_id, "TASK_SUCCEEDED", result, utc_now())
        return self.store.get_task(task_id) or {}


class Handler(BaseHTTPRequestHandler):
    server_version = "PARADISE/0.1"

    @property
    def app(self) -> ParadiseApplication:
        return self.server.app  # type: ignore[attr-defined]

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _authorized(self) -> bool:
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else None
        return self.app.authenticate(token)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 256 * 1024:
            raise ValueError("request body must be 1..262144 bytes")
        raw = self.rfile.read(length)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json(HTTPStatus.OK, {"status": "ok", "version": VERSION})
            return
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if self.path == "/v1/status":
            self._json(HTTPStatus.OK, self.app.status())
            return
        if self.path.startswith("/v1/tasks/"):
            task_id = self.path.rsplit("/", 1)[-1]
            task = self.app.store.get_task(task_id)
            if task is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "task not found"})
            else:
                self._json(HTTPStatus.OK, task)
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return
        if self.path != "/v1/tasks":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            task = self.app.submit(self._body())
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        status = HTTPStatus.OK if task.get("status") == "SUCCEEDED" else HTTPStatus.UNPROCESSABLE_ENTITY
        self._json(status, task)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("PARADISE " + (format % args) + "\n")


def create_server(config: RuntimeConfig | None = None) -> ThreadingHTTPServer:
    config = config or RuntimeConfig()
    app = ParadiseApplication(config)
    server = ThreadingHTTPServer((config.host, config.port), Handler)
    server.app = app  # type: ignore[attr-defined]
    return server


def main() -> int:
    config = RuntimeConfig()
    server = create_server(config)
    print(f"PARADISE {VERSION} listening on http://{config.host}:{config.port}")
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
