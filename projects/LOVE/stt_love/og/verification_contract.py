"""Maker/checker and evidence-state contract shared by existing OG validators.

This module defines records only. It does not grant execution or promotion authority.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    INCOMPLETE = "INCOMPLETE"


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerificationRecord:
    subject: str
    maker_id: str
    maker_output_digest: str
    checker_id: str
    checker_result_digest: str
    independent: bool
    status: EvidenceStatus
    evidence_refs: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.subject.strip() or not self.maker_id.strip() or not self.checker_id.strip():
            raise ValueError("subject, maker_id and checker_id are required")
        if self.maker_id == self.checker_id:
            raise ValueError("maker and checker must be distinct")
        if not self.maker_output_digest or not self.checker_result_digest:
            raise ValueError("maker/checker digests are required")
        if self.status is EvidenceStatus.VERIFIED and not self.independent:
            raise ValueError("VERIFIED requires an independent checker")
        if self.status is EvidenceStatus.VERIFIED and not self.evidence_refs:
            raise ValueError("VERIFIED requires evidence_refs")

    @property
    def passed(self) -> bool:
        return self.status is EvidenceStatus.VERIFIED

    def to_dict(self) -> dict:
        return {
            "schema_version": "OG-VERIFICATION-1.0",
            "subject": self.subject,
            "maker_id": self.maker_id,
            "maker_output_digest": self.maker_output_digest,
            "checker_id": self.checker_id,
            "checker_result_digest": self.checker_result_digest,
            "independent": self.independent,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
        }

    def digest(self) -> str:
        return digest(self.to_dict())


def make_verification_record(
    *,
    subject: str,
    maker_id: str,
    maker_output: object,
    checker_id: str,
    checker_result: object,
    independent: bool,
    status: EvidenceStatus,
    evidence_refs: Iterable[str] = (),
    reason: str = "",
) -> VerificationRecord:
    return VerificationRecord(
        subject=subject,
        maker_id=maker_id,
        maker_output_digest=digest(maker_output),
        checker_id=checker_id,
        checker_result_digest=digest(checker_result),
        independent=independent,
        status=status,
        evidence_refs=tuple(str(x) for x in evidence_refs),
        reason=reason,
    )


@dataclass(frozen=True)
class EvidenceAlignment:
    """Compare expected and observed evidence without granting promotion authority."""
    subject: str
    expected: tuple[str, ...]
    observed: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    status: EvidenceStatus

    @classmethod
    def compare(cls, subject: str, expected: Iterable[str], observed: Iterable[str]):
        exp = tuple(dict.fromkeys(str(x) for x in expected if str(x).strip()))
        obs = tuple(dict.fromkeys(str(x) for x in observed if str(x).strip()))
        missing = tuple(x for x in exp if x not in obs)
        unexpected = tuple(x for x in obs if x not in exp)
        status = EvidenceStatus.NOT_RUN if not obs else (
            EvidenceStatus.INCOMPLETE if missing else EvidenceStatus.OBSERVED
        )
        return cls(subject, exp, obs, missing, unexpected, status)

    def to_dict(self) -> dict:
        return {
            "schema_version": "OG-EVIDENCE-ALIGNMENT-1.0",
            "subject": self.subject,
            "expected": list(self.expected),
            "observed": list(self.observed),
            "missing": list(self.missing),
            "unexpected": list(self.unexpected),
            "status": self.status.value,
        }
