#!/usr/bin/env python3
"""Minimal AgentRunbook-R reproduction smoke.

This intentionally skips the official QA evaluator and model calls.  It reads
the pinned LongMemEval-V2 trajectory export, normalizes two records through our
adapter, and writes an auditable text-only compatibility report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from workflow_memory.adapters.longmemeval_v2 import LongMemEvalV2Adapter  # noqa: E402
from workflow_memory.ir import normalize_trajectory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "third_party/LongMemEval-V2/data/longmemeval-v2/trajectories.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/agentrunbook-r-smoke/report.json")
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()
    records = LongMemEvalV2Adapter(args.data).records()[: max(1, args.limit)]
    rows = []
    for record in records:
        events = normalize_trajectory(record)
        rows.append({
            "trajectory_id": record.get("id"),
            "domain": record.get("domain"),
            "events": len(events),
            "first_event_id": events[0].event_id if events else None,
            "last_event_id": events[-1].event_id if events else None,
            "text_only": True,
        })
    report = {
        "status": "completed",
        "official_harness": "LongMemEval-V2 AgentRunbook-R",
        "official_commit": "2cc8c540bdb87fe6761629b585e727e1c4704520",
        "evaluation": "skipped",
        "model_calls": 0,
        "text_only": True,
        "data_path": str(args.data),
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
