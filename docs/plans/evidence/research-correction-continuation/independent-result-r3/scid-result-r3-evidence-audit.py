import collections
import json
import re
from pathlib import Path
import sys

root = Path(sys.argv[1])
base = Path('/tmp/scid-continuation-implementation-baseline')
evidence = root / 'docs/plans/evidence/research-correction-continuation'
records = json.loads((evidence / 'p4-checks.json').read_text())
nodeids = [line for line in (evidence / 'p4-collection.log').read_text().splitlines()
           if line.startswith('tests/') and '::' in line]
counts = collections.Counter(node.split('::')[0] for node in nodeids)
final_runs = {}
for batch in records['batches']:
    for name in batch['files']:
        final_runs[name] = batch
totals = collections.Counter()
unique_batches = {batch['log']: batch for batch in final_runs.values()}
for log, batch in unique_batches.items():
    lines = (evidence / log).read_text().splitlines()
    summary = next(line for line in reversed(lines) if re.search(r'\d+ (passed|failed|skipped)', line))
    metrics = {kind: int(number) for number, kind in re.findall(r'(\d+) (passed|failed|skipped)', summary)}
    assert sum(metrics.values()) == sum(counts[name] for name in batch['files']), log
    totals.update(metrics)
for item in records['reused']:
    assert counts[item['file']] == item['collected_tests']
    totals['passed'] += item['collected_tests']
covered = set(final_runs) | {item['file'] for item in records['reused']}
assert covered == set(counts)

groups = {
    'plugin': ('src/scidiscovery/general_science_plugin.py', 'src/scidiscovery/general_science_resources.py',
               'src/scidiscovery/general_science_agent_operations.py', 'src/scidiscovery/general_science_experiment_operations.py'),
    'transform': ('src/scidiscovery/general_science_components.py', 'src/scidiscovery/general_science_control_operations.py',
                  'src/scidiscovery/general_science_experiment_components.py'),
}
lines = {key: {label: sum(len((directory / name).read_text().splitlines()) for name in names)
               for label, directory in (('baseline', base), ('candidate', root))}
         for key, names in groups.items()}
print(json.dumps({'collected_nodeids': len(nodeids), 'unique_nodeids': len(set(nodeids)),
                  'covered_files': len(covered), 'missing_files': sorted(set(counts) - covered),
                  'independently_recomputed_final_totals': dict(totals),
                  'summary_claim_matches': totals['passed'] == 676 and totals['failed'] == 10 and totals['skipped'] == 0,
                  'line_counts': lines,
                  'line_count_growth': sum(item['candidate'] - item['baseline'] for item in lines.values()),
                  'basis': 'Final batch summaries checked against raw logs and exact collected nodeids; reused passes as attributed by existing logs, no full pytest rerun.'},
                 indent=2))
