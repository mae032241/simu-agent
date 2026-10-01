"""F-13: authoring, packing, runner collection and analysis agree on control paths."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact import remote_runner_py36 as runner
from tcad_artifact.execution_control import PROCESS_LOG_PATH
from tcad_artifact.project_packager import (
    DeckProjectDraft, ExecutionPackage, TCADRuntimeManifest,
    attest_runtime_contract, package_execution_package_json,
)
from tests.operations.test_runtime_plugin_configuration import _execution_package


def log_package():
    body = json.loads(_execution_package())
    body['project'].update(collect_generated_outputs=True, expected_outputs=[{
        'name': 'tcad_log', 'relative_path': 'tcad.log', 'capture': 'process_log',
        'media_type': 'text/plain', 'max_bytes': 4096,
    }])
    package = ExecutionPackage.model_validate_json(canonical_json(body), strict=True)
    return package, canonical_json(package.model_dump(mode='json'))


def test_sealed_log_alias_survives_real_packaging_collection_and_attestation(tmp_path):
    package, raw = log_package()
    packaged = package_execution_package_json(raw, output_root=tmp_path / 'prepared')
    job = packaged.job_spec.model_dump(mode='json')
    runner._validate_job(job)
    assert job['expected_outputs'][0]['relative_path'] == PROCESS_LOG_PATH
    assert canonical_json(package.model_dump(mode='json')) == raw
    assert package.project.expected_outputs[0].relative_path == 'tcad.log'
    assert package_execution_package_json(raw, output_root=tmp_path / 'prepared') == packaged
    work = tmp_path / 'remote/work'
    work.mkdir(parents=True)
    (work.parent / 'worker.log').write_bytes(b'captured stdout\n')
    (work / 'tcad.log').write_bytes(b'native log must survive\n')
    (work / 'adaptive_0079.tdr').write_bytes(b'generated frame')
    records = runner._collect_expected(str(work), job['expected_outputs'],
        {'max_output_bytes': 4096, 'transfer_chunk_bytes': 1024},
        collect_generated_outputs=True)
    assert {item['relative_path'] for item in records} == {
        PROCESS_LOG_PATH, 'tcad.log', 'adaptive_0079.tdr'}
    assert (work / 'tcad.log').read_bytes() == b'native log must survive\n'
    manifest = TCADRuntimeManifest.model_validate_json(canonical_json({
        'started_at': None, 'completed_at': '2026-09-29T00:00:00Z',
        'terminal_state': 'succeeded', 'exit_code': 0, 'error': '', 'outputs': records}), strict=True)
    payloads = {item['name']: (work / item['relative_path']).read_bytes() for item in records}
    assert attest_runtime_contract(package, manifest, output_payloads=payloads).verdict == 'pass'
    wrong = manifest.model_copy(update={'outputs': tuple(
        item.model_copy(update={'relative_path': 'tcad.log.old'}) if item.name == 'tcad_log' else item
        for item in manifest.outputs)})
    assert attest_runtime_contract(package, wrong).verdict == 'fail'


@pytest.mark.parametrize('change', ['two_logs', 'reserved_output', 'reserved_input', 'reserved_slot'])
def test_capture_conflicts_rejected_before_execution(change):
    package, _ = log_package()
    body = package.project.model_dump(mode='json')
    if change == 'two_logs':
        body['expected_outputs'].append({**body['expected_outputs'][0], 'name': 'other', 'relative_path': 'other.log'})
    elif change == 'reserved_output':
        body['expected_outputs'].append({**body['expected_outputs'][0], 'capture': 'workspace_file',
            'name': 'other', 'relative_path': PROCESS_LOG_PATH})
    elif change == 'reserved_input':
        body['files'].append({'relative_path': PROCESS_LOG_PATH, 'content': 'collision'})
    else:
        body['input_slots'] = [{'semantic_name': 'collision', 'target_relative_path': PROCESS_LOG_PATH,
            'media_type': 'text/plain'}]
    with pytest.raises(ValidationError):
        DeckProjectDraft.model_validate_json(canonical_json(body), strict=True)


def test_author_schema_and_real_prepare_delegate_all_output_capture(tmp_path, monkeypatch):
    from tests.operations.test_experiment_approval_handoff import experiment, start, decide
    from tcad_artifact.command_adapter import CommandTCADExecutorAdapter
    from tests.operations.tcad_policy_fixtures import policy_snapshot
    f = experiment(tmp_path, monkeypatch)
    schema = f.worker.call_tool('worker_experiment_prepare', {'action': 'schema'})['implementation_schema']
    assert not {'expected_outputs', 'collect_generated_outputs'} & schema['properties'].keys()
    assert '.scid-capture' not in json.dumps(schema)
    # Keep the real command-adapter preparation; replace only the external transport.
    adapter = object.__new__(CommandTCADExecutorAdapter)
    adapter.local_result_root = tmp_path / 'results'
    monkeypatch.setattr(adapter, 'execution_policy', policy_snapshot)
    monkeypatch.setattr(adapter, '_require_active_capability', lambda _: None)
    calls = []
    def transport(action, payload):
        calls.append(action)
        assert action == 'prepare'
        job = json.loads(Path(payload['job_spec']['local_path']).read_bytes())
        runner._validate_job(job)
        assert job['collect_generated_outputs'] is True
        assert job['expected_outputs'][0]['relative_path'] == PROCESS_LOG_PATH
        return {'submission': {'schema_version': 1, **payload['job_spec']}}
    monkeypatch.setattr(adapter, '_call', transport)
    monkeypatch.setattr(f.adapter, 'prepare', adapter.prepare)
    first = start(f)
    assert first['state'] == 'awaiting_authorization' and not calls
    decide(f, first, 'authorize_execution')
    for _ in range(2):
        assert f.worker.call_tool('worker_experiment_execute', {'action': 'advance'})['state'] == 'running'
    assert calls == ['prepare'] and f.adapter.submits == 1


def test_collected_process_log_enters_analysis_with_same_transport_mapping(tmp_path, monkeypatch):
    from tests.operations import test_tcad_result_analysis as fixture
    original = fixture.analysis_materials
    def with_log(**kwargs):
        plan, package, manifest, plx, csv = original(**kwargs)
        project = package.project.model_dump(mode='json')
        project['expected_outputs'][0]['capture'] = 'process_log'
        package = package.model_copy(update={'project': DeckProjectDraft.model_validate_json(canonical_json(project), strict=True)})
        value = json.loads(manifest)
        value['outputs'][0]['relative_path'] = PROCESS_LOG_PATH
        return plan, package, canonical_json(value), plx, csv
    monkeypatch.setattr(fixture, 'analysis_materials', with_log)
    system = fixture.analysis_system(tmp_path)
    worker, opened = fixture.open_analysis(system)
    fixture.write_analysis(opened, fixture.analysis_report())
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
