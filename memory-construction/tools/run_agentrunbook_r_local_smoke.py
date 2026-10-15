#!/usr/bin/env python3
"""Run the pinned LongMemEval-V2 AgentRunbook-R implementation locally.

The upstream algorithm and prompts are imported unchanged.  Only the OpenAI
transport is replaced with serialized local Transformers calls so the smoke
run can use the two user-provided checkpoints without starting vLLM.  Images
are deliberately replaced by 1x1 placeholders when the public screenshot
bundles are unavailable; the output is therefore labelled ``text_only`` and
is not an official QA score.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_ROOT = REPO_ROOT / "memory-construction" / "third_party" / "LongMemEval-V2"
WORKFLOW_SRC = REPO_ROOT / "memory-construction" / "src"
for path in (WORKFLOW_SRC, UPSTREAM_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from workflow_memory.backends import ModelRequest  # noqa: E402
from workflow_memory.local_backends import (  # noqa: E402
    TransformersEmbeddingBackend,
    TransformersQwenBackend,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/w8AAusB9Wn5xX8AAAAASUVORK5CYII="
)


def _text_content(messages: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    """Drop image blocks for this explicitly text-only smoke path."""

    out: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, Mapping):
                    value = item.get("text")
                    if isinstance(value, str) and value.strip():
                        chunks.append(value)
            content = "\n".join(chunks)
        out.append({"role": role, "content": str(content or "")})
    return tuple(out)


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


class _ChatCore:
    def __init__(self, *, model_path: str, device: str, max_input_tokens: int) -> None:
        self.backend = TransformersQwenBackend(
            model_path=model_path,
            device=device,
            max_input_tokens=max_input_tokens,
            enable_thinking=False,
        )
        self.lock = threading.Lock()

    def complete(self, messages: Sequence[Mapping[str, Any]], *, max_tokens: int, temperature: float) -> str:
        request = ModelRequest(
            messages=_text_content(messages),
            max_tokens=max_tokens,
            temperature=temperature,
        )
        with self.lock:
            return self.backend.complete(request).text


class _ChatCompletions:
    def __init__(self, core: _ChatCore) -> None:
        self.core = core

    def create(self, **kwargs: Any) -> Any:
        text = self.core.complete(
            kwargs.get("messages", ()),
            max_tokens=int(kwargs.get("max_tokens") or 1024),
            temperature=float(kwargs.get("temperature") or 0.0),
        )
        return SimpleNamespace(
            model=str(kwargs.get("model") or "Qwen3.5-9B"),
            choices=[SimpleNamespace(message=SimpleNamespace(content=text, reasoning_content=""))],
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )


class _AsyncChatCompletions:
    def __init__(self, core: _ChatCore) -> None:
        self.core = core

    async def create(self, **kwargs: Any) -> Any:
        return await asyncio.to_thread(
            _ChatCompletions(self.core).create,
            **kwargs,
        )


class _DirectOpenAI:
    chat: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        self.chat = SimpleNamespace(completions=_ChatCompletions(_CHAT_CORE))
        self.embeddings = _EmbeddingCompletions(_EMBED_CORE)


class _DirectAsyncOpenAI:
    chat: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        self.chat = SimpleNamespace(completions=_AsyncChatCompletions(_CHAT_CORE))


class _EmbeddingCompletions:
    def __init__(self, core: "_EmbeddingCore") -> None:
        self.core = core

    def create(self, **kwargs: Any) -> Any:
        values = kwargs.get("input", ())
        if isinstance(values, str):
            values = [values]
        vectors = self.core.embed([str(item) for item in values])
        return SimpleNamespace(
            model=str(kwargs.get("model") or "Qwen3-Embedding-8B"),
            data=[SimpleNamespace(index=i, embedding=row) for i, row in enumerate(vectors)],
            usage=SimpleNamespace(prompt_tokens=0, total_tokens=0),
        )


class _EmbeddingCore:
    def __init__(self, *, model_path: str, device: str, max_length: int) -> None:
        self.backend = TransformersEmbeddingBackend(
            model_path=model_path,
            device=device,
            max_length=max_length,
            batch_size=2,
        )
        self.lock = threading.Lock()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        with self.lock:
            return [list(row) for row in self.backend.embed(list(texts)).vectors]


_CHAT_CORE: _ChatCore
_EMBED_CORE: _EmbeddingCore


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_records(path: Path, limit: int, max_states: int | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(records) >= limit:
                break
            if not line.strip():
                continue
            record = json.loads(line)
            states = record.get("states")
            if not isinstance(states, list) or not states:
                continue
            if max_states is not None and len(states) > max_states:
                record = dict(record)
                record["states"] = states[:max_states]
            records.append(record)
    if not records:
        raise RuntimeError(f"no usable trajectories found in {path}")
    return records


def _materialize_images(records: Sequence[Mapping[str, Any]], root: Path) -> None:
    for record in records:
        trajectory_id = str(record["id"])
        states = record.get("states", [])
        target = root / "screenshots" / trajectory_id
        target.mkdir(parents=True, exist_ok=True)
        for index, _state in enumerate(states):
            path = target / f"{index}.png"
            if not path.exists():
                path.write_bytes(PNG_1X1)


def _memory_config(*, workspace: Path, trajectory_root: Path) -> dict[str, Any]:
    base = json.loads(
        (UPSTREAM_ROOT / "evaluation" / "memory_configs" / "agentrunbook_r.json").read_text(
            encoding="utf-8"
        )
    )
    params = dict(base["memory_params"])
    params["workspace_dir"] = str(workspace)
    params["trajectories_root_dir"] = str(trajectory_root)
    params["controller_params"] = dict(params["controller_params"])
    params["controller_params"].update(
        {
            "model": "Qwen3.5-9B",
            "base_url": "local://transformers",
            "api_key_env": "UNUSED_LOCAL_KEY",
            "max_completion_tokens": 512,
            "max_retries": 0,
            "temperature": 0.0,
            "disable_thinking": True,
        }
    )
    params["embedding_params"] = dict(params["embedding_params"])
    params["embedding_params"].update(
        {
            "model": "Qwen3-Embedding-8B",
            "base_url": "local://transformers",
            "api_key_env": "UNUSED_LOCAL_KEY",
            "max_input_tokens": 4096,
        }
    )
    return {"memory_type": "agentrunbook_r", "memory_params": params}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trajectory-file",
        type=Path,
        default=REPO_ROOT / "memory-construction" / "data" / "longmemeval_dev.jsonl",
    )
    parser.add_argument("--max-trajectories", type=int, default=1)
    parser.add_argument("--max-states", type=int, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "memory-construction" / "runs" / "agentrunbook-r-local-smoke",
    )
    args = parser.parse_args()
    source = args.trajectory_file.expanduser().resolve()
    records = _load_records(source, max(1, args.max_trajectories), args.max_states)
    args.out.mkdir(parents=True, exist_ok=True)
    trajectory_root = args.out / "input"
    trajectory_root.mkdir(parents=True, exist_ok=True)
    _materialize_images(records, trajectory_root)
    input_path = trajectory_root / "trajectories.jsonl"
    with input_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    workspace = args.out / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    global _CHAT_CORE, _EMBED_CORE
    _CHAT_CORE = _ChatCore(
        model_path=os.environ.get("LME_LOCAL_CHAT_MODEL", "/data/predator/ly/Mem/models/Qwen3.5-9B"),
        device=os.environ.get("LME_LOCAL_CHAT_DEVICE", "cuda:0"),
        max_input_tokens=int(os.environ.get("LME_LOCAL_CHAT_MAX_INPUT", "8192")),
    )
    _EMBED_CORE = _EmbeddingCore(
        model_path=os.environ.get("LME_LOCAL_EMBED_MODEL", "/data/predator/ly/Mem/models/Qwen3-Embedding-8B"),
        device=os.environ.get("LME_LOCAL_EMBED_DEVICE", "cuda:1"),
        max_length=int(os.environ.get("LME_LOCAL_EMBED_MAX_INPUT", "4096")),
    )

    import memory_modules.agentrunbook_r as upstream  # noqa: E402

    upstream.OpenAI = _DirectOpenAI  # type: ignore[assignment]
    upstream.AsyncOpenAI = _DirectAsyncOpenAI  # type: ignore[assignment]
    from memory_modules.memory import build_memory  # noqa: E402

    memory = build_memory(_memory_config(workspace=workspace, trajectory_root=trajectory_root))
    for record in records:
        memory.insert(record)
    question = str(records[0].get("goal") or "What was observed in this trajectory?")
    context = memory.query(question)
    payload = {
        "status": "completed",
        "method": "agentrunbook_r",
        "source_mode": "text_only_placeholder_images",
        "upstream_commit": "2cc8c540bdb87fe6761629b585e727e1c4704520",
        "input": {
            "path": str(source),
            "sha256": _sha256(source),
            "trajectories": len(records),
            "states": sum(len(row.get("states", [])) for row in records),
            "max_states": args.max_states,
        },
        "query": {
            "question_hash": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "context_items": len(context),
            "context_text_items": sum(1 for item in context if item.get("type") == "text"),
        },
        "workspace": str(workspace),
    }
    (args.out / "result.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
