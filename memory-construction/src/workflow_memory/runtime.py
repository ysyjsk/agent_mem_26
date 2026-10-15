"""P0 run planning, manifests, and resumable execution state.

The runner is intentionally backend-neutral.  It creates a complete,
content-addressed task plan before any model work.  A later implementation can
register a suite backend through workflow_memory.pipeline.run_suite without
changing the persistence or resume contract established here.
"""

from __future__ import annotations

import importlib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .config import ConfigError, content_hash, load_runtime, write_json
from .telemetry import JsonlLogger, new_run_id, utc_now


class RuntimeErrorBase(RuntimeError):
    """Base class for expected run lifecycle failures."""


class BackendUnavailable(RuntimeErrorBase):
    """Raised when a non-dry run has no registered execution backend."""


class ResumeMismatch(RuntimeErrorBase):
    """Raised when a run cannot be safely resumed under another config."""


@dataclass(frozen=True)
class RunPaths:
    root: Path
    manifest: Path
    task_plan: Path
    state: Path
    events: Path
    outputs: Path


def _paths(runtime: Mapping[str, Any], run_id: str) -> RunPaths:
    root = Path(str(runtime["paths"]["runs"])).expanduser().resolve() / run_id
    return RunPaths(
        root=root,
        manifest=root / "manifest.json",
        task_plan=root / "task_plan.json",
        state=root / "state.json",
        events=root / "events.jsonl",
        outputs=root / "outputs",
    )


def _suite_config(runtime: Mapping[str, Any], suite: str) -> dict[str, Any]:
    plan = runtime.get("plan", {})
    suites = plan.get("suites", {}) if isinstance(plan, Mapping) else {}
    if not isinstance(suites, Mapping) or suite not in suites:
        available = ", ".join(sorted(str(key) for key in suites)) if isinstance(suites, Mapping) else "none"
        raise ConfigError(f"unknown suite {suite!r}; available suites: {available}")
    raw = suites[suite]
    if not isinstance(raw, Mapping):
        raise ConfigError(f"suite {suite!r} must be a JSON object")
    return dict(raw)


def _as_list(value: Any, default: Sequence[str]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item) for item in value]
    return list(default)


def build_task_plan(runtime: Mapping[str, Any], *, suite: str, run_id: str) -> dict[str, Any]:
    """Construct a deterministic, explicit task list for one suite."""

    spec = _suite_config(runtime, suite)
    methods = _as_list(spec.get("methods"), ["default"])
    protocols = _as_list(spec.get("protocols"), ["A"])
    if suite == "correctness" and not spec.get("protocols"):
        protocols = ["C"]
    variants = _as_list(spec.get("variants"), ["full"])
    repeats = int(spec.get("performance_repeats", 1) or 1)
    repeats = max(1, repeats)
    target_trajectories = spec.get("target_trajectories")
    if target_trajectories is None:
        target_trajectories = runtime.get("plan", {}).get("data", {}).get("smoke_trajectory_target")
    tasks: list[dict[str, Any]] = []
    ordinal = 0
    for method in methods:
        method_variants = variants if suite == "ablations" else [None]
        for variant in method_variants:
            for protocol in protocols:
                for repeat in range(1, repeats + 1):
                    identity = {
                        "suite": suite,
                        "method": method,
                        "variant": variant,
                        "protocol": protocol,
                        "repeat": repeat,
                        "ordinal": ordinal,
                    }
                    task_id = f"task-{content_hash(identity)[:16]}"
                    tasks.append(
                        {
                            "task_id": task_id,
                            "ordinal": ordinal,
                            "suite": suite,
                            "method": method,
                            "variant": variant,
                            "protocol": protocol,
                            "repeat": repeat,
                            "target_trajectories": target_trajectories,
                            "status": "planned",
                            "requires_live_models": bool(spec.get("requires_live_models", False)),
                            "requires_frozen_config": bool(spec.get("requires_frozen_config", False)),
                            "output_dir": str(Path("outputs") / task_id),
                            "dependencies": [],
                        }
                    )
                    ordinal += 1
    plan = {
        "task_plan_schema_version": "workflow-memory-task-plan/1",
        "run_id": run_id,
        "suite": suite,
        "suite_spec": spec,
        "config_sha256": runtime.get("runtime_sha256"),
        "created_at": utc_now(),
        "status": "planned",
        "tasks": tasks,
        "estimates": {
            "task_count": len(tasks),
            "target_trajectories": target_trajectories,
            "model_calls": "pending_backend_estimate",
            "storage_bytes": "pending_backend_estimate",
        },
    }
    plan["task_plan_sha256"] = content_hash(plan)
    return plan


def _state_from_plan(runtime: Mapping[str, Any], task_plan: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "state_schema_version": "workflow-memory-run-state/1",
        "run_id": run_id,
        "suite": task_plan.get("suite"),
        "status": "planned",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "config_sha256": runtime.get("runtime_sha256"),
        "plan_sha256": runtime.get("plan_sha256"),
        "task_plan_sha256": task_plan.get("task_plan_sha256"),
        "tasks": [
            {"task_id": row["task_id"], "status": row.get("status", "planned"), "error": None}
            for row in task_plan.get("tasks", [])
        ],
        "backend": "not_selected",
        "failure": None,
    }


def _write_state(path: Path, state: dict[str, Any]) -> None:
    state = dict(state)
    state["updated_at"] = utc_now()
    write_json(path, state)
    # The workplan calls the externally visible lifecycle file status.json;
    # keep state.json as the richer resume ledger for backward compatibility.
    write_json(path.with_name("status.json"), {
        "run_id": state.get("run_id"),
        "suite": state.get("suite"),
        "status": state.get("status"),
        "updated_at": state.get("updated_at"),
        "failure": state.get("failure"),
    })


def create_run(runtime: Mapping[str, Any], *, suite: str, run_id: str | None = None) -> tuple[dict[str, Any], RunPaths]:
    selected_id = run_id or new_run_id(suite=suite, config_hash=str(runtime.get("runtime_sha256", "")))
    paths = _paths(runtime, selected_id)
    if paths.root.exists() and any(paths.root.iterdir()):
        raise RuntimeErrorBase(f"run directory already exists: {paths.root}")
    paths.outputs.mkdir(parents=True, exist_ok=True)
    task_plan = build_task_plan(runtime, suite=suite, run_id=selected_id)
    state = _state_from_plan(runtime, task_plan, selected_id)
    manifest = {
        "manifest_schema_version": "workflow-memory-run/1",
        "run_id": selected_id,
        "suite": suite,
        "created_at": utc_now(),
        "config_sha256": runtime.get("runtime_sha256"),
        "plan_sha256": runtime.get("plan_sha256"),
        "task_plan_sha256": task_plan.get("task_plan_sha256"),
        "runtime_path": runtime.get("runtime_path"),
        "status": "planned",
        "model_calls_allowed": False,
        "credentials_recorded": False,
    }
    write_json(paths.manifest, manifest)
    write_json(paths.task_plan, task_plan)
    _write_state(paths.state, state)
    # Create the complete run contract up front so an interrupted or blocked
    # run remains auditable rather than looking like a successful partial run.
    for filename in (
        "spans.jsonl",
        "llm_calls.jsonl",
        "dependencies.jsonl",
        "snapshots.jsonl",
        "qa_per_question.jsonl",
    ):
        (paths.root / filename).touch()
    write_json(paths.root / "correctness.json", {"status": "planned"})
    write_json(paths.root / "metrics.json", {"status": "planned"})
    (paths.root / "stderr.log").touch()
    with JsonlLogger(paths.events, run_id=selected_id, suite=suite) as logger:
        logger.event(
            "run.created",
            status="planned",
            task_count=len(task_plan.get("tasks", [])),
            config_sha256=runtime.get("runtime_sha256"),
        )
    return manifest, paths


def _load_run(paths: RunPaths) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        task_plan = json.loads(paths.task_plan.read_text(encoding="utf-8"))
        state = json.loads(paths.state.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ResumeMismatch(f"run is missing required manifest: {exc.filename}") from exc
    return manifest, task_plan, state


def find_latest_run(runtime: Mapping[str, Any], *, suite: str) -> str:
    root = Path(str(runtime["paths"]["runs"])).expanduser().resolve()
    candidates: list[tuple[float, str]] = []
    if root.is_dir():
        for child in root.iterdir():
            if not child.is_dir() or not (child / "manifest.json").is_file():
                continue
            try:
                manifest = json.loads((child / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("suite") == suite:
                candidates.append((child.stat().st_mtime, child.name))
    if not candidates:
        raise ResumeMismatch(f"no prior run found for suite {suite!r}")
    return max(candidates)[1]


def resume_run(runtime: Mapping[str, Any], *, suite: str, run_id: str | None = None) -> tuple[dict[str, Any], RunPaths]:
    selected_id = run_id or find_latest_run(runtime, suite=suite)
    paths = _paths(runtime, selected_id)
    manifest, task_plan, state = _load_run(paths)
    current_config = runtime.get("runtime_sha256")
    if manifest.get("config_sha256") != current_config or state.get("config_sha256") != current_config:
        raise ResumeMismatch(
            "runtime configuration differs from the run; regenerate only after explicitly starting a new run"
        )
    if task_plan.get("task_plan_sha256") != manifest.get("task_plan_sha256"):
        raise ResumeMismatch("task plan hash mismatch")
    candidate = dict(task_plan)
    expected = candidate.pop("task_plan_sha256", None)
    if expected != content_hash(candidate):
        raise ResumeMismatch("task plan content hash mismatch")
    if manifest.get("suite") != suite:
        raise ResumeMismatch(f"run belongs to suite {manifest.get('suite')!r}, not {suite!r}")
    # A completed task must retain its output directory and status marker.  A
    # missing marker means the node cache/output cannot be trusted for resume.
    for task in state.get("tasks", []):
        if task.get("status") != "completed":
            continue
        task_dir = paths.outputs / str(task.get("task_id"))
        marker = task_dir / "task_status.json"
        if not marker.is_file():
            raise ResumeMismatch(f"completed task {task.get('task_id')} is missing its output/cache marker")
    manifest["resumed_at"] = utc_now()
    manifest["status"] = state.get("status", "planned")
    write_json(paths.manifest, manifest)
    with JsonlLogger(paths.events, run_id=selected_id, suite=suite) as logger:
        logger.event("run.resumed", status=manifest["status"])
    return manifest, paths


def _discover_backend() -> Callable[..., Any] | None:
    """Find an optional suite backend without importing model clients eagerly."""

    candidates = (
        ("workflow_memory.pipeline", "run_suite"),
        ("workflow_memory.experiment", "run_suite"),
        ("workflow_memory.runner", "run_suite"),
    )
    for module_name, function_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        function = getattr(module, function_name, None)
        if callable(function):
            return function
    return None


def execute_run(runtime: Mapping[str, Any], *, suite: str, paths: RunPaths, resume: bool = False) -> dict[str, Any]:
    """Execute a registered backend or fail explicitly with a blocked run."""

    manifest, task_plan, state = _load_run(paths)
    backend = _discover_backend()
    if backend is None:
        state["status"] = "blocked"
        state["backend"] = "unavailable"
        state["failure"] = {
            "type": "BackendUnavailable",
            "message": "no workflow_memory suite backend is registered; use --dry-run for planning",
        }
        for task in state.get("tasks", []):
            if isinstance(task, dict) and task.get("status") in {"planned", "running"}:
                task["status"] = "blocked"
                task["error"] = state["failure"]["message"]
        _write_state(paths.state, state)
        manifest["status"] = "blocked"
        write_json(paths.manifest, manifest)
        with JsonlLogger(paths.events, run_id=paths.root.name, suite=suite) as logger:
            logger.event("run.blocked", reason=state["failure"]["message"])
        raise BackendUnavailable(state["failure"]["message"])

    state["status"] = "running"
    state["backend"] = f"{backend.__module__}.{backend.__name__}"
    _write_state(paths.state, state)
    with JsonlLogger(paths.events, run_id=paths.root.name, suite=suite) as logger:
        logger.event("run.started", backend=state["backend"], resume=resume)
    try:
        result = backend(runtime=runtime, suite=suite, task_plan=task_plan, paths=paths, resume=resume)
    except BaseException as exc:
        state["status"] = "blocked" if isinstance(exc, BackendUnavailable) else "failed"
        state["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        for task in state.get("tasks", []):
            if isinstance(task, dict) and task.get("status") in {"planned", "running"}:
                task["status"] = "blocked" if isinstance(exc, BackendUnavailable) else "failed"
                task["error"] = str(exc)
        _write_state(paths.state, state)
        manifest["status"] = state["status"]
        write_json(paths.manifest, manifest)
        with JsonlLogger(paths.events, run_id=paths.root.name, suite=suite) as logger:
            logger.event(
                "run.blocked" if isinstance(exc, BackendUnavailable) else "run.failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        raise
    state["status"] = "completed"
    state["result"] = result
    for task in state.get("tasks", []):
        task_id = str(task.get("task_id"))
        task_dir = paths.outputs / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        marker = {
            "task_id": task_id,
            "status": "completed",
            "result_hash": content_hash(result),
            "config_sha256": runtime.get("runtime_sha256"),
            "updated_at": utc_now(),
        }
        write_json(task_dir / "task_status.json", marker)
        task["status"] = "completed"
        task["output_fingerprint"] = marker["result_hash"]
    for task in state.get("tasks", []):
        if isinstance(task, dict) and task.get("status") in {"planned", "running"}:
            task["status"] = "completed"
            task["error"] = None
    _write_state(paths.state, state)
    manifest["status"] = "completed"
    write_json(paths.manifest, manifest)
    with JsonlLogger(paths.events, run_id=paths.root.name, suite=suite) as logger:
        logger.event("run.completed")
    return manifest


def prepare_data(runtime: Mapping[str, Any]) -> Path:
    """Prepare locally supplied JSON/JSONL trajectories without downloading.

    A missing source remains explicitly blocked.  When a caller supplies a
    local export, this stage records counts and hashes but does not expose
    future labels to the construction code.
    """

    root = Path(str(runtime["paths"]["data"])).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "PREPARE_DATA_PENDING.json"
    candidates = [path for path in sorted(root.glob("*.json")) + sorted(root.glob("*.jsonl")) if path.name != marker.name]
    if not candidates:
        write_json(
            marker,
            {
                "status": "blocked",
                "reason": "no local JSON/JSONL trajectory export was supplied; downloading is intentionally not implicit",
                "config_sha256": runtime.get("runtime_sha256"),
                "created_at": utc_now(),
            },
        )
        raise BackendUnavailable("dataset preparation is blocked: supply a local LongMemEval-V2 JSON/JSONL export")
    from .adapters.longmemeval_v2 import LongMemEvalV2Adapter
    from .config import content_hash

    records = []
    event_count = 0
    source_rows = []
    for path in candidates:
        adapter = LongMemEvalV2Adapter(path)
        file_records = adapter.records()
        records.extend(file_records)
        local_events = sum(len(adapter.normalize(record)) for record in file_records)
        event_count += local_events
        source_rows.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "records": len(file_records), "events": local_events})
    manifests = Path(str(runtime["paths"]["manifests"])).expanduser().resolve()
    reports = Path(str(runtime["paths"]["reports"])).expanduser().resolve()
    manifests.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    data_manifest = {
        "manifest_schema_version": "workflow-memory-data/1",
        "status": "prepared",
        "root": str(root),
        "sources": source_rows,
        "record_count": len(records),
        "event_count": event_count,
        "prefix_information_only": True,
        "outcome_available_at": runtime.get("plan", {}).get("data", {}).get("outcome_available_at"),
        "config_sha256": runtime.get("runtime_sha256"),
    }
    write_json(manifests / "data.json", data_manifest)
    write_json(manifests / "splits.json", {"manifest_schema_version": "workflow-memory-splits/1", "status": "prepared", "seed": runtime.get("plan", {}).get("data", {}).get("split_seed"), "records": len(records)})
    (reports / "data_audit.md").write_text(
        "# Data audit\n\n"
        f"Prepared {len(records)} trajectory records and {event_count} normalized source events from local exports.\n\n"
        "The audit preserves source hashes and keeps benchmark labels out of prefix construction.\n",
        encoding="utf-8",
    )
    marker.unlink(missing_ok=True)
    return root


def dry_run(runtime: Mapping[str, Any], *, suite: str, run_id: str | None = None) -> tuple[dict[str, Any], RunPaths]:
    """Create a planned run without invoking any model or external backend."""

    return create_run(runtime, suite=suite, run_id=run_id)
