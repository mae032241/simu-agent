"""Typed, lossless host form for the shared research declaration.

No configuration file is required. Omission is meaningful: this module never
supplies preparation defaults and never starts research or reads credentials.
"""
from __future__ import annotations

import copy
import base64
import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time
from html import escape
import json
import math
from pathlib import Path

from . import research_config


@dataclass(frozen=True)
class Field:
    path: str
    label: str
    kind: str = 'string'
    choices: tuple = ()
    required: bool = False
    placeholder: str = ''


# Every declaration leaf is here, or inside an explicitly structured extension.
FIELDS = [
    Field('version', '声明版本', 'integer', placeholder='1'),
    Field('research.root', '新实例目录', required=True),
    Field('research.objective', '已有任务原件路径'),
    Field('research.public_root', '公开材料目录', required=True),
    Field('research.user_updates', '已有全局补充原件', 'strings'),
    Field('research.source_restrictions', '来源限制声明', 'array'),
    Field('agent.backend', 'Agent 后端', choices=('codex', 'protocol'), placeholder='codex'),
    Field('agent.launcher', '启动命令参数（逐项）', 'strings'),
    Field('agent.model', '全局模型', placeholder=research_config.DEFAULT_MODEL),
    Field('agent.reasoning_effort', '全局推理力度', placeholder=research_config.DEFAULT_REASONING_EFFORT),
    Field('agent.service_tier', '全局服务档位', placeholder=research_config.DEFAULT_SERVICE_TIER),
    *[Field(f'agent.roles.{role}.{key}', f'{role} 角色{label}')
      for role in 'HWAE' for key, label in [('model', '模型'), ('reasoning_effort', '推理力度'), ('service_tier', '服务档位')]],
    Field('agent.native.sandbox_workspace_write.writable_roots', '原生额外可写目录', 'strings'),
    *[Field(f'agent.native.sandbox_workspace_write.{key}', label, 'boolean') for key, label in [
        ('network_access', '原生 sandbox 联网'), ('exclude_tmpdir_env_var', '排除 TMPDIR'), ('exclude_slash_tmp', '排除 /tmp')]],
    Field('agent.native.features.fast_mode', '原生快速模式', 'boolean'),
    Field('permissions.workspace', '文件系统权限', choices=('read-only', 'workspace-write', 'danger-full-access')),
    Field('permissions.network', '网络权限', 'boolean'),
    Field('permissions.web', '网页检索权限', choices=('disabled', 'cached', 'live')),
    Field('permissions.subagents', '子 Agent 权限', 'boolean'),
    Field('budget.max_tokens', '总 tokens 预算', 'integer', required=True),
    Field('budget.max_seconds', '总活动时间（秒）', 'number', required=True),
    Field('budget.max_steps', '总节点步数', 'integer', required=True),
    Field('budget.max_output_item_bytes', '单项输出字节上限', 'integer'),
    Field('budget.max_output_total_bytes', '全部输出字节上限', 'integer'),
    Field('budget.candidate_extra_slots', '候选额外名额', 'integer'),
    Field('budget.portfolio_review_after_cycles', '组合复核周期数', 'integer'),
    *[Field(f'budget.node_targets.{role}.{key}', f'{role} 节点软目标：{label}', kind)
      for role in 'HWAE' for key, label, kind in [('max_observed_tokens', 'tokens', 'integer'), ('max_seconds', '秒', 'number')]],
    Field('budget.role_shares', '角色预算份额策略', 'table'),
    *[Field(f'budget.breadth.{key}', label, 'integer') for key, label in [
        ('max_w_seconds', 'W 软目标秒数'), ('max_w_observed_tokens', 'W 软目标 tokens'),
        ('max_requested_repairs', '请求修复次数'), ('initial_calls', '首次探索调用数')]],
    Field('budget.correction.review_after', '补正复核阈值', 'integer'),
    Field('budget.correction.pause_after', '补正暂停阈值', 'integer'),
    Field('executor.mode', '实验执行归属', choices=('local', 'external')),
    Field('executor.config.executor', '实验执行插件', placeholder='plugin:binding'),
    Field('executor.config.config_file', '插件配置文件', placeholder='./plugin.toml'),
    Field('executor.config.configuration', '插件内联配置（仅支持此方式的插件）', 'table'),
    Field('executor.resource_policy', '累计实验资源策略', 'table'),
    Field('delivery', '交付策略及 adapter 配置', 'table'),
    *[Field(f'policies.{key}', label, 'boolean') for key, label in [
        ('formal_review', '正式独立复核'), ('execution_authority', '实验执行授权合同'),
        ('candidate_audit', '候选审计'), ('decision_contract', '科学决策合同')]],
    Field('policies.worker_context', 'Worker 上下文', choices=('same_session', 'new_context')),
    Field('policies.selection', '选择策略', 'table'),
    Field('policies.resume', '原调用恢复策略', 'table'),
    Field('policies.history_observer', '历史观察器及插件配置', 'table'),
    Field('ui.port', '实例网页端口（0 为自动）', 'integer'),
    Field('ui.open_browser', '打开浏览器', 'boolean'),
    Field('ui.approval_secret_file', '宿主操作密钥文件引用（仅路径）'),
]


def _get(document, path, default=None):
    for key in path.split('.'):
        if not isinstance(document, dict) or key not in document:
            return default
        document = document[key]
    return document


def _put(document, path, value):
    keys = path.split('.')
    for key in keys[:-1]:
        if key not in document:
            document[key] = {}
        if not isinstance(document[key], dict):
            raise ValueError(f'{path}：父字段必须为对象')
        document = document[key]
    document[keys[-1]] = value


def _delete(document, path):
    keys = path.split('.')
    if len(keys) == 1:
        document.pop(keys[0], None)
    elif isinstance(document.get(keys[0]), dict):
        _delete(document[keys[0]], '.'.join(keys[1:]))
        if not document[keys[0]]:
            del document[keys[0]]


def blank(*, base):
    return dict(document={}, task_mode='text', task_text='', base=str(Path(base).resolve()))


def imported(document, *, base):
    if _get(document, 'research.objective') is not None and _get(document, 'research.objective_text') is not None:
        raise ValueError('任务输入：已有原件与任务原文只能选择一项')
    result = blank(base=base)
    result['document'] = copy.deepcopy(document)
    inline = _get(document, 'research.objective_text')
    result['task_mode'] = 'text' if inline is not None else 'file'
    result['task_text'] = inline if inline is not None else ''
    return result


def declaration(draft):
    document = copy.deepcopy(draft['document'])
    if draft['task_mode'] == 'text':
        _delete(document, 'research.objective')
        _put(document, 'research.objective_text', draft['task_text'])
    else:
        _delete(document, 'research.objective_text')
    return document


def load(path):
    path = Path(path).expanduser().resolve()
    return imported(research_config.read_declaration(path), base=path.parent)


def _single(fields, key, default=''):
    value = fields.get(key, default)
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise ValueError(f'{key}：字段不能重复')
        value = value[0]
    if not isinstance(value, str):
        raise ValueError(f'{key}：字段必须为文本')
    return value


def _typed(value, kind, label):
    try:
        if kind == 'boolean':
            if value not in ('true', 'false'):
                raise ValueError()
            return value == 'true'
        if kind == 'integer':
            return int(value) if value.strip() and all(c in '+-0123456789' for c in value) else _invalid()
        if kind == 'number':
            result = float(value)
            if not math.isfinite(result):
                raise ValueError()
            return result
        if kind == 'datetime':
            return datetime.fromisoformat(value)
        if kind == 'date':
            return date.fromisoformat(value)
        if kind == 'time':
            return time.fromisoformat(value)
        if kind == 'string':
            return value
    except (ValueError, OverflowError):
        raise ValueError(f'{label}：请输入有效的{dict(integer="整数", number="有限数字", boolean="布尔值").get(kind, kind)}') from None
    raise ValueError(f'{label}：不支持的类型')


def _invalid():
    raise ValueError()


class FormError(ValueError):
    """Recoverable typed entry error with every edited control retained."""
    def __init__(self, message, draft):
        super().__init__(message)
        self.draft = draft


class _Invalid(str):
    def __new__(cls, value, kind):
        item = super().__new__(cls, value)
        item.kind = kind
        return item

    def __getnewargs__(self):
        return str(self), self.kind


def parse(fields, *, base):
    """Parse only typed visible controls, retaining all extra imported data."""
    allowed = {'task_mode', 'task_text'} | {'cfg.'+f.path for f in FIELDS if f.kind not in ('table', 'array', 'strings')} | {'enabled.'+f.path for f in FIELDS if f.kind in ('table', 'array', 'strings')}
    for name in fields:
        parts = name.split('.')
        if name not in allowed and not any(name == 'cfg.'+f.path or (name.startswith('cfg.'+f.path+'.') and name[len('cfg.'+f.path+'.'):].isdecimal()) for f in FIELDS if f.kind == 'strings') and not (len(parts) == 3 and parts[0] == 'node' and parts[1].isdecimal() and parts[2] in {'kind','parent','key','value'}):
            raise ValueError('不支持的表单字段：'+name)
    result = blank(base=base)
    result['task_mode'] = _single(fields, 'task_mode', 'text')
    if result['task_mode'] not in ('text', 'file'):
        raise ValueError('任务输入：请选择文本或已有原件')
    result['task_text'] = _single(fields, 'task_text')
    errors = []
    def typed(value, kind, label):
        try:
            return _typed(value, kind, label)
        except ValueError as error:
            errors.append(str(error))
            return _Invalid(value, kind)
    nodes = {}
    for name in fields:
        if name.startswith('node.') and name.endswith('.kind'):
            identity = name[5:-5]
            if not identity.isdecimal() or len(nodes) >= 2000:
                raise ValueError('结构字段数量或标识无效')
            prefix = f'node.{identity}.'
            nodes[identity] = dict(kind=_single(fields, prefix+'kind'),
                parent=_single(fields, prefix+'parent'), key=_single(fields, prefix+'key'),
                value=_single(fields, prefix+'value'))
    used = set()
    def tree(parent, kind, depth=0):
        if depth > 24:
            raise ValueError('结构字段嵌套超过上限')
        value = {} if kind == 'table' else []
        for identity, node in nodes.items():
            if node['parent'] != parent:
                continue
            if identity in used:
                raise ValueError('结构字段存在循环')
            used.add(identity)
            item = (tree(identity, node['kind'], depth+1) if node['kind'] in ('table', 'array')
                    else typed(node['value'], node['kind'], node['key'] or '数组项'))
            if kind == 'table':
                if not node['key'] or node['key'] in value:
                    raise ValueError('结构字段：键名必填且不能重复')
                value[node['key']] = item
            else:
                value.append(item)
        return value
    for field in FIELDS:
        if field.kind == 'strings':
            prefix = 'cfg.'+field.path
            items = [_single(fields, name) for name in fields if name.startswith(prefix+'.')]
            if prefix in fields:
                items.append(_single(fields, prefix))
            if prefix in fields or _single(fields, 'enabled.'+field.path) == 'yes':
                _put(result['document'], field.path, items)
            continue
        if field.kind in ('table', 'array'):
            if _single(fields, 'enabled.'+field.path) == 'yes':
                _put(result['document'], field.path, tree('@'+field.path, field.kind))
            continue
        raw = _single(fields, 'cfg.'+field.path)
        if raw != '':
            if field.choices and raw not in field.choices:
                errors.append(f'{field.label}：请选择支持的选项')
            _put(result['document'], field.path, typed(raw, field.kind, field.label))
    # An explicit extra tree preserves empty groups and arbitrary imported keys.
    extras = tree('@extra', 'table')
    def merge(target, extra):
        for key, value in extra.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                merge(target[key], value)
            elif key in target:
                raise ValueError(f'{key}：扩展字段与标准字段重复')
            else:
                target[key] = value
    merge(result['document'], extras)
    # Disabled groups' children are deliberately omitted. Reject stray topology.
    allowed = {identity for identity, node in nodes.items() if node['parent'].startswith('@') and
               node['parent'][1:] in {f.path for f in FIELDS if f.kind in ('table', 'array', 'strings')}}
    pending = set(allowed)
    while pending:
        parent = pending.pop()
        for identity, node in nodes.items():
            if node['parent'] == parent and identity not in allowed:
                allowed.add(identity)
                pending.add(identity)
    if set(nodes) - used - allowed:
        raise ValueError('结构字段没有有效的父对象')
    if errors:
        raise FormError('；'.join(errors), result)
    return result


def _kind(value):
    if isinstance(value, _Invalid): return value.kind
    if isinstance(value, dict): return 'table'
    if isinstance(value, list): return 'array'
    if type(value) is bool: return 'boolean'
    if type(value) is int: return 'integer'
    if type(value) is float: return 'number'
    if isinstance(value, datetime): return 'datetime'
    if isinstance(value, date): return 'date'
    if isinstance(value, time): return 'time'
    if isinstance(value, str): return 'string'
    raise ValueError('声明包含不支持的字段类型')


def render(draft):
    """Render a guided form; hidden steps retain successful, typed controls."""
    document = draft['document']
    extras = copy.deepcopy(document)
    _delete(extras, 'research.objective_text')
    counter = [0]
    def tree(value, parent):
        contents = []
        items = value.items() if isinstance(value, dict) else enumerate(value)
        for key, item in items:
            counter[0] += 1
            identity = str(counter[0]); kind = _kind(item); prefix = 'node.'+identity+'.'
            scalar = str(item).lower() if type(item) is bool else (item.isoformat() if isinstance(item, (date,time)) else str(item))
            contents.append('<div class="config-node" data-node="'+identity+'" data-error-label="'+escape(str(key),quote=True)+'"'+(' data-invalid="true"' if isinstance(item, _Invalid) else '')+'>'
                '<input type="hidden" name="'+prefix+'parent" value="'+escape(parent, quote=True)+'">'
                '<label>键名 <input name="'+prefix+'key" value="'+escape(str(key) if isinstance(value,dict) else '',quote=True)+'"></label>'
                '<label>类型 <select name="'+prefix+'kind" class="config-kind">'+''.join(
                    '<option value="'+k+'"'+(' selected' if k==kind else '')+'>'+label+'</option>'
                    for k,label in [('string','文本'),('integer','整数'),('number','数字'),('boolean','布尔'),('table','对象'),('array','数组'),('datetime','日期时间'),('date','日期'),('time','时间')])+'</select></label>'
                '<label class="config-value">值 <input name="'+prefix+'value" value="'+escape(scalar if kind not in ('table','array') else '',quote=True)+'"></label>'
                '<button type="button" class="config-remove">删除此项</button>'
                '<div class="config-children" data-parent="'+identity+'">'+
                (tree(item, identity) if kind in ('table','array') else '')+'</div>'
                '<button type="button" class="config-add" data-parent="'+identity+'">添加子项</button></div>')
        return ''.join(contents)
    labels = {
        'research.root': '新研究保存到哪里', 'research.public_root': '研究可使用的材料目录',
        'research.objective': '任务文件路径', 'agent.model': '研究使用的模型',
        'agent.reasoning_effort': '推理力度', 'agent.service_tier': '服务档位',
        'budget.max_tokens': '模型用量上限', 'budget.max_seconds': '研究活动时间上限',
        'budget.max_steps': '研究阶段数上限', 'permissions.workspace': '文件读写范围',
        'permissions.network': '允许程序联网', 'permissions.web': '网页检索方式',
        'permissions.subagents': '允许创建子研究助手',
    }
    hints = {
        'research.root': '将在服务器上新建此目录，保存任务、研究记录和结果。请选择尚不存在的目录；不能覆盖已有研究。',
        'research.public_root': '填写服务器上已存在的目录，放入允许研究使用的文件。即使暂时没有材料，也需先准备一个空目录。这里不会上传浏览器中的文件。',
        'research.objective': '读取服务器上的现有文本文件；原文会作为本次任务保存。',
        'agent.model': '留空使用统一默认模型 '+research_config.DEFAULT_MODEL+'。各研究角色默认沿用此模型，可在高级设置中分别指定。',
        'agent.reasoning_effort': '留空使用统一默认值 '+research_config.DEFAULT_REASONING_EFFORT+'；具体支持取决于模型。',
        'agent.service_tier': '留空使用统一默认值 '+research_config.DEFAULT_SERVICE_TIER+'。',
        'budget.max_tokens': '单位：tokens，模型处理文本的用量，不是金额。必须由你填写；实际费用取决于模型及服务计价。',
        'budget.max_seconds': '单位：秒。累计研究活动时间，不是从创建起计算的日历时间；暂停等待不会自动恢复预算。',
        'budget.max_steps': '单位：阶段。每次研究角色工作算一个节点阶段，与时间、tokens 分别限制。',
        'permissions.workspace': '选择研究助手可读写的范围。留空采用统一配置；检查时会显示实际权限与限制。',
        'permissions.network': '控制程序的网络访问声明，与下方网页检索分别设置。实际能否限制由后端决定。',
        'permissions.web': '禁用、仅缓存或实时检索。留空采用统一配置，确认页显示生效值。',
        'permissions.subagents': '允许研究助手再创建子助手。留空采用统一配置；与本页面的研究角色分工不同。',
    }
    placeholders = {'research.root': '/srv/research/new-study', 'research.public_root': '/srv/research/materials',
                    'research.objective': '/srv/research/task.txt'}
    choice_labels = {'true':'允许', 'false':'不允许', 'read-only':'只读文件',
        'workspace-write':'可写工作目录', 'danger-full-access':'不限制文件访问',
        'disabled':'禁用网页检索', 'cached':'仅使用缓存', 'live':'实时检索'}

    def control(field, *, advanced=False):
        value = _get(document, field.path)
        if value is not None:
            _delete(extras, field.path)
        label = escape(labels.get(field.path, field.label))
        if field.path.startswith('agent.roles.'):
            role = field.path.split('.')[2]
            role_name = dict(H='提出方向', W='探索方案', A='评估复核', E='实验实现')[role]
            label = role_name+'（'+role+'） · '+dict(model='模型', reasoning_effort='推理力度', service_tier='服务档位')[field.path.split('.')[-1]]
        label += ' <span class="required-mark">必填</span>' if field.required else ''
        metadata = '<small class="field-key">'+escape(field.path)+'</small>' if advanced else ''
        hint = '<small class="field-help">'+escape(hints[field.path])+'</small>' if field.path in hints else ''
        identity = 'config-'+field.path.replace('.', '-')
        attributes = ' data-config-path="'+escape(field.path,quote=True)+'" data-error-label="'+escape(field.label,quote=True)+'"'+(' data-invalid="true"' if isinstance(value, _Invalid) else '')
        if field.kind == 'strings':
            if value is not None and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
                raise ValueError(f'{field.label}：导入值必须为文本数组')
            entries = ''.join('<div class="config-string-row"><textarea rows="1" aria-label="'+escape(field.label,quote=True)+'第 '+str(index+1)+' 项" name="cfg.'+field.path+'.'+str(index)+'">'+escape(item)+'</textarea><button type="button" class="config-string-remove secondary-button">删除</button></div>' for index,item in enumerate(value or []))
            return '<div class="config-field"'+attributes+'><p class="field-label">'+label+metadata+'</p><label class="check-label"><input type="checkbox" name="enabled.'+field.path+'" value="yes"'+(' checked' if value is not None else '')+'>显式声明此列表</label><div class="config-string-list" data-path="'+field.path+'">'+entries+'</div><button type="button" class="config-string-add secondary-button" data-path="'+field.path+'">添加一项</button></div>'
        if field.kind in ('table','array'):
            if value is not None and not isinstance(value, dict if field.kind=='table' else list):
                raise ValueError(f'{field.label}：导入类型不正确')
            return '<details class="structured-setting"'+attributes+'><summary>'+label+metadata+'</summary>'\
                '<label class="check-label"><input type="checkbox" name="enabled.'+field.path+'" value="yes"'+(' checked' if value is not None else '')+'>声明此可选组（取消后整组省略）</label>'\
                '<div class="config-children" data-parent="@'+field.path+'">'+tree(value if value is not None else ({} if field.kind=='table' else []),'@'+field.path)+'</div>'\
                '<button type="button" class="config-add secondary-button" data-parent="@'+field.path+'">添加项</button></details>'
        text = '' if value is None else (str(value).lower() if type(value) is bool else str(value))
        if field.choices or field.kind == 'boolean':
            choices = list(field.choices or ('true','false'))
            choices += [text] if text and text not in choices else []
            widget = '<select id="'+identity+'" name="cfg.'+field.path+'"><option value="">沿用统一配置'+('（'+escape(field.placeholder)+'）' if field.placeholder else '')+'</option>'+''.join(
                '<option value="'+escape(choice,quote=True)+'"'+(' selected' if text==choice else '')+'>'+escape(choice_labels.get(choice,choice))+'</option>' for choice in choices)+'</select>'
        else:
            widget = '<input id="'+identity+'" name="cfg.'+field.path+'" value="'+escape(text,quote=True)+'" placeholder="'+escape(placeholders.get(field.path,field.placeholder),quote=True)+'"'+(' inputmode="decimal"' if field.kind in ('integer','number') else '')+'>'
        return '<div class="config-field"'+attributes+'><label for="'+identity+'">'+label+metadata+'</label>'+widget+hint+'</div>'

    by_path = {field.path: field for field in FIELDS}
    def fields(paths, *, advanced=False):
        return ''.join(control(by_path[path], advanced=advanced) for path in paths)

    rows = ['<noscript><p class="note">请依次填写下方任务与资源设置，再点击底部“检查配置”。</p></noscript><section class="setup-panel" data-setup-step="1" aria-labelledby="setup-task-title">'
        '<div class="section-heading"><span class="eyebrow">第一步 / 任务与材料</span><h2 id="setup-task-title" tabindex="-1">你想研究什么？</h2>'
        '<p>写清问题、期望得到的结果，以及需要遵守的限制。先准备任务和文件，再设置研究用量。</p></div>'
        '<div class="config-field task-mode"><label for="task-mode">如何提供任务</label><select id="task-mode" name="task_mode">'+''.join(
            '<option value="'+mode+'"'+(' selected' if draft['task_mode']==mode else '')+'>'+label+'</option>'
            for mode,label in [('text','直接写下任务'),('file','读取已有任务文件')])+'</select></div>'
        '<div class="config-field" data-task-panel="text"><label for="task-text">研究任务 <span class="required-mark">必填</span></label>'
        '<textarea id="task-text" name="task_text" rows="6" placeholder="描述你要解决的问题、已有条件和期望交付的结果。">'+escape(draft['task_text'])+'</textarea>'
        '<small class="field-help">这段原文会作为本次研究的任务保存。请不要填写密码或访问密钥。</small></div>'
        '<div data-task-panel="file">'+fields(['research.objective'])+'</div>'
        '<div class="path-heading"><h3>材料从哪里来，结果存到哪里？</h3><p class="note">以下都是运行 SciDiscovery 的服务器上的目录，不是浏览器本机目录。</p></div>'
        +fields(['research.public_root','research.root'])+
        '<details class="path-base"><summary>服务器路径怎么填写？</summary><p>可填写完整绝对路径；相对路径从此服务器目录开始：<code>'+escape(draft['base'])+'</code></p></details>'
        '<div class="setup-actions"><span class="note">下一步：选择模型，填写用量上限</span><button type="button" hidden data-setup-go="2">下一步：模型与预算 →</button></div></section>']
    primary = ['agent.model','agent.reasoning_effort','agent.service_tier','budget.max_tokens','budget.max_seconds','budget.max_steps']
    permissions = ['permissions.workspace','permissions.network','permissions.web','permissions.subagents']
    rows.append('<section class="setup-panel" data-setup-step="2" aria-labelledby="setup-limits-title">'
        '<div class="section-heading"><span class="eyebrow">第二步 / 模型与预算</span><h2 id="setup-limits-title" tabindex="-1">这次研究可以使用多少资源？</h2>'
        '<p>模型可以沿用统一默认值。三项总预算都需明确填写，达到任一限制会影响研究继续。</p></div>'
        '<div class="model-fields">'+fields(primary[:3])+'</div>'
        '<h3 class="subsection-title">设定本次研究的总上限</h3><div class="budget-fields">'+fields(primary[3:])+'</div>'
        '<details class="permission-settings"><summary>研究助手可以访问什么？<span class="summary-note">权限与联网</span></summary>'
        '<p class="note">权限沿用统一配置，检查时会列出生效值。实验执行仍需自身的授权条件。</p>'+fields(permissions)+'</details>')
    used = set(primary+permissions+['research.root','research.public_root','research.objective'])
    categories = [
        ('补充任务与材料约束','research','已有全局补充原文、材料来源限制。'),
        ('模型角色与启动方式','agent','角色分别负责提出方向、探索方案、评估复核、实验实现；未单独指定时沿用全局模型。原生设置由所选后端解释。'),
        ('研究搜索与分阶段用量','budget','设置阶段软目标、角色份额、候选探索与输出上限；软目标不替代总预算。'),
        ('实验执行与资源','executor','选择执行归属与插件，声明累计实验资源。配置本身不会授予实验执行许可。'),
        ('交付与外部适配','delivery','交付策略、外部接口和相关插件参数。'),
        ('复核与恢复规则','policies','正式复核、决策合同、原调用恢复与历史观察配置。'),
        ('网页与本地管理','ui','实例网页端口与宿主管理文件路径。'),
        ('声明格式','version','导入配置的格式版本。'),
    ]
    rows.append('<details class="advanced-settings"><summary>高级设置<span class="summary-note">按用途展开 · 角色、实验、交付等完整参数</span></summary>'
        '<p class="note">只有需要覆盖统一配置或使用专门插件时才需要修改。已导入的值会完整保留；空白表示未声明。</p>')
    for title, prefix, explanation in categories:
        paths = [field.path for field in FIELDS if field.path not in used and (field.path == prefix or field.path.startswith(prefix+'.'))]
        rows.append('<details class="advanced-category"><summary>'+title+'</summary><p class="note">'+explanation+'</p>'+fields(paths, advanced=True)+'</details>')
    rows.append('<details class="advanced-category"><summary>其他导入字段</summary><p class="note">原样保留并校验额外字段；不支持的声明会在检查时提示。</p><div class="config-children" data-parent="@extra">'+tree(extras,'@extra')+'</div><button type="button" class="config-add secondary-button" data-parent="@extra">添加扩展字段</button></details></details>'
        '<div class="setup-actions"><button type="button" hidden class="secondary-button" data-setup-go="1">← 返回任务与材料</button><span class="note">下一步会检查配置，尚不创建或运行研究。</span></div></section>')
    rows.append('<script>'+SCRIPT_SOURCE+'</script>')
    return '\n'.join(rows)


SCRIPT_SOURCE = r'''
(() => {
document.addEventListener('DOMContentLoaded', () => {
  const flow = document.querySelector('.setup-flow');
  if (!flow) return;
  const form = document.getElementById('research-config-form');
  const submit = form.querySelector('button[value="preview"]');
  submit.classList.add('setup-check');
  let current = Number(flow.dataset.startStep || 1);
  const mode = form.querySelector('[name="task_mode"]');
  const taskPanels = () => flow.querySelectorAll('[data-task-panel]').forEach(panel => { panel.hidden = panel.dataset.taskPanel !== mode.value; });
  taskPanels(); mode.addEventListener('change', () => { flow.querySelectorAll('[data-setup-missing]').forEach(note => note.remove()); taskPanels(); });
  function show(step, focus = true) {
    current = step; form.hidden = step === 3;
    flow.querySelectorAll('[data-setup-step]').forEach(panel => { panel.hidden = Number(panel.dataset.setupStep) !== step; });
    flow.querySelectorAll('[data-setup-marker]').forEach(marker => {
      const active = Number(marker.dataset.setupMarker) === step;
      marker.classList.toggle('is-current', active);
      marker.classList.toggle('is-complete', Number(marker.dataset.setupMarker) < step);
      if (active) marker.setAttribute('aria-current', 'step'); else marker.removeAttribute('aria-current');
    });
    submit.hidden = step !== 2;
    flow.querySelector('.setup-tools').hidden = step === 3;
    if (focus) flow.querySelector('[data-setup-step="'+step+'"] h2')?.focus();
  }
  flow.querySelectorAll('[data-setup-go]').forEach(button => { button.hidden = false; button.addEventListener('click', () => {
    const target = Number(button.dataset.setupGo);
    if (current === 1 && target === 2) {
      const names = [mode.value === 'text' ? 'task_text' : 'cfg.research.objective', 'cfg.research.public_root', 'cfg.research.root'];
      for (const name of names) {
        const control = form.elements.namedItem(name);
        if (!control.value.trim()) {
          flow.querySelectorAll('[data-setup-missing]').forEach(note => note.remove());
          const note=document.createElement('p'); note.dataset.setupMissing=''; note.className='field-error'; note.setAttribute('role','alert'); note.textContent='请先填写这一项，再继续。'; control.after(note); control.focus();
          control.addEventListener('input', () => note.remove(), {once:true}); return;
        }
      }
    }
    show(target);
  }); });
  const notice = flow.querySelector('[role="alert"]');
  if (notice && current !== 3) {
    const error = notice.textContent;
    const invalid = Array.from(form.querySelectorAll('[data-error-label]')).find(field => field.dataset.invalid || (field.dataset.errorLabel && error.includes(field.dataset.errorLabel)) || (field.dataset.configPath && error.includes(field.dataset.configPath)));
    current = invalid ? Number(invalid.closest('[data-setup-step]').dataset.setupStep) : (/任务|objective|public_root|fresh directory|research.root/.test(error) ? 1 : 2);
    if (invalid) { for (let node=invalid; node && node!==form; node=node.parentElement) if(node.tagName==='DETAILS') node.open=true; }
  }
  show(current, false);
  if (notice) notice.focus(); else if (current === 3) flow.querySelector('[data-setup-step="3"] h2')?.focus();
});
let next = Math.max(0, ...Array.from(document.querySelectorAll('.config-node')).map(node => Number(node.dataset.node)), ...Array.from(document.querySelectorAll('.config-string-list textarea')).map(node => Number(node.name.split('.').pop())));
const update = node => {
  const kind = node.querySelector('.config-kind').value;
  const composite = kind === 'table' || kind === 'array';
  node.querySelector('.config-value').hidden = composite;
  node.querySelector('.config-children').hidden = !composite;
  node.querySelector('.config-add').hidden = !composite;
};
document.querySelectorAll('.config-node').forEach(update);
const invalidate = e => {
  if (!e.target.closest('form[action$="/control/configure"]') || e.target.name === 'save_path') return;
  const create = document.querySelector('form[action$="/control/create"]');
  if (!create) return;
  create.querySelectorAll('button').forEach(button => {button.disabled=true;});
  let note=document.getElementById('config-edited-note');
  if (!note) {note=document.createElement('p');note.id='config-edited-note';e.target.closest('form').after(note);}
  note.textContent='参数已修改，请重新检查并预览。';
};
document.addEventListener('input',invalidate); document.addEventListener('change',invalidate);
document.addEventListener('click', e => { if (e.target.matches('.config-add,.config-remove,.config-string-add,.config-string-remove')) invalidate(e); });
document.addEventListener('change', e => {
  if (!e.target.matches('.config-kind')) return;
  const node = e.target.closest('.config-node');
  node.querySelector('.config-children').replaceChildren(); update(node);
});
document.addEventListener('click', e => {
  if (e.target.matches('.config-string-remove')) { e.target.closest('.config-string-row').remove(); return; }
  if (e.target.matches('.config-string-add')) {
    const path=e.target.dataset.path, container=Array.from(document.querySelectorAll('.config-string-list')).find(item=>item.dataset.path===path);
    const row=document.createElement('div'); row.className='config-string-row';
    const input=document.createElement('textarea'); input.rows=1; input.name='cfg.'+path+'.'+String(++next); row.append(input);
    const button=document.createElement('button'); button.type='button'; button.className='config-string-remove'; button.textContent='删除'; row.append(button);
    container.append(row); document.querySelector('[name="enabled.'+path+'"]').checked=true; return;
  }
  if (e.target.matches('.config-remove')) { e.target.closest('.config-node').remove(); return; }
  if (!e.target.matches('.config-add')) return;
  const group=e.target.closest('details'), enabled=group && group.querySelector('input[type="checkbox"]'); if(enabled) enabled.checked=true;
  const parent = e.target.dataset.parent, id = String(++next), prefix = 'node.'+id+'.';
  const node = document.createElement('div'); node.className = 'config-node'; node.dataset.node = id;
  const hidden = document.createElement('input'); hidden.type = 'hidden'; hidden.name = prefix+'parent'; hidden.value = parent; node.append(hidden);
  const key = document.createElement('input'); key.name = prefix+'key'; key.placeholder = '对象键名（数组项留空）'; node.append(key);
  const kind = document.createElement('select'); kind.name = prefix+'kind'; kind.className = 'config-kind';
  for (const [value,label] of [['string','文本'],['integer','整数'],['number','数字'],['boolean','布尔'],['table','对象'],['array','数组'],['datetime','日期时间'],['date','日期'],['time','时间']]) {
    const option = document.createElement('option'); option.value = value; option.textContent = label; kind.append(option);
  } node.append(kind);
  const label = document.createElement('label'); label.className='config-value'; label.textContent='值 ';
  const value=document.createElement('input'); value.name=prefix+'value'; label.append(value); node.append(label);
  const remove=document.createElement('button'); remove.type='button'; remove.className='config-remove'; remove.textContent='删除此项'; node.append(remove);
  const children=document.createElement('div'); children.className='config-children'; children.dataset.parent=id; node.append(children);
  const add=document.createElement('button'); add.type='button'; add.className='config-add'; add.dataset.parent=id; add.textContent='添加子项'; node.append(add);
  const container=Array.from(document.querySelectorAll('.config-children')).find(item => item.dataset.parent === parent);
  container.append(node); update(node);
});
})();
'''
SCRIPT_CSP = "'sha256-" + base64.b64encode(hashlib.sha256(SCRIPT_SOURCE.encode()).digest()).decode() + "'"


def _options(draft):
    def reject_invalid(value):
        if isinstance(value, _Invalid):
            raise ValueError('参数仍有类型错误，请修改后重新检查')
        if isinstance(value, dict):
            for item in value.values(): reject_invalid(item)
        if isinstance(value, list):
            for item in value: reject_invalid(item)
    reject_invalid(draft['document'])
    for field in FIELDS:
        if field.required and _get(draft['document'], field.path) is None:
            raise ValueError(f'{field.label}：必填')
    if draft['task_mode'] == 'text' and not draft['task_text'].strip():
        raise ValueError('任务原文：必填')
    if draft['task_mode'] == 'file' and not _get(draft['document'], 'research.objective'):
        raise ValueError('已有任务原件路径：必填')
    for field in FIELDS:
        value = _get(draft['document'], field.path)
        if value is not None and field.kind not in ('array', 'table', 'strings'):
            if field.choices and value not in field.choices:
                raise ValueError(f'{field.label}：请选择支持的选项')
            _typed(str(value).lower() if type(value) is bool else str(value), field.kind, field.label)
    return research_config.normalize(research_config.from_document(declaration(draft), base=draft['base']))


def preview(draft):
    return research_config.controller.prepare(**_options(draft), validate_only=True)


def create(draft):
    return research_config.controller.prepare(**_options(draft))


validate = preview
prepare = create
initial_draft = blank


def export_toml(draft):
    """Optional export; inline tables preserve arbitrary nested declaration data."""
    def value(item):
        if isinstance(item, _Invalid): raise ValueError('参数仍有类型错误，请修改后重新保存')
        kind = _kind(item)
        if kind == 'table':
            return '{' + ', '.join(json.dumps(k,ensure_ascii=False)+' = '+value(v) for k,v in item.items()) + '}'
        if kind == 'array': return '['+', '.join(value(v) for v in item)+']'
        if kind == 'string': return json.dumps(item, ensure_ascii=False)
        if kind == 'boolean': return str(item).lower()
        if kind in ('datetime','date','time'): return item.isoformat()
        if kind == 'number' and not math.isfinite(item): raise ValueError('导出需要有限数字')
        return str(item)
    document = declaration(draft)
    # Export uses canonical explicit paths so another save location cannot alter
    # the declaration's meaning. The decoder remains the authority for paths.
    base = Path(draft['base']).expanduser().resolve()
    def path_at(table, key):
        if key in table:
            table[key] = str(research_config._path(table[key], base, key))
    research = document.get('research', {})
    for key in ('root', 'objective', 'public_root'):
        path_at(research, key)
    if 'user_updates' in research:
        research['user_updates'] = [str(research_config._path(v,base,'user_updates')) for v in research['user_updates']]
    for row in research.get('source_restrictions', []):
        path_at(row, 'source')
    agent = document.get('agent', {})
    launcher = agent.get('launcher')
    if launcher and ('/' in launcher[0] or launcher[0].startswith('~')):
        launcher[0] = str(research_config._path(launcher[0],base,'launcher'))
    sandbox = _get(document, 'agent.native.sandbox_workspace_write', {})
    if 'writable_roots' in sandbox:
        sandbox['writable_roots'] = [str(research_config._path(v,base,'writable_roots')) for v in sandbox['writable_roots']]
    adapter = _get(document, 'delivery.adapter', {})
    if isinstance(adapter, dict):
        path_at(adapter, 'adapter')
        if 'source_roots' in adapter:
            adapter['source_roots'] = [str(research_config._path(v,base,'source_roots')) for v in adapter['source_roots']]
        argv = adapter.get('launcher_argv')
        if argv and '/' in argv[0]:
            argv[0] = str(research_config._path(argv[0],base,'launcher_argv'))
    path_at(document.get('ui', {}), 'approval_secret_file')
    path_at(_get(document, 'executor.config', {}), 'config_file')
    return '\n'.join(json.dumps(k,ensure_ascii=False)+' = '+value(v) for k,v in document.items())+'\n'
