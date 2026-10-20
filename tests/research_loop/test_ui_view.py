"""Workbench view models: plain data from sealed/control reads, no HTML, no writes."""
import json
import os
from pathlib import Path

import pytest

from scidiscovery.research_loop import instance_control as control, ui_view
from test_execution_authority import prepare
from test_history_handoff import finish


def test_numbers_durations_and_metrics_are_readable_without_rounding_science():
    assert ui_view.fmt_tokens(5846087) == '584.6 万'
    assert ui_view.fmt_tokens(5000000) == '500 万'
    assert ui_view.fmt_tokens(1234) == '1,234' and ui_view.fmt_tokens(30) == '30'
    assert ui_view.fmt_tokens(None) == '未记录'
    assert ui_view.fmt_duration(2636.5) == '43 分 57 秒'
    assert ui_view.fmt_duration(10800) == '3 小时' and ui_view.fmt_duration(3720) == '1 小时 2 分'
    assert ui_view.fmt_duration(45) == '45 秒' and ui_view.fmt_duration(None) == '未记录'
    assert ui_view.percent(5846087, 5000000) == 117 and ui_view.percent(1, None) is None
    assert ui_view.fmt_metric(0.91) == '0.91' and ui_view.fmt_metric(1.2345678901) == '1.2346'
    assert ui_view.fmt_metric(None) == '—' and ui_view.fmt_metric(3) == '3' and ui_view.fmt_metric('n/a') == 'n/a'
    assert ui_view.first_sentence('First claim. Second claim.') == 'First claim.'
    assert ui_view.first_sentence('第一句。第二句。') == '第一句。'
    assert ui_view.first_sentence(None) is None and ui_view.first_sentence('  ') is None
    assert ui_view.objective_title('\n# **Sparse** `inverse`\nbody', 'fallback') == 'Sparse inverse'
    assert ui_view.objective_title('', 'fallback') == 'fallback'
    assert len(ui_view.objective_title('x' * 80, 'f')) == 60


def test_metric_direction_comes_only_from_author_declaration():
    assert ui_view.direction_sense('higher recovery is better') == 'max'
    assert ui_view.direction_sense('min') == 'min' and ui_view.direction_sense('lower is better') == 'min'
    assert ui_view.direction_sense(None) is None and ui_view.direction_sense('see notes') is None
    same = [dict(evaluation_key='val', metric=0.5, direction='max'), dict(evaluation_key='val', metric=0.7, direction='max')]
    assert ui_view._candidate_extreme(same)['text'] == '最高 0.7（val）'
    undeclared = [dict(evaluation_key='val', metric=0.5), dict(evaluation_key='val', metric=0.7)]
    assert ui_view._candidate_extreme(undeclared)['text'] == '范围 0.5–0.7（val；方向未声明）'
    mixed = [dict(evaluation_key='a', metric=1.0, direction='max'), dict(evaluation_key='b', metric=9.0, direction='max')]
    assert ui_view._candidate_extreme(mixed)['text'] == '多种口径，见候选表'


class FakeReader:
    """Sealed nodes only; reading an unsealed node's original is a failure."""

    def __init__(self, nodes):
        self.root = Path('/nonexistent-ui-view-fixture')
        self.nodes = nodes

    def node(self, step):
        if self.nodes[step] is None:
            pytest.fail('Unsealed role lines must not read originals')
        return self.nodes[step]

    def observation(self, step):
        return self.nodes[step].get('observation')

    def role(self, step):
        return self.nodes[step]['job']['role'] if self.nodes[step] else 'W'


def sealed(step, role, payload, *, observation=None, materials=0, **job):
    return dict(job=dict(step=step, role=role, **job), payload=payload,
                seal=dict(materials=[{}] * materials, raw_sha256='x'), observation=observation)


def calls(count):
    return [dict(call_id=f'{index:04d}', accepted=dict(at=1)) for index in range(1, count + 1)] + [dict(call_id='rejected', accepted=None)]


def test_rounds_split_at_each_h_and_take_outcome_from_last_ordinary_a():
    candidates = [dict(id='local-a', label='alpha', evaluation_key='val', metric=0.8, direction='higher', status='ok'),
                  dict(id='local-b', label='beta', evaluation_key='val', metric=0.9, direction='higher', status='ok')]
    reader = FakeReader({
        1: sealed(1, 'E', dict(summary='Prepared evidence')),
        2: sealed(2, 'H', dict(summary='Plan', next_action='experiment', search_plan=dict(commitments=[
            dict(label=f'M{index}') for index in range(1, 7)]))),
        3: sealed(3, 'W', dict(summary='', scientific_result='Measured. More detail.'),
                  observation=dict(candidates=candidates, managed_calls=calls(4)), materials=7),
        4: sealed(4, 'A', dict(summary='Revise', next_action='revise_h', route_reason='Need a narrower question. Details.',
                               candidate_recommendation=None, search_review=dict(
                                   dispositions=[dict(mechanism_ref='h002.m1', status='screened'), dict(mechanism_ref='h002.m2', status='deferred')],
                                   next_focus=dict(mechanism_ref='h002.m2', action='improve')))),
        5: sealed(5, 'H', dict(summary='Revised', next_action='experiment', search_plan=None)),
        6: None,
    })
    nodes = [dict(step=1, role='E', state='seal_present_unverified'), dict(step=2, role='H', state='seal_present_unverified'),
             dict(step=3, role='W', state='seal_present_unverified'), dict(step=4, role='A', state='seal_present_unverified'),
             dict(step=5, role='H', state='seal_present_unverified'), dict(step=6, role='W', state='running', continuations=1)]
    mechanisms = ui_view.mechanism_labels(reader, [1, 2, 3, 4, 5, 6])
    assert mechanisms['h002.m2'] == 'M2'
    value = ui_view.rounds(reader, nodes, lambda text, limit=16384: str(text)[:limit], mechanisms=mechanisms,
                           labels={'local-a': 'alpha'})
    chronological = list(reversed(value['rounds']))
    assert [item['index'] for item in chronological] == [None, 1, 2]
    assert [item['steps'] for item in chronological] == [[1], [2, 3, 4], [5, 6]]
    assert [item['outcome'] for item in chronological] == ['进行中', '修订方向', '进行中']
    first = chronological[1]
    assert first['experiments'] == 4 and first['summary'] == '第 1 轮 · 修订方向 · W 4 次实验 · 最高 0.9（val）'
    h, w, a = first['h'], first['w'][0], first['a'][0]
    assert h['facts'][0]['value'].startswith('6 个：M1、M2、M3、M4、M5') and '另 1 个' in h['facts'][0]['value']
    assert w['one_line'] == 'Measured.' and w['facts'][0]['title'] == ui_view.EXPERIMENT_TOOLTIP
    assert w['links'][2]['label'] == '研究文件（7 份）'
    facts = {row['label']: row['value'] for row in a['facts']}
    assert facts['决定'] == '修订方向' and facts['理由'] == 'Need a narrower question.'
    assert facts['机制处置'] == '已筛查 1，暂缓 1' and facts['下一焦点'] == 'M2 · improve' and facts['候选推荐'] == '未推荐'
    assert chronological[2]['h']['facts'][0]['value'] == '未记录'
    running = chronological[2]['w'][0]
    assert running['sealed'] is False and running['one_line'] is None and running['facts'] == []
    assert running['links'] == [dict(label='公开进度', href='/nodes/6/progress?attempt=1')]


def test_formal_review_does_not_decide_round_and_closeout_is_labelled():
    reader = FakeReader({
        1: sealed(1, 'H', dict(summary='Plan', next_action='experiment')),
        2: sealed(2, 'A', dict(summary='Review', verdict='pass', next_action='finish'), formal_review=True),
        3: sealed(3, 'A', dict(summary='Final', next_action='deliver', candidate_recommendation='local-x'), purpose='closeout'),
        4: sealed(4, 'A', dict(summary='Late review', verdict='fail'), formal_review=True),
    })
    nodes = [dict(step=index, role=role, state='seal_present_unverified') for index, role in ((1, 'H'), (2, 'A'), (3, 'A'), (4, 'A'))]
    (item,) = ui_view.rounds(reader, nodes, lambda text, limit=16384: str(text), labels={'local-x': 'chosen <label>'})['rounds']
    assert item['outcome'] == '交付'
    assert [line['role_label'] for line in item['a']] == ['A · 正式评审', 'A · 最终评估', 'A · 正式评审']
    assert {row['label']: row['value'] for row in item['a'][1]['facts']}['候选推荐'] == '★ chosen <label>'


def test_status_matrix_maps_existing_presentation_without_new_control_semantics():
    def summary(state='seal_present_unverified', *, completed=False, waiting=False, active=False, paused=False, current=True, **options):
        node = dict(step=4, role='W', state=state) if current else None
        presentation = dict(current=node, state=state if current else 'ready', completed=completed, waiting=waiting, active=active)
        return ui_view.status_summary(presentation, dict(paused=paused), **options)
    assert summary(current=False)['state'] == 'ready' and summary(current=False)['badge'] == '未开始'
    active = summary('running', active=True, current_round=2, elapsed='12 分钟')
    assert active['state'] == 'active' and active['headline'] == '第 2 轮 · W 正在实验（已 12 分钟）'
    assert summary('running', active=True, paused=True)['state'] == 'pause_requested'
    assert summary(paused=True)['headline'] == '已暂停于第 4 阶段'
    assert summary(waiting=True, waiting_reason='Need data.')['headline'] == 'A 等待：Need data.'
    assert summary('unknown')['badge'] == '需要核对'
    assert summary(final_phase=True)['state'] == 'final'
    assert summary(exhausted=['tokens'])['headline'] == '预算已用完：tokens'
    assert summary(completed=True, completed_line='第 3 轮 · A 决定交付 x')['badge'] == '已完成'
    assert summary()['state'] == 'idle' and '第 4 阶段 · W · 实验 · 已有阶段结论' == summary()['stage']


def test_usage_cards_mark_overrun_unknown_usage_and_waiting():
    view = dict(budget=dict(max_tokens=5000000, max_seconds=10800.0, consumed_seconds=2636.5, waiting_seconds=600, max_steps=80),
                usage=dict(observed_tokens=5846087, unknown_steps=[3, 4]),
                closeout=dict(final_overrun=dict(shared_tokens_over_ceiling=846087)))
    value = ui_view.usage_stats(view, used_steps=11, candidates=dict(count=32, recommended=True, delivered=True))
    tokens = value['tokens']
    assert (tokens['value'], tokens['limit'], tokens['percent'], tokens['over']) == ('584.6 万', '500 万', 117, True)
    assert tokens['notes'] == ['最终 A 受保护，超出 84.6 万', '2 个阶段用量未知（下界）']
    assert (value['time']['value'], value['time']['limit'], value['time']['notes']) == ('43 分 57 秒', '3 小时', ['其中等待 10 分'])
    assert (value['steps']['value'], value['steps']['limit']) == ('11', '80')
    assert value['candidates']['value'] == '32' and value['candidates']['notes'] == ['A 推荐 1', '已交付 1']
    missing = ui_view.usage_stats({})
    assert missing['tokens']['value'] == '未记录' and missing['time']['limit'] == '未记录' and missing['candidates']['value'] == '未记录'


def test_candidate_rows_keep_observation_order_groups_marks_and_missing_values():
    index = [dict(id=f'local-{number:02d}', label=None if number == 3 else f'c{number}',
                  evaluation_key=None if number == 4 else ('val' if number % 2 else 'test'),
                  metric=None if number == 5 else 30 - number, direction='higher' if number % 2 else None,
                  status='failed' if number == 6 else 'ok', observation_step=2 + number // 10)
             for number in range(1, 26)]
    graph = dict(mechanisms={'h001.m1': dict(label='Mechanism one')},
                 candidates={'local-02': dict(mechanism_ref='h001.m1', execution_status='known_success')})
    value = ui_view.candidate_rows(dict(index=index, graph=graph, references={'local-01': 'W002-C001/model.pkl'}),
                                   recommended='local-07', delivered='local-07', audits={'local-01': '公开审计通过'})
    rows = [row for group in value['groups'] for row in group['rows']]
    assert value['total'] == 25 and len(rows) == 25
    assert [group['key'] for group in value['groups']] == ['val', 'test', '未声明']
    assert all(earlier['order'] < later['order'] for group in value['groups'] for earlier, later in zip(group['rows'], group['rows'][1:]))
    by_id = {row['id']: row for row in rows}
    assert by_id['local-03']['label'] == '03' and by_id['local-05']['metric_text'] == '—'
    assert by_id['local-02']['mechanism'] == 'Mechanism one' and by_id['local-01']['mechanism'] == '未关联'
    assert by_id['local-07']['marks'] == ['recommended', 'delivered'] and by_id['local-06']['marks'] == ['failed']
    assert by_id['local-01']['audit'] == '公开审计通过' and by_id['local-08']['audit'] == '未审计'
    assert by_id['local-01']['reference'] == 'W002-C001/model.pkl'
    assert not any(row['extra'] for row in rows)  # Every group is within its default 20 rows.
    single = ui_view.candidate_rows(dict(index=[dict(row, evaluation_key='val') for row in index], graph=graph, references={}),
                                    recommended='local-25')
    flags = [row['extra'] for row in single['groups'][0]['rows']]
    assert flags == [False] * 20 + [True] * 4 + [False]  # A marked row is never hidden by default.
    assert not any('best' in json.dumps(row) or '最佳' in json.dumps(row, ensure_ascii=False) for row in rows)


def test_guarded_component_error_is_typed_and_hides_private_paths(tmp_path):
    root, _ = prepare(tmp_path, enabled=False)
    clean = ui_view.cleaner(root)
    def broken():
        raise ValueError('Ledger at ' + str(root) + '/control-ledger is malformed')
    value = ui_view.guarded(broken, clean=clean)
    assert value['error']['kind'] == 'ValueError'
    assert str(root) not in value['error']['message'] and '[private]' in value['error']['message']
    assert ui_view.failure(OSError('/secret/path'))['error']['message'] == '错误信息不可显示'


def test_projection_and_result_card_read_sealed_fixture_without_writes(tmp_path):
    root, _ = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='experiment', summary='First <script>plan</script>')
    finish(root, 2, 'A', [1], action='finish', summary='Final judgment', limitations=['L1', 'L2', 'L3', 'L4'])
    before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
    view = control.status(root, after=0, limit=50, live_feedback=False)
    value = ui_view.project(root, view, final_step=2)
    assert value['header']['title'] == 'Assess one exact declared implementation.'
    (item,) = value['trail']['rounds']
    assert item['index'] == 1 and item['outcome'] == '结束探索' and item['h']['one_line'] == 'First <script>plan</script>'
    assert value['candidates'] == dict(count=0, partial=False, recommended=False, delivered=False)
    again = ui_view.project(root, view, final_step=2, memo={})
    assert again['trail'] == value['trail']
    assert value['used_steps'] == 2
    card = ui_view.result_card(ui_view.Reader(root), 2, closeout=view.get('closeout'))
    assert card['delivery_state'] == 'none' and card['delivery_label'] == '未推荐' and card['chosen'] is None
    assert card['unmet'] == ['L1', 'L2', 'L3'] and card['unmet_omitted'] == 1 and card['criteria_change'] is None
    assert card['goal_completion'] == '未记录' and card['decision'] == '结束探索'
    row = ui_view.results_list_row(ui_view.Reader(root), 1, ui_view.cleaner(root))
    assert row == dict(step=1, role='H', role_label='H · 假设', one_line='First <script>plan</script>')
    assert before == {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}


SAMPLE = os.environ.get('SCID_UI_SAMPLE_S1')


@pytest.mark.skipif(not SAMPLE, reason='Optional retained real sample; set SCID_UI_SAMPLE_S1 to a read-only copy')
def test_retained_real_sample_projection_matches_acceptance_facts():
    root = Path(SAMPLE)
    before = {path: path.stat().st_mtime_ns for path in root.rglob('*') if path.is_file()}
    view = control.status(root, after=0, limit=50, live_feedback=False)
    value = ui_view.project(root, view, final_step=9)
    chronological = list(reversed(value['trail']['rounds']))
    assert [item['outcome'] for item in chronological] == ['修订方向', '修订方向', '交付']
    assert [item['experiments'] for item in chronological] == [5, 3, 13]
    usage = ui_view.usage_stats(view, used_steps=value['used_steps'], candidates=value['candidates'])
    assert (usage['tokens']['value'], usage['tokens']['limit'], usage['tokens']['percent']) == ('584.6 万', '500 万', 117)
    assert usage['tokens']['over'] and usage['tokens']['notes'][0].startswith('最终 A 受保护')
    assert usage['time']['value'].startswith('43 分') and usage['time']['limit'] == '3 小时'
    projection = ui_view.candidate_projection(root, 9)
    rows = ui_view.candidate_rows(projection, recommended=value['confirmed'], delivered=value['confirmed'])
    assert rows['total'] == 32 and len(rows['groups']) == 2
    reader = ui_view.Reader(root)
    card = ui_view.result_card(reader, 9, closeout=view['closeout'], projection=projection)
    assert card['chosen']['label'] == 'convex_strong' and card['delivery_label'] == '已确认交付'
    assert card['criteria_change']['status'] == 'revised' and len(card['unmet']) == 3
    member = ui_view.candidate_file(reader, card['chosen'], projection)
    assert member['sha256'] == view['closeout']['last_confirmed']['artifact_sha256']
    assert before == {path: path.stat().st_mtime_ns for path in root.rglob('*') if path.is_file()}


def test_delivery_state_uses_control_records_and_open_submissions_outrank_old_confirmations():
    confirmed = dict(last_confirmed=dict(candidate_id='local-a'), current_actual=dict(candidate_id='local-a'), status='delivery_confirmed')
    assert ui_view._delivery_state(confirmed, 'local-a', 'ref') == ('confirmed', '已确认交付')
    assert ui_view._delivery_state(confirmed, 'local-b', 'ref') == ('recommended', '已推荐未交付')
    assert ui_view._delivery_state(confirmed, None, None) == ('none', '未推荐')
    pending = dict(confirmed, current_actual='unknown', status='delivery_unknown')
    assert ui_view._delivery_state(pending, 'local-a', 'ref') == ('unknown', '交付状态未知')
    assert ui_view._delivery_state(dict(status='delivery_confirmation_pending'), 'local-a', 'ref')[0] == 'unknown'
    assert ui_view._delivery_state(None, 'local-a', 'ref', unresolved_reference=True)[0] == 'unknown'


def test_reader_memo_reuses_only_unchanged_verified_originals(tmp_path):
    root, _ = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='experiment', summary='Plan')
    memo = {}
    first = ui_view.Reader(root, memo).node(1)
    assert ui_view.Reader(root, memo).node(1) is first
    original = root / 'native-evidence/001/science-output.json'
    original.chmod(0o600); original.write_bytes(original.read_bytes() + b' ')
    with pytest.raises(ValueError):
        ui_view.Reader(root, memo).node(1)
