"""Human-readable execution settings; never dispatches or approves research."""
from html import escape
from typing import get_args
from urllib.parse import quote

from ...agent_execution_settings import Language, ReasoningEffort, parse_settings, resolve_settings
from .navigation import hidden, navigation

LABELS = {"narrative_language": "科学报告语言", "model": "模型", "reasoning_effort": "推理强度",
          "max_attempts": "恢复链最多 Run 数（包含首轮）"}
SOURCES = {"operation_default": "任务原有默认", "compatibility_default": "兼容默认",
           "global.defaults": "公共默认", "global.operation": "公共任务覆盖",
           "instance.defaults": "实例默认", "instance.operation": "实例任务覆盖"}


def agent_operations(catalog):
    return {name: catalog.operation(name) for name in catalog.operation_ids()
            if catalog.operation(name).spec.executor.kind == "agent"}


def apply_form(current, form, catalog):
    def one(name):
        values = form.get(name, [""])
        if len(values) != 1:
            raise ValueError(f"{name}: repeated setting field")
        return values[0]
    if one("settings_action") == "reset":
        return {}
    if one("settings_action") != "save":
        raise ValueError("invalid settings action")
    result = parse_settings(current).sparse()
    operation = one("operation_id")
    if operation and operation not in agent_operations(catalog):
        raise ValueError("所选任务当前未安装；已有覆盖保留但不生效。")
    for prefix, keys in (("default", LABELS), ("operation", ("model", "reasoning_effort", "max_attempts"))):
        if prefix == "operation" and not operation:
            continue
        values = {}
        for key in keys:
            value = one(prefix + "_" + key).strip()
            if value:
                try:
                    values[key] = int(value) if key == "max_attempts" else value
                except ValueError as error:
                    raise ValueError(f"{LABELS[key]}：需要正整数。") from error
        if prefix == "default":
            result["defaults"] = values
        else:
            operations = result.setdefault("operations", {})
            if values:
                operations[operation] = values
            else:
                operations.pop(operation, None)
    return parse_settings(result).sparse()


def _field(prefix, key, override, effective, source, *, writable):
    name = prefix + "_" + key
    value = str(override.get(key, ""))
    disabled = "" if writable else " disabled"
    attrs = f"name='{name}' data-setting-label='{escape(LABELS[key])}' data-original='{escape(value, quote=True)}'{disabled}"
    if key in {"reasoning_effort", "narrative_language"}:
        options = get_args(ReasoningEffort if key == "reasoning_effort" else Language)
        choices = ["<option value=''>继承默认</option>"]
        for option in options:
            label = {"zh-CN": "简体中文", "en": "English"}.get(option, option)
            choices.append(f"<option value='{option}'{' selected' if option == value else ''}>{label}</option>")
        control = f"<select {attrs}>" + "".join(choices) + "</select>"
    else:
        kind = "number" if key == "max_attempts" else "text"
        limits = " min='1' step='1'" if kind == "number" else " maxlength='256'"
        control = f"<input type='{kind}' {attrs} value='{escape(value, quote=True)}' placeholder='留空继承'{limits}>"
    return (f"<label class='agent-setting-field'><span>{LABELS[key]}</span>{control}"
            f"<small>当前有效：{escape(str(effective))} · {escape(SOURCES.get(source, source))}</small></label>")


def render_settings(instance, record, *, catalog, global_settings, csrf, writable, selected="", standalone=False, readonly_reason="当前没有设置修改权限。"):
    operations = agent_operations(catalog)
    if selected and selected not in operations:
        raise ValueError("所选任务当前未安装。")
    settings = parse_settings(record["settings"])
    base = "/instance/" + quote(instance.instance_id, safe="")
    operation = operations.get(selected)
    effective = resolve_settings(global_settings, settings, operation_id=selected,
        operation_model=operation.spec.executor.model if operation else "按任务默认",
        operation_max_attempts=operation.spec.limits.max_attempts if operation else 1)
    values = {**effective["profile"].model_dump(), "max_attempts": effective["max_attempts"]}
    if not selected and effective["sources"]["max_attempts"] == "operation_default":
        values["max_attempts"] = "按任务默认"
    body = ("<section class='workbench-section agent-settings'><h2>Agent 设置</h2>"
            "<p>仅影响后续任务；正在运行与已完成的任务保留原配置。公共配置文件在服务重启时加载，实例覆盖保存后供新预检使用。</p>"
            "<p>留空表示继承。模型和推理强度是请求配置，平台实际生效需有运行观测；不会生成新角色。语言只约束新报告，历史原文保留。</p>")
    body += (f"<form method='get' action='{base}/settings'><details{' open' if selected else ''}><summary>按任务类型查看与覆盖</summary>"
             "<label>任务类型<select name='operation'><option value=''>实例统一默认</option>")
    for name, compiled in operations.items():
        body += f"<option value='{escape(name, quote=True)}'{' selected' if name == selected else ''}>{escape(name)} — {escape(compiled.spec.description.purpose)}</option>"
    body += "</select></label><button type='submit'>查看该任务</button></details></form>"
    body += (f"<form class='agent-settings-form' method='post' action='{base}/manage/agent-settings'>"
             + hidden("csrf_token", csrf) + hidden("expected_revision", str(record["revision"]))
             + hidden("operation_id", selected) + "<h3>实例默认覆盖</h3><div class='agent-settings-grid'>")
    defaults = settings.defaults.model_dump(exclude_none=True)
    # The default panel shows defaults, not a selected Operation's higher-priority overrides.
    default_effective = resolve_settings(global_settings, settings, operation_id="",
        operation_model="按任务默认", operation_max_attempts=1)
    default_values = {**default_effective["profile"].model_dump(), "max_attempts": default_effective["max_attempts"]}
    if default_effective["sources"]["max_attempts"] == "operation_default":
        default_values["max_attempts"] = "按任务默认"
    for key in LABELS:
        body += _field("default", key, defaults, default_values[key], default_effective["sources"][key], writable=writable)
    body += "</div>"
    if selected:
        override = settings.operations.get(selected)
        body += f"<h3>{escape(selected)}</h3><div class='agent-settings-grid'>"
        for key in ("model", "reasoning_effort", "max_attempts"):
            body += _field("operation", key, override.model_dump(exclude_none=True) if override else {},
                           values[key], effective["sources"][key], writable=writable)
        body += "</div>"
    inactive = (set(settings.operations) | set(global_settings.operations)) - set(operations)
    if inactive:
        body += "<p class='source-gap'>以下已保存任务覆盖因插件未安装而暂不生效，仍保留：" + escape("、".join(sorted(inactive))) + "</p>"
    if writable:
        body += ("<div class='agent-settings-preview' aria-live='polite'><h3>本次变更</h3><p data-settings-preview>尚无修改。</p></div>"
                 "<button name='settings_action' value='save'>保存后续任务设置</button> "
                 "<button name='settings_action' value='reset'>清除本实例全部覆盖，恢复继承</button>")
    else:
        body += "<p class='source-gap'>当前仅可查看设置。" + escape(readonly_reason) + "</p><a href='/instances/manage'>返回实例管理</a>"
    body += "</form></section>"
    script = "<script defer src='/static/agent-settings.js'></script>"
    if standalone:
        body = ("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<link rel='stylesheet' href='/static/style.css'><title>Agent 设置</title></head><body>"
                + navigation(instance.instance_id) + "<main class='workbench-page'><h1>" + escape(instance.title) + "</h1>" + body + "</main>" + script + "</body></html>")
    else:
        body += script
    return body
