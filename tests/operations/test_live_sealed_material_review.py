"""Review exact stage originals without completing or granting access to the owner."""
import json
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from tests.operations.test_experiment_continuation import continuation, submit
from tests.operations.test_instance_content_display import picture


@pytest.mark.parametrize('origin', ['current', 'historical', 'legacy_access', 'legacy_historical'])
def test_review_reads_failed_owners_solver_files_through_another_stage(tmp_path, monkeypatch, origin):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.service.experiment_execution import bind_experiment_services
    from scidiscovery.artifact_agent.service.run_records import RunContractUnavailable
    from tests.operations.test_r4_experiment_task import _real_experiment

    class FixtureFinished(Exception):
        pass

    def check(runtime, root, owner, instance, workspace, catalog, collected):
        runs = runtime.runs
        owner_id = owner._run_id
        material = next(r for r in runs.tool_evidence(owner_id) if r['alias'] == collected['reference'])
        exact_ref = ArtifactRef.model_validate(material['artifact_ref'])
        name = runs.publish_sealed_material(runs.status(owner_id), material['alias'])
        old = runs.status(owner_id)
        runs.record_failure(owner_id, reason='fixture interruption after collection',
            expected_state=old.state, expected_last_activity_at=old.last_activity_at)
        made = root.call_tool('operation_invoke', {'name': 'reuse-collected-material',
            'operation_id': 'science.experiment.v1', 'instruction': 'Inspect the exact collected result.',
            'inputs': [{'port': 'subject', 'artifact_names': ['objective']},
                {'port': 'scientific_materials', 'artifact_names': [name]}]})
        assert made['result']['state'] == 'queued', made
        reused_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id,
            namespace='run', name='reuse-collected-material')
        runs.worker_connections.attach(run_id=reused_id, platform_session='reuse', thread_id='consumer')
        compiled = catalog.operation('science.experiment.v1')
        coordinator = runs.experiment_executions
        services = bind_experiment_services(runs, compiled, dict(coordinator.worker_services), coordinator=coordinator)
        worker = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id,
            operation_digest=compiled.digest, run_id=reused_id,
            trusted_caller=('reuse', 'consumer'), tool_services=services)
        worker.call_tool('worker_open_assignment', {})
        alias = next(i.source_name for i in runs.status(reused_id).inputs if i.artifact_ref == exact_ref)
        stage = worker.call_tool('worker_experiment_stage', {'stage': 'validity',
            'conclusion': 'Inspect the exact collected originals.', 'materials': [alias]})
        subject = runs.publish_sealed_material(runs.status(reused_id), stage['reference'])
        made = root.call_tool('operation_invoke', {'name': 'nested-review',
            'operation_id': 'science.object.review.v1',
            'inputs': [{'port': 'subject', 'artifact_names': [subject]}],
            'instruction': 'Review the stage and its original solver files.'})
        assert made['result']['state'] == 'queued', made
        review_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='nested-review')
        runs.worker_connections.attach(run_id=review_id, platform_session='review', thread_id='reviewer')
        compiled = catalog.operation('science.object.review.v1')
        reviewer = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id,
            operation_digest=compiled.digest, run_id=review_id, trusted_caller=('review', 'reviewer'))
        reviewer.call_tool('worker_open_assignment', {})
        if origin in {'historical', 'legacy_historical'}:
            compiled_for = runs._compiled
            def unavailable(value):
                if value.run_id in {owner_id, reused_id}:
                    raise RunContractUnavailable('Producer contract changed after deployment')
                return compiled_for(value)
            monkeypatch.setattr(runs, '_compiled', unavailable)
        bound = next(i.source_name for i in runs.status(review_id).inputs if i.port_name == 'subject')
        index = reviewer.call_tool('worker_reference_read', {'source': bound})
        edge = next(e for e in index['references'] if e.get('alias') == alias)
        receipt = reviewer.call_tool('worker_reference_read', {'source': bound,
            'action': 'read', 'reference': edge['reference']})
        access = next(r for r in runs.reference_access_records(review_id) if r['alias'] == receipt['source'])
        assert access['proof_run_id'] == owner_id
        assert access['authorizing_run_id'] == reused_id
        if origin in {'legacy_access', 'legacy_historical'}:
            # Simulate an already committed pre-fix access receipt; no new read
            # from the parent stage should be needed to repair its next hop.
            access_records = runs.reference_access_records
            def old_receipts(run_id):
                return [{**r, 'proof_run_id': None, 'proof_manifest_ref': None}
                        if run_id == review_id and r['alias'] == receipt['source'] else r
                        for r in access_records(run_id)]
            monkeypatch.setattr(runs, 'reference_access_records', old_receipts)
        files = reviewer.call_tool('worker_reference_read', {'source': receipt['source']})
        assert {e['file_name'] for e in files['references']} == {'case-A/final.tdr', 'case-A/profile_480s.txt'}
        for entry in files['references']:
            result = reviewer.call_tool('worker_reference_read', {'source': receipt['source'],
                'action': 'read', 'reference': entry['reference'], 'delivery': 'file'})
            assert Path(result['file_path']).read_bytes() == b'observed fixture\n'
        assert runs.status(owner_id).state == 'failed'
        assert 'artifact_ref' not in json.dumps(files)
        if origin == 'current':
            from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
            access_records = runs.reference_access_records
            def mismatched_proof(run_id):
                return [{**r, 'proof_run_id': reused_id,
                         'proof_manifest_ref': r['authorizing_manifest_ref']}
                        if run_id == review_id and r['alias'] == receipt['source'] else r
                        for r in access_records(run_id)]
            monkeypatch.setattr(runs, 'reference_access_records', mismatched_proof)
            with pytest.raises(WorkerToolError) as rejected:
                reviewer.call_tool('worker_reference_read', {'source': receipt['source']})
            assert rejected.value.details[0]['code'] == 'reference_record_unpaired'
        raise FixtureFinished()

    with pytest.raises(FixtureFinished):
        _real_experiment(tmp_path, monkeypatch, before_submit=check)


@pytest.mark.parametrize('owner_state', ['running', 'failed', 'completed'])
@pytest.mark.parametrize('historical', [False, True])
def test_reviewer_reads_sealed_stage_and_its_image_before_owner_completion(tmp_path, monkeypatch, owner_state, historical):
    f = continuation(tmp_path, monkeypatch)
    raw = picture('blue')
    (f.workspace / 'scratch/plot.png').write_bytes(raw)
    saved = f.worker.call_tool('worker_publish_files', {'source_aliases': [f.alias],
        'files': [{'path': 'scratch/plot.png', 'purpose': 'Exact comparison plot.'}]})
    image_alias = saved['files'][0]['reference']
    stage = f.worker.call_tool('worker_experiment_stage', {'stage': 'validity',
        'conclusion': 'Review this exact image.', 'materials': [image_alias]})
    if owner_state == 'failed':
        old = f.runs.status(f.run_id)
        f.runs.record_failure(f.run_id, reason='fixture interruption', expected_state=old.state,
            expected_last_activity_at=old.last_activity_at)
    elif owner_state == 'completed':
        assert submit(f, [stage['reference']], outcome='inconclusive')['state'] == 'completed'
    subject = f.runs.publish_sealed_material(f.runs.status(f.run_id), stage['reference'])
    if historical:
        from scidiscovery.artifact_agent.service.run_records import RunContractUnavailable
        compiled_for = f.runs._compiled
        def unavailable(value):
            if value.run_id == f.run_id:
                raise RunContractUnavailable('Producer contract changed after deployment')
            return compiled_for(value)
        monkeypatch.setattr(f.runs, '_compiled', unavailable)
    created = f.root.call_tool('operation_invoke', {'name': 'live-stage-review', 'operation_id': 'science.object.review.v1',
        'inputs': [{'port': 'subject', 'artifact_names': [subject]}], 'instruction': 'Read the stage and its exact plot.'})
    assert created['result']['state'] == 'queued'
    run_id = f.runtime.scheduler_bindings.resolve(instance=f.instance.instance_id, namespace='run', name='live-stage-review')
    f.runs.worker_connections.attach(run_id=run_id, platform_session='review', thread_id='reviewer')
    compiled = f.catalog.operation('science.object.review.v1')
    worker = LocalWorkerMCPRouter(f.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest,
        run_id=run_id, trusted_caller=('review', 'reviewer'))
    worker.call_tool('worker_open_assignment', {})
    bound = next(i.source_name for i in f.runs.status(run_id).inputs if i.port_name == 'subject')
    directory = worker.call_tool('worker_reference_read', {'source': bound})
    assert 'references' in directory, directory
    if owner_state == 'running' and not historical:
        (f.workspace / 'scratch/unrelated.txt').write_text('Unrelated later sealed work.')
        later = f.worker.call_tool('worker_publish_files', {'source_aliases': [f.alias],
            'files': [{'path': 'scratch/unrelated.txt', 'purpose': 'Not part of the reviewed stage.'}]})
        assert later['files'][0]['reference'] not in {e.get('alias') for e in directory['references']}
        from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
        with pytest.raises(WorkerToolError):
            worker.call_tool('worker_reference_read', {'source': later['files'][0]['reference']})
    content = worker.call_tool('worker_reference_read', {'source': bound, 'action': 'read', 'reference': 'content'})
    assert 'Review this exact image.' in content['fragment']
    edge = next(e for e in directory['references'] if e.get('alias') == image_alias)
    delivered = worker.call_tool('worker_reference_read', {'source': bound, 'action': 'read',
        'reference': edge['reference'], 'delivery': 'file'})
    assert Path(delivered['file_path']).read_bytes() == raw
    nested = worker.call_tool('worker_reference_read', {'source': delivered['source']})
    assert any(e.get('reference') == 'content' for e in nested['references']), nested
    assert f.runs.status(f.run_id).state == owner_state
    assert 'artifact_ref' not in json.dumps(directory)


def test_prepare_rejects_runner_storage_limit_before_sealing_or_review(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
    from tcad_artifact.execution_policy import execution_admission
    from tcad_artifact.project_packager import ExecutionPackage
    from tests.operations.tcad_policy_fixtures import policy_snapshot
    f = continuation(tmp_path, monkeypatch, require_execution_review=True)
    policy = policy_snapshot()
    policy = policy.model_copy(update={'runner': policy.runner.model_copy(update={'max_transfer_bytes': 1024**3})})
    adapter = f.coordinator.bridge._adapter('tcad_artifact:tcad')
    monkeypatch.setattr(adapter, 'execution_admission', lambda payload, **kwargs:
        execution_admission(policy, ExecutionPackage.model_validate_json(payload, strict=True)))
    document = json.loads(f.runtime.artifacts.read(ArtifactRef.model_validate(f.implementation['artifact_ref'])))['implementation']
    document['resource_limits'].update(max_storage_bytes=2 * 1024**3, max_output_bytes=1024**3)
    path = f.workspace / 'scratch/experiment.json'
    path.write_text(json.dumps(document))
    before = f.runs.tool_evidence(f.run_id)
    with pytest.raises(WorkerToolError) as caught:
        f.worker.call_tool('worker_experiment_prepare', {})
    assert caught.value.details[0]['code'] == 'execution_storage_capability_exceeded'
    assert '1073741824' in str(caught.value)
    assert f.runs.tool_evidence(f.run_id) == before
    assert not f.runtime.scheduler_bindings.list(instance=f.instance.instance_id, namespace='execution', name_prefix='experiment-' + f.run_id)
    document['resource_limits'].update(max_storage_bytes=1024**3, max_output_bytes=512 * 1024**2)
    path.write_text(json.dumps(document))
    assert f.worker.call_tool('worker_experiment_prepare', {})['state'] == 'sealed'


def test_review_reads_collected_solver_files_while_owner_still_running(tmp_path, monkeypatch):
    from tests.operations.test_r4_experiment_task import _real_experiment
    def check(runtime, root, owner, instance, workspace, catalog, collected):
        runs = runtime.runs
        original = runs.status(owner._run_id)
        name = runs.publish_sealed_material(original, collected['reference'])
        root.call_tool('operation_invoke', {'name': 'live-execution-review',
            'operation_id': 'science.object.review.v1', 'inputs': [{'port': 'subject', 'artifact_names': [name]}],
            'instruction': 'Inspect the exact collected originals.'})
        review_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='live-execution-review')
        runs.worker_connections.attach(run_id=review_id, platform_session='review', thread_id='reviewer')
        compiled = catalog.operation('science.object.review.v1')
        reviewer = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id,
            operation_digest=compiled.digest, run_id=review_id, trusted_caller=('review', 'reviewer'))
        reviewer.call_tool('worker_open_assignment', {})
        subject = next(i.source_name for i in runs.status(review_id).inputs if i.port_name == 'subject')
        index = reviewer.call_tool('worker_reference_read', {'source': subject})
        assert {i['file_name'] for i in index['references']} == {'case-A/final.tdr', 'case-A/profile_480s.txt'}
        for item in index['references']:
            saved = reviewer.call_tool('worker_reference_read', {'source': subject,
                'action': 'read', 'reference': item['reference'], 'delivery': 'file'})
            assert Path(saved['file_path']).read_bytes() == b'observed fixture\n'
        assert runs.status(original.run_id).state == 'running'
        return []
    _real_experiment(tmp_path, monkeypatch, before_submit=check)
