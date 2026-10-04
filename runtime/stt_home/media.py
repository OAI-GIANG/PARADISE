"""Native media generation adapters for PARADISE.

Provider APIs are implementation details; PARADISE owns the capability contract,
artifact storage, provenance and evidence boundary.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class MediaError(RuntimeError):
    pass


class OpenAIMediaProvider:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.image_model = os.getenv("PARADISE_IMAGE_MODEL", "gpt-image-2")
        self.video_model = os.getenv("PARADISE_VIDEO_MODEL", "sora-2")

    def _request(self, method: str, url: str, data: bytes | None = None, content_type: str = "application/json") -> dict[str, Any]:
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
        if not prompt.strip():
            raise MediaError("prompt_required")
        payload = json.dumps({"model": self.image_model, "prompt": prompt, "size": size, "quality": quality}).encode()
        result = self._request("POST", "https://api.openai.com/v1/images/generations", payload)
        data = result.get("data") or []
        if not data:
            raise MediaError("image_generation_empty")
        item = data[0]
        raw = item.get("b64_json")
        if not raw:
            raise MediaError("image_generation_missing_content")
        artifact_id = f"img_{uuid.uuid4().hex}"
        path = self.root / f"{artifact_id}.png"
        path.write_bytes(base64.b64decode(raw))
        return {"artifact_id": artifact_id, "type": "image", "path": str(path), "model": self.image_model, "prompt": prompt, "mime": "image/png"}

    def generate_video(self, prompt: str, seconds: str = "4", size: str = "1280x720") -> dict[str, Any]:
        if not prompt.strip():
            raise MediaError("prompt_required")
        boundary = "----PARADISE" + uuid.uuid4().hex
        fields = {"model": self.video_model, "prompt": prompt, "seconds": str(seconds), "size": size}
        chunks = []
        for key, value in fields.items():
            chunks += [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode()]
        chunks += [f"--{boundary}--\r\n".encode()]
        result = self._request("POST", "https://api.openai.com/v1/videos", b"".join(chunks), f"multipart/form-data; boundary={boundary}")
        return {"artifact_id": result["id"], "type": "video", "status": result.get("status", "queued"), "model": result.get("model", self.video_model), "prompt": prompt, "remote_id": result["id"]}

    def poll_video(self, remote_id: str, timeout_s: int = 180) -> dict[str, Any]:
        deadline = time.time() + min(max(timeout_s, 1), 600)
        while time.time() < deadline:
            result = self._request("GET", f"https://api.openai.com/v1/videos/{remote_id}")
            status = result.get("status")
            if status == "completed":
                return result
            if status in {"failed", "cancelled"}:
                raise MediaError(f"video_generation_{status}")
            time.sleep(3)
        raise MediaError("video_generation_timeout")

    def download_video(self, remote_id: str, artifact_id: str) -> dict[str, Any]:
        if not self.api_key:
            raise MediaError("media_provider_not_configured")
        req = urllib.request.Request(f"https://api.openai.com/v1/videos/{remote_id}/content", headers={"Authorization": f"Bearer {self.api_key}"})
        path = self.root / f"{artifact_id}.mp4"
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            raise MediaError(f"video_download_http_{exc.code}") from exc
        return {"path": str(path), "mime": "video/mp4"}
