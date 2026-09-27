"""Restricted originals survive publication and exact scientific consumption."""
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN
from scidiscovery.operations.catalog import compile_catalog
from tests.operations.test_l3_review_and_human_policy import _system
from tests.operations.test_scientific_attachments import finish
from tests.operations.worker_fixtures import attached_worker


def system(tmp_path):
    extract = next(op for op in PLUGIN.operations if op.operation_id == 'science.evidence.extract.v1')
    consumer = extract.model_copy(update={'operation_id': 'science.fixture.consume.v1', 'review': None,
        'inputs': tuple(port.model_copy(update={'usage': 'claim_evidence', 'schema_id': 'opaque', 'schema_resource': extract.outputs[1].schema_resource, 'media_types': ('text/csv',), 'exposure': 'on_demand', 'max_item_bytes': 1024 * 1024})
                        if port.name == 'source_material' else port for port in extract.inputs)})
    intake_port = extract.outputs[0]
    intake_consumer = consumer.model_copy(update={'operation_id': 'science.fixture.consume_intake.v1',
        'inputs': tuple(port.model_copy(update={'schema_id': intake_port.schema_id, 'media_types': intake_port.media_types,
            'codec': intake_port.codec, 'schema_resource': intake_port.schema_resource})
            if port.name == 'source_material' else port for port in consumer.inputs)})
    catalog = compile_catalog((CORE_PLUGIN, PLUGIN.model_copy(update={'operations': (*PLUGIN.operations, consumer, intake_consumer)})))
    _, runtime, instance, root = _system(tmp_path, catalog=catalog)
    for name, labels in [('restricted', {'scientific_claim_admissible': 'false'}), ('clean', {})]:
        envelope = runtime.artifacts.register(name.encode(), ArtifactRegistration(kind='source', schema_id='opaque',
            payload_schema_version=1, media_type='text/plain', creator=runtime.actor, labels=labels), idempotency_key=name)
        runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name=name, object_id=envelope.artifact_id)
    root.call_tool('operation_invoke', {'name': 'evidence', 'operation_id': extract.operation_id,
        'instruction': 'Extract bounded evidence while preserving source restrictions.', 'inputs': [
            {'port': 'source_material', 'artifact_names': ['clean']},
            {'port': 'feedback', 'artifact_names': ['restricted']}]})
    worker = attached_worker(runtime, root, 'evidence')
    opened = worker.call_tool('worker_open_assignment', {})
    aliases = {item.port_name: item.source_name for item in runtime.runs.status(worker._run_id).inputs}
    return runtime, root, worker, opened, aliases


def consume(root, name, action='operation_preflight'):
    return root.call_tool(action, {'name': 'consume', 'operation_id': ('science.fixture.consume_intake.v1' if name.endswith('.output') else 'science.fixture.consume.v1'),
        'instruction': 'Use this material as scientific claim evidence.',
        'inputs': [{'port': 'source_material', 'artifact_names': [name]}]})


@pytest.mark.parametrize('publication', ['attachment', 'tool'])
@pytest.mark.parametrize('restricted', [True, False])
@pytest.mark.parametrize('historical', [False, True])
def test_publication_and_cited_result_preserve_only_actual_source_restrictions(tmp_path, monkeypatch, publication, restricted, historical):
    runtime, root, worker, opened, aliases = system(tmp_path)
    if historical:
        # Register old-format objects once; never rewrite stored envelopes or bytes.
        register, register_file = runtime.artifacts.register, runtime.artifacts.register_file
        def old_registration(method):
            def call(content, registration, **kwargs):
                labels = {key: value for key, value in registration.labels.items() if key != 'scientific_claim_admissible'}
                return method(content, registration.model_copy(update={'labels': labels}), **kwargs)
            return call
        monkeypatch.setattr(runtime.artifacts, 'register', old_registration(register))
        monkeypatch.setattr(runtime.artifacts, 'register_file', old_registration(register_file))
    source = aliases['feedback' if restricted else 'source_material']
    if publication == 'attachment':
        workspace = Path(opened['assignment_path']).parent
        (workspace / 'scratch/derived.csv').write_bytes(b'x,y\n1,2\n')
        saved = worker.call_tool('worker_publish_files', {'source_aliases': [source],
            'files': [{'path': 'scratch/derived.csv', 'purpose': 'Bounded derived observations'}]})
        alias = saved['files'][0]['reference']
    else:
        record = runtime.runs.accept_tool_evidence(worker._run_id, tool_name='fixture_derived',
            allowed_ports=('tool_evidence',), raw=b'x,y\n1,2\n', media_type='text/csv',
            metadata={'kind': 'fixture'}, derived_from=(source,))
        alias = record['alias']
    # A second publication cites the first receipt, not the original input.
    workspace = Path(opened['assignment_path']).parent
    (workspace / 'scratch/second.csv').write_bytes(b'x,y\n2,4\n')
    second = worker.call_tool('worker_publish_files', {'source_aliases': [alias],
        'files': [{'path': 'scratch/second.csv', 'purpose': 'Second derived observations'}]})
    assert finish(worker, opened, second['files'][0]['reference'])['state'] == 'completed'
    status = root.call_tool('run_status', {'name': 'evidence', 'intent': 'navigation'})
    records = runtime.runs.tool_evidence(worker._run_id)
    refs = [ArtifactRef.model_validate(record['artifact_ref']) for record in records]
    before = [(runtime.artifacts.catalog(ref), runtime.artifacts.read(ref)) for ref in refs]
    read = runtime.artifacts.read
    def no_file_reads(ref):
        assert ref not in refs, 'Scientific admission must not read attachment/tool bytes'
        return read(ref)
    monkeypatch.setattr(runtime.artifacts, 'read', no_file_reads)
    for name in ['evidence.output', *(item['artifact_name'] for item in status['evidence_outputs'])]:
        result = consume(root, name)
        if restricted:
            assert result.get('reason_code') == 'input_scientific_claim_forbidden', result
            from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
            with pytest.raises(RootToolError, match='input_scientific_claim_forbidden'):
                consume(root, name, 'operation_invoke')
        else:
            assert result['admissible'], result
    monkeypatch.setattr(runtime.artifacts, 'read', read)
    assert before == [(runtime.artifacts.catalog(ref), read(ref)) for ref in refs]
    for record in records:
        labels = runtime.artifacts.catalog(ArtifactRef.model_validate(record['artifact_ref'])).labels
        assert (labels.get('scientific_claim_admissible') == 'false') is (restricted and not historical)


def test_unreferenced_restricted_prior_draft_does_not_taint_new_result(tmp_path):
    runtime, root, worker, opened, aliases = system(tmp_path)
    assert finish(worker, opened, aliases['feedback'])['state'] == 'completed'
    assert consume(root, 'evidence.output')['reason_code'] == 'input_scientific_claim_forbidden'
    root.call_tool('operation_invoke', {'name': 'reconsidered', 'operation_id': 'science.evidence.extract.v1',
        'instruction': 'Use the independent clean source; retain the old draft for comparison.', 'inputs': [
            {'port': 'source_material', 'artifact_names': ['clean']},
            {'port': 'prior_draft', 'artifact_names': ['evidence.output']}]})
    following = attached_worker(runtime, root, 'reconsidered')
    opened = following.call_tool('worker_open_assignment', {})
    clean = next(item.source_name for item in runtime.runs.status(following._run_id).inputs if item.port_name == 'source_material')
    assert finish(following, opened, clean)['state'] == 'completed'
    assert consume(root, 'reconsidered.output')['admissible']


@pytest.mark.parametrize('fault', ['budget', 'contract'])
def test_unavailable_historical_provenance_returns_explicit_admission_error(tmp_path, monkeypatch, fault):
    runtime, root, worker, opened, aliases = system(tmp_path)
    assert finish(worker, opened, aliases['source_material'])['state'] == 'completed'
    if fault == 'budget':
        from dataclasses import replace
        from scidiscovery.operations import tooling
        original = tooling.reference_policy
        monkeypatch.setattr(tooling, 'reference_policy', lambda compiled: replace(original(compiled), max_calls=1))
    else:
        from scidiscovery.artifact_agent.service.run_records import RunContractUnavailable
        def unavailable(value):
            raise RunContractUnavailable('Historical exact contract unavailable')
        monkeypatch.setattr(runtime.runs, '_compiled', unavailable)
    result = consume(root, 'evidence.output')
    assert result['reason_code'] == 'input_scientific_provenance_unavailable', result


@pytest.mark.parametrize('restricted', [False, True])
def test_optional_ledger_keeps_direct_citation_limits_and_exact_control_manifest(tmp_path, restricted):
    import json
    from tests.operations.test_general_transform_operations import _intake
    from scidiscovery.artifact_agent.service.scientific_usage import ScientificProvenanceError, scientific_use_restricted

    runtime, root, worker, opened, aliases = system(tmp_path)
    payload = _intake().model_dump(mode='json')
    payload['scientific_foundation'].pop('evidence')
    payload['scientific_foundation']['items'][0]['evidence_keys'] = [aliases['feedback' if restricted else 'source_material']]
    Path(opened['output_directory'], 'result.json').write_text(json.dumps({
        'handoff': {'verdict': 'pass', 'summary': 'Direct source citation.'}, 'payload': payload}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    producer = runtime.runs.status(worker._run_id)
    envelope = runtime.artifacts.catalog(producer.output_ref)
    manifest = next(runtime.artifacts.catalog(ref) for ref in envelope.parent_refs
                    if ref.schema_id == 'scidiscovery.tool-evidence-manifest.v1')
    assert scientific_use_restricted(runtime.runs, (manifest.ref,)) is restricted
    result = consume(root, 'evidence.output')
    assert result['admissible'] is not restricted, result
    # Equal bytes and copied producer labels do not prove sealed manifest identity.
    copied = runtime.artifacts.register(runtime.artifacts.read(manifest.ref), ArtifactRegistration(
        kind=manifest.kind, schema_id=manifest.schema_id, payload_schema_version=1,
        media_type=manifest.media_type, creator=runtime.actor, parent_refs=manifest.parent_refs,
        labels=manifest.labels), idempotency_key='copied-manifest')
    assert copied.ref != manifest.ref
    with pytest.raises(ScientificProvenanceError, match='unique exact producer receipt'):
        scientific_use_restricted(runtime.runs, (copied.ref,))
