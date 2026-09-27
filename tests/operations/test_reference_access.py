"""Exact references, recovery scopes and atomic access receipts on real SQLite."""
from contextlib import contextmanager
import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Barrier
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.tool_evidence import ToolEvidenceMixin
from scidiscovery.artifact_agent.service.reference_access import ReferenceAccessError
from scidiscovery.reference_tools import ReferencePolicy, ReferenceReadRequest, ReferenceRule


class Harness(ToolEvidenceMixin):
    def __init__(self, root):
        self.root = root
        self.database_path = root / 'control.sqlite'
        self.policy = ReferencePolicy()
        self.contents = {}
        self.envelopes = {}
        self.producers = {}
        self.inputs = {}
        self.artifacts = SimpleNamespace(read=self.read, catalog=lambda ref: self.envelopes[ref], open_original=self.open_original)
        self.backend = SimpleNamespace(capabilities=('native_workspace',), open=lambda run_id: SimpleNamespace(root=root / run_id / 'workspace', input_paths={item.source_name: root/run_id/'workspace'/'inputs'/item.source_name for item in self.inputs.get(run_id, ())}))
        with self._connect() as db:
            db.executescript('''
              CREATE TABLE runs(run_id TEXT PRIMARY KEY, instance_id TEXT, state TEXT,
                accepted_candidate_digest TEXT, draft_from_run_id TEXT, resume_from_run_id TEXT);
              CREATE TABLE run_activity(run_id TEXT, activity TEXT, recorded_at TEXT, diagnostic_json BLOB);
              CREATE TABLE run_tool_evidence(run_id TEXT, ordinal INTEGER, evidence_key TEXT, record_json BLOB, alias TEXT,
                PRIMARY KEY(run_id,ordinal), UNIQUE(run_id,evidence_key));
            ''')

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _row(self, connection, run_id):
        return connection.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()

    def _append_activity(self, connection, run_id, activity, at, raw):
        connection.execute('INSERT INTO run_activity VALUES (?,?,?,?)', (run_id, activity, at, raw))

    def status(self, run_id):
        with self._connect() as db:
            row = dict(self._row(db, run_id))
        return SimpleNamespace(**row, operation_digest='a' * 64, inputs=self.inputs[run_id],
                               output_ref=self.producers.get(run_id), recovery_policy={})

    def _require_running(self, run_id):
        result = self.status(run_id)
        assert result.state == 'running'
        return result

    def _compiled(self, value):
        return SimpleNamespace(spec=SimpleNamespace(outputs=(), inputs=[SimpleNamespace(name=port, agent_visible=True,
            exposure='handoff_only' if port == 'hidden' else 'full') for port in {i.port_name for i in value.inputs}]))

    def _reference_policy(self, value, policy=None):
        if self.policy is None or policy is not None and policy != self.policy:
            raise ReferenceAccessError('reference_capability_missing', 'missing policy')
        return self.policy

    def recovery_tool_proof(self, value):
        return None

    def _refresh_evidence_schema(self, run_id):
        pass

    def recovery_links(self, run_id):
        value = self.status(run_id)
        return {key: getattr(value, key) for key in ('draft_from_run_id', 'resume_from_run_id')}

    def completed_for_output(self, ref):
        producer = self.producers.get(ref)
        return self.status(producer) if producer else None

    @contextmanager
    def open_original(self, ref):
        yield io.BytesIO(self.contents[ref])

    def read(self, ref):
        return self.contents[ref]

    def artifact(self, content, *, schema='opaque', media='text/plain', parents=(), labels=None):
        raw = content if isinstance(content, bytes) else canonical_json(content)
        ref = ArtifactRef(artifact_id=f'object_{len(self.contents)}', sha256=hashlib.sha256(raw).hexdigest(), kind='fixture', schema_id=schema)
        self.contents[ref] = raw
        self.envelopes[ref] = SimpleNamespace(media_type=media, size_bytes=len(raw), parent_refs=parents, labels=labels or {})
        return ref

    def run(self, name, roots=(), *, parent=None, instance='one', state='running'):
        with self._connect() as db:
            db.execute('INSERT INTO runs VALUES (?,?,?,NULL,?,NULL)', (name, instance, state, parent))
        self.inputs[name] = tuple(SimpleNamespace(source_name=f'root_{i}', port_name='reference_material', artifact_ref=ref) for i, ref in enumerate(roots))
        (self.root / name / 'workspace' / 'inputs').mkdir(parents=True)
        for item in self.inputs[name]:
            (self.root/name/'workspace'/'inputs'/item.source_name).write_bytes(self.contents[item.artifact_ref])
        return name

    def report(self, name, targets, *, document=None, instance='one', records=(), bindings=None):
        self.run(name, instance=instance, state='completed')
        bindings = bindings or {alias: {'artifact_ref': ref.model_dump(mode='json'), 'port_name': 'reference_material'} for alias, ref in targets.items()}
        manifest = self.artifact({'schema_version': 1, 'bindings': bindings, 'records': list(records)},
            schema='scidiscovery.tool-evidence-manifest.v1', media='application/json',
            parents=tuple(targets.values()), labels={'tool_producer_run': name})
        report = self.artifact(document or {'source_references': [{'source_key': alias, 'input_alias': alias} for alias in targets]},
            schema='scidiscovery.layered-diagnosis.v1', media='application/json', parents=(manifest,))
        self.producers[report] = name
        self.producers[name] = report
        for record in records:
            self.producers[ArtifactRef.model_validate(record['artifact_ref'])] = name
        return report

    def call(self, run, **values):
        return self.reference_read(run, ReferenceReadRequest(source='root_0', **values), self.policy)

    def usage(self, run):
        with self._connect() as db:
            return self._reference_usage(db, self._reference_scope(db, run))


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


def prepared(harness, content=b'{"answer":42,"other":"unchanged"}', media='application/json'):
    target = harness.artifact(content, media=media)
    root = harness.report('producer', {'original': target})
    harness.run('reader', [root])
    listed = harness.call('reader', action='list')
    return target, root, listed['references'][0]['reference']


def test_partial_response_exact_identity_idempotent_replay_and_no_publication(harness):
    target, root, handle = prepared(harness)
    assert harness.reference_access_records('reader') == []
    response = harness.call('reader', action='read', reference=handle, pointer='/answer')
    assert response['fragment'] == '42'
    assert response['provided']['pointer'] == '/answer'
    before = harness.usage('reader')
    assert harness.call('reader', action='read', reference=handle, pointer='/answer') == response
    assert len(harness.reference_access_records('reader')) == 1
    assert harness.tool_evidence('reader') == []
    assert harness.usage('reader')['calls'] == before['calls'] + 1
    assert harness.usage('reader')['response_bytes'] > before['response_bytes']
    assert harness.usage('reader')['materials'] == before['materials']
    record = harness.reference_access_records('reader')[0]
    assert ArtifactRef.model_validate(record['artifact_ref']) == target
    assert ArtifactRef.model_validate(record['root_ref']) == root
    assert harness.source_descriptor(harness.status('reader'), response['source']).port_name == 'reference_access'
    assert harness.evidence_sources('reader')[0][response['source']] == harness.contents[target]


def test_precise_handle_cannot_cross_roots_or_instances(harness):
    target, root, handle = prepared(harness)
    other = harness.artifact(b'other')
    second = harness.report('second', {'original': other})
    harness.run('different', [second])
    assert harness.call('different', action='read', reference=handle)['code'] == 'reference_handle_invalid'
    harness.run('foreign', [root], instance='other')
    assert harness.call('foreign', action='list')['code'] == 'reference_instance_mismatch'
    assert not harness.reference_access_records('different')


@pytest.mark.parametrize('locator', ['/summary; /limitations', 'all rows', 'https://example.org/figure'])
def test_in_file_locator_is_not_a_missing_source(harness, locator):
    target = harness.artifact(b'original', media='text/plain')
    root = harness.report('producer', {'data': target}, document={
        'evidence': [{'source_key': 'data', 'locator': locator}]})
    harness.run('reader', [root])
    listed = harness.call('reader', action='list')
    assert len(listed['references']) == 1
    assert listed['references'][0]['alias'] == 'data'
    assert 'error' not in listed['references'][0]
    read = harness.call('reader', action='read', reference=listed['references'][0]['reference'])
    assert read['fragment'] == 'original'


@pytest.mark.parametrize('legacy_path', [False, True])
def test_file_receipts_and_recovery_do_not_persist_delivery_paths(harness, legacy_path):
    target, root, handle = prepared(harness, b'original', 'text/plain')
    first = harness.call('reader', action='read', reference=handle, delivery='file')
    old_path = Path(first['file_path'])
    assert old_path.read_bytes() == harness.contents[target]
    assert 'file_path' not in harness.reference_access_records('reader')[0]['response']
    with harness._connect() as db:
        events = [json.loads(row[0]) for row in db.execute(
            "SELECT diagnostic_json FROM run_activity WHERE activity='reference_read_settled'")]
    assert all('file_path' not in e['response'] for e in events)
    if legacy_path:
        receipt = harness.reference_access_records('reader')[0]
        receipt['response']['file_path'] = first['file_path']
        with harness._connect() as db:
            db.execute('UPDATE run_tool_evidence SET record_json=? WHERE run_id=?',
                       (canonical_json(receipt), 'reader'))
        replay = harness.call('reader', action='read', reference=handle, delivery='file')
        assert replay['file_path'] == first['file_path']
        snapshot = harness._encode_evidence_snapshot(harness.status('reader'), [], [receipt], None, [])
        assert first['file_path'].encode() not in snapshot
    harness.run('continued', [root], parent='reader')
    harness.adopt_reference_access('continued')
    assert 'file_path' not in harness.reference_access_records('continued')[0]['response']
    following = harness.call('continued', action='read', reference=handle, delivery='file')
    assert following['file_path'] != first['file_path']
    assert Path(following['file_path']).read_bytes() == old_path.read_bytes()


def test_control_manifest_fault_is_not_a_worker_output_rejection(tmp_path, monkeypatch):
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, analysis_report
    from tests.operations.test_analysis_claim_scope import submit
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    original = worker.runs._evidence_snapshot
    def invalid_manifest(run_id):
        document = json.loads(original(run_id))
        document['records'] = 'invalid control record collection'
        return canonical_json(document)
    monkeypatch.setattr(worker.runs, '_evidence_snapshot', invalid_manifest)
    assert submit(worker, opened, analysis_report())['state'] == 'failed'
    status = system[2].call_tool('run_status', {'name': 'analysis', 'output_paths': []})
    diagnostic = worker.runs.diagnostic_summary(worker.runs.status(worker._run_id))
    assert diagnostic['rejection_count'] == 0
    assert diagnostic['failure']['category'] == 'checker_failure'
    assert diagnostic['failure']['repairable_by_output'] is False


def test_generic_analysis_accepts_result_material_without_a_fixed_plan_gate(tmp_path):
    from tests.operations.test_tcad_result_analysis import analysis_system
    _, _, root, _, _, _ = analysis_system(tmp_path)
    values = {'name': 'generic_relationship_probe', 'operation_id': 'science.result.diagnose.v1',
              'instruction': 'Diagnose the supplied observations and their limitations.',
              'inputs': [{'port': 'experiment_results', 'artifact_names': ['output_A']}]}
    assert root.call_tool('operation_preflight', values)['admissible']
    assert root.call_tool('operation_invoke', values)['result']['state'] == 'queued'


def test_encoded_response_limit_unicode_and_distinct_ranges(harness):
    _, _, handle = prepared(harness, ('汉字' * 2000).encode(), 'text/plain')
    first = harness.call('reader', action='read', reference=handle, limit=512)
    assert len(canonical_json(first)) <= 512
    assert first['omitted'] and first['next_offset'] > 0
    second = harness.call('reader', action='read', reference=handle, limit=512, offset=first['next_offset'])
    assert second['source'] == first['source']
    assert len(harness.reference_access_records('reader')) == 2


def test_same_request_concurrency_has_one_fact_but_both_io_costs(harness):
    target, root, handle = prepared(harness)
    barrier = Barrier(2)
    original = harness.artifacts.read
    def read(ref):
        if ref == target:
            barrier.wait(timeout=5)
        return original(ref)
    harness.artifacts.read = read
    before = harness.usage('reader')
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: harness.call('reader', action='read', reference=handle), range(2)))
    assert replies[0] == replies[1]
    assert len(harness.reference_access_records('reader')) == 1
    after = harness.usage('reader')
    assert after['calls'] == before['calls'] + 2
    assert sum(after['materials'].values()) == len(harness.contents[target])
    assert after['io_bytes'] - before['io_bytes'] >= 2 * len(harness.contents[target])


@pytest.mark.parametrize('state,accepted', [('cancelled', None), ('running', 'sealed')])
def test_cancel_or_seal_wins_before_commit_no_access_source(harness, state, accepted):
    target, _, handle = prepared(harness)
    original = harness.artifacts.read
    def read(ref):
        result = original(ref)
        if ref == target:
            with harness._connect() as db:
                db.execute('UPDATE runs SET state=?,accepted_candidate_digest=? WHERE run_id=?', (state, accepted, 'reader'))
        return result
    harness.artifacts.read = read
    response = harness.call('reader', action='read', reference=handle)
    assert response['state'] == 'rejected'
    assert harness.reference_access_records('reader') == []
    assert harness.usage('reader')['io_bytes'] > 0


def test_recovery_keeps_root_permissions_and_scope_budget(harness):
    target, root, handle = prepared(harness)
    original = harness.call('reader', action='read', reference=handle)
    harness.run('continued', [root], parent='reader')
    harness.adopt_reference_access('continued')
    records = harness.reference_access_records('continued')
    assert records and records[0]['alias'] == original['source']
    assert records[0]['artifact_ref'] == target.model_dump(mode='json')
    assert harness.usage('continued') == harness.usage('reader')
    harness.run('lost_root', [], parent='continued')
    harness.adopt_reference_access('lost_root')
    assert not harness.reference_access_records('lost_root')
    assert harness.usage('lost_root') == harness.usage('reader')
    harness.run('lost_capability', [root], parent='continued')
    harness.policy = None
    harness.adopt_reference_access('lost_capability')
    assert not harness.reference_access_records('lost_capability')


def test_pending_reservation_and_unique_material_budget_survive_recovery(harness):
    target, root, handle = prepared(harness)
    value = harness.status('reader')
    harness._reference_reserve(value, ReferenceReadRequest(source='root_0'), harness.policy)
    harness.run('continued', [root], parent='reader')
    harness.policy = replace(harness.policy, max_calls=2)
    denied = harness.call('continued', action='read', reference=handle)
    assert denied['code'] == 'reference_budget_exhausted'
    assert not harness.reference_access_records('continued')


def test_independent_scopes_charge_same_ref_independently(harness):
    target, root, handle = prepared(harness)
    harness.run('independent', [root])
    harness.call('reader', action='read', reference=handle)
    harness.call('independent', action='read', reference=handle)
    assert sum(harness.usage('reader')['materials'].values()) == len(harness.contents[target])
    assert sum(harness.usage('independent')['materials'].values()) == len(harness.contents[target])


def test_binary_committed_response_survives_publish_interruption(harness, monkeypatch):
    target, _, handle = prepared(harness, b'\x00\xffbinary', 'application/octet-stream')
    publish = harness._reference_publish_file
    monkeypatch.setattr(harness, '_reference_publish_file', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('fixture interruption')))
    failed = harness.call('reader', action='read', reference=handle)
    assert failed['state'] == 'rejected'
    records = harness.reference_access_records('reader')
    assert len(records) == 1
    assert 'file_path' not in records[0]['response']
    assert not (harness.backend.open('reader').root / '.reference-access' / (records[0]['alias'] + '.bin')).exists()
    monkeypatch.setattr(harness, '_reference_publish_file', publish)
    recovered = harness.call('reader', action='read', reference=handle)
    assert Path(recovered['file_path']).read_bytes() == harness.contents[target]
    assert len(harness.reference_access_records('reader')) == 1


def test_binary_unavailable_backend_does_not_create_source(harness):
    _, _, handle = prepared(harness, b'\x00\xffbinary', 'application/octet-stream')
    harness.backend.capabilities = ()
    denied = harness.call('reader', action='read', reference=handle)
    assert denied['code'] == 'binary_file_access_unavailable'
    assert harness.reference_access_records('reader') == []


def test_binary_cancellation_never_exposes_staged_file(harness):
    target, _, handle = prepared(harness, b'\x00\xffbinary', 'application/octet-stream')
    original = harness.artifacts.open_original
    @contextmanager
    def read(ref):
        with original(ref) as stream:
            if ref == target:
                with harness._connect() as db:
                    db.execute("UPDATE runs SET state='cancelled' WHERE run_id='reader'")
            yield stream
    harness.artifacts.open_original = read
    assert harness.call('reader', action='read', reference=handle)['state'] == 'rejected'
    assert not list((harness.root / 'reader/workspace/.reference-access').glob('*'))
    # Exact authorization survives, but the interrupted file is never exposed.
    assert len(harness.reference_access_records('reader')) == 1


def test_material_limit_and_same_bytes_different_refs_are_not_deduplicated(harness):
    first = harness.artifact(b'same')
    second = harness.artifact(b'same')
    root = harness.report('producer', {'first': first, 'second': second})
    harness.run('reader', [root])
    references = harness.call('reader', action='list')['references']
    harness.policy = replace(harness.policy, max_unique_bytes=4)
    assert 'fragment' in harness.call('reader', action='read', reference=references[0]['reference'])
    rejected = harness.call('reader', action='read', reference=references[1]['reference'])
    assert rejected['code'] == 'reference_material_limit'
    assert len(harness.reference_access_records('reader')) == 1


def test_unsealed_and_unpaired_manifest_roots_fail_closed(harness):
    target = harness.artifact(b'content')
    root = harness.report('producer', {'input': target})
    harness.run('reader', [root])
    with harness._connect() as db:
        db.execute("UPDATE runs SET state='running' WHERE run_id='producer'")
    missing = harness.call('reader', action='list')
    assert missing['code'] == 'reference_producer_missing'
    assert Path(missing['original_access']['file_path']).is_file()
    assert 'no exact completed producer' in missing['message']
    with harness._connect() as db:
        db.execute("UPDATE runs SET state='completed' WHERE run_id='producer'")
    manifest = harness.envelopes[root].parent_refs[0]
    harness.envelopes[manifest].parent_refs = ()
    unpaired = harness.call('reader', action='list')
    assert unpaired['code'] == 'reference_manifest_unpaired'
    assert unpaired['message'] == 'Manifest binding is not an exact manifest parent.'
    assert Path(unpaired['original_access']['file_path']).read_bytes() == harness.contents[root]
    assert not harness.reference_access_records('reader')


def test_binding_count_is_checked_before_committing_access(harness):
    _, root, handle = prepared(harness)
    harness.inputs['reader'] = tuple(SimpleNamespace(source_name=f'root_{index}', port_name='reference_material', artifact_ref=root)
                                     for index in range(128))
    response = harness.call('reader', action='read', reference=handle)
    assert response['state'] == 'rejected'
    assert 'binding limit' in response['message']
    assert not harness.reference_access_records('reader')


def test_adoption_retains_committed_fact_when_worker_call_budget_is_exhausted(harness):
    harness.policy = replace(harness.policy, max_calls=2)
    _, root, handle = prepared(harness)
    response = harness.call('reader', action='read', reference=handle)
    before = harness.usage('reader')
    harness.run('continued', [root], parent='reader')
    harness.adopt_reference_access('continued')
    assert harness.reference_access_records('continued')[0]['alias'] == response['source']
    assert harness.usage('continued') == before
    assert harness.call('continued', action='read', reference=handle)['code'] == 'reference_budget_exhausted'


def test_hidden_input_cannot_be_selected_by_guessing_its_alias(harness):
    _, _, _ = prepared(harness)
    harness.inputs['reader'][0].port_name = 'hidden'
    response = harness.call('reader', action='list')
    assert response['code'] == 'reference_source_unknown'
    assert not harness.reference_access_records('reader')


def test_same_ref_reuses_visible_input_alias_and_preserves_its_port(harness):
    target, root, handle = prepared(harness)
    harness.inputs['reader'] += (SimpleNamespace(source_name='existing', port_name='reference_material', artifact_ref=target),)
    response = harness.call('reader', action='read', reference=handle)
    assert response['source'] == 'existing'
    descriptor = harness.source_descriptor(harness.status('reader'), 'existing')
    assert descriptor.port_name == 'reference_material'
    snapshot = json.loads(harness._encode_evidence_snapshot(harness.status('reader'), [], harness.reference_access_records('reader'), None, []))
    assert snapshot['bindings']['existing']['port_name'] == 'reference_material'
    assert len([item for item in snapshot['bindings'].values() if item['artifact_ref'] == target.model_dump(mode='json')]) == 1


def test_two_roots_to_same_ref_keep_distinct_paths_and_one_alias(harness):
    target, root, handle = prepared(harness)
    second = harness.report('second_producer', {'input': target})
    harness.inputs['reader'] += (SimpleNamespace(source_name='other_root', port_name='reference_material', artifact_ref=second),)
    first = harness.call('reader', action='read', reference=handle)
    listed = harness.reference_read('reader', ReferenceReadRequest(source='other_root'), harness.policy)
    other = harness.reference_read('reader', ReferenceReadRequest(source='other_root', action='read', reference=listed['references'][0]['reference']), harness.policy)
    assert first['source'] == other['source']
    records = harness.reference_access_records('reader')
    assert len(records) == 2 and records[0]['root_ref'] != records[1]['root_ref']


def test_text_original_can_be_requested_as_exact_native_file(harness):
    target, _, handle = prepared(harness, b'x,y\n1,2\n3,4\n', 'text/csv')
    response = harness.call('reader', action='read', reference=handle, delivery='file')
    assert 'fragment' not in response
    assert response['provided']['kind'] == 'file_access'
    assert Path(response['file_path']).read_bytes() == harness.contents[target]
    record = harness.reference_access_records('reader')[0]
    assert record['selector']['delivery'] == 'file'
    assert record['artifact_ref'] == target.model_dump(mode='json')


@pytest.mark.parametrize('selector', [{'pointer': '/answer'}, {'offset': 1}])
def test_full_file_delivery_rejects_partial_selectors(selector):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReferenceReadRequest(source='root', action='read', reference='handle', delivery='file', **selector)


def test_review_new_router_requires_explicit_running_or_queued_recovery(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter, WorkerToolError
    from tests.operations.test_r4_experiment_task import _real_experiment

    runtime, root, catalog, _, _ = _real_experiment(tmp_path, monkeypatch)
    operation = catalog.operation('science.object.review.v1')
    assert any(tool.reference_policy is not None for tool in operation.worker_tools)
    assert any(tool.name == "worker_publish_files" for tool in operation.worker_tools)
    assert any(port.name == 'recovery_manifest_output' for port in operation.spec.outputs)
    request = dict(name='reference_only_review', operation_id=operation.spec.operation_id,
        instruction='Review the bounded fixture plan.',
        inputs=[dict(port='subject', artifact_names=['observe.output'])])
    root.call_tool('operation_invoke', request)

    def router(**values):
        return LocalWorkerMCPRouter(runtime.runs, operation_id=operation.spec.operation_id,
            operation_digest=operation.digest, **values)

    from tests.operations.worker_fixtures import attached_worker
    first = attached_worker(runtime, root, 'reference_only_review')
    opened = first.call_tool('worker_open_assignment', {})
    original_id = first._run_id
    fresh = router()
    with pytest.raises(WorkerToolError, match='trusted gateway caller'):
        fresh.call_tool('worker_open_assignment', {})
    assert fresh._run_id is None
    assert runtime.runs.status(original_id).state == 'running'

    # A trusted explicit Run binding retains the existing reattachment path.
    attached = attached_worker(runtime, root, 'reference_only_review')
    reattached = attached.call_tool('worker_open_assignment', {})
    assert attached._run_id == original_id
    assert reattached['workspace_path'] == opened['workspace_path']

    # Explicit scheduler recovery creates a queued successor; it remains openable
    # without granting a fresh unbound router permission to take the running Run.
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json(dict(
        schema_version=1, handoff=dict(verdict='pass', summary='Bounded review draft.'),
        payload=dict(review_target='experiment_portfolio', verdict='pass', summary='Bounded review draft.'))))
    status = runtime.runs.status(original_id)
    runtime.runs.record_failure(original_id, reason='Fixture interruption before submission.',
        expected_state='running', expected_last_activity_at=status.last_activity_at)
    # The fixture explicitly grants a second attempt through the public scheduler
    # request; the review Operation's default one-attempt limit stays unchanged.
    root.call_tool('operation_invoke', {**request, 'name': 'reference_only_recovered',
        'resume_from': 'reference_only_review', 'max_attempts': 2})
    recovered = attached_worker(runtime, root, 'reference_only_recovered')
    assert recovered.call_tool('worker_open_assignment', {})['state'] == 'opened'
    assert recovered._run_id != original_id
    assert runtime.runs.recovery_links(recovered._run_id)['resume_from_run_id'] == original_id
