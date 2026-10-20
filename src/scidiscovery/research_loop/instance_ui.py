"""One explicit instance's loopback status, controls and optional decision host."""
from __future__ import annotations

from contextlib import contextmanager
import base64
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import hmac
import json
import os
from pathlib import Path
import secrets
import shutil
import threading
import tempfile
from urllib.parse import parse_qs, quote, urlsplit
import uuid

from scidiscovery.browser_access import BrowserAccessDenied, BrowserAccessService, access_cookie, cookie_name
from scidiscovery import execution_security as security
from . import budget, contracts as c, execution, execution_authority as authority, instance_control as control
from . import instance_science as science
from . import instance_render as render
from . import instance_live as live
from . import configuration_form, progress, public_output, research_config, user_guidance


_ENTRY_SCRIPT = "location.replace('./');"
_ENTRY_SCRIPT_SOURCE = "'sha256-" + base64.b64encode(hashlib.sha256(_ENTRY_SCRIPT.encode()).digest()).decode() + "'"


@contextmanager
def _host_lock(root, *, workspace=False):
    directory = root / ('.scid-ui' if workspace else 'execution-authority')
    directory.mkdir(exist_ok=True)
    fd = os.open(directory / 'ui.lock',
                 os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('This instance already has a UI host') from error
        yield
    finally:
        os.close(fd)


class InstanceUI:
    def __init__(self, root, *, secret_file, instance_roots=(), approval_host=True, workspace=False):
        self.root = Path(root).resolve()
        self.workspace = workspace
        if workspace and not self.root.is_dir():
            raise ValueError('UI workspace must be an existing explicit directory')
        self.secret_file = Path(secret_file).resolve()
        self.instance_roots = list(dict.fromkeys([self.root, *(Path(item).expanduser().resolve() for item in instance_roots)]))
        self.children = {}
        settings = {} if workspace else c.settings(self.root)
        self.approvals_configured = settings.get('execution_authority_policy') is not None
        self.approvals = self.approvals_configured and approval_host
        self.secret = security.read_secret_file(secret_file, label='instance UI')
        if self.approvals:
            authority.contract(self.root)
            authority.bind_secret(self.root, self.secret, source=secret_file)
        self.instance = ('workspace-' + uuid.uuid5(uuid.NAMESPACE_URL, str(self.root)).hex
                         if workspace else settings['goal_id'])
        self.boot = uuid.uuid4().hex
        self.browser = BrowserAccessService(secret=self.secret, ui_session_id=self.boot)
        self.management_token = secrets.token_urlsafe(32)
        self.read_token = secrets.token_urlsafe(32)
        self.control_nonce = secrets.token_urlsafe(32)
        self.control_lock = threading.Lock()
        self.control_result = None
        self.config_selections = {}
        self.host = None
        self.live_cache = live.SnapshotCache()
        self.live_stop = threading.Event()
        self.live_gate = threading.BoundedSemaphore(live.MAX_CLIENTS)

    def _browser(self, cookie, *, scope='maintenance'):
        self.browser.from_cookie(cookie, instance_id=self.instance, scope=scope)
        from http.cookies import SimpleCookie
        parsed = SimpleCookie(); parsed.load(cookie)
        return parsed[cookie_name(self.instance)].value

    def _page(self, title, body, *, live=True):
        marker = '<p class="connection" data-live-url="/live" role="status">正在连接工作台状态…</p>'
        return render.page(title, (marker if live else '') + body, live=live)

    def _csrf(self, browser_token, action, nonce):
        return security.receipt_hmac(self.secret, security.canonical(
            ['scidiscovery.instance-control.v1', self.instance, self.boot, browser_token, action, nonce]))

    def _control_form(self, browser_token, action, *, correction_trigger=None):
        with self.control_lock:
            nonce = self.control_nonce
        body = ('<form method="post" action="/control/' + action + '">'
            '<input type="hidden" name="nonce" value="' + nonce + '">'
            '<input type="hidden" name="csrf" value="' + self._csrf(browser_token, action, nonce) + '">')
        if action == 'continue':
            body += ('<input type="hidden" name="ack_correction" value="'
                + html.escape(correction_trigger or '', quote=True) + '">')
            body += ('<label>说明为什么继续本次研究 '
                '<textarea name="authorization_note" required></textarea></label>' if correction_trigger else
                '<input type="hidden" name="authorization_note" value="">')
        return body + '<button type="submit">' + {'start': '开始研究', 'pause': '本阶段结束后暂停', 'continue': '继续研究'}[action] + '</button></form>'

    def _continue(self, **options):
        self.control_result = control.start_background(self.root, continue_run=True, **options)

    def _form(self, browser_token, action, fields, label, *, mode=None):
        nonce = self.control_nonce
        submit = ' name="mode" value="' + mode + '"' if mode else ''
        return ('<form method="post" action="/control/' + action + '">'
            '<input type="hidden" name="nonce" value="' + nonce + '">'
            '<input type="hidden" name="csrf" value="' + self._csrf(browser_token, action, nonce) + '">'
            + fields + '<button type="submit"' + submit + '>' + html.escape(label) + '</button></form>')

    def _admin(self, browser_token):
        if 'maintenance' not in self.browser.verify(browser_token, instance_id=self.instance).scopes:
            raise PermissionError('Local management access required')

    def _child(self, index):
        if not 0 < index < len(self.instance_roots):
            raise ValueError('Select an explicitly opened instance')
        with self.control_lock:
            if index not in self.children:
                root = self.instance_roots[index]
                source = c.settings(root).get('ui', {}).get('approval_secret_file') or self.secret_file
                self.children[index] = InstanceUI(root, secret_file=source, approval_host=False)
            child = self.children[index]
            child.host = self.host
            child.live_stop = self.live_stop
            child.live_gate = self.live_gate
        return child

    @staticmethod
    def _mounted(result, index):
        status, body, headers = result
        prefix = '/instances/' + str(index)
        if isinstance(body, live.Stream):
            body.mount = prefix
        if isinstance(body, bytes) and headers.get('Content-Type', 'text/html').startswith('text/html'):
            # Only host-authored HTML links/forms are mounted; scientific bytes
            # and checked download streams are returned exactly as sealed.
            body = body.replace(b'href="/instances"', b'href="__INSTANCE_LIST__"')
            body = body.replace(b'href="/', ('href="' + prefix + '/').encode())
            body = body.replace(b'action="/', ('action="' + prefix + '/').encode())
            for attribute in (b'data-live-url', b'data-progress'):
                body = body.replace(attribute + b'="/', attribute + ('="' + prefix + '/').encode())
            body = body.replace(b'href="__INSTANCE_LIST__"', b'href="/instances"')
        headers = dict(headers)
        if headers.get('Location', '').startswith('/'):
            headers['Location'] = prefix + headers['Location']
        return status, body, headers

    def _instances_page(self, token):
        self._admin(token)
        if self.workspace:
            return self._workspace_page(token)
        body = '<nav><a href="/">返回总览</a><a href="/configuration">创建新研究</a></nav><p>这里仅显示你明确打开的实例。</p>'
        body += '<div id="live-instances">' + self._loaded_instances() + '</div>' + self._form(token, 'open',
            '<label>已有实例的完整目录 <input name="root" required></label>', '打开此实例')
        return 200, self._page('已有实例', body), {}

    def _configuration_page(self, token, *, text='', path='', result=None):
        self._admin(token)
        frozen = ''
        if not self.workspace:
            frozen = '<details><summary>此实例实际冻结的配置</summary><pre>' + html.escape(json.dumps(
                public_output.settings_view(c.settings(self.root)), ensure_ascii=False, indent=2)) + '</pre></details>'
        return self._new_research_page(token, frozen=frozen)

    def _workspace_page(self, token):
        self._admin(token)
        body = ('<p class="setup-intro">准备一项新研究，或继续已有的工作。每个研究单独保存任务、预算、进度和结果。</p>'
            '<div class="cards"><section><h2>从一个研究问题开始</h2><p>写下任务，指定材料，再决定模型和用量上限。创建后，由你开始研究。</p>'
            '<a class="primary" href="/new">创建新研究 →</a></section>'
            '<section><h2>加载已有实例</h2><p>填写已有实例的完整目录，加载后即可进入管理。</p>')
        body += self._form(token, 'open', '<label>实例目录<input name="root" required placeholder="已有实例的完整目录"></label>', '加载实例')
        body += '</section></div><section><h2>已加载的实例</h2><p class="note">列表保留于本次工作台会话；重启后可按目录重新加载，研究文件和已用预算仍保留。</p>'
        body += '<div id="live-instances">' + self._loaded_instances() + '</div>'
        body += '</section><details><summary>工作台信息</summary><p class="note">工作台目录：' + html.escape(str(self.root)) + '</p></details>'
        return 200, self._page('研究工作台', body), {}

    def _new_research_page(self, token, *, draft=None, selection='', preview=None, notice='', frozen=''):
        self._admin(token)
        if draft is None:
            draft = configuration_form.blank(base=self.root)
        body = ('<nav class="setup-nav"><a href="/">← 研究工作台</a><a href="/instances">打开已有研究</a></nav>'
            '<p class="setup-intro">把问题交给研究助手之前，先明确任务、材料和用量。创建后，由你另行开始研究。</p>'
            '<div class="setup-flow" data-start-step="'+('3' if preview is not None else '1')+'">'
            '<ol class="setup-progress" aria-label="创建研究的步骤">'
            '<li data-setup-marker="1"><span>1</span>任务与材料</li>'
            '<li data-setup-marker="2"><span>2</span>模型与预算</li>'
            '<li data-setup-marker="3"><span>3</span>确认创建</li></ol>')
        if notice:
            body += '<p class="setup-notice" role="alert" tabindex="-1">' + html.escape(notice) + '</p>'
        selected = self.config_selections.get(token) if selection else None
        source = selected.get('source') if selected else None
        if source:
            body += '<p class="import-notice">已导入配置：<code>'+html.escape(str(source['path']))+'</code>。请逐步检查任务、模型和预算；所有高级参数均已保留。</p>'
        fields = '<input type="hidden" name="selection" value="' + html.escape(selection, quote=True) + '">'
        fields += configuration_form.render(draft)
        body += self._form(token, 'configure', fields, '检查配置，进入确认 →', mode='preview').replace(
            '<form ', '<form id="research-config-form" ', 1)
        if preview is not None:
            clean = public_output.cleaner(self.root, settings={})
            settings_view = public_output.settings_view(preview)
            permissions = settings_view.get('native_permissions', {})
            task_preview = clean(preview['objective'], limit=len(preview['objective']))
            meanings = {'read-only':'只读文件', 'workspace-write':'可写工作目录', 'danger-full-access':'不限制文件访问',
                'disabled':'禁用', 'cached':'仅缓存', 'live':'实时检索', 'unknown':'由启动器控制，框架无法确认', True:'允许', False:'不允许'}
            def meaning(value):
                return html.escape(str(meanings.get(value, value)))
            def path_summary(value):
                path = Path(value)
                short = '…/' + '/'.join(path.parts[-2:]) if len(path.parts) > 3 else str(path)
                return ('<span class="review-path">'+html.escape(short)+'</span>'
                    '<details class="review-full-path"><summary>查看完整绝对路径</summary><code>'+html.escape(str(path))+'</code></details>')
            body += ('<section class="setup-panel confirmation" data-setup-step="3" aria-labelledby="setup-confirm-title">'
                '<div class="section-heading"><span class="eyebrow">第三步 / 确认创建</span><h2 id="setup-confirm-title" tabindex="-1">检查这次研究的安排</h2>'
                '<p>配置已通过检查。确认后将创建研究目录，模型仍未开始工作。</p></div>'
                '<h3>研究任务</h3><div class="finding">'+html.escape(task_preview[:1800])+'</div>')
            if len(task_preview) > 1800:
                body += '<details><summary>展开完整研究任务</summary><div class="finding">'+html.escape(task_preview)+'</div></details>'
            research = draft['document'].get('research', {})
            root = Path(research.get('root', '')).expanduser()
            root = root if root.is_absolute() else Path(draft['base']) / root
            body += ('<dl class="review-summary">'
                '<div><dt>材料目录</dt><dd>'+path_summary(preview['public_root'])+'</dd></div>'
                '<div><dt>新研究保存到</dt><dd>'+path_summary(root.resolve())+'</dd></div>'
                '<div><dt>全局模型</dt><dd>'+html.escape(str(preview['model']))+'</dd></div>'
                '<div><dt>推理力度 / 服务档位</dt><dd>'+html.escape(str(preview.get('reasoning_effort') or '后端未指定'))+' / '+html.escape(str(preview.get('service_tier') or '后端未指定'))+'</dd></div>'
                '<div><dt>模型用量上限</dt><dd>'+html.escape(str(preview['max_tokens']))+' tokens</dd></div>'
                '<div><dt>活动时间上限</dt><dd>'+html.escape(str(preview['max_seconds']))+' 秒</dd></div>'
                '<div><dt>研究阶段数上限</dt><dd>'+html.escape(str(preview['max_steps']))+' 阶段</dd></div></dl>'
                '<h3>研究助手的实际权限</h3><p class="note">下面区分声明与后端生效值；实验执行仍受自身授权条件限制。</p>'
                '<table class="permission-review"><thead><tr><th scope="col">访问项目</th><th scope="col">配置声明</th><th scope="col">生效值</th></tr></thead><tbody>')
            for key, label in [('workspace','文件读写'),('network','程序联网'),('web','网页检索'),('subagents','子研究助手')]:
                body += '<tr><th scope="row">'+label+'</th><td>'+meaning(permissions.get('requested',{}).get(key,'未声明'))+'</td><td>'+meaning(permissions.get('effective',{}).get(key,'unknown'))+'</td></tr>'
            body += '</tbody></table>'
            if permissions.get('limitations'):
                limitations = {
                    'The launcher owns access controls; declarations do not establish isolation.': '访问控制由启动器负责；这里的声明不代表已建立隔离。',
                    'This retained instance has no frozen framework permission declaration.': '此已有实例没有冻结框架权限声明，实际权限需检查原生配置。',
                    'danger-full-access provides no filesystem or network sandbox.': '当前未限制文件访问，也没有程序联网隔离。',
                    'The requested offline setting is not enforced in danger-full-access mode.': '当前文件访问模式下，关闭程序联网的声明无法生效。',
                    'The workspace-write network option does not enable networking in read-only mode.': '只读模式不会因可写工作目录的联网选项而启用程序联网。',
                }
                body += '<p class="permission-limit">权限限制说明：</p><ul class="permission-limit">'+''.join('<li>'+html.escape(limitations.get(item,item))+'</li>' for item in permissions['limitations'])+'</ul>'
            advanced = []
            for label, predicate in [
                ('角色专用模型', bool(draft['document'].get('agent',{}).get('roles'))),
                ('原生后端设置', bool(draft['document'].get('agent',{}).get('native'))),
                ('实验执行配置', bool(draft['document'].get('executor'))),
                ('交付配置', bool(draft['document'].get('delivery'))),
                ('复核与恢复规则', bool(draft['document'].get('policies'))),
                ('材料补充或限制', bool(research.get('user_updates') or research.get('source_restrictions'))),
                ('分阶段或搜索用量', any(key not in {'max_tokens','max_seconds','max_steps'} for key in draft['document'].get('budget',{}))),
                ('网页管理设置', bool(draft['document'].get('ui'))),
            ]:
                if predicate: advanced.append(label)
            body += '<p class="advanced-review">专门设置：'+('、'.join(advanced) if advanced else '未另行声明，沿用统一配置')+'。可返回第二步展开高级设置核对。</p>'
            body += '<details class="effective-details"><summary>查看完整生效配置与后端能力</summary><pre>' + html.escape(json.dumps(settings_view, ensure_ascii=False, indent=2)) + '</pre></details>'
            body += '<div class="setup-actions"><button type="button" hidden class="secondary-button" data-setup-go="2">← 返回修改</button>'
            body += self._form(token, 'create', '<input type="hidden" name="selection" value="' + html.escape(selection,quote=True) + '">', '确认创建研究')+'</div>'
            body += '<p class="note">创建不会调用模型。进入实例后点击“开始研究”才会运行。</p></section>'
        body += ('<details class="setup-tools"><summary>配置文件工具<span class="summary-note">可选 · 导入、导出或保存</span></summary>'
            '<div class="tools-grid"><div><h3>导入已有配置</h3><p class="note">从服务器上的 TOML 文件开始，导入后仍需检查并确认。</p>'
            + self._form(token, 'load-config', '<label>服务器上的配置文件路径<input name="config_path" required placeholder="/srv/research/research.toml"></label>', '导入配置')
            + '</div><div><h3>保留当前配置</h3><p class="note">导出为浏览器下载，或保存到服务器。都不会创建、开始研究。</p>'
            '<button class="secondary-button" form="research-config-form" name="mode" value="export" type="submit">下载 TOML 配置</button>'
            '<label>保存到服务器的文件路径<input form="research-config-form" name="save_path" placeholder="/srv/research/research.toml"></label>'
            '<button class="secondary-button" form="research-config-form" name="mode" value="save" type="submit">保存到服务器</button></div></div></details>'
            +frozen+'</div>')
        return 200, self._page('创建你的研究', body), {}

    def _selected_config(self, token, selection):
        selected = self.config_selections.get(token)
        if not selected or not selection or not hmac.compare_digest(selection, selected['selection']):
            raise ValueError('请先检查并预览本次研究配置。')
        return selected

    def _remember_config(self, token, draft, *, source=None, previewed=False, task_source=None):
        selection = secrets.token_urlsafe(32)
        self.config_selections[token] = dict(selection=selection, draft=draft, source=source,
            previewed=previewed, task_source=task_source)
        return selection

    def _draft_task(self, draft):
        if draft['task_mode'] != 'file':
            return None
        objective = Path(draft['document'].get('research', {}).get('objective', '')).expanduser()
        objective = objective if objective.is_absolute() else Path(draft['base']) / objective
        if objective.resolve() == self.secret_file:
            raise ValueError('Select a research task file')
        return objective, c.regular(objective, limit=256000).read_bytes()

    def _import_config(self, token, path, *, notice=''):
        path = Path(path).expanduser().absolute()
        if path.suffix.lower() != '.toml' or path.resolve() == self.secret_file:
            raise ValueError('Select a research TOML declaration file')
        source = c.regular(path, limit=256000).read_bytes()
        path = path.resolve()
        document = research_config.read_declaration(path)
        proof = dict(path=path, source=source)
        research = document.get('research', {})
        if isinstance(research, dict) and isinstance(research.get('objective'), str):
            objective = Path(research['objective']).expanduser()
            objective = objective if objective.is_absolute() else path.parent / objective
            if objective.resolve() == self.secret_file:
                raise ValueError('Select a research task file')
            proof.update(objective=objective, task_source=c.regular(objective, limit=256000).read_bytes())
        if c.regular(path, limit=256000).read_bytes() != source:
            raise ValueError('配置已变化，请重新加载研究配置。')
        draft = configuration_form.imported(document, base=path.parent)
        selection = self._remember_config(token, draft, source=proof)
        return self._new_research_page(token, draft=draft, selection=selection, notice=notice)

    @staticmethod
    def _config_changed(source):
        if source is None:
            return False
        return (c.regular(source['path'], limit=256000).read_bytes() != source['source'] or
            'objective' in source and c.regular(source['objective'], limit=256000).read_bytes() != source['task_source'])

    @staticmethod
    def _navigation():
        return ('<nav><a href="/instances">返回工作台</a><a href="/">总览</a><a href="/progress">实时进度</a>'
            '<a href="/results">阶段结论</a><a href="/final-results">最终结果</a>'
            '<a href="/guidance">方向建议</a><a href="/configuration">高级设置</a></nav>')

    def _guidance_page(self, token):
        manager = 'maintenance' in self.browser.verify(token, instance_id=self.instance).scopes
        body = self._navigation() + '<p>这里可以补充关注点、约束或目标变化。建议将在适用阶段交给研究者；建议本身不会授予实验执行权限。</p>'
        clean = public_output.cleaner(self.root)
        statuses = {'pending': '等待采用', 'applied': '已交给研究者', 'revoked': '已撤回'}
        for row in user_guidance.list_guidance(self.root):
            body += '<section><h2>' + statuses.get(row['status'], html.escape(row['status'])) + '</h2>' + render.excerpt(clean(row['text']), 4000)
            body += '<p class="note">适用范围：' + ('整个研究' if row.get('scope') == 'research' else '下一适用阶段') + '</p>'
            hidden = ('<input type="hidden" name="guidance_id" value="' + row['guidance_id'] + '">'
                '<input type="hidden" name="expected_revision" value="' + str(row['revision']) + '">')
            if manager and row['status'] == 'pending':
                body += self._form(token, 'guidance-edit', hidden + '<label>修改建议<textarea name="text" required>' + html.escape(row['text']) + '</textarea></label>', '保存修改')
            if manager and (row['status'] == 'pending' or row['status'] == 'applied' and row.get('scope') == 'research' and not row.get('future_revocation')):
                body += self._form(token, 'guidance-revoke', hidden, '撤回后续建议')
            body += '</section>'
        if manager:
            fields = ('<label>你希望研究者关注什么？<textarea name="text" rows="5" required placeholder="例如：请说明哪些结论仍缺少证据，以及下一步最值得验证的问题。"></textarea></label>'
                '<label>交给谁<select name="target">' + ''.join('<option value="' + key + '">' + label + '</option>' for key, label in [('global','所有研究角色'), ('H','H · 假设'), ('W','W · 实验'), ('A','A · 综合评估'), ('E','E · 证据')]) + '</select></label>'
                '<label>建议类型<select name="kind"><option value="advice">补充建议</option><option value="goal_change">修改研究目标</option></select></label>'
                '<label>生效范围<select name="scope"><option value="next">下一适用阶段</option><option value="research">整个研究的后续阶段</option></select></label>'
                '<label>从第几阶段生效（修改目标时必填）<input name="effective_step" type="number" min="1"></label>')
            body += '<section><h2>添加方向建议（可选）</h2>' + self._form(token, 'guidance-submit', fields, '提交建议') + '</section>'
        return 200, self._page('方向建议', body), {}

    def _operations_page(self, token):
        self._admin(token)
        body = self._navigation() + '<p>启动、暂停和预算调整的请求处理情况。处理结束不代表科学目标已完成。</p>'
        body += '<div id="live-operations">' + self._operation_rows(self._snapshot()['operations']) + '</div>'
        return 200, self._page('控制请求记录', body), {}

    def _operation_rows(self, rows):
        clean = public_output.cleaner(self.root)
        labels = {'accepted':'请求已接受', 'running':'控制请求正在处理', 'completed':'控制请求已结束', 'failed':'处理失败', 'applied':'已应用'}
        body = ''
        for row in reversed(rows):
            body += '<section><h2>' + labels.get(row['status'], '请求已记录') + '</h2><p>' + ('预算调整' if row['kind'] == 'budget' else '研究控制') + '</p>'
            if row.get('error'):
                body += '<p>' + html.escape(clean(row['error'])) + '</p>'
            body += '</section>'
        return body or '<p>还没有控制请求。</p>'

    def _recent_results(self, snapshot):
        body = '<section><h2>最近返回的阶段结论</h2><ul>'
        for node in reversed(snapshot['view']['nodes']):
            if node['state'] == 'seal_present_unverified':
                body += '<li><a href="/results/' + str(node['step']) + '">第 ' + str(node['step']) + ' 阶段 · ' + self._role(node['role']) + '</a></li>'
        return body + '</ul></section>'

    @staticmethod
    def _event_html(item):
        kind = item.get('type')
        if kind == 'message':
            text = item['text']
        elif kind == 'tool':
            text = '工具 ' + item['tool'] + ' · ' + {'started': '开始', 'updated': '进行中', 'completed': '已完成', 'failed': '失败'}[item['status']]
        elif kind == 'usage':
            text = '用量更新：输入 ' + str(item['usage']['input_tokens']) + ' / 输出 ' + str(item['usage']['output_tokens']) + ' tokens'
        else:
            text = {'session.started': '研究助手已连接', 'turn.completed': '本次助手工作已结束，等待阶段结论'}.get(kind, '')
        return '<article class="event"><p>' + html.escape(text) + '</p>' + ('<small>本条公开文本已截短</small>' if item.get('omitted_characters') else '') + '</article>' if text else ''

    def _latest_step(self):
        maximum = budget.historical_step_limit(self.root)
        return max((int(path.stem) for path in (self.root / 'jobs').glob('*.json')
            if path.stem.isascii() and path.stem.isdecimal() and path.stem == f'{int(path.stem):03d}'
            and 0 < int(path.stem) <= maximum), default=0)

    def _final_step(self):
        final = budget.final_a_barrier(self.root)
        step = final['step'] if final is not None else self._latest_step()
        if not step or not (execution.origin(self.root, step) / 'result-identity.json').exists():
            return None
        _, seal, raw, proof = science._sealed(self.root, step)
        if final is not None:
            return step
        job_path = self.root / 'jobs' / f'{step:03d}.json'
        job = science._json(job_path, science._proof(job_path, seal['job_sha256']))
        with science.Original(raw, proof) as original:
            payload = json.load(original.stream); original.check()
        return step if job['role'] == 'A' and not job.get('formal_review') and payload.get('next_action') == 'finish' else None

    def _progress_page(self, step, attempt, cursor):
        value = progress.read(self.root, step, attempt=attempt, cursor=cursor)
        base = '/nodes/' + str(step) + '/progress?attempt=' + str(attempt)
        body = self._navigation() + '<p>第 ' + str(step) + ' 阶段 · ' + self._role(value['role']) + '</p>'
        body += '<p class="note">这里显示助手公开的工作文本和工具状态；阶段完成后请查看“阶段结论”。</p>'
        body += '<p><a href="' + base + '">重新读取公开进度</a> · <a href="/nodes/' + str(step) + '">查看此阶段</a></p>'
        body += '<section data-progress="/nodes/' + str(step) + '/events?attempt=' + str(attempt) + '" data-cursor="' + html.escape(value.get('cursor') or '', quote=True) + '"><h2>助手正在做什么</h2><p data-stream-status>正在连接进度；最多展示最近 200 条公开消息</p><div data-events>'
        body += ''.join(self._event_html(item) for item in value['events'][-200:]) + '</div>'
        if not value['events']:
            body += '<p class="note">还没有公开消息，开始运行后会在这里更新。</p>'
        body += '<details><summary>高级：公开事件详情</summary><pre data-raw-events>' + html.escape(json.dumps(value['events'][-200:], ensure_ascii=False, indent=2)) + '</pre></details></section>'
        if value.get('cursor') and not value.get('restart_required'):
            body += '<a href="' + base + '&amp;cursor=' + quote(value['cursor'], safe='') + '">手动读取下一批消息</a>'
        if value.get('restart_required'):
            body += '<p>日志来源已变化，请点击上方“重新读取公开进度”；系统不会重新提交研究任务。</p>'
        return 200, self._page('实时进度', body, live=True), {}

    def _following_progress_page(self):
        body = self._navigation() + '<p>这里自动跟随当前阶段；打开各阶段的公开进度链接可固定查看历史记录。</p>'
        body += '<section data-progress="" data-follow-latest="true" data-cursor=""><h2 data-progress-heading>当前助手的公开工作</h2><p data-stream-status>等待当前阶段；状态会自动更新</p><div data-events></div>'
        body += '<details><summary>高级：公开事件详情</summary><pre data-raw-events>[]</pre></details></section>'
        return 200, self._page('实时进度', body, live=True), {}

    @staticmethod
    def _role(role):
        return html.escape({'H': 'H · 假设', 'W': 'W · 实验', 'A': 'A · 综合评估', 'E': 'E · 证据'}.get(role, role))

    @staticmethod
    def _state(state):
        return {'prepared': '等待开始', 'running': '正在运行', 'waiting': '等待外部工作',
            'seal_present_unverified': '已有阶段结论', 'native_outcome_unsealed': '工作已结束，结论尚未记录',
            'native_not_submitted': '尚未提交', 'unknown': '原任务状态待核对'}.get(state, '状态待核对')

    @staticmethod
    def _node_view(node):
        value = {key: str(node[key])[:300] if isinstance(node[key], str) else node[key]
                for key in ('step', 'role', 'state', 'stop_reason', 'returncode', 'continuations') if key in node}
        if isinstance(node.get('stop_reason'), str):
            value['stop_reason_omitted_characters'] = max(0, len(node['stop_reason']) - 300)
        return value

    def _snapshot(self, *, force=False):
        def load():
            latest = self._latest_step()
            view = control.status(self.root, after=max(0, latest - 20), limit=20, live_feedback=False)
            conclusion = None
            for node in reversed(view['nodes']):
                if node['state'] == 'seal_present_unverified':
                    _, seal, raw, proof = science._sealed(self.root, node['step'])
                    with science.Original(raw, proof) as original:
                        payload = json.load(original.stream); original.check()
                    job_path = self.root / 'jobs' / f'{node["step"]:03d}.json'
                    job = science._json(job_path, science._proof(job_path, seal['job_sha256']))
                    conclusion = dict(step=node['step'], role=node['role'], ordinary=not job.get('formal_review') and job.get('purpose') != 'closeout', payload=payload)
                    break
            operations = control.operations(self.root)
            return dict(view=view, conclusion=conclusion, operation=operations[-1] if operations else None, operations=operations[-20:],
                        final=self._final_step())
        return self.live_cache.read(self.root, load, force=force, refresh=lambda value:
            value['view']['budget']['clock_phase'] in {'advance','waiting'} or
            any(node['state'] in {'running','waiting','unknown','prepared'} for node in value['view']['nodes'][-1:]) or
            (value['operation'] or {}).get('status') in {'accepted','running'})

    def _receipt(self, snapshot):
        receipt = snapshot['operation'] or self.control_result or {}
        operation_id = receipt.get('operation_id')
        if operation_id and (self.root / 'host-control/operations' / (operation_id + '.json')).is_file():
            receipt = control.operation(self.root, operation_id)
        return receipt

    def _loaded_instances(self, *, force=False):
        rows = []
        for index, root in enumerate(tuple(self.instance_roots)[:100]):
            if not index and self.workspace:
                continue
            child = self._child(index) if index else self
            try:
                snapshot = child._snapshot(force=force)
                view = snapshot['view']
                current = view['nodes'][-1] if view['nodes'] else None
                state = child._presentation(snapshot, child._receipt(snapshot))
                target = '/instances/' + str(index) + '/manage?token=' + child.management_token if index else '/'
                rows.append('<article><h3><a href="' + html.escape(target, quote=True) + '">实例 ' + str(index) + ' · ' + html.escape(root.name) + '</a></h3>'
                    + render.excerpt(public_output.cleaner(root)(view['objective']), 240)
                    + '<p>' + html.escape(state['title']) + (' · ' + child._role(current['role']) + ' · 第 ' + str(current['step']) + ' 阶段' if current else '')
                    + '</p><details class="review-full-path"><summary>查看实例完整目录</summary><code>' + html.escape(str(root)) + '</code></details><p class="note">模型用量 ' + str(view['usage']['observed_tokens']) + ' / ' + str(view['budget']['max_tokens']) + ' tokens</p></article>')
            except (ValueError, OSError, RuntimeError, KeyError, TypeError):
                rows.append('<article><h3>实例 ' + str(index) + ' · ' + html.escape(root.name) + '</h3><p>状态暂不可用；请核对已有实例。</p></article>')
        return ''.join(rows) or '<p>还没有加载实例。你可以新建一个，或填写目录加载已有研究。</p>'

    def _presentation(self, snapshot, receipt):
        view = snapshot['view']
        current = view['nodes'][-1] if view['nodes'] else None
        state = current['state'] if current else 'ready'
        conclusion = snapshot['conclusion']
        waiting = bool(current and conclusion and conclusion['step'] == current['step']
                       and conclusion['payload'].get('next_action') == 'wait')
        completed = snapshot['final'] is not None or (view.get('closeout') or {}).get('status') in {'final_a_completed', 'delivery_confirmed', 'exported_unsubmitted'}
        # A durable sealed/terminal node outranks a transient accepted receipt.
        active = state in {'running', 'waiting'} or (state in {'ready', 'prepared'} and receipt.get('status') in {'accepted', 'running'})
        title = ('最终结论已返回' if completed else '等待补充条件' if waiting else
            '暂停已请求：本阶段结束后停止' if view['paused'] and active else '研究已暂停' if view['paused'] else
            '研究正在进行' if active else '可以开始研究' if not current else self._state(state))
        return dict(current=current, state=state, waiting=waiting, completed=completed, active=active, title=title)

    def _dashboard_parts(self, token, snapshot):
        manager = 'maintenance' in self.browser.verify(token, instance_id=self.instance).scopes
        view = snapshot['view']; limits, usage = view['budget'], view['usage']
        receipt = self._receipt(snapshot)
        display = self._presentation(snapshot, receipt)
        current = display['current']; paused = view['paused']
        clean = public_output.cleaner(self.root)
        hero = '<section class="hero"><span class="badge">' + html.escape(display['title']) + '</span><h2>' + (self._role(current['role']) + ' · 第 ' + str(current['step']) + ' 阶段' if current else '实例已创建') + '</h2>'
        if display['waiting']:
            payload = snapshot['conclusion']['payload']
            hero += '<p>研究者已记录等待结论。请先核对等待原因、补充材料或方向建议，再通过适用的后续操作处理。</p>'
            hero += render.excerpt(clean(payload.get('route_reason') or payload.get('remaining_question') or payload.get('summary') or '请查看本阶段结论中的等待条件。'), 1600)
            hero += '<a class="primary" href="/results/' + str(current['step']) + '">查看等待原因与阶段结论</a>'
            if manager and current['role'] == 'A' and snapshot['conclusion']['ordinary'] and not display['completed']:
                hero += '<p class="note">确认后继续研究，将由综合评估助手重新判断下一步；原结论与已用预算保留。</p>'
                hero += self._control_form(token, 'continue', correction_trigger=(view['correction'].get('current_pause') or {}).get('trigger_id'))
        elif display['state'] == 'unknown':
            hero += '<p>上一次任务的结果还不确定。请先核对原任务，再决定后续操作；不要重复提交。</p><a class="primary" href="/progress">查看原任务进度</a>'
        elif display['completed']:
            hero += '<p>可以阅读综合结论和研究文件，并查看原文中的局限。</p><a class="primary" href="/final-results">查看最终结果</a>'
        elif display['active']:
            hero += '<p>研究正在进行，状态会自动更新。</p><a class="primary" href="/progress">查看实时进度</a>'
        elif manager:
            hero += '<p>' + ('确认继续后，研究沿用原来的任务与授权；已有用量保留。' if paused else '点击下方按钮后，研究助手才会开始工作。') + '</p>'
            hero += self._control_form(token, 'continue' if paused else 'start', correction_trigger=(view['correction'].get('current_pause') or {}).get('trigger_id'))
        else:
            hero += '<p>当前为只读页面。使用本地管理入口可开始或暂停研究。</p>'
        if receipt:
            notices = {'accepted':'已接受请求，正在安排研究工作。', 'running':'控制请求仍在处理；研究状态以上方阶段为准。',
                'completed':'本次控制请求已结束；研究结论以上方阶段为准。', 'applied':'本次控制请求已处理。',
                'failed':'本次请求未完成，请查看控制请求记录。', 'pause_requested':'暂停已请求；当前已接受的工作完成后停止。'}
            hero += '<p class="note">' + notices.get(receipt.get('status'), '控制请求已记录。') + '</p>'
        if current and current.get('stop_reason'):
            hero += '<p class="gap">工作停止说明：' + html.escape(clean(current['stop_reason'])) + '</p>'
        hero += '</section>'
        cards = '<div class="cards"><section><h2>模型用量</h2><p class="metric">' + str(usage['observed_tokens']) + ' / ' + str(limits['max_tokens']) + ' tokens</p><p class="note">已观测用量 / 授权总上限；预留 ' + str(usage.get('reserved_tokens', 0)) + ' tokens</p>'
        cards += '<p>' + (str(len(usage['unknown_steps'])) + ' 个阶段的用量尚不完整，不能视作全部实际用量。' if usage['unknown_steps'] else '已记录阶段的用量可核对。') + '</p></section>'
        cards += '<section><h2>研究时间</h2><p class="metric">' + str(round(limits['seconds_remaining'], 1)) + ' 秒</p><p>剩余时间；授权总上限 ' + str(limits['max_seconds']) + ' 秒。</p><p class="note">等待与运行时间按实例配置计量。</p></section></div>'
        pause = ''
        if manager and display['active'] and not paused:
            pause = '<section class="secondary"><h2>需要暂停吗？</h2><p>当前已接受的工作完成并记录结论后，停止推进下一阶段。</p>' + self._control_form(token, 'pause') + '</section>'
        nodes = '<section><h2>最近研究阶段</h2>'
        for node in view['nodes']:
            base = '/nodes/' + str(node['step'])
            nodes += '<article><h3><a href="' + base + '">第 ' + str(node['step']) + ' 阶段 · ' + self._role(node['role']) + '</a></h3><p>' + self._state(node['state']) + '</p>'
            nodes += ('<a href="/results/' + str(node['step']) + '">阅读阶段结论</a> · <a href="' + base + '/science">完整结论原文</a> · <a href="' + base + '/materials">下载研究文件</a>' if node['state'] == 'seal_present_unverified' else '<a href="' + base + '/progress?attempt=' + str(node.get('continuations', 0)) + '">查看此阶段公开进度</a>') + '</article>'
        if not view['nodes']:
            nodes += '<p>还没有开始研究。开始后，这里会显示研究阶段。</p>'
        nodes += '</section>'
        conclusion = '<section><h2>最新阶段结论</h2>'
        if snapshot['conclusion']:
            result = snapshot['conclusion']
            conclusion += '<p>第 ' + str(result['step']) + ' 阶段 · ' + self._role(result['role']) + '</p>'
            conclusion += render.excerpt(clean(result['payload'].get('summary', '请阅读阶段结论原文。')), 1600)
            conclusion += '<p><a href="/results/' + str(result['step']) + '">阅读发现与局限</a></p>'
        else:
            conclusion += '<p>阶段结论尚未返回，可先查看助手的公开工作。</p>'
        conclusion += '</section>'
        return {'live-hero':hero, 'live-usage':cards, 'live-pause':pause, 'live-nodes':nodes, 'live-conclusion':conclusion}

    def _live_snapshot(self, token, mount, *, force=False):
        self.browser.verify(token, instance_id=self.instance)
        manager = 'maintenance' in self.browser.verify(token, instance_id=self.instance).scopes
        fragments = {}
        current = None
        if self.workspace:
            self._admin(token)
            fragments['live-instances'] = self._loaded_instances(force=force)
        else:
            snapshot = self._snapshot(force=force)
            fragments = self._dashboard_parts(token, snapshot)
            current = snapshot['view']['nodes'][-1] if snapshot['view']['nodes'] else None
            fragments['live-results'] = self._recent_results(snapshot)
            if manager:
                fragments['live-operations'] = self._operation_rows(snapshot['operations'])
            if manager and not mount:
                fragments['live-instances'] = self._loaded_instances(force=force)
        if mount:
            for key, value in fragments.items():
                value = value.replace('href="/instances"', 'href="__WORKSPACE__"')
                for attribute in ('href', 'action', 'data-progress'):
                    value = value.replace(attribute + '="/', attribute + '="' + mount + '/')
                fragments[key] = value.replace('href="__WORKSPACE__"', 'href="/instances"')
        with self.control_lock:
            nonce = self.control_nonce
            tokens = {action:self._csrf(token, action, nonce) for action in (
                'start','pause','continue','resume','budget','guidance-submit','guidance-edit','guidance-revoke',
                'open','configure','create','load-config','configuration')} if manager else {}
        return dict(fragments=fragments, nonce=nonce if manager else None, csrf=tokens,
            current=dict(step=current['step'], role=self._role(current['role']), attempt=current.get('continuations',0),
                url=mount + '/nodes/' + str(current['step']) + '/events?attempt=' + str(current.get('continuations',0))) if current else None)

    def _instance_page(self, browser_token, *, after=None, step=None):
        snapshot = self._snapshot()
        manager = 'maintenance' in self.browser.verify(browser_token, instance_id=self.instance).scopes
        body = self._navigation()
        body += '<p class="note">当前实例：' + html.escape(self.root.name) + ' · 各页面状态会自动同步。</p>'
        parts = self._dashboard_parts(browser_token, snapshot)
        for name in (('live-hero','live-usage','live-conclusion','live-pause') if step is None else ('live-usage',)):
            body += '<div id="' + name + '">' + parts[name] + '</div>'
        if step is None and after is None:
            body += '<div id="live-nodes">' + parts['live-nodes'] + '</div>'
        else:
            view = control.status(self.root, after=step-1 if step is not None else after, limit=1 if step is not None else 20, live_feedback=False)
            if step is not None and not view['nodes']:
                raise ValueError('This instance node does not exist')
            body += '<section><h2>' + ('固定阶段记录' if step else '研究阶段记录') + '</h2>'
            for node in view['nodes']:
                base = '/nodes/' + str(node['step'])
                body += '<article><h3>第 ' + str(node['step']) + ' 阶段 · ' + self._role(node['role']) + '</h3><p>' + self._state(node['state']) + '</p>'
                if node['state'] == 'seal_present_unverified':
                    body += '<p><a href="/results/' + str(node['step']) + '">阅读阶段结论</a> · <a href="' + base + '/science">完整结论原文</a> · <a href="' + base + '/materials">下载研究文件</a></p>'
                else:
                    body += '<p><a href="' + base + '/progress?attempt=' + str(node.get('continuations', 0)) + '">查看此阶段公开进度</a></p>'
                body += '</article>'
            if view.get('next_after') is not None:
                body += '<a href="/?after=' + str(view['next_after']) + '">查看后续阶段</a>'
            body += '</section>'
        body += '<details class="secondary"><summary>预算与高级管理</summary>'
        if manager:
            body += '<p><a href="/operations">控制请求记录</a> · <a href="/?after=0">浏览阶段</a></p>'
            # These explicit advanced operations remain subject to the common
            # controller gates. Live status does not grant new permissions.
            for action in ('start','pause','continue'):
                body += self._control_form(browser_token, action, correction_trigger=(snapshot['view']['correction'].get('current_pause') or {}).get('trigger_id'))
            if step is not None:
                body += self._form(browser_token, 'resume', '<input type="hidden" name="step" value="' + str(step) + '">', '继续此阶段原任务（须满足原有条件）')
            body += '<h3>申请调整预算</h3><p>填写新上限和原因。变更在安全边界处理；已用额度保留。</p>'
            body += self._form(browser_token, 'budget', '<label>新的 tokens 总上限<input name="max_tokens" type="number" min="1"></label><label>新的时间总上限（秒）<input name="max_seconds" type="number" step="any" min="0"></label><label>新的阶段总上限<input name="max_steps" type="number" min="1"></label><label>授权原因<textarea name="authorization_note" required></textarea></label><label>原始授权陈述（调整阶段上限时必填）<textarea name="authorization_statement"></textarea></label>', '提交预算变更')
        if self.approvals:
            body += '<p><a href="/requests">实验执行请求</a></p>'
        body += '</details>'
        return 200, self._page('研究总览' if step is None else '研究阶段', body), {}

    def _materials_page(self, step, after):
        page=science.materials(self.root,step,after=after)
        body=self._navigation() + '<p>第 '+str(step)+' 阶段的研究文件，可逐项下载。</p><ul>'
        for item in page['items']:
            body += ('<li><a href="/nodes/'+str(step)+'/materials/'+str(item['index'])+'">'
                +html.escape(item['name'])+'</a> ('+str(item['size_bytes'])+' bytes)</li>')
        body+='</ul><p>'+str(page['total'])+' 份研究文件。'+html.escape(page['scope'])+'</p>'
        if page['next_after'] is not None:
            body += '<a href="/nodes/'+str(step)+'/materials?after='+str(page['next_after'])+'">后续研究文件</a>'
        return 200,self._page('研究文件下载',body,live=False),{}

    def _results_page(self, after):
        maximum=budget.historical_step_limit(self.root)
        steps=sorted(int(path.stem) for path in (self.root/'jobs').glob('*.json')
            if path.stem.isascii() and path.stem.isdecimal() and path.stem==f'{int(path.stem):03d}'
            and after<int(path.stem)<=maximum)
        found=[]
        for step in steps:
            record=execution.origin(self.root,step)/'result-identity.json'
            if record.exists() or record.is_symlink():found.append(step)
            if len(found)==21:break
        body=self._navigation() + '<div id="live-conclusion"></div><div id="live-results">' + self._recent_results(self._snapshot()) + '</div><p>每个完成阶段的研究发现、建议和局限都保留在这里。点击可阅读原文摘要并下载研究文件。</p><ul>'
        for step in found[:20]:body+='<li><a href="/results/'+str(step)+'">第 '+str(step)+' 阶段结论</a></li>'
        body+='</ul>'
        if not found:body+='<p>还没有阶段结论。开始研究后，可先到“实时进度”查看工作情况。</p>'
        if len(found)>20:body+='<a href="/results?after='+str(found[19])+'">查看后续阶段结论</a>'
        return 200,self._page('阶段结论',body),{}

    def _result_page(self, step):
        _,seal,raw,proof=science._sealed(self.root,step)
        job_path=self.root/'jobs'/f'{step:03d}.json'
        job=science._json(job_path,science._proof(job_path,seal['job_sha256']))
        with science.Original(raw,proof) as original:
            payload=json.load(original.stream);original.check()
        return 200,render.result(step,job,payload,seal),{}

    def get(self, target, *, host, cookie=None):
        if host != self.host:
            raise PermissionError('Exact local Host required')
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise PermissionError('Local relative request target required')
        if parsed.path.startswith('/instances/'):
            parts = parsed.path.split('/', 3)
            if len(parts) != 4 or not parts[2].isascii() or not parts[2].isdecimal():
                raise ValueError('Exact explicit instance route required')
            child = self._child(int(parts[2]))
            return self._mounted(child.get('/' + parts[3] + ('?' + parsed.query if parsed.query else ''), host=host, cookie=cookie), int(parts[2]))
        if parsed.path in {'/manage', '/view'}:
            query = parse_qs(parsed.query, strict_parsing=True)
            values = query.get('token', [])
            expected = self.management_token if parsed.path == '/manage' else self.read_token
            if set(query) != {'token'} or len(values) != 1 or not hmac.compare_digest(values[0], expected):
                raise BrowserAccessDenied('本地浏览入口无效。')
            token = self.browser.issue(self.instance, maintenance=parsed.path == '/manage')
            # A committed local document ends a cross-site navigation chain.
            # A 303 here withholds the new Strict cookie from the destination.
            # The relative script target also remains inside mounted children.
            page = self._page('正在打开工作台', '<p>正在建立本地浏览会话…</p>'
                '<p><a href="/">进入工作台</a>（未自动跳转时点击）</p>'
                '<script>' + _ENTRY_SCRIPT + '</script>', live=False)
            return 200, page, {'Set-Cookie': access_cookie(self.instance, token),
                'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': render.CSP.replace(
                    'script-src ', 'script-src ' + _ENTRY_SCRIPT_SOURCE + ' ', 1)}
        browser_token = self._browser(cookie, scope='read')
        if self.workspace and parsed.path not in {'/', '/new', '/instances', '/configuration', '/live'}:
            raise PermissionError('Open an explicit instance to access research pages')
        if parsed.path == '/live':
            if parsed.query:
                raise ValueError('Exact live workbench route required')
            if self.workspace:
                self._admin(browser_token)
            return 200, live.Stream(lambda mount, **options: self._live_snapshot(browser_token, mount, **options),
                stop=self.live_stop, gate=self.live_gate), {'Content-Type':'text/event-stream; charset=utf-8'}
        if self.workspace and parsed.path == '/':
            if parsed.query:
                raise ValueError('Exact workspace page required')
            return self._workspace_page(browser_token)
        if self.workspace and parsed.path == '/new':
            if parsed.query:
                raise ValueError('Exact new research page required')
            return self._new_research_page(browser_token)
        if parsed.path in {'/instances', '/configuration', '/guidance', '/operations'}:
            if parsed.query:
                raise ValueError('Exact instance page required')
            return {'/instances': self._instances_page, '/configuration': self._configuration_page,
                    '/guidance': self._guidance_page, '/operations': self._operations_page}[parsed.path](browser_token)
        if parsed.path == '/progress':
            if parsed.query:
                raise ValueError('Exact progress page required')
            return self._following_progress_page()
        if parsed.path == '/final-results':
            if parsed.query:
                raise ValueError('Exact final result page required')
            final = self._final_step()
            if final is not None:
                return self._result_page(final)
            return 200, self._page('最终结果', self._navigation() + '<section class="empty"><h2>最终综合结论尚未返回</h2><p>你可以先阅读已完成阶段的发现与局限。</p><a class="primary" href="/results">查看阶段结论</a></section>'), {}
        if parsed.path=='/results':
            query=parse_qs(parsed.query,strict_parsing=True) if parsed.query else {}
            if set(query)-{'after'} or any(len(values)!=1 for values in query.values()):
                raise ValueError('Exact scientific result continuation required')
            after=query.get('after',['0'])[0]
            if not after.isascii() or not after.isdecimal():raise ValueError('Exact scientific result continuation required')
            return self._results_page(int(after))
        if parsed.path.startswith('/results/'):
            number=parsed.path.removeprefix('/results/')
            if parsed.query or not number.isascii() or not number.isdecimal() or int(number)<=0:
                raise ValueError('Exact sealed scientific result required')
            return self._result_page(int(number))
        if parsed.path == '/':
            query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
            if set(query) - {'after'} or any(len(values) != 1 for values in query.values()):
                raise ValueError('Exact node continuation required')
            after = query.get('after', ['0'])[0]
            if not after.isascii() or not after.isdecimal():
                raise ValueError('Invalid node continuation')
            return self._instance_page(browser_token, after=int(after) if query else None)
        if parsed.path.startswith('/nodes/'):
            parts = parsed.path.removeprefix('/nodes/').split('/')
            number = parts[0]
            if not number.isascii() or not number.isdecimal() or int(number)<=0:
                raise ValueError('Exact instance node required')
            step=int(number)
            if len(parts)==1 and not parsed.query:
                return self._instance_page(browser_token,step=step)
            if parts[1:] in (['progress'], ['events']):
                query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
                if set(query) - {'attempt', 'cursor'} or any(len(values) != 1 for values in query.values()):
                    raise ValueError('Exact progress continuation required')
                attempt = query.get('attempt', ['0'])[0]
                if not attempt.isascii() or not attempt.isdecimal():
                    raise ValueError('Exact progress attempt required')
                cursor = query.get('cursor', [None])[0]
                if parts[1:] == ['events']:
                    value = progress.read(self.root, step, attempt=int(attempt), cursor=cursor)
                    return 200, json.dumps(value, ensure_ascii=False).encode(), {'Content-Type': 'application/json; charset=utf-8'}
                return self._progress_page(step, int(attempt), cursor)
            if parts[1:]==['science'] and not parsed.query:
                return 200,science.science(self.root,step),{'Content-Type':'application/json; charset=utf-8'}
            if parts[1:]==['materials']:
                query=parse_qs(parsed.query,strict_parsing=True) if parsed.query else {}
                if set(query)-{'after'} or any(len(values)!=1 for values in query.values()):
                    raise ValueError('Exact scientific deliverable continuation required')
                after=query.get('after',['0'])[0]
                if not after.isascii() or not after.isdecimal():
                    raise ValueError('Exact scientific deliverable continuation required')
                return self._materials_page(step,int(after))
            if len(parts)==3 and parts[1]=='materials' and not parsed.query:
                if not parts[2].isascii() or not parts[2].isdecimal() or int(parts[2])<=0:
                    raise ValueError('Exact scientific deliverable index required')
                original,name=science.artifact(self.root,step,int(parts[2]))
                return 200,original,{'Content-Type':'application/octet-stream',
                    'Content-Disposition':"attachment; filename=scientific-deliverable; filename*=UTF-8''"+quote(name,safe='')}
            raise ValueError('Exact instance node required')
        if not self.approvals:
            raise ValueError('Execution approval routes are unavailable for this instance; status and controls remain available')
        if parsed.path == '/requests':
            query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
            if set(query) - {'after'} or any(len(values) != 1 for values in query.values()):
                raise ValueError('Exact request continuation required')
            after = query.get('after', [''])[0]
            if after and not authority.ID.fullmatch(after):
                raise ValueError('Invalid request continuation')
            directory = self.root / 'execution-authority/requests'
            paths = sorted(directory.iterdir()) if directory.exists() else []
            ids = [path.name for path in paths if authority.ID.fullmatch(path.name) and path.name > after]
            links = ''.join('<li><a href="/requests/' + key + '">' + key + '</a></li>' for key in ids[:20])
            more = ('<a href="/requests?after=' + ids[19] + '">Next requests</a>') if len(ids) > 20 else ''
            return 200, self._page('Execution requests', '<a href="/">Instance</a><p>Decisions grant no execution or additional budget by themselves.</p><ul>' + links + '</ul>' + more), {}
        parts = parsed.path.strip('/').split('/')
        if parsed.query or len(parts) not in (2, 3) or parts[0] != 'requests':
            raise ValueError('Unknown instance UI path')
        request_id = parts[1]
        value, ref = authority.request(self.root, request_id)
        if len(parts) == 3:
            if parts[2] != 'original':
                raise ValueError('Unknown request original')
            return 200, self.root / ref['path'], {'Content-Type': 'application/json; charset=utf-8'}
        state = authority.status(self.root, request_id, secret=self.secret)
        tokens = authority.form_tokens(self.root, request_id, secret=self.secret,
                                       boot=self.boot, browser_token=browser_token)
        # Full mechanical binding stays available as an exact original download.
        compact = dict(state=state['state'], subject=value['subject']['material']['path'],
            target=value['target'], resources=value['resources'], policy=value['policy']['outcome'],
            expires_at=value['expires_at'], scope=authority.SCOPE)
        body = '<pre>' + html.escape(json.dumps(compact, ensure_ascii=False, indent=2)) + '</pre>'
        body += '<p><a href="/requests/' + request_id + '/original">Complete frozen request</a></p>'
        successor=authority.request_successor(self.root,ref)
        if successor is not None:
            body += '<p><a href="/requests/' + Path(successor['path']).parent.name + '">Explicit replacement request</a> (the original request and decision remain unchanged).</p>'
        manager = 'maintenance' in self.browser.verify(browser_token, instance_id=self.instance).scopes
        if manager and state['state'] == 'pending':
            options = ''.join('<option value="' + item + '">' + item + '</option>' for item in value['options'])
            body += ('<form method="post" action="/requests/' + request_id + '/decision">'
                '<input type="hidden" name="nonce" value="' + tokens['nonce'] + '">'
                '<input type="hidden" name="csrf" value="' + tokens['csrf'] + '">'
                '<label>Decision <select name="selected_option">' + options + '</select></label>'
                '<label>Reason <textarea name="rationale" required></textarea></label>'
                '<button type="submit">Record decision</button></form>')
        if manager and state['state'] in {'pending', 'decided'}:
            body += ('<form method="post" action="/requests/' + request_id + '/revoke">'
                '<input type="hidden" name="nonce" value="' + tokens['nonce'] + '">'
                '<input type="hidden" name="csrf" value="' + tokens['csrf'] + '">'
                '<label>Reason <textarea name="rationale" required></textarea></label>'
                '<button type="submit">Revoke request</button></form>')
        return 200, self._page('Exact execution decision', body), {}

    def post(self, target, *, host, origin, cookie, content_type, body):
        security.require_same_origin(host, origin, self.host)
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError('Exact instance control or decision form required')
        if parsed.path.startswith('/instances/'):
            parts = parsed.path.split('/', 3)
            if len(parts) != 4 or not parts[2].isascii() or not parts[2].isdecimal():
                raise ValueError('Exact explicit instance route required')
            child = self._child(int(parts[2]))
            return self._mounted(child.post('/' + parts[3], host=host, origin=origin, cookie=cookie,
                content_type=content_type, body=body), int(parts[2]))
        browser_token = self._browser(cookie)
        parts = parsed.path.strip('/').split('/')
        if self.workspace and parsed.path not in {'/control/open', '/control/configuration', '/control/create', '/control/load-config', '/control/configure'}:
            raise PermissionError('Open an explicit instance to use research controls')
        if content_type != 'application/x-www-form-urlencoded':
            raise ValueError('Exact instance control or decision form required')
        if len(parts) == 2 and parts[0] == 'control':
            action = parts[1]
            schemas = {
                'pause': set(), 'start': set(), 'resume': {'step'}, 'continue': {'ack_correction', 'authorization_note'},
                'create': {'selection'}, 'load-config': {'config_path'}, 'configure': None,
                'open': {'root'}, 'configuration': {'config_path', 'config_text', 'mode'},
                'budget': {'max_tokens', 'max_seconds', 'max_steps', 'authorization_note', 'authorization_statement'},
                'guidance-submit': {'text', 'target', 'kind', 'scope', 'effective_step'},
                'guidance-edit': {'guidance_id', 'expected_revision', 'text'},
                'guidance-revoke': {'guidance_id', 'expected_revision'},
            }
            if action not in schemas:
                raise ValueError('Unknown instance control')
            form = parse_qs(body.decode('utf-8'), keep_blank_values=True, strict_parsing=True)
            if (not {'nonce', 'csrf'} <= set(form) or
                    schemas[action] is not None and set(form) != schemas[action] | {'nonce', 'csrf'} or
                    any(len(values) != 1 for values in form.values())):
                raise ValueError('Control form contains missing or duplicate fields')
            form = {key: values[0] for key, values in form.items()}
            with self.control_lock:
                if (not hmac.compare_digest(form['nonce'], self.control_nonce) or not hmac.compare_digest(
                        form['csrf'], self._csrf(browser_token, action, form['nonce']))):
                    raise PermissionError('Instance control CSRF or nonce mismatch')
                # A download leaves its source form visible in the browser.
                if not (action == 'configure' and form.get('mode') == 'export'):
                    self.control_nonce = secrets.token_urlsafe(32)
            location = '/'
            if action == 'continue':
                self._continue(ack_correction=form['ack_correction'] or None,
                               authorization_note=form['authorization_note'] or None)
            elif action == 'start':
                self.control_result = control.start_background(self.root)
            elif action == 'resume':
                self.control_result = control.start_background(self.root, resume_step=int(form['step']))
            elif action == 'pause':
                self.control_result = control.request_pause(self.root)
            elif action == 'budget':
                self.control_result = control.request_budget_amendment(self.root,
                    max_tokens=int(form['max_tokens']) if form['max_tokens'] else None,
                    max_seconds=float(form['max_seconds']) if form['max_seconds'] else None,
                    max_steps=int(form['max_steps']) if form['max_steps'] else None,
                    authorization_note=form['authorization_note'],
                    authorization_statement=form['authorization_statement'] or None)
                location = '/operations'
            elif action.startswith('guidance-'):
                if action == 'guidance-submit':
                    user_guidance.submit(self.root, form['text'], target=form['target'], kind=form['kind'],
                        scope=form['scope'], effective_step=int(form['effective_step']) if form['effective_step'] else None)
                elif action == 'guidance-edit':
                    user_guidance.edit(self.root, form['guidance_id'], form['text'], expected_revision=int(form['expected_revision']))
                else:
                    user_guidance.revoke(self.root, form['guidance_id'], expected_revision=int(form['expected_revision']))
                location = '/guidance'
            elif action == 'open':
                selected = Path(form['root']).expanduser().resolve()
                c.settings(selected)  # Explicit existing root, never an inferred directory choice.
                if selected not in self.instance_roots:
                    self.instance_roots.append(selected)
                index = self.instance_roots.index(selected)
                if index:
                    child = self._child(index)
                    location = '/instances/' + str(index) + '/manage?token=' + child.management_token
                else:
                    location = '/'
            elif action == 'load-config':
                return self._import_config(browser_token, form['config_path'])
            elif action == 'configure':
                mode = form.get('mode')
                if mode not in {'preview', 'export', 'save'}:
                    raise ValueError('Select an explicit configuration action')
                fields = {key: value for key, value in form.items() if key not in {'nonce', 'csrf', 'selection', 'save_path', 'mode'}}
                selected = self._selected_config(browser_token, form['selection']) if form.get('selection') else None
                source = selected['source'] if selected else None
                if self._config_changed(source):
                    return self._import_config(browser_token, source['path'], notice='原配置或任务已变化，请重新检查并确认。')
                base = selected['draft']['base'] if selected else self.root
                draft = selected['draft'] if selected else configuration_form.blank(base=base)
                try:
                    draft = configuration_form.parse(fields, base=base)
                    self._draft_task(draft)
                except (OSError, ValueError, TypeError, KeyError) as error:
                    draft = getattr(error, 'draft', draft)
                    selection = self._remember_config(browser_token, draft, source=source)
                    return self._new_research_page(browser_token, draft=draft, selection=selection,
                        notice=public_output.cleaner(self.root, settings={})(str(error)))
                if mode == 'export':
                    text = configuration_form.export_toml(draft)
                    return 200, text.encode('utf-8'), {'Content-Type': 'application/toml; charset=utf-8',
                        'Content-Disposition': 'attachment; filename="research.toml"'}
                if mode == 'save':
                    path = Path(form.get('save_path', '')).expanduser().absolute()
                    if path.suffix.lower() != '.toml' or path.resolve() == self.secret_file:
                        raise ValueError('Select a research TOML declaration file')
                    if path.exists() or path.is_symlink():
                        c.regular(path, limit=256000)
                    text = configuration_form.export_toml(draft)
                    if len(text.encode('utf-8')) > 256000:
                        raise ValueError('Research TOML exceeds its byte budget')
                    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(descriptor, 'w', encoding='utf-8') as destination:
                        destination.write(text)
                    return self._import_config(browser_token, path, notice='配置已保存。创建实例前请检查并预览。')
                try:
                    task_source = self._draft_task(draft)
                    preview = configuration_form.preview(draft)
                    if self._draft_task(draft) != task_source:
                        raise ValueError('任务原文已变化，请重新检查并预览。')
                except (OSError, ValueError, TypeError, KeyError) as error:
                    selection = self._remember_config(browser_token, draft, source=source)
                    return self._new_research_page(browser_token, draft=draft, selection=selection,
                        notice=public_output.cleaner(self.root, settings={})(str(error)))
                selection = self._remember_config(browser_token, draft, source=source, previewed=True, task_source=task_source)
                return self._new_research_page(browser_token, draft=draft, selection=selection, preview=preview)
            elif action == 'create':
                selected = self._selected_config(browser_token, form['selection'])
                if not selected['previewed']:
                    raise ValueError('请先检查并预览本次研究配置。')
                source = selected['source']
                if self._config_changed(source):
                    return self._import_config(browser_token, source['path'], notice='原配置或任务已变化，请重新检查并确认。')
                draft = selected['draft']
                if self._draft_task(draft) != selected['task_source']:
                    task_source = self._draft_task(draft)
                    preview = configuration_form.preview(draft)
                    if self._draft_task(draft) != task_source:
                        raise ValueError('任务原文已变化，请重新检查并预览。')
                    selection = self._remember_config(browser_token, draft, source=source, previewed=True, task_source=task_source)
                    return self._new_research_page(browser_token, draft=draft, selection=selection,
                        preview=preview, notice='任务原文已变化，请重新确认后创建。')
                configuration_form.create(draft)
                root = Path(selected['draft']['document']['research']['root']).expanduser()
                selected_root = (Path(selected['draft']['base']) / root).resolve() if not root.is_absolute() else root.resolve()
                self.config_selections.pop(browser_token, None)
                if selected_root not in self.instance_roots:
                    self.instance_roots.append(selected_root)
                index = self.instance_roots.index(selected_root)
                child = self._child(index)
                location = '/instances/' + str(index) + '/manage?token=' + child.management_token
            elif action == 'configuration':
                path = Path(form['config_path']).expanduser().absolute()
                if path.suffix.lower() != '.toml' or path.resolve() == self.secret_file:
                    raise ValueError('Select a research TOML declaration file')
                if path.exists() or path.is_symlink():
                    c.regular(path, limit=256000)
                path = path.resolve()
                text, mode = form['config_text'], form['mode']
                if mode not in {'load', 'check', 'save', 'prepare'}:
                    raise ValueError('Select an explicit TOML action')
                if not text or mode == 'load':
                    text = c.regular(path, limit=256000).read_text(encoding='utf-8')
                if len(text.encode()) > 256000:
                    raise ValueError('Research TOML exceeds its byte budget')
                result = dict(status='config_loaded')
                if mode in {'check', 'prepare'}:
                    # Draft editing remains available before the declaration
                    # is valid. Only check/prepare enter scientific validation.
                    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.toml', dir=path.parent) as source:
                        source.write(text); source.flush()
                        options = research_config.load(source.name)
                    checked = research_config.prepare(**options, validate_only=True)
                    result = public_output.settings_view(checked)
                    result['source'] = 'research_config'
                if mode == 'save':
                    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(descriptor, 'w', encoding='utf-8') as destination:
                        destination.write(text)
                    result = dict(status='config_saved')
                elif mode == 'prepare':
                    prepared = research_config.prepare(**options)
                    selected = Path(options['root']).resolve()
                    if selected not in self.instance_roots:
                        self.instance_roots.append(selected)
                    result = dict(status='prepared', goal_id=prepared['goal_id'])
                return self._configuration_page(browser_token, text=text, path=str(path), result=result)
            return 303, b'', {'Location': location}
        if not self.approvals:
            raise ValueError('Execution approval routes are unavailable for this instance')
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or len(parts) != 3
                or parts[0] != 'requests' or parts[2] not in {'decision', 'revoke'}
                or content_type != 'application/x-www-form-urlencoded'):
            raise ValueError('Exact execution decision form required')
        form = parse_qs(body.decode('utf-8'), keep_blank_values=True, strict_parsing=True)
        fields = {'nonce', 'csrf', 'rationale'} | ({'selected_option'} if parts[2] == 'decision' else set())
        if set(form) != fields or any(len(values) != 1 for values in form.values()):
            raise ValueError('Decision form contains missing or duplicate fields')
        form = {key: values[0] for key, values in form.items()}
        if parts[2] == 'decision':
            authority.record_decision(self.root, parts[1], secret=self.secret, boot=self.boot,
                browser_token=browser_token, **form)
        else:
            expected = authority.form_tokens(self.root, parts[1], secret=self.secret,
                boot=self.boot, browser_token=browser_token)
            if not all(hmac.compare_digest(form[key], expected[key]) for key in ('nonce', 'csrf')):
                raise PermissionError('Execution revocation CSRF or nonce mismatch')
            authority.revoke(self.root, parts[1], secret=self.secret, reason=form['rationale'])
        return 303, b'', {'Location': '/requests/' + parts[1]}


def serve(root, *, secret_file, port=None, instance_roots=(), workspace=False):
    root = Path(root).resolve()
    options = dict(workspace=True) if workspace else {}
    ui = InstanceUI(root, secret_file=secret_file, instance_roots=instance_roots, **options)
    if port is None:
        port = 0 if workspace else c.settings(root).get('ui', {}).get('port', 0)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # Never copy capability URLs/cookies into logs.

        def handle_request(self, method):
            body=None
            try:
                fields = ('Host', 'Cookie') + (('Origin', 'Content-Length', 'Content-Type') if method == 'POST' else ())
                if self.headers.get('Transfer-Encoding') or any(len(self.headers.get_all(name, [])) > 1 for name in fields):
                    raise PermissionError('Ambiguous request headers are not accepted')
                if method == 'GET':
                    result = ui.get(self.path, host=self.headers.get('Host'), cookie=self.headers.get('Cookie'))
                else:
                    length = self.headers.get('Content-Length')
                    # A transport form limit is not a record/history truncation.
                    if length is None or not length.isdecimal() or not 0 < int(length) <= 1048576:
                        raise ValueError('Decision form length is invalid')
                    result = ui.post(self.path, host=self.headers.get('Host'), origin=self.headers.get('Origin'),
                        cookie=self.headers.get('Cookie'), content_type=self.headers.get('Content-Type'),
                        body=self.rfile.read(int(length)))
                status, body, headers = result
                if isinstance(body,science.Original):
                    body.check()
            except (PermissionError, ValueError, OSError, KeyError, TypeError, RuntimeError) as error:
                if isinstance(body,science.Original):body.close()
                if isinstance(error, BrowserAccessDenied):
                    status, body, headers = 403, ui._page('请重新打开工作台入口',
                        '<p>未能建立有效的本地浏览会话。</p>'
                        '<p>请回到启动工作台的终端，打开本次输出的 <code>management_url</code> 完整链接。'
                        '若仍无法进入，请确认浏览器允许此本地网页保存 Cookie。</p>', live=False), {}
                else:
                    status, body, headers = (409 if isinstance(error, RuntimeError) else 403), ui._page(
                        '此操作暂时无法完成', '<p>' + html.escape(public_output.cleaner(root,
                            settings={} if workspace else None)(str(error))) + '</p>'), {}
            try:
                self.send_response(status)
                self.send_header('Content-Type', headers.pop('Content-Type', 'text/html; charset=utf-8'))
                # Native forms retain their exact same-origin Origin in Chrome.
                # Capability-entry documents override this to no-referrer.
                for key, value in {'Cache-Control': 'no-store', 'Referrer-Policy': 'same-origin',
                        'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy':
                        render.CSP, **headers}.items():
                    self.send_header(key, value)
                if isinstance(body, live.Stream):
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.close_connection = True
                    body.write(self.wfile)
                    return
                length=body.size if isinstance(body,science.Original) else body.stat().st_size if isinstance(body,Path) else len(body)
                self.send_header('Content-Length',str(length))
                self.end_headers()
                if isinstance(body,science.Original):
                    body.copy_to(self.wfile)
                elif isinstance(body,Path):
                    with c.regular(body).open('rb') as stream:
                        shutil.copyfileobj(stream,self.wfile)
                else:
                    self.wfile.write(body)
            finally:
                if isinstance(body,science.Original):body.close()

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')

    with _host_lock(root, workspace=workspace), ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
        ui.host = '127.0.0.1:' + str(server.server_port)
        if ui.approvals:
            endpoint = dict(instance=ui.instance, boot=ui.boot, origin='http://' + ui.host)
            endpoint['receipt_hmac'] = security.receipt_hmac(ui.secret, security.canonical(endpoint))
            c.write(root / 'execution-authority/ui-endpoint.json', endpoint)
        print(json.dumps(dict(status='ui_listening', instance=ui.instance,
            management_url='http://' + ui.host + '/manage?token=' + ui.management_token,
            read_url='http://' + ui.host + '/view?token=' + ui.read_token), ensure_ascii=False), flush=True)
        try:
            server.serve_forever(poll_interval=.5)
        except KeyboardInterrupt:
            pass
        finally:
            ui.live_stop.set()
            if ui.approvals:
                (root / 'execution-authority/ui-endpoint.json').unlink(missing_ok=True)
    return dict(status='ui_stopped')
