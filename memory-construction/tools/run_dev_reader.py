#!/usr/bin/env python3
"""Frozen auto-source development questions; not official or human-gold QA.

Preparation may inspect source fields. Evaluation reads persisted checkpoints;
only the question and budgeted memory evidence enter the real Qwen Reader.
One resident Reader serves all requested construction runs, without answer cache.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Mapping, Sequence
import unicodedata

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT / "src"))
sys.path.insert(0, str(CODE_ROOT / "tools"))

from run_fast_compare import RecordingBackend, append_jsonl, file_hash, load_workload, now, percentile, token_sum, write_table
from workflow_memory.backends import ModelRequest
from workflow_memory.config import load_json, write_json
from workflow_memory.construction import Snapshot, query, validate_snapshot
from workflow_memory.ir import canonical_json, stable_hash
from workflow_memory.local_backends import TransformersQwenBackend


def prepare_questions(workload: Mapping[str, Any]) -> dict[str, Any]:
    questions = []
    for spec, events in load_workload(workload):
        checkpoints = spec["checkpoint_prefix_lengths"]
        if not 1 <= len(checkpoints) <= 3:
            raise ValueError("development QA requires one to three fixed checkpoints per window")
        for index, cut in enumerate(checkpoints):
            current = events[cut - 1]
            if index == 0:
                expected = current.post_state_ref.get("url") if isinstance(current.post_state_ref, Mapping) else None
                expected = expected if isinstance(expected, str) and expected else None
                category, targets, fields = "observed_url", [current], ["post_state_ref.url"]
                text = (f"At the checkpoint containing {cut} source steps, what URL was observed after source step {cut}? "
                        "Return only the exact observed URL. Do not infer an action succeeded. If it is absent from the retrieved evidence, return unknown.")
                answer_format = "exact_scalar"
            elif index == 1:
                expected = current.action
                category, targets, fields = "attempt_action", [current], ["action"]
                text = (f"At the checkpoint containing {cut} source steps, what action command was attempted at source step {cut}? "
                        "Return only the exact action command, not an inferred outcome. If it is absent from the retrieved evidence, return unknown.")
                answer_format = "exact_scalar"
            else:
                targets = events[max(0, cut - 2) : cut]
                expected = [source.action for source in targets]
                category, fields = ("workflow_order" if len(targets) == 2 else "workflow_order_single"), ["action"] * len(targets)
                if len(targets) == 2:
                    text = (f"At the checkpoint containing {cut} source steps, list the action commands attempted at source steps {cut-1} and {cut}, in that order. "
                            "Return only a JSON array of two exact command strings. If either is absent from the retrieved evidence, return unknown.")
                else:
                    text = (f"At the checkpoint containing {cut} source steps, list the action command attempted at source step {cut}. "
                            "Return only a JSON array of one exact command string. If it is absent from the retrieved evidence, return unknown.")
                answer_format = "ordered_exact_array"
            values = expected if isinstance(expected, list) else [expected]
            reference_available = all(isinstance(value, str) and value for value in values)
            refs = [{"event_id": source.event_id, "source_revision": source.source_revision,
                     "raw_content_hash": source.raw_content_hash, "field": field, "field_value_hash": stable_hash(value)}
                    for source, field, value in zip(targets, fields, values)]
            question = {"question_id": f"{spec['window_id']}-cp{cut}-{category}", "window_id": spec["window_id"],
                        "checkpoint_prefix_length": cut, "category": category, "question": text,
                        "answer_format": answer_format, "quality_type": "exact_field",
                        "reference": {"expected": expected, "source_fields": refs,
                        "generation": "deterministic direct source-field projection, not human gold"}}
            question["reference"].update(reference_status="available" if reference_available else "unavailable")
            question["reference"]["reference_hash"] = stable_hash({key: value for key, value in question["reference"].items() if key != "reference_hash"})
            questions.append(question)
    manifest = {"schema_version": "development-reader/1", "purpose": "auto-source development proxy; not official QA or human gold",
                "generator": "tools/run_dev_reader.py:prepare_questions/v2", "generator_sha256": file_hash(Path(__file__)),
                "workload_manifest_hash": stable_hash(workload), "source_file": workload["source_file"],
                "source_sha256": workload["source_sha256"], "input_modality": "text-only",
                "reader_settings": {"retrieval": "core_lexical_query_v1", "retrieval_budget": 8, "output_tokens": 256,
                                    "max_input_tokens": 8192, "temperature": 0.0, "enable_thinking": False},
                "scoring": "normalized exact scalar / ordered JSON array; bag-token F1 secondary; all attempted questions denominator",
                "reference_visibility": "evaluator only; no reference fields or oracle source IDs in Reader requests/retrieval",
                "cross_check": "source SHA256, normalized event IDs and source-field hashes verified during deterministic preparation",
                "short_window_categories": "one checkpoint observed_url; two observed_url/attempt_action; three observed_url/attempt_action/workflow_order",
                "missing_reference_rule": "retain fixed question, report unavailable/null score; do not choose an easier replacement",
                "questions": questions}
    manifest["manifest_hash"] = stable_hash(manifest)
    return manifest


def _extra_reference(expected: Any, target: Any, field: str, *, generation: str,
                     source_value: Any = None) -> dict[str, Any]:
    """Build evaluator-only provenance for a frozen v2 diagnostic question."""

    reference = {"expected": expected, "source_fields": [{
        "event_id": target.event_id,
        "source_revision": target.source_revision,
        "raw_content_hash": target.raw_content_hash,
        "field": field,
        "field_value_hash": stable_hash(expected if source_value is None else source_value),
    }], "generation": generation}
    reference["reference_status"] = "available" if expected not in (None, "", []) else "unavailable"
    reference["reference_hash"] = stable_hash({key: value for key, value in reference.items()
                                                if key != "reference_hash"})
    return reference


def prepare_questions_v2(workload: Mapping[str, Any]) -> dict[str, Any]:
    """Extend v1 with source-grounded status/state diagnostics."""

    from workflow_memory.source_literals import literal_evidence

    base = prepare_questions(workload)
    questions = list(base["questions"])
    by_window = {spec["window_id"]: (spec, events) for spec, events in load_workload(workload)}

    def event(window_id: str, cut: int):
        spec, events = by_window[window_id]
        if cut not in spec["checkpoint_prefix_lengths"]:
            raise ValueError(f"v2 question cut {cut} is not frozen for {window_id}")
        return events[cut - 1]

    def literal(window_id: str, cut: int, predicate: str, contains: str | None = None):
        target = event(window_id, cut)
        rows = literal_evidence(target, version="source-literals-v1")
        for row in rows:
            if row.predicate == predicate and (contains is None or contains in str(row.value)):
                return target, row
        raise ValueError(f"no source literal {predicate!r} for {window_id} cp{cut}")

    def add(window_id: str, cut: int, category: str, text: str, expected: Any,
            answer_format: str, quality_type: str, field: str, target: Any,
            source_value: Any = None) -> None:
        questions.append({"question_id": f"{window_id}-cp{cut}-{category}", "window_id": window_id,
                          "checkpoint_prefix_length": cut, "category": category, "question": text,
                          "answer_format": answer_format, "quality_type": quality_type,
                          "reference": _extra_reference(expected, target, field,
                                                         generation="deterministic source-literal/status projection, not human gold",
                                                         source_value=source_value)})

    target = event("170f5570-prefix9", 9)
    outcome = str(target.observed_outcome or "not_recorded")
    add("170f5570-prefix9", 9, "outcome_status",
        'At source step 9, what outcome status was explicitly recorded? Return exactly one of "success", "failure", or "not_recorded".',
        outcome, "exact_scalar", "semantic", "observed_outcome", target)

    target, failure = literal("4a5f0d7f-prefix12", 4, "error_span")
    add("4a5f0d7f-prefix12", 4, "failure_message_exact",
        "At source step 4, what exact failure message/span was observed? Return the exact message text; if it is absent from the retrieved evidence, return unknown.",
        str(failure.value), "exact_scalar", "exact_field", "post_state_ref.accessibility_tree.error_span", target)
    add("4a5f0d7f-prefix12", 4, "failure_status",
        'Classify the observed result at source step 4. Return exactly "blocked" or "not_recorded", using only retrieved failure evidence.',
        "blocked", "exact_scalar", "semantic", "post_state_ref.accessibility_tree.error_span", target,
        source_value=str(failure.value))

    target, state_record = literal("0db80092-prefix12", 12, "control_state", "value='Consumed'")
    add("0db80092-prefix12", 12, "control_state_exact",
        "At source step 12, return the exact published control-state record whose value is Consumed. If it is absent from the retrieved evidence, return unknown.",
        str(state_record.value), "exact_scalar", "exact_field", "post_state_ref.accessibility_tree.control_state", target)
    add("0db80092-prefix12", 12, "control_state_value",
        "What value was selected in the State field at source step 12? Return only the value, not an inferred outcome.",
        "Consumed", "exact_scalar", "semantic", "post_state_ref.accessibility_tree.control_state", target,
        source_value=str(state_record.value))

    target, shipping = literal("ec6c60c2-prefix12", 8, "control_state", "default shipping address")
    add("ec6c60c2-prefix12", 8, "shipping_checkbox_state",
        'At source step 8, was "Use as my default shipping address" checked? Return exactly true or false.',
        "false", "exact_scalar", "semantic", "post_state_ref.accessibility_tree.control_state", target,
        source_value=str(shipping.value))

    manifest = dict(base)
    manifest.update({"schema_version": "development-reader/2",
                     "purpose": "auto-source development proxy with exact-field and semantic diagnostics; not official QA or human gold",
                     "generator": "tools/run_dev_reader.py:prepare_questions_v2",
                     "question_version": "v2", "questions": questions,
                     "quality_dimensions": {"exact_field": "verbatim source literal/control/failure recovery",
                                             "semantic": "constrained status/state interpretation from retrieved evidence"},
                     "short_window_categories": "v1 12 questions plus frozen success/failure/state diagnostics"})
    manifest.pop("manifest_hash", None)
    manifest["manifest_hash"] = stable_hash(manifest)
    return manifest


def verify_questions(manifest: Mapping[str, Any]) -> None:
    if stable_hash({key: value for key, value in manifest.items() if key != "manifest_hash"}) != manifest["manifest_hash"]:
        raise ValueError("question manifest hash mismatch")
    ids = [question["question_id"] for question in manifest["questions"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate fixed development question IDs")
    for question in manifest["questions"]:
        reference = question["reference"]
        if stable_hash({key: value for key, value in reference.items() if key != "reference_hash"}) != reference["reference_hash"]:
            raise ValueError("question reference hash mismatch")


def load_checkpoint(row: Mapping[str, Any], question: Mapping[str, Any]) -> Snapshot:
    if row.get("status") != "completed" or not row.get("snapshot_valid"):
        raise ValueError("construction checkpoint did not complete with a valid snapshot")
    snapshot = Snapshot.from_dict(load_json(row["snapshot_path"]))
    store_path = Path(snapshot.store_path).resolve()
    if not store_path.is_file():
        raise ValueError("checkpoint's pinned SQLite store is missing")
    # Read-only URI prevents evaluation from changing the construction run.
    with sqlite3.connect(store_path.as_uri() + "?mode=ro", uri=True) as connection:
        record = connection.execute("SELECT payload_json,epoch,checksum FROM snapshots WHERE snapshot_id=?",
                                    (snapshot.snapshot_id,)).fetchone()
    if record is None or canonical_json(Snapshot.from_dict(json.loads(record[0])).to_dict()) != canonical_json(snapshot.to_dict()):
        raise ValueError("checkpoint file differs from its persisted SQLite payload")
    if (record[1] != snapshot.epoch or record[2] != snapshot.checksum or row["snapshot_id"] != snapshot.snapshot_id
            or len(snapshot.events) != question["checkpoint_prefix_length"] or not validate_snapshot(snapshot).valid):
        raise ValueError("checkpoint identity, epoch, prefix or checksum is invalid")
    return snapshot


def _bounded_reader_views(snapshot: Snapshot, selected_ids: Sequence[str],
                          positions: Mapping[str, int], *, allowed_positions: Sequence[int] | None = None,
                          limit: int = 8) -> dict[str, Any]:
    """Expose persisted derived views without serializing raw source history.

    Exact actions/URLs remain available only through retrieved evidence (and,
    in a quality run, source-literal evidence).  State/workflow/index are
    bounded public projections that let the Reader use views that were already
    published by construction instead of silently dropping them.
    """
    selected = set(str(item) for item in selected_ids)
    selected_items = [item for item in snapshot.evidence if item.evidence_id in selected]
    selected_events = {ref for item in selected_items for ref in item.source_refs}
    allowed = set(int(item) for item in allowed_positions) if allowed_positions is not None else None
    if allowed is not None:
        selected_events = {ref for ref in selected_events if positions.get(ref) in allowed}
    selected_state_keys = {f"{item.valid_scope}|{item.subject_ref}|{item.predicate}" for item in selected_items}
    evidence_positions = {item.evidence_id: sorted({positions[ref] for ref in item.source_refs if ref in positions})
                          for item in snapshot.evidence}

    def bounded_value(value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str) and len(value) <= 512:
            return value
        text = canonical_json(value) if not isinstance(value, str) else value
        return {"summary": text[:480], "truncated": len(text) > 480}
    state_rows = []
    for key, value in sorted(snapshot.state_view.items(), key=lambda pair: str(pair[0])):
        if not isinstance(value, Mapping):
            continue
        event_id = str(value.get("event_id", ""))
        evidence_ids = set(str(item) for item in value.get("evidence_ids", ())) if isinstance(value.get("evidence_ids"), (list, tuple, set)) else set()
        if key not in selected_state_keys and not (evidence_ids & selected):
            continue
        if allowed is not None and positions.get(event_id) not in allowed:
            continue
        state_rows.append({"predicate": value.get("predicate"), "value": bounded_value(value.get("value")),
                           "event_kind": value.get("event_kind"), "source_position": positions.get(event_id)})
        if len(state_rows) >= limit:
            break
    workflow_rows = []
    for scope, entries in sorted(snapshot.workflow_view.items(), key=lambda pair: str(pair[0])):
        if not isinstance(entries, (list, tuple)):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            event_id = str(entry.get("event_id", ""))
            evidence_ids = [str(item) for item in entry.get("evidence_ids", ())] if isinstance(entry.get("evidence_ids"), (list, tuple)) else []
            if event_id not in selected_events and not (set(evidence_ids) & selected):
                continue
            if allowed is not None and positions.get(event_id) not in allowed:
                continue
            # Do not copy raw action/outcome fields from workflow history;
            # source-literal/evidence records are the auditable fact channel.
            workflow_rows.append({"scope_slot": len(workflow_rows), "source_position": positions.get(event_id),
                                  "evidence_source_positions": sorted({position for item in evidence_ids if item in selected
                                                                         for position in evidence_positions.get(item, ())})})
            if len(workflow_rows) >= limit:
                break
        if len(workflow_rows) >= limit:
            break
    index_rows = []
    for term, evidence_ids in sorted(snapshot.index.items(), key=lambda pair: str(pair[0])):
        ids = [str(item) for item in evidence_ids if str(item) in selected]
        if allowed is not None:
            ids = [item for item in ids if set(evidence_positions.get(item, ())) & allowed]
        if not ids:
            continue
        index_rows.append({"term": str(term), "source_positions": sorted({position for item in ids
                                                                                for position in evidence_positions.get(item, ())})})
        if len(index_rows) >= limit * 4:
            break
    return {"state": state_rows, "workflow": workflow_rows, "index": index_rows}


def answer_snapshot(snapshot: Snapshot, question: Mapping[str, Any], backend: Any, recording: RecordingBackend,
                    settings: Mapping[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    mode = str(settings.get("retrieval", "core_lexical_query_v1"))
    if mode == "public-step-lexical-v2":
        from workflow_memory.temporal_retrieval import query_public_steps
        bundle, plan = query_public_steps(snapshot, question["question"], int(settings["retrieval_budget"]))
    elif mode == "core_lexical_query_v1":
        bundle = query(snapshot, question["question"], int(settings["retrieval_budget"]))
        plan = {"mode": mode, "strategy": "core_lexical_query", "budget": int(settings["retrieval_budget"]),
                "snapshot_id": snapshot.snapshot_id, "epoch": snapshot.epoch,
                "selected_evidence_ids": [item.evidence_id for item in bundle.evidence],
                "checks": {"budget_respected": len(bundle.evidence) <= int(settings["retrieval_budget"])},
                "request_hash": stable_hash({"question": question["question"], "mode": mode,
                                               "budget": int(settings["retrieval_budget"]), "snapshot_id": snapshot.snapshot_id, "epoch": snapshot.epoch})}
    else:
        raise ValueError(f"unknown Reader retrieval mode: {mode}")
    retrieval_s = time.perf_counter() - started
    positions = {source.event_id: index + 1 for index, source in enumerate(snapshot.events)}
    # Expose only actual retrieved memory and ordinal provenance. Gold source
    # IDs and source raw actions/states never enter the Reader prompt.
    evidence = [{"predicate": item.predicate, "value": item.value, "event_kind": item.event_kind,
                 "certainty": item.certainty, "modality": item.modality,
                 "exact_source_literal": item.modality == "source_literal",
                 "source_positions": [positions[ref] for ref in item.source_refs if ref in positions]}
                for item in bundle.evidence]
    allowed_positions = plan.get("in_prefix_source_positions") if plan.get("requested_source_positions") else None
    views = (_bounded_reader_views(snapshot, [item.evidence_id for item in bundle.evidence], positions,
                                   allowed_positions=allowed_positions)
             if settings.get("include_views", False) else {})
    context = {"retrieval_s": retrieval_s, "evidence_count": len(evidence), "reader_evidence": evidence,
            "reader_views": views,
            "retrieval_mode": mode, "public_query_plan": plan,
            "retrieved_evidence_ids": [item.evidence_id for item in bundle.evidence],
            "retrieved_source_ids": sorted({ref for item in bundle.evidence for ref in item.source_refs}),
            "snapshot_id": snapshot.snapshot_id, "epoch": snapshot.epoch}
    reader_started = time.perf_counter()
    try:
        reader_kwargs = {"_complete": recording.complete,
                         "max_tokens": int(settings["output_tokens"]),
                         "max_input_tokens": int(settings["max_input_tokens"])}
        if settings.get("include_views", False):
            reader_kwargs["bounded_views"] = True
        answer = backend.answer(question["question"], {"evidence": evidence, **views}, **reader_kwargs)
    except Exception as exc:
        exc.reader_context = {**context, "reader_s": time.perf_counter()-reader_started,
                              "elapsed_s": time.perf_counter()-started}
        raise
    return {**context, "answer": answer, "reader_s": time.perf_counter()-reader_started,
            "elapsed_s": time.perf_counter()-started}


def _normalize(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value)).strip().strip("`").split())


def score_answer(answer: str, question: Mapping[str, Any]) -> dict[str, Any]:
    text = str(answer).strip()
    if text.startswith("```") and text.endswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    unknown = _normalize(text).lower().rstrip(".") in {"unknown", "not enough evidence", "not evidenced", "insufficient evidence"}
    if question["reference"].get("reference_status") == "unavailable":
        return {"proxy_exact": None, "proxy_token_f1": None, "unknown": unknown,
                "proxy_score_status": "reference_unavailable"}
    expected = question["reference"]["expected"]
    try:
        decoded = json.loads(text)
    except (ValueError, TypeError):
        decoded = text
    if isinstance(expected, list):
        exact = isinstance(decoded, list) and [_normalize(value) for value in decoded] == [_normalize(value) for value in expected]
        reference_text = canonical_json(expected)
    else:
        # Scalar references are strings, including literal tokens such as
        # "false" or "02139".  JSON parsing is only a convenience for quoted
        # strings; it must not turn an identical plain token into a type error.
        scalar = decoded if isinstance(decoded, str) else text
        exact = _normalize(scalar) == _normalize(expected)
        reference_text = str(expected)
    tokenize = lambda value: Counter(re.findall(r"\w+|[^\w\s]", unicodedata.normalize("NFC", value).casefold()))
    predicted, reference = tokenize(text), tokenize(reference_text)
    overlap = sum((predicted & reference).values())
    denominator = sum(predicted.values()) + sum(reference.values())
    f1 = 2 * overlap / denominator if denominator else 1.0
    return {"proxy_exact": int(exact and not unknown), "proxy_token_f1": 0.0 if unknown else 1.0 if exact else f1, "unknown": unknown}


def summarize(rows: Sequence[Mapping[str, Any]], raw_path: Path) -> list[dict[str, Any]]:
    summaries = []
    for key in dict.fromkeys((row["construction_run_id"], row["method"]) for row in rows):
        selected = [row for row in rows if (row["construction_run_id"], row["method"]) == key]
        completed = [row for row in selected if row["status"] == "completed"]
        evaluable = [row for row in selected if row.get("reference_available", True)]
        summaries.append({"construction_run_id": key[0], "method": key[1], "n_questions": len(selected),
                          "completed_questions": len(completed), "failed_questions": len(selected)-len(completed),
                          "unknown_answers": sum(bool(row["unknown"]) for row in selected),
                          "proxy_evaluable_questions": len(evaluable), "unavailable_references": len(selected)-len(evaluable),
                          "dev_proxy_exact_rate": sum(row["proxy_exact"] or 0 for row in evaluable)/len(evaluable) if evaluable else None,
                          "dev_proxy_token_f1": sum(row["proxy_token_f1"] or 0 for row in evaluable)/len(evaluable) if evaluable else None,
                          "retrieval_source_recall": sum(row.get("retrieval_source_recall", 0.0) for row in selected)/len(selected),
                          "reader_calls": sum(row["reader_calls"] for row in selected),
                          "input_tokens": token_sum(selected, "input_tokens"), "output_tokens": token_sum(selected, "output_tokens"),
                          "reader_latency_p50_s": percentile([row["reader_s"] for row in completed], 0.5),
                          "query_latency_p50_s": percentile([row.get("elapsed_s", row["reader_s"]) for row in completed], 0.5),
                          "total_retrieval_s": sum(row.get("retrieval_s", 0.0) for row in selected),
                          "total_reader_s": sum(row.get("reader_s", 0.0) for row in selected),
                          "official_qa_status": "not_evaluated", "quality_scope": "auto_source_development_proxy",
                          "retrieval_mode": selected[0].get("retrieval_mode", "core_lexical_query_v1"),
                          "reader_settings_hash": selected[0].get("reader_settings_hash"),
                          "quality_type": (selected[0].get("quality_type", "exact_field")
                                            if len({row.get("quality_type", "exact_field") for row in selected}) == 1
                                            else "mixed"),
                          "raw_metrics_path": str(raw_path)})
    return summaries


def summarize_by_quality_type(rows: Sequence[Mapping[str, Any]], raw_path: Path) -> list[dict[str, Any]]:
    output = []
    for quality_type in dict.fromkeys(row.get("quality_type", "exact_field") for row in rows):
        for summary in summarize([row for row in rows
                                  if row.get("quality_type", "exact_field") == quality_type], raw_path):
            summary["quality_type"] = quality_type
            output.append(summary)
    return output


def run(args: argparse.Namespace) -> int:
    if args.prepare_only:
        workload = load_json(args.manifest)
        if args.questions.exists():
            manifest = load_json(args.questions)
            verify_questions(manifest)
            if (manifest["workload_manifest_hash"] != stable_hash(workload)
                    or file_hash(Path(workload["source_file"])) != manifest["source_sha256"]):
                raise ValueError("refuse to overwrite a different frozen question manifest")
        else:
            manifest = prepare_questions_v2(workload) if args.question_version == "v2" else prepare_questions(workload)
            write_json(args.questions, manifest)
        print(json.dumps({"questions": len(manifest["questions"]), "manifest_hash": manifest["manifest_hash"],
                          "path": str(args.questions.resolve()), "official_qa": False}), flush=True)
        return 0
    if not args.runs or args.out is None:
        raise ValueError("--run requires --runs <completed construction directories> and --out <new directory>")
    manifest = load_json(args.questions)
    verify_questions(manifest)
    if file_hash(Path(manifest["source_file"])) != manifest["source_sha256"]:
        raise ValueError("frozen QA source hash changed")
    root = args.out.resolve()
    if root.exists():
        raise ValueError("refuse to overwrite an existing Reader run")
    targets, provenance = [], []
    wanted = set(args.methods.split(",")) if args.methods else None
    for path in args.runs:
        path = path.resolve()
        source_manifest, status = load_json(path / "manifest.json"), load_json(path / "status.json")
        if status["status"] not in {"completed", "completed_with_failures"}:
            raise ValueError(f"construction run is still active: {path}")
        if stable_hash(source_manifest["workload"]) != manifest["workload_manifest_hash"]:
            raise ValueError(f"construction workload differs from frozen development questions: {path}")
        metrics = [json.loads(line) for line in (path / "checkpoint_metrics.jsonl").read_text().splitlines() if line.strip()]
        rows_by_key = {(row["method"], row["window_id"], row["checkpoint_prefix_length"], row["repeat"]): row for row in metrics}
        methods = [method for method in source_manifest["methods"] if wanted is None or method in wanted]
        provenance.append({"path": str(path), "manifest_sha256": file_hash(path / "manifest.json"),
                           "metrics_sha256": file_hash(path / "checkpoint_metrics.jsonl"), "methods": methods})
        targets.extend((path.name, method, question, rows_by_key.get((method, question["window_id"],
                        question["checkpoint_prefix_length"], args.repeat))) for method in methods for question in manifest["questions"])
    if not targets:
        raise ValueError("no selected construction methods to evaluate")
    runtime = load_json(args.config)
    model = runtime["plan"]["models"]["reader"]
    settings = dict(manifest["reader_settings"])
    retrieval_override = getattr(args, "retrieval_mode", None)
    if retrieval_override is not None:
        settings["retrieval"] = retrieval_override
    if getattr(args, "reader_views", False):
        settings["include_views"] = True
    settings_hash = stable_hash(settings)
    code_paths = [Path(__file__), CODE_ROOT / "src/workflow_memory/local_backends.py", CODE_ROOT / "src/workflow_memory/construction.py"]
    if settings["retrieval"] == "public-step-lexical-v2":
        code_paths.append(CODE_ROOT / "src/workflow_memory/temporal_retrieval.py")
    code_paths.append(CODE_ROOT / "src/workflow_memory/source_literals.py")
    root.mkdir(parents=True)
    write_json(root / "questions.json", manifest)
    write_json(root / "manifest.json", {"schema_version": "development-reader-run/1", "started_at": now(),
               "question_manifest_hash": manifest["manifest_hash"], "construction_runs": provenance, "repeat": args.repeat,
               "reader_model": model, "reader_settings": settings, "config_sha256": file_hash(args.config),
               "reader_settings_hash": settings_hash, "reader_settings_manifest_original": manifest["reader_settings"],
               "retrieval_mode_override": retrieval_override,
               "code_sha256": {str(path.relative_to(CODE_ROOT)): file_hash(path) for path in code_paths},
               "quality_scope": "auto_source_development_proxy", "official_qa_status": "not_evaluated",
               "construction_latency_includes_reader": False, "reader_response_cache": False})
    write_json(root / "status.json", {"status": "loading", "started_at": now()})
    backend = TransformersQwenBackend(model["local_path"], device=model.get("device", "cuda:0"),
              dtype=model.get("dtype") or model.get("precision") or "bfloat16",
              max_input_tokens=settings["max_input_tokens"], enable_thinking=False)
    started = time.perf_counter()
    try:
        backend._ensure_loaded()
        load_s = time.perf_counter()-started
        warm = backend.complete(ModelRequest(prompt="Reply OK only.", max_tokens=8, temperature=0.0))
        write_json(root / "model_setup.json", {"load_s": load_s, "warmup_usage": dict(warm.usage), "fingerprint": backend.fingerprint()})
    except Exception as exc:
        write_json(root / "status.json", {"status": "failed", "error": str(exc), "error_type": type(exc).__name__})
        raise
    recording, rows = RecordingBackend(backend, root), []
    for source_run_id, method, question, checkpoint in targets:
        recording.context = {"construction_run_id": source_run_id, "method": method, "question_id": question["question_id"],
                             "window_id": question["window_id"], "checkpoint_prefix_length": question["checkpoint_prefix_length"]}
        row = {**recording.context, "category": question["category"],
               "quality_type": question.get("quality_type", "exact_field"),
               "question": question["question"], "repeat": args.repeat,
               "status": "failed", "unknown": False, "proxy_exact": 0, "proxy_token_f1": 0.0, "reader_calls": 0,
               # A failed request has no trustworthy usage accounting.  Keep
               # these null so summaries cannot misread a failed call as an
               # actual zero-token success.
               "input_tokens": None, "output_tokens": None, "question_manifest_hash": manifest["manifest_hash"],
               "reference_available": question["reference"].get("reference_status") != "unavailable",
               "reader_settings_hash": settings_hash, "retrieval_mode": settings["retrieval"]}
        call_start, started = len(recording.calls), time.perf_counter()
        try:
            if checkpoint is None:
                raise ValueError("requested construction checkpoint is missing")
            snapshot = load_checkpoint(checkpoint, question)
            response = answer_snapshot(snapshot, question, backend, recording, settings)
            row.update(response, **score_answer(response["answer"], question), status="completed")
        except Exception as exc:
            row.update(error=str(exc), error_type=type(exc).__name__)
            row.update(getattr(exc, "reader_context", {}))
        refs = {item["event_id"] for item in question["reference"]["source_fields"]}
        row["retrieval_source_recall"] = len(refs & set(row.get("retrieved_source_ids", [])))/len(refs)
        row["reference"] = question["reference"]  # Evaluator-side log only; never sent to the backend.
        if not row["reference_available"]:
            row.update(proxy_exact=None, proxy_token_f1=None, proxy_score_status="reference_unavailable")
        calls = recording.calls[call_start:]
        row.update(reader_calls=len(calls), input_tokens=token_sum(calls, "input_tokens"),
                   output_tokens=token_sum(calls, "output_tokens"), wall_s=time.perf_counter()-started,
                   finish_reasons=[call.get("finish_reason") for call in calls])
        append_jsonl(root / "qa_per_question.jsonl", row)
        if "public_query_plan" in row:
            append_jsonl(root / "retrieval_plans.jsonl", {**recording.context, "question": question["question"],
                         "reader_settings_hash": settings_hash, **row["public_query_plan"]})
        rows.append(row)
        write_json(root / "progress.json", {"status": "running", "questions_attempted": len(rows), "total": len(targets),
                   "last": recording.context, "updated_at": now()})
        print(json.dumps({key: row[key] for key in ("construction_run_id", "method", "question_id", "status", "proxy_exact", "unknown")}), flush=True)
    summaries = summarize(rows, root / "qa_per_question.jsonl")
    write_table(root / "dev_quality.csv", summaries)
    summaries_by_type = summarize_by_quality_type(rows, root / "qa_per_question.jsonl")
    write_table(root / "dev_quality_by_type.csv", summaries_by_type)
    categories = [{"category": category, **summary} for category in dict.fromkeys(row["category"] for row in rows)
                  for summary in summarize([row for row in rows if row["category"] == category], root / "qa_per_question.jsonl")]
    write_table(root / "dev_quality_by_category.csv", categories)
    failures = sum(row["status"] != "completed" for row in rows)
    status = "completed_with_failures" if failures else "completed"
    write_json(root / "metrics.json", {"status": status, "n_attempted": len(rows), "failed_questions": failures,
               "question_manifest_hash": manifest["manifest_hash"], "summaries": summaries,
               "summaries_by_quality_type": summaries_by_type, "official_qa_status": "not_evaluated"})
    write_json(root / "status.json", {"status": status, "updated_at": now(), "failed_questions": failures})
    write_json(root / "progress.json", {"status": status, "questions_attempted": len(rows), "total": len(targets),
               "failed_questions": failures, "updated_at": now()})
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--manifest", type=Path, default=CODE_ROOT / "manifests/fastloop_dev_v1.json")
    parser.add_argument("--questions", type=Path, default=CODE_ROOT / "manifests/fastloop_dev_qa_v1.json")
    parser.add_argument("--config", type=Path, default=CODE_ROOT / "configs/runtime.local.json")
    parser.add_argument("--runs", nargs="+", type=Path)
    parser.add_argument("--methods", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--question-version", choices=["v1", "v2"], default="v1")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--retrieval-mode", choices=["core_lexical_query_v1", "public-step-lexical-v2"], default=None,
                        help="override recorded in run settings/hash; frozen question manifest stays unchanged")
    parser.add_argument("--reader-views", action="store_true", help="include bounded persisted derived views; recorded in settings/hash")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
