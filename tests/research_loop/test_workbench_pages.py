"""Overview, result and workspace pages: read-only display, unchanged controls."""
import re
from urllib.parse import urlencode

import pytest

from scidiscovery.research_loop import instance_render as render
from scidiscovery.research_loop.configuration_form import SCRIPT_CSP as CONFIG_SCRIPT_CSP
from test_execution_authority import prepare
from test_history_handoff import finish
from test_instance_ui import session


def text(page):
    return page.decode() if isinstance(page, bytes) else page


def files(root):
    return {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_overview_answers_state_action_usage_and_rounds_for_manager_and_reader(tmp_path):
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    page = text(ui.get('/', host=ui.host, cookie=cookie)[1])
    assert '<h1>Assess one exact declared implementation.</h1>' in page
    assert '未开始' in page and '已准备，等待你开始' in page
    head = re.search(r'<div class="head-action">(.*?)</div></section>', page, re.S).group(1)
    assert head.count('<form') == 1 and 'action="/control/start"' in head
    assert page.count('<section class="stat') == 4 and '还没有开始研究' in page
    assert '更多操作' in page and '如何理解这些结果' in page and 'id="budget"' in page
    assert 'nav class="top-nav"' in page and '研究过程' in page and 'href="/settings"' in page
    finish(root, 1, 'H', [], action='experiment', summary='Plan <script>x</script>')
    finish(root, 2, 'A', [1], action='revise_h', summary='Revise')
    ui._snapshot(force=True)  # The shared cache otherwise serves the same 2 s window.
    page = text(ui.get('/', host=ui.host, cookie=cookie)[1])
    assert '第 1 轮 · 修订方向' in page and '&lt;script&gt;x&lt;/script&gt;' in page and '<script>x' not in page
    _, _, headers = ui.get('/view?' + urlencode({'token': ui.read_token}), host=ui.host)
    reader = headers['Set-Cookie']
    before = files(root)
    readonly = text(ui.get('/', host=ui.host, cookie=reader)[1])
    assert 'action="/control/' not in readonly and '只读查看' in readonly
    for path in ('/settings', '/results', '/results/1', '/results/2', '/final-results', '/progress', '/guidance', '/?after=0', '/nodes/1'):
        assert ui.get(path, host=ui.host, cookie=reader)[0] == 200, path
    assert files(root) == before


def test_status_matrix_primary_actions_follow_state_without_new_controls(tmp_path):
    root, key = prepare(tmp_path, enabled=False)
    ui, cookie = session(root, key)
    token = ui._browser(cookie)
    snapshot = ui._snapshot()
    def primary(state, manager=True):
        return ui._primary(token, manager, snapshot, dict(state=state, display=dict(current=dict(step=4))))
    assert 'action="/control/start"' in primary('ready') and 'action="/control/pause"' in primary('active')
    assert 'action="/control/continue"' in primary('paused')
    assert primary('pause_requested') is None and primary('error') is None  # No cancellation exists.
    assert 'href="/results/4"' in primary('waiting') and 'href="/progress"' in primary('unknown')
    assert 'href="/final-results"' in primary('completed') and 'href="#budget"' in primary('budget_exhausted')
    assert all('<form' not in (primary(state, False) or '') for state in ('ready', 'active', 'paused', 'final'))
    assert '只读查看' in primary('active', False)


def test_tiny_budget_and_waiting_states_list_what_needs_the_user(tmp_path):
    root, key = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='experiment')
    finish(root, 2, 'A', [1], summary='Needs a missing measurement')
    ui, cookie = session(root, key)
    page = text(ui.get('/', host=ui.host, cookie=cookie)[1])
    assert '等待条件' in page and 'A 等待：Exact scientific question' in page and '需要你处理' in page
    attention = re.search(r'<section class="attention".*?</section>', page, re.S).group(0)
    assert 'action="/control/continue"' in attention and 'href="/results/2"' in attention


def test_snapshot_failure_is_specific_and_the_page_still_renders(tmp_path, monkeypatch):
    root, key = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='analyze')
    ui, cookie = session(root, key)
    def broken(**options):
        raise ValueError('Control ledger at ' + str(root) + '/control-ledger is malformed')
    monkeypatch.setattr(ui, '_snapshot', broken)
    status, page, _ = ui.get('/', host=ui.host, cookie=cookie)
    page = text(page)
    assert status == 200 and '状态不可读' in page and 'ValueError' in page and 'is malformed' in page
    assert str(root) not in page and '更多操作' in page and 'nav class="top-nav"' in page
    live = ui._live_snapshot(ui._browser(cookie), '')
    assert 'ValueError' in live['fragments']['live-hero'] and live['current'] is None


def test_workspace_list_names_the_failure_instead_of_a_generic_note(tmp_path, monkeypatch):
    from scidiscovery.research_loop.instance_ui import InstanceUI
    root, key = prepare(tmp_path, enabled=False)
    workspace = tmp_path / 'workbench'; workspace.mkdir()
    host = InstanceUI(workspace, secret_file=key, instance_roots=[root], workspace=True)
    host.host = '127.0.0.1:18753'
    good = host._loaded_instances()
    assert 'instance-card' in good and '未开始' in good and '0 / 4,000 tokens' in good
    child = host._child(1)
    monkeypatch.setattr(child, '_snapshot', lambda **options: (_ for _ in ()).throw(OSError('busy record')))
    failed = host._loaded_instances()
    assert '无法读取此实例：OSError：busy record' in failed and '重试' in failed
    assert '状态暂不可用' not in failed


def test_result_pages_lead_with_the_conclusion_and_keep_the_original(tmp_path):
    root, key = prepare(tmp_path, enabled=False)
    finish(root, 1, 'H', [], action='experiment', files={'plan.md': 'plan'})
    finish(root, 2, 'A', [1], action='finish', summary='Final <b>judgment</b>', limitations=['L1', 'L2', 'L3', 'L4'])
    ui, cookie = session(root, key)
    before = files(root)
    status, page, headers = ui.get('/final-results', host=ui.host, cookie=cookie)
    page = text(page)
    assert status == 200 and page.index('class="result-card') < page.index('class="candidates') < page.index('id="materials"')
    assert page.index('id="materials"') < page.index('id="full-text"')
    assert '未推荐' in page and 'L1' in page and 'L3' in page and '另有 1 条局限' in page
    assert '本阶段 0 份；截至本阶段，各阶段共 1 份研究文件' in page and 'href="/nodes/1/materials"' in page
    assert 'Final &lt;b&gt;judgment&lt;/b&gt;' in page and '研究发现' in page and '/nodes/2/science' in page
    assert '<script>' + render.PROGRESS_SCRIPT + '</script>' in page and page.count('<script') == 1
    h = text(ui.get('/results/1', host=ui.host, cookie=cookie)[1])
    assert 'class="role-line"' in h and 'id="full-text"' not in h and '<script' not in h
    listing = text(ui.get('/results', host=ui.host, cookie=cookie)[1])
    assert listing.count('href="/results/2"') == 1 and listing.index('/results/2') < listing.index('/results/1')
    assert files(root) == before
    with pytest.raises(ValueError):
        ui.get('/results/3', host=ui.host, cookie=cookie)


def test_csp_keeps_hash_only_inline_sources():
    assert "'unsafe-inline'" not in render.CSP and "'unsafe-eval'" not in render.CSP
    assert render.CSP == ("default-src 'none'; style-src " + render.STYLE_SOURCE + "; script-src " + render.SCRIPT_SOURCE
                          + " " + CONFIG_SCRIPT_CSP + "; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
