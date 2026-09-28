"""One retained installed core candidate and the shipped daemon/UI, without models."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts.probe_root_host_live import Host, prepare
from scripts import run_tests as guard


@pytest.mark.installed
def test_retained_core_candidate_dormant_daemon_and_ui(tmp_path):
    # Explicit path keeps the exact tested wheel available for the native journey.
    root = Path(os.environ.get('SCID_B6_CANDIDATE', str(tmp_path / 'candidate')))
    if not (root / 'candidate.json').exists():
        root.mkdir(parents=True, exist_ok=False)
        prepare(root)
    config = json.loads((root / 'candidate.json').read_text())
    result = subprocess.run([config['python'], '-I', '-c',
        "import scidiscovery,sys;from pathlib import Path;"
        "assert Path(scidiscovery.__file__).resolve().is_relative_to(Path(sys.prefix).resolve());"
        "from scidiscovery.artifact_agent.service.runs import RunService;"
        "assert callable(RunService.admission_matches);assert callable(RunService.native_identities)"],
        cwd=config['project'], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    Path(os.environ['SCID_TEST_LOG_DIR']).mkdir(parents=True, exist_ok=True)
    host = Host(root, json.loads(guard.DEFAULT_CONFIG.read_text())['limits'])
    try:
        host.start_services()
        from urllib.request import urlopen
        with urlopen(host.ui_url + '/static/style.css', timeout=5) as response:
            assert response.status == 200
        from scidiscovery.plugin_runtime.transport import forward_request
        request = dict(jsonrpc='2.0', id=1, method='initialize', params={},
            _scidiscovery_scheduler_proxy='sch_' + 'a' * 32)
        assert 'result' in forward_request(root / 'control.sock', json.dumps(request).encode(), timeout=5)
        assert not (root / 'state/progression-logs').exists()
        # Restart exactly the installed service against its original state.
        daemon = host.children[-1]
        daemon.terminate()
        daemon.wait(timeout=10)
        host.launch(daemon.args, 'daemon-restarted')
        import time
        deadline = time.monotonic() + 10
        while True:
            try:
                assert 'result' in forward_request(root / 'control.sock', json.dumps(request).encode(), timeout=1)
                break
            except (OSError, RuntimeError):
                assert time.monotonic() < deadline
                time.sleep(.05)
        assert not (root / 'state/progression-logs').exists()
    finally:
        host.close()
    from scripts.installed_candidates import _run_logged
    _run_logged([config['python'], '-I', '-c', r'''
import json,tempfile
from pathlib import Path
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);project=root/'project';project.mkdir()
    runtime=open_runtime(project_root=project,state_root=root/'state',worker_backend='local',
        approval_receipt_secret=b'a'*32)
    bindings=runtime.scheduler_bindings
    archive=InstanceArchive(runtime)  # Unmodified production writer/maintenance guards.
    for with_progression in (False,True):
        instance=bindings.create_instance_and_bind_session(session_key='reader',
            name='with-control' if with_progression else 'legacy-shape',title='Fixture',objective='Original intent')
        identity=instance.instance_id
        if with_progression:
            bindings.progression_command(instance_id=identity,session_key='reader',command='start')
            row=bindings.progression_status(instance_id=identity,internal=True)
            # Synthetic accounting fixtures are not measured model usage.
            bindings.checkpoint_progression(instance_id=identity,session_key='reader',
                expected_generation=row['generation'],checkpoint={'budget':{'tasks':2},
                    'usage_summary':{'coverage':'fixture'},'report':{'summary':'insufficient evidence'}})
            bindings.progression_command(instance_id=identity,session_key='reader',command='pause')
            before=json.loads(bindings.progression_status(instance_id=identity,internal=True)['checkpoint_json'])
        preview=archive.preview(identity)
        assert preview['ready'],preview
        assert archive.archive(identity,preview['fingerprint'])['storage_state']=='archived'
        preview=archive.restore_preview(identity)
        assert preview['ready'],preview
        archive.restore(identity,preview['fingerprint'])
        assert bindings.session_instance(session_key='reader') is None
        if with_progression:
            row=bindings.progression_status(instance_id=identity,internal=True)
            assert row['state']=='paused' and row['host_json'] is None and row['owner_session'] is None
            after=json.loads(row['checkpoint_json'])
            for key in ('budget','usage_summary','report'):assert after[key]==before[key]
        else:assert bindings.progression_status(instance_id=identity)['state']=='idle'
'''], cwd=Path(config['project']), env=dict(os.environ), timeout=60)
