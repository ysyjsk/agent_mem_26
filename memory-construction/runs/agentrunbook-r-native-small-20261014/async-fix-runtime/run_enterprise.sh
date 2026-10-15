#!/usr/bin/env bash
set -euo pipefail

# Isolated follow-up for the completed web run. This script deliberately
# never contains an API key; supply ALIYUN_API_KEY in the process environment.
ROOT="/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction"
PY="/data/predator/ly/Mem/.venv/bin/python"
DATA_ROOT="$ROOT/third_party/LongMemEval-V2/data/longmemeval-v2"
FIX_ROOT="$ROOT/runs/agentrunbook-r-native-small-20261014/async-fix-runtime"
UPSTREAM_ROOT="$ROOT/third_party/LongMemEval-V2"
OUT="$ROOT/runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl-asyncfix/enterprise"

if ! env | grep -q '^ALIYUN_API_KEY='; then
  echo "ALIYUN_API_KEY must be supplied in the process environment" >&2
  exit 2
fi
if [[ -e "$OUT" ]]; then
  echo "Refusing to reuse a non-empty run output: $OUT" >&2
  exit 3
fi

umask 077
mkdir -p "$OUT"
export PYTHONNOUSERSITE=1
# FIX_ROOT must precede the frozen upstream tree so memory_modules resolves to
# the lifecycle-patched copy while evaluation/, data/, and prompts remain the
# official frozen files.
export PYTHONPATH="$FIX_ROOT:$UPSTREAM_ROOT"
export LME_EMBEDDING_TOKENIZER_MODEL="/data/predator/ly/Mem/models/Qwen3-Embedding-8B"

exec > >(tee -a "$OUT/run.log") 2>&1
echo "run_kind=adapted-matched-asyncfix"
echo "method=agentrunbook_r domain=enterprise tier=small"
echo "reader_controller=qwen3-vl-plus evaluator=qwen-plus evaluator_scope=evaluator-only"
echo "embedding=local-Qwen3-Embedding-8B reader_concurrency=1 prompt_build_workers=1"
echo "output_dir=$OUT"

# Fail closed if Python would import the unpatched source. The emitted JSON is
# provenance only: it contains paths and SHA256 values, never the API key.
"$PY" - "$OUT" "$FIX_ROOT" "$UPSTREAM_ROOT" "$ROOT/third_party/LongMemEval-V2/evaluation/run_eval.py" <<'PY'
import hashlib
import importlib
import json
import sys
from pathlib import Path

out_dir, fix_root, upstream_root, run_eval_path = map(Path, sys.argv[1:])
importlib.import_module("memory_modules.memory")
module = importlib.import_module("memory_modules.agentrunbook_r")
loaded = Path(module.__file__).resolve()
expected = (fix_root / "memory_modules" / "agentrunbook_r.py").resolve()
if loaded != expected:
    raise SystemExit(f"patched import check failed: loaded={loaded} expected={expected}")

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

payload = {
    "loaded_agentrunbook_r": str(loaded),
    "patched_agentrunbook_r_sha256": sha256(loaded),
    "upstream_agentrunbook_r": str(upstream_root / "memory_modules" / "agentrunbook_r.py"),
    "upstream_agentrunbook_r_sha256": sha256(upstream_root / "memory_modules" / "agentrunbook_r.py"),
    "run_eval": str(Path(run_eval_path).resolve()),
    "run_eval_sha256": sha256(Path(run_eval_path)),
    "pythonpath_head": sys.path[:5],
}
(out_dir / "code_provenance.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, sort_keys=True))
PY

/usr/bin/time -f "domain=enterprise wall_seconds=%e" -o "$OUT/wall_time.txt" \
  "$PY" "$UPSTREAM_ROOT/evaluation/run_eval.py" \
  --method agentrunbook_r \
  --data-root "$DATA_ROOT" \
  --domain enterprise \
  --tier small \
  --output-dir "$OUT" \
  --reader-model qwen3-vl-plus \
  --reader-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --reader-api-key-env ALIYUN_API_KEY \
  --reader-temperature 0.6 \
  --reader-top-p 0.95 \
  --reader-top-k 20 \
  --reader-max-concurrent-requests 1 \
  --reader-enable-thinking \
  --max-completion-tokens 20000 \
  --memory-context-max-tokens 200000 \
  --controller-model qwen3-vl-plus \
  --controller-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --controller-api-key-env ALIYUN_API_KEY \
  --controller-temperature 0.6 \
  --controller-top-p 0.95 \
  --controller-top-k 20 \
  --no-controller-disable-thinking \
  --embedding-model Qwen3-Embedding-8B \
  --embedding-base-url http://127.0.0.1:8114/v1 \
  --embedding-api-key-env LME_LOCAL_EMBEDDING_API_KEY \
  --evaluator-model qwen-plus \
  --evaluator-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --evaluator-api-key-env ALIYUN_API_KEY \
  --evaluator-reasoning-effort medium \
  --evaluator-max-completion-tokens 4096 \
  --prompt-build-max-workers 1
