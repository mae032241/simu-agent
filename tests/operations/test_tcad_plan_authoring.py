"""Author forms, automatic plan identities, and real Worker sealing agree."""
import json
from pathlib import Path
import pytest
from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report, write_analysis


@pytest.mark.parametrize('embedded', [False, True])
def test_plan_identity_is_completed_from_frozen_inputs(tmp_path, embedded):
    system = analysis_system(tmp_path, state='failed', bind_names=())
    catalog, runtime, root, request, artifacts, register = system
    if embedded:
        package = json.loads(runtime.artifacts.read(artifacts['package'].ref))
        package['project']['execution_plan'] = json.loads(runtime.artifacts.read(artifacts['plan'].ref))
        sealed = register('embedded-package', canonical_json(package), 'tcad.execution-package.v2')
        register('embedded-manifest', runtime.artifacts.read(artifacts['manifest'].ref), 'opaque', parents=(sealed.ref,))
        request['inputs'] = [i for i in request['inputs'] if i['port'] != 'experiment_plan']
        for item in request['inputs']:
            if item['port'] == 'execution_package': item['artifact_names'] = ['embedded-package']
            if item['port'] == 'runtime_manifest': item['artifact_names'] = ['embedded-manifest']
    worker, opened = open_analysis(system)
    def assert_form():
        form = json.loads(Path(opened['workspace_path'], 'schema/result.schema.json').read_bytes())
        assert not {'plan_key', 'experiment_key'} & form['properties']['payload']['properties'].keys()
    assert_form()
    runtime.runs._refresh_evidence_schema(root.facade._binding('run','analysis').object_id)
    assert_form()
    report = analysis_report()
    keys = {k: report.pop(k) for k in ('plan_key','experiment_key')}
    write_analysis(opened, report)
    submitted = worker.call_tool('worker_submit_result', {})
    assert submitted['state'] == 'completed', submitted
    result = root.call_tool('run_status', {'name':'analysis', 'intent':'decision', 'output_fields':list(keys)})
    values = {item['pointer'][1:]:item['value'] for item in result['selected_output']['items']}
    assert values == keys


def test_multiple_plan_choices_are_explicit_and_wrong_identity_rejected():
    from tcad_artifact.analysis_bindings import analysis_draft_schema, complete_plan_identity
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
    from scidiscovery.artifact_agent.schema.role_result import RoleResultEnvelope
    schema = RoleResultEnvelope[LayeredDiagnosisReport].model_json_schema()
    # Use the same payload schema layout as the real assignment compiler.
    schema['properties']['payload'] = LayeredDiagnosisReport.model_json_schema()
    choices = [{'plan_key':'p1', 'experiment_key':'a'}, {'plan_key':'p2','experiment_key':'b'}]
    plan = {'validation_plans':choices}
    form = analysis_draft_schema(schema, 'scidiscovery.layered-diagnosis.v1', {'package':'execution_package'},
        {'package':canonical_json({'project':{'execution_plan':plan}})})['properties']['payload']
    assert set(('plan_key','experiment_key')) <= set(form['required'])
    assert [{key:item[key] for key in ('plan_key','experiment_key')}
            for item in form['x-scidiscovery-validation-plans']] == choices
    assert form['x-scidiscovery-validation-plans'][1]['pointer'] == '/project/execution_plan/validation_plans/1'
    with pytest.raises(WorkspaceProtocolError):
        complete_plan_identity({'plan_key':'wrong'}, {'validation_plans':choices[:1]})


@pytest.mark.parametrize('embedded', [False, True])
def test_multiple_plans_require_a_scientific_choice_before_sealing(tmp_path, embedded):
    from copy import deepcopy
    from tests.operations.test_tcad_result_analysis import analysis_materials
    from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
    plan = analysis_materials()[0].model_dump(mode='json')
    proposal = deepcopy(plan['proposals'][0])
    proposal['experiment_key'] = 'alternative_check'
    plan['proposals'].append(proposal)
    validation = deepcopy(plan['validation_plans'][0])
    validation.update(plan_key='alternative_plan',experiment_key='alternative_check')
    plan['validation_plans'].append(validation)
    plan['priority_order'].append('alternative_check')
    system = analysis_system(tmp_path,state='failed',bind_names=(),
        plan=ExperimentPortfolio.model_validate_json(canonical_json(plan),strict=True))
    if embedded:
        _, runtime, _, request, artifacts, register = system
        package = json.loads(runtime.artifacts.read(artifacts['package'].ref))
        package['project']['execution_plan'] = plan
        sealed = register('embedded-package', canonical_json(package), 'tcad.execution-package.v2')
        register('embedded-manifest', runtime.artifacts.read(artifacts['manifest'].ref), 'opaque', parents=(sealed.ref,))
        request['inputs'] = [item for item in request['inputs'] if item['port'] != 'experiment_plan']
        next(item for item in request['inputs'] if item['port'] == 'runtime_manifest')['artifact_names'] = ['embedded-manifest']
    worker, opened = open_analysis(system)
    form = json.loads(Path(opened['workspace_path'],'schema/result.schema.json').read_bytes())['properties']['payload']
    assert {'plan_key','experiment_key'} <= set(form['required'])
    if embedded:
        for choice in form['x-scidiscovery-validation-plans']:
            assert 'source' not in choice
            projection = json.loads(Path(opened['workspace_path'], choice['relative_path']).read_bytes())
            assert projection['project']['execution_plan'] == plan
            assert 'capability' not in projection
    report = analysis_report()
    report['plan_key'] = 'alternative_plan'  # wrong scientific pair is not silently repaired
    write_analysis(opened,report)
    rejected = worker.call_tool('worker_submit_result',{})
    assert rejected['state'] == 'rejected'
    assert 'exact bound plan' in json.dumps(rejected)
    report['experiment_key'] = 'alternative_check'
    write_analysis(opened,report)
    assert worker.call_tool('worker_submit_result',{})['state'] == 'completed'


def test_embedded_and_standalone_plans_cannot_disagree(tmp_path):
    system = analysis_system(tmp_path,state='failed',bind_names=())
    _, runtime, root, request, artifacts, register = system
    package = json.loads(runtime.artifacts.read(artifacts['package'].ref))
    plan = json.loads(runtime.artifacts.read(artifacts['plan'].ref))
    plan['objective'] = 'A different scientific objective.'
    package['project']['execution_plan'] = plan
    sealed = register('conflicting-package',canonical_json(package),'tcad.execution-package.v2')
    register('conflicting-manifest',runtime.artifacts.read(artifacts['manifest'].ref),'opaque',parents=(sealed.ref,))
    for item in request['inputs']:
        if item['port'] == 'execution_package': item['artifact_names'] = ['conflicting-package']
        if item['port'] == 'runtime_manifest': item['artifact_names'] = ['conflicting-manifest']
    result = root.call_tool('operation_preflight',request)
    assert not result['admissible']
    assert result['reason_code'] == 'input_execution_plan_conflict'
