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
from scidiscovery.research_loop import budget, contracts as c, controller, delivery, experiment_client, generic_delivery

FIXTURE = Path(__file__).parents[1] / 'fixtures/generic_inverse'


def generic_case(tmp_path, monkeypatch, deliver=True, max_steps=5, observer=None, native_source=None):
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
                        ((FIXTURE / 'native.py').read_text() if native_source is None else native_source))
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
            selection=dict(version=2))
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
    # Delivery needs a separate, catalogue-bound A plus submit and confirm.
    root, target, cli, public = generic_case(tmp_path, monkeypatch, deliver, max_steps=6 if deliver else 5)
    finished = cli('run', '--root', root)
    assert finished['status'] == ('delivery_confirmed' if deliver else 'finish'), finished
    roles = [c.read(p)['role'] for p in sorted((root / 'jobs').glob('*.json'))]
    assert roles == (['H', 'W', 'A', 'A'] if deliver else ['H', 'W', 'A'])
    for step in (2, 3):
        task = c.read(c.workspace(root, step) / 'science-task.json')
        assert task['configured_delivery']['configured'] is deliver
        assert task['configured_delivery'] == c.read(root / 'jobs' / f'{step:03d}.json')['configured_delivery']
        assert 'original task' in task['delivery_requirements']
        if deliver:
            assert 'local directory only' in task['configured_delivery']['effect_scope']
            assert 'task-native submission' in task['configured_delivery']['effect_scope']
    work = c.workspace(root, 2)
    client_path = work / 'work/experiment-config.json'
    client = c.read(client_path)
    assert client == dict(worker_view_version=1, step=2, attempt=0)
    config = experiment_client.resolve(client_path, client)
    assert config['execution_interface']['executor'] == 'local_execution:command'
    assert config['max_seconds'] <= 60
    calls_directory = experiment_client.record_directory(root, 2) / 'calls'
    assert Path(config['record_dir']) == calls_directory.parent
    assert not calls_directory.is_relative_to(work)
    record = c.host_record(work)
    seal = c.read(record / 'result-identity.json')
    observation = c.read(root / seal['observations']['path'])
    assert len(observation['candidates']) == 2
    assert len({candidate['id'] for candidate in observation['candidates']}) == 2
    assert {candidate['evaluation_key'] for candidate in observation['candidates']} == {'generic_inverse.v1/public_target_stress/latent_mse'}
    # Old sealed rows omitted the projection marker; resolve from their host binding.
    from scidiscovery.research_loop import generic_results
    legacy = dict(observation, managed_calls=[{key:value for key,value in row.items() if key!='result_protocol'} for row in observation['managed_calls']])
    for candidate in observation['candidates']:
        assert generic_results.sources(root, legacy, candidate['id'])['candidate_id']==candidate['id']
    assert generic_results.protocol(dict(executor='local_execution:command',version=1))=='scidiscovery.local-result.v1'
    assert generic_results.protocol(dict(executor='composed_execution:fixture',version=1)) is None
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
        directory = calls_directory / call['call_id']
        accepted = c.read(directory / 'accepted.json')
        assert (directory / 'inputs/dataset.json').read_bytes() == (public / 'dataset.json').read_bytes()
        assert (directory / 'inputs/run.py').read_bytes() == (FIXTURE / 'run.py').read_bytes()
        assert (Path(accepted['experiment_directory']) / 'dataset.json').read_text().startswith('source deliberately changed')
        evidence.append(dict(call_id=call['call_id'], status=call['status'], accepted=call['accepted'],
                             result=call['execution']['result'], originals=call['originals'], outputs=call['outputs']))
    before = {str(p): c.digest(p) for p in calls_directory.rglob('*') if p.is_file()}
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
        assert len(screen['rows']) == 2 and 'default' not in screen
        assert all(row['smoke']['status'] == row['audit']['status'] == 'not_run' for row in screen['rows'])
        assert not list((root / 'host-delivery/selection').rglob('*.intent.json'))
        operation = exported['last_confirmed']['operation_id']
        bundle = target / operation
        manifest = c.read(bundle / 'manifest.json')
        chosen = min(observation['candidates'], key=lambda candidate: candidate['metric'])
        assert manifest['candidate_id'] == chosen['id']
        original_author = c.validate(c.workspace(root, 3))
        closeout_job = c.read(root / 'jobs/004.json')
        assert closeout_job['purpose'] == 'closeout' and closeout_job['source_cutoff'] == 3
        assert closeout_job['selection']['version'] == 2
        closeout_author = c.validate(c.workspace(root, 4))
        assert 'scientific qualification' in closeout_author['scientific_result'] or any(
            'qualification' in text or 'audit' in text for text in closeout_author['limitations'])
        assert original_author['next_action'] == closeout_author['next_action'] == 'deliver'
        assert original_author['candidate_recommendation'] == closeout_author['candidate_recommendation'] == chosen['id']
        comparison_choice = closeout_author['candidate_comparison']
        assert comparison_choice['rationale'].strip() and comparison_choice['evidence_steps'] == [2]
        from scidiscovery.research_loop import candidate_refs
        chosen_reference = candidate_refs.public_reference(root, closeout_job, chosen['id'])
        assert [row['candidate_id'] for row in comparison_choice['rows'] if row['decision'] == 'keep'] == [chosen_reference]
        assert candidate_refs.resolve_reference(root, closeout_job, chosen_reference) == chosen['id']
        assert comparison_choice == c.read(c.host_record(c.workspace(root, 4)) / 'science-output.json')['candidate_comparison']
        assert c.settings(root)['max_steps'] == budget.effective_max_steps(root) == budget.used_steps(root) == 6
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
    assert before == {str(p): c.digest(p) for p in calls_directory.rglob('*') if p.is_file()}
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


def test_generic_directory_delivery_preserves_final_author_without_optional_comparison(tmp_path, execution_registry, monkeypatch):
    native_source = (FIXTURE / 'native.py').read_text()
    comparison_start = native_source.index('    if comparison:\n')
    comparison_end = native_source.index('\nargs = sys.argv[1:]', comparison_start)
    # Omit only the optional explanation before preparation freezes this native
    # fixture. Its explicit candidate choice and deliver action stay unchanged.
    native_source = native_source[:comparison_start] + native_source[comparison_end:]
    root, target, cli, _ = generic_case(tmp_path, monkeypatch, max_steps=5, native_source=native_source)
    settings = (root / 'settings.json').read_bytes()
    finished = cli('run', '--root', root)
    assert finished['status'] == 'delivery_confirmed' and finished['goal_completion'] == 'not_asserted', finished
    jobs = sorted((root / 'jobs').glob('*.json'))
    assert [c.read(path)['role'] for path in jobs] == ['H', 'W', 'A', 'A']
    job_originals = {path: path.read_bytes() for path in jobs}
    grant = budget.final_a_barrier(root)
    assert grant['step'] == 4 and grant['basis'] == 'final_state'
    final_step = grant['step']
    job = c.read(root / 'jobs' / f'{final_step:03d}.json')
    assert job['final_only'] and job['purpose'] == 'closeout' and job['source_cutoff'] == 3
    author = c.validate(c.workspace(root, final_step))
    assert author['next_action'] == 'deliver' and author['candidate_recommendation'] is not None
    assert 'candidate_comparison' not in author
    record = c.host_record(c.workspace(root, final_step))
    assert c.read(record / 'native-outcome.json')['final_a_completion']['scope'] == 'original_final_a_only'
    original_names = ('science-output.json', 'result.json', 'result-identity.json',
                      'native-intent.json', 'native-outcome.json', 'usage.json')
    originals = {name: (record / name).read_bytes() for name in original_names}
    raw = c.read(record / 'science-output.json')
    assert 'candidate_comparison' not in raw
    from scidiscovery.research_loop import candidate_refs
    assert candidate_refs.resolve_reference(root, job, raw['candidate_recommendation']) == author['candidate_recommendation']
    worker_seal = c.read(c.host_record(c.workspace(root, 2)) / 'result-identity.json')
    observation = c.read(root / worker_seal['observations']['path'])
    chosen, = [row for row in observation['candidates'] if row['id'] == author['candidate_recommendation']]
    actions = budget.closeout_state(root)['actions']
    assert [row['intent']['action_kind'] for row in actions] == ['submit', 'confirm']
    assert all(row['outcome']['result']['note'] == 'exact_local_directory_delivery_confirmed' for row in actions)
    marker = c.read(record / 'native-intent.json')['budget_slice']['final_return']
    assert all(row['intent']['final_return'] == marker and row['intent']['decision']['step'] == final_step for row in actions)
    operation = finished['last_confirmed']['operation_id']
    bundle = target / operation
    manifest = c.read(bundle / 'manifest.json')
    assert manifest['operation_id'] == operation and manifest['candidate_id'] == chosen['id']
    assert c.digest(bundle / 'artifact') == manifest['artifact_sha256'] == chosen['evidence'][1]['sha256']
    assert (bundle / 'artifact').read_bytes() == (root / chosen['evidence'][1]['snapshot']).read_bytes()
    assert all(c.digest(bundle / name) == digest for name, digest in manifest['objects'].items())
    delivered = {path: path.read_bytes() for path in target.rglob('*') if path.is_file()}
    from scidiscovery.research_loop import native
    observed_tokens = native.usage(root)['observed_tokens']
    used_steps = budget.used_steps(root)
    assert budget.effective_max_steps(root) == 5
    for command in ('run', 'closeout'):
        repeated = cli(command, '--root', root)
        assert repeated['status'] == 'delivery_confirmed' and repeated['goal_completion'] == 'not_asserted', repeated
        assert repeated['last_confirmed'] == finished['last_confirmed']
        assert not (root / 'jobs' / f'{final_step+1:03d}.json').exists() and budget.closeout_state(root)['actions'] == actions
        assert job_originals == {path: path.read_bytes() for path in (root / 'jobs').glob('*.json')}
        assert delivered == {path: path.read_bytes() for path in target.rglob('*') if path.is_file()}
        assert budget.used_steps(root) == used_steps and budget.effective_max_steps(root) == 5
        assert native.usage(root)['observed_tokens'] == observed_tokens
        assert budget.final_a_barrier(root) == grant and (root / 'settings.json').read_bytes() == settings
        assert originals == {name: (record / name).read_bytes() for name in original_names}
        assert c.validate(c.workspace(root, final_step)) == author


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
    jobs = {path: path.read_bytes() for path in (root / 'jobs').glob('*.json')}
    claim = budget.final_a_barrier(root)
    resumed = controller.closeout(root)
    assert resumed['status'] == ('delivery_confirmed' if promoted else 'delivery_unknown'), resumed
    assert calls.count('promote') == 1
    assert calls.count('confirm') == (2 if fault == 'confirmation-response-lost' else 1)
    assert [row['intent']['action_kind'] for row in budget.closeout_state(root)['actions']].count('submit') == 1
    before = list(calls)
    repeated = controller.closeout(root)
    assert repeated['status'] == resumed['status'] and calls.count('promote') == 1
    assert {path: path.read_bytes() for path in (root / 'jobs').glob('*.json')} == jobs
    assert budget.final_a_barrier(root) == claim
    if promoted:
        assert calls == before  # A completed confirmation is reused, without another leaf call.


@pytest.mark.parametrize('declaration', [None, 'explicit', 'missing-metric', 'missing-direction', 'missing-evaluation', 'artifact-only', 'missing-output', 'unhashable'])
def test_generic_candidate_requires_exact_retained_artifact_without_scientific_ranking(tmp_path, declaration):
    from scidiscovery.research_loop.local_experiments import LocalExecution
    from scidiscovery.research_loop import generic_results
    value = dict(version=1, metrics=[dict(name='quality', value=1, evaluation_key='public/v1', direction='max'),
        dict(name='cost', value=2, evaluation_key='cost/v1', direction='min')],
        outputs=[dict(path='artifacts/product.bin', label='Declared product')])
    if declaration is not None:
        value['candidate'] = dict(label='Explicit method', metric='quality', artifact='artifacts/product.bin')
        if declaration == 'missing-metric':value['candidate']['metric'] = 'unstated'
        if declaration == 'missing-direction':value['metrics'][0].pop('direction')
        if declaration == 'missing-evaluation':value['metrics'][0].pop('evaluation_key')
        if declaration == 'artifact-only':value['candidate'] = dict(artifact='artifacts/product.bin')
        if declaration == 'missing-output':value['candidate']['artifact'] = 'artifacts/unstated.bin'
        if declaration == 'unhashable':value['candidate']['metric'] = []
    c.write(tmp_path / 'result.json', value)
    result = LocalExecution.read_result(tmp_path, [dict(name='product.bin')])
    assert result['status'] == 'available'
    assert result['metrics']==value['metrics'] and result['outputs']==value['outputs']
    row = dict(call_id='call-1', scope=dict(step=2, goal='original'), status='known_success',result_protocol='scidiscovery.local-result.v1',
        completed=dict(retention='archived'), execution=dict(result=result), outputs=[dict(name='product.bin')])
    candidates = generic_results.candidates([row])
    if declaration in {None,'missing-output'}:
        assert candidates == []
    else:
        candidate=candidates[0]
        assert len(candidates)==1
        if declaration in {'missing-metric','artifact-only','unhashable'}:
            assert candidate['metric'] is candidate['direction'] is candidate['evaluation_key'] is None
        else:
            assert candidate['metric']==1
            assert candidate['direction']==(None if declaration=='missing-direction' else 'max')
            assert candidate['evaluation_key']==(None if declaration=='missing-evaluation' else 'public/v1')
        assert generic_results.identity(row) == candidate['id']
        assert generic_results.identity(dict(row, scope=dict(step=2, goal='other'))) != candidate['id']
        assert generic_results.candidates([dict(row, status='known_failed')]) == []


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


def test_generic_isolated_delivery_keeps_large_manifest_and_all_objects(tmp_path):
    from scidiscovery.research_loop import protocol
    if shutil.which('bwrap') is None:pytest.skip('Actual namespace required')
    stage=tmp_path/'stage';inputs=stage/'inputs';inputs.mkdir(parents=True)
    target=tmp_path/'target';target.mkdir()
    source=Path(protocol.__file__).resolve();shutil.copyfile(source,inputs/'scid-current-protocol')
    artifact=inputs/'artifact';artifact.write_bytes(b'exact managed artifact')
    objects={'artifact':c.digest(artifact)}
    for index in range(150):
        name='outputs/'+str(index)+'x'*170
        item=inputs/name;item.parent.mkdir(exist_ok=True);item.write_text('exact output '+str(index))
        objects[name]=c.digest(item)
    python=Path(sys.executable);module=Path(generic_delivery.__file__).resolve()
    request=dict(phase='promote',scope=dict(handoff_protocol=protocol.CURRENT),stage=str(stage),
        operation_id='e'*64,candidate_id='local-explicit',artifact_sha256=objects['artifact'],
        config=dict(python=str(python)),target=dict(directory=str(target)),object_digests=objects,
        context=dict(kind='managed_local_result',retained_metadata='x'*280000),
        inputs=[dict(label='scid-current-protocol',sha256=c.digest(source),size_bytes=source.stat().st_size),
            dict(label='runtime-python',invoked_path=str(python.absolute()),path=str(python.resolve()),sha256=c.digest(python.resolve()))])
    spec=dict(launcher_argv=[sys.executable,str(module),'--isolate'],adapter=str(module))
    promoted=delivery._call(spec,request,10)
    assert promoted['status']=='confirmed'
    saved=target/request['operation_id'];manifest=saved/'manifest.json'
    assert manifest.stat().st_size>256000
    assert c.read(manifest)['objects']==objects
    assert all(c.digest(saved/name)==digest for name,digest in objects.items())
    repeated=delivery._call(spec,dict(request,phase='confirm'),10)
    assert repeated['status']=='confirmed'
    (saved/next(name for name in objects if name.startswith('outputs/'))).write_text('tampered')
    assert delivery._call(spec,dict(request,phase='confirm'),10)['status']=='unknown'
