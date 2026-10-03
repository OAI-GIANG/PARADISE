from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from statistics import mean
from typing import Any, Iterable

from .qualification import is_routing_eligible


def select_provider_from_performance(
    capability_id: str,
    fallback: str,
    observations: Iterable[dict[str, Any]],
    *,
    max_age_days: int = 30,
    risk_class: str = "LOW",
    task_constraints: Iterable[str] = (),
) -> dict[str, Any]:
    """Select only from G7-qualified, fresh performance records."""
    if not capability_id.strip() or not fallback.strip():
        raise ValueError("capability_id and fallback are required")
    if max_age_days <= 0:
        raise ValueError("max_age_days must be positive")
    constraints = tuple(sorted({
        str(value).strip().lower()
        for value in task_constraints
        if str(value).strip()
    }))
    rows = [
        row
        for row in observations
        if is_routing_eligible(
            row,
            capability_id=capability_id,
            risk_class=risk_class,
            max_age_days=max_age_days,
        )
    ]
    if not rows:
        return {
            "provider": fallback,
            "basis": "registry_fallback",
            "observations_considered": 0,
        }
    def provider_fit(row: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
        profile = row.get("task_profile") or {}
        reasons: list[str] = []
        score = 0
        for constraint in constraints:
            if constraint.startswith("task_family:"):
                wanted = constraint.split(":", 1)[1]
                actual = str(profile.get("task_family", row.get("task_family", ""))).lower()
                if actual == wanted:
                    score += 10
                    reasons.append("task_family_match")
            elif constraint.startswith("tool:"):
                wanted = constraint.split(":", 1)[1]
                tools = {
                    str(item).lower()
                    for item in (profile.get("supported_tools") or row.get("supported_tools") or ())
                }
                if wanted in tools:
                    score += 8
                    reasons.append("tool_match")
            elif constraint.startswith("environment:"):
                wanted = constraint.split(":", 1)[1]
                actual = str(profile.get("environment_class", row.get("environment_class", ""))).lower()
                if actual == wanted:
                    score += 8
                    reasons.append("environment_match")
            elif constraint.startswith("side_effect:"):
                wanted = constraint.split(":", 1)[1]
                actual = str(profile.get("side_effect_class", row.get("side_effect_class", ""))).lower()
                if actual == wanted:
                    score += 8
                    reasons.append("side_effect_match")
            elif constraint in {"low_latency", "latency_low"}:
                latency = float(row["metrics"].get("latency_ms_p95", float("inf")))
                if latency < float("inf"):
                    score += max(1, 7 - min(6, int(latency // 100)))
                    reasons.append("latency_fit")
        return score, tuple(sorted(set(reasons)))

    ranked = []
    for row in rows:
        fit_score, fit_reasons = provider_fit(row)
        ranked.append((fit_score, fit_reasons, row))
    ranked.sort(
        key=lambda item: (
            -item[0],
            -float(item[2]["metrics"]["success_rate"]),
            float(item[2]["metrics"].get("latency_ms_p95", float("inf"))),
            str(item[2].get("provider_id", "")),
        )
    )
    winner_fit_score, winner_fit_reasons, winner = ranked[0]
    qualification = winner.get("qualification") or {}
    return {
        "provider": str(winner["provider_id"]),
        "basis": "qualified_provider_performance",
        "observations_considered": len(rows),
        "fit_score": winner_fit_score,
        "fit_reasons": list(winner_fit_reasons),
        "task_constraints": list(constraints),
        "success_rate": float(winner["metrics"]["success_rate"]),
        "latency_ms_p95": float(winner["metrics"].get("latency_ms_p95", float("inf"))),
        "source_commit": winner.get("evidence", {}).get("source_commit"),
        "evidence_refs": list(winner.get("evidence", {}).get("evidence_refs", [])),
        "qualification_id": qualification.get("qualification_id"),
        "cohort_id": qualification.get("cohort_id"),
        "qualification": qualification.get("qualification"),
    }




def compute_metrics(tasks: list[dict], publications: list[dict]) -> dict[str, Any]:
    completed = [t for t in tasks if t.get("state") == "COMPLETED"]
    failed = [t for t in tasks if t.get("state") == "FAILED"]
    async_tasks = [t for t in tasks if t.get("async")]
    recovered = [t for t in async_tasks if int(t.get("recovery_count", 0)) > 0]
    artifacts = []
    durations = []
    commands = Counter()
    for task in completed:
        report = task.get("report", {})
        result = report.get("result", {})
        commands[str(result.get("selected_command", "unknown"))] += 1
        for item in result.get("results", []):
            if item.get("artifact"):
                artifacts.append(item["artifact"])
            if isinstance(item.get("duration_ms"), (int, float)):
                durations.append(float(item["duration_ms"]))
    verified = [a for a in artifacts if a.get("validation") == "VERIFIED"]
    return {
        "tasks_total": len(tasks),
        "tasks_completed": len(completed),
        "tasks_failed": len(failed),
        "async_total": len(async_tasks),
        "async_recovered": len(recovered),
        "media_artifacts_verified": len(verified),
        "publications": len(publications),
        "verified_media_publish_rate": (len(publications) / len(verified)) if verified else 0.0,
        "avg_observed_duration_ms": mean(durations) if durations else 0.0,
        "commands_observed": dict(commands),
    }
def compute_learning(tasks: list[dict], publications: list[dict], metrics: dict[str, Any]) -> dict[str, Any]:
    verified = metrics["media_artifacts_verified"]
    observations = []
    recommendations = []
    if verified:
        observations.append("verified_media_generation_is_repeatable")
    if metrics["publications"] < verified:
        observations.append("verified_media_exists_beyond_publication_count")
        recommendations.append("publish_latest_verified_media")
    pending_recovery = [
        t for t in tasks
        if t.get("async") and t.get("state") == "RECOVERY_PENDING"
    ]
    if pending_recovery:
        observations.append("recovery_pending_tasks_exist")
        recommendations.append("recover_one_pending_task")
    if metrics["tasks_failed"] == 0 and metrics["tasks_completed"] > 0:
        observations.append("observed_task_success_without_failure")
    return {
        "schema_version": "LOVE-LEARNING-1.0",
        "observed_only": True,
        "observations": observations,
        "recommendations": recommendations,
        "metrics_digest": sha256(repr(sorted(metrics.items())).encode()).hexdigest(),
        "bounded_next_actions": recommendations[:1],
    }


def build_knowledge_hint(learning: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    """Bounded, observational knowledge hint for the next cognition turn.

    It is derived only from observed metrics/learning and carries
    ``authority: none``: it can inform a later decision but never authorizes or
    promotes anything by itself.
    """
    observations = [str(x) for x in (learning.get("observations") or [])][:8]
    recommendations = [str(x) for x in (learning.get("recommendations") or [])][:4]
    return {
        "schema_version": "LOVE-KNOWLEDGE-HINT-1.0",
        "observed_only": True,
        "authority": "none",
        "observations": observations,
        "recommendations": recommendations,
        "metrics_digest": learning.get("metrics_digest"),
        "tasks_completed": int(metrics.get("tasks_completed", 0) or 0),
        "tasks_failed": int(metrics.get("tasks_failed", 0) or 0),
        "content": "; ".join(observations + recommendations)[:500],
    }


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(float(ordered[0]), 3)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(float(ordered[lower] + (ordered[upper] - ordered[lower]) * weight), 3)


def compute_provider_performance_memory(
    tasks: list[dict],
    *,
    capability_id: str = "reasoning",
    provider_id: str = "deepseek.model",
    model_id: str | None = None,
    source_commit: str = "UNDECLARED",
    source_tree_sha: str | None = None,
) -> dict[str, Any] | None:
    """Build one provider-performance record from observed model-backed tasks.

    The output follows docs/contracts/provider_performance_memory.schema.json and
    is strictly observational: it never promotes a provider or a capability, and
    it returns ``None`` when no model-backed sample exists.
    """
    samples: list[dict[str, Any]] = []
    for task in tasks:
        result = task.get("report", {}).get("result", {})
        if not isinstance(result, dict):
            continue
        model = result.get("model")
        if not model:
            continue
        if model_id and model != model_id:
            continue
        success = task.get("state") == "COMPLETED" and bool(result.get("success"))
        latency = result.get("model_latency_ms")
        failure_code = None
        if not success:
            error = task.get("error")
            failure_code = (
                str(error.get("type"))
                if isinstance(error, dict) and error.get("type")
                else "task_failed"
            )
        samples.append(
            {
                "task_id": task.get("id"),
                "model": model,
                "success": success,
                "latency": float(latency) if isinstance(latency, (int, float)) else None,
                "failure_code": failure_code,
                "observed_at": str(task.get("created_at") or task.get("updated_at") or ""),
            }
        )
    if not samples:
        return None

    effective_model = model_id or str(samples[-1]["model"])
    total = len(samples)
    successes = sum(1 for sample in samples if sample["success"])
    failures = total - successes
    latencies = [sample["latency"] for sample in samples if sample["latency"] is not None]
    failure_modes = Counter(
        sample["failure_code"] for sample in samples if sample["failure_code"]
    )
    evidence_refs = [str(sample["task_id"]) for sample in samples if sample["task_id"]]
    observed = [sample["observed_at"] for sample in samples if sample["observed_at"]]

    return {
        "record_id": "PPM-"
        + sha256(
            repr([capability_id, provider_id, effective_model, evidence_refs]).encode("utf-8")
        ).hexdigest()[:24],
        "capability_id": capability_id,
        "provider_id": provider_id,
        "model_id": effective_model,
        "observation_window": {
            "start": min(observed) if observed else "",
            "end": max(observed) if observed else "",
            "sample_count": total,
        },
        "metrics": {
            "success_rate": round(successes / total, 6),
            "failure_rate": round(failures / total, 6),
            "latency_ms_p50": _percentile(latencies, 0.50),
            "latency_ms_p95": _percentile(latencies, 0.95),
        },
        "failure_modes": [
            {"code": code, "count": count} for code, count in sorted(failure_modes.items())
        ],
        "evidence": {
            "source_commit": source_commit,
            "source_tree_sha": source_tree_sha,
            "evidence_refs": evidence_refs,
        },
    }
