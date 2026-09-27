import json
import pytest
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
from tests.operations.test_agent_contract_alignment import experiment_case, _partial_experiment, _review_run

@pytest.mark.parametrize('category', ['integrity_failure', 'admission_defect'])
def test_finalizer_fault_preserves_category_and_reason(tmp_path, monkeypatch, experiment_case, category):
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    intent, inputs = _partial_experiment(experiment_case)
    plan, _ = materialize_experiment_plan({
        'experiment_design_intent': canonical_json(intent),
        'research_objective': inputs['research_objective'],
        'hypothesis_portfolio': inputs['hypothesis_portfolio'],
    })
    runtime, run_id, workspace = _review_run(tmp_path, {'experiment_plan': plan})
    reason = 'TCAD bound input is unavailable in the workspace' if category == 'integrity_failure' else 'admitted execution_capability is invalid JSON'
    def fault(*args, **kwargs):
        raise RunCheckerError(reason, category=category)
    monkeypatch.setattr(runtime.runs, '_finalize_workspace', fault)
    state, details = runtime.runs.submit(run_id)
    value = runtime.runs.status(run_id)
    actual = {'state': state, 'reason': value.reason, 'diagnostic': runtime.runs.diagnostic_summary(value)['failure']}
    print(json.dumps({'injected_category': category, 'actual': actual}))
    assert state == 'failed'
    assert actual['diagnostic']['category'] == category
    assert reason in json.dumps(actual)

def test_bound_audit_subject_accepts_optional_citation(tmp_path):
    from pathlib import Path
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.operations.catalog import compile_catalog
    from tests.operations.test_general_transform_operations import _intake, _register, _root
    from tests.operations.test_historical_compatibility_paths import _complete
    catalog = compile_catalog((CORE_PLUGIN, PLUGIN))
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    _register(runtime, instance, name='source', raw=b'Frozen source.', kind='source', schema='opaque', media_type='text/plain')
    payload = json.loads(_intake().canonical_json().replace(b'"paper"', b'"source_material"'))
    intake = _complete(runtime, root, 'extracted', 'science.evidence.extract.v1', {'source_material': 'source'}, payload)
    operation = 'science.evidence.audit.intake.v1'
    request = {'name': 'audit', 'operation_id': operation,
        'inputs': [{'port': 'scientific_intake', 'artifact_names': [intake]},
                   {'port': 'source_material', 'artifact_names': ['source']}],
        'instruction': 'Audit the bound intake.'}
    assert root.call_tool('operation_preflight', request)['admissible']
    root.call_tool('operation_invoke', request)
    compiled = catalog.operation(operation)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=operation, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    payload = {'checks': [{'check_key': 'trace', 'subject': 'Bound intake', 'status': 'pass',
        'basis': 'Exact fixture.', 'evidence_keys': ['scientific_intake']}],
        'evidence': [{'source_key': 'scientific_intake', 'source_type': 'frozen_input', 'locator': '/scientific_foundation'}]}
    path = Path(opened['output_directory']) / 'result.json'
    def submit():
        path.write_bytes(canonical_json({'schema_version': 1, 'payload': payload,
            'handoff': {'verdict': 'pass', 'summary': 'Exact audit.'}}))
        return worker.call_tool('worker_submit_result', {})
    with_citation = submit()
    payload.pop('evidence')
    without_citation = submit()
    print(json.dumps({'with_optional_citation': with_citation, 'without_optional_citation_state': without_citation['state']}))
    assert without_citation['state'] == 'completed'
    assert with_citation['state'] == 'completed'

def test_author_gap_rejection_preserves_locator_reason(tmp_path):
    from tests.operations.test_l4_local_tcad import _system, _invoke, _debug_worker, _ImmediateDebugAdapter, _task_gap, _write_gap
    catalog, runtime, root, _ = _system(tmp_path, solver_kind='sprocess')
    inputs = [{'port': 'execution_capability', 'artifact_names': ['execution_capability']},
              {'port': 'experiment_plan', 'artifact_names': ['experiment_plan']}]
    _invoke(root, 'gap_author', 'tcad.deck.author.initial.v1', inputs)
    worker = _debug_worker(catalog, runtime, _ImmediateDebugAdapter(), tmp_path / 'unused-debug')
    opened = worker.call_tool('worker_open_assignment', {})
    gap = _task_gap()
    gap['affected_work'][0]['plan_locator'] = '/not_an_existing_plan_path'
    _write_gap(opened, raw=canonical_json(gap))
    reply = worker.call_tool('worker_submit_result', {})
    print(json.dumps({'gap_submit': reply}))
    assert reply['state'] == 'rejected'
    assert 'gap plan_locator must be an existing JSON pointer in experiment_plan' in json.dumps(reply)

@pytest.mark.parametrize('second_alias', ['solver_outputs_001', 'solver_outputs_002'])
def test_analysis_repeated_citation_keeps_one_source_identity(tmp_path, second_alias):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    report = analysis_report(alias='solver_outputs_001')
    report['source_references'] = []
    report['evidence'] = [
        {'source_key': 'raw_evidence', 'source_type': 'runtime_output', 'title': 'Exact fixture result', 'locator': 'solver_outputs_001:row1'},
        {'source_key': 'raw_evidence', 'source_type': 'runtime_output', 'title': 'Exact fixture result', 'locator': second_alias + ':row2'},
    ]
    write_analysis(opened, report)
    reply = worker.call_tool('worker_submit_result', {})
    summary = {'second_alias': second_alias, 'reply': reply}
    if reply['state'] == 'completed':
        status = system[2].call_tool('run_status', {'name': 'analysis'})
        summary['sealed_source_references'] = status['sealed_output']['payload']['source_references']
    print(json.dumps(summary))
    assert reply['state'] == ('completed' if second_alias == 'solver_outputs_001' else 'rejected')
