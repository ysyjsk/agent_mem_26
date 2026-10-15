"""Provider-independent Fresh and Incremental memory construction.

This module is the executable core of the workplan.  It intentionally keeps
model serving behind the small protocols in :mod:`workflow_memory.backends`:
without a backend, a deterministic structured extractor is used for offline
contract/correctness tests; when a backend is supplied, its exact request is
part of the node fingerprint and the call happens before the SQLite publish
transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import OrderedDict
import inspect
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Iterable, Mapping, Sequence

from .backends import ModelRequest, ModelResponse, backend_fingerprint
from .cache import CacheKey, NodeCache, make_cache_key
from .config import write_json
from .dependency import ComputeGraph, normalized_output, plan_graph
from .event_store import EventStore
from .ir import (
    ComputeNode,
    Evidence,
    PreparedUpdate,
    PublishedSnapshot,
    SourceEvent,
    canonical_json,
    normalize_trajectory,
    source_frontier,
    stable_hash,
)
from .source_literals import VERSION as SOURCE_LITERAL_VERSION, literal_evidence


class ConstructionError(RuntimeError):
    """Expected construction/publish failure."""


@dataclass(frozen=True)
class Snapshot:
    """A queryable immutable view of one published memory epoch."""

    snapshot_id: str
    published: PublishedSnapshot
    events: tuple[SourceEvent, ...] = field(default_factory=tuple)
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    nodes: tuple[ComputeNode, ...] = field(default_factory=tuple)
    state_view: Mapping[str, Any] = field(default_factory=dict)
    aliases: Mapping[str, Any] = field(default_factory=dict)
    relations: Mapping[str, Any] = field(default_factory=dict)
    workflow_view: Mapping[str, Any] = field(default_factory=dict)
    index: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    graph: ComputeGraph | None = None
    store_path: str = ":memory:"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def epoch(self) -> int:
        return self.published.epoch

    @property
    def parent_epoch(self) -> int | None:
        return self.published.parent_epoch

    @property
    def checksum(self) -> str:
        return self.published.checksum

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "published": self.published.to_dict(),
            "events": [item.to_dict() for item in self.events],
            "evidence": [item.to_dict() for item in self.evidence],
            "nodes": [item.to_dict() for item in self.nodes],
            "state_view": dict(self.state_view),
            "aliases": dict(self.aliases),
            "relations": dict(self.relations),
            "workflow_view": dict(self.workflow_view),
            "index": {key: list(value) for key, value in self.index.items()},
            "metadata": dict(self.metadata),
            "store_path": self.store_path,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], *, graph: ComputeGraph | None = None) -> "Snapshot":
        published = PublishedSnapshot.from_dict(payload.get("published", payload))
        return cls(
            snapshot_id=str(payload.get("snapshot_id", f"snapshot-{published.epoch}")),
            published=published,
            events=tuple(SourceEvent.from_dict(item) for item in payload.get("events", ())),
            evidence=tuple(Evidence.from_dict(item) for item in payload.get("evidence", ())),
            nodes=tuple(ComputeNode.from_dict(item) for item in payload.get("nodes", ())),
            state_view=payload.get("state_view", {}),
            aliases=payload.get("aliases", {}),
            relations=payload.get("relations", {}),
            workflow_view=payload.get("workflow_view", {}),
            index={str(key): tuple(str(x) for x in value) for key, value in payload.get("index", {}).items()},
            graph=graph,
            store_path=str(payload.get("store_path", ":memory:")),
            metadata=payload.get("metadata", {}),
        )


@dataclass(frozen=True)
class UpdateReceipt:
    """Lifecycle receipt; each stage is represented independently."""

    update_id: str
    source_event_ids: tuple[str, ...]
    accepted: bool
    prepared: bool
    committed: bool
    queryable: bool
    snapshot_id: str | None = None
    epoch: int | None = None
    snapshot: Snapshot | None = field(default=None, repr=False, compare=False)
    affected_scopes: tuple[str, ...] = field(default_factory=tuple)
    reused_node_ids: tuple[str, ...] = field(default_factory=tuple)
    invalidated_node_ids: tuple[str, ...] = field(default_factory=tuple)
    propagation_stopped_node_ids: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None
    timestamps: Mapping[str, str] = field(default_factory=dict)

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "update_id": self.update_id,
            "source_event_ids": list(self.source_event_ids),
            "accepted": self.accepted,
            "prepared": self.prepared,
            "committed": self.committed,
            "queryable": self.queryable,
            "snapshot_id": self.snapshot_id,
            "epoch": self.epoch,
            "has_snapshot": self.snapshot is not None,
            "affected_scopes": list(self.affected_scopes),
            "reused_node_ids": list(self.reused_node_ids),
            "invalidated_node_ids": list(self.invalidated_node_ids),
            "propagation_stopped_node_ids": list(self.propagation_stopped_node_ids),
            "error": self.error,
            "timestamps": dict(self.timestamps),
            "status": self.status,
        }


@dataclass(frozen=True)
class EvidenceBundle:
    snapshot_id: str
    epoch: int
    question: str
    evidence: tuple[Evidence, ...]
    state: Mapping[str, Any] = field(default_factory=dict)
    aliases: Mapping[str, Any] = field(default_factory=dict)
    relations: Mapping[str, Any] = field(default_factory=dict)
    workflow: Mapping[str, Any] = field(default_factory=dict)
    reader_answer: Any = None
    budget: int | None = None
    scores: Mapping[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "epoch": self.epoch,
            "question": self.question,
            "evidence": [item.to_dict() for item in self.evidence],
            "state": dict(self.state),
            "aliases": dict(self.aliases),
            "relations": dict(self.relations),
            "workflow": dict(self.workflow),
            "reader_answer": self.reader_answer,
            "budget": self.budget,
            "scores": dict(self.scores),
        }


@dataclass(frozen=True)
class ValidationReport:
    snapshot_id: str | None
    valid: bool
    checks: Mapping[str, bool]
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "valid": self.valid,
            "checks": dict(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "checked_at": self.checked_at,
        }


_REGISTRY: dict[str, Snapshot] = {}
_STORES: dict[str, EventStore] = {}
_CACHES: dict[str, NodeCache] = {}
# Optional request-only memoization.  This cache intentionally stores no model
# responses and is namespaced by the method-owned storage path.  It is off by
# default so historical request construction and cache identities remain
# byte-for-byte unchanged.
_REQUEST_MEMOS: dict[str, OrderedDict[str, ModelRequest]] = {}
_SNAPSHOT_STORE_PATHS: dict[str, str] = {}
_LOCK = threading.RLock()


def _locator_path() -> Path:
    return Path(os.environ.get("WORKFLOW_MEMORY_SNAPSHOT_INDEX", ".workflow_memory_snapshots.json")).expanduser().resolve()


def _record_snapshot_location(snapshot_id: str, store_path: str) -> None:
    if store_path == ":memory:":
        return
    path = _locator_path()
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not isinstance(existing, dict):
            existing = {}
    except (OSError, json.JSONDecodeError):
        existing = {}
    existing[str(snapshot_id)] = str(store_path)
    write_json(path, existing)


def _lookup_snapshot_location(snapshot_id: str) -> str | None:
    path = _locator_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        value = payload.get(str(snapshot_id)) if isinstance(payload, Mapping) else None
        return str(value) if value else None
    except (OSError, json.JSONDecodeError):
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _config_value(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, Mapping):
        if key in config:
            return config[key]
        algorithm = config.get("algorithm")
        if isinstance(algorithm, Mapping) and key in algorithm:
            return algorithm[key]
        paths = config.get("paths")
        if isinstance(paths, Mapping) and key in paths:
            return paths[key]
    return getattr(config, key, default)


def _store_path(config: Any) -> str:
    explicit = _config_value(config, "storage_path", None) or _config_value(config, "store_path", None)
    if explicit:
        if str(explicit) == ":memory:":
            return ":memory:"
        return str(Path(str(explicit)).expanduser().resolve())
    env = os.environ.get("WORKFLOW_MEMORY_STORE")
    if env:
        return str(Path(env).expanduser().resolve())
    return ":memory:"


def _store(config: Any) -> EventStore:
    path = _store_path(config)
    with _LOCK:
        if path not in _STORES:
            _STORES[path] = EventStore(path)
        return _STORES[path]


def _cache(config: Any) -> NodeCache:
    path = _store_path(config)
    with _LOCK:
        if path not in _CACHES:
            cache_path = None if path == ":memory:" else f"{path}.cache.json"
            _CACHES[path] = NodeCache(cache_path)
        return _CACHES[path]


def _event_key(event: SourceEvent) -> str:
    return f"event:{event.event_id}"


def _scope(event: SourceEvent) -> str:
    return f"{event.trajectory_id}/{event.environment_instance_id or 'trajectory'}"


def _event_sort_key(event: SourceEvent) -> tuple[Any, ...]:
    return (event.trajectory_id, event.source_sequence, event.source_revision, event.event_id)


def _context_for_event(events: Sequence[SourceEvent], index: int, window: int) -> list[SourceEvent]:
    """Return prefix-only context in the same trajectory/environment scope."""

    current = events[index]
    scope = (current.trajectory_id, current.environment_instance_id or "trajectory")
    prior = [
        item for item in events[: index + 1]
        if (item.trajectory_id, item.environment_instance_id or "trajectory") == scope
    ]
    return prior[-(max(0, window) + 1) :]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return canonical_json(value)
    except Exception:
        return str(value)


def _tokens(value: Any) -> set[str]:
    return {token.lower() for token in re.findall(r"[\w-]+", _text(value), flags=re.UNICODE) if len(token) > 1}


def _source_literals_enabled(config: Any = None) -> bool:
    value = _config_value(config, "source_literal_evidence", False)
    return bool(value)


def _extraction_request_cache_enabled(config: Any = None) -> bool:
    return bool(_config_value(config, "extraction_request_cache", False))


def _extraction_request_cache_limit(config: Any = None) -> int:
    value = int(_config_value(config, "extraction_request_cache_max_entries", 256) or 256)
    if value < 1:
        raise ConstructionError("extraction_request_cache_max_entries must be positive")
    return value


def _extraction_system_prompt(config: Any, *, strict: bool, projection: str) -> str:
    """Build the exact system prompt used by :func:`_extraction_request`."""

    prompt = _extract_prompt(strict, config)
    if projection == _MODEL_INPUT_PROJECTION_SALIENT:
        prompt += (
            "\n\nThe user payload may include evidence_signals with exact source literals. "
            "Treat them as observations, not inferences. Preserve exact spelling for "
            "action_command, observed_url, operator, explicit error_span, and control "
            "selected/value/disabled fields when emitting a useful local fact. "
            "Prefer an explicit failure or control state over a generic summary, and "
            "never claim a state change without an observed source field."
        )
    return prompt


def _extraction_request_memo_key(event: SourceEvent, context: Sequence[SourceEvent],
                                 config: Any, *, strict: bool, projection: str,
                                 prompt: str) -> str:
    """Fingerprint every input that can affect the exact ModelRequest bytes.

    The bounded memo stores requests, not responses.  Keep the full source
    event/context dictionaries in this key: dropping a field here would let a
    revised source silently reuse an old prompt.  ``extract_operator_version``
    is included as a conservative parser/request policy fence even when the
    current prompt bytes happen to be unchanged.
    """

    max_tokens = int(_config_value(config, "extraction_output_tokens", 1024) or 1024)
    temperature = float(_config_value(config, "temperature", 0.0) or 0.0)
    char_budget = int(_config_value(config, "model_input_char_budget", 6000) or 6000)
    context_window = int(_config_value(config, "source_context_window_events_default", 2) or 0)
    metadata = {"operator": "extract", "event_id": event.event_id, "strict_json": strict}
    if projection == _MODEL_INPUT_PROJECTION_SALIENT:
        metadata["model_input_projection"] = projection
    return stable_hash({
        "event": event.to_dict(),
        "context": [item.to_dict() for item in context],
        "request": {
            "system_prompt": prompt,
            "model": str(_config_value(config, "construction_model", "")) or None,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "images": [],
            "metadata": metadata,
            "model_input_projection": projection,
            "model_input_char_budget": char_budget,
            "strict_model_output": strict,
            "context_window": context_window,
            "prefix_only": True,
            "extract_operator_version": str(_config_value(config, "extract_operator_version", "2")),
        },
    })


def _extraction_request_memo_namespace(config: Any) -> str:
    """Return the method/store-owned namespace for request memoization.

    A storage path is the primary ownership boundary.  Some paired runners
    intentionally use one temporary store while switching construction
    methods, however, so include an explicit method identity when supplied.
    This keeps B0, Ours, and B3 request memos independent without changing
    historical configs that only provide ``storage_path``.
    """

    store = _store_path(config)
    method = None
    for key in ("method", "method_id", "construction_method", "algorithm_id"):
        value = _config_value(config, key, None)
        if value not in (None, ""):
            method = str(value)
            break
    return f"{store}::method={method}" if method is not None else store


def _extraction_request_memo_get(namespace: str, key: str) -> ModelRequest | None:
    with _LOCK:
        memo = _REQUEST_MEMOS.get(namespace)
        if memo is None:
            return None
        value = memo.get(key)
        if value is not None:
            memo.move_to_end(key)
        return value


def _extraction_request_memo_put(namespace: str, key: str, value: ModelRequest,
                                  *, limit: int) -> None:
    with _LOCK:
        memo = _REQUEST_MEMOS.setdefault(namespace, OrderedDict())
        memo[key] = value
        memo.move_to_end(key)
        while len(memo) > limit:
            memo.popitem(last=False)


def _clear_extraction_request_memo() -> None:
    """Clear optional request memoization for isolated tests/runs."""

    with _LOCK:
        _REQUEST_MEMOS.clear()


def _augment_source_literals(event: SourceEvent, extracted: Sequence[Evidence], config: Any) -> list[Evidence]:
    """Add exact source spans only for an explicitly versioned quality run."""

    rows = list(extracted)
    if not _source_literals_enabled(config):
        return rows
    version = str(_config_value(config, "source_literal_version", SOURCE_LITERAL_VERSION)
                  or SOURCE_LITERAL_VERSION)
    if version != SOURCE_LITERAL_VERSION:
        raise ConstructionError(f"unsupported source_literal_version={version!r}")
    rows.extend(literal_evidence(event, version=version))
    return rows


_MODEL_INPUT_PROJECTION_DEFAULT = "compact-v2"
_MODEL_INPUT_PROJECTION_SALIENT = "salient-v3"

# These are deliberately source-field names, not inferred semantics.  The
# upstream trajectory adapters use several aliases for the same values; the
# projection keeps all of them available to the extractor when a long state
# has to be clipped.  The old compact-v2 projection remains the default so
# old manifests/caches and their measurements are unchanged.
_SALIENT_URL_KEYS = {
    "url", "observed_url", "current_url", "page_url", "href", "address",
}
_SALIENT_COMMAND_KEYS = {
    "action_command", "command", "tool_call", "operation", "selector",
}
_SALIENT_OPERATOR_KEYS = {
    "operator", "comparison", "comparator", "filter_operator", "condition",
}
_SALIENT_CONTROL_KEYS = {
    "role", "aria_role", "control", "control_type", "name", "label", "text",
    "value", "selected", "checked", "disabled", "expanded", "pressed",
    "option", "selected_option", "input_value",
}
_SALIENT_STATE_KEYS = {"selected", "checked", "disabled", "expanded", "pressed"}
_SALIENT_FREE_TEXT_KEYS = {
    "thought", "goal", "screenshot", "text", "message", "description", "content",
}
_SALIENT_ERROR_RE = re.compile(
    r"(?:\bfail(?:ed|ure)?\b|\berror\b|\bexception\b|\bdenied\b|\bforbidden\b|"
    r"\btimeout\b|\bblocked\b|\binvalid\b|\bcannot\b|\bcan't\b|\bunable\b|"
    r"\bnot allowed\b|\bwait (?:a|some) while\b|\bno more\b|\btoo many\b)",
    flags=re.IGNORECASE,
)
_SALIENT_OPERATOR_RE = re.compile(
    r"\b(?:starts? with|ends? with|contains?|equals?|is not|not equal|"
    r"greater than|less than|before|after|between|matches?)\b",
    flags=re.IGNORECASE,
)
_SALIENT_STATE_RE = re.compile(
    r"\b(?:selected|checked|disabled|expanded|pressed)\s*[:=]\s*"
    r"(?:true|false|yes|no|on|off|0|1)\b",
    flags=re.IGNORECASE,
)
_SALIENT_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'`]+", flags=re.IGNORECASE)
_SALIENT_CONTROL_LINE_RE = re.compile(
    r"(?:\[[^\]]+\]\s*)?(?P<role>combobox|listbox|option|textbox|searchbox|"
    r"checkbox|radio|switch|slider|spinbutton)\s+"
    r"(?P<quote>['\"])(?P<label>.*?)(?P=quote)(?P<attrs>.*)$",
    flags=re.IGNORECASE,
)
_SALIENT_VALUE_ATTR_RE = re.compile(r"\bvalue\s*=\s*(['\"])(.*?)\1", flags=re.IGNORECASE)
_SALIENT_FLAG_ATTR_RE = re.compile(
    r"\b(?P<name>selected|checked|disabled|expanded|pressed)\s*=\s*"
    r"['\"]?(?P<value>true|false|yes|no|on|off|0|1)\b",
    flags=re.IGNORECASE,
)


def _projection_mode(config: Any = None) -> str:
    """Return the bounded source projection policy used in model requests."""

    mode = str(_config_value(config, "model_input_projection", _MODEL_INPUT_PROJECTION_DEFAULT)
               or _MODEL_INPUT_PROJECTION_DEFAULT)
    if mode not in {_MODEL_INPUT_PROJECTION_DEFAULT, _MODEL_INPUT_PROJECTION_SALIENT}:
        raise ConstructionError(
            f"unsupported model_input_projection={mode!r}; expected "
            f"{_MODEL_INPUT_PROJECTION_DEFAULT!r} or {_MODEL_INPUT_PROJECTION_SALIENT!r}"
        )
    return mode


def _signal_text(value: Any) -> str:
    """Render a scalar source value without inventing or normalizing content."""

    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    return ""


def _signal_path(path: Sequence[str], key: Any = None) -> str:
    parts = [str(item) for item in path]
    if key is not None:
        parts.append(str(key))
    return ".".join(parts) or "$"


def _append_signal(rows: list[Any], value: Any, *, limit: int = 8) -> None:
    """Append a deterministic, de-duplicated source fragment."""

    if value in (None, "", {}, []):
        return
    if value in rows or len(rows) >= limit:
        return
    rows.append(value)


def _salient_source_fields(value: Any, *, char_budget: int = 768,
                          action: Any = None, previous: Any = None) -> dict[str, Any]:
    """Extract bounded *literal* source spans that generic clipping can hide.

    This helper intentionally does not infer facts or change the normalized
    source.  It merely copies exact URLs, action/operator values, control
    state fields and lines containing explicit failure/status markers into a
    separately named projection.  The projection is opt-in (``salient-v3``)
    and appears in the request/cache fingerprint, so old compact-v2 runs are
    not silently mixed with a quality candidate.
    """

    budget = max(256, int(char_budget))
    urls: list[dict[str, str]] = []
    commands: list[dict[str, str]] = []
    operators: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    state_spans: list[dict[str, str]] = []
    controls: list[dict[str, Any]] = []
    seen: set[str] = set()
    nodes = 0
    target_ids = set(re.findall(
        r"\b(?:click|fill|select_option|check|uncheck|hover|press)\s*\(\s*['\"]([^'\"]+)['\"]",
        _text(action),
    ))
    old_tree = previous.get("accessibility_tree", "") if isinstance(previous, Mapping) else previous
    old_lines = {line.strip() for line in str(old_tree or "").splitlines()}

    def add(category: list[Any], record: Any, limit: int = 8) -> None:
        key = canonical_json(record)
        if key in seen or len(category) >= limit:
            return
        # Keep every record bounded independently; long accessibility lines
        # should never crowd all other categories out of the request.
        if len(canonical_json(record)) > 512:
            return
        seen.add(key)
        category.append(record)

    def line_scan(text: str, path: str) -> None:
        text = str(text)
        for match in _SALIENT_URL_RE.finditer(text):
            literal = match.group(0).rstrip(".,;:)]}")
            add(urls, {"path": path, "value": literal})
        lines = text.splitlines(keepends=True) or [text]
        offset = 0
        for index, line in enumerate(lines):
            literal = line.strip()
            leading = len(line) - len(line.lstrip())
            start, end = offset + leading, offset + leading + len(literal)
            offset += len(line)
            if not literal:
                continue
            line_path = f"{path}[{index}]" if len(lines) > 1 else path
            control = _SALIENT_CONTROL_LINE_RE.match(literal)
            if control is not None:
                record: dict[str, Any] = {
                    "path": line_path,
                    "role": control.group("role"),
                    "name": control.group("label"),
                    "source_span": [start, end],
                }
                control_id = re.match(r"\[([^\]]+)\]", literal)
                if control_id is not None:
                    record["control_id"] = control_id.group(1)
                value = _SALIENT_VALUE_ATTR_RE.search(control.group("attrs"))
                if value is not None:
                    record["control_value"] = value.group(2)
                for flag in _SALIENT_FLAG_ATTR_RE.finditer(control.group("attrs")):
                    normalized = flag.group("value").casefold()
                    record[f"control_{flag.group('name').casefold()}"] = normalized in {"true", "yes", "on", "1"}
                if any(key.startswith("control_") for key in record):
                    label = str(record.get("name", "")).casefold()
                    explicit_selection = any(name in record for name in (
                        "control_selected", "control_checked", "control_disabled",
                    ))
                    explicit_value = "control_value" in record
                    explicit_state = explicit_selection or explicit_value
                    changed = previous is not None and literal not in old_lines
                    state_related = any(term in label for term in (
                        "state", "serial number", "consumed", "none", "starts with",
                    ))
                    selected_true = any(record.get(name) is True for name in (
                        "control_selected", "control_checked",
                    ))
                    selected_false = any(record.get(name) is False for name in (
                        "control_selected", "control_checked",
                    ))
                    value_text = str(record.get("control_value", "")).casefold()
                    selected_true_semantic = selected_true and (state_related or value_text == "-- none --")
                    record["_priority"] = (
                        0 if record.get("control_id") in target_ids else
                        1 if selected_true_semantic else
                        2 if selected_false and any(term in label for term in ("state", "consumed", "none")) else
                        3 if explicit_value and state_related else
                        4 if explicit_selection else
                        5 if changed and state_related else
                        6 if changed else 7
                    )
                    add(controls, record, limit=4096)
            if _SALIENT_ERROR_RE.search(literal):
                add(errors, {"path": line_path, "value": literal, "source_span": [start, end]})
            if _SALIENT_OPERATOR_RE.search(literal):
                if control is not None and (value is not None or any(
                        flag.group("value").casefold() == "true"
                        for flag in _SALIENT_FLAG_ATTR_RE.finditer(control.group("attrs")))):
                    add(operators, {"path": line_path, "value": literal, "source_span": [start, end]})
            if _SALIENT_STATE_RE.search(literal):
                add(state_spans, {"path": line_path, "value": literal})

    def visit(node: Any, path: tuple[str, ...]) -> None:
        nonlocal nodes
        nodes += 1
        # AX trees can be very large.  A hard traversal cap bounds CPU work,
        # while category limits keep the resulting request small and stable.
        if nodes > 4096:
            return
        if isinstance(node, Mapping):
            normalized = {str(key).casefold(): key for key in node}
            controls_present = any(key in normalized for key in _SALIENT_CONTROL_KEYS)
            if controls_present:
                record: dict[str, Any] = {"path": _signal_path(path)}
                for name in sorted(_SALIENT_CONTROL_KEYS):
                    original = normalized.get(name)
                    if original is None:
                        continue
                    scalar = node[original]
                    if isinstance(scalar, (str, int, float, bool)) or scalar is None:
                        if name in _SALIENT_STATE_KEYS:
                            record[f"control_{name}"] = scalar
                        elif name in {"value", "selected_option", "input_value"}:
                            record["control_value"] = scalar
                        else:
                            record[name] = scalar
                if len(record) > 1:
                    add(controls, record, limit=12)
            for key in sorted(node, key=lambda item: str(item).casefold()):
                key_text = str(key)
                key_folded = key_text.casefold()
                item = node[key]
                # Free-form thoughts/descriptions can contain future plans or
                # unrelated URLs. They are intentionally outside this
                # prefix-visible source projection; explicit accessibility
                # lines, URLs, actions and structured state keys remain.
                if key_folded in _SALIENT_FREE_TEXT_KEYS:
                    continue
                scalar = _signal_text(item)
                item_path = _signal_path(path, key_text)
                if scalar:
                    if key_folded in _SALIENT_URL_KEYS:
                        add(urls, {"path": item_path, "value": scalar})
                    if key_folded in _SALIENT_COMMAND_KEYS or key_folded == "action":
                        add(commands, {"path": item_path, "value": scalar})
                    if key_folded in _SALIENT_OPERATOR_KEYS:
                        add(operators, {"path": item_path, "value": scalar})
                    if key_folded in {"error", "error_message", "failure", "failure_message", "status"}:
                        if _SALIENT_ERROR_RE.search(scalar):
                            add(errors, {"path": item_path, "value": scalar})
                    # Free-form thoughts/goals are plans or narration, not
                    # observed UI facts.  Do not turn future actions in them
                    # into salient evidence; accessibility_tree and explicit
                    # scalar state fields remain eligible.
                    if key_folded not in {"thought", "goal", "description", "text", "screenshot"}:
                        line_scan(scalar, item_path)
                if key_folded not in {"thought", "goal", "description", "text", "screenshot"}:
                    visit(item, path + (key_text,))
            return
        if isinstance(node, (list, tuple)):
            for index, item in enumerate(node):
                visit(item, path + (str(index),))
            return
        if isinstance(node, str):
            line_scan(node, _signal_path(path))

    visit(value, ())
    controls.sort(key=lambda row: (row.get("_priority", 4), row.get("path", ""), canonical_json(row)))
    controls = [{key: item for key, item in row.items() if key != "_priority"} for row in controls]
    result: dict[str, Any] = {}
    # Failure/status literals get first claim on the side-channel budget;
    # otherwise a dense AXTree full of controls could hide the one error line
    # that caused the quality failure. URL/action and control values follow.
    for key, rows in (("action_command", commands), ("observed_url", urls),
                      ("error_span", errors), ("controls", controls),
                      ("operator", operators), ("state_span", state_spans)):
        if key == "controls" and budget < 900:
            # Reserve room for one explicitly rendered filter operator after
            # the highest-priority action/changed control values.
            rows = rows[:2]
        if rows:
            result[key] = rows
    if not result:
        return {}
    # Trim by serialized size while retaining category order.  A record is
    # only dropped when the complete explicit projection cannot fit; no
    # partial string is fabricated and the original compact state remains.
    trimmed: dict[str, Any] = {"source_projection_version": _MODEL_INPUT_PROJECTION_SALIENT}
    remaining = budget - len(canonical_json(trimmed))
    for key, rows in result.items():
        selected: list[Any] = []
        for row in rows:
            candidate = {key: [*selected, row]}
            if len(canonical_json(candidate)) > remaining and selected:
                break
            if len(canonical_json(candidate)) > remaining:
                continue
            selected.append(row)
        if selected:
            trimmed[key] = selected
            remaining = max(0, remaining - len(canonical_json({key: selected})))
    return trimmed


def _strip_planning_fields(value: Any) -> Any:
    """Remove free-form plans before the opt-in quality prompt is rendered."""
    if isinstance(value, Mapping):
        return {key: _strip_planning_fields(item) for key, item in value.items()
                if str(key).casefold() not in {"thought", "goal"}}
    if isinstance(value, (list, tuple)):
        return [_strip_planning_fields(item) for item in value]
    return value


def _compact_for_model(value: Any, *, char_budget: int = 6000) -> Any:
    """Keep model prompts bounded without changing source hashes or views.

    LongMemEval accessibility trees can be hundreds of thousands of
    characters.  The complete source remains in ``SourceEvent`` and the
    cache key; only the provider request is clipped to a deterministic,
    prefix-visible projection.  This prevents a single event from exhausting
    the local GPU while retaining URL/action/outcome and both tree boundaries.
    """

    if value is None or isinstance(value, (bool, int, float)):
        return value
    char_budget = max(32, int(char_budget))
    if isinstance(value, str):
        if len(value) <= char_budget:
            return value
        marker = "\n...[truncated]...\n"
        if char_budget <= len(marker):
            return value[:char_budget]
        available = char_budget - len(marker)
        head = max(1, available * 2 // 3)
        tail = max(1, available - head)
        return value[:head] + marker + value[-tail:]
    if isinstance(value, Mapping):
        preferred = (
            # These names are used by the explicit event projection below and
            # keep the identity/scope and both state boundaries visible.
            "event_id",
            "scope",
            "trajectory_id",
            "environment_instance_id",
            "source_sequence",
            "goal",
            "action",
            "pre_state",
            "post_state",
            "observed_outcome",
            # State records should expose their AXTree before less useful
            # metadata.  The previous fixed per-field decrement could exhaust
            # the budget on sorted bookkeeping fields first.
            "url",
            "title",
            "accessibility_tree",
            "thought",
            "screenshot",
            "state_index",
            "step",
        )
        keys = [key for key in preferred if key in value]
        keys.extend(sorted(str(key) for key in value if str(key) not in keys))
        result: dict[str, Any] = {}
        remaining = char_budget
        for key in keys:
            if key not in value:
                continue
            # Allocate from the actual compacted value, not a nominal fixed
            # field size.  This prevents short URL/metadata fields from
            # consuming a full 1200-character allowance and dropping the
            # pre/post state or AXTree prematurely.
            if remaining <= 0:
                break
            key_text = str(key)
            # Leave a small amount for each state boundary when possible.
            reserve = 96 if key_text in {"pre_state", "post_state", "accessibility_tree"} else 0
            field_budget = max(32, remaining - reserve)
            field_budget = min(field_budget, 2400 if key_text in {"pre_state", "post_state", "accessibility_tree", "thought"} else field_budget)
            compacted = _compact_for_model(value[key], char_budget=field_budget)
            result[key_text] = compacted
            used = len(canonical_json({key_text: compacted}))
            remaining = max(0, remaining - used)
        return result
    if isinstance(value, (list, tuple)):
        rows: list[Any] = []
        remaining = char_budget
        for item in value:
            if remaining <= 0:
                break
            compacted = _compact_for_model(item, char_budget=min(1200, remaining))
            rows.append(compacted)
            remaining = max(0, remaining - len(canonical_json(compacted)))
        return rows
    return _compact_for_model(str(value), char_budget=char_budget)


def _compact_event_projection(event: SourceEvent, *, char_budget: int,
                              projection: str = _MODEL_INPUT_PROJECTION_DEFAULT) -> dict[str, Any]:
    """Project one event without letting bookkeeping hide its state edges."""

    budget = max(256, int(char_budget))
    if projection == _MODEL_INPUT_PROJECTION_SALIENT:
        # The opt-in side channel is part of the same bounded request, not an
        # unmetered append to compact-v2. Reserve one quarter for each
        # compact state and one quarter for each literal signal projection.
        state_budget = max(128, budget // 5)
        metadata_budget = max(128, budget - (4 * state_budget))
    else:
        state_budget = max(128, budget // 3)
        metadata_budget = max(128, budget - (2 * state_budget))
    metadata = {
        "event_id": event.event_id,
        "scope": _scope(event),
        "trajectory_id": event.trajectory_id,
        "environment_instance_id": event.environment_instance_id or "trajectory",
        "source_sequence": event.source_sequence,
        "goal": event.goal,
        "action": event.action,
        "observed_outcome": event.observed_outcome,
    }
    compacted = _compact_for_model(metadata, char_budget=metadata_budget)
    # Keep the semantic fields addressable even if an unusually long goal or
    # action consumed the small metadata budget.  Their values are still
    # compacted; this only avoids silently changing the schema seen by the
    # model.
    for key, value in (("goal", event.goal), ("action", event.action), ("observed_outcome", event.observed_outcome)):
        compacted.setdefault(key, _compact_for_model(value, char_budget=max(32, metadata_budget // 4)))
    # Keep these keys present even when the source side is genuinely absent;
    # null is more informative to the extractor than silently omitting a
    # boundary. Small URL/title facts precede the potentially enormous tree.
    def visible_state(source: Any) -> Any:
        if isinstance(source, Mapping):
            return {key: visible_state(item) for key, item in source.items()
                    if str(key).casefold() not in _SALIENT_FREE_TEXT_KEYS | {"action", "command"}}
        if isinstance(source, (list, tuple)):
            return [visible_state(item) for item in source]
        return source

    pre_state = visible_state(event.pre_state_ref) if projection == _MODEL_INPUT_PROJECTION_SALIENT else event.pre_state_ref
    post_state = visible_state(event.post_state_ref) if projection == _MODEL_INPUT_PROJECTION_SALIENT else event.post_state_ref
    compacted["pre_state"] = _compact_for_model(pre_state, char_budget=state_budget)
    compacted["post_state"] = _compact_for_model(post_state, char_budget=state_budget)
    if projection == _MODEL_INPUT_PROJECTION_SALIENT:
        # Keep exact source spans beside (rather than instead of) the bounded
        # state projection.  This makes the candidate auditable and lets the
        # model recover a middle-of-tree failure or control value without
        # granting it the entire raw accessibility tree.
        event_signals = _salient_source_fields(
            {"action": event.action, "observed_outcome": event.observed_outcome},
            char_budget=max(256, metadata_budget),
            action=event.action,
        )
        if event_signals:
            compacted["evidence_signals"] = event_signals
        for field, original in (("pre_state", pre_state), ("post_state", post_state)):
            state = _compact_for_model(_strip_planning_fields(original), char_budget=state_budget)
            signals = _salient_source_fields(
                original,
                char_budget=max(256, state_budget),
                action=event.action,
                previous=pre_state if field == "post_state" else None,
            )
            if signals:
                if isinstance(state, Mapping):
                    state = dict(state)
                    state["evidence_signals"] = signals
                else:
                    state = {"value": state, "evidence_signals": signals}
                compacted[field] = state
    return compacted


def _model_event_payload(event: SourceEvent, context: Sequence[SourceEvent], *, char_budget: int,
                         projection: str = _MODEL_INPUT_PROJECTION_DEFAULT) -> dict[str, Any]:
    """Build a bounded, prefix-local extraction payload.

    ``context`` is already prefix-filtered by :func:`_context_for_event`.
    The current event is sent separately so its pre/post AXTree fragments are
    not duplicated and then discarded by a generic sorted-field truncator.
    """

    budget = max(512, int(char_budget))
    current_budget = max(256, (budget * 2) // 3)
    prior = [item for item in context if item.event_id != event.event_id]
    context_budget = max(128, budget - current_budget)
    per_context = max(128, context_budget // max(1, len(prior)))
    payload = {
        "event": _compact_event_projection(event, char_budget=current_budget, projection=projection),
        "context": [
            _compact_event_projection(item, char_budget=per_context, projection=projection)
            for item in prior
        ],
    }
    # Keep the historical compact-v2 request byte-for-byte compatible.  The
    # version marker is only needed when the opt-in salient side channel is
    # active and therefore belongs to that candidate's cache identity.
    if projection == _MODEL_INPUT_PROJECTION_SALIENT:
        payload["projection_version"] = projection
        # Serialized JSON framing/side-channel keys also consume the budget.
        # Reduce only prior context first; keep the current observation and
        # exact spans intact unless it alone exceeds the declared budget.
        adjusted_context = per_context
        adjusted_current = current_budget
        while len(canonical_json(payload)) > budget and adjusted_context > 256 and prior:
            adjusted_context = max(256, adjusted_context - 128)
            payload["context"] = [_compact_event_projection(item, char_budget=adjusted_context,
                                                           projection=projection) for item in prior]
        while len(canonical_json(payload)) > budget and payload["context"]:
            payload["context"].pop(0)
        while len(canonical_json(payload)) > budget and adjusted_current > 512:
            adjusted_current = max(512, adjusted_current - 128)
            payload["event"] = _compact_event_projection(event, char_budget=adjusted_current,
                                                         projection=projection)
        if len(canonical_json(payload)) > budget:
            raise ConstructionError("salient-v3 cannot fit the declared serialized input character budget")
    return payload


def _status_kind(event: SourceEvent) -> tuple[str, str]:
    """Return event kind and predicate without treating intent as success."""

    outcome = _text(event.observed_outcome).lower()
    action = _text(event.action)
    if any(word in outcome for word in ("fail", "error", "denied", "timeout", "exception")):
        return "failure", "outcome"
    if outcome and any(word in outcome for word in ("success", "succeeded", "completed", "done", "ok", "true")):
        return "confirmation", "outcome"
    if event.post_state_ref is not None:
        return "observation", "post_state"
    if action:
        return "attempt", "action"
    return "observation", "observation"


def _subject_for(value: Any, scope: str) -> str:
    if isinstance(value, Mapping):
        for key in ("entity_id", "id", "subject", "name", "url", "path"):
            candidate = value.get(key)
            if candidate not in (None, ""):
                return f"{scope}:{key}={candidate}"
    return f"{scope}:{stable_hash(value)[:12]}"


def _local_evidence(event: SourceEvent) -> list[Evidence]:
    scope = _scope(event)
    kind, predicate = _status_kind(event)
    values: list[tuple[str, Any, str]] = []
    if event.action is not None:
        values.append((f"{event.event_id}:attempt", event.action, "attempt"))
    if event.pre_state_ref is not None:
        values.append((f"{event.event_id}:pre", event.pre_state_ref, "observation"))
    if event.post_state_ref is not None:
        values.append((f"{event.event_id}:post", event.post_state_ref, "observation"))
    if event.observed_outcome is not None:
        values.append((f"{event.event_id}:outcome", event.observed_outcome, kind))
    if not values:
        values.append((f"{event.event_id}:observation", event.goal or "", kind))
    result: list[Evidence] = []
    for suffix, value, event_kind in values:
        subject = _subject_for(value, scope)
        result.append(
            Evidence(
                evidence_id=suffix,
                source_refs=(event.event_id,),
                source_versions={event.event_id: event.source_revision},
                source_spans=(suffix,),
                subject_ref=subject,
                predicate=predicate if suffix.endswith("outcome") else suffix.rsplit(":", 1)[-1],
                value=value,
                modality="screenshot+structured" if event.screenshot_hashes else "structured",
                certainty=1.0,
                event_kind=event_kind,
                valid_scope=scope,
                revision=event.source_revision,
            )
        )
    return result


def _strict_output_enabled(config: Any) -> bool:
    return bool(_config_value(config, "strict_model_output", False))


def _response_payload(response: Any) -> Any:
    """Prefer generated text over provider bookkeeping in ``raw``."""

    if isinstance(response, ModelResponse):
        # Local Transformers responses intentionally keep device/model_path in
        # ``raw``.  That metadata is not an evidence payload.
        if str(response.text or "").strip():
            return response.text
        return response.raw
    text = getattr(response, "text", None)
    if text is not None and str(text).strip():
        return text
    raw = getattr(response, "raw", None)
    if raw is not None:
        return raw
    return response


def _json_payload(value: Any) -> Any:
    """Decode direct or fenced JSON without accepting prose as evidence."""

    if not isinstance(value, str):
        return value
    text = value.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


def _scope_subject(subject: Any, value: Any, scope: str) -> str:
    """Namespace model subjects so they cannot leak across trajectories."""

    if subject in (None, ""):
        return _subject_for(value, scope)
    text = str(subject)
    if text == scope or text.startswith(scope + ":"):
        return text
    return f"{scope}:{text}"


def _parse_backend_evidence(event: SourceEvent, response: Any, *, context: Sequence[SourceEvent] = (), strict: bool = False) -> list[Evidence] | None:
    """Parse the versioned evidence object returned by a model backend.

    ``None`` means the response was not parseable.  An empty list is a valid
    strict extraction (the model found no local evidence), so callers must not
    use truthiness to distinguish these cases.
    """

    if response is None:
        if strict:
            raise ConstructionError(f"strict evidence output missing for {event.event_id}")
        return None
    payload = _json_payload(_response_payload(response))
    if isinstance(payload, Mapping) and not any(key in payload for key in ("evidence", "items", "output", "outputs")):
        # OpenAI-compatible envelope (when a caller passed a raw mapping).
        if any(key in payload for key in ("content", "text", "choices")):
            payload = _json_payload(ModelResponse.from_any(payload).text)
        # A single evidence object is accepted for lightweight adapters.
        elif any(key in payload for key in ("predicate", "value", "event_kind", "source_refs")):
            payload = [payload]
    if isinstance(payload, Mapping):
        payload = payload.get("evidence", payload.get("items", payload.get("output", payload.get("outputs"))))
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        if strict:
            raise ConstructionError(f"strict evidence output is not a JSON evidence list for {event.event_id}")
        return None

    scope = _scope(event)
    prefix_events = {item.event_id: item for item in context}
    prefix_events[event.event_id] = event
    known_sources = set(prefix_events)
    result: list[Evidence] = []
    for index, item in enumerate(payload):
        if isinstance(item, Evidence):
            item = item.to_dict()
        if not isinstance(item, Mapping):
            if strict:
                raise ConstructionError(f"strict evidence item {index} is not an object for {event.event_id}")
            continue
        raw_refs = item.get("source_refs", (event.event_id,))
        if isinstance(raw_refs, (str, bytes)):
            raw_refs = (raw_refs.decode() if isinstance(raw_refs, bytes) else raw_refs,)
        refs = tuple(str(x) for x in (raw_refs or ()))
        unknown = tuple(ref for ref in refs if ref not in known_sources)
        if unknown:
            if strict:
                raise ConstructionError(f"strict evidence {index} references unknown source(s): {unknown}")
            refs = tuple(ref for ref in refs if ref in known_sources)
        if not refs:
            refs = (event.event_id,)
        cross_scope = tuple(ref for ref in refs if _scope(prefix_events[ref]) != scope)
        if cross_scope:
            if strict:
                raise ConstructionError(f"strict evidence {index} crosses scope(s): {cross_scope}")
            refs = tuple(ref for ref in refs if ref not in cross_scope) or (event.event_id,)
        raw_versions = item.get("source_versions", {})
        if not isinstance(raw_versions, Mapping):
            if strict:
                raise ConstructionError(f"strict evidence {index} has invalid source_versions")
            raw_versions = {}
        versions: dict[str, Any] = {}
        for ref in refs:
            expected_revision = prefix_events[ref].source_revision
            supplied_revision = raw_versions.get(ref)
            if supplied_revision is not None and str(supplied_revision) != str(expected_revision):
                if strict:
                    raise ConstructionError(
                        f"strict evidence {index} has source revision mismatch for {ref}: "
                        f"{supplied_revision!r} != {expected_revision!r}"
                    )
            # Source versions are builder-owned provenance, never a model
            # claim.  This keeps cache/publish lineage tied to the actual
            # normalized event revisions.
            versions[ref] = expected_revision
        raw_spans = item.get("source_spans", ())
        if isinstance(raw_spans, (str, bytes)):
            raw_spans = (raw_spans.decode() if isinstance(raw_spans, bytes) else raw_spans,)
        kind = str(item.get("event_kind", "observation"))
        if kind not in {"intent", "attempt", "observation", "confirmation", "failure"}:
            if strict:
                raise ConstructionError(f"strict evidence {index} has unsupported event_kind {kind!r}")
            kind = "observation"
        try:
            revision = int(item.get("revision", event.source_revision))
        except (TypeError, ValueError):
            if strict:
                raise ConstructionError(f"strict evidence {index} has invalid revision")
            revision = event.source_revision
        result.append(
            Evidence(
                # Models may reuse e1 at every event. Builder-owned IDs
                # prevent dict dedup from deleting older source facts.
                evidence_id=f"{event.event_id}:model:{index}",
                source_refs=refs,
                source_versions=versions,
                source_spans=tuple(raw_spans or ()),
                subject_ref=_scope_subject(item.get("subject_ref"), item.get("value"), scope),
                predicate=str(item.get("predicate", "observation")),
                value=item.get("value"),
                modality=item.get("modality", "model"),
                certainty=item.get("certainty"),
                event_kind=kind,
                valid_scope=scope,
                revision=revision,
            )
        )
    return result


def _extract_prompt(strict: bool, config: Any = None) -> str:
    frozen = _config_value(config, "extraction_prompt", None)
    if frozen is not None:
        return str(frozen)
    if not strict:
        return "Extract only local observations. Do not infer action success without an observed result."
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "extract_evidence_v2.txt"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConstructionError(f"strict extraction prompt is unavailable: {prompt_path}") from exc


def _extraction_request(event: SourceEvent, context: Sequence[SourceEvent], config: Any) -> ModelRequest:
    strict = _strict_output_enabled(config)
    projection = _projection_mode(config)
    prompt = _extraction_system_prompt(config, strict=strict, projection=projection)
    cache_enabled = _extraction_request_cache_enabled(config)
    metadata = {"operator": "extract", "event_id": event.event_id, "strict_json": strict}
    if projection == _MODEL_INPUT_PROJECTION_SALIENT:
        metadata["model_input_projection"] = projection

    namespace = None
    key = None
    if cache_enabled:
        namespace = _extraction_request_memo_namespace(config)
        key = _extraction_request_memo_key(
            event,
            context,
            config,
            strict=strict,
            projection=projection,
            prompt=prompt,
        )
        cached = _extraction_request_memo_get(namespace, key)
        if cached is not None:
            return cached

    request = ModelRequest(
        model=str(_config_value(config, "construction_model", "")) or None,
        temperature=float(_config_value(config, "temperature", 0.0) or 0.0),
        max_tokens=int(_config_value(config, "extraction_output_tokens", 1024) or 1024),
        messages=(
            {"role": "system", "content": prompt},
            {"role": "user", "content": canonical_json(_model_event_payload(
                event, context, char_budget=int(_config_value(config, "model_input_char_budget", 6000) or 6000),
                projection=projection))},
        ),
        metadata=metadata,
    )
    if cache_enabled:
        _extraction_request_memo_put(
            namespace,
            key,
            request,
            limit=_extraction_request_cache_limit(config),
        )
    return request


def _extraction_cache_key(event: SourceEvent, context: Sequence[SourceEvent], backend: Any, config: Any) -> CacheKey:
    request = _extraction_request(event, context, config)
    context_rules = {
        "window": int(_config_value(config, "source_context_window_events_default", 2) or 0),
        "prefix_only": True,
        "strict_model_output": _strict_output_enabled(config),
    }
    projection = _projection_mode(config)
    literals_enabled = _source_literals_enabled(config)
    if projection == _MODEL_INPUT_PROJECTION_SALIENT or literals_enabled:
        # Preserve historical compact-v2 cache identities.  Versioned quality
        # variants must instead name every fact/projection policy explicitly.
        context_rules.update(
            model_input_projection=projection,
            source_literal_evidence=literals_enabled,
            source_literal_version=str(_config_value(config, "source_literal_version", SOURCE_LITERAL_VERSION)
                                       or SOURCE_LITERAL_VERSION),
        )
    return make_cache_key(
        operator="extract",
        request={"event": event.to_dict(), "context": [item.to_dict() for item in context],
                 "model_request": request.to_dict()},
        operator_version=str(_config_value(config, "extract_operator_version", "2")),
        prompt_hash=stable_hash(request.messages[0]["content"]),
        model_fingerprint=backend_fingerprint(backend) if backend else "deterministic-local",
        read_versions={item.event_id: item.source_revision for item in context},
        context_rules=context_rules,
        sampling={"temperature": request.temperature, "max_tokens": request.max_tokens},
    )


def _backend_evidence(event: SourceEvent, backend: Any, config: Any, *, context: Sequence[SourceEvent]) -> list[Evidence]:
    """Obtain evidence through an injected backend, never inside a DB tx."""

    strict = _strict_output_enabled(config)
    custom = getattr(backend, "extract_event", None) if backend is not None else None
    if callable(custom):
        value = custom(event, context=context, config=config)
        if inspect.isawaitable(value):
            raise ConstructionError("async backend supplied to synchronous builder; use a synchronous adapter")
        parsed = _parse_backend_evidence(event, value, context=context, strict=strict)
        if parsed is not None:
            return parsed
    if backend is None:
        return _local_evidence(event)
    request = _extraction_request(event, context, config)
    complete = getattr(backend, "complete", None)
    if not callable(complete):
        raise ConstructionError(f"backend {type(backend).__name__} lacks complete() or extract_event()")
    response = complete(request)
    if inspect.isawaitable(response):
        raise ConstructionError("async backend supplied to synchronous builder; use a synchronous adapter")
    parsed = _parse_backend_evidence(event, response, context=context, strict=strict)
    if parsed is not None:
        return parsed
    if strict:
        # _parse_backend_evidence normally raises with a useful reason.  Keep
        # this guard for custom response objects that bypass its decoder.
        raise ConstructionError(f"strict evidence output could not be parsed for {event.event_id}")
    return _local_evidence(event)


def _node_for(graph: ComputeGraph, operator: str, event_id: str) -> ComputeNode | None:
    matches = [node for node in graph.nodes.values() if node.operator == operator and f"{event_id}" in node.output_refs]
    return sorted(matches, key=lambda node: node.node_id)[0] if matches else None


def _make_nodes(events: Sequence[SourceEvent], evidence: Sequence[Evidence], config: Any, *, graph: ComputeGraph | None = None, previous: Snapshot | None = None, affected: set[str] | None = None) -> tuple[tuple[ComputeNode, ...], dict[str, Any]]:
    graph = graph or plan_graph(events, config)
    by_event: dict[str, list[Evidence]] = {}
    for item in evidence:
        for source in item.source_refs:
            by_event.setdefault(source, []).append(item)
    old_nodes = {node.node_id: node for node in (previous.nodes if previous else ())}
    nodes: list[ComputeNode] = []
    outputs: dict[str, Any] = {}
    for node_id in graph.topological_order():
        planned = graph.nodes[node_id]
        event_id = next((ref.split(":", 1)[1] for ref in planned.output_refs if ref.startswith(("event:", "evidence:", "state:", "workflow:", "index:"))), None)
        if planned.operator == "source":
            value = {"event_id": event_id, "raw_content_hash": next((item.raw_content_hash for item in events if item.event_id == event_id), None)}
        elif planned.operator == "extract":
            value = [item.to_dict() for item in by_event.get(event_id or "", ())]
        elif planned.operator == "resolve":
            value = [item.to_dict() for item in by_event.get(event_id or "", ()) if item.event_kind in {"observation", "confirmation", "failure"}]
        elif planned.operator == "workflow":
            value = {"event_id": event_id, "scope": planned.predicate_scopes[0] if planned.predicate_scopes else None, "evidence_ids": [item.evidence_id for item in by_event.get(event_id or "", ())]}
        elif planned.operator == "embed":
            value = {"event_id": event_id, "terms": sorted(_tokens(by_event.get(event_id or "", ())))}
        elif planned.operator == "publish":
            value = {"node_ids": list(planned.read_dependencies)}
        else:
            value = {}
        old = old_nodes.get(node_id)
        if old is not None and affected is not None and node_id not in affected:
            node = old
            outputs[node_id] = value
        else:
            payload = normalized_output(value)
            node = ComputeNode(
                node_id=planned.node_id,
                operator=planned.operator,
                operator_version=planned.operator_version,
                prompt_hash=planned.prompt_hash,
                model_fingerprint=planned.model_fingerprint,
                read_dependencies=planned.read_dependencies,
                read_fields=planned.read_fields,
                predicate_scopes=planned.predicate_scopes,
                output_refs=planned.output_refs,
                content_hash=stable_hash(payload),
                provenance_hash=stable_hash({"sources": planned.read_dependencies}),
                interpretation_hash=stable_hash({"operator": planned.operator, "output": payload}),
                status="ready",
                input_fingerprint=planned.input_fingerprint,
                retry_count=0,
            )
            outputs[node_id] = value
        nodes.append(node)
    if not any(node.operator == "publish" for node in nodes):
        publish_id = f"publish:{stable_hash([node.node_id for node in nodes])[:20]}"
        publish = ComputeNode(
            node_id=publish_id,
            operator="publish",
            operator_version="1",
            read_dependencies=tuple(f"node:{node.node_id}" for node in nodes),
            read_fields=("content", "provenance", "interpretation"),
            predicate_scopes=tuple(sorted({scope for node in nodes for scope in node.predicate_scopes})),
            output_refs=("snapshot:published",),
            content_hash=stable_hash([node.content_hash for node in nodes]),
            provenance_hash=stable_hash([node.provenance_hash for node in nodes]),
            interpretation_hash=stable_hash([node.interpretation_hash for node in nodes]),
            status="ready",
            input_fingerprint=stable_hash([node.input_fingerprint for node in nodes]),
        )
        nodes.append(publish)
        outputs[publish_id] = {"node_ids": [node.node_id for node in nodes[:-1]]}
    return tuple(nodes), outputs


def _build_views(events: Sequence[SourceEvent], evidence: Sequence[Evidence]) -> tuple[dict[str, Any], dict[str, Any], dict[str, tuple[str, ...]]]:
    # State is a projection; evidence remains append-only.  A failed/attempted
    # action is not promoted to a successful post-state.
    state: dict[str, Any] = {}
    workflow: dict[str, Any] = {}
    terms: dict[str, list[str]] = {}
    event_by_id = {item.event_id: item for item in events}
    evidence_by_event: dict[str, list[Evidence]] = {}
    for item in evidence:
        for source in item.source_refs:
            evidence_by_event.setdefault(source, []).append(item)
    for event in sorted(events, key=_event_sort_key):
        scope = _scope(event)
        workflow.setdefault(scope, []).append(
            {
                "event_id": event.event_id,
                "source_sequence": event.source_sequence,
                "action": event.action,
                "outcome": event.observed_outcome,
                "evidence_ids": [item.evidence_id for item in evidence_by_event.get(event.event_id, ())],
            }
        )
        for item in evidence_by_event.get(event.event_id, ()):
            key = f"{scope}|{item.subject_ref}|{item.predicate}"
            if item.event_kind in {"failure", "attempt"}:
                # Keep the fact for history but do not overwrite an observed
                # state with an unconfirmed intention/failure.
                continue
            state[key] = {
                "subject_ref": item.subject_ref,
                "predicate": item.predicate,
                "value": item.value,
                "event_id": event.event_id,
                "source_revision": event.source_revision,
                "event_kind": item.event_kind,
            }
            for token in _tokens({"predicate": item.predicate, "value": item.value}):
                terms.setdefault(token, []).append(item.evidence_id)
    return state, workflow, {key: tuple(dict.fromkeys(value)) for key, value in terms.items()}


def _build_relations(evidence: Sequence[Evidence]) -> tuple[dict[str, Any], dict[str, Any]]:
    aliases: dict[str, Any] = {}
    relations: dict[str, Any] = {}
    for item in evidence:
        predicate = str(item.predicate).lower()
        if predicate in {"alias", "aliases", "aka"}:
            aliases[str(item.subject_ref or item.evidence_id)] = item.value
        elif predicate in {"relation", "relates_to", "depends_on", "parent", "child"}:
            relations[str(item.evidence_id)] = {
                "subject_ref": item.subject_ref,
                "predicate": item.predicate,
                "value": item.value,
                "scope": item.valid_scope,
                "source_refs": list(item.source_refs),
            }
    return aliases, relations


def _snapshot_id(epoch: int, events: Sequence[SourceEvent], evidence: Sequence[Evidence], nodes: Sequence[ComputeNode]) -> str:
    digest = stable_hash(
        {
            "events": [item.raw_content_hash for item in events],
            "evidence": [item.content_hash for item in evidence],
            "nodes": [item.node_id for item in nodes],
        }
    )
    return f"snapshot-{epoch}-{digest[:16]}"


def _publish_snapshot(snapshot: Snapshot, *, store: EventStore, update: PreparedUpdate | None = None) -> Snapshot:
    store.commit_snapshot(
        snapshot,
        events=snapshot.events,
        evidence=snapshot.evidence,
        nodes=snapshot.nodes,
        update_ids=update.predecessor_updates + (update.update_id,) if update else snapshot.published.included_update_ids,
    )
    with _LOCK:
        _REGISTRY[snapshot.snapshot_id] = snapshot
        _SNAPSHOT_STORE_PATHS[snapshot.snapshot_id] = snapshot.store_path
        _record_snapshot_location(snapshot.snapshot_id, snapshot.store_path)
    return snapshot


def _resolve_snapshot(snapshot: Snapshot | str | int, config: Any = None) -> Snapshot:
    if isinstance(snapshot, Snapshot):
        return snapshot
    key = str(snapshot)
    explicit = _config_value(config, "storage_path", None) or _config_value(config, "store_path", None)
    if explicit is None:
        with _LOCK:
            if key in _REGISTRY:
                return _REGISTRY[key]
    # Identical prefixes in independent method stores may share snapshot IDs.
    # An explicitly pinned store takes precedence over the global locator.
    path = _store_path(config) if explicit is not None else _SNAPSHOT_STORE_PATHS.get(key) or _lookup_snapshot_location(key)
    store = _store({"storage_path": path}) if path else _store(config)
    record = store.get_snapshot(snapshot)
    if not record:
        raise ConstructionError(f"snapshot not found: {snapshot}")
    objects = store.snapshot_objects(record["snapshot_id"])
    payload = record.get("payload", {})
    if not isinstance(payload, Mapping):
        payload = {}
    data = dict(payload)
    data.setdefault("snapshot_id", record["snapshot_id"])
    data.setdefault("published", {
        "epoch": record["epoch"],
        "parent_epoch": record.get("parent_epoch"),
        "checksum": record.get("checksum", ""),
        "included_event_frontier": record.get("included_event_frontier", {}),
        "included_update_ids": record.get("included_update_ids", []),
    })
    # The immutable snapshot payload contains the exact objects of its epoch.
    # The latest object tables can contain later source/evidence revisions.
    data.setdefault("events", [row["payload"] for row in objects["events"]])
    data.setdefault("evidence", [row["payload"] for row in objects["evidence"]])
    data.setdefault("nodes", [row["payload"] for row in objects["nodes"]])
    graph = plan_graph(tuple(SourceEvent.from_dict(item) for item in data["events"]), config)
    loaded = Snapshot.from_dict(data, graph=graph)
    with _LOCK:
        _REGISTRY[loaded.snapshot_id] = loaded
    return loaded


def plan_graph_for(history_prefix: Any, algorithm_config: Any = None) -> ComputeGraph:
    events = normalize_trajectory(history_prefix) if not isinstance(history_prefix, (list, tuple)) or (history_prefix and not isinstance(history_prefix[0], SourceEvent)) else list(history_prefix)
    return plan_graph(events, algorithm_config)


def build_fresh(history_prefix: Any, model_backend: Any = None, config: Any = None, *, backend: Any = None) -> Snapshot:
    """Build an immutable snapshot from a prefix using the canonical graph."""

    if backend is not None:
        model_backend = backend
    events = normalize_trajectory(history_prefix) if not isinstance(history_prefix, (list, tuple)) or (history_prefix and not isinstance(history_prefix[0], SourceEvent)) else list(history_prefix)
    events = sorted(events, key=_event_sort_key)
    store = _store(config)
    graph = plan_graph(events, config)
    context_window = int(_config_value(config, "source_context_window_events_default", 2) or 0)
    evidence: list[Evidence] = []
    cache = _cache(config)
    for index, event in enumerate(events):
        context = _context_for_event(events, index, context_window)
        key = _extraction_cache_key(event, context, model_backend, config)
        cached = cache.get(key)
        if cached is not None:
            extracted = [Evidence.from_dict(item) for item in cached]
        else:
            extracted = _backend_evidence(event, model_backend, config, context=context)
            cache.put(key, [item.to_dict() for item in extracted], metadata={"event_id": event.event_id, "operator": "extract"})
        extracted = _augment_source_literals(event, extracted, config)
        evidence.extend(extracted)
    # Preserve append-only evidence IDs when a backend emits duplicates.
    unique_evidence: dict[str, Evidence] = {item.evidence_id: item for item in evidence}
    evidence = [unique_evidence[key] for key in sorted(unique_evidence)]
    nodes, _ = _make_nodes(events, evidence, config, graph=graph)
    state, workflow, index = _build_views(events, evidence)
    aliases, relations = _build_relations(evidence)
    epoch = (store.get_snapshot(None) or {}).get("epoch", 0) + 1
    published = PublishedSnapshot(
        epoch=epoch,
        parent_epoch=None,
        object_versions={event.event_id: event.source_revision for event in events},
        index_manifest={"terms": sorted(index), "version": stable_hash(index)[:16]},
        included_event_frontier=source_frontier(events),
        included_update_ids=(),
    )
    snapshot_id = _snapshot_id(epoch, events, evidence, nodes)
    snapshot = Snapshot(
        snapshot_id=snapshot_id,
        published=published,
        events=tuple(events),
        evidence=tuple(evidence),
        nodes=nodes,
        state_view=state,
        aliases=aliases,
        relations=relations,
        workflow_view={key: tuple(value) for key, value in workflow.items()},
        index=index,
        graph=graph,
        store_path=_store_path(config),
        metadata={"mode": "fresh", "model_fingerprint": backend_fingerprint(model_backend) if model_backend else "deterministic-local", "created_at": _now()},
    )
    return _publish_snapshot(snapshot, store=store)


def apply_delta(snapshot: Snapshot | str | int, events: Any, model_backend: Any = None, config: Any = None, *, backend: Any = None) -> UpdateReceipt:
    """Prepare and atomically publish a prefix update.

    Unchanged source objects retain their evidence and node cache entries.  A
    revision invalidates its bounded scope and downstream nodes; exact output
    hashes allow propagation to stop when only a duplicate observation arrived.
    """

    if backend is not None:
        model_backend = backend
    previous = _resolve_snapshot(snapshot, config)
    incoming = normalize_trajectory(events) if not isinstance(events, (list, tuple)) or (events and not isinstance(events[0], SourceEvent)) else list(events)
    incoming = sorted(incoming, key=_event_sort_key)
    update_id = f"update-{stable_hash([event.to_dict() for event in incoming])[:20]}"
    start = _now()
    if not incoming:
        return UpdateReceipt(update_id=update_id, source_event_ids=(), accepted=True, prepared=True, committed=True, queryable=True, snapshot_id=previous.snapshot_id, epoch=previous.epoch, snapshot=previous, timestamps={"accepted": start, "prepared": start, "committed": start, "queryable": start})
    old_by_id = {event.event_id: event for event in previous.events}
    changed: list[SourceEvent] = []
    new_events = list(previous.events)
    for event in incoming:
        old = old_by_id.get(event.event_id)
        if old is None:
            new_events.append(event)
            changed.append(event)
        elif event.source_revision > old.source_revision or event.raw_content_hash != old.raw_content_hash:
            new_events = [item for item in new_events if item.event_id != event.event_id]
            new_events.append(event)
            changed.append(event)
    if not changed:
        return UpdateReceipt(update_id=update_id, source_event_ids=tuple(item.event_id for item in incoming), accepted=True, prepared=True, committed=True, queryable=True, snapshot_id=previous.snapshot_id, epoch=previous.epoch, snapshot=previous, affected_scopes=tuple(sorted({_scope(item) for item in incoming})), reused_node_ids=tuple(item.node_id for item in previous.nodes), propagation_stopped_node_ids=tuple(item.node_id for item in previous.nodes), timestamps={"accepted": start, "prepared": start, "committed": start, "queryable": start})
    all_events = sorted(new_events, key=_event_sort_key)
    graph = plan_graph(all_events, config)
    # Conservative affected set: changed event plus nodes whose declared graph
    # dependencies include its source key; this is bounded by trajectory scope.
    changed_keys = {f"event:{item.event_id}" for item in changed} | {item.event_id for item in changed}
    affected = graph.affected_nodes(changed_keys)
    evidence: list[Evidence] = []
    context_window = int(_config_value(config, "source_context_window_events_default", 2) or 0)
    cache = _cache(config)
    for index, event in enumerate(all_events):
        context = _context_for_event(all_events, index, context_window)
        # Unchanged events may read revised prefix context. Validate their
        # own real cached extraction rather than reuse stale evidence.
        key = _extraction_cache_key(event, context, model_backend, config)
        cached = cache.get(key)
        extracted = [Evidence.from_dict(item) for item in cached] if cached is not None else _backend_evidence(event, model_backend, config, context=context)
        if cached is None:
            cache.put(key, [item.to_dict() for item in extracted], metadata={"event_id": event.event_id, "operator": "extract"})
        extracted = _augment_source_literals(event, extracted, config)
        evidence.extend(extracted)
    unique_evidence = {item.evidence_id: item for item in evidence}
    evidence = [unique_evidence[key] for key in sorted(unique_evidence)]
    nodes, _ = _make_nodes(all_events, evidence, config, graph=graph, previous=previous, affected=affected)
    state, workflow, index = _build_views(all_events, evidence)
    aliases, relations = _build_relations(evidence)
    parent = previous.published
    epoch = parent.epoch + 1
    update = PreparedUpdate(update_id=update_id, source_event_ids=tuple(item.event_id for item in incoming), read_version_vector={event.event_id: event.source_revision for event in previous.events}, affected_scopes=tuple(sorted({_scope(item) for item in changed})), writes=tuple(sorted(item.node_id for item in nodes if item.node_id in affected)), predecessor_updates=parent.included_update_ids)
    store = _store(config) if config is not None else _STORES.get(previous.store_path, _store({"storage_path": previous.store_path}))
    store.put_prepared_update(update, status="prepared")
    published = PublishedSnapshot(epoch=epoch, parent_epoch=parent.epoch, object_versions={event.event_id: event.source_revision for event in all_events}, index_manifest={"terms": sorted(index), "version": stable_hash(index)[:16]}, included_event_frontier=source_frontier(all_events), included_update_ids=parent.included_update_ids + (update_id,))
    new_id = _snapshot_id(epoch, all_events, evidence, nodes)
    new_snapshot = Snapshot(snapshot_id=new_id, published=published, events=tuple(all_events), evidence=tuple(evidence), nodes=nodes, state_view=state, aliases=aliases, relations=relations, workflow_view={key: tuple(value) for key, value in workflow.items()}, index=index, graph=graph, store_path=_store_path(config) if config is not None else previous.store_path, metadata={"mode": "incremental", "parent_snapshot_id": previous.snapshot_id, "created_at": _now(), "changed_event_ids": [item.event_id for item in changed]})
    _publish_snapshot(new_snapshot, store=store, update=update)
    reused = tuple(node.node_id for node in previous.nodes if node.node_id not in affected)
    stopped = tuple(node.node_id for node in previous.nodes if node.node_id not in affected)
    return UpdateReceipt(update_id=update_id, source_event_ids=tuple(item.event_id for item in incoming), accepted=True, prepared=True, committed=True, queryable=True, snapshot_id=new_id, epoch=epoch, snapshot=new_snapshot, affected_scopes=update.affected_scopes, reused_node_ids=reused, invalidated_node_ids=tuple(sorted(affected)), propagation_stopped_node_ids=stopped, timestamps={"accepted": start, "prepared": _now(), "committed": _now(), "queryable": _now()})


def query(snapshot_id: Snapshot | str | int, question: str, retrieval_budget: int | Mapping[str, Any] | None = None, *, budget: int | Mapping[str, Any] | None = None, reader_backend: Any = None, config: Any = None) -> EvidenceBundle:
    """Retrieve source-grounded evidence from one pinned snapshot epoch."""

    snapshot = _resolve_snapshot(snapshot_id, config)
    selected_budget = budget if budget is not None else retrieval_budget
    limit = int(selected_budget if isinstance(selected_budget, (int, float)) else (selected_budget or {}).get("max_evidence", 8) if isinstance(selected_budget, Mapping) else 8)
    limit = max(1, limit)
    qtokens = _tokens(question)
    scored: list[tuple[float, Evidence]] = []
    for item in snapshot.evidence:
        text = _tokens({"subject": item.subject_ref, "predicate": item.predicate, "value": item.value, "kind": item.event_kind})
        overlap = len(qtokens & text)
        score = float(overlap) + (0.1 if item.event_kind in {"confirmation", "observation"} else 0.0)
        if score > 0 or not qtokens:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].evidence_id))
    chosen = tuple(item for _, item in scored[:limit])
    answer = None
    if reader_backend is not None:
        method = getattr(reader_backend, "answer", None)
        if callable(method):
            answer = method(question, {"evidence": [item.to_dict() for item in chosen], "state": snapshot.state_view, "workflow": snapshot.workflow_view})
            if inspect.isawaitable(answer):
                raise ConstructionError("async reader supplied to synchronous query")
    scores = {item.evidence_id: score for score, item in scored[:limit]}
    return EvidenceBundle(snapshot_id=snapshot.snapshot_id, epoch=snapshot.epoch, question=question, evidence=chosen, state=snapshot.state_view, aliases=snapshot.aliases, relations=snapshot.relations, workflow=snapshot.workflow_view, reader_answer=answer, budget=limit, scores=scores)


def validate_snapshot(snapshot_id: Snapshot | str | int, *, config: Any = None) -> ValidationReport:
    try:
        snapshot = _resolve_snapshot(snapshot_id, config)
    except Exception as exc:
        return ValidationReport(snapshot_id=None if snapshot_id is None else str(snapshot_id), valid=False, checks={"exists": False}, errors=(str(exc),), checked_at=_now())
    errors: list[str] = []
    warnings: list[str] = []
    event_ids = [item.event_id for item in snapshot.events]
    evidence_ids = [item.evidence_id for item in snapshot.evidence]
    node_ids = [item.node_id for item in snapshot.nodes]
    checks: dict[str, bool] = {
        "exists": True,
        "unique_event_ids": len(event_ids) == len(set(event_ids)),
        "unique_evidence_ids": len(evidence_ids) == len(set(evidence_ids)),
        "unique_node_ids": len(node_ids) == len(set(node_ids)),
        "source_refs_exist": True,
        "scoped_entities": True,
        "checksum": True,
        "published_epoch": snapshot.epoch >= 0,
    }
    if not checks["unique_event_ids"]:
        errors.append("duplicate source event IDs")
    if not checks["unique_evidence_ids"]:
        errors.append("duplicate evidence IDs")
    if not checks["unique_node_ids"]:
        errors.append("duplicate compute node IDs")
    known_events = set(event_ids)
    for item in snapshot.evidence:
        if any(source not in known_events for source in item.source_refs):
            checks["source_refs_exist"] = False
            errors.append(f"evidence {item.evidence_id} references unknown source")
        if not item.valid_scope:
            checks["scoped_entities"] = False
            errors.append(f"evidence {item.evidence_id} has no valid scope")
    expected = stable_hash({"epoch": snapshot.published.epoch, "parent_epoch": snapshot.published.parent_epoch, "object_versions": snapshot.published.object_versions, "index_manifest": snapshot.published.index_manifest, "included_event_frontier": snapshot.published.included_event_frontier, "included_update_ids": snapshot.published.included_update_ids})
    if expected != snapshot.published.checksum:
        checks["checksum"] = False
        errors.append("published snapshot checksum mismatch")
    for event in snapshot.events:
        if event.observed_outcome is None and event.action is not None and any(item.event_kind == "confirmation" and event.event_id in item.source_refs for item in snapshot.evidence):
            warnings.append(f"confirmation derived without explicit outcome for {event.event_id}")
    return ValidationReport(snapshot_id=snapshot.snapshot_id, valid=not errors, checks=checks, errors=tuple(errors), warnings=tuple(warnings), checked_at=_now())


__all__ = ["Snapshot", "UpdateReceipt", "EvidenceBundle", "ValidationReport", "ConstructionError", "plan_graph_for", "build_fresh", "apply_delta", "query", "validate_snapshot"]
