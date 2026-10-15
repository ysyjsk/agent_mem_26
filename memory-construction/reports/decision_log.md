# Decision log

## 2026-10-12 — implementation bootstrap

- Chose a standard-library Python package under `memory-construction/`.
- Kept model serving behind `ModelBackend`, `OpenAICompatibleBackend`, and
  `VLLMBackend`; no endpoint or credential is hard-coded.
- Used deterministic local extraction for offline correctness checks only. It
  is marked synthetic and is not a live benchmark result.
- Fresh and Incremental share the same prefix-only graph, normalization,
  scopes, cache-key rules, and structured views. Incremental reuses unaffected
  nodes and records a prepared update before SQLite publication.
- Live suites remain blocked until configured construction/embedding/reader/
  judge services and benchmark data are supplied.
