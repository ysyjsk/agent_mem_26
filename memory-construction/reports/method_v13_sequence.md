# V13: continuous correction cost and current evidence

Text-only/adapted development. Two shared full-domain histories, three controlled corrections per selected state; each branch carries its own published snapshot and all legal exact caches into the next round. Initial construction is inherited and excluded, NOT zero-cost cold construction. All current lines below are generated-event evidence, not merely saved raw text. Notes and unchanged facts require separate semantic review.

| Domain/round | Policy | Update LLM tokens/calls | Publish s | Embed tokens/vectors | Event chars | Obsolete lines labeled current | QA correct/scored; truncated | Query+Reader LLM tokens |
|---|---|---:|---:|---:|---:|---:|---|---:|
| web/1 | b3 | 8704/2 | 49.129 | 8470/7 | 22773 | 0 | 2/2; 0 | 25072 |
| web/1 | source_overlay | 0/0 | 2.475 | 8290/5 | 23304 | 0 | 2/2; 0 | 24867 |
| web/1 | source_coalesced | 0/0 | 2.444 | 8234/5 | 23184 | 0 | 2/2; 0 | 25900 |
| web/2 | b3 | 8714/2 | 49.869 | 8354/7 | 22556 | 0 | 2/2; 0 | 24412 |
| web/2 | source_overlay | 0/0 | 2.554 | 8699/5 | 24809 | 4 | 2/2; 0 | 25442 |
| web/2 | source_coalesced | 0/0 | 2.457 | 8234/5 | 23184 | 0 | 2/2; 0 | 23086 |
| web/3 | b3 | 8652/2 | 33.885 | 8282/7 | 22157 | 0 | 2/2; 0 | 24647 |
| web/3 | source_overlay | 0/0 | 2.665 | 9102/5 | 26314 | 8 | 2/2; 0 | 24359 |
| web/3 | source_coalesced | 0/0 | 2.553 | 8224/5 | 23184 | 0 | 2/2; 0 | 23849 |
| enterprise/1 | b3 | 14900/1 | 37.656 | 5246/3 | 35292 | 0 | 2/2; 0 | 22561 |
| enterprise/1 | source_overlay | 0/0 | 2.278 | 5205/3 | 35030 | 0 | 2/2; 0 | 22782 |
| enterprise/1 | source_coalesced | 0/0 | 2.175 | 5073/3 | 34766 | 0 | 2/2; 0 | 22357 |
| enterprise/2 | b3 | 14772/1 | 17.124 | 5130/3 | 34822 | 0 | 2/2; 0 | 23792 |
| enterprise/2 | source_overlay | 0/0 | 1.810 | 6079/3 | 37682 | 8 | 1/2; 0 | 24252 |
| enterprise/2 | source_coalesced | 0/0 | 1.633 | 5073/3 | 34766 | 0 | 2/2; 0 | 22431 |
| enterprise/3 | b3 | 14838/1 | 18.387 | 5184/3 | 35044 | 0 | 1/2; 0 | 23650 |
| enterprise/3 | source_overlay | 0/0 | 2.006 | 6961/3 | 40334 | 16 | 2/2; 0 | 26163 |
| enterprise/3 | source_coalesced | 0/0 | 1.579 | 5073/3 | 34766 | 0 | 2/2; 0 | 22488 |

Primary metric is update LLM tokens. Coalescing and append-only overlay both use zero update LLM; any additional gain is in evidence validity, embedding/context length or actual query cost, not a further reduction below zero. Cumulative curves include retrieval-controller and Reader tokens plus update tokens. Cost sums are actual sequential phases, not a sum of concurrent request durations. Question repeats/controlled source revisions are not independent samples or proof of statistical quality equivalence.
