"""Lossless, auditable source-field evidence for quality experiments.

The construction model remains the source of semantic evidence.  This module
only preserves exact fields that a bounded semantic prompt can otherwise lose
(commands, URLs, explicit failure spans and control state).  Every record is
versioned and carries a source path/span; it is therefore part of the
published memory and never an evaluator answer or a hidden gold lookup.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .ir import Evidence, SourceEvent, stable_hash


VERSION = "source-literals-v1"
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'`]+", re.IGNORECASE)
_ERROR = re.compile(
    r"(?:\bfail(?:ed|ure)?\b|\berror\b|\bexception\b|\bdenied\b|\bforbidden\b|"
    r"\btimeout\b|\bblocked\b|\binvalid\b|\bcannot\b|\bcan't\b|\bunable\b|"
    r"\bnot allowed\b|\bwait (?:a|some) while\b|\bno more\b|\btoo many\b)",
    re.IGNORECASE,
)
_OPERATOR = re.compile(
    r"\b(?:starts? with|ends? with|contains?|equals?|is not|not equal|"
    r"greater than|less than|before|after|between|matches?)\b", re.IGNORECASE,
)
_CONTROL = re.compile(
    r"\b(?:combobox|checkbox|radio|option|textbox|button|listbox|select|input)\b",
    re.IGNORECASE,
)
_CONTROL_STATE = re.compile(
    r"(?:\bvalue\s*=|\bselected\s*=|\bchecked\s*=|\bdisabled(?:\s*=|\b)|"
    r"\b(?:starts? with|is empty)\b)", re.IGNORECASE,
)


def _scope(event: SourceEvent) -> str:
    return f"{event.trajectory_id}/{event.environment_instance_id or 'trajectory'}"


def _kind(outcome: Any) -> str:
    text = str(outcome or "").lower()
    if _ERROR.search(text):
        return "failure"
    if text and any(word in text for word in ("success", "succeeded", "completed", "done", "ok", "true")):
        return "confirmation"
    return "observation"


def _record(event: SourceEvent, *, predicate: str, value: Any, path: str,
            event_kind: str = "observation", span: Mapping[str, Any] | None = None) -> Evidence:
    marker = {"version": VERSION, "event": event.event_id, "predicate": predicate,
              "value": value, "path": path, "span": dict(span or {})}
    evidence_id = f"{event.event_id}:literal:{predicate}:{stable_hash(marker)[:12]}"
    return Evidence(
        evidence_id=evidence_id,
        source_refs=(event.event_id,),
        source_versions={event.event_id: event.source_revision},
        source_spans=(dict(span or {"path": path, "version": VERSION}),),
        subject_ref=f"{_scope(event)}:source",
        predicate=predicate,
        value=value,
        modality="source_literal",
        certainty="source_exact",
        event_kind=event_kind,
        valid_scope=_scope(event),
        revision=event.source_revision,
    )


def _walk_scalars(value: Any, path: str = "$"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if isinstance(item, (str, int, float, bool)) or item is None:
                yield child, str(key).casefold(), item
            else:
                yield from _walk_scalars(item, child)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk_scalars(item, f"{path}[{index}]")


def literal_evidence(event: SourceEvent, *, version: str = VERSION,
                     max_records: int = 24) -> tuple[Evidence, ...]:
    """Return exact source-field facts, bounded and deterministically ordered."""
    if version != VERSION:
        raise ValueError(f"unsupported source literal version: {version!r}")
    pending: list[tuple[str, Any, str, str, Mapping[str, Any]]] = []
    seen: set[tuple[str, str, str]] = set()
    focus_terms = {token.casefold() for token in re.findall(r"[\w-]+", str(event.goal or "")) if len(token) > 2}
    focus_terms.update(token.casefold() for token in re.findall(r"[\w-]+", str(event.action or "")) if len(token) > 2)

    def add(predicate: str, value: Any, path: str, *, kind: str = "observation",
            span: Mapping[str, Any] | None = None) -> None:
        if value in (None, ""):
            return
        key = (predicate, str(value), path)
        if key in seen:
            return
        seen.add(key)
        focused = bool((span or {}).get("focused"))
        generic_cap = 4 if predicate == "control_state" and not focused else 12
        if sum(item[0] == predicate and not bool(item[4].get("focused")) for item in pending) >= generic_cap and not focused:
            return
        if sum(item[0] == predicate and bool(item[4].get("focused")) for item in pending) >= 12 and focused:
            return
        pending.append((predicate, value, path, kind,
                        {"version": VERSION, "path": path, **dict(span or {})}))

    if event.action not in (None, ""):
        add("action_command", event.action, "event.action", kind="attempt")
    if event.observed_outcome not in (None, ""):
        add("observed_outcome", event.observed_outcome, "event.observed_outcome", kind=_kind(event.observed_outcome))

    post = event.post_state_ref
    if isinstance(post, Mapping):
        # Direct URL is the primary exact field; nested URL aliases are also
        # preserved without importing any answer or question metadata.
        for path, key, value in _walk_scalars(post):
            if key in {"url", "observed_url", "current_url", "page_url", "href", "address"}:
                add("observed_url", value, path)
            elif key in {"operator", "comparison", "comparator", "filter_operator", "condition"}:
                add("control_operator", value, path)
            elif key in {"selected", "checked", "disabled", "expanded", "pressed"}:
                add("control_state", {"field": key, "value": value}, path)
            elif key in {"value", "selected_option", "input_value"} and value not in (None, ""):
                add("control_value", value, path)
        tree = post.get("accessibility_tree")
        if isinstance(tree, str):
            for index, raw in enumerate(tree.splitlines()):
                line = raw.strip()
                if not line:
                    continue
                path = f"post_state.accessibility_tree[{index}]"
                if _ERROR.search(line):
                    add("error_span", line, path, kind="failure", span={"line": index})
                if _CONTROL.search(line) and _CONTROL_STATE.search(line):
                    line_terms = {token.casefold() for token in re.findall(r"[\w-]+", line) if len(token) > 2}
                    focused = bool(line_terms & focus_terms) or "selected=true" in line.casefold() or "checked=true" in line.casefold()
                    add("control_state", line, path, span={"line": index, "focused": focused})
                selected_operator = ("selected=true" in line.casefold() or "value=" in line.casefold()
                                     or "operator" in line.casefold())
                if _OPERATOR.search(line) and selected_operator and (_CONTROL.search(line) or "operator" in line.casefold() or "filter" in line.casefold()):
                    add("control_operator", line, path, span={"line": index})
                for match in _URL.finditer(line):
                    add("observed_url", match.group(0).rstrip(".,;:)]}"), path,
                        span={"line": index, "column": match.start()})
    # Preserve an explicit URL if an adapter used a scalar post-state.
    if isinstance(post, str):
        for match in _URL.finditer(post):
            add("observed_url", match.group(0).rstrip(".,;:)]}"), "post_state_ref",
                span={"column": match.start()})
    priority = {"action_command": 0, "observed_outcome": 1, "observed_url": 2,
                "error_span": 3, "control_operator": 4, "control_value": 5,
                "control_state": 6}
    pending.sort(key=lambda row: (priority.get(row[0], 99),
                                  0 if bool(row[4].get("focused")) else 1,
                                  row[2], str(row[1])))
    return tuple(_record(event, predicate=predicate, value=value, path=path,
                         event_kind=kind, span=span)
                 for predicate, value, path, kind, span in pending[: int(max_records)])


__all__ = ["VERSION", "literal_evidence"]
