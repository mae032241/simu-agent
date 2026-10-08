"""Brief-only summary references preserve exact public scientific values."""
from copy import deepcopy
import json

import pytest

from scidiscovery.artifact_agent.service.run_read_projection import _output_selection
from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
from tests.operations.test_progression import progression, row


def decision(name='result'):
    summary = '有限观测不能消除原有不确定性。' * 40
    payload = dict(outcome='inconclusive', summary=summary, limitations=['Exact fixture only.'],
        remaining_question='Which bound input is missing?', remaining_contradiction='The mechanism is unresolved.',
        hypothesis_assessments=[dict(outcome='inconclusive')], next_action='Read the missing input.',
        progress_assessment=dict(outcome='unknown'))
    output = dict(artifact_name=name + '.output', kind='scientific',
        schema='scidiscovery.experiment-report.v1', payload=payload)
    return dict(name=name, state='completed', sealed_output_status='available', operation_contract_status='current',
        output_artifact_name=output['artifact_name'], selected_output=_output_selection(output, ['/' + key for key in payload]),
        scheduler_signal_status='available', scheduler_signal=dict(summary=summary, verdict='inconclusive',
            assumptions=['Conditional premise.'], missing_inputs=['Missing exact input.'], next_actions=['A suggestion.']),
        scheduler_signal_omissions=dict(omitted_items=dict(next_actions=2), read=dict(tool='run_status', name=name, intent='full')))


def brief(p, monkeypatch, results, limit=20000):
    p.coordinator.tick()
    saved = row(p)
    facade = p.facade(saved['owner_session'])
    monkeypatch.setattr(facade, 'run_status', lambda name, intent, scheduler_view: results[name])
    monkeypatch.setattr(p.coordinator, 'facade_factory', lambda _: facade)
    snapshot = dict(goal=saved['objective_ref_json'], runs=[dict(name=name, state='completed') for name in results], approvals=[])
    raw = p.coordinator._brief(saved, snapshot, limit)
    return json.loads(raw.split('\n')[-1])


def reference_value(change):
    reference = change['scheduler_signal']['summary_ref']
    assert reference['within'] == 'this_change'
    value = change
    for token in reference['pointer'].split('/')[1:]:
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def test_equal_summary_is_folded_only_in_brief_without_mutating_result(progression, monkeypatch):
    original = decision()
    before = deepcopy(original)
    change = brief(progression, monkeypatch, {'result': original})['changes'][0]
    assert reference_value(change) == original['scheduler_signal']['summary']
    assert change['scheduler_signal']['summary_ref']['pointer'] == '/selected_output/items/1/value'
    assert 'summary' not in change['scheduler_signal']
    assert {key: value for key, value in change.items() if key != 'scheduler_signal'} == {
        key: value for key, value in original.items() if key != 'scheduler_signal'}
    assert {key: value for key, value in change['scheduler_signal'].items() if key != 'summary_ref'} == {
        key: value for key, value in original['scheduler_signal'].items() if key != 'summary'}
    assert original == before
    assert len(json.dumps(change, ensure_ascii=False).encode()) < len(json.dumps(original, ensure_ascii=False).encode())


@pytest.mark.parametrize('variant', ['different', 'missing', 'omitted', 'null', 'signal_missing', 'historical', 'unknown_contract'])
def test_summary_without_exact_complete_current_match_is_preserved(progression, monkeypatch, variant):
    original = decision()
    item = original['selected_output']['items'][1]
    if variant == 'different':
        original['scheduler_signal']['summary'] += '\n'
    elif variant in {'missing', 'omitted'}:
        item['status'] = variant
        item.pop('value')
    elif variant == 'null':
        item['value'] = original['scheduler_signal']['summary'] = None
    elif variant == 'signal_missing':
        original['scheduler_signal'] = None
    elif variant == 'historical':
        original['sealed_output_status'] = 'historical'
    else:
        original['operation_contract_status'] = 'unknown'
    before = deepcopy(original)
    assert brief(progression, monkeypatch, {'result': original})['changes'] == [before]
    assert original == before


def test_capacity_omits_whole_change_without_dangling_summary_reference(progression, monkeypatch):
    first, oversized = decision('first'), decision('oversized')
    oversized['selected_output']['items'][2]['value'] = ['x' * 20000]
    rendered = brief(progression, monkeypatch, {'first': first, 'oversized': oversized}, limit=12000)
    assert [change['name'] for change in rendered['changes']] == ['first']
    assert reference_value(rendered['changes'][0]) == first['scheduler_signal']['summary']
    assert rendered['result_omissions'] == 1
    assert 'summary_ref' not in json.dumps(rendered['omissions'])


def test_public_analysis_summary_reads_and_sealed_bytes_remain_complete(tmp_path):
    from tests.operations.test_analysis_claim_scope import generic_worker
    from tests.operations.test_analysis_handoff_report import compact_report, submit_compact
    worker, opened, system = generic_worker(tmp_path, return_system=True)
    runtime, root = system[1], system[2]
    report = compact_report('experiment_results')
    submit_compact(worker, opened, report)
    saved = runtime.runs.status(worker._run_id)
    original = runtime.artifacts.read(saved.output_ref)
    default = root.call_tool('run_status', dict(name='generic_analysis'))
    with pytest.raises(RootToolError):
        root.call_tool('run_status', dict(name='generic_analysis', output_fields=['summary']))
    explicit = root.facade.run_status(name='generic_analysis', output_fields=['summary'])
    with pytest.raises(RootToolError):
        root.call_tool('run_status', dict(name='generic_analysis', intent='full'))
    full = root.facade.run_status(name='generic_analysis', intent='full')
    summary = next(item for item in default['selected_output']['items'] if item['pointer'] == '/summary')
    assert summary['status'] == 'omitted' and 'value' not in summary
    assert default['scheduler_signal_omissions']['omitted_items']['summary']
    for view in (explicit,):
        summary = next(item for item in view['selected_output']['items'] if item['pointer'] == '/summary')
        assert summary['status'] == 'selected' and summary['value'] == report['summary']
        assert view['scheduler_signal']['summary'] == report['summary']
        assert 'summary_ref' not in view['scheduler_signal']
    assert full['sealed_output']['payload']['summary'] == full['scheduler_signal']['summary'] == report['summary']
    assert runtime.artifacts.read(saved.output_ref) == original
