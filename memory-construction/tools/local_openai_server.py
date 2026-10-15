#!/usr/bin/env python3
"""Small local OpenAI-compatible server for the pinned Qwen checkpoints.

This is intentionally a thin adapter around ``workflow_memory.local_backends``.
It exists so the unmodified LongMemEval-V2 harness can use the same local
Transformers model as the internal runner without introducing a silent model
substitution.  Run one process in ``chat`` mode on GPU 0 and one in
``embedding`` mode on GPU 1.  The server is single-model and serializes
generation because a 9B checkpoint does not benefit from concurrent eager
``transformers`` calls on a single 3090 Ti.

The endpoint implements the subset used by the upstream harness:

* ``GET /v1/models``
* ``POST /v1/chat/completions``
* ``POST /v1/embeddings``

It is not a replacement for vLLM.  For larger runs, point the same upstream
configuration at a vLLM server instead.  No credential is logged or persisted.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
from typing import Any, Mapping
from urllib.parse import urlsplit


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _data_url_image(value: Any) -> Any | None:
    """Decode an OpenAI image URL to a PIL image when possible.

    The upstream harness sends screenshots as ``data:image/...;base64,...``.
    If PIL is unavailable or a non-data URL is supplied, return the original
    value so a compatible processor can decide how to handle it.
    """

    if not isinstance(value, str):
        return value
    if not value.startswith("data:"):
        return value
    try:
        header, encoded = value.split(",", 1)
        if ";base64" not in header:
            return value
        raw = base64.b64decode(encoded, validate=True)
        from PIL import Image

        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return value


def _normalize_chat_messages(messages: Any) -> tuple[tuple[dict[str, Any], ...], tuple[Any, ...]]:
    normalized: list[dict[str, Any]] = []
    images: list[Any] = []
    if not isinstance(messages, list):
        messages = []
    for raw in messages:
        if not isinstance(raw, Mapping):
            continue
        role = str(raw.get("role", "user"))
        content = raw.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    text_parts.append(block)
                    continue
                if not isinstance(block, Mapping):
                    continue
                block_type = str(block.get("type", ""))
                if block_type == "text" or "text" in block:
                    value = block.get("text", "")
                    if value:
                        text_parts.append(str(value))
                elif block_type in {"image_url", "image"}:
                    image_value = block.get("image_url", block.get("image"))
                    if isinstance(image_value, Mapping):
                        image_value = image_value.get("url")
                    if image_value is not None:
                        images.append(_data_url_image(image_value))
            text = "\n".join(text_parts)
        else:
            text = str(content)
        normalized.append({"role": role, "content": text})
    if not normalized:
        normalized.append({"role": "user", "content": ""})
    return tuple(normalized), tuple(images)


class _State:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.lock = threading.Lock()
        self.backend: Any | None = None
        self.loaded = False

    def _ensure_backend(self) -> Any:
        if self.backend is not None:
            return self.backend
        # Import lazily so /v1/models can be used as a cheap health check.
        import sys

        code_root = Path(__file__).resolve().parents[1]
        if str(code_root / "src") not in sys.path:
            sys.path.insert(0, str(code_root / "src"))
        if self.args.mode == "chat":
            from workflow_memory.local_backends import TransformersQwenBackend

            self.backend = TransformersQwenBackend(
                self.args.model_path,
                device=self.args.device,
                dtype=self.args.dtype,
                max_input_tokens=self.args.max_input_tokens,
                enable_thinking=self.args.enable_thinking,
            )
        else:
            from workflow_memory.local_backends import TransformersEmbeddingBackend

            self.backend = TransformersEmbeddingBackend(
                self.args.model_path,
                device=self.args.device,
                dtype=self.args.dtype,
                max_length=self.args.max_input_tokens,
                batch_size=self.args.batch_size,
            )
        return self.backend

    def model_fingerprint(self) -> str:
        backend = self._ensure_backend()
        fingerprint = getattr(backend, "fingerprint", None)
        return str(fingerprint() if callable(fingerprint) else self.args.model_id)

    def chat(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        messages, images = _normalize_chat_messages(payload.get("messages"))
        requested = payload.get("max_tokens", payload.get("max_completion_tokens", 1024))
        max_tokens = max(1, int(requested or 1024))
        cap = int(self.args.max_new_tokens_cap or 0)
        if cap > 0:
            max_tokens = min(max_tokens, cap)
        temperature = payload.get("temperature", 0.0)
        temperature = float(temperature) if temperature is not None else 0.0
        from workflow_memory.backends import ModelRequest, ModelResponse

        extra_body = payload.get("extra_body")
        if not isinstance(extra_body, Mapping):
            extra_body = {}
        template_kwargs = payload.get("chat_template_kwargs")
        if not isinstance(template_kwargs, Mapping):
            template_kwargs = extra_body.get("chat_template_kwargs", {})
        if not isinstance(template_kwargs, Mapping):
            template_kwargs = {}
        top_p = payload.get("top_p", extra_body.get("top_p"))
        top_k = payload.get("top_k", extra_body.get("top_k"))
        enable_thinking = template_kwargs.get("enable_thinking")
        metadata: dict[str, Any] = {}
        if top_p is not None:
            metadata["top_p"] = float(top_p)
        if top_k is not None:
            metadata["top_k"] = int(top_k)
        if enable_thinking is not None:
            metadata["enable_thinking"] = bool(enable_thinking)
        request = ModelRequest(
            messages=messages,
            model=str(payload.get("model") or self.args.model_id),
            temperature=temperature,
            max_tokens=max_tokens,
            images=images,
            metadata=metadata,
        )
        started = time.perf_counter()
        with self.lock:
            response = self._ensure_backend().complete(request)
        response = ModelResponse.from_any(response)
        elapsed = time.perf_counter() - started
        if self.args.log_requests:
            print(
                json.dumps(
                    {
                        "kind": "chat",
                        "prompt_tokens": response.usage.get("prompt_tokens", 0),
                        "completion_tokens": response.usage.get("completion_tokens", 0),
                        "elapsed_seconds": round(elapsed, 3),
                    },
                    ensure_ascii=True,
                ),
                flush=True,
            )
        usage = dict(response.usage or {})
        usage.setdefault("prompt_tokens", 0)
        usage.setdefault("completion_tokens", 0)
        usage.setdefault("total_tokens", int(usage["prompt_tokens"]) + int(usage["completion_tokens"]))
        return {
            "id": f"chatcmpl-local-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": response.model or self.args.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response.text},
                    "finish_reason": response.finish_reason or "stop",
                }
            ],
            "usage": usage,
        }

    def embeddings(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        values = payload.get("input", "")
        if isinstance(values, str):
            texts = [values]
        elif isinstance(values, list):
            texts = [str(item) for item in values]
        else:
            texts = [str(values)]
        started = time.perf_counter()
        with self.lock:
            response = self._ensure_backend().embed(texts)
        elapsed = time.perf_counter() - started
        if self.args.log_requests:
            print(
                json.dumps(
                    {"kind": "embedding", "texts": len(texts), "elapsed_seconds": round(elapsed, 3)},
                    ensure_ascii=True,
                ),
                flush=True,
            )
        usage = dict(getattr(response, "usage", {}) or {})
        return {
            "object": "list",
            "model": self.args.model_id,
            "data": [
                {"object": "embedding", "index": index, "embedding": list(vector)}
                for index, vector in enumerate(response.vectors)
            ],
            "usage": usage,
        }


class _Handler(BaseHTTPRequestHandler):
    server_version = "LocalQwenOpenAI/1.0"

    @property
    def state(self) -> _State:
        return self.server.state  # type: ignore[attr-defined]

    def _send(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path in {"/health", "/v1/health"}:
            self._send(HTTPStatus.OK, {"status": "ok", "mode": self.state.args.mode})
            return
        if path == "/v1/models":
            self._send(
                HTTPStatus.OK,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": self.state.args.model_id,
                            "object": "model",
                            "owned_by": "local-transformers",
                        }
                    ],
                },
            )
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": {"message": "not found", "type": "not_found"}})

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            if path == "/v1/chat/completions" and self.state.args.mode == "chat":
                self._send(HTTPStatus.OK, self.state.chat(payload))
                return
            if path == "/v1/embeddings" and self.state.args.mode == "embedding":
                self._send(HTTPStatus.OK, self.state.embeddings(payload))
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": {"message": "endpoint unavailable for this server mode", "type": "not_found"}})
        except Exception as exc:  # noqa: BLE001
            print(f"request failed: {type(exc).__name__}: {exc}", file=os.sys.stderr, flush=True)
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": {"message": str(exc), "type": type(exc).__name__}})

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["chat", "embedding"], required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--max-input-tokens", type=int, default=32768)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-new-tokens-cap", type=int, default=0, help="Optional smoke-only generation cap; 0 preserves request max_tokens")
    parser.add_argument("--enable-thinking", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--log-requests", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not Path(args.model_path).is_dir():
        raise SystemExit(f"model path does not exist: {args.model_path}")
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    server.state = _State(args)  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "status": "ready",
                "mode": args.mode,
                "model_id": args.model_id,
                "device": args.device,
                "base_url": f"http://{args.host}:{args.port}/v1",
            },
            ensure_ascii=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
