"""Pure presentation values over an already authorized immutable cohort.

No UI loading, HTML, filesystem access, or artifact discovery occurs here. The
control UI validates every returned source and applies aggregate output bounds.
"""
from collections.abc import Mapping
import json
import math
import re
from urllib.parse import parse_qsl, urlsplit

MAX_VALUE_BYTES = 16 * 1024
PRESENTATION_COLLECTIONS = ("sections", "parameters", "figures", "gaps")
__all__ = ['plain', 'json_size', 'safe_value', 'pointer', 'source', 'items', 'empty', 'add_gap', 'add_fields', 'MAX_VALUE_BYTES', 'PRESENTATION_COLLECTIONS']


def plain(value, *, depth=0):
    """Copy JSON values without accepting arbitrary Python object protocols."""
    if depth > 64:
        raise ValueError("presentation JSON nesting is too deep")
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("presentation object keys must be text")
        return {key: plain(item, depth=depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item, depth=depth + 1) for item in value]
    raise ValueError("presentation accepts only JSON values")


def json_size(value):
    return len(json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8"))


def safe_value(value):
    value = plain(value)
    return value if json_size(value) <= MAX_VALUE_BYTES else {"display_state": "too_large", "message": "内容较长，请按来源查看完整原文"}


def pointer(*parts):
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def source(artifact, path=""):
    base = artifact.get("source", {}).get("json_pointer", "")
    return {"artifact_id": artifact["artifact_id"], "json_pointer": base + path}


def items(value):
    return tuple(value) if isinstance(value, (list, tuple)) else ()


def empty():
    return {key: [] for key in PRESENTATION_COLLECTIONS}


def add_gap(result, code, artifact=None, path="", **details):
    if len(result["gaps"]) < 64:
        result["gaps"].append({"code": code, **({"source": source(artifact, path)} if artifact else {}), **details})


def add_fields(result, artifact, title, fields, *, payload=None, path="", kind=None):
    payload = artifact.get("payload") if payload is None else payload
    if not isinstance(payload, Mapping):
        return
    values = [{"label": label, "value": safe_value(payload[key]), "source": source(artifact, path + pointer(key))}
              for key, label in fields if key in payload]
    if values and len(result["sections"]) < 64:
        result["sections"].append({"title": title, "items": values, **({"kind": kind} if kind else {})})


MISSING = "未记录"
NO_UNCERTAINTY = "未提供估计"
NO_SOURCE = "原记录未声明科学分类"

def value_at(value, path):
    if path == "":
        return value
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("invalid presentation pointer")
    for token in path[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", token):
            raise ValueError("invalid pointer escape")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping):
            value = value[token]
        elif isinstance(value, (list, tuple)) and token.isascii() and token.isdecimal() and (token == "0" or not token.startswith("0")):
            value = value[int(token)]
        else:
            raise KeyError(token)
    return value


def parameter(artifact, path, *, name, selected_value, unit=MISSING, conditions=MISSING,
              case_scope=MISSING, epistemic_status=NO_SOURCE, uncertainty=NO_UNCERTAINTY,
              rationale=MISSING, reported_values=(), sources=(), field_sources=None,
              record_type="原参数记录", source_status=None):
    acquisition = "、".join(dict.fromkeys(item["acquisition"] for item in sources if item.get("acquisition"))) or "本记录取值；外部取得方式未声明"
    source_status = source_status or ("已连接原记录出处" if sources else "该原记录未直接列出出处")
    return {"name": safe_value(name), "selected_value": safe_value(selected_value),
            "reported_values": safe_value(reported_values), "unit": safe_value(unit),
            "conditions": safe_value(conditions), "case_scope": safe_value(case_scope),
            "epistemic_status": safe_value(epistemic_status), "acquisition": acquisition,
            "uncertainty": safe_value(uncertainty), "rationale": safe_value(rationale),
            "sources": list(sources), "source": source(artifact, path),
            "field_sources": field_sources or {}, "record_type": record_type, "source_status": source_status}


def dependency_cohort(artifact, cohort):
    """Saved parent ancestry, excluding unrelated roots and superseded versions."""
    by_id = {item["artifact_id"]: item for item in cohort}
    found, pending = {}, [artifact]
    while pending:
        current = pending.pop()
        identity = current["artifact_id"]
        if identity in found:
            continue
        found[identity] = current
        for ref in current.get("provenance", ()):
            parent = by_id.get(ref.get("artifact_id"))
            if parent is not None:
                pending.append(parent)
    return tuple(found.values())


def dependency_complete(artifact, cohort):
    dependencies = dependency_cohort(artifact, cohort)
    known = {item["artifact_id"] for item in dependencies}
    return all(item.get("parent_count", len(item.get("provenance", ()))) == len(item.get("provenance", ()))
               and all(ref.get("artifact_id") in known for ref in item.get("provenance", ())) for item in dependencies)


class ParameterPageRows(list):
    """Count the bounded original's rows, retaining only the requested window."""
    def __init__(self, after, limit):
        super().__init__()
        self.after, self.limit, self.total = after, limit, 0

    def append(self, row):
        if self.after <= self.total < self.after + self.limit:
            super().append(row)
        self.total += 1


def safe_url(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            return None
        if any(key.lower() in {"token", "capability", "access_token", "csrf_token"} for key, _ in parse_qsl(parsed.query.replace(";", "&"))):
            return None
    except ValueError:
        return None
    return value


def citation(artifact, path, entry, *, locator=None):
    network = entry.get("source_type") == "web_snapshot"
    return {"title": safe_value(entry.get("title", MISSING)),
            "locator": safe_value(entry.get("locator", MISSING) if locator is None else locator),
            "url": safe_url(entry.get("final_url") or entry.get("original_url")),
            "original_url": safe_url(entry.get("original_url")),
            "accessed_at": entry.get("accessed_at") if network else None,
            "acquisition": {"web_snapshot": "网络检索", "frozen_input": "冻结输入材料",
                "user_statement": "用户陈述", "runtime_output": "运行记录"}.get(entry.get("source_type"),
                    "原记录取得类型：" + str(entry.get("source_type")) if entry.get("source_type") else "取得方式未声明"),
            "doi": safe_value(entry.get("doi")), "authors": safe_value(entry.get("authors", ())),
            "publication_year": entry.get("publication_year"), "source": source(artifact, path)}


__all__ += ['value_at', 'parameter', 'dependency_cohort', 'dependency_complete', 'ParameterPageRows', 'safe_url', 'citation', 'MISSING', 'NO_UNCERTAINTY', 'NO_SOURCE']
