"""P0 environment discovery and runtime bootstrap."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .config import (
    build_runtime_config,
    content_hash,
    load_plan,
    model_endpoint_inventory,
    write_json,
)


def _command(*args: str, timeout: float = 4.0) -> dict[str, Any]:
    """Run a discovery command without raising or leaking its environment."""

    try:
        completed = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={"PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "error": type(exc).__name__}
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    return {
        "available": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": stdout[:4000],
        "stderr": stderr[:1000],
    }


def _git_discovery(path: Path) -> dict[str, Any]:
    root = _command("git", "-C", str(path), "rev-parse", "--show-toplevel")
    if not root.get("available"):
        return {"available": False, "path": str(path)}
    git_root = Path(str(root["stdout"])).resolve()
    head = _command("git", "-C", str(git_root), "rev-parse", "HEAD")
    status = _command(
        "git",
        "-C",
        str(git_root),
        "status",
        "--porcelain",
        "--untracked-files=normal",
    )
    status_text = status.get("stdout", "")
    return {
        "available": True,
        "root": str(git_root),
        "head": head.get("stdout") if head.get("available") else None,
        "dirty": bool(status_text),
        "untracked": any(line.startswith("??") for line in status_text.splitlines()),
        "tracked_patch_status": status_text[:4000],
    }


def _torch_discovery() -> dict[str, Any]:
    try:
        import torch  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local install
        return {"importable": False, "error": type(exc).__name__}
    rows: list[dict[str, Any]] = []
    try:
        count = int(torch.cuda.device_count())
        for index in range(count):
            props = torch.cuda.get_device_properties(index)
            rows.append(
                {
                    "index": index,
                    "name": str(props.name),
                    "total_memory_bytes": int(props.total_memory),
                    "capability": f"{props.major}.{props.minor}",
                }
            )
    except Exception as exc:  # pragma: no cover - hardware dependent
        return {"importable": True, "cuda_available": False, "error": type(exc).__name__}
    return {
        "importable": True,
        "version": getattr(torch, "__version__", None),
        "cuda_available": bool(torch.cuda.is_available()),
        "device_count": len(rows),
        "devices": rows,
    }


def discover_environment(*, plan: Mapping[str, Any], code_root: Path) -> dict[str, Any]:
    """Collect reproducibility-relevant local capabilities, never secrets."""

    usage = shutil.disk_usage(code_root)
    package_names = {
        "torch": "torch",
        "vllm": "vllm",
        "openai": "openai",
        "datasets": "datasets",
        "pillow": "PIL",
    }
    packages = {
        label: {"importable": importlib.util.find_spec(module) is not None}
        for label, module in package_names.items()
    }
    return {
        "discovered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "code_root": str(code_root),
        "git": _git_discovery(code_root),
        "disk": {
            "total_bytes": int(usage.total),
            "free_bytes": int(usage.free),
            "used_bytes": int(usage.used),
        },
        "gpu": {
            "nvidia_smi": _command(
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ),
            "torch": _torch_discovery(),
        },
        "packages": packages,
        "model_endpoints": model_endpoint_inventory(plan),
        "credentials_recorded": False,
    }


def _markdown_environment(discovery: Mapping[str, Any], *, plan_path: Path, plan_hash: str) -> str:
    lines = [
        "# Environment discovery",
        "",
        "This report records capability presence and versions only; endpoint values and credentials are intentionally omitted.",
        "",
        f"- Plan: `{plan_path}`",
        f"- Plan SHA-256: `{plan_hash}`",
        f"- Discovered at: `{discovery.get('discovered_at', 'unknown')}`",
        f"- Host: `{discovery.get('hostname', 'unknown')}`",
        f"- Platform: `{discovery.get('platform', 'unknown')}`",
        f"- Python: `{discovery.get('python', {}).get('version', 'unknown')}` ({discovery.get('python', {}).get('implementation', 'unknown')})",
        "",
        "## Runtime capabilities",
        "",
        "| Capability | Finding |",
        "|---|---|",
    ]
    packages = discovery.get("packages", {})
    for name, row in packages.items():
        lines.append(f"| package `{name}` | {'available' if row.get('importable') else 'missing'} |")
    gpu = discovery.get("gpu", {})
    nvidia = gpu.get("nvidia_smi", {})
    lines.append(f"| `nvidia-smi` | {'available' if nvidia.get('available') else 'missing'} |")
    torch = gpu.get("torch", {})
    lines.append(f"| PyTorch CUDA | {'available' if torch.get('cuda_available') else 'missing/unavailable'} |")
    git = discovery.get("git", {})
    if git.get("available"):
        lines.extend(
            [
                "",
                "## Source revision",
                "",
                f"- Git root: {git.get('root', 'unknown')}",
                f"- HEAD: {git.get('head', 'unknown')}",
                f"- Dirty: {'yes' if git.get('dirty') else 'no'}",
                f"- Untracked files: {'yes' if git.get('untracked') else 'no'}",
            ]
        )
    lines.extend(["", "## Model endpoint presence", "", "| Role | Model | Base URL configured | API key configured |", "|---|---|---:|---:|"])
    for row in discovery.get("model_endpoints", []):
        lines.append(
            f"| `{row.get('role')}` | `{row.get('model_id')}` | "
            f"{'yes' if row.get('base_url_configured') else 'no'} | "
            f"{'yes' if row.get('api_key_configured') else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Missing model endpoints do not make deterministic planning unavailable. "
            "Live suites must remain explicitly blocked until a backend is configured; no model is silently substituted.",
            "",
        ]
    )
    return "\n".join(lines)


def _versions_manifest(plan: Mapping[str, Any], plan_path: Path, discovery: Mapping[str, Any]) -> dict[str, Any]:
    git = discovery.get("git", {})
    return {
        "manifest_schema_version": "workflow-memory-versions/1",
        "generated_at": discovery.get("discovered_at"),
        "plan": {"path": str(plan_path), "sha256": content_hash(plan), "schema_version": plan.get("schema_version")},
        "git": {
            "root": git.get("root"),
            "head": git.get("head"),
            "dirty": git.get("dirty"),
        },
        "python": discovery.get("python"),
        "packages": discovery.get("packages"),
        "models": plan.get("models", {}),
        "status": "environment_discovered_not_experiment_result",
    }


def _data_manifest(plan: Mapping[str, Any], code_root: Path) -> dict[str, Any]:
    data = plan.get("data", {})
    root = data.get("root") if isinstance(data, Mapping) else None
    resolved = Path(root).expanduser().resolve() if isinstance(root, str) and root else code_root / "data"
    return {
        "manifest_schema_version": "workflow-memory-data/1",
        "status": "not_prepared",
        "root": str(resolved),
        "configured_root": root,
        "preserve_images": bool(data.get("preserve_images", True)) if isinstance(data, Mapping) else True,
        "prefix_information_only": bool(data.get("prefix_information_only", True)) if isinstance(data, Mapping) else True,
        "outcome_available_at": data.get("outcome_available_at") if isinstance(data, Mapping) else None,
        "dataset": plan.get("sources", {}).get("dataset", {}),
    }


def _split_manifest(plan: Mapping[str, Any]) -> dict[str, Any]:
    data = plan.get("data", {})
    return {
        "manifest_schema_version": "workflow-memory-splits/1",
        "status": "planned_not_materialized",
        "seed": data.get("split_seed") if isinstance(data, Mapping) else None,
        "development": {
            "target_trajectories": data.get("dev_trajectory_target") if isinstance(data, Mapping) else None,
            "domain_targets": data.get("dev_domain_targets", {}) if isinstance(data, Mapping) else {},
            "selection": "deterministic_after_prepare_data",
        },
        "official": {"small": "official_manifest_pending", "medium": "official_manifest_pending"},
        "audit": {"small_medium_overlap": "pending", "near_duplicates": "pending"},
    }


def _bootstrap_documents(*, source_plan: Path, code_root: Path) -> dict[str, Any]:
    """Copy execution-package documents into the code root when needed.

    The source execution bundle can live next to a project checkout.  Keeping
    a local copy makes later resume/audit operations independent of the caller's
    original working directory.  Existing local files are never overwritten.
    """

    source_root = source_plan.parent.parent if source_plan.parent.name == "configs" else source_plan.parent
    copied: list[str] = []
    skipped: list[str] = []
    for name in ("WORKPLAN.md", "STATUS.md", "START_HERE.md", "REFERENCE_V1.txt"):
        source = source_root / name
        target = code_root / name
        if not source.is_file():
            continue
        if target.exists():
            skipped.append(str(target))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(str(target))
    local_plan = code_root / "configs" / source_plan.name
    if source_plan.resolve() != local_plan.resolve() and not local_plan.exists():
        local_plan.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_plan, local_plan)
        copied.append(str(local_plan))
    elif local_plan.exists():
        skipped.append(str(local_plan))
    return {
        "source_root": str(source_root.resolve()),
        "copied": copied,
        "existing": skipped,
    }


def run_doctor(*, plan_path: Path, out_path: Path, code_root: Path | None = None) -> dict[str, Any]:
    """Discover the local environment and write the P0 runtime artifacts."""

    plan, source = load_plan(plan_path)
    root = (code_root or Path(__file__).resolve().parents[2]).resolve()
    output = out_path.expanduser().resolve()
    bootstrap = _bootstrap_documents(source_plan=source, code_root=root)
    discovery = discover_environment(plan=plan, code_root=root)
    discovery["bootstrap_documents"] = bootstrap
    generated_at = str(discovery["discovered_at"])
    runtime = build_runtime_config(
        plan,
        plan_path=source,
        code_root=root,
        runtime_path=output,
        discovery=discovery,
        generated_at=generated_at,
    )
    write_json(output, runtime)

    reports = root / "reports"
    manifests = root / "manifests"
    reports.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    (reports / "environment.md").write_text(
        _markdown_environment(discovery, plan_path=source, plan_hash=content_hash(plan)),
        encoding="utf-8",
    )
    write_json(manifests / "versions.json", _versions_manifest(plan, source, discovery))
    write_json(manifests / "data.json", _data_manifest(plan, root))
    write_json(manifests / "splits.json", _split_manifest(plan))
    return runtime
