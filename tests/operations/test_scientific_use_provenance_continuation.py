"""Exact Transform families and adopted experiment stages preserve source limits."""
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.spec import ComponentRef
from tests.operations.test_general_transform_operations import _intake, _register, _root
from tests.operations.worker_fixtures import attached_worker


OBJECTIVE = {'objective_key': 'objective', 'intent': 'engineering', 'statement': 'Observe one bounded source.',
    'closure_requirements': [{'requirement_key': 'observation', 'description': 'Retain an observation.',
        'requirement_type': 'comparison_present', 'comparison_purposes': ['exploratory_diagnostic']}]}


def system(tmp_path):
    extract = next(op for op in PLUGIN.operations if op.operation_id == 'science.evidence.extract.v1')
    consumers = []
    for suffix, schema, resource in [('foundation', 'scidiscovery.scientific-foundation.v1', 'scientific_foundation_schema'),
                                     ('experiment', 'scidiscovery.experiment-report.v1', 'experiment_task_schema')]:
        consumers.append(extract.model_copy(update={'operation_id': f'science.fixture.consume_{suffix}.v1', 'review': None,
            'inputs': tuple(port.model_copy(update={'schema_id': schema, 'schema_resource': ComponentRef(resource),
                'media_types': ('application/json',), 'codec': ComponentRef('json_codec'),
                'usage': 'claim_evidence', 'exposure': 'on_demand', 'max_item_bytes': 1024 * 1024}) if port.name == 'source_material' else port
                for port in extract.inputs)}))
    project = next(op for op in PLUGIN.operations if op.operation_id == 'science.objective.project.v1')
    project = project.model_copy(update={'operation_id': 'science.fixture.project.v1', 'input_admission': None})
    plugins = [CORE_PLUGIN, PLUGIN.model_copy(update={'operations': (*PLUGIN.operations, *consumers, project)})]
    catalog = compile_catalog(plugins)
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    return runtime, instance, root


def consume(root, name, kind='foundation', action='operation_preflight'):
    return root.call_tool(action, {'name': 'consume', 'operation_id': f'science.fixture.consume_{kind}.v1',
        'instruction': 'Consume the exact scientific claim evidence.',
        'inputs': [{'port': 'source_material', 'artifact_names': [name]}]})


def artifact(runtime, instance, name):
    return runtime.artifacts.get_by_id(runtime.scheduler_bindings.resolve(
        instance=instance.instance_id, namespace='artifact', name=name))


@pytest.mark.parametrize('restricted', [False, True])
def test_historical_transform_uses_exact_bound_family_and_new_transform_preserves_limit(tmp_path, monkeypatch, restricted):
    runtime, instance, root = system(tmp_path)
    payload = _intake().model_dump(mode='json')
    payload['scientific_foundation']['objective_contract'] = {**OBJECTIVE, 'statement': payload['scientific_foundation']['objective']}
    _register(runtime, instance, name='intake', raw=canonical_json(payload), kind='scientific_intake',
        schema='scidiscovery.scientific-intake.v1', provisional=restricted)
    _register(runtime, instance, name='audit', raw=b'{}', kind='evidence_audit', schema='scidiscovery.evidence-audit.v1')
    original = runtime.artifacts.register
    def historical(content, registration, **kwargs):
        if 'transform_profile' in registration.labels:
            labels = {key: value for key, value in registration.labels.items()
                      if key not in {'scientific_claim_admissible', 'operation_invocation_name', 'operation_invocation_instance'}}
            registration = registration.model_copy(update={'labels': labels})
        return original(content, registration, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(runtime.artifacts, 'register', historical)
        root.call_tool('operation_invoke', {'name': 'split', 'operation_id': 'science.intake.split.v1', 'inputs': [
            {'port': 'scientific_intake', 'artifact_names': ['intake']},
            {'port': 'evidence_audit', 'artifact_names': ['audit']}]})
    foundation = artifact(runtime, instance, 'split.scientific_foundation')
    assert 'scientific_claim_admissible' not in foundation.labels
    before = runtime.artifacts.read(foundation.ref)
    # The same navigation name in another instance is not an origin candidate.
    other = runtime.scheduler_bindings.create_instance(name='other', title='Other', objective='Independent binding.')
    _register(runtime, other, name='split.scientific_foundation', raw=before, kind='scientific_foundation',
        schema='scidiscovery.scientific-foundation.v1', provisional=not restricted)
    from scidiscovery.artifact_agent.service.scientific_usage import scientific_use_restricted
    with monkeypatch.context() as patch:
        patch.setattr(runtime.artifacts, 'verify', lambda ref: pytest.fail('Restriction recovery must use metadata only'))
        assert scientific_use_restricted(runtime.runs, (foundation.ref,)) is restricted
    result = consume(root, 'split.scientific_foundation')
    assert result['admissible'] is not restricted, result
    if restricted:
        assert result['reason_code'] == 'input_scientific_claim_forbidden'
    root.call_tool('operation_invoke', {'name': 'objective', 'operation_id': 'science.fixture.project.v1',
        'inputs': [{'port': 'scientific_foundation', 'artifact_names': ['split.scientific_foundation']}]})
    assert (artifact(runtime, instance, 'objective').labels.get('scientific_claim_admissible') == 'false') is restricted
    assert runtime.artifacts.catalog(foundation.ref) == foundation
    assert runtime.artifacts.read(foundation.ref) == before


@pytest.mark.parametrize('adopt', [False, True])
def test_experiment_only_inherits_restrictions_from_adopted_stages(tmp_path, adopt):
    runtime, instance, root = system(tmp_path)
    _register(runtime, instance, name='objective', raw=canonical_json(OBJECTIVE), kind='research_objective',
        schema='scidiscovery.research-objective.v1')
    _register(runtime, instance, name='restricted', raw=b'bounded exploratory source', kind='source', schema='opaque',
        media_type='text/plain', provisional=True)
    root.call_tool('operation_invoke', {'name': 'experiment', 'operation_id': 'science.experiment.v1',
        'instruction': 'Retain an exploratory stage without claiming execution.', 'inputs': [
            {'port': 'research_objective', 'artifact_names': ['objective']},
            {'port': 'scientific_materials', 'artifact_names': ['restricted']}]})
    worker = attached_worker(runtime, root, 'experiment')
    opened = worker.call_tool('worker_open_assignment', {})
    source = next(item.source_name for item in runtime.runs.status(worker._run_id).inputs if item.port_name == 'scientific_materials')
    stage = worker.call_tool('worker_experiment_stage', {'stage': 'design', 'conclusion': 'Exploratory design.', 'materials': [source]})
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'payload': {
        'summary': 'Bounded experiment conclusion.', 'outcome': 'inconclusive', 'remaining_question': 'Execution is still needed.',
        'adopted_stages': [stage['reference']] if adopt else []}}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    report = artifact(runtime, instance, 'experiment.output')
    assert (report.labels.get('scientific_claim_admissible') == 'false') is adopt
    result = consume(root, 'experiment.output', 'experiment')
    assert result['admissible'] is not adopt, result
    if adopt:
        assert result['reason_code'] == 'input_scientific_claim_forbidden'


def test_independent_review_can_assess_restricted_subject_without_requalifying_it(tmp_path):
    from tests.operations.test_scientific_use_provenance import system as extraction_system, consume as consume_intake
    from tests.operations.test_scientific_attachments import finish
    runtime, root, author, opened, aliases = extraction_system(tmp_path)
    assert finish(author, opened, aliases['feedback'])['state'] == 'completed'
    subject = runtime.artifacts.catalog(runtime.runs.status(author._run_id).output_ref)
    original = runtime.artifacts.read(subject.ref)
    root.call_tool('operation_invoke', {'name': 'review', 'operation_id': 'science.object.review.v1',
        'instruction': 'Independently assess this exact restricted subject.',
        'inputs': [{'port': 'subject', 'artifact_names': ['evidence.output']}]})
    worker = attached_worker(runtime, root, 'review')
    opened = worker.call_tool('worker_open_assignment', {})
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'payload': {
        'verdict': 'pass', 'summary': 'The bounded exploratory statement is faithful.',
        'limitations': ['This review does not remove the source restriction.']}}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    review = runtime.artifacts.catalog(runtime.runs.status(worker._run_id).output_ref)
    assert review.labels.get('scientific_claim_admissible') != 'false'
    assert consume_intake(root, 'evidence.output')['reason_code'] == 'input_scientific_claim_forbidden'
    assert runtime.artifacts.catalog(subject.ref) == subject
    assert runtime.artifacts.read(subject.ref) == original
