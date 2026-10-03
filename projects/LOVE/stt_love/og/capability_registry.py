"""Canonical OG capability registry loader.

The JSON registry is the canonical declaration; this module exposes a
small typed/read-only interface to the router and runtime boundary.
"""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"

@dataclass(frozen=True)
class Capability:
    name: str
    provider: str

class CapabilityRegistry:
    def __init__(self, path: Path = REGISTRY_PATH) -> None:
        self.path = path
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
        self.status = payload["status"]
        self.owner = payload["owner"]
        self.capabilities = {
            name: Capability(name, payload["providers"].get(name, "UNMAPPED"))
            for name in payload["capabilities"]
        }
        self.commands = {
            item["command"].lstrip("/"): item["capability"]
            for item in payload["commands"]
        }

    def capability_for(self, command: str) -> Capability:
        key = command.lstrip("/")
        if key not in self.commands:
            raise KeyError(f"Unknown OG command: /{key}")
        capability = self.commands[key]
        return self.capabilities[capability]

    def validate(self) -> list[str]:
        errors: list[str] = []
        for command, capability in self.commands.items():
            if capability not in self.capabilities:
                errors.append(f"/{command}: missing capability {capability}")
            elif self.capabilities[capability].provider == "UNMAPPED":
                errors.append(f"{capability}: unmapped provider")
        return errors
