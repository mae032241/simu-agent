"""Shared read-only projection of persisted progression facts; no report writing."""
from html import escape
from urllib.parse import quote, urlencode

from .presentation_render import render_json_value


def _text(value):
    return escape(str(value)) if value is not None else '未测量 / 未提供'


def render_progression(status, *, instance_id):
    if not isinstance(status, dict):
        return "<section class='workbench-section'><h2>目标推进</h2><p>推进状态未读取。</p></section>"
    base = '/instance/' + quote(instance_id, safe='')
    states = dict(idle='尚未启动', active='推进中', pending='等待宿主', paused='已暂停', stopped='已停止')
    reasons = dict(not_started='尚未启动', interactive='交互调度', runtime_unavailable='等待可用宿主',
        host_active='宿主已连接', user_paused='用户暂停', user_stopped='用户停止',
        user_question='等待用户回答', waiting='等待条件变化', goal_completed='已记录目标结论',
        budget_exhausted='预算耗尽', resource_limit='资源止损', archive_restored='归档恢复后保持暂停',
        scientific_progress_persistent_gap='复判后仍缺少有依据的推进，暂停新派发',
        human_continuation='用户已确认人工继续，保留原缺口与预算',
        independent_interactive='用户已确认独立人工工作，旧后台预算另行保留')
    body = "<section class='workbench-section progression-panel'><h2>目标推进</h2><dl class='metadata'>"
    for label, value in (("状态", states.get(status.get('state'), status.get('state'))),
            ("推进方式", status.get('mode')), ("等待 / 停止原因", reasons.get(status.get('reason'), status.get('reason'))),
            ("当前调度者", status.get('writer', 'none')), ("宿主状态", status.get('runtime_status')),
            ("故障记录", status.get('fault_code'))):
        body += '<dt>' + label + '</dt><dd>' + _text(value) + '</dd>'
    body += '</dl><p>暂停或停止只阻止后续调度；在途 Worker 和外部任务仍可完成。取消外部任务是独立操作，须核对其实际结果。</p>'
    body += '<p>诊断已预留但未获接收确认时须保留预留并安全停止，读取已有诊断状态或任务 run_status。当前版本尚无可信缺席证明 / 退款入口，需待受信控制协议合入后验证。</p>'
    human = status.get('human_continuation') or {}
    if human.get('history'):
        body += '<h3>人工继续记录</h3><p>' + ('当前人工继续有效。' if human.get('active') else '历史确认当前不生效。')
        body += '用户决定属于调度控制，不是新的科学证据；原始缺口与复判次数仍见科研进展观测。</p>'
        body += render_json_value(human, max_bytes=16384)
    independent = status.get('interactive_session') or {}
    if independent.get('history'):
        body += '<h3>独立人工工作作用域</h3><p>下方 budget / usage 属于保留的后台调度会话。人工任务另记，实例执行累计预算始终适用；人工原生 token 用量可能未观测。</p>'
        body += render_json_value(independent, max_bytes=16384)
    if status.get('human_handoff'):
        body += '<h3>人工成果回后台交接</h3><p>仅消费已存在成果，仍受原后台预算约束；预算不足时保留成果及原通知，请明确选择独立人工工作。科学推进仍须 Root 引用原件判断。</p>'
        body += render_json_value(status['human_handoff'], max_bytes=4096)
    if status.get('historical'):
        body += '<p>以下为归档时的历史推进记录；通知仅供回读，不会恢复调度或重发通知。</p>'
    body += '<p>关闭终端或重新选择读取实例不会暂停推进，也不会接管调度权。</p>'
    name = status.get('objective_name')
    if name:
        body += "<p><a href='" + base + '/nodes/' + quote('artifact:' + name, safe='') + "'>读取本次目标原文 · " + _text(name) + '</a></p>'
    command = status.get('last_command')
    if command:
        body += '<h3>最近控制命令的实际结果</h3>' + render_json_value(command, max_bytes=2048)
        body += '<p>此处为执行时回读；当前状态见上方。</p>'
    for field, title in (('report', '已知结论与待答问题'), ('last_report', '先前目标 / 轮次摘要（历史）')):
        report = status.get(field)
        if not report:
            if field == 'report':
                body += '<h3>' + title + '</h3><p>尚无目标摘要；任务成果请按下方原件核对。</p>'
            continue
        body += '<h3>' + title + '</h3><p>' + _text(report.get('summary')) + '</p>'
        body += '<p>目标结束记录：' + ('已记录' if report.get('completed') else '未记录') + '</p>'
        body += '<p>剩余 / 待答问题：' + _text(report.get('question')) + '</p>'
    body += "<p><a href='" + base + "#trajectory'>任务成果、限制、图件、表格与授权原件</a>（任务完成不自动代表整个目标完成。）</p>"
    closeout = status.get('closeout')
    if closeout:
        body += '<h3>本目标任务成果交接</h3><p>以下按已接受任务读取封存结果，不代表整个目标完成，也不是新的科学结论。</p>'
        body += '<p>停止 / 等待原因：' + _text(reasons.get(closeout.get('stop_reason'), closeout.get('stop_reason'))) + '</p>'
        for item in closeout['tasks']:
            body += "<h4><a href='" + base + '/nodes/' + quote('run:' + item['name'], safe='') + "'>" + _text(item['name']) + '</a> · ' + _text(item['state']) + '</h4>'
            output = item.get('output_artifact_name')
            if output:
                body += "<p><a href='" + base + '/nodes/' + quote('artifact:' + output, safe='') + "'>封存输出 · " + _text(output) + '</a></p>'
            body += render_json_value({key: item[key] for key in ('scientific_intent', 'selected_output', 'scheduler_signal',
                'scheduler_signal_omissions', 'content_unavailable', 'reason') if key in item}, max_bytes=16384)
        if closeout['in_flight'] or closeout['unresolved']:
            body += '<p>仍有在途或未核清任务，不得视为交付完成。</p>' + render_json_value(
                closeout['in_flight'] + closeout['unresolved'], max_bytes=8192)
        if closeout['omissions']:
            body += '<p>部分结果超过交接显示上限，请从准确任务入口继续读取。</p>'
        if not closeout['tasks']:
            body += '<p>尚无可读取的已接受任务成果。</p>'
    for key, title in (('progress_shadow', '科研进展观测与提示'), ('external_work', '未结束外部作业与消费责任'), ('terminal_deliveries', '终态信息投递与结算')):
        if status.get(key):
            body += '<h3>' + title + '</h3>' + render_json_value(status[key], max_bytes=16384)
    continuation = (status.get('terminal_deliveries') or {}).get('continuation')
    if continuation:
        query = urlencode({key: continuation[key] for key in ('delivery_cursor', 'delivery_limit')})
        body += "<p><a href='" + base + '?' + escape(query, quote=True) + "'>继续读取终态投递历史</a></p>"
    progress = status.get('progress') or {}
    if progress.get('items'):
        body += '<h3>目标进展判断（Root，非科学审查）</h3>'
        for item in progress['items']:
            body += '<h4>' + _text(item['task_name']) + ' · 修订 ' + _text(item['revision']) + '</h4>'
            body += render_json_value(item, max_bytes=16384)
        if progress.get('next_cursor') is not None:
            body += '<p>另有判断历史，可通过 progression_status 的进展续页读取。</p>'
    notices = status.get('notifications') or {}
    if status.get('platform_requests'):
        body += '<h3>平台请求与待答信息</h3>' + render_json_value(status['platform_requests'], max_bytes=16384)
    body += '<h3>持久事项</h3><p>刷新页面或查询推进状态可重读；相同阻塞合并。提供读取不等于用户已读或科研完成；未提供聊天推送和已读回执。</p>'
    categories = dict(user_decision='需用户决定', system_wait='系统等待', status='普通状态变化')
    for category, title in categories.items():
        items = [item for item in notices.get('items', []) if item.get('category') == category]
        if not items:
            continue
        body += '<h4>' + title + '</h4><ul>'
        for item in reversed(items):
            current = item.get('id') == notices.get('current_id')
            body += '<li>' + ('当前 · ' if current else '历史 · ') + _text(item.get('recorded_at')) + ' · '
            body += _text(item.get('question_preview') or reasons.get(item.get('reason'), item.get('reason')))
            if item.get('question_truncated'):
                body += '（问题预览；当前完整问题见上方）'
            body += '</li>'
        body += '</ul>'
    if not notices.get('items'):
        body += '<p>暂无已记录事项。</p>'
    if notices.get('omitted'):
        body += '<p>较早事项已省略：' + _text(notices['omitted']) + '。此列表不是完整事件日志。</p>'
    if status.get('messages'):
        body += '<h3>已补充的用户原文</h3><ul>'
        for item in status['messages']:
            body += "<li><a href='" + base + '/nodes/' + quote('artifact:' + item['name'], safe='') + "'>" + _text(item['name']) + '</a> · '
            body += ('推进器已处理' if item['processed'] else '等待下一个安全轮次') + '</li>'
        body += '</ul><p>补充原文不恢复已暂停目标，也不授予审批或执行权限。</p>'
    budget = status.get('budget') or {}
    body += '<h3>预算、用量与缺测</h3><dl class="metadata">'
    for key, label in (('rounds', '推进轮次'), ('tasks', '任务数'), ('attempts', '尝试数'), ('probes', '探测数'),
            ('elapsed_seconds', '经过时间（秒）'), ('root_running_seconds', 'Root 运行时间（秒）'),
            ('waiting_seconds', '等待时间（秒）'), ('observed_tokens', '最新已观测 Token'),
            ('stop_snapshot_tokens', '首次止损时已观测 Token'),
            ('token_coverage', '目标 Token 覆盖'), ('time_coverage', '时间覆盖'), ('token_enforcement', 'Token 约束方式')):
        body += '<dt>' + label + '</dt><dd>' + _text(budget.get(key)) + '</dd>'
    body += '</dl>'
    if budget.get('limits'):
        body += '<details><summary>本次冻结预算上限</summary>' + render_json_value(budget['limits'], max_bytes=8192) + '</details>'
    usage = status.get('usage') or {}
    body += '<p>用量覆盖：' + _text(usage.get('coverage')) + '；货币费用未测量。缓存输入是输入子集，不重复相加。</p>'
    if usage.get('unmeasured_participants'):
        body += '<p>已知参与者尚无用量观测：</p>' + render_json_value(usage['unmeasured_participants'], max_bytes=2048)
    body += '<table><thead><tr><th>归属</th><th>输入 Token</th><th>缓存输入</th><th>输出 Token</th><th>失败线程</th><th>缺测线程</th></tr></thead><tbody>'
    for role, label in (('root', 'Root'), ('worker', 'Worker'), ('helper', '助手'), ('unattributed', '未归属')):
        group = usage.get('groups', {}).get(role, {})
        tokens = group.get('tokens', {})
        body += '<tr><th>' + label + '</th>' + ''.join('<td>' + _text(value) + '</td>' for value in (
            tokens.get('input_tokens'), tokens.get('cached_input_tokens'), tokens.get('output_tokens'),
            group.get('failed_threads'), group.get('unmeasured_threads'))) + '</tr>'
    body += '</tbody></table><p>未观测数据不按零计算；异步 Token 与资源采样不能证明完整实时硬保护。</p>'
    resources = status.get('resources')
    body += '<h4>资源覆盖与限制</h4>' + (render_json_value(resources, max_bytes=8192) if resources
        else '<p>资源未测量；无法据此判断 Worker、助手或外部任务的完整资源消耗。</p>')
    return body + '</section>'
