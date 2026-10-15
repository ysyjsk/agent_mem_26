"""Semantic and publication consistency checks for memory snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .core_builder import MemorySnapshot
from .event_store import EventStore, content_hash
from .ir import SourceEvent, stable_hash


@dataclass(frozen=True)
class ValidationReport:
    snapshot_id: str | None
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    checked_events: int = 0
    checked_evidence: int = 0
    checked_nodes: int = 0
    checked_views: int = 0

    @property
    def ok(self) -> bool:
        return self.valid

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "valid": self.valid,
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checked_events": self.checked_events,
            "checked_evidence": self.checked_evidence,
            "checked_nodes": self.checked_nodes,
            "checked_views": self.checked_views,
        }


def _load_snapshot(snapshot_id: str | int | None, store: EventStore | None) -> MemorySnapshot | None:
    if store is None:
        return None
    from .retrieval import _snapshot_from_store

    return _snapshot_from_store(store, snapshot_id)


def validate_snapshot(
    snapshot_id: str | int | None = None,
    *,
    snapshot: MemorySnapshot | None = None,
    store: EventStore | None = None,
) -> ValidationReport:
    if isinstance(snapshot_id, MemorySnapshot) and snapshot is None:
        snapshot = snapshot_id
        snapshot_id = snapshot.epoch
    target = snapshot or _load_snapshot(snapshot_id, store)
    if target is None:
        return ValidationReport(snapshot_id=None if snapshot_id is None else str(snapshot_id), valid=False, errors=("snapshot_not_found",))
    errors: list[str] = []
    warnings: list[str] = []
    events = list(target.events)
    evidence = list(target.evidence)
    nodes = list(target.nodes)
    event_ids = [item.event_id for item in events]
    evidence_ids = [item.evidence_id for item in evidence]
    node_ids = [item.node_id for item in nodes]
    if len(event_ids) != len(set(event_ids)):
        errors.append("duplicate_event_id")
    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("duplicate_evidence_id")
    if len(node_ids) != len(set(node_ids)):
        errors.append("duplicate_node_id")
    event_map = {item.event_id: item for item in events}
    for event in events:
        if not event.trajectory_id:
            errors.append(f"event_missing_trajectory:{event.event_id}")
        if event.source_sequence < 0:
            errors.append(f"event_negative_sequence:{event.event_id}")
        # SourceEvent computes a hash when absent.  If a caller supplied a
        # hash, compare it to the projected fields while allowing upstream
        # opaque fields to remain represented by their original hash.
        if not event.raw_content_hash:
            errors.append(f"event_missing_raw_hash:{event.event_id}")
    for item in evidence:
        if not item.source_refs:
            warnings.append(f"evidence_without_source:{item.evidence_id}")
        for ref in item.source_refs:
            if ref not in event_map:
                errors.append(f"evidence_unknown_source:{item.evidence_id}:{ref}")
        if item.event_kind not in {"intent", "attempt", "observation", "confirmation", "failure"}:
            errors.append(f"evidence_unknown_event_kind:{item.evidence_id}:{item.event_kind}")
        if item.event_kind in {"attempt", "intent"}:
            # This is a warning rather than an error: attempts are valid
            # evidence, but state views must not treat them as observations.
            warnings.append(f"non_confirming_evidence:{item.evidence_id}")
    # Node references and DAG consistency.
    node_map = {item.node_id: item for item in nodes}
    graph = target.graph
    if graph.nodes:
        if graph.has_cycle():
            errors.append("compute_graph_cycle")
        for node_id, predecessors in graph.edges.items():
            if node_id not in node_map:
                warnings.append(f"graph_node_not_persisted:{node_id}")
            for predecessor in predecessors:
                if predecessor not in graph.nodes:
                    errors.append(f"unknown_predecessor:{node_id}:{predecessor}")
    for node in nodes:
        for ref in node.output_refs:
            if ref.startswith("evidence:") and ref.split(":", 1)[1] not in set(evidence_ids):
                warnings.append(f"node_unknown_evidence_output:{node.node_id}:{ref}")
    # Every required view should have a corresponding scope and source history.
    for scope, view in target.views.state.items():
        if not scope:
            errors.append("empty_state_scope")
        for evidence_id in view.history:
            if evidence_id not in evidence_ids:
                errors.append(f"state_unknown_history:{scope}:{evidence_id}")
    for scope, view in target.views.workflow.items():
        if not scope:
            errors.append("empty_workflow_scope")
        for evidence_id in view.source_refs:
            if evidence_id not in evidence_ids:
                errors.append(f"workflow_unknown_source:{scope}:{evidence_id}")
    # Published checksum is over IR fields, not elapsed time or file order.
    published = target.published
    if published.checksum:
        expected_payload = {
            "epoch": published.epoch,
            "parent_epoch": published.parent_epoch,
            "object_versions": published.object_versions,
            "index_manifest": published.index_manifest,
            "included_event_frontier": published.included_event_frontier,
            "included_update_ids": published.included_update_ids,
        }
        expected_checksum = stable_hash(expected_payload)
        if expected_checksum != published.checksum:
            errors.append("snapshot_checksum_mismatch")
    if published.epoch < 1:
        errors.append("invalid_snapshot_epoch")
    if published.parent_epoch is not None and published.parent_epoch >= published.epoch:
        errors.append("invalid_snapshot_parent_epoch")
    return ValidationReport(
        snapshot_id=str(snapshot_id if snapshot_id is not None else target.epoch),
        valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
        checked_events=len(events),
        checked_evidence=len(evidence),
        checked_nodes=len(nodes),
        checked_views=len(target.views.state) + len(target.views.workflow),
    )


__all__ = ["ValidationReport", "validate_snapshot"]
