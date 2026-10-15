# AgentRunbook-R adapted Small summary

Snapshot generated UTC: 2026-10-13T19:08:19.975599+00:00
Run root: runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl

This is a read-only snapshot; partial/in-progress runs are not treated as complete.
Scores from qwen-plus are evaluator-only, not official LongMemEval Judge scores. Official score remains unavailable while judge status is pending_judge.

## Domain and total metrics

| domain | status | expected questions | scored answers | adapted full-set score | official score | judge/evaluator status |
|---|---:|---:|---:|---:|---:|---|
| web | in_progress | 240 | — | — | — | pending_judge;evaluator-only |
| enterprise | not_started | — | — | — | — | pending_judge;evaluator-only |
| total | in_progress | 240 | — | — | — | pending_judge;evaluator-only |

## Configuration provenance

- Run kind: adapted-matched
- Method / tier: agentrunbook_r / small
- Upstream commit: 2cc8c540bdb87fe6761629b585e727e1c4704520
- Reader/controller: qwen3-vl-plus; thinking=True; output limit=20000
- Embedding: Qwen3-Embedding-8B
- Evaluator: qwen-plus (evaluator-only); official Judge=pending_judge

## Build and calls

| domain | build seconds (sum/p95) | build failures | calls (success/fail) | prompt/completion tokens | controller seconds | embedding seconds | fast async RuntimeError |
|---|---:|---:|---:|---:|---:|---:|---:|
| web | 1605.2054709560252/174.17787372999737 | 0 | 457 (433/24) | 14456633/120604 | 4972.969456916937 | 325.3558360220195 | 18 |
| enterprise | None/None | — | None (None/None) | None/None | — | — | — |
| total | 1605.2054709560252/None | 0 | 457 (433/24) | 14456633/120604 | 4972.969456916937 | 325.3558360220195 | 18 |

## Async error note

The model-call log records RuntimeError and a null HTTP status for fast async_text failures, but it does not record the exception message. The observed pattern is therefore not by itself proof of a server error. Source inspection shows a single cached AsyncOpenAI client is reused while _run_async invokes asyncio.run for trajectory batches; cross-event-loop client/transport reuse is a high-probability lifecycle cause, to be confirmed only in a later isolated rerun.

## Artifacts

- web: per_question=missing; aggregate=missing; build=runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl/web/memory_build_metrics.jsonl; model_calls=runs/agentrunbook-r-native-small-20261014/adapted-aliyun-vl/web/memory_workspace/shared/model_calls.jsonl
- enterprise: per_question=missing; aggregate=missing; build=missing; model_calls=missing
- total: per_question=missing; aggregate=missing; build=missing; model_calls=missing
