"""Collected binary diagnostics must survive negative delivery and continuation."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.operation_workspace import snapshot_workspace, materialize_workspace
from tcad_artifact.project_packager import ImplementationGap
from scidiscovery.operations.workspace import WorkspaceMaterializationRequest
from tests.operations import test_tcad_initialization_outputs as initialization
from tests.operations.test_l4_local_tcad import _write_gap, _task_gap

BINARY = b'\x89HDF\r\n\x1a\n\x00\xff\x80fixture'


def test_collected_binary_gap_seals_snapshots_and_restores(tmp_path, monkeypatch):
    monkeypatch.setattr(initialization, 'RAW', BINARY)
    worker, transport, workspace = initialization.setup_case(tmp_path)
    declarations = workspace / 'deck/declarations.json'
    value = json.loads(declarations.read_bytes())
    value['raw_outputs'][0].update(relative_path='results/state.tdr', media_type='application/octet-stream')
    declarations.write_bytes(canonical_json(value))
    reply = worker.call_tool('worker_tcad_debug_run', dict(run_name='init', mode='initialization', output_names=['coarse_pre']))
    assert reply['state'] == 'succeeded', reply
    detail = json.loads(Path(reply['details_path']).read_bytes())
    relative = detail['outputs'][0]['relative_path']
    assert (workspace / relative).read_bytes() == BINARY
    _write_gap({'workspace_path': workspace})
    snapshot = snapshot_workspace(workspace)
    binary_snapshot = next(x for x in snapshot if x.relative_path == relative)
    assert binary_snapshot.content == BINARY
    assert binary_snapshot.media_type == 'application/octet-stream'
    sealed = worker.call_tool('worker_submit_result', {})
    assert sealed['state'] == 'completed', sealed
    assert 'iUhERg' not in json.dumps(sealed)  # Binary bytes never expand the tool summary.
    # Read the actual finalized candidate, not a hand-constructed gap.
    result = json.loads((worker._workspace.output_directory / 'result.json').read_bytes())
    gap = ImplementationGap.model_validate_json(canonical_json(result['payload']), strict=True)
    saved = next(x for x in gap.attempt_files if 'init/coarse_pre' in x.relative_path)
    assert saved.encoding == 'base64' and saved.raw_bytes() == BINARY
    assert result['handoff']['verdict'] == 'blocked'
    inputs = {}
    for port in ('execution_capability', 'experiment_plan'):
        inputs[port] = worker._workspace.input_paths[port]
    inputs['project'] = tmp_path / 'sealed-gap.json'
    inputs['project'].write_bytes(canonical_json(gap.model_dump(mode='json')))
    restored = tmp_path / 'review-workspace'
    materialize_workspace(WorkspaceMaterializationRequest(operation_id='tcad.deck.review.v1', workspace=restored,
        input_paths=inputs, provisional_roots=()))
    assert (restored / relative).read_bytes() == BINARY
    assert (restored / relative).stat().st_mode & 0o222 == 0
    # A failed-run snapshot must retain binary bytes and restore them as history.
    saved_snapshot = tmp_path / 'snapshot'
    for item in snapshot:
        destination = saved_snapshot / item.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item.content)
    retry = tmp_path / 'retry-workspace'
    materialize_workspace(WorkspaceMaterializationRequest(operation_id='tcad.deck.author.initial.v1', workspace=retry,
        input_paths=inputs, provisional_roots=(saved_snapshot,)))
    histories = list((retry / 'deck/reports/history').glob('*_coarse_pre'))
    assert len(histories) == 1 and histories[0].read_bytes() == BINARY
    assert not (retry / 'deck/reports/initialization.json').exists()
    assert len(transport.jobs) == 1


def test_binary_source_error_preserves_filename_and_cause(tmp_path):
    worker, _, workspace = initialization.setup_case(tmp_path)
    (workspace / 'deck/files/main.cmd').write_bytes(BINARY)
    _write_gap({'workspace_path': workspace})
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected'
    diagnostic = rejected['diagnostics'][0]
    assert diagnostic['path'] == '$.deck.files'
    assert all(x in diagnostic['message'] for x in ('main.cmd', 'not UTF-8', 'offset 0'))


def test_legacy_gap_encoding_and_invalid_binary_records():
    legacy = {**_task_gap(), 'attempt_files': [{'relative_path': 'reports/old.log', 'content': 'old log'}]}
    gap = ImplementationGap.model_validate_json(canonical_json(legacy), strict=True)
    assert gap.attempt_files[0].raw_bytes() == b'old log'
    for path, content in [('reports/bad.tdr', 'not-base64!'), ('../escape', 'AA==')]:
        with pytest.raises(ValueError):
            ImplementationGap.model_validate_json(canonical_json({**_task_gap(), 'attempt_files': [
                {'relative_path': path, 'content': content, 'encoding': 'base64'}]}), strict=True)


@pytest.mark.parametrize('defect', ['symlink', 'oversize'])
def test_binary_gap_retains_existing_file_safety_bounds(tmp_path, defect):
    worker, _, workspace = initialization.setup_case(tmp_path)
    path = workspace / 'deck/reports/state.tdr'
    if defect == 'symlink':
        outside = tmp_path / 'outside'; outside.write_bytes(BINARY)
        path.symlink_to(outside)
    else:
        with path.open('wb') as stream:
            stream.truncate(8 * 1024 * 1024 + 1)
    _write_gap({'workspace_path': workspace})
    rejected = worker.call_tool('worker_submit_result', {})
    assert rejected['state'] == 'rejected'
    expected = 'non-symlink' if defect == 'symlink' else 'byte limit'
    assert expected in str(rejected['diagnostics']), rejected


def test_installed_binary_gap_roundtrip(installed_probe):
    installed_probe('full', r'''
import json
import tempfile
from pathlib import Path
from tcad_artifact.operation_workspace import finalize_workspace, snapshot_workspace, _restore_attempt
from tcad_artifact.project_packager import parse_author_result
from scidiscovery.operations.workspace import WorkspaceFinalizationRequest
root = Path(tempfile.mkdtemp()); deck = root / 'deck'
(deck / 'files').mkdir(parents=True); (deck / 'reports').mkdir()
raw = b'\x89HDF\r\n\x1a\n\x00\xff'
(deck / 'reports/state.tdr').write_bytes(raw)
plan = root / 'plan.json'; plan.write_text('{"proposals":[{}]}')
gap = dict(schema_version=1, result_kind='implementation_gap', summary='Numerical gate failed.', missing_inputs=[],
    affected_work=[dict(plan_locator='/proposals/0', impact='Cannot proceed.')], suggested_resolution='Review initialization.')
(deck / 'gap.json').write_text(json.dumps(gap))
result = json.loads(finalize_workspace(WorkspaceFinalizationRequest(operation_id='tcad.deck.author.initial.v1',
    workspace=root, input_paths={'experiment_plan':plan}, output_limit_bytes=8*1024*1024, final_submission=True)))
parsed = parse_author_result(json.dumps(result['payload']).encode())
assert result['handoff']['verdict'] == 'blocked'
target = root / 'restored'
_restore_attempt(target, parsed.attempt_files, author=False, deterministic=False)
assert (target / 'reports/state.tdr').read_bytes() == raw
assert next(x for x in snapshot_workspace(root) if x.relative_path=='deck/reports/state.tdr').content == raw
''')
