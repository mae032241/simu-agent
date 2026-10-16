"""Real CLI/subprocess handoff, with a local deterministic native stand-in."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.research_loop import contracts, controller, native
from scidiscovery.research_loop.cli import main, status


@pytest.fixture
def instance(tmp_path):
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.txt'
    objective.write_text('Distinguish competing explanations; retain uncertainty.')
    launcher = tmp_path / 'native.py'
    launcher.write_text('''import json,os,pathlib,sys
args=sys.argv[1:]
role=os.environ['THIN_HWA_ROLE']
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE'])
prompt=sys.stdin.read()
assert 'MCP' not in prompt
job=json.loads((work/'science-task.json').read_text())
assert job['role']==role and 'global' in job
assert not (work/'science-result.schema.json').exists()
assert 'Do not build attachment indexes' in prompt
assert 'inputs/global/objective.md' == job['global']['objective']
output=pathlib.Path(args[args.index('--output-last-message')+1])
payload={'summary':role+' bounded finding','scientific_result':'Evidence in artifacts/observation.txt',
         'limitations':['Only a deterministic test; no science validation.'],
         'implementation_selection':None}
if role in {'H','A'}:
    payload.update(next_action='experiment' if role=='H' else 'finish',route_reason='Exact test direction')
if role == 'W':
    payload.update(stage_intent='review',mechanism_findings=[{'mechanism':'Fixture mechanism',
      'basis':'blocked','finding':'No managed scientific observation in this transport fixture.'}])
if role == 'A':
    payload['candidate_recommendation'] = None
    payload['progress_assessment'] = None
    payload['decision_request'] = None
    payload['portfolio_review'] = None
    mechanisms=json.loads((work/job['lineage']['indexes']['mechanisms']).read_text())
    ref=mechanisms['mechanisms'][0]['mechanism_ref']
    payload['search_review']={'dispositions':[{'mechanism_ref':ref,'status':'pending',
      'reason':'No managed scientific observation in this transport fixture.'}], 'next_focus':None}
if role == 'H':
    payload['search_plan']={'scope':'Fixture scope','commitments':[{'label':'Fixture mechanism',
      'minimal_test':'Fixture measurement','existing_ref':None}],
      'focus':{'label':'Fixture mechanism','action':'screen'}}
(work/'artifacts'/'observation.txt').write_text(role+' observation')
output.write_text(json.dumps(payload))
print(json.dumps({'type':'thread.started','thread_id':'native-'+role}),flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':5}}),flush=True)
''')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, [sys.executable, str(launcher)],
                       max_tokens=2000, max_seconds=60, max_steps=6,
                       model='gpt-6.1-sol', reasoning_effort='high')
    return root


def test_real_native_process_completes_without_root_or_loopx(instance):
    result = controller.run(instance)
    assert result['status'] == 'finish', result
    assert result['completed_steps'] == 3
    assert contracts.read(Path(result['scientific_output_path']))['scientific_result'].startswith('Evidence')
    assert result['usage'] == dict(input_tokens=300, cached_input_tokens=240, output_tokens=15,
                                    observed_tokens=315, unknown_steps=[])
    assert [node['role'] for node in status(instance)['nodes']] == ['H', 'W', 'A']
    assert not (instance / 'registry.json').exists()
    for step in range(1, 4):
        work = contracts.workspace(instance, step)
        assert contracts.validate(work)['role'] == ('H', 'W', 'A')[step-1]
    assert controller.run(instance) == result


def test_cli_entrypoint_status_is_read_only(instance):
    environment = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[2] / 'src')}
    result = subprocess.run([sys.executable, '-m', 'scidiscovery.research_loop.cli',
                             'run', '--root', str(instance)], env=environment,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)['completed_steps'] == 3
    before = {p: contracts.digest(p) for p in instance.rglob('*') if p.is_file()}
    result = subprocess.run([sys.executable, '-m', 'scidiscovery.research_loop.cli',
                             'status', '--root', str(instance)], env=environment,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert {p: contracts.digest(p) for p in instance.rglob('*') if p.is_file()} == before


def test_pause_and_continue_between_nodes(instance, capsys):
    assert main(['pause', '--root', str(instance)]) == 0
    assert controller.run(instance)['status'] == 'paused'
    assert not (instance / 'jobs').exists()
    assert main(['continue', '--root', str(instance)]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['completed_steps'] == 3


def test_role_route_is_exact_enum_not_prose(tmp_path):
    path = tmp_path / 'raw.json'
    value = dict(summary='A', scientific_result='Observed', limitations=[],
                 implementation_selection=None, candidate_recommendation=None,
                 progress_assessment=None, decision_request=None, portfolio_review=None,
                 search_review=None, next_action='continue_w', route_reason='A reason')
    path.write_text(json.dumps(value))
    assert contracts.science_payload(path, 'A')['route_reason'] == 'A reason'
    value['next_action'] = 'continue_w: more experiments'
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='next_action'):
        contracts.science_payload(path, 'A')


def test_native_without_usage_is_not_replayed(instance):
    settings = contracts.read(instance / 'settings.json')
    script = Path(settings['native_launcher_argv'][1])
    script.write_text(script.read_text().replace("'turn.completed'", "'usage_unavailable'"))
    assert controller.run(instance)['status'] == 'native_stopped'
    log = contracts.host_record(contracts.workspace(instance, 1)) / 'native.jsonl'
    before = contracts.digest(log)
    assert controller.run(instance)['status'] == 'native_outcome_unsealed'
    assert contracts.digest(log) == before


def test_tampered_direct_result_never_reaches_next_role(instance):
    result = controller.run(instance)
    assert result['status'] == 'finish', result
    work = contracts.workspace(instance, 3)
    (work / 'inputs/parents/002/conclusion.json').chmod(0o600)
    (work / 'inputs/parents/002/conclusion.json').write_text('{}')
    assert controller.run(instance)['status'] == 'sealed_node_invalid'


def test_actual_material_copy_cannot_change_while_parent_stays_valid(instance):
    result = controller.run(instance)
    assert result['status'] == 'finish', result
    work = contracts.workspace(instance, 3)
    original = work / 'inputs/parents/002/artifacts/observation.txt'
    original.chmod(0o600)
    original.write_text('Fabricated local evidence')
    assert contracts.validate(contracts.workspace(instance, 2))['role'] == 'W'
    with pytest.raises(ValueError, match='actually read'):
        contracts.validate(work)
    assert controller.run(instance)['status'] == 'sealed_node_invalid'


def test_next_role_receives_science_without_parent_bindings(instance):
    result = controller.run(instance)
    assert result['status'] == 'finish', json.dumps(result)
    work = contracts.workspace(instance, 3)
    value = contracts.read(work / 'inputs/parents/002/conclusion.json')
    assert set(value) == {'summary', 'scientific_result', 'limitations', 'implementation_selection',
                          'stage_intent', 'mechanism_findings'}
    task = contracts.read(work / 'science-task.json')
    assert all(set(item) == {'conclusion', 'artifacts', 'role', 'limitations', 'limitations_omitted_count'}
               for item in task['parents'])
    assert 'sha256' not in json.dumps(task)
    assert not (work / 'inputs/parents/001/inputs').exists()


def test_native_meter_rejects_impossible_caching():
    assert native._usage_event(dict(type='turn.completed', usage=dict(
        input_tokens=5, cached_input_tokens=6, output_tokens=1))) is None


def test_actual_native_launch_rechecks_frozen_settings(instance, monkeypatch):
    contracts.build_job(instance, 1, 'H', [])
    policy = contracts.read(instance / 'settings.json')
    policy['model'] = 'unauthorized-replacement'
    contracts.write(instance / 'settings.json', policy)
    monkeypatch.setattr(native.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not launch'))
    with pytest.raises(ValueError, match='settings changed'):
        native.execute_native(instance, 1)
    assert not (contracts.host_record(contracts.workspace(instance, 1)) / 'native-intent.json').exists()


@pytest.mark.process_e2e
def test_running_session_tokens_project_before_terminal_without_double_count(instance):
    import time
    settings = contracts.read(instance / 'settings.json')
    script = Path(settings['native_launcher_argv'][1])
    original = "print(json.dumps({'type':'thread.started','thread_id':'native-'+role}),flush=True)"
    streaming = '''import time
thread='native-'+role
home=pathlib.Path(os.environ['THIN_HWA_NATIVE_HOME'])
session=home/'sessions'/('rollout-'+thread+'.jsonl')
session.parent.mkdir(parents=True,exist_ok=True)
session.write_text(json.dumps({'type':'session_meta','payload':{'id':thread,'cwd':str(work)}})+'\\n')
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)
with session.open('a') as log:
    log.write(json.dumps({'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':30,'cached_input_tokens':20,'output_tokens':2}}}})+'\\n')
    log.flush()
if role == 'H':
    (work/'work/tokens-written').write_text(str(time.monotonic()))
    until=time.monotonic()+15
    while not (work/'work/release').exists() and time.monotonic()<until:time.sleep(.05)
with session.open('a') as log:
    log.write(json.dumps({'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':5}}}})+'\\n')
'''
    script.write_text(script.read_text().replace(original, streaming))
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[2] / 'src')}
    contracts.build_job(instance, 1, 'H', [])
    bootstrap = ('import json,sys;from pathlib import Path;'
                 'from scidiscovery.research_loop import native;'
                 'print(json.dumps(native.execute_native(Path(sys.argv[1]),1)))')
    process = subprocess.Popen([sys.executable, '-c', bootstrap, str(instance)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    work = contracts.workspace(instance, 1)
    record = contracts.host_record(work)
    until = time.monotonic() + 10
    try:
        while time.monotonic() < until:
            if (record / 'usage-observation.json').exists():
                observation = contracts.read(record / 'usage-observation.json')
                if observation['coverage'] == 'live':
                    break
            time.sleep(.05)
        else:
            pytest.fail('running token projection was not published within 10 seconds')
        assert process.poll() is None
        assert time.monotonic() - float((work / 'work/tokens-written').read_text()) < 5
        assert contracts.read(record / 'usage.json')['input_tokens'] == 30
        assert observation['tokens']['output_tokens'] == 2
        assert observation['unreported_usage']
        assert not (record / 'native-outcome.json').exists()
    finally:
        (work / 'work/release').touch()
        stdout, stderr = process.communicate(timeout=20)
    assert process.returncode == 0, stderr + stdout
    result = json.loads(stdout)
    assert result['summary'] == 'H bounded finding', result
    assert native.usage(instance)['observed_tokens'] == 105
    assert contracts.read(record / 'usage.json')['input_tokens'] == 100
    metering = contracts.read(record / 'native-outcome.json')['metering']
    assert metering['coverage'] == 'terminal'
    assert metering['reconciliation'] == 'matched'


@pytest.mark.process_e2e
def test_terminal_usage_cannot_reduce_live_observation(instance):
    settings = contracts.read(instance / 'settings.json')
    script = Path(settings['native_launcher_argv'][1])
    original = "print(json.dumps({'type':'thread.started','thread_id':'native-'+role}),flush=True)"
    script.write_text(script.read_text().replace(original, '''thread='native-'+role
home=pathlib.Path(os.environ['THIN_HWA_NATIVE_HOME'])
session=home/'sessions'/('rollout-'+thread+'.jsonl')
session.parent.mkdir(parents=True,exist_ok=True)
session.write_text(json.dumps({'type':'session_meta','payload':{'id':thread,'cwd':str(work)}})+'\\n'+json.dumps({'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':150,'cached_input_tokens':80,'output_tokens':5}}}})+'\\n')
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)'''))
    result = controller.run(instance)
    assert result['status'] == 'native_stopped', result
    record = contracts.host_record(contracts.workspace(instance, 1))
    outcome = contracts.read(record / 'native-outcome.json')
    assert outcome['stop_reason'] == 'native_usage_unreconciled'
    assert outcome['metering']['reason'] == 'terminal_usage_below_live_observation'
    assert contracts.read(record / 'usage.json')['input_tokens'] == 150
    assert outcome['usage']['unknown_steps'] == [1]


@pytest.mark.process_e2e
def test_live_tokens_reach_shared_limit_before_turn_completion(tmp_path):
    import time
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.txt'
    objective.write_text('No model; verify a running token observation stops execution.')
    launcher = tmp_path / 'native.py'
    launcher.write_text('''import json,os,pathlib,sys,time
sys.stdin.read()
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE'])
home=pathlib.Path(os.environ['THIN_HWA_NATIVE_HOME'])
thread='live-limit-thread'
session=home/'sessions'/('rollout-'+thread+'.jsonl')
session.parent.mkdir(parents=True,exist_ok=True)
session.write_text(json.dumps({'type':'session_meta','payload':{'id':thread,'cwd':str(work)}})+'\\n'+json.dumps({'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':5}}}})+'\\n')
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)
time.sleep(20)
''')
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, [sys.executable, str(launcher)],
        max_tokens=50, max_seconds=60, max_steps=6, model='no-model', reasoning_effort='high')
    started = time.monotonic()
    result = controller.run(root)
    assert time.monotonic() - started < 5
    assert result['status'] == 'native_stopped', result
    record = contracts.host_record(contracts.workspace(root, 1))
    outcome = contracts.read(record / 'native-outcome.json')
    assert outcome['stop_reason'] == 'token_limit'
    assert outcome['usage']['observed_tokens'] == 105
    assert outcome['usage']['unknown_steps'] == [1]
    assert outcome['metering']['reason'] == 'terminal_usage_unreported'


@pytest.mark.process_e2e
@pytest.mark.parametrize('explicit_home', [True, False])
def test_raw_codex_live_usage_uses_actual_inherited_home_without_replacing_config(tmp_path, monkeypatch, explicit_home):
    import time
    user_home = tmp_path / 'user-home'
    user_home.mkdir()
    actual_home = tmp_path / 'configured-codex-home' if explicit_home else user_home / '.codex'
    actual_home.mkdir()
    (actual_home / 'config.toml').write_text('fixture configuration')
    (actual_home / 'auth.json').write_text('fixture credentials')
    monkeypatch.setenv('HOME', str(user_home))
    if explicit_home:
        monkeypatch.setenv('CODEX_HOME', str(actual_home))
    else:
        monkeypatch.delenv('CODEX_HOME', raising=False)
    public = tmp_path / 'public'
    public.mkdir()
    objective = public / 'objective.txt'
    objective.write_text('No model; meter the raw launcher from its actual native home.')
    launcher = tmp_path / 'codex'
    launcher.write_text('#!' + sys.executable + '\n' + '''import json,os,pathlib,sys,time
sys.stdin.read()
work=pathlib.Path(os.environ['THIN_HWA_WORKSPACE'])
# Mimic raw Codex storage; deliberately do not read THIN_HWA_NATIVE_HOME.
home=pathlib.Path(os.environ.get('CODEX_HOME') or (pathlib.Path.home()/'.codex'))
assert (home/'config.toml').read_text()=='fixture configuration'
assert (home/'auth.json').read_text()=='fixture credentials'
(work/'work/native-env.json').write_text(json.dumps({'codex_home':os.environ.get('CODEX_HOME'),'home':str(pathlib.Path.home())}))
thread='raw-native-home-thread'
session=home/'sessions'/('rollout-'+thread+'.jsonl')
session.parent.mkdir(parents=True,exist_ok=True)
session.write_text(json.dumps({'type':'session_meta','payload':{'id':thread,'cwd':str(work)}})+'\\n'+json.dumps({'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':5}}}})+'\\n')
print(json.dumps({'type':'thread.started','thread_id':thread}),flush=True)
time.sleep(20)
''')
    launcher.chmod(0o755)
    root = tmp_path / 'instance'
    controller.prepare(root, objective, public, [str(launcher)], max_tokens=50,
        max_seconds=10, max_steps=6, model='no-model', reasoning_effort='high')
    started = time.monotonic()
    result = controller.run(root)
    assert time.monotonic() - started < 5
    assert result['status'] == 'native_stopped', result
    work = contracts.workspace(root, 1)
    outcome = contracts.read(contracts.host_record(work) / 'native-outcome.json')
    assert outcome['stop_reason'] == 'token_limit'
    assert outcome['usage']['observed_tokens'] == 105
    assert contracts.read(work / 'work/native-env.json') == dict(
        codex_home=str(actual_home) if explicit_home else None, home=str(user_home))
    assert not (root / 'native-homes/001/sessions').exists()
    assert (actual_home / 'config.toml').read_text() == 'fixture configuration'
    assert (actual_home / 'auth.json').read_text() == 'fixture credentials'
