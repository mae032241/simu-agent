"""Safe previews and on-demand original reading; never interprets Agent HTML."""
from __future__ import annotations

import html
from io import BytesIO
import json
import warnings
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000


def preview_type(raw: bytes, media_type: str) -> str | None:
    """Require registered type, actual format, bounded dimensions and valid bytes."""
    declared = media_type.split(";", 1)[0].strip().lower()
    expected = {"image/png": "PNG", "image/jpeg": "JPEG"}.get(declared)
    if expected is None or len(raw) > MAX_IMAGE_BYTES:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as picture:
                if (picture.format != expected or picture.width * picture.height > MAX_IMAGE_PIXELS
                        or max(picture.size) > 8192 or getattr(picture, "n_frames", 1) != 1):
                    return None
                picture.verify()
            with Image.open(BytesIO(raw)) as picture:
                picture.load()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        return None
    return declared


def query_url(url: str, **values) -> str:
    parsed = urlsplit(url)
    current = dict(parse_qsl(parsed.query, keep_blank_values=True))
    current.update({key: str(value) for key, value in values.items() if value is not None})
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(current), ""))


def render_evidence(view: dict, *, href: str, instance_id: str | None = None, parent_href: str | None = None) -> bytes:
    from .navigation import navigation
    from .presentation_render import safe_local_href
    escape = html.escape
    source = view.get("source", {})
    pointer = source.get("json_pointer", "")
    state = view.get("payload_state", "unknown")
    if state == "available":
        body = "<pre class='json-tree'>" + escape(json.dumps(view.get("payload"), ensure_ascii=False, indent=2)) + "</pre>"
    elif state == "navigation":
        rows = []
        for item in view["navigation"]["items"]:
            path = item.get("json_pointer")
            if path is None:
                rows.append("<li>字段定位过长，请下载原件。</li>")
                continue
            link = query_url(href, pointer=path, child_after=0)
            rows.append(f"<li><a href='{escape(link, quote=True)}'>{escape(path)}</a></li>")
        after = view["navigation"].get("next_after")
        more = (f"<a href='{escape(query_url(href, pointer=pointer, child_after=after), quote=True)}'>下一页字段</a>"
                if after is not None else "")
        body = "<p>原文较大，按字段阅读或下载完整原件。</p><ul>" + "".join(rows) + "</ul>" + more
    else:
        body = f"<p>当前预览状态：{escape(str(state))}。可下载已登记原件；未提供或损坏的原件不会被替代。</p>"
    gaps = "".join(f"<li>{escape(json.dumps(item, ensure_ascii=False))}</li>" for item in view.get("gaps", []))
    parent = safe_local_href(parent_href)
    back = f"<p><a href='{escape(parent, quote=True)}'>返回原审批</a></p>" if parent else ""
    return ("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>来源原文</title><link rel='stylesheet' href='/static/style.css'></head>"
            "<body>" + navigation(instance_id) + "<main class='page'>" + back + "<h1>来源原文</h1>"
            f"<p>{escape(str(view.get('schema_id', '')))}</p><p>精确位置：<code>{escape(pointer or '/ (原件根)')}</code></p>"
            f"<a href='{escape(query_url(href, format='download'), quote=True)}'>下载完整原件</a>"
            f"{body}<ul>{gaps}</ul></main></body></html>").encode("utf-8")


def render_parameter_page(presentation, *, href, instance_id, evidence_href, parent_href=None):
    from .navigation import navigation
    from .presentation_render import render_parameter_table, render_json_value, safe_local_href
    page = presentation["parameter_page"]
    after, total = page.get("after", 0), page.get("total")
    rows = presentation.get("parameters", [])
    count = (f"本页 {after + 1 if rows else 0}–{after + len(rows) if rows else 0} 条，共 {total} 条"
             if total is not None else "完整条数暂不可得；请查看原件与读取说明")
    links = []
    for label, offset in (("上一页参数", max(0, after - 8) if after else None), ("下一页参数", page.get("next_after"))):
        if offset is not None:
            links.append("<a href='" + html.escape(query_url(href, after=offset), quote=True) + "'>" + label + "</a>")
    original = query_url(href, view="original", pointer="", child_after=0)
    back = ("<a href='" + html.escape(parent_href, quote=True) + "'>返回原审批</a>" if safe_local_href(parent_href) else "")
    return ("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'><title>原件参数</title>"
        "<link rel='stylesheet' href='/static/style.css'></head><body>" + navigation(instance_id)
        + "<main class='page parameter-page'><h1>原件参数</h1><p>" + html.escape(count) + "</p>"
        + "<p>按原记录顺序展示，保留每个案例与原字段位置。设计取值不等同于文献实测依据。</p>"
        + "<nav class='parameter-pagination'>" + back + " ".join(links)
        + " <a href='" + html.escape(original, quote=True) + "'>查看原件</a></nav>"
        + render_parameter_table(rows, evidence_href)
        + ("<details><summary>资料读取说明</summary>" + render_json_value(presentation["gaps"]) + "</details>" if presentation.get("gaps") else "")
        + "</main></body></html>").encode("utf-8")
