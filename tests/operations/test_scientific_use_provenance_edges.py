"""Actual stage/final/admission paths with bounded direct-edge reuse."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.scientific_usage import (
    EDGE_ACTIVITY, ScientificProvenanceError, scientific_use_restricted,
)
from scidiscovery.reference_tools import ReferencePolicy
from tests.operations.test_scientific_use_provenance_continuation import (
    OBJECTIVE, system, _register, artifact, consume,
)
from tests.operations.worker_fixtures import attached_worker


def experiment(runtime, instance, root, name, *, prior=None, restricted=False, stages=1):
    inputs = [{'port': 'subject', 'artifact_names': ['objective.hypothesis.output']}]
    materials = ([prior] if prior else []) + (['restricted'] if restricted else [])
    if materials:
        inputs.append({'port': 'scientific_materials', 'artifact_names': materials})
    root.call_tool('operation_invoke', {'name': name, 'operation_id': 'science.experiment.v1',
        'instruction': 'Preserve the exact adopted source chain.', 'inputs': inputs})
    worker = attached_worker(runtime, root, name)
    opened = worker.call_tool('worker_open_assignment', {})
    run = runtime.runs.status(worker._run_id)
    prior_ref = artifact(runtime, instance, prior).ref if prior else None
    prior_alias = next((i.source_name for i in run.inputs if i.artifact_ref == prior_ref), None)
    source = prior_alias or next(i.source_name for i in run.inputs if i.port_name == 'subject')
    restricted_alias = next((i.source_name for i in run.inputs if i.artifact_ref == artifact(runtime, instance, 'restricted').ref), None)
    for number in range(stages):
        sources = [source] + ([restricted_alias] if restricted and number == stages - 1 else [])
        result = worker.call_tool('worker_experiment_stage', {'stage': 'design',
            'conclusion': 'One bounded conditional design.', 'materials': sources})
        source = result['reference']
    Path(opened['output_directory'], 'result.json').write_bytes(canonical_json({'payload': {
        'summary': 'Adopt this exact chain, without claiming experiment execution.',
        'outcome': 'inconclusive', 'remaining_question': 'Execution remains needed.',
        'adopted_stages': [source]}}))
    assert worker.call_tool('worker_submit_result', {})['state'] == 'completed'
    return artifact(runtime, instance, name + '.output').ref


def setup(runtime, instance, root):
    from tests.operations.scientific_chain_fixtures import sealed_hypothesis
    _register(runtime, instance, name='objective', raw=canonical_json(OBJECTIVE), kind='research_objective',
        schema='scidiscovery.research-objective.v1')
    sealed_hypothesis(runtime, root, instance, 'objective')
    _register(runtime, instance, name='restricted', raw=b'restricted origin', kind='source',
        schema='opaque', media_type='text/plain', provisional=True)


def edges(runs):
    with runs._connect() as connection:
        return [tuple(row) for row in connection.execute(
            'SELECT rowid,run_id,diagnostic_json FROM run_activity WHERE activity=? ORDER BY rowid',
            (EDGE_ACTIVITY,))]


@pytest.mark.parametrize('restricted', [False, True])
def test_actual_stage_final_admission_long_chain_cold_warm_restart(tmp_path, monkeypatch, restricted):
    from scidiscovery.artifact_agent.service.runs import RunService
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    outputs, prior = [], None
    # Four tasks stay under per-task receipt AND attempt contracts, while the
    # adopted scientific closure crosses the old cumulative 128-object bound.
    for number in range(4):
        name = f'chain{number}'
        outputs.append(experiment(runtime, instance, root, name, prior=prior,
                                  restricted=restricted and number == 3, stages=33))
        prior = name + '.output'
    retained = edges(runtime.runs)
    assert len(retained) >= 136  # 132 stage receipts plus four primary outputs.
    # Ignore propagated own labels so even the restricted case traverses every
    # exact adopted edge and reaches the original restricted source.
    ignored = tuple(ArtifactRef.model_validate(json.loads(row[2])['artifact_ref']) for row in retained)
    original_read = runtime.artifacts.read
    def no_primary_reads(ref):
        assert ref not in outputs, 'Warm direct-edge reuse reread a primary body'
        return original_read(ref)
    with monkeypatch.context() as patch:
        patch.setattr(runtime.artifacts, 'read', no_primary_reads)
        assert scientific_use_restricted(runtime.runs, (outputs[-1],), ignore_labels=ignored) is restricted
        assert consume(root, prior, 'experiment')['admissible'] is not restricted
    assert edges(runtime.runs) == retained  # Query/preflight creates no control rows.
    previous = runtime.runs
    restarted = RunService(artifacts=previous.artifacts, database_path=previous.database_path,
        service_actor=previous.service_actor, operation_catalog=previous.operation_catalog,
        backend=previous.backend, scheduler_bindings=previous.scheduler_bindings)
    assert scientific_use_restricted(restarted, (outputs[-1],), ignore_labels=ignored) is restricted
    with restarted._connect() as connection:
        connection.execute('DELETE FROM run_activity WHERE activity=?', (EDGE_ACTIVITY,))
    assert scientific_use_restricted(restarted, (outputs[-1],), ignore_labels=ignored) is restricted
    assert not edges(restarted)
    assert consume(root, prior, 'experiment')['admissible'] is not restricted
    if not restricted:
        assert consume(root, prior, 'experiment', 'operation_invoke')['result']['state'] == 'queued'


@pytest.mark.parametrize('budget', ['bytes', 'time'])
def test_cold_budget_exhaustion_never_claims_clear(tmp_path, monkeypatch, budget):
    from scidiscovery.artifact_agent.service import scientific_usage
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    ref = experiment(runtime, instance, root, 'bounded')
    policy = ReferencePolicy()
    if budget == 'bytes':
        policy = replace(policy, max_unique_bytes=0)
    else:
        policy = replace(policy, max_io_seconds=0)
    before = edges(runtime.runs)
    with pytest.raises(ScientificProvenanceError, match='bound'):
        scientific_use_restricted(runtime.runs, (ref,), policy=policy)
    assert edges(runtime.runs) == before


def test_ancestor_receipt_missing_cannot_be_hidden_by_root_direct_edges(tmp_path):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    first = experiment(runtime, instance, root, 'first')
    final = experiment(runtime, instance, root, 'final', prior='first.output')
    assert scientific_use_restricted(runtime.runs, (final,)) is False
    producer = runtime.runs.completed_for_output(first)
    with runtime.runs._connect() as connection:
        connection.execute('DELETE FROM run_tool_evidence WHERE run_id=?', (producer.run_id,))
    with pytest.raises(ScientificProvenanceError, match='unique exact producer receipt'):
        scientific_use_restricted(runtime.runs, (final,))


def test_record_identity_corruption_does_not_create_clear(tmp_path):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    ref = experiment(runtime, instance, root, 'corrupt')
    row = next(row for row in edges(runtime.runs) if json.loads(row[2])['artifact_ref'] == ref.model_dump(mode='json'))
    document = json.loads(row[2])
    document['artifact_ref']['artifact_id'] = 'wrong-exact-object'
    with runtime.runs._connect() as connection:
        connection.execute('UPDATE run_activity SET diagnostic_json=? WHERE rowid=?',
                           (canonical_json(document), row[0]))
    with pytest.raises(ScientificProvenanceError, match='invalid'):
        scientific_use_restricted(runtime.runs, (ref,))


@pytest.mark.parametrize('identity', ['policy', 'catalog'])
def test_current_rule_identity_miss_uses_cold_parsing(tmp_path, monkeypatch, identity):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    ref = experiment(runtime, instance, root, 'identity')
    before = edges(runtime.runs)
    reads, read = [], runtime.artifacts.read
    def observed(ref):
        reads.append(ref)
        return read(ref)
    monkeypatch.setattr(runtime.artifacts, 'read', observed)
    policy = ReferencePolicy()
    if identity == 'policy':
        policy = replace(policy, max_calls=127)
    else:
        monkeypatch.setattr(type(runtime.runs.operation_catalog),
                            'scientific_provenance_digest', lambda self: 'changed-current-history-catalog')
    assert scientific_use_restricted(runtime.runs, (ref,), policy=policy) is False
    assert ref in reads
    assert edges(runtime.runs) == before


def test_ignore_labels_is_applied_per_invocation_not_cached_as_a_verdict(tmp_path):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    ref = experiment(runtime, instance, root, 'ignore', restricted=True)
    cached_refs = tuple(ArtifactRef.model_validate(json.loads(row[2])['artifact_ref'])
                       for row in edges(runtime.runs))
    source = artifact(runtime, instance, 'restricted').ref
    assert scientific_use_restricted(runtime.runs, (ref,), ignore_labels=(ref,)) is True
    assert scientific_use_restricted(runtime.runs, (ref,), ignore_labels=(*cached_refs, source)) is False
    assert scientific_use_restricted(runtime.runs, (ref,), ignore_labels=cached_refs) is True


@pytest.mark.parametrize('fault', ['duplicate', 'oversized'])
def test_optional_cache_size_misses_but_ambiguous_identity_fails(tmp_path, fault):
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    ref = experiment(runtime, instance, root, 'damaged')
    row = next(row for row in edges(runtime.runs) if json.loads(row[2])['artifact_ref'] == ref.model_dump(mode='json'))
    with runtime.runs._connect() as connection:
        if fault == 'duplicate':
            connection.execute('INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) '
                'SELECT run_id,activity,recorded_at,diagnostic_json FROM run_activity WHERE rowid=?', (row[0],))
        else:
            connection.execute('UPDATE run_activity SET diagnostic_json=? WHERE rowid=?',
                               (b' ' * (1024 * 1024 + 1), row[0]))
    if fault == 'duplicate':
        with pytest.raises(ScientificProvenanceError, match='ambiguous'):
            scientific_use_restricted(runtime.runs, (ref,))
    else:
        assert scientific_use_restricted(runtime.runs, (ref,)) is False



def test_recent_owner_collections_are_released_and_reloads_consume_budget(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service import scientific_usage
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    first = experiment(runtime, instance, root, 'recent_first', restricted=True)
    second = experiment(runtime, instance, root, 'recent_second', prior='recent_first.output')
    ids = [runtime.runs.completed_for_output(ref).run_id for ref in (first, second)]
    probe = scientific_usage._Check(runtime.runs, ReferencePolicy())
    for run_id in ids:
        probe.bindings(probe.producer(run_id))
    # This deliberately tiny *live owner cache* still accommodates either exact
    # owner separately. It must evict an old collection, not reject total history.
    limit = max(probe.owner_sizes.values())
    check = scientific_usage._Check(runtime.runs, ReferencePolicy())
    check.owner_limit = limit
    for run_id in ids:
        check.bindings(check.producer(run_id))
    assert ids[0] not in check.producers and ids[0] not in check.receipts and ids[0] not in check.aliases
    remaining = check.remaining_bytes
    check.bindings(check.producer(ids[0]))
    assert ids[1] not in check.producers and ids[1] not in check.receipts and ids[1] not in check.aliases
    assert check.remaining_bytes < remaining
    original_init = scientific_usage._Check.__init__
    original_retain = scientific_usage._Check.retain_owner
    evicted = set()
    def small_recent_cache(self, runs, limits):
        original_init(self, runs, limits)
        self.owner_limit = limit
    def observe_eviction(self, run_id, size):
        before = set(self.owner_sizes)
        original_retain(self, run_id, size)
        evicted.update(before - self.owner_sizes.keys())
    monkeypatch.setattr(scientific_usage._Check, '__init__', small_recent_cache)
    monkeypatch.setattr(scientific_usage._Check, 'retain_owner', observe_eviction)
    ignored = tuple(ArtifactRef.model_validate(json.loads(row[2])['artifact_ref'])
                    for row in edges(runtime.runs))
    assert scientific_use_restricted(runtime.runs, (second,), ignore_labels=ignored) is True
    assert ids[1] in evicted  # Restriction is reached through the previous owner.


@pytest.mark.parametrize('kind', ['tool', 'access'])
def test_receipt_collection_snapshot_does_not_expand_during_legal_append(tmp_path, monkeypatch, kind):
    import threading
    from scidiscovery.artifact_agent.service.scientific_usage import _Check
    if kind == 'tool':
        from tests.operations.test_scientific_use_provenance import system as evidence_system
        runtime, _, worker, _, aliases = evidence_system(tmp_path)
        source = aliases['source_material']
        def append(number):
            return runtime.runs.accept_tool_evidence(worker._run_id, tool_name='fixture_derived',
                allowed_ports=('tool_evidence',), raw=b'x,y\n1,2\n', media_type='text/csv',
                metadata={'kind': 'fixture', 'round': number, 'note': '\u00e9' * 100}, derived_from=(source,))
        append(1)
        write = lambda: append(2)
    else:
        from tests.operations.test_scientific_attachments import publish_fixture, finish, audit_worker
        _, runtime, root, original, opened, _, _, _, _, args = publish_fixture(tmp_path)
        args['files'] = args['files'][:1]
        saved = original.call_tool('worker_publish_files', args)
        assert finish(original, opened, saved['files'][0]['reference'])['state'] == 'completed'
        worker, source = audit_worker(root, runtime)
        listed = worker.call_tool('worker_reference_read', {'source': source})
        write = lambda: worker.call_tool('worker_reference_read', {'source': source, 'action': 'read',
            'reference': listed['references'][0]['reference'], 'delivery': 'file'})
    runs, run_id = runtime.runs, worker._run_id
    with runs._connect() as connection:
        before = connection.execute('SELECT COALESCE(sum(length(CAST(record_json AS BLOB))),0) '
                                    'FROM run_tool_evidence WHERE run_id=?', (run_id,)).fetchone()[0]
    checker = _Check(runs, replace(ReferencePolicy(), max_unique_bytes=before, max_io_bytes=before))
    ready, release, inserted = threading.Event(), threading.Event(), threading.Event()
    result, errors, forbidden_fetch = [], [], [False]
    original_connect = runs._connect
    writer = None
    class Connection:
        def __init__(self, connection):
            self.connection = connection
        def __enter__(self):
            self.connection.__enter__()
            return self
        def __exit__(self, *args):
            return self.connection.__exit__(*args)
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def execute(self, sql, parameters=()):
            if threading.current_thread() is writer and sql.startswith('INSERT INTO run_tool_evidence'):
                ready.set()
                assert release.wait(10), 'Reader never reached its length-checked snapshot'
                cursor = self.connection.execute(sql, parameters)
                inserted.set()
                return cursor
            if threading.current_thread() is not writer and forbidden_fetch[0]:
                assert not sql.startswith('SELECT record_json FROM run_tool_evidence'), 'Budget failure fetched JSON'
            return self.connection.execute(sql, parameters)
    monkeypatch.setattr(runs, '_connect', lambda: Connection(original_connect()))
    original_budget = checker.budget
    def budget(size=0):
        original_budget(size)
        if not release.is_set():
            release.set()
            assert inserted.wait(10), 'Legal writer did not insert before the body query'
    monkeypatch.setattr(checker, 'budget', budget)
    def write_in_thread():
        try:
            result.append(write())
        except BaseException as error:
            errors.append(error)
            ready.set()
    writer = threading.Thread(target=write_in_thread)
    writer.start()
    try:
        assert ready.wait(10), 'Legal writer did not reach its receipt insertion'
        assert not errors
        snapshot = checker.records(run_id)
        assert sum(len(canonical_json(record)) for record in snapshot) == before
        assert checker.remaining_bytes == 0
    finally:
        release.set()
        writer.join(15)
    assert not writer.is_alive() and not errors and result
    assert kind == 'tool' or result[0].get('state') != 'rejected'
    fresh = _Check(runs, replace(ReferencePolicy(), max_unique_bytes=before, max_io_bytes=before))
    forbidden_fetch[0] = True
    with pytest.raises(ScientificProvenanceError, match='byte bound'):
        fresh.records(run_id)  # Newly committed collection fails before fetching/parsing any JSON.


@pytest.mark.parametrize('carrier', ['unused', 'inputs'])
def test_owner_projection_guards_needed_bytes_without_hydrating_unrelated_carriers(tmp_path, monkeypatch, carrier):
    from scidiscovery.artifact_agent.service.scientific_usage import _Check
    runtime, instance, root = system(tmp_path)
    setup(runtime, instance, root)
    ref = experiment(runtime, instance, root, 'projection')
    run_id = runtime.runs.completed_for_output(ref).run_id
    with runtime.runs._connect() as connection:
        if carrier == 'unused':
            connection.execute('UPDATE runs SET recovery_draft_json=?,execution_profile_json=?,signal_json=? '
                'WHERE run_id=?', (b'unparsed recovery' * 200000, b'unparsed settings' * 200000,
                                  b'unparsed approval/signal' * 200000, run_id))
        else:
            connection.execute('UPDATE runs SET inputs_json=? WHERE run_id=?',
                               (b'invalid input JSON' * 100000, run_id))
    monkeypatch.setattr(runtime.runs, 'status', lambda *args: pytest.fail('Checker hydrated full RunStatus'))
    monkeypatch.setattr(runtime.runs, 'completed_for_output', lambda *args: pytest.fail('Checker used full output owner lookup'))
    if carrier == 'unused':
        assert scientific_use_restricted(runtime.runs, (ref,)) is False
    else:
        with pytest.raises(ScientificProvenanceError, match='owner projection is malformed'):
            _Check(runtime.runs, ReferencePolicy()).producer(run_id)
