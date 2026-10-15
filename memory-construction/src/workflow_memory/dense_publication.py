"""Small, pinned dense-index publication boundary for the development runner.

Each caller owns its cache: use a distinct dictionary per method/window, and
an empty one at every Fresh checkpoint. Only exact rendered embedding inputs
and the backend fingerprint authorize reuse. No responses cross method stores.
"""
from __future__ import annotations

import math
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from .backends import EmbeddingResponse, backend_fingerprint
from .config import load_json, write_json
from .construction import Snapshot, validate_snapshot
from .event_store import EventStore
from .ir import canonical_json, stable_hash


EMBEDDING_RENDER_FULL_V1 = "full-v1"
EMBEDDING_RENDER_SOURCE_REF_V1 = "source-ref-v1"
EMBEDDING_RENDER_SOURCE_REF_V2 = "source-ref-v2"
DEFAULT_EMBEDDING_RENDER_VERSION = EMBEDDING_RENDER_FULL_V1
EMBEDDING_RENDER_VERSIONS = frozenset({
    EMBEDDING_RENDER_FULL_V1,
    EMBEDDING_RENDER_SOURCE_REF_V1,
    EMBEDDING_RENDER_SOURCE_REF_V2,
})


def _compact_source_spans(spans: Sequence[Any] | None) -> list[Any]:
    """Keep bounded provenance structure useful for dense disambiguation.

    Source-literal spans are normally small mappings such as ``path``,
    ``line`` and ``focused``.  Preserve those structural keys, while dropping
    arbitrary raw payload keys that would recreate full-v1's token cost.  A
    short scalar span remains available for provider-specific provenance; an
    unbounded scalar is omitted rather than truncating fact-bearing evidence.
    """

    output: list[Any] = []
    for span in tuple(spans or ()):
        if isinstance(span, Mapping):
            compact = {key: span[key] for key in ("version", "path", "line", "column", "focused")
                       if key in span}
            if compact:
                output.append(compact)
        elif isinstance(span, (str, int, float, bool)) and (not isinstance(span, str) or len(span) <= 128):
            output.append(span)
    return output


def render_evidence(evidence: Any, render_version: str = DEFAULT_EMBEDDING_RENDER_VERSION, *,
                    source_positions: Mapping[str, int] | None = None) -> str:
    """Render one evidence item for dense embedding input.

    ``full-v1`` is the historical byte-for-byte rendering.  The opt-in
    ``source-ref-v1`` projection keeps the fact-bearing fields and source
    references while leaving the complete evidence record pinned in the core
    snapshot.  ``source-ref-v2`` is a hybrid projection: it restores subject
    and complete source spans, and adds public one-based source-step labels
    from the pinned snapshot's event order.  It never consults a question or
    evaluator reference.  Values, UI state flags and command text are not
    parsed, summarized or truncated by either projection.

    Rendering is versioned because its bytes are part of both the vector
    cache identity and the immutable dense-index content hash.  Source refs
    are opaque IDs: v2 must receive real snapshot ordinals and must not infer
    a step number by parsing an ID suffix.
    """
    version = str(render_version)
    if version == EMBEDDING_RENDER_FULL_V1:
        return canonical_json(evidence.to_dict())
    if version == EMBEDDING_RENDER_SOURCE_REF_V1:
        return canonical_json({
            "predicate": evidence.predicate,
            "value": evidence.value,
            "event_kind": evidence.event_kind,
            "modality": evidence.modality,
            "source_refs": evidence.source_refs,
        })
    if version == EMBEDDING_RENDER_SOURCE_REF_V2:
        positions = source_positions if source_positions is not None else {}
        source_steps = []
        for source_ref in evidence.source_refs:
            position = positions.get(source_ref)
            if isinstance(position, bool) or not isinstance(position, int) or position < 1:
                raise ValueError("source-ref-v2 requires positive pinned snapshot source positions")
            label = f"source step {position}"
            if label not in source_steps:
                source_steps.append(label)
        return canonical_json({
            "predicate": evidence.predicate,
            "value": evidence.value,
            "event_kind": evidence.event_kind,
            "modality": evidence.modality,
            "source_refs": evidence.source_refs,
            "subject_ref": evidence.subject_ref,
            "source_spans": _compact_source_spans(evidence.source_spans),
            "source_steps": source_steps,
        })
    raise ValueError(f"unsupported embedding evidence render version: {version!r}")


def _vector(value: Sequence[float], dimensions: int | None = None) -> tuple[float, ...]:
    vector = tuple(float(item) for item in value)
    if not vector or (dimensions is not None and len(vector) != dimensions):
        raise ValueError("dense vector dimension mismatch or empty vector")
    norm = math.sqrt(math.fsum(item * item for item in vector))
    if not all(math.isfinite(item) for item in vector) or not math.isfinite(norm) or norm <= 0:
        raise ValueError("dense vectors must have finite values and finite nonzero norms")
    return vector


def _disk_snapshot(store_path: str, snapshot_id: str) -> Snapshot:
    if store_path == ":memory:" or not Path(store_path).is_file():
        raise ValueError("dense publication requires an existing file-backed core snapshot")
    store = EventStore(store_path)
    try:
        record = store.get_snapshot(snapshot_id)
    finally:
        store.close()
    if record is None:
        raise ValueError("dense publication core snapshot is missing from its pinned store")
    snapshot = Snapshot.from_dict(record["payload"])
    if (snapshot.snapshot_id != snapshot_id or snapshot.epoch != record["epoch"]
            or snapshot.checksum != record["checksum"] or not validate_snapshot(snapshot).valid
            or Path(snapshot.store_path).resolve() != Path(store_path).resolve()):
        raise ValueError("dense publication core snapshot identity/checksum is invalid")
    return snapshot


def read_dense(descriptor: Mapping[str, Any] | str | Path, *, snapshot: Snapshot | None = None) -> dict[str, Any]:
    """Read immutable vectors only after checking the exact core/dense epoch."""
    descriptor = dict(descriptor) if isinstance(descriptor, Mapping) else load_json(descriptor)
    data = load_json(descriptor["index_path"])
    if stable_hash(data) != descriptor["data_hash"]:
        raise ValueError("dense index content hash mismatch")
    # Older full-v1 indexes predate the explicit render-version field.  Treat
    # a missing value as the historical default, but reject any disagreement
    # between descriptor and index before accepting vector content.
    descriptor_render_version = str(descriptor.get("render_version", DEFAULT_EMBEDDING_RENDER_VERSION))
    data_render_version = str(data.get("render_version", DEFAULT_EMBEDDING_RENDER_VERSION))
    if descriptor_render_version not in EMBEDDING_RENDER_VERSIONS:
        raise ValueError(f"unsupported dense embedding render version: {descriptor_render_version!r}")
    if data_render_version not in EMBEDDING_RENDER_VERSIONS:
        raise ValueError(f"unsupported dense index render version: {data_render_version!r}")
    if descriptor_render_version != data_render_version:
        raise ValueError("dense descriptor/index render version mismatch")
    for field in ("snapshot_id", "epoch", "store_path", "core_snapshot_hash", "embedding_fingerprint",
                  "model_settings_hash", "dimensions"):
        if data[field] != descriptor[field]:
            raise ValueError(f"dense publication descriptor/index {field} mismatch")
    if stable_hash(data["model_settings"]) != data["model_settings_hash"]:
        raise ValueError("dense embedding model settings hash mismatch")
    core = _disk_snapshot(descriptor["store_path"], descriptor["snapshot_id"])
    if core.epoch != descriptor["epoch"] or stable_hash(core.to_dict()) != descriptor["core_snapshot_hash"]:
        raise ValueError("dense index does not match the persisted core snapshot payload/epoch")
    if snapshot is not None and stable_hash(snapshot.to_dict()) != descriptor["core_snapshot_hash"]:
        raise ValueError("dense index does not match the supplied checkpoint snapshot")
    ids = [evidence.evidence_id for evidence in core.evidence]
    if data["evidence_ids"] != ids or len(ids) != len(set(ids)) or len(data["vectors"]) != len(ids):
        raise ValueError("dense index evidence IDs/count do not match the pinned core snapshot")
    source_positions = {event.event_id: index + 1 for index, event in enumerate(core.events)}
    hashes = [stable_hash(render_evidence(evidence, data_render_version, source_positions=source_positions))
              for evidence in core.evidence]
    if data["rendered_content_hashes"] != hashes:
        raise ValueError("dense index rendered evidence content differs from its pinned core snapshot")
    if descriptor["n_vectors"] != len(ids) or stable_hash(ids) != descriptor["evidence_ids_hash"]:
        raise ValueError("dense publication evidence manifest mismatch")
    dimensions = int(data["dimensions"])
    if (ids and dimensions < 1) or (not ids and dimensions != 0):
        raise ValueError("dense index has an invalid dimension")
    for vector in data["vectors"]:
        _vector(vector, dimensions)
    return data


def validate_dense(descriptor: Mapping[str, Any] | str | Path, *, snapshot: Snapshot | None = None) -> dict[str, Any]:
    try:
        data = read_dense(descriptor, snapshot=snapshot)
        return {"valid": True, "errors": [], "snapshot_id": data["snapshot_id"], "epoch": data["epoch"],
                "n_vectors": len(data["vectors"]), "dimensions": data["dimensions"]}
    except Exception as exc:
        return {"valid": False, "errors": [str(exc)]}


def publish_dense(snapshot: Snapshot, embedding_backend: Any, publication_dir: str | Path,
                 cache: dict | None = None, *,
                 render_version: str = DEFAULT_EMBEDDING_RENDER_VERSION) -> tuple[dict[str, Any], dict[str, Any]]:
    render_version = str(render_version)
    if render_version not in EMBEDDING_RENDER_VERSIONS:
        raise ValueError(f"unsupported embedding evidence render version: {render_version!r}")
    started = time.perf_counter()
    core = _disk_snapshot(snapshot.store_path, snapshot.snapshot_id)
    core_hash = stable_hash(core.to_dict())
    if core_hash != stable_hash(snapshot.to_dict()):
        raise ValueError("cannot publish dense vectors for an unpersisted/mismatched snapshot")
    fingerprint = backend_fingerprint(embedding_backend)
    model_settings = {field: getattr(embedding_backend, field, None)
                      for field in ("dtype", "max_length", "batch_size")}
    settings_hash = stable_hash(model_settings)
    source_positions = {event.event_id: index + 1 for index, event in enumerate(core.events)}
    texts = [render_evidence(evidence, render_version, source_positions=source_positions) for evidence in core.evidence]
    # Render version is explicit even though it also changes ``text``.  This
    # prevents a future renderer that happens to emit identical bytes from
    # silently sharing vectors with another semantic version.
    keys = [(fingerprint, settings_hash, render_version, text) for text in texts]
    owned_cache = cache if cache is not None else {}
    missing = list(dict.fromkeys(key for key in keys if key not in owned_cache))
    pending: dict[tuple[str, str, str, str], tuple[float, ...]] = {}
    embed_s, calls, tokens = 0.0, 0, 0
    token_reason = None
    batch_size = min(4, max(1, int(getattr(embedding_backend, "batch_size", 4))))
    for start in range(0, len(missing), batch_size):
        batch = missing[start : start + batch_size]
        embed_started = time.perf_counter()
        response = EmbeddingResponse.from_any(embedding_backend.embed([key[3] for key in batch]))
        embed_s += time.perf_counter() - embed_started
        calls += 1
        if len(response.vectors) != len(batch):
            raise ValueError("embedding response count differs from the submitted text batch")
        count = response.usage.get("input_tokens", response.usage.get("prompt_tokens"))
        if count is None:
            tokens, token_reason = None, "embedding backend returned no token usage"
        elif int(count) < 0 or float(count) != int(count):
            raise ValueError("embedding backend returned invalid token usage")
        elif tokens is not None:
            tokens += int(count)
        pending.update((key, _vector(vector)) for key, vector in zip(batch, response.vectors))
    vectors = [_vector(pending[key] if key in pending else owned_cache[key]) for key in keys]
    dimensions = len(vectors[0]) if vectors else 0
    for vector in vectors:
        _vector(vector, dimensions)
    data = {"schema_version": 1, "render_version": render_version,
            "snapshot_id": core.snapshot_id, "epoch": core.epoch,
            "store_path": str(Path(core.store_path).resolve()), "core_snapshot_hash": core_hash,
            "embedding_fingerprint": fingerprint, "model_settings": model_settings,
            "model_settings_hash": settings_hash, "dimensions": dimensions,
            "evidence_ids": [evidence.evidence_id for evidence in core.evidence],
            "rendered_content_hashes": [stable_hash(text) for text in texts], "vectors": vectors}
    root = Path(publication_dir).resolve()
    index_path = root / f"index-{stable_hash(data)}.json"
    if index_path.exists():
        if stable_hash(load_json(index_path)) != stable_hash(data):
            raise ValueError("an existing immutable dense index has different content")
    else:
        write_json(index_path, data)
    descriptor = {key: data[key] for key in ("snapshot_id", "epoch", "store_path", "core_snapshot_hash",
                                            "embedding_fingerprint", "model_settings_hash", "dimensions",
                                            "render_version")}
    descriptor.update(schema_version=1, index_path=str(index_path), data_hash=stable_hash(data),
                      n_vectors=len(vectors), evidence_ids_hash=stable_hash(data["evidence_ids"]))
    read_dense(descriptor, snapshot=snapshot)  # Never publish a pointer before read-back verification.
    # Includes cache preparation, core pinning and the online readback before
    # pointer publication, not just vector-file serialization.
    index_s = time.perf_counter() - started - embed_s
    publish_started = time.perf_counter()
    write_json(root / "published.json", descriptor)
    publish_s = time.perf_counter() - publish_started
    owned_cache.update(pending)
    stats = {"elapsed_s": time.perf_counter() - started, "embed_elapsed_s": embed_s, "index_s": index_s,
             "publish_s": publish_s, "embedding_calls": calls, "input_tokens": tokens,
             "input_tokens_reason": token_reason, "n_texts": len(texts), "new_vectors": len(missing),
             "reused_vectors": len(keys) - len(missing), "dense_valid": True}
    return descriptor, stats


def search_dense(descriptor: Mapping[str, Any] | str | Path, query_vector: Sequence[float], top_k: int = 8,
                 *, snapshot: Snapshot | None = None) -> list[dict[str, Any]]:
    data = read_dense(descriptor, snapshot=snapshot)
    if int(top_k) < 0:
        raise ValueError("top_k must be non-negative")
    if not data["vectors"]:
        return []
    query = _vector(query_vector, int(data["dimensions"]))
    query_norm = math.sqrt(math.fsum(value * value for value in query))
    query = tuple(value / query_norm for value in query)
    scored = []
    for evidence_id, vector in zip(data["evidence_ids"], data["vectors"]):
        norm = math.sqrt(math.fsum(value * value for value in vector))
        scored.append({"evidence_id": evidence_id, "score": math.fsum(a * (b / norm) for a, b in zip(query, vector)),
                       "snapshot_id": data["snapshot_id"], "epoch": data["epoch"]})
    return sorted(scored, key=lambda row: (-row["score"], row["evidence_id"]))[: int(top_k)]
