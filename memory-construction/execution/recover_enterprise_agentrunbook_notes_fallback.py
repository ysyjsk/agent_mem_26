#!/usr/bin/env python3
"""Recover one failed full-Small AgentRunbook expansion with note fallback.

The registered enterprise expansion reached the final long trajectory's event
groups but failed during Notes generation because the local chat service ran
out of CUDA memory.  This recovery keeps the registered event extraction and
uses AgentRunbook-R's existing deterministic note fallback for this affected
trajectory only.  It does not change the frozen method for other units.
"""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "runs/agentrunbook-r-native-small-20261014/local-text-only"
sys.path.insert(0, str(LOCAL))
sys.path.insert(0, str(ROOT / "tools"))


# Import the registry module first; memory.py intentionally imports the
# AgentRunbook class at its tail, so importing the class directly would create
# a circular-import failure in this recovery-only entrypoint.
from memory_modules import memory as _memory_registry  # noqa: E402,F401
from memory_modules.agentrunbook_r import AgentRunbookR  # noqa: E402


def _fallback_entries(self, *, trajectory_dir, simplified_trajectory):
    try:
        return _fallback_entries.original(
            self, trajectory_dir=trajectory_dir, simplified_trajectory=simplified_trajectory
        )
    except Exception as exc:
        # _call_controller_text has already recorded the failed request.  Add
        # a non-model recovery marker and preserve the same native fallback
        # representation used by the implementation for parse failures.
        marker = {
            "channel": "note_generation",
            "status": "deterministic_fallback",
            "trajectory_id": simplified_trajectory["id"],
            "reason": repr(exc),
            "recovery": "enterprise-agentrunbook-notes-fallback-20261016",
        }
        self._append_model_call_metric(marker)
        procedure = self._fallback_note_entry(
            simplified_trajectory=simplified_trajectory, note_type="procedure"
        )
        hint = self._fallback_note_entry(
            simplified_trajectory=simplified_trajectory, note_type="hint"
        )
        procedure_entry = {
            "entry_id": f"{simplified_trajectory['id']}:procedure_note",
            "trajectory_id": simplified_trajectory["id"],
            "note_type": "procedure",
            "title": procedure["title"],
            "description": procedure["description"],
            "content": procedure["content"],
            "note_text": (
                f"Title: {procedure['title']}\n"
                f"Description: {procedure['description']}\n"
                f"{procedure['content']}"
            ).strip(),
        }
        hint_entry = {
            "entry_id": f"{simplified_trajectory['id']}:hint_note",
            "trajectory_id": simplified_trajectory["id"],
            "note_type": "hint",
            "title": hint["title"],
            "description": hint["description"],
            "content": hint["content"],
            "note_text": (
                f"Title: {hint['title']}\n"
                f"Description: {hint['description']}\n"
                f"{hint['content']}"
            ).strip(),
        }
        return procedure_entry, hint_entry


_fallback_entries.original = AgentRunbookR._build_note_entries
AgentRunbookR._build_note_entries = _fallback_entries

receipt = {
    "version": "enterprise-agentrunbook-notes-fallback-20261016-v1",
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "affected_unit": "expand-enterprise-agentrunbook",
    "trajectory": "02dad10c",
    "reason": "second CUDA OOM during final long-trajectory Notes request after event groups reached state 100",
    "scope": "only the failed enterprise AgentRunbook expansion; successful web and independent RAG stages reused",
    "fallback": "existing AgentRunbook-R deterministic procedure/hint note fallback; no replacement model call",
    "quality_boundary": "event/source checks remain applicable; generated Notes require separate semantic review and are not claimed equivalent",
    "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
receipt_path = ROOT / "execution/recovery/enterprise-agentrunbook-notes-fallback-20261016-v1.json"
if not receipt_path.exists():
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

sys.argv = [
    str(ROOT / "tools/extend_full_small_memory.py"),
    "--domain",
    "enterprise",
    "--source",
    str(ROOT / "runs/focused-maintenance-v4/formal/matched-enterprise/memory_state"),
    "--output",
    str(ROOT / "runs/focused-maintenance-v4/full-small-recovery-v1/initial/enterprise-agentrunbook"),
    "--manifest",
    str(ROOT / "manifests/focused-maintenance-v4/full-small-recovery-v1/data_manifest.json"),
]
runpy.run_path(str(ROOT / "tools/extend_full_small_memory.py"), run_name="__main__")
