"""Evidence-preserving aggregation and reproduction checks for run artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "workflow-memory-paired/1"

def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if isinstance(item, dict): rows.append(item)
            except json.JSONDecodeError: continue
    except OSError: pass
    return rows

def evidence_class(metrics: dict[str, Any], manifest: dict[str, Any]) -> str:
    if metrics.get("replay_for_paired_methods") is True or metrics.get("backend") == "deterministic_replay": return "replay"
    if metrics.get("protocol") == "C" or metrics.get("suite") == "correctness": return "offline"
    if metrics.get("text_only") is True or metrics.get("official_harness") or manifest.get("official_harness"): return "text_only"
    method = str(metrics.get("method", manifest.get("method", ""))).lower()
    if method in {"memforest", "agentrunbook_r", "codex_native"}: return "native"
    if metrics.get("backend") == "transformers_local" and metrics.get("live_model_calls", 0): return "live_internal"
    return "missing"

def paired_row(run_dir: Path) -> dict[str, Any]:
    metrics = _read_json(run_dir / "metrics.json")
    manifest = _read_json(run_dir / "manifest.json")
    calls, spans, events, snapshots = (_jsonl(run_dir / name) for name in ("llm_calls.jsonl", "spans.jsonl", "events.jsonl", "snapshots.jsonl"))
    usage_in = sum(int((x.get("usage") or {}).get("prompt_tokens", 0) or 0) for x in calls)
    usage_out = sum(int((x.get("usage") or {}).get("completion_tokens", 0) or 0) for x in calls)
    row = {"schema_version": SCHEMA_VERSION, "run_id": run_dir.name, "method": metrics.get("method", manifest.get("method", "unknown")), "suite": metrics.get("suite", manifest.get("suite", "unknown")), "status": metrics.get("status", _read_json(run_dir / "status.json").get("status", "missing")), "evidence_class": evidence_class(metrics, manifest), "official": bool(metrics.get("official") or manifest.get("official_harness")), "live_calls": len(calls) if (run_dir / "llm_calls.jsonl").is_file() else metrics.get("live_model_calls"), "input_tokens": usage_in if calls else metrics.get("live_model_input_tokens"), "output_tokens": usage_out if calls else metrics.get("live_model_output_tokens"), "call_elapsed_ns": sum(int(x.get("elapsed_ns", 0) or 0) for x in calls), "span_elapsed_ns": sum(int(x.get("elapsed_ns", 0) or 0) for x in spans), "events_logged": len(events), "snapshots_logged": len(snapshots), "metrics_elapsed_ns": metrics.get("elapsed_ns"), "metrics_path": str(run_dir / "metrics.json")}
    return row

def aggregate_runs(runs_root: Path) -> list[dict[str, Any]]:
    return [paired_row(path) for path in sorted(runs_root.glob("*/")) if (path / "metrics.json").is_file()]

def reproduce_run(run_dir: Path) -> dict[str, Any]:
    row = paired_row(run_dir)
    metrics = _read_json(run_dir / "metrics.json")
    checks = {"metrics_exists": (run_dir / "metrics.json").is_file(), "status_consistent": not _read_json(run_dir / "status.json") or _read_json(run_dir / "status.json").get("status") == metrics.get("status")}
    if (run_dir / "llm_calls.jsonl").is_file():
        checks["calls_match"] = row["live_calls"] == metrics.get("live_model_calls") and row["input_tokens"] == metrics.get("live_model_input_tokens") and row["output_tokens"] == metrics.get("live_model_output_tokens")
    else: checks["calls_match"] = None
    if (run_dir / "snapshots.jsonl").is_file(): checks["snapshots_logged"] = row["snapshots_logged"] > 0
    else: checks["snapshots_logged"] = None
    return {"schema_version": SCHEMA_VERSION, "run_id": run_dir.name, "status": "verified" if all(v is not False for v in checks.values()) else "mismatch", "checks": checks, "recomputed": row}

