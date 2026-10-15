# Local text-only AgentRunbook-R/RAG+Notes smoke

This is a diagnostic comparison, not LongMemEval-V2 Small and not an official QA result. Both rows use the same official-schema enterprise question/trajectory fixture, a four-state prefix, local `Qwen3.5-9B` for Controller/Reader, local `Qwen3-Embedding-8B`, and the same text-only adapter. Screenshots are intentionally omitted from every model request; `adapter_provenance.json` marks `native_claim=false` and `official_small_claim=false`.

| method | build (s) | query (s) | reader (s) | calls | embedding/controller calls | Reader tokens | proxy |
|---|---:|---:|---:|---:|---:|---:|---:|
| AgentRunbook-R | 42.585 | 1.935 | 7.031 | 13 | 8 / 5 | 666 / 256 | 0/1 |
| RAG+Notes | 17.683 | 0.132 | 7.038 | 7 | 6 / 1 | 752 / 256 | 0/1 |
| RAG (no Notes) | 3.630 | 0.046 | 6.876 | 2 | 2 / 0 | 185 / 256 | 0/1 |

The RAG+Notes row is a real local run after fixing the isolated adapter's shared model-call audit aliases. Two failed attempts are retained in `smoke-rag-notes-v1/` and `smoke-rag-notes-v2/`; neither is included in the CSV. The 0/1 proxy scores are negative diagnostic evidence and must not be used as official accuracy.

RAG without Notes is a real ablation on the same fixture: it avoids note-generation controller calls and is faster, but its memory prompt is much smaller and the proxy remains 0/1. This is a diagnostic cost/quality trade-off only.

Raw runs: `runs/agentrunbook-r-native-small-20261014/local-text-only/smoke-run-enterprise-v3/`, `runs/agentrunbook-r-native-small-20261014/local-text-only/smoke-rag-notes-v3/`, and `runs/agentrunbook-r-native-small-20261014/local-text-only/smoke-rag-v1/`.
