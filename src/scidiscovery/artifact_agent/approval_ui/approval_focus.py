"""Decision-first display of exact approval subjects and recorded admission facts."""
import html
import logging

from .presentation_render import render_json_value, render_source


def execution_budget(model, approval_id):
    """Only follow the execution request explicitly frozen into this approval."""
    from ..schema.approval import ApprovalRequest
    from ..schema.execution import ExecutionRequest
    try:
        status = model.approvals.status(approval_id)
        request = ApprovalRequest.model_validate_json(model.artifacts.read(status.approval_request_ref), strict=True)
        refs = [ref for ref in request.subject_refs if ref.schema_id == 'scidiscovery.execution-request']
        if len(refs) != 1 or model.executions is None:
            return {}
        execution = ExecutionRequest.model_validate_json(model.artifacts.read(refs[0]), strict=True)
        registered = model.artifacts.get_by_id(model.executions.request_artifact_id(execution.execution_id))
        if registered.ref != refs[0]:
            return {}
        value = model.executions.authorization(execution.execution_id)
        value["budget_extension_limits"] = model.executions.budget_extension_limits.model_dump()
        return {key: value[key] for key in ('reason', 'budget', 'allowance', 'configured_allowance', 'budget_extension_limits', 'per_execution_allowance', 'budget_usage', 'accounting') if key in value}
    except Exception as error:
        logging.getLogger(__name__).warning('approval budget display unavailable: %s', type(error).__name__)
        return {}


def _text(value):
    return html.escape(str(value), quote=True)


def _amount(key, value):
    if type(value) is not int:
        return '未记录'
    if key.endswith('_seconds'):
        return f'{value:,} 秒（{value / 60:g} 分钟）'
    if key.endswith('_bytes'):
        return f'{value:,} 字节（{value / 1_000_000_000:g} GB）'
    return str(value)


def budget_brief(authorization):
    budget, allowance = authorization.get('budget', {}), authorization.get('per_execution_allowance') or authorization.get('allowance', {})
    return '；'.join(label + '：申请 ' + _amount(key, budget[key])
        + ' / 单次免审批阈值 ' + _amount(key, allowance.get(key))
        for key, label in (('wall_time_seconds', '时限'), ('max_storage_bytes', '存储')) if key in budget)


def render_approval_focus(presentation, *, subject_ids, evidence_href, authorization=None):
    """Keep requested values visible, exclude ancestor parameters, preserve sources."""
    body = ''
    authorization = authorization or {}
    budget, allowance = authorization.get('budget', {}), authorization.get('per_execution_allowance') or authorization.get('allowance', {})
    if budget:
        reasons = {'autonomy_disabled_or_budget_exceeded': '自动执行未启用，或本次申请超出自动执行额度。',
            'cumulative_budget_exceeded': '同一科学任务的累计自动执行额度不足。'}
        reason = reasons.get(authorization.get('reason'), authorization.get('reason') or '原记录未提供原因。')
        body += '<p class="approval-reason"><strong>为什么需要审批：</strong>' + _text(reason) + '</p>'
        remaining = (authorization.get('budget_usage') or {}).get('remaining', {})
        overage = (authorization.get('budget_usage') or {}).get('overage', {})
        rows = []
        for key, label in (('wall_time_seconds', '运行时限'), ('max_storage_bytes', '存储上限')):
            if key not in budget:
                continue
            exceeds = type(allowance.get(key)) is int and budget[key] > allowance[key]
            rows.append('<tr><th scope="row">' + label + '</th><td><strong>' + _amount(key, budget[key])
                + '</strong></td><td>' + _amount(key, allowance.get(key)) + '</td><td>'
                + _amount(key, max(0, remaining[key]) if type(remaining.get(key)) is int else None) + '</td><td>' + ('超出自动额度' if exceeds else '请结合累计额度与策略核对') + '</td></tr>')
        body += ('<p class="source-note">审批对象是本次申请。累计额度扣除已结算实际用量和未结算预留；预留不代表实际消耗。GB 按十进制显示。</p>'
            '<div class="approval-table-scroll"><table class="approval-key-table"><thead><tr>'
            '<th>审批项</th><th>本次申请</th><th>单次免审批阈值</th><th>累计可用额度</th><th>核对重点</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
        cumulative = authorization.get('allowance', {})
        if cumulative:
            body += '<p class="source-note">累计免审批阈值：' + '；'.join(
                label + ' ' + _amount(key, cumulative[key]) for key, label in
                (('wall_time_seconds', '时长'), ('max_storage_bytes', '存储')) if key in cumulative) + '</p>'
            configured = authorization.get('configured_allowance', {}).get('wall_time_seconds')
            if type(configured) is int and cumulative.get('wall_time_seconds', configured) > configured:
                body += '<p class="source-note">其中用户已追加累计时长：' + _amount('wall_time_seconds', cumulative['wall_time_seconds'] - configured) + '。</p>'
        accounting = authorization.get('accounting') or {}
        if accounting:
            actual = accounting.get('actual', {}).get('wall_time_seconds')
            body += '<p class="source-note">本次已结算实际时长：' + _amount('wall_time_seconds', actual) + (
                '。仍有未结算预留，不能视为实际消耗。' if accounting.get('unsettled_reservation') else '。') + '</p>'
            if accounting.get('estimated'):
                body += '<p class="source-note">终态缺少观测，以下项目按申请上限估算扣账（不是实测）：' + '；'.join(
                    label + ' ' + _amount(key, accounting['estimated'][key]) for key, label in
                    (('wall_time_seconds', '时长'), ('max_storage_bytes', '存储')) if key in accounting['estimated']) + '。</p>'
        if any(type(value) is int and value > 0 for value in overage.values()):
            body += '<p class="source-note">累计超额（不是本次申请）：' + '；'.join(_amount(key, value) for key, value in overage.items() if value > 0) + '</p>'
    presentation = presentation or {}
    subjects = set(subject_ids)
    cards, seen = [], set()
    for section in presentation.get('sections', []):
        if section.get('kind') != 'execution_scope':
            continue
        for item in section.get('items', []):
            ref = item.get('source', {})
            identity = (ref.get('artifact_id'), ref.get('json_pointer'))
            if identity[0] not in subjects or identity in seen:
                continue
            seen.add(identity)
            # Long arrays stay in the detailed evidence panel; scalar limits stay visible.
            if isinstance(item.get('value'), (dict, list)):
                continue
            field = str(identity[1]).rsplit('/', 1)[-1]
            value = (_amount(field, item['value']) if type(item.get('value')) is int and field.endswith(('_bytes', '_seconds'))
                else render_json_value(item.get('value'), max_bytes=768, compact_numbers=True))
            cards.append('<div class="approval-key-fact"><dt>' + _text(item.get('label', '审批参数'))
                + '</dt><dd>' + value
                + render_source(ref, evidence_href) + '</dd></div>')
    if cards:
        body += '<dl class="approval-key-grid">' + ''.join(cards[:12]) + '</dl>'
        if len(cards) > 12:
            body += '<p class="source-note">其余执行参数请在下方完整依据中核对。</p>'
    parameters = [row for row in presentation.get('parameters', []) if row.get('source', {}).get('artifact_id') in subjects]
    if parameters:
        rows = []
        for row in parameters[:8]:
            rows.append('<tr><th scope="row">' + _text(str(row.get('name', '未命名参数'))[:256]) + '</th><td><strong>'
                + render_json_value(row.get('selected_value'), max_bytes=768, compact_numbers=True)
                + '</strong></td><td>' + _text(str(row.get('unit', '未记录'))[:128]) + '</td><td>'
                + render_json_value(row.get('case_scope'), max_bytes=384, compact_numbers=True)
                + render_json_value(row.get('conditions'), max_bytes=512, compact_numbers=True)
                + render_source(row.get('source'), evidence_href) + '</td></tr>')
        body += ('<div class="approval-table-scroll"><table class="approval-key-table"><thead><tr>'
            '<th>参数</th><th>本次取值</th><th>单位</th><th>适用范围与条件</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div><p class="source-note">展示前 8 项冻结参数；全部参数和不确定性见下方依据及原件参数页。</p>')
    if not body:
        body = '<p>此请求没有可提取的关键参数摘要；请核对下方冻结审批事项与原件。</p>'
    return ('<section class="approval-focus" aria-label="本次审批关键参数"><h2>本次审批关键参数</h2>'
        '<p class="source-note">仅摘要展示本次冻结对象；完整条件、结构化输入与审查依据仍需按下方原件核对。</p>'
        + body + '</section>')
