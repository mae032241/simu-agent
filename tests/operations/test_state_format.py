"""A breaking release must reject old state before it mutates anything."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from scidiscovery.artifact_agent.state_format import ensure_state_format, StateFormatError, MARKER, STATE_FORMAT


def test_new_state_and_restart(tmp_path):
    state = tmp_path / 'state'
    ensure_state_format(state)
    assert json.loads((state / MARKER).read_text()) == {'format':STATE_FORMAT}
    (state / 'database').mkdir()
    ensure_state_format(state)


@pytest.mark.parametrize('marker', [None, '{}', '{', '{"format":"old"}'])
def test_rejects_old_state_without_writes(tmp_path, marker):
    from scidiscovery.artifact_agent.runtime import open_runtime
    state = tmp_path / 'state'
    state.mkdir()
    (tmp_path / 'project').mkdir()
    (state / 'old.sqlite3').write_bytes(b'old-data')
    if marker is not None:
        (state / MARKER).write_text(marker)
    before = {p.name:p.read_bytes() for p in state.iterdir()}
    with pytest.raises(StateFormatError, match='new empty state root'):
        open_runtime(project_root=tmp_path / 'project', state_root=state)
    assert {p.name:p.read_bytes() for p in state.iterdir()} == before


def test_concurrent_initialization_and_symlink_marker(tmp_path):
    state = tmp_path / 'state'
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(ensure_state_format, [state, state]))
    other = tmp_path / 'other'
    other.mkdir()
    (other / MARKER).symlink_to(state / MARKER)
    with pytest.raises(StateFormatError):
        ensure_state_format(other)


def test_install_precheck_is_read_only(tmp_path):
    state = tmp_path / 'new'
    ensure_state_format(state, initialize=False)
    assert not state.exists()
    state.mkdir()
    ensure_state_format(state, initialize=False)
    assert list(state.iterdir()) == []
    (state / 'old').write_bytes(b'old')
    with pytest.raises(StateFormatError):
        ensure_state_format(state, initialize=False)
    assert [item.name for item in state.iterdir()] == ['old']


@pytest.mark.parametrize('entrypoint', ['worker','collector','daemon','ui'])
def test_entrypoints_reject_before_opening_storage(tmp_path, monkeypatch, entrypoint):
    from scidiscovery.artifact_agent.service.artifacts import ArtifactService
    def forbidden(*args, **kwargs):
        pytest.fail('Old state must be rejected before database assembly')
    monkeypatch.setattr(ArtifactService, 'open', forbidden)
    state = tmp_path / 'old-state'
    state.mkdir()
    (state / 'old.db').write_bytes(b'old')
    with pytest.raises(StateFormatError):
        if entrypoint == 'worker':
            from scidiscovery.artifact_agent.interfaces.mcp_local_worker import build_local_worker_router
            build_local_worker_router(state_root=state,operation_id='missing',operation_digest='missing')
        elif entrypoint == 'collector':
            from scidiscovery.artifact_agent.service.execution_collection import open_collection_executions
            open_collection_executions(state)
        elif entrypoint == 'daemon':
            from scidiscovery.artifact_agent.interfaces.mcp_daemon import main
            main(['--project-root',str(tmp_path),'--state-root',str(state), '--socket',str(tmp_path/'socket'),
                '--approval-secret-file',str(tmp_path/'key'),'--runtime-summary',str(tmp_path/'summary'),
                '--local-workspace-root',str(tmp_path/'work')])
        else:
            from scidiscovery.artifact_agent.interfaces.cli import build_parser, _run
            _run(build_parser().parse_args(['--state-root',str(state),'serve-approval-ui']))
    assert {p.name:p.read_bytes() for p in state.iterdir()} == {'old.db':b'old'}
