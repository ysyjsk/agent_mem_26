#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BG_ROOT="$ROOT/execution/background"
if [[ ! -d "$BG_ROOT" ]]; then exit 0; fi
for job_dir in "$BG_ROOT"/*; do
  [[ -d "$job_dir" ]] || continue
  name=$(basename "$job_dir")
  pid=$(cat "$job_dir/pid" 2>/dev/null || true)
  status=$(cat "$job_dir/status" 2>/dev/null || echo unknown)
  ppid=-
  sid=-
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    live=yes
    ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    sid=$(ps -o sid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
    [[ -n "$ppid" ]] || ppid=-
    [[ -n "$sid" ]] || sid=-
  else
    live=no
  fi
  printf '%s\tstatus=%s\tlive=%s\tpid=%s\tppid=%s\tsid=%s\tdir=%s\n' "$name" "$status" "$live" "$pid" "$ppid" "$sid" "$job_dir"
done
