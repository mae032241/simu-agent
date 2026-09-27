import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT = Path(__file__).resolve().parents[2]
DEPLOY = PROJECT / "plugins/tcad_artifact/deploy"
SOURCE = PROJECT / "plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py"


def setup(tmp_path, *, incomplete=False):
    spec = importlib.util.spec_from_file_location("remote_deployment_test", DEPLOY / "remote_deployment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "remote"
    runner, config = root / "bin/scidiscovery-tcad-ssh-runner", root / "config/runner.json"
    runner.parent.mkdir(parents=True)
    config.parent.mkdir()
    runner.write_bytes(b"old runner bytes\n")
    runner.chmod(0o750)
    values = json.loads((PROJECT / "plugins/tcad_artifact/config/remote-runner.example.json").read_bytes())
    values.update(exchange_root=str(root / "exchange"), state_root=str(root / "state"),
        result_root=str(root / "state/runs"), tools=[dict(profile_id="fixture",solver_kind="deterministic_tool",
        executable=sys.executable, arguments=[],environment={},release_evidence="fixture only")])
    if incomplete:
        del values["debug"]
    config.write_text(json.dumps(values))
    config.chmod(0o640)
    request = dict(phase="prepare", transaction="a"*32, runner=str(runner),config=str(config),
        source=base64.b64encode(SOURCE.read_bytes()).decode(), configuration=None)
    return module, request, runner, config


def test_remote_upgrade_and_outer_failure_restore_exact_files(tmp_path):
    module, request, runner, config = setup(tmp_path)
    before = (runner.read_bytes(), config.read_bytes())
    assert module.deploy(request)["state"] == "prepared"
    assert (runner.read_bytes(), config.read_bytes()) == before
    assert module.deploy(dict(request,phase="activate"))["policy_available"] is True
    assert runner.read_bytes() == SOURCE.read_bytes() and config.read_bytes() == before[1]
    assert module.deploy(dict(request,phase="finish"))["state"] == "complete"
    assert module.deploy(dict(request,phase="rollback"))["state"] == "rolled_back"
    assert (runner.read_bytes(), config.read_bytes()) == before
    assert config.stat().st_mode & 0o777 == 0o640


def test_incompatible_remote_policy_never_replaces_working_files(tmp_path):
    module, request, runner, config = setup(tmp_path, incomplete=True)
    before = (runner.read_bytes(), config.read_bytes())
    with pytest.raises(RuntimeError, match="validation failed"):
        module.deploy(request)
    assert (runner.read_bytes(), config.read_bytes()) == before
    assert module.deploy(dict(request,phase="rollback"))["state"] == "not_activated"


def test_active_job_prevents_remote_replacement(tmp_path):
    module, request, runner, config = setup(tmp_path)
    job = runner.parent.parent / "state/runs/job"
    job.mkdir(parents=True)
    (job / "submitted_at").touch()
    with pytest.raises(RuntimeError, match="still be active"):
        module.deploy(request)
    assert runner.read_bytes() == b"old runner bytes\n"


def test_administrator_change_between_phases_is_not_overwritten(tmp_path):
    module, request, runner, config = setup(tmp_path)
    module.deploy(request)
    runner.write_bytes(b"newer administrator version")
    with pytest.raises(RuntimeError, match="changed after preparation"):
        module.deploy(dict(request,phase="activate"))
    module.deploy(dict(request,phase="rollback"))
    assert runner.read_bytes() == b"newer administrator version"


def test_explicit_configuration_is_validated_and_rolled_back(tmp_path):
    module, request, runner, config = setup(tmp_path)
    before=config.read_bytes()
    replacement=json.loads(before)
    replacement["debug"]["initialization"]["wall_time_seconds"]=30
    request["configuration"]=base64.b64encode(json.dumps(replacement).encode()).decode()
    module.deploy(request)
    module.deploy(dict(request,phase="activate"))
    assert json.loads(config.read_bytes())["debug"]["initialization"]["wall_time_seconds"]==30
    module.deploy(dict(request,phase="rollback"))
    assert config.read_bytes()==before


def test_partial_activation_restores_both_targets(tmp_path, monkeypatch):
    module, request, runner, config = setup(tmp_path)
    before = (runner.read_bytes(), config.read_bytes())
    replacement = json.loads(before[1])
    replacement["debug"]["initialization"]["wall_time_seconds"] = 30
    request["configuration"] = base64.b64encode(json.dumps(replacement).encode()).decode()
    module.deploy(request)
    write = module.write
    def fail_runner(path, raw, mode=0o600):
        if path == runner:
            raise OSError("injected replacement failure")
        return write(path, raw, mode)
    monkeypatch.setattr(module, "write", fail_runner)
    with pytest.raises(OSError):
        module.deploy(dict(request, phase="activate"))
    assert config.read_bytes() != before[1] and runner.read_bytes() == before[0]
    monkeypatch.setattr(module, "write", write)
    module.deploy(dict(request, phase="rollback"))
    assert (runner.read_bytes(), config.read_bytes()) == before


def test_finish_cannot_accept_a_different_deployed_version(tmp_path):
    module, request, runner, config = setup(tmp_path)
    module.deploy(request)
    module.deploy(dict(request, phase="activate"))
    runner.write_bytes(runner.read_bytes() + b"\n# subsequent change\n")
    with pytest.raises(RuntimeError, match="differs"):
        module.deploy(dict(request, phase="finish"))


def test_remote_runtime_cli_composes_transport_and_transaction(tmp_path):
    _, _, runner, config = setup(tmp_path)
    ssh = tmp_path / "ssh"
    ssh.write_text('#!' + sys.executable + '\nimport os,shlex,sys\n'
        'command=shlex.split(sys.argv[-1])\nos.execv(sys.executable,[sys.executable,*command[1:]])\n')
    ssh.chmod(0o750)
    transport=tmp_path / "transport.json"
    transport.write_text(json.dumps(dict(ssh_executable=str(ssh),destination="fixture@local",
        remote_helper=str(runner),remote_config=str(config),remote_exchange_root=str(runner.parent.parent/'exchange'),
        max_transfer_bytes=2000000000)))
    command=tmp_path / "command.json"
    command.write_text(json.dumps(dict(executable="/usr/local/bin/scidiscovery-tcad-transport",
        arguments=["--config",str(transport)])))
    transaction=tmp_path/'transaction';transaction.mkdir()
    for phase in ('prepare','activate','finish'):
        completed=subprocess.run([sys.executable,str(DEPLOY/'remote_runtime.py'),phase,
            '--command-config',str(command),'--transaction-root',str(transaction)],
            capture_output=True,text=True,timeout=20,
            env={**os.environ,'PYTHONPATH':os.pathsep.join([str(PROJECT/'src'),str(PROJECT/'plugins/tcad_artifact')])})
        assert completed.returncode==0,completed.stderr
    receipt=json.loads((transaction/'remote-tcad.json').read_bytes())
    assert receipt['state']=='complete' and receipt['policy_available'] is True
    assert runner.read_bytes()==SOURCE.read_bytes()


@pytest.mark.parametrize('fail_phase',['prepare','activate',None])
def test_main_installer_never_starts_local_services_after_remote_failure(tmp_path,fail_phase):
    log=tmp_path/'phases'
    script=r'''
source "$1"
TCAD_ENABLED=1
for fn in require_root validate_source validate_base_python validate_figure_dependencies install_packages \
 begin_install_transaction retire_old_deployment retire_inactive_tcad_surfaces activate_packages \
 create_local_workspace_root create_instance_archive_root normalize_database_ownership ensure_secret \
 ensure_agent_settings configure_tcad_runtime install_units configure_platform verify_installation; do
 eval "$fn() { :; }"
done
install() { :; }
remote_tcad_runtime() { printf '%s\n' "$1" >> "$PHASE_LOG"; [[ "$1" != "$FAIL_PHASE" ]]; }
systemctl() { printf 'local_service_action\n' >> "$PHASE_LOG"; }
complete_install_transaction() { remote_tcad_runtime finish; }
install_all
'''
    completed=subprocess.run(['bash','-c',script,'bash',str(PROJECT/'deploy/install.sh')],
        capture_output=True,text=True,timeout=10,env={**os.environ,'SCID_WORKSPACE':str(tmp_path),
            'SCID_TCAD_COMMAND_CONFIG':str(tmp_path/'command.json'),'PHASE_LOG':str(log),'FAIL_PHASE':fail_phase or ''})
    phases=log.read_text().splitlines()
    assert (completed.returncode==0)==(fail_phase is None),completed.stderr
    if fail_phase:
        assert 'local_service_action' not in phases and 'finish' not in phases
    else:
        assert phases.index('prepare')<phases.index('activate')<phases.index('local_service_action')<phases.index('finish')
