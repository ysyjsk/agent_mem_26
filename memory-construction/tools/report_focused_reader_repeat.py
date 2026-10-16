#!/usr/bin/env python3
"""Record one detached fixed-Reader repeat without changing the frozen main table."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPEAT = ROOT / "runs/focused-maintenance-v4/repeat-20261016"
OUT = ROOT / "results/tables/focused-maintenance-v4/formal_reader_repeat_20261016.csv"

def main() -> None:
    rows = []
    for path in sorted(REPEAT.glob("*/aggregated_metrics.json")):
        data = json.loads(path.read_text())
        branch = path.parent.name
        domain, policy = branch.split("-", 1)
        status = data["answer_status"]
        rows.append({
            "repeat_id": "formal-reader-repeat-20261016",
            "domain": domain, "policy": policy,
            "correct": status["correct"], "scored": status["scored"],
            "complete_parseable": status["complete_parseable"],
            "truncated": status["truncated"],
            "service_failure": status["service_failure"],
            "parse_failure": status["parse_failure"],
            "reader_input_tokens": data["tokens"]["prompt_tokens"],
            "reader_output_tokens": data["tokens"]["completion_tokens"],
            "reader_total_tokens": data["tokens"]["total_tokens"],
            "prompt_build_s": data["timing"]["prompt_build_wall_seconds"],
            "reader_generation_s": data["timing"]["reader_generation_wall_seconds"],
            "raw_path": str(path.parent.relative_to(ROOT)),
        })
    fields = list(rows[0]) if rows else []
    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "output": str(OUT)}))

if __name__ == "__main__":
    main()
