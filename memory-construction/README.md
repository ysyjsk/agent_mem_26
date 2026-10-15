# workflow-memory

This directory contains the executable implementation described by the parent
`WORKPLAN.md`. It is deliberately runnable without a model service for
structural and correctness checks; live extraction, embedding, reader and
judge calls are injected through `workflow_memory.backends`.

```bash
PYTHONPATH=src python -m workflow_memory doctor \
  --plan configs/experiment-plan.json --out configs/runtime.json
PYTHONPATH=src python -m workflow_memory check \
  --suite correctness --config configs/runtime.json
PYTHONPATH=src python -m workflow_memory run \
  --suite pilot --config configs/runtime.json --dry-run
```

`OpenAICompatibleBackend` and `VLLMBackend` are opt-in adapters. Missing
endpoints cause live suites to be marked `blocked`; deterministic replay is
used only for correctness and is keyed by complete request content.
