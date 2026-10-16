"""Generic task execution/result/artifact handoff, using real CLIs and no models."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

from execution_fixtures import execution_registry
from scidiscovery.research_loop import budget, contracts as c, controller, delivery, generic_delivery

FIXTURE = Path(__file__).parents[1] / 'fixtures/generic_inverse'


def generic_case(tmp_path, monkeypatch, deliver=True, max_steps=5, observer=None):
    public = tmp_path / 'public'
    public.mkdir()
    for filename in ('run.py', 'objective.md'):
        shutil.copyfile(FIXTURE / filename, public / filename)
    generated = subprocess.run([sys.executable, str(FIXTURE / 'generate.py'), str(public / 'dataset.json')],
                               capture_output=True, text=True)
    assert generated.returncode == 0, generated.stderr
    subprocess.run([sys.executable, str(FIXTURE / 'generate.py'), str(tmp_path / 'same-dataset.json')], check=True)
    assert (public / 'dataset.json').read_bytes() == (tmp_path / 'same-dataset.json').read_bytes()
    monkeypatch.setenv('SCID_GENERIC_PUBLIC', str(public))
    isolated = ['-I'] if os.environ.get('SCID_GENERIC_INSTALLED') == '1' else []
    if not isolated:
        source = str(Path(c.__file__).parents[2])
        monkeypatch.setenv('PYTHONPATH', source + os.pathsep + os.environ.get('PYTHONPATH', ''))
    launcher = tmp_path / 'bin/codex'
    launcher.parent.mkdir()
    launcher.write_text('#!' + sys.executable + (' -I' if isolated else '') + '\n' +
                        (FIXTURE / 'native.py').read_text())
    launcher.chmod(0o555)
    disabled_search = tmp_path / 'search.json'
    disabled_search.write_text('null')
    root = tmp_path / 'instance'
    options = []
    target = tmp_path / 'delivered'
    if deliver:
        target.mkdir()
        monkeypatch.setenv('SCID_GENERIC_DELIVERY', '1')
        files = dict(delivery=dict(closeout_a=dict(max_observed_tokens=100, max_seconds=10),
            inflight_tokens=20, cleanup_seconds=5, submit_seconds=10, confirm_seconds=5,
            adapter=generic_delivery.descriptor(target)),
            node={role: dict(max_observed_tokens=150, max_seconds=15) for role in 'HWAE'},
            selection=dict(version=1, shortlist_k=2, smoke_seconds=1))
        for name, value in files.items():
            c.write(tmp_path / (name + '.json'), value)
        options = ['--delivery-policy', tmp_path / 'delivery.json', '--node-budget-policy', tmp_path / 'node.json',
                   '--selection-policy', tmp_path / 'selection.json']
    if observer is not None:
        adapter = tmp_path / 'observer.py'
        adapter.write_text('import json,sys\njson.load(sys.stdin)\n' +
            ('print("invalid observer response")\n' if observer == 'unavailable' else
             'print(json.dumps(dict(candidates=[],current_candidate=None,actual_submission=None,coverage=dict(status="complete",note="No domain facts"))))\n'))
        c.write(tmp_path / 'observer.json', dict(adapter=str(adapter), config={}))
        options += ['--history-observer-config', tmp_path / 'observer.json']

    def cli(*args):
        reply = subprocess.run([sys.executable, *isolated, '-m', 'scidiscovery.research_loop.cli', *map(str, args)],
                               capture_output=True, text=True)
        assert reply.returncode in (0, 2), (reply.stdout, reply.stderr)
        return json.loads(reply.stdout)

    prepared = cli('prepare', '--root', root, '--objective', public / 'objective.md', '--public-root', public,
                   '--native-launcher-json', json.dumps([str(launcher)]), '--max-tokens', '1000',
                   '--max-seconds', '60', '--max-steps', str(max_steps), '--model', 'fake', '--reasoning-effort', 'high',
                   '--search-policy', disabled_search, *options)
    assert prepared['status'] == 'prepared'
    assert c.settings(root)['experiment_mode'] == 'local'
    return root, target, cli, public


@pytest.mark.parametrize('deliver', [False, True], ids=['export', 'directory-delivery'])
def test_generic_inverse_default_local_cli_handoff_and_export(tmp_path, execution_registry, monkeypatch, deliver):
    root, target, cli, public = generic_case(tmp_path, monkeypatch, deliver)
    finished = cli('run', '--root', root)
    assert finished['status'] == ('delivery_confirmed' if deliver else 'finish'), finished
    roles = [c.read(p)['role'] for p in sorted((root / 'jobs').glob('*.json'))]
    assert roles[:3] == ['H', 'W', 'A'] and all(role == 'A' for role in roles[3:])
    work = c.workspace(root, 2)
    config = c.read(work / 'work/experiment-config.json')
    assert config['execution_interface']['executor'] == 'local_execution:command'
    assert config['max_seconds'] <= 60
    record = c.host_record(work)
    seal = c.read(record / 'result-identity.json')
    observation = c.read(root / seal['observations']['path'])
    assert len(observation['candidates']) == 2
    assert len({candidate['id'] for candidate in observation['candidates']}) == 2
    assert {candidate['evaluation_key'] for candidate in observation['candidates']} == {'generic_inverse.v1/public_target_stress/latent_mse'}
    calls = observation['managed_calls']
    assert len(calls) == 3
    read_proofs = c.read(c.workspace(root, 3) / 'work/read-proof.json')
    baseline = {proof['method']['method']: {m['name']: m['value'] for m in proof['metrics']} for proof in read_proofs}
    assert set(baseline) == {'source_linear', 'operator_ridge'}
    comparison = c.read(c.workspace(root, 3) / 'work/comparison.json')
    assert comparison['scripted'] is True
    assert comparison['winners'] == {name: min(baseline, key=lambda method: baseline[method][name])
                                    for name in ('source_validation_mse', 'public_target_stress_mse')}
    evidence = []
    for call in calls:
        assert call['mechanism_binding'] is None
        assert all(item['retention'] == 'archived' for item in [*call['originals'], *call['outputs']])
        directory = work / 'work/lineage/calls' / call['call_id']
        accepted = c.read(directory / 'accepted.json')
        assert (directory / 'inputs/dataset.json').read_bytes() == (public / 'dataset.json').read_bytes()
        assert (directory / 'inputs/run.py').read_bytes() == (FIXTURE / 'run.py').read_bytes()
        assert (Path(accepted['experiment_directory']) / 'dataset.json').read_text().startswith('source deliberately changed')
        evidence.append(dict(call_id=call['call_id'], status=call['status'], accepted=call['accepted'],
                             result=call['execution']['result'], originals=call['originals'], outputs=call['outputs']))
    before = {str(p): c.digest(p) for p in (work / 'work/lineage/calls').rglob('*') if p.is_file()}
    repeated = cli('run', '--root', root)
    assert repeated['status'] == finished['status']
    if deliver:assert repeated['last_confirmed'] == finished['last_confirmed']
    else:assert repeated == finished
    exported = cli('closeout', '--root', root, *([] if deliver else ['--export-only']))
    assert exported['status'] == ('delivery_confirmed' if deliver else 'exported_unsubmitted')
    assert exported['goal_completion'] == 'not_asserted'
    if deliver:
        actions = budget.closeout_state(root)['actions']
        assert [row['intent']['action_kind'] for row in actions] == ['submit', 'confirm']
        assert all(row['outcome']['result']['note'] == 'exact_local_directory_delivery_confirmed' for row in actions)
        screen = c.read(root / 'host-delivery/selection/screen.json')
        assert len(screen['rows']) == 2 and not screen['smoke_capability'] and not screen['audit_configured']
        assert all(row['smoke']['status'] == 'not_provided' and row['audit']['status'] == 'unconfigured' for row in screen['rows'])
        operation = exported['last_confirmed']['operation_id']
        bundle = target / operation
        manifest = c.read(bundle / 'manifest.json')
        chosen = min(observation['candidates'], key=lambda candidate: candidate['metric'])
        assert manifest['candidate_id'] == chosen['id']
        assert (bundle / 'artifact').read_bytes() == (root / chosen['evidence'][1]['snapshot']).read_bytes()
        previous = {str(p): c.digest(p) for p in target.rglob('*') if p.is_file()}
        assert cli('closeout', '--root', root)['status'] == 'delivery_confirmed'
        assert budget.closeout_state(root)['actions'] == actions
        assert previous == {str(p): c.digest(p) for p in target.rglob('*') if p.is_file()}
        # Reproduce the delivered product using only the delivered inputs and replay instruction.
        replay = tmp_path / 'delivery-reproduction'
        shutil.copytree(bundle / 'inputs', replay)
        command = manifest['result']['replay']
        repeat = subprocess.run([sys.executable, '-I', str(replay / command['entry']), *command['arguments']],
            cwd=replay, capture_output=True, text=True)
        assert repeat.returncode == 0, repeat.stderr
        for name in manifest['objects']:
            if name.startswith('outputs/'):
                assert (replay / 'artifacts' / name.removeprefix('outputs/')).read_bytes() == (bundle / name).read_bytes()
    else:
        assert not list((root / 'host-delivery').glob('**/*.intent.json'))
    assert before == {str(p): c.digest(p) for p in (work / 'work/lineage/calls').rglob('*') if p.is_file()}
    # Rebuild only from archived originals after export, not the changed Worker inputs.
    reproduced = []
    for call in calls:
        if call['status'] != 'known_success':
            assert call['status'] == 'known_failed' and call['execution']['result']['status'] == 'missing'
            continue
        replay = tmp_path / 'export-reproduction' / call['call_id']
        replay.mkdir(parents=True)
        for item in call['originals']:
            if '/inputs/' not in item['path']:
                continue
            original = root / item['snapshot']
            assert hashlib.sha256(original.read_bytes()).hexdigest() == item['sha256']
            destination = replay / item['path'].split('/inputs/', 1)[1]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(original.read_bytes())
        accepted = c.read(root / call['accepted']['snapshot'])
        args = accepted['command'][accepted['script_index'] + 1:]
        repeat = subprocess.run([sys.executable, '-I', str(replay / 'run.py'), *args], cwd=replay,
                                capture_output=True, text=True)
        assert repeat.returncode == 0, repeat.stderr
        for item in call['outputs']:
            assert (replay / 'artifacts' / item['name']).read_bytes() == (root / item['snapshot']).read_bytes()
        reproduced.append(call['call_id'])
    report = dict(passed=True, models_called=0, scientific_reasoning=False, implementation=config['execution_interface']['executor'],
                  default_local=True, search_disabled=True, comparison=comparison, roles=roles, baseline=baseline,
                  calls=evidence, repeat_run_no_replay=True, a_read_outputs=True,
                  export_status=exported['status'], goal_completion=exported['goal_completion'],
                  archive_reproduction_byte_identical=reproduced, core_module=str(c.__file__),
                  candidate_ids=[row['id'] for row in observation['candidates']],
                  directory_delivery=(dict(status=exported['status'], candidate_id=manifest['candidate_id'],
                      operation_id=operation, manifest_sha256=c.digest(bundle / 'manifest.json'),
                      submit_count=sum(row['intent']['action_kind']=='submit' for row in actions),
                      exact_bundle_reproduction=True) if deliver else None),
                  limitations=['Public target stress only; no hidden reward.',
                               'Optional domain audit/smoke not provided; directory confirmation is not external service submission.',
                               'Scripted roles; no model reasoning.'])
    (tmp_path / 'acceptance-evidence.json').write_text(json.dumps(report, indent=2) + '\n')


@pytest.mark.parametrize('fault', ['promotion-response-lost', 'confirmation-response-lost', 'pending-target-conflict'])
def test_generic_directory_delivery_recovers_by_confirmation_without_resubmission(tmp_path, execution_registry, monkeypatch, fault):
    root, target, _, _ = generic_case(tmp_path, monkeypatch, max_steps=10)
    original = delivery._call
    calls = []
    injected = False
    def interrupted(spec, request, seconds, **options):
        nonlocal injected
        calls.append(request['phase'])
        phase = 'promote' if fault != 'confirmation-response-lost' else 'confirm'
        fail = not injected and request['phase'] == phase
        if fail and fault == 'pending-target-conflict':
            (target / ('.pending-' + request['operation_id'])).mkdir()
        reply = original(spec, request, seconds, **options)
        if fail:
            injected = True
            return None  # A lost response is uncertainty, never a scientific rejection.
        return reply
    monkeypatch.setattr(delivery, '_call', interrupted)
    stopped = controller.run(root)
    assert injected and stopped['status'] == 'delivery_unknown', stopped
    assert calls.count('promote') == 1
    actions = budget.closeout_state(root)['actions']
    operation = actions[0]['intent']['operation_id']
    promoted = fault != 'pending-target-conflict'
    assert (target / operation / 'manifest.json').exists() == promoted
    assert all(row['outcome']['result']['status'] != 'rejected' for row in actions)
    resumed = controller.closeout(root)
    assert resumed['status'] == ('delivery_confirmed' if promoted else 'delivery_unknown'), resumed
    assert calls.count('promote') == 1
    assert [row['intent']['action_kind'] for row in budget.closeout_state(root)['actions']].count('submit') == 1
    before = list(calls)
    repeated = controller.closeout(root)
    assert repeated['status'] == resumed['status'] and calls.count('promote') == 1
    if promoted:
        assert calls == before  # A completed confirmation is reused, without another leaf call.


@pytest.mark.parametrize('declaration', [None, 'explicit', 'missing-metric', 'missing-direction', 'missing-output', 'unhashable'])
def test_generic_candidate_requires_explicit_scientific_metric_and_retained_artifact(tmp_path, declaration):
    from scidiscovery.research_loop.local_experiments import LocalExecution
    from scidiscovery.research_loop import generic_results
    value = dict(version=1, metrics=[dict(name='quality', value=1, evaluation_key='public/v1', direction='max'),
        dict(name='cost', value=2, evaluation_key='cost/v1', direction='min')],
        outputs=[dict(path='artifacts/product.bin', label='Declared product')])
    if declaration is not None:
        value['candidate'] = dict(label='Explicit method', metric='quality', artifact='artifacts/product.bin')
        if declaration == 'missing-metric':value['candidate']['metric'] = 'unstated'
        if declaration == 'missing-direction':value['metrics'][0].pop('direction')
        if declaration == 'missing-output':value['candidate']['artifact'] = 'artifacts/unstated.bin'
        if declaration == 'unhashable':value['candidate']['metric'] = []
    c.write(tmp_path / 'result.json', value)
    result = LocalExecution.read_result(tmp_path, [dict(name='product.bin')])
    if declaration in {None, 'explicit'}:
        assert result['status'] == 'available'
        row = dict(call_id='call-1', scope=dict(step=2, goal='original'), status='known_success',
            completed=dict(retention='archived'), execution=dict(result=result), outputs=[dict(name='product.bin')])
        candidates = generic_results.candidates([row])
        if declaration is None:assert candidates == []  # Two metrics do not silently select one.
        else:
            assert len(candidates) == 1 and candidates[0]['metric'] == 1 and candidates[0]['direction'] == 'max'
            assert candidates[0]['evaluation_key'] == 'public/v1'
            assert generic_results.identity(row) == candidates[0]['id']
            assert generic_results.identity(dict(row, scope=dict(step=2, goal='other'))) != candidates[0]['id']
            assert generic_results.candidates([dict(row, status='known_failed')]) == []
    else:
        assert result['status'] == 'invalid'


def test_generic_adapter_missing_required_audit_is_rejected_before_instance_creation(tmp_path):
    public = tmp_path / 'public';public.mkdir()
    objective = public / 'objective.md';objective.write_text('Explicit required scientific audit')
    target = tmp_path / 'target';target.mkdir()
    root = tmp_path / 'instance'
    policy = dict(closeout_a=dict(max_observed_tokens=100, max_seconds=10), inflight_tokens=0,
        cleanup_seconds=5, submit_seconds=10, confirm_seconds=5, adapter=generic_delivery.descriptor(target))
    with pytest.raises(ValueError, match='required.*no audit capability'):
        controller.prepare(root, objective, public, ['never-run'], max_tokens=1000, max_seconds=60, max_steps=5,
            model='no-model', reasoning_effort='high', search_policy=None, experiment_mode='local',
            node_budget_policy={role: dict(max_observed_tokens=100, max_seconds=10) for role in 'HWAE'},
            delivery_policy=policy, candidate_audit_policy=dict(version=1))
    assert not root.exists() and list(target.iterdir()) == []


@pytest.mark.parametrize('observer', ['empty', 'unavailable'])
def test_generic_candidates_are_registered_independently_of_optional_domain_observer(tmp_path, execution_registry, monkeypatch, observer):
    root, _, cli, _ = generic_case(tmp_path, monkeypatch, deliver=False, observer=observer)
    assert cli('run', '--root', root)['status'] == 'finish'
    seal = c.read(c.host_record(c.workspace(root, 2)) / 'result-identity.json')
    fact = c.read(root / seal['observations']['path'])
    assert len(fact['managed_calls']) == 3 and len(fact['candidates']) == 2
    assert {row['label'] for row in fact['candidates']} == {'source_linear', 'operator_ridge'}
    if observer == 'unavailable':assert fact['coverage']['status'] == 'unavailable'
