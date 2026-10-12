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
         'limitations':['Only a deterministic test; no science validation.']}
if role in {'H','A'}:
    payload.update(next_action='experiment' if role=='H' else 'finish',route_reason='Exact test direction')
if role == 'A':
    payload['candidate_recommendation'] = None
    payload['progress_assessment'] = None
    mechanisms=json.loads((work/job['lineage']['indexes']['mechanisms']).read_text())
    ref=mechanisms['mechanisms'][0]['mechanism_ref']
    payload['search_review']={'dispositions':[{'mechanism_ref':ref,'status':'screened',
      'reason':'Fixture screen evidence','evidence':['inputs/parents/002/conclusion.json']}], 'next_focus':None}
if role == 'H':
    payload['search_plan']={'scope':'Fixture scope','commitments':[{'label':'Fixture mechanism',
      'minimal_test':'Fixture measurement','existing_ref':None}],
      'focus':{'label':'Fixture mechanism','action':'screen','repair_source':None}}
if 'implementation_selection' in job['final_response']:
    payload['implementation_selection'] = None
    if role == 'H': payload['search_plan']['focus'].pop('repair_source')
    if role == 'A': payload['search_review']['dispositions'][0].pop('evidence')
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
    path.write_text(json.dumps(dict(summary='A', scientific_result='Observed', limitations=[],
                                   next_action='continue_w: more experiments', route_reason='A reason')))
    with pytest.raises(ValueError):
        contracts.science_payload(path, 'A')
    value = json.loads(path.read_text())
    value['next_action'] = 'continue_w'
    path.write_text(json.dumps(value))
    assert contracts.science_payload(path, 'A')['route_reason'] == 'A reason'


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
    controller.run(instance)
    work = contracts.workspace(instance, 3)
    (work / 'inputs/parents/002/conclusion.json').chmod(0o600)
    (work / 'inputs/parents/002/conclusion.json').write_text('{}')
    assert controller.run(instance)['status'] == 'sealed_node_invalid'


def test_actual_material_copy_cannot_change_while_parent_stays_valid(instance):
    controller.run(instance)
    work = contracts.workspace(instance, 3)
    original = work / 'inputs/parents/002/artifacts/observation.txt'
    original.chmod(0o600)
    original.write_text('Fabricated local evidence')
    assert contracts.validate(contracts.workspace(instance, 2))['role'] == 'W'
    with pytest.raises(ValueError, match='actually read'):
        contracts.validate(work)
    assert controller.run(instance)['status'] == 'sealed_node_invalid'


def test_next_role_receives_science_without_parent_bindings(instance):
    controller.run(instance)
    work = contracts.workspace(instance, 3)
    value = contracts.read(work / 'inputs/parents/002/conclusion.json')
    assert set(value) == {'summary', 'scientific_result', 'limitations', 'implementation_selection'}
    task = contracts.read(work / 'science-task.json')
    assert all(set(item) == {'conclusion', 'artifacts'} for item in task['parents'])
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
