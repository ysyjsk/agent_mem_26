#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

LOCAL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = LOCAL_ROOT.parents[2]
LONGMEM_ROOT = PROJECT_ROOT / "third_party" / "LongMemEval-V2"
# Keep this diagnostic adapter self-contained: when launched by absolute path,
# Python normally puts the script directory first, but callers may provide a
# PYTHONPATH that would otherwise import the upstream evaluation package.
if str(LOCAL_ROOT) in sys.path:
    sys.path.remove(str(LOCAL_ROOT))
sys.path.insert(0, str(LOCAL_ROOT))
for import_root in (LONGMEM_ROOT, PROJECT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.append(str(import_root))

from data.public_data import (  # noqa: E402
    materialize_runtime_haystack,
    materialize_runtime_questions,
    write_json,
)


METHODS = {
    "workflow_b3",
    "workflow_ours",
    "no_retrieval",
    "rag_query_to_slice",
    "rag_query_to_slice_notes",
    "agentrunbook_r",
    "codex",
    "agentrunbook_c",
    "agentrunbook_c_v2",
}

OPENAI_SDK_TIMEOUT_SECONDS_BY_REASONING_EFFORT = {
    "low": 200.0,
    "medium": 800.0,
    "xhigh": 1200.0,
}


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean-like value, got {raw!r}")


def parse_question_ids(raw_values: list[str] | None) -> list[str] | None:
    if not raw_values:
        return None
    out: list[str] = []
    for raw in raw_values:
        for item in raw.split(","):
            stripped = item.strip()
            if stripped:
                out.append(stripped)
    return out or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LongMemEval-V2 evaluation.")
    parser.add_argument("--data-root", required=True, help="Path to the downloaded LongMemEval-V2 dataset")
    parser.add_argument("--domain", choices=["web", "enterprise"], required=True)
    parser.add_argument("--tier", choices=["small", "medium"], default="small")
    parser.add_argument("--method", choices=sorted(METHODS), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N selected questions")
    parser.add_argument("--question-ids", nargs="*", default=None, help="Optional question ids, space or comma separated")

    parser.add_argument("--reader-model", default=os.getenv("READER_MODEL", "Qwen/Qwen3.5-9B"))
    parser.add_argument("--reader-base-url", default=os.getenv("READER_BASE_URL", "http://localhost:8023/v1"))
    parser.add_argument("--reader-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--reader-temperature", type=float, default=float(os.getenv("READER_TEMPERATURE", "0.6")))
    parser.add_argument("--reader-top-p", type=float, default=float(os.getenv("READER_TOP_P", "0.95")))
    parser.add_argument("--reader-top-k", type=int, default=int(os.getenv("READER_TOP_K", "20")))
    parser.add_argument("--reader-max-concurrent-requests", type=int, default=16)
    # Local Reader development default.  Older smoke runs used 128/256 and
    # silently cut off the answer before the boxed final response.
    parser.add_argument("--max-completion-tokens", type=int, default=1024)
    parser.add_argument("--memory-context-max-tokens", type=int, default=200000)
    parser.add_argument("--reader-enable-thinking", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--text-only",
        action=argparse.BooleanOptionalAction,
        default=env_bool("LME_TEXT_ONLY", False),
        help=(
            "Diagnostic mode: omit all screenshot image_url blocks from controller,"
            " event, and Reader requests. This is not a native visual benchmark run."
        ),
    )

    parser.add_argument("--controller-model", default=os.getenv("LME_CONTROLLER_MODEL", "Qwen/Qwen3.5-9B"))
    parser.add_argument("--controller-base-url", default=os.getenv("LME_CONTROLLER_BASE_URL", "http://localhost:8023/v1"))
    parser.add_argument("--controller-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--controller-temperature", type=float, default=float(os.getenv("LME_CONTROLLER_TEMPERATURE", "0.6")))
    parser.add_argument("--controller-top-p", type=float, default=float(os.getenv("LME_CONTROLLER_TOP_P", "0.95")))
    parser.add_argument("--controller-top-k", type=int, default=int(os.getenv("LME_CONTROLLER_TOP_K", "20")))
    parser.add_argument("--controller-disable-thinking", action=argparse.BooleanOptionalAction, default=False)

    parser.add_argument("--embedding-model", default=os.getenv("LME_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-8B"))
    parser.add_argument("--embedding-base-url", default=os.getenv("LME_EMBEDDING_BASE_URL", "http://localhost:8114/v1"))
    parser.add_argument("--embedding-api-key-env", default="OPENAI_API_KEY")

    parser.add_argument("--codex-binary", default=os.getenv("CODEX_BINARY", "codex"))
    parser.add_argument("--codex-model", default=os.getenv("CODEX_MODEL", "gpt-5.4-mini"))
    parser.add_argument("--codex-reasoning-effort", default=os.getenv("CODEX_REASONING_EFFORT", "xhigh"))
    parser.add_argument("--codex-timeout-seconds", type=float, default=float(os.getenv("CODEX_TIMEOUT_SECONDS", "1800")))
    parser.add_argument("--codex-max-retries", type=int, default=int(os.getenv("CODEX_MAX_RETRIES", "3")))
    parser.add_argument("--openai-sdk-model", default=os.getenv("OPENAI_SDK_MODEL", "gpt-5.4-mini"))
    parser.add_argument(
        "--openai-sdk-reasoning-effort",
        choices=tuple(OPENAI_SDK_TIMEOUT_SECONDS_BY_REASONING_EFFORT),
        default=os.getenv("OPENAI_SDK_REASONING_EFFORT", "medium"),
        help="OpenAI Agents SDK reasoning effort. Query timeout is fixed by tier: low=200, medium=800, xhigh=1200.",
    )
    parser.add_argument("--openai-sdk-max-retries", type=int, default=int(os.getenv("OPENAI_SDK_MAX_RETRIES", os.getenv("CODEX_MAX_RETRIES", "3"))))
    parser.add_argument("--openai-sdk-api-key-env", default=os.getenv("OPENAI_SDK_API_KEY_ENV", "OPENAI_API_KEY"))
    parser.add_argument("--openai-sdk-max-turns", type=int, default=int(os.getenv("OPENAI_SDK_MAX_TURNS", "30")))
    parser.add_argument("--openai-sdk-tool-timeout-seconds", type=float, default=float(os.getenv("OPENAI_SDK_TOOL_TIMEOUT_SECONDS", "30")))
    parser.add_argument("--openai-sdk-max-tool-output-chars", type=int, default=int(os.getenv("OPENAI_SDK_MAX_TOOL_OUTPUT_CHARS", "1048576")))
    parser.add_argument(
        "--enable-online-learning",
        action=argparse.BooleanOptionalAction,
        default=env_bool("OPENAI_SDK_ONLINE_LEARNING", False),
        help="Enable online learned retrieval strategy for agentrunbook_c_v2.",
    )
    parser.add_argument(
        "--openai-sdk-online-learning",
        action=argparse.BooleanOptionalAction,
        default=argparse.SUPPRESS,
        dest="enable_online_learning",
        help=argparse.SUPPRESS,
    )

    parser.add_argument("--evaluator-model", default=os.getenv("EVALUATOR_MODEL", "gpt-5.2"))
    parser.add_argument("--evaluator-base-url", default=os.getenv("EVALUATOR_BASE_URL", None))
    parser.add_argument("--evaluator-api-key-env", default=os.getenv("EVALUATOR_API_KEY_ENV", "OPENAI_API_KEY"))
    parser.add_argument("--evaluator-reasoning-effort", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--evaluator-max-completion-tokens", type=int, default=1024)

    parser.add_argument("--prompt-build-max-workers", type=int, default=1)
    parser.add_argument("--save-memory", action="store_true", help="Persist each completed trajectory and verify the shared memory can be loaded")
    parser.add_argument("--skip-evaluation", action="store_true", help="Build and validate saved memory without querying")
    parser.add_argument("--construction-trajectory-limit", type=int, default=None, help="Construction screening only: first N complete trajectories, requires --skip-evaluation")
    parser.add_argument("--event-group-size", type=int, choices=[1, 2], default=1)
    parser.add_argument("--event-output-tokens", type=int, default=None, help="Output ceiling per event; paired extraction receives twice this budget")
    parser.add_argument("--event-max-input-tokens", type=int, default=None, help="Resource-aware preflight; reuse existing bounded-state fallback before oversized single-event requests")
    parser.add_argument("--controller-max-retries", type=int, default=3)
    parser.add_argument("--record-full-requests", action="store_true")
    parser.add_argument("--reuse-build-embedding", action="store_true", help="Exact prepared-input reuse in construction; all source mappings retained")
    parser.add_argument("--load-memory-dir", default=None, help="Reuse a previously saved compatible shared memory")
    parser.add_argument("--event-state-max-chars", type=int, default=None, help="Limit AXTree chars per state in first event extraction request (diagnostic variant)")
    parser.add_argument("--event-concurrency", type=int, default=None, help="Bound simultaneous event extraction requests (diagnostic variant)")
    parser.add_argument("--evidence-first", action="store_true", help="Put raw state evidence before generated notes/events in query context (diagnostic variant)")
    parser.add_argument("--skip-event-generation", action="store_true", help="Ablate generated events; retain complete trajectories, raw-state index and generated notes")
    parser.add_argument("--chunk-memory-context", action="store_true", help="Split and interleave oversized text evidence before Reader truncation (diagnostic variant)")
    parser.add_argument("--cache-context-tokenizer", action="store_true", help="Reuse the same tokenizer instance across budget checks; identical tokenization")
    parser.add_argument("--lexical-backfill", action="store_true", help="Add deduplicated query-matching source lines from the top retrieved trajectories")
    parser.add_argument("--backfill-neighbor-lines", type=int, choices=[0, 1], default=0, help="Ablate local source context around lexical backfill anchors")
    parser.add_argument("--reuse-query-embedding", action="store_true", help="Reuse identical embedding requests within one query invocation, across retrieval pools")
    parser.add_argument("--raw-state-search-top-k-per-query", type=int, default=6)
    parser.add_argument("--raw-state-result-merge-budget", type=int, default=6)
    parser.add_argument("--interleave-notes-after-raw-hits", type=int, default=0, help="Place note results after this many raw hits (diagnostic query-order variant)")
    parser.add_argument("--shuffle-questions-seed", type=int, default=None)
    args = parser.parse_args()
    if args.openai_sdk_reasoning_effort not in OPENAI_SDK_TIMEOUT_SECONDS_BY_REASONING_EFFORT:
        parser.error(
            "--openai-sdk-reasoning-effort must be one of "
            f"{', '.join(OPENAI_SDK_TIMEOUT_SECONDS_BY_REASONING_EFFORT)}"
        )
    return args


def controller_params(args: argparse.Namespace) -> dict[str, object]:
    return {
        "model": args.controller_model,
        "base_url": args.controller_base_url,
        "api_key_env": args.controller_api_key_env,
        "api_key_file": None,
        "max_completion_tokens": 8192,
        "timeout_seconds": 600.0,
        "max_retries": args.controller_max_retries,
        "disable_thinking": args.controller_disable_thinking,
        "temperature": args.controller_temperature,
        "top_p": args.controller_top_p,
        "top_k": args.controller_top_k,
    }


def embedding_params(args: argparse.Namespace) -> dict[str, object]:
    return {
        "model": args.embedding_model,
        "base_url": args.embedding_base_url,
        "api_key_env": args.embedding_api_key_env,
        "api_key_file": None,
        "max_input_tokens": 4096,
        "query_instruction": "Given a question about past agent trajectories, retrieve relevant memory entries that help answer it.",
    }


def openai_sdk_query_params(args: argparse.Namespace) -> dict[str, object]:
    return {
        "model": args.openai_sdk_model,
        "reasoning_effort": args.openai_sdk_reasoning_effort,
        "timeout_seconds": openai_sdk_timeout_seconds(args),
        "max_retries": args.openai_sdk_max_retries,
        "max_turns": args.openai_sdk_max_turns,
        "api_key_env": args.openai_sdk_api_key_env,
        "tool_timeout_seconds": args.openai_sdk_tool_timeout_seconds,
        "max_tool_output_chars": args.openai_sdk_max_tool_output_chars,
    }


def openai_sdk_timeout_seconds(args: argparse.Namespace) -> float:
    reasoning_effort = str(args.openai_sdk_reasoning_effort).lower()
    return OPENAI_SDK_TIMEOUT_SECONDS_BY_REASONING_EFFORT[reasoning_effort]


def write_diagnostic_provenance(
    *,
    output_dir: Path,
    runtime_dir: Path,
    args: argparse.Namespace,
) -> None:
    """Mark this isolated adapter as non-native, even if harness output exists.

    The official harness writes ``run_args.json`` itself.  We merge the marker
    after that write as well as emitting a separate provenance file so a text-only
    diagnostic cannot be mistaken for the visual native benchmark.
    """
    marker = {
        "run_kind": "diagnostic-text-only" if args.text_only else "diagnostic-visual-adapter",
        "native_claim": False,
        "input_modality": "text-only" if args.text_only else "visual",
        "official_small_claim": False,
        "reason": (
            "Screenshots intentionally omitted from controller/event/Reader requests;"
            " use only for local diagnostics, not native Small or official quality."
            if args.text_only
            else "Isolated local adapter wrapper; not the frozen official native entrypoint."
        ),
        "runner": str(Path(__file__).resolve()),
        "runtime_dir": str(runtime_dir),
        "method": args.method,
        "domain": args.domain,
        "tier": args.tier,
        "reader_model": args.reader_model,
        "controller_model": args.controller_model,
        "embedding_model": args.embedding_model,
        "event_state_max_chars": args.event_state_max_chars,
        "event_concurrency": args.event_concurrency,
        "event_group_size": args.event_group_size,
        "event_output_tokens": args.event_output_tokens,
        "event_max_input_tokens": args.event_max_input_tokens,
        "controller_max_retries": args.controller_max_retries,
        "construction_trajectory_limit": args.construction_trajectory_limit,
        "record_full_requests": args.record_full_requests,
        "reuse_build_embedding": args.reuse_build_embedding,
        "evidence_first": args.evidence_first,
        "skip_event_generation": args.skip_event_generation,
        "chunk_memory_context": args.chunk_memory_context,
        "cache_context_tokenizer": args.cache_context_tokenizer,
        "lexical_backfill": args.lexical_backfill,
        "backfill_neighbor_lines": args.backfill_neighbor_lines,
        "reuse_query_embedding": args.reuse_query_embedding,
        "raw_state_search_top_k_per_query": args.raw_state_search_top_k_per_query,
        "raw_state_result_merge_budget": args.raw_state_result_merge_budget,
        "interleave_notes_after_raw_hits": args.interleave_notes_after_raw_hits,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "adapter_provenance.json", marker)
    run_args_path = output_dir / "run_args.json"
    if run_args_path.exists():
        try:
            existing = json.loads(run_args_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if not isinstance(existing, dict):
            existing = {}
        existing.update(marker)
        write_json(run_args_path, existing)


def build_memory_config(args: argparse.Namespace, data_root: Path) -> dict[str, object]:
    if args.method == "no_retrieval":
        return {"memory_type": "no_retrieval", "memory_params": {}}
    if args.method in {"rag_query_to_slice", "rag_query_to_slice_notes", "workflow_b3", "workflow_ours"}:
        return {
            "memory_type": args.method if args.method.startswith("workflow_") else "rag",
            "memory_params": {
                "trajectory_pool_root": None,
                "controller_params": controller_params(args),
                "embedding_params": embedding_params(args),
                "index_params": {"raw_state_slice_radius": 1},
                "retrieval_params": {
                    "enable_notes": args.method == "rag_query_to_slice_notes",
                    "raw_state_search_top_k": 6,
                    "note_search_top_k_per_type": 3,
                },
            },
        }
    if args.method == "agentrunbook_r":
        return {
            "memory_type": "agentrunbook_r",
            "memory_params": {
                "trajectory_pool_root": None,
                "controller_params": controller_params(args),
                "embedding_params": embedding_params(args),
                "index_params": {"raw_state_slice_radius": 1},
                "query_params": {
                    "max_raw_state_queries": 5,
                    "query_generation_disable_thinking": args.controller_disable_thinking,
                },
                "retrieval_params": {
                    "raw_state_search_top_k_per_query": args.raw_state_search_top_k_per_query,
                    "event_search_top_k": 6,
                    "note_search_top_k_per_type": 3,
                    "raw_state_result_merge_budget": args.raw_state_result_merge_budget,
                    "raw_state_result_merge_per_query_cap": 2,
                    "rerank_candidate_limit": 8,
                    "enable_rerank": False,
                },
            },
        }
    codex_params = {
        "binary": args.codex_binary,
        "model": args.codex_model,
        "reasoning_effort": args.codex_reasoning_effort,
        "timeout_seconds": args.codex_timeout_seconds,
        "max_retries": args.codex_max_retries,
        "extra_config": [],
        "extra_args": [],
    }
    if args.method == "codex":
        return {
            "memory_type": "codex",
            "memory_params": {
                "evidence_mode": "both",
                "trajectory_pool_root": None,
                "codex_params": codex_params,
            },
        }
    if args.method == "agentrunbook_c_v2":
        memory_params: dict[str, object] = {
            "evidence_mode": "both",
            "trajectory_pool_root": None,
            "query_openai_sdk_params": openai_sdk_query_params(args),
        }
        if args.enable_online_learning:
            memory_params["online_learning_params"] = {
                "enabled": True,
                "strategy_memory_dir": None,
                "consolidation_codex_binary": args.codex_binary,
                "timeout_seconds": args.codex_timeout_seconds,
            }
        return {
            "memory_type": "agentrunbook_c_v2",
            "memory_params": memory_params,
        }
    return {
        "memory_type": "agentrunbook_c",
        "memory_params": {
            "evidence_mode": "both",
            "trajectory_pool_root": None,
            "query_codex_params": codex_params,
        },
    }


def main() -> None:
    args = parse_args()
    os.environ["LME_EVENT_GROUP_SIZE"] = str(args.event_group_size)
    os.environ["LME_RECORD_FULL_REQUESTS"] = "1" if args.record_full_requests else "0"
    os.environ["LME_REUSE_BUILD_EMBEDDING"] = "1" if args.reuse_build_embedding else "0"
    if args.event_max_input_tokens is not None:
        if not 1 <= args.event_max_input_tokens <= 32768:
            raise SystemExit("--event-max-input-tokens must fit the resident server's 32768 input ceiling")
        os.environ["LME_EVENT_MAX_INPUT_TOKENS"] = str(args.event_max_input_tokens)
    else:
        os.environ.pop("LME_EVENT_MAX_INPUT_TOKENS", None)
    if args.event_output_tokens is not None:
        if not 1 <= args.event_output_tokens <= 4096 // args.event_group_size:
            raise SystemExit("Event output budget must fit the resident server's 4096-token ceiling")
        os.environ["LME_EVENT_OUTPUT_TOKENS"] = str(args.event_output_tokens)
    else:
        os.environ.pop("LME_EVENT_OUTPUT_TOKENS", None)
    if args.construction_trajectory_limit is not None and (not args.skip_evaluation or args.construction_trajectory_limit < 1):
        raise SystemExit("Construction limit requires --skip-evaluation and a positive limit")
    os.environ["LME_CACHE_CONTEXT_TOKENIZER"] = "1" if args.cache_context_tokenizer else "0"
    os.environ["LME_LEXICAL_BACKFILL"] = "1" if args.lexical_backfill else "0"
    os.environ["LME_BACKFILL_NEIGHBOR_LINES"] = str(args.backfill_neighbor_lines)
    os.environ["LME_REUSE_QUERY_EMBEDDING"] = "1" if args.reuse_query_embedding else "0"
    if args.event_state_max_chars is not None:
        if args.event_state_max_chars <= 0:
            raise SystemExit("--event-state-max-chars must be positive")
        os.environ["LME_EVENT_STATE_MAX_CHARS"] = str(args.event_state_max_chars)
    else:
        os.environ.pop("LME_EVENT_STATE_MAX_CHARS", None)
    if args.event_concurrency is not None:
        if args.event_concurrency <= 0:
            raise SystemExit("--event-concurrency must be positive")
        os.environ["LME_EVENT_CONCURRENCY"] = str(args.event_concurrency)
    else:
        os.environ.pop("LME_EVENT_CONCURRENCY", None)
    if args.evidence_first:
        os.environ["LME_EVIDENCE_FIRST"] = "1"
    else:
        os.environ.pop("LME_EVIDENCE_FIRST", None)
    if args.interleave_notes_after_raw_hits < 0:
        raise SystemExit("--interleave-notes-after-raw-hits cannot be negative")
    os.environ["LME_INTERLEAVE_NOTES_AFTER_RAW_HITS"] = str(args.interleave_notes_after_raw_hits)
    if args.skip_event_generation:
        os.environ["LME_SKIP_EVENT_GENERATION"] = "1"
    else:
        os.environ.pop("LME_SKIP_EVENT_GENERATION", None)
    if args.chunk_memory_context:
        os.environ["LME_CHUNK_MEMORY_CONTEXT"] = "1"
    else:
        os.environ.pop("LME_CHUNK_MEMORY_CONTEXT", None)
    if args.text_only:
        os.environ["LME_TEXT_ONLY"] = "1"
    else:
        # Do not leak a caller's text-only setting into an explicitly visual
        # invocation of this adapter.
        os.environ.pop("LME_TEXT_ONLY", None)
    # The local OpenAI-compatible embedding service uses a filesystem model id
    # that is not a HuggingFace repo name.  AgentRunbook-R also tokenizes
    # embedding inputs locally for request accounting, so make that path
    # explicit in this isolated adapter unless the caller supplied another
    # tokenizer.
    os.environ.setdefault(
        "LME_EMBEDDING_TOKENIZER_MODEL",
        "/data/predator/ly/Mem/models/Qwen3-Embedding-8B",
    )
    if args.enable_online_learning and args.method != "agentrunbook_c_v2":
        raise SystemExit("--enable-online-learning is only supported with --method agentrunbook_c_v2")
    if args.enable_online_learning and args.prompt_build_max_workers != 1:
        raise SystemExit("--enable-online-learning requires --prompt-build-max-workers 1 for sequential online learning")
    data_root = Path(args.data_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    runtime_dir = output_dir / "runtime_inputs"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    selected_questions = materialize_runtime_questions(
        data_root=data_root,
        domain=args.domain,
        question_ids=parse_question_ids(args.question_ids),
        limit=args.limit,
        output_path=runtime_dir / "questions.json",
    )
    materialize_runtime_haystack(
        data_root=data_root,
        tier=args.tier,
        selected_questions=selected_questions,
        output_path=runtime_dir / "haystack.json",
    )
    if args.construction_trajectory_limit is not None:
        haystack = json.loads((runtime_dir / "haystack.json").read_text())
        write_json(runtime_dir / "haystack.json", {qid: ids[:args.construction_trajectory_limit] for qid, ids in haystack.items()})
    memory_config = build_memory_config(args, data_root)
    memory_config_path = runtime_dir / "memory_config.json"
    write_json(memory_config_path, memory_config)

    harness_argv = [
        "evaluation.harness",
        "--domain",
        args.domain,
        "--questions-path",
        str(runtime_dir / "questions.json"),
        "--haystack-path",
        str(runtime_dir / "haystack.json"),
        "--trajectories-path",
        str(data_root / "trajectories.jsonl"),
        "--memory-config-path",
        str(memory_config_path),
        "--output-dir",
        str(output_dir),
        "--model",
        args.reader_model,
        "--base-url",
        args.reader_base_url,
        "--api-key-env",
        args.reader_api_key_env,
        "--temperature",
        str(args.reader_temperature),
        "--top-p",
        str(args.reader_top_p),
        "--top-k",
        str(args.reader_top_k),
        "--max-completion-tokens",
        str(args.max_completion_tokens),
        "--memory-context-max-tokens",
        str(args.memory_context_max_tokens),
        "--reader-max-concurrent-requests",
        str(args.reader_max_concurrent_requests),
        "--prompt-build-max-workers",
        str(args.prompt_build_max_workers),
        "--evaluator-model",
        args.evaluator_model,
        "--evaluator-base-url",
        args.evaluator_base_url or "",
        "--evaluator-api-key-env",
        args.evaluator_api_key_env,
        "--evaluator-reasoning-effort",
        args.evaluator_reasoning_effort,
        "--evaluator-max-completion-tokens",
        str(args.evaluator_max_completion_tokens),
    ]
    if not args.reader_enable_thinking:
        harness_argv.append("--reader-disable-thinking")
    if args.save_memory:
        harness_argv.append("--save-memory")
    if args.skip_evaluation:
        harness_argv.append("--skip-evaluation")
    if args.load_memory_dir:
        harness_argv.extend(["--load-memory-dir", args.load_memory_dir])
    if args.shuffle_questions_seed is not None:
        harness_argv.extend(["--shuffle-questions-seed", str(args.shuffle_questions_seed)])
    print(json.dumps({"runtime_dir": str(runtime_dir), "method": args.method}, indent=2))
    old_argv = sys.argv
    try:
        sys.argv = harness_argv
        from evaluation.harness import main as harness_main

        harness_main()
    finally:
        sys.argv = old_argv
        write_diagnostic_provenance(output_dir=output_dir, runtime_dir=runtime_dir, args=args)


if __name__ == "__main__":
    main()
