from dataclasses import dataclass
from dataclasses import dataclass
from typing import Any, Iterable
import re

from ..learning import select_provider_from_performance
from ..og.capability_registry import CapabilityRegistry

@dataclass(frozen=True)
class TaskProfile:
    goal: str
    risk: str = "LOW"
    constraints: tuple[str, ...] = ()

@dataclass(frozen=True)
class CapabilitySelection:
    command: str
    capability: str
    provider: str
    score: int
    reasons: tuple[str, ...]
    status: str = "SELECTED"
    provider_basis: str = "registry_fallback"
    provider_evidence_refs: tuple[str, ...] = ()
    provider_fit_score: int = 0
    provider_fit_reasons: tuple[str, ...] = ()

class CapabilitySelector:
    KEYWORDS = {
        "/verify": ("verify", "xác minh", "kiểm tra", "check", "validate"),
        "/research": ("research", "status", "trạng thái", "tìm hiểu", "inspect"),
        "/debug": ("repair", "debug", "sửa lỗi", "khắc phục"),
        "/compare": ("compare", "so sánh"),
        "/decision": ("decision", "quyết định"),
        "/strategy": ("strategy", "chiến lược"),
        "/roadmap": ("roadmap", "lộ trình"),
        "/media": ("video", "clip", "mp4", "media", "phim", "tạo video", "create video"),
        "/image": ("tạo ảnh", "generate image", "image", "hình ảnh", "picture", "/image"),
        "/video": ("tạo video", "sinh video", "generate video", "video ai", "ai video", "video", "clip", "/video"),
    }

    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        provider_performance: Iterable[dict[str, Any]] | None = None,
    ):
        self.registry = registry or CapabilityRegistry()
        self.provider_performance = list(provider_performance or ())

    @staticmethod
    def _semantic_relation(goal: str, known_goal: str) -> tuple[str, float] | None:
        """Bounded advisory relation; it never grants execution authority."""
        def grams(text: str) -> set[str]:
            normalized = re.sub(r"[^\w]+", "", text.lower(), flags=re.UNICODE)
            return {normalized[i:i + 3] for i in range(max(0, len(normalized) - 2))}
        left, right = grams(goal), grams(known_goal)
        if not left or not right:
            return None
        score = len(left & right) / len(left | right)
        if score < 0.18:
            return None
        return "bounded_char_ngram_relation", round(score, 4)

    def _semantic_candidates(self, goal: str, memory=None):
        candidates = []
        if not memory:
            return candidates
        for entry in memory:
            if not isinstance(entry, dict) or entry.get("kind") != "observed_task":
                continue
            provenance = entry.get("provenance")
            if not isinstance(provenance, dict) or not provenance.get("source"):
                continue
            known_goal = str(entry.get("content", "")).strip().lower()
            if not known_goal:
                continue
            relation = self._semantic_relation(goal, known_goal)
            if relation is None:
                continue
            relation_kind, relation_score = relation
            for command, words in self.KEYWORDS.items():
                if command.lstrip("/") not in self.registry.commands:
                    continue
                hits = tuple(word for word in words if word in known_goal)
                if not hits:
                    continue
                capability = self.registry.capability_for(command)
                candidates.append((int(relation_score * 100), command, capability,
                                   hits, str(entry.get("id", "")) or "UNIDENTIFIED",
                                   relation_kind, relation_score, provenance))
        return candidates

    def select(self, profile: TaskProfile, memory=None) -> CapabilitySelection:
        goal = profile.goal.strip().lower()
        # Explicit command fast-path: "/image ..." / "/video ..." are routed
        # directly to their registered capability (deterministic, no keyword tie).
        first = goal.split()[0] if goal.split() else ""
        if first.startswith("/") and first.lstrip("/") in self.registry.commands:
            capability = self.registry.capability_for(first)
            return CapabilitySelection(
                command=first,
                capability=capability.name,
                provider=capability.provider,
                score=100,
                reasons=("explicit_command",),
            )
        goal_tokens = {t for t in re.findall(r"\w+", goal, flags=re.UNICODE) if len(t) >= 3}

        def keyword_candidates(text):
            out = []
            for command, words in self.KEYWORDS.items():
                if command.lstrip("/") not in self.registry.commands:
                    continue
                hits = tuple(word for word in words if word in text)
                if hits:
                    capability = self.registry.capability_for(command)
                    score = len(hits) * 10
                    if profile.risk in {"HIGH", "CRITICAL"} and capability.name == "governance":
                        score += 5
                    out.append((score, command, capability, hits))
            return out

        search_text = goal
        memory_refs = []
        memory_hits = set()
        memory_only = False
        # Direct matches from the goal take precedence; memory is only consulted
        # when the goal itself yields no capability. A memory-only match is
        # flagged so cognition can defer to the model instead of executing an
        # irrelevantly inferred capability.
        candidates = keyword_candidates(goal)
        if not candidates and memory:
            matched = 0
            for entry in memory:
                if not isinstance(entry, dict) or entry.get("kind") != "observed_task":
                    continue
                content = str(entry.get("content", "")).strip().lower()
                if not content:
                    continue
                content_tokens = set(re.findall(r"\w+", content, flags=re.UNICODE))
                overlap = goal_tokens & content_tokens
                if not overlap:
                    continue
                memory_refs.append(str(entry.get("id", "")) or "UNIDENTIFIED")
                memory_hits.update(overlap)
                search_text += " " + content[:500]
                matched += 1
                if matched >= 8:
                    break
            if memory_refs:
                candidates = keyword_candidates(search_text)
                memory_only = bool(candidates)
        semantic_used = False
        semantic_ref = None
        semantic_score = None
        semantic_kind = None
        if not candidates:
            semantic = self._semantic_candidates(goal, memory=memory)
            if semantic:
                selected = sorted(semantic, key=lambda x: (-x[0], x[1], x[4]))[0]
                score, command, capability, hits, semantic_ref, semantic_kind, semantic_score, _ = selected
                candidates.append((score, command, capability, hits))
                semantic_used = True
                memory_only = True
        if not candidates:
            raise ValueError("no safe bounded capability matched the goal")
        candidates.sort(key=lambda item: (-item[0], item[1]))
        score, command, capability, hits = candidates[0]
        reasons = [f"keyword_hits={','.join(hits)}", "deterministic_selection"]
        if memory_refs:
            reasons.append(f"memory_refs={','.join(memory_refs)}")
            reasons.append(f"memory_recall={','.join(sorted(memory_hits))}")
        if semantic_used:
            reasons.append(f"semantic_relation={semantic_kind}")
            reasons.append(f"semantic_relation_score={semantic_score}")
            reasons.append(f"semantic_memory_ref={semantic_ref}")
        if memory_only:
            reasons.append("memory_only_selection")
        provider_choice = select_provider_from_performance(
            capability.name,
            capability.provider,
            self.provider_performance,
            risk_class=profile.risk,
            task_constraints=profile.constraints,
        )
        if provider_choice["basis"] == "qualified_provider_performance":
            reasons.append("provider_selected_from_qualified_performance")
        else:
            reasons.append("provider_registry_fallback")
        return CapabilitySelection(
            command=command,
            capability=capability.name,
            provider=str(provider_choice["provider"]),
            score=score,
            reasons=tuple(reasons),
            provider_basis=str(provider_choice["basis"]),
            provider_evidence_refs=tuple(provider_choice.get("evidence_refs", ())),
            provider_fit_score=int(provider_choice.get("fit_score", 0)),
            provider_fit_reasons=tuple(provider_choice.get("fit_reasons", ())),
        )
