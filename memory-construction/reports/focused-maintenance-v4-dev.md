# V13: continuous correction cost and current evidence

Text-only/adapted development. Two shared full-domain histories, three controlled corrections per selected state; each branch carries its own published snapshot and all legal exact caches into the next round. Initial construction is inherited and excluded, NOT zero-cost cold construction. All current lines below are generated-event evidence, not merely saved raw text. Notes and unchanged facts require separate semantic review.

| Domain/round | Policy | Update LLM tokens/calls | Publish s | Embed tokens/vectors | Event chars | Obsolete lines labeled current | QA correct/scored; truncated | Query+Reader LLM tokens |
|---|---|---:|---:|---:|---:|---:|---|---:|
| web/1 | b3 | 8784/2 | 27.502 | 8550/7 | 23225 | 0 | 2/2; 0 | 23116 |
| web/1 | source_only | 0/0 | 2.040 | 7503/3 | 21391 | 0 | 2/2; 0 | 24227 |
| web/1 | source_coalesced | 0/0 | 2.304 | 8234/5 | 23184 | 0 | 2/2; 0 | 25012 |
| web/2 | b3 | 8704/2 | 25.093 | 8340/7 | 22425 | 0 | 2/2; 0 | 24588 |
| web/2 | source_only | 0/0 | 2.036 | 7503/3 | 21391 | 0 | 2/2; 0 | 24071 |
| web/2 | source_coalesced | 0/0 | 2.704 | 8234/5 | 23184 | 0 | 2/2; 0 | 23941 |
| web/3 | b3 | 8696/2 | 24.998 | 8327/7 | 22370 | 0 | 2/2; 0 | 24827 |
| web/3 | source_only | 0/0 | 2.029 | 7497/3 | 21391 | 0 | 2/2; 0 | 23624 |
| web/3 | source_coalesced | 0/0 | 2.352 | 8224/5 | 23184 | 0 | 2/2; 0 | 26930 |
| enterprise/1 | b3 | 14734/1 | 18.245 | 5080/3 | 34603 | 0 | 2/2; 0 | 24938 |
| enterprise/1 | source_only | 0/0 | 1.308 | 4096/1 | 32378 | 0 | 1/2; 0 | 26170 |
| enterprise/1 | source_coalesced | 0/0 | 1.628 | 5073/3 | 34766 | 0 | 2/2; 0 | 22155 |
| enterprise/2 | b3 | 14868/1 | 19.635 | 5214/3 | 35207 | 0 | 2/2; 0 | 22373 |
| enterprise/2 | source_only | 0/0 | 1.275 | 4096/1 | 32378 | 0 | 1/2; 0 | 24538 |
| enterprise/2 | source_coalesced | 0/0 | 1.589 | 5073/3 | 34766 | 0 | 2/2; 0 | 22136 |
| enterprise/3 | b3 | 14826/1 | 18.262 | 5172/3 | 34957 | 0 | 2/2; 0 | 22567 |
| enterprise/3 | source_only | 0/0 | 1.299 | 4096/1 | 32378 | 0 | 0/2; 0 | 26869 |
| enterprise/3 | source_coalesced | 0/0 | 1.661 | 5073/3 | 34766 | 0 | 2/2; 0 | 22334 |

Primary metric is update LLM tokens. Coalescing and append-only overlay both use zero update LLM; any additional gain is in evidence validity, embedding/context length or actual query cost, not a further reduction below zero. Cumulative curves include retrieval-controller and Reader tokens plus update tokens. Cost sums are actual sequential phases, not a sum of concurrent request durations. Question repeats/controlled source revisions are not independent samples or proof of statistical quality equivalence.
