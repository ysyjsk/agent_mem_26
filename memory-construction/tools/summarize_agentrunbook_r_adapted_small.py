#!/usr/bin/env python3
"""Build a read-only summary of an AgentRunbook-R adapted Small run.

The source run is never modified. A live JSONL tail may be partial; malformed
lines are counted and skipped. Adapted evaluator scores are kept separate from
official Judge scores, which stay blank while official_judge_status is pending.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import statistics
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    try:
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                if isinstance(item, dict):
                    rows.append(item)
                else:
                    malformed += 1
    except OSError:
        pass
    return rows, malformed


def number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return value if math.isfinite(float(value)) else None


def total(values: Iterable[Any]) -> float | int | None:
    values = [number(value) for value in values]
    values = [value for value in values if value is not None]
    if not values:
        return None
    result = sum(float(value) for value in values)
    return int(result) if all(float(value).is_integer() for value in values) else result


def mean(values: Iterable[Any]) -> float | None:
    values = [number(value) for value in values]
    values = [float(value) for value in values if value is not None]
    return statistics.fmean(values) if values else None


def p95(values: Iterable[Any]) -> float | None:
    values = sorted(float(value) for value in values if number(value) is not None)
    if not values:
        return None
    return values[max(1, math.ceil(0.95 * len(values))) - 1]


def relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fp:
            fp.write(text)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


def summarize_calls(rows: list[dict[str, Any]], present: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "model_call_count": len(rows) if present else None,
        "model_success_count": sum(r.get("status") == "success" for r in rows) if present else None,
        "model_failed_count": sum(r.get("status") == "failed" for r in rows) if present else None,
        "model_prompt_tokens_observed_total": total(r.get("prompt_tokens") for r in rows),
        "model_prompt_token_records": sum(number(r.get("prompt_tokens")) is not None for r in rows) if present else None,
        "model_completion_tokens_observed_total": total(r.get("completion_tokens") for r in rows),
        "model_completion_token_records": sum(number(r.get("completion_tokens")) is not None for r in rows) if present else None,
        "model_total_tokens_observed_total": total(r.get("total_tokens") for r in rows),
        "model_total_token_records": sum(number(r.get("total_tokens")) is not None for r in rows) if present else None,
    }
    for channel in ("controller", "embedding"):
        selected = [r for r in rows if r.get("channel") == channel]
        out[channel + "_call_count"] = len(selected) if present and selected else (0 if present else None)
        out[channel + "_success_count"] = sum(r.get("status") == "success" for r in selected) if present else None
        out[channel + "_failed_count"] = sum(r.get("status") == "failed" for r in selected) if present else None
        out[channel + "_elapsed_seconds_total"] = total(r.get("elapsed_seconds") for r in selected)
        out[channel + "_prompt_tokens_observed_total"] = total(r.get("prompt_tokens") for r in selected)
        out[channel + "_prompt_token_records"] = sum(number(r.get("prompt_tokens")) is not None for r in selected) if present else None
        out[channel + "_completion_tokens_observed_total"] = total(r.get("completion_tokens") for r in selected)
        out[channel + "_completion_token_records"] = sum(number(r.get("completion_tokens")) is not None for r in selected) if present else None
        out[channel + "_total_tokens_observed_total"] = total(r.get("total_tokens") for r in selected)
        out[channel + "_total_token_records"] = sum(number(r.get("total_tokens")) is not None for r in selected) if present else None
    out["async_runtime_error_fast_count"] = sum(
        r.get("channel") == "controller" and r.get("call_mode") == "async_text"
        and r.get("status") == "failed" and r.get("error_type") == "RuntimeError"
        and number(r.get("elapsed_seconds")) is not None and float(r["elapsed_seconds"]) <= 0.1
        and r.get("error_status_code") is None for r in rows
    ) if present else None
    for error_name, field_name in (("RuntimeError", "model_runtime_error_count"), ("RateLimitError", "model_rate_limit_error_count")):
        out[field_name] = sum(r.get("status") == "failed" and r.get("error_type") == error_name for r in rows) if present else None
    out["model_other_error_count"] = sum(
        r.get("status") == "failed" and r.get("error_type") not in {None, "RuntimeError", "RateLimitError"}
        for r in rows
    ) if present else None
    return out


def ids_from_rows(rows: list[dict[str, Any]], field: str) -> list[str]:
    return [row[field] for row in rows if isinstance(row.get(field), str) and row[field]]


def input_question_id(row: dict[str, Any]) -> Any:
    # Official LongMemEval runtime_inputs/questions.json uses `id`; harness
    # prompt/per-question artifacts use `question_id`.
    return row.get("question_id") or row.get("id")


def summarize_reader(rows: list[dict[str, Any]], present: bool) -> dict[str, Any]:
    usage_rows = [r.get("usage") for r in rows if isinstance(r.get("usage"), dict)]
    out: dict[str, Any] = {
        # The harness persists one row per question, not every HTTP retry. Keep
        # this separate from memory_model_call_count below.
        "reader_question_count": len(rows) if present else None,
        "reader_success_count": sum(r.get("reader_status") in (None, "ok", "success") for r in rows) if present else None,
        "reader_failed_count": sum(r.get("reader_status") not in (None, "ok", "success") for r in rows) if present else None,
    }
    for label, key in (("prompt", "prompt_tokens"), ("completion", "completion_tokens"), ("total", "total_tokens")):
        values = [usage.get(key) for usage in usage_rows]
        out[f"reader_{label}_tokens_observed_total"] = total(values)
        out[f"reader_{label}_token_records"] = sum(number(value) is not None for value in values) if present else None
        out[f"reader_{label}_tokens_missing_count"] = max(0, len(rows) - out[f"reader_{label}_token_records"]) if present else None
    return out


def summarize_domain(run_root: Path, domain: str, manifest: dict[str, Any]) -> dict[str, Any]:
    folder = run_root / domain
    args_path = folder / "run_args.json"
    args = read_json(args_path)
    args = args if isinstance(args, dict) else {}
    q_input = folder / "runtime_inputs" / "questions.json"
    questions = read_json(q_input)
    expected = len(questions) if isinstance(questions, list) else None
    expected_question_ids = (
        [input_question_id(row) for row in questions]
        if isinstance(questions, list) and all(isinstance(row, dict) for row in questions)
        else None
    )
    question_ids_valid = bool(expected_question_ids is not None and all(isinstance(qid, str) and qid for qid in expected_question_ids))
    haystack = read_json(folder / "runtime_inputs" / "haystack.json")
    expected_build_ids = ({item for ids in haystack.values() if isinstance(ids, list) for item in ids if isinstance(item, str)} if isinstance(haystack, dict) else None)
    expected_build = len(expected_build_ids) if expected_build_ids is not None else None

    pq_path = folder / "per_question.jsonl"
    pq, pq_bad = read_jsonl(pq_path)
    pq_ids = ids_from_rows(pq, "question_id")
    expected_qid_set = set(expected_question_ids) if question_ids_valid else set()
    qid_set = set(pq_ids)
    q_missing = len(expected_qid_set - qid_set) if question_ids_valid else None
    q_extra = len(qid_set - expected_qid_set) if question_ids_valid else None
    q_duplicates = len(pq_ids) - len(qid_set) if pq_path.exists() else None
    question_complete = (
        question_ids_valid and pq_bad == 0 and len(pq) == expected
        and len(pq_ids) == len(pq) and qid_set == expected_qid_set
    )
    aggregate_path = folder / "aggregated_metrics.json"
    aggregate = read_json(aggregate_path)
    aggregate = aggregate if isinstance(aggregate, dict) else None
    build_path = folder / "memory_build_metrics.jsonl"
    builds, build_bad = read_jsonl(build_path)
    build_ids = ids_from_rows(builds, "trajectory_id")
    build_id_set = set(build_ids)
    build_missing = len(expected_build_ids - build_id_set) if expected_build_ids is not None else None
    build_extra = len(build_id_set - expected_build_ids) if expected_build_ids is not None else None
    build_duplicates = len(build_ids) - len(build_id_set) if build_path.exists() else None
    build_summary_path = folder / "memory_build_summary.json"
    build_summary = read_json(build_summary_path)
    build_summary = build_summary if isinstance(build_summary, dict) else None
    prompt_summary_path = folder / "prompt_build_summary.json"
    prompt_summary = read_json(prompt_summary_path)
    prompt_summary = prompt_summary if isinstance(prompt_summary, dict) else None
    prompt_rows_path = folder / "prompt_rows.jsonl"
    prompt_rows, prompt_rows_bad = read_jsonl(prompt_rows_path)
    prompt_ids = ids_from_rows(prompt_rows, "question_id")
    prompt_id_set = set(prompt_ids)
    calls_path = folder / "memory_workspace" / "shared" / "model_calls.jsonl"
    calls, calls_bad = read_jsonl(calls_path)
    config = manifest.get("configuration") if isinstance(manifest.get("configuration"), dict) else {}
    overall = aggregate.get("overall") if aggregate and isinstance(aggregate.get("overall"), dict) else {}
    required = [args_path, pq_path, aggregate_path, build_path, build_summary_path, prompt_summary_path, prompt_rows_path, calls_path]
    artifacts_present = all(path.is_file() for path in required)
    successful_build_ids = {r.get("trajectory_id") for r in builds if r.get("status") == "success"}
    build_complete = (
        expected_build_ids is not None and build_bad == 0 and len(builds) == expected_build
        and len(build_ids) == len(builds) and build_id_set == expected_build_ids
        and successful_build_ids == expected_build_ids
        and all(r.get("status") == "success" for r in builds)
    )
    agg_count = number(overall.get("count_all_questions")) if isinstance(overall, dict) else None
    aggregate_complete = expected is not None and agg_count == expected
    summary_prompt_ids = prompt_summary.get("question_ids") if prompt_summary else None
    prompt_complete = (
        question_ids_valid and prompt_summary is not None
        and prompt_summary.get("prompt_row_count") == expected
        and isinstance(summary_prompt_ids, list) and len(summary_prompt_ids) == expected
        and set(summary_prompt_ids) == expected_qid_set
        and prompt_rows_bad == 0 and len(prompt_rows) == expected
        and len(prompt_ids) == len(prompt_rows) and prompt_id_set == expected_qid_set
    )
    build_summary_complete = (
        build_summary is not None
        and build_summary.get("status") == "success"
        and build_summary.get("trajectory_count") == expected_build
    )
    if (
        artifacts_present and question_complete and aggregate_complete and build_complete
        and prompt_complete and build_summary_complete and calls_bad == 0
    ):
        status = "complete"
    elif any(path.exists() for path in (q_input, pq_path, build_path, calls_path)):
        status = "in_progress"
    else:
        status = "not_started"

    evaluator = config.get("evaluator_model") or args.get("evaluator_model")
    evaluator_scope = config.get("evaluator_scope") or args.get("evaluator_scope")
    judge_status = config.get("official_judge_status") or args.get("official_judge_status") or "unknown"
    evaluator_only = "evaluator-only" in str(evaluator_scope) or (evaluator and str(evaluator).lower() != "gpt-5.2")
    adapted_score = overall.get("overall_full_set") if evaluator_only else None
    official_score = overall.get("overall_full_set") if not evaluator_only and judge_status != "pending_judge" else None
    quality_status = ";".join(x for x, yes in (("pending_judge", judge_status == "pending_judge"), ("evaluator-only", bool(evaluator_only))) if yes) or None
    build_success = [r for r in builds if r.get("status") == "success"]
    build_failed = [r for r in builds if r.get("status") == "failed"]
    reader_failed = [r for r in pq if r.get("reader_status") not in (None, "ok", "success")]

    row: dict[str, Any] = {
        "domain": domain, "status": status, "run_kind": manifest.get("run_kind"),
        "method": manifest.get("method"), "tier": manifest.get("tier"), "upstream_commit": manifest.get("upstream_commit"),
        "quality_status": quality_status, "official_judge_status": judge_status,
        "evaluator_scope": evaluator_scope, "evaluator_model": evaluator,
        "official_overall_full_set": official_score, "adapted_overall_full_set": adapted_score,
        "adapted_overall_non_abstention_only": overall.get("overall_non_abstention_only") if evaluator_only else None,
        "adapted_overall_abstention_only": overall.get("overall_abstention_only") if evaluator_only else None,
        "expected_questions": expected, "scored_questions": len(pq) if pq_path.exists() else None,
        "question_ids_valid": question_ids_valid if questions is not None else None,
        "question_ids_unique_count": len(qid_set) if pq_path.exists() else None,
        "question_ids_missing_count": q_missing, "question_ids_extra_count": q_extra,
        "question_ids_duplicate_count": q_duplicates,
        "count_all_questions": overall.get("count_all_questions"), "count_non_abstention": overall.get("count_non_abstention"),
        "count_abstention": overall.get("count_abstention"), "reader_failure_count": len(reader_failed) if pq_path.exists() else None,
        "expected_unique_build_trajectories": expected_build,
        "build_metric_count": len(builds) if build_path.exists() else None,
        "build_summary_present": build_summary is not None if build_summary_path.exists() else None,
        "build_summary_trajectory_count": build_summary.get("trajectory_count") if build_summary else None,
        "build_summary_status": build_summary.get("status") if build_summary else None,
        "build_summary_elapsed_seconds": build_summary.get("elapsed_seconds") if build_summary else None,
        "build_success_count": len(build_success) if build_path.exists() else None,
        "build_failed_count": len(build_failed) if build_path.exists() else None,
        "build_ids_unique_count": len(build_id_set) if build_path.exists() else None,
        "build_ids_missing_count": build_missing, "build_ids_extra_count": build_extra,
        "build_ids_duplicate_count": build_duplicates,
        "build_elapsed_seconds_total": total(r.get("elapsed_seconds") for r in builds),
        "build_elapsed_seconds_avg": mean(r.get("elapsed_seconds") for r in builds),
        "build_elapsed_seconds_p95": p95(r.get("elapsed_seconds") for r in builds),
        "reader_generation_seconds_total": total(r.get("reader_generation_duration_seconds") for r in pq),
        "reader_generation_seconds_avg": mean(r.get("reader_generation_duration_seconds") for r in pq),
        "reader_generation_seconds_p95": p95(r.get("reader_generation_duration_seconds") for r in pq),
        "memory_query_seconds_total": total(r.get("memory_query_duration_seconds") for r in pq),
        "memory_query_seconds_avg": mean(r.get("memory_query_duration_seconds") for r in pq),
        "memory_query_seconds_p95": p95(r.get("memory_query_duration_seconds") for r in pq),
        "memory_post_query_seconds_total": total(r.get("memory_post_query_duration_seconds") for r in pq),
        "memory_context_tokens_total": total(r.get("memory_context_token_count") for r in pq),
        "memory_context_original_tokens_total": total(r.get("memory_context_original_token_count") for r in pq),
        "per_question_malformed_lines": pq_bad if pq_path.exists() else None,
        "build_malformed_lines": build_bad if build_path.exists() else None,
        "calls_malformed_lines": calls_bad if calls_path.exists() else None,
        "prompt_build_summary_present": prompt_summary is not None if prompt_summary_path.exists() else None,
        "prompt_build_row_count": prompt_summary.get("prompt_row_count") if prompt_summary else None,
        "prompt_rows_present": prompt_rows_path.exists(),
        "prompt_rows_count": len(prompt_rows) if prompt_rows_path.exists() else None,
        "prompt_rows_malformed_lines": prompt_rows_bad if prompt_rows_path.exists() else None,
        "prompt_question_ids_unique_count": len(prompt_id_set) if prompt_rows_path.exists() else None,
        "prompt_build_completed_at_utc": prompt_summary.get("completed_at_utc") if prompt_summary else None,
        "run_args_path": relpath(args_path) if args_path.exists() else None,
        "provenance_manifest_path": relpath(run_root / "provenance_manifest.json") if (run_root / "provenance_manifest.json").exists() else None,
        "per_question_path": relpath(pq_path) if pq_path.exists() else None,
        "aggregate_path": relpath(aggregate_path) if aggregate_path.exists() else None,
        "build_metrics_path": relpath(build_path) if build_path.exists() else None,
        "build_summary_path": relpath(build_summary_path) if build_summary_path.exists() else None,
        "prompt_build_summary_path": relpath(prompt_summary_path) if prompt_summary_path.exists() else None,
        "model_calls_path": relpath(calls_path) if calls_path.exists() else None,
    }
    row.update(summarize_calls(calls, calls_path.exists()))
    row.update(summarize_reader(pq, pq_path.exists()))
    row["memory_model_call_count"] = row.get("model_call_count")
    row["memory_model_failed_count"] = row.get("model_failed_count")
    row["memory_model_prompt_tokens_observed_total"] = row.get("model_prompt_tokens_observed_total")
    row["memory_model_completion_tokens_observed_total"] = row.get("model_completion_tokens_observed_total")
    for key in ("reader_controller_model", "reader_controller_base_url", "embedding_model", "embedding_base_url", "reader_temperature", "reader_top_p", "reader_top_k", "reader_enable_thinking", "reader_max_completion_tokens", "controller_max_completion_tokens", "memory_context_max_tokens", "reader_max_concurrent_requests", "prompt_build_max_workers"):
        row[key] = config.get(key, args.get(key))
    return row


def summarize_total(rows: list[dict[str, Any]], run_root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"domain": "total", "status": "complete" if all(r.get("status") == "complete" for r in rows) else "in_progress"}
    for key in rows[0]:
        if key in {"domain", "status"}:
            continue
        values = [r.get(key) for r in rows]
        if key.endswith(("_count", "_questions", "_tokens_total", "_tokens_observed_total", "_token_records", "_seconds_total")) or key in {"expected_questions", "scored_questions", "count_non_abstention", "count_abstention", "build_summary_elapsed_seconds"}:
            out[key] = total(values)
        elif key in {"official_overall_full_set", "adapted_overall_full_set", "adapted_overall_non_abstention_only", "adapted_overall_abstention_only"}:
            count_key = "count_non_abstention" if "non_abstention" in key else "count_abstention" if "abstention" in key else "count_all_questions"
            pairs = [(number(score), number(r.get(count_key))) for score, r in zip(values, rows)]
            if all(score is not None and count is not None for score, count in pairs) and pairs:
                out[key] = sum(float(score) * int(count) for score, count in pairs) / sum(int(count) for _, count in pairs)
            else:
                out[key] = None
        elif key in {"official_judge_status", "evaluator_scope", "evaluator_model", "quality_status"}:
            out[key] = ";".join(sorted({str(value) for value in values if value is not None})) or None
        elif key.endswith(("_avg", "_p95")):
            # A total-row mean/p95 cannot be recovered by averaging domain
            # summaries; leave it blank rather than implying a pooled statistic.
            out[key] = None
        elif key.endswith("_path"):
            out[key] = None
        elif len({str(value) for value in values if value is not None}) == 1:
            out[key] = next((value for value in values if value is not None), None)
        else:
            out[key] = None

    # Recompute pooled percentiles/means from raw per-record measurements;
    # averaging domain p95s would not be a valid overall p95.
    all_builds: list[dict[str, Any]] = []
    all_questions: list[dict[str, Any]] = []
    for domain in ("web", "enterprise"):
        folder = run_root / domain
        build_rows, _ = read_jsonl(folder / "memory_build_metrics.jsonl")
        question_rows, _ = read_jsonl(folder / "per_question.jsonl")
        all_builds.extend(build_rows)
        all_questions.extend(question_rows)
    out["build_elapsed_seconds_avg"] = mean(r.get("elapsed_seconds") for r in all_builds)
    out["build_elapsed_seconds_p95"] = p95(r.get("elapsed_seconds") for r in all_builds)
    out["reader_generation_seconds_avg"] = mean(r.get("reader_generation_duration_seconds") for r in all_questions)
    out["reader_generation_seconds_p95"] = p95(r.get("reader_generation_duration_seconds") for r in all_questions)
    out["memory_query_seconds_avg"] = mean(r.get("memory_query_duration_seconds") for r in all_questions)
    out["memory_query_seconds_p95"] = p95(r.get("memory_query_duration_seconds") for r in all_questions)

    expected_ids: set[str] = set()
    for domain in ("web", "enterprise"):
        haystack = read_json(run_root / domain / "runtime_inputs" / "haystack.json")
        if isinstance(haystack, dict):
            expected_ids.update(
                item for ids in haystack.values() if isinstance(ids, list)
                for item in ids if isinstance(item, str)
            )
    out["expected_unique_build_trajectories"] = len(expected_ids) if expected_ids else None
    return out


def csv_text(rows: list[dict[str, Any]]) -> str:
    preferred = ["domain", "status", "run_kind", "method", "tier", "upstream_commit", "quality_status", "official_judge_status", "evaluator_scope", "evaluator_model", "official_overall_full_set", "adapted_overall_full_set", "adapted_overall_non_abstention_only", "adapted_overall_abstention_only", "expected_questions", "scored_questions", "count_all_questions", "count_non_abstention", "count_abstention", "reader_failure_count", "expected_unique_build_trajectories", "build_metric_count", "build_summary_present", "build_summary_trajectory_count", "build_summary_status", "build_summary_elapsed_seconds", "build_success_count", "build_failed_count", "build_elapsed_seconds_total", "build_elapsed_seconds_avg", "build_elapsed_seconds_p95", "prompt_build_summary_present", "prompt_build_row_count", "prompt_build_completed_at_utc", "reader_generation_seconds_total", "reader_generation_seconds_avg", "reader_generation_seconds_p95", "memory_query_seconds_total", "memory_query_seconds_avg", "memory_query_seconds_p95", "memory_post_query_seconds_total", "memory_context_tokens_total", "memory_context_original_tokens_total", "model_call_count", "model_success_count", "model_failed_count", "model_runtime_error_count", "model_rate_limit_error_count", "model_other_error_count", "model_prompt_tokens_observed_total", "model_prompt_token_records", "model_completion_tokens_observed_total", "model_completion_token_records", "model_total_tokens_observed_total", "model_total_token_records", "controller_call_count", "controller_success_count", "controller_failed_count", "controller_elapsed_seconds_total", "controller_prompt_tokens_observed_total", "controller_prompt_token_records", "controller_completion_tokens_observed_total", "controller_completion_token_records", "embedding_call_count", "embedding_success_count", "embedding_failed_count", "embedding_elapsed_seconds_total", "embedding_prompt_tokens_observed_total", "embedding_prompt_token_records", "embedding_completion_tokens_observed_total", "embedding_completion_token_records", "async_runtime_error_fast_count", "per_question_malformed_lines", "build_malformed_lines", "calls_malformed_lines", "reader_controller_model", "embedding_model", "reader_temperature", "reader_top_p", "reader_top_k", "reader_enable_thinking", "reader_max_completion_tokens", "controller_max_completion_tokens", "reader_max_concurrent_requests", "prompt_build_max_workers", "run_args_path", "provenance_manifest_path", "per_question_path", "aggregate_path", "build_metrics_path", "build_summary_path", "prompt_build_summary_path", "model_calls_path"]
    extras = sorted({key for row in rows for key in row if key not in preferred})
    fields = [key for key in preferred if any(key in row for row in rows)] + extras
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def markdown(rows: list[dict[str, Any]], run_root: Path, manifest: dict[str, Any]) -> str:
    config = manifest.get("configuration") if isinstance(manifest.get("configuration"), dict) else {}
    lines = ["# AgentRunbook-R adapted Small summary", "", "Snapshot generated UTC: " + dt.datetime.now(dt.timezone.utc).isoformat(), "Run root: " + relpath(run_root), "", "This is a read-only snapshot; partial/in-progress runs are not treated as complete.", "Scores from qwen-plus are evaluator-only, not official LongMemEval Judge scores. Official score remains unavailable while judge status is pending_judge.", "", "## Domain and total metrics", "", "| domain | status | expected questions | scored answers | adapted full-set score | official score | judge/evaluator status |", "|---|---:|---:|---:|---:|---:|---|"]
    for row in rows:
        cells = [row.get("domain"), row.get("status"), row.get("expected_questions"), row.get("scored_questions"), row.get("adapted_overall_full_set"), row.get("official_overall_full_set"), row.get("quality_status")]
        lines.append("| " + " | ".join("—" if value is None else str(value) for value in cells) + " |")
    lines.extend(["", "## Configuration provenance", "", "- Run kind: " + str(manifest.get("run_kind")), "- Method / tier: " + str(manifest.get("method")) + " / " + str(manifest.get("tier")), "- Upstream commit: " + str(manifest.get("upstream_commit")), "- Reader/controller: " + str(config.get("reader_controller_model")) + "; thinking=" + str(config.get("reader_enable_thinking")) + "; output limit=" + str(config.get("reader_max_completion_tokens")), "- Embedding: " + str(config.get("embedding_model")), "- Evaluator: " + str(config.get("evaluator_model")) + " (" + str(config.get("evaluator_scope")) + "); official Judge=" + str(config.get("official_judge_status")), "", "## Build, query, and calls", "", "| domain | build wall / trajectory sum / p95 (s) | query sum / p95 (s) | build failures | calls (success/fail) | observed prompt tokens (records) | observed completion tokens (records) | controller s | embedding s | RuntimeError / RateLimitError / other |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in rows:
        cells = [row.get("domain"), f"{row.get('build_summary_elapsed_seconds', '—')} / {row.get('build_elapsed_seconds_total', '—')} / {row.get('build_elapsed_seconds_p95', '—')}", f"{row.get('memory_query_seconds_total', '—')} / {row.get('memory_query_seconds_p95', '—')}", row.get("build_failed_count"), f"{row.get('model_call_count', '—')} ({row.get('model_success_count', '—')}/{row.get('model_failed_count', '—')})", f"{row.get('model_prompt_tokens_observed_total', '—')} ({row.get('model_prompt_token_records', '—')})", f"{row.get('model_completion_tokens_observed_total', '—')} ({row.get('model_completion_token_records', '—')})", row.get("controller_elapsed_seconds_total"), row.get("embedding_elapsed_seconds_total"), f"{row.get('model_runtime_error_count', '—')} / {row.get('model_rate_limit_error_count', '—')} / {row.get('model_other_error_count', '—')}"]
        lines.append("| " + " | ".join("—" if value is None else str(value) for value in cells) + " |")
    lines.extend(["", "## Async error note", "", "The model-call log records RuntimeError and a null HTTP status for fast async_text failures, but it does not record the exception message. The observed pattern is therefore not by itself proof of a server error. Source inspection shows a single cached AsyncOpenAI client is reused while _run_async invokes asyncio.run for trajectory batches; cross-event-loop client/transport reuse is a high-probability lifecycle cause, to be confirmed only in a later isolated rerun.", "", "## Artifacts", ""])
    for row in rows:
        lines.append("- " + str(row.get("domain")) + ": per_question=" + str(row.get("per_question_path") or "missing") + "; aggregate=" + str(row.get("aggregate_path") or "missing") + "; build metrics=" + str(row.get("build_metrics_path") or "missing") + "; build summary=" + str(row.get("build_summary_path") or "missing") + "; prompt summary=" + str(row.get("prompt_build_summary_path") or "missing") + "; model_calls=" + str(row.get("model_calls_path") or "missing"))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True, help="adapted run root containing web/ and enterprise/")
    parser.add_argument("--out-table", type=Path, default=PROJECT_ROOT / "results/tables/agentrunbook_r_adapted_small.csv")
    parser.add_argument("--out-report", type=Path, default=PROJECT_ROOT / "reports/agentrunbook_r_adapted_small.md")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    manifest = read_json(run_root / "provenance_manifest.json")
    manifest = manifest if isinstance(manifest, dict) else {}
    rows = [summarize_domain(run_root, d, manifest) for d in ("web", "enterprise")]
    rows.append(summarize_total(rows, run_root))
    atomic_write(args.out_table.resolve(), csv_text(rows))
    atomic_write(args.out_report.resolve(), markdown(rows, run_root, manifest))
    print(json.dumps({"table": str(args.out_table.resolve()), "report": str(args.out_report.resolve()), "domain_status": {r["domain"]: r["status"] for r in rows}}, indent=2))


if __name__ == "__main__":
    main()
