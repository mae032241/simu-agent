"""Production output declarations and sealed decision reads stay aligned."""
import json
import pytest

from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD
from curve_figure_evidence.plugin import PLUGIN as FIGURE
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import operation_primary_output
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_general_transform_operations import _root, _register, _intake
from tests.operations.test_historical_compatibility_paths import _complete


@pytest.fixture(scope='module')
def catalog():
    return compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD, FIGURE))


def _schema_path(root, path):
    current = root
    for token in path.lstrip('/').split('/'):
        while '$ref' in current:
            ref = current['$ref']
            assert ref.startswith('#/')
            current = root
            for part in ref[2:].split('/'):
                current = current[part]
        if 'anyOf' in current:
            current = next(part for part in current['anyOf'] if part.get('type') != 'null')
            while '$ref' in current:
                current = root['$defs'][current['$ref'].split('/')[-1]]
        token = token.replace('~1', '/').replace('~0', '~')
        assert token in current.get('properties', {}), path
        current = current['properties'][token]


def test_all_twelve_production_agent_decision_paths_exist_in_primary_schema(catalog):
    agents = [catalog.operation(key) for key in catalog.operation_ids()
              if catalog.operation(key).spec.executor.kind == 'agent']
    assert len(agents) == 12
    problems = []
    for operation in agents:
        schema = operation.output_contracts[operation_primary_output(operation).name]
        for path in operation.spec.decision_fields:
            try:
                _schema_path(schema, path)
            except AssertionError:
                problems.append((operation.spec.operation_id, path))
    assert not problems, problems


def _extracted(tmp_path, catalog):
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    _register(runtime, instance, name='source', raw=b'Frozen source.', kind='source', schema='opaque', media_type='text/plain')
    payload = json.loads(_intake().canonical_json().replace(b'"paper"', b'"source_material"'))
    payload['scientific_foundation']['open_questions'] = ['Does the unresolved condition hold?']
    _complete(runtime, root, 'author', 'science.evidence.extract.v1', {'source_material': 'source'}, payload)
    return runtime, instance, root, payload


def _values(result):
    return {item['pointer']: item['value'] for item in result['selected_output']['items'] if item['status'] == 'selected'}


@pytest.mark.parametrize('status,verdict', [('fail','blocked'), ('unknown','inconclusive'), ('pass','pass')])
def test_completed_audit_default_exposes_actual_checks(tmp_path, catalog, status, verdict):
    runtime, instance, root, _ = _extracted(tmp_path, catalog)
    payload = {'checks': [{'check_key': 'trace', 'subject': 'Frozen source', 'status': status,
        'basis': 'Exact source checked independently.', 'evidence_keys': ['source_material']}],
        'evidence': [{'source_key':'source_material','source_type':'frozen_input','locator':'line 1'}]}
    _complete(runtime, root, 'audit', 'science.evidence.audit.intake.v1',
        {'scientific_intake':'author.output','source_material':'source'}, payload, verdict=verdict)
    result = root.call_tool('run_status', {'name':'audit'})
    assert _values(result)['/checks'] == payload['checks']
    assert result['scheduler_signal']['verdict'] == verdict
    assert all(item['status'] != 'missing' for item in result['selected_output']['items'])


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('removed', [False, True])
def test_historical_reads_frozen_decision_fields_or_explicit_navigation(tmp_path, catalog, legacy, removed):
    runtime, instance, root, payload = _extracted(tmp_path, catalog)
    current = root.call_tool('run_status', {'name':'author'})
    run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='author')
    if legacy:
        with runtime.runs._connect() as connection:
            connection.execute('UPDATE runs SET decision_fields_json=NULL WHERE run_id=?', (run_id,))
    changed = GENERAL.model_copy(update={'operations': tuple(op.model_copy(update={'version':'next', 'decision_fields':('no_longer_exists',),
        'operation_id':'science.evidence.extract.retired-fixture.v1' if removed else op.operation_id})
        if op.operation_id == 'science.evidence.extract.v1' else op for op in GENERAL.operations)})
    replacement = compile_catalog((CORE_PLUGIN, changed, CURVE, TCAD, FIGURE))
    runtime.runs.operation_catalog = root.facade._operation_catalog = replacement
    result = root.call_tool('run_status', {'name':'author'})
    assert result['operation_contract_status'] == result['sealed_output_status'] == 'historical'
    if legacy:
        assert result['default_output_unavailable'] == 'decision_fields_not_recorded'
        assert result['selected_output'] is None
        assert result['output_index']['status'] == 'available'
        assert len(canonical_json(result['output_index'])) <= 8192
    else:
        assert _values(result) == _values(current)
        assert _values(result)['/scientific_foundation/open_questions'] == payload['scientific_foundation']['open_questions']
    selected = root.call_tool('run_status', {'name':'author', 'output_paths':['/scientific_foundation/summary']})
    assert _values(selected)['/scientific_foundation/summary'] == payload['scientific_foundation']['summary']
    from scidiscovery.artifact_agent.service.run_records import RunContractUnavailable
    with pytest.raises(RunContractUnavailable):
        runtime.runs.compiled_operation(runtime.runs.status(run_id))


@pytest.mark.parametrize('verdict', ['fail', 'invalid_study'])
def test_default_analysis_retains_formal_verdict_and_claim_permission(tmp_path, verdict):
    from tests.operations.test_tcad_result_analysis import analysis_system, analysis_report, write_analysis
    from tests.operations.worker_fixtures import attached_worker
    system = analysis_system(tmp_path)
    _, runtime, root, request, _, _ = system
    root.call_tool('operation_invoke', request)
    worker = attached_worker(runtime, root, request['name'])
    opened = worker.call_tool('worker_open_assignment', {})
    report = analysis_report()
    report.update(overall_verdict=verdict, claim_allowed=False, summary='The bounded study needs further work.', next_action='Inspect the original validity evidence.')
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    result = root.call_tool('run_status', {'name':request['name']})
    assert result['scheduler_signal']['verdict'] == 'blocked'
    assert _values(result)['/overall_verdict'] == verdict
    assert _values(result)['/claim_allowed'] is False
    assert _values(result)['/next_action'] == report['next_action']


def test_active_and_failed_runs_never_read_scientific_draft(tmp_path, catalog, monkeypatch):
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    _register(runtime, instance, name='source', raw=b'Exact source.', kind='source', schema='opaque', media_type='text/plain')
    root.call_tool('operation_invoke', {'name':'unfinished','operation_id':'science.evidence.extract.v1',
        'instruction':'Inspect only the exact supplied source.',
        'inputs':[{'port':'source_material','artifact_names':['source']}]})
    def no_payload_read(*args, **kwargs):
        raise AssertionError('A non-completed decision read must not read artifacts')
    monkeypatch.setattr(runtime.artifacts, 'read', no_payload_read)
    result = root.call_tool('run_status', {'name':'unfinished'})
    assert result['state']=='queued' and result['sealed_output_status']=='unavailable'
    assert 'selected_output' not in result and 'output_index' not in result
    root.call_tool('run_record_failure', {'name':'unfinished','reason':'Fixture stopped before authoring.',
        'expected_state':'queued', 'expected_last_activity_at':result['last_activity_at']})
    result = root.call_tool('run_status', {'name':'unfinished'})
    assert result['state']=='failed' and result['sealed_output_status']=='unavailable'
    assert 'selected_output' not in result and 'output_index' not in result
    assert 'decision_fields' not in result and 'decision_fields_json' not in result
