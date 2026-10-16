"""Source service lifecycle and archive compatibility; no candidate installation."""
import json
import os
from pathlib import Path
import sys
import time
from urllib.request import urlopen

import pytest

from scripts.probe_root_host_live import Host
from scripts import run_tests as guard


@pytest.mark.process_e2e
def test_source_dormant_daemon_ui_and_restart(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "candidate.json").write_text(json.dumps({"python": sys.executable, "project": str(project)}))
    secret = tmp_path / "approval-secret"
    secret.write_bytes(b"a" * 32)
    secret.chmod(0o600)
    Path(os.environ["SCID_TEST_LOG_DIR"]).mkdir(parents=True, exist_ok=True)
    # The existing Host lifecycle runs exactly its normal services, with source
    # metadata instead of installed distributions. No native host is launched.
    repository = Path(__file__).resolve().parents[2]
    launcher = tmp_path / "source-service.py"
    launcher.write_text("import sys; sys.path.insert(0, " + repr(str(repository / "src")) + ")\n" + r'''
from importlib.metadata import EntryPoint, EntryPoints
from scidiscovery.operations import catalog
catalog.entry_points = lambda: EntryPoints((
    EntryPoint(name="builtin", value="scidiscovery.builtin_plugin:CORE_PLUGIN", group="scidiscovery.plugins"),
    EntryPoint(name="general_science", value="scidiscovery.general_science_plugin:PLUGIN", group="scidiscovery.plugins"),
))
import runpy
module = sys.argv.pop(1)
runpy.run_module(module, run_name="__main__")
''')
    host = Host(tmp_path, json.loads(guard.DEFAULT_CONFIG.read_text())["limits"])
    launch = host.launch

    def launch_source(command, name, pipe=False):
        assert command[1] == "-m"
        return launch([sys.executable, "-I", str(launcher), *command[2:]], name, pipe)

    monkeypatch.setattr(host, "launch", launch_source)
    from scidiscovery.plugin_runtime.transport import forward_request
    request = dict(jsonrpc="2.0", id=1, method="initialize", params={},
                   _scidiscovery_scheduler_proxy="sch_" + "a" * 32)
    try:
        host.start_services()
        with urlopen(host.ui_url + "/static/style.css", timeout=5) as response:
            assert response.status == 200
        assert "result" in forward_request(tmp_path / "control.sock", json.dumps(request).encode(), timeout=5)
        assert not (tmp_path / "state/progression-logs").exists()
        daemon = host.children[-1]
        # Pass the normal service argv through the source launcher once again.
        normal_command = [sys.executable, "-m", *daemon.args[3:]]
        daemon.terminate()
        daemon.wait(timeout=10)
        host.launch(normal_command, "daemon-restarted")
        deadline = time.monotonic() + 10
        while True:
            try:
                assert "result" in forward_request(tmp_path / "control.sock", json.dumps(request).encode(), timeout=1)
                break
            except (OSError, RuntimeError):
                assert time.monotonic() < deadline
                time.sleep(.05)
        assert not (tmp_path / "state/progression-logs").exists()
    finally:
        host.close()


def test_source_archive_restore_retains_checkpoint_without_waking_runtime(source_catalog, tmp_path):
    source_catalog()
    import json
    from scidiscovery.artifact_agent.runtime import open_runtime
    from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
    root=tmp_path;project=root/'project';project.mkdir()
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
            with bindings._connect() as db:
                db.execute('UPDATE scheduler_progression SET checkpoint_json=? WHERE instance_id=?',
                    (json.dumps({'budget':{'tasks':2}, 'usage_summary':{'coverage':'fixture'},
                        'report':{'summary':'insufficient evidence'}}),identity))
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
