"""Bounded receipt dependency closure, without database or workspace reads."""
from ..schema.common import canonical_json
from ..schema.tool_evidence import ToolEvidenceManifest
from ...operation_contract import DiagnosticError, contract_diagnostic


def proof_error(code, message):
    return DiagnosticError(message, details=(contract_diagnostic(code,
        phase='tool_execution', affected_action='tool_call', repairable=False,
        message=message),))


def source_bindings(value, records, accesses):
    bindings = {i.source_name: {'schema_version': 1,
        'artifact_ref': i.artifact_ref.model_dump(mode='json'), 'port_name': i.port_name} for i in value.inputs}
    bindings.update({r['alias']: {'schema_version': 1, 'artifact_ref': r['artifact_ref'],
        'port_name': r.get('output_port', 'tool_evidence')} for r in records})
    for r in accesses:
        bindings.setdefault(r['alias'], {'schema_version': 1, 'artifact_ref': r['artifact_ref'],
            'port_name': 'reference_access'})
    return bindings


def material_snapshot(value, selected, records, accesses, attempts, recovery):
    """Keep exact sources and attempts, with each recovery namespace separate."""
    import hashlib
    from .calculation_proof import ControlledCalculationRecord
    bindings = source_bindings(value, records, accesses)
    by_alias = {r['alias']: r for r in records}
    inputs = {i.source_name for i in value.inputs}
    pending, needed, current_attempts, recovery_origins = [selected['alias']], set(), {}, {}
    origins = ([recovery, *recovery.get('ancestors', ())] if recovery else [])
    while pending:
        alias = pending.pop()
        if alias in needed:
            continue
        if alias not in bindings:
            raise proof_error('reference_proof_incomplete',
                'A declared material dependency has no exact stored binding; repair its original receipt before reuse.')
        needed.add(alias)
        if len(needed) > 128:
            raise proof_error('reference_proof_limit',
                'This material requires more than 128 exact bindings. Automatic proof repair cannot truncate them; publish a bounded material with its complete required sources.')
        record = by_alias.get(alias)
        if record is None:
            continue
        metadata = record.get('metadata', {})
        if 'derived_from' in metadata:
            pending.extend(metadata['derived_from'])
        elif record.get('source_ref') is not None:
            sources = [name for name, binding in bindings.items()
                if binding['artifact_ref'] == record['source_ref']]
            if not sources:
                raise proof_error('reference_proof_incomplete',
                    'The receipt source has no exact stored binding; repair its original receipt before reuse.')
            pending.extend(sources)
        elif metadata.get('origin') != 'public_web':
            # Historical receipts without explicit derivation retain frozen
            # inputs conservatively, never the unrelated later tool history.
            pending.extend(inputs)
        if metadata.get('kind') == 'experiment_execution' and 'control_parents' not in record:
            pending.extend(inputs)  # Legacy execution-parent disambiguation.
        proof = metadata.get('calculation_proof')
        if proof is None:
            continue
        calculation = ControlledCalculationRecord.model_validate_json(canonical_json(proof))
        if calculation.attempt is None:
            pending.extend(calculation.input_digests)
            continue
        if calculation.attempt.manifest_alias != 'tool_recovery_manifest':
            pending.append(calculation.attempt.manifest_alias)
            pending.extend(calculation.input_digests)
            continue
        request_digest = hashlib.sha256(canonical_json(calculation.request)).hexdigest()
        matched = False
        for index, origin in enumerate([{'bindings': bindings, 'attempts': attempts}, *origins]):
            for attempt in origin['attempts']:
                if (attempt['attempt_key'] != calculation.attempt.attempt_key
                        or attempt['request_digest'] != request_digest
                        or not all(name in origin['bindings'] and origin['bindings'][name]['artifact_ref']['sha256'] == digest
                            for name, digest in calculation.input_digests.items())):
                    continue
                matched = True
                if index == 0:
                    current_attempts[attempt['attempt_key']] = attempt
                    pending.extend(attempt['read_sources'])
                    pending.extend(calculation.input_digests)
                else:
                    namespace = recovery_origins.setdefault(index, {**origin, 'bindings': {}, 'attempts': {}})
                    namespace.pop('ancestors', None)
                    namespace['attempts'][attempt['attempt_key']] = attempt
                    for name in (*attempt['read_sources'], *calculation.input_digests):
                        if name not in origin['bindings']:
                            raise proof_error('reference_proof_incomplete', 'A recovery attempt has a missing source binding; repair its original receipt before reuse.')
                        namespace['bindings'][name] = origin['bindings'][name]
        if not matched:
            raise proof_error('reference_proof_incomplete', 'The calculation has no matching stored attempt; repair its original receipt before reuse.')
    recovery_values = [{**origin, 'attempts': list(origin['attempts'].values())}
        for origin in recovery_origins.values()]
    if (sum(len(o['attempts']) for o in recovery_values) + len(current_attempts) > 64
            or any(len(o['bindings']) > 128 for o in recovery_values)):
        raise proof_error('reference_proof_limit', 'Required recovery evidence exceeds the proof limits; automatic repair cannot truncate it. Publish a bounded material with complete required sources.')
    selected_accesses = [{k: v for k, v in r.items() if k != 'response'}
        for r in accesses if r['alias'] in needed]
    if len(selected_accesses) > 32:
        raise proof_error('reference_proof_limit',
            'This material requires more than 32 reference accesses; automatic repair cannot truncate them.')
    document = {'schema_version': 1, 'bindings': {name: binding for name, binding in bindings.items() if name in needed},
        'records': [r for r in records if r['alias'] in needed],
        'accesses': selected_accesses,
        'attempts': list(current_attempts.values()),
        'recovery': {**recovery_values[0], 'ancestors': recovery_values[1:]} if recovery_values else None}
    raw = canonical_json(document)
    ToolEvidenceManifest.model_validate_json(raw)
    return raw
