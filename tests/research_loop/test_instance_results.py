"""Selective result rendering and exact readers; no install/model/browser."""
import base64
import hashlib
from urllib.parse import urlencode

import pytest

from scidiscovery.research_loop import (budget, contracts as c, history, instance_control as control,
    instance_render as render, selection)
from test_execution_authority import prepare
from test_history_handoff import finish
from test_instance_ui import session
from test_instance_science import read


def test_result_cards_preserve_exact_ties_and_do_not_replace_empty_a_recommendation():
    metric=1.2345678901234567
    candidates=[dict(id=key,label=key,evaluation_key='eval-<script>',metric=metric,direction='min',status='ok')
        for key in ('candidate-a','candidate-b')]
    candidates.append(dict(id='candidate-unknown',label='Unknown retained candidate',evaluation_key='eval-<script>',
        metric=None,direction='min',status='unknown'))
    facts=[dict(step=1,role='W',recommendation=None,coverage='complete',candidates=candidates,
        current_candidate=None,actual_submission=None),dict(step=2,role='A',recommendation='candidate-a',
        coverage=None,candidates=[],current_candidate=None,actual_submission=None)]
    comparison=selection.project(facts)
    # These are existing frozen omissions, not another UI ranking calculation.
    comparison['proxy_highest'][0]['ties_omitted_count']=2
    comparison['proxy_groups_omitted_count']=3
    job=dict(role='A',history=dict(view=dict(candidates=comparison)),execution_config=dict(private_host_token='DO-NOT-RENDER'))
    payload=dict(summary='Exact <script>finding</script>',scientific_result='The observed proxy remains inconclusive.',
        candidate_recommendation=None,limitations=['Bounded evidence.'],next_action='finish')
    page=render.result(3,job,payload,dict(materials=[])).decode()
    assert str(metric) in page and 'candidate-a, candidate-b' in page
    assert '2 additional tied candidates omitted' in page and '3 comparison groups omitted' in page
    assert 'unknown_candidate_count' in page and 'candidate-unknown' in page
    assert 'input boundary' in page and 'later evidence is not included' in page
    assert 'This sealed A makes no candidate recommendation' in page
    assert 'This sealed A recommends:' not in page and 'Earlier A recommendation' in page
    assert '<details>' in page and '/nodes/3/science' in page
    assert '<script>' not in page and '&lt;script&gt;' in page and 'DO-NOT-RENDER' not in page
    assert '<iframe' not in page and '<img' not in page
    digest=base64.b64encode(hashlib.sha256(render.CSS.encode()).digest()).decode()
    assert render.STYLE_SOURCE=="'sha256-"+digest+"'" and 'unsafe-inline' not in render.CSP
    formal=render.result(4,dict(job,formal_review=True),dict(payload,verdict='pass'),dict(materials=[])).decode()
    assert 'not an ordinary A recommendation' in formal
    empty=render.result(5,dict(role='W'),payload,dict(materials=[])).decode()
    assert 'No ranked group is available' in empty and 'Observation coverage: unknown' in empty


def test_result_routes_are_read_only_exact_and_independent_of_live_clock(tmp_path,monkeypatch):
    root,key=prepare(tmp_path,enabled=False)
    finish(root,1,'H',[],action='analyze',text='<script>scientific text</script>',files={'report.html':'<script>attachment only</script>'})
    c.build_job(root,2,'A',[1])  # Unsealed record must not become a result.
    ui,_=session(root,key)
    _,_,headers=ui.get('/view?'+urlencode({'token':ui.read_token}),host=ui.host)
    cookie=headers['Set-Cookie']
    before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    def forbidden(*args,**kwargs):pytest.fail('Results must not sample clocks or rebuild historical projections')
    monkeypatch.setattr(budget,'clock_stamp',forbidden)
    monkeypatch.setattr(control,'status',forbidden)
    monkeypatch.setattr(history,'rebuild',forbidden)
    monkeypatch.setattr(selection,'project',forbidden)
    index=ui.get('/results',host=ui.host,cookie=cookie)[1]
    assert b'/results/1' in index and b'/results/2' not in index
    assert b'/results/1' not in ui.get('/results?after=1',host=ui.host,cookie=cookie)[1]
    status,page,_=ui.get('/results/1',host=ui.host,cookie=cookie)
    assert status==200 and b'&lt;script&gt;scientific text&lt;/script&gt;' in page
    assert b'/nodes/1/science' in page and b'/nodes/1/materials' in page and b'action="/control/' not in page
    _,raw,headers=ui.get('/nodes/1/science',host=ui.host,cookie=cookie)
    assert headers['Content-Type'].startswith('application/json') and b'<script>scientific text</script>' in read(raw)
    _,artifact,headers=ui.get('/nodes/1/materials/1',host=ui.host,cookie=cookie)
    assert headers['Content-Disposition'].startswith('attachment;') and read(artifact)==b'<script>attachment only</script>'
    assert before=={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    for target in ('/results?after=0&after=1','/results/../operator.key','/results/1?path=operator.key','/results/2'):
        with pytest.raises(ValueError):ui.get(target,host=ui.host,cookie=cookie)
    with pytest.raises(PermissionError):ui.get('/results/1',host=ui.host)
    with pytest.raises(PermissionError):ui.get('/results',host='other.invalid',cookie=cookie)
    path=root/'jobs/001.json';raw=path.read_bytes();mode=path.stat().st_mode&0o777
    path.chmod(0o600);path.write_bytes(raw+b'\n')
    with pytest.raises(ValueError,match='changed'):ui.get('/results/1',host=ui.host,cookie=cookie)
    path.write_bytes(raw);path.chmod(mode)
    original=root/'native-evidence/001/science-output.json';original.chmod(0o600);original.write_bytes(b'{}')
    with pytest.raises(ValueError,match='changed'):ui.get('/results/1',host=ui.host,cookie=cookie)
