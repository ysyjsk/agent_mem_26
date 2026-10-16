#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BG_ROOT="$ROOT/execution/background"

if [[ $# -lt 3 || "$2" != "--" ]]; then
  echo "usage: $0 JOB_NAME -- COMMAND [ARGS...]" >&2
  exit 2
fi
JOB_NAME=$1
shift 2
if [[ ! "$JOB_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "invalid job name: $JOB_NAME" >&2
  exit 2
fi
JOB_DIR="$BG_ROOT/$JOB_NAME"
mkdir -p "$BG_ROOT"
if [[ -f "$JOB_DIR/pid" ]]; then
  OLD_PID=$(<"$JOB_DIR/pid")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "job already running: $JOB_NAME pid=$OLD_PID" >&2
    exit 1
  fi
fi
mkdir -p "$JOB_DIR"
printf '%q ' "$@" > "$JOB_DIR/command.txt"
printf '\n' >> "$JOB_DIR/command.txt"
printf 'queued\n' > "$JOB_DIR/status"
date --iso-8601=seconds > "$JOB_DIR/queued_at"

nohup setsid bash -c '
  job_dir=$1
  shift
  date --iso-8601=seconds > "$job_dir/started_at"
  echo running > "$job_dir/status"
  set +e
  "$@" > "$job_dir/stdout.log" 2> "$job_dir/stderr.log"
  rc=$?
  set -e
  printf "%s\n" "$rc" > "$job_dir/exit_code"
  date --iso-8601=seconds > "$job_dir/finished_at"
  if [[ "$rc" == 0 ]]; then echo completed > "$job_dir/status"; else echo failed > "$job_dir/status"; fi
' _ "$JOB_DIR" "$@" </dev/null > "$JOB_DIR/launcher.log" 2>&1 &
PID=$!
printf '%s\n' "$PID" > "$JOB_DIR/pid"
date --iso-8601=seconds > "$JOB_DIR/detached_at"
echo "$JOB_NAME pid=$PID dir=$JOB_DIR"
