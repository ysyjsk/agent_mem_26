"""Dependency graph construction and precise invalidation utilities.

The graph is a logical build graph, not a worker-completion chain.  Source
events are connected by explicit causal predecessors and by the bounded
prefix-context rule.  Derived nodes declare the actual source/node keys they
read; the reverse index is then used to invalidate only affected work.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .ir import ComputeNode, SourceEvent, canonical_json, normalize_trajectory, stable_hash


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclass
class ComputeGraph:
    """Deterministic DAG plus indexes used by schedulers and caches."""

    nodes: dict[str, ComputeNode] = field(default_factory=dict)
    edges: dict[str, set[str]] = field(default_factory=dict)
    reverse_edges: dict[str, set[str]] = field(default_factory=dict)
    source_to_nodes: dict[str, set[str]] = field(default_factory=dict)
    dependency_to_nodes: dict[str, set[str]] = field(default_factory=dict)
    node_to_source: dict[str, str] = field(default_factory=dict)

    def add_node(
        self,
        node: ComputeNode,
        *,
        predecessors: Iterable[str] = (),
        source_event_id: str | None = None,
    ) -> None:
        self.nodes[node.node_id] = node
        self.edges.setdefault(node.node_id, set()).update(str(x) for x in predecessors if x)
        self.reverse_edges.setdefault(node.node_id, set())
        for predecessor in self.edges[node.node_id]:
            self.reverse_edges.setdefault(predecessor, set()).add(node.node_id)
        for dep in node.read_dependencies:
            key = str(dep)
            self.dependency_to_nodes.setdefault(key, set()).add(node.node_id)
            if key.startswith("event:"):
                self.source_to_nodes.setdefault(key.split(":", 1)[1], set()).add(node.node_id)
        # Predicate/range reads opt in explicitly via a ``scope:...`` or
        # ``predicate:...`` dependency.  Merely declaring an output scope
        # must not make every same-scope event invalidate every old node.
        for dep in node.read_dependencies:
            if str(dep).startswith(("scope:", "predicate:")):
                self.dependency_to_nodes.setdefault(str(dep), set()).add(node.node_id)
        if source_event_id is not None:
            self.node_to_source[node.node_id] = str(source_event_id)

    def topological_order(self) -> list[str]:
        indegree = {node_id: len(preds) for node_id, preds in self.edges.items()}
        for node_id in self.nodes:
            indegree.setdefault(node_id, 0)
        ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
        order: list[str] = []
        while ready:
            node_id = ready.popleft()
            order.append(node_id)
            for child in sorted(self.reverse_edges.get(node_id, ())):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        # Unknown/cyclic dependencies are intentionally surfaced as a stable
        # tail rather than silently discarded; validation reports the cycle.
        if len(order) != len(self.nodes):
            order.extend(sorted(set(self.nodes) - set(order)))
        return order

    def ready_nodes(self, completed: Iterable[str] = ()) -> list[str]:
        done = set(completed)
        return [
            node_id
            for node_id in self.topological_order()
            if node_id not in done and self.edges.get(node_id, set()).issubset(done)
        ]

    def has_cycle(self) -> bool:
        indegree = {node_id: len(self.edges.get(node_id, set())) for node_id in self.nodes}
        ready = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
        visited = 0
        while ready:
            node_id = ready.popleft()
            visited += 1
            for child in self.reverse_edges.get(node_id, ()):
                if child in indegree:
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        ready.append(child)
        return visited != len(self.nodes)

    def affected_nodes(self, changed_keys: Iterable[str]) -> set[str]:
        """Return changed nodes and all downstream consumers."""
        changed = {str(key) for key in changed_keys}
        affected: set[str] = set()
        queue: deque[str] = deque()
        for key in changed:
            queue.extend(self.source_to_nodes.get(key, ()))
            queue.extend(self.dependency_to_nodes.get(key, ()))
            queue.extend(node_id for node_id, source_id in self.node_to_source.items() if source_id == key)
            if key in self.nodes:
                queue.append(key)
        while queue:
            node_id = queue.popleft()
            if node_id in affected:
                continue
            affected.add(node_id)
            queue.extend(self.reverse_edges.get(node_id, ()))
        return affected

    def as_dict(self) -> dict[str, Any]:
        return {
            "nodes": {key: node.to_dict() for key, node in sorted(self.nodes.items())},
            "edges": {key: sorted(value) for key, value in sorted(self.edges.items())},
            "source_to_nodes": {key: sorted(value) for key, value in sorted(self.source_to_nodes.items())},
            "dependency_to_nodes": {
                key: sorted(value) for key, value in sorted(self.dependency_to_nodes.items())
            },
            "node_to_source": dict(sorted(self.node_to_source.items())),
        }


def _node_id(event_id: str, operator: str, scope: str = "") -> str:
    payload = f"{event_id}|{operator}|{scope}"
    return f"{operator}:{stable_hash(payload)[:20]}"


def _event_scope(event: SourceEvent) -> str:
    instance = event.environment_instance_id or "trajectory"
    return f"{event.trajectory_id}/{instance}"


def _event_context(events: Sequence[SourceEvent], index: int, window: int) -> list[SourceEvent]:
    current = events[index]
    # Context is local to one trajectory/environment scope.  A trajectory's
    # source order may be interleaved with another trajectory in a batch, but
    # that does not establish a state dependency between them.
    candidates = [
        event
        for event in events[: index + 1]
        if event.trajectory_id == current.trajectory_id
        and (event.environment_instance_id or "trajectory")
        == (current.environment_instance_id or "trajectory")
    ]
    return candidates[-(max(0, window) + 1) :]


def _config(config: Any, key: str, default: Any) -> Any:
    if isinstance(config, Mapping):
        if key in config:
            return config[key]
        algorithm = config.get("algorithm")
        if isinstance(algorithm, Mapping) and key in algorithm:
            return algorithm[key]
    return getattr(config, key, default)


def plan_graph(history_prefix: Iterable[SourceEvent] | Any, algorithm_config: Mapping[str, Any] | Any = None) -> ComputeGraph:
    """Create the canonical extraction→resolve→views→embed graph.

    Node IDs depend only on stable source identity/operator/scope.  Worker
    completion order never affects graph structure.  The default context
    window is two prior events, matching the workplan.
    """
    if isinstance(history_prefix, (list, tuple)):
        raw_events = list(history_prefix)
    elif isinstance(history_prefix, SourceEvent):
        raw_events = [history_prefix]
    else:
        # Accept the same raw trajectory encodings as normalize_trajectory;
        # callers of the public plan_graph API need not normalize twice.
        raw_events = normalize_trajectory(history_prefix)
    if raw_events and not isinstance(raw_events[0], SourceEvent):
        raw_events = normalize_trajectory(raw_events)
    events = sorted(
        list(raw_events), key=lambda event: (event.trajectory_id, event.source_sequence, event.source_revision, event.event_id)
    )
    window = int(_config(algorithm_config, "source_context_window_events_default", 2) or 0)
    layers = tuple(_config(algorithm_config, "layers", ("evidence", "state_relation", "workflow")) or ())
    model_fp = _config(algorithm_config, "model_fingerprint", _config(algorithm_config, "construction_model", None))
    prompt_fp = _config(algorithm_config, "prompt_hash", None)
    graph = ComputeGraph()
    event_by_id = {event.event_id: event for event in events}
    previous_by_scope: dict[str, list[str]] = defaultdict(list)
    evidence_nodes: dict[str, str] = {}
    state_nodes: dict[str, str] = {}
    workflow_nodes: dict[str, str] = {}
    embed_nodes: dict[str, str] = {}
    for index, event in enumerate(events):
        scope = _event_scope(event)
        context = _event_context(events, index, window)
        context_ids = tuple(f"event:{item.event_id}" for item in context)
        explicit = tuple(
            f"event:{item}"
            for item in event.causal_predecessors
            if item in event_by_id
            and event_by_id[item].source_sequence <= event.source_sequence
            and event_by_id[item].arrival_sequence <= event.arrival_sequence
        )
        read_events = tuple(dict.fromkeys((*context_ids, *explicit)))
        source_id = _node_id(event.event_id, "source", scope)
        source = ComputeNode(
            node_id=source_id,
            operator="source",
            operator_version="1",
            read_fields=("raw_content_hash", "source_revision", "arrival_sequence"),
            predicate_scopes=(scope,),
            output_refs=(f"event:{event.event_id}",),
            content_hash=event.raw_content_hash,
            provenance_hash=stable_hash({"event_id": event.event_id, "revision": event.source_revision}),
            interpretation_hash=stable_hash({"scope": scope}),
            input_fingerprint=event.raw_content_hash,
            status="ready",
        )
        graph.add_node(source, predecessors=(), source_event_id=event.event_id)
        extract_id = _node_id(event.event_id, "extract", scope)
        extract = ComputeNode(
            node_id=extract_id,
            operator="extract",
            operator_version=str(_config(algorithm_config, "extract_operator_version", "1")),
            prompt_hash=None if prompt_fp is None else str(prompt_fp),
            model_fingerprint=None if model_fp is None else str(model_fp),
            read_dependencies=read_events,
            read_fields=("action", "pre_state_ref", "post_state_ref", "observed_outcome", "screenshot_hashes"),
            predicate_scopes=(scope,),
            output_refs=(f"evidence:{event.event_id}",),
            input_fingerprint=stable_hash({"event": event.to_dict(), "context": read_events}),
            status="planned",
        )
        graph.add_node(extract, predecessors=(source_id,), source_event_id=event.event_id)
        evidence_nodes[event.event_id] = extract_id
        prior_scope = previous_by_scope[scope][-1:]

        resolve_id = _node_id(event.event_id, "resolve", scope)
        resolve_deps = tuple(dict.fromkeys((*read_events, f"node:{extract_id}", *prior_scope)))
        resolve = ComputeNode(
            node_id=resolve_id,
            operator="resolve",
            operator_version=str(_config(algorithm_config, "resolve_operator_version", "1")),
            prompt_hash=None if prompt_fp is None else str(prompt_fp),
            model_fingerprint=None if model_fp is None else str(model_fp),
            read_dependencies=resolve_deps,
            read_fields=("subject_ref", "predicate", "value", "aliases", "relations"),
            predicate_scopes=(scope,),
            output_refs=(f"state:{event.event_id}",),
            input_fingerprint=stable_hash({"event": event.event_id, "deps": resolve_deps}),
            status="planned",
        )
        graph.add_node(resolve, predecessors=(extract_id, *prior_scope), source_event_id=event.event_id)
        state_nodes[event.event_id] = resolve_id

        if "workflow" in layers:
            workflow_id = _node_id(event.event_id, "workflow", scope)
            wf_deps = tuple(dict.fromkeys((*context_ids, f"node:{resolve_id}")))
            workflow = ComputeNode(
                node_id=workflow_id,
                operator="workflow",
                operator_version=str(_config(algorithm_config, "workflow_operator_version", "1")),
                prompt_hash=None if prompt_fp is None else str(prompt_fp),
                model_fingerprint=None if model_fp is None else str(model_fp),
                read_dependencies=wf_deps,
                read_fields=("event_order", "step_group", "phase", "result", "failure"),
                predicate_scopes=(scope,),
                output_refs=(f"workflow:{event.event_id}",),
                input_fingerprint=stable_hash({"event": event.event_id, "deps": wf_deps}),
                status="planned",
            )
            graph.add_node(workflow, predecessors=(resolve_id,), source_event_id=event.event_id)
            workflow_nodes[event.event_id] = workflow_id
            last_view = workflow_id
        else:
            last_view = resolve_id

        embed_id = _node_id(event.event_id, "embed", scope)
        embed_deps = (f"node:{last_view}",)
        embed = ComputeNode(
            node_id=embed_id,
            operator="embed",
            operator_version=str(_config(algorithm_config, "embed_operator_version", "1")),
            prompt_hash=None if prompt_fp is None else str(prompt_fp),
            model_fingerprint=None if model_fp is None else str(model_fp),
            read_dependencies=embed_deps,
            read_fields=("content",),
            predicate_scopes=(scope,),
            output_refs=(f"index:{event.event_id}",),
            input_fingerprint=stable_hash({"event": event.event_id, "deps": embed_deps}),
            status="planned",
        )
        graph.add_node(embed, predecessors=(last_view,), source_event_id=event.event_id)
        embed_nodes[event.event_id] = embed_id
        previous_by_scope[scope].append(embed_id)

    # Logical publication is part of the canonical graph. The actual SQLite
    # transaction is performed by the builder after preparation finishes.
    all_node_ids = tuple(sorted(graph.nodes))
    publish_id = f"publish:{stable_hash(all_node_ids)[:20]}"
    publish = ComputeNode(
        node_id=publish_id,
        operator="publish",
        operator_version="1",
        read_dependencies=tuple(f"node:{node_id}" for node_id in all_node_ids),
        read_fields=("content", "provenance", "interpretation"),
        predicate_scopes=tuple(sorted({scope for node in graph.nodes.values() for scope in node.predicate_scopes})),
        output_refs=("snapshot:published",),
        content_hash=stable_hash(all_node_ids),
        provenance_hash=stable_hash({"nodes": all_node_ids}),
        interpretation_hash=stable_hash({"operator": "publish"}),
        input_fingerprint=stable_hash(all_node_ids),
        status="planned",
    )
    graph.add_node(publish, predecessors=all_node_ids)

    return graph


def changed_dependency_keys(events: Iterable[SourceEvent]) -> set[str]:
    keys: set[str] = set()
    for event in events:
        keys.add(event.event_id)
        keys.add(f"event:{event.event_id}")
        keys.add(f"trajectory:{event.trajectory_id}")
        keys.add(f"scope:{_event_scope(event)}")
        for predecessor in event.causal_predecessors:
            keys.add(str(predecessor))
            keys.add(f"event:{predecessor}")
    return keys


def normalized_output(value: Any) -> Any:
    """Normalize output for exact propagation-stop comparison.

    No embedding similarity or fuzzy string matching is used.  This function
    only strips representation details that are semantically non-observable,
    such as dictionary ordering and tuple/list distinction.
    """
    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): normalized_output(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [normalized_output(item) for item in value]
        if isinstance(value, (set, frozenset)):
            values.sort(key=canonical_json)
        return values
    return value


def output_changed(previous: Any, current: Any, *, fields: Iterable[str] | None = None) -> bool:
    if hasattr(previous, "to_dict") and callable(previous.to_dict):
        previous = previous.to_dict()
    if hasattr(current, "to_dict") and callable(current.to_dict):
        current = current.to_dict()
    if fields is not None and isinstance(previous, Mapping) and isinstance(current, Mapping):
        selected = {str(field) for field in fields}
        previous = {key: previous.get(key) for key in selected}
        current = {key: current.get(key) for key in selected}
    return canonical_json(normalized_output(previous)) != canonical_json(normalized_output(current))


class DependencyTracker:
    """Mutable reverse dependency index used during incremental updates."""

    def __init__(self, graph: ComputeGraph | None = None):
        self.graph = graph or ComputeGraph()
        self.node_outputs: dict[str, Any] = {}
        self.node_input_versions: dict[str, Mapping[str, Any]] = {}

    def register(self, node: ComputeNode, *, output: Any = None) -> None:
        self.graph.add_node(node)
        if output is not None:
            self.node_outputs[node.node_id] = output
        self.node_input_versions[node.node_id] = {
            "input_fingerprint": node.input_fingerprint,
            "content_hash": node.content_hash,
            "provenance_hash": node.provenance_hash,
            "interpretation_hash": node.interpretation_hash,
        }

    def invalidate(self, changed_events: Iterable[SourceEvent] | Iterable[str]) -> set[str]:
        items = list(changed_events)
        if not items:
            return set()
        if isinstance(items[0], str):
            keys = {str(item) for item in items}
        else:
            keys = changed_dependency_keys(items)  # type: ignore[arg-type]
        return self.graph.affected_nodes(keys)

    def propagation_stops(self, node_id: str, previous: Any, current: Any, *, fields: Iterable[str] | None = None) -> bool:
        unchanged = not output_changed(previous, current, fields=fields)
        if unchanged:
            self.node_outputs[node_id] = current
        return unchanged


__all__ = [
    "ComputeGraph",
    "DependencyTracker",
    "plan_graph",
    "changed_dependency_keys",
    "normalized_output",
    "output_changed",
]
