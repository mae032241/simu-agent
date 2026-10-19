"""Scripted transport roles for real CLI acceptance; no model reasoning."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

work = Path(os.environ['THIN_HWA_WORKSPACE'])
role = os.environ['THIN_HWA_ROLE']
prompt = sys.stdin.read()
task = json.loads((work / 'science-task.json').read_text())
isolated = ['-I'] if os.environ.get('SCID_GENERIC_INSTALLED') == '1' else []
payload = dict(summary=role + ' generic inverse tool acceptance',
               scientific_result='Scripted public fixture; no scientific qualification.',
               limitations=['All evaluation labels are public.', 'No model reasoning or hidden reward.',
                            'Selection is scripted; optional domain audit and smoke are not provided.'],
               implementation_selection=None)
if role == 'H':
    payload.update(next_action='experiment', route_reason='Compare two explicit inverse mechanisms', search_plan=None)
if role == 'W':
    assert 'Managed local experiments:' in prompt
    public = Path(os.environ['SCID_GENERIC_PUBLIC'])
    config = work / 'work/experiment-config.json'
    command = [sys.executable, *isolated, '-m', 'scidiscovery.research_loop.experiments', '--config', str(config)]
    receipts = []
    for name, method, fail in [('source', 'source_linear', False), ('ridge', 'operator_ridge', False),
                               ('failure', 'source_linear', True)]:
        experiment = work / 'experiments' / name
        experiment.mkdir(parents=True)
        for filename in ('dataset.json', 'run.py', 'objective.md'):
            shutil.copyfile(public / filename, experiment / filename)
        args = ['run', '--experiment-dir', str(experiment), '--script', str(experiment / 'run.py'),
                '--', '--method', method, *(['--fail'] if fail else [])]
        reply = subprocess.run([*command, *args], capture_output=True, text=True)
        assert reply.returncode == int(fail), (reply.stdout, reply.stderr)
        receipt = json.loads(reply.stdout)
        assert receipt['status'] == ('known_failed' if fail else 'known_success'), receipt
        assert receipt['result']['status'] == ('missing' if fail else 'available'), receipt
        for action in ('query', 'lookup', 'collect'):
            read = subprocess.run([*command, action, '--call-id', receipt['call_id']], capture_output=True, text=True)
            assert read.returncode == 0, (read.stdout, read.stderr)
        receipts.append(receipt)
        (experiment / 'dataset.json').write_text('source deliberately changed after acceptance\n')
        (experiment / 'run.py').write_text('raise RuntimeError("source changed after acceptance")\n')
    (work / 'work/cli-receipts.json').write_text(json.dumps(receipts, indent=2))
    payload.update(stage_intent='review', mechanism_findings=None)
if role == 'A':
    payload.update(next_action='finish', route_reason='Retain the bound public observations and limitations',
        candidate_recommendation=None, search_review=None, progress_assessment=None,
        decision_request=None, portfolio_review=None)
if role == 'A' and any(parent['role'] == 'W' for parent in task['parents']):
    page = task['lineage']['indexes']['experiments']
    calls = []
    while page:
        index = json.loads((work / page).read_text())
        calls.extend(index['experiments'])
        page = index['next_page']
    assert len(calls) == 3, calls
    assert sorted(call['execution_status'] for call in calls) == ['known_failed', 'known_success', 'known_success']
    read_proofs = []
    for call in calls:
        if call['execution_status'] == 'known_failed':
            assert call['result_status'] == 'missing' and call['metrics'] == []
            continue
        assert call['result_status'] == 'available'
        assert {metric['name'] for metric in call['metrics']} == {'source_validation_mse', 'public_target_stress_mse'}
        assert all(metric['direction'] == 'min' and metric['evaluation_key'].startswith('generic_inverse.v1/')
                   for metric in call['metrics'])
        outputs = {Path(item['path']).name: item['path'] for item in call['outputs']}
        method = json.loads((work / outputs['method.json']).read_text())
        predictions = json.loads((work / outputs['predictions.json']).read_text())
        assert not method['target_labels_used_for_fit'] and method['all_evaluation_labels_public']
        assert set(predictions) == {'source_validation', 'public_target_stress'}
        assert all(len(values) == 64 for values in predictions.values())
        read_proofs.append(dict(method=method, metrics=call['metrics'], outputs=outputs))
    assert {proof['method']['method'] for proof in read_proofs} == {'source_linear', 'operator_ridge'}
    (work / 'work/read-proof.json').write_text(json.dumps(read_proofs, indent=2))
    rankings = {name: sorted(read_proofs, key=lambda proof: next(metric['value'] for metric in proof['metrics']
                 if metric['name'] == name))[0]['method']['method']
                for name in ('source_validation_mse', 'public_target_stress_mse')}
    (work / 'work/comparison.json').write_text(json.dumps(dict(scripted=True, winners=rankings,
        rankings_agree=len(set(rankings.values())) == 1, selection_qualification='not_a_candidate_selection'), indent=2))
    payload.update(next_action='finish', route_reason='Public measurements and retained artifacts read',
                   candidate_recommendation=None, search_review=None, progress_assessment=None,
                   decision_request=None, portfolio_review=None,
                   scientific_result='Read both public MSE measurements and exact reconstruction artifacts; tool acceptance only.')
if role == 'A' and os.environ.get('SCID_GENERIC_DELIVERY') == '1':
    page = task['lineage']['indexes']['candidates']
    candidates = []
    while page:
        index = json.loads((work / page).read_text())
        candidates.extend(index['candidates']);page = index['next_page']
    assert len(candidates) == 2
    chosen = min(candidates, key=lambda candidate: candidate['metric'])['id']
    payload.update(next_action='deliver', candidate_recommendation=chosen,
        selection_explanation=dict(criteria='Compare the declared public target stress MSE.',
            criteria_change=dict(status='unchanged',prior_criteria=None,changes=None,evidence=None,accepted_tradeoffs=None)),
        route_reason='Deliver exact retained reconstructions using the declared public stress MSE')
    comparison = task.get('closeout', {}).get('comparison')
    if comparison:
        payload['candidate_comparison'] = dict(rows=[dict(candidate_id=row['candidate_id'],
            key_risk='Public stress metric only; no hidden evaluation or scientific qualification.',
            decision='keep' if row['candidate_id'] == chosen else 'replace') for row in comparison['rows']],
            rationale='Use the explicitly declared stress metric', evidence_steps=[2])
args = sys.argv[1:]
Path(args[args.index('--output-last-message') + 1]).write_text(json.dumps(payload))
print(json.dumps(dict(type='thread.started', thread_id='generic-inverse-fixture-' + role)), flush=True)
print(json.dumps(dict(type='turn.completed', usage=dict(input_tokens=10, cached_input_tokens=0, output_tokens=5))), flush=True)
