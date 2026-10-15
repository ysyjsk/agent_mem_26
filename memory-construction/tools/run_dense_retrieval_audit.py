#!/usr/bin/env python3
"""Audit dense retrieval against fixed development questions.

This is a narrow, non-official quality gate.  It reads the immutable dense
descriptor and pinned snapshot emitted by ``run_fast_compare.py``, embeds each
plain question independently with one resident local Qwen embedding model,
and calls :func:`workflow_memory.dense_publication.search_dense` with
``top_k=8``.  It never calls a Reader, sends evaluator references to a model,
or edits the fixed question manifest.

The only quality numbers produced here are evaluator-side retrieval metrics:
source-event recall and optional exact source-literal field coverage.  These
are not answer accuracy or official QA scores.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Mapping, Sequence

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT / "src"))

from workflow_memory.config import load_json, write_json  # noqa: E402
from workflow_memory.construction import Snapshot, validate_snapshot  # noqa: E402
from workflow_memory.dense_publication import read_dense, search_dense  # noqa: E402
from workflow_memory.ir import canonical_json, stable_hash  # noqa: E402
from workflow_memory.local_backends import TransformersEmbeddingBackend  # noqa: E402


PROTOCOL = "dense-retrieval-audit/non-official-v1"
DEFAULT_TOP_K = 8
DEFAULT_MAX_LENGTH = 1024
DEFAULT_BATCH_SIZE = 2
_MODEL_PAYLOAD_FORBIDDEN_KEYS = frozenset({
    "reference", "source_fields", "source_ids", "source_refs", "gold", "expected",
})


def file_hash(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def write_table(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("status\nmissing\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()


def verify_question_manifest(manifest: Mapping[str, Any]) -> None:
    """Verify fixed QA metadata without changing or exposing it to the model."""

    manifest_hash = manifest.get("manifest_hash")
    if manifest_hash and stable_hash({key: value for key, value in manifest.items()
                                      if key != "manifest_hash"}) != manifest_hash:
        raise ValueError("question manifest hash mismatch")
    questions = manifest.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("question manifest has no fixed questions")
    ids = []
    for question in questions:
        if not isinstance(question, Mapping):
            raise ValueError("question manifest contains a non-object question")
        question_id = str(question.get("question_id", ""))
        if not question_id:
            raise ValueError("fixed question is missing question_id")
        ids.append(question_id)
        reference = question.get("reference")
        if not isinstance(reference, Mapping):
            raise ValueError(f"question {question_id} is missing evaluator reference")
        reference_hash = reference.get("reference_hash")
        if reference_hash and stable_hash({key: value for key, value in reference.items()
                                           if key != "reference_hash"}) != reference_hash:
            raise ValueError(f"question {question_id} reference hash mismatch")
        fields = reference.get("source_fields")
        if not isinstance(fields, list):
            raise ValueError(f"question {question_id} has no source_fields")
    if len(ids) != len(set(ids)):
        raise ValueError("question manifest contains duplicate question IDs")


def _descriptor_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = row.get("dense_descriptor")
    if isinstance(descriptor, Mapping):
        return dict(descriptor)
    if isinstance(descriptor, (str, Path)):
        return dict(load_json(descriptor))
    descriptor_path = row.get("dense_descriptor_path")
    if descriptor_path:
        return dict(load_json(descriptor_path))
    raise ValueError("checkpoint row has no dense_descriptor")


def load_pinned_snapshot(row: Mapping[str, Any]) -> Snapshot:
    """Load and independently verify the snapshot referenced by one row."""

    snapshot_path = row.get("snapshot_path")
    if not snapshot_path:
        raise ValueError("checkpoint row has no snapshot_path")
    snapshot = Snapshot.from_dict(load_json(snapshot_path))
    if row.get("snapshot_id") != snapshot.snapshot_id:
        raise ValueError("checkpoint row snapshot_id differs from snapshot payload")
    if row.get("checkpoint_prefix_length") is not None and len(snapshot.events) != int(row["checkpoint_prefix_length"]):
        raise ValueError("snapshot event prefix differs from checkpoint row")
    report = validate_snapshot(snapshot)
    if not report.valid:
        raise ValueError(f"snapshot validation failed: {report.errors}")
    store_path = Path(snapshot.store_path).resolve()
    if not store_path.is_file():
        raise ValueError("snapshot's pinned SQLite store is missing")
    with sqlite3.connect(store_path.as_uri() + "?mode=ro", uri=True) as connection:
        persisted = connection.execute(
            "SELECT payload_json,epoch,checksum FROM snapshots WHERE snapshot_id=?",
            (snapshot.snapshot_id,),
        ).fetchone()
    if persisted is None:
        raise ValueError("snapshot is not present in its pinned SQLite store")
    persisted_snapshot = Snapshot.from_dict(json.loads(persisted[0]))
    if (canonical_json(persisted_snapshot.to_dict()) != canonical_json(snapshot.to_dict())
            or int(persisted[1]) != snapshot.epoch or str(persisted[2]) != snapshot.checksum):
        raise ValueError("snapshot payload/epoch/checksum differs from persisted store")
    return snapshot


def prepare_targets(construction_runs: Sequence[Path], questions: Sequence[Mapping[str, Any]],
                    methods: Sequence[str], repeat: int = 1) -> list[dict[str, Any]]:
    """Expand fixed questions into method/checkpoint targets without model calls."""

    if not methods or len(set(methods)) != len(methods):
        raise ValueError("methods must be non-empty and distinct")
    targets: list[dict[str, Any]] = []
    for run_path in construction_runs:
        run_path = Path(run_path).resolve()
        source_manifest = load_json(run_path / "manifest.json")
        run_status = load_json(run_path / "status.json")
        if run_status.get("status") not in {"completed", "completed_with_failures"}:
            raise ValueError(f"construction run is still active: {run_path}")
        available = [str(method) for method in source_manifest.get("methods", ())]
        selected = [method for method in methods if method in available]
        if not selected:
            raise ValueError(f"none of requested methods {list(methods)} exists in {run_path}")
        metrics_path = run_path / "checkpoint_metrics.jsonl"
        if not metrics_path.is_file():
            raise ValueError(f"construction metrics are missing: {metrics_path}")
        rows = [json.loads(line) for line in metrics_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows_by_key = {
            (str(row.get("method")), str(row.get("window_id")), int(row.get("checkpoint_prefix_length")),
             int(row.get("repeat", 1))): row
            for row in rows
        }
        for method in selected:
            for question in questions:
                key = (method, str(question["window_id"]), int(question["checkpoint_prefix_length"]), int(repeat))
                row = rows_by_key.get(key)
                if row is None:
                    raise ValueError(f"missing construction checkpoint {key} in {run_path}")
                targets.append({"construction_run_id": run_path.name, "construction_run": str(run_path),
                                "method": method, "question": dict(question), "checkpoint": row})
    return targets


def query_payload(question: Mapping[str, Any], model_id: str, *, max_length: int,
                  batch_size: int) -> dict[str, Any]:
    """Build the exact plain-text embedding request, with no evaluator data."""

    text = str(question.get("question", ""))
    if not text.strip():
        raise ValueError("fixed question text is empty")
    payload = {"model": str(model_id), "input": text,
               "max_length": int(max_length), "batch_size": int(batch_size)}
    if _MODEL_PAYLOAD_FORBIDDEN_KEYS & set(payload):
        raise AssertionError("evaluator-only fields leaked into embedding payload")
    return payload


def _reference_sources(reference: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item["event_id"]) for item in reference.get("source_fields", ())
                               if isinstance(item, Mapping) and item.get("event_id")))


def retrieval_metrics(snapshot: Snapshot, hits: Sequence[Mapping[str, Any]],
                      reference: Mapping[str, Any]) -> dict[str, Any]:
    """Compute evaluator-only source recall and literal coverage after search."""

    evidence_by_id = {item.evidence_id: item for item in snapshot.evidence}
    hit_ids = [str(hit["evidence_id"]) for hit in hits]
    hit_items = [evidence_by_id[item] for item in hit_ids if item in evidence_by_id]
    retrieved_sources = {source for item in hit_items for source in item.source_refs}
    reference_sources = set(_reference_sources(reference))
    source_recall = (len(retrieved_sources & reference_sources) / len(reference_sources)
                     if reference_sources else None)

    fields = [item for item in reference.get("source_fields", ()) if isinstance(item, Mapping)]
    covered_fields = 0
    for field in fields:
        event_id = str(field.get("event_id", ""))
        value_hash = field.get("field_value_hash")
        if any(event_id in item.source_refs and item.modality == "source_literal"
               and (not value_hash or stable_hash(item.value) == value_hash) for item in hit_items):
            covered_fields += 1
    literal_coverage = covered_fields / len(fields) if fields else None
    return {
        "retrieved_source_ids": sorted(retrieved_sources),
        "reference_source_ids": sorted(reference_sources),
        "source_recall": source_recall,
        "literal_field_coverage": literal_coverage,
        "literal_fields_covered": covered_fields,
        "literal_fields_total": len(fields),
    }


def _usage_tokens(usage: Mapping[str, Any]) -> int | None:
    value = usage.get("input_tokens", usage.get("prompt_tokens"))
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def summarize(rows: Sequence[Mapping[str, Any]], raw_path: Path) -> list[dict[str, Any]]:
    output = []
    keys = dict.fromkeys((row["construction_run_id"], row["method"]) for row in rows)
    for run_id, method in keys:
        selected = [row for row in rows if (row["construction_run_id"], row["method"]) == (run_id, method)]
        completed = [row for row in selected if row.get("status") == "completed"]
        recalls = [float(row["source_recall"]) for row in completed if row.get("source_recall") is not None]
        literal = [float(row["literal_field_coverage"]) for row in completed
                   if row.get("literal_field_coverage") is not None]
        token_values = [int(row["input_tokens"]) for row in completed if row.get("input_tokens") is not None]
        versions = sorted({str(row.get("render_version", "full-v1")) for row in selected})
        output.append({
            "construction_run_id": run_id,
            "method": method,
            "n_questions": len(selected),
            "completed_questions": len(completed),
            "failed_questions": len(selected) - len(completed),
            "source_recall_mean": sum(recalls) / len(recalls) if recalls else None,
            "literal_field_coverage_mean": sum(literal) / len(literal) if literal else None,
            "embedding_calls": sum(int(row.get("embedding_calls", 0)) for row in selected),
            "input_tokens": sum(token_values) if token_values else None,
            "embedding_elapsed_s": sum(float(row.get("embedding_elapsed_s") or 0.0) for row in selected),
            "retrieval_elapsed_s": sum(float(row.get("retrieval_elapsed_s") or 0.0) for row in selected),
            "total_elapsed_s": sum(float(row.get("elapsed_s") or 0.0) for row in selected),
            "dense_checks_passed": sum(bool(row.get("dense_valid")) for row in selected),
            "render_versions": ";".join(versions),
            "top_k": max((int(row.get("top_k", DEFAULT_TOP_K)) for row in selected), default=DEFAULT_TOP_K),
            "reader_calls": 0,
            "quality_scope": PROTOCOL,
            "official_qa_status": "not_evaluated",
            "raw_metrics_path": str(raw_path),
        })
    return output


def run(args: argparse.Namespace) -> int:
    if args.top_k < 1 or args.max_length < 1 or args.batch_size < 1:
        raise ValueError("top_k, max_length and batch_size must be positive")
    if args.top_k != DEFAULT_TOP_K:
        raise ValueError("this quality gate is pinned to top_k=8")
    questions_manifest = load_json(args.questions)
    verify_question_manifest(questions_manifest)
    questions = questions_manifest["questions"]
    methods = tuple(item.strip() for item in args.methods.split(",") if item.strip())
    targets = prepare_targets(args.construction_runs, questions, methods, repeat=args.repeat)
    root = args.out.resolve()
    if root.exists():
        raise ValueError(f"refuse to overwrite existing audit directory: {root}")
    root.mkdir(parents=True)

    runtime = load_json(args.config)
    embedding_cfg = dict(runtime["plan"]["models"]["embedding"])
    model_path = Path(str(embedding_cfg["local_path"])).expanduser().resolve()
    if not model_path.is_dir():
        raise ValueError(f"local embedding model path is missing: {model_path}")
    device = str(args.device or embedding_cfg.get("device") or "cuda:1")
    model_id = str(embedding_cfg.get("id") or model_path.name)
    audit_manifest = {
        "schema_version": "dense-retrieval-audit/1",
        "protocol": PROTOCOL,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config_sha256": file_hash(args.config),
        "question_manifest": str(args.questions.resolve()),
        "question_manifest_hash": questions_manifest.get("manifest_hash"),
        "construction_runs": [str(Path(path).resolve()) for path in args.construction_runs],
        "methods": list(methods),
        "repeat": int(args.repeat),
        "embedding": {"model_id": model_id, "local_path": str(model_path), "device": device,
                      "max_length": int(args.max_length), "batch_size": int(args.batch_size),
                      "query_text_policy": "plain_question_only", "network": "disabled_local_files_only",
                      "resident_model_loads": 1},
        "retrieval": {"top_k": int(args.top_k), "search": "search_dense", "reader_called": False,
                      "official_qa_status": "not_evaluated"},
        "evaluator_reference_policy": "source_fields_only_after_retrieval; never in embedding payload",
    }
    audit_manifest["manifest_hash"] = stable_hash(audit_manifest)
    write_json(root / "manifest.json", audit_manifest)
    write_json(root / "questions.json", questions_manifest)
    write_json(root / "status.json", {"status": "preflight", "started_at": audit_manifest["started_at"]})

    valid_targets: list[dict[str, Any]] = []
    preflight_failures = 0
    for index, target in enumerate(targets):
        question = target["question"]
        checkpoint = target["checkpoint"]
        preflight = {"target_index": index, "construction_run_id": target["construction_run_id"],
                     "method": target["method"], "question_id": question["question_id"],
                     "window_id": question["window_id"],
                     "checkpoint_prefix_length": question["checkpoint_prefix_length"], "status": "failed"}
        try:
            descriptor = _descriptor_from_row(checkpoint)
            snapshot = load_pinned_snapshot(checkpoint)
            snapshot_event_ids = {event.event_id for event in snapshot.events}
            reference_event_ids = set(_reference_sources(question["reference"]))
            if not reference_event_ids <= snapshot_event_ids:
                missing = sorted(reference_event_ids - snapshot_event_ids)
                raise ValueError(f"question reference source events are outside pinned snapshot: {missing}")
            data = read_dense(descriptor, snapshot=snapshot)
            if descriptor.get("snapshot_id") != snapshot.snapshot_id or int(descriptor.get("epoch")) != snapshot.epoch:
                raise ValueError("dense descriptor is not pinned to the requested snapshot")
            preflight.update(status="ready", snapshot_id=snapshot.snapshot_id, epoch=snapshot.epoch,
                             n_vectors=len(data["vectors"]), dimensions=data["dimensions"],
                             render_version=data.get("render_version", "full-v1"),
                             index_path=descriptor["index_path"])
            target = {**target, "descriptor": descriptor, "snapshot": snapshot, "dense_data": data}
            valid_targets.append(target)
        except Exception as exc:
            preflight_failures += 1
            preflight.update(error_type=type(exc).__name__, error=str(exc))
        append_jsonl(root / "preflight.jsonl", preflight)

    if not valid_targets:
        write_json(root / "status.json", {"status": "failed", "preflight_failures": preflight_failures})
        write_json(root / "metrics.json", {"status": "failed", "preflight_failures": preflight_failures,
                                            "n_targets": len(targets), "official_qa_status": "not_evaluated"})
        return 1

    if args.preflight_only:
        status = "completed_with_failures" if preflight_failures else "completed"
        write_json(root / "metrics.json", {"status": status, "n_targets": len(targets),
                                            "ready_targets": len(valid_targets),
                                            "preflight_failures": preflight_failures,
                                            "official_qa_status": "not_evaluated",
                                            "reader_calls": 0, "gpu_model_calls": 0})
        write_json(root / "status.json", {"status": status, "preflight_failures": preflight_failures,
                                           "gpu_model_calls": 0})
        return 0 if not preflight_failures else 1

    backend = TransformersEmbeddingBackend(
        str(model_path), device=device,
        dtype=str(embedding_cfg.get("dtype") or embedding_cfg.get("precision") or "bfloat16"),
        max_length=int(args.max_length), batch_size=int(args.batch_size),
        local_files_only=True,
    )
    load_started = time.perf_counter()
    try:
        backend._ensure_loaded()
    except Exception as exc:
        load_s = time.perf_counter() - load_started
        write_json(root / "embedding_setup.json", {
            "load_s": load_s, "model_id": model_id, "device": device,
            "max_length": int(args.max_length), "batch_size": int(args.batch_size),
            "resident_model_loads": 1, "warmup_calls": 0,
            "status": "failed", "error_type": type(exc).__name__, "error": str(exc),
        })
        write_json(root / "metrics.json", {"status": "failed", "n_targets": len(targets),
                                            "ready_targets": len(valid_targets),
                                            "preflight_failures": preflight_failures,
                                            "model_load_s": load_s, "model_load_error": str(exc),
                                            "official_qa_status": "not_evaluated", "reader_calls": 0})
        write_json(root / "status.json", {"status": "failed", "preflight_failures": preflight_failures,
                                           "model_load_error": str(exc)})
        raise
    load_s = time.perf_counter() - load_started
    write_json(root / "embedding_setup.json", {
        "load_s": load_s, "fingerprint": backend.fingerprint(), "model_id": model_id,
        "device": device, "max_length": int(args.max_length), "batch_size": int(args.batch_size),
        "resident_model_loads": 1, "warmup_calls": 0,
    })
    write_json(root / "status.json", {"status": "running", "model_load_s": load_s,
                                       "preflight_failures": preflight_failures})

    rows: list[dict[str, Any]] = []
    for index, target in enumerate(valid_targets):
        question = target["question"]
        snapshot = target["snapshot"]
        descriptor = target["descriptor"]
        payload = query_payload(question, model_id, max_length=args.max_length, batch_size=args.batch_size)
        row = {
            "construction_run_id": target["construction_run_id"], "construction_run": target["construction_run"],
            "method": target["method"], "question_id": question["question_id"],
            "window_id": question["window_id"], "checkpoint_prefix_length": question["checkpoint_prefix_length"],
            "category": question.get("category"), "quality_type": question.get("quality_type", "unknown"),
            "status": "failed", "query_request": payload, "request_hash": stable_hash(payload),
            "reader_called": False, "official_qa_status": "not_evaluated", "quality_scope": PROTOCOL,
            "top_k": args.top_k, "snapshot_id": snapshot.snapshot_id, "epoch": snapshot.epoch,
            "render_version": descriptor.get("render_version", "full-v1"), "dense_valid": False,
            "embedding_calls": 0, "input_tokens": None, "output_tokens": None,
            "embedding_elapsed_s": None, "retrieval_elapsed_s": None, "elapsed_s": None,
        }
        started = time.perf_counter()
        try:
            embed_started = time.perf_counter()
            row["embedding_calls"] = 1
            response = backend.embed([str(question["question"])])
            embedding_elapsed_s = time.perf_counter() - embed_started
            if len(response.vectors) != 1:
                raise ValueError("embedding backend returned a vector count different from one query")
            query_vector = response.vectors[0]
            usage = dict(response.usage)
            row.update(embedding_usage=usage, embedding_raw=dict(response.raw),
                       embedding_request_fingerprint=response.request_fingerprint,
                       input_tokens=_usage_tokens(usage), embedding_elapsed_s=embedding_elapsed_s)
            retrieval_started = time.perf_counter()
            hits = search_dense(descriptor, query_vector, top_k=args.top_k, snapshot=snapshot)
            retrieval_elapsed_s = time.perf_counter() - retrieval_started
            evaluator = retrieval_metrics(snapshot, hits, question["reference"])
            row.update({"status": "completed", "dense_valid": True, "embedding_calls": 1,
                        "embedding_usage": usage, "embedding_raw": dict(response.raw),
                        "embedding_request_fingerprint": response.request_fingerprint,
                        "input_tokens": _usage_tokens(usage), "embedding_elapsed_s": embedding_elapsed_s,
                        "retrieval_elapsed_s": retrieval_elapsed_s, "query_vector_dimensions": len(query_vector),
                        "hits": [{"evidence_id": hit["evidence_id"], "score": hit["score"],
                                  "snapshot_id": hit["snapshot_id"], "epoch": hit["epoch"]} for hit in hits],
                        "hit_evidence_ids": [hit["evidence_id"] for hit in hits],
                        **evaluator})
        except Exception as exc:
            row.update(error_type=type(exc).__name__, error=str(exc))
            if row["embedding_calls"] and row.get("embedding_elapsed_s") is None:
                row["embedding_elapsed_s"] = time.perf_counter() - embed_started
        row["elapsed_s"] = time.perf_counter() - started
        # Evaluator-only provenance is kept outside query_request and is never
        # passed to the embedding backend.
        row["evaluator_only"] = {"reference_status": question["reference"].get("reference_status"),
                                 "source_fields": question["reference"].get("source_fields", [])}
        append_jsonl(root / "embedding_requests.jsonl", {
            "construction_run_id": row["construction_run_id"], "method": row["method"],
            "question_id": row["question_id"], "request_hash": row["request_hash"],
            "payload": payload, "status": row["status"], "embedding_calls": row["embedding_calls"],
            "usage": row.get("embedding_usage"), "elapsed_s": row["embedding_elapsed_s"],
            "evaluator_fields_sent": False,
        })
        append_jsonl(root / "retrieval_per_question.jsonl", row)
        rows.append(row)
        write_json(root / "progress.json", {"status": "running", "questions_attempted": len(rows),
                   "total": len(valid_targets), "preflight_failures": preflight_failures,
                   "last": {key: row[key] for key in ("construction_run_id", "method", "question_id", "status")},
                   "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        print(json.dumps({key: row.get(key) for key in ("construction_run_id", "method", "question_id", "status",
                                                         "source_recall", "literal_field_coverage")}, ensure_ascii=False),
              flush=True)

    summaries = summarize(rows, root / "retrieval_per_question.jsonl")
    write_table(root / "retrieval_summary.csv", summaries)
    failures = preflight_failures + sum(row.get("status") != "completed" for row in rows)
    status = "completed_with_failures" if failures else "completed"
    write_json(root / "metrics.json", {"status": status, "n_targets": len(targets),
               "preflight_failures": preflight_failures, "question_attempts": len(rows),
               "failed_questions": sum(row.get("status") != "completed" for row in rows),
               "summary": summaries, "official_qa_status": "not_evaluated",
               "reader_calls": 0, "model_load_s": load_s})
    write_json(root / "status.json", {"status": status, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                       "preflight_failures": preflight_failures,
                                       "failed_questions": sum(row.get("status") != "completed" for row in rows)})
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--construction-runs", nargs="+", type=Path, required=True)
    parser.add_argument("--methods", required=True, help="comma-separated method IDs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--device", default=None, help="override runtime embedding device; default is config (cuda:1)")
    parser.add_argument("--preflight-only", action="store_true",
                        help="validate fixed snapshots and dense indexes without loading the embedding model")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
