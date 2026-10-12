"""Public constraints and masking; no historical hidden answers or model work."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from scidiscovery.research_loop import guidance, selection

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('public_selection_replay',ROOT/'scripts/acceptance/rootless_public_selection_replay.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)
FIXTURE=json.loads((ROOT/'docs/plans/fixtures/rootless-selection-actions-v1.json').read_text())


@pytest.mark.parametrize('case',FIXTURE['cases'],ids=lambda case:case['name'])
def test_frozen_allowed_actions(case):
    original=copy.deepcopy(case)
    if 'error' in case['expected']:
        with pytest.raises(ValueError,match=case['expected']['error']):selection.project(**case['projection'])
    else:
        view=selection.project(**case['projection']);before=copy.deepcopy(view)
        result=replay.allowed_actions(view,request=case['request'],source_status=case['source_status'])
        assert all(result[key]==value for key,value in case['expected'].items())
        assert view==before
        assert result['audit_request_is_final_recommendation'] is False
    assert case==original


def test_a_guidance_is_bounded_conditional_and_scientific():
    assert sum(len(text.encode()) for text in guidance.DEFAULT.values())<=2048
    advice=guidance.DEFAULT['A']
    assert 'If audit action is available' in advice and 'not a final recommendation' in advice
    assert 'not target evidence' in advice and 'not failed or qualified' in advice
    assert 'must not force candidate swaps or elimination' in advice


def public_manifest(tmp_path):
    root=tmp_path/'instance';(root/'runs').mkdir(parents=True)
    ledger=root/'runs/results.jsonl';ledger.write_text(json.dumps(dict(run_id=1,ok=True,val_score=.75))+'\n')
    return dict(groups={'fixture':dict(instance=str(root),ledger_sha256=hashlib.sha256(ledger.read_bytes()).hexdigest(),
        public_conditions={name:'a'*64 for name in ('train.csv','val.csv','meta.json','runner.py','exp_cli.py')},actual_submission=1,
        candidates=[dict(run_id=1,audit=dict(audit_score=.7,leakage_flag=False),official_reward=.9)])})


def test_masked_inputs_are_noninterfering_and_unbound_audit_not_qualified(tmp_path):
    manifest=public_manifest(tmp_path);original=copy.deepcopy(manifest)
    public=replay.export_public(manifest)
    mutated=copy.deepcopy(manifest)
    mutated['hidden_score']=999
    mutated['groups']['fixture']['candidates'][0]['official_reward']=-99
    mutated['groups']['fixture']['public_conditions']['hidden_test_conditions']='secret'
    assert replay.export_public(mutated)==public
    result=replay.replay(public)['fixture'];view=result['view']
    assert view['target_best'] is None and view['public_audits'][0]['status']=='unknown'
    assert result['historical_audits'][0]['recorded_audit']=='recorded_unbound'
    assert result['choice_generated'] is False and result['reward_generated'] is False
    assert result['probes'][0]['advice']['audit_required'] is True
    assert result['probes'][0]['advice']['next_step']=='resolve_source_or_defer'
    assert 'official_reward' not in json.dumps(public) and 'hidden' not in json.dumps(public)
    assert manifest==original


@pytest.mark.parametrize('field',['hidden_score','official_reward'])
def test_normalized_hidden_field_is_rejected_without_action(tmp_path,field):
    view=selection.project(replay.export_public(public_manifest(tmp_path))['groups']['fixture']['records'])
    view[field]=.9
    with pytest.raises(ValueError,match='non_public_field'):replay.allowed_actions(view)


def test_rule_hash_is_checked_before_opening_pool(monkeypatch,tmp_path):
    monkeypatch.setattr('sys.argv',['replay','--pool-manifest',str(tmp_path/'absent'),
        '--rules-sha256','0'*64,'--output',str(tmp_path/'out')])
    with pytest.raises(ValueError,match='Freeze rule source hash'):replay.main()
    assert not (tmp_path/'out').exists()
