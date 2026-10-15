#!/usr/bin/env python3
"""Real local-model continuous-arrival probe for adapted AgentRunbook-R.

This runner starts each method from the same persisted full snapshot, then
appends controlled same-trajectory observations one at a time in a single
process.  Every arrival performs real controller/embedding work, saves a
queryable artifact, reloads it, and executes a retrieval probe.  It is a
text-only/adapted mechanism result, not an official LongMemEval stream.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "runs/agentrunbook-r-native-small-20261014/local-text-only"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(ROOT / "tools"))

from memory_modules.memory import load_memory, save_memory
from memory_modules.agentrunbook_r import AgentRunbookR
from run_agentrunbook_updates import (
    UpdateRunbook,
    digest,
    jsonl,
    request_key,
    replace_partition,
    seed_caches,
)


def _sum_known(rows, key):
    values = [row.get(key) for row in rows]
    return None if any(value is None for value in values) else sum(int(value or 0) for value in values)


def _percentile(values, q):
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), q, method="linear"))


def _seed_without_target(memory, target_id: str, target_goal: str) -> None:
    """Restore legal shared-snapshot caches, excluding target/future requests."""
    seed_caches(memory)
    safe = {}
    for record in jsonl(memory.workspace_dir / "model_calls.jsonl"):
        if record.get("query_invocation_id") or record.get("channel") != "controller" or record.get("status") != "success":
            continue
        if not record.get("messages") or record.get("finish_reason") != "stop":
            continue
        messages_blob = json.dumps(record["messages"], ensure_ascii=False)
        if target_id in messages_blob or target_goal in messages_blob:
            continue
        key = request_key(record["messages"], record["model"], record["base_url"],
                          record["max_completion_tokens"], record["temperature"],
                          record["top_p"], record["top_k"], record["enable_thinking"])
        safe[key] = record["response_text"]
    memory.exact_requests = safe


def _remove_target_trajectory(memory, target_id: str) -> dict:
    """Remove one trajectory only from the isolated method clone."""
    if target_id not in memory.inserted_trajectory_ids:
        raise ValueError(f"target trajectory not in starting snapshot: {target_id}")
    before = {}
    for entries_name, vectors_name in (
        ("raw_state_entries", "raw_state_embeddings"),
        ("event_entries", "event_embeddings"),
        ("procedure_note_entries", "procedure_note_embeddings"),
        ("hint_note_entries", "hint_note_embeddings"),
    ):
        entries = list(getattr(memory, entries_name))
        vectors = np.asarray(getattr(memory, vectors_name))
        if vectors.shape[0] != len(entries):
            raise ValueError(f"unaligned entries/vectors before target removal: {entries_name}")
        keep = np.asarray([row.get("trajectory_id") != target_id for row in entries], dtype=bool)
        before[entries_name] = [digest(row) for row, retain in zip(entries, keep) if retain]
        setattr(memory, entries_name, [row for row, retain in zip(entries, keep) if retain])
        setattr(memory, vectors_name, vectors[keep].copy())
    memory.inserted_trajectory_ids = [tid for tid in memory.inserted_trajectory_ids if tid != target_id]
    target_dir = (memory.workspace_dir / "trajectories" / target_id).resolve()
    if memory.workspace_dir.resolve() not in target_dir.parents:
        raise ValueError(f"unsafe trajectory removal path: {target_dir}")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    memory._refresh_runtime_query_summary()
    save_memory(memory, memory.workspace_dir)
    loaded = load_memory(memory.workspace_dir)
    if target_id in loaded.inserted_trajectory_ids:
        raise RuntimeError("removed trajectory reappeared after reload")
    for name in ("raw_state_entries", "event_entries", "procedure_note_entries", "hint_note_entries"):
        if any(row.get("trajectory_id") == target_id for row in getattr(loaded, name)):
            raise RuntimeError(f"target trajectory remains in persisted pool {name}")
    return before


def _prefix_for_events(full: dict, event_count: int) -> dict:
    prefix = copy.deepcopy(full)
    prefix["states"] = copy.deepcopy(full["states"][: event_count + 1])
    prefix["actions"] = [state.get("action") or "<none>" for state in prefix["states"][1:]]
    prefix["outcome"] = None
    return prefix


def _materialize_prefix(source: Path, workspace: Path, prefix: dict) -> None:
    """Copy only screenshots referenced by the arrived prefix into this clone."""
    target_dir = workspace / "trajectories" / str(prefix["id"])
    source_dir = source / "trajectories" / str(prefix["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    keep = {str(Path(state["screenshot"])) for state in prefix["states"] if state.get("screenshot")}
    for rel in sorted(keep):
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError(f"unsafe screenshot reference: {rel}")
        src, dst = source_dir / rel_path, target_dir / rel_path
        if not src.is_file():
            raise FileNotFoundError(f"source screenshot missing for arrived prefix: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for path in target_dir.rglob("*"):
        if path.is_file() and path.name != "trajectory.json":
            rel = str(path.relative_to(target_dir))
            if rel not in keep:
                path.unlink()
    for path in sorted(target_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    (target_dir / "trajectory.json").write_text(json.dumps(prefix, ensure_ascii=False, indent=2) + "\n")


def _stream_quality(memory, target_id: str, prefix: dict, previous_event_count: int, other_before: dict) -> dict:
    states = prefix["states"]
    target_raw = [x for x in memory.raw_state_entries if x.get("trajectory_id") == target_id]
    target_events = [x for x in memory.event_entries if x.get("trajectory_id") == target_id]
    target_procedure = [x for x in memory.procedure_note_entries if x.get("trajectory_id") == target_id]
    target_hints = [x for x in memory.hint_note_entries if x.get("trajectory_id") == target_id]
    expected_ids = {f"event_{states[i]['state_index']:04d}_{states[i + 1]['state_index']:04d}" for i in range(len(states) - 1)}
    actual_ids = {str(x.get("event_id")) for x in target_events}
    expected_pairs = {(int(states[i]["state_index"]), int(states[i + 1]["state_index"])) for i in range(len(states) - 1)}
    actual_pairs = {(int(x.get("pre_state_index", -1)), int(x.get("post_state_index", -1))) for x in target_events}
    events_by_id = {str(x.get("event_id")): x for x in target_events}
    action_mappings = []
    for i in range(len(states) - 1):
        event_id = f"event_{states[i]['state_index']:04d}_{states[i + 1]['state_index']:04d}"
        source_action = str(states[i + 1].get("action") or "<none>").strip()
        emitted_action = str(events_by_id.get(event_id, {}).get("local_action") or "")
        action_mappings.append(source_action == "<none>" and emitted_action == "<none>" or
                               source_action != "<none>" and source_action in emitted_action)
    raw_covered = {int(i) for item in target_raw for i in item.get("slice_state_indexes", [])}
    prefix_indexes = {int(x["state_index"]) for x in states}
    future_refs = sorted(raw_covered - prefix_indexes)
    future_events = [x.get("event_id") for x in target_events if int(x.get("post_state_index", -1)) > int(states[-1]["state_index"])]
    raw_text_blob = "\n".join(str(x.get("slice_axtree_text") or "") for x in target_raw)
    source_facts_retained = all(
        not str(state.get("text") or "").strip()
        or str(state.get("text")).strip()[:80] in raw_text_blob
        for state in states
    )
    current_other = {}
    for name in ("raw_state_entries", "event_entries", "procedure_note_entries", "hint_note_entries"):
        current_other[name] = [digest(row) for row in getattr(memory, name) if row.get("trajectory_id") != target_id]
    other_preserved = current_other == other_before
    passed = (
        target_id in memory.inserted_trajectory_ids
        and len(target_raw) == len(states)
        and prefix_indexes.issubset(raw_covered)
        and not future_refs
        and actual_ids == expected_ids
        and len(target_events) == len(expected_ids)
        and actual_pairs == expected_pairs
        and all(action_mappings)
        and not future_events
        and source_facts_retained
        and len(target_procedure) == 1
        and len(target_hints) == 1
        and prefix.get("outcome") is None
        and len(prefix.get("actions", [])) == len(states) - 1
        and other_preserved
        and len(actual_ids) >= previous_event_count
    )
    return {
        "quality_pass": passed,
        "arrived_state_indexes": sorted(prefix_indexes),
        "raw_covered_state_indexes": sorted(raw_covered),
        "future_raw_state_refs": future_refs,
        "expected_event_ids": sorted(expected_ids),
        "actual_event_ids": sorted(actual_ids),
        "future_event_refs": future_events,
        "source_action_mappings_pass": all(action_mappings),
        "source_facts_retained": source_facts_retained,
        "prior_event_count_retained": len(actual_ids) >= previous_event_count,
        "notes_present": len(target_procedure) == 1 and len(target_hints) == 1,
        "target_outcome_hidden": prefix.get("outcome") is None,
        "unmodified_trajectories_preserved": other_preserved,
    }


def _set_runtime_env(source: Path) -> None:
    config_path = source / "construction_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        if config.get("event_max_input_tokens"):
            os.environ["LME_EVENT_MAX_INPUT_TOKENS"] = str(config["event_max_input_tokens"])
    for key, value in {
        "LME_TEXT_ONLY": "1",
        "LME_EVENT_GROUP_SIZE": "2",
        "LME_EVENT_OUTPUT_TOKENS": "2048",
        "LME_EVENT_CONCURRENCY": "1",
        "LME_REUSE_BUILD_EMBEDDING": "1",
        "LME_RECORD_FULL_REQUESTS": "1",
        "LME_EMBEDDING_TOKENIZER_MODEL": "/data/predator/ly/Mem/models/Qwen3-Embedding-8B",
    }.items():
        os.environ[key] = value


def _run_method(source: Path, out: Path, policy: str, trajectory_id: str, batch_sizes: list[int]) -> dict:
    method_out = out / policy
    method_out.mkdir(parents=True, exist_ok=False)
    workspace = method_out / "memory_state"
    shutil.copytree(source, workspace)
    full_trajectory = json.loads((source / "trajectories" / trajectory_id / "trajectory.json").read_text())
    if len(full_trajectory.get("states", [])) < sum(batch_sizes) + 1:
        raise ValueError("batch schedule exceeds available source transitions")
    memory = load_memory(workspace)
    memory.__class__ = UpdateRunbook
    memory.update_policy = policy
    memory.configure_runtime()
    base_ids = set(memory.inserted_trajectory_ids) - {trajectory_id}
    other_before = _remove_target_trajectory(memory, trajectory_id)
    memory = load_memory(workspace)
    memory.__class__ = UpdateRunbook
    memory.update_policy = policy
    memory.configure_runtime()
    _seed_without_target(memory, trajectory_id, str(full_trajectory.get("goal") or ""))
    if set(memory.inserted_trajectory_ids) != base_ids:
        raise RuntimeError("common starting snapshot does not match target-excluded trajectory set")

    rows = []
    total_update_s = 0.0
    cumulative_events = 0
    arrival_latencies_by_event = []
    stream_started_ns = time.perf_counter_ns()
    for arrival_index, event_batch_size in enumerate(batch_sizes, 1):
        # Batch sizes 1, 2, 3 are distinct arrival loads.  The following
        # source states are only materialized after this batch is declared arrived.
        memory.__class__ = UpdateRunbook
        memory.update_policy = policy
        memory.configure_runtime()
        memory.update_event_outputs = 0
        memory.update_notes_regenerated = 0
        previous_event_count = cumulative_events
        cumulative_events += event_batch_size
        arrival_started_ns = time.perf_counter_ns()
        prefix = _prefix_for_events(full_trajectory, cumulative_events)
        if len(prefix["states"]) != cumulative_events + 1 or prefix.get("outcome") is not None:
            raise RuntimeError("prefix materialization violated arrival frontier")
        _materialize_prefix(source, workspace, prefix)
        (method_out / f"arrival_{arrival_index:02d}_input.json").write_text(
            json.dumps({"event_batch_size": event_batch_size, "cumulative_events": cumulative_events,
                        "trajectory": prefix}, ensure_ascii=False, indent=2) + "\n"
        )
        before_call_count = len(jsonl(workspace / "model_calls.jsonl"))
        try:
            bundle = memory._build_trajectory_artifact_bundle(
                trajectory_dir=workspace / "trajectories" / trajectory_id,
                simplified_trajectory=prefix,
            )
            replace_partition(memory, prefix, bundle)
            save_memory(memory, workspace)
            published = load_memory(workspace)
            publish_s = (time.perf_counter_ns() - arrival_started_ns) / 1e9
            total_update_s += publish_s
            after_build_calls = jsonl(workspace / "model_calls.jsonl")[before_call_count:]
            controller = [r for r in after_build_calls if r.get("channel") == "controller"]
            embedding = [r for r in after_build_calls if r.get("channel") == "embedding"]
            quality = _stream_quality(published, trajectory_id, prefix, previous_event_count, other_before)
            # Query on the reloaded artifact to verify real retrieval after publication.
            probe_started = time.perf_counter()
            probe_error = None
            probe_items = []
            try:
                published.configure_runtime()
                published.set_query_context(query_invocation_id=f"stream-{policy}-{arrival_index}")
                probe_items = published.query(f"What has been observed so far while doing this task: {prefix['goal']}")
            except Exception as exc:
                probe_error = f"{type(exc).__name__}: {exc}"
            finally:
                published.clear_query_context()
            probe_s = time.perf_counter() - probe_started
            probe_call_rows = jsonl(workspace / "model_calls.jsonl")[before_call_count + len(after_build_calls):]
            probe_controller = [r for r in probe_call_rows if r.get("channel") == "controller"]
            probe_embedding = [r for r in probe_call_rows if r.get("channel") == "embedding"]
            for _ in range(event_batch_size):
                arrival_latencies_by_event.append(publish_s)
            row = {
                "policy": policy,
                "arrival_index": arrival_index,
                "trajectory_id": trajectory_id,
                "arrived_events_this_batch": event_batch_size,
                "cumulative_arrived_events": cumulative_events,
                "source_state_indexes_arrived": [s["state_index"] for s in prefix["states"]],
                "newly_arrived_state_indexes": ([prefix["states"][0]["state_index"]] if previous_event_count == 0 else []) +
                                                   [s["state_index"] for s in prefix["states"]
                                                    if int(s["state_index"]) > int(full_trajectory["states"][previous_event_count]["state_index"])],
                "arrival_to_queryable_s": publish_s,
                "artifact_save_reload_included": True,
                "retrieval_probe_s": probe_s,
                "retrieval_probe_ok": bool(probe_items) and probe_error is None,
                "retrieval_probe_items": len(probe_items),
                "retrieval_probe_error": probe_error,
                "controller_calls": len(controller),
                "embedding_calls": len(embedding),
                "controller_input_tokens": _sum_known(controller, "prompt_tokens"),
                "controller_output_tokens": _sum_known(controller, "completion_tokens"),
                "embedding_input_tokens": _sum_known(embedding, "prompt_tokens"),
                "embedding_vectors": sum(int(r.get("input_text_count") or 0) for r in embedding),
                "failed_calls": sum(r.get("status") == "failed" for r in controller + embedding),
                "probe_controller_calls": len(probe_controller),
                "probe_embedding_calls": len(probe_embedding),
                "reextracted_event_outputs": int(memory.update_event_outputs),
                "regenerated_notes": int(memory.update_notes_regenerated),
                "quality": quality,
                "quality_pass": bool(quality.get("quality_pass")) and bool(probe_items) and probe_error is None,
                "raw_path": str(method_out),
            }
            rows.append(row)
            (method_out / "arrival_metrics.jsonl").open("a").write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as exc:
            elapsed = (time.perf_counter_ns() - arrival_started_ns) / 1e9
            row = {
                "policy": policy,
                "arrival_index": arrival_index,
                "trajectory_id": trajectory_id,
                "status": "failed",
                "arrival_to_queryable_s": elapsed,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "raw_path": str(method_out),
            }
            rows.append(row)
            (method_out / "arrival_metrics.jsonl").open("a").write(json.dumps(row, ensure_ascii=False) + "\n")
            # Preserve the failed arrival and stop this method rather than
            # allowing a later prefix to mask a failed/unpublished frontier.
            break
    stream_wall_s = (time.perf_counter_ns() - stream_started_ns) / 1e9
    freshness = arrival_latencies_by_event
    published_events = sum(int(r.get("arrived_events_this_batch") or 0) for r in rows if r.get("status", "completed") != "failed")
    summary = {
        "policy": policy,
        "trajectory_id": trajectory_id,
        "arrival_count": len(batch_sizes),
        "batch_sizes_events": list(batch_sizes),
        "completed_arrivals": sum(r.get("status", "completed") != "failed" for r in rows),
        "failed_arrivals": sum(r.get("status") == "failed" for r in rows) + (len(batch_sizes) - len(rows)),
        "stream_wall_s_including_retrieval_probes": stream_wall_s,
        "update_publish_s_total": total_update_s,
        "freshness_p50_s": _percentile(freshness, 50),
        "freshness_p95_s": _percentile(freshness, 95),
        "freshness_sample_unit": "each newly arrived transition; same-batch events share publication time",
        "goodput_new_events_per_publish_s": published_events / total_update_s if total_update_s else None,
        "controller_calls": sum(int(r.get("controller_calls") or 0) for r in rows),
        "controller_input_tokens": sum(int(r.get("controller_input_tokens") or 0) for r in rows),
        "controller_output_tokens": sum(int(r.get("controller_output_tokens") or 0) for r in rows),
        "embedding_calls": sum(int(r.get("embedding_calls") or 0) for r in rows),
        "embedding_vectors": sum(int(r.get("embedding_vectors") or 0) for r in rows),
        "quality_passes": sum(bool(r.get("quality_pass")) for r in rows),
        "retrieval_probe_passes": sum(bool(r.get("retrieval_probe_ok")) for r in rows),
        "scope": "local_text_only_adapted_closed_loop_source_prefix_stream",
        "qa_status": "source_grounded_checks_only; official_judge_pending",
        "raw_path": str(method_out),
    }
    (method_out / "stream_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trajectory-id", default="0ab99e0c")
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--methods", default="b3,ours")
    args = parser.parse_args()
    args.source = args.source.resolve()
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error(f"refuse to overwrite existing output directory: {args.output}")
    if len(args.batch_sizes) < 3 or any(size < 1 for size in args.batch_sizes):
        parser.error("provide at least three positive batch sizes")
    _set_runtime_env(args.source)
    args.output.mkdir(parents=True)
    manifest = {
        "source": str(args.source),
        "trajectory_id": args.trajectory_id,
        "batch_sizes_events": args.batch_sizes,
        "cumulative_events": list(np.cumsum(args.batch_sizes).astype(int)),
        "methods": [x.strip() for x in args.methods.split(",") if x.strip()],
        "protocol": "closed-loop source-prefix arrivals with batch sizes 1,2,3; no later trajectory states or outcome are materialized until that batch arrives; each method owns an independent clone; actual local Qwen/Embedding; save/reload/query probe",
        "scope": "text-only/adapted controlled source-replay stream; not official LongMemEval streaming",
        "source_sha256": {
            name: hashlib.sha256((args.source / name).read_bytes()).hexdigest()
            for name in ("index.json", "memory_config.json", "construction_config.json", "pools/event_pool.jsonl",
                         "pools/raw_state_pool.jsonl", f"trajectories/{args.trajectory_id}/trajectory.json")
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    summaries = []
    for policy in manifest["methods"]:
        if policy not in {"b3", "ours"}:
            parser.error("methods must be b3,ours")
        summaries.append(_run_method(args.source, args.output, policy, args.trajectory_id, args.batch_sizes))
    (args.output / "stream_summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
