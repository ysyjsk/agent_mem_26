# Correctness checks

Run `PYTHONPATH=src python -m workflow_memory check --suite correctness --config configs/runtime.json` from this directory. The command writes a per-run `correctness.json`; deterministic checks cover Fresh/Incremental equivalence, source grounding, scope isolation, and failure-vs-success semantics.
