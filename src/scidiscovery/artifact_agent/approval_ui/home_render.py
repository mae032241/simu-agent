"""Home, instance directory and explicit session handoff forms."""
from html import escape
from urllib.parse import quote

from .navigation import hidden, navigation
from .progression_render import render_progression


def page(title, content):
    return ("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)}</title><link rel='stylesheet' href='/static/style.css'></head><body>"
        + navigation() + "<main class='home-page'><h1>" + escape(title) + "</h1>" + content + "</main></body></html>").encode()


def client_directory(rows, *, csrf, links, offset=0, cleared=None):
    cards = []
    for row in rows:
        key = row["session_key"]
        state = "已暂停" if not row["enabled"] else "已选择 · 按实例调度权执行" if row["instance_id"] else "申请绑定"
        label = "暂停后续调度" if row["enabled"] else "恢复调度"
        cards.append("<article class='instance-directory-card'><h2>科研会话 · " + escape(key[-8:]) + "</h2>"
            "<p>在线 · " + state + "</p><p>关联实例：" + escape(row["title"] or "尚未绑定") + "</p>"
            "<p>登记时间：" + escape(row["requested_at"]) + "</p>"
            "<a href='" + escape(links[key], quote=True) + "'>" + ("选择此会话并管理绑定" if row["instance_id"] else "处理绑定申请") + "</a>"
            "<form method='post' action='/instances/client-state'>" + hidden("csrf", csrf) + hidden("session_key", key)
            + hidden("expected_enabled", str(row["enabled"])) + hidden("enabled", str(1-int(row["enabled"])))
            + "<button type='submit'>" + label + "</button></form></article>")
    paging = (f"<a href='/sessions?offset={max(0,offset-30)}'>上一页</a>" if offset else "")
    if len(rows)==30: paging += f"<a href='/sessions?offset={offset+30}'>下一页</a>"
    return page("科研会话管理", "<p>仅显示正在连接的科研客户端；首次调用科研工具后登记，由工作台选择实例并确认。"
        "客户端每 20 秒自动发送心跳，正常断开即退出列表；异常中断最多 90 秒后退出。在线不代表正在计算。<a href='/sessions'>刷新列表</a></p>"
        "<p>暂停保留绑定和记录，阻止后续科研操作，不会强杀已有任务。归档还需等待已有任务和文件收集结束。</p>"
        + ("<p role='status'>已清理 " + str(cleared) + " 个离线会话。</p>" if cleared is not None else "")
        + "<form method='post' action='/instances/clients-clear'>" + hidden("csrf", csrf)
        + "<button type='submit'>清理离线会话</button><p class='source-note'>删除离线会话记录并解除其临时绑定；实例、科研成果和后台任务保留。正在归档或恢复的关联记录暂不清理。</p></form>"
        + "<div class='instance-directory'>" + ("".join(cards) or "<p>暂无在线科研会话。实例资料仍可从首页的实例管理查看。</p>")
        + "</div>" + paging)


def access_form(instance_id, *, csrf, label, scope="read", destination=""):
    return ("<form method='post' action='/instances/access'>" + hidden("csrf", csrf)
        + hidden("instance_id", instance_id) + hidden("scope", scope)
        + hidden("destination", destination) + "<button type='submit'>" + escape(label) + "</button></form>")


def access_page(instance, *, csrf, destination=""):
    title = "Agent 设置" if destination == "settings" else "资料整理与归档" if destination == "manage" else "实例工作台"
    return page("进入" + title, "<p>" + escape(instance.title) + "</p>"
        "<p>尚未取得此实例的浏览授权，或授权已过期。可直接从本机进入，无需连接科研对话。</p>"
        + access_form(instance.instance_id, csrf=csrf, label="进入" + title,
            scope="maintenance" if destination else "read", destination=destination)
        + "<p class='source-note'>此操作不会绑定或切换科研对话，不会批准执行或启动研究任务。</p>")


def create_form(*, csrf, token=None):
    action = "create" if token else "create-unbound"
    label = "创建并绑定当前会话" if token else "创建实例（不绑定对话）"
    return ("<details class='research-panel' data-create-instance><summary>创建实例</summary><div class='research-panel-body'>"
        "<form class='instance-command' method='post' action='/instances/" + action + "'>"
        + hidden("csrf", csrf) + (hidden("capability", token) if token else "")
        + "<label>实例名称<input name='name' required maxlength='256' pattern='[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}'></label>"
        "<label>显示标题<input name='title' required maxlength='512'></label>"
        "<label>研究目标<textarea name='objective' required maxlength='8192'></textarea></label>"
        "<button type='submit'>" + label + "</button></form></div></details>")


def session_controls(rows, *, token, csrf, current=None, expires_at=None, workbench_available=True, progression=None,
                     human_confirmation=None, background_continuations=(), loop_proposal=None):
    current_title = escape(current.title) if current else "尚未绑定实例"
    body = ("<section class='home-session' id='session-binding'><h2>实例绑定</h2><p class='session-title'>"
            + current_title + "</p><p>打开实例查看资料不会改变会话绑定。</p>")
    common = hidden("capability", token) + hidden("csrf", csrf)
    if current and workbench_available:
        body += ("<form method='post' action='/instances/access'>" + common + hidden("instance_id", current.instance_id)
            + hidden("scope", "read") + "<button type='submit'>进入当前实例工作台</button></form>")
    elif current:
        body += "<a href='/instance/" + quote(current.instance_id, safe="") + "'>查看当前实例基本信息</a>"
    body += "<p class='source-note'>本页会话授权有效期：" + escape(expires_at or "") + "</p>"
    if current and progression:
        body += render_progression(progression, instance_id=current.instance_id)
        body += ("<section><h3>调度控制</h3><p>后台启动以实际宿主状态为准。</p>"
            + "<form method='post' action='/instances/progression'>" + common
            + "<label>确切目标名称（启动时可指定）<input name='objective_name'></label>"
            + "<label>模式<select name='mode'><option value='interactive'>交互</option><option value='background'>后台</option></select></label>"
            + "<button name='command' value='start'>启动</button></form>")
        for command, label in (("pause", "暂停"), ("resume", "恢复"), ("stop", "停止"), ("takeover", "接管交互调度")):
            body += ("<form method='post' action='/instances/progression'>" + common
                + hidden("command", command) + "<button type='submit'>" + label + "</button></form>")
        if human_confirmation:
            body += ("<details><summary>人工接管并继续（保留预算）</summary>"
                "<p>适用于已暂停且原生提交已核清的当前目标：" + escape(progression.get('objective_name') or '')
                + "。确认后转为交互模式，由你继续调度当前目标。请先读取上方原始缺口。"
                "此决定不代表科学问题已解决，不增加预算；确认从已消费水位开启下一观察窗口；"
                "使用原 loop 的剩余额度，明确暂停不计推进启用时间。未知提交须先核清。"
                "后续窗口仍会按科研阈值暂停；返回后台仍受原预算约束。</p>"
                + "<form method='post' action='/instances/progression'>" + common
                + hidden("command", "human_continue") + hidden("instance_id", current.instance_id)
                + hidden("confirmation_binding", human_confirmation)
                + "<label><input type='checkbox' name='confirm_human_continue' value='yes' required>"
                "我已读取原始缺口，确认从当前已消费水位继续此目标，保留所有额度及旧触发</label>"
                "<button type='submit'>人工接管并继续（保留预算）</button></form></details>")
        if loop_proposal and loop_proposal['available']:
            from .presentation_render import render_json_value
            body += ("<details data-loop-authorization><summary>明确授权新的研究 loop 预算</summary>"
                "<p>本次授权冻结以下额度与配置；容量上限不是自动授权。授权后仍保持暂停，请再启动所选目标。"
                "交互、后台、换目标和人工继续共享此 loop；恢复不续额。实例执行池继续累计。"
                "研究名额与精确独立审查名额分别冻结；审查名额不挪用研究名额，审查及 helper 用量仍计总预算。"
                "旧任务与迟到用量归原 loop；活动／未知工作及原生宿主真实用量缺口会阻止创建。"
                "前台 Root、Worker 和 helper 尚未接入原生遥测；strict 拒绝缺测时新增工作，"
                "bounded_fallback 按任务、时间和已知 tokens 限额继续，保留 missing／partial，不能保证全角色 token 硬封顶。"
                "此预算决定不清除科学暂停。"
                "事先授权有限策略创建入口尚未实现。</p>"
                "<p>自然期限从本次确认起连续计时，暂停和服务停机也流逝；推进启用时长包含正常外部等待，"
                "排除明确暂停。任一额度耗尽就停止新派发；有效剩余时间取两者较小值。"
                "单个外部作业仍使用原执行时限，不随 loop 扩大。</p>"
                "<p>恢复策略随本次确认冻结：本地安全观察耗尽短重试后按退避有限恢复；"
                "确认失败的 Root 回合仅在 recover_failed_turns 启用时恢复为下一次决策。"
                "累计恢复受 max_recoveries 限制，连续失败受 recovery_failure_threshold 限制；"
                "原生恢复还同时受 max_attempts 限制（默认 2），max_recoveries 不扩展该额度。"
                "恢复继续消耗原回合、token 与时间余额；暂停、停止、科学刹车及未知提交不会自动复活，"
                "已接受任务与远端提交不重放。恢复次数与退避经重启、换目标或人工继续均不清零。</p>"
                + '<p>本次自然寿命：' + str(loop_proposal['limits']['max_calendar_seconds'])
                + ' 秒；推进启用时长：' + str(loop_proposal['limits']['max_elapsed_seconds'])
                + ' 秒；初始有效时间上限：' + str(min(loop_proposal['limits']['max_calendar_seconds'],
                    loop_proposal['limits']['max_elapsed_seconds'])) + ' 秒。截止时间在确认时冻结。</p>'
                + render_json_value(loop_proposal['limits'], max_bytes=16384)
                + "<form method='post' action='/instances/progression'>" + common
                + hidden("command", "authorize_loop") + hidden("instance_id", current.instance_id)
                + hidden("confirmation_binding", loop_proposal['confirmation_binding'])
                + "<label>新 loop 的确切原始目标名称<input name='objective_name' required></label>"
                "<label><input type='checkbox' name='confirm_loop_budget' value='yes' required>"
                "我明确授权上述完整预算、自然期限、推进启用时长与恢复策略；旧任务不重放，科学暂停另行核对</label>"
                "<button type='submit'>确认新 loop 预算</button></form></details>")
        for target in background_continuations:
            body += "<details><summary>恢复后台目标：" + escape(target.get('objective_name') or '目标绑定待核对') + "</summary>"
            if target.get('error'):
                body += '<p>' + escape(target['error']) + '</p></details>'
                continue
            remaining = target['remaining']
            body += '<p>后台暂停原因：' + escape(', '.join(item['reason'] for item in target['causes']))
            body += '。剩余任务：' + str(remaining['tasks']) + '；剩余轮次：' + str(remaining['rounds'])
            body += '；剩余时间秒：' + str(round(remaining['seconds'])) + '；剩余 token：' + str(remaining['tokens'])
            body += '。剩余时间取自然期限与启用时长余额较小值；自然期限经过暂停和停机仍流逝。正常等待及同 loop 人工工作计启用时长，明确暂停不计启用时长；恢复不重置额度'
            body += '。从后台已消费水位 ' + str(target['through_sequence']) + ' 开启下一窗口；人工授权与分账、旧触发与全部账目保留。</p>'
            body += '<p>确认后转为后台自动推进，并将当前目标切换为所选目标：' + escape(target['objective_name'])
            body += '。其他目标的暂停仍须分别确认；多次确认后，最后选择的目标成为当前目标。</p>'
            body += "<form data-background-continue method='post' action='/instances/progression'>" + common
            body += hidden('command', 'human_continue') + hidden('instance_id', current.instance_id)
            body += hidden('objective_name', target['objective_name']) + hidden('confirmation_binding', target['confirmation_binding'])
            body += "<label><input type='checkbox' name='confirm_human_continue' value='yes' required>我确认切换到这个目标并在后台继续，保留全部额度</label>"
            body += "<button type='submit'>确认切换目标并在后台继续</button></form></details>"
        body += "</section>"
    options = "<option value='' disabled selected>选择要绑定的实例</option>"
    for row in rows:
        instance = row["instance"]
        if instance.state != "active" or row["storage_state"] not in {"active", "restored"} or row["binding"]["target_is_current"]:
            continue
        options += ("<option value='" + escape(instance.name, quote=True) + "'>" + escape(instance.title)
            + " · " + escape(row["binding_label"]) + "</option>")
    body += ("<section><h3>绑定或接续实例</h3><form class='instance-command' method='post' action='/instances/select'>"
        + common + "<label>目标实例<select name='name' required>" + options + "</select></label>"
        "<button type='submit'>绑定到当前会话</button></form><p class='source-note'>选择仅增加当前读取关系；调度权须通过上方控制取得或显式接管。</p></section>"
        + "<p><a href='/#create-instance'>需要新实例？前往首页创建</a></p></section>")
    return body


def instance_directory(rows, *, token, csrf, offset=0, total=0, workbench_available=True, maintenance_available=True, local_access=False):
    cards = []
    for row in rows:
        instance = row["instance"]
        path = "/instance/" + quote(instance.instance_id, safe="")
        buttons = ""
        if not workbench_available:
            buttons += f"<a href='{path}'>查看基本信息</a>"
        elif row["can_read"]:
            buttons += f"<a class='button-link' href='{path}'>查看状态与轨迹</a>"
        elif token or local_access:
            buttons += access_form(instance.instance_id, csrf=csrf, label="查看状态与轨迹")
        else:
            buttons += f"<a href='{path}'>查看基本信息</a><span class='source-note'>状态与轨迹需要实例浏览授权</span>"
        entries = []
        if workbench_available:
            entries.append(("settings", "Agent 设置"))
        if maintenance_available:
            entries.append(("manage", "资料整理与归档"))
        for destination, label in entries:
            if row["can_manage"]:
                buttons += f"<a href='{path}/{destination}'>{label}</a>"
            elif token or local_access:
                buttons += access_form(instance.instance_id, csrf=csrf, label=label, scope="maintenance", destination=destination)
            elif destination == "settings" and row["can_read"]:
                buttons += f"<a href='{path}/settings'>查看 Agent 设置</a>"
        status = escape(row["status"])
        cards.append("<article class='instance-directory-card'><div><h2>" + escape(instance.title)
            + "</h2><span class='workbench-state'>" + escape(row["storage_label"]) + "</span></div>"
            "<p>" + escape(row["binding_label"]) + "</p><p class='instance-latest'>" + status + "</p>"
            "<div class='instance-actions'>" + buttons + "</div></article>")
    paging = ""
    if offset:
        paging += f"<a href='/instances/manage?offset={max(0, offset-30)}'>上一页</a>"
    if offset + len(rows) < total:
        paging += f"<a href='/instances/manage?offset={offset+len(rows)}'>下一页</a>"
    return page("实例管理", "<p>查看每个实例的当前状态、研究轨迹和阶段成果。浏览不会改变科研会话绑定。</p>"
        "<p class='source-note'>创建实例请返回首页；绑定或接续请进入具体科研会话。</p>"
        + "<div class='instance-directory'>" + ("".join(cards) or "<p>暂无实例，请在首页创建。</p>")
        + "</div><nav class='directory-pagination'>" + paging + "</nav>")


def confirm_binding(*, action, values, token, csrf, snapshot, current_title, target_title, activity):
    fields = hidden("capability", token) + hidden("csrf", csrf) + hidden("confirm_binding", "yes")
    fields += hidden("expected_binding", snapshot["fingerprint"])
    fields += "".join(hidden(key, value) for key, value in values.items())
    ownership = "目标实例已有其他读取会话；选择后这些会话仍可读取。" if snapshot["target_bound"] else "目标实例没有其他会话绑定。"
    return page("确认科研会话接续", "<section class='home-session'><p>当前实例：<strong>" + escape(current_title)
        + "</strong></p><p>接续到：<strong>" + escape(target_title) + "</strong></p><p>" + ownership
        + "</p><p>原实例的记录会保留。读取选择不取得或转移调度权，也不代表新的执行授权。</p>"
        "<p>已记录的任务情况：" + escape(activity) + "</p><form method='post' action='/instances/" + escape(action, quote=True) + "'>"
        + fields + "<button type='submit'>确认接续到当前会话</button> <a href='/sessions'>取消并返回会话列表</a></form></section>")
