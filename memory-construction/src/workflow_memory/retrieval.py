"""Deterministic evidence retrieval over a published memory snapshot."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .core_builder import MemorySnapshot
from .event_store import EventStore
from .ir import Evidence, canonical_json
from .views import StateView, WorkflowView


_TOKEN_RE = re.compile(r"[\w\-:.]+", re.UNICODE)


def _tokens(value: Any) -> set[str]:
    return {item.lower() for item in _TOKEN_RE.findall(str(value or "")) if item}


def _scope_string(value: Any) -> str | None:
    if isinstance(value, Mapping):
        trajectory = value.get("trajectory_id", value.get("trajectory"))
        instance = value.get("environment_instance_id", value.get("instance", "trajectory"))
        if trajectory is not None:
            return f"{trajectory}/{instance or 'trajectory'}"
    return None if value is None else str(value)


@dataclass(frozen=True)
class EvidenceBundle:
    question: str
    snapshot_epoch: int | None
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    state: tuple[StateView, ...] = field(default_factory=tuple)
    workflow: tuple[WorkflowView, ...] = field(default_factory=tuple)
    documents: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    retrieval_budget: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "snapshot_epoch": self.snapshot_epoch,
            "evidence": [item.to_dict() for item in self.evidence],
            "state": [item.to_dict() for item in self.state],
            "workflow": [item.to_dict() for item in self.workflow],
            "documents": [dict(item) for item in self.documents],
            "retrieval_budget": self.retrieval_budget,
        }


def _snapshot_from_store(store: EventStore, snapshot_id: str | int | None) -> MemorySnapshot | None:
    # Import lazily to avoid a module cycle at import time.
    from .core_builder import MemorySnapshot
    from .ir import ComputeNode, PublishedSnapshot, SourceEvent
    from .views import ViewBundle, build_views

    row = store.get_snapshot(snapshot_id)
    if not row:
        return None
    objects = store.snapshot_objects(row["snapshot_id"])
    events: list[SourceEvent] = []
    for event_row in objects["events"]:
        payload = event_row.get("payload", event_row)
        try:
            events.append(SourceEvent.from_dict(payload))
        except TypeError:
            continue
    evidence: list[Evidence] = []
    for evidence_row in objects["evidence"]:
        payload = evidence_row.get("payload", evidence_row)
        try:
            evidence.append(Evidence.from_dict(payload))
        except TypeError:
            continue
    nodes: list[ComputeNode] = []
    for node_row in objects["nodes"]:
        payload = node_row.get("payload", node_row)
        try:
            nodes.append(ComputeNode.from_dict(payload))
        except TypeError:
            continue
    published = PublishedSnapshot(
        epoch=int(row["epoch"]),
        parent_epoch=row.get("parent_epoch"),
        object_versions=(row.get("payload") or {}).get("object_versions", {}),
        index_manifest=(row.get("payload") or {}).get("index_manifest", {}),
        included_event_frontier=row.get("included_event_frontier", {}),
        included_update_ids=tuple(row.get("included_update_ids", [])),
        checksum=str(row.get("checksum", "")),
    )
    view = build_views(evidence, events=events)
    return MemorySnapshot(
        published=published,
        events=tuple(events),
        evidence=tuple(evidence),
        nodes=tuple(nodes),
        views=view,
        metadata={"loaded_from_store": True},
        store=store,
    )


def retrieve(
    snapshot: MemorySnapshot,
    question: str,
    retrieval_budget: int | Mapping[str, Any] | None = None,
) -> EvidenceBundle:
    if isinstance(retrieval_budget, Mapping):
        budget = int(retrieval_budget.get("k", retrieval_budget.get("top_k", 8)) or 8)
    else:
        budget = int(retrieval_budget or 8)
    budget = max(0, budget)
    query_tokens = _tokens(question)
    scored: list[tuple[float, str, Evidence, Mapping[str, Any]]] = []
    for item in snapshot.evidence:
        text_tokens = _tokens(" ".join((item.subject_ref or "", item.predicate or "", str(item.value or ""), item.event_kind)))
        overlap = len(query_tokens & text_tokens)
        # Exact predicate/subject matches are useful tie-breakers.  Source
        # provenance remains attached; no fuzzy embedding equality is used.
        score = float(overlap)
        if item.predicate and item.predicate.lower() in query_tokens:
            score += 1.5
        if item.subject_ref and item.subject_ref.lower() in query_tokens:
            score += 1.0
        doc = {
            "id": item.evidence_id,
            "kind": "evidence",
            "score": score,
            "scope": item.valid_scope,
            "source_refs": list(item.source_refs),
        }
        scored.append((score, item.evidence_id, item, doc))
    scored.sort(key=lambda row: (-row[0], row[1]))
    selected = scored[:budget]
    selected_ids = {item.evidence_id for _, _, item, _ in selected}
    selected_scopes = {
        scope for _, _, item, _ in selected if (scope := _scope_string(item.valid_scope)) is not None
    }
    # Add view records for scopes represented by selected evidence.  For an
    # empty lexical match, expose the first deterministic scopes within budget.
    state_rows = list(snapshot.views.state.values())
    workflow_rows = list(snapshot.views.workflow.values())
    if selected_scopes:
        state_rows = [row for row in state_rows if row.scope in selected_scopes]
        workflow_rows = [row for row in workflow_rows if row.scope in selected_scopes]
    state_rows = sorted(state_rows, key=lambda row: row.scope)[: max(1, min(2, budget))] if budget else []
    workflow_rows = sorted(workflow_rows, key=lambda row: row.scope)[: max(1, min(2, budget))] if budget else []
    docs = [doc for _, _, _, doc in selected]
    return EvidenceBundle(
        question=str(question),
        snapshot_epoch=snapshot.epoch,
        evidence=tuple(item for _, _, item, _ in selected),
        state=tuple(state_rows),
        workflow=tuple(workflow_rows),
        documents=tuple(docs),
        retrieval_budget=budget,
    )


def query_snapshot(
    snapshot_id: str | int,
    question: str,
    retrieval_budget: int | Mapping[str, Any] | None = None,
    *,
    store: EventStore | None = None,
    snapshot: MemorySnapshot | None = None,
) -> EvidenceBundle:
    target = snapshot
    if target is None and store is not None:
        target = _snapshot_from_store(store, snapshot_id)
    if target is None:
        raise KeyError(f"snapshot {snapshot_id!r} is not available")
    return retrieve(target, question, retrieval_budget)


def query(
    snapshot_id: str | int | MemorySnapshot,
    question: str,
    retrieval_budget: int | Mapping[str, Any] | None = None,
    *,
    store: EventStore | None = None,
) -> EvidenceBundle:
    if isinstance(snapshot_id, MemorySnapshot):
        return retrieve(snapshot_id, question, retrieval_budget)
    return query_snapshot(snapshot_id, question, retrieval_budget, store=store)


__all__ = ["EvidenceBundle", "retrieve", "query_snapshot", "query"]
