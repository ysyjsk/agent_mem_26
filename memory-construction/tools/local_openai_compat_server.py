#!/usr/bin/env python3
"""Small OpenAI-compatible HTTP proxy for the pinned baseline runners.

It intentionally implements only the endpoints used by LongMemEval-V2 and
MemForest: ``/v1/models``, ``/v1/chat/completions`` and ``/v1/embeddings``.
The model itself is the same local Transformers backend used by the internal
runner; requests are serialized so a baseline's large prompts cannot trigger
concurrent GPU allocation spikes.  This is a transport shim, not a change to
any baseline algorithm.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_SRC = REPO_ROOT / "memory-construction" / "src"
if str(WORKFLOW_SRC) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SRC))

from workflow_memory.backends import ModelRequest  # noqa: E402
from workflow_memory.local_backends import (  # noqa: E402
    TransformersEmbeddingBackend,
    TransformersQwenBackend,
)


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                kind = item.get("type")
                if kind in {"text", "input_text"}:
                    chunks.append(str(item.get("text", "")))
                elif kind in {"image_url", "image"}:
                    # LongMemEval's reader can request image evidence.  The
                    # local proxy is deliberately text-only, so preserve a
                    # stable marker instead of silently losing message order.
                    chunks.append("[image omitted by local text-only proxy]")
            elif item is not None:
                chunks.append(str(item))
        return "\n".join(chunks)
    return str(content or "")


class _ServerState:
    def __init__(self, backend: Any, model_name: str, kind: str) -> None:
        self.backend = backend
        self.model_name = model_name
        self.kind = kind
        self.lock = threading.RLock()
        self.started_at = time.time()


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalOpenAICompat/0.1"

    @property
    def state(self) -> _ServerState:
        return self.server.state  # type: ignore[attr-defined]

    def _write_json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/v1/models":
            self._write_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": self.state.model_name,
                            "object": "model",
                            "owned_by": "local-transformers",
                        }
                    ],
                },
            )
            return
        if self.path in {"/health", "/v1/health"}:
            self._write_json(200, {"status": "ok", "model": self.state.model_name, "kind": self.state.kind})
            return
        self._write_json(404, {"error": {"message": "not found", "type": "not_found"}})

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._read_json()
            path = self.path.rstrip("/")
            if path == "/v1/chat/completions":
                self._chat(payload)
                return
            if path == "/v1/embeddings":
                self._embeddings(payload)
                return
            self._write_json(404, {"error": {"message": "not found", "type": "not_found"}})
        except Exception as exc:  # pragma: no cover - exercised by live server
            self._write_json(
                500,
                {"error": {"message": f"{type(exc).__name__}: {exc}", "type": "server_error"}},
            )

    def _chat(self, payload: Mapping[str, Any]) -> None:
        if self.state.kind != "chat":
            raise RuntimeError("chat endpoint is unavailable on embedding server")
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise ValueError("messages must be a list")
        normalized = []
        for message in messages:
            if not isinstance(message, Mapping):
                continue
            normalized.append({"role": str(message.get("role", "user")), "content": _text_content(message.get("content", ""))})
        with self.state.lock:
            response = self.state.backend.complete(
                ModelRequest(
                    messages=tuple(normalized),
                    max_tokens=int(payload.get("max_tokens") or payload.get("max_completion_tokens") or 1024),
                    temperature=float(payload.get("temperature") or 0.0),
                )
            )
        request_id = f"chatcmpl-local-{uuid.uuid4().hex[:16]}"
        usage = dict(response.usage or {})
        self._write_json(
            200,
            {
                "id": request_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": self.state.model_name,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response.text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage.get("completion_tokens", 0)),
                    "total_tokens": int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0)),
                },
            },
        )

    def _embeddings(self, payload: Mapping[str, Any]) -> None:
        if self.state.kind != "embedding":
            raise RuntimeError("embedding endpoint is unavailable on chat server")
        value = payload.get("input")
        texts = value if isinstance(value, list) else [value]
        texts = [str(item or "") for item in texts]
        with self.state.lock:
            response = self.state.backend.embed(texts)
        self._write_json(
            200,
            {
                "object": "list",
                "data": [
                    {"object": "embedding", "embedding": list(vector), "index": index}
                    for index, vector in enumerate(response.vectors)
                ],
                "model": self.state.model_name,
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            },
        )

    def log_message(self, format: str, *args: Any) -> None:
        # Keep baseline stdout/stderr readable; errors are returned as JSON.
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["chat", "embedding"], required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--max-input-tokens", type=int, default=32768)
    args = parser.parse_args()
    model_name = args.model_name or Path(args.model_path).name
    if args.kind == "chat":
        backend = TransformersQwenBackend(
            model_path=args.model_path,
            device=args.device,
            dtype=args.dtype,
            max_input_tokens=args.max_input_tokens,
            enable_thinking=False,
        )
    else:
        backend = TransformersEmbeddingBackend(
            model_path=args.model_path,
            device=args.device,
            dtype=args.dtype,
            max_length=args.max_input_tokens,
            batch_size=2,
        )
    # Trigger model loading before accepting requests, so health/readiness
    # reflects usable model state and startup failures are explicit.
    backend._ensure_loaded()  # type: ignore[attr-defined]
    state = _ServerState(backend, model_name, args.kind)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.state = state  # type: ignore[attr-defined]
    print(json.dumps({"status": "ready", "kind": args.kind, "model": model_name, "host": args.host, "port": args.port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
