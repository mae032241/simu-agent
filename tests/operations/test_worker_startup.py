"""Worker startup through real assignment, readers, and submission boundaries."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.output_schema_reader import workspace_view
from scidiscovery.artifact_agent.service.run_assignment import result_schema_json
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import operation_primary_output
from tests.operations.test_agent_contract_alignment import CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN
from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN


def test_all_production_worker_forms_hide_control_metadata_keep_scientific_rules():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, FIGURE_PLUGIN))
    for name in catalog.operation_ids():
        compiled = catalog.operation(name)
        if compiled.spec.executor.kind != 'agent':
            continue
        primary = operation_primary_output(compiled)
        static = compiled.output_contracts[primary.name]
        original = canonical_json(dict(static))
        aliases = {f'material_{i}': port.name for i, port in enumerate(compiled.spec.inputs)}
        form = json.loads(result_schema_json(compiled, input_source_ports=aliases))
        Draft202012Validator.check_schema(form)
        payload = form['properties']['payload']
        assert 'x-scidiscovery-input-validation-contract' not in payload
        contract = payload['x-scidiscovery-validation-contract']
        assert set(contract) == {'rules', 'max_output_bytes'}
        assert compiled.digest not in json.dumps(form)
        semantic = payload['x-scidiscovery-semantic-constraints']['rules']
        assert [(r['rule_id'], r['description'], r['output_paths']) for r in semantic] == [
            (r['rule_id'], r['description'], list(r['output_paths']))
            for r in static['x-scidiscovery-semantic-constraints']['rules']]
        for rule in (*semantic, *contract['rules']):
            assert 'required_inputs' not in rule
            assert set(rule.get('sources', ())) <= set(aliases)
        assert all('port' not in source for source in payload.get('x-scidiscovery-readable-evidence', ()))
        assert canonical_json(dict(static)) == original  # Control retains its own full contract.


def test_analysis_start_is_complete_without_reading_other_owner_instructions(tmp_path):
    from tests.operations.test_analysis_claim_scope import generic_worker
    worker, opened = generic_worker(tmp_path)
    root = Path(opened['workspace_path'])
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    assignment = json.loads((root / 'assignment.json').read_bytes())
    domain = json.loads((root / 'domain-workspace.json').read_bytes())
    assert Path(opened['start_here_path']).name == 'worker-start.json'
    from scidiscovery.agent_execution_settings import MaterialInputSettings
    reader_settings = root / 'tools/input-reader-settings.json'
    assert json.loads(reader_settings.read_text())['startup_page_bytes'] == MaterialInputSettings().startup_read_page_bytes
    assert not reader_settings.stat().st_mode & 0o222
    for key in ('instruction', 'role_instructions', 'inputs', 'tools'):
        assert start[key] == assignment[key]
    assert 'tool_contracts' not in start
    assert start['workspace']['patch_contract'] == domain['patch_contract']
    assert start['workspace']['manifest'] == domain['manifest']
    navigation = json.loads((root / start['workspace']['paths']['analysis_navigation']).read_bytes())
    assert not {'instruction', 'role_instructions', 'budget', 'output', 'tool_contracts', 'guidance'} & navigation.keys()
    # --full is a complete authoring form, including only the author's handoff fields.
    form = workspace_view(root, full=True)['schema']
    assert not {'summary', 'verdict', 'next_actions'} & form['$defs']['RoleHandoff']['properties'].keys()
    assert 'schema_version' not in form['properties']
    (root / 'output/result.json').write_bytes(b'{}')
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected'
    assert {d['path'] for d in rejected['diagnostics']} == {'$.payload'}
    assert '$.schema_version' not in json.dumps(rejected)
    from tests.operations.test_analysis_handoff_report import compact_report
    payload = compact_report('experiment_results')
    payload.pop('schema_version', None)
    draft = {'payload': payload}
    Draft202012Validator(form).validate(draft)
    (root / 'output/result.json').write_bytes(canonical_json(draft))
    result = worker.call_tool('worker_submit_result', {})
    assert result['state'] == 'completed', result


def test_audit_form_preserves_authored_handoff_and_unknown_field_repair(tmp_path):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN))
    raw = result_schema_json(catalog.operation('science.figure.evidence.audit.v2'))
    (tmp_path / 'schema').mkdir()
    (tmp_path / 'schema/result.schema.json').write_bytes(raw)
    form = workspace_view(tmp_path, full=True)['schema']
    assert 'summary' in form['$defs']['RoleHandoff']['required']
    assert 'verdict' not in form['$defs']['RoleHandoff']['properties']
    assert 'handoff' in form['required']
    with pytest.raises(ValueError, match='Choose from:.*checks'):
        workspace_view(tmp_path, ['summary'])


def test_form_refresh_retains_controlled_reference_alias_without_internal_port():
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN))
    form = json.loads(result_schema_json(catalog.operation('science.evidence.extract.figure.v3'),
        input_source_ports={'paper': 'paper_source', 'cited_original': 'reference_access',
                            'private_proof': 'hidden_control_port'}))
    payload = form['properties']['payload']
    assert {s['alias'] for s in payload['x-scidiscovery-readable-evidence']} == {'paper', 'cited_original'}
    assert all('port' not in s for s in payload['x-scidiscovery-readable-evidence'])
    foundation = payload['$defs']['ScientificFoundation']
    evidence = foundation['properties']['evidence']['items']['allOf'][-1]
    assert 'cited_original' in evidence['properties']['source_key']['enum']
    assert 'private_proof' not in json.dumps(form)


def test_start_does_not_silently_truncate_plugin_instructions_or_recovery():
    from scidiscovery.artifact_agent.service.worker_start import startup_document
    assignment = dict(instruction='研究任务' * 10000, role_instructions='Complete rules', inputs=[],
        revision={'editable_target': 'output/result.json'}, recovery_draft={'scientific_evidence': False},
        tool_contracts={'unused_tool': {'large': 'do not preload'}})
    start = startup_document(assignment)
    assert start['instruction'] == assignment['instruction']
    assert start['revision'] == assignment['revision']
    assert start['recovery_draft'] == assignment['recovery_draft']
    assert 'tool_contracts' not in start


def test_input_pointer_errors_offer_navigation_without_changing_rfc_semantics():
    from scidiscovery.artifact_agent.service.input_reader import select
    value = {'checks': [], '': 'empty member'}
    assert select(value, '/') == 'empty member'
    assert select(value, '') is value
    with pytest.raises(ValueError, match='--directory'):
        select({'checks': []}, '/summary')
    with pytest.raises(ValueError, match='out of range'):
        select(value, '/checks/0')


@pytest.mark.parametrize('identity,first_visible,first_exposure,expected', [
    ('same', True, 'on_demand', True),
    ('different', True, 'on_demand', False),
    ('same', False, 'on_demand', False),
    ('same', True, 'handoff_only', False),
])
def test_original_reuse_requires_exact_identity_and_visible_alias(
    identity, first_visible, first_exposure, expected,
):
    from dataclasses import replace
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service.run_assignment import assignment_json
    from scidiscovery.artifact_agent.service.run_records import RunInputBinding
    from scidiscovery.artifact_agent.service.worker_start import startup_document
    from scidiscovery.operations.invoke import BoundInput, BoundOperationCall, InvocationArtifact

    compiled = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN)).operation('science.evidence.extract.v1')
    # Exercise projection visibility, not admission of a new plugin contract.
    spec = compiled.spec.model_copy(update={'inputs': tuple(
        port.model_copy(update={'agent_visible': first_visible}) if port.name == 'source_material' else port
        for port in compiled.spec.inputs)})
    compiled = replace(compiled, spec=spec)
    original = ArtifactRef(artifact_id='original', sha256='a' * 64, kind='source', schema_id='opaque')
    other = original if identity == 'same' else original.model_copy(update={'artifact_id': 'other'})
    bindings, inputs = [], []
    for port, alias, ref, exposure, usage in (
        ('source_material', 'evidence', original, first_exposure, 'claim'),
        ('user_context', 'context', other, 'on_demand', 'prior_signal'),
    ):
        # Even matching names and digests must not merge distinct registrations.
        bindings.append(RunInputBinding(port, alias, 'same-name', ref, 'text/plain', exposure, usage, False))
        inputs.append(BoundInput(port, alias, 'same-name', InvocationArtifact(
            artifact_name='same-name', ref=ref, schema_id='opaque', media_type='text/plain', size_bytes=10), exposure, usage))
    start = startup_document(json.loads(assignment_json(BoundOperationCall(
        compiled=compiled, name='reuse', inputs=tuple(inputs), instruction=None), tuple(bindings), tool_names=())))
    context = next(item for item in start['inputs'] if item['source_name'] == 'context')
    assert context.get('same_source_as') == ('evidence' if expected else None)
    assert context['usage'] == 'prior_signal'
    assert ('same_source_as' in start['reading']['inputs']) == expected
    if not first_visible or first_exposure == 'handoff_only':
        assert [item['source_name'] for item in start['inputs']] == ['context']
