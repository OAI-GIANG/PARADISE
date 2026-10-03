"""Source-to-OG convergence contracts inspired by the supplied Printing Press source.
They are deterministic records only: no source code is copied and no execution authority is added.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable

class ConvergenceStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    OBSERVED = "OBSERVED"
    ADOPTED = "ADOPTED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"

class DriftStatus(StrEnum):
    EXACT = "EXACT"
    DRIFT = "DRIFT"
    NOT_CHECKED = "NOT_CHECKED"

def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str).encode("utf-8")
    return sha256(raw).hexdigest()

def file_sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

@dataclass(frozen=True)
class CapabilityObservation:
    capability_id: str
    source_ref: str
    description: str
    status: ConvergenceStatus = ConvergenceStatus.CANDIDATE
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability_id.strip() or not self.source_ref.strip():
            raise ValueError("capability_id and source_ref are required")
        if not self.description.strip():
            raise ValueError("description is required")
@dataclass(frozen=True)
class SourceManifest:
    source_id: str
    source_kind: str
    source_sha256: str
    observations: tuple[CapabilityObservation, ...]
    adopted_capabilities: tuple[str, ...] = ()
    deferred_capabilities: tuple[str, ...] = ()
    rejected_capabilities: tuple[str, ...] = ()
    gap_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.source_kind.strip():
            raise ValueError("source identity is required")
        if len(self.source_sha256) != 64:
            raise ValueError("source_sha256 must be a SHA-256 digest")
        ids = {row.capability_id for row in self.observations}
        for name in (*self.adopted_capabilities, *self.deferred_capabilities, *self.rejected_capabilities):
            if name not in ids:
                raise ValueError(f"decision references unknown capability: {name}")
        decision_sets = [
            set(self.adopted_capabilities),
            set(self.deferred_capabilities),
            set(self.rejected_capabilities),
        ]
        if decision_sets[0] & decision_sets[1] or decision_sets[0] & decision_sets[2] or decision_sets[1] & decision_sets[2]:
            raise ValueError("capability decision categories must be disjoint")

    @property
    def manifest_digest(self) -> str:
        return digest(self.to_dict())
    def to_dict(self) -> dict:
        return {
            "schema_version": "OG-SOURCE-MANIFEST-1.0",
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "source_sha256": self.source_sha256,
            "observations": [
                {
                    "capability_id": x.capability_id,
                    "source_ref": x.source_ref,
                    "description": x.description,
                    "status": x.status.value,
                    "evidence_refs": list(x.evidence_refs),
                }
                for x in self.observations
            ],
            "adopted_capabilities": list(self.adopted_capabilities),
            "deferred_capabilities": list(self.deferred_capabilities),
            "rejected_capabilities": list(self.rejected_capabilities),
            "gap_notes": list(self.gap_notes),
        }

@dataclass(frozen=True)
class DerivedArtifact:
    artifact_id: str
    producer: str
    source_manifest_digest: str
    input_digest: str
    output_digest: str
    artifact_kind: str

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (
            self.artifact_id, self.producer, self.source_manifest_digest,
            self.input_digest, self.output_digest, self.artifact_kind
        )):
            raise ValueError("derived artifact identity fields are required")
    def to_dict(self) -> dict:
        return {
            "schema_version": "OG-DERIVED-ARTIFACT-1.0",
            "artifact_id": self.artifact_id,
            "producer": self.producer,
            "source_manifest_digest": self.source_manifest_digest,
            "input_digest": self.input_digest,
            "output_digest": self.output_digest,
            "artifact_kind": self.artifact_kind,
        }

@dataclass(frozen=True)
class DriftReport:
    status: DriftStatus
    expected_digest: str
    observed_digest: str
    artifact_id: str
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": "OG-DRIFT-1.0",
            "status": self.status.value,
            "expected_digest": self.expected_digest,
            "observed_digest": self.observed_digest,
            "artifact_id": self.artifact_id,
            "reason": self.reason,
        }

def check_drift(
    *,
    artifact_id: str,
    expected_digest: str,
    observed_digest: str | None,
) -> DriftReport:
    if not observed_digest:
        return DriftReport(
            DriftStatus.NOT_CHECKED, expected_digest, "",
            artifact_id, "observed digest unavailable",
        )
    status = DriftStatus.EXACT if observed_digest == expected_digest else DriftStatus.DRIFT
    return DriftReport(
        status, expected_digest, observed_digest, artifact_id,
        "digest match" if status is DriftStatus.EXACT else "derived artifact drift",
    )
