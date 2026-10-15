"""Fresh and incremental memory construction over the versioned IR.

The implementation is intentionally backend-agnostic.  A live vLLM/OpenAI
client can implement :class:`workflow_memory.backends.ModelBackend`; tests can
use ``DeterministicReplayBackend``.  When no backend is supplied, a conservative
local extractor is used only for structural/offline tests and the resulting
snapshot is marked ``synthetic`` in its metadata.
"""

from __future__ import annotations

import asyncio
import json
import inspect
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

from .backends import ModelRequest, ModelResponse, backend_fingerprint, request_from_any
from .dependency import ComputeGraph, DependencyTracker, changed_dependency_keys, plan_graph
from .event_store import EventStore, canonical_json, content_hash
from .ir import (
    ComputeNode,
    Evidence,
    PreparedUpdate,
    PublishedSnapshot,
    SourceEvent,
    normalize_trajectory,
    source_frontier,
    stable_hash,
)
from .views import ViewBundle, build_views


@dataclass(frozen=True)
class MemorySnapshot:
    """Queryable in-memory view of one published epoch."""

    published: PublishedSnapshot
    events: tuple[SourceEvent, ...] = field(default_factory=tuple)
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    nodes: tuple[ComputeNode, ...] = field(default_factory=tuple)
    views: ViewBundle = field(default_factory=ViewBundle)
    graph: ComputeGraph = field(default_factory=ComputeGraph, compare=False, repr=False)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    store: EventStore | None = field(default=None, compare=False, repr=False)

    @property
    def epoch(self) -> int:
        return self.published.epoch

    @property
    def snapshot_id(self) -> str:
        return str(self.published.epoch)

    @property
    def checksum(self) -> str:
        return self.published.checksum

    def to_dict(self) -> dict[str, Any]:
        return {
            "published": self.published.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "evidence": [item.to_dict() for item in self.evidence],
            "nodes": [node.to_dict() for node in self.nodes],
            "views": self.views.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class UpdateReceipt:
    update_id: str
    accepted: bool
    prepared: bool
    committed: bool
    queryable: bool
    snapshot: MemorySnapshot | None = None
    affected_scopes: tuple[str, ...] = field(default_factory=tuple)
    invalidated_nodes: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None

    @property
    def status(self) -> str:
        if self.queryable:
            return "queryable"
        if self.committed:
            return "committed"
        if self.prepared:
            return "prepared"
        if self.accepted:
            return "accepted"
        return "rejected"


def _cfg(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, Mapping):
        if key in config:
            return config[key]
        algorithm = config.get("algorithm")
        if isinstance(algorithm, Mapping) and key in algorithm:
            return algorithm[key]
    return getattr(config, key, default)


def _prefix_context(events: Sequence[SourceEvent], index: int, window: int) -> list[SourceEvent]:
    current = events[index]
    scope = (current.trajectory_id, current.environment_instance_id or "trajectory")
    prior = [
        item for item in events[: index + 1]
        if (item.trajectory_id, item.environment_instance_id or "trajectory") == scope
    ]
    return prior[-(max(0, window) + 1) :]


def _normalize_input(value: Any) -> list[SourceEvent]:
    if isinstance(value, (list, tuple)) and all(isinstance(item, SourceEvent) for item in value):
        return list(value)
    return normalize_trajectory(value)


def _run_maybe_awaitable(value: Any) -> Any:
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)
    # Synchronous APIs called from an active event loop cannot block it.  Run
    # the awaitable in a short-lived helper thread instead.
    import threading

    result: list[Any] = []
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(value))
        except BaseException as exc:  # pragma: no cover - defensive
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0] if result else None


def _complete(backend: Any, request: ModelRequest) -> ModelResponse:
    method = getattr(backend, "complete", None)
    if method is None:
        method = getattr(backend, "acomplete", None)
    if method is None and callable(backend):
        method = backend
    if method is None:
        raise TypeError("model backend must implement complete/acomplete or be callable")
    return ModelResponse.from_any(_run_maybe_awaitable(method(request)), request_fingerprint=request.fingerprint)


def _parse_json_response(text: str) -> Any:
    candidate = (text or "").strip()
    if not candidate:
        return None
    # Permit fenced JSON commonly returned by instruction-tuned models.
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.startswith("json"):
            candidate = candidate[4:]
    try:
        return json.loads(candidate)
    except (TypeError, ValueError):
        return None


def _heuristic_evidence(event: SourceEvent, *, synthetic: bool = True) -> list[Evidence]:
    """Conservative non-LLM evidence projection for smoke/correctness tests."""
    source = (event.event_id,)
    scope = {
        "trajectory_id": event.trajectory_id,
        "environment_instance_id": event.environment_instance_id or "trajectory",
    }
    evidence: list[Evidence] = []
    action = event.action
    outcome = event.observed_outcome
    if action is not None:
        evidence.append(
            Evidence(
                evidence_id=f"{event.event_id}:attempt",
                source_refs=source,
                source_versions={event.event_id: event.source_revision},
                source_spans=("action",),
                subject_ref=event.trajectory_id,
                predicate="action",
                value=action,
                modality="observed",
                certainty="explicit",
                event_kind="attempt",
                valid_scope=scope,
                revision=event.source_revision,
            )
        )
    if event.post_state_ref is not None:
        evidence.append(
            Evidence(
                evidence_id=f"{event.event_id}:state",
                source_refs=source,
                source_versions={event.event_id: event.source_revision},
                source_spans=("post_state_ref",),
                subject_ref=event.trajectory_id,
                predicate="state",
                value=event.post_state_ref,
                modality="observed",
                certainty="explicit",
                event_kind="observation",
                valid_scope=scope,
                revision=event.source_revision,
            )
        )
    if outcome is not None:
        outcome_text = str(outcome).lower()
        kind = "failure" if any(word in outcome_text for word in ("fail", "error", "timeout", "denied")) else "confirmation"
        evidence.append(
            Evidence(
                evidence_id=f"{event.event_id}:outcome",
                source_refs=source,
                source_versions={event.event_id: event.source_revision},
                source_spans=("observed_outcome",),
                subject_ref=event.trajectory_id,
                predicate="outcome",
                value=outcome,
                modality="observed",
                certainty="explicit",
                event_kind=kind,
                valid_scope=scope,
                revision=event.source_revision,
            )
        )
    return evidence


def _backend_evidence(backend: Any, event: SourceEvent, context: Sequence[SourceEvent], config: Any) -> tuple[list[Evidence], dict[str, Any]]:
    """Call an optional extraction adapter and normalize its response."""
    if backend is None:
        return _heuristic_evidence(event), {"synthetic": True, "backend": "heuristic"}
    direct = getattr(backend, "extract_evidence", None) or getattr(backend, "extract", None)
    if callable(direct):
        response = _run_maybe_awaitable(direct(event, context=context, config=config))
        metadata = {"synthetic": False, "backend": backend_fingerprint(backend)}
    else:
        prompt = {
            "task": "extract_local_evidence",
            "event": event.to_dict(),
            "context": [item.to_dict() for item in context],
            "rules": {
                "do_not_infer_success_from_intent": True,
                "prefix_only": True,
                "preserve_source_spans": True,
            },
        }
        request = ModelRequest(
            messages=({"role": "user", "content": canonical_json(prompt)},),
            model=_cfg(config, "construction_model", _cfg(config, "model", None)),
            temperature=float(_cfg(config, "temperature", 0) or 0),
            max_tokens=int(_cfg(config, "extraction_output_tokens", 1024) or 1024),
            metadata={"operator": "extract", "event_id": event.event_id},
        )
        response = _complete(backend, request)
        metadata = {
            "synthetic": False,
            "backend": backend_fingerprint(backend),
            "request_fingerprint": response.request_fingerprint,
            "usage": dict(response.usage),
        }
        parsed = _parse_json_response(response.text)
        response = parsed if parsed is not None else response.text
    if isinstance(response, Mapping):
        rows = response.get("evidence", response.get("items", response.get("outputs", response)))
    else:
        rows = response
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, (list, tuple)):
        rows = []
    out: list[Evidence] = []
    for index, row in enumerate(rows):
        if isinstance(row, Evidence):
            out.append(row)
            continue
        if not isinstance(row, Mapping):
            row = {"predicate": "observation", "value": row}
        data = dict(row)
        data.setdefault("evidence_id", f"{event.event_id}:evidence:{index}")
        data.setdefault("source_refs", (event.event_id,))
        data.setdefault("source_versions", {event.event_id: event.source_revision})
        data.setdefault("subject_ref", event.trajectory_id)
        data.setdefault("event_kind", "observation")
        data.setdefault(
            "valid_scope",
            {
                "trajectory_id": event.trajectory_id,
                "environment_instance_id": event.environment_instance_id or "trajectory",
            },
        )
        data.setdefault("revision", event.source_revision)
        try:
            out.append(Evidence.from_dict(data))
        except TypeError:
            # Keep unknown provider fields out of the strict IR constructor.
            allowed = {key: data[key] for key in Evidence._field_names() if key in data}
            out.append(Evidence.from_dict(allowed))
    if not out:
        # A provider may return prose or an empty extraction.  Preserve the
        # source event as a low-certainty observation rather than losing it.
        out = _heuristic_evidence(event, synthetic=False)
        metadata["empty_provider_output"] = True
    return out, metadata


def _replace_node(node: ComputeNode, *, output_refs: Sequence[str], status: str = "complete", content: Any = None, provenance: Any = None, interpretation: Any = None) -> ComputeNode:
    return replace(
        node,
        output_refs=tuple(output_refs),
        status=status,
        content_hash=node.content_hash or stable_hash(content if content is not None else output_refs),
        provenance_hash=node.provenance_hash or stable_hash(provenance if provenance is not None else node.read_dependencies),
        interpretation_hash=node.interpretation_hash or stable_hash(interpretation if interpretation is not None else {"operator": node.operator, "outputs": output_refs}),
    )


def _build_snapshot(
    events: Sequence[SourceEvent],
    evidence: Sequence[Evidence],
    graph: ComputeGraph,
    nodes: Sequence[ComputeNode],
    *,
    epoch: int,
    parent_epoch: int | None,
    metadata: Mapping[str, Any] | None = None,
    store: EventStore | None = None,
    update_ids: Sequence[str] = (),
) -> MemorySnapshot:
    views = build_views(evidence, events={event.event_id: event for event in events})
    object_versions = {
        "events": stable_hash([event.to_dict() for event in events]),
        "evidence": stable_hash([item.to_dict() for item in evidence]),
        "nodes": stable_hash([node.to_dict() for node in nodes]),
        "views": stable_hash(views.to_dict()),
    }
    index_manifest = {
        "document_ids": [str(item.get("id")) for item in views.index_documents],
        "document_hash": stable_hash(views.index_documents),
    }
    published = PublishedSnapshot(
        epoch=epoch,
        parent_epoch=parent_epoch,
        object_versions=object_versions,
        index_manifest=index_manifest,
        included_event_frontier=source_frontier(events),
        included_update_ids=tuple(update_ids),
    )
    snapshot = MemorySnapshot(
        published=published,
        events=tuple(events),
        evidence=tuple(evidence),
        nodes=tuple(nodes),
        views=views,
        graph=graph,
        metadata=dict(metadata or {}),
        store=store,
    )
    if store is not None:
        store.commit_snapshot(
            published,
            events=events,
            evidence=evidence,
            nodes=nodes,
            update_ids=update_ids,
        )
    return snapshot


def build_fresh(
    history_prefix: Any,
    model_backend: Any = None,
    config: Any = None,
    *,
    store: EventStore | None = None,
) -> MemorySnapshot:
    """Build a complete snapshot from a prefix without reusing old outputs."""
    events = _normalize_input(history_prefix)
    events = sorted(events, key=lambda item: (item.trajectory_id, item.source_sequence, item.source_revision, item.event_id))
    graph = plan_graph(events, config)
    event_map = {event.event_id: event for event in events}
    evidence: list[Evidence] = []
    node_outputs: dict[str, list[str]] = {}
    metadata: dict[str, Any] = {"mode": "fresh", "backend": backend_fingerprint(model_backend) if model_backend else "heuristic", "synthetic": model_backend is None}
    for event in events:
        context_window = int(_cfg(config, "source_context_window_events_default", 2) or 0)
        index = events.index(event)
        context = _prefix_context(events, index, context_window)
        extracted, call_meta = _backend_evidence(model_backend, event, context, config)
        metadata.setdefault("calls", []).append(call_meta)
        evidence.extend(extracted)
        for node_id in graph.source_to_nodes.get(event.event_id, ()):
            node = graph.nodes[node_id]
            # Only the extraction node directly materializes this event's
            # evidence.  Resolve/workflow/embed nodes may read the same event
            # as context but must remain planned until their predecessors are
            # wired in topological order.
            if node.operator != "extract" or graph.node_to_source.get(node_id) != event.event_id:
                continue
            refs = tuple(item.evidence_id for item in extracted)
            graph.nodes[node_id] = _replace_node(node, output_refs=refs, content=extracted, provenance=event.raw_content_hash)
            node_outputs[node_id] = list(refs)
    # Derived node output references are wired to the previous layer's output.
    completed: list[ComputeNode] = []
    for node_id in graph.topological_order():
        node = graph.nodes[node_id]
        if node.status == "complete":
            completed.append(node)
            continue
        refs: list[str] = []
        for predecessor in graph.edges.get(node_id, ()):
            refs.extend(graph.nodes.get(predecessor, node).output_refs)
        graph.nodes[node_id] = _replace_node(node, output_refs=tuple(dict.fromkeys(refs)), content=refs)
        completed.append(graph.nodes[node_id])
    nodes = tuple(completed)
    return _build_snapshot(events, evidence, graph, nodes, epoch=1, parent_epoch=None, metadata=metadata, store=store)


def apply_delta(
    snapshot: MemorySnapshot,
    events: Any,
    model_backend: Any = None,
    config: Any = None,
    *,
    store: EventStore | None = None,
) -> UpdateReceipt:
    """Prepare and publish a delta against a prior consistent snapshot."""
    incoming = _normalize_input(events)
    if not incoming:
        return UpdateReceipt(
            update_id=f"empty-{snapshot.epoch}", accepted=True, prepared=True, committed=True, queryable=True, snapshot=snapshot
        )
    existing = {event.event_id: event for event in snapshot.events}
    changed: list[SourceEvent] = []
    for event in incoming:
        previous = existing.get(event.event_id)
        if previous is None or previous.raw_content_hash != event.raw_content_hash or previous.source_revision != event.source_revision:
            changed.append(event)
        existing[event.event_id] = event
    combined_events = sorted(existing.values(), key=lambda item: (item.trajectory_id, item.source_sequence, item.source_revision, item.event_id))
    graph = plan_graph(combined_events, config)
    tracker = DependencyTracker(graph)
    invalidated = tracker.invalidate(changed)
    old_evidence_by_source: dict[str, list[Evidence]] = {}
    for item in snapshot.evidence:
        for ref in item.source_refs:
            old_evidence_by_source.setdefault(ref, []).append(item)
    evidence = [item for item in snapshot.evidence if not any(ref in {event.event_id for event in changed} for ref in item.source_refs)]
    metadata: dict[str, Any] = dict(snapshot.metadata)
    metadata.update({"mode": "incremental", "backend": backend_fingerprint(model_backend) if model_backend else metadata.get("backend", "heuristic")})
    changed_ids = {event.event_id for event in changed}
    extracted_refs: dict[str, tuple[str, ...]] = {}
    for event in changed:
        index = combined_events.index(event)
        window = int(_cfg(config, "source_context_window_events_default", 2) or 0)
        context = _prefix_context(combined_events, index, window)
        extracted, call_meta = _backend_evidence(model_backend, event, context, config)
        metadata.setdefault("calls", []).append(call_meta)
        evidence.extend(extracted)
        extracted_refs[event.event_id] = tuple(item.evidence_id for item in extracted)
    # Rewire/reuse node outputs.  Nodes not in invalidated retain output refs;
    # invalidated nodes are marked complete after their changed source output.
    old_nodes = {node.node_id: node for node in snapshot.nodes}
    nodes: list[ComputeNode] = []
    for node_id in graph.topological_order():
        node = graph.nodes[node_id]
        if node_id not in invalidated and node_id in old_nodes:
            # Reuse the exact prior node record (including output and
            # interpretation hashes) when no actual dependency changed.
            graph.nodes[node_id] = old_nodes[node_id]
            nodes.append(old_nodes[node_id])
            continue
        if node_id in invalidated:
            if node.operator == "extract":
                source_id = graph.node_to_source.get(node_id)
                source_event = next((event for event in combined_events if event.event_id == source_id), None)
                if source_event is not None and source_event.event_id in extracted_refs:
                    graph.nodes[node_id] = _replace_node(
                        node,
                        output_refs=extracted_refs[source_event.event_id],
                        content=extracted_refs[source_event.event_id],
                        provenance=source_event.raw_content_hash,
                    )
                    nodes.append(graph.nodes[node_id])
                    continue
            refs: list[str] = []
            for predecessor in graph.edges.get(node_id, ()):
                refs.extend(graph.nodes.get(predecessor, node).output_refs)
            graph.nodes[node_id] = _replace_node(node, output_refs=tuple(dict.fromkeys(refs)), content=refs)
        nodes.append(graph.nodes[node_id])
    update_id = f"update:{stable_hash({'events': [event.to_dict() for event in incoming], 'parent': snapshot.epoch})[:24]}"
    prepared = PreparedUpdate(
        update_id=update_id,
        source_event_ids=tuple(event.event_id for event in incoming),
        read_version_vector={event.event_id: event.source_revision for event in incoming},
        affected_scopes=tuple(sorted({f"{event.trajectory_id}/{event.environment_instance_id or 'trajectory'}" for event in incoming})),
        writes=tuple(item.evidence_id for item in evidence if any(ref in changed_ids for ref in item.source_refs)),
        predecessor_updates=tuple(snapshot.published.included_update_ids),
    )
    target_store = store or snapshot.store
    if target_store is not None:
        target_store.put_prepared_update(prepared, status="prepared")
    next_snapshot = _build_snapshot(
        combined_events,
        evidence,
        graph,
        nodes,
        epoch=snapshot.epoch + 1,
        parent_epoch=snapshot.epoch,
        metadata=metadata,
        store=target_store,
        update_ids=(*snapshot.published.included_update_ids, update_id),
    )
    return UpdateReceipt(
        update_id=update_id,
        accepted=True,
        prepared=True,
        committed=True,
        queryable=True,
        snapshot=next_snapshot,
        affected_scopes=prepared.affected_scopes,
        invalidated_nodes=tuple(sorted(invalidated)),
    )


__all__ = ["MemorySnapshot", "UpdateReceipt", "build_fresh", "apply_delta"]
