"""Canonical model identity contract for the LOVE inference layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping


_REQUIRED_FIELDS = (
    "provider_id",
    "model_id",
    "model_version",
    "adapter_id",
    "adapter_version",
    "identity_source",
)


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Immutable identity of the model/provider path used by an inference request.

    ``identity_observed`` is deliberately explicit: configuration alone never
    establishes that a provider actually served the claimed model identity.
    """

    provider_id: str
    model_id: str
    model_version: str
    adapter_id: str
    adapter_version: str
    identity_source: str
    identity_observed: bool

    def __post_init__(self) -> None:
        for field in _REQUIRED_FIELDS:
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        if not isinstance(self.identity_observed, bool):
            raise TypeError("identity_observed must be bool")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical field representation."""
        return asdict(self)

    def canonical_bytes(self) -> bytes:
        """Return deterministic UTF-8 bytes for evidence/replay hashing."""
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def sha256(self) -> str:
        """Return the deterministic identity digest used by evidence binding."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelIdentity":
        """Construct an identity without accepting undeclared identity fields."""
        expected = set(_REQUIRED_FIELDS) | {"identity_observed"}
        actual = set(value)
        missing = expected - actual
        extra = actual - expected
        if missing:
            raise ValueError(f"missing model identity fields: {sorted(missing)}")
        if extra:
            raise ValueError(f"unexpected model identity fields: {sorted(extra)}")
        return cls(**{key: value[key] for key in expected})
