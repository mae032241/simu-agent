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
                     human_confirmation=None, background_continuations=()):
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
                + "。请先读取上方原始缺口。此决定不代表科学问题已解决，不增加预算；确认从已消费水位开启下一观察窗口；"
                "原墙钟预算继续计时，耗尽时请明确选择下方独立人工工作。未知提交须先核清。"
                "后续窗口仍会按科研阈值暂停；返回后台仍受原预算约束。</p>"
                + "<form method='post' action='/instances/progression'>" + common
                + hidden("command", "human_continue") + hidden("instance_id", current.instance_id)
                + hidden("confirmation_binding", human_confirmation)
                + "<label><input type='checkbox' name='confirm_human_continue' value='yes' required>"
                "我已读取原始缺口，确认从当前已消费水位继续此目标，保留所有额度及旧触发</label>"
                "<button type='submit'>人工接管并继续（保留预算）</button></form></details>")
            body += ("<details><summary>建立独立人工工作作用域</summary>"
                "<p>明确另起交互工作，可选择当前或新的确切目标。原后台任务数、轮次、token 和墙钟预算保留，"
                "本次人工任务单独记账；实例执行累计预算仍适用。此决定不授权新后台预算，不清除未知提交、"
                "原范围的科学暂停或触发历史。暂停、切换调度者或目标后须重新确认。</p>"
                + "<form method='post' action='/instances/progression'>" + common
                + hidden("command", "independent_interactive") + hidden("instance_id", current.instance_id)
                + hidden("confirmation_binding", human_confirmation)
                + "<label>本次人工工作的确切目标名称<input name='objective_name' required></label>"
                "<label><input type='checkbox' name='confirm_independent_interactive' value='yes' required>"
                "我确认这是独立人工工作，保留旧后台账目与实例执行预算</label>"
                "<button type='submit'>确认独立人工工作</button></form></details>")
        for target in background_continuations:
            body += "<details><summary>恢复后台目标：" + escape(target.get('objective_name') or '目标绑定待核对') + "</summary>"
            if target.get('error'):
                body += '<p>' + escape(target['error']) + '</p></details>'
                continue
            remaining = target['remaining']
            body += '<p>后台暂停原因：' + escape(', '.join(item['reason'] for item in target['causes']))
            body += '。剩余任务：' + str(remaining['tasks']) + '；剩余轮次：' + str(remaining['rounds'])
            body += '；剩余时间秒：' + str(round(remaining['seconds'])) + '；剩余 token：' + str(remaining['tokens'])
            body += '。从后台已消费水位 ' + str(target['through_sequence']) + ' 开启下一窗口；人工窗口、旧触发与全部账目保留。</p>'
            body += "<form data-background-continue method='post' action='/instances/progression'>" + common
            body += hidden('command', 'human_continue') + hidden('instance_id', current.instance_id)
            body += hidden('objective_name', target['objective_name']) + hidden('confirmation_binding', target['confirmation_binding'])
            body += "<label><input type='checkbox' name='confirm_human_continue' value='yes' required>我确认恢复这个确切后台目标，保留全部额度</label>"
            body += "<button type='submit'>确认恢复后台目标</button></form></details>"
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
