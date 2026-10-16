"""Explicit local result declarations projected into existing candidate bindings."""
import hashlib
from pathlib import Path

from . import contracts as c
from . import experiments as e


def identity(row):
    return 'local-' + hashlib.sha256(e.encoded(dict(scope=row['scope'], call_id=row['call_id']))).hexdigest()


def candidates(rows):
    result = []
    for row in rows:
        declared = row.get('execution', {}).get('result') or {}
        candidate = declared.get('candidate')
        if row['status'] != 'known_success' or declared.get('status') != 'available' or candidate is None:
            continue
        metric = next(item for item in declared['metrics'] if item['name'] == candidate['metric'])
        artifact = next(item for item in row['outputs'] if 'artifacts/' + item['name'] == candidate['artifact'])
        result.append(dict(id=identity(row), label=candidate['label'], implementation=None,
            evaluation_key=metric['evaluation_key'], metric=metric['value'], direction=metric['direction'], status='ok',
            evidence=[row['completed'], artifact]))
    return result


def sources(root, fact, candidate_id):
    """Resolve only a declared local candidate, from its exact sealed call archive."""
    matches = [row for row in fact.get('managed_calls', []) if identity(row) == candidate_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError('Managed candidate identity is ambiguous')
    row = matches[0]
    observed = [item for item in candidates([row]) if item['id'] == candidate_id]
    if len(observed) != 1 or observed[0] not in fact['candidates']:
        raise ValueError('Managed candidate differs from declared sealed result')
    accepted = c.read(root / row['accepted']['snapshot'])
    completed = c.read(root / row['completed']['snapshot'])
    if 'entry' not in accepted:
        raise ValueError('Managed delivery requires retained experiment inputs')
    def proof(item):
        if item.get('retention') != 'archived':
            raise ValueError('Managed delivery original is not archived')
        return dict(path=item['snapshot'], sha256=item['sha256'], size_bytes=item['size_bytes'])
    # Input names come from the accepted snapshot inventory, never basename matching.
    objects = {}
    for item in accepted['snapshot_files']:
        matches = [p for p in row['originals'] if root / p['path'] == Path(accepted['cwd']) / item['name']]
        if len(matches) != 1 or any(matches[0][key] != item[key] for key in ('sha256', 'size_bytes')):
            raise ValueError('Managed delivery input differs from accepted snapshot')
        objects['inputs/' + item['name']] = proof(matches[0])
    for item in row['outputs']:
        objects['outputs/' + item['name']] = proof(item)
    declaration = completed['result']['candidate']
    objects['artifact'] = objects['outputs/' + declaration['artifact'].removeprefix('artifacts/')]
    return dict(candidate_id=candidate_id, status='audit_pending',
        ledger=proof(row['completed']), objects=objects,
        context=dict(kind='managed_local_result', call_id=row['call_id'],
            replay=dict(entry=accepted['entry'], arguments=accepted['command'][accepted['script_index'] + 1:]),
            candidate=declaration, metrics=completed['result']['metrics'],
            limitation='Declared public measurements; scientific validity and target optimality are not qualified.'))
