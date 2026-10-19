"""Explicit local result declarations projected into existing candidate bindings."""
import hashlib
import math
from pathlib import Path

from . import contracts as c
from . import experiments as e


def identity(row):
    return 'local-' + hashlib.sha256(e.encoded(dict(scope=row['scope'], call_id=row['call_id']))).hexdigest()


def protocol(interface):
    if 'result_protocol' in interface:return interface['result_protocol']
    # Read-only compatibility for the exact previously published local binding.
    if interface.get('executor')=='local_execution:command' and type(interface.get('version')) is int and interface['version']==1:
        return e.LOCAL_RESULT_PROTOCOL
    return None


def candidates(rows, *, diagnostics=None):
    result = []
    for row in rows:
        if row.get('result_protocol')!=e.LOCAL_RESULT_PROTOCOL:continue
        declared = row.get('execution', {}).get('result') or {}
        if not isinstance(declared,dict):continue
        candidate = declared.get('candidate')
        if row['status'] != 'known_success' or declared.get('status') != 'available' or candidate is None:
            continue
        metrics=declared.get('metrics');outputs=row.get('outputs')
        valid=(isinstance(candidate,dict) and isinstance(candidate.get('artifact'),str)
            and isinstance(metrics,list) and isinstance(outputs,list))
        matching_outputs=[item for item in outputs if isinstance(item,dict) and isinstance(item.get('name'),str)
            and 'artifacts/'+item['name']==candidate['artifact']] if valid else []
        declared_outputs=declared.get('outputs')
        valid=(valid and isinstance(declared_outputs,list) and len(matching_outputs)==1
            and sum(isinstance(item,dict) and item.get('path')==candidate['artifact'] for item in declared_outputs)==1)
        if not valid:
            if diagnostics is not None:diagnostics.append(dict(call_id=row['call_id'],code='declared_candidate_mapping_invalid'))
            continue
        matching_metrics=[item for item in metrics if isinstance(item,dict)
            and isinstance(candidate.get('metric'),str) and item.get('name')==candidate['metric']]
        metric=matching_metrics[0] if len(matching_metrics)==1 else {}
        value=metric.get('value')
        try:finite=type(value) in (int,float) and math.isfinite(value)
        except OverflowError:finite=False
        if not finite:
            metric={};value=None
            if 'metric' in candidate and diagnostics is not None:
                diagnostics.append(dict(call_id=row['call_id'],code='declared_candidate_metric_unknown'))
        artifact=matching_outputs[0]
        result.append(dict(id=identity(row), label=candidate.get('label'), implementation=None,
            evaluation_key=metric.get('evaluation_key'), metric=value, direction=metric.get('direction'), status='ok',
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
    if 'result_protocol' not in row:
        from . import history
        accepted=c.read(root/row['accepted']['snapshot'])
        row=dict(row,result_protocol=protocol(history._execution_interface(root,accepted)))
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
