"""E1: original task quotes through sealed H/W/A, compact and original readers.

The source lane checks citation bytes and delivered author guidance, not an
automatic understanding of requirements or live scientific decision quality.
"""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_gateway import UnifiedMCPRouter
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_boundary_provenance import declaration, full_boundary, invoke, submit
from tests.operations.test_hypothesis_objective_boundary import _proposal
from tests.operations.test_l2_run_invariants import _system
from tests.operations.test_unified_mcp import call, result
from tests.operations.worker_fixtures import attached_worker


EXPLORATION = 'Continue exploring justified directions while the research budget permits.'
TASK = ('# Research task\nImprove the stated predictor.\n'
    '## Requirements\nDo not overwrite original observations.\n'
    'Completion requires supported target conditions and a reproducible delivery.\n'
    + EXPLORATION + '\n## Example\nA small comparison is an example, not a mandated method.\n')


def proposal_payload():
    value = _proposal(hypothesis_keys=('mechanism',))
    value.pop('research_objective_key')
    return value


def assignment(opened):
    return json.loads(Path(opened['assignment_path']).read_text())


def deliver(worker, opened, payload, references):
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(schema_version=1,
        payload=payload, handoff=dict(verdict='inconclusive', summary='Bounded owner conclusion.',
            boundary_references=references))))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


@pytest.mark.parametrize('occurrences', ['unique', 'repeated', 'overlapping'])
def test_plain_heading_quote_and_original_exploration_survive_h_w_a(tmp_path, occurrences):
    _, runtime, _, _, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    text = TASK + ('\nExample repeats: ' + EXPLORATION if occurrences == 'repeated' else '\naaa' if occurrences == 'overlapping' else '')
    quote = 'aa' if occurrences == 'overlapping' else EXPLORATION
    result(call(gateway, 'artifact_ingest_text', dict(name='task-original', text=text)))
    invoke(gateway, 'H', 'science.hypothesis.propose.v1', {'subject': 'task-original'})
    authored = [
        declaration('exploration', 'Owner interpretation of the original exploration requirement.',
            locator='## Requirements', quote=quote, hypothesis_key='mechanism'),
        declaration('no-quote', 'No quotation is a source-unverified interpretation.', locator='## Requirements', quote=None),
        declaration('short-quote', 'A short byte match cannot impose an extra method.', locator='## Requirements', quote='Continue'),
        declaration('explicit-pointer', 'An explicit pointer is not a heading hint.', locator='/Requirements', quote=EXPLORATION),
    ]
    _, h_opened, h_run = submit(runtime, root, 'H', proposal_payload(), authored,
        [dict(boundary_key='exploration')])
    controls = {entry['declaration']['boundary_key']: entry for entry in h_run.signal.boundary_declarations}
    check = controls['exploration']['source_checks'][0]
    assert check['source_location_verification'] == 'unverified'
    assert check['quote_verification'] == check['verification'] == 'matched'
    assert check['quote_match_scope'] == 'source_text'
    assert check['quote_match_multiplicity'] == ('unique' if occurrences == 'unique' else 'multiple')
    assert not {'offset', 'location', 'start', 'end'} & check.keys()
    assert controls['no-quote']['source_checks'][0]['quote_verification'] == 'absent'
    assert controls['no-quote']['source_checks'][0]['verification'] == 'unverified'
    assert controls['short-quote']['source_checks'][0]['quote_verification'] == 'matched'
    assert controls['explicit-pointer']['source_checks'][0]['quote_verification'] == 'unverified'
    assert all(entry['interpretation_verification'] == 'unverified' for entry in controls.values())
    h_assignment = assignment(h_opened)
    assert 'original goal, prohibitions,' in h_assignment['role_instructions']
    assert 'completion conditions, exploration requirements and method examples' in h_assignment['role_instructions']
    assert 'State\nunknown coverage honestly' in h_assignment['role_instructions']
    schema = json.loads((Path(h_opened['workspace_path']) / 'schema/result.schema.json').read_text())
    assert 'never falls back' in schema['$defs']['SourceReference']['properties']['locator']['description']
    public = result(call(gateway, 'run_status', dict(name='H')))['scheduler_signal']['boundary_declarations'][0]
    assert public['source_checks'][0]['quote_match_multiplicity'] == check['quote_match_multiplicity']
    assert public['declaration']['evidence'][0]['quote'] == quote
    assert public['interpretation_verification'] == 'unverified'
    assert 'user_required' not in json.dumps(public)
    assert not any(token in json.dumps(public) for token in ('artifact_ref', 'run_id', 'sha256'))

    invoke(gateway, 'W', 'science.experiment.v1', {'subject': 'H.output'})
    w_worker = attached_worker(runtime, root, 'W')
    w_opened = w_worker.call_tool('worker_open_assignment', {})
    recovered, _ = full_boundary(w_worker, source='hypothesis_portfolio', key='exploration')
    assert recovered['source_checks'] == public['source_checks']
    hypothesis = next(item for item in assignment(w_opened)['inputs'] if item['source_name'] == 'hypothesis_portfolio')
    assert hypothesis['scientific_view']['boundary_application'] == 'assigned_subject_boundary'
    deliver(w_worker, w_opened, dict(summary='The current target remains unresolved.',
        outcome='inconclusive', remaining_question='Assess the original exploration requirement.', adopted_stages=[]),
        [dict(source_key='hypothesis_portfolio', boundary_key='exploration')])
    invoke(gateway, 'A', 'science.result.analyze.v1', {'subject': 'W.output'})
    direction = 'H: assess the uncovered exploration requirement using objective_source and hypothesis_portfolio.'
    a_worker = attached_worker(runtime, root, 'A')
    a_opened = a_worker.call_tool('worker_open_assignment', {})
    a_assignment = assignment(a_opened)
    original = next(item for item in a_assignment['inputs'] if item['source_name'] == 'objective_source')
    assert (Path(a_opened['workspace_path']) / original['relative_path']).read_text() == text
    assert 'Before recommending closeout, reread relevant objective_source originals' in a_assignment['role_instructions']
    assert 'exploration\nrequirements and method examples' in a_assignment['role_instructions']
    a_boundary, _ = full_boundary(a_worker, source='hypothesis_portfolio', key='exploration')
    assert a_boundary['source_checks'] == public['source_checks']
    deliver(a_worker, a_opened, dict(summary='Original exploration coverage remains unknown.',
        overall_verdict='inconclusive', claim_allowed=False, remaining_contradiction='The original exploration requirement is not covered.',
        next_action=direction), [dict(source_key='hypothesis_portfolio', boundary_key='exploration')])
    compact = result(call(gateway, 'run_status', dict(name='A')))['scheduler_signal']
    assert compact['next_actions'] == [direction]
    assert compact['boundary_references'][0]['reference']['boundary_key'] == 'exploration'
    assert compact['boundary_references'][0]['declaration']['source_checks'] == public['source_checks']


def test_structured_pointer_never_uses_plaintext_hint_fallback_or_user_labels(tmp_path):
    _, runtime, _, _, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    result(call(gateway, 'artifact_ingest_text', dict(name='goal', text=TASK)))
    material = runtime.artifacts.register(canonical_json(dict(constraints=dict(explicit=EXPLORATION), extra='Other text.')),
        ArtifactRegistration(kind='scientific_note', schema_id='thirdparty.note.v1', payload_schema_version=1,
            media_type='application/json', creator=runtime.actor, labels={'source_origin': 'user_via_scheduler'}),
        idempotency_key='scientific-json')
    runtime.scheduler_bindings.bind(instance=root.facade.instance, namespace='artifact', name='material', object_id=material.artifact_id)
    invoke(gateway, 'H-structured', 'science.hypothesis.propose.v1', {'subject': 'goal', 'result_analysis': 'material'})
    authored = [declaration(key, 'Owner interpretation, not user authorization.', source='result_analysis', locator=locator, quote=EXPLORATION)
        for key, locator in [('correct', '/constraints/explicit'), ('missing', '/not-present'), ('wrong-value', '/extra'), ('heading', '## Constraints')]]
    _, _, sealed = submit(runtime, root, 'H-structured', proposal_payload(), authored)
    records = {record['declaration']['boundary_key']: record for record in sealed.signal.boundary_declarations}
    checks = {item['boundary_key']: records[item['boundary_key']]['source_checks'][0] for item in authored}
    assert checks['correct']['source_location_verification'] == checks['correct']['quote_verification'] == 'matched'
    assert checks['correct']['quote_match_scope'] == 'selected_value'
    assert checks['correct']['quote_match_multiplicity'] == 'unique'
    assert checks['wrong-value']['source_location_verification'] == 'matched'
    assert all(checks[key]['quote_verification'] == 'unverified' for key in ('missing', 'wrong-value', 'heading'))
    assert all(checks[key]['origin'] == 'frozen_material' for key in ('correct', 'missing', 'wrong-value', 'heading'))
    compact = result(call(gateway, 'run_status', dict(name='H-structured')))['scheduler_signal']
    assert all(record['authority'] == 'owner_interpretation' and record['interpretation_verification'] == 'unverified'
        for record in compact['boundary_declarations'])


def test_markdown_scientific_material_matches_bytes_without_becoming_user_text(tmp_path):
    _, runtime, _, _, root = _system(tmp_path)
    gateway = UnifiedMCPRouter(root, worker_backend='local')
    result(call(gateway, 'artifact_ingest_text', dict(name='goal', text=TASK)))
    note = runtime.artifacts.register(TASK.encode(), ArtifactRegistration(kind='scientific_note',
        schema_id='thirdparty.note.v1', payload_schema_version=1, media_type='text/markdown',
        creator=runtime.actor, labels={'source_origin': 'user_via_scheduler'}), idempotency_key='scientific-markdown')
    runtime.scheduler_bindings.bind(instance=root.facade.instance, namespace='artifact', name='note', object_id=note.artifact_id)
    invoke(gateway, 'H-markdown', 'science.hypothesis.propose.v1', {'subject': 'goal', 'result_analysis': 'note'})
    _, _, sealed = submit(runtime, root, 'H-markdown', proposal_payload(),
        [declaration('scientific-words', 'Owner interpretation of scientific material.', source='result_analysis',
            locator='## Requirements', quote=EXPLORATION)])
    check = sealed.signal.boundary_declarations[0]['source_checks'][0]
    assert check['quote_verification'] == 'matched' and check['source_location_verification'] == 'unverified'
    assert check['origin'] == 'frozen_material'
    compact = result(call(gateway, 'run_status', dict(name='H-markdown')))['scheduler_signal']['boundary_declarations'][0]
    assert compact['authority'] == 'owner_interpretation' and compact['interpretation_verification'] == 'unverified'
