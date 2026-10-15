#!/usr/bin/env python3
"""Re-score an existing development Reader run without making model calls.

This is deliberately narrower than :mod:`run_dev_reader`: it only reads a
completed run's ``qa_per_question.jsonl`` and applies the current
``run_dev_reader.score_answer`` implementation.  The source run is never
opened for writing, and all latency/token fields in the output are copied from
the source rows for auditability rather than counted as a new experiment.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT / "src"))
sys.path.insert(0, str(CODE_ROOT / "tools"))

from run_dev_reader import (  # noqa: E402  (the script is also an importable narrow API)
    score_answer,
    summarize,
    summarize_by_quality_type,
)
from run_fast_compare import file_hash, now, write_table  # noqa: E402
from workflow_memory.config import write_json  # noqa: E402


ALLOWED_SOURCE_STATUSES = {"completed", "completed_with_failures"}
OUTPUT_FILES = (
    "qa_per_question.jsonl",
    "dev_quality.csv",
    "dev_quality_by_type.csv",
    "dev_quality_by_category.csv",
    "metrics.json",
    "manifest.json",
    "status.json",
)


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"Reader output is missing: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Reader row at {path}:{line_number} is not an object")
            rows.append(dict(value))
    if not rows:
        raise ValueError(f"Reader output has no rows: {path}")
    return rows


def _load_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def _same_score(left: Any, right: Any) -> bool:
    """Compare score values without treating bool and numeric values as equal."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float) and isinstance(right, float):
        return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
    return left == right


def _rescore_row(row: Mapping[str, Any], *, source_run: Path, source_qa: Path,
                 source_row_index: int, scorer_sha256: str) -> dict[str, Any]:
    old_exact = row.get("proxy_exact")
    old_f1 = row.get("proxy_token_f1")
    old_unknown = row.get("unknown")
    # A completed_with_failures Reader run can contain failed rows without an
    # answer.  Keep those source failures in the denominator and preserve
    # their original score fields; only rows with a real answer are rescored.
    missing_answer = "answer" not in row
    missing_reference = not isinstance(row.get("reference"), Mapping)
    if missing_answer or missing_reference:
        if str(row.get("status", "")) == "completed":
            missing = "answer" if missing_answer else "evaluator reference object"
            raise ValueError(f"completed Reader row {source_row_index} has no {missing}")
        rescored = {"proxy_exact": old_exact, "proxy_token_f1": old_f1, "unknown": old_unknown}
        changed_fields: list[str] = []
        correction_reason = "not_scored_source_failure"
    else:
        rescored = score_answer(row["answer"], row)
        changed_fields = [
            name for name, old, new in (
                ("proxy_exact", old_exact, rescored.get("proxy_exact")),
                ("proxy_token_f1", old_f1, rescored.get("proxy_token_f1")),
                ("unknown", old_unknown, rescored.get("unknown")),
            )
            if not _same_score(old, new)
        ]
        correction_reason = "run_dev_reader.score_answer"

    # Copy the entire source row first.  This preserves the real answer,
    # retrieval evidence, timing, token usage, and all source provenance.
    output = dict(row)
    output.update({
        "old_proxy_exact": old_exact,
        "old_proxy_token_f1": old_f1,
        "old_unknown": old_unknown,
        "proxy_exact": rescored.get("proxy_exact"),
        "proxy_token_f1": rescored.get("proxy_token_f1"),
        "unknown": rescored.get("unknown"),
        "score_correction": bool(changed_fields),
        "score_correction_status": "changed" if changed_fields else "unchanged",
        "score_correction_fields": changed_fields,
        "score_correction_reason": correction_reason,
        "rescore_scorer_sha256": scorer_sha256,
        "source_run": str(source_run),
        "source_run_path": str(source_run),
        "source_qa_per_question": str(source_qa),
        "source_qa_per_question_path": str(source_qa),
        "source_row_index": source_row_index,
        "evaluator_only": True,
        "no_new_model_calls": True,
        "latency_tokens_reused": True,
        "not_a_new_experiment": True,
    })
    if "proxy_score_status" in rescored:
        output["proxy_score_status"] = rescored["proxy_score_status"]
    else:
        # Do not leave an old unavailable-reference marker beside a newly
        # computed ordinary score.
        output.pop("proxy_score_status", None)
    return output


def _annotate_summary(rows: Sequence[Mapping[str, Any]], source_run: Path,
                     source_qa: Path) -> list[dict[str, Any]]:
    summaries = summarize(rows, Path("qa_per_question.jsonl"))
    for summary in summaries:
        summary.update({
            "source_run": str(source_run),
            "source_run_path": str(source_run),
            "source_qa_per_question": str(source_qa),
            "evaluator_only": True,
            "no_new_model_calls": True,
            "latency_tokens_reused": True,
            "not_a_new_experiment": True,
        })
    return summaries


def _annotate_type_summary(rows: Sequence[Mapping[str, Any]], source_run: Path,
                           source_qa: Path) -> list[dict[str, Any]]:
    summaries = summarize_by_quality_type(rows, Path("qa_per_question.jsonl"))
    for summary in summaries:
        summary.update({
            "source_run": str(source_run),
            "source_run_path": str(source_run),
            "source_qa_per_question": str(source_qa),
            "evaluator_only": True,
            "no_new_model_calls": True,
            "latency_tokens_reused": True,
            "not_a_new_experiment": True,
        })
    return summaries


def rescore_run(source_run: Path, out: Path) -> dict[str, Any]:
    """Rescore ``source_run`` into a new directory and return its manifest."""
    source_run = source_run.expanduser().resolve()
    out = out.expanduser().resolve()
    if source_run == out:
        raise ValueError("refuse to overwrite the source Reader run")
    if not source_run.is_dir():
        raise ValueError(f"source Reader run is not a directory: {source_run}")
    if out.exists():
        raise ValueError(f"refuse to overwrite an existing output directory: {out}")

    source_status_path = source_run / "status.json"
    source_manifest_path = source_run / "manifest.json"
    source_status = _load_object(source_status_path, "source status")
    source_manifest = _load_object(source_manifest_path, "source manifest")
    source_status_value = str(source_status.get("status", ""))
    if source_status_value not in ALLOWED_SOURCE_STATUSES:
        raise ValueError(f"source Reader run is not completed: {source_run} ({source_status_value or 'missing status'})")
    source_qa = source_run / "qa_per_question.jsonl"
    source_rows = _jsonl_rows(source_qa)
    scorer_path = CODE_ROOT / "tools" / "run_dev_reader.py"
    scorer_sha256 = file_hash(scorer_path)
    rescored_rows = [
        _rescore_row(row, source_run=source_run, source_qa=source_qa,
                     source_row_index=index, scorer_sha256=scorer_sha256)
        for index, row in enumerate(source_rows)
    ]
    summaries = _annotate_summary(rescored_rows, source_run, source_qa)
    summaries_by_type = _annotate_type_summary(rescored_rows, source_run, source_qa)
    categories: list[dict[str, Any]] = []
    for category in dict.fromkeys(str(row.get("category", "unknown")) for row in rescored_rows):
        category_rows = [row for row in rescored_rows if str(row.get("category", "unknown")) == category]
        for summary in _annotate_summary(category_rows, source_run, source_qa):
            categories.append({"category": category, **summary})

    changed_rows = sum(bool(row["score_correction"]) for row in rescored_rows)
    source_qa_sha256 = file_hash(source_qa)
    source_manifest_sha256 = file_hash(source_manifest_path)
    source_status_sha256 = file_hash(source_status_path)
    manifest = {
        "schema_version": "development-reader-rescore/1",
        "status": "completed",
        "started_at": now(),
        "completed_at": now(),
        "evaluator_only": True,
        "no_new_model_calls": True,
        "new_model_calls": 0,
        "new_embedding_calls": 0,
        "not_a_new_experiment": True,
        "score_function": "tools/run_dev_reader.py:score_answer",
        "score_function_sha256": scorer_sha256,
        "source_run": str(source_run),
        "source_run_path": str(source_run),
        "source_status": source_status_value,
        "source_status_sha256": source_status_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "source_manifest_schema_version": source_manifest.get("schema_version"),
        "source_qa_per_question": str(source_qa),
        "source_qa_per_question_sha256": source_qa_sha256,
        "source_rows": len(source_rows),
        "rescored_rows": len(rescored_rows),
        "score_corrections": changed_rows,
        "latency_tokens_policy": "copy source row usage and latency; not counted as a new experiment",
        "source_metrics_reused": [
            "reader_calls", "input_tokens", "output_tokens", "elapsed_s", "reader_s",
            "retrieval_s", "wall_s",
        ],
        "output_files": list(OUTPUT_FILES),
    }

    # Create only after all source validation and scoring has succeeded.  A
    # pre-existing destination is rejected above, so no existing run can be
    # silently replaced.
    out.mkdir(parents=True, exist_ok=False)
    qa_out = out / "qa_per_question.jsonl"
    with qa_out.open("x", encoding="utf-8") as handle:
        for row in rescored_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    # Summaries intentionally point at the new QA file while retaining the
    # absolute source-run link and copied accounting policy in every row.
    for table_rows in (summaries, summaries_by_type, categories):
        for row in table_rows:
            row["raw_metrics_path"] = str(qa_out)
    write_table(out / "dev_quality.csv", summaries)
    write_table(out / "dev_quality_by_type.csv", summaries_by_type)
    write_table(out / "dev_quality_by_category.csv", categories)
    manifest["output_qa_per_question_sha256"] = file_hash(qa_out)
    manifest["summary_files"] = {
        "dev_quality": str(out / "dev_quality.csv"),
        "dev_quality_by_type": str(out / "dev_quality_by_type.csv"),
        "dev_quality_by_category": str(out / "dev_quality_by_category.csv"),
    }
    metrics = {
        "status": "completed",
        "evaluator_only": True,
        "no_new_model_calls": True,
        "new_model_calls": 0,
        "not_a_new_experiment": True,
        "source_run": str(source_run),
        "source_qa_per_question": str(source_qa),
        "source_rows": len(source_rows),
        "rescored_rows": len(rescored_rows),
        "score_corrections": changed_rows,
        "summaries": summaries,
        "summaries_by_quality_type": summaries_by_type,
        "summaries_by_category": categories,
        "latency_tokens_reused": True,
    }
    write_json(out / "metrics.json", metrics)
    write_json(out / "manifest.json", manifest)
    write_json(out / "status.json", {
        "status": "completed",
        "updated_at": manifest["completed_at"],
        "evaluator_only": True,
        "no_new_model_calls": True,
        "new_model_calls": 0,
        "not_a_new_experiment": True,
        "source_run": str(source_run),
        "score_corrections": changed_rows,
    })
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", dest="source_run", required=True, type=Path,
                        help="completed Reader run containing qa_per_question.jsonl")
    parser.add_argument("--out", required=True, type=Path,
                        help="new output directory; an existing directory is rejected")
    args = parser.parse_args()
    manifest = rescore_run(args.source_run, args.out)
    print(json.dumps({
        "status": manifest["status"],
        "source_run": manifest["source_run"],
        "out": str(args.out.expanduser().resolve()),
        "rescored_rows": manifest["rescored_rows"],
        "score_corrections": manifest["score_corrections"],
        "evaluator_only": manifest["evaluator_only"],
        "no_new_model_calls": manifest["no_new_model_calls"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
