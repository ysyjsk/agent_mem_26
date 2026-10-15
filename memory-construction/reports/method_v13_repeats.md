# V13 paired cost repeats

Two independent paired repeats start from the same original matched snapshots; B3/coalesced order alternates across passes. No query reruns are claimed.

| Run | Trajectory | Policy | Update tokens/calls | Publish s | Embedding tokens/vectors | Source-derived checks |
|---|---|---|---:|---:|---:|---|
| method-first-20261015 | 0ab99e0c | b3 | 14803/1 | 17.388 | 5148/3 | True |
| method-first-20261015 | 0ab99e0c | source_coalesced | 0/0 | 1.590 | 5073/3 | False |
| method-first-20261015 | 1ad1af4b | b3 | 8697/2 | 24.491 | 8463/7 | True |
| method-first-20261015 | 1ad1af4b | source_coalesced | 0/0 | 2.271 | 8234/5 | False |
| method-first-20261015 | 0ab99e0c | b3 | 14795/1 | 17.050 | 5141/3 | False |
| method-first-20261015 | 0ab99e0c | source_coalesced | 0/0 | 1.557 | 5073/3 | False |
| method-first-20261015 | 1ad1af4b | b3 | 8679/2 | 24.012 | 8447/7 | True |
| method-first-20261015 | 1ad1af4b | source_coalesced | 0/0 | 2.255 | 8234/5 | False |
| **sum b3** | 4 paired cases | b3 | 46974 | 82.941 | 27199 | 3/4 |
| **sum source_coalesced** | 4 paired cases | source_coalesced | 0 | 7.673 | 26614 | 0/4 |

Coalescing remains zero-update-LLM by construction. The source-derived lexical rule may flag stale prose that is explicitly labeled prior/non-authoritative; this is retained as a quality limitation, not silently counted as a pass. Reader confirmation is supplied by the sequential and held-out tables.
