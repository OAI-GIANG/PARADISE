"""Deterministic repository intelligence for the OG Engineering Agent.

This module provides repository facts without modifying the workspace or
invoking an LLM. It is deliberately bounded and evidence-oriented so that a
later model planner can consume observations as data rather than authority.
"""
from __future__ import annotations

from ast import Import, ImportFrom, parse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Callable


SECRET_NAME_RE = re.compile(
    r"(?:^|[_-])(api[_-]?key|secret|token|password|credential)(?:$|[_-])",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[A-Za-z0-9_]{3,}")


def digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True)
class RepoCommand:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict:
        return {
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "stdout": self.stdout[:4000],
            "stderr": self.stderr[:4000],
        }


Runner = Callable[[list[str], Path], RepoCommand]


def _default_runner(argv: list[str], cwd: Path) -> RepoCommand:
    p = subprocess.run(
        argv,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        shell=False,
    )
    return RepoCommand(tuple(argv), p.returncode, p.stdout, p.stderr)


@dataclass(frozen=True)
class RepositoryIntelligence:
    repository_root: str
    git: dict
    inventory: dict
    python_imports: dict
    tests: list[str]
    instruction_files: list[str]
    relevant_files: list[dict]
    risk_flags: list[str]
    dependency_graph: dict[str, list[str]]
    digest: str

    def to_dict(self) -> dict:
        return {
            "schema_version": "OG-OEA-REPO-INTEL-1.0",
            "verification_status": "OBSERVED",
            "repository_root": self.repository_root,
            "git": self.git,
            "inventory": self.inventory,
            "python_imports": self.python_imports,
            "tests": self.tests,
            "instruction_files": self.instruction_files,
            "relevant_files": self.relevant_files,
            "risk_flags": self.risk_flags,
            "dependency_graph": self.dependency_graph,
            "digest": self.digest,
        }


class RepositoryIntelligenceEngine:
    """Read-only repository inspection engine."""

    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or _default_runner

    @staticmethod
    def _root(configured_root: str | Path, requested_root: str | None) -> Path:
        root = Path(configured_root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"repository root is not a directory: {root}")
        requested_path = Path(requested_root).expanduser() if requested_root else None
        selected = root if requested_path is None else ((root / requested_path) if not requested_path.is_absolute() else requested_path).resolve()
        try:
            selected.relative_to(root)
        except ValueError as exc:
            raise PermissionError("repository root is outside OG_ENGINEERING_ROOT") from exc
        return selected

    @staticmethod
    def _inventory(root: Path) -> tuple[dict, list[Path]]:
        excluded = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
        files: list[Path] = []
        by_extension: dict[str, int] = {}
        for path in root.rglob("*"):
            if any(part in excluded for part in path.parts):
                continue
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            files.append(rel)
            suffix = rel.suffix.lower() or "[no-extension]"
            by_extension[suffix] = by_extension.get(suffix, 0) + 1
        files.sort(key=lambda p: p.as_posix())
        return (
            {
                "file_count": len(files),
                "by_extension": dict(sorted(by_extension.items())),
                "files_digest": digest([x.as_posix() for x in files]),
            },
            files,
        )

    @staticmethod
    def _python_imports(root: Path, files: list[Path]) -> dict:
        result: dict[str, list[str] | dict] = {}
        for rel in files:
            if rel.suffix.lower() != ".py":
                continue
            path = root / rel
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                tree = parse(text, filename=str(rel))
            except (OSError, SyntaxError, UnicodeError) as exc:
                result[rel.as_posix()] = {"parse_error": type(exc).__name__}
                continue

            imports: set[str] = set()
            for node in tree.body:
                if isinstance(node, Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
            result[rel.as_posix()] = sorted(imports)
        return dict(sorted(result.items()))

    @staticmethod
    def _tests(files: list[Path]) -> list[str]:
        found = []
        for rel in files:
            name = rel.name.lower()
            text = rel.as_posix().lower()
            if name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f"/{text}":
                if rel.suffix.lower() == ".py":
                    found.append(rel.as_posix())
        return found

    @staticmethod
    def _instruction_files(files: list[Path]) -> list[str]:
        exact = {"agents.md", "readme.md", "contributing.md", "security.md"}
        found = []
        for rel in files:
            lower = rel.name.lower()
            if lower in exact or lower.startswith("agents."):
                found.append(rel.as_posix())
        return found

    @staticmethod
    def _task_tokens(intent: str) -> set[str]:
        return {x.lower() for x in WORD_RE.findall(intent)}

    @staticmethod
    def _relevance(root: Path, files: list[Path], intent: str) -> list[dict]:
        tokens = RepositoryIntelligenceEngine._task_tokens(intent)
        scored: list[dict] = []
        for rel in files:
            lower = rel.as_posix().lower()
            score = 0
            hits: list[str] = []
            for token in tokens:
                if token in lower:
                    score += 3
                    hits.append(token)
            if rel.suffix.lower() in {".py", ".sh", ".yml", ".yaml", ".json", ".toml"}:
                score += 1
            path = root / rel
            try:
                if path.stat().st_size <= 256 * 1024 and rel.suffix.lower() in {
                    ".py", ".sh", ".yml", ".yaml", ".json", ".toml", ".md"
                }:
                    body = path.read_text(encoding="utf-8", errors="replace")
                    for token in tokens:
                        if token in body.lower() and token not in hits:
                            score += 1
                            hits.append(token)
            except OSError:
                continue
            if score:
                scored.append(
                    {
                        "path": rel.as_posix(),
                        "score": score,
                        "matched_terms": sorted(hits),
                    }
                )
        scored.sort(key=lambda x: (-x["score"], x["path"]))
        return scored[:50]

    @staticmethod
    def _python_local_dependencies(root: Path, files: list[Path]) -> dict[str, list[str]]:
        module_map: dict[str, str] = {}
        for rel in files:
            if rel.suffix.lower() != ".py":
                continue
            parts = list(rel.with_suffix("").parts)
            module = ".".join(parts[:-1]) if parts[-1] == "__init__" else ".".join(parts)
            module_map[module] = rel.as_posix()

        graph: dict[str, set[str]] = {
            rel.as_posix(): set() for rel in files if rel.suffix.lower() == ".py"
        }
        for rel in files:
            if rel.suffix.lower() != ".py":
                continue
            path = root / rel
            try:
                tree = parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(rel))
            except (OSError, SyntaxError, UnicodeError):
                continue
            imported: set[str] = set()
            package_parts = list(rel.with_suffix("").parts[:-1])
            for node in tree.body:
                if isinstance(node, Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ImportFrom):
                    if node.module:
                        if node.level:
                            base = package_parts[: max(0, len(package_parts) - (node.level - 1))]
                            imported.add(".".join(base + node.module.split(".")))
                        else:
                            imported.add(node.module)
            current = rel.as_posix()
            for name in sorted(imported):
                parts = name.split(".")
                for index in range(len(parts), 0, -1):
                    candidate = module_map.get(".".join(parts[:index]))
                    if candidate and candidate != current:
                        graph[current].add(candidate)
                        break
        return {key: sorted(value) for key, value in sorted(graph.items())}

    @staticmethod
    def dependency_blast_radius(
        dependency_graph: dict[str, list[str]],
        changed_paths: list[str] | tuple[str, ...],
    ) -> dict[str, list[str]]:
        reverse: dict[str, set[str]] = {}
        for source, dependencies in dependency_graph.items():
            for target in dependencies:
                reverse.setdefault(target, set()).add(source)
        seeds = {str(path).replace("\\", "/") for path in changed_paths}
        direct: set[str] = set()
        affected: set[str] = set(seeds)
        frontier = list(seeds)
        for seed in sorted(seeds):
            direct.update(reverse.get(seed, set()))
        frontier.extend(sorted(direct))
        affected.update(direct)
        while frontier:
            target = frontier.pop()
            for parent in sorted(reverse.get(target, set())):
                if parent not in affected:
                    affected.add(parent)
                    frontier.append(parent)
        return {
            "changed": sorted(seeds),
            "direct_dependents": sorted(direct),
            "transitive_affected": sorted(affected - seeds),
        }

    @staticmethod
    def _risk_flags(intent: str, files: list[Path]) -> list[str]:
        low = intent.lower()
        flags: list[str] = []
        if any(x in low for x in ("deploy", "production", "railway", "release")):
            flags.append("production-or-deployment-scope")
        if any(x in low for x in ("delete", "remove", "reset", "destroy")):
            flags.append("destructive-intent")
        if any(SECRET_NAME_RE.search(x.name) for x in files):
            flags.append("repository-contains-secret-named-files")
        if any(x.name.lower() in {"dockerfile", "docker-compose.yml", "railway.json"} for x in files):
            flags.append("deployment-config-present")
        return sorted(set(flags))

    def inspect(
        self,
        *,
        configured_root: str | Path,
        intent: str,
        requested_root: str | None = None,
    ) -> RepositoryIntelligence:
        if not str(intent).strip():
            raise ValueError("intent is required")
        root = self._root(configured_root, requested_root)

        command_rows = []
        for argv in (
            ["git", "rev-parse", "--show-toplevel"],
            ["git", "branch", "--show-current"],
            ["git", "rev-parse", "HEAD"],
            ["git", "status", "--short"],
            ["git", "diff", "--stat"],
        ):
            command_rows.append(self._runner(argv, root))
        if command_rows[0].exit_code != 0:
            raise RuntimeError("repository is not a valid git worktree")

        git = {
            "repository_root": command_rows[0].stdout.strip(),
            "branch": command_rows[1].stdout.strip(),
            "head": command_rows[2].stdout.strip(),
            "status_short": command_rows[3].stdout[:8000],
            "diff_stat": command_rows[4].stdout[:4000],
            "commands": [x.to_dict() for x in command_rows],
        }
        inventory, files = self._inventory(root)
        dependency_graph = self._python_local_dependencies(root, files)
        payload = {
            "git": git,
            "inventory": inventory,
            "python_imports": self._python_imports(root, files),
            "tests": self._tests(files),
            "instruction_files": self._instruction_files(files),
            "relevant_files": self._relevance(root, files, intent),
            "risk_flags": self._risk_flags(intent, files),
            "dependency_graph": dependency_graph,
        }
        return RepositoryIntelligence(
            repository_root=str(root),
            git=git,
            inventory=inventory,
            python_imports=payload["python_imports"],
            tests=payload["tests"][:250],
            instruction_files=payload["instruction_files"][:100],
            relevant_files=payload["relevant_files"],
            risk_flags=payload["risk_flags"],
            dependency_graph=dependency_graph,
            digest=digest({"repository_root": str(root), "intent": intent, **payload}),
        )
