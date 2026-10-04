"""PARADISE media runtime: local/self-host first, paid providers opt-in only.

The runtime owns capability, policy, artifact provenance and fail-closed behavior.
A GPU worker is an implementation detail reached through a small JSON-over-stdio
contract. No paid provider is contacted unless explicitly enabled.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class MediaError(RuntimeError):
    pass


class LocalMediaWorker:
    """Invoke an authorized local/self-host worker through stdin/stdout JSON.

    Request: {"operation":"image.generate"|"video.generate", ...}
    Response: {"status":"COMPLETED", "artifact_path":"...", "mime":"...", ...}
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.command = os.getenv("PARADISE_MEDIA_WORKER_CMD", "").strip()
        self.timeout_s = min(max(int(os.getenv("PARADISE_MEDIA_WORKER_TIMEOUT", "600")), 5), 3600)

    @property
    def configured(self) -> bool:
        return bool(self.command)

    def _call(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.command:
            raise MediaError("local_media_worker_not_configured")
        try:
            proc = subprocess.run(
                self.command,
                input=json.dumps(request, ensure_ascii=False),
                text=True,
                capture_output=True,
                shell=True,
                cwd=self.root,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise MediaError("local_media_worker_timeout") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip()[:500]
            raise MediaError(f"local_media_worker_failed:{detail or proc.returncode}")
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise MediaError("local_media_worker_invalid_json") from exc
        if not isinstance(result, dict):
            raise MediaError("local_media_worker_invalid_response")
        return result

    def generate(self, operation: str, prompt: str, **options: Any) -> dict[str, Any]:
        if not prompt.strip():
            raise MediaError("prompt_required")
        result = self._call({"operation": operation, "prompt": prompt, **options})
        if result.get("status") not in {"COMPLETED", "QUEUED"}:
            raise MediaError("local_media_worker_invalid_status")
        if result.get("status") == "COMPLETED":
            artifact = result.get("artifact_path")
            if not artifact:
                raise MediaError("local_media_worker_missing_artifact")
            path = Path(str(artifact))
            if not path.is_absolute():
                path = (self.root / path).resolve()
            else:
                path = path.resolve()
            if not path.is_file():
                raise MediaError("local_media_worker_artifact_not_found")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result["artifact_path"] = str(path)
            result["sha256"] = digest
            result.setdefault("artifact_id", f"local_{uuid.uuid4().hex}")
        return result


class OpenAIMediaProvider:
    """Paid provider retained only as an explicitly authorized implementation detail."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.enabled = os.getenv("PARADISE_ALLOW_PAID_MEDIA", "0").lower() in {"1", "true", "yes", "on"}
        self.image_model = os.getenv("PARADISE_IMAGE_MODEL", "gpt-image-2")
        self.video_model = os.getenv("PARADISE_VIDEO_MODEL", "sora-2")

    def _request(self, method: str, url: str, data: bytes | None = None, content_type: str = "application/json") -> dict[str, Any]:
        if not self.enabled:
            raise MediaError("paid_media_not_authorized")
        if not self.api_key:
            raise MediaError("media_provider_not_configured")
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": content_type,
        })
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MediaError(f"media_provider_http_{exc.code}: {detail[:500]}") from exc
        except urllib.error.URLError as exc:
            raise MediaError(f"media_provider_network_error: {exc.reason}") from exc

    def generate_image(self, prompt: str, size: str = "1024x1024", quality: str = "auto") -> dict[str, Any]:
        payload = json.dumps({"model": self.image_model, "prompt": prompt, "size": size, "quality": quality}).encode()
        result = self._request("POST", "https://api.openai.com/v1/images/generations", payload)
        data = result.get("data") or []
        if not data or not data[0].get("b64_json"):
            raise MediaError("image_generation_missing_content")
        artifact_id = f"img_{uuid.uuid4().hex}"
        path = self.root / f"{artifact_id}.png"
        path.write_bytes(base64.b64decode(data[0]["b64_json"]))
        return {"artifact_id": artifact_id, "type": "image", "path": str(path), "model": self.image_model, "prompt": prompt, "mime": "image/png", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def media_policy() -> dict[str, Any]:
    worker = LocalMediaWorker(Path(os.getenv("PARADISE_MEDIA_ARTIFACT_ROOT", Path(__file__).resolve().parent / "media_artifacts")))
    paid = OpenAIMediaProvider(worker.root)
    return {
        "default_route": "local_self_host",
        "local_worker_configured": worker.configured,
        "paid_provider_authorized": paid.enabled,
        "paid_provider_requires_key": True,
        "fail_closed": True,
    }


def generate_local(root: Path, kind: str, prompt: str, **options: Any) -> dict[str, Any]:
    worker = LocalMediaWorker(root)
    operation = f"{kind}.generate"
    return worker.generate(operation, prompt, **options)
