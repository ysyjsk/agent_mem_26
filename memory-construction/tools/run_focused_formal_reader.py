#!/usr/bin/env python3
"""Run the frozen Reader on one focused-maintenance formal snapshot.

This uses the existing local text-only AgentRunbook-R harness and a fixed
two-question maintenance workload.  It never rebuilds memory; the persisted
update snapshot is loaded and queried with the frozen 2048/12000 settings.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "runs/agentrunbook-r-native-small-20261014/local-text-only"
sys.path.insert(0, str(ADAPTER))
sys.path.append(str(ROOT / "third_party/LongMemEval-V2"))

from focused_runtime import configure, configure_loaded_query, reader_arguments, record_observed_runtime  # noqa: E402
from focused_reader_transport import configure_reader_transport


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=("web", "enterprise"), required=True)
    parser.add_argument("--policy", choices=("b3", "source_only", "source_overlay", "source_coalesced", "delta_guarded"), required=True)
    parser.add_argument("--output-root", default=None, help="Optional root for a repeat run; source snapshot remains the frozen formal branch.")
    parser.add_argument("--update-root", default=None, help="Directory containing literal_revision-<policy> branches; defaults to the frozen domain-update root.")
    parser.add_argument("--questions-path", default=None, help="Preselected fixed question JSONL; default is the original exposed diagnostic set.")
    parser.add_argument("--memory-dir", default=None, help="Explicit compatible persisted snapshot (including full-history branches).")
    parser.add_argument("--trajectories-path", default=None, help="Source trajectory provenance; loaded memory is never reconstructed here.")
    args = parser.parse_args()
    contract = configure(ROOT)
    # Import only after resolving adapter flags, including text-only mode.
    from evaluation import harness
    # Reuse the already mounted local tokenizer; otherwise transformers tries
    # to populate the full HF cache under /home/ly, which is quota-limited.
    os.environ.setdefault(
        "LME_EMBEDDING_TOKENIZER_MODEL",
        "/data/predator/ly/Mem/models/Qwen3-Embedding-8B",
    )
    os.environ.setdefault("HF_HOME", "/data/predator/ly/Mem/.cache/huggingface")

    formal_root = ROOT / "runs/focused-maintenance-v4/formal"
    branch_root = Path(args.update_root).resolve() if args.update_root else formal_root / f"{args.domain}-update"
    update_root = branch_root / f"literal_revision-{args.policy}"
    memory_dir = Path(args.memory_dir).resolve() if args.memory_dir else update_root / "memory_state"
    if not memory_dir.is_dir():
        raise SystemExit(f"missing persisted update memory: {memory_dir}")
    out = ((Path(args.output_root).resolve() / f"{args.domain}-{args.policy}")
           if args.output_root else update_root / "revision_reader")
    if out.exists():
        raise SystemExit(f"refusing to overwrite existing Reader output: {out}")
    runtime = out / "runtime_inputs"
    runtime.mkdir(parents=True)
    configure_reader_transport(harness, out)

    questions = load_jsonl(Path(args.questions_path) if args.questions_path else formal_root / "query-data" / args.domain / "questions.jsonl")
    # The enterprise formal snapshot legitimately reuses a historical build
    # whose insertion order differs from the data Manifest.  Query exactly
    # the persisted order; every method branch is checked against its own
    # identical matched snapshot.
    ids = json.loads((memory_dir / "index.json").read_text())["inserted_trajectory_ids"]
    (runtime / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n")
    (runtime / "haystack.json").write_text(json.dumps({q["id"]: ids for q in questions}, indent=2) + "\n")

    # Use the saved non-query construction configuration as the requested
    # config; harness validates it against the loaded snapshot.
    config_path = memory_dir / "memory_config.json"
    traj_path = (Path(args.trajectories_path).resolve() if args.trajectories_path else
                 ROOT / "runs/dev-adapted-text-v1/data-expanded20" / args.domain / "trajectories.jsonl")
    argv = [
        "evaluation.harness",
        "--domain", args.domain,
        "--questions-path", str(runtime / "questions.json"),
        "--haystack-path", str(runtime / "haystack.json"),
        "--trajectories-path", str(traj_path),
        "--memory-config-path", str(config_path),
        "--output-dir", str(out),
        "--load-memory-dir", str(memory_dir),
        "--base-url", "http://localhost:8023/v1",
        "--api-key-env", "OPENAI_API_KEY",
        "--prompt-build-max-workers", "1",
        "--reader-max-concurrent-requests", "1",
        "--evaluator-model", "",
        "--evaluator-base-url", "",
    ]
    argv.extend(reader_arguments(contract))
    record_observed_runtime(ROOT, out, contract, argv)
    old = sys.argv
    original_load = harness.load_memory
    try:
        def load_query_memory(*load_args, **load_kwargs):
            memory = original_load(*load_args, **load_kwargs)
            return configure_loaded_query(memory, contract, out)
        harness.load_memory = load_query_memory
        sys.argv = argv
        harness.main()
    finally:
        sys.argv = old
        harness.load_memory = original_load


if __name__ == "__main__":
    main()
