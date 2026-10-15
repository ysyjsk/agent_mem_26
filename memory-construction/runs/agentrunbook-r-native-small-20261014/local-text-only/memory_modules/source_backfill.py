"""Query-time source backfill: no answer labels, extra generation or embeddings."""
import math
import os
import re
from collections import Counter

STOP = set('a an the is are was were be been being i am my our your it its this that these those to of in on at for from with by and or as do does did what which how when where who after before should one more say says answer final question using use based contains appears please'.split())


def terms(text):
    # Small query-word normalizer, deliberately not an answer-specific rule.
    return {w[:-1] if w.endswith('s') and len(w) > 4 else w
            for w in re.findall(r'[a-z][a-z0-9]+', text.lower()) if w not in STOP}


def source_backfill(query, trajectories, *, max_lines=64, max_chars=12000):
    """Select stable-deduplicated source lines, preserving provenance and order.

    Only top retrieved trajectories are searched. Repeated page furniture is
    counted once; rank by query-term IDF, with quoted query words weighted 3x.
    This is adapted heuristic retrieval, never an oracle evidence locator.
    """
    qterms = terms(query)
    quoted = set().union(*(terms(s) for s in re.findall(r'["\x27]([^"\x27]{1,50})["\x27]', query)))
    rows, seen, source_lines = [], set(), {}
    for trajectory in trajectories:
        tid = trajectory['id']
        for state in trajectory['states']:
            lines = state.get('text', state.get('accessibility_tree', '')).splitlines()
            state_index = state.get('state_index', state.get('step'))
            source_lines[(tid, state_index)] = lines
            for line_index, line in enumerate(lines):
                canonical = re.sub(r'^\s*\[[^\]]+\]', '', line).strip()
                key = (tid, canonical)
                if not canonical or key in seen:
                    continue
                seen.add(key)
                rows.append({'tid': tid, 'state': state_index,
                             'line': line_index, 'text': line, 'terms': terms(canonical),
                             'order': len(rows)})
    counts = Counter(t for row in rows for t in row['terms'])
    for row in rows:
        row['score'] = sum((3 if t in quoted else 1) * math.log(1 + len(rows)/(1 + counts[t]))
                           for t in row['terms'] & qterms)
    selected, anchors, chars = [], [], 0
    for row in sorted(rows, key=lambda r: (-r['score'], r['order'])):
        if row['score'] <= 0 or len(selected) >= max_lines:
            break
        line = f"[{row['tid']} state {row['state']} line {row['line']}] {row['text']}"
        if chars + len(line) > max_chars:
            continue
        selected.append((row['order'], line))
        anchors.append(row)
        chars += len(line) + 1
    if os.getenv('LME_BACKFILL_NEIGHBOR_LINES', '0') == '1':
        # Add context only within the unchanged total excerpt character cap.
        included = {(r['tid'], re.sub(r'^\s*\[[^\]]+\]', '', r['text']).strip()) for r in anchors}
        for row in anchors:
            lines = source_lines[(row['tid'], row['state'])]
            for offset in (-1, 1):
                index = row['line'] + offset
                if not 0 <= index < len(lines):
                    continue
                canonical = re.sub(r'^\s*\[[^\]]+\]', '', lines[index]).strip()
                key = (row['tid'], canonical)
                if not canonical or key in included:
                    continue
                line = f"[{row['tid']} state {row['state']} line {index}] {lines[index]}"
                if chars + len(line) + 1 > max_chars:
                    continue
                included.add(key)
                selected.append((row['order'] + offset*0.25, line))
                chars += len(line) + 1
    if not selected:
        return []
    return [{'type': 'text', 'value': 'Query-matching source excerpts (stable repeated lines shown once; not a complete state)\n'
             + '\n'.join(line for _, line in sorted(selected))}]
