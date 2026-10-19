"""A owns changing scientific criteria; control requires an explicit account."""
import copy

import jsonschema
import pytest

from scidiscovery.research_loop import budget, contracts as c, controller, continuation, execution, native
from scidiscovery.research_loop.output_repair import OutputRepairRequired
from test_candidate_response_contract import response
from test_history_handoff import selection_explanation
from test_worker_resume import REPAIR_FAKE, instance


def revised():
    return dict(criteria='Retain the candidate improving the measured noise control.',
        criteria_change=dict(status='revised',
            prior_criteria='The W design required improvement against both declared controls.',
            changes='Replace the dual-control Pareto rule with the measured noise-control criterion.',
            evidence='W002 report, comparison table: the candidate did not dominate the second control; target robustness remains unmeasured.',
            accepted_tradeoffs='Accept the unresolved second-control comparison and no claim of global dominance.'))


@pytest.mark.parametrize('final',[False,True])
@pytest.mark.parametrize('missing',['selection_explanation','criteria','status','prior_criteria','changes','evidence','accepted_tradeoffs'])
def test_missing_selection_account_requires_same_output_repair(tmp_path,final,missing):
    payload=response('W002-C001');payload['next_action']='deliver' if final else 'continue_w'
    payload['selection_explanation']=revised()
    if missing=='selection_explanation':payload.pop(missing)
    elif missing=='criteria':payload['selection_explanation']['criteria']='  '
    else:payload['selection_explanation']['criteria_change'].pop(missing)
    raw=tmp_path/'science-output.json';c.write(raw,payload);original=raw.read_bytes()
    with pytest.raises(OutputRepairRequired,match='selection_explanation') as error:
        c.science_payload(raw,'A',final_only=final,final_delivery=final)
    assert error.value.code=='selection_explanation_incomplete'
    assert raw.read_bytes()==original


@pytest.mark.parametrize('explanation',[selection_explanation(),revised()])
def test_complete_declaration_is_schema_valid_without_scientific_scoring(tmp_path,explanation):
    payload=response('W002-C001');payload['selection_explanation']=explanation
    raw=tmp_path/'science-output.json';c.write(raw,payload)
    jsonschema.Draft202012Validator(c.selection_explanation_schema()).validate(explanation)
    assert c.science_payload(raw,'A')==payload
    # The framework cannot prove the scientific truth or sufficiency of text.
    changed=copy.deepcopy(payload);changed['selection_explanation']['criteria_change']=dict(
        status='revised',prior_criteria='A declared prior rule.',changes='A declared revision.',
        evidence='A claimed locator: W002 section 3.',accepted_tradeoffs='A declared cost.')
    c.write(raw,changed)
    assert c.science_payload(raw,'A')==changed


def test_planning_a_does_not_need_an_invented_selection(tmp_path):
    payload=response();payload.pop('selection_explanation')
    raw=tmp_path/'science-output.json';c.write(raw,payload)
    assert c.science_payload(raw,'A')==payload


def author_fake(*,repeated=False):
    program=REPAIR_FAKE.replace("candidate_recommendation=None,progress_assessment=None",
        "candidate_recommendation='unavailable-fixture',progress_assessment=None")
    insertion="\nif resume:payload['selection_explanation']="+repr(selection_explanation())+'\n'
    if repeated:insertion='\n'
    program=program.replace("destination=pathlib.Path",insertion+"destination=pathlib.Path")
    # Keep the original helper's known output; the first response lacks only
    # the selection declaration, and the resumed same A fills it.
    return program


@pytest.mark.parametrize('final',[False,True])
@pytest.mark.process_e2e
def test_selection_account_is_repaired_by_same_a_without_replaying_work(tmp_path,final):
    root=instance(tmp_path,fake=author_fake(),output_repair=True,steps=1 if final else 4,
        max_tokens=1 if final else 1000,cap=1 if final else 100)
    if final:budget.begin_closeout(root,0,1,'Exact final A declaration fixture',final_only=True)
    job=c.build_job(root,1,'A',[],**(dict(final_report=dict(source_cutoff=0,stopped_original=None)) if final else {}))
    (c.workspace(root,1)/'work').mkdir(exist_ok=True)
    (c.workspace(root,1)/'work/output-kind').write_text('selection')
    c.write(root/'host-started.json',budget.clock_stamp());budget.transition(root,'advance','fixture')
    settings=(root/'settings.json').read_bytes()
    result=native.execute_native(root,1)
    origin=execution.origin(root,1);current=execution.record(root,1)
    assert current==origin/'continuations/001'
    assert result['candidate_recommendation']=='unavailable-fixture'
    assert result['selection_explanation']==selection_explanation()
    assert c.read(current/'native-intent.json')['output_repair']['code']=='selection_explanation_incomplete'
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\nresume\n'
    assert (c.workspace(root,1)/'work/completed-experiment').read_text()=='one completed execution'
    assert native.usage(root)['observed_tokens']==28
    assert (root/'settings.json').read_bytes()==settings and not (root/'jobs/002.json').exists()
    if final:
        grant=budget.final_a_barrier(root)
        assert grant['step']==1
        intents=[c.read(path/'native-intent.json') for path in (origin,current)]
        assert intents[0]['budget_slice']['final_return']==intents[1]['budget_slice']['final_return']
        assert intents[1]['budget_slice']['previous_tokens']==14
        assert budget.final_a_return(root,job,intents[1])==grant
        altered=copy.deepcopy(intents[1]);altered.pop('output_repair')
        with pytest.raises(ValueError,match='Final A return'):budget.final_a_return(root,job,altered)
        outcome=c.read(current/'native-outcome.json')
        assert outcome['final_a_completion']['final_overrun']['observed_node_tokens']==28
        assert len([event for event in budget._events(root,c.settings(root))[0] if event['kind']=='final_a_return'])==1
        assert controller.run(root)['status']=='final_a_completed'


@pytest.mark.process_e2e
def test_final_selection_output_repair_does_not_retry_unknown_execution(tmp_path):
    root=instance(tmp_path,fake=author_fake(),output_repair=True,steps=1)
    budget.begin_closeout(root,0,1,'Exact final unknown fixture',final_only=True)
    c.build_job(root,1,'A',[],final_report=dict(source_cutoff=0,stopped_original=None))
    (c.workspace(root,1)/'work').mkdir(exist_ok=True)
    (c.workspace(root,1)/'work/output-kind').write_text('unknown')
    result=controller.run(root)
    assert result['status']=='closeout_native_unsealed'
    assert len(execution.records(root,1))==1
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\n'


@pytest.mark.process_e2e
def test_final_selection_repair_retains_original_finite_attempt_limit(tmp_path):
    root=instance(tmp_path,fake=author_fake(repeated=True),output_repair=True,attempts=1,steps=1,max_tokens=1)
    budget.begin_closeout(root,0,1,'Exact final finite-repair fixture',final_only=True)
    c.build_job(root,1,'A',[],final_report=dict(source_cutoff=0,stopped_original=None))
    (c.workspace(root,1)/'work').mkdir(exist_ok=True)
    (c.workspace(root,1)/'work/output-kind').write_text('selection')
    c.write(root/'host-started.json',budget.clock_stamp());budget.transition(root,'advance','fixture')
    with pytest.raises(continuation.ResumeUnavailable,match='worker_resume_limit'):native.execute_native(root,1)
    assert len(execution.records(root,1))==2
    assert (c.workspace(root,1)/'work/launches').read_text()=='exec\nresume\n'
    assert not (execution.origin(root,1)/'result-identity.json').exists()
