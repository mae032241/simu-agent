"""Shared read-only projection of persisted progression facts; no report writing."""
from html import escape
from urllib.parse import quote

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
        budget_exhausted='预算耗尽', resource_limit='资源止损', archive_restored='归档恢复后保持暂停')
    body = "<section class='workbench-section progression-panel'><h2>目标推进</h2><dl class='metadata'>"
    for label, value in (("状态", states.get(status.get('state'), status.get('state'))),
            ("推进方式", status.get('mode')), ("等待 / 停止原因", reasons.get(status.get('reason'), status.get('reason'))),
            ("当前调度者", status.get('writer', 'none')), ("宿主状态", status.get('runtime_status')),
            ("故障记录", status.get('fault_code'))):
        body += '<dt>' + label + '</dt><dd>' + _text(value) + '</dd>'
    body += '</dl><p>暂停或停止只阻止后续调度；在途 Worker 和外部任务仍可完成。取消外部任务是独立操作，须核对其实际结果。</p>'
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
    notices = status.get('notifications') or {}
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
            ('waiting_seconds', '等待时间（秒）'), ('observed_tokens', '已观测 Token'),
            ('token_coverage', '目标 Token 覆盖'), ('time_coverage', '时间覆盖'), ('token_enforcement', 'Token 约束方式')):
        body += '<dt>' + label + '</dt><dd>' + _text(budget.get(key)) + '</dd>'
    body += '</dl>'
    if budget.get('limits'):
        body += '<details><summary>本次冻结预算上限</summary>' + render_json_value(budget['limits'], max_bytes=8192) + '</details>'
    usage = status.get('usage') or {}
    body += '<p>用量覆盖：' + _text(usage.get('coverage')) + '；货币费用未测量。缓存输入是输入子集，不重复相加。</p>'
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
