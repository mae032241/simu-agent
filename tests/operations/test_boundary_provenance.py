"""Sealed H/W/A boundary provenance through real MCP and Worker entries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.input_reader import compact_handoff, public_boundary_record, COMPACT_BOUNDARY_BYTES
from tests.operations.test_l2_run_invariants import _system, _invoke, _worker, _envelope
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.test_unified_mcp import call, result
from tests.operations.worker_fixtures import attached_worker


USER = 'Improve the predictor. 不得将val并入training。'
QUOTE = '不得将val并入training'


def invoke(gateway, name, operation, inputs):
    response = result(call(gateway, 'operation_invoke', dict(name=name, operation_id=operation,
        inputs=[dict(port=port, artifact_names=[artifact]) for port, artifact in inputs.items()],
        instruction='Follow the exact owner direction and original constraints.')))
    assert response['result']['state'] == 'queued', response


def submit(runtime, root, name, payload, declarations=(), references=()):
    worker = attached_worker(runtime, root, name)
    opened = worker.call_tool('worker_open_assignment', {})
    value = dict(schema_version=1, payload=payload, boundary_declarations=list(declarations),
        handoff=dict(verdict='inconclusive', summary='Bounded owner conclusion.',
            assumptions=['No external scientific attestation.'], boundary_references=list(references)))
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(value))
    response = worker.call_tool('worker_submit_result', {})
    assert response['state'] == 'completed', response
    run = runtime.runs.status(worker._run_id)
    return worker, opened, run


def declaration(key, statement, *, source='subject', locator='text', quote=QUOTE, interpretation=None, **extra):
    return dict(boundary_key=key, statement=statement, interpretation=interpretation or statement,
        evidence=[dict(source=dict(source_key=source, source_type='user_statement', locator=locator), quote=quote)]
        if source else [], **extra)


def full_boundary(worker, source=None, history=None, key=None, limit=512):
    args = dict(view='boundaries', limit=limit, **({'source': source} if source else {'history_task': history}))
    entries, cursor = [], 0
    while True:
        page = worker.call_tool('worker_reference_read', dict(args, cursor=cursor))
        assert len(canonical_json(page)) <= limit
        entries.extend(page['references'])
        cursor = page['next_cursor']
        if cursor is None:
            break
    entry = next(item for item in entries if item['boundary_key'] == key)
    chunks, offset = [], 0
    while True:
        page = worker.call_tool('worker_reference_read', dict(args, action='read', reference=entry['reference'], offset=offset))
        assert len(canonical_json(page)) <= limit
        chunks.append(page['fragment'])
        next_offset = page['next_offset']
        if next_offset is None:
            break
        assert next_offset > offset
        offset = next_offset
    return json.loads(''.join(chunks)), entry['reference']


def test_real_h_w_a_revision_keeps_true_constraint_and_attributed_stronger_interpretation(tmp_path):
    catalog, runtime, _, _, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    result(call(gateway, 'artifact_ingest_text', dict(name='user-task', text=USER)))
    from tests.operations.test_attempt_history import SECRET
    from tests.operations.research_loop_fixtures import authorize_loop
    session = 'sch_' + 'b' * 32
    runtime.scheduler_bindings.bind_session(session_key=session, instance_id=root.facade.instance)
    root.facade.session_key = session
    root.facade.instance_management_secret = SECRET
    root.call_tool('progression_command', dict(command='takeover', mode='interactive'))
    root.call_tool('progression_command', dict(command='pause'))
    authorize_loop(runtime, root.facade.instance, session, 'user-task')
    root.call_tool('progression_command', dict(command='start', mode='interactive', objective_name='user-task'))
    # Exact same words in scientific material are never promoted by schema/type or quote.
    science = runtime.artifacts.register(QUOTE.encode(), ArtifactRegistration(kind='scientific_note',
        schema_id='thirdparty.note.v1', payload_schema_version=1, media_type='text/plain', creator=runtime.actor,
        labels={'source_origin': 'user_via_scheduler'}), idempotency_key='same-scientific-words')
    runtime.scheduler_bindings.bind(instance=root.facade.instance, namespace='artifact', name='note', object_id=science.artifact_id)
    invoke(gateway, 'H-original', 'science.hypothesis.propose.v1', {'subject': 'user-task', 'result_analysis': 'note'})
    h_payload = _proposal(hypothesis_keys=('mechanism',)); h_payload.pop('research_objective_key')
    h_payload['hypotheses'][0]['scope'] = 'All operators estimated on training observations only.'
    h_payload['hypotheses'][0]['parameters'] = [dict(name='regularization', role='fixed', unit='dimensionless', basis='Finite chosen proxy.')]
    declarations = [
        declaration('no-val-training', QUOTE),
        declaration('operator-rule', h_payload['hypotheses'][0]['scope'], interpretation='H derives a stronger all-operator train-only rule.', hypothesis_key='mechanism'),
        declaration('science-quote', 'The note contains the same words.', source='result_analysis'),
        declaration('bad-quote', 'Retain this H restriction while clarifying the source.', quote='SOURCE_ABSENT_SENTINEL'),
    ]
    _, _, original = submit(runtime, root, 'H-original', h_payload, declarations,
        [dict(boundary_key=d['boundary_key']) for d in declarations])
    controls = {record['declaration']['boundary_key']: record for record in original.signal.boundary_declarations}
    assert controls['no-val-training']['source_checks'][0]['origin'] == 'original_user_text'
    assert controls['operator-rule']['source_checks'][0]['verification'] == 'matched'
    assert controls['operator-rule']['authority'] == 'owner_interpretation'
    assert controls['science-quote']['source_checks'][0]['verification'] == 'matched'
    assert controls['science-quote']['source_checks'][0]['origin'] == 'frozen_material'
    assert controls['bad-quote']['verification'] == 'unverified'
    assert all(record['effect'] == 'owner_statement' for record in controls.values())
    assert any(record['declaration'].get('parameter_name') == 'regularization' and record['verification'] == 'unverified' for record in controls.values())
    h_default = result(call(gateway, 'run_status', dict(name='H-original')))['scheduler_signal']
    assert h_default['boundary_declarations'][1]['declaration']['interpretation'] == declarations[1]['interpretation']
    assert all('declaration' not in reference for reference in h_default['boundary_references'])
    assert 'user_required' not in json.dumps(h_default)
    assert not any(token in json.dumps(h_default) for token in ('artifact_ref', 'run_id', 'sha256'))

    invoke(gateway, 'W', 'science.experiment.v1', {'subject': 'H-original.output'})
    worker = attached_worker(runtime, root, 'W')
    opened = worker.call_tool('worker_open_assignment', {})
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    hypothesis = next(item for item in assignment['inputs'] if item['source_name'] == 'hypothesis_portfolio')
    assert hypothesis['scientific_view']['boundary_application'] == 'assigned_subject_boundary'
    assert len(hypothesis['scientific_view']['handoff']['boundary_declarations']) == len(controls)
    recovered, handle = full_boundary(worker, source='hypothesis_portfolio', key='operator-rule')
    assert canonical_json(recovered['declaration']) == canonical_json(controls['operator-rule']['declaration'])
    assert not any(token in json.dumps(recovered) for token in ('artifact_ref', 'run_id', 'sha256'))
    with pytest.raises(WorkerToolError, match="offset exceeds"):
        worker.call_tool('worker_reference_read', dict(view='boundaries', source='hypothesis_portfolio', action='read', reference=handle, offset=999999))
    # W references the assigned H rule, even when its citation was unverified.
    w_refs = [dict(source_key='hypothesis_portfolio', boundary_key=key) for key in ('no-val-training', 'operator-rule', 'bad-quote', 'missing-declaration')]
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(payload=dict(summary='The bounded test is unresolved.',
        outcome='inconclusive', remaining_question='A should assess the derived rule.', adopted_stages=[]), handoff=dict(boundary_references=w_refs))))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    w_run = runtime.runs.status(worker._run_id)
    assert w_run.signal.boundary_references[2]['effect'] == 'assigned_subject_boundary'
    assert w_run.signal.boundary_references[2]['declaration']['verification'] == 'unverified'
    assert w_run.signal.boundary_references[3]['verification'] == 'unverified'
    assert w_run.signal.boundary_references[3]['effect'] == 'unresolved'

    invoke(gateway, 'A', 'science.result.analyze.v1', {'subject': 'W.output'})
    report = dict(summary='The stronger operator rule is H-derived, beyond the no-val-training constraint.',
        overall_verdict='inconclusive', claim_allowed=False, remaining_contradiction='Clarify a valid revised operator rule.',
        next_action='H: explicitly revise operator-rule, retain no-val-training, using hypothesis_portfolio and experiment_results.')
    _, _, analysis = submit(runtime, root, 'A', report,
        [declaration('proposal', 'Consider relaxing the derived operator rule only.', source=None)],
        [dict(source_key='hypothesis_portfolio', boundary_key='operator-rule')])
    assert analysis.signal.boundary_declarations[0]['effect'] == 'owner_statement'
    assert analysis.signal.boundary_references[0]['effect'] == 'referenced_owner_statement'
    assert runtime.runs.status(original.run_id).signal == original.signal

    revised_payload = deepcopy(h_payload)
    revised_payload['hypotheses'][0]['scope'] = 'Use a justified operator estimator without merging val into training.'
    revised_payload['contradiction'] = 'The derived operator rule was stronger than the true user constraint.'
    invoke(gateway, 'H-revised', 'science.hypothesis.propose.v1', {'subject': 'user-task', 'previous_hypotheses': 'H-original.output', 'result_analysis': 'A.output'})
    revised_declarations = [declarations[0], declaration('operator-rule-v2', revised_payload['hypotheses'][0]['scope'],
        hypothesis_key='mechanism', interpretation='Explicitly revises H-derived operator-rule; no-val-training is retained.',
        revises=[dict(source_key='previous_hypotheses', boundary_key='operator-rule')])]
    reader, _, revised = submit(runtime, root, 'H-revised', revised_payload, revised_declarations,
        [dict(boundary_key=item['boundary_key']) for item in revised_declarations])
    revision = revised.signal.boundary_declarations[1]['revision_checks'][0]
    assert revision['verification'] == 'matched'
    assert revision['resolved_source']['artifact_ref'] == original.output_ref.model_dump(mode='json')
    assert 'declaration' not in revision  # No recursively copied ancestor tree.
    old_payload = json.loads(runtime.artifacts.read(original.output_ref))
    assert old_payload['hypotheses'][0]['predictions'] == revised_payload['hypotheses'][0]['predictions']
    assert old_payload['hypotheses'][0]['scope'] == h_payload['hypotheses'][0]['scope']
    public = result(call(gateway, 'run_status', dict(name='H-revised')))['scheduler_signal']
    assert public['boundary_declarations'][1]['revision_checks'][0]['resolved_source']['boundary_key'] == 'operator-rule'
    assert not any(token in json.dumps(public) for token in ('artifact_ref', 'run_id', 'sha256'))
    # Restore immutable history from an active owner assignment, not a completed child.
    invoke(gateway, 'history-reader', 'science.hypothesis.propose.v1', {'subject': 'user-task', 'previous_hypotheses': 'H-revised.output'})
    from scidiscovery.artifact_agent.runtime import open_runtime
    reopened = open_runtime(project_root=tmp_path/'project', state_root=tmp_path/'state',
        worker_backend='local', local_workspace_root=tmp_path/'project/.scidiscovery-runs')
    reopened.runs.operation_catalog = catalog
    reader = attached_worker(reopened, root, 'history-reader'); reader.call_tool('worker_open_assignment', {})
    history, _ = full_boundary(reader, history='H-original', key='operator-rule', limit=1024)
    assert canonical_json(history['declaration']) == canonical_json(controls['operator-rule']['declaration'])


def test_generic_plugin_envelope_and_compact_oversize_preserve_source_checks(tmp_path):
    catalog, runtime, _, _, root = _system(tmp_path)
    _invoke(root, 'plugin')
    worker = _worker(catalog, runtime)
    opened = worker.call_tool('worker_open_assignment', {})
    value = json.loads(_envelope())
    value['boundary_declarations'] = [declaration('plugin-boundary', 'Generic plugin boundary.', source='source_table', quote='sample,value')]
    value['handoff']['boundary_references'] = [dict(boundary_key='plugin-boundary')]
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(value))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    signal = runtime.runs.status(worker._run_id).signal.model_dump(mode='json')
    record = signal['boundary_declarations'][0]
    record['declaration']['interpretation'] = '界' * 2048
    compact, omissions = compact_handoff(signal)
    projected = compact['boundary_declarations'][0]
    assert projected['boundary_key'] == 'plugin-boundary'
    assert projected['producer']['output_name'] == 'plugin.output'
    assert projected['source_checks'][0]['verification'] == 'matched'
    assert 'omission' in projected and '界' not in json.dumps(projected)
    assert projected['omission'] == 'complete_quote_and_interpretation_omitted_together'
    assert not {'interpretation', 'evidence', 'statement'} & projected.keys()
    assert projected['owner_read']['output_name'] == 'plugin.output'
    assert projected['owner_read']['boundary_key'] == 'plugin-boundary'
    assert projected['owner_read']['view'] == 'boundaries'
    assert not any(token in json.dumps(compact) for token in ('artifact_ref', 'run_id', 'sha256'))
    assert record['source_checks'][0]['artifact_ref']


@pytest.mark.parametrize('quote', [None, '不得', QUOTE], ids=['absent', 'short-bytes', 'complete-bytes'])
def test_real_source_location_and_quote_never_verify_stronger_interpretation(tmp_path, quote):
    _, runtime, _, _, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    result(call(gateway, 'artifact_ingest_text', dict(name='goal', text=USER)))
    invoke(gateway, 'H', 'science.hypothesis.propose.v1', {'subject': 'goal'})
    payload = _proposal(hypothesis_keys=('mechanism',)); payload.pop('research_objective_key')
    stronger = 'The owner extends this to every operator, without semantic verification.'
    payload['hypotheses'][0]['scope'] = stronger
    authored = declaration('stronger', stronger, quote=quote, interpretation=stronger, hypothesis_key='mechanism')
    _, _, sealed = submit(runtime, root, 'H', payload, [authored], [dict(boundary_key='stronger')])
    record = sealed.signal.boundary_declarations[0]
    check = record['source_checks'][0]
    assert check['source_location_verification'] == 'matched'
    assert check['quote_verification'] == ('absent' if quote is None else 'matched')
    assert check['verification'] == ('unverified' if quote is None else 'matched')
    assert check['verification_scope'] == 'quoted_bytes_only'
    assert record['verification'] == record['interpretation_verification'] == 'unverified'
    compact = result(call(gateway, 'run_status', dict(name='H')))['scheduler_signal']
    public = compact['boundary_declarations'][0]
    assert public['declaration']['evidence'][0]['quote'] == quote
    assert public['declaration']['interpretation'] == stronger
    assert public['authority'] == 'owner_interpretation' and 'user_required' not in json.dumps(compact)
    assert compact['boundary_references'][0]['verification_scope'] == 'declaration_identity_only'
    invoke(gateway, 'W', 'science.experiment.v1', {'subject': 'H.output'})
    worker = attached_worker(runtime, root, 'W'); opened = worker.call_tool('worker_open_assignment', {})
    recovered, _ = full_boundary(worker, source='hypothesis_portfolio', key='stronger')
    assert recovered['declaration'] == public['declaration']
    assert recovered['interpretation_verification'] == 'unverified'
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    hypothesis = next(item for item in assignment['inputs'] if item['source_name'] == 'hypothesis_portfolio')
    assert hypothesis['scientific_view']['boundary_application'] == 'assigned_subject_boundary'


def test_historical_aggregate_match_does_not_promote_absent_quote():
    original = dict(producer=dict(output_name='old-H.output', operation_id='thirdparty.H', run_id='PRIVATE'),
        declaration=declaration('old', 'Owner interpretation.', quote=None),
        source_checks=[dict(source_key='subject', locator='text', verification='matched')],
        verification='matched', authority='owner_interpretation', effect='owner_statement')
    frozen = deepcopy(original)
    public = public_boundary_record(original)
    assert public['source_checks'][0]['quote_verification'] == 'absent'
    assert public['source_checks'][0]['verification'] == 'unverified'
    assert public['source_checks'][0]['source_location_verification'] == 'unverified'
    assert public['interpretation_verification'] == public['verification'] == 'unverified'
    assert original == frozen


def test_real_root_boundary_collections_share_budget_and_keep_quote_interpretation_pairs(tmp_path, record_property):
    _, runtime, _, _, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    result(call(gateway, 'artifact_ingest_text', dict(name='goal', text=USER)))
    invoke(gateway, 'large-H', 'science.hypothesis.propose.v1', {'subject': 'goal'})
    payload = _proposal(hypothesis_keys=('mechanism',)); payload.pop('research_objective_key')
    declarations = [declaration('h.'+str(index), 'Owner statement. '*70,
        interpretation='Owner interpretation. '*60, hypothesis_key='mechanism') for index in range(4)]
    submit(runtime, root, 'large-H', payload, declarations)
    invoke(gateway, 'large-W', 'science.experiment.v1', {'subject': 'large-H.output'})
    own = [declaration('w.'+str(index), 'Worker statement. '*70,
        interpretation='Worker interpretation. '*60, source=None) for index in range(4)]
    references = [dict(source_key='hypothesis_portfolio', boundary_key=item['boundary_key']) for item in declarations]
    _, _, run = submit(runtime, root, 'large-W', dict(summary='Scoped result.', outcome='inconclusive',
        remaining_question='Analyze the existing boundaries.', adopted_stages=[]), own, references)
    signal = run.signal.model_dump(mode='json')
    without = {key: value for key, value in signal.items() if not key.startswith('boundary_')}
    baseline, _ = compact_handoff(without)
    compact, omissions = compact_handoff(signal)
    fields = ('boundary_declarations', 'boundary_references')
    block = {field: compact.get(field, []) for field in fields}
    block['omitted_items'] = {field: len(signal[field])-len(compact.get(field, [])) for field in fields}
    assert len(canonical_json(block)) <= COMPACT_BOUNDARY_BYTES
    assert omissions or any('omission' in entry for field in fields for entry in compact.get(field, []))
    for field in fields:
        for entry in compact.get(field, []):
            if 'omission' in entry:
                assert 'declaration' not in entry
                assert entry['omission'] == 'complete_quote_and_interpretation_omitted_together'
                assert entry['owner_read']['boundary_key']
            else:
                owner = entry['declaration']
                authored = owner['declaration'] if 'producer' in owner else owner
                assert authored['interpretation']
                assert all('quote' in citation for citation in authored['evidence'])
    response = result(call(gateway, 'run_status', dict(name='large-W')))
    assert response['scheduler_signal'] == compact
    public_block = {field: response['scheduler_signal'].get(field, []) for field in fields}
    public_block['scheduler_signal_omissions'] = response.get('scheduler_signal_omissions', {})
    assert len(canonical_json(public_block)) <= COMPACT_BOUNDARY_BYTES
    assert response['name'] == 'large-W' and response['output_metadata']['artifact_name'] == 'large-W.output'
    assert not any(token in json.dumps(compact) for token in ('artifact_ref', 'run_id', 'sha256'))
    measurements = dict(boundary_block_bytes=len(canonical_json(block)),
        root_boundary_wrapper_bytes=len(canonical_json(public_block)),
        compact_handoff_bytes=len(canonical_json(compact)),
        compact_increment_bytes=len(canonical_json(compact))-len(canonical_json(baseline)),
        root_response_bytes=len(canonical_json(response)),
        declarations_preserved=len(compact.get('boundary_declarations', [])),
        references_preserved=len(compact.get('boundary_references', [])),
        references_omitted=omissions.get('boundary_references', 0))
    for key, value in measurements.items():
        record_property(key, value)
    print('BOUNDARY_BYTE_MEASUREMENTS', json.dumps(measurements, sort_keys=True))


def test_actual_authoring_schema_and_prompts_define_science_only_fields(tmp_path):
    _, runtime, _, _, root = _system(tmp_path)
    root.call_tool('artifact_ingest_text', dict(name='goal', text=USER))
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    invoke(gateway, 'schema-owner', 'science.hypothesis.propose.v1', {'subject': 'goal'})
    worker = attached_worker(runtime, root, 'schema-owner'); opened = worker.call_tool('worker_open_assignment', {})
    assignment = json.loads(Path(opened['assignment_path']).read_text())
    schema = json.loads((Path(opened['workspace_path'])/'schema/result.schema.json').read_text())
    properties = schema['$defs']['BoundaryDeclaration']['properties']
    assert set(properties) == {'boundary_key', 'statement', 'evidence', 'interpretation', 'hypothesis_key', 'parameter_name', 'revises'}
    assert schema['properties']['boundary_declarations']['maxItems'] == 32
    assert not {'producer', 'effect', 'authority', 'artifact_ref', 'verification'} & properties.keys()
    assert 'never the interpretation' in assignment['role_instructions']
    assert 'handoff.boundary_references' in assignment['role_instructions']
    from scidiscovery.plugin_runtime.results import materialize_hypothesis_boundaries
    value = dict(payload=dict(hypotheses=[dict(hypothesis_key='h'*256, scope='Exact scope.', parameters=[])]))
    materialize_hypothesis_boundaries(value)
    assert len(value['boundary_declarations'][0]['boundary_key']) < 256
    full = dict(payload=deepcopy(value['payload']), boundary_declarations=[
        dict(boundary_key='custom.'+str(index), statement='Owner statement.', interpretation='Owner interpretation.')
        for index in range(128)])
    materialize_hypothesis_boundaries(full)
    assert len(full['boundary_declarations']) == 128
    assert full['payload'] == value['payload']




def test_existing_evidence_extraction_source_remains_produced_and_exactly_readable(tmp_path):
    from tests.operations.test_general_transform_operations import _intake
    _, runtime, _, _, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    result(call(gateway, 'artifact_ingest_text', dict(name='user-goal', text=USER)))
    paper_text = 'Paper fixture: one scoped target. ' + QUOTE
    result(call(gateway, 'artifact_ingest_text', dict(name='paper-original', text=paper_text)))
    # Root dispatching initial H does not claim evidence sufficiency. The owner
    # may request extraction through the existing handoff, without a skip form.
    invoke(gateway, 'H-needs-evidence', 'science.hypothesis.propose.v1', {'subject': 'user-goal'})
    preliminary = attached_worker(runtime, root, 'H-needs-evidence')
    preliminary_opened = preliminary.call_tool('worker_open_assignment', {})
    initial = _proposal(); initial.pop('research_objective_key')
    requested = 'Evidence extraction: identify the scoped target from paper-original before revising the hypothesis.'
    Path(preliminary_opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1,
        payload=initial, handoff=dict(verdict='inconclusive', summary='The required paper evidence remains unextracted.',
            missing_inputs=['Extracted scoped target.'], next_actions=[requested]))))
    assert preliminary.call_tool('worker_submit_result', {})['state'] == 'completed'
    direction = result(call(gateway, 'run_status', dict(name='H-needs-evidence')))['scheduler_signal']
    assert direction['next_actions'] == [requested]
    assert direction['missing_inputs'] == ['Extracted scoped target.']
    invoke(gateway, 'extraction', 'science.evidence.extract.v1', {'source_material': 'paper-original'})
    payload = json.loads(canonical_json(_intake().model_dump(mode='json')).replace(b'"paper"', b'"source_material"'))
    payload['scientific_foundation']['summary'] = QUOTE
    _, _, extraction = submit(runtime, root, 'extraction', payload)
    invoke(gateway, 'H-from-extracted', 'science.hypothesis.propose.v1',
        {'subject': 'user-goal', 'result_analysis': 'extraction.output'})
    worker = attached_worker(runtime, root, 'H-from-extracted')
    opened = worker.call_tool('worker_open_assignment', {})
    listing = worker.call_tool('worker_reference_read', dict(source='result_analysis'))
    assert listing['references']
    original = worker.call_tool('worker_reference_read', dict(source='result_analysis', action='read',
        reference=listing['references'][0]['reference']))
    assert original['fragment'] == paper_text
    proposal = _proposal(hypothesis_keys=('mechanism',)); proposal.pop('research_objective_key')
    authored = declaration('extracted-boundary', 'Interpret the extracted observation within its scope.',
        source='result_analysis', locator='/scientific_foundation/summary')
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1,
        payload=proposal, boundary_declarations=[authored], handoff=dict(verdict='inconclusive',
            summary='H used the sealed extracted source.', boundary_references=[dict(boundary_key='extracted-boundary')]))))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    hypothesis = runtime.runs.status(worker._run_id)
    check = hypothesis.signal.boundary_declarations[0]['source_checks'][0]
    assert check['verification'] == 'matched'
    assert check['origin'] == 'produced_material'
    assert check['artifact_ref'] == extraction.output_ref.model_dump(mode='json')
    public = result(call(gateway, 'run_status', dict(name='H-from-extracted')))['scheduler_signal']
    assert public['boundary_declarations'][0]['source_checks'][0]['origin'] == 'produced_material'
    assert public['boundary_declarations'][0]['authority'] == 'owner_interpretation'
    assignment = json.loads(Path(opened['assignment_path']).read_text())
    assert 'evidence extraction -> H -> W -> A' in assignment['role_instructions']
    assert 'Root dispatching H is not a finding that evidence is sufficient' in assignment['role_instructions']
