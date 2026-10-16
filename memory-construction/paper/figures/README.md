# Measured development figures

These figures are an offline presentation of the saved five-history/domain,
three-revision sequence. No new inference, scores or timings were produced.
The source is
`reports/execution-recovery-20261016/public-sequence-v3/continuous_cost.csv`.
Earlier figures remain unchanged. Full-history formal figures remain pending.

- `development-continuous-cost.svg`: actual cumulative update plus retrieval
  controller plus Reader cost. Initial construction is excluded. Every update
  has two fixed diagnostic queries; three rounds do not mean three independent
  target trajectories. Lines connect measured rounds and are not extrapolations.
- `development-evidence-size.svg`: target query-eligible event characters and
  current-evidence blocks after each revision, not cumulative cost. Source and
  Notes are excluded. B3 and Coalesced both have two blocks; the dashed Coalesced
  line overlays the solid B3 line without changing coordinates. Source-only
  retires affected events. Overlay was not measured in this development series,
  so this figure alone cannot isolate the benefit of coalescing.

Render from the project root with the existing offline reporter functions:

```python
import csv, sys
from pathlib import Path
sys.path.insert(0, 'tools')
from report_full_small_formal import continuous_figure, evidence_figure
source = Path('reports/execution-recovery-20261016/public-sequence-v3/continuous_cost.csv')
with source.open() as stream:
    rows = list(csv.DictReader(stream))
for row in rows:
    row['round'] = int(row['round'])
    for key in ('cumulative_update_query_llm_tokens', 'cumulative_update_query_wall_s',
                'target_query_eligible_event_chars', 'target_current_evidence_blocks'):
        row[key] = float(row[key]) if row[key] else None
out = Path('paper/figures')
continuous_figure(out/'development-continuous-cost.svg', rows,
    title='Development histories (5/domain): measured continuous maintenance',
    policies=['raw_rag', 'rag_notes', 'b3', 'source_only', 'source_coalesced'])
evidence_figure(out/'development-evidence-size.svg', rows,
    title='Development histories (5/domain): published event size',
    policies=['b3', 'source_coalesced', 'source_only'])
```
