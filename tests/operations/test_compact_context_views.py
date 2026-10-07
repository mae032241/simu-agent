"""Compact entry views preserve exact scientific and exceptional history access."""
from copy import deepcopy
import json
from pathlib import Path
import shlex
import subprocess
import sys

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.service.attempt_memory import memory_navigation
from scidiscovery.artifact_agent.service.worker_start import startup_document, compact_startup_document
from scidiscovery.artifact_agent.service.progression import compact_brief_overviews
from tests.operations.test_progression import progression, row
from tests.operations.test_progression_brief_summary import decision, brief
from tests.artifact_agent.test_input_reader import body


def memory():
    return dict(recent=[dict(name='recent', state='completed', summary='Repeated report. ' * 300,
        original_read='not_confirmed', original=dict(tool='worker_reference_read', history_task='recent', action='list'))],
        exact_source_related=[dict(name='source-task', state='completed', summary='Same source report. ' * 300,
            read=dict(tool='run_status', name='source-task', intent='decision'),
            navigation=dict(tool='run_status', name='source-task', intent='navigation'))],
        failure_boundaries=[dict(name='early-failure', state='failed', limitation='Changed conditions required.')],
        scientific_negative_candidates=[dict(name='negative', scientific_negative=True, limitation='Retain contrary evidence.')],
        revision_scope=dict(coverage='exact_explicit_revision_ancestors'),
        coverage='bounded_overview', limitations='Excerpts are not original reading.',
        history=dict(tool='worker_read_history'))


def test_compact_memory_preserves_failures_negative_results_and_exact_access():
    original = memory()
    before = deepcopy(original)
    read = dict(command='python tools/read_input.py worker-context.json --file --pointer /attempt_memory')
    view = memory_navigation(original, read=read)
    assert view['failure_boundaries'] == original['failure_boundaries']
    assert view['scientific_negative_candidates'] == original['scientific_negative_candidates']
    assert view['revision_scope'] == original['revision_scope']
    assert view['omitted_overviews'] == dict(recent=1, exact_source_related=1)
    assert view['overview_read'] == read
    assert view['recent'][0]['original'] == original['recent'][0]['original']
    assert view['recent'][0]['original_read'] == 'not_confirmed'
    assert view['exact_source_related'][0]['read'] == original['exact_source_related'][0]['read']
    assert view['exact_source_related'][0]['navigation'] == original['exact_source_related'][0]['navigation']
    assert view['recent'][0]['state'] == 'completed' and view['recent'][0]['details_omitted'] is True
    assert 'summary' not in view['recent'][0]
    assert original == before
    assert len(canonical_json(view)) < len(canonical_json(original)) // 4


def test_real_worker_snapshot_expands_current_memory_without_rewriting_assignment(tmp_path, monkeypatch):
    from tests.operations.test_analysis_claim_scope import generic_worker
    worker, opened = generic_worker(tmp_path)
    workspace = Path(opened['workspace_path'])
    original_assignment = (workspace/'assignment.json').read_bytes()
    assignment = json.loads(original_assignment)
    current = memory()
    monkeypatch.setattr(worker.runs, 'worker_memory', lambda _: current)
    reopened = worker.call_tool('worker_open_assignment', {})
    start = json.loads(Path(reopened['start_here_path']).read_bytes())
    context = json.loads((workspace/'worker-context.json').read_bytes())
    assert context['attempt_memory'] == current
    assert start['attempt_memory']['failure_boundaries'] == current['failure_boundaries']
    command = shlex.split(start['attempt_memory']['overview_read']['command'])
    reply = subprocess.run([sys.executable, '-I', *command[1:], '--budget', '8192'],
        cwd=workspace, text=True, capture_output=True, timeout=10, check=True)
    # Select an individual report rather than interpreting a partial memory page.
    command[-1] += '/failure_boundaries'
    complete = subprocess.run([sys.executable, '-I', *command[1:]], cwd=workspace,
        text=True, capture_output=True, timeout=10, check=True)
    assert json.loads(body(complete.stdout)) == current['failure_boundaries']
    assert '--selection' in reply.stdout and 'next_offset' in reply.stdout
    assert len(reply.stdout.encode()) <= 8192
    for key in ('instruction', 'scientific_intent', 'role_instructions', 'inputs',
                'execution_requirements', 'task_network_policy', 'revision', 'recovery_draft'):
        assert start.get(key) == assignment.get(key)
    assert start['budget'] == reopened['budget']
    assert (workspace/'assignment.json').read_bytes() == original_assignment
    assert not (workspace/'worker-context.json').stat().st_mode & 0o222
    complete = startup_document({**assignment, 'budget': reopened['budget'], 'attempt_memory': current},
        json.loads((workspace/'domain-workspace.json').read_bytes()))
    assert len(canonical_json(start)) < len(canonical_json(complete)) - 8000
    assert set(context) == {'attempt_memory'}


def test_root_overviews_preserve_new_decisions_and_retain_exact_status_navigation(progression):
    p = progression
    p.coordinator.tick()
    saved = row(p)
    cp = json.loads(saved['checkpoint_json'])
    scientific = decision()
    original = dict(budget=cp['budget'], progress=dict(items=[dict(assessment='x'*5000)],
        authority='root_judgment_not_worker_conclusion'), attempt_memory=memory(), changes=[scientific],
        previous_report=dict(summary='Carry the exact limit.', question='Missing datum?'))
    before = deepcopy(original)
    projected = compact_brief_overviews(original)
    assert projected['changes'] == original['changes']
    assert projected['previous_report'] == original['previous_report']
    assert projected['attempt_memory']['failure_boundaries'] == original['attempt_memory']['failure_boundaries']
    guide = projected['budget']['limits_omitted']['read']
    expanded = p.root.call_tool(guide['tool'], guide['arguments'])
    assert expanded['budget']['limits'] == cp['budget']['limits']
    progress_guide = projected['progress']['read']
    arguments = {key: value for key, value in progress_guide.items() if key != 'tool'}
    assert 'progress' in p.root.call_tool(progress_guide['tool'], arguments)
    assert original == before
    assert compact_brief_overviews(projected) == projected


def test_capacity_discards_optional_memory_before_new_exact_decision(progression, monkeypatch):
    p = progression
    bulky = memory()
    bulky['failure_boundaries'][0]['limitation'] = '界' * 2500
    p.root.facade.instance_management_secret = b'm' * 32
    monkeypatch.setattr(p.runtime.runs, 'memory_overview', lambda *args, **kwargs: bulky)
    p.coordinator.tick()
    from tests.operations.test_local_worker_contracts import _invoke
    root = p.root.__class__(p.facade(p.coordinator.host.scheduler_session))
    _invoke(root, 'new')
    rendered = brief(p, monkeypatch, {'new': decision('new')}, limit=12000)
    assert [change['name'] for change in rendered['changes']] == ['new']
    assert 'result_omissions' not in rendered
    assert rendered['attempt_memory']['omissions'] == 'context_byte_budget; read the frozen time index'
    assert rendered['attempt_memory']['history']['view'] == 'history'


def test_compact_start_keeps_full_scientific_instructions_and_submission_rules():
    assignment = dict(instruction='Exact question.' * 300, scientific_intent=dict(
        target='Expected versus observed', expected='Resolve only the bound criterion.'),
        role_instructions='All mandatory scientific rules.' * 300, inputs=[],
        tools=['worker_submit_result'], attempt_memory=memory(),
        budget=dict(remaining_seconds=120, instruction='No extension.'))
    full = startup_document(assignment)
    view = compact_startup_document(full)
    assert view['instruction'] == full['instruction']
    assert view['role_instructions'] == full['role_instructions']
    assert view['scientific_intent'] == full['scientific_intent']
    assert view['budget'] == full['budget']
    assert 'uncertain submission must not be replayed' in view['output']['closeout']
    assert 'Only completed is sealed delivery' in view['output']['closeout']
