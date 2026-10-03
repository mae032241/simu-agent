"""Exact sealed evidence stays reusable across producer lifecycle and later work."""
import json
import pytest
from scidiscovery.artifact_agent.schema.common import canonical_json

@pytest.mark.parametrize('owner_state', ['running', 'failed', 'completed_after_read'])
def test_live_calculation_remains_reusable_through_finalization(tmp_path, owner_state):
    from tests.operations.test_analysis_claim_scope import generic_worker, submit
    from tests.operations.test_analysis_artifact_references import cite
    from tests.operations.test_result_analysis_tool import score_inputs, limited_report
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    catalog, runtime, root, *_ = system
    runs = runtime.runs
    original = runs.status(worker._run_id)
    calculation = worker.call_tool('worker_curve_score', {'record_key': 'original', 'request': score_inputs()[1]})
    assert calculation['status'] == 'computed'
    name = runs.publish_sealed_material(runs.status(original.run_id), calculation['calculation_ref'])
    if owner_state == 'failed':
        current = runs.status(original.run_id)
        runs.record_failure(original.run_id, reason='audit owner interrupted', expected_state=current.state,
            expected_last_activity_at=current.last_activity_at)
    request = {**system[3], 'name': 'reuse-live-calculation', 'inputs': [
        {**item, 'artifact_names': [*item['artifact_names'], name]}
        if item['port'] == 'reference_material' else item for item in system[3]['inputs']]}
    made = root.call_tool('operation_invoke', request)
    assert made['result']['state'] == 'queued', made
    rid = runtime.scheduler_bindings.resolve(instance=original.instance_id, namespace='run', name='reuse-live-calculation')
    runs.worker_connections.attach(run_id=rid, platform_session='audit', thread_id='consumer')
    compiled = catalog.operation('tcad.result.analyze.v1')
    consumer = LocalWorkerMCPRouter(runs, operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest, run_id=rid, trusted_caller=('audit', 'consumer'))
    assignment = consumer.call_tool('worker_open_assignment', {})
    alias = next(i.source_name for i in runs.status(rid).inputs if i.artifact_name == name)
    directory = consumer.call_tool('worker_reference_read', {'source': alias})
    assert any(r['reference'] == 'content' for r in directory['references'])
    read = consumer.call_tool('worker_reference_read', {'source': alias, 'action': 'read', 'reference': 'content'})
    assert read.get('state') != 'rejected', read
    if owner_state == 'completed_after_read':
        assert submit(worker, opened, cite(limited_report(), calculation['calculation_ref']))['state'] == 'completed'
        access = next(r for r in runs.reference_access_records(rid) if r['alias'] == read['source'])
        from scidiscovery.artifact_agent.schema.refs import ArtifactRef
        proof = ArtifactRef.model_validate(access['proof_manifest_ref'])
        assert proof not in runtime.artifacts.catalog(runs.status(original.run_id).output_ref).parent_refs
    assert runs.reference_calculation_sources(runs.status(rid), read['source']).tool_snapshot
    from tests.operations.test_tcad_result_analysis import analysis_report
    result = submit(consumer, assignment, cite(analysis_report(), read['source']))
    assert result['state'] == 'completed', result


def test_legacy_implementation_excludes_only_exact_frozen_inputs(tmp_path, monkeypatch):
    from tests.operations.test_experiment_continuation import continuation
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.operation_contract import DiagnosticError
    f = continuation(tmp_path, monkeypatch)
    record = f.implementation
    ref = ArtifactRef.model_validate(record['artifact_ref'])
    envelope = f.runtime.artifacts.catalog(ref)
    actual = f.coordinator._implementation_payload(record)
    earlier = f.runtime.artifacts.register(b'{}', ArtifactRegistration(kind='experiment_execution_package',
        schema_id=actual.schema_id, payload_schema_version=1, media_type='application/json', creator=f.runtime.actor),
        idempotency_key='audit-earlier-package').ref
    ambiguous = f.runtime.artifacts.register(f.runtime.artifacts.read(ref), ArtifactRegistration(
        kind=envelope.kind, schema_id=envelope.schema_id, payload_schema_version=envelope.payload_schema_version,
        media_type=envelope.media_type, creator=f.runtime.actor, parent_refs=(*envelope.parent_refs, earlier),
        labels=envelope.labels),
        idempotency_key='audit-two-package-parents').ref
    historical = {k: v for k, v in record.items() if k != 'control_parents'}
    assert f.coordinator._implementation_payload(historical) == actual
    historical['artifact_ref'] = ambiguous.model_dump(mode='json')
    with pytest.raises(DiagnosticError, match='unique controlled execution package'):
        f.coordinator._implementation_payload(historical)
    assert f.coordinator._implementation_payload({**historical, 'control_parents': [actual.model_dump(mode='json')]}) == actual
    from types import SimpleNamespace
    original = f.runs.status
    owner = envelope.labels['tool_producer_run']
    inputs = (*original(owner).inputs, SimpleNamespace(artifact_ref=earlier))
    with monkeypatch.context() as patch:
        patch.setattr(f.runs, 'status', lambda rid: SimpleNamespace(inputs=inputs) if rid == owner else original(rid))
        assert f.coordinator._implementation_payload(historical) == actual
    with pytest.raises(DiagnosticError, match='unique controlled execution package'):
        f.coordinator._implementation_payload(historical)


@pytest.mark.parametrize('case', ['wrong_kind', 'wrong_version', 'wrong_media', 'valid_plus_wrong_media'])
def test_parent_derivation_admission_boundaries(tmp_path, case):
    from tests.operations.test_tcad_result_analysis import analysis_system
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    _, runtime, root, request, artifacts, register = analysis_system(tmp_path)
    original = artifacts['package']
    alternate = runtime.artifacts.register(runtime.artifacts.read(original.ref), ArtifactRegistration(
        kind='arbitrary_label' if case == 'wrong_kind' else original.kind,
        schema_id=original.schema_id,
        payload_schema_version=99 if case == 'wrong_version' else original.payload_schema_version,
        media_type='text/plain' if 'media' in case else original.media_type,
        creator=runtime.actor, parent_refs=original.parent_refs), idempotency_key='audit-parent').ref
    parents = (original.ref, alternate) if case == 'valid_plus_wrong_media' else (alternate,)
    register('audit_manifest', runtime.artifacts.read(artifacts['manifest'].ref), 'opaque', parents=parents)
    for name in ('A', 'B'):
        output = artifacts['output_' + name]
        register('audit_output_' + name, runtime.artifacts.read(output.ref), 'opaque',
            media=output.media_type, parents=parents, output_name=name)
    request = {**request, 'inputs': [{**i, 'artifact_names': ['audit_manifest']}
        if i['port'] == 'runtime_manifest' else {**i, 'artifact_names': ['audit_output_A', 'audit_output_B']}
        if i['port'] == 'solver_outputs' else i for i in request['inputs']]}
    result = root.call_tool('operation_preflight', request)
    if case in {'wrong_kind', 'wrong_version'}:
        assert result['admissible'] is True, json.dumps(result)
    elif case == 'wrong_media':
        assert result['admissible'] is False and 'input_origin_missing' in json.dumps(result), result
    else:
        assert result['admissible'] is True, result


def test_published_material_reuses_its_fixed_proof_after_later_work(tmp_path):
    from tests.operations.test_analysis_claim_scope import generic_worker
    from tests.operations.test_result_analysis_tool import score_inputs
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    worker, _, _ = generic_worker(tmp_path, return_system=True)
    runs = worker.runs
    first_record = worker.call_tool('worker_curve_score', {'record_key': 'first', 'request': score_inputs()[1]})
    record = next(r for r in runs.tool_evidence(worker._run_id) if r['alias'] == first_record['calculation_ref'])
    ref = ArtifactRef.model_validate(record['artifact_ref'])
    first = runs.reference_manifest(runs.status(worker._run_id), subject_ref=ref)
    worker.call_tool('worker_curve_score', {'record_key': 'unrelated', 'request': score_inputs()[1]})
    assert runs.reference_manifest(runs.status(worker._run_id), subject_ref=ref) == first
    assert runs.artifacts.catalog(first).labels['operation_output_port'] == 'reference_proof'


def evidence_submission(tmp_path):
    from tests.operations.test_analysis_claim_scope import generic_worker
    worker, _, _ = generic_worker(tmp_path, return_system=True)
    runs = worker.runs
    owner = runs.status(worker._run_id)
    return runs, owner, dict(run_id=owner.run_id, tool_name='worker_curve_score', allowed_ports=('tool_evidence',),
        raw=b'{}', media_type='application/json', metadata={'kind': 'analysis_derived'},
        derived_from=(owner.inputs[0].source_name,))


@pytest.mark.parametrize('failure', ['limit', 'storage'])
def test_proof_failure_rolls_back_receipt_and_retry_completes(tmp_path, monkeypatch, failure):
    from scidiscovery.artifact_agent.service import tool_evidence
    from scidiscovery.artifact_agent.service.reference_proofs import proof_error
    from scidiscovery.operation_contract import DiagnosticError
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    runs, owner, args = evidence_submission(tmp_path)
    before = runs.tool_evidence(owner.run_id)
    with monkeypatch.context() as patch:
        if failure == 'limit':
            def excessive_dependencies(*args):
                raise proof_error('reference_proof_limit', 'Fixture dependency limit')
            patch.setattr(tool_evidence, 'material_snapshot', excessive_dependencies)
            error = DiagnosticError
        else:
            register = runs.artifacts.register
            def fail_proof(raw, registration, **kwargs):
                if registration.kind == 'tool_evidence_manifest':
                    raise OSError('fixture proof storage failure')
                return register(raw, registration, **kwargs)
            patch.setattr(runs.artifacts, 'register', fail_proof)
            error = OSError
        with pytest.raises(error):
            runs.accept_tool_evidence(**args)
    assert runs.tool_evidence(owner.run_id) == before
    record = runs.accept_tool_evidence(**args)
    assert len(runs.tool_evidence(owner.run_id)) == len(before) + 1
    ref = ArtifactRef.model_validate(record['artifact_ref'])
    proof = runs.reference_manifest(owner, subject_ref=ref)
    assert any(r['artifact_ref'] == record['artifact_ref'] for r in json.loads(runs.artifacts.read(proof))['records'])


def test_retry_repairs_historical_missing_proof_once(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    runs, owner, args = evidence_submission(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(runs, 'reference_manifest', lambda *a, **k: None)
        original = runs.accept_tool_evidence(**args)
    snapshots = []
    from scidiscovery.artifact_agent.service import tool_evidence
    encode = tool_evidence.material_snapshot
    def capture(*args):
        snapshots.append(True)
        return encode(*args)
    monkeypatch.setattr(tool_evidence, 'material_snapshot', capture)
    assert runs.accept_tool_evidence(**args) == original
    assert runs.accept_tool_evidence(**args) == original
    assert len(snapshots) == 1
    assert len(runs.tool_evidence(owner.run_id)) == 1
    assert runs.reference_manifest(owner, subject_ref=ArtifactRef.model_validate(original['artifact_ref']))


@pytest.mark.parametrize('external', [False, True])
def test_orphan_proof_cannot_override_receipt_after_rollback(tmp_path, monkeypatch, external):
    from scidiscovery.artifact_agent.schema.refs import ArtifactRef
    if external:
        from tests.operations.test_evidence_source_capture import open_extraction
        _, runtime, _, worker, _, _ = open_extraction(tmp_path)
        runs = runtime.runs
        owner = runs.status(worker._run_id)
        args = dict(run_id=owner.run_id, tool_name='worker_capture_source', allowed_ports=('tool_evidence',),
            raw=b'{}', media_type='text/plain', metadata={'origin': 'public_web'}, external_source=True)
    else:
        runs, owner, args = evidence_submission(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(runs, '_bind_evidence_output', lambda *a, **k: (_ for _ in ()).throw(OSError('binding interrupted')))
        with pytest.raises(OSError):
            runs.accept_tool_evidence(**args)
    assert not runs.tool_evidence(owner.run_id)
    runs.accept_tool_evidence(**{**args, 'raw': b'{"later": true}'})
    record = runs.accept_tool_evidence(**args)
    ref = ArtifactRef.model_validate(record['artifact_ref'])
    proof = runs.reference_manifest(owner, subject_ref=ref)
    matches = [r for r in json.loads(runs.artifacts.read(proof))['records'] if r['artifact_ref'] == record['artifact_ref']]
    assert len(matches) == 1 and matches[0]['alias'] == record['alias'] == 'tool_evidence_002'
