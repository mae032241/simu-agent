"""Saved UI browsing never replays scientific admission or sealed hashes."""
import json
import re
from ui_html import element_texts

from scidiscovery.research_loop import (
    budget, contracts as c, execution, history, instance_control, instance_science,
    qualification, ui_saved_status, ui_view,
)
from scidiscovery.research_loop.instance_ui import InstanceUI
from test_instance_science import read
from test_instance_ui import session
from test_ui_view import nominated_scene
from test_execution_authority import prepare
from test_history_handoff import finish


def test_saved_workbench_results_and_downloads_do_not_requalify(tmp_path, monkeypatch):
    root, key = nominated_scene(tmp_path)
    ui, cookie = session(root, key)
    workspace = tmp_path / 'workbench'; workspace.mkdir()
    host = InstanceUI(workspace, secret_file=key, instance_roots=[root], workspace=True)
    host.host = ui.host
    before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
    def forbidden(*args, **options):
        raise AssertionError('Browsing invoked scientific admission or hash validation')
    for module, names in (
        (c, ('settings', 'validate', 'digest')),
        (history, ('source_sequence', '_source', 'candidate_materials')),
        (instance_science, ('_sealed', 'science', 'materials', 'artifact')),
        (qualification, ('validate_inputs', 'status', 'validate_outputs')),
        (execution, ('record', 'records', 'reference')),
        (budget, ('_events', 'snapshot', 'closeout_state')),
        (instance_control, ('status', 'operations', 'operation')),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    for target in ('/', '/results', '/nodes/2/materials', '/final-results'):
        status, page, _ = ui.get(target, host=ui.host, cookie=cookie)
        assert status == 200
        assert b'AssertionError' not in page
    for step, nominees in ((4, range(1, 7)), (6, range(7, 13))):
        status, page, _ = ui.get(f'/results/{step}', host=ui.host, cookie=cookie)
        assert status == 200
        page = page.decode()
        assert 'AssertionError' not in page
        table = re.search(r'<section class="candidates.*?</section>', page, re.S).group(0)
        assert element_texts(table, 'span', cls='cand-label') == [
            f'Candidate {number}' for number in [*nominees, 37]]
        href = re.search(r'href="([^"]+)"[^>]*>下载推荐候选的研究文件：model-37.py', page).group(1)
        response = ui.get(href, host=ui.host, cookie=cookie)
        assert read(response[1]) == b'# exact original 37\n'
    projection = ui_view.candidate_projection(root, 4)
    assert len(projection['index']) == 37
    assert [row['step'] for row in projection['records']] == [1, 2, 3]
    assert 'instance-card' in host._loaded_instances()
    original = ui.get('/nodes/4/science', host=ui.host, cookie=cookie)
    assert read(original[1]) == (root / 'native-evidence/004/science-output.json').read_bytes()
    assert before == {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_workspace_cards_do_not_construct_scientific_projection(tmp_path, monkeypatch):
    root, key = nominated_scene(tmp_path)
    workspace = tmp_path / 'workbench'; workspace.mkdir()
    host = InstanceUI(workspace, secret_file=key, instance_roots=[root], workspace=True)
    def forbidden(*args, **options):
        raise AssertionError('Instance cards loaded a full scientific projection')
    monkeypatch.setattr(ui_view, 'project', forbidden)
    monkeypatch.setattr(ui_view, 'candidate_projection', forbidden)
    cards = host._loaded_instances()
    assert 'instance-card' in cards and 'AssertionError' not in cards
    assert '第 6 阶段' in cards and 'Candidate 37' not in cards


def test_saved_final_return_stops_marking_resumed_normal_science_completed(tmp_path):
    root, key = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='experiment')
    finish(root, 2, 'A', [1], action='finish')
    finish(root, 3, 'H', [2], action='experiment')
    ui, _ = session(root, key)
    directory = root / 'control-ledger'; directory.mkdir(exist_ok=True)
    events = [dict(kind='closeout_begin', mode='final', first_step=2),
              dict(kind='final_a_return', version=2, step=2)]
    for index, event in enumerate(events, 1):
        (directory / f'{index:06d}.json').write_text(json.dumps(event))
    assert ui._final_step() == 2
    (directory / '000003.json').write_text(json.dumps(dict(kind='closeout_resume')))
    assert ui._final_step() is None
    assert ui_saved_status.final_return(root) is None


def test_saved_final_return_selects_only_the_new_active_final_cycle(tmp_path):
    events = [dict(kind='closeout_begin', mode='final', first_step=2),
              dict(kind='final_a_return', version=2, step=2), dict(kind='closeout_resume'),
              dict(kind='closeout_begin', mode='final', first_step=5)]
    assert ui_saved_status.final_return(tmp_path, events) is None
    current = dict(kind='final_a_return', version=2, step=5)
    assert ui_saved_status.final_return(tmp_path, [*events, current]) == current
    legacy = dict(kind='final_a_return', version=1, step=2)
    assert ui_saved_status.final_return(tmp_path, [legacy, dict(kind='closeout_resume')]) == legacy


def test_saved_audit_nodes_do_not_erase_the_prior_scientific_recommendation(tmp_path):
    from test_candidate_audit import audit_fixture
    root = audit_fixture(tmp_path, candidate_count=2)
    finish(root, 3, 'A', [1, 2], action='continue_w', recommendation='run-1')
    finish(root, 4, 'A', [1, 2, 3], action='audit', recommendation='run-2')
    finish(root, 5, 'A', [1, 2, 3, 4], action='audit', recommendation='run-2')
    assert ui_view.candidate_projection(root, 5)['recommended'] == 'run-1'


def test_saved_used_steps_retain_continuations_delivery_and_audit_intents(tmp_path):
    for name in ('native-evidence/002/continuations/001/native-intent.json',
                 'native-evidence/002/candidate-audit/intent.json',
                 'host-delivery/audit-recovery/original-operation/intent.json'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    events = [dict(kind='action_intent', action_kind='submit'),
              dict(kind='action_outcome'), dict(kind='action_intent', action_kind='confirm')]
    assert ui_saved_status.used_steps(tmp_path, [1, 2, 5], events) == 10
