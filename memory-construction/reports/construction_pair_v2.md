# Adjacent extraction: live construction costs

Text-only/adapted; complete official-source trajectories. Not native Small or official Judge quality. 
Cold build starts from empty method memory with resident shared models. Wall time ends after save/reload validation; query work is excluded.

Single and paired events use 2048 tokens/event (server ceiling4096), thinking off, c1; notes retain original 8192 requested/4096 effective ceiling. All events, both notes and indexes retained.

Frozen queries: 2048 output,12000 context,chunking,cached tokenizer,lexical backfill,no neighbor expansion,query-local exact embedding reuse. Quality is a constraint, not a search objective.

| Run | Publish s | LLM calls | Input/output tokens | Embedding vectors/tokens | QA correct/complete/attempted | Structural |
|---|---:|---:|---:|---:|---:|---|
| full10-enterprise-baseline | 502.39 | 55 | 490066/10776 | 113/230848 | 4/4/4 | True |
| full10-enterprise-combined | 491.29 | 49 | 463241/10983 | 108/210442 | 3/4/4 | True |
| full10-enterprise-embed | 533.81 | 58 | 491160/11189 | 108/210100 | 4/4/4 | True |
| full10-enterprise-joint | 683.39 | 52 | 483991/11033 | 113/230484 | 4/4/4 | True |
| full10-web-baseline | 327.61 | 38 | 244957/7827 | 79/139494 | 3/4/4 | True |
| full10-web-combined | 498.62 | 27 | 203471/8271 | 76/126621 | 3/4/4 | True |
| full10-web-embed | 349.15 | 39 | 245431/8656 | 76/127403 | 3/4/4 | True |
| full10-web-joint | 342.38 | 26 | 202963/7997 | 79/139041 | 3/4/4 | True |

Unknown-usage failures are counted separately and are not zero-cost. Client call-duration sums are not publication wall time.
Event/source/schema checks and five first-trajectory literal probes are not a substitute for the fixed eight-question development evaluation.
All original requests and responses are retained in each memory_state/model_calls.jsonl; per_question.jsonl preserves answers and scoring basis.
Screening result: 7→4 event requests, total8→5 controller calls; input38824→29581 (−23.8%); output1528→1608. Wall61.20→61.51s: no demonstrated speedup in this one-pair screen. No API errors, truncations, missing events or notes.

V2 common resource handling: preflight at18000 input tokens; oversized single-event requests use the already-existing12000-char/state fallback before an OOM. Full raw trajectories remain in memory. Oversized joint groups split. SDK automatic controller retries are0. These shared fixes are not attributed to joint extraction or embedding reuse; V1 results are separate.
