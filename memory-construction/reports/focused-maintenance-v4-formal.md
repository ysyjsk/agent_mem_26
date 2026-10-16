# Focused-maintenance-v4 formal Small maintenance

Scope: frozen text-only/adapted Small history libraries, 10 complete trajectories per domain, one predeclared revision and two fixed dynamic questions per domain. Reader is Qwen3.5-9B, thinking disabled, 2,048 completion tokens and 12,000 memory-context tokens. The enterprise initial snapshot is a legal reused 10-trajectory build; its historical construction cost is not silently presented as a new cold-build measurement.

## Main result

The formal update cost is strongly lower for Source-only and source_coalesced than B3: both use zero update LLM calls on these fixed literal corrections. Source-only uses fewer embedding vectors than the coalesced representation, while coalesced preserves current evidence blocks and 13 unaffected event dependencies. The downstream Reader constraint is not maintained uniformly: web scores are B3 2/2, Source-only 0/2, coalesced 1/2; enterprise scores are 1/2 for all three. All 12 responses are complete and parseable with zero truncation, service failures, or parse failures. Therefore the formal result supports a cost reduction, but not a claim of quality equivalence or a universally superior method.

## Quality and failure interpretation

Source-grounded checks pass for both Source-only formal branches and fail the predeclared coalesced lexical rule on both domains because the generated event text does not retain every requested neighboring fact. This is retained as a limitation rather than repaired after looking at scores. The fixed Reader answers are recorded per question in `results/tables/focused-maintenance-v4/formal_reader_answers.csv`; semantic Judge scoring is not used.

## Cost accounting

Update wall time includes artifact construction, embedding, save/reload and queryable publication. Reader prompt construction, retrieval and Reader generation are reported separately; the cumulative figure adds update LLM tokens to fixed Reader prompt/output tokens and never substitutes embedding tokens for LLM tokens. Raw paths in `public_main.csv` point to the persisted metrics and Reader records.

## Reproducibility and boundary

This is a formal adapted maintenance experiment, not native multimodal Small and not a cold-construction comparison. The public Raw RAG/RAG+Notes maintenance adapters remain deferred under execution-ready-r2-freeze; no incompatible historical row is mixed into this table.
