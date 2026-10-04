"""Local PARADISE STT Home server. Standard library only."""
from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from core import STTHome

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
PORT = int(os.getenv("PARADISE_HOME_PORT", "8787"))
HOST = os.getenv("PARADISE_HOME_HOST", "127.0.0.1")


class Handler(BaseHTTPRequestHandler):
    home = STTHome()

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json(HTTPStatus.OK, self.home.health())
        if path == "/api/state":
            return self._json(HTTPStatus.OK, self.home.store.snapshot())
        if path == "/api/events":
            rows = self.home.store.conn.execute(
                "SELECT * FROM events ORDER BY sequence DESC LIMIT 50"
            ).fetchall()
            return self._json(HTTPStatus.OK, {"events": [dict(r) for r in rows]})
        if path.startswith("/api/session/"):
            sid = path.rsplit("/", 1)[-1]
            return self._json(HTTPStatus.OK, {
                "session_id": sid,
                "messages": self.home.store.recent_messages(sid, 60),
            })
        return self._static(path)

    def _static(self, path: str) -> None:
        rel = "index.html" if path in {"", "/"} else path.lstrip("/")
        candidate = (STATIC / rel).resolve()
        if STATIC not in candidate.parents and candidate != STATIC:
            return self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
        if not candidate.is_file():
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        data = candidate.read_bytes()
        ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._body()
            if path == "/api/session":
                sid = self.home.store.create_session()
                return self._json(HTTPStatus.CREATED, {"session_id": sid})
            if path == "/api/chat":
                sid = str(payload.get("session_id") or self.home.store.create_session())
                result = self.home.chat(sid, str(payload.get("message", "")))
                return self._json(HTTPStatus.OK, result)
            if path == "/api/memory":
                mid = self.home.remember(
                    str(payload.get("content", "")),
                    str(payload.get("kind", "experience")),
                    str(payload.get("trust", "unverified")),
                    str(payload.get("provenance", "user")),
                )
                return self._json(HTTPStatus.CREATED, {"memory_id": mid})
            if path == "/api/task":
                tid = self.home.store.create_task(
                    str(payload.get("title", "")),
                    payload.get("mission_id") or self.home.mission_id,
                )
                return self._json(HTTPStatus.CREATED, {"task_id": tid})
            if path == "/api/task/transition":
                ok = self.home.store.transition_task(
                    str(payload.get("task_id", "")),
                    str(payload.get("expected_status", "")),
                    str(payload.get("new_status", "")),
                )
                return self._json(HTTPStatus.OK if ok else HTTPStatus.CONFLICT, {"ok": ok})
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except ValueError as exc:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": type(exc).__name__ + ": " + str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"PARADISE STT HOME listening on http://{HOST}:{PORT}")
    print(f"database={Handler.home.store.db_path}")
    print(f"provider={Handler.home.provider.name}/{Handler.home.provider.model}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        Handler.home.store.close()


if __name__ == "__main__":
    main()
