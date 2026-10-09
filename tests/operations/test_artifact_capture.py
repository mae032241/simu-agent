"""Real task-local seal, immutable versions, inventory and original readers."""
import json
from copy import deepcopy
import os
from pathlib import Path

import pytest
from jsonschema.validators import validator_for

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.scientific_usage import scientific_use_restricted
from scidiscovery.operation_contract import DiagnosticError
from scidiscovery.artifact_agent.service.run_outputs import RunOutputError
from tests.operations.test_evidence_source_capture import open_extraction
from tests.operations.test_general_transform_operations import _intake
from tests.operations.test_scientific_attachments import audit_worker
from tests.operations.test_scientific_use_provenance_edges import setup
from tests.operations.test_scientific_use_provenance_continuation import system
from tests.operations.worker_fixtures import attached_worker


def extraction(tmp_path):
    catalog, runtime, root, worker, opened, request = open_extraction(tmp_path)
    workspace = Path(opened['assignment_path']).parent
    alias = runtime.runs.status(worker._run_id).inputs[0].source_name
    return catalog, runtime, root, worker, opened, workspace, alias


def draft(opened, source, *, batch_sources=None):
    payload = _intake().model_dump(mode='json')
    payload['scientific_foundation']['evidence'][0]['source_key'] = source
    payload['scientific_foundation']['items'][0]['evidence_keys'] = [source]
    value = {'handoff':{'verdict':'pass','summary':'Capture fixture.'}, 'payload':payload}
    if batch_sources is not None:
        value['capture_sources'] = [{'source_aliases':batch_sources}]
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(value))
    return value


def experiment(tmp_path):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    root.call_tool('operation_invoke', {'name':'capture', 'operation_id':'science.experiment.v1',
        'instruction':'Test this exact hypothesis with local evidence.',
        'inputs':[{'port':'subject','artifact_names':['objective.hypothesis.output']}]})
    worker = attached_worker(runtime, root, 'capture')
    opened = worker.call_tool('worker_open_assignment', {})
    return runtime, instance, root, worker, opened, Path(opened['assignment_path']).parent


def records(runtime, worker):
    return runtime.runs.tool_evidence(worker._run_id)


def index(runtime, worker):
    record = next(r for r in reversed(records(runtime, worker)) if r['metadata'].get('kind') == 'capture_inventory')
    return record, json.loads(runtime.artifacts.read(ArtifactRef.model_validate(record['artifact_ref'])))


def test_final_capture_unselected_failure_draft_projection_and_downstream_reader(tmp_path, monkeypatch):
    catalog, runtime, root, worker, opened, workspace, alias = extraction(tmp_path)
    for name, data in {'trial1.csv':b'x,y\n1,2\n','trial2.csv':b'x,y\n2,3\n','trial3.csv':b'x,y\n3,-1\n'}.items():
        (workspace/'scratch/artifacts'/name).write_bytes(data)
    value = draft(opened, 'file:trial1.csv', batch_sources=[alias])
    schema = json.loads((workspace/'schema/result.schema.json').read_bytes())
    projected = deepcopy(value)
    from scidiscovery.plugin_runtime.results import RESULT_COPIES
    for path in RESULT_COPIES['scidiscovery.scientific-intake.v1']:
        node = projected
        tokens = path.strip('/').split('/')
        for token in tokens[:-1]:
            node = node.get(token, {})
        if isinstance(node, dict): node.pop(tokens[-1], None)
    def remove_versions(node):
        if isinstance(node, dict):
            node.pop('schema_version', None)
            for child in node.values(): remove_versions(child)
        elif isinstance(node, list):
            for child in node: remove_versions(child)
    remove_versions(projected)
    errors = list(validator_for(schema)(schema).iter_errors(projected))
    assert not errors, [(list(error.path), error.message) for error in errors]
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    captured = [r for r in records(runtime, worker) if r['metadata'].get('kind') == 'scientific_attachment']
    assert len(captured) == 3 and all(r['metadata']['capture_mode'] == 'auto_captured' for r in captured)
    third = next(r for r in captured if r['metadata']['file_name'] == 'trial3.csv')
    report = runtime.artifacts.read(runtime.runs.status(worker._run_id).output_ref)
    assert third['alias'].encode() not in report and b'file:' not in report and b'capture_sources' not in report
    control, capture = index(runtime, worker)
    assert capture['attempt_inventory'] == 'not_declared' and capture['coverage'] == 'complete'
    assert control['source_ref'] is None and control['metadata']['scientific_claim_admissible'] is False
    assert scientific_use_restricted(runtime.runs, [ArtifactRef.model_validate(control['artifact_ref'])]) is True
    auditor, source = audit_worker(root, runtime)
    found = auditor.call_tool('worker_reference_read', {'source':source})['references']
    attachment = next(r for r in found if r['locator'] == '/@attachments/'+third['alias'])
    original_read = runtime.artifacts.read
    def no_bulk(ref):
        assert ref != ArtifactRef.model_validate(third['artifact_ref'])
        return original_read(ref)
    monkeypatch.setattr(runtime.artifacts, 'read', no_bulk)
    delivered = auditor.call_tool('worker_reference_read', {'source':source,'action':'read',
        'reference':attachment['reference'],'delivery':'file'})
    assert Path(delivered['file_path']).read_bytes() == b'x,y\n3,-1\n'


def test_stage_versions_scoped_paths_native_completion_and_receipt_reuse(tmp_path):
    runtime, instance, root, worker, opened, workspace = experiment(tmp_path)
    artifact_dir = workspace/'scratch/artifacts'
    (artifact_dir/'derive.py').write_bytes(b'print(1)\n')
    implementation = worker.call_tool('worker_experiment_stage', {'stage':'implementation',
        'conclusion':'Exact runnable method.', 'materials':['file:scratch/artifacts/derive.py']})
    count = len(records(runtime, worker))
    duplicate = worker.call_tool('worker_experiment_stage', {'stage':'implementation',
        'conclusion':'Exact runnable method.', 'materials':['file:scratch/artifacts/derive.py']})
    assert duplicate['reference'] == implementation['reference'] and len(records(runtime, worker)) == count
    (artifact_dir/'result.csv').write_bytes(b'value\n1\n')
    (artifact_dir/'run.log').write_bytes(b'finished\n')
    execution = worker.call_tool('worker_experiment_stage', {'stage':'execution','conclusion':'Local worker result.',
        'native_execution':{'implementation':implementation['reference'],'state':'succeeded',
            'logs':['file:run.log'],'results':['file:result.csv']}})
    old_stage = runtime.runs.sealed_material_record(runtime.runs.status(worker._run_id), execution['reference'])
    old_raw = runtime.artifacts.read(ArtifactRef.model_validate(old_stage['artifact_ref']))
    old_file = json.loads(old_raw)['native_execution']['results'][0]
    (artifact_dir/'result.csv').write_bytes(b'value\n2\n')
    latest = worker.call_tool('worker_experiment_stage', {'stage':'validity','conclusion':'Retain exact observed version.',
        'materials':[execution['reference'],'file:result.csv',f"file@{execution['reference']}:scratch/artifacts/result.csv"]})
    last_raw = runtime.runs.read_tool_evidence(runtime.runs.status(worker._run_id), latest['reference'])
    assert json.loads(last_raw)['materials'][-1] == old_file
    assert json.loads(last_raw)['materials'][-2] != old_file
    assert runtime.artifacts.read(ArtifactRef.model_validate(old_stage['artifact_ref'])) == old_raw
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'payload':{
        'summary':'Native implementation and actual execution.', 'outcome':'completed', 'remaining_question':'',
        'adopted_stages':[implementation['reference'],execution['reference'],latest['reference']]}}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'


def comparison_versions(tmp_path):
    from tests.operations.test_native_experiment import _declared_prediction, _observation_comparison
    runtime, _, _, worker, opened, workspace = experiment(tmp_path)
    declaration = worker.call_tool('worker_experiment_stage', _declared_prediction(['objective_source']))['reference']
    directory = workspace/'scratch/artifacts'
    (directory/'sum.py').write_bytes(b'print(4)\n')
    implementation = worker.call_tool('worker_experiment_stage', {'stage':'implementation',
        'conclusion':'Retain the exact sum program.', 'materials':['file:sum.py']})['reference']
    (directory/'sum.log').write_bytes(b'4\n')
    (directory/'result.csv').write_bytes(b'value,revision\n4,1\n')
    execution = worker.call_tool('worker_experiment_stage', {'stage':'execution', 'conclusion':'Worker reported 4.',
        'native_execution':{'implementation':implementation, 'state':'succeeded', 'logs':['file:sum.log'],
            'results':['file:result.csv']}})['reference']
    sealed = json.loads(runtime.runs.read_tool_evidence(runtime.runs.status(worker._run_id), execution))
    old_alias = sealed['native_execution']['results'][0]
    (directory/'result.csv').write_bytes(b'value,revision\n4,2\n')
    old_reference = f'file@{execution}:scratch/artifacts/result.csv'
    return runtime, worker, opened, declaration, implementation, execution, old_alias, _observation_comparison(declaration, old_reference)


@pytest.mark.parametrize('reference', ['old_version', 'current_file', 'sealed_alias'])
def test_stage_comparison_authoring_normalizes_exact_versions_and_final_adoption(tmp_path, reference):
    from scidiscovery.general_science_experiment_task import STAGE_TOOL, StageSubmission
    from scidiscovery.artifact_agent.schema.validation import ValidationCheckResult
    from tests.operations.test_native_experiment import _observation_comparison
    runtime, worker, opened, declaration, implementation, execution, old_alias, request = comparison_versions(tmp_path)
    if reference != 'old_version':
        request = _observation_comparison(declaration, 'file:scratch/artifacts/result.csv' if reference == 'current_file' else old_alias)
    request['materials'] = [execution]
    schema = STAGE_TOOL.input_model.model_json_schema()
    assert not list(validator_for(schema)(schema).iter_errors(request))
    sealed_schema = ValidationCheckResult.model_json_schema()
    assert sealed_schema['properties']['evidence_keys']['items']['pattern'] == r'^[A-Za-z0-9][A-Za-z0-9_.:/-]*$'
    if reference == 'old_version':
        assert list(validator_for(StageSubmission.model_json_schema())(StageSubmission.model_json_schema()).iter_errors(request))
    validity = worker.call_tool('worker_experiment_stage', request)['reference']
    run = runtime.runs.status(worker._run_id)
    raw = runtime.runs.read_tool_evidence(run, validity)
    sealed = StageSubmission.model_validate_json(raw, strict=True)
    observation = sealed.comparison.observations[0]
    assert sealed.comparison.result.evidence_keys == (observation,) and not observation.startswith(('file:', 'file@'))
    assert (observation == old_alias) is (reference != 'current_file')
    expected = b'value,revision\n4,2\n' if reference == 'current_file' else b'value,revision\n4,1\n'
    assert runtime.runs.read_tool_evidence(run, observation) == expected
    record = runtime.runs.sealed_material_record(run, validity)
    original = runtime.runs.sealed_material_record(run, observation)
    assert record['source_refs'][observation].model_dump(mode='json') == original['artifact_ref']
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'payload':{
        'summary':'Retained the exact sum comparison.', 'outcome':'completed', 'remaining_question':'',
        'limitations':['Worker-reported native execution without independent attestation.'],
        'adopted_stages':[declaration, implementation, execution, validity]}}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert runtime.runs.read_tool_evidence(runtime.runs.status(worker._run_id), observation) == expected


@pytest.mark.parametrize('fault', ['unknown_stage', 'missing_old_file', 'outside_observations',
    'missing_value', 'missing_unit', 'changed_check', 'changed_mode'])
def test_stage_comparison_draft_references_preserve_scientific_rejections(tmp_path, fault):
    from scidiscovery.operation_contract import SemanticRuleViolation, ToolInputError
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    runtime, worker, _, _, _, _, _, request = comparison_versions(tmp_path)
    comparison = request['comparison']
    if fault == 'unknown_stage':
        comparison['observations'] = comparison['result']['evidence_keys'] = ['file@not_sealed:scratch/artifacts/result.csv']
    elif fault == 'missing_old_file':
        comparison['observations'] = comparison['result']['evidence_keys'] = [comparison['observations'][0].replace('result.csv', 'missing.csv')]
    elif fault == 'outside_observations': comparison['result']['evidence_keys'] = ['file:sum.log']
    elif fault == 'missing_value': comparison['result'].pop('observed_value')
    elif fault == 'missing_unit': comparison['result'].pop('unit')
    elif fault == 'changed_check': comparison['result']['check_key'] = 'other'
    elif fault == 'changed_mode': comparison['result']['evaluation_mode'] = 'reviewed_qualitative'
    with pytest.raises((WorkerToolError, SemanticRuleViolation, ToolInputError)):
        worker.call_tool('worker_experiment_stage', request)
    assert not any(record['metadata'].get('stage') == 'validity' for record in records(runtime, worker))
    assert runtime.runs.status(worker._run_id).state == 'running'


def test_unknown_inventory_is_readable_but_not_adoptable_and_repair_is_new_receipt(tmp_path):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    draft(opened, 'file:result.csv')
    reply = worker.call_tool('worker_submit_result', {})
    assert reply['state'] == 'rejected' and runtime.runs.status(worker._run_id).state == 'running'
    unknown = next(r for r in records(runtime, worker) if r['metadata'].get('kind') == 'scientific_attachment')
    assert unknown['source_ref'] is None and unknown['metadata']['provenance_status'] == 'unknown'
    assert runtime.runs.read_tool_evidence(runtime.runs.status(worker._run_id), unknown['alias']) == b'x\n1\n'
    draft(opened, 'file:result.csv', batch_sources=[alias])
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    current = records(runtime, worker)
    assert unknown in current
    known = next(r for r in current if r['metadata'].get('provenance_status') == 'known')
    assert known['artifact_ref'] != unknown['artifact_ref'] and known['publication_key'] != unknown['publication_key']
    with runtime.runs._connect() as db:
        cleared = db.execute("SELECT diagnostic_json FROM run_activity WHERE run_id=? AND activity='scientific_source_edges_v1'", (worker._run_id,)).fetchall()
    assert all(unknown['artifact_ref']['artifact_id'].encode() not in row[0] for row in cleared)


@pytest.mark.parametrize('reference', ['file:duplicate.csv','run:trial'])
def test_ambiguous_or_run_reference_is_not_silently_resolved(tmp_path, reference):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    for directory in ['a','b']:
        (workspace/'scratch/artifacts'/directory).mkdir()
        (workspace/'scratch/artifacts'/directory/'duplicate.csv').write_bytes(b'x\n1\n')
    draft(opened, reference, batch_sources=[alias])
    assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    assert runtime.runs.status(worker._run_id).output_ref is None


@pytest.mark.parametrize('fault', ['secret','chunk_secret','key','long_line','opaque','fifo','symlink','excluded','symlink_parent'])
def test_private_unsafe_and_unreadable_files_are_capture_gaps(tmp_path, fault):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    target = workspace/'scratch/artifacts/data.txt'
    if fault == 'secret': target.write_bytes(b'password=123456789012\n')
    elif fault == 'chunk_secret': target.write_bytes((b'x\n'*524280)+b'api_key='+(b'A'*24)+b'\n')
    elif fault == 'key': target.write_bytes(b'-----BEGIN PRIVATE KEY-----\nabc\n')
    elif fault == 'long_line': target.write_bytes(b'a'*65537)
    elif fault == 'opaque': target = target.with_suffix('.npz'); target.write_bytes(b'opaque')
    elif fault == 'fifo': os.mkfifo(target)
    elif fault == 'symlink': target.symlink_to(workspace/'assignment.json')
    elif fault == 'excluded': target = workspace/'scratch/artifacts/.credentials'; target.write_bytes(b'private')
    elif fault == 'symlink_parent':
        (workspace/'scratch/artifacts/link').symlink_to(workspace/'inputs', target_is_directory=True)
        target = workspace/'scratch/artifacts/link/source.txt'
    draft(opened, 'file:'+str(target.relative_to(workspace)), batch_sources=[alias])
    assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    assert not any(r['metadata'].get('kind') == 'scientific_attachment' for r in records(runtime, worker))
    _, captured = index(runtime, worker)
    assert all('artifact_ref' not in entry for entry in captured['entries'])
    assert not any('.credentials' in json.dumps(entry) for entry in captured['entries'])


def test_diagnostics_do_not_capture_and_empty_stages_do_not_create_index(tmp_path):
    runtime, instance, root, worker, opened, workspace = experiment(tmp_path)
    for number in range(3):
        worker.call_tool('worker_experiment_stage', {'stage':'design','conclusion':str(number)})
    assert len(records(runtime, worker)) == 3
    assert not any(r['metadata'].get('kind') == 'capture_inventory' for r in records(runtime, worker))
    (workspace/'scratch/artifacts/new.csv').write_bytes(b'x\n1\n')
    Path(opened['output_directory'],'result.json').write_bytes(canonical_json({'payload':{
        'summary':'Not captured by diagnosis.', 'outcome':'inconclusive','remaining_question':'Need verification.',
        'adopted_stages':['file:new.csv']}}))
    with pytest.raises(RunOutputError): runtime.runs.validate_candidate(worker._run_id)
    assert len(records(runtime, worker)) == 3


def test_explicit_authorized_binary_survives_automatic_type_gap(tmp_path):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    (workspace/'scratch/artifacts/model.npz').write_bytes(b'opaque model fixture')
    published = worker.call_tool('worker_publish_files', {'source_aliases':[alias],
        'files':[{'path':'scratch/artifacts/model.npz','purpose':'Authorized model deliverable'}]})
    draft(opened, published['files'][0]['reference'])
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    _, captured = index(runtime, worker)
    assert captured['coverage'] == 'incomplete' and captured['entries'][0]['status'] == 'metadata_only'


def test_receipt_index_and_m3a_edges_roll_back_together_then_reuse_orphans(tmp_path, monkeypatch):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    draft(opened, 'file:result.csv', batch_sources=[alias])
    saved = []
    register = runtime.artifacts.register_file
    def remember(*args, **kwargs):
        result = register(*args, **kwargs)
        saved.append(result.ref)
        return result
    monkeypatch.setattr(runtime.artifacts, 'register_file', remember)
    with monkeypatch.context() as patch:
        patch.setattr(runtime.runs, '_encode_evidence_snapshot', lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError('fixture transaction failure')))
        assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    assert saved and not records(runtime, worker)
    with runtime.runs._connect() as db:
        assert not db.execute("SELECT 1 FROM run_activity WHERE run_id=? AND activity='scientific_source_edges_v1'", (worker._run_id,)).fetchall()
    from scidiscovery.artifact_agent.service.scientific_usage import ScientificProvenanceError
    with pytest.raises(ScientificProvenanceError): scientific_use_restricted(runtime.runs, (saved[0],))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert ArtifactRef.model_validate(records(runtime, worker)[0]['artifact_ref']) == saved[0]


def test_accepted_candidate_retry_never_reads_mutable_capture_directory(tmp_path, monkeypatch):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    output = workspace/'scratch/artifacts/result.csv'
    output.write_bytes(b'x\n1\n')
    draft(opened, 'file:result.csv', batch_sources=[alias])
    with monkeypatch.context() as patch:
        patch.setattr(runtime.runs, '_register_candidate', lambda *args: (_ for _ in ()).throw(ConnectionError('fixture registration interruption')))
        assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    assert runtime.runs.status(worker._run_id).accepted_candidate_digest is not None
    original = records(runtime, worker)
    output.write_bytes(b'x\n2\n')
    import scidiscovery.artifact_agent.service.artifact_capture as capture
    monkeypatch.setattr(capture, '_source', lambda *args: pytest.fail('Accepted retry reread mutable files'))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert records(runtime, worker) == original
    ref = ArtifactRef.model_validate(next(r for r in original if r['metadata']['kind'] == 'scientific_attachment')['artifact_ref'])
    assert runtime.artifacts.read(ref) == b'x\n1\n'


@pytest.mark.parametrize('limit', ['bytes','files','enumeration'])
def test_capture_limits_are_explicit_without_partial_receipt_identity(tmp_path, monkeypatch, limit):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    for name in ['one.csv','two.csv']:
        (workspace/'scratch/artifacts'/name).write_bytes(b'x\n1\n')
    if limit in {'bytes','files'}:
        run = runtime.runs.status(worker._run_id)
        policy = dict(run.recovery_policy)
        policy['attachments'][{'bytes':'max_total_bytes','files':'max_files'}[limit]] = 1
        with runtime.runs._connect() as db:
            db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (canonical_json(policy), worker._run_id))
    else:
        compiled = runtime.runs._compiled(runtime.runs.status(worker._run_id))
        reduced = compiled.spec.artifact_capture.model_copy(update={'max_entries':1})
        replacement = __import__('dataclasses').replace(compiled, spec=compiled.spec.model_copy(update={'artifact_capture':reduced}))
        original = runtime.runs._compiled
        monkeypatch.setattr(runtime.runs, '_compiled', lambda run: replacement if run.run_id == worker._run_id else original(run))
    draft(opened, 'file:missing.csv' if limit == 'enumeration' else 'file:two.csv', batch_sources=[alias])
    assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    if limit != 'enumeration':
        assert not records(runtime, worker)
    else:
        _, captured = index(runtime, worker)
        assert captured['coverage'] == 'incomplete' and len(captured['entries']) <= 1


def test_author_cannot_expand_capture_to_external_or_private_roots(tmp_path):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    for scope in ['scratch','/opt/results','scratch/../inputs','scratch/.ssh','scratch/credentials']:
        value = draft(opened, alias)
        value['capture_sources'] = [{'directories':[scope],'source_aliases':[alias]}]
        Path(opened['output_directory'],'result.json').write_bytes(canonical_json(value))
        assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
        assert not records(runtime, worker)


def test_reading_index_through_reference_alias_does_not_make_it_a_scientific_source(tmp_path):
    _, runtime, root, worker, opened, workspace, alias = extraction(tmp_path)
    (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    draft(opened, 'file:result.csv', batch_sources=[alias])
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    control, captured = index(runtime, worker)
    encoded = json.dumps(captured)
    assert not any(key in encoded for key in ['artifact_ref','artifact_id','publication_key','sha256'])
    auditor, source = audit_worker(root, runtime)
    listing = auditor.call_tool('worker_reference_read', {'source':source})['references']
    entry = next(item for item in listing if item['locator'] == '/@attachments/'+control['alias'])
    original = auditor.call_tool('worker_reference_read', {'source':source,'action':'read',
        'reference':entry['reference'],'delivery':'file'})
    assert 'artifact_ref' not in Path(original['file_path']).read_text()
    from tests.operations.test_l2_run_invariants import _audit_envelope
    output = runtime.runs.backend.open(auditor._run_id).output_directory
    (output/'result.json').write_bytes(_audit_envelope(original['source']))
    assert auditor.call_tool('worker_submit_result', {})['state'] == 'rejected'


def test_declared_scientific_sources_and_unadopted_batches_remain_separate(tmp_path):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    root.call_tool('operation_invoke', {'name':'capture','operation_id':'science.experiment.v1',
        'instruction':'Use exact scientific sources.', 'inputs':[
            {'port':'subject','artifact_names':['objective.hypothesis.output']},
            {'port':'scientific_materials','artifact_names':['restricted']}]})
    worker = attached_worker(runtime, root, 'capture')
    opened = worker.call_tool('worker_open_assignment', {})
    workspace = Path(opened['assignment_path']).parent
    run = runtime.runs.status(worker._run_id)
    restricted = next(i.source_name for i in run.inputs if i.port_name == 'scientific_materials')
    clean = next(i.source_name for i in run.inputs if i.port_name == 'objective_source')
    for directory in ['clean','restricted']:
        (workspace/'scratch/artifacts'/directory).mkdir()
        (workspace/'scratch/artifacts'/directory/'result.csv').write_bytes(b'x\n1\n')
    request = {'stage':'design','conclusion':'One clean adopted batch.',
        'materials':['file:scratch/artifacts/clean/result.csv'], 'capture_sources':[
            {'directories':['scratch/artifacts/clean'],'source_aliases':[clean]},
            {'directories':['scratch/artifacts/restricted'],'source_aliases':[restricted]}]}
    stage = worker.call_tool('worker_experiment_stage', request)
    attachments = [r for r in records(runtime, worker) if r['metadata'].get('kind') == 'scientific_attachment']
    assert len(attachments) == 2  # Overlapping roots do not enumerate twice.
    clean_file = next(r for r in attachments if '/clean/' in r['metadata']['locator'])
    private_file = next(r for r in attachments if '/restricted/' in r['metadata']['locator'])
    assert not scientific_use_restricted(runtime.runs, [ArtifactRef.model_validate(clean_file['artifact_ref'])])
    assert scientific_use_restricted(runtime.runs, [ArtifactRef.model_validate(private_file['artifact_ref'])])
    record = runtime.runs.sealed_material_record(run, stage['reference'])
    assert not scientific_use_restricted(runtime.runs, [ArtifactRef.model_validate(record['artifact_ref'])])
    # Declared existing materials provide sources only for the cited new file.
    (workspace/'scratch/artifacts/adopted.csv').write_bytes(b'x\n2\n')
    stage = worker.call_tool('worker_experiment_stage', {'stage':'validity',
        'conclusion':'Explicit restricted adoption.', 'materials':[restricted,'file:adopted.csv']})
    adopted = next(r for r in records(runtime, worker) if r['metadata'].get('locator') == 'scratch/artifacts/adopted.csv')
    assert restricted in adopted['metadata']['derived_from']
    assert scientific_use_restricted(runtime.runs, [ArtifactRef.model_validate(adopted['artifact_ref'])])
    Path(opened['output_directory'],'result.json').write_bytes(canonical_json({'payload':{
        'summary':'Carry the actual adoption limitation.', 'outcome':'inconclusive',
        'remaining_question':'Independent evidence needed.', 'adopted_stages':[stage['reference']]}}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert scientific_use_restricted(runtime.runs, [runtime.runs.status(worker._run_id).output_ref])


@pytest.mark.parametrize('mutation', ['file','directory'])
def test_observed_mutation_is_a_capture_gap_without_reexecution(tmp_path, monkeypatch, mutation):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    target = workspace/'scratch/artifacts/result.csv'
    target.write_bytes(b'x\n1\n')
    import scidiscovery.artifact_agent.service.artifact_capture as capture
    if mutation == 'file':
        original = capture._Guard.feed
        def feed(guard, chunk):
            original(guard, chunk)
            target.write_bytes(b'x\n2\n')
        monkeypatch.setattr(capture._Guard, 'feed', feed)
    else:
        original = capture.snapshot_file
        def snapshot(*args, **kwargs):
            result = original(*args, **kwargs)
            (target.parent/'later.csv').write_bytes(b'x\n3\n')
            return result
        monkeypatch.setattr(capture, 'snapshot_file', snapshot)
    draft(opened, 'file:result.csv', batch_sources=[alias])
    result = worker.call_tool('worker_submit_result', {})
    _, captured = index(runtime, worker)
    assert captured['coverage'] == 'incomplete'
    if mutation == 'file':
        assert result['state'] == 'rejected'
        assert not any(r['metadata'].get('kind') == 'scientific_attachment' for r in records(runtime, worker))
    else:
        assert result['state'] == 'completed' and captured['coverage_changed']
        assert all(entry.get('path') != 'scratch/artifacts/later.csv' for entry in captured['entries'])


@pytest.mark.parametrize('when', ['index_registration','candidate_acceptance'])
def test_concurrent_successful_receipt_survives_repairable_capture_retry(tmp_path, monkeypatch, when):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    (workspace/'scratch/independent.txt').write_bytes(b'Independent successful receipt.\n')
    draft(opened, 'file:result.csv', batch_sources=[alias])
    def concurrent():
        return worker.call_tool('worker_publish_files', {'files':[{'path':'scratch/independent.txt',
            'purpose':'Preserve successful concurrent work.'}], 'source_aliases':[alias]})
    fired = []
    if when == 'index_registration':
        original = runtime.artifacts.register_file
        def register(path, registration, **kwargs):
            if Path(path).name == 'capture-index' and not fired:
                fired.append(concurrent())
            return original(path, registration, **kwargs)
        monkeypatch.setattr(runtime.artifacts, 'register_file', register)
    else:
        original = runtime.runs._accept_candidate
        def accept(run_id, digest):
            if not fired:
                fired.append(concurrent())
            return original(run_id, digest)
        monkeypatch.setattr(runtime.runs, '_accept_candidate', accept)
    result = worker.call_tool('worker_submit_result', {})
    assert result['state'] == 'rejected' and runtime.runs.status(worker._run_id).state == 'running'
    prior = next(r for r in records(runtime, worker) if r['metadata'].get('file_name') == 'independent.txt')
    assert fired and prior['alias'] == fired[0]['files'][0]['reference']
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    assert prior in records(runtime, worker)
    retained = records(runtime, worker)
    # A normalized retry uses exact original sources; it does not multiply files.
    assert len([r for r in retained if r['metadata'].get('locator') == 'scratch/artifacts/result.csv']) == 1


def test_unknown_and_known_capture_recovery_keeps_exact_receipts_and_scope(tmp_path):
    catalog, runtime, root, worker, opened, request = open_extraction(tmp_path)
    workspace = Path(opened['assignment_path']).parent
    alias = runtime.runs.status(worker._run_id).inputs[0].source_name
    (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    draft(opened, 'file:result.csv')
    assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    value = draft(opened, 'file:result.csv', batch_sources=[alias])
    value['handoff']['verdict'] = 'invalid'
    Path(opened['output_directory'],'result.json').write_bytes(canonical_json(value))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    saved = records(runtime, worker)
    prior = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(prior.run_id, reason='fixture interruption',
        expected_state=prior.state, expected_last_activity_at=prior.last_activity_at)
    root.call_tool('operation_invoke', {**request,'name':'continued','draft_from':'evidence','max_attempts':2})
    following = attached_worker(runtime, root, 'continued')
    following_open = following.call_tool('worker_open_assignment', {})
    assert records(runtime, following) == saved
    unknown = next(r for r in saved if r['metadata'].get('kind') == 'scientific_attachment' and r['metadata']['provenance_status'] == 'unknown')
    draft(following_open, unknown['alias'])
    assert following.call_tool('worker_submit_result', {})['state'] == 'rejected'
    known = next(r for r in saved if r['metadata'].get('provenance_status') == 'known')
    draft(following_open, known['alias'])
    assert following.call_tool('worker_submit_result', {})['state'] == 'completed'
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    other = runtime.artifacts.register(b'Other original.', ArtifactRegistration(kind='source',schema_id='opaque',
        payload_schema_version=1,media_type='text/plain',creator=runtime.actor),idempotency_key='other')
    runtime.scheduler_bindings.bind(instance=prior.instance_id,namespace='artifact',name='other',object_id=other.artifact_id)
    root.call_tool('operation_invoke', {**request,'name':'scope_changed','draft_from':'evidence','max_attempts':3,
        'inputs':[{'port':'source_material','artifact_names':['other']}]})
    changed = attached_worker(runtime, root, 'scope_changed')
    changed.call_tool('worker_open_assignment', {})
    assert records(runtime, changed) == []
    status = runtime.runs.recovery_evidence_status(runtime.runs.status(changed._run_id))
    assert status['adopted_count'] == 0 and len(status['not_adopted_record_indices']) == len(saved)


def test_undeclared_third_party_capture_does_not_change_identity_or_runtime(tmp_path):
    from tests.operations.test_l2_run_invariants import _system, _invoke
    from scidiscovery.operations.spec import json_projection
    catalog, runtime, _, _, root = _system(tmp_path)
    compiled = catalog.operation('blind.csv.observe.v1')
    assert compiled.spec.artifact_capture is None and 'artifact_capture' not in json_projection(compiled.spec)
    _invoke(root, 'plain')
    worker = attached_worker(runtime, root, 'plain')
    opened = worker.call_tool('worker_open_assignment', {})
    workspace = Path(opened['assignment_path']).parent
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    assert 'artifact_capture' not in assignment
    startup = json.loads((workspace/'worker-start.json').read_bytes())
    assert 'artifact_capture' not in startup and 'capture that declared scope' not in json.dumps(startup)
    (workspace/'scratch/artifacts/unrequested.txt').write_bytes(b'No declared automatic capture.\n')
    # The ordinary malformed output remains owned by its original validator.
    Path(opened['output_directory'],'result.json').write_text('{}')
    assert worker.call_tool('worker_submit_result', {})['state'] == 'rejected'
    assert not records(runtime, worker)


@pytest.mark.parametrize('directories', [
    ('scratch/results',),
    ('scratch/results', 'scratch/plots/data'),
    ('scratch/results', 'scratch/results/derived'),
])
def test_third_party_declared_roots_follow_startup_and_reach_exact_downstream_reader(tmp_path, directories):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.general_science_agent_operations import INTAKE_OUTPUT, _input
    from scidiscovery.operation_declaration import scientific_agent_operation
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.spec import ArtifactCaptureSpec, ComponentRef, ComponentSpec, PluginDependency, PluginDefinition
    from tests.operations.test_general_transform_operations import _root, _register
    def general(reference):
        return ComponentRef(reference.component_id, 'general_science') if reference is not None else None
    source = _input('source_material', 'Exact source for the custom-root batch.', 'opaque', media_types=('text/plain',))
    source = source.model_copy(update={'codec':general(source.codec), 'schema_resource':general(source.schema_resource)})
    output = INTAKE_OUTPUT.model_copy(update={key:general(getattr(INTAKE_OUTPUT, key)) for key in
        ('codec', 'schema_resource', 'validator', 'context_validator', 'semantic_contract')})
    declaration = scientific_agent_operation('third_party.capture.v1', 'Capture a declared custom scientific directory.',
        'A local batch requires immutable attachments.', 'External execution or scientific qualification.',
        agent=ComponentRef('evidence_agent', 'general_science'), workspace=ComponentRef('workspace', 'general_science'),
        prompt=ComponentRef('prompt'), tools=(), inputs=(source,), outputs=(output,), timeout=300,
        max_input_bytes=1024 * 1024, max_output_bytes=65536, max_files=1,
        artifact_capture=ArtifactCaptureSpec(roots=directories, required_source_ports=('source_material',)))
    plugin = PluginDefinition(plugin_id='third_party_capture', version='0.1.0', protocol_version='1',
        dependencies=(PluginDependency('builtin', '0.1.0'), PluginDependency('general_science', '0.1.0')),
        components=(ComponentSpec('prompt', 'resource', 'scidiscovery.general_science_resources:Resources.evidence_prompt'),),
        operations=(declaration,))
    catalog = compile_catalog((CORE_PLUGIN, PLUGIN, plugin))
    assert catalog.operation('third_party.capture.v1').plugin_id == 'third_party_capture'
    runtime, instance, root = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    _register(runtime, instance, name='original', raw=b'Exact custom batch source.', kind='source', schema='opaque', media_type='text/plain')
    root.call_tool('operation_invoke', {'name':'evidence', 'operation_id':'third_party.capture.v1',
        'instruction':'Retain the exact generated files.', 'inputs':[{'port':'source_material', 'artifact_names':['original']}]})
    worker = attached_worker(runtime, root, 'evidence')
    opened = worker.call_tool('worker_open_assignment', {})
    workspace = Path(opened['assignment_path']).parent
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    startup = json.loads((workspace/'worker-start.json').read_bytes())
    assert startup['artifact_capture'] == assignment['artifact_capture'] == {'directories':list(directories)}
    instruction = startup['output']['attachments']
    assert 'scratch/artifacts' not in instruction and f'file:{directories[0]}/path' in instruction
    assert f'file@<sealed-stage-reference>:{directories[0]}/path' in instruction
    assert not (workspace/'scratch/artifacts').exists()
    files = {}
    for number, directory in enumerate(startup['artifact_capture']['directories']):
        assert (workspace/directory).is_dir() and directory + '/' in instruction
        relative = directory + f'/trial{number}.csv'
        files[relative] = f'x,y\n{number},2\n'.encode()
        (workspace/relative).write_bytes(files[relative])
    (workspace/'scratch/artifacts').mkdir()
    (workspace/'scratch/artifacts/outside.csv').write_bytes(b'x,y\n99,99\n')
    draft(opened, 'file:'+next(iter(files)))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    captured = [record for record in records(runtime, worker) if record['metadata'].get('kind') == 'scientific_attachment']
    assert {record['metadata']['locator'] for record in captured} == set(files)
    _, inventory = index(runtime, worker)
    assert inventory['coverage'] == 'complete' and 'scratch/artifacts' not in json.dumps(inventory)
    for relative in files:
        (workspace/relative).write_bytes(b'changed after sealing\n')
    auditor, source = audit_worker(root, runtime)
    found = auditor.call_tool('worker_reference_read', {'source':source})['references']
    for record in captured:
        attachment = next(item for item in found if item['locator'] == '/@attachments/'+record['alias'])
        delivered = auditor.call_tool('worker_reference_read', {'source':source, 'action':'read',
            'reference':attachment['reference'], 'delivery':'file'})
        assert Path(delivered['file_path']).read_bytes() == files[record['metadata']['locator']]


@pytest.mark.parametrize('directory', ['../escape', '/tmp/escape', 'scratch', 'scratch/../escape', 'scratch/cache/results', 'scratch/credentials'])
def test_workspace_preparation_rejects_unsafe_declared_roots(tmp_path, directory):
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend, WorkspaceError
    backend = LocalTrustedBackend(tmp_path/'backend')
    with pytest.raises(WorkspaceError, match='capture directories are invalid'):
        backend.prepare(run_id='run_unsafe', inputs=(), assignment=canonical_json({'artifact_capture':{'directories':[directory]}}), result_schema=b'{}')
    assert list((tmp_path/'backend/workspaces').iterdir()) == []


def test_workspace_preparation_does_not_follow_custom_root_symlink(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend, WorkspaceError
    backend = LocalTrustedBackend(tmp_path/'backend')
    outside = tmp_path/'outside'
    outside.mkdir()
    original = os.mkdir
    def replaced(path, mode=0o777, *, dir_fd=None):
        if path == 'results' and dir_fd is not None:
            os.symlink(outside, path, target_is_directory=True, dir_fd=dir_fd)
        else:
            original(path, mode, dir_fd=dir_fd)
    monkeypatch.setattr(os, 'mkdir', replaced)
    with pytest.raises(WorkspaceError, match='not a real directory tree'):
        backend.prepare(run_id='run_unsafe', inputs=(), assignment=canonical_json({'artifact_capture':{'directories':['scratch/results/nested']}}), result_schema=b'{}')
    assert list(outside.iterdir()) == [] and list((tmp_path/'backend/.bindings').iterdir()) == []


def test_installed_capture_roots_and_stage_authoring_schema_preserve_sealed_contract(installed_probe):
    installed_probe('core', r'''
import json
import tempfile
from pathlib import Path
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.validation import ValidationCheckResult
from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.service.worker_start import write_worker_start
from scidiscovery.artifact_agent.service import artifact_capture
from scidiscovery.general_science_experiment_task import StageSubmission
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN
from scidiscovery.operations.catalog import compile_catalog, compile_installed_catalog
from scidiscovery.operations.spec import ArtifactCaptureSpec
catalog = compile_installed_catalog()
stage = next(tool for tool in catalog.operation('science.experiment.v1').worker_tools if tool.name == 'worker_experiment_stage')
old = 'file@tool_evidence_001:scratch/artifacts/result.csv'
request = {'stage':'validity', 'conclusion':'Compare the exact old version.', 'comparison':{
    'prediction':'tool_evidence_002', 'observations':[old], 'result':{
        'check_key':'sum', 'status':'pass', 'evaluation_mode':'deterministic_threshold',
        'observed_value':4.0, 'observed_text':'The retained sum is 4.', 'unit':'dimensionless',
        'evidence_keys':[old], 'rationale':'Retain the declared criterion.'}}}
Draft202012Validator(stage.input_model.model_json_schema()).validate(request)
stage.input_model.model_validate_json(canonical_json(request), strict=True)
assert ValidationCheckResult.model_json_schema()['properties']['evidence_keys']['items']['pattern'] == r'^[A-Za-z0-9][A-Za-z0-9_.:/-]*$'
try:
    StageSubmission.model_validate_json(canonical_json(request), strict=True)
except ValidationError:
    pass
else:
    raise AssertionError('sealed identifiers accepted raw file@ navigation')
request['comparison']['result'].pop('unit')
try:
    stage.input_model.model_validate_json(canonical_json(request), strict=True)
except ValidationError:
    pass
else:
    raise AssertionError('draft input lost scientific unit validation')
roots = ('scratch/results', 'scratch/plots/data')
operations = tuple(operation.model_copy(update={'artifact_capture':ArtifactCaptureSpec(roots=roots)})
    if operation.operation_id == 'science.evidence.extract.v1' else operation for operation in PLUGIN.operations)
compiled = compile_catalog((CORE_PLUGIN, PLUGIN.model_copy(update={'operations':operations}))).operation('science.evidence.extract.v1')
assignment = {'inputs':[], 'tools':['worker_publish_files'],
    'artifact_capture':{'directories':list(compiled.spec.artifact_capture.roots)}}
backend = LocalTrustedBackend(Path(tempfile.mkdtemp())/'backend')
workspace = backend.prepare(run_id='run_installed', inputs=(), assignment=canonical_json(assignment), result_schema=b'{}')
start = json.loads(write_worker_start(workspace, assignment).read_bytes())
assert start['artifact_capture'] == assignment['artifact_capture']
assert 'scratch/artifacts' not in start['output']['attachments']
assert 'file:scratch/results/path' in start['output']['attachments']
assert all((workspace.root/root).is_dir() for root in roots)
assert not (workspace.root/'scratch/artifacts').exists()
''')


@pytest.mark.parametrize('limit', ['index_item','deadline','empty_enumeration'])
def test_control_index_and_capture_time_share_explicit_bounds(tmp_path, monkeypatch, limit):
    _, runtime, _, worker, opened, workspace, alias = extraction(tmp_path)
    import scidiscovery.artifact_agent.service.artifact_capture as capture
    if limit == 'empty_enumeration':
        for name in ['a','b']:
            (workspace/'scratch/artifacts'/name).mkdir()
        compiled = runtime.runs._compiled(runtime.runs.status(worker._run_id))
        replacement = __import__('dataclasses').replace(compiled, spec=compiled.spec.model_copy(update={
            'artifact_capture':compiled.spec.artifact_capture.model_copy(update={'max_entries':1})}))
        original = runtime.runs._compiled
        monkeypatch.setattr(runtime.runs, '_compiled', lambda run: replacement if run.run_id == worker._run_id else original(run))
    else:
        (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    if limit == 'index_item':
        run = runtime.runs.status(worker._run_id)
        policy = deepcopy(run.recovery_policy)
        policy['attachments']['max_item_bytes'] = 8
        with runtime.runs._connect() as db:
            db.execute('UPDATE runs SET recovery_policy_json=? WHERE run_id=?', (canonical_json(policy), worker._run_id))
    elif limit == 'deadline':
        ticks = iter([0.0, 1000.0])
        monkeypatch.setattr(capture, 'time', __import__('types').SimpleNamespace(monotonic=lambda: next(ticks,1000.0)))
    draft(opened, alias, batch_sources=[alias])
    result = worker.call_tool('worker_submit_result', {})
    if limit == 'empty_enumeration':
        assert result['state'] == 'completed'
        _, captured = index(runtime, worker)
        assert captured['coverage'] == 'incomplete' and captured['entries'] == []
    else:
        assert result['state'] == 'rejected' and not records(runtime, worker)


def test_compiled_capture_identity_reaches_outer_invoke_conflict(tmp_path, monkeypatch):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from blind_csv_plugin.plugin import PLUGIN as BLIND
    from scidiscovery.operations.catalog import compile_catalog
    catalog, runtime, root, worker, _, request = open_extraction(tmp_path)
    old = catalog.operation(request['operation_id'])
    changed = old.spec.model_copy(update={'artifact_capture':old.spec.artifact_capture.model_copy(update={'max_entries':17})})
    revised = PLUGIN.model_copy(update={'operations':tuple(changed if op.operation_id == changed.operation_id else op for op in PLUGIN.operations)})
    current = compile_catalog((CORE_PLUGIN,revised,BLIND))
    assert current.operation(request['operation_id']).digest != old.digest
    frozen = runtime.runs.status(worker._run_id)
    assert frozen.operation_digest == old.digest
    monkeypatch.setattr(root.facade, '_operation_catalog', current)
    with pytest.raises(Exception, match='semantic_name_conflict'):
        root.call_tool('operation_invoke', request)
    assert runtime.runs.status(worker._run_id).operation_digest == frozen.operation_digest


@pytest.mark.parametrize('invalid', ['private_root','whole_scratch','source_port','capability'])
def test_capture_contract_invalid_scope_or_capability_fails_at_compile(invalid):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN
    from scidiscovery.operations.catalog import compile_catalog, CatalogCompileError
    op = next(op for op in PLUGIN.operations if op.operation_id == 'science.evidence.extract.v1')
    changes = {'private_root':{'roots':('scratch/credentials',)}, 'whole_scratch':{'roots':('scratch',)},
        'source_port':{'required_source_ports':('absent',)}}
    if invalid == 'capability':
        changed = op.model_copy(update={'executor':op.executor.model_copy(update={
            'native_tools':op.executor.native_tools.model_copy(update={'shell':'none'})})})
    else:
        changed = op.model_copy(update={'artifact_capture':op.artifact_capture.model_copy(update=changes[invalid])})
    revised = PLUGIN.model_copy(update={'operations':tuple(changed if current.operation_id == changed.operation_id else current for current in PLUGIN.operations)})
    with pytest.raises(CatalogCompileError) as failure:
        compile_catalog((CORE_PLUGIN,revised))
    assert failure.value.reason_code == 'artifact_capture_invalid'


def test_enumeration_order_does_not_multiply_capture_receipts(tmp_path, monkeypatch):
    runtime, _, _, worker, _, workspace = experiment(tmp_path)
    for name in ['b.csv','a.csv']:
        (workspace/'scratch/artifacts'/name).write_bytes(b'x\n1\n')
    import scidiscovery.artifact_agent.service.artifact_capture as capture
    original = capture._listing
    calls = []
    def listing(*args):
        entries, identity, complete = original(*args)
        calls.append(None)
        return (list(reversed(entries)) if len(calls) > 2 else entries), identity, complete
    monkeypatch.setattr(capture, '_listing', listing)
    request = {'stage':'design','conclusion':'Stable exact originals.', 'materials':['file:a.csv']}
    first = worker.call_tool('worker_experiment_stage', request)
    retained = records(runtime, worker)
    second = worker.call_tool('worker_experiment_stage', request)
    assert first == second and records(runtime, worker) == retained


@pytest.mark.parametrize('private', [b'api_key=abcdef0123456789abcdef', b'/home/owner/.ssh/private_key'])
def test_explicit_binary_publication_cannot_bypass_known_private_content(tmp_path, private):
    _, runtime, _, worker, _, workspace, alias = extraction(tmp_path)
    (workspace/'scratch/artifacts/model.npz').write_bytes(b'PK\x03\x04\x00' + private)
    with pytest.raises(DiagnosticError, match='private content'):
        worker.call_tool('worker_publish_files', {'files':[{'path':'scratch/artifacts/model.npz',
            'purpose':'Explicit binary fixture.'}], 'source_aliases':[alias]})
    assert not records(runtime, worker)
