"""Command-line entry point for the workflow-memory execution package."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .config import ConfigError, load_runtime
from .doctor import run_doctor
from .runtime import (
    BackendUnavailable,
    ResumeMismatch,
    create_run,
    dry_run,
    execute_run,
    prepare_data,
    resume_run,
)
from .config import content_hash, write_json

CLI_VERSION = "workflow-memory-p0/1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workflow_memory",
        description="Workflow-aware concurrent and incremental memory construction",
    )
    parser.add_argument("--version", action="version", version=CLI_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="discover local resources and create runtime config")
    doctor.add_argument("--plan", required=True, type=Path, help="workplan JSON")
    doctor.add_argument("--out", required=True, type=Path, help="runtime JSON output")
    doctor.add_argument("--code-root", type=Path, help="code root (defaults to memory-construction)")

    prepare = commands.add_parser("prepare-data", help="prepare and audit benchmark data")
    prepare.add_argument("--config", required=True, type=Path)

    run = commands.add_parser("run", help="create or execute a suite run")
    run.add_argument("--suite", required=True)
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--resume", action="store_true", help="resume the latest compatible run")
    run.add_argument("--run-id", help="resume or create a specific run id")
    run.add_argument("--dry-run", action="store_true", help="plan only; never invoke a backend")

    check = commands.add_parser("check", help="run correctness or contract checks")
    check.add_argument("--suite", required=True)
    check.add_argument("--config", required=True, type=Path)
    check.add_argument("--run-id")

    tune = commands.add_parser("tune", help="run development tuning")
    tune.add_argument("--config", required=True, type=Path)

    freeze = commands.add_parser("freeze", help="freeze a formal runtime configuration")
    freeze.add_argument("--config", required=True, type=Path)
    freeze.add_argument("--out", required=True, type=Path)

    report = commands.add_parser("report", help="generate tables and figures from runs")
    report.add_argument("--runs", required=True, type=Path)
    report.add_argument("--out", required=True, type=Path)

    reproduce = commands.add_parser("reproduce", help="replay a result manifest")
    reproduce.add_argument("--manifest", required=True, type=Path)
    return parser


def _json_line(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _run(args: argparse.Namespace) -> int:
    runtime, config_path = load_runtime(args.config)
    if args.resume:
        manifest, paths = resume_run(runtime, suite=args.suite, run_id=args.run_id)
        if args.dry_run:
            _json_line(
                {
                    "status": manifest.get("status", "planned"),
                    "run_id": manifest.get("run_id"),
                    "run_dir": str(paths.root),
                    "task_plan": str(paths.task_plan),
                    "events": str(paths.events),
                    "config": str(config_path),
                }
            )
            return 0
        try:
            final = execute_run(runtime, suite=args.suite, paths=paths, resume=True)
        except BackendUnavailable as exc:
            _json_line(
                {
                    "status": "blocked",
                    "run_id": manifest.get("run_id"),
                    "run_dir": str(paths.root),
                    "events": str(paths.events),
                    "error": str(exc),
                }
            )
            return 2
        _json_line({"status": final.get("status"), "run_id": final.get("run_id"), "run_dir": str(paths.root), "events": str(paths.events)})
        return 0

    manifest, paths = dry_run(runtime, suite=args.suite, run_id=args.run_id)
    if args.dry_run:
        _json_line(
            {
                "status": "planned",
                "run_id": manifest.get("run_id"),
                "run_dir": str(paths.root),
                "task_plan": str(paths.task_plan),
                "events": str(paths.events),
                "config": str(config_path),
                "task_count": len(json.loads(paths.task_plan.read_text(encoding="utf-8")).get("tasks", [])),
            }
        )
        return 0
    try:
        final = execute_run(runtime, suite=args.suite, paths=paths)
    except BackendUnavailable as exc:
        _json_line(
            {
                "status": "blocked",
                "run_id": manifest.get("run_id"),
                "run_dir": str(paths.root),
                "events": str(paths.events),
                "error": str(exc),
            }
        )
        return 2
    _json_line({"status": final.get("status"), "run_id": final.get("run_id"), "run_dir": str(paths.root), "events": str(paths.events)})
    return 0


def _not_implemented(command: str) -> int:
    print(
        f"{command}: stage backend is not implemented yet; command is intentionally non-successful",
        file=sys.stderr,
    )
    return 2


def _check(args: argparse.Namespace) -> int:
    if args.suite != "correctness":
        return _not_implemented(f"check --suite {args.suite}")
    runtime, config_path = load_runtime(args.config)
    manifest, paths = dry_run(runtime, suite="correctness", run_id=args.run_id)
    try:
        final = execute_run(runtime, suite="correctness", paths=paths)
    except Exception as exc:
        _json_line({"status": "failed", "run_id": manifest.get("run_id"), "error": str(exc), "run_dir": str(paths.root)})
        return 2
    _json_line({"status": final.get("status"), "run_id": final.get("run_id"), "run_dir": str(paths.root), "correctness": str(paths.root / "correctness.json")})
    return 0


def _freeze(args: argparse.Namespace) -> int:
    runtime, _ = load_runtime(args.config)
    discovery = runtime.get("discovery", {})
    endpoints = discovery.get("model_endpoints", []) if isinstance(discovery, dict) else []
    missing = [row.get("role", "unknown") for row in endpoints if isinstance(row, dict) and not row.get("base_url_configured")]
    data_manifest = Path(runtime.get("paths", {}).get("manifests", "manifests")) / "data.json"
    data_pending = True
    if data_manifest.is_file():
        try:
            data_pending = json.loads(data_manifest.read_text(encoding="utf-8")).get("status") != "prepared"
        except (OSError, json.JSONDecodeError):
            data_pending = True
    if missing or data_pending:
        print("freeze: blocked; unresolved model endpoints/data manifest", file=sys.stderr)
        _json_line({"status": "blocked", "missing_model_roles": missing, "data_manifest_pending": data_pending})
        return 2
    frozen = dict(runtime)
    frozen["freeze_schema_version"] = "workflow-memory-frozen/1"
    frozen["frozen_config_sha256"] = content_hash(frozen)
    write_json(args.out, frozen)
    _json_line({"status": "frozen", "out": str(Path(args.out).expanduser().resolve()), "sha256": frozen["frozen_config_sha256"]})
    return 0


def _report(args: argparse.Namespace) -> int:
    runs_root = Path(args.runs).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if runs_root.is_dir():
        for metrics_path in runs_root.glob("*/metrics.json"):
            try:
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            metrics["run_id"] = metrics_path.parent.name
            if metrics.get("status") in {"completed", "failed", "blocked"}:
                rows.append(metrics)
    # Keep protocol families separate.  In particular, deterministic fixture
    # correctness metrics must never be copied into QA/native/mechanism tables
    # where they could be mistaken for benchmark results.
    def _suite(row: Mapping[str, Any]) -> str:
        return str(row.get("suite", ""))

    def _protocol(row: Mapping[str, Any]) -> str:
        return str(row.get("protocol", ""))

    def _write_table(name: str, table_rows: list[dict[str, Any]], *, reason: str | None = None) -> None:
        prepared = [dict(row) for row in table_rows]
        if reason and not prepared:
            prepared = [{"status": "blocked", "reason": reason}]
        fieldnames = sorted({key for row in prepared for key in row}) or ["status", "reason"]
        with (tables / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(prepared)

    correctness_rows = [row for row in rows if _protocol(row) == "C" or _suite(row) == "correctness"]
    live_rows = [row for row in rows if row.get("backend") == "transformers_local" and _protocol(row) == "B"]
    ablation_rows = [row for row in live_rows if _suite(row) == "ablations"]
    internal_rows = [row for row in live_rows if _suite(row) != "ablations"]
    _write_table("correctness_recovery", correctness_rows)
    _write_table("main_internal", internal_rows)
    _write_table("ablations", ablation_rows)
    _write_table("mechanisms", live_rows)
    _write_table(
        "native_systems",
        [row for row in rows if str(row.get("method", "")).lower() in {"memforest", "agentrunbook_r", "codex_native"}],
        reason="No external native baseline run manifest was completed in this workspace.",
    )
    _write_table(
        "official_qa",
        [row for row in rows if bool(row.get("official_question")) or _suite(row) == "official_qa"],
        reason="Official LongMemEval QA is not populated by the local goal-smoke/internal runs.",
    )
    report = out / "final_research_report.md"
    report.write_text(
        "# Workflow Memory report\n\n"
        "This report is generated from run manifests and raw metrics. "
        "It contains no fabricated live-model or benchmark results.\n\n"
        f"Runs discovered: {len(rows)}\n\n"
        f"Correctness/recovery rows: {len(correctness_rows)}\n"
        f"Local internal rows: {len(internal_rows)}\n"
        f"Ablation rows: {len(ablation_rows)}\n"
        "External native and official QA tables contain explicit blocked/NA rows "
        "until their native runner and official question/evaluator path are executed.\n",
        encoding="utf-8",
    )
    reproduce = {"schema_version": "workflow-memory-reproduce/1", "runs_root": str(runs_root), "metrics": [str(path) for path in runs_root.glob("*/metrics.json")] if runs_root.is_dir() else []}
    write_json(out / "reproduce_manifest.json", reproduce)
    _json_line({"status": "completed", "runs": len(rows), "out": str(out), "report": str(report)})
    return 0


def _reproduce(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).expanduser().resolve()
    if not manifest_path.is_file():
        print(f"reproduce: manifest does not exist: {manifest_path}", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"reproduce: invalid manifest: {exc}", file=sys.stderr)
        return 2
    metrics = manifest.get("metrics", []) if isinstance(manifest, dict) else []
    missing = [path for path in metrics if not Path(path).is_file()]
    if missing:
        _json_line({"status": "blocked", "missing": missing})
        return 2
    _json_line({"status": "verified", "manifest": str(manifest_path), "metrics": len(metrics)})
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            runtime = run_doctor(plan_path=args.plan, out_path=args.out, code_root=args.code_root)
            _json_line(
                {
                    "status": "ready",
                    "runtime": str(Path(args.out).expanduser().resolve()),
                    "plan_sha256": runtime.get("plan_sha256"),
                    "runtime_sha256": runtime.get("runtime_sha256"),
                    "environment_report": str(Path(runtime["paths"]["reports"]) / "environment.md"),
                }
            )
            return 0
        if args.command == "prepare-data":
            runtime, _ = load_runtime(args.config)
            prepare_data(runtime)
            return 0
        if args.command == "run":
            return _run(args)
        if args.command == "check":
            return _check(args)
        if args.command == "tune":
            return _not_implemented("tune")
        if args.command == "freeze":
            return _freeze(args)
        if args.command == "report":
            return _report(args)
        if args.command == "reproduce":
            return _reproduce(args)
        raise AssertionError(f"unhandled command: {args.command}")
    except (ConfigError, ResumeMismatch, BackendUnavailable) as exc:
        print(f"workflow_memory: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("workflow_memory: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
