"""Managed delivery uses sealed public call originals, never mutable current files."""
import copy
import json
from pathlib import Path
import shutil
import sys

import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, cov_delivery, cov_lineage, delivery
from test_cov_lineage import BACKEND
from test_delivery import FAKE_HARNESS, descriptor, delivery_policy, prepare_fixture
from test_history_handoff import finish


def managed_scene(tmp_path, *, alias_correct=True):
    if shutil.which('bwrap') is None:
        pytest.skip('Actual namespace lane required')
    root, public = tmp_path / 'instance', tmp_path / 'public'
    (public / 'harness').mkdir(parents=True)
    for name in ('exp_cli.py', 'runner.py', 'train.csv', 'val.csv', 'meta.json'):
        path = public / 'harness' / name
        if name == 'exp_cli.py':
            path.write_text(FAKE_HARNESS)
        elif name == 'meta.json':
            c.write(path, dict(mode='ok', control_path=str(root / 'settings.json'), hidden_path=str(tmp_path / 'hidden-never-mounted')))
        else:
            path.write_text('Public fixture only\n')
    objective = public / 'objective.md';objective.write_text('Deliver the exact public scientific candidate.')
    spec = descriptor(root, public)
    spec['config']['namespace_runs'] = str(root / 'runs') if alias_correct else '/opt/exp/runs'
    controller.prepare(root, objective, public, ['fake-no-model'], max_tokens=100000, max_seconds=300, max_steps=12,
        model='fixture', reasoning_effort='high', search_policy=None,
        node_budget_policy={role: dict(max_observed_tokens=2000, max_seconds=60) for role in ('H','W','A','E')},
        delivery_policy=delivery_policy(spec),
        history_observer=dict(contract_version=2, adapter=str(Path(cov_lineage.__file__).absolute()),
            config=dict(runs='runs', calls='project/nodes', evaluation_key='covshift-public-val-v1')))
    (root / 'runs').mkdir();(root / 'submission').mkdir()
    finish(root, 1, 'H', [], action='experiment')
    c.build_job(root, 2, 'W', [1])
    record = c.host_record(c.workspace(root, 2))
    c.write(record / 'native-intent.json', dict(task_sha256=c.digest(root / 'jobs/002.json')))
    backend = tmp_path / 'backend.py';backend.write_text(BACKEND)
    config_path = tmp_path / 'config.json'
    cov_lineage.configure(root, 2, [sys.executable, str(backend), '--runs-root', str(root / 'runs')], root / 'runs', config_path)
    config, digest = cov_lineage._config(config_path)
    script = c.workspace(root, 2) / 'work/train.py'
    script.write_text(json.dumps(dict(mode='success', revision='P')))
    first = cov_lineage.run(config, digest, script, new=True)
    source_p = script.read_bytes();model_p = Path(first['model']['path']).read_bytes()
    script.write_text(json.dumps(dict(mode='success', revision='Q')))
    second = cov_lineage.run(config, digest, script, parent=first['candidate_id'])
    finish(root, 2, 'W', [1])
    c.write(root / 'host-started.json', budget.clock_stamp())
    budget.transition(root, 'advance', 'Bounded delivery preparation')
    nodes = [dict(step=step, seal_sha256=c.digest(c.host_record(c.workspace(root, step)) / 'result-identity.json')) for step in (1,2)]
    return root, nodes, first, second, script, source_p, model_p


def test_real_resolver_uses_p_archives_after_same_script_model_and_calls_change(tmp_path):
    root, nodes, first, _, script, source_p, model_p = managed_scene(tmp_path)
    script.write_text('Current script is no longer the original P implementation\n')
    (root / 'runs/model_run1.pkl').write_bytes(b'current model is not P')
    call_source = Path(first['model']['path']).parent / 'source.py'
    call_source.chmod(0o600);call_source.write_text('Changed current call bundle')
    refs = delivery.freeze_sources(root, nodes)  # Actual task-Python bwrap leaf, no package import.
    chosen = next(item for item in refs['items'] if item['candidate_id'] == first['candidate_id'])
    assert chosen['status'] == 'audit_pending'
    assert (root / chosen['objects']['source.py']['path']).read_bytes() == source_p
    assert (root / chosen['objects']['artifact']['path']).read_bytes() == model_p
    assert chosen['context']['identity_note'].startswith('Exact sealed managed')


def test_absolute_namespace_alias_mismatch_is_unavailable_not_wrong_candidate(tmp_path):
    root, nodes, *_ = managed_scene(tmp_path, alias_correct=False)
    refs = delivery.freeze_sources(root, nodes)
    assert refs['items'] and all(item['status'] == 'unavailable' for item in refs['items'])


def test_archived_original_hash_tamper_is_hard_before_resolver(tmp_path):
    root, nodes, first, *_ = managed_scene(tmp_path)
    seal = c.read(c.host_record(c.workspace(root, 2)) / 'result-identity.json')
    observation = c.read(root / seal['observations']['path'])
    context = next(item for item in observation['contexts'] if item['candidate_id'] == first['candidate_id'])
    proof = next(item for item in context['proofs'] if Path(item['path']).name == 'source.py')
    archived = root / proof['snapshot'];archived.chmod(0o600);archived.write_bytes(b'tampered archive')
    with pytest.raises(ValueError, match='Archived observer original changed'):
        delivery.freeze_sources(root, nodes)


@pytest.mark.parametrize('kind', ['missing', 'ambiguous', 'unknown', 'unretained'])
def test_managed_context_problem_never_falls_back_to_current_source(kind):
    proof = dict(name='source.py', sha256='a'*64, size_bytes=1, retention='digest_only', input_label=None)
    context = dict(candidate_id='run-1', run_id=1, status='known_success',
        proofs=[proof, dict(proof, name='model.pkl'), dict(proof, name='row.json')], model=dict(proof, name='model.pkl'))
    contexts = [context]
    if kind == 'missing':contexts = []
    if kind == 'ambiguous':contexts = [context, copy.deepcopy(context)]
    if kind == 'unknown':context['status'] = 'unknown'
    with pytest.raises(cov_delivery.SourceUnavailable):
        cov_delivery.managed_objects(dict(candidate_id='run-1', execution_contexts=contexts), dict(run_id=1))


def test_legacy_v1_snapshot_is_explicitly_limited_and_still_works(tmp_path):
    root, _, nodes = prepare_fixture(tmp_path)
    refs = delivery.freeze_sources(root, nodes)
    assert refs['items'][0]['status'] == 'audit_pending'
    assert refs['items'][0]['context']['identity_note'].startswith('Legacy current-source snapshot')
