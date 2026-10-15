#!/usr/bin/env python3
"""Materialize a one-question/one-trajectory LongMemEval-V2 smoke fixture.

The official V2 release stores trajectory screenshots in multi-gigabyte tar
archives.  This fixture deliberately keeps the official JSON schema and
runner, but substitutes one existing released question screenshot for each
trajectory state so the memory baseline can be exercised text-only without
downloading those archives.  The manifest calls out that substitution; the
fixture is exploratory and never a formal QA result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        default="memory-construction/third_party/LongMemEval-V2/data/longmemeval-v2",
    )
    parser.add_argument(
        "--out-root",
        default="memory-construction/runs/lme-v2-micro-20261013/data-root",
    )
    parser.add_argument("--question-id", default="01307e07")
    parser.add_argument("--trajectory-id", default="00332982")
    parser.add_argument("--placeholder-screenshot", default="question_screenshots/f2b221fd.png")
    parser.add_argument("--max-states", type=int, default=None, help="Optional prefix limit for an exploratory baseline smoke")
    args = parser.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    questions = read_jsonl(source_root / "questions.jsonl")
    question = next((row for row in questions if row.get("id") == args.question_id), None)
    if question is None:
        raise SystemExit(f"question id not found: {args.question_id}")
    trajectories = read_jsonl(source_root / "trajectories.jsonl")
    trajectory = next((row for row in trajectories if row.get("id") == args.trajectory_id), None)
    if trajectory is None:
        raise SystemExit(f"trajectory id not found: {args.trajectory_id}")
    placeholder_source = source_root / args.placeholder_screenshot
    if not placeholder_source.is_file():
        raise SystemExit(f"placeholder screenshot not found: {placeholder_source}")

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "haystacks").mkdir(parents=True, exist_ok=True)
    (out_root / "question_screenshots").mkdir(parents=True, exist_ok=True)
    placeholder_target = out_root / args.placeholder_screenshot
    placeholder_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(placeholder_source, placeholder_target)

    # Keep one official question but remove its optional image so all reader
    # calls use the text-only local endpoint.
    question_copy = dict(question)
    question_copy["image"] = None
    trajectory_copy = json.loads(json.dumps(trajectory))
    states = trajectory_copy.get("states", [])
    if args.max_states is not None:
        states = states[: max(1, int(args.max_states))]
        trajectory_copy["states"] = states
        trajectory_copy["outcome"] = None
    for state in states:
        if isinstance(state, dict):
            state["screenshot"] = args.placeholder_screenshot

    (out_root / "questions.jsonl").write_text(
        json.dumps(question_copy, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_root / "trajectories.jsonl").write_text(
        json.dumps(trajectory_copy, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps({args.question_id: [args.trajectory_id]}, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "status": "prepared",
        "source_root": str(source_root),
        "out_root": str(out_root),
        "question_id": args.question_id,
        "trajectory_id": args.trajectory_id,
        "source_question_count": len(questions),
        "source_trajectory_count": len(trajectories),
        "selected_state_count": len(states),
        "source_state_count": len(trajectory.get("states", [])),
        "prefix_truncated": len(states) < len(trajectory.get("states", [])),
        "source_question_sha256": sha256_file(source_root / "questions.jsonl"),
        "source_trajectories_sha256": sha256_file(source_root / "trajectories.jsonl"),
        "fixture_question_sha256": sha256_file(out_root / "questions.jsonl"),
        "fixture_trajectory_sha256": sha256_file(out_root / "trajectories.jsonl"),
        "semantics": {
            "official_runner": True,
            "official_QA": False,
            "text_only": True,
            "vision_omitted": True,
            "screenshot_substitution": args.placeholder_screenshot,
            "one_question_one_trajectory_subset": True,
        },
    }
    (out_root.parent / "fixture_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
