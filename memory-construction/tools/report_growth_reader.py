#!/usr/bin/env python3
"""Summarize the fixed 8-question Reader regression on growth snapshots."""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/tables/agentrunbook_growth_reader_regression.csv'
REPORT = ROOT / 'reports/agentrunbook_growth_reader_regression.md'

def main() -> None:
    rows = []
    details = []
    for domain in ('web', 'enterprise'):
        for method in ('b3', 'ours'):
            root = ROOT / f'runs/agentrunbook-updates-main/reader-growth-{domain}-{method}'
            agg = json.loads((root / 'aggregated_metrics.json').read_text())
            status, tok, timing, query = agg['answer_status'], agg['tokens'], agg['timing'], agg['memory_query']
            rows.append({
                'domain': domain, 'method': method, 'questions': agg['overall']['count_all_questions'],
                'complete_parseable': status['complete_parseable'], 'correct': status['correct'],
                'truncated': status['truncated'], 'service_failure': status['service_failure'],
                'parse_failure': status['parse_failure'], 'pending_judge': status['pending_judge'],
                'reader_input_tokens': tok['prompt_tokens'], 'reader_output_tokens': tok['completion_tokens'],
                'prompt_build_wall_s': timing['prompt_build_wall_seconds'],
                'reader_generation_wall_s': timing['reader_generation_wall_seconds'],
                'memory_query_wall_sum_s': query['total_seconds'], 'raw_path': str(root.relative_to(ROOT)),
            })
            for line in (root / 'per_question.jsonl').read_text().splitlines():
                q = json.loads(line)
                details.append({
                    'domain': domain, 'method': method, 'question_id': q['question_id'],
                    'gold': q.get('answer_gold'), 'answer': q.get('response_parsed_boxed'),
                    'correct': q.get('score_bool'), 'reader_status': q.get('reader_status'),
                    'truncated': q.get('reader_truncated'), 'finish_reason': q.get('reader_finish_reason'),
                    'parse_status': q.get('reader_parse_status'), 'complete': q.get('reader_answer_complete'),
                })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    detail_path = OUT.with_name('agentrunbook_growth_reader_per_question.csv')
    with detail_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(details[0])); w.writeheader(); w.writerows(details)
    lines = [
        '# Reader regression on same-trajectory growth snapshots', '',
        'This is a text-only/adapted quality check over the fixed eight development questions (four web + four enterprise), reusing the already published growth snapshots. It does not change construction/update timing and is not native Small or official Judge scoring.', '',
        '| Domain | Method | Correct / 4 | Complete / 4 | Trunc | Service failures | Parse failures | Reader input/output tokens | Prompt/query build wall s | Reader generation wall s |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in rows:
        lines.append(f"| {r['domain']} | {r['method']} | {r['correct']}/{r['questions']} | {r['complete_parseable']}/{r['questions']} | {r['truncated']} | {r['service_failure']} | {r['parse_failure']} | {r['reader_input_tokens']}/{r['reader_output_tokens']} | {r['prompt_build_wall_s']:.2f} | {r['reader_generation_wall_s']:.2f} |")
    lines += ['', 'All four cells produced complete, boxed, service-successful answers with zero truncation or parse failure. Web B3/Ours both score 3/4; enterprise B3/Ours both score 3/4. The only web miss is the same dynamic question answered UNKNOWN by both; the enterprise miss is the task-type question, with B3 returning “Type of Change” and Ours returning “type, type”.', '', 'Query/prompt build wall time is reported separately because it is not part of the construction/update cost claim. It varied widely across paired runs (for example, web 88.04 s vs 532.52 s), so only the complete/parseable status and paired question scores are used as the quality constraint here.', '', f'Raw aggregate rows: `{OUT.relative_to(ROOT)}`. Per-question rows: `{detail_path.relative_to(ROOT)}`.']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'rows': len(rows), 'details': len(details), 'table': str(OUT), 'report': str(REPORT)}))

if __name__ == '__main__':
    main()
