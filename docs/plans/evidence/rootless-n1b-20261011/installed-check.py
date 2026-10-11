"""Installed entrypoint smoke. Deterministic stand-ins; zero model calls."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1] / '123/scidiscovery-e5.2'
sys.path.insert(0, str(REPO / 'scripts'))
import run_tests


def command(argv, cwd=BASE):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    result = subprocess.run([str(x) for x in argv], cwd=cwd, env=env,
                            text=True, capture_output=True, timeout=120)
    with (BASE / 'commands.log').open('a') as stream:
        stream.write(json.dumps({'argv': [str(x) for x in argv], 'code': result.returncode,
                                'stdout': result.stdout, 'stderr': result.stderr}) + '\n')
    if result.returncode:
        raise RuntimeError(f'Command failed: {argv[0]}, see commands.log')
    return result.stdout


def main():
    with run_tests.serial_lock():
        wheel_dir = BASE / 'wheels'
        wheel_dir.mkdir(exist_ok=False)
        command([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                 '--wheel-dir', wheel_dir, REPO])
        wheels = list(wheel_dir.glob('*.whl'))
        assert len(wheels) == 1
        command([sys.executable, '-m', 'venv', '--system-site-packages', BASE / 'venv'])
        python = BASE / 'venv/bin/python'
        command([python, '-m', 'pip', 'install', '--no-deps', wheels[0]])
        module = command([python, '-I', '-c',
                          'from scidiscovery.research_loop import budget; print(budget.__file__)']).strip()
        assert str(BASE / 'venv') in module
        public = BASE / 'public'
        public.mkdir()
        (public / 'objective.md').write_text('Test exact historical implementation reuse and bounded recovery.')
        launcher = BASE / 'fake-native.py'
        launcher.write_text('''import json,os,pathlib,sys
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE'])
role=os.environ['THIN_HWA_ROLE']; step=int(work.name)
sys.stdin.read()
payload={'summary':f'{role} fixture {step}','scientific_result':'Bounded fixture result','limitations':['No scientific claim.']}
if role=='H':
 payload.update(next_action='experiment',route_reason='Execute explicit bounded hypothesis')
 if step==4:payload['scientific_result']='Reuse [candidate](inputs/parents/002/artifacts/candidate.py#reuse-implementation)'
if role=='W':
 if step==2:
  (work/'artifacts/candidate.py').write_text('candidate=42\\n')
  (work/'artifacts/unselected.txt').write_text('must not travel further')
 if step==5:
  assert (work/'inputs/parents/002/artifacts/candidate.py').read_text()=='candidate=42\\n'
  assert not (work/'inputs/parents/002/artifacts/unselected.txt').exists()
if role=='A':payload.update(next_action='revise_h' if step==3 else 'finish',route_reason='Fixture decision')
pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(payload))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'cached_input_tokens':8,'output_tokens':2}}),flush=True)
''')
        root = BASE / 'instance'
        cli = BASE / 'venv/bin/scid-research'
        command([cli, 'prepare', '--root', root, '--objective', public / 'objective.md',
                 '--public-root', public, '--native-launcher-json', json.dumps([str(python), str(launcher)]),
                 '--max-tokens', '2000', '--max-seconds', '120', '--max-steps', '8'])
        command([cli, 'pause', '--root', root])
        command([cli, 'budget-amend', '--root', root, '--max-seconds', '150',
                 '--authorization-note', 'External operator deterministic installation check'])
        result = json.loads(command([cli, 'continue', '--root', root]))
        assert result['status'] == 'finish' and result['completed_steps'] == 6, result
        def logs():
            return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in root.glob('native-evidence/*/native.jsonl')}
        before = logs()
        command([cli, 'run', '--root', root])
        assert before == logs() and len(before) == 6
        status = json.loads(command([cli, 'status', '--root', root]))
        assert status['budget']['time_budget_basis'] == 'active'
        assert status['budget']['max_seconds'] == 150
        assert status['usage']['observed_tokens'] == 72, status
        report = dict(passed=True, module=module, models_called=0, completed_steps=6,
                      history_reuse=True, no_ancestor_bundle=True, no_replay=True,
                      active_budget=True, audited_amend=True,
                      wheel_sha256=hashlib.sha256(wheels[0].read_bytes()).hexdigest())
        (BASE / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))


if __name__ == '__main__':
    main()
