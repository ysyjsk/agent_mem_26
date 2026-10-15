"""Versioned intermediate representation used by the memory builder.

The IR is intentionally provider-agnostic.  It stores source observations and
derived records separately, keeps provenance/version information explicit, and
offers deterministic JSON serialization for cache keys and replay manifests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import date, datetime, time
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def _canonical_value(value: Any) -> Any:
    """Convert a value into JSON-compatible, deterministically ordered data.

    Canonicalization is used for cache and replay keys.  It must not depend on
    dictionary insertion order, Python object identity, or a worker's finish
    order.  Unknown objects are represented by their string form only as a
    last resort; normal IR values should be JSON-compatible already.
    """

    if is_dataclass(value):
        return _canonical_value(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_canonical_value(item) for item in value]
        return sorted(normalized, key=lambda item: canonical_json(item))
    if isinstance(value, bytes):
        return {"__bytes_sha256__": hashlib.sha256(value).hexdigest()}
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        # JSON permits NaN, but allowing it would break cross-language replay.
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("non-finite floats are not valid canonical values")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def canonical_json(value: Any) -> str:
    """Return stable UTF-8 JSON suitable for hashing and manifests."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_hash(value: Any) -> str:
    """SHA-256 of :func:`canonical_json` (without a ``sha256:`` prefix)."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, (list, set, frozenset)):
        return tuple(value)
    return (value,)


class _RecordMixin:
    """Shared deterministic serialization helpers for IR dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        return _canonical_value(asdict(self))

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def to_json(self) -> str:
        """Alias used by manifest writers."""
        return self.canonical_json()

    def content_digest(self) -> str:
        return stable_hash(self.to_dict())

    @classmethod
    def _field_names(cls) -> set[str]:
        return {item.name for item in fields(cls)}

    @classmethod
    def from_json(cls, value: str) -> Any:
        payload = json.loads(value)
        if not isinstance(payload, Mapping):
            raise TypeError(f"{cls.__name__}.from_json expects a JSON object")
        return cls.from_dict(payload)


@dataclass(frozen=True, slots=True)
class SourceEvent(_RecordMixin):
    """One ordered, append-only observation from a trajectory.

    ``pre_state_ref`` and ``post_state_ref`` are references or compact state
    descriptors, not an implicit claim that an action succeeded.  The
    ``observed_outcome`` field is intentionally optional and is only populated
    when the source actually exposes an observation/result.
    """

    event_id: str
    trajectory_id: str
    environment_family: str
    source_sequence: int
    source_revision: int = 0
    arrival_sequence: int = 0
    environment_instance_id: str | None = None
    observation_time: str | None = None
    goal: Any = None
    pre_state_ref: Any = None
    action: Any = None
    post_state_ref: Any = None
    screenshot_hashes: tuple[str, ...] = field(default_factory=tuple)
    observed_outcome: Any = None
    causal_predecessors: tuple[str, ...] = field(default_factory=tuple)
    raw_content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", str(self.event_id))
        object.__setattr__(self, "trajectory_id", str(self.trajectory_id))
        object.__setattr__(self, "environment_family", str(self.environment_family))
        object.__setattr__(self, "source_sequence", int(self.source_sequence))
        object.__setattr__(self, "source_revision", int(self.source_revision))
        object.__setattr__(self, "arrival_sequence", int(self.arrival_sequence))
        object.__setattr__(self, "screenshot_hashes", tuple(str(x) for x in _as_tuple(self.screenshot_hashes)))
        object.__setattr__(self, "causal_predecessors", tuple(str(x) for x in _as_tuple(self.causal_predecessors)))
        if not self.raw_content_hash:
            # Exclude the derived hash itself, so the value is stable.
            payload = {
                key: value
                for key, value in self.to_dict().items()
                if key != "raw_content_hash"
            }
            object.__setattr__(self, "raw_content_hash", stable_hash(payload))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SourceEvent":
        values = {key: payload[key] for key in cls._field_names() if key in payload}
        return cls(**values)


@dataclass(frozen=True, slots=True)
class Evidence(_RecordMixin):
    evidence_id: str
    source_refs: tuple[str, ...] = field(default_factory=tuple)
    source_versions: Mapping[str, Any] = field(default_factory=dict)
    source_spans: tuple[Any, ...] = field(default_factory=tuple)
    subject_ref: str | None = None
    predicate: str = ""
    value: Any = None
    modality: str | None = None
    certainty: float | str | None = None
    event_kind: str = "observation"
    valid_scope: Any = None
    content_hash: str = ""
    provenance_hash: str = ""
    revision: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "source_refs", tuple(str(x) for x in _as_tuple(self.source_refs)))
        object.__setattr__(self, "source_spans", tuple(_as_tuple(self.source_spans)))
        if self.source_versions is None:
            object.__setattr__(self, "source_versions", {})
        if self.event_kind not in {"intent", "attempt", "observation", "confirmation", "failure"}:
            raise ValueError(f"unsupported evidence event_kind: {self.event_kind!r}")
        object.__setattr__(self, "revision", int(self.revision))
        if not self.content_hash:
            object.__setattr__(
                self,
                "content_hash",
                stable_hash(
                    {
                        "subject_ref": self.subject_ref,
                        "predicate": self.predicate,
                        "value": self.value,
                        "modality": self.modality,
                        "certainty": self.certainty,
                        "event_kind": self.event_kind,
                        "valid_scope": self.valid_scope,
                    }
                ),
            )
        if not self.provenance_hash:
            object.__setattr__(
                self,
                "provenance_hash",
                stable_hash(
                    {
                        "source_refs": self.source_refs,
                        "source_versions": self.source_versions,
                        "source_spans": self.source_spans,
                        "revision": self.revision,
                    }
                ),
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Evidence":
        values = {key: payload[key] for key in cls._field_names() if key in payload}
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ComputeNode(_RecordMixin):
    node_id: str
    operator: str
    operator_version: str = "1"
    prompt_hash: str | None = None
    model_fingerprint: str | None = None
    read_dependencies: tuple[str, ...] = field(default_factory=tuple)
    read_fields: tuple[str, ...] = field(default_factory=tuple)
    predicate_scopes: tuple[Any, ...] = field(default_factory=tuple)
    output_refs: tuple[str, ...] = field(default_factory=tuple)
    content_hash: str = ""
    provenance_hash: str = ""
    interpretation_hash: str = ""
    status: str = "planned"
    input_fingerprint: str = ""
    retry_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", str(self.node_id))
        object.__setattr__(self, "operator", str(self.operator))
        object.__setattr__(self, "read_dependencies", tuple(str(x) for x in _as_tuple(self.read_dependencies)))
        object.__setattr__(self, "read_fields", tuple(str(x) for x in _as_tuple(self.read_fields)))
        object.__setattr__(self, "predicate_scopes", tuple(_as_tuple(self.predicate_scopes)))
        object.__setattr__(self, "output_refs", tuple(str(x) for x in _as_tuple(self.output_refs)))
        object.__setattr__(self, "retry_count", int(self.retry_count))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComputeNode":
        values = {key: payload[key] for key in cls._field_names() if key in payload}
        return cls(**values)


@dataclass(frozen=True, slots=True)
class PreparedUpdate(_RecordMixin):
    update_id: str
    source_event_ids: tuple[str, ...] = field(default_factory=tuple)
    read_version_vector: Mapping[str, Any] = field(default_factory=dict)
    affected_scopes: tuple[Any, ...] = field(default_factory=tuple)
    writes: tuple[Any, ...] = field(default_factory=tuple)
    index_delta_ref: str | None = None
    predecessor_updates: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "update_id", str(self.update_id))
        object.__setattr__(self, "source_event_ids", tuple(str(x) for x in _as_tuple(self.source_event_ids)))
        if self.read_version_vector is None:
            object.__setattr__(self, "read_version_vector", {})
        object.__setattr__(self, "affected_scopes", tuple(_as_tuple(self.affected_scopes)))
        object.__setattr__(self, "writes", tuple(_as_tuple(self.writes)))
        object.__setattr__(self, "predecessor_updates", tuple(str(x) for x in _as_tuple(self.predecessor_updates)))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PreparedUpdate":
        values = {key: payload[key] for key in cls._field_names() if key in payload}
        return cls(**values)


@dataclass(frozen=True, slots=True)
class PublishedSnapshot(_RecordMixin):
    epoch: int
    parent_epoch: int | None = None
    object_versions: Mapping[str, Any] = field(default_factory=dict)
    index_manifest: Mapping[str, Any] = field(default_factory=dict)
    included_event_frontier: Mapping[str, Any] = field(default_factory=dict)
    included_update_ids: tuple[str, ...] = field(default_factory=tuple)
    checksum: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "epoch", int(self.epoch))
        for name in ("object_versions", "index_manifest", "included_event_frontier"):
            if getattr(self, name) is None:
                object.__setattr__(self, name, {})
        if self.parent_epoch is not None:
            object.__setattr__(self, "parent_epoch", int(self.parent_epoch))
        object.__setattr__(self, "included_update_ids", tuple(str(x) for x in _as_tuple(self.included_update_ids)))
        if not self.checksum:
            object.__setattr__(
                self,
                "checksum",
                stable_hash(
                    {
                        "epoch": self.epoch,
                        "parent_epoch": self.parent_epoch,
                        "object_versions": self.object_versions,
                        "index_manifest": self.index_manifest,
                        "included_event_frontier": self.included_event_frontier,
                        "included_update_ids": self.included_update_ids,
                    }
                ),
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PublishedSnapshot":
        values = {key: payload[key] for key in cls._field_names() if key in payload}
        return cls(**values)


_MISSING = object()


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _container_and_metadata(raw: Any) -> tuple[list[Any], Mapping[str, Any]]:
    """Extract an ordered event container from common trajectory encodings."""

    if is_dataclass(raw):
        raw = asdict(raw)
    elif not isinstance(raw, (Mapping, list, tuple)) and hasattr(raw, "__dict__"):
        raw = vars(raw)
    if isinstance(raw, (list, tuple)):
        return list(raw), {}
    if not isinstance(raw, Mapping):
        return [raw], {}

    # Prefer paired arrays over the bare ``actions`` list when both are
    # present; otherwise the post-state alignment would be lost.
    states = raw.get("states")
    actions = raw.get("actions")
    if isinstance(states, (list, tuple)) and isinstance(actions, (list, tuple)):
        paired: list[dict[str, Any]] = []
        for index, action in enumerate(actions):
            paired.append(
                {
                    "source_sequence": index,
                    "action": action,
                    "pre_state": states[index] if index < len(states) else None,
                    "post_state": states[index + 1] if index + 1 < len(states) else None,
                    "raw_source_index": index,
                }
            )
        return paired, raw
    # LongMemEval/AgentRunbook exports commonly store the action on the
    # state *before* it is executed, with one terminal state carrying no
    # action.  Treat each adjacent pair as one transition.  This alignment is
    # prefix-safe: event ``i`` can see only state ``i`` and its observed
    # successor, while the trajectory-level outcome is attached later to the
    # final transition by ``normalize_trajectory``.
    if isinstance(states, (list, tuple)) and states and all(
        isinstance(item, Mapping) for item in states
    ):
        transitions: list[dict[str, Any]] = []
        # In the benchmark export the initial state has ``action=None`` and
        # each following state stores the action that led *to* that state.
        # Therefore state[i-1] -> state[i] is the transition for
        # state[i]['action']; pairing state[i] with state[i+1] would silently
        # drop the final action and shift every pre/post observation.
        for index in range(1, len(states)):
            previous_state = states[index - 1]
            state = states[index]
            action = state.get("action")
            if action is None:
                continue
            transitions.append(
                {
                    "source_sequence": max(
                        0,
                        int(state.get("step", state.get("state_index", index))) - 1,
                    ),
                    "action": action,
                    "pre_state": previous_state,
                    "post_state": state,
                    "screenshots": tuple(
                        value
                        for value in (previous_state.get("screenshot"), state.get("screenshot"))
                        if value is not None
                    ),
                    "raw_source_index": index - 1,
                }
            )
        if transitions:
            return transitions, raw
    container_keys = (
        "events",
        "steps",
        "trajectory",
        "transitions",
        "records",
        "messages",
        "actions",
    )
    for key in container_keys:
        value = raw.get(key)
        if isinstance(value, (list, tuple)):
            return list(value), raw
    # Some benchmark exports keep parallel state/action arrays.  Pair each
    # action with the state before and after it without inventing a terminal
    # outcome; the adapter can still audit the original arrays via hashes.
    # A single transition object is also accepted.
    return [raw], raw


def _hash_screenshot(value: Any) -> str:
    if isinstance(value, Mapping):
        explicit = _first(value, "sha256", "hash", "screenshot_hash", "content_hash")
        if explicit:
            return str(explicit)
        value = _first(value, "bytes", "data", "content", default=value)
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value):
        # ``screenshot_hashes`` often already contains SHA-256 digests.
        return value.lower()
    return stable_hash(value)


def _screenshot_hashes(item: Mapping[str, Any]) -> tuple[str, ...]:
    values = item.get("screenshot_hashes")
    if values is None:
        values = _first(item, "screenshots", "screenshot", "image_refs", "images")
    if values is None:
        return ()
    if not isinstance(values, (list, tuple, set, frozenset)):
        values = [values]
    return tuple(_hash_screenshot(value) for value in values)


def normalize_trajectory(raw: Any) -> list[SourceEvent]:
    """Normalize common trajectory/state-action encodings into ``SourceEvent``.

    The adapter is intentionally conservative: it keeps explicit fields and
    does not infer success from an action.  Unknown fields remain represented
    by ``raw_content_hash`` so cache invalidation observes source revisions.
    Returned events retain source order and receive deterministic fallback IDs.
    """

    items, metadata = _container_and_metadata(raw)
    # ``trajectory`` is commonly the actual list of steps, not an ID.  Only
    # scalar metadata fields may determine the trajectory scope.
    trajectory_candidate = _first(metadata, "trajectory_id", "episode_id", "session_uuid", "session_id", "id")
    if isinstance(trajectory_candidate, (list, tuple, dict, set, frozenset)):
        trajectory_candidate = None
    trajectory_id = str(trajectory_candidate or "trajectory")
    environment_family = str(
        _first(metadata, "environment_family", "domain", "environment", "env_family", default="unknown")
    )
    environment_instance_id = _first(
        metadata,
        "environment_instance_id",
        "environment_instance",
        "env_instance_id",
        "instance_id",
    )
    trajectory_goal = _first(metadata, "goal", "task", "objective", "target")
    terminal_outcome = _first(metadata, "observed_outcome", "terminal_outcome", "final_outcome", "outcome")
    out: list[SourceEvent] = []
    for index, value in enumerate(items):
        item: Mapping[str, Any]
        if isinstance(value, Mapping):
            item = value
        elif is_dataclass(value):
            item = asdict(value)
        elif hasattr(value, "__dict__"):
            item = vars(value)
        else:
            item = {"observation": value}
        sequence = _first(item, "source_sequence", "sequence", "step", "step_index", "index", default=index)
        try:
            sequence_int = int(sequence)
        except (TypeError, ValueError):
            sequence_int = index
        revision = _first(item, "source_revision", "revision", "version", default=0)
        arrival = _first(item, "arrival_sequence", "arrival", "arrival_index", default=index)
        event_id = _first(item, "event_id", "source_event_id", "step_id", "id")
        event_trajectory = str(_first(item, "trajectory_id", "episode_id", "session_uuid", default=trajectory_id))
        if event_id is None:
            event_id = f"{event_trajectory}:{sequence_int}"
        event_family = str(_first(item, "environment_family", "domain", "environment", default=environment_family))
        event_instance = _first(
            item,
            "environment_instance_id",
            "environment_instance",
            "env_instance_id",
            "instance_id",
            default=environment_instance_id,
        )
        event_goal = _first(item, "goal", "task", "objective", "target", default=trajectory_goal)
        pre_state = _first(
            item,
            "pre_state_ref",
            "pre_state",
            "state_before",
            "previous_state",
            "before",
            "state",
        )
        action = _first(item, "action", "tool_call", "operation", "command", "input")
        post_state = _first(item, "post_state_ref", "post_state", "state_after", "next_state", "after")
        outcome = _first(item, "observed_outcome", "outcome", "result", "observation", "tool_result", "status")
        if outcome is None and index == len(items) - 1 and terminal_outcome is not None:
            outcome = terminal_outcome
        predecessors = _first(item, "causal_predecessors", "predecessors", "depends_on", "parents", default=())
        if isinstance(predecessors, (str, bytes)):
            predecessors = (predecessors.decode() if isinstance(predecessors, bytes) else predecessors,)
        event = SourceEvent(
            event_id=str(event_id),
            trajectory_id=event_trajectory,
            environment_family=event_family,
            environment_instance_id=None if event_instance is None else str(event_instance),
            source_sequence=sequence_int,
            source_revision=int(revision) if str(revision).lstrip("-").isdigit() else 0,
            arrival_sequence=int(arrival) if str(arrival).lstrip("-").isdigit() else index,
            observation_time=_first(item, "observation_time", "timestamp", "time", "current_time"),
            goal=event_goal,
            pre_state_ref=pre_state,
            action=action,
            post_state_ref=post_state,
            screenshot_hashes=_screenshot_hashes(item),
            observed_outcome=outcome,
            causal_predecessors=tuple(str(x) for x in (predecessors or ())),
            # Keep a hash of the complete source record, including fields not
            # projected into the normalized IR (for example a thought/text
            # span or an opaque accessibility-tree payload).  This is what
            # makes source revisions invalidate caches even when the adapter
            # does not understand every upstream field yet.
            raw_content_hash=str(
                _first(item, "raw_content_hash", "content_hash", default=stable_hash(item))
            ),
        )
        out.append(event)
    return out


def source_frontier(events: Iterable[SourceEvent]) -> dict[str, int]:
    """Return the latest source revision/sequence per trajectory."""

    frontier: dict[str, int] = {}
    for event in events:
        frontier[event.trajectory_id] = max(frontier.get(event.trajectory_id, -1), event.source_sequence)
    return frontier


__all__ = [
    "SourceEvent",
    "Evidence",
    "ComputeNode",
    "PreparedUpdate",
    "PublishedSnapshot",
    "normalize_trajectory",
    "source_frontier",
    "canonical_json",
    "stable_hash",
]
