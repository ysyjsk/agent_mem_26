#!/usr/bin/env python3
"""Run the pinned MemForest implementation against the local Qwen checkpoints.

This runner does not alter MemForest's algorithms.  It only replaces the
OpenAI-compatible transport with the already available Transformers backends
used by the internal experiment.  That lets us validate the upstream
``MemForest`` insert/query path on this machine without requiring a separate
vLLM process.  The generated config keeps MemForest's default 4B topology and
prompt/retrieval settings, while selecting the user-provided local 9B and
8B checkpoints and reducing concurrency to one for a deterministic smoke run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
MEMFOREST_ROOT = REPO_ROOT / "memory-construction" / "third_party" / "MemForest"
WORKFLOW_SRC = REPO_ROOT / "memory-construction" / "src"
for path in (MEMFOREST_ROOT, WORKFLOW_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from workflow_memory.backends import ModelRequest  # noqa: E402
from workflow_memory.local_backends import (  # noqa: E402
    TransformersEmbeddingBackend,
    TransformersQwenBackend,
)


class _DirectChatClient:
    """OpenAIChatClient-compatible transport backed by local Transformers."""

    def __init__(self, config: Any, *, api_logger: Any | None = None) -> None:
        del api_logger
        self.config = config
        self.backend = TransformersQwenBackend(
            model_path=os.environ.get(
                "MEMFOREST_LOCAL_CHAT_MODEL",
                "/data/predator/ly/Mem/models/Qwen3.5-9B",
            ),
            device=os.environ.get("MEMFOREST_LOCAL_CHAT_DEVICE", "cuda:0"),
            dtype=os.environ.get("MEMFOREST_LOCAL_DTYPE", "bfloat16"),
            max_input_tokens=int(os.environ.get("MEMFOREST_LOCAL_MAX_INPUT", "32768")),
            enable_thinking=False,
        )

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        timeout: float | None = None,
        step_label: str = "llm",
        trace: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del model_name, top_p, timeout, step_label, trace
        request = ModelRequest(
            messages=(
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ),
            max_tokens=int(max_tokens or 1024),
            temperature=float(temperature or 0.0),
        )
        response = self.backend.complete(request)
        return _parse_json_object(response.text)


class _DirectEmbeddingClient:
    """OpenAIEmbeddingClient-compatible transport backed by local Transformers."""

    def __init__(self, config: Any, *, client: Any | None = None) -> None:
        del config, client
        self.backend = TransformersEmbeddingBackend(
            model_path=os.environ.get(
                "MEMFOREST_LOCAL_EMBED_MODEL",
                "/data/predator/ly/Mem/models/Qwen3-Embedding-8B",
            ),
            device=os.environ.get("MEMFOREST_LOCAL_EMBED_DEVICE", "cuda:1"),
            dtype=os.environ.get("MEMFOREST_LOCAL_DTYPE", "bfloat16"),
            max_length=int(os.environ.get("MEMFOREST_LOCAL_EMBED_MAX_LENGTH", "8192")),
            batch_size=int(os.environ.get("MEMFOREST_LOCAL_EMBED_BATCH", "2")),
        )

    def embed_texts(self, texts: Sequence[str], *, batch_size: int = 256) -> list[list[float]]:
        del batch_size
        return [list(row) for row in self.backend.embed([str(text) for text in texts]).vectors]


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            raw = "\n".join(lines[1:-1]).strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _load_local_config() -> Any:
    import yaml
    from src.config.config import load_default_config

    source = MEMFOREST_ROOT / "src" / "config" / "default_4b.yaml"
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    payload["model"]["llm"]["global"].update(
        {
            "url": "local://transformers/v1",
            "model_name": os.environ.get("MEMFOREST_LOCAL_CHAT_MODEL", "/data/predator/ly/Mem/models/Qwen3.5-9B"),
            "key": "EMPTY",
        }
    )
    payload["model"]["embedding"]["global"].update(
        {
            "url": "local://transformers/v1",
            "model_name": os.environ.get("MEMFOREST_LOCAL_EMBED_MODEL", "/data/predator/ly/Mem/models/Qwen3-Embedding-8B"),
            "key": "EMPTY",
            "dimension": 4096,
        }
    )
    # Keep upstream semantics while avoiding a large concurrent request fanout
    # on a single local model process.
    payload["extraction"]["max_workers"] = 1
    payload["extraction"]["max_inflight_requests"] = 1
    payload["tree"]["summary_manager"]["max_inflight"] = 1
    payload["tree"]["summary_manager"]["max_retries"] = 0
    payload["query"]["browse"]["max_workers"] = 1
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix="memforest-local-",
        dir=str(REPO_ROOT / "memory-construction" / "runs"),
        delete=False,
        encoding="utf-8",
    )
    with handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
    config = load_default_config(handle.name)
    # MemForestConfig is frozen but not slotted; retain the generated YAML
    # path solely so the run manifest can hash the exact effective config.
    object.__setattr__(config, "_source_path", handle.name)
    return config


def _synthetic_turns() -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": "I moved from Boston to Davis in May 2023 and prefer quiet neighborhoods.",
            "timestamp": "2023-05-01T00:00:00Z",
            "content_id": "turn-1",
        },
        {
            "role": "assistant",
            "content": "Understood. I will remember Davis as your current city and your preference for quiet neighborhoods.",
            "timestamp": "2023-05-01T00:01:00Z",
            "content_id": "turn-2",
        },
        {
            "role": "user",
            "content": "In July 2024 I moved from Davis to Miami for work, but I still prefer quiet neighborhoods.",
            "timestamp": "2024-07-01T00:00:00Z",
            "content_id": "turn-3",
        },
        {
            "role": "assistant",
            "content": "Your latest move was from Davis to Miami in July 2024; the quiet-neighborhood preference remains.",
            "timestamp": "2024-07-01T00:01:00Z",
            "content_id": "turn-4",
        },
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _iter_jsonl(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} is not a JSON object")
            yield value


def _trajectory_to_turns(
    record: Mapping[str, Any],
    *,
    max_states: int | None = None,
    max_chars_per_state: int = 12000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Convert one public V2 trajectory to text-only MemForest turns.

    LongMemEval-V2 stores an ordered state/action trace without wall-clock
    timestamps.  We therefore retain source ordering and use omitted
    timestamps (MemForest's deterministic sequence fallback) rather than
    inventing calendar times.  Accessibility trees and screenshot paths are
    retained in source metadata, but only bounded accessibility text is sent to
    the text-only baseline; no image is passed to the model.
    """

    trajectory_id = str(record.get("id") or "trajectory")
    states = record.get("states")
    if not isinstance(states, list) or not states:
        raise ValueError(f"trajectory {trajectory_id!r} has no states")
    selected_states = states if max_states is None else states[: max(1, int(max_states))]
    goal = str(record.get("goal") or "").strip()
    domain = str(record.get("domain") or "").strip()
    environment = str(record.get("environment") or "").strip()
    outcome = str(record.get("outcome") or "").strip()
    turns: list[dict[str, Any]] = []
    for idx, state in enumerate(selected_states):
        if not isinstance(state, Mapping):
            continue
        state_index = state.get("state_index", idx)
        step = state.get("step", idx)
        action = str(state.get("action") or "None").strip()
        thought = str(state.get("thought") or "").strip()
        url = str(state.get("url") or "").strip()
        tree = str(state.get("accessibility_tree") or "").strip()
        if len(tree) > max_chars_per_state:
            tree = tree[:max_chars_per_state] + "\n...[accessibility tree truncated by text-only adapter]"
        header = ""
        if idx == 0:
            header = (
                f"LongMemEval-V2 trajectory {trajectory_id}. Domain: {domain}. "
                f"Environment: {environment}. Goal: {goal}\n"
            )
        content = (
            f"{header}[state_index={state_index}, step={step}]\n"
            f"URL: {url}\n"
            f"Action: {action}\n"
            f"Thought: {thought}\n"
            f"Accessibility tree (text-only observation):\n{tree}"
        )
        # The official outcome is only exposed once the terminal state arrives;
        # this keeps a streaming prefix from seeing the future result.
        if idx == len(selected_states) - 1 and len(selected_states) == len(states) and outcome:
            content += f"\nFinal trajectory outcome: {outcome}"
        turns.append(
            {
                "role": "user",
                "speaker_name": "environment",
                "listener_name": "agent",
                "content": content,
                "content_id": f"{trajectory_id}#state_{int(state_index):04d}",
                "metadata": {
                    "trajectory_id": trajectory_id,
                    "state_index": state_index,
                    "step": step,
                    "url": url,
                    "screenshot": state.get("screenshot"),
                    "vision_omitted": True,
                    "source_accessibility_tree_sha256": hashlib.sha256(
                        str(state.get("accessibility_tree") or "").encode("utf-8")
                    ).hexdigest(),
                },
            }
        )
    if not turns:
        raise ValueError(f"trajectory {trajectory_id!r} yielded no valid states")
    metadata = {
        "trajectory_id": trajectory_id,
        "domain": domain,
        "environment": environment,
        "goal": goal,
        "outcome": outcome if len(selected_states) == len(states) else None,
        "source_state_count": len(states),
        "selected_state_count": len(turns),
        "prefix_truncated": len(turns) < len(states),
        "text_only": True,
        "vision_omitted": True,
        "timestamp_policy": "raw V2 trajectory has no timestamps; MemForest sequence fallback",
        "record_sha256": _sha256_json(record),
    }
    return turns, metadata


def _load_trajectory_inputs(
    path: Path,
    *,
    trajectory_id: str | None,
    max_trajectories: int | None,
    max_states: int | None,
    max_chars_per_state: int,
) -> tuple[list[tuple[Mapping[str, Any], list[dict[str, Any]], dict[str, Any]]], dict[str, Any]]:
    selected: list[tuple[Mapping[str, Any], list[dict[str, Any]], dict[str, Any]]] = []
    for record in _iter_jsonl(path):
        record_id = str(record.get("id") or "")
        if trajectory_id and record_id != trajectory_id:
            continue
        turns, metadata = _trajectory_to_turns(
            record,
            max_states=max_states,
            max_chars_per_state=max_chars_per_state,
        )
        selected.append((record, turns, metadata))
        if max_trajectories is not None and len(selected) >= max(1, int(max_trajectories)):
            break
    if not selected:
        wanted = f" id={trajectory_id!r}" if trajectory_id else ""
        raise ValueError(f"no trajectory selected from {path}{wanted}")
    return selected, {
        "input_path": str(path.resolve()),
        "input_file_sha256": _sha256_file(path),
        "selected_trajectory_ids": [str(item[0].get("id") or "") for item in selected],
        "selected_record_sha256": [item[2]["record_sha256"] for item in selected],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", default=str(REPO_ROOT / "memory-construction" / "runs" / "memforest-local-smoke"))
    parser.add_argument("--user-id", default="local-smoke-user")
    parser.add_argument("--session-id", default="session-001")
    parser.add_argument("--question", default="Where did I live before moving to Miami?")
    parser.add_argument(
        "--trajectory-jsonl",
        default=None,
        help="Optional LongMemEval-V2 trajectories.jsonl. When supplied, run the pinned baseline on selected V2 records.",
    )
    parser.add_argument("--trajectory-id", default=None, help="Optional exact V2 trajectory id")
    parser.add_argument("--max-trajectories", type=int, default=1, help="Maximum V2 trajectories to ingest (default: 1)")
    parser.add_argument(
        "--max-states",
        type=int,
        default=None,
        help="Optional state-prefix limit per trajectory; omitted means full trajectory",
    )
    parser.add_argument(
        "--max-chars-per-state",
        type=int,
        default=12000,
        help="Bounded accessibility-tree text sent to the text-only baseline",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Optional output manifest path (defaults to <snapshot-dir>/manifest.json)",
    )
    parser.add_argument("--keep-snapshot", action="store_true")
    args = parser.parse_args()

    # MemForest constructs these classes inside __init__.  Replacing only the
    # transport classes leaves all extraction, tree, and query algorithms at
    # the pinned upstream commit unchanged.
    import src.api.client as api_client

    api_client.OpenAIChatClient = _DirectChatClient  # type: ignore[assignment]
    api_client.OpenAIEmbeddingClient = _DirectEmbeddingClient  # type: ignore[assignment]

    from src.forest.memforest import MemForest

    snapshot_dir = Path(args.snapshot_dir).expanduser().resolve()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    config = _load_local_config()
    forest = MemForest(snapshot_dir, config=config, max_workers=1)
    config_file = Path(getattr(config, "_source_path", "")) if getattr(config, "_source_path", None) else None
    if config_file is not None and config_file.is_file():
        config_sha256 = _sha256_file(config_file)
    else:
        # load_default_config returns a dataclass; hash the fields actually
        # consumed by MemForest if the temporary YAML path is unavailable.
        config_sha256 = _sha256_json(repr(config))

    if args.trajectory_jsonl:
        trajectory_path = Path(args.trajectory_jsonl).expanduser().resolve()
        selected, input_manifest = _load_trajectory_inputs(
            trajectory_path,
            trajectory_id=args.trajectory_id,
            max_trajectories=args.max_trajectories,
            max_states=args.max_states,
            max_chars_per_state=max(100, int(args.max_chars_per_state)),
        )
        per_trajectory: list[dict[str, Any]] = []
        for record, turns, source_meta in selected:
            trajectory_id = str(record.get("id") or "trajectory")
            user_id = args.user_id if len(selected) == 1 else f"{args.user_id}-{trajectory_id}"
            session_id = args.session_id if len(selected) == 1 else f"lme-v2-{trajectory_id}"
            forest.register_user(user_id, load_existing=False)
            ingest = forest.ingest_session(user_id, session_id, turns)
            query = args.question
            if query == parser.get_default("question"):
                query = f"What evidence is relevant to this trajectory goal? Goal: {source_meta['goal']}"
            result = forest.query(user_id, query, top_k=10, max_facts=10)
            forest.save(user_id)
            per_trajectory.append(
                {
                    "trajectory_id": trajectory_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "source": source_meta,
                    "turn_count": len(turns),
                    "ingest": {
                        "session_id": ingest.session_id,
                        "cells_extracted": ingest.cells_extracted,
                        "facts_inserted": ingest.facts_inserted,
                        "facts_merged": ingest.facts_merged,
                        "trees_updated": ingest.trees_updated,
                    },
                    "query": {
                        "question": query,
                        "protocol": "goal_smoke_not_official_QA",
                        "question_type": result.question_type,
                        "recalled_trees": len(result.recalled_trees),
                        "raw_facts": result.n_raw_facts,
                        "top_facts": [fact.fact_text for fact in result.top_facts],
                    },
                }
            )
        payload = {
            "status": "completed",
            "method": "memforest",
            "commit": "2b5af6d9f92618b30f3e8b7eb99412c1d5eddd6d",
            "snapshot_dir": str(snapshot_dir),
            "config_sha256": config_sha256,
            "input": input_manifest,
            "run_semantics": {
                "text_only": True,
                "vision_omitted": True,
                "official_QA": False,
                "query_protocol": "goal_smoke_not_official_QA",
            },
            "trajectories": per_trajectory,
        }
    else:
        forest.register_user(args.user_id, load_existing=False)
        ingest = forest.ingest_session(args.user_id, args.session_id, _synthetic_turns())
        result = forest.query(args.user_id, args.question, top_k=10, max_facts=10)
        forest.save(args.user_id)
        payload = {
        "status": "completed",
        "method": "memforest",
        "commit": "2b5af6d9f92618b30f3e8b7eb99412c1d5eddd6d",
        "snapshot_dir": str(snapshot_dir),
        "config_sha256": config_sha256,
        "input": {"protocol": "synthetic_smoke"},
        "ingest": {
            "session_id": ingest.session_id,
            "cells_extracted": ingest.cells_extracted,
            "facts_inserted": ingest.facts_inserted,
            "facts_merged": ingest.facts_merged,
            "trees_updated": ingest.trees_updated,
        },
        "query": {
            "question": args.question,
            "question_type": result.question_type,
            "recalled_trees": len(result.recalled_trees),
            "raw_facts": result.n_raw_facts,
            "top_facts": [fact.fact_text for fact in result.top_facts],
        },
        }
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else snapshot_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not args.keep_snapshot:
        # Keep the result JSON/logs but avoid accidental reuse of a smoke
        # snapshot in a later baseline run.
        import shutil

        shutil.rmtree(snapshot_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
