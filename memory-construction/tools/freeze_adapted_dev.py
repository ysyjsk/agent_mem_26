#!/usr/bin/env python3
"""Freeze two shared-haystack, full-trajectory text-only development sets."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/LongMemEval-V2/data/longmemeval-v2"
DEST = ROOT / "runs/dev-adapted-text-v1/data"
ANCHORS = {
    "enterprise": {
        "0d07143c": "49f98e9e",  # default asset sort field
        "25b00876": "0c80a9e1",  # expense-line workflow field
        "87711b62": "0ab99e0c",  # change request filter option
        "ad903be2": "12c22166",  # Apple Watch delivery time
    },
    "web": {
        "11dac74b": "2e8f6477",  # reply banner
        "631667c9": "1ad1af4b",  # moderated forum Toolbox
        "8c55d6bc": "2a99f536",  # product-views report banner
        "99ae54d1": "3331c568",  # profile edit link
    },
}
DISTRACTORS = {"enterprise": ["276f9dff"], "web": ["4ba5e9cb"]}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    if DEST.exists():
        raise RuntimeError(f"Refusing to change frozen dev set: {DEST}")
    questions = {x["id"]: x for x in map(json.loads, (SOURCE / "questions.jsonl").open())}
    official = json.loads((SOURCE / "haystacks/lme_v2_small.json").read_text())
    wanted = {tid for anchors in ANCHORS.values() for tid in anchors.values()}
    wanted.update(tid for extras in DISTRACTORS.values() for tid in extras)
    trajectories = {t["id"]: t for t in map(json.loads, (SOURCE / "trajectories.jsonl").open()) if t["id"] in wanted}
    assert set(trajectories) == wanted
    for domain, anchors in ANCHORS.items():
        chosen = set(anchors.values()) | set(DISTRACTORS[domain])
        first_qid = next(iter(anchors))
        ordered = [tid for tid in official[first_qid] if tid in chosen]
        assert len(ordered) == len(chosen)
        assert all(set(ordered).issubset(official[qid]) for qid in anchors)
        assert all(questions[qid]["domain"] == domain for qid in anchors)
        base = DEST / domain
        base.mkdir(parents=True)
        (base / "haystacks").mkdir()
        (base / "screenshots").symlink_to(SOURCE / "screenshots", target_is_directory=True)
        (base / "question_screenshots").symlink_to(SOURCE / "question_screenshots", target_is_directory=True)
        with (base / "questions.jsonl").open("w") as out:
            for qid in anchors:
                out.write(json.dumps(questions[qid], ensure_ascii=False) + "\n")
        with (base / "trajectories.jsonl").open("w") as out:
            for tid in ordered:
                out.write(json.dumps(trajectories[tid], ensure_ascii=False) + "\n")
        write(base / "haystacks/lme_v2_small.json", {qid: ordered for qid in anchors})
        evidence = []
        for qid, tid in anchors.items():
            t = trajectories[tid]
            gold = questions[qid]["answer"].casefold()
            states = [i for i, state in enumerate(t["states"]) if gold in str(state.get("accessibility_tree", "")).casefold()]
            assert states, f"No literal accessibility-tree evidence for {qid} in {tid}"
            evidence.append({"question_id": qid, "question_type": questions[qid]["question_type"], "answer_evidence_trajectory": tid, "evidence_state_indices": states, "selection_reason": "Answer literal in official full-trajectory accessibility tree; varied task/page types; programmatic development scoring."})
        write(base / "frozen_manifest.json", {
            "scope": "local-text-only/adapted development, not native or official Small",
            "source_questions": str(SOURCE / "questions.jsonl"),
            "source_trajectories": str(SOURCE / "trajectories.jsonl"),
            "question_count": len(anchors), "trajectory_count": len(ordered),
            "state_count": sum(len(trajectories[t]["states"]) for t in ordered),
            "shared_ordered_trajectory_ids": ordered,
            "distractor_trajectory_ids": DISTRACTORS[domain],
            "full_trajectory_state_counts": {tid: len(trajectories[tid]["states"]) for tid in ordered},
            "questions_with_evidence": evidence,
            "data_sha256": {name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in ["questions.jsonl", "trajectories.jsonl", "haystacks/lme_v2_small.json"]},
        })
        print(f"{domain}: {len(anchors)} questions, {len(ordered)} shared full trajectories, {sum(len(trajectories[t]['states']) for t in ordered)} states; frozen {base}", flush=True)


if __name__ == "__main__":
    main()
