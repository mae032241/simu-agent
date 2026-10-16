"""Generic task execution/result/artifact handoff, using real CLIs and no models."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from execution_fixtures import execution_registry
from scidiscovery.research_loop import contracts as c

FIXTURE = Path(__file__).parents[1] / 'fixtures/generic_inverse'


def test_generic_inverse_default_local_cli_handoff_and_export(tmp_path, execution_registry, monkeypatch):
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

    def cli(*args):
        reply = subprocess.run([sys.executable, *isolated, '-m', 'scidiscovery.research_loop.cli', *map(str, args)],
                               capture_output=True, text=True)
        assert reply.returncode in (0, 2), (reply.stdout, reply.stderr)
        return json.loads(reply.stdout)

    prepared = cli('prepare', '--root', root, '--objective', public / 'objective.md', '--public-root', public,
                   '--native-launcher-json', json.dumps([str(launcher)]), '--max-tokens', '1000',
                   '--max-seconds', '60', '--max-steps', '5', '--model', 'fake', '--reasoning-effort', 'high',
                   '--search-policy', disabled_search)
    assert prepared['status'] == 'prepared'
    assert c.settings(root)['experiment_mode'] == 'local'
    finished = cli('run', '--root', root)
    assert finished['status'] == 'finish', finished
    assert [c.read(p)['role'] for p in sorted((root / 'jobs').glob('*.json'))] == ['H', 'W', 'A']
    work = c.workspace(root, 2)
    config = c.read(work / 'work/experiment-config.json')
    assert config['execution_interface']['executor'] == 'local_execution:command'
    assert config['max_seconds'] <= 60
    record = c.host_record(work)
    seal = c.read(record / 'result-identity.json')
    observation = c.read(root / seal['observations']['path'])
    assert observation['candidates'] == []
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
    assert cli('run', '--root', root) == finished
    exported = cli('closeout', '--root', root, '--export-only')
    assert exported['status'] == 'exported_unsubmitted' and exported['goal_completion'] == 'not_asserted'
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
            target = replay / item['path'].split('/inputs/', 1)[1]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
        accepted = c.read(root / call['accepted']['snapshot'])
        args = accepted['command'][accepted['script_index'] + 1:]
        repeat = subprocess.run([sys.executable, '-I', str(replay / 'run.py'), *args], cwd=replay,
                                capture_output=True, text=True)
        assert repeat.returncode == 0, repeat.stderr
        for item in call['outputs']:
            assert (replay / 'artifacts' / item['name']).read_bytes() == (root / item['snapshot']).read_bytes()
        reproduced.append(call['call_id'])
    report = dict(passed=True, models_called=0, scientific_reasoning=False, implementation=config['execution_interface']['executor'],
                  default_local=True, search_disabled=True, comparison=comparison, roles=['H', 'W', 'A'], baseline=baseline,
                  calls=evidence, repeat_run_no_replay=True, a_read_outputs=True,
                  export_status=exported['status'], goal_completion=exported['goal_completion'],
                  archive_reproduction_byte_identical=reproduced, core_module=str(c.__file__),
                  limitations=['Public target stress only; no hidden reward.',
                               'No generic candidate selection, shortlist or external audit qualification.',
                               'Scripted roles; no model reasoning.'])
    (tmp_path / 'acceptance-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
