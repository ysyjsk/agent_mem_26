"""Materialized state/relation/workflow views derived from evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .ir import Evidence, SourceEvent, canonical_json, stable_hash


def _scope(event: SourceEvent | None = None, evidence: Evidence | None = None) -> str:
    if event is not None:
        return f"{event.trajectory_id}/{event.environment_instance_id or 'trajectory'}"
    value = evidence.valid_scope if evidence is not None else None
    if isinstance(value, Mapping):
        trajectory = value.get("trajectory_id", value.get("trajectory", "unknown"))
        instance = value.get("environment_instance_id", value.get("instance", "trajectory"))
        return f"{trajectory}/{instance}"
    return str(value or "unknown/trajectory")


def _evidence_scope(evidence: Evidence, events: Mapping[str, SourceEvent]) -> str:
    """Resolve scope from explicit evidence scope or its source event."""
    if evidence.valid_scope is not None:
        return _scope(evidence=evidence)
    for ref in evidence.source_refs:
        event = events.get(ref)
        if event is not None:
            return _scope(event=event)
    return _scope(evidence=evidence)


def _evidence_key(evidence: Evidence, scope: str) -> str:
    return f"{scope}|{evidence.subject_ref or '?'}|{evidence.predicate}"


def _source_order(evidence: Evidence, events: Mapping[str, SourceEvent]) -> tuple[int, int, str]:
    candidates = [events[ref] for ref in evidence.source_refs if ref in events]
    if not candidates:
        return (0, evidence.revision, evidence.evidence_id)
    latest = max(candidates, key=lambda item: (item.source_sequence, item.source_revision, item.event_id))
    return (latest.source_sequence, latest.source_revision, evidence.evidence_id)


@dataclass(frozen=True)
class StateView:
    scope: str
    values: Mapping[str, Any] = field(default_factory=dict)
    aliases: Mapping[str, str] = field(default_factory=dict)
    relations: Mapping[str, Any] = field(default_factory=dict)
    history: tuple[str, ...] = field(default_factory=tuple)
    source_versions: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "values": dict(self.values),
            "aliases": dict(self.aliases),
            "relations": dict(self.relations),
            "history": list(self.history),
            "source_versions": dict(self.source_versions),
        }

    @property
    def content_hash(self) -> str:
        return stable_hash({"scope": self.scope, "values": self.values, "aliases": self.aliases, "relations": self.relations})

    @property
    def provenance_hash(self) -> str:
        return stable_hash({"history": self.history, "source_versions": self.source_versions})


@dataclass(frozen=True)
class WorkflowView:
    scope: str
    stages: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    program_notes: tuple[str, ...] = field(default_factory=tuple)
    experiences: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    source_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "stages": [dict(stage) for stage in self.stages],
            "program_notes": list(self.program_notes),
            "experiences": [dict(item) for item in self.experiences],
            "source_refs": list(self.source_refs),
        }

    @property
    def content_hash(self) -> str:
        return stable_hash({"scope": self.scope, "stages": self.stages, "program_notes": self.program_notes, "experiences": self.experiences})

    @property
    def provenance_hash(self) -> str:
        return stable_hash(self.source_refs)


@dataclass(frozen=True)
class ViewBundle:
    state: Mapping[str, StateView] = field(default_factory=dict)
    workflow: Mapping[str, WorkflowView] = field(default_factory=dict)
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    index_documents: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": {key: value.to_dict() for key, value in self.state.items()},
            "workflow": {key: value.to_dict() for key, value in self.workflow.items()},
            "evidence": [item.to_dict() for item in self.evidence],
            "index_documents": [dict(item) for item in self.index_documents],
        }


def build_state_views(
    evidence: Iterable[Evidence],
    *,
    events: Mapping[str, SourceEvent] | Iterable[SourceEvent] | None = None,
) -> dict[str, StateView]:
    event_map: dict[str, SourceEvent] = {}
    if events is not None:
        event_map = events if isinstance(events, Mapping) else {item.event_id: item for item in events}
    grouped: dict[str, list[Evidence]] = {}
    for item in evidence:
        grouped.setdefault(_evidence_scope(item, event_map), []).append(item)
    views: dict[str, StateView] = {}
    for scope, items in grouped.items():
        values: dict[str, Any] = {}
        aliases: dict[str, str] = {}
        relations: dict[str, Any] = {}
        history: list[str] = []
        source_versions: dict[str, Any] = {}
        # Preserve evidence order for provenance but resolve current values by
        # source sequence/revision rather than worker completion order.
        for item in sorted(items, key=lambda row: _source_order(row, event_map)):
            history.append(item.evidence_id)
            source_versions[item.evidence_id] = dict(item.source_versions)
            predicate = (item.predicate or "").strip().lower()
            key = str(item.subject_ref or "?")
            if predicate in {"alias", "also_known_as", "aka"} and item.value is not None:
                aliases[str(item.value)] = key
            elif predicate in {"relates_to", "relation", "related_to", "depends_on", "parent_of", "child_of"}:
                relations[f"{key}|{predicate}"] = item.value
            # Attempts/failures are retained in history but do not overwrite a
            # successful observed state.  A confirmation/observation can
            # replace an older attempt or failure.
            if item.event_kind in {"attempt", "intent"}:
                continue
            if item.event_kind == "failure" and key in values and values[key] is not None:
                continue
            # State projections keep observed properties under the subject
            # key.  Action/outcome evidence remains historical metadata (or a
            # separate predicate key) and cannot overwrite the current state
            # merely because it arrived later.
            if predicate in {"state", "status", "property", "attribute", "value"}:
                values[key] = item.value
            elif item.event_kind == "confirmation":
                values[f"{key}|{predicate}"] = item.value
        views[scope] = StateView(
            scope=scope,
            values=values,
            aliases=aliases,
            relations=relations,
            history=tuple(history),
            source_versions=source_versions,
        )
    return views


def build_workflow_views(
    evidence: Iterable[Evidence],
    *,
    events: Mapping[str, SourceEvent] | Iterable[SourceEvent] | None = None,
) -> dict[str, WorkflowView]:
    event_map: dict[str, SourceEvent] = {}
    if events is not None:
        event_map = events if isinstance(events, Mapping) else {item.event_id: item for item in events}
    grouped: dict[str, list[Evidence]] = {}
    for item in evidence:
        grouped.setdefault(_evidence_scope(item, event_map), []).append(item)
    views: dict[str, WorkflowView] = {}
    for scope, items in grouped.items():
        ordered = sorted(items, key=lambda row: _source_order(row, event_map))
        stages: list[dict[str, Any]] = []
        notes: list[str] = []
        experiences: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for item in ordered:
            source_event = next((event_map[ref] for ref in item.source_refs if ref in event_map), None)
            stage_name = str(item.valid_scope.get("stage")) if isinstance(item.valid_scope, Mapping) and item.valid_scope.get("stage") else None
            if stage_name is None:
                stage_name = item.predicate or item.event_kind or "step"
            if current is None or current.get("stage") != stage_name:
                current = {"stage": stage_name, "evidence_ids": [], "status": "in_progress"}
                stages.append(current)
            current["evidence_ids"].append(item.evidence_id)
            if item.event_kind == "failure":
                current["status"] = "failed"
            elif item.event_kind == "confirmation":
                current["status"] = "completed"
            if item.event_kind in {"failure", "confirmation"}:
                experiences.append(
                    {
                        "evidence_id": item.evidence_id,
                        "kind": item.event_kind,
                        "predicate": item.predicate,
                        "value": item.value,
                        "source_refs": list(item.source_refs),
                    }
                )
            if item.predicate in {"procedure", "program_note", "how_to", "tip"} and item.value is not None:
                notes.append(str(item.value))
            if source_event and source_event.goal and not notes:
                notes.append(str(source_event.goal))
        views[scope] = WorkflowView(
            scope=scope,
            stages=tuple(stages),
            program_notes=tuple(dict.fromkeys(notes)),
            experiences=tuple(experiences),
            source_refs=tuple(item.evidence_id for item in ordered),
        )
    return views


def make_index_documents(
    evidence: Iterable[Evidence],
    state: Mapping[str, StateView],
    workflow: Mapping[str, WorkflowView],
    *,
    events: Mapping[str, SourceEvent] | Iterable[SourceEvent] | None = None,
) -> list[dict[str, Any]]:
    event_map: dict[str, SourceEvent] = {}
    if events is not None:
        event_map = events if isinstance(events, Mapping) else {item.event_id: item for item in events}
    docs: list[dict[str, Any]] = []
    for item in evidence:
        # Index documents are generated after the state/workflow scopes have
        # been materialized; use the source event scope if valid_scope is not
        # explicit so cross-trajectory records stay isolated.
        scope = _evidence_scope(item, event_map)
        docs.append(
            {
                "id": item.evidence_id,
                "scope": scope,
                "text": " ".join(
                    str(part)
                    for part in (item.subject_ref or "", item.predicate or "", item.value or "")
                    if part != ""
                ),
                "kind": "evidence",
                "source_refs": list(item.source_refs),
                "content_hash": item.content_hash,
                "provenance_hash": item.provenance_hash,
            }
        )
    for scope, view in state.items():
        docs.append(
            {
                "id": f"state:{scope}",
                "scope": scope,
                "text": canonical_json(view.values),
                "kind": "state",
                "source_refs": list(view.history),
                "content_hash": view.content_hash,
                "provenance_hash": view.provenance_hash,
            }
        )
    for scope, view in workflow.items():
        docs.append(
            {
                "id": f"workflow:{scope}",
                "scope": scope,
                "text": canonical_json(view.to_dict()),
                "kind": "workflow",
                "source_refs": list(view.source_refs),
                "content_hash": view.content_hash,
                "provenance_hash": view.provenance_hash,
            }
        )
    return docs


def build_views(
    evidence: Sequence[Evidence],
    *,
    events: Mapping[str, SourceEvent] | Iterable[SourceEvent] | None = None,
) -> ViewBundle:
    state = build_state_views(evidence, events=events)
    workflow = build_workflow_views(evidence, events=events)
    return ViewBundle(
        state=state,
        workflow=workflow,
        evidence=tuple(evidence),
        index_documents=tuple(make_index_documents(evidence, state, workflow, events=events)),
    )


__all__ = [
    "StateView",
    "WorkflowView",
    "ViewBundle",
    "build_state_views",
    "build_workflow_views",
    "build_views",
    "make_index_documents",
]
