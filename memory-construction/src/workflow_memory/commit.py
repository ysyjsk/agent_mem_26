"""Optimistic short-transaction publication and reader epoch pinning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .event_store import EventStore


class CommitConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ReadSet:
    versions: Mapping[str, Any]
    predicate_scopes: tuple[str, ...] = ()
    predecessor_updates: tuple[str, ...] = ()


class SnapshotCommitter:
    """Validate a parent epoch before delegating one atomic store commit."""

    def __init__(self, store: EventStore, *, max_retries: int = 2) -> None:
        self.store = store
        self.max_retries = max(0, int(max_retries))

    def validate_parent(self, expected_epoch: int | None) -> None:
        latest = self.store.get_snapshot(None)
        current = None if latest is None else int(latest["epoch"])
        if expected_epoch is not None and current != expected_epoch:
            raise CommitConflict(f"parent epoch changed: expected {expected_epoch}, current {current}")

    def publish(self, snapshot: Any, *, read_set: ReadSet | None = None, events: Iterable[Any] = (), evidence: Iterable[Any] = (), nodes: Iterable[Any] = (), update_ids: Iterable[str] = ()) -> str:
        expected = None if read_set is None else snapshot.parent_epoch
        self.validate_parent(expected)
        return self.store.commit_snapshot(snapshot, events=events, evidence=evidence, nodes=nodes, update_ids=tuple(update_ids))


@dataclass(frozen=True)
class ReaderEpoch:
    snapshot_id: str
    epoch: int
    snapshot: Any

    @classmethod
    def pin(cls, snapshot: Any) -> "ReaderEpoch":
        return cls(snapshot_id=str(getattr(snapshot, "snapshot_id", getattr(snapshot, "epoch", ""))), epoch=int(getattr(snapshot, "epoch", 0)), snapshot=snapshot)


__all__ = ["CommitConflict", "ReadSet", "SnapshotCommitter", "ReaderEpoch"]
