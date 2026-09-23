"""Small production-path continuations; no solver or scientific Agent is launched."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from tests.operations.test_tcad_result_analysis import (
    analysis_system, open_analysis, analysis_report, raw_request, write_analysis,
)


def test_legacy_draft_without_coverage_or_runtime_files_does_not_advertise_them(tmp_path):
    from curve_score.analysis_workspace import materialize
    from scidiscovery.operations.workspace import WorkspaceMaterializationRequest
    draft = tmp_path/'recovery-draft'; (draft/'scratch').mkdir(parents=True)
    (draft/'scratch/numbers.json').write_text('{"value":3}')
    (tmp_path/'assignment.json').write_text('{"inputs":[],"tools":[]}')
    result = materialize(WorkspaceMaterializationRequest(operation_id='fixture', workspace=tmp_path,
        input_paths={}, provisional_roots=(draft,), edit_protocol='native'))
    start = json.loads((tmp_path/'analysis-start.json').read_bytes())
    assert result.paths['recovery_manifest'] is start['recovery']['coverage_path'] is None
    assert start['recovery']['historical_runtime_path'] is None
    assert (tmp_path/'scratch/numbers.json').read_text() == '{"value":3}'


def test_compact_open_and_editable_nested_recovery_with_fresh_runtime(tmp_path):
    from scidiscovery.artifact_agent.service import local_process_observation as observation
    from tests.operations.test_analysis_evidence_recovery import recovery_system
    system, worker, opened, _ = recovery_system(tmp_path)
    root = Path(opened['workspace_path'])
    start = json.loads(Path(opened['start_here_path']).read_bytes())
    domain = json.loads((root / 'domain-workspace.json').read_bytes())
    assert domain['paths']['recovery_manifest'] is start['recovery']['coverage_path'] is None
    assert 'tool_contracts' not in opened
    assert start['excerpts'] and all('pointer' in item for item in start['excerpts'])
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    contracts = assignment['tool_contracts']
    assert set(start['tool_contracts']) == set(contracts)
    assert len(canonical_json(opened)) < len(canonical_json(contracts))
    assert Path(opened['start_here_path']).stat().st_size <= 24 * 1024
    scratch = root / 'scratch'; (scratch / 'nested').mkdir()
    (scratch / 'nested/numbers.json').write_text('{"value":3}')
    script = 'from pathlib import Path\nassert Path("nested/numbers.json").read_text() == \'{"value":3}\'\nPath("plot.txt").write_text("plot only")\n'
    (scratch / 'plot.py').write_text(script)
    active = root / observation.RECORD_DIR; active.mkdir()
    (active / 'latest.json').write_text('{"state":"running","exit_code":77}')
    (active / 'error.log').write_text('ModuleNotFoundError: fixture_plotter\n')
    runtime, facade = system[1:3]
    value = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(value.run_id, reason='fixture plot dependency', expected_state='running',
        expected_last_activity_at=value.last_activity_at)
    request = deepcopy(system[3]); request.update(name='copied', draft_from='analysis')
    following, new_opened = open_analysis((*system[:3], request, *system[4:]))
    new = Path(new_opened['workspace_path']); draft = new / 'recovery-draft'
    domain = json.loads((new / 'domain-workspace.json').read_bytes())
    entry = json.loads(Path(new_opened['start_here_path']).read_bytes())
    from curve_score.analysis_workspace import GUIDANCE, REPORT_GUIDANCE
    assert entry['guidance'] == start['guidance'] == GUIDANCE
    assert domain['patch_contract']['instruction'] == REPORT_GUIDANCE
    assert domain['paths']['recovery_manifest'] == entry['recovery']['coverage_path']
    assert (new / domain['paths']['recovery_manifest']).is_file()
    frozen = draft / 'scratch/nested/numbers.json'
    assert stat.S_IMODE(frozen.stat().st_mode) == 0o400
    assert stat.S_IMODE((frozen.parent).stat().st_mode) == 0o500
    assert stat.S_IMODE((new / 'scratch/nested').stat().st_mode) == 0o700
    assert stat.S_IMODE((new / 'scratch/plot.py').stat().st_mode) == 0o600
    assert not (new / observation.RECORD_DIR).exists()
    assert observation.read_summary(new)['coverage'] == 'unobserved'
    assert 'ModuleNotFoundError' in (draft / observation.RECORD_DIR / 'error.log').read_text()
    (new / 'scratch/plot.py').write_text(script + '# editable without chmod\n')
    (new / 'scratch/nested/new').mkdir()
    proc = subprocess.run([sys.executable, 'tools/local_process_observation.py', '--timeout', '5',
        '--submission-reserve', '0', 'plot.py'], cwd=new, capture_output=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert (new / 'scratch/plot.txt').read_text() == 'plot only'
    assert frozen.read_text() == '{"value":3}'
    assert (draft / 'scratch/plot.py').read_text() == script
    # Contract navigation does not depend on optional analysis navigation.
    domain = json.loads((new / 'domain-workspace.json').read_text())
    domain['paths'].pop('start_here')
    (new / 'domain-workspace.json').chmod(0o600)
    (new / 'domain-workspace.json').write_text(json.dumps(domain))
    reopened = following.call_tool('worker_open_assignment', {})
    assert 'tool_contracts' not in reopened and 'start_here_path' not in reopened
    assert json.loads(Path(reopened['tool_contracts_path']).read_bytes())['tool_contracts'] == contracts


def test_prior_mapping_reused_across_alias_reorder_tool_receipt_and_next_seal(tmp_path):
    system = analysis_system(tmp_path, mapped=False)
    worker, opened = open_analysis(system)
    report = analysis_report(alias='solver_outputs_001', output_name='A', mapped=True)
    report['source_references'][0]['case_mapping_basis'] = dict(kind='evidence', evidence_refs=[
        dict(input_alias='experiment_plan', locator='experiment_plan:/proposals/0/cases/0')],
        rationale='Conditional fixture association to the exact original plan.')
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    request = deepcopy(system[3]); request['name'] = 'with_history'
    next(item for item in request['inputs'] if item['port'] == 'solver_outputs')['artifact_names'].reverse()
    request['inputs'].extend([
        dict(port='prior_analysis', artifact_names=['analysis.output']),
        dict(port='prior_analysis_manifest', artifact_names=['analysis.output.recovery_manifest'])])
    worker, opened = open_analysis((*system[:3], request, *system[4:]))
    view = json.loads((Path(opened['workspace_path']) / 'analysis-bindings.json').read_text())
    known = view['sources']['solver_outputs_002']
    assert known['origin']['kind'] == 'prior_conditional_claim'
    assert known['case_key'] == 'baseline'
    call = raw_request(alias='solver_outputs_002')
    call['sources'][0].pop('experiment_key'); call['sources'][0].pop('output_name')
    before = deepcopy(call)
    record = worker.call_tool('worker_tcad_curve_score', dict(record_key='reused', request=call))
    assert record['status'] == 'computed', record
    record = json.loads(Path(record['calculation_path']).read_bytes())
    assert record['request'] == before == call
    attempts = system[1].runs.tool_attempts(worker._run_id)
    assert attempts[-1]['request_digest'] == hashlib.sha256(canonical_json(call)).hexdigest()
    report = analysis_report(alias='solver_outputs_002', output_name='A', mapped=False)
    report['source_references'] = []
    report['calculation_records'] = [record]
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    sealed = system[2].call_tool('run_status', {'name':'with_history', 'view':'detail'})['sealed_output']['payload']
    assert 'case_mapping_basis' not in known  # Display points to the preserved prior basis.
    origin = known['origin']
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    original_input = next(item for item in assignment['inputs'] if item['source_name'] == origin['input_alias'])
    original = json.loads((Path(opened['workspace_path']) / original_input['relative_path']).read_bytes())
    reference = original['source_references'][int(origin['pointer'].rsplit('/', 1)[1])]
    assert sealed['source_references'][0]['case_mapping_basis'] == reference['case_mapping_basis']
    request['name'] = 'history_again'
    next(i for i in request['inputs'] if i['port']=='prior_analysis')['artifact_names'] = ['with_history.output']
    next(i for i in request['inputs'] if i['port']=='prior_analysis_manifest')['artifact_names'] = ['with_history.output.recovery_manifest']
    worker, opened = open_analysis((*system[:3], request, *system[4:]))
    report['calculation_records'] = []; report['source_references'] = []
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    sealed = system[2].call_tool('run_status', {'name':'history_again', 'view':'detail'})['sealed_output']['payload']
    assert sealed['source_references'][0]['case_key'] == 'baseline'


def test_native_read_error_survives_success_and_is_visible_in_completed_root_status(tmp_path):
    system = analysis_system(tmp_path); worker, opened = open_analysis(system)
    root = Path(opened['workspace_path'])
    command = [sys.executable, 'tools/local_process_observation.py', '--timeout', '5',
        '--submission-reserve', '0', '--display', 'raw', '--command', sys.executable, '-c']
    failed = subprocess.run(command + ['from pathlib import Path; Path("missing-recovery.json").read_text()'],
        cwd=root, capture_output=True, timeout=10)
    assert failed.returncode == 1 and b'FileNotFoundError' in failed.stderr
    assert subprocess.run(command + ['print("prepared")'], cwd=root, capture_output=True, timeout=10).stdout == b'prepared\n'
    report = analysis_report(alias='solver_outputs_001', output_name='A', mapped=True)
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    status = system[2].call_tool('run_status', {'name':'analysis', 'view':'detail'})
    native, diagnostic = status['native_execution'], status['diagnostic_summary']
    assert native['exit_code'] == 0 and native['attempt_count'] == 2 and native['error_count'] == 1
    error = diagnostic['latest_native_error']
    assert error['exit_code'] == 1 and error['error_type'] == 'FileNotFoundError'
    assert 'missing-recovery.json' in (root / error['stderr_log']).read_text()
    assert diagnostic['rejection_count'] == 0 and diagnostic['failure'] is None
    assert 'missing-recovery.json' not in json.dumps(diagnostic)


@pytest.mark.parametrize('keep_original', [False, True])
def test_recovery_with_changed_inputs_keeps_draft_and_only_adopts_applicable_receipts(tmp_path, keep_original):
    system = analysis_system(tmp_path); worker, opened = open_analysis(system)
    catalog, runtime, facade, request, artifacts, register = system
    root = Path(opened['workspace_path'])
    (root / 'scratch/analysis.py').write_text('# saved work\n')
    (root / 'scratch/numbers.json').write_text('{"value":3}')
    worker.call_tool('worker_analysis_publish_files', dict(source_aliases=['reference_material'],
        script_path='scratch/analysis.py', files=[dict(path='scratch/numbers.json',media_type='application/json')],
        method='Fixture saved calculation.'))
    receipts = runtime.runs.tool_evidence(worker._run_id)
    current = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(current.run_id, reason='fixture interruption', expected_state='running',
        expected_last_activity_at=current.last_activity_at)
    # Same bytes do not substitute for the old Artifact identity.
    register('new_reference', runtime.artifacts.read(artifacts['reference'].ref), 'opaque', media='text/csv')
    request = deepcopy(request); request.update(name='changed_inputs', draft_from='analysis', max_attempts=3)
    next(i for i in request['inputs'] if i['port']=='reference_material')['artifact_names'] = (
        ['new_reference','reference'] if keep_original else ['new_reference'])
    worker, opened = open_analysis((*system[:3], request, *system[4:]))
    adopted = runtime.runs.tool_evidence(worker._run_id)
    assert adopted == (receipts if keep_original else [])
    coverage = opened['recovery_evidence']
    assert coverage['preserved_count'] == len(receipts)
    assert coverage['adopted_count'] == (len(receipts) if keep_original else 0)
    assert facade.call_tool('run_status', {'name':'changed_inputs'})['recovery']['tool_evidence'] == coverage
    new = Path(opened['workspace_path'])
    assert (new/'scratch/numbers.json').read_text() == (root/'scratch/numbers.json').read_text()
    (new/'scratch/analysis.py').write_text('# edited safely\n')
    assert (new/'recovery-draft/scratch/analysis.py').read_text() == '# saved work\n'
    if keep_original:
        # Receipt aliases still belong to the original producer after a second recovery.
        current = runtime.runs.status(worker._run_id)
        runtime.runs.record_failure(current.run_id, reason='fixture interruption', expected_state='running',
            expected_last_activity_at=current.last_activity_at)
        request.update(name='recovered_again', draft_from='changed_inputs')
        worker, opened = open_analysis((*system[:3], request, *system[4:]))
        assert runtime.runs.tool_evidence(worker._run_id) == receipts
    report = analysis_report()
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_out_of_scope_receipt_corruption_still_fails_open_with_record_index(tmp_path, monkeypatch):
    system = analysis_system(tmp_path); worker, opened = open_analysis(system)
    root = Path(opened['workspace_path']); runtime = system[1]
    (root/'scratch/work.py').write_text('# saved\n')
    (root/'scratch/data.json').write_text('{"value":3}')
    worker.call_tool('worker_analysis_publish_files', dict(source_aliases=['reference_material'],
        script_path='scratch/work.py', files=[dict(path='scratch/data.json',media_type='application/json')],
        method='Fixture partial result.'))
    origin = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(origin.run_id, reason='fixture interruption', expected_state='running',
        expected_last_activity_at=origin.last_activity_at)
    read = runtime.runs.tool_evidence
    def corrupted(run_id):
        records = read(run_id)
        if run_id == origin.run_id:
            records[0]['source_ref'] = system[4]['plan'].ref.model_dump(mode='json')
        return records
    monkeypatch.setattr(runtime.runs, 'tool_evidence', corrupted)
    request = deepcopy(system[3]); request.update(name='bad_receipt', draft_from='analysis')
    request['inputs'] = [i for i in request['inputs'] if i['port'] != 'reference_material']
    with pytest.raises(Exception, match='preserved tool evidence integrity failure'):
        open_analysis((*system[:3], request, *system[4:]))
    status = system[2].call_tool('run_status', {'name':'bad_receipt'})
    assert status['state'] == 'failed' and 'records[0] receipt differs from its origin' in status['reason']


@pytest.mark.parametrize('field, value, expected', [
    ('source_key', [], '$.payload.source_references[0].source_key'),
    ('input_alias', 'untrusted\nalias', '$.payload.source_references[0].input_alias'),
    ('output_name', 'wrong', '$.payload.source_references[0].output_name'),
    ('case_key', 'wrong', '$.payload.source_references[0].case_key'),
])
def test_output_repair_has_exact_path_and_never_echoes_arbitrary_alias(tmp_path, field, value, expected):
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    system = analysis_system(tmp_path); worker, opened = open_analysis(system)
    report = analysis_report(alias='solver_outputs_001', output_name='A', mapped=True)
    report['source_references'][0][field] = value
    write_analysis(opened, report)
    reply = MCPRouter(worker, name='probe').handle(dict(jsonrpc='2.0', id=1, method='tools/call',
        params=dict(name='worker_submit_result', arguments={})))
    result = reply['result']['structuredContent']
    assert result['state'] == 'rejected', reply
    assert result['diagnostics'][0]['path'] == expected, reply
    assert 'untrusted' not in json.dumps(reply)
    report = analysis_report(alias='solver_outputs_001', output_name='A', mapped=True)
    # Additional mapping metadata need not have a second evidence table entry.
    report['source_references'].append({**report['source_references'][0], 'source_key':'metadata_only'})
    write_analysis(opened, report)
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def _mapping_fixture():
    from tests.operations.test_prior_analysis_sources import bindings, replace_manifest
    from scidiscovery.operations.input_validation import ValidationSources
    basis = dict(kind='evidence', evidence_refs=[dict(input_alias='old_plan', locator='old_plan:/proposals/0')], rationale='Conditional fixture mapping.')
    previous = canonical_json({'source_references':[dict(source_key='r', input_alias='old_curve', output_name='A',
        experiment_key='e', case_key='one', case_mapping_basis=basis)]})
    contents, descriptors = bindings(previous=previous)
    proof = json.loads(contents['proof'])
    for alias, port, value in [
            ('plan', 'experiment_plan', {'proposals':[{'experiment_key':'e','cases':[{'case_key':'one'},{'case_key':'two'}]}]}),
            ('package', 'reviewed_package', {'project':{'expected_outputs':[{'name':'A','case_key':None}]}})]:
        raw = canonical_json(value)
        identity = descriptors['new_curve'].artifact_ref.model_copy(update={'artifact_id':'artifact_'+alias, 'sha256':hashlib.sha256(raw).hexdigest()})
        contents[alias] = raw
        descriptors[alias] = replace(descriptors['new_curve'], source_name=alias, port_name=port,
            artifact_ref=identity, sha256=identity.sha256, size_bytes=len(raw))
        proof['bindings']['old_'+alias] = {'artifact_ref':identity.model_dump(mode='json'), 'port_name':port}
    descriptors['proof'] = replace(descriptors['proof'], parent_refs=(*descriptors['proof'].parent_refs,
        descriptors['plan'].artifact_ref, descriptors['package'].artifact_ref))
    replace_manifest(contents, descriptors, proof)
    descriptors['new_curve'] = replace(descriptors['new_curve'], output_name='A')
    descriptors['old_curve'] = replace(descriptors['old_curve'], output_name='B')
    return ValidationSources(contents, descriptors)


@pytest.mark.parametrize('defect', ['none', 'cohort', 'raw_identity', 'ambiguous', 'basis_missing'])
def test_conditional_projection_never_guesses_or_changes_identity(defect):
    from tcad_artifact.analysis_bindings import source_bindings
    from scidiscovery.operations.input_validation import ValidationSources
    sources = _mapping_fixture(); contents = dict(sources); descriptors = dict(sources.binding_descriptors)
    if defect in {'cohort', 'raw_identity'}:
        alias = 'plan' if defect == 'cohort' else 'new_curve'
        descriptors[alias] = replace(descriptors[alias], artifact_ref=descriptors[alias].artifact_ref.model_copy(update={'artifact_id':'different_identity'}))
    elif defect in {'ambiguous', 'basis_missing'}:
        prior = json.loads(contents['previous'])
        if defect == 'ambiguous':
            prior['source_references'].append({**prior['source_references'][0], 'source_key':'other', 'case_key':'two'})
        else:
            prior['source_references'][0]['case_mapping_basis']['evidence_refs'][0]['input_alias'] = 'unbound_log'
        contents['previous'] = canonical_json(prior)
    current = ValidationSources(contents, descriptors)
    before = deepcopy(contents)
    view = source_bindings(current)
    assert contents == before
    assert 'case_key' not in view['sources']['old_curve']  # Same bytes/old spelling is a different Artifact.
    if defect == 'none':
        known = view['sources']['new_curve']
        assert known['case_key'] == 'one'
        assert known['case_mapping_basis']['evidence_refs'] == [dict(input_alias='plan', locator='plan:/proposals/0')]
    else:
        assert 'case_key' not in view['sources']['new_curve']


def test_admitted_package_over_two_mib_still_opens_and_seals(tmp_path, monkeypatch):
    from tests.operations import test_tcad_result_analysis as fixture
    original = fixture.canonical_json
    def padded_package(value):
        raw = original(value)
        if isinstance(value, dict) and {"project", "review", "capability"}.issubset(value):
            # Legal JSON whitespace crosses the byte boundary without changing
            # the package's source hashes, review or scientific content.
            raw += b" " * (2 * 1024 * 1024)
        return raw
    monkeypatch.setattr(fixture, 'canonical_json', padded_package)
    worker, opened = open_analysis(analysis_system(tmp_path))
    write_analysis(opened, analysis_report(alias='solver_outputs_001', output_name='A'))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def test_start_excerpts_are_bounded_traceable_and_skip_hidden_inputs(tmp_path):
    from curve_score.analysis_workspace import _start_file, START_LIMIT
    from scidiscovery.operations.workspace import WorkspaceMaterializationRequest
    sources = _mapping_fixture()
    visible = tmp_path / 'inputs/plan.json'; visible.parent.mkdir()
    value = {'objective':'o' * 8192, 'proposals':[
        {'objectives':['later' * 1000], 'current_objectives':['current' * 1000], 'stop_conditions':['stop' * 1000]}
        for _ in range(16)]}
    visible.write_text(json.dumps(value))
    assignment = {'instruction':'Continue the selected task.', 'inputs':[dict(source_name='plan',
        port='experiment_plan', relative_path='inputs/plan.json', historical=True)], 'tools':[]}
    (tmp_path / 'assignment.json').write_text(json.dumps(assignment))
    descriptor = sources.binding_descriptors['plan']
    descriptors = {'plan':replace(descriptor, artifact_ref=descriptor.artifact_ref.model_copy(
        update={'schema_id':'scidiscovery.experiment-portfolio.v1'})),
        'hidden_secret':replace(descriptor, source_name='hidden_secret', port_name='hidden')}
    request = WorkspaceMaterializationRequest('fixture', tmp_path, {'plan':visible}, (), binding_descriptors=descriptors)
    _start_file(request, {'restored':[], 'copy_omissions':[]})
    raw = (tmp_path / 'analysis-start.json').read_bytes(); start = json.loads(raw)
    assert len(raw) <= START_LIMIT and start['omitted'] > 0
    assert b'hidden_secret' not in raw
    assert any(item['omitted'] for item in start['excerpts'])
    for item in start['excerpts']:
        original = value
        for key in item['pointer'].strip('/').split('/'):
            original = original[int(key)] if isinstance(original, list) else original[key]
        text = original if isinstance(original, str) else json.dumps(original, ensure_ascii=False)
        assert text.startswith(item['text'])


def test_explicit_new_scientific_basis_is_not_replaced_by_history():
    from tcad_artifact.analysis_bindings import source_bindings, materialize_references
    sources = _mapping_fixture()
    reference = dict(source_key='new_claim', input_alias='new_curve', output_name='A',
        experiment_key='e', case_key='two', case_mapping_basis=dict(kind='evidence',
            evidence_refs=[dict(input_alias='plan', locator='/proposals/0/cases/1')],
            rationale='A newly argued association, different from the prior conditional claim.'))
    payload = {'evidence':[dict(source_key='new_claim', locator='new_curve')], 'source_references':[reference]}
    before = deepcopy(payload)
    materialize_references(payload, source_bindings(sources), sources.binding_descriptors)
    assert payload == before
