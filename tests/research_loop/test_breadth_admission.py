"""Shared registered-call opportunities through real local/cov subprocesses."""
import copy
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import experiments as e
from test_registered_experiments import managed
from execution_fixtures import execution_registry


def combination(*,ambiguous=False,grant=None,baseline=None,prior_unknown=False):
    rows=[dict(mechanism_ref=f'h001.m{index}',label='same' if ambiguous else label,source_h=1,
        source_h_sha256='c'*64,minimal_test='A distinguishable scientific prediction',status='pending')
        for index,label in enumerate(('P','Q'),1)]
    return dict(version=1,initial_calls=1,mechanisms=rows,
        baseline=baseline or [dict(mechanism_ref=row['mechanism_ref'],accepted_count=0) for row in rows],
        grant=grant,prior_unknown=prior_unknown)


def configure(lane,value,**changes):
    config=json.loads(lane.config.read_text());config.pop('execution_interface')
    config.update(breadth=value,**changes)
    lane.config.write_text(json.dumps(e.freeze(config,lane.executor,path=lane.config)))


@pytest.fixture
def lane(managed):
    configure(managed,combination())
    return managed


def originals(lane):
    return [json.loads(path.read_text()) for path in sorted(lane.records.glob('calls/*/accepted.json'))]


def tree(root):
    if not root.exists():return {}
    return {str(path.relative_to(root)):(path.lstat().st_mode,path.read_bytes() if path.is_file() else None)
        for path in [root,*root.rglob('*')]}


def run(lane,name,mechanism='P',*,failed=False,expected=0):
    script=lane.source(name,failed=failed)
    return lane.cli('run','--script',script,'--mechanism',mechanism,'--new-plan',expected=expected)


def rejected(lane,script,mechanism='P'):
    before=tree(lane.records)
    result=lane.cli('run','--script',script,'--mechanism',mechanism,'--new-plan',expected=2)
    assert result['status']=='unresolved' and 'initial call opportunities' in result['note']
    assert tree(lane.records)==before
    return result


def test_first_branch_second_call_waits_for_another_branch_then_shared_search_continues(lane):
    first=run(lane,'P-initial')
    directory=lane.records/'calls'/first['call_id']
    assert (directory/'process.json').is_file() and (directory/'completed.json').is_file()
    original=originals(lane)[0]
    assert original['scope']['mechanism_ref'] is None
    assert original['mechanism_binding']==dict(mechanism_ref='h001.m1',source_h=1,source_h_sha256='c'*64,
        job_sha256=original['scope']['job_sha256'],grant=None)
    rejected(lane,lane.source('P-extra'))
    other=run(lane,'Q-initial','h001.m2')
    assert other['status']=='known_success'
    third=run(lane,'P-after-Q')
    assert third['status']=='known_success'
    assert [item['mechanism_binding']['mechanism_ref'] for item in originals(lane)]==['h001.m1','h001.m2','h001.m1']
    assert len(list(lane.records.glob('calls/*/process.json')))==3
    # Opportunity records never acquire an authored scientific screened verdict.
    assert all('screened' not in item for item in originals(lane))


def test_failed_call_changed_script_and_repair_attempt_do_not_reset_opportunity(lane):
    first=run(lane,'failed-P',failed=True,expected=1)
    assert first['status']=='known_failed'
    original=copy.deepcopy(originals(lane)[0])
    rejected(lane,lane.source('different-script-P'))
    configure(lane,combination(),native_attempt=dict(number=1,execution_key='e'*64))
    rejected(lane,lane.source('repair-P'))
    assert originals(lane)==[original]
    assert len(list(lane.records.glob('calls/*/process.json')))==1
    assert run(lane,'Q-after-failed-P','Q')['status']=='known_success'


def test_real_unknown_transport_cannot_be_replayed_under_any_mechanism(lane):
    source=lane.source('uncertain-P')
    if lane.kind=='cov':source.write_text(json.dumps(dict(mode='missing_receipt')))
    else:source.write_text(source.read_text().replace('print("ordinary public output")',f'print("x"*{e.MAX_BYTES+1})'))
    result=lane.cli('run','--script',source,'--mechanism','P','--new-plan',expected=2)
    assert result['status']=='unknown'
    assert lane.cli('query','--call-id',result['call_id'])['state']=='unknown'
    assert lane.cli('collect','--call-id',result['call_id'],expected=2)['status']=='unavailable'
    for mechanism in ('P','Q'):
        retry=lane.source('retry-'+mechanism)
        before=tree(lane.records)
        reply=lane.cli('run','--script',retry,'--mechanism',mechanism,'--new-plan',expected=2)
        assert reply['status']=='unknown' and tree(lane.records)==before
    assert len(originals(lane))==len(list(lane.records.glob('calls/*/process.json')))==1


def test_exact_a_extra_one_call_is_consumed_once_and_queries_collect_remain_available(lane):
    grant=dict(mechanism_ref='h001.m1',source_a=3,source_a_sha256='d'*64,extra_calls=1,used_calls=0)
    baseline=[dict(mechanism_ref='h001.m1',accepted_count=1),dict(mechanism_ref='h001.m2',accepted_count=0)]
    configured=combination(grant=grant,baseline=baseline)
    configure(lane,configured)
    result=run(lane,'A-extra-P')
    binding=originals(lane)[0]['mechanism_binding']
    assert binding['grant']==dict(source_a=3,source_a_sha256='d'*64)
    assert binding['mechanism_ref']=='h001.m1' and binding['source_h_sha256']=='c'*64
    rejected(lane,lane.source('do-not-reuse-A-extra'))
    # Re-loading the same frozen grant does not erase its accepted original.
    configure(lane,configured)
    rejected(lane,lane.source('same-A-new-script'))
    assert lane.cli('query','--call-id',result['call_id'])['state']=='succeeded'
    assert lane.cli('lookup','--call-id',result['call_id'])['state']=='succeeded'
    collected=lane.cli('collect','--call-id',result['call_id'])
    assert collected['status']=='collected' and collected['outputs']
    assert all(e.proof(item['local_path'])['sha256']==item['sha256'] for item in collected['outputs'])
    assert len(originals(lane))==len(list(lane.records.glob('calls/*/process.json')))==1


@pytest.mark.parametrize('kind',['missing','ambiguous','unauthorized'])
def test_scientific_label_must_resolve_exactly_before_accept_or_process(lane,kind):
    if kind=='ambiguous':configure(lane,combination(ambiguous=True))
    source=lane.source('unbound-'+kind)
    args=['run','--script',source,'--new-plan']
    if kind!='missing':args+=['--mechanism','same' if kind=='ambiguous' else 'not-authorized']
    reply=lane.cli(*args,expected=2)
    assert reply['status']=='unresolved' and 'exact authorized H mechanism' in reply['note']
    assert originals(lane)==[] and not list(lane.records.glob('calls/*/process.json'))
    assert not list(lane.records.glob('.prepared-*'))
    if lane.kind=='cov':assert not (lane.root/'runs/backend-calls.jsonl').exists()
    else:assert not list(lane.records.rglob('starts.log'))


def test_completed_receipt_cannot_change_exact_a_authorization(lane):
    grant=dict(mechanism_ref='h001.m1',source_a=3,source_a_sha256='d'*64,extra_calls=1,used_calls=0)
    configure(lane,combination(grant=grant,baseline=[dict(mechanism_ref='h001.m1',accepted_count=1),
        dict(mechanism_ref='h001.m2',accepted_count=0)]))
    result=run(lane,'exact-A-original')
    path=lane.records/'calls'/result['call_id']/'completed.json'
    receipt=json.loads(path.read_text());receipt['mechanism_binding']['grant']['source_a_sha256']='e'*64
    path.write_text(json.dumps(receipt))
    reply=lane.cli('query','--call-id',result['call_id'],expected=3)
    assert reply['status']=='integrity_error'
    assert len(list(lane.records.glob('calls/*/process.json')))==1
