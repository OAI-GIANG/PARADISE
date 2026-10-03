"""Reusable execution graph contract for existing OG plans.

The graph is a validation/coordination primitive; it does not own permissions,
execution authority, or scheduling policy.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Any


class GraphValidationError(ValueError):
    pass


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    depends_on: tuple[str, ...] = ()
    kind: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "depends_on": list(self.depends_on),
            "kind": self.kind,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class ExecutionGraph:
    nodes: tuple[GraphNode, ...]

    @classmethod
    def from_stages(cls, stages: Iterable[Any]) -> "ExecutionGraph":
        return cls(tuple(
            GraphNode(
                str(stage.stage_id),
                tuple(str(x) for x in stage.depends_on),
                str(stage.kind),
                {"name": str(stage.name), "mode": str(stage.mode)},
            )
            for stage in stages
        ))

    def validate(self) -> None:
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise GraphValidationError("duplicate node_id")
        known = set(ids)
        for node in self.nodes:
            if node.node_id in node.depends_on:
                raise GraphValidationError(f"self dependency: {node.node_id}")
            missing = sorted(set(node.depends_on) - known)
            if missing:
                raise GraphValidationError(
                    f"unknown dependencies for {node.node_id}: {', '.join(missing)}"
                )

        visiting: set[str] = set()
        visited: set[str] = set()
        deps = {node.node_id: set(node.depends_on) for node in self.nodes}

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise GraphValidationError(f"dependency cycle at {node_id}")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dep in sorted(deps[node_id]):
                visit(dep)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)

    def topological_layers(self) -> tuple[tuple[str, ...], ...]:
        self.validate()
        deps = {node.node_id: set(node.depends_on) for node in self.nodes}
        remaining = set(deps)
        layers: list[tuple[str, ...]] = []
        while remaining:
            ready = tuple(sorted(node for node in remaining if not (deps[node] & remaining)))
            if not ready:
                raise GraphValidationError("dependency cycle prevents layering")
            layers.append(ready)
            remaining.difference_update(ready)
        return tuple(layers)

    def topological_order(self) -> tuple[str, ...]:
        return tuple(node_id for layer in self.topological_layers() for node_id in layer)

    def fan_out_nodes(self) -> tuple[str, ...]:
        outgoing = {node.node_id: 0 for node in self.nodes}
        for node in self.nodes:
            for dep in node.depends_on:
                outgoing[dep] += 1
        return tuple(sorted(node for node, count in outgoing.items() if count > 1))

    def fan_in_nodes(self) -> tuple[str, ...]:
        return tuple(sorted(node.node_id for node in self.nodes if len(node.depends_on) > 1))

    def ready_nodes(self, completed: Iterable[str]) -> tuple[str, ...]:
        done = set(str(x) for x in completed)
        return tuple(sorted(
            node.node_id
            for node in self.nodes
            if node.node_id not in done and set(node.depends_on).issubset(done)
        ))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "OG-EXECUTION-GRAPH-1.0",
            "nodes": [node.to_dict() for node in self.nodes],
            "topological_layers": [list(x) for x in self.topological_layers()],
            "fan_out_nodes": list(self.fan_out_nodes()),
            "fan_in_nodes": list(self.fan_in_nodes()),
        }
