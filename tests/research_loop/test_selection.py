"""Synthetic public facts only; no hidden pool or scientific execution."""
import copy
import json
from pathlib import Path

import pytest

from scidiscovery.research_loop import selection

FIXTURE = Path(__file__).resolve().parents[2] / 'scripts/acceptance/fixtures/rootless_selection/selection.json'


@pytest.mark.parametrize('case', json.loads(FIXTURE.read_text())['cases'], ids=lambda case: case['name'])
def test_frozen_public_selection_cases(case):
    data = copy.deepcopy(case['input'])
    if 'error' in case['expected']:
        with pytest.raises(ValueError, match=case['expected']['error']):
            selection.project(**data)
        return
    result = selection.project(**data)
    expected = case['expected']
    assert data == case['input']
    assert len(selection._bytes(result)) <= 4096
    expected_ids=list(dict.fromkeys(item['id'] for row in sorted(data['records'],key=lambda row:row['step']) for item in row['candidates']))
    assert [row['id'] for row in result['candidate_facts']]==expected_ids[:len(result['candidate_facts'])]
    assert len(result['candidate_facts'])+result['candidate_facts_omitted_count']==len(expected_ids)
    if 'audit_states' in expected:
        audits={row['candidate_id']:row['status'] for row in result['public_audits']}
        assert {cid:audits.get(cid,'unknown') for cid in expected['audit_states']}==expected['audit_states']
        assert set(audits)=={row['candidate_id'] for row in data.get('audits',[])}
    for field in ('historical_a_recommendation', 'latest_a_step', 'coverage', 'scope'):
        if field in expected:
            assert result[field] == expected[field]
    for field in ('a_recommended', 'current_candidate', 'observed_actual_submission'):
        if field in expected:
            assert (result[field]['candidate_id'] if result[field] else None) == expected[field]
    if 'delivery_state' in expected:
        assert result['delivery']['state'] == expected['delivery_state']
    if 'last_confirmed' in expected:
        assert result['delivery']['last_confirmed']['candidate_id'] == expected['last_confirmed']
        assert result['delivery']['current_confirmed'] is None


def candidate(cid, metric=1, key='public-v1', direction='max'):
    return dict(id=cid, label=cid, metric=metric, evaluation_key=key, direction=direction, status='ok')


def record(candidates, step=2):
    return dict(step=step, role='W', recommendation=None, coverage='complete', candidates=candidates,
                current_candidate=None, actual_submission=None)


def test_ties_versions_and_missing_metrics_stay_visible_in_observed_order():
    result = selection.project([record([candidate('P'), candidate('Q'), candidate('R', key='public-v2'),
                                       candidate('S', 0, direction='min'), candidate('unscored', None)])])
    assert [row['id'] for row in result['candidate_facts']] == ['P','Q','R','S','unscored']
    assert result['candidate_facts_omitted_count']==0
    assert 'target_best' not in result


@pytest.mark.parametrize('changes', [{'metric': float('nan')}, {'hidden_reward': .5}])
def test_invalid_public_candidate_facts(changes):
    with pytest.raises(ValueError):
        selection.project([record([dict(candidate('P'), **changes)])])


def test_missing_and_free_scientific_metadata_do_not_gate_candidate_catalogue():
    rows=[dict(id='unmeasured',status='ok'),dict(candidate('free'),label={'text':'unbounded'},
        evaluation_key={'conditions':['A','B']},direction='maximize after feasibility',metric=None)]
    result=selection.project([record(rows)])
    assert [row['id'] for row in result['candidate_facts']]==['unmeasured','free']
    assert result['candidate_facts'][0]['metric'] is None
    assert result['candidate_facts'][1]['direction']==rows[1]['direction']
    assert selection.shortlist([record(rows)])['members'][0]['metric'] is None


def test_conflicting_immutable_candidate_identity_rejected():
    with pytest.raises(ValueError, match='identity changed'):
        selection.project([record([candidate('P')]), record([candidate('P', 2)], step=4)])


def test_public_inputs_drops_private_receipts_without_mutation():
    raw = [dict(step=2, role='W', recommendation=None, view={'summary': 'science'},
                observation=dict(coverage={'status': 'partial', 'note': 'bounded'},
                    candidates=[dict(candidate('P'), implementation='private/path', evidence=[{'sha256': 'private'}])],
                    current_candidate={'candidate_id': 'P', 'evidence': []},
                    actual_submission={'candidate_id': 'P', 'artifact': {'retention': 'archived', 'path': 'private'}, 'evidence': []},
                    contexts=[{'private': 'execution'}]), source={'private': 'binding'})]
    original = copy.deepcopy(raw)
    result = selection.public_inputs(raw)
    assert raw == original
    assert set(result[0]['candidates'][0]) == selection.CANDIDATE_FIELDS
    assert 'private' not in json.dumps(result)
    assert selection.project(result)['coverage'] == 'partial'
    raw[0]['observation']['candidates'][0]['hidden_score'] = 1
    with pytest.raises(ValueError, match='non_public_field'):
        selection.public_inputs(raw)


def test_byte_bound_omissions_and_exact_comparison_before_display_clipping():
    rows = [candidate(f'候选{i:03}', key='评估' * 300 + str(i)) for i in range(100)]
    result = selection.project([record(rows)])
    assert len(selection._bytes(result)) <= 4096
    assert len(result['candidate_facts']) + result['candidate_facts_omitted_count'] == 100
    assert result['public_audits']==[] and result['audits_omitted_count']==0
    assert all(row['evaluation_key'] == rows[index]['evaluation_key'] for index,row in enumerate(result['candidate_facts']))
    assert 'target_best' not in result


def test_audit_does_not_inherit_parent_or_status_ok():
    result = selection.project([record([candidate('P'), candidate('Q')])], audits=[
        dict(candidate_id='P', status='completed', artifact_bound=True, leakage_flag=False)])
    assert result['public_audits'] == [dict(candidate_id='P', status='public_audit_passed')]
    assert result['delivery']['state'] == 'unknown'


def test_unknown_confirmed_reference_is_not_silently_preserved():
    with pytest.raises(ValueError, match='Unknown confirmed'):
        selection.project([record([candidate('P')])], delivery=dict(state='unknown', last_confirmed={'candidate_id': 'missing'}))


def brief_fixture():
    from scidiscovery.research_loop import lineage
    rows = [record([candidate('P'), candidate('Q', .8)], step=2),
            dict(record([], step=3), role='A', recommendation='P', coverage=None),
            dict(record([], step=5), role='A', recommendation=None, coverage=None)]
    rows[0]['current_candidate'] = {'candidate_id': 'Q'}
    raw = []
    for row in rows:
        obs = None if row['coverage'] is None else dict(coverage={'status': row['coverage'], 'note': 'public'},
            candidates=[dict(item, implementation=None, evidence=[]) for item in row['candidates']],
            current_candidate=row['current_candidate'], actual_submission=None)
        raw.append(dict(step=row['step'], role=row['role'], recommendation=row['recommendation'], observation=obs,
            view=dict(summary='scientific result', summary_omitted_chars=0, limitations=['applicability unknown'],
                      limitations_omitted_count=0, conclusion_pages=[f"inputs/history/nodes/{row['step']:03}/0001.json"])))
    return raw, lineage.candidate_view(raw), {'relations': [], 'coverage': 'complete'}, {'candidates': 'inputs/history/candidates/0001.json'}


def test_single_brief_marker_uses_one_current_recommendation_authority():
    from scidiscovery.research_loop import lineage
    records, candidates, graph, indexes = brief_fixture()
    default = lineage.brief(records, None, graph, candidates, indexes)
    explicit_old = lineage.brief(records, None, graph, candidates, indexes, selection_protocol=0)
    assert selection._bytes(default) == selection._bytes(explicit_old)
    assert default['candidates']['a_recommended'] is None
    assert default['candidates']['historical_a_recommendation']['candidate_id'] == 'P'
    assert 'selection_protocol' not in default['candidates']
    new = lineage.brief(records, None, graph, candidates, indexes, selection_protocol=1)
    assert new['candidates']['a_recommended'] is None
    assert new['candidates']['historical_a_recommendation']['candidate_id'] == 'P'
    assert new['candidates']['current_candidate']['candidate_id'] == 'Q'
    assert new['candidates']['delivery']['state'] == 'unknown'
    assert 'target_best' not in new['candidates']
    assert 'selection' not in new  # replace the one candidate slice, never append a second packet
    assert len(selection._bytes(new)) <= 4096


def test_optional_projection_unavailable_does_not_publish_hidden_values():
    from scidiscovery.research_loop import lineage
    records, candidates, graph, indexes = brief_fixture()
    records[0]['observation']['candidates'][0]['hidden_score'] = .999
    new = lineage.brief(records, None, graph, candidates, indexes, selection_protocol=1)
    assert new['candidates']['scope'] == 'unavailable'
    assert 'target_best' not in new['candidates']
    assert 'hidden_score' not in json.dumps(new)
    assert '.999' not in json.dumps(new)
    assert new['indexes'] == indexes


def test_entire_single_brief_remains_bounded_after_selection_preview():
    from scidiscovery.research_loop import lineage
    records, _, graph, indexes = brief_fixture()
    records[0]['observation']['candidates'] = [dict(candidate(f'候选{i:03}', key='版本' * 300 + str(i)), implementation=None, evidence=[]) for i in range(100)]
    records[0]['observation']['current_candidate'] = None
    for row in records[1:]:
        row['recommendation'] = None
    candidates = lineage.candidate_view(records)
    new = lineage.brief(records, None, graph, candidates, indexes, selection_protocol=1)
    assert len(selection._bytes(new)) <= 4096
    view = new['candidates']
    assert len(view['candidate_facts']) + view['candidate_facts_omitted_count'] == 100
    assert view['public_audits']==[] and view['audits_omitted_count']==0


def test_mixed_step_types_are_optional_projection_value_errors():
    with pytest.raises(ValueError, match='record identity'):
        selection.project([record([candidate('P')]), record([], step='4')])


@pytest.mark.parametrize('field', ['coverage', 'status'])
def test_enum_list_is_optional_projection_value_error(field):
    row = record([candidate('P')])
    if field == 'coverage':
        row[field] = []
    else:
        row['candidates'][0][field] = []
    with pytest.raises(ValueError):
        selection.project([row])


def test_direction_scientific_json_is_preserved_without_becoming_execution_status():
    row=record([candidate('P',direction=[])])
    result=selection.project([row])
    assert result['candidate_facts'][0]['direction']==[]
    assert result['candidate_facts'][0]['status']=='ok'
    assert selection.shortlist([row])['members'][0]['direction']==[]


def test_audit_request_preserves_prior_choice_and_observed_facts():
    original = record([candidate('P')])
    choice = dict(record([], step=3), role='A', recommendation='P')
    audit = dict(record([candidate('Q', 2)], step=4), role='A', audit_request=True,
                 actual_submission=dict(candidate_id='Q', artifact_retention='unknown'))
    result = selection.project([original, choice, audit])
    assert result['a_recommended'] == dict(candidate_id='P', author_step=3)
    assert result['latest_a_step'] == 3
    assert result['candidate_count'] == 2
    assert result['observed_actual_submission']['candidate_id'] == 'Q'
    assert [row['id'] for row in result['candidate_facts']] == ['P','Q']
    # A later scientific null remains a real choice to clear the recommendation.
    later = dict(record([], step=5), role='A')
    assert selection.project([original, choice, audit, later])['a_recommended'] is None


@pytest.mark.parametrize('changes', [dict(role='W'), dict(audit_request=False), dict(recommendation='P')])
def test_audit_defer_marker_cannot_hide_a_different_author_or_choice(changes):
    audit = dict(record([candidate('P')]), role='A', audit_request=True)
    with pytest.raises(ValueError, match='defers candidate recommendation'):
        selection.project([dict(audit, **changes)])


def test_public_projection_retains_only_the_host_defer_flag():
    raw = dict(step=3, role='A', recommendation=None, observation=None, audit_request=True,
               audit_private_path='not public')
    view = selection.public_inputs([raw])
    assert view[0]['audit_request'] is True and 'audit_private_path' not in view[0]
    assert selection.project(view)['latest_a_step'] is None
