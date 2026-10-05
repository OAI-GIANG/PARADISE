"""Provider-performance qualification predicate used by LOVE learning."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any


def is_routing_eligible(
    row: dict[str, Any],
    *,
    capability_id: str,
    risk_class: str,
    max_age_days: int,
) -> bool:
    if str(row.get("capability_id", "")) != capability_id:
        return False
    qualification = row.get("qualification") or {}
    if qualification.get("qualification") not in {"G7", "QUALIFIED", "VERIFIED"}:
        return False
    if str(row.get("risk_class", "LOW")).upper() != str(risk_class).upper():
        return False
    evidence = row.get("evidence") or {}
    if not evidence.get("source_commit") or not evidence.get("evidence_refs"):
        return False
    observed = row.get("observed_at") or row.get("created_at")
    if not observed:
        return False
    try:
        dt = datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    age = datetime.now(timezone.utc) - dt
    if age.days > max_age_days:
        return False
    metrics = row.get("metrics") or {}
    try:
        success_rate = float(metrics["success_rate"])
    except (KeyError, TypeError, ValueError):
        return False
    return 0.0 <= success_rate <= 1.0
