"""Bounded user-facing capabilities for PARADISE STT Home.

No new semantic primitive is introduced here. This is an application capability
adapter over the existing governance/runtime boundary.
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any


class CapabilityError(ValueError):
    pass


class WorkspaceCapability:
    """Sandboxed project workspace with explicit, evidence-bound mutations."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, relative: str) -> Path:
        if not relative or relative in {".", "./"}:
            return self.root
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise CapabilityError("workspace_path_outside_root")
        return candidate

    def list(self, relative: str = ".") -> list[dict[str, Any]]:
        path = self._path(relative)
        if not path.is_dir():
            raise CapabilityError("workspace_directory_required")
        rows = []
        for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            rows.append({"name": item.name, "type": "directory" if item.is_dir() else "file", "size": item.stat().st_size if item.is_file() else None})
        return rows

    def read(self, relative: str, max_bytes: int = 256_000) -> dict[str, Any]:
        path = self._path(relative)
        if not path.is_file():
            raise CapabilityError("workspace_file_required")
        data = path.read_bytes()
        if len(data) > max_bytes:
            raise CapabilityError("workspace_file_too_large")
        return {"path": relative, "content": data.decode("utf-8"), "bytes": len(data)}

    def write(self, relative: str, content: str) -> dict[str, Any]:
        path = self._path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        if len(encoded) > 512_000:
            raise CapabilityError("workspace_write_too_large")
        path.write_bytes(encoded)
        return {"path": relative, "bytes": len(encoded)}

    def run(self, relative: str, args: list[str] | None = None, timeout_s: int = 20) -> dict[str, Any]:
        path = self._path(relative)
        if not path.is_file():
            raise CapabilityError("workspace_file_required")
        if path.suffix.lower() != ".py":
            raise CapabilityError("workspace_run_allows_python_only")
        timeout_s = max(1, min(int(timeout_s), 60))
        command = [os.environ.get("PYTHON", "python"), str(path), *(args or [])]
        try:
            proc = subprocess.run(command, cwd=self.root, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            return {"execution_id": str(uuid.uuid4()), "status": "TIMED_OUT", "stdout": exc.stdout or "", "stderr": exc.stderr or ""}
        return {"execution_id": str(uuid.uuid4()), "status": "COMPLETED" if proc.returncode == 0 else "FAILED", "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def capability_catalog() -> list[dict[str, Any]]:
    return [
        {"id": "code.workspace", "status": "implemented", "operations": ["list", "read", "write", "run_python"]},
        {"id": "media.image", "status": "implemented", "operations": ["generate", "artifact_preview"]},
        {"id": "media.video", "status": "implemented", "operations": ["generate", "job_poll", "artifact_preview"]},
        {"id": "document.text", "status": "partial", "operations": ["compose", "edit", "export"]},
        {"id": "language.natural", "status": "partial", "operations": ["chat", "continuity", "style"]},
        {"id": "plugin.integration", "status": "planned", "operations": ["discover", "authorize", "invoke", "observe", "revoke"]},
    ]
