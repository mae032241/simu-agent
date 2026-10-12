"""New selection layout is job-frozen; old science and guidance stay byte exact."""
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import contracts as c, controller, execution, guidance
from test_history_handoff import finish


def prepare(tmp_path, *, selection_protocol=1, advice=None):
    public=tmp_path/'public';public.mkdir();objective=public/'objective';objective.write_text('Use only public comparisons and sealed scientific judgments.')
    adapter=tmp_path/'observer.py';adapter.write_text('''import json,sys
r=json.load(sys.stdin)
c=[dict(id='P',label='Observed candidate P',implementation=None,evaluation_key='public-val-v1',metric=.8,direction='max',status='ok',evidence=['project/global/objective.md'])] if r['step']==1 else []
print(json.dumps(dict(candidates=c,current_candidate=None,actual_submission=None,coverage=dict(status='complete',note='Public fixture boundary'))))
''')
    root=tmp_path/'instance'
    controller.prepare(root,objective,public,['fake'],max_tokens=100000,max_seconds=3600,max_steps=8,
        model='fake',reasoning_effort='high',search_policy=None,selection_protocol=selection_protocol,
        role_guidance=guidance.DEFAULT if advice is None else advice,history_observer=dict(adapter=str(adapter),config={}))
    return root


def test_new_job_freezes_selection_and_null_a_is_not_an_old_recommendation(tmp_path):
    root=prepare(tmp_path)
    finish(root,1,'H',[]);finish(root,2,'W',[1]);finish(root,3,'A',[2],recommendation='P')
    job,_,_=finish(root,4,'H',[3])
    assert c.settings(root)['selection_protocol']==1 and job['selection_protocol']==1
    before=c.science_view(job,root)['lineage']['candidates']
    assert before['a_recommended']['candidate_id']=='P'
    finish(root,5,'A',[4],recommendation=None)
    later=c.build_job(root,6,'H',[5]);view=c.science_view(later,root)['lineage']['candidates']
    assert view['selection_protocol']==1 and view['a_recommended'] is None
    assert view['historical_a_recommendation']['candidate_id']=='P'
    assert view['target_best'] is None and view['delivery']['state']=='unknown'
    assert 'role_guidance' not in c.result_schema('A',8)['properties']
    assert sum(len(text.encode()) for text in c.settings(root)['role_guidance'].values())<=2048


def test_old_t2_t3_job_marker_and_literal_do_not_follow_current_defaults(tmp_path,monkeypatch):
    old_advice={**guidance.DEFAULT,'A':'Previously frozen scientific advice, unchanged by new rules.'}
    root=prepare(tmp_path,selection_protocol=None,advice=old_advice)
    finish(root,1,'H',[]);finish(root,2,'W',[1]);job,work,record=finish(root,3,'A',[2],recommendation='P')
    assert 'selection_protocol' not in job and 'selection_protocol' not in c.settings(root)
    assert job['role_guidance']==old_advice['A']
    originals={p:p.read_bytes() for p in (root/'settings.json',root/'jobs/003.json',work/'science-task.json',record/'science-output.json',record/'result-identity.json')}
    monkeypatch.setitem(guidance.DEFAULT,'A','Changed future default')
    c.build_job(root,3,'A',[2]);c.validate(work)
    assert 'selection_protocol' not in c.science_view(job,root)['lineage']['candidates']
    assert all(p.read_bytes()==data for p,data in originals.items())


@pytest.mark.parametrize('bad',[True,0,2,'1'])
def test_invalid_selection_marker_cannot_prepare(tmp_path,bad):
    with pytest.raises(ValueError):prepare(tmp_path,selection_protocol=bad)
    assert not (tmp_path/'instance').exists()


def test_prepared_selection_marker_cannot_disagree_with_its_frozen_view(tmp_path):
    root=prepare(tmp_path);finish(root,1,'H',[])
    job=c.build_job(root,2,'W',[1]);work=c.workspace(root,2)
    changed={**job,'selection_protocol':0}
    c.write(root/'jobs/002.json',changed)
    with pytest.raises(ValueError,match='Frozen selection projection'):
        c._validate_inputs(root,work,changed)
    assert not (execution.origin(root,2)/'native-intent.json').exists()
