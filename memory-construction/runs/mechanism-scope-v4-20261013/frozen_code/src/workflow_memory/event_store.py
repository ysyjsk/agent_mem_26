"""SQLite-backed event, node and snapshot storage.

The store is deliberately small and dependency-free.  It uses SQLite WAL and
short transactions so model calls can happen outside a write lock.  The
objects accepted by this module are the dataclasses in :mod:`workflow_memory.ir`
but the serializer also accepts ordinary mappings; this keeps the persistence
layer useful while model adapters are being wired in.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


def _jsonable(value: Any) -> Any:
    """Convert dataclasses and common value objects to JSON-compatible data."""
    if is_dataclass(value):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    # datetime-like objects are uncommon in the IR; ISO conversion avoids a
    # non-deterministic repr while allowing callers to pass them through.
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _ident(obj: Any, *names: str) -> str | None:
    for name in names:
        value = _field(obj, name)
        if value is not None and value != "":
            return str(value)
    return None


class EventStore:
    """Versioned SQLite store used by builders and readers.

    ``:memory:`` is accepted for tests.  For a file-backed store, parent
    directories are created and WAL mode is enabled.  A connection is kept per
    thread; each public mutating method opens a short transaction via
    ``_transaction``.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path = ":memory:", *, timeout: float = 30.0):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._local = threading.local()
        self._lock = threading.RLock()
        # A plain ``:memory:`` database is connection-local.  Keep one
        # check_same_thread=False connection for that mode so worker threads
        # observe the same schema/data during concurrency tests.
        self._shared_connection: sqlite3.Connection | None = None
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        if self.path == ":memory:" and self._shared_connection is not None:
            return self._shared_connection
        conn = getattr(self._local, "connection", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=self.timeout, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            if self.path != ":memory:":
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
            if self.path == ":memory:":
                self._shared_connection = conn
            else:
                self._local.connection = conn
        return conn

    def _initialize(self) -> None:
        conn = self._connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_events (
              event_id TEXT PRIMARY KEY,
              trajectory_id TEXT NOT NULL,
              environment_family TEXT,
              environment_instance_id TEXT,
              source_sequence INTEGER NOT NULL,
              source_revision INTEGER NOT NULL DEFAULT 0,
              arrival_sequence INTEGER,
              observation_time TEXT,
              payload_json TEXT NOT NULL,
              raw_content_hash TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,
              created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_traj_seq
              ON source_events(trajectory_id, source_sequence, source_revision);
            CREATE INDEX IF NOT EXISTS idx_events_arrival
              ON source_events(arrival_sequence);
            CREATE TABLE IF NOT EXISTS source_event_revisions (
              event_id TEXT NOT NULL,
              source_revision INTEGER NOT NULL,
              payload_json TEXT NOT NULL,
              raw_content_hash TEXT NOT NULL,
              superseded_at REAL NOT NULL,
              PRIMARY KEY(event_id, source_revision)
            );
            CREATE TABLE IF NOT EXISTS evidence (
              evidence_id TEXT PRIMARY KEY,
              payload_json TEXT NOT NULL,
              content_hash TEXT,
              provenance_hash TEXT,
              interpretation_hash TEXT,
              revision INTEGER NOT NULL DEFAULT 0,
              valid INTEGER NOT NULL DEFAULT 1,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence_revisions (
              evidence_id TEXT NOT NULL,
              revision INTEGER NOT NULL,
              payload_json TEXT NOT NULL,
              content_hash TEXT,
              provenance_hash TEXT,
              interpretation_hash TEXT,
              superseded_at REAL NOT NULL,
              PRIMARY KEY(evidence_id, revision)
            );
            CREATE TABLE IF NOT EXISTS compute_nodes (
              node_id TEXT PRIMARY KEY,
              operator TEXT NOT NULL,
              operator_version TEXT,
              status TEXT NOT NULL,
              input_fingerprint TEXT,
              payload_json TEXT NOT NULL,
              output_refs_json TEXT,
              read_dependencies_json TEXT,
              read_fields_json TEXT,
              predicate_scopes_json TEXT,
              content_hash TEXT,
              provenance_hash TEXT,
              interpretation_hash TEXT,
              retry_count INTEGER NOT NULL DEFAULT 0,
              updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_nodes_input ON compute_nodes(input_fingerprint);
            CREATE TABLE IF NOT EXISTS prepared_updates (
              update_id TEXT PRIMARY KEY,
              payload_json TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
              snapshot_id TEXT PRIMARY KEY,
              epoch INTEGER NOT NULL UNIQUE,
              parent_epoch INTEGER,
              payload_json TEXT NOT NULL,
              checksum TEXT NOT NULL,
              included_event_frontier_json TEXT,
              included_update_ids_json TEXT,
              created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_epoch ON snapshots(epoch);
            CREATE TABLE IF NOT EXISTS snapshot_events (
              snapshot_id TEXT NOT NULL,
              event_id TEXT NOT NULL,
              PRIMARY KEY(snapshot_id, event_id),
              FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
              FOREIGN KEY(event_id) REFERENCES source_events(event_id) ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS snapshot_evidence (
              snapshot_id TEXT NOT NULL,
              evidence_id TEXT NOT NULL,
              PRIMARY KEY(snapshot_id, evidence_id),
              FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
              FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id) ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS snapshot_nodes (
              snapshot_id TEXT NOT NULL,
              node_id TEXT NOT NULL,
              PRIMARY KEY(snapshot_id, node_id),
              FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
              FOREIGN KEY(node_id) REFERENCES compute_nodes(node_id) ON DELETE RESTRICT
            );
            CREATE TABLE IF NOT EXISTS dependencies (
              node_id TEXT NOT NULL,
              dependency_key TEXT NOT NULL,
              dependency_kind TEXT NOT NULL DEFAULT 'object',
              version TEXT,
              PRIMARY KEY(node_id, dependency_key, dependency_kind),
              FOREIGN KEY(node_id) REFERENCES compute_nodes(node_id) ON DELETE CASCADE
            );
            INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', '1');
            """
        )
        conn.commit()

    class _Tx:
        def __init__(self, store: "EventStore"):
            self.store = store
            self.conn: sqlite3.Connection | None = None

        def __enter__(self) -> sqlite3.Connection:
            self.store._lock.acquire()
            self.conn = self.store._connection()
            self.conn.execute("BEGIN IMMEDIATE")
            return self.conn

        def __exit__(self, exc_type, exc, tb) -> None:
            assert self.conn is not None
            try:
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
            finally:
                self.store._lock.release()

    def _transaction(self) -> "EventStore._Tx":
        return EventStore._Tx(self)

    # ---- generic rows -------------------------------------------------
    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return None if row is None else {k: row[k] for k in row.keys()}

    @staticmethod
    def _decode_json(value: Any, default: Any = None) -> Any:
        if value is None:
            return default
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default

    # ---- source events ------------------------------------------------
    def put_source_event(self, event: Any) -> str:
        event_id = _ident(event, "event_id", "id") or content_hash(event)[:24]
        trajectory_id = _ident(event, "trajectory_id", "trajectory", "episode_id") or "unknown"
        source_sequence = int(_field(event, "source_sequence", _field(event, "sequence", 0)) or 0)
        source_revision = int(_field(event, "source_revision", _field(event, "revision", 0)) or 0)
        arrival_sequence = _field(event, "arrival_sequence")
        if arrival_sequence is not None:
            arrival_sequence = int(arrival_sequence)
        raw_hash = _field(event, "raw_content_hash") or content_hash(event)
        payload = _jsonable(event)
        with self._transaction() as conn:
            self._archive_previous_event_revision(conn, event_id, source_revision, raw_hash)
            conn.execute(
                """INSERT INTO source_events(event_id, trajectory_id, environment_family,
                   environment_instance_id, source_sequence, source_revision,
                   arrival_sequence, observation_time, payload_json,
                   raw_content_hash, active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(event_id) DO UPDATE SET
                     payload_json=excluded.payload_json,
                     source_revision=excluded.source_revision,
                     arrival_sequence=excluded.arrival_sequence,
                     raw_content_hash=excluded.raw_content_hash,
                     active=excluded.active""",
                (
                    event_id,
                    trajectory_id,
                    _field(event, "environment_family"),
                    _field(event, "environment_instance_id"),
                    source_sequence,
                    source_revision,
                    arrival_sequence,
                    _field(event, "observation_time"),
                    canonical_json(payload),
                    str(raw_hash),
                    1 if _field(event, "active", True) else 0,
                    time.time(),
                ),
            )
        return event_id

    def put_source_events(self, events: Iterable[Any]) -> list[str]:
        return [self.put_source_event(event) for event in events]

    def get_source_event(self, event_id: str) -> dict[str, Any] | None:
        row = self._connection().execute(
            "SELECT * FROM source_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        result = self._row_to_dict(row)
        if result:
            result["payload"] = self._decode_json(result.pop("payload_json"), {})
        return result

    def iter_source_events(
        self, trajectory_id: str | None = None, *, active_only: bool = True
    ) -> Iterator[dict[str, Any]]:
        sql = "SELECT * FROM source_events"
        args: list[Any] = []
        where: list[str] = []
        if trajectory_id is not None:
            where.append("trajectory_id = ?")
            args.append(trajectory_id)
        if active_only:
            where.append("active = 1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY trajectory_id, source_sequence, source_revision, event_id"
        for row in self._connection().execute(sql, args):
            result = self._row_to_dict(row) or {}
            result["payload"] = self._decode_json(result.pop("payload_json"), {})
            yield result

    # ---- evidence and compute nodes ----------------------------------
    def put_evidence(self, evidence: Any) -> str:
        evidence_id = _ident(evidence, "evidence_id", "id") or content_hash(evidence)[:24]
        payload = _jsonable(evidence)
        with self._transaction() as conn:
            self._archive_previous_evidence_revision(conn, evidence_id, evidence)
            conn.execute(
                """INSERT INTO evidence(evidence_id, payload_json, content_hash,
                   provenance_hash, interpretation_hash, revision, valid, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(evidence_id) DO UPDATE SET
                     payload_json=excluded.payload_json,
                     content_hash=excluded.content_hash,
                     provenance_hash=excluded.provenance_hash,
                     interpretation_hash=excluded.interpretation_hash,
                     revision=excluded.revision,
                     valid=excluded.valid""",
                (
                    evidence_id,
                    canonical_json(payload),
                    _field(evidence, "content_hash"),
                    _field(evidence, "provenance_hash"),
                    _field(evidence, "interpretation_hash"),
                    int(_field(evidence, "revision", 0) or 0),
                    1 if _field(evidence, "valid", True) else 0,
                    time.time(),
                ),
            )
        return evidence_id

    def put_evidence_many(self, evidence: Iterable[Any]) -> list[str]:
        return [self.put_evidence(item) for item in evidence]

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        row = self._connection().execute(
            "SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        result = self._row_to_dict(row)
        if result:
            result["payload"] = self._decode_json(result.pop("payload_json"), {})
        return result

    def iter_evidence(self, *, valid_only: bool = False) -> Iterator[dict[str, Any]]:
        sql = "SELECT * FROM evidence"
        if valid_only:
            sql += " WHERE valid = 1"
        sql += " ORDER BY evidence_id"
        for row in self._connection().execute(sql):
            result = self._row_to_dict(row) or {}
            result["payload"] = self._decode_json(result.pop("payload_json"), {})
            yield result

    def put_compute_node(self, node: Any) -> str:
        node_id = _ident(node, "node_id", "id") or content_hash(node)[:24]
        payload = _jsonable(node)
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO compute_nodes(node_id, operator, operator_version,
                   status, input_fingerprint, payload_json, output_refs_json,
                   read_dependencies_json, read_fields_json, predicate_scopes_json,
                   content_hash, provenance_hash, interpretation_hash, retry_count,
                   updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(node_id) DO UPDATE SET
                     operator=excluded.operator,
                     operator_version=excluded.operator_version,
                     status=excluded.status,
                     input_fingerprint=excluded.input_fingerprint,
                     payload_json=excluded.payload_json,
                     output_refs_json=excluded.output_refs_json,
                     read_dependencies_json=excluded.read_dependencies_json,
                     read_fields_json=excluded.read_fields_json,
                     predicate_scopes_json=excluded.predicate_scopes_json,
                     content_hash=excluded.content_hash,
                     provenance_hash=excluded.provenance_hash,
                     interpretation_hash=excluded.interpretation_hash,
                     retry_count=excluded.retry_count,
                     updated_at=excluded.updated_at""",
                (
                    node_id,
                    str(_field(node, "operator", "unknown")),
                    _field(node, "operator_version"),
                    str(_field(node, "status", "ready")),
                    _field(node, "input_fingerprint"),
                    canonical_json(payload),
                    canonical_json(_field(node, "output_refs", [])),
                    canonical_json(_field(node, "read_dependencies", [])),
                    canonical_json(_field(node, "read_fields", [])),
                    canonical_json(_field(node, "predicate_scopes", [])),
                    _field(node, "content_hash"),
                    _field(node, "provenance_hash"),
                    _field(node, "interpretation_hash"),
                    int(_field(node, "retry_count", 0) or 0),
                    time.time(),
                ),
            )
            conn.execute("DELETE FROM dependencies WHERE node_id = ?", (node_id,))
            dependencies = _field(node, "read_dependencies", []) or []
            for dep in dependencies:
                dep_key = str(dep if not isinstance(dep, Mapping) else dep.get("key", dep.get("id", dep)))
                version = dep.get("version") if isinstance(dep, Mapping) else None
                conn.execute(
                    """INSERT INTO dependencies(node_id, dependency_key, dependency_kind, version)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(node_id, dependency_key, dependency_kind) DO UPDATE SET version=excluded.version""",
                    (node_id, dep_key, "object", None if version is None else str(version)),
                )
        return node_id

    def put_compute_nodes(self, nodes: Iterable[Any]) -> list[str]:
        return [self.put_compute_node(node) for node in nodes]

    def get_compute_node(self, node_id: str) -> dict[str, Any] | None:
        row = self._connection().execute(
            "SELECT * FROM compute_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        result = self._row_to_dict(row)
        if result:
            for field in (
                "payload_json",
                "output_refs_json",
                "read_dependencies_json",
                "read_fields_json",
                "predicate_scopes_json",
            ):
                target = field.removesuffix("_json")
                result[target] = self._decode_json(result.pop(field), [] if target != "payload" else {})
        return result

    def iter_compute_nodes(self, *, status: str | None = None) -> Iterator[dict[str, Any]]:
        sql = "SELECT node_id FROM compute_nodes"
        args: list[Any] = []
        if status is not None:
            sql += " WHERE status = ?"
            args.append(status)
        sql += " ORDER BY node_id"
        for row in self._connection().execute(sql, args):
            node = self.get_compute_node(str(row[0]))
            if node:
                yield node

    # ---- prepared updates and snapshots ------------------------------
    def put_prepared_update(self, update: Any, *, status: str = "prepared") -> str:
        update_id = _ident(update, "update_id", "id") or content_hash(update)[:24]
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO prepared_updates(update_id, payload_json, status, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(update_id) DO UPDATE SET payload_json=excluded.payload_json,
                     status=excluded.status""",
                (update_id, canonical_json(update), status, time.time()),
            )
        return update_id

    def get_prepared_update(self, update_id: str) -> dict[str, Any] | None:
        row = self._connection().execute(
            "SELECT * FROM prepared_updates WHERE update_id = ?", (update_id,)
        ).fetchone()
        result = self._row_to_dict(row)
        if result:
            result["payload"] = self._decode_json(result.pop("payload_json"), {})
        return result

    def _next_epoch(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COALESCE(MAX(epoch), 0) + 1 FROM snapshots").fetchone()
        return int(row[0])

    def commit_snapshot(
        self,
        snapshot: Any,
        *,
        events: Iterable[Any] = (),
        evidence: Iterable[Any] = (),
        nodes: Iterable[Any] = (),
        update_ids: Sequence[str] = (),
    ) -> str:
        """Atomically persist a snapshot and all referenced objects.

        Expensive model/embedding work must be done before this method.  The
        transaction only validates and writes prepared objects.
        """
        snapshot_id = _ident(snapshot, "snapshot_id", "id") or f"snapshot-{content_hash(snapshot)[:20]}"
        payload = _jsonable(snapshot)
        event_list = list(events)
        evidence_list = list(evidence)
        node_list = list(nodes)
        event_ids = [_ident(x, "event_id", "id") or content_hash(x)[:24] for x in event_list]
        evidence_ids = [_ident(x, "evidence_id", "id") or content_hash(x)[:24] for x in evidence_list]
        node_ids = [_ident(x, "node_id", "id") or content_hash(x)[:24] for x in node_list]
        with self._transaction() as conn:
            # Persist objects within the same short transaction.  Individual
            # helper methods intentionally are not called to avoid nested BEGIN.
            for event in event_list:
                self._put_source_event_conn(conn, event)
            for item in evidence_list:
                self._put_evidence_conn(conn, item)
            for node in node_list:
                self._put_compute_node_conn(conn, node)
            epoch = int(_field(snapshot, "epoch", 0) or 0) or self._next_epoch(conn)
            parent_epoch = _field(snapshot, "parent_epoch")
            checksum = _field(snapshot, "checksum") or content_hash(
                {"payload": payload, "events": event_ids, "evidence": evidence_ids, "nodes": node_ids}
            )
            conn.execute(
                """INSERT INTO snapshots(snapshot_id, epoch, parent_epoch, payload_json,
                   checksum, included_event_frontier_json, included_update_ids_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(snapshot_id) DO UPDATE SET epoch=excluded.epoch,
                     parent_epoch=excluded.parent_epoch, payload_json=excluded.payload_json,
                     checksum=excluded.checksum, included_event_frontier_json=excluded.included_event_frontier_json,
                     included_update_ids_json=excluded.included_update_ids_json""",
                (
                    snapshot_id,
                    epoch,
                    None if parent_epoch is None else int(parent_epoch),
                    canonical_json(payload),
                    checksum,
                    canonical_json(_field(snapshot, "included_event_frontier", {})),
                    canonical_json(list(update_ids) or _field(snapshot, "included_update_ids", [])),
                    time.time(),
                ),
            )
            conn.execute("DELETE FROM snapshot_events WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute("DELETE FROM snapshot_evidence WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute("DELETE FROM snapshot_nodes WHERE snapshot_id = ?", (snapshot_id,))
            conn.executemany(
                "INSERT OR IGNORE INTO snapshot_events(snapshot_id, event_id) VALUES (?, ?)",
                [(snapshot_id, event_id) for event_id in event_ids],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO snapshot_evidence(snapshot_id, evidence_id) VALUES (?, ?)",
                [(snapshot_id, evidence_id) for evidence_id in evidence_ids],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO snapshot_nodes(snapshot_id, node_id) VALUES (?, ?)",
                [(snapshot_id, node_id) for node_id in node_ids],
            )
            if update_ids:
                conn.executemany(
                    "UPDATE prepared_updates SET status = 'committed' WHERE update_id = ?",
                    [(str(update_id),) for update_id in update_ids],
                )
        return snapshot_id

    def _put_source_event_conn(self, conn: sqlite3.Connection, event: Any) -> str:
        event_id = _ident(event, "event_id", "id") or content_hash(event)[:24]
        trajectory_id = _ident(event, "trajectory_id", "trajectory", "episode_id") or "unknown"
        source_sequence = int(_field(event, "source_sequence", _field(event, "sequence", 0)) or 0)
        source_revision = int(_field(event, "source_revision", _field(event, "revision", 0)) or 0)
        arrival_sequence = _field(event, "arrival_sequence")
        raw_hash = _field(event, "raw_content_hash") or content_hash(event)
        self._archive_previous_event_revision(conn, event_id, source_revision, raw_hash)
        conn.execute(
            """INSERT INTO source_events(event_id, trajectory_id, environment_family,
               environment_instance_id, source_sequence, source_revision,
               arrival_sequence, observation_time, payload_json,
               raw_content_hash, active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(event_id) DO UPDATE SET payload_json=excluded.payload_json,
                 source_revision=excluded.source_revision, arrival_sequence=excluded.arrival_sequence,
                 raw_content_hash=excluded.raw_content_hash, active=excluded.active""",
            (
                event_id,
                trajectory_id,
                _field(event, "environment_family"),
                _field(event, "environment_instance_id"),
                source_sequence,
                source_revision,
                None if arrival_sequence is None else int(arrival_sequence),
                _field(event, "observation_time"),
                canonical_json(_jsonable(event)),
                str(raw_hash),
                1 if _field(event, "active", True) else 0,
                time.time(),
            ),
        )
        return event_id

    @staticmethod
    def _archive_previous_event_revision(
        conn: sqlite3.Connection, event_id: str, new_revision: int, new_hash: Any
    ) -> None:
        """Keep superseded source payloads append-only before replacing latest."""
        previous = conn.execute(
            "SELECT source_revision, payload_json, raw_content_hash FROM source_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if previous is None:
            return
        old_revision, payload_json, old_hash = int(previous[0]), previous[1], str(previous[2])
        if old_revision == int(new_revision) and old_hash == str(new_hash):
            return
        conn.execute(
            """INSERT OR IGNORE INTO source_event_revisions(
                 event_id, source_revision, payload_json, raw_content_hash, superseded_at)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, old_revision, payload_json, old_hash, time.time()),
        )

    def iter_source_event_revisions(self, event_id: str | None = None) -> Iterator[dict[str, Any]]:
        sql = "SELECT * FROM source_event_revisions"
        args: list[Any] = []
        if event_id is not None:
            sql += " WHERE event_id = ?"
            args.append(event_id)
        sql += " ORDER BY event_id, source_revision"
        for row in self._connection().execute(sql, args):
            result = self._row_to_dict(row) or {}
            result["payload"] = self._decode_json(result.pop("payload_json"), {})
            yield result

    def _put_evidence_conn(self, conn: sqlite3.Connection, evidence: Any) -> str:
        evidence_id = _ident(evidence, "evidence_id", "id") or content_hash(evidence)[:24]
        self._archive_previous_evidence_revision(conn, evidence_id, evidence)
        conn.execute(
            """INSERT INTO evidence(evidence_id, payload_json, content_hash,
               provenance_hash, interpretation_hash, revision, valid, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(evidence_id) DO UPDATE SET payload_json=excluded.payload_json,
                 content_hash=excluded.content_hash, provenance_hash=excluded.provenance_hash,
                 interpretation_hash=excluded.interpretation_hash, revision=excluded.revision,
                 valid=excluded.valid""",
            (
                evidence_id,
                canonical_json(_jsonable(evidence)),
                _field(evidence, "content_hash"),
                _field(evidence, "provenance_hash"),
                _field(evidence, "interpretation_hash"),
                int(_field(evidence, "revision", 0) or 0),
                1 if _field(evidence, "valid", True) else 0,
                time.time(),
            ),
        )
        return evidence_id

    @staticmethod
    def _archive_previous_evidence_revision(conn: sqlite3.Connection, evidence_id: str, evidence: Any) -> None:
        previous = conn.execute(
            "SELECT revision, payload_json, content_hash, provenance_hash, interpretation_hash FROM evidence WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
        if previous is None:
            return
        revision = int(_field(evidence, "revision", 0) or 0)
        old_revision = int(previous[0])
        if old_revision == revision and str(previous[2] or "") == str(_field(evidence, "content_hash", "") or ""):
            return
        conn.execute(
            """INSERT OR IGNORE INTO evidence_revisions(
                 evidence_id, revision, payload_json, content_hash, provenance_hash,
                 interpretation_hash, superseded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, old_revision, previous[1], previous[2], previous[3], previous[4], time.time()),
        )

    def iter_evidence_revisions(self, evidence_id: str | None = None) -> Iterator[dict[str, Any]]:
        sql = "SELECT * FROM evidence_revisions"
        args: list[Any] = []
        if evidence_id is not None:
            sql += " WHERE evidence_id = ?"
            args.append(evidence_id)
        sql += " ORDER BY evidence_id, revision"
        for row in self._connection().execute(sql, args):
            result = self._row_to_dict(row) or {}
            result["payload"] = self._decode_json(result.pop("payload_json"), {})
            yield result

    def _put_compute_node_conn(self, conn: sqlite3.Connection, node: Any) -> str:
        node_id = _ident(node, "node_id", "id") or content_hash(node)[:24]
        conn.execute(
            """INSERT INTO compute_nodes(node_id, operator, operator_version, status,
               input_fingerprint, payload_json, output_refs_json,
               read_dependencies_json, read_fields_json, predicate_scopes_json,
               content_hash, provenance_hash, interpretation_hash, retry_count, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(node_id) DO UPDATE SET operator=excluded.operator,
                 operator_version=excluded.operator_version, status=excluded.status,
                 input_fingerprint=excluded.input_fingerprint, payload_json=excluded.payload_json,
                 output_refs_json=excluded.output_refs_json, read_dependencies_json=excluded.read_dependencies_json,
                 read_fields_json=excluded.read_fields_json, predicate_scopes_json=excluded.predicate_scopes_json,
                 content_hash=excluded.content_hash, provenance_hash=excluded.provenance_hash,
                 interpretation_hash=excluded.interpretation_hash, retry_count=excluded.retry_count,
                 updated_at=excluded.updated_at""",
            (
                node_id,
                str(_field(node, "operator", "unknown")),
                _field(node, "operator_version"),
                str(_field(node, "status", "ready")),
                _field(node, "input_fingerprint"),
                canonical_json(_jsonable(node)),
                canonical_json(_field(node, "output_refs", [])),
                canonical_json(_field(node, "read_dependencies", [])),
                canonical_json(_field(node, "read_fields", [])),
                canonical_json(_field(node, "predicate_scopes", [])),
                _field(node, "content_hash"),
                _field(node, "provenance_hash"),
                _field(node, "interpretation_hash"),
                int(_field(node, "retry_count", 0) or 0),
                time.time(),
            ),
        )
        conn.execute("DELETE FROM dependencies WHERE node_id = ?", (node_id,))
        for dep in _field(node, "read_dependencies", []) or []:
            dep_key = str(dep if not isinstance(dep, Mapping) else dep.get("key", dep.get("id", dep)))
            version = dep.get("version") if isinstance(dep, Mapping) else None
            conn.execute(
                """INSERT INTO dependencies(node_id, dependency_key, dependency_kind, version)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(node_id, dependency_key, dependency_kind) DO UPDATE SET version=excluded.version""",
                (node_id, dep_key, "object", None if version is None else str(version)),
            )
        return node_id

    def get_snapshot(self, snapshot_id: str | int | None = None) -> dict[str, Any] | None:
        conn = self._connection()
        if snapshot_id is None:
            row = conn.execute("SELECT * FROM snapshots ORDER BY epoch DESC LIMIT 1").fetchone()
        elif isinstance(snapshot_id, int) or (isinstance(snapshot_id, str) and snapshot_id.isdigit()):
            row = conn.execute("SELECT * FROM snapshots WHERE epoch = ?", (int(snapshot_id),)).fetchone()
        else:
            row = conn.execute("SELECT * FROM snapshots WHERE snapshot_id = ?", (str(snapshot_id),)).fetchone()
        result = self._row_to_dict(row)
        if result is None:
            return None
        for field, default in (
            ("payload_json", {}),
            ("included_event_frontier_json", {}),
            ("included_update_ids_json", []),
        ):
            target = field.removesuffix("_json")
            result[target] = self._decode_json(result.pop(field), default)
        result["event_ids"] = [
            str(r[0]) for r in conn.execute(
                "SELECT event_id FROM snapshot_events WHERE snapshot_id = ? ORDER BY event_id",
                (result["snapshot_id"],),
            )
        ]
        result["evidence_ids"] = [
            str(r[0]) for r in conn.execute(
                "SELECT evidence_id FROM snapshot_evidence WHERE snapshot_id = ? ORDER BY evidence_id",
                (result["snapshot_id"],),
            )
        ]
        result["node_ids"] = [
            str(r[0]) for r in conn.execute(
                "SELECT node_id FROM snapshot_nodes WHERE snapshot_id = ? ORDER BY node_id",
                (result["snapshot_id"],),
            )
        ]
        return result

    def iter_snapshots(self) -> Iterator[dict[str, Any]]:
        for row in self._connection().execute("SELECT snapshot_id FROM snapshots ORDER BY epoch"):
            snapshot = self.get_snapshot(str(row[0]))
            if snapshot:
                yield snapshot

    def latest_snapshot(self) -> dict[str, Any] | None:
        return self.get_snapshot(None)

    def snapshot_exists(self, snapshot_id: str | int) -> bool:
        return self.get_snapshot(snapshot_id) is not None

    def snapshot_objects(self, snapshot_id: str | int | None = None) -> dict[str, list[dict[str, Any]]]:
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return {"events": [], "evidence": [], "nodes": []}
        return {
            "events": [self.get_source_event(x) for x in snapshot["event_ids"] if self.get_source_event(x)],
            "evidence": [self.get_evidence(x) for x in snapshot["evidence_ids"] if self.get_evidence(x)],
            "nodes": [self.get_compute_node(x) for x in snapshot["node_ids"] if self.get_compute_node(x)],
        }

    def close(self) -> None:
        if self._shared_connection is not None:
            self._shared_connection.close()
            self._shared_connection = None
        conn = getattr(self._local, "connection", None)
        if conn is not None:
            conn.close()
            self._local.connection = None

    def __enter__(self) -> "EventStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = ["EventStore", "canonical_json", "content_hash"]
