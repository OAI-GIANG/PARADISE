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
from capabilities import WorkspaceCapability, capability_catalog
from media import MediaError, OpenAIMediaProvider

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
WORKSPACE = Path(os.getenv("PARADISE_HOME_WORKSPACE", BASE / "workspace")).resolve()
PORT = int(os.getenv("PARADISE_HOME_PORT", "8787"))
HOST = os.getenv("PARADISE_HOME_HOST", "127.0.0.1")
REQUIRE_AUTH = os.getenv("PARADISE_HOME_REQUIRE_AUTH", "0") == "1"
API_TOKEN = os.getenv("PARADISE_HOME_API_TOKEN")
if REQUIRE_AUTH and not API_TOKEN:
    raise RuntimeError("PARADISE_HOME_API_TOKEN is required when PARADISE_HOME_REQUIRE_AUTH=1")


class Handler(BaseHTTPRequestHandler):
    home = STTHome()
    workspace = WorkspaceCapability(WORKSPACE)
    media_root = BASE / "media_artifacts"
    media = OpenAIMediaProvider(media_root)

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not REQUIRE_AUTH:
            return True
        value = self.headers.get("Authorization", "")
        return value == f"Bearer {API_TOKEN}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "authentication required"})
        return False

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json(HTTPStatus.OK, self.home.health())
        if path == "/api/state":
            if not self._require_auth(): return
            return self._json(HTTPStatus.OK, self.home.store.snapshot())
        if path == "/api/capabilities":
            if not self._require_auth(): return
            return self._json(HTTPStatus.OK, {"capabilities": capability_catalog()})
        if path == "/api/workspace/list":
            if not self._require_auth(): return
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            return self._json(HTTPStatus.OK, {"items": self.workspace.list(q.get("path", ["."])[0])})
        if path == "/api/workspace/read":
            if not self._require_auth(): return
            from urllib.parse import parse_qs
            q = parse_qs(urlparse(self.path).query)
            return self._json(HTTPStatus.OK, self.workspace.read(q.get("path", [""])[0]))
        if path == "/api/events":
            if not self._require_auth(): return
            rows = self.home.store.conn.execute(
                "SELECT * FROM events ORDER BY sequence DESC LIMIT 50"
            ).fetchall()
            return self._json(HTTPStatus.OK, {"events": [dict(r) for r in rows]})
        if path.startswith("/api/session/"):
            if not self._require_auth(): return
            sid = path.rsplit("/", 1)[-1]
            return self._json(HTTPStatus.OK, {
                "session_id": sid,
                "messages": self.home.store.recent_messages(sid, 60),
            })
        if path.startswith("/api/media/"):
            if not self._require_auth(): return
            name = path.rsplit("/", 1)[-1]
            candidate = (Handler.media_root / name).resolve()
            if Handler.media_root.resolve() not in candidate.parents or not candidate.is_file():
                return self._json(HTTPStatus.NOT_FOUND, {"error": "media_not_found"})
            data = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "private, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
            return
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
        if not self._require_auth():
            return
        try:
            payload = self._body()
            if path == "/api/workspace/write":
                if not payload.get("confirm"):
                    return self._json(HTTPStatus.CONFLICT, {"error": "explicit confirmation required"})
                result = self.workspace.write(str(payload.get("path", "")), str(payload.get("content", "")))
                result["evidence_id"] = self.home.store.record_event("WORKSPACE_WRITE", result["path"], {"bytes": result["bytes"]})
                return self._json(HTTPStatus.CREATED, result)
            if path == "/api/workspace/run":
                if not payload.get("confirm"):
                    return self._json(HTTPStatus.CONFLICT, {"error": "explicit confirmation required"})
                result = self.workspace.run(str(payload.get("path", "")), payload.get("args") or [], int(payload.get("timeout_s", 20)))
                result["evidence_id"] = self.home.store.record_event("WORKSPACE_RUN", str(payload.get("path", "")), {"status": result["status"], "execution_id": result["execution_id"]})
                return self._json(HTTPStatus.OK, result)
            if path == "/api/session":
                sid = self.home.store.create_session()
                return self._json(HTTPStatus.CREATED, {"session_id": sid})
            if path == "/api/chat":
                sid = str(payload.get("session_id") or self.home.store.create_session())
                result = self.home.chat(sid, str(payload.get("message", "")))
                return self._json(HTTPStatus.OK, result)
            if path == "/api/media/image":
                result = self.media.generate_image(
                    str(payload.get("prompt", "")),
                    str(payload.get("size", "1024x1024")),
                    str(payload.get("quality", "auto")),
                )
                result["url"] = "/api/media/" + Path(result["path"]).name
                result["evidence_id"] = self.home.store.record_event("MEDIA_IMAGE_GENERATION", result["artifact_id"], {"provider": "openai", "model": result["model"], "prompt": result["prompt"]})
                return self._json(HTTPStatus.CREATED, result)
            if path == "/api/media/video":
                result = self.media.generate_video(
                    str(payload.get("prompt", "")),
                    str(payload.get("seconds", "4")),
                    str(payload.get("size", "1280x720")),
                )
                if payload.get("wait", False):
                    final = self.media.poll_video(result["remote_id"], int(payload.get("timeout_s", 180)))
                    downloaded = self.media.download_video(result["remote_id"], result["artifact_id"])
                    result.update(final)
                    result.update(downloaded)
                    result["url"] = "/api/media/" + Path(downloaded["path"]).name
                result["evidence_id"] = self.home.store.record_event("MEDIA_VIDEO_GENERATION", result["artifact_id"], {"provider": "openai", "model": result["model"], "prompt": result["prompt"], "status": result.get("status")})
                return self._json(HTTPStatus.ACCEPTED if result.get("status") != "completed" else HTTPStatus.CREATED, result)
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
