"""Regression boundaries for observation, resumable collection and diagnostics."""
import hashlib
import subprocess
import pytest
from types import SimpleNamespace

from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.interfaces.mcp import rpc_error
from scidiscovery.artifact_agent.service.local_process_observation import read_summary
from tcad_artifact.ssh_transport import SSHTCADTransport


def test_terminal_sync_never_calls_collect(tmp_path):
    current = SimpleNamespace(state="succeeded", external_run_id="run", executor="fixture")
    saved = {}
    executions = SimpleNamespace(status=lambda _: current, exchange_root=tmp_path,
        save_observation=lambda _, value: saved.update(value), observation=lambda _: dict(saved))
    def forbidden(*args, **kwargs):
        raise AssertionError("observation entered artifact collection")
    adapter = SimpleNamespace(lookup_submission=lambda _: None, collect=forbidden,
        status_details=lambda _: {"state": "succeeded", "progress": {"elapsed_seconds": 12}})
    bridge = ExecutionBridge(executions, adapters={"fixture": adapter})
    assert bridge.sync(execution_id="execution")["elapsed_seconds"] == 12
    assert saved["progress"]["elapsed_seconds"] == 12


def test_completed_download_is_reused(tmp_path, monkeypatch):
    raw = b"solver data\n"
    calls = []
    remote = SimpleNamespace(get=lambda path: calls.append(path) or raw)
    transport = SSHTCADTransport(remote, local_result_root=tmp_path)
    monkeypatch.setattr(transport, "_rpc", lambda *args: {"outputs": [{
        "name": "profile", "local_path": "/remote/profile.dat", "media_type": "text/plain",
        "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}]})
    first = transport._collect("run_" + "a" * 32)
    assert transport._collect("run_" + "a" * 32) == first
    assert calls == ["/remote/profile.dat"]


def test_empty_subprocess_timeout_preserves_actionable_cause():
    error = subprocess.TimeoutExpired(["hidden-command"], 30, output=b"", stderr=b"")
    response = rpc_error(1, error)
    text = str(response)
    assert "TimeoutExpired" in text and "30" in text
    assert "hidden-command" not in text


def test_engineering_record_is_scoped_and_public_message_is_redacted(tmp_path):
    import pytest
    from scidiscovery.artifact_agent.service.engineering_diagnostics import EngineeringDiagnostics
    store = EngineeringDiagnostics(tmp_path)
    try:
        raise subprocess.TimeoutExpired(["secret-command"], 30)
    except subprocess.TimeoutExpired as cause:
        try:
            raise RuntimeError("download failed; credential=do-not-expose /private/runtime/log") from cause
        except RuntimeError as error:
            facts = store.capture(error, scope="instance:one", layer="transport", action="collect")
            response = rpc_error(1, error)
    assert "TimeoutExpired" in str(response) and "30" in str(response)
    assert "do-not-expose" not in str(response) and "/private/runtime" not in str(response)
    public = store.read(facts["reference"], scopes=("instance:one",))
    assert "secret-command" not in public["text"]
    with pytest.raises(ValueError, match="another instance"):
        store.read(facts["reference"], scopes=("instance:two",))
    with pytest.raises(ValueError, match="reference"):
        store.read("../other", scopes=("instance:one",))


def test_diagnostic_write_failure_preserves_original_error(tmp_path):
    from scidiscovery.artifact_agent.service.engineering_diagnostics import EngineeringDiagnostics
    root = tmp_path / "not-a-directory"
    root.write_text("file")
    value = EngineeringDiagnostics(root).capture(TimeoutError("socket wait"), scope="one", layer="transport", action="read")
    assert value["causes"][0]["type"] == "TimeoutError"
    assert value["recording_error"]["causes"][0]["type"] == "FileExistsError"
    assert "reference" not in value


def test_observation_missing_and_corrupt_are_distinct(tmp_path):
    missing = read_summary(tmp_path)
    directory = tmp_path / "scratch/.analysis-process"
    directory.mkdir(parents=True)
    (directory / "latest.json").write_text("invalid json")
    invalid = read_summary(tmp_path)
    assert missing["coverage"] == invalid["coverage"] == "unobserved"
    assert missing["reason"] != invalid["reason"]


def _until(predicate, *, seconds=5):
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError("bounded process condition was not observed")


def test_collection_process_reaps_legacy_hang_and_releases_slot(tmp_path, monkeypatch):
    import os
    import sys
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(sys.path))
    executions = SimpleNamespace(database_path=tmp_path / "database/executions.sqlite3",
        exchange_root=tmp_path / "exchange", service_actor=ActorRef(actor_id="test", actor_type="service"),
        status=lambda name: SimpleNamespace(state="succeeded"))
    coordinator = ExecutionCollection(executions, plugin_configs={}, child_command=[sys.executable, "-c",
        "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"])
    try:
        first = coordinator.collect("first", scope="one", total_seconds=.6)
        assert first["accepted"]
        process = coordinator._active[1]
        duplicate = coordinator.collect("first", scope="one", total_seconds=30)
        assert not duplicate["accepted"] and duplicate["total_seconds"] == .6
        assert coordinator.collect("second", scope="one")["state"] == "busy"
        assert not (tmp_path / "exchange/second/collection/status.json").exists()
        _until(lambda: coordinator._active is None)
        assert process.poll() is not None
        assert coordinator.summary("first")["state"] == "timed_out"
        assert coordinator.collect("second", scope="one", total_seconds=.6)["accepted"]
    finally:
        coordinator.close()
        _until(lambda: coordinator._active is None)


def test_collection_supervisor_start_failure_reaps_child_before_unlock(tmp_path, monkeypatch):
    import os
    import sys
    import threading
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(sys.path))
    executions = SimpleNamespace(database_path=tmp_path / "database/executions.sqlite3",
        exchange_root=tmp_path / "exchange", service_actor=ActorRef(actor_id="test", actor_type="service"),
        status=lambda name: SimpleNamespace(state="succeeded"))
    coordinator = ExecutionCollection(executions, plugin_configs={}, child_command=[sys.executable, "-c", "import time; time.sleep(30)"])
    processes = []
    start_process = subprocess.Popen
    def capture(*args, **kwargs):
        process = start_process(*args, **kwargs)
        processes.append(process)
        return process
    def fail_start(_):
        raise RuntimeError("cannot start collection supervisor")
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "Popen", capture)
        patch.setattr(threading.Thread, "start", fail_start)
        with pytest.raises(RuntimeError, match="supervisor"):
            coordinator.collect("first", scope="one")
    assert len(processes) == 1 and processes[0].poll() is not None
    assert coordinator._active is None
    assert coordinator.collect("second", scope="one", total_seconds=.5)["accepted"]
    assert coordinator.close()
    assert (tmp_path / "exchange/second/collection/process.stderr.log").is_file()


def test_completed_manifest_checkpoint_registers_in_real_child(tmp_path, monkeypatch):
    import os
    import sys
    from scidiscovery.artifact_agent.schema.execution import LocalFileDescriptor
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    from scidiscovery.artifact_agent.service.engineering_diagnostics import atomic_json
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
    runtime, _, adapter, _, root, _ = _setup(tmp_path)
    _create_effect(root, name="collected")
    _decide_execution_approval(runtime, root, name="collected")
    root.call_tool("execution_start", {"name": "collected"})
    execution_id = root.facade._resolve("execution", "collected")
    current = runtime.executions.status(execution_id)
    runtime.executions.record_status(execution_id=execution_id, external_run_id=current.external_run_id, state="succeeded")
    output = tmp_path / "original.dat"
    output.write_bytes(b"solver output\n")
    descriptor = LocalFileDescriptor(name="profile", local_path=str(output), media_type="text/plain",
        size_bytes=output.stat().st_size, sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    coordinator = ExecutionCollection(runtime.executions, plugin_configs={})
    root.facade.execution_collection = coordinator
    directory = coordinator.directory(execution_id)
    atomic_json(directory / "outputs.json", {"outputs": [descriptor.model_dump(mode="json")],
        "collected_at": "2026-09-13T00:00:00Z"})
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(sys.path))
    try:
        reply = root.call_tool("execution_collect", {"name": "collected", "total_seconds": 10})
        assert reply["collection"]["accepted"]
        _until(lambda: coordinator._active is None)
        assert coordinator.summary(execution_id)["state"] == "completed", coordinator.summary(execution_id)
        status = root.call_tool("execution_status", {"name": "collected"})
        assert status["state"] == "collected"
        assert status["result_artifact_name"] is None  # status remains a pure read
        outputs = root.call_tool("execution_outputs", {"name": "collected"})
        assert outputs["outputs"][0]["output_label"] == "profile"
        assert root.call_tool("execution_status", {"name": "collected"})["result_artifact_name"]
        assert root.call_tool("execution_collect", {"name": "collected"})["collection"]["state"] == "completed"
        assert adapter.submit_count == 1
    finally:
        coordinator.close()


def test_transport_differentiates_no_progress_and_total_deadline():
    import sys
    import pytest
    from scidiscovery.artifact_agent.service.execution_collection import run_bounded
    for idle, expected in ((.05, "transfer_no_progress"), (None, "operation_total")):
        with pytest.raises(subprocess.TimeoutExpired) as caught:
            run_bounded([sys.executable, "-c", "import time; time.sleep(30)"],
                input=b"", timeout=.15, idle_seconds=idle)
        assert caught.value.timeout_kind == expected


def test_common_launcher_preserves_environment_and_full_stdout(tmp_path, monkeypatch):
    import os
    import sys
    from scidiscovery.artifact_agent.service.local_process_observation import materialize_launcher
    materialize_launcher(tmp_path)
    import json
    from datetime import datetime, timedelta, timezone
    (tmp_path/'assignment.json').write_text(json.dumps({'budget':{'deadline_at':
        (datetime.now(timezone.utc)+timedelta(seconds=10)).isoformat()}}))
    monkeypatch.setenv("OMP_NUM_THREADS", "3")
    result = subprocess.run([sys.executable, str(tmp_path / "tools/local_process_observation.py"),
        "--timeout", "4", "--command", sys.executable, "-c",
        "import os; print(os.environ['OMP_NUM_THREADS']); print('x'*140000)"], capture_output=True, timeout=6)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(b"3\n") and len(result.stdout) > 140000
    assert read_summary(tmp_path)["coverage"] == "local_launcher"


def test_partial_manifest_resumes_43_files_without_cross_execution_cache(tmp_path, monkeypatch):
    import pytest
    from scidiscovery.artifact_agent.service.execution_collection import CollectionContext
    outputs = [{"name": f"profile_{i}", "local_path": f"/remote/p{i}", "media_type": "text/plain",
        "size_bytes": 4, "sha256": hashlib.sha256(b"data").hexdigest()} for i in range(43)]
    calls = []
    def get(path):
        calls.append(path)
        if len(calls) == 18:
            raise TimeoutError("transfer stopped at file 18")
        return b"data"
    transport = SSHTCADTransport(SimpleNamespace(get=get), local_result_root=tmp_path)
    monkeypatch.setattr(transport, "_rpc", lambda *args: {"outputs": outputs})
    run = "run_" + "a" * 32
    with pytest.raises(TimeoutError):
        transport._collect(run, context=CollectionContext.for_seconds(10))
    result = transport._collect(run, context=CollectionContext.for_seconds(10))
    assert len(result['outputs']) == 43 and len(calls) == 44
    # Same-sized corrupted file must be fetched again; the other 42 are reused.
    from pathlib import Path
    Path(result['outputs'][0]['local_path']).write_bytes(b"oops")
    transport._collect(run, context=CollectionContext.for_seconds(10))
    assert len(calls) == 45
    transport._collect("run_" + "b" * 32, context=CollectionContext.for_seconds(10))
    assert len(calls) == 88


def test_proxy_daemon_status_stays_available_during_collection(tmp_path, monkeypatch):
    import json
    import multiprocessing
    import os
    import signal
    import sys
    import time
    from scidiscovery.interfaces.daemon import UnixSocketDaemon
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_daemon import RootBrokerRouter
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
    runtime, _, adapter, _, root, _ = _setup(tmp_path)
    _create_effect(root, name="slow")
    _decide_execution_approval(runtime, root, name="slow")
    root.call_tool("execution_start", {"name": "slow"})
    execution_id = root.facade._resolve("execution", "slow")
    current = runtime.executions.status(execution_id)
    runtime.executions.record_status(execution_id=execution_id, external_run_id=current.external_run_id, state="succeeded")
    socket = tmp_path / "root.sock"
    # Fixture setup has no open DB connection; the child constructs its own coordinator.
    def serve():
        collector = ExecutionCollection(runtime.executions, plugin_configs={}, child_command=[sys.executable,
            "-c", "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"])
        root.facade.execution_collection = collector
        def stop(*_):
            collector.close()
            os._exit(0)
        signal.signal(signal.SIGTERM, stop)
        UnixSocketDaemon(socket, RootBrokerRouter(lambda _: MCPRouter(root, name="fixture"))).serve_forever()
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(sys.path))
    process = multiprocessing.get_context("fork").Process(target=serve)
    process.start()
    def call(name, arguments):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
        reply = subprocess.run([sys.executable, "-m", "scidiscovery.artifact_agent.interfaces.mcp_proxy",
            "--socket", str(socket), "--timeout", "1"], input=json.dumps(request).encode()+b"\n",
            capture_output=True, timeout=3)
        assert reply.returncode == 0, reply.stderr
        return json.loads(reply.stdout)
    try:
        _until(socket.exists)
        start = time.monotonic()
        accepted = call("execution_collect", {"name": "slow", "total_seconds": 5})
        assert "error" not in accepted, accepted
        status = call("execution_status", {"name": "slow"})
        assert "error" not in status and "running" in str(status), status
        sync = call("execution_sync", {"name": "slow"})
        assert "error" not in sync, sync
        assert time.monotonic() - start < 3
        rejected = call("execution_outputs", {"name": "slow"})
        assert 'error' in rejected and 'engineering' in rejected['error']['data']
        reference = rejected['error']['data']['engineering']['reference']
        assert 'error' not in call("diagnostic_read", {"reference": reference})
    finally:
        process.terminate()
        process.join(3)
        if process.is_alive():
            process.kill(); process.join()
            raise AssertionError("daemon failed to stop its collector within its reserve")
    assert adapter.submit_count == 1
    # A fresh coordinator reads the stopped attempt without restarting it.
    reader = ExecutionCollection(runtime.executions, plugin_configs={})
    assert reader.summary(execution_id)['state'] == 'interrupted'


def test_worker_error_reference_and_tool_time_survive_router_reopen(tmp_path, monkeypatch):
    from tests.operations.test_l4_local_tcad import _budget_case
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    import pytest
    worker, adapter, _ = _budget_case(tmp_path)
    def fail(_):
        raise TimeoutError("test debug collection timed out")
    monkeypatch.setattr(adapter, "collect", fail)
    with pytest.raises(WorkerToolError) as caught:
        worker.call_tool("worker_tcad_debug_run", {"run_name": "failure", "mode": "preflight"})
    value = worker.runs.status(worker._run_id)
    summary = worker.runs.diagnostic_summary(value)
    assert summary['latest_tool_error']['engineering']['reference'] == caught.value.engineering['reference']
    assert any(cause['type'] == 'TimeoutError' for cause in summary['latest_tool_error']['engineering']['causes'])
    times = worker.runs.tool_timing(value.run_id)
    assert any(item['tool_name'] == 'worker_tcad_debug_run' and item['duration_seconds'] >= 0 for item in times)


@pytest.mark.parametrize('delay,legacy', [(0.01,False), (10,False), (10,True)])
def test_author_service_collection_uses_run_budget_in_real_process(tmp_path, monkeypatch, delay, legacy):
    import json
    import os
    import sys
    import time
    from dataclasses import replace
    from pathlib import Path
    from scidiscovery.operations.runtime_plugins import RuntimePluginContext
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    from tests.operations.test_l4_local_tcad import _budget_case
    from tests.operations.test_log_preservation import _descriptor
    worker, adapter, _ = _budget_case(tmp_path)
    root = tmp_path / 'runtime'
    result_root = root / 'executor-results'
    result_root.mkdir(parents=True)
    (result_root / 'log').write_text('bounded syntax check complete\n')
    (result_root / 'manifest').write_text(json.dumps({'terminal_state':'succeeded','exit_code':0,'outputs':[]}))
    outputs = [_descriptor('tcad_log', result_root/'log', 'text/plain').model_dump(mode='json'),
        _descriptor('tcad_manifest', result_root/'manifest', 'application/json').model_dump(mode='json')]
    packet = tmp_path / 'outputs.json'
    packet.write_text(json.dumps(outputs))
    script = tmp_path / 'transport.py'
    script.write_text('import json,time,sys,os\nfrom pathlib import Path\nr=json.load(sys.stdin)\nassert r["operation"] == "collect"\n'
        f'Path({str(tmp_path / "transport.pid")!r}).write_text(str(os.getpid()))\n'
        f'time.sleep({delay!r})\n' +
        'print(json.dumps({"schema_version":1,"operation":"collect","ok":True,"payload":{"outputs":json.load(open(sys.argv[1]))}}))\n')
    config = tmp_path / 'command.json'
    config.write_text(json.dumps({'executable':sys.executable,'arguments':[str(script),str(packet)],
        'operation_timeout_seconds':30}))
    config.chmod(0o600)
    service = worker.tool_services['tcad_artifact:tcad.development_debug']
    service.runtime_context = RuntimePluginContext(plugin_id='tcad_artifact',mode='local_worker',
        config_path=tmp_path/'runtime.json',config_bytes=json.dumps({'transport':'command',
            'command_config_path':str(config)}).encode(),state_root=root)
    original = worker._context
    monkeypatch.setattr(worker, '_context', lambda *args: replace(original(*args), remaining_seconds=2))
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(sys.path))
    if legacy:
        from tcad_artifact import debug_collection
        bounded = debug_collection.run_bounded
        def run_legacy(command, **kwargs):
            code = 'from tcad_artifact.command_adapter import CommandTCADExecutorAdapter; del CommandTCADExecutorAdapter.collect_with_budget; from tcad_artifact.debug_collection import main; raise SystemExit(main())'
            return bounded([sys.executable, '-c', code], **kwargs)
        monkeypatch.setattr(debug_collection, 'run_bounded', run_legacy)
    start = time.monotonic()
    if delay < 1:
        response = worker.call_tool('worker_tcad_debug_run', {'run_name':'bounded','mode':'preflight'})
        assert response['phase'] == 'collected', response
    else:
        with pytest.raises(WorkerToolError) as caught:
            worker.call_tool('worker_tcad_debug_run', {'run_name':'bounded','mode':'preflight'})
        assert caught.value.engineering['category'] == 'timeout'
        assert time.monotonic() - start < 3
        import psutil
        pid = int((tmp_path/'transport.pid').read_text())
        def stopped():
            return not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
        _until(stopped)
    assert adapter.submissions == 1


@pytest.mark.parametrize('stage', ['output', 'manifest', 'committed'])
def test_ingestion_process_exit_preserves_idempotent_registration(tmp_path, monkeypatch, stage):
    import os
    import sys
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    from scidiscovery.artifact_agent.service.engineering_diagnostics import atomic_json
    from tests.operations.test_r4_execution_approval_identity import _setup, _create_effect, _decide_execution_approval
    from tests.operations.test_log_preservation import _descriptor
    runtime, _, adapter, _, root, _ = _setup(tmp_path)
    _create_effect(root, name='interrupted')
    _decide_execution_approval(runtime, root, name='interrupted')
    root.call_tool('execution_start', {'name':'interrupted'})
    execution_id = root.facade._resolve('execution','interrupted')
    value = runtime.executions.status(execution_id)
    runtime.executions.record_status(execution_id=execution_id,external_run_id=value.external_run_id,state='succeeded')
    output = tmp_path / 'data'
    output.write_bytes(b'raw solver output')
    script = tmp_path / 'crash.py'
    script.write_text('import os,sys\nfrom pathlib import Path\n'
        'from scidiscovery.artifact_agent.service.artifacts import ArtifactService\n'
        'from scidiscovery.artifact_agent.service.executions import ExecutionService\n'
        'from scidiscovery.artifact_agent.service.execution_collection import _child\n'
        f'stage={stage!r}\n' +
        'original=ArtifactService.register\n'
        'def register(self, content, registration, **kwargs):\n'
        ' result=original(self,content,registration,**kwargs)\n'
        ' if (stage=="output" and registration.kind=="execution_output") or (stage=="manifest" and registration.kind=="execution_result"): os._exit(71)\n'
        ' return result\n'
        'ArtifactService.register=register\n'
        'ingest=ExecutionService.ingest_result\n'
        'def finish(self, **kwargs):\n'
        ' result=ingest(self,**kwargs)\n'
        ' if stage=="committed": os._exit(72)\n'
        ' return result\n'
        'ExecutionService.ingest_result=finish\n'
        'raise SystemExit(_child(Path(sys.argv[1])))\n')
    collector = ExecutionCollection(runtime.executions,plugin_configs={},child_command=[sys.executable,str(script)])
    root.facade.execution_collection = collector
    frozen = {'outputs':[_descriptor('profile',output,'text/plain').model_dump(mode='json')],
        'collected_at':'2026-09-13T00:00:00Z'}
    atomic_json(collector.directory(execution_id)/'outputs.json', frozen)
    monkeypatch.setenv('PYTHONPATH',os.pathsep.join(sys.path))
    try:
        collector.collect(execution_id,scope='instance:'+value.instance_id if hasattr(value,'instance_id') else 'fixture',total_seconds=10)
        _until(lambda: collector._active is None)
        assert collector.summary(execution_id)['state'] == ('completed' if stage=='committed' else 'failed')
        collector.child_command = [sys.executable,'-m','scidiscovery.artifact_agent.service.execution_collection']
        collector.collect(execution_id,scope='fixture',total_seconds=10)
        _until(lambda: collector._active is None)
        assert runtime.executions.status(execution_id).state == 'collected', collector.summary(execution_id)
        result = runtime.executions.status(execution_id).result_ref
        import json
        assert json.loads(runtime.artifacts.read(result))['collected_at'] == frozen['collected_at']
        assert adapter.submit_count == 1
    finally:
        collector.close()


@pytest.mark.parametrize('native_ssh', [False, True])
def test_parent_death_stops_collector_before_restart_releases_lock(tmp_path, monkeypatch, native_ssh):
    import os
    import sys
    from pathlib import Path
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    leaf_code = ('import os,time; from pathlib import Path; '
        f'Path({str(tmp_path/"transport.ready")!r}).write_text(str(os.getpid())+" "+str(os.getpgrp())); '
        f'time.sleep(2); Path({str(tmp_path/"late-write")!r}).write_text("escaped"); time.sleep(30)')
    transport_code = ('import sys; from tcad_artifact.ssh_transport import SSHRemoteClient,SSHTCADTransportConfig; '
        f'c=SSHTCADTransportConfig(ssh_executable=sys.executable,destination="user@fixture",destination_resolver=(sys.executable,"-c",{leaf_code!r}),'
        'remote_helper="/helper",remote_config="/config",remote_exchange_root="/exchange"); SSHRemoteClient(c)._destination()')
    child_code = ('import json,sys,threading,time,os; from pathlib import Path; '
        'from scidiscovery.artifact_agent.service.execution_collection import watch_parent,CollectionContext; '
        'from tcad_artifact.command_adapter import CommandTCADExecutorAdapter,CommandAdapterConfig; '
        'p=Path(sys.argv[1]); r=json.loads(p.read_text()); watch_parent(r["parent_fd"],threading.Event()); '
        '(p.parent/"ready").write_text(str(os.getpid())); '
        f'a=CommandTCADExecutorAdapter(CommandAdapterConfig(executable=sys.executable,arguments=("-c",{transport_code!r}),environment={{"PYTHONPATH":os.environ["PYTHONPATH"]}}),local_result_root=p.parent); '
        'a.collect_with_budget("original",context=CollectionContext(**r["budget"]))')
    if native_ssh:
        import shutil
        ssh = shutil.which('ssh')
        if not ssh:
            pytest.skip('native OpenSSH is unavailable')
        # ProxyCommand only runs local sleep: no remote host or SSH connection.
        child_code = ('import os,sys,subprocess,signal,time; from pathlib import Path; '
            'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
            '(Path(sys.argv[1]).parent/"ready").write_text(str(os.getpid())); '
            f'p=subprocess.Popen([{ssh!r},"-F","/dev/null","-o","ProxyCommand=/usr/bin/sleep 30","user@unused"]); '
            f'Path({str(tmp_path/"transport.ready")!r}).write_text(str(p.pid)+" "+str(os.getpgrp())); '
            'p.wait()')
    supervisor = tmp_path / 'supervisor.py'
    supervisor.write_text('import sys,time\nfrom pathlib import Path\nfrom types import SimpleNamespace\n'
        'from scidiscovery.artifact_agent.schema.refs import ActorRef\n'
        'from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection\n'
        'p=Path(sys.argv[1])\n'
        's=SimpleNamespace(database_path=p/"database/executions.sqlite3",exchange_root=p/"exchange",'
        'service_actor=ActorRef(actor_id="fixture",actor_type="service"),status=lambda _:SimpleNamespace(state="succeeded"))\n'
        f'c=ExecutionCollection(s,plugin_configs={{}},child_command=[sys.executable,"-c",{child_code!r}])\n'
        'c.collect("original",scope="fixture",total_seconds=20)\ntime.sleep(30)\n')
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(sys.path))
    process = subprocess.Popen([sys.executable,str(supervisor),str(tmp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    executions = SimpleNamespace(database_path=tmp_path/'database/executions.sqlite3',exchange_root=tmp_path/'exchange',
        service_actor=ActorRef(actor_id='fixture',actor_type='service'),status=lambda _:SimpleNamespace(state='succeeded'))
    restarted = ExecutionCollection(executions,plugin_configs={},child_command=[sys.executable,'-c','pass'])
    try:
        _until((tmp_path/'transport.ready').exists)
        import psutil
        pid, group = map(int,(tmp_path/'transport.ready').read_text().split())
        assert group == int((tmp_path/'exchange/original/collection/ready').read_text())
        if native_ssh:
            import signal
            import time
            _until(lambda: psutil.Process(pid).name() == 'ssh')
            # Stopped native code cannot handle TERM yet. The control owner
            # must survive while the whole work group awaits forced stop.
            os.killpg(group, signal.SIGSTOP)
        process.kill(); process.wait(timeout=2)
        if native_ssh:
            time.sleep(.05)
            assert psutil.Process(pid).status() == psutil.STATUS_STOPPED
            assert restarted.summary('original')['recovery_pending']
            assert not restarted.collect('original',scope='fixture',total_seconds=2)['accepted']
        _until(lambda: restarted.summary('original')['state'] == 'interrupted')
        _until(lambda: not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE)
        assert not (tmp_path/'late-write').exists()
        assert restarted.collect('original',scope='fixture',total_seconds=2)['accepted']
        _until(lambda: restarted._active is None)
    finally:
        if process.poll() is None:
            process.kill(); process.wait()
        process.stdout.close(); process.stderr.close()
        restarted.close()


def test_nested_transport_cause_survives_multiple_wrappers():
    from scidiscovery.artifact_agent.service.engineering_diagnostics import exception_facts
    transport = RuntimeError('remote command failed')
    transport.engineering = {'layer':'ssh_transfer','causes':[{'type':'TimeoutExpired','message':'file stalled',
        'timeout':30,'timeout_kind':'transfer_no_progress'}]}
    outer = RuntimeError('debug collection unavailable')
    outer.__cause__ = transport
    facts = exception_facts(outer,layer='worker',action='debug')
    assert facts['category'] == 'timeout' and facts['origin_layer'] == 'ssh_transfer'
    assert any(item.get('timeout_kind') == 'transfer_no_progress' for item in facts['causes'])


def test_socket_collect_uses_collection_deadline_through_real_service(tmp_path):
    import json
    import multiprocessing
    import sqlite3
    import time
    from scidiscovery.interfaces.daemon import UnixSocketDaemon
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.artifact_agent.service.execution_collection import CollectionContext
    from tcad_artifact.execution_control import TCADExecutionFacade,TCADExecutionPolicy,TCADExecutionRouter,ToolProfile
    from tcad_artifact.execution_adapter import TCADExecutorAdapter
    facade = TCADExecutionFacade(policy=TCADExecutionPolicy(allowed_input_roots=(str(tmp_path),),
        tools=(ToolProfile(profile_id='fixture',solver_kind='deterministic_tool',executable='/bin/true',release_evidence='fixture'),)),
        state_root=tmp_path/'state')
    run = 'terminal_fixture'
    directory = facade.runs_root / run
    (directory/'work').mkdir(parents=True)
    (directory/'worker.log').write_bytes(b'original log')
    (directory/'done').touch()
    (directory/'output_manifest.json').write_text(json.dumps({'terminal_state':'succeeded','exit_code':0,'outputs':[]}))
    with sqlite3.connect(facade.database_path) as connection:
        connection.execute('INSERT INTO submissions VALUES (?,?,?,?)',('a'*64,run,'2026-09-13T00:00:00Z','terminal'))
    collect = facade.tcad_collect
    def slow(**values):
        time.sleep(.15)
        return collect(**values)
    facade.tcad_collect = slow
    socket = tmp_path/'control.sock'
    process = multiprocessing.get_context('fork').Process(target=UnixSocketDaemon(
        socket,MCPRouter(TCADExecutionRouter(facade),name='tcad-control')).serve_forever)
    process.start()
    try:
        _until(socket.exists)
        adapter = TCADExecutorAdapter(socket, timeout=.03)
        outputs = adapter.collect_with_budget(run,context=CollectionContext.for_seconds(1))
        assert {item.name for item in outputs} == {'tcad_log','tcad_manifest'}
        with pytest.raises(TimeoutError) as caught:
            adapter.collect_with_budget(run,context=CollectionContext.for_seconds(.08))
        assert caught.value.timeout_kind == 'collection_total'
        assert adapter.status(run) == 'succeeded'
    finally:
        process.terminate(); process.join(3)
        if process.is_alive():
            process.kill(); process.join()
            raise AssertionError('TCAD service fixture did not stop')


def test_collection_guard_keeps_locks_when_stop_observation_fails(tmp_path, monkeypatch):
    import os
    import sys
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(sys.path))
    # Inject failure only in the private guard's process observation, after the
    # work leader exits with a living descendant. No production hook is added.
    guard = tmp_path / 'guard.py'
    guard.write_text('import os,sys\nfrom pathlib import Path\n'
        'from scidiscovery.artifact_agent.service.execution_collection import _guard\n'
        'scan=os.scandir\n'
        'def unavailable(path):\n'
        f' if str(path)=="/proc" and not Path({str(tmp_path / "observe")!r}).exists(): raise OSError(5,"injected process observation EIO")\n'
        ' return scan(path)\n'
        'os.scandir=unavailable\nraise SystemExit(_guard(Path(sys.argv[1])))\n')
    original = subprocess.Popen
    def launch(command, **kwargs):
        if '--guard' in command:
            command = [sys.executable, str(guard), command[-1]]
        return original(command, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', launch)
    descendant = ('import os,time; from pathlib import Path; '
        f'Path({str(tmp_path / "descendant")!r}).write_text(str(os.getpid())); time.sleep(30)')
    worker = ('import subprocess,sys,time; '
        f'subprocess.Popen([sys.executable,"-c",{descendant!r}]); time.sleep(.2)')
    executions = SimpleNamespace(database_path=tmp_path/'database/executions.sqlite3', exchange_root=tmp_path/'exchange',
        service_actor=ActorRef(actor_id='fixture',actor_type='service'),status=lambda _:SimpleNamespace(state='succeeded'))
    collector = ExecutionCollection(executions,plugin_configs={},child_command=[sys.executable,'-c',worker])
    restarted = ExecutionCollection(executions,plugin_configs={})
    try:
        collector.collect('original',scope='fixture',total_seconds=5)
        process = collector._active[1]
        _until((tmp_path/'descendant').exists)
        import psutil
        pid = int((tmp_path/'descendant').read_text())
        # The signal must still be sent despite the observation failure.
        _until(lambda: not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE)
        assert process.poll() is None
        details = restarted.summary('original')['stop_observation_error']
        assert details['action'] == 'observe_stop'
        assert any('injected process observation EIO' in x['message'] for x in details['causes'])
        assert not restarted.collect('original',scope='fixture')['accepted']
        assert restarted.collect('another',scope='fixture')['state'] == 'busy'
        (tmp_path/'observe').touch()
        _until(lambda: collector._active is None)
        assert not collector.summary('original').get('recovery_pending', False)
    finally:
        (tmp_path/'observe').touch()
        collector.close()
        restarted.close()


def test_collection_timeout_reason_survives_delayed_parent_watcher(tmp_path, monkeypatch):
    import os
    import sys
    import time
    from scidiscovery.artifact_agent.schema.refs import ActorRef
    from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
    monkeypatch.setenv('PYTHONPATH', os.pathsep.join(sys.path))
    executions = SimpleNamespace(database_path=tmp_path/'database/executions.sqlite3', exchange_root=tmp_path/'exchange',
        service_actor=ActorRef(actor_id='fixture',actor_type='service'),status=lambda _:SimpleNamespace(state='succeeded'))
    collector = ExecutionCollection(executions,plugin_configs={},child_command=[sys.executable,'-c',
        'import time; time.sleep(30)'])
    watch = collector._watch
    def delayed(*args):
        time.sleep(1.3)
        watch(*args)
    monkeypatch.setattr(collector, '_watch', delayed)
    try:
        collector.collect('original',scope='fixture',total_seconds=.8)
        _until(lambda: collector._active is None)
        result = collector.summary('original')
        assert result['state'] == 'timed_out'
        assert result['error']['category'] == 'timeout'
        assert any(x.get('timeout_kind') == 'collection_total' for x in result['error']['causes'])
    finally:
        collector.close()
