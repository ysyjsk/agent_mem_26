# V11 development paired confirmation (not frozen)

Primary metric: total LLM tokens. Each pair starts from independent copies of the same source and legal caches. Three fresh runs per two replacement cases, alternating B3/candidate order; no historical controls in this table. Source values are controlled counterfactual corrections, not official QA amendments.

| Trajectory | Pairs | Mean B3/candidate tokens | Paired token reduction range | Mean B3/candidate publish s | Paired wall reduction range | Candidate necessary checks |
|---|---:|---:|---:|---:|---:|---:|
| 0ab99e0c | 3 | 14776.0/1209.3 | 91.6–92.3% | 17.66/6.12 | 57.4–77.3% | 3/3 |
| 1ad1af4b | 3 | 8732.3/1949.3 | 77.2–78.5% | 26.79/12.59 | 46.7–62.5% | 2/3 |

Necessary lexical checks are not semantic quality certification. Review generated event/state roles and notes in reports/method_literal_quality_review.md; fixed Reader regression remains independent. No cold construction or query savings are counted. All per-stage tokens, vectors, failures, setup/publication and raw paths are in results/tables/method_update_costs.csv.
