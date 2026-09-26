"""Author-visible contracts and one submission across scientific/control ownership."""
import json

import pytest
from pydantic import ValidationError
from jsonschema import Draft202012Validator

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.scientific_foundation import EvidenceItem
from scidiscovery.artifact_agent.service.run_assignment import result_schema_json
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.plugin_runtime.results import materialize_general_result
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from tests.operations.test_general_transform_operations import _intake


def _compiled(name='science.evidence.extract.figure.v3'):
    return compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN)).operation(name)


def test_figure_contract_and_validator_report_independent_scientific_defects():
    from scidiscovery.operation_contract import validation_diagnostics
    item = dict(item_key='p', item_type='parameter', epistemic_status='inference',
        statement='The inferred parameter is 3.', value=3, scope='Only this panel.')
    with pytest.raises(ValidationError) as caught:
        EvidenceItem.model_validate_json(canonical_json(item))
    details = validation_diagnostics(caught.value, schema=EvidenceItem.model_json_schema())
    assert {d['path'] for d in details} == {'$.unit', '$.rationale'}
    schema = json.loads(result_schema_json(_compiled()))
    visible = json.dumps(schema)
    assert all(d['message'] in visible for d in details)
    # Unknown parameters remain parameters, without invented values or units.
    unknown = dict(item, statement='The source does not report this parameter.',
        value=None, rationale='No estimate can be justified from this image.')
    assert EvidenceItem.model_validate_json(canonical_json(unknown)).value is None


def test_intake_author_writes_summary_and_objective_once():
    draft = dict(payload=_intake().model_dump(mode='json'), handoff={'verdict': 'inconclusive'})
    draft['payload']['problem_frame'].pop('objective')
    def versions(value):
        if isinstance(value, dict):
            value.pop('schema_version', None)
            for child in value.values(): versions(child)
        elif isinstance(value, list):
            for child in value: versions(child)
    versions(draft)
    schema = json.loads(result_schema_json(_compiled()))
    Draft202012Validator(schema).validate(draft)
    # Reproducible fixture measurements, not estimates of a live model's tokens
    # or of every conditional scientific judgment in an arbitrary Intake.
    import os
    from pathlib import Path
    def leaves(value):
        if isinstance(value, dict): return sum(leaves(child) for child in value.values())
        if isinstance(value, list): return sum(leaves(child) for child in value)
        return 1
    def required_leaves(node, root, path=''):
        if '$id' in node: root = node
        if '$ref' in node:
            target = root
            for part in node['$ref'].removeprefix('#/').split('/'): target = target[part]
            return required_leaves(target, root, path)
        if node.get('type') == 'object':
            return [leaf for key in node.get('required', ()) for leaf in
                required_leaves(node['properties'][key], root, path + '/' + key)]
        if node.get('type') == 'array' and node.get('minItems', 0):
            return required_leaves(node['items'], root, path + '/*')
        return [path]
    baseline = dict(schema_version=1, payload=_intake().model_dump(mode='json'),
        handoff={'verdict': 'inconclusive', 'summary': _intake().scientific_foundation.summary})
    measurements = dict(fixture='test_intake_author_writes_summary_and_objective_once',
        baseline_scalar_values=leaves(baseline), draft_scalar_values=leaves(draft),
        baseline_bytes=len(canonical_json(baseline)), draft_bytes=len(canonical_json(draft)),
        duplicate_scientific_value_bytes_removed=len(canonical_json(baseline['handoff']['summary'])) +
            len(canonical_json(baseline['payload']['problem_frame']['objective'])),
        unconditional_required_author_leaf_paths=required_leaves(schema, schema),
        caveat='Required paths describe one minimum schema branch; source/rationale/unit conditional rules remain in the same visible contract. Fixture counts are not live Worker usage.')
    directory = Path(os.environ['SCID_TEST_LOG_DIR'])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'field-measurements.json').write_text(json.dumps(measurements, indent=2))
    handoff = schema['$defs']['RoleHandoff']['properties']
    assert not {'summary', 'missing_inputs', 'assumptions', 'evidence_bundle_fingerprint_sha256'} & handoff.keys()
    assert 'objective' not in schema['properties']['payload']['$defs']['ProblemFrame']['properties']
    materialize_general_result(draft, 'scidiscovery.scientific-intake.v1')
    assert draft['handoff']['summary'] == draft['payload']['scientific_foundation']['summary']
    assert draft['handoff']['verdict'] == 'inconclusive'
    from scidiscovery.artifact_agent.schema.role_result import parse_role_result
    from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
    parse_role_result(draft)
    ScientificIntake.model_validate_json(canonical_json(draft['payload']))


def test_no_plan_analysis_has_no_placeholder_requirement():
    from scidiscovery.artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
    result = LayeredDiagnosisReport.model_validate_json(canonical_json(dict(summary='Only digitized evidence was assessed.',
        overall_verdict='inconclusive', claim_allowed=False, limitations=['No experiment plan.'])))
    assert result.plan_key is result.experiment_key is None


def test_actual_figure_assignment_tool_contract_excludes_source_control_fields():
    from scidiscovery.artifact_agent.service.run_assignment import assignment_json
    from scidiscovery.operations.invoke import BoundOperationCall
    from scidiscovery.operations.tooling import operation_worker_tools
    compiled = _compiled()
    names = tuple(tool.name for tool in operation_worker_tools(compiled))
    assignment = json.loads(assignment_json(BoundOperationCall(compiled=compiled, name='field-contract',
        inputs=(), instruction=None), (), tool_names=names))
    for tool_name in ('worker_curve_figure_preview', 'worker_curve_figure_save'):
        source = assignment['tool_contracts'][tool_name]['inputSchema']['$defs']['ScientificFigureSource']
        assert set(source['properties']) == {'page', 'document_image_index'}
    assert 'mechanical metadata fields may be omitted' not in assignment['role_instructions']


def _submit(tmp_path, compiled, document, sources):
    import hashlib
    from scidiscovery.artifact_agent.service.local_workspace import SealedFile, SealedWorkspace
    from scidiscovery.artifact_agent.service.run_outputs import validate_run_output
    raw = canonical_json(document)
    (tmp_path / 'result.json').write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    sealed = SealedWorkspace(backend='test', backend_version='1', run_id='field-contract',
        digest=digest, root=tmp_path, files=(SealedFile(relative_path='result.json',
        media_type='application/json', size_bytes=len(raw), sha256=digest),))
    return validate_run_output(compiled, sealed, input_source_ports={name: 'source_material' for name in sources}, input_bytes=sources)


def test_submission_reports_all_independent_item_errors_and_rejects_forged_sources(tmp_path):
    from scidiscovery.artifact_agent.service.run_outputs import RunOutputError
    compiled = _compiled('science.evidence.extract.v1')
    draft = dict(payload=_intake().model_dump(mode='json'), handoff={'verdict': 'inconclusive'})
    item = draft['payload']['scientific_foundation']['items'][0]
    item.update(item_type='parameter', epistemic_status='inference', value=3)
    materialize_general_result(draft, 'scidiscovery.scientific-intake.v1')
    with pytest.raises(RunOutputError) as caught:
        _submit(tmp_path, compiled, draft, {'paper': b'Exact source.'})
    paths = {d['path'] for d in caught.value.details}
    assert {'$.payload.scientific_foundation.items[0].unit', '$.payload.scientific_foundation.items[0].rationale'} <= paths
    assert any(d['type'] == 'dependent_checks_deferred' for d in caught.value.details)
    item.update(unit='dimensionless', rationale='Explicit inference from the reported relation.')
    accepted = _submit(tmp_path, compiled, draft, {'paper': b'Exact source.'})
    assert accepted.signal.summary == draft['payload']['scientific_foundation']['summary']
    item['evidence_keys'] = ['forged']
    with pytest.raises(RunOutputError) as caught:
        _submit(tmp_path, compiled, draft, {'paper': b'Exact source.'})
    assert any(d['path'].endswith('.evidence_keys[0]') for d in caught.value.details)


def test_draft_no_plan_analysis_and_nested_parameter_fields_are_absent():
    from tests.operations.test_agent_contract_alignment import TCAD_PLUGIN
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    analysis = json.loads(result_schema_json(catalog.operation('science.result.diagnose.v1'), input_source_ports={'results': 'experiment_results'}))
    assert not {'plan_key', 'experiment_key'} & analysis['properties']['payload']['properties'].keys()
    with_plan = json.loads(result_schema_json(catalog.operation('science.result.diagnose.v1'), input_source_ports={'plan': 'experiment_plan'}))
    assert {'plan_key', 'experiment_key'} <= with_plan['properties']['payload']['properties'].keys()
    package = json.loads(result_schema_json(catalog.operation('tcad.parameter.evidence.extract.v1')))
    assert 'coverage' not in package['properties']['payload']['properties']
    assert 'objective' not in package['properties']['payload']['$defs']['ProblemFrame']['properties']
    assert 'statement' not in package['properties']['payload']['$defs']['ResearchObjectiveContract']['properties']


def test_large_intake_summary_and_gaps_are_projected_without_truncation():
    from scidiscovery.artifact_agent.schema.role_result import parse_role_result
    draft = dict(payload=_intake().model_dump(mode='json'), handoff={'verdict': 'inconclusive'})
    foundation = draft['payload']['scientific_foundation']
    foundation['summary'] = 'S' * 8192
    foundation['missing_inputs'] = [f'Gap {index}' for index in range(128)]
    materialize_general_result(draft, 'scidiscovery.scientific-intake.v1')
    result = parse_role_result(draft)
    assert result.handoff.summary == foundation['summary']
    assert list(result.handoff.missing_inputs) == foundation['missing_inputs']


def test_missing_authored_summary_diagnostic_points_to_science_not_generated_handoff():
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    draft = dict(payload=_intake().model_dump(mode='json'), handoff={'verdict': 'inconclusive'})
    draft['payload']['scientific_foundation'].pop('summary')
    with pytest.raises(WorkspaceProtocolError) as caught:
        materialize_general_result(draft, 'scidiscovery.scientific-intake.v1')
    assert caught.value.details[0]['path'] == '$.payload.scientific_foundation.summary'


def test_hypothesis_identity_is_generated_from_exact_frozen_foundation(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.plugin_runtime.results import finalize_general_result
    from scidiscovery.operations.workspace import WorkspaceFinalizationRequest
    from tests.operations.test_hypothesis_objective_boundary import _foundation, _proposal
    payload = _proposal()
    payload.pop('research_objective_key')
    payload.pop('schema_version')
    draft = dict(payload=payload, handoff={'verdict': 'inconclusive', 'summary': 'No supported mechanism yet.'})
    schema = json.loads(result_schema_json(_compiled('science.hypothesis.propose.v1')))
    assert 'research_objective_key' not in schema['properties']['payload']['properties']
    Draft202012Validator(schema).validate(draft)
    (tmp_path / 'output').mkdir()
    (tmp_path / 'output/result.json').write_bytes(canonical_json(draft))
    raw = _foundation('exact_objective')
    request = WorkspaceFinalizationRequest('fixture', tmp_path, {}, 65536,
        output_schema_id='scidiscovery.hypothesis-proposal.v2', input_contents={'original': raw},
        binding_descriptors={'original': SimpleNamespace(port_name='scientific_foundation')})
    result = json.loads(finalize_general_result(request))
    assert result['payload']['research_objective_key'] == 'exact_objective'
    assert result['payload']['stage_objective'] == payload['stage_objective']
    assert request.input_contents['original'] == raw


def test_parameter_doi_and_objective_draft_copies_finalize_and_check(tmp_path):
    from types import SimpleNamespace
    from scidiscovery.operations.workspace import WorkspaceFinalizationRequest
    from tcad_artifact.parameter_operations import _finalize_parameter_result, check_parameters, ParameterCheckInput
    from tests.operations.test_agent_contract_alignment import TCAD_PLUGIN
    from tests.operations.test_m2_parameter_package import _package
    payload = _package().model_dump(mode='json')
    payload['scientific_intake']['problem_frame'].pop('objective')
    payload['source_catalog']['sources'][0]['doi'] = '10.1234/EXACT'
    payload['source_catalog']['sources'][0].pop('work_key')
    payload.pop('coverage', None)
    draft = dict(payload=payload, handoff={'verdict': 'inconclusive'})
    def versions(value):
        if isinstance(value, dict):
            value.pop('schema_version', None)
            for child in value.values(): versions(child)
        elif isinstance(value, list):
            for child in value: versions(child)
    versions(draft)
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    schema = json.loads(result_schema_json(catalog.operation('tcad.parameter.evidence.extract.v1')))
    Draft202012Validator(schema).validate(draft)
    (tmp_path / 'output').mkdir()
    (tmp_path / 'output/result.json').write_bytes(canonical_json(draft))
    checked = check_parameters(ParameterCheckInput(package_path='output/result.json'), SimpleNamespace(workspace=tmp_path))
    result = json.loads(_finalize_parameter_result(WorkspaceFinalizationRequest('fixture', tmp_path, {}, 1024*1024,
        output_schema_id='scidiscovery.parameter-evidence-package.v1')))
    assert result['payload']['source_catalog']['sources'][0]['work_key'] == 'doi:10.1234/exact'
    assert result['payload']['coverage'] == checked['coverage']
    assert result['handoff']['summary'] == payload['scientific_intake']['scientific_foundation']['summary']


@pytest.mark.parametrize('schema_id,operation,payload', [
    ('scidiscovery.experiment-report.v1', 'science.experiment.v1', dict(summary='Unavailable observation.', outcome='inconclusive', remaining_question='Which source is needed?')),
    ('scidiscovery.experiment-review.v1', 'science.object.review.v1', dict(summary='Missing support.', verdict='inconclusive')),
])
def test_complete_task_draft_finalizer_and_scientific_repair_location(tmp_path, schema_id, operation, payload):
    from scidiscovery.general_science_experiment_task import finalize
    from scidiscovery.operations.workspace import WorkspaceFinalizationRequest, WorkspaceProtocolError
    draft = {'payload': payload}
    schema = json.loads(result_schema_json(_compiled(operation)))
    assert 'summary' not in schema['$defs']['RoleHandoff']['properties']
    assert 'verdict' not in schema['$defs']['RoleHandoff']['properties']
    Draft202012Validator(schema).validate(draft)
    (tmp_path / 'output').mkdir()
    path = tmp_path / 'output/result.json'
    path.write_bytes(canonical_json(draft))
    request = WorkspaceFinalizationRequest('fixture', tmp_path, {}, 65536, output_schema_id=schema_id)
    result = json.loads(finalize(request))
    assert result['handoff']['summary'] == payload['summary']
    assert result['handoff']['verdict'] == 'inconclusive'
    payload.pop('summary')
    path.write_bytes(canonical_json(draft))
    with pytest.raises(WorkspaceProtocolError) as error:
        finalize(request)
    assert error.value.details[0]['path'] == '$.payload.summary'


@pytest.mark.parametrize('custom_finalizer', [False, True])
def test_shared_schema_requires_actual_workspace_projection_capability(tmp_path, custom_finalizer):
    from dataclasses import replace
    from scidiscovery.operations.workspace import operation_workspace_hooks
    compiled = _compiled('science.object.review.v1')
    workspace_key = compiled.permission_template.workspace
    specs = dict(compiled.component_specs)
    implementations = dict(compiled.implementations)
    workspace = specs[workspace_key]
    references = []
    for ref in workspace.resources:
        key = f'{ref.plugin_id or compiled.plugin_id}:{ref.component_id}'
        if specs[key].kind == 'workspace_finalizer':
            if not custom_finalizer:
                continue
            implementations[key] = lambda request: (request.workspace / 'output/result.json').read_bytes()
        references.append(ref)
    specs[workspace_key] = workspace.model_copy(update={'resources': tuple(references)})
    compiled = replace(compiled, component_specs=specs, implementations=implementations)
    schema = json.loads(result_schema_json(compiled))
    assert {'summary', 'verdict'} <= schema['$defs']['RoleHandoff']['properties'].keys()
    assert 'handoff' in schema['required']
    document = dict(schema_version=1, payload=dict(summary='Review complete.', verdict='inconclusive'),
                    handoff=dict(summary='Review complete.', verdict='inconclusive'))
    Draft202012Validator(schema).validate(document)
    (tmp_path / 'output').mkdir()
    (tmp_path / 'output/result.json').write_bytes(canonical_json(document))
    hook = operation_workspace_hooks(compiled).get('workspace_finalizer')
    from scidiscovery.operations.workspace import WorkspaceFinalizationRequest
    if hook:
        assert json.loads(hook(WorkspaceFinalizationRequest(compiled.spec.operation_id, tmp_path, {}, 65536))) == document
    assert _submit(tmp_path, compiled, document, {}).signal.summary == 'Review complete.'


def test_finalizer_and_output_validation_report_real_bounded_diagnostic_counts(tmp_path):
    from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
    from scidiscovery.operations.workspace import WorkspaceProtocolError
    from scidiscovery.plugin_runtime.results import validate_finalizer_payload
    from scidiscovery.operation_contract import sanitize_diagnostic_details
    from scidiscovery.artifact_agent.service.run_outputs import RunOutputError
    payload = _intake().model_dump(mode='json')
    payload['scientific_foundation']['items'] = [dict(item_key=f'p{i}', item_type='parameter',
        epistemic_status='inference', statement='PRIVATE_SCIENTIFIC_TEXT', value=i,
        scope='This panel.') for i in range(20)]
    with pytest.raises(WorkspaceProtocolError) as finalizer:
        validate_finalizer_payload(ScientificIntake, payload)
    full = dict(payload=payload, handoff={'verdict': 'inconclusive'})
    materialize_general_result(full, 'scidiscovery.scientific-intake.v1')
    with pytest.raises(RunOutputError) as normal:
        _submit(tmp_path, _compiled('science.evidence.extract.v1'), full, {'paper': b'original'})
    for diagnostics in (finalizer.value.details, normal.value.details):
        visible = sanitize_diagnostic_details(diagnostics, schema=ScientificIntake.model_json_schema(),
            rules=tuple(d["rule_id"] for d in diagnostics if "rule_id" in d))
        assert len(visible) == 16
        summary = visible[-1]
        assert summary['type'] == 'dependent_checks_deferred'
        assert '15 of 40' in summary['message'] and 'omitted 25' in summary['message']
        assert 'not evaluated' in summary['message']
        assert 'PRIVATE_SCIENTIFIC_TEXT' not in json.dumps(visible)
        assert all(d['path'].startswith('$.payload') for d in visible[:-1])



def test_compiled_digest_tracks_actual_finalizer_projection(monkeypatch):
    from dataclasses import replace
    import scidiscovery.general_science_components as components
    original = components.RESULT_FINALIZER
    baseline = _compiled('science.evidence.extract.v1')
    hook = original.implementation
    monkeypatch.setattr(components, 'RESULT_FINALIZER', replace(original,
        implementation=replace(hook, projection_version=hook.projection_version + '.changed')))
    changed = _compiled('science.evidence.extract.v1')
    assert changed.digest != baseline.digest
    monkeypatch.setattr(components, 'RESULT_FINALIZER', replace(original, implementation=hook.implementation))
    plain = _compiled('science.evidence.extract.v1')
    assert plain.digest not in {baseline.digest, changed.digest}
    assert 'summary' in json.loads(result_schema_json(plain))['$defs']['RoleHandoff']['properties']
    monkeypatch.setattr(components, 'RESULT_FINALIZER', original)
    assert _compiled('science.evidence.extract.v1').digest == baseline.digest


def test_public_diagnostic_sanitizer_discloses_omissions_without_input_echo():
    from scidiscovery.operation_contract import sanitize_diagnostic_details
    raw = [dict(path='$.summary', message='PRIVATE_VALUE', type='missing') for _ in range(40)]
    visible = sanitize_diagnostic_details(raw, schema={'properties': {'summary': {}}})
    assert len(visible) == 16
    assert visible[-1]['type'] == 'diagnostics_omitted'
    assert '15 of 40' in visible[-1]['message'] and 'omitted 25' in visible[-1]['message']
    assert 'PRIVATE_VALUE' not in json.dumps(visible)



def test_parameter_submission_preserves_finalizer_counts_and_repairs_once(tmp_path):
    from pathlib import Path
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from tests.operations.test_general_transform_operations import _root
    from tests.operations.test_m2_parameter_package import _package
    from tests.operations.test_agent_contract_alignment import TCAD_PLUGIN
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))
    runtime, _, root = _root(tmp_path, catalog=catalog)
    root.call_tool('artifact_ingest_text', dict(name='source', text='scale=1'))
    root.call_tool('operation_invoke', dict(name='extract', operation_id='tcad.parameter.evidence.extract.v1',
        instruction='Extract the bound parameters.', inputs=[dict(port='source_material', artifact_names=['source'])]))
    compiled = catalog.operation('tcad.parameter.evidence.extract.v1')
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    payload = _package('source_material').model_dump(mode='json')
    items = payload['scientific_intake']['scientific_foundation']['items']
    items.extend(dict(item_key=f'p{i}', item_type='parameter', epistemic_status='inference',
        statement='PRIVATE_SCIENTIFIC_TEXT', value=i, scope='This panel.') for i in range(20))
    draft = dict(payload=payload, handoff=dict(verdict='inconclusive'))
    output = Path(opened['output_directory'], 'result.json')
    output.write_bytes(canonical_json(draft))
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected'
    details = rejected['diagnostics']
    assert len(details) == 16 and '15 of 40' in details[-1]['message']
    assert 'omitted 25' in details[-1]['message'] and 'not evaluated' in details[-1]['message']
    assert all(d['path'].startswith('$.payload.scientific_intake.scientific_foundation.items') for d in details[:-1])
    assert 'PRIVATE_SCIENTIFIC_TEXT' not in json.dumps(rejected)
    for item in items[1:]:
        item.update(unit='dimensionless', rationale='A bounded fixture inference from the relation.')
    output.write_bytes(canonical_json(draft))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
