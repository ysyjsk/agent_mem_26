# Adjacent extraction: live construction costs

Text-only/adapted; complete official-source trajectories. Not native Small or official Judge quality. 
Cold build starts from empty method memory with resident shared models. Wall time ends after save/reload validation; query work is excluded.

Single and paired events use 2048 tokens/event (server ceiling4096), thinking off, c1; notes retain original 8192 requested/4096 effective ceiling. All events, both notes and indexes retained.

Frozen queries: 2048 output,12000 context,chunking,cached tokenizer,lexical backfill,no neighbor expansion,query-local exact embedding reuse. Quality is a constraint, not a search objective.

| Run | Publish s | LLM calls | Input/output tokens | Embedding vectors/tokens | QA correct/complete/attempted | Structural |
|---|---:|---:|---:|---:|---:|---|
| full10-enterprise-baseline | 780.95 | 86 | 508476/10739 | 113/231016 | 3/4/4 | True |
| full10-web-baseline | 558.09 | 38 | 252945/8216 | 79/139785 | 3/4/4 | True |
| full10-web-joint | 520.17 | 29 | 211444/8870 | 79/139380 | 3/4/4 | True |
| screen-web-g1 | 61.20 | 8 | 38824/1528 | 17/26503 | 0/0/0 | True |
| screen-web-g2 | 61.51 | 5 | 29581/1608 | 17/26378 | 0/0/0 | True |

Unknown-usage failures are counted separately and are not zero-cost. Client call-duration sums are not publication wall time.
Event/source/schema checks and five first-trajectory literal probes are not a substitute for the fixed eight-question development evaluation.
All original requests and responses are retained in each memory_state/model_calls.jsonl; per_question.jsonl preserves answers and scoring basis.
Screening result: 7→4 event requests, total8→5 controller calls; input38824→29581 (−23.8%); output1528→1608. Wall61.20→61.51s: no demonstrated speedup in this one-pair screen. No API errors, truncations, missing events or notes.
