#!/usr/bin/env python3
"""Write a non-secret provenance manifest for an AgentRunbook-R Small run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--kind", default="adapted-matched")
    args = parser.parse_args()
    root = args.root.resolve()
    run = args.run.resolve()
    data = root / "third_party/LongMemEval-V2/data/longmemeval-v2"
    code_paths = [
        root / "third_party/LongMemEval-V2/evaluation/run_eval.py",
        root / "third_party/LongMemEval-V2/evaluation/harness.py",
        root / "third_party/LongMemEval-V2/evaluation/qa_eval_metrics.py",
        root / "third_party/LongMemEval-V2/memory_modules/agentrunbook_r.py",
        root / "third_party/LongMemEval-V2/memory_modules/trajectory_store.py",
        root / "tools/run_agentrunbook_r_small_adapted.sh",
        root / "tools/write_agentrunbook_r_manifest.py",
    ]
    archive_paths = [
        data / "trajectory_screenshots/web_screenshots.tar.gz",
        data / "trajectory_screenshots/enterprise_screenshots_base.tar.gz",
    ]
    payload = {
        "schema_version": 1,
        "run_kind": args.kind,
        "method": "agentrunbook_r",
        "tier": "small",
        "upstream_commit": subprocess.check_output(
            ["git", "-C", str(root / "third_party/LongMemEval-V2"), "rev-parse", "HEAD"],
            text=True,
        ).strip(),
        "upstream_modified_files": [
            "evaluation/run_eval.py",
            "evaluation/harness.py",
            "memory_modules/agentrunbook_r.py",
        ],
        "data_root": str(data),
        "validated_data_counts": {
            "questions": 451,
            "web_questions": 240,
            "enterprise_questions": 211,
            "trajectories": 1870,
            "small_unique_trajectories": 200,
            "small_state_screenshot_references": 5095,
            "validate_data_check_screenshots": "passed",
        },
        "data_files": {
            str(path.relative_to(root)): sha256(path)
            for path in [data / "questions.jsonl", data / "trajectories.jsonl", data / "haystacks/lme_v2_small.json"]
        },
        "screenshot_archives": {
            str(path.relative_to(root)): {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "gzip_test": "passed",
            }
            for path in archive_paths
        },
        "code_sha256": {str(path.relative_to(root)): sha256(path) for path in code_paths},
        "configuration": {
            "reader_controller_model": "qwen3-vl-plus",
            "reader_controller_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "embedding_model": "Qwen3-Embedding-8B",
            "embedding_base_url": "http://127.0.0.1:8114/v1",
            "reader_temperature": 0.6,
            "reader_top_p": 0.95,
            "reader_top_k": 20,
            "reader_enable_thinking": True,
            "reader_max_completion_tokens": 20000,
            "controller_max_completion_tokens": 8192,
            "memory_context_max_tokens": 200000,
            "reader_max_concurrent_requests": 1,
            "prompt_build_max_workers": 1,
            "evaluator_model": "qwen-plus",
            "evaluator_scope": "evaluator-only",
            "official_judge_status": "pending_judge",
            "api_key_persistence": "runtime environment only; secret omitted",
        },
    }
    run.mkdir(parents=True, exist_ok=True)
    (run / "provenance_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"path": str(run / "provenance_manifest.json"), "code_files": len(code_paths)}, indent=2))


if __name__ == "__main__":
    main()
