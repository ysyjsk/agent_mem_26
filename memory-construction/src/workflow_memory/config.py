"""Configuration and reproducibility helpers for :mod:`workflow_memory`.

The execution package intentionally keeps configuration handling small and
dependency free.  A workplan is treated as immutable input; a runtime
configuration is a resolved, self-contained snapshot of that plan plus local
paths and discovered capabilities.  Model clients are not constructed here:
their endpoints are represented by environment-variable names and availability
flags only, so credentials can never be written to manifests accidentally.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


class ConfigError(ValueError):
    """Raised when a plan or runtime configuration is malformed."""


def canonical_bytes(value: Any) -> bytes:
    """Return a stable JSON representation suitable for hashing.

    ``default=str`` is deliberately avoided.  A configuration containing an
    unsupported value should fail loudly instead of silently changing its
    identity.
    """

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ConfigError(f"value is not JSON canonicalisable: {exc}") from exc
    return encoded.encode("utf-8")


def content_hash(value: Any) -> str:
    """Compute a SHA-256 hash over canonical JSON."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: str | os.PathLike[str]) -> Any:
    """Load UTF-8 JSON and raise a useful error for missing/invalid files."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ConfigError(f"configuration file does not exist: {source}")
    try:
        with source.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {source}: {exc}") from exc


def write_json(path: str | os.PathLike[str], value: Any, *, indent: int = 2) -> None:
    """Atomically write JSON, creating the parent directory as needed."""

    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        allow_nan=False,
    )
    # ``NamedTemporaryFile`` in the destination directory keeps os.replace
    # atomic on the same filesystem and avoids partially written manifests
    # after an interrupted run.
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def resolve_path(value: str | os.PathLike[str], *, base: Path) -> Path:
    """Resolve a plan-relative path without depending on the caller's cwd."""

    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a JSON object")
    return value


def validate_plan(plan: Any) -> dict[str, Any]:
    """Validate the minimum workplan contract while preserving all fields."""

    data = dict(require_mapping(plan, "plan"))
    required = ("schema_version", "project", "models", "suites")
    missing = [field for field in required if field not in data]
    if missing:
        raise ConfigError(f"plan is missing required fields: {', '.join(missing)}")
    project = require_mapping(data["project"], "plan.project")
    package = project.get("package")
    if not isinstance(package, str) or not package:
        raise ConfigError("plan.project.package must be a non-empty string")
    suites = require_mapping(data["suites"], "plan.suites")
    if not suites:
        raise ConfigError("plan.suites must not be empty")
    for suite_name, suite in suites.items():
        if not isinstance(suite_name, str) or not suite_name:
            raise ConfigError("plan.suites keys must be non-empty strings")
        require_mapping(suite, f"plan.suites.{suite_name}")
    return data


def load_plan(path: str | os.PathLike[str]) -> tuple[dict[str, Any], Path]:
    source = Path(path).expanduser().resolve()
    return validate_plan(load_json(source)), source


def build_runtime_config(
    plan: Mapping[str, Any],
    *,
    plan_path: Path,
    code_root: Path,
    runtime_path: Path,
    discovery: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Build a self-contained runtime snapshot from a workplan.

    The complete plan is copied under ``plan``.  The source path and hash are
    retained for auditability, while all output paths are explicit absolute
    paths so a resumed run cannot accidentally target another checkout.
    """

    project = require_mapping(plan.get("project"), "plan.project")
    runs_root = code_root / "runs"
    reports_root = code_root / "reports"
    manifests_root = code_root / "manifests"
    results_root = code_root / "results"
    runtime = {
        "runtime_schema_version": "workflow-memory-runtime/1",
        "generated_at": generated_at,
        "plan_source": str(plan_path),
        "plan_sha256": content_hash(plan),
        "runtime_path": str(runtime_path),
        "code_root": str(code_root),
        "package": project.get("package", "workflow_memory"),
        "paths": {
            "code_root": str(code_root),
            "runs": str(runs_root),
            "reports": str(reports_root),
            "manifests": str(manifests_root),
            "results": str(results_root),
            "data": str(code_root / "data"),
            "prompts": str(code_root / "prompts"),
            "configs": str(code_root / "configs"),
        },
        "discovery": dict(discovery),
        "plan": json.loads(json.dumps(plan, ensure_ascii=False)),
    }
    runtime["runtime_sha256"] = content_hash(runtime)
    return runtime


def load_runtime(path: str | os.PathLike[str]) -> tuple[dict[str, Any], Path]:
    source = Path(path).expanduser().resolve()
    data = load_json(source)
    if not isinstance(data, dict):
        raise ConfigError("runtime configuration must be a JSON object")
    if data.get("runtime_schema_version") != "workflow-memory-runtime/1":
        raise ConfigError("unsupported or missing runtime_schema_version")
    if not isinstance(data.get("plan"), dict):
        raise ConfigError("runtime configuration must include an embedded plan")
    validate_plan(data["plan"])
    expected = data.get("runtime_sha256")
    if expected:
        candidate = dict(data)
        candidate.pop("runtime_sha256", None)
        actual = content_hash(candidate)
        if expected != actual:
            raise ConfigError(
                f"runtime configuration hash mismatch: expected {expected}, got {actual}"
            )
    return data, source


def model_endpoint_inventory(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return model endpoint presence without exposing credential values."""

    models = plan.get("models", {})
    if not isinstance(models, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for role, raw in models.items():
        if not isinstance(raw, Mapping):
            continue
        base_env = raw.get("base_url_env")
        key_env = raw.get("api_key_env")
        rows.append(
            {
                "role": role,
                "model_id": raw.get("id"),
                "base_url_env": base_env,
                "base_url_configured": bool(base_env and os.environ.get(str(base_env))),
                "api_key_env": key_env,
                "api_key_configured": bool(key_env and os.environ.get(str(key_env))),
            }
        )
    return rows

