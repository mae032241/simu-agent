"""Isolated capability probes, not production server observations."""
from dataclasses import asdict, replace
import json
from pathlib import Path
from types import SimpleNamespace


def test_author_debug_pending_and_terminal_log_visibility(tmp_path, monkeypatch):
    from tests.operations.test_l4_local_tcad import _budget_case
    from tcad_artifact.debug_contract import CollectedTCADDebugFile
    worker, adapter, opened = _budget_case(tmp_path)
    collect = adapter.collect
    raw = b'fixture solver step completed\nElapsed wallclock time: 12 s\n'
    monkeypatch.setattr(adapter, 'collect', lambda value: replace(collect(value),
        log_excerpt=raw.decode(), files=(CollectedTCADDebugFile('debug.log.txt', 'text/plain', raw),)))
    adapter.pending = True
    request = {'run_name': 'visibility', 'mode': 'preflight'}
    pending = worker.call_tool('worker_tcad_debug_run', request)
    assert pending['phase'] == 'pending'
    assert not {'log_excerpt', 'log_relative_path', 'started_at', 'elapsed_seconds'} & pending.keys()
    adapter.pending = False
    terminal = worker.call_tool('worker_tcad_debug_run', request)
    assert terminal['phase'] == 'collected'
    assert (Path(opened['workspace_path']) / terminal['log_relative_path']).read_bytes() == raw
    print(json.dumps({'pending_keys': sorted(pending), 'terminal_keys': sorted(terminal),
        'terminal_log_readable': True, 'budget_is_reserved_upper_bound': pending['reserved_wall_seconds_for_run']}))


def test_debug_bridge_does_not_project_server_manifest_timestamps(tmp_path):
    from tests.operations.test_log_preservation import _descriptor
    from tcad_artifact.debug_adapter import TCADDevelopmentDebugBridge
    log = tmp_path / 'worker.log'; log.write_text('fixture complete\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'terminal_state': 'succeeded', 'exit_code': 0, 'error': '', 'outputs': [],
        'started_at': '2026-09-13T00:00:00Z', 'completed_at': '2026-09-13T00:00:12Z'}))
    adapter = SimpleNamespace(collect=lambda _: (
        _descriptor('tcad_log', log, 'text/plain'), _descriptor('tcad_manifest', manifest, 'application/json')))
    result = asdict(TCADDevelopmentDebugBridge(adapter).collect('fixture'))
    assert not {'started_at', 'completed_at', 'elapsed_seconds'} & result.keys()
    assert not any(item['name'] == 'tcad_manifest' for item in result['files'])
    print(json.dumps({'server_manifest_has_timestamps': True,
        'debug_result_keys': sorted(result), 'debug_file_names': [item['name'] for item in result['files']]}))


def test_runtime_author_accepts_the_server_log_media_type(tmp_path):
    from tests.operations.test_l4_local_tcad import _system, _project
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.schema.common import canonical_json
    from scidiscovery.operations.invoke import InvocationArtifact, OperationInvocationError, _validate_port_binding
    catalog, runtime, root, capability = _system(tmp_path)
    instance = runtime.scheduler_bindings.list_instances()[0].instance_id
    def register(name, raw, schema, media='application/json'):
        record = runtime.artifacts.register(raw, ArtifactRegistration(kind='fixture', schema_id=schema,
            payload_schema_version=1, media_type=media, creator=runtime.actor), idempotency_key=name)
        runtime.scheduler_bindings.bind(instance=instance, namespace='artifact', name=name, object_id=record.artifact_id)
        return record
    register('prior', canonical_json(_project(capability).model_dump(mode='json')), 'tcad.deck-project.v1')
    register('attestation', canonical_json(dict(schema_version=1, verdict='fail', terminal_state='failed', exit_code=1,
        checks=[dict(check_key='solver_failed', status='fail', rationale='Fixture solver failure.')],
        solver_native_output_count=0, transport_derived_output_count=0, parser_derived_output_count=0,
        rationale='Fixture terminal failure.')), 'tcad.runtime-attestation.v1')
    request = dict(name='runtime_revision', operation_id='tcad.deck.author.runtime-failure.v1',
        instruction='Fix the fixture runtime failure.', inputs=[
            dict(port='prior_project', artifact_names=['prior']), dict(port='runtime_attestation', artifact_names=['attestation']),
            dict(port='execution_capability', artifact_names=['execution_capability']),
            dict(port='experiment_plan', artifact_names=['experiment_plan'])])
    replies = {}
    port_results = {}
    port = next(p for p in catalog.operation(request['operation_id']).spec.inputs if p.name == 'solver_log')
    for name, media in [('plain_log', 'text/plain'), ('server_log', 'text/plain; charset=utf-8')]:
        artifact = register(name, b'fixture solver error\n', 'opaque', media)
        try:
            _validate_port_binding(port, (InvocationArtifact(artifact_name=name, ref=artifact.ref,
                schema_id=artifact.schema_id, media_type=artifact.media_type, size_bytes=artifact.size_bytes),))
            port_results[media] = 'accepted'
        except OperationInvocationError as error:
            port_results[media] = error.reason_code
        replies[media] = root.call_tool('operation_preflight', {**request,
            'inputs': request['inputs'] + [dict(port='solver_log', artifact_names=[name])]})
    print(json.dumps({'runtime_author_log_preflight': replies, 'exact_compiled_solver_log_port': port_results,
        'limit': 'The synthetic prior project is unqualified; this is a log port control, not a full author handoff.'}))
    assert port_results['text/plain'] == 'accepted'
    assert port_results['text/plain; charset=utf-8'] == 'accepted'
