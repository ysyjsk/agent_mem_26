# Environment discovery

This report records capability presence and versions only; endpoint values and credentials are intentionally omitted.

- Plan: `/data/predator/ly/agent-memory-construction-2026-10-12/memory-construction/configs/local-experiment-plan.json`
- Plan SHA-256: `da0f3ff0fc7b5423762999205ab62db95a7f613ea063b44c50d3681aa2c2fc0e`
- Discovered at: `2026-10-12T14:35:23.034691Z`
- Host: `aces-System-Product-Name`
- Platform: `Linux-7.0.0-34-generic-x86_64-with-glibc2.39`
- Python: `3.12.3` (CPython)

## Runtime capabilities

| Capability | Finding |
|---|---|
| package `torch` | missing |
| package `vllm` | missing |
| package `openai` | missing |
| package `datasets` | missing |
| package `pillow` | available |
| `nvidia-smi` | available |
| PyTorch CUDA | missing/unavailable |

## Source revision

- Git root: /data/predator/ly
- HEAD: cb75d3be3f5729aa80aee0107cfde797c3878a8a
- Dirty: yes
- Untracked files: yes

## Model endpoint presence

| Role | Model | Base URL configured | API key configured |
|---|---|---:|---:|
| `construction` | `Qwen/Qwen3.5-9B` | no | no |
| `embedding` | `Qwen/Qwen3-Embedding-8B` | no | no |
| `reader` | `Qwen/Qwen3.5-9B` | no | no |
| `judge` | `gpt-5.2` | no | no |
| `native_v2_codex` | `gpt-5.4-mini` | no | no |

## Interpretation

Missing model endpoints do not make deterministic planning unavailable. Live suites must remain explicitly blocked until a backend is configured; no model is silently substituted.
