#!/usr/bin/env bash
set -u -o pipefail

ROOT="/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction"
PY="/data/predator/ly/Mem/.venv/bin/python"
DATA_ROOT="$ROOT/third_party/LongMemEval-V2/data/longmemeval-v2"
OUT_ROOT="$ROOT/runs/agentrunbook-r-native-small-20261013/matched-runtime-v2"
LOG="$ROOT/runs/agentrunbook-r-native-small-20261013/matched-runtime/continuation-v3.log"
WEB_ARCHIVE="$DATA_ROOT/trajectory_screenshots/web_screenshots.tar.gz"
ENT_ARCHIVE="$DATA_ROOT/trajectory_screenshots/enterprise_screenshots_base.tar.gz"

exec >>"$LOG" 2>&1
echo "continuation_started=$(date -Is)"
echo "download_pids=2568703 (original parent 2568699 exited after graceful interrupt)"

while :; do
  if [[ -f "$WEB_ARCHIVE" && -f "$ENT_ARCHIVE" ]]; then
    break
  fi
  if ! kill -0 2568703 2>/dev/null; then
    echo "download_exited_before_archives=$(date -Is)"
    exit 20
  fi
  date -Is
  stat -c '%n %s %y' "$DATA_ROOT"/.cache/huggingface/download/trajectory_screenshots/*.incomplete 2>/dev/null || true
  sleep 60
done

echo "archives_present=$(date -Is)"
stat -c '%n %s %y' "$WEB_ARCHIVE" "$ENT_ARCHIVE"
WEB_SIZE=$(stat -c '%s' "$WEB_ARCHIVE")
ENT_SIZE=$(stat -c '%s' "$ENT_ARCHIVE")
[[ "$WEB_SIZE" == "2562302847" ]] || { echo "web_size_mismatch=$WEB_SIZE"; exit 21; }
[[ "$ENT_SIZE" == "3354163660" ]] || { echo "enterprise_size_mismatch=$ENT_SIZE"; exit 22; }
WEB_SHA=$(sha256sum "$WEB_ARCHIVE" | awk '{print $1}')
ENT_SHA=$(sha256sum "$ENT_ARCHIVE" | awk '{print $1}')
echo "web_sha256=$WEB_SHA"
echo "enterprise_sha256=$ENT_SHA"
[[ "$WEB_SHA" == "68699c6842412e09a6f89d3c05c5ae8813275918002b52d82dec43ab24dd01fb" ]] || { echo "web_sha_mismatch"; exit 23; }
[[ "$ENT_SHA" == "5c4a67ae0856aa1ede9b040e7da7c7a2d0b76fdd6344ef87380bcdf9f4b6d7a3" ]] || { echo "enterprise_sha_mismatch"; exit 24; }

cd "$ROOT"
if [[ -d "$DATA_ROOT/trajectory_screenshots/web_screenshots" ]] && [[ -z "$(find "$DATA_ROOT/trajectory_screenshots/web_screenshots" -mindepth 1 -print -quit)" ]]; then
  rmdir "$DATA_ROOT/trajectory_screenshots/web_screenshots"
  echo "removed_empty_web_extract_dir=$(date -Is)"
fi
echo "prepare_started=$(date -Is)"
PYTHONNOUSITE=1 "$PY" third_party/LongMemEval-V2/data/prepare_data.py \
  --data-root "$DATA_ROOT" --mode symlink
echo "prepare_exit=$? prepare_finished=$(date -Is)"

echo "validate_started=$(date -Is)"
PYTHONNOUSITE=1 "$PY" third_party/LongMemEval-V2/data/validate_data.py \
  --data-root "$DATA_ROOT" --tier small --check-screenshots
VALIDATE_EXIT=$?
echo "validate_exit=$VALIDATE_EXIT validate_finished=$(date -Is)"
[[ "$VALIDATE_EXIT" == "0" ]] || exit 25

PYTHONNOUSITE=1 DATA_ROOT="$DATA_ROOT" "$PY" - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["DATA_ROOT"])
questions = [json.loads(line) for line in (root / "questions.jsonl").read_text().splitlines() if line.strip()]
question_by_id = {row["id"]: row for row in questions}
haystack = json.loads((root / "haystacks" / "lme_v2_small.json").read_text())
trajectories = {
    row["id"]: row
    for row in (json.loads(line) for line in (root / "trajectories.jsonl").read_text().splitlines() if line.strip())
}
assert len(questions) == len(haystack) == 451
assert sum(row["domain"] == "web" for row in questions) == 240
assert sum(row["domain"] == "enterprise" for row in questions) == 211
ids = {item for values in haystack.values() for item in values}
assert len(ids) == 200
assert all(len(values) == 100 for values in haystack.values())
assert sum(len(trajectories[item]["states"]) for item in ids) == 5095
assert all(
    (root / "screenshots" / item / f"{state['state_index']}.png").is_file()
    for item in ids
    for state in trajectories[item]["states"]
)
for question_id, values in haystack.items():
    domains = {trajectories[item]["domain"] for item in values}
    assert domains == {question_by_id[question_id]["domain"]}
print("small_coverage_ok questions=451 unique_trajectories=200 states=5095")
PY

run_domain() {
  local domain="$1"
  local output="$OUT_ROOT/$domain"
  if [[ -f "$output/run_args.json" ]]; then
    echo "skip_existing_domain=$domain"
    return 0
  fi
  mkdir -p "$output"
  echo "run_started domain=$domain at=$(date -Is)"
  /usr/bin/time -f "domain=$domain wall_seconds=%e" -o "$output/wall_time.txt" \
    env PYTHONNOUSITE=1 PYTHONPATH="$ROOT/third_party/LongMemEval-V2" \
      LME_READER_PROCESSOR_MODEL=/data/predator/ly/Mem/models/Qwen3.5-9B \
      LME_EMBEDDING_TOKENIZER_MODEL=/data/predator/ly/Mem/models/Qwen3-Embedding-8B \
      "$PY" third_party/LongMemEval-V2/evaluation/run_eval.py \
      --method agentrunbook_r \
      --data-root "$DATA_ROOT" \
      --domain "$domain" \
      --tier small \
      --output-dir "$output" \
      --reader-model Qwen3.5-9B \
      --reader-base-url http://127.0.0.1:8023/v1 \
      --reader-temperature 0.6 \
      --reader-top-p 0.95 \
      --reader-top-k 20 \
      --reader-max-concurrent-requests 16 \
      --reader-enable-thinking \
      --max-completion-tokens 20000 \
      --memory-context-max-tokens 200000 \
      --controller-model Qwen3.5-9B \
      --controller-base-url http://127.0.0.1:8023/v1 \
      --controller-temperature 0.6 \
      --controller-top-p 0.95 \
      --controller-top-k 20 \
      --embedding-model Qwen3-Embedding-8B \
      --embedding-base-url http://127.0.0.1:8114/v1 \
      --evaluator-model gpt-5.6-terra \
      --evaluator-base-url https://api.labforge.cc/v1 \
      --evaluator-api-key-env OPENAI_API_KEY \
      --evaluator-reasoning-effort medium \
      --prompt-build-max-workers 1
  local status=$?
  echo "run_finished domain=$domain status=$status at=$(date -Is)"
  return "$status"
}

run_domain web
WEB_STATUS=$?
run_domain enterprise
ENT_STATUS=$?
echo "continuation_finished=$(date -Is) web_status=$WEB_STATUS enterprise_status=$ENT_STATUS"
[[ "$WEB_STATUS" == "0" && "$ENT_STATUS" == "0" ]]
