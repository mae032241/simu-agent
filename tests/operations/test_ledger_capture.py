"""Host-only stable observation, safe derived views, exact identity and readers."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from scidiscovery.agent_execution_settings import parse_settings, effective_settings
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.scientific_usage import scientific_use_restricted
from tests.operations.test_artifact_capture import draft, index, records
from tests.operations.test_l2_run_invariants import _system
from tests.operations.test_scientific_attachments import audit_worker
from tests.operations.worker_fixtures import attached_worker

FIELDS = {'run_id':'int', 'ok':'bool', 'started_at':'int', 'metric':'str',
    'val_acc':'float', 'val_score':'float', 'wall_seconds':'float'}
PRIVATE_SCRIPT = '/home/' + 'fixture/private/script.py'
PRIVATE_MODEL = '/opt/exp/private/model.bin'


def row(number=1, **updates):
    return {'run_id':number, 'ok':number != 3, 'started_at':1234 + number,
        'metric':'validation', 'val_acc':0.5, 'val_score':-float(number), 'wall_seconds':1.0,
        'script':PRIVATE_SCRIPT, 'model_path':PRIVATE_MODEL, **updates}


def config(path, *, name='evidence', operation='science.evidence.extract.v1', **updates):
    return {'capture':{'allowed_roots':[str(path.parent)], 'tasks':{name:{'operation_id':operation,
        'ledgers':[{'logical_name':'covshift_results', 'path':str(path), 'fields':FIELDS,
            'name_field':'run_id', 'status_field':'ok', 'redacted_fields':['script','model_path'], **updates}]}}}}


def system(tmp_path, *, raw=None, **updates):
    catalog, runtime, instance, _, root = _system(tmp_path)
    source = runtime.artifacts.register(b'Study a bounded source.', ArtifactRegistration(
        kind='source', schema_id='opaque', payload_schema_version=1, media_type='text/plain',
        creator=runtime.actor), idempotency_key='ledger-source')
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact',
        name='source_paper', object_id=source.artifact_id)
    host = tmp_path/'host'
    host.mkdir()
    path = host/'results.jsonl'
    path.write_bytes(raw if raw is not None else b''.join(canonical_json(row(n))+b'\n' for n in range(1,31)))
    value = config(path, **updates)
    runtime.runs.agent_settings = parse_settings(value)
    request = dict(name='evidence', operation_id='science.evidence.extract.v1', max_attempts=2,
        instruction='Extract the bounded source facts.', inputs=[dict(port='source_material', artifact_names=['source_paper'])])
    root.call_tool('operation_invoke', request)
    worker = attached_worker(runtime, root, 'evidence')
    opened = worker.call_tool('worker_open_assignment', {})
    return runtime, instance, root, worker, opened, path, value, request


def seal(runtime, worker, opened):
    source = runtime.runs.status(worker._run_id).inputs[0].source_name
    draft(opened, source)
    return worker.call_tool('worker_submit_result', {})


def ledger(runtime, worker):
    return next(r for r in records(runtime, worker) if r['metadata'].get('representation') == 'derived_projection')


def view(runtime, worker):
    item = ledger(runtime, worker)
    return [json.loads(line) for line in runtime.artifacts.read(ArtifactRef.model_validate(item['artifact_ref'])).splitlines()]


def test_real_shape_third_failure_is_readable_derived_without_raw_or_qualification(tmp_path, monkeypatch):
    runtime, _, root, worker, opened, path, _, _ = system(tmp_path)
    assignment = json.loads(Path(opened['assignment_path']).read_bytes())
    assert assignment['artifact_capture']['ledgers'] == [{'logical_name':'covshift_results',
        'representation':'derived_projection', 'raw_retained':False, 'producer_trust':'author_reported'}]
    assert str(path) not in json.dumps(assignment)
    from scidiscovery.artifact_agent.service.worker_start import startup_document
    start = startup_document(assignment)
    assert start['artifact_capture']['ledgers'] == assignment['artifact_capture']['ledgers']
    raw_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert seal(runtime, worker, opened)['state'] == 'completed'
    item = ledger(runtime, worker)
    assert item['metadata']['private_source']['sha256'] == raw_digest
    assert item['metadata']['derived_from'] == [] and item['source_ref'] is None
    assert item['metadata']['provenance_status'] == 'unknown'
    assert item['metadata']['scientific_claim_admissible'] is False
    assert scientific_use_restricted(runtime.runs, [ArtifactRef.model_validate(item['artifact_ref'])])
    rows = view(runtime, worker)
    assert len(rows) == 30 and rows[2]['values']['ok'] is False
    assert rows[2]['values']['run_id'] == 3 and rows[2]['values']['val_score'] == -3
    assert all(r['raw_retained'] is False and r['omitted_fields'] == ['script','model_path'] for r in rows)
    control, public = index(runtime, worker)
    entry = next(e for e in public['entries'] if e['path'] == 'ledger:covshift_results')
    assert entry['physical_records'] == 30 and entry['physical_count_complete']
    assert entry['attempt_total'] == 'unknown' and entry['projection_coverage'] == 'complete'
    assert public['attempt_inventory'] == 'declared_author_reported'
    assert 'private_source' not in json.dumps(public) and raw_digest not in json.dumps(public)
    # Real original attachment reader, including delivery=file, exposes only view.
    auditor, source = audit_worker(root, runtime)
    refs = auditor.call_tool('worker_reference_read', {'source':source})['references']
    target = next(r for r in refs if r['locator'] == '/@attachments/'+item['alias'])
    original_read = runtime.artifacts.read
    def no_bulk(ref):
        assert ref != ArtifactRef.model_validate(item['artifact_ref'])
        return original_read(ref)
    monkeypatch.setattr(runtime.artifacts, 'read', no_bulk)
    delivered = auditor.call_tool('worker_reference_read', {'source':source, 'action':'read',
        'reference':target['reference'], 'delivery':'file'})
    safe_bytes = Path(delivered['file_path']).read_bytes()
    assert len(safe_bytes.splitlines()) == 30
    assert PRIVATE_SCRIPT.encode() not in safe_bytes and PRIVATE_MODEL.encode() not in safe_bytes
    from scidiscovery.artifact_agent.service.tool_evidence import scientific_evidence_projection
    public_receipts = scientific_evidence_projection(canonical_json({'records':records(runtime, worker)}))
    assert b'derived_projection' in public_receipts and b'"raw_retained":false' in public_receipts
    assert raw_digest.encode() not in public_receipts and str(path).encode() not in public_receipts
    assert not any(r['metadata'].get('file_name') == 'results.jsonl' for r in records(runtime, worker))


@pytest.mark.parametrize('fault', ['tail','invalid','duplicate','missing','nonfinite','secret','absolute','rows','record'])
def test_rows_fields_and_caps_preserve_explicit_gaps(tmp_path, fault):
    raw = canonical_json(row())+b'\n'
    updates = {}
    if fault == 'tail': raw += canonical_json(row(2))
    elif fault == 'invalid': raw += b'{broken\n'+canonical_json(row(3))+b'\n'
    elif fault == 'duplicate': raw += canonical_json(row(1, ok=False))+b'\n'
    elif fault == 'missing':
        value = row(); value.pop('ok'); raw = canonical_json(value)+b'\n'
    elif fault == 'nonfinite': raw = raw.replace(b'0.5', b'NaN')
    elif fault == 'secret': raw = canonical_json(row(metric='sk-'+'a'*24))+b'\n'
    elif fault == 'absolute': raw = canonical_json(row(metric='/opt/private/value'))+b'\n'
    elif fault == 'rows': raw += canonical_json(row(2))+b'\n'; updates['max_rows'] = 1
    elif fault == 'record': updates['max_record_bytes'] = 128
    runtime, _, _, worker, opened, _, _, _ = system(tmp_path, raw=raw, **updates)
    assert seal(runtime, worker, opened)['state'] == 'completed'
    _, public = index(runtime, worker)
    entry = next(e for e in public['entries'] if e['path'].startswith('ledger:'))
    assert public['coverage'] == 'incomplete' and entry['attempt_total'] == 'unknown'
    assert entry['physical_records'] == len(raw.splitlines())
    if fault == 'duplicate': assert entry['duplicate_groups'][0]['locators'] == ['line:1','line:2']
    rows = view(runtime, worker)
    if fault == 'tail': assert rows[-1]['status'] == 'pending_tail' and rows[-1]['values'] == {}
    if fault == 'rows': assert rows[-1]['status'] == 'omitted' and rows[-1]['through_line'] == 2
    safe = json.dumps(rows)
    assert 'sk-'+'a'*24 not in safe and '/opt/private' not in safe and 'broken' not in safe


@pytest.mark.parametrize('change', ['path','fields','rows','root','links','source_total','retained_total'])
def test_effective_configuration_changes_all_request_identities(tmp_path, change):
    runtime, _, root, worker, opened, path, value, request = system(tmp_path)
    frozen = runtime.runs.status(worker._run_id)
    normalized = root.call_tool('operation_preflight', request)['normalized_request']
    assert normalized['capture_policy_digest'] == frozen.recovery_policy['capture']['digest']
    assert str(path) not in json.dumps(normalized)
    assert seal(runtime, worker, opened)['state'] == 'completed'
    changed = deepcopy(value)
    setting = changed['capture']['tasks']['evidence']['ledgers'][0]
    if change == 'path': setting['path'] = str(path.parent/'other.jsonl')
    elif change == 'fields': setting['fields'] = {key:kind for key,kind in FIELDS.items() if key != 'val_score'}
    elif change == 'rows': setting['max_rows'] = 10
    elif change == 'root': changed['capture']['allowed_roots'] = [str(path.parent.parent)]
    elif change == 'links': setting['path_links'] = {PRIVATE_MODEL:'scratch/artifacts/result.csv'}
    elif change == 'source_total': changed['capture']['max_total_source_bytes'] = 1000
    elif change == 'retained_total': changed['attachments'] = {'max_total_bytes':65536}
    runtime.runs.agent_settings = parse_settings(changed)
    with pytest.raises(Exception, match='semantic_name_conflict'): root.call_tool('operation_invoke', request)
    with pytest.raises(Exception, match='capture_configuration_changed'): root.call_tool('operation_invoke', normalized)
    fresh = root.call_tool('operation_preflight', {**request,'on_conflict':'create_revision'})
    assert fresh['admissible'], fresh
    assert fresh['normalized_request']['capture_policy_digest'] != frozen.recovery_policy['capture']['digest']
    revision = root.call_tool('operation_invoke', fresh['normalized_request'])['result']
    current = runtime.runs.status(runtime.scheduler_bindings.resolve(instance=root.facade.instance,
        namespace='run', name=revision['name']))
    assert current.request_digest != frozen.request_digest
    assert current.output_binding_fingerprint != frozen.output_binding_fingerprint


@pytest.mark.parametrize('fault', ['root_symlink','file_symlink','fifo','missing','bytes','revoked','cap'])
def test_external_authority_and_safe_open_fail_closed_without_raw(tmp_path, fault):
    runtime, _, _, worker, opened, path, value, _ = system(tmp_path)
    if fault == 'root_symlink':
        moved = path.parent.with_name('moved'); path.parent.rename(moved); path.parent.symlink_to(moved)
    elif fault == 'file_symlink':
        moved = path.with_name('moved.jsonl'); path.rename(moved); path.symlink_to(moved)
    elif fault == 'fifo': path.unlink(); os.mkfifo(path)
    elif fault == 'missing': path.unlink()
    elif fault == 'bytes': path.write_bytes(b'x'*1048577)
    elif fault == 'revoked': runtime.runs.agent_settings = parse_settings({})
    elif fault == 'cap':
        value['capture']['tasks']['evidence']['ledgers'][0]['max_rows'] = 1
        runtime.runs.agent_settings = parse_settings(value)
    assert seal(runtime, worker, opened)['state'] == 'completed'
    _, public = index(runtime, worker)
    entry = next(e for e in public['entries'] if e['path'].startswith('ledger:'))
    assert entry['status'] == 'incomplete' and public['coverage'] == 'incomplete'
    assert 'reference' not in entry and 'physical_records' not in entry
    assert str(path) not in json.dumps(public)
    assert not any(r['metadata'].get('representation') for r in records(runtime, worker))


def test_instance_and_author_cannot_grant_capture_and_disabled_tasks_keep_identity(tmp_path):
    runtime, instance, root, worker, opened, _, value, request = system(tmp_path)
    with pytest.raises(ValueError, match='deployment-only'):
        runtime.scheduler_bindings.save_agent_settings(instance.instance_id, value,
            expected_revision=0, maintenance=runtime.instance_maintenance)
    with pytest.raises(ValueError, match='deployment-only'):
        effective_settings(parse_settings({}), value)
    with pytest.raises(Exception): root.call_tool('operation_invoke', {**request, 'resolved_capture_policy':value})
    with pytest.raises(Exception):
        worker.call_tool('worker_publish_files', {'files':[{'path':PRIVATE_SCRIPT,'purpose':'invalid'}], 'source_aliases':[]})
    assert seal(runtime, worker, opened)['state'] == 'completed'
    runtime.runs.agent_settings = parse_settings({})
    new = root.call_tool('operation_preflight', {**request,'name':'different'})
    assert new['admissible'], new
    assert 'capture_policy_digest' not in new['normalized_request']


def test_exact_configured_file_link_uses_only_same_capture_and_view_remains_unknown(tmp_path):
    runtime, _, _, worker, opened, _, _, _ = system(tmp_path,
        path_links={PRIVATE_MODEL:'scratch/artifacts/result.csv'})
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    source = runtime.runs.status(worker._run_id).inputs[0].source_name
    draft(opened, 'file:result.csv', batch_sources=[source])
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    rows = view(runtime, worker)
    assert rows[0]['file_links'] == [{'field':'model_path','file':'file:scratch/artifacts/result.csv'}]
    assert ledger(runtime, worker)['metadata']['derived_from'] == []


def test_recovery_inherits_source_policy_and_revocation_blocks_new_read(tmp_path):
    runtime, instance, root, worker, opened, path, value, request = system(tmp_path)
    # Capture a view without final acceptance, then fail the authoring Run.
    from scidiscovery.artifact_agent.service.artifact_capture import capture_science
    workspace = Path(opened['assignment_path']).parent
    capture_science(runtime.runs, worker._run_id, {}, (), workspace=workspace)
    old = ledger(runtime, worker)
    prior = runtime.runs.status(worker._run_id)
    runtime.runs.record_failure(prior.run_id, reason='fixture interruption', expected_state='running',
        expected_last_activity_at=prior.last_activity_at)
    new_path = path.with_name('new.jsonl'); new_path.write_bytes(canonical_json(row(99))+b'\n')
    value['capture']['tasks']['evidence']['ledgers'][0]['path'] = str(new_path)
    runtime.runs.agent_settings = parse_settings(value)
    recovery = root.call_tool('operation_preflight', {**request,'name':'continued','draft_from':'evidence','max_attempts':2})
    assert recovery['admissible']
    assert recovery['normalized_request']['capture_policy_digest'] == prior.recovery_policy['capture']['digest']
    root.call_tool('operation_invoke', recovery['normalized_request'])
    continued = attached_worker(runtime, root, 'continued')
    restored = continued.call_tool('worker_open_assignment', {})
    source = runtime.runs.status(continued._run_id)
    assert source.recovery_policy['capture']['ledgers'][0]['path'] == str(path)
    runtime.runs.agent_settings = parse_settings({})
    capture_science(runtime.runs, continued._run_id, {}, (), workspace=Path(restored['assignment_path']).parent)
    assert runtime.artifacts.read(ArtifactRef.model_validate(old['artifact_ref']))
    _, public = index(runtime, continued)
    assert public['coverage'] == 'incomplete'
    assert next(e for e in public['entries'] if e['path'].startswith('ledger:'))['reason'] == 'capture_authority_unavailable'


def test_installed_configuration_contract_and_derived_projection(installed_probe):
    installed_probe('core', r'''
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path
from scidiscovery.agent_execution_settings import parse_settings, AttachmentSettings
from scidiscovery.operations.spec import ArtifactCaptureSpec, json_projection
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
from scidiscovery.artifact_agent.service.artifact_capture import _LedgerFraming, _project_ledger, _Guard
from scidiscovery.artifact_agent.service.attachments import snapshot_file
from scidiscovery.operation_contract import ToolInputError
import scidiscovery.artifact_agent.service.artifact_capture as module
assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert compile_installed_catalog().operation('science.evidence.extract.v1').spec.artifact_capture
assert 'ledgers' not in json_projection(ArtifactCaptureSpec())
assert 'capture_policy_digest' in OperationCallInput.model_json_schema()['properties']
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)/'input.jsonl'
    raw = b'{"run_id":3,"ok":false,"val_score":-1.5,"script":"/home/' + b'fixture/private/a.py","model_path":"/opt/exp/private/a.bin"}\n'
    path.write_bytes(raw)
    settings = parse_settings({'capture':{'allowed_roots':[directory], 'tasks':{'probe':{
        'operation_id':'science.evidence.extract.v1', 'ledgers':[{'logical_name':'results',
        'path':str(path), 'name_field':'run_id', 'status_field':'ok',
        'fields':{'run_id':'int','ok':'bool','val_score':'float'},
        'redacted_fields':['script','model_path']}]}}}})
    ledger = settings.capture.tasks['probe'].ledgers[0].model_dump(mode='json')
    framing = _LedgerFraming(); framing.feed(raw)
    target = Path(directory)/'view.jsonl'
    evidence = _project_ledger(path, target, ledger, framing, [], 65536, time.monotonic()+5)
    guard = _Guard('text/plain',65536); guard.feed(target.read_bytes()); guard.finish()
    record = json.loads(target.read_bytes())
    assert record['values'] == {'run_id':3,'ok':False,'val_score':-1.5}
    assert record['raw_retained'] is False and record['representation'] == 'derived_projection'
    assert evidence['physical_records'] == 1 and evidence['attempt_total'] == 'unknown'
    assert b'/home/' not in target.read_bytes() and b'/opt/' not in target.read_bytes()
    consumed = []
    def charge(size):
        consumed.append(size)
        path.write_bytes(raw+b' ')
    bounds = AttachmentSettings(max_item_bytes=512,max_total_bytes=len(raw)+32)
    try:
        with path.open('rb',buffering=0) as source:
            snapshot_file(source,Path(directory)/'failed',bounds,lambda:None,on_read=charge)
        raise AssertionError('Mutated source must be rejected')
    except ToolInputError:
        pass
    assert len(raw) <= sum(consumed) <= bounds.max_total_bytes
    second = Path(directory)/'second.jsonl'; second.write_bytes(raw)
    try:
        with second.open('rb',buffering=0) as source:
            snapshot_file(source,Path(directory)/'second-view',bounds,lambda:None,
                total=sum(consumed),on_read=consumed.append)
        raise AssertionError('Failed observation must not refund consumed bytes')
    except ToolInputError:
        pass
''')


def test_stage_versions_and_negative_file_links_keep_exact_source_observation(tmp_path):
    from tests.operations.test_scientific_use_provenance_continuation import system as scientific_system
    from tests.operations.test_scientific_use_provenance_edges import setup
    runtime, instance, root = scientific_system(tmp_path)
    setup(runtime, instance, root)
    path = tmp_path/'ledger.jsonl'
    path.write_bytes(canonical_json(row())+b'\n'+canonical_json(row(2,model_path='/opt/other/model.bin'))+b'\n')
    runtime.runs.agent_settings = parse_settings(config(path,name='capture',operation='science.experiment.v1',
        path_links={PRIVATE_MODEL:'scratch/artifacts/result.csv'}))
    root.call_tool('operation_invoke', {'name':'capture','operation_id':'science.experiment.v1',
        'instruction':'Test this exact hypothesis with local evidence.',
        'inputs':[{'port':'subject','artifact_names':['objective.hypothesis.output']}]})
    worker = attached_worker(runtime,root,'capture')
    opened = worker.call_tool('worker_open_assignment',{})
    workspace = Path(opened['assignment_path']).parent
    (workspace/'scratch/artifacts/method.py').write_bytes(b'print(1)\n')
    (workspace/'scratch/artifacts/result.csv').write_bytes(b'x\n1\n')
    stage = worker.call_tool('worker_experiment_stage',{'stage':'implementation',
        'conclusion':'Runnable fixture.', 'materials':['file:method.py']})
    _,public = index(runtime,worker)
    assert stage['capture']['attempt_inventory'] == public['attempt_inventory'] == 'declared_author_reported'
    original = ledger(runtime,worker)
    first_bytes = runtime.artifacts.read(ArtifactRef.model_validate(original['artifact_ref']))
    first_rows = [json.loads(line) for line in first_bytes.splitlines()]
    assert first_rows[0]['file_links'] and 'file_links' not in first_rows[1]
    assert original['metadata']['derived_from'] == []
    path.write_bytes(canonical_json(row(99))+b'\n')
    worker.call_tool('worker_experiment_stage',{'stage':'validity','conclusion':'New source version.',
        'materials':[stage['reference']]})
    versions = [r for r in records(runtime,worker) if r['metadata'].get('representation')]
    assert len(versions) == 2
    assert versions[0]['metadata']['private_source']['sha256'] != versions[1]['metadata']['private_source']['sha256']
    assert runtime.artifacts.read(ArtifactRef.model_validate(original['artifact_ref'])) == first_bytes


@pytest.mark.parametrize('fault',['mutation','parse_deadline'])
def test_observation_mutation_and_parser_deadline_are_bounded_gaps(tmp_path,monkeypatch,fault):
    runtime,_,_,worker,opened,path,_,_ = system(tmp_path)
    import scidiscovery.artifact_agent.service.artifact_capture as capture
    if fault == 'mutation':
        original = capture._LedgerFraming.feed
        def feed(counter,chunk):
            original(counter,chunk)
            path.write_bytes(canonical_json(row(99))+b'\n')
        monkeypatch.setattr(capture._LedgerFraming,'feed',feed)
    else:
        original = capture._project_ledger
        def project(snapshot,target,ledger,framing,entries,limit,deadline):
            return original(snapshot,target,ledger,framing,entries,limit,0)
        monkeypatch.setattr(capture,'_project_ledger',project)
    assert seal(runtime,worker,opened)['state'] == 'completed'
    _,public = index(runtime,worker)
    entry = next(e for e in public['entries'] if e['path'].startswith('ledger:'))
    assert public['coverage'] == 'incomplete'
    if fault == 'mutation': assert entry['status'] == 'incomplete' and 'private_source' not in entry
    else:
        assert entry['physical_records'] == 30 and entry['parsed_records'] == 0
        assert view(runtime,worker)[0]['through_line'] == 30


def test_accepted_retry_does_not_reobserve_host_and_private_unknown_names_never_publish(tmp_path,monkeypatch):
    raw = canonical_json(row(**{'/opt/private/key':'sk-'+'a'*24}))+b'\n'
    runtime,_,_,worker,opened,path,_,_ = system(tmp_path,raw=raw)
    source = runtime.runs.status(worker._run_id).inputs[0].source_name
    draft(opened,source)
    with monkeypatch.context() as patch:
        patch.setattr(runtime.runs,'_register_candidate',lambda *args: (_ for _ in ()).throw(ConnectionError('fixture')))
        assert worker.call_tool('worker_submit_result',{})['state'] == 'rejected'
    assert runtime.runs.status(worker._run_id).accepted_candidate_digest
    item = ledger(runtime,worker)
    raw_view = runtime.artifacts.read(ArtifactRef.model_validate(item['artifact_ref']))
    assert b'/opt/private/key' not in raw_view and b'sk-' not in raw_view
    assert json.loads(raw_view)['unconfigured_fields'] == 1
    path.write_bytes(canonical_json(row(99))+b'\n')
    import scidiscovery.artifact_agent.service.artifact_capture as capture
    monkeypatch.setattr(capture,'_ledger_source',lambda *args: pytest.fail('accepted host reread'))
    assert worker.call_tool('worker_submit_result',{})['state'] == 'completed'
    assert runtime.artifacts.read(ArtifactRef.model_validate(item['artifact_ref'])) == raw_view


@pytest.mark.parametrize('field',['password','api_key','secret','access_token'])
def test_configured_private_export_names_are_rejected_and_cannot_be_aliased(tmp_path,field):
    path = tmp_path/'source.jsonl'
    path.write_bytes(canonical_json({**row(),field:'abcdefghijklmnop'})+b'\n')
    value = config(path,fields={**FIELDS,field:'str'})
    with pytest.raises(ValueError,match='Invalid host ledger declaration'):
        parse_settings(value)
    # fields maps each exact source key to its scalar type; it has no rename or
    # source selector through which a password could become a harmless key.
    value = config(path,fields={**FIELDS,'note':{'source':field,'kind':'str'}})
    with pytest.raises(ValueError): parse_settings(value)


@pytest.mark.parametrize('publication',['automatic','explicit'])
@pytest.mark.parametrize('field',['password','api_key','secret'])
def test_quoted_json_secret_is_rejected_by_shared_publication_guard(tmp_path,publication,field):
    from tests.operations.test_artifact_capture import extraction
    _,runtime,_,worker,opened,workspace,source = extraction(tmp_path)
    target = workspace/'scratch/artifacts/data.json'
    target.write_bytes(canonical_json({field:'abcdefghijklmnop'})+b'\n')
    if publication == 'explicit':
        with pytest.raises(Exception,match='private'):
            worker.call_tool('worker_publish_files',{'files':[{'path':'scratch/artifacts/data.json',
                'purpose':'Fixture JSON.'}],'source_aliases':[source]})
    else:
        draft(opened,'file:data.json',batch_sources=[source])
        assert worker.call_tool('worker_submit_result',{})['state'] == 'rejected'
        _,public = index(runtime,worker)
        assert next(e for e in public['entries'] if e.get('path') == 'scratch/artifacts/data.json')['reason'] == 'capture_private_content'
    assert not any(r['metadata'].get('locator') == 'scratch/artifacts/data.json' for r in records(runtime,worker))


def test_legacy_frozen_projection_omits_private_field_and_unknown_alias_does_not_select_it(tmp_path):
    from scidiscovery.artifact_agent.service.artifact_capture import _LedgerFraming, _project_ledger
    import time
    source = tmp_path/'source.jsonl'
    raw = canonical_json({**row(),'password':'abcdefghijklmnop'})+b'\n'
    source.write_bytes(raw)
    configured = config(source,fields={**FIELDS,'password':'str'})['capture']['tasks']['evidence']['ledgers'][0]
    configured.update(max_rows=128,max_record_bytes=16384,path_links={})
    target = tmp_path/'derived.jsonl'
    framing = _LedgerFraming(); framing.feed(raw)
    _project_ledger(source,target,configured,framing,[],65536,time.monotonic()+5)
    entry = json.loads(target.read_bytes())
    assert 'password' not in entry['values']
    assert {'field':'password','reason':'unsafe_or_type'} in entry['field_gaps']
    assert b'abcdefghijklmnop' not in target.read_bytes()


def two_ledgers(runtime,path,value,*,source_budget):
    second = path.with_name('second.jsonl')
    path.write_bytes(canonical_json(row())+b'\n')
    second.write_bytes(canonical_json(row(2))+b'\n')
    item = value['capture']['tasks']['evidence']['ledgers'][0]
    item['max_bytes'] = 512
    value['capture']['tasks']['evidence']['ledgers'].append({**deepcopy(item),
        'logical_name':'second', 'path':str(second)})
    value['capture']['max_total_source_bytes'] = source_budget
    runtime.runs.agent_settings = parse_settings(value)
    return second


def test_two_source_observations_share_explicit_io_cap_independent_of_view_storage(tmp_path):
    # Configure before invocation so the aggregate cap is in the same identity.
    runtime,_,root,worker,opened,path,value,request = system(tmp_path)
    assert seal(runtime,worker,opened)['state'] == 'completed'
    second = two_ledgers(runtime,path,value,source_budget=300)
    assert path.stat().st_size < 300 and second.stat().st_size < 300
    assert path.stat().st_size + second.stat().st_size > 300
    reply = root.call_tool('operation_invoke',{**request,'on_conflict':'create_revision'})['result']
    continued = attached_worker(runtime,root,reply['name'])
    opened = continued.call_tool('worker_open_assignment',{})
    assert seal(runtime,continued,opened)['state'] == 'completed'
    _,public = index(runtime,continued)
    entries = [entry for entry in public['entries'] if entry['path'].startswith('ledger:')]
    assert [entry['status'] for entry in entries] == ['retained','incomplete']
    assert public['coverage'] == 'incomplete'
    assert len([r for r in records(runtime,continued) if r['metadata'].get('representation')]) == 1


def test_tightened_live_storage_cap_counts_both_ledgers_and_existing_receipts(tmp_path):
    runtime,_,root,worker,opened,path,value,request = system(tmp_path)
    assert seal(runtime,worker,opened)['state'] == 'completed'
    second = two_ledgers(runtime,path,value,source_budget=1024)
    reply = root.call_tool('operation_invoke',{**request,'on_conflict':'create_revision'})['result']
    continued = attached_worker(runtime,root,reply['name'])
    opened = continued.call_tool('worker_open_assignment',{})
    from scidiscovery.artifact_agent.service.artifact_capture import capture_science
    workspace = Path(opened['assignment_path']).parent
    capture_science(runtime.runs,continued._run_id,{},(),workspace=workspace)
    previous = records(runtime,continued)
    refs = [ArtifactRef.model_validate(r['artifact_ref']) for r in previous if r['metadata'].get('representation')]
    assert len(refs) == 2
    view_bytes = [len(runtime.artifacts.read(ref)) for ref in refs]
    limit = max(view_bytes)+10
    assert all(size < limit for size in view_bytes) and sum(view_bytes) > limit
    # Reading permission remains; only aggregate retained storage is tightened.
    value['attachments'] = {'max_total_bytes':limit}
    runtime.runs.agent_settings = parse_settings(value)
    path.write_bytes(canonical_json(row(3))+b'\n')
    second.write_bytes(canonical_json(row(4))+b'\n')
    with pytest.raises(Exception,match='budget'):
        capture_science(runtime.runs,continued._run_id,{},(),workspace=workspace)
    assert records(runtime,continued) == previous
    assert all(runtime.artifacts.read(ref) for ref in refs)


def test_failed_mutating_first_source_does_not_refund_consumed_io(tmp_path,monkeypatch):
    runtime,_,root,worker,opened,path,value,request = system(tmp_path)
    assert seal(runtime,worker,opened)['state'] == 'completed'
    second = two_ledgers(runtime,path,value,source_budget=300)
    # Both fit alone; the first consumes its allowance before mutation is found.
    raw = canonical_json(row(metric='validation'+'x'*32))+b'\n'
    path.write_bytes(raw); second.write_bytes(raw)
    assert 220 < len(raw) < 300 and 2*len(raw) > 300
    reply = root.call_tool('operation_invoke',{**request,'on_conflict':'create_revision'})['result']
    continued = attached_worker(runtime,root,reply['name'])
    opened = continued.call_tool('worker_open_assignment',{})
    import scidiscovery.artifact_agent.service.artifact_capture as capture
    original = capture._LedgerFraming.feed
    consumed = []
    def mutate(counter,chunk):
        consumed.append(len(chunk))
        original(counter,chunk)
        path.write_bytes(raw+b' ')
    monkeypatch.setattr(capture._LedgerFraming,'feed',mutate)
    assert seal(runtime,continued,opened)['state'] == 'completed'
    _,public = index(runtime,continued)
    entries = [entry for entry in public['entries'] if entry['path'].startswith('ledger:')]
    assert [entry['status'] for entry in entries] == ['incomplete','incomplete']
    assert all(entry['reason'] == 'attachment_publication_invalid' for entry in entries)
    assert len(raw) <= sum(consumed) <= 300
    assert not any(r['metadata'].get('representation') for r in records(runtime,continued))
