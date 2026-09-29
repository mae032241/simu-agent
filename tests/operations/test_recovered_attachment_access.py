"""Published files remain readable through failure, recovery and final sealing."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_experiment_continuation import continuation, submit
from tests.operations.test_instance_content_display import picture


def test_hidden_attachment_port_does_not_hide_recovered_scientific_files(tmp_path, monkeypatch):
    f = continuation(tmp_path, monkeypatch)
    raw = picture('blue')
    (f.workspace / 'scratch/overlay.png').write_bytes(raw)
    saved = f.worker.call_tool('worker_publish_files', {'source_aliases': [f.alias],
        'files': [{'path': 'scratch/overlay.png', 'purpose': 'Original target comparison.'}]})
    attachment = saved['files'][0]['reference']
    stage = f.worker.call_tool('worker_experiment_stage', {'stage': 'validity',
        'conclusion': 'Retain the exact comparison, without a new solver run.', 'materials': [attachment]})['reference']
    compiled = f.catalog.operation('science.experiment.v1')
    assert not next(p for p in compiled.spec.outputs if p.name == 'attachments').agent_visible

    def check(worker):
        listed = worker.call_tool('worker_reference_read', {'source': attachment})
        content = next(x for x in listed['references'] if x['reference'] == 'content')
        delivered = worker.call_tool('worker_reference_read', {'source': attachment, 'action': 'read',
            'reference': content['reference'], 'delivery': 'file'})
        assert Path(delivered['file_path']).read_bytes() == raw
        linked = worker.call_tool('worker_reference_read', {'source': stage})
        edge = next(x for x in linked['references'] if x.get('alias') == attachment)
        delivered = worker.call_tool('worker_reference_read', {'source': stage, 'action': 'read',
            'reference': edge['reference'], 'delivery': 'file'})
        assert delivered['source'] == attachment
        assert Path(delivered['file_path']).read_bytes() == raw
        assert not any(key in json.dumps(linked) for key in ('artifact_ref', 'artifact_id', 'output_port'))
        with pytest.raises(DiagnosticError) as error:
            worker.call_tool('worker_reference_read', {'source': 'tool_recovery_manifest'})
        assert error.value.details[0]['code'] == 'reference_source_unknown'

    check(f.worker)
    old = f.runs.status(f.run_id)
    f.runs.record_failure(f.run_id, reason='fixture interruption', expected_state=old.state,
        expected_last_activity_at=old.last_activity_at)
    response = f.root.call_tool('operation_invoke', {**f.invocation, 'name': 'recovered', 'draft_from': 'continuation'})
    assert response['result']['state'] == 'queued', response
    recovered = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace='run', name='recovered')
    f.runs.worker_connections.attach(run_id=recovered, platform_session='recovery', thread_id='attachment-owner')
    services = bind_experiment_services(f.runs, compiled, dict(f.coordinator.worker_services), coordinator=f.coordinator)
    f.worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, tool_services=services)
    f.workspace = Path(f.worker.call_tool('worker_open_assignment', {})['workspace_path'])
    check(f.worker)
    assert submit(f, [stage, attachment], outcome='inconclusive')['state'] == 'completed'
