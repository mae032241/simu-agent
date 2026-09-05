"""Minimal loopback HTTP server for direct human decisions."""

from __future__ import annotations

import html
import ipaddress
import logging
import secrets
import socket
import threading
from contextlib import nullcontext
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..schema.approval import LocalIdentityRef
from ..service.approvals import (
    ApprovalAccessDenied,
    ApprovalError,
    ApprovalExpired,
    ApprovalService,
)
from ..service.scheduler_bindings import (
    SchedulerBindingError,
    SchedulerBindingService,
    SchedulerInstanceNotFound,
)
from ..service.instance_management import (
    InstanceManagementCapabilityError,
    verify_instance_management_capability,
)
from ..service.maintenance import StateMaintenanceLock
from ..storage import CASIntegrityError
from .render import ReviewContext, render_review


MAX_POST_BYTES = 64 * 1024
STATIC_ROOT = Path(__file__).with_name("static")
LOGGER = logging.getLogger(__name__)
_RETIRED_INSTANCE_APPROVAL_KINDS = (
    "instance_creation",
    "research_instance_registration",
    "session_binding",
    "research_session_binding",
)


class ApprovalUI:
    def __init__(
        self,
        service: ApprovalService,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        local_identity: LocalIdentityRef | None = None,
        bindings: SchedulerBindingService | None = None,
        instance_management_secret: bytes | None = None,
        maintenance: StateMaintenanceLock | None = None,
    ) -> None:
        try:
            address = ipaddress.ip_address(host)
        except ValueError as error:
            raise ValueError("approval UI host must be a literal loopback address") from error
        if not address.is_loopback:
            raise ValueError("approval UI may only bind a loopback address")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("approval UI port is invalid")
        self.service = service
        self.host = host
        self.port = port
        self.identity = local_identity or LocalIdentityRef(
            identity_id="local_user",
            display_name="Local user",
        )
        self.bindings = bindings
        self.instance_management_secret = instance_management_secret
        self.maintenance = maintenance
        self.session_id = f"ui_{secrets.token_hex(16)}"
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("approval UI is not running")
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self._server.server_port}"

    def start(self) -> str:
        if self._server is not None:
            return self.base_url
        ui = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                with ui._shared_maintenance():
                    ui._handle_get(self)

            def do_POST(self) -> None:
                ui._handle_post(self)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        server_type = ThreadingHTTPServer
        if ":" in self.host:
            class IPv6HTTPServer(ThreadingHTTPServer):
                address_family = socket.AF_INET6

            server_type = IPv6HTTPServer
        self._server = server_type((self.host, self.port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="artifact-approval-ui",
            daemon=True,
        )
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def _handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        if not self._valid_host(handler):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        parsed = urlparse(handler.path)
        if parsed.path == "/static/style.css":
            return self._static(handler, "style.css", "text/css; charset=utf-8")
        if parsed.path == "/static/app.js":
            return self._static(handler, "app.js", "text/javascript; charset=utf-8")
        if parsed.path == "/":
            instances = self.bindings.list_instances() if self.bindings is not None else ()
            return self._respond(
                handler,
                HTTPStatus.OK,
                _render_dashboard(
                    self.service.list_requests(
                        status="pending",
                        limit=100,
                        excluded_kinds=_RETIRED_INSTANCE_APPROVAL_KINDS,
                    ),
                    context_for=self._review_context,
                    instances=instances,
                    csrf_token=self.session_id,
                ),
                "text/html; charset=utf-8",
            )
        parts = [part for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query, strict_parsing=True)
        token = _one(query, "token")
        try:
            if parsed.path == "/instances":
                capability_token = _one(query, "capability")
                capability = self._instance_capability(capability_token)
                return self._respond(
                    handler,
                    HTTPStatus.OK,
                    _render_instance_management(
                        capability_token=capability_token or "",
                        expires_at=capability.expires_at,
                        csrf_token=self.session_id,
                        instances=(
                            self.bindings.list_instances(state="active")
                            if self.bindings is not None
                            else ()
                        ),
                    ),
                    "text/html; charset=utf-8",
                )
            if len(parts) == 2 and parts[0] == "instance":
                if self.bindings is None:
                    return self._error(handler, HTTPStatus.NOT_FOUND)
                instance = self.bindings.get_instance(instance_id=parts[1])
                approval_ids = self.bindings.instance_history_approval_ids(
                    instance=instance.instance_id
                )
                history = []
                for approval_id in approval_ids:
                    try:
                        history.append(self.service.request_summary(approval_id))
                    except ApprovalError:
                        continue
                history.sort(key=lambda item: item.created_at, reverse=True)
                return self._respond(
                    handler,
                    HTTPStatus.OK,
                    _render_instance_page(instance, tuple(history)),
                    "text/html; charset=utf-8",
                )
            if len(parts) == 2 and parts[0] == "review" and token:
                review = self.service.review(parts[1], access_token=token)
                return self._respond(
                    handler,
                    HTTPStatus.OK,
                    render_review(
                        review,
                        access_token=token,
                        identity=self.identity,
                        context=self._review_context(parts[1]),
                        read_only=(
                            review.request.kind
                            in _RETIRED_INSTANCE_APPROVAL_KINDS
                        ),
                    ),
                    "text/html; charset=utf-8",
                )
            if len(parts) == 2 and parts[0] == "history" and token:
                review = self.service.review(parts[1], access_token=token)
                if review.status == "pending":
                    return self._error(handler, HTTPStatus.NOT_FOUND)
                return self._respond(
                    handler,
                    HTTPStatus.OK,
                    render_review(
                        review,
                        access_token=token,
                        identity=self.identity,
                        context=self._review_context(parts[1]),
                        read_only=(
                            review.request.kind
                            in _RETIRED_INSTANCE_APPROVAL_KINDS
                        ),
                    ),
                    "text/html; charset=utf-8",
                )
            if len(parts) == 3 and parts[0] == "subject" and token:
                review = self.service.review(parts[1], access_token=token)
                index = int(parts[2])
                if not 0 <= index < len(review.subjects):
                    raise IndexError("approval subject index is out of range")
                _, content = review.subjects[index]
                return self._respond(
                    handler,
                    HTTPStatus.OK,
                    content,
                    "application/octet-stream",
                    extra_headers={
                        "Content-Disposition": f"attachment; filename=subject-{index}.bin"
                    },
                )
        except (
            ApprovalAccessDenied,
            InstanceManagementCapabilityError,
            ValueError,
            IndexError,
        ):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        except SchedulerInstanceNotFound:
            return self._error(handler, HTTPStatus.NOT_FOUND)
        except ApprovalExpired:
            return self._error(handler, HTTPStatus.GONE)
        except (ApprovalError, CASIntegrityError):
            return self._error(handler, HTTPStatus.CONFLICT)
        self._error(handler, HTTPStatus.NOT_FOUND)

    def _review_context(self, approval_id: str) -> ReviewContext | None:
        if self.bindings is None:
            return None
        try:
            owner = self.bindings.find_owner(
                namespace="approval", object_id=approval_id
            )
        except SchedulerBindingError:
            return None
        if owner is None:
            return None
        instance, binding = owner
        return ReviewContext(
            instance_name=instance.name,
            instance_title=instance.title,
            instance_objective=instance.objective,
            approval_name=binding.name,
            approval_logical_name=binding.logical_name,
            approval_revision=binding.revision,
        )

    def _handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        if not self._valid_host(handler):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        parsed = urlparse(handler.path)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 2 and parts[0] == "instances" and parts[1] in {
            "create",
            "select",
        }:
            return self._handle_instance_post(handler, action=parts[1])
        if len(parts) == 3 and parts[0] == "review" and parts[2] == "refresh-access":
            return self._handle_access_refresh(handler, approval_id=parts[1])
        if len(parts) != 3 or parts[0] != "review" or parts[2] != "decision":
            return self._error(handler, HTTPStatus.NOT_FOUND)
        with self._shared_maintenance():
            origin = handler.headers.get("Origin")
            if not self._valid_origin(origin):
                return self._error(handler, HTTPStatus.FORBIDDEN)
            if handler.headers.get("Content-Type", "").split(";", 1)[0] != "application/x-www-form-urlencoded":
                return self._error(handler, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            try:
                length = int(handler.headers.get("Content-Length", "-1"))
            except ValueError:
                return self._error(handler, HTTPStatus.BAD_REQUEST)
            if not 0 <= length <= MAX_POST_BYTES:
                return self._error(handler, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            try:
                form = parse_qs(
                    handler.rfile.read(length).decode("utf-8", errors="strict"),
                    strict_parsing=True,
                    keep_blank_values=True,
                )
                token = _required(form, "token")
                csrf = _required(form, "csrf")
                nonce = _required(form, "nonce")
                selected = _required(form, "selected_option")
                rationale = _required(form, "rationale", allow_blank=True)
                if _required(form, "confirm") != "confirm":
                    raise ValueError("confirmation mismatch")
                review = self.service.review(parts[1], access_token=token)
                if review.request.kind in _RETIRED_INSTANCE_APPROVAL_KINDS:
                    return self._error(
                        handler,
                        HTTPStatus.CONFLICT,
                        "该实例管理审批已经停用，只能读取历史内容。",
                    )
                decision_ref = self.service.record_ui_decision(
                    approval_id=parts[1],
                    access_token=token,
                    csrf_token=csrf,
                    decision_nonce=nonce,
                    selected_option=selected,
                    rationale=rationale,
                    decided_by=self.identity,
                    ui_session_id=self.session_id,
                )
            except (UnicodeDecodeError, ValueError, ApprovalAccessDenied):
                return self._error(handler, HTTPStatus.FORBIDDEN)
            except ApprovalExpired:
                return self._error(handler, HTTPStatus.GONE)
            except (ApprovalError, CASIntegrityError):
                return self._error(handler, HTTPStatus.CONFLICT)
        location = f"/review/{parts[1]}?token={token}"
        self._respond(
            handler,
            HTTPStatus.SEE_OTHER,
            b"",
            "text/plain; charset=utf-8",
            extra_headers={
                "Location": location,
                "X-Decision-Artifact": decision_ref.artifact_id,
            },
        )

    def _handle_instance_post(
        self, handler: BaseHTTPRequestHandler, *, action: str
    ) -> None:
        if not self._valid_host(handler):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        if self.bindings is None:
            return self._error(handler, HTTPStatus.NOT_FOUND)
        origin = handler.headers.get("Origin")
        if not self._valid_origin(origin):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        if (
            handler.headers.get("Content-Type", "").split(";", 1)[0]
            != "application/x-www-form-urlencoded"
        ):
            return self._error(handler, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        try:
            length = int(handler.headers.get("Content-Length", "-1"))
        except ValueError:
            return self._error(handler, HTTPStatus.BAD_REQUEST)
        if not 0 <= length <= MAX_POST_BYTES:
            return self._error(handler, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            form = parse_qs(
                handler.rfile.read(length).decode("utf-8", errors="strict"),
                strict_parsing=True,
                keep_blank_values=True,
            )
            capability_token = _required(form, "capability")
            capability = self._instance_capability(capability_token)
            if not secrets.compare_digest(
                _required(form, "csrf"), self.session_id
            ):
                raise ValueError("CSRF mismatch")
            name = _required(form, "name")
            with self._shared_maintenance():
                if action == "create":
                    instance = self.bindings.create_instance_and_bind_session(
                        session_key=capability.session_key,
                        name=name,
                        title=_required(form, "title"),
                        objective=_required(form, "objective"),
                    )
                else:
                    instance = self.bindings.bind_session_by_name(
                        session_key=capability.session_key,
                        name=name,
                    )
        except (
            UnicodeDecodeError,
            InstanceManagementCapabilityError,
            ValueError,
        ):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        except SchedulerInstanceNotFound:
            return self._error(handler, HTTPStatus.NOT_FOUND)
        except SchedulerBindingError as error:
            return self._error(handler, HTTPStatus.CONFLICT, str(error))
        self._respond(
            handler,
            HTTPStatus.SEE_OTHER,
            b"",
            "text/plain; charset=utf-8",
            extra_headers={"Location": f"/instance/{instance.instance_id}"},
        )

    def _handle_access_refresh(
        self, handler: BaseHTTPRequestHandler, *, approval_id: str
    ) -> None:
        origin = handler.headers.get("Origin")
        if not self._valid_origin(origin):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        if (
            handler.headers.get("Content-Type", "").split(";", 1)[0]
            != "application/x-www-form-urlencoded"
        ):
            return self._error(handler, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        try:
            length = int(handler.headers.get("Content-Length", "-1"))
        except ValueError:
            return self._error(handler, HTTPStatus.BAD_REQUEST)
        if not 0 <= length <= MAX_POST_BYTES:
            return self._error(handler, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            form = parse_qs(
                handler.rfile.read(length).decode("utf-8", errors="strict"),
                strict_parsing=True,
            )
            if not secrets.compare_digest(
                _required(form, "csrf"), self.session_id
            ):
                raise ValueError("CSRF mismatch")
            with self._shared_maintenance():
                launch = self.service.refresh_access(approval_id)
        except (UnicodeDecodeError, ValueError, ApprovalAccessDenied):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        except ApprovalExpired:
            return self._error(handler, HTTPStatus.GONE)
        except ApprovalError:
            return self._error(handler, HTTPStatus.CONFLICT)
        self._respond(
            handler,
            HTTPStatus.SEE_OTHER,
            b"",
            "text/plain; charset=utf-8",
            extra_headers={"Location": launch.review_path},
        )

    def _instance_capability(self, token: str | None):
        if self.instance_management_secret is None or token is None:
            raise InstanceManagementCapabilityError(
                "instance-management capability is unavailable"
            )
        return verify_instance_management_capability(
            token,
            secret=self.instance_management_secret,
        )

    def _shared_maintenance(self):
        return (
            self.maintenance.shared()
            if self.maintenance is not None
            else nullcontext()
        )

    def _valid_host(self, handler: BaseHTTPRequestHandler) -> bool:
        return self._valid_loopback_authority(handler.headers.get("Host"))

    def _valid_origin(self, origin: str | None) -> bool:
        if origin is None:
            return False
        try:
            parsed = urlparse(origin)
            if (
                parsed.scheme != "http"
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in ("", "/")
                or parsed.params
                or parsed.query
                or parsed.fragment
            ):
                return False
        except ValueError:
            return False
        return self._valid_loopback_authority(parsed.netloc)

    def _valid_loopback_authority(self, authority: str | None) -> bool:
        if authority is None or self._server is None:
            return False
        try:
            parsed = urlparse(f"//{authority}")
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            return False
        if (
            hostname is None
            or port != self._server.server_port
            or parsed.username is not None
            or parsed.password is not None
        ):
            return False
        if hostname.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            return False

    def _static(
        self,
        handler: BaseHTTPRequestHandler,
        name: str,
        content_type: str,
    ) -> None:
        self._respond(handler, HTTPStatus.OK, (STATIC_ROOT / name).read_bytes(), content_type)

    def _error(
        self,
        handler: BaseHTTPRequestHandler,
        status: HTTPStatus,
        message: str | None = None,
    ) -> None:
        body = f"{status.value} {status.phrase}"
        if message is not None and message.strip():
            body += "\n" + message.strip()
        self._respond(
            handler,
            status,
            (body + "\n").encode("utf-8"),
            "text/plain; charset=utf-8",
        )

    def _respond(
        self,
        handler: BaseHTTPRequestHandler,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        handler.send_response(status)
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
            "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            "X-Frame-Options": "DENY",
            # Chrome serializes form POST Origin as "null" under no-referrer,
            # which makes the same-origin decision form fail our Origin gate.
            "Referrer-Policy": "same-origin",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        }
        if extra_headers:
            headers.update(extra_headers)
        for name, value in headers.items():
            handler.send_header(name, value)
        handler.end_headers()
        handler.wfile.write(body)


def _render_dashboard(
    items: tuple[object, ...],
    *,
    context_for,
    instances: tuple[object, ...] = (),
    csrf_token: str,
) -> bytes:
    rows = []
    for item in items:
        review_path = getattr(item, "review_path", None)
        access_expired = bool(getattr(item, "access_expired", False))
        if review_path is None and not access_expired:
            continue
        kind_value = str(getattr(item, "kind", "review"))
        kind = html.escape(
            {
                "scientific_foundation": "科学基础审批",
                "execution_authorization": "执行授权审批",
                "review": "科研审批",
            }.get(kind_value, kind_value)
        )
        question = html.escape(str(getattr(item, "question", "待审批事项")))
        created_at = html.escape(str(getattr(item, "created_at", "")))
        href = html.escape(str(review_path), quote=True)
        approval_id = html.escape(
            str(getattr(item, "approval_id", "")), quote=True
        )
        context = context_for(str(getattr(item, "approval_id", "")))
        if context is None:
            instance = (
                "<div class='approval-instance approval-instance-unbound'>"
                "<span>未绑定研究实例</span></div>"
            )
            approval_name = "旧审批"
        else:
            instance = (
                "<div class='approval-instance'>"
                "<span class='approval-instance-label'>研究实例</span>"
                f"<strong>{html.escape(context.instance_title)}</strong>"
                f"<code>{html.escape(context.instance_name)}</code></div>"
            )
            approval_name = context.approval_name
        summary = (
            f"{instance}"
            "<div class='approval-summary'>"
            f"<h2>{question}</h2>"
            "<p>"
            f"<span class='approval-kind'>{kind}</span>"
            f"<span>审批项：<code>{html.escape(approval_name)}</code></span>"
            f"<time>{created_at}</time></p></div>"
        )
        if access_expired:
            csrf = html.escape(csrf_token, quote=True)
            action = f"/review/{approval_id}/refresh-access"
            rows.append(
                "<li class='approval-item'>"
                f"<div>{summary}</div>"
                f"<form method='post' action='{action}'>"
                f"<input type='hidden' name='csrf' value='{csrf}'>"
                "<button type='submit'>刷新访问链接</button></form></li>"
            )
        else:
            rows.append(
                "<li class=\"approval-item\">"
                f"<a href=\"{href}\">{summary}"
                "<span class='approval-open' aria-hidden='true'>查看</span>"
                "</a></li>"
            )
    content = (
        "<ul class=\"approval-list\">" + "".join(rows) + "</ul>"
        if rows
        else "<p class=\"empty-state\">当前没有待审批事项。</p>"
    )
    instance_rows = []
    for instance in instances:
        instance_id = html.escape(str(getattr(instance, "instance_id", "")), quote=True)
        name = html.escape(str(getattr(instance, "name", "")))
        title = html.escape(str(getattr(instance, "title", "")))
        state_value = str(getattr(instance, "state", ""))
        state = html.escape(
            {
                "active": "进行中",
                "deleting": "删除恢复中",
                "proposed": "待创建",
                "binding": "待绑定",
            }.get(
                state_value, state_value
            )
        )
        created_at = html.escape(str(getattr(instance, "created_at", "")))
        instance_rows.append(
            "<li class='instance-item'><a href='/instance/"
            f"{instance_id}'><div><strong>{title}</strong><code>{name}</code>"
            f"<p><span>{state}</span><time>{created_at}</time></p></div>"
            "<span class='approval-open' aria-hidden='true'>管理</span></a></li>"
        )
    instance_content = (
        "<ul class='instance-list'>" + "".join(instance_rows) + "</ul>"
        if instance_rows
        else "<p class='empty-state'>当前没有研究实例。</p>"
    )
    return (
        "<!doctype html><html lang=\"zh-CN\"><head>"
        "<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>科学任务审批</title><link rel=\"stylesheet\" href=\"/static/style.css\">"
        "</head><body><main class=\"approval-dashboard\">"
        "<header><p class=\"eyebrow\">SciDiscovery</p><h1>待审批事项</h1>"
        "<p>智能体只提交结构化科研对象；本页由固定代码按白名单数据格式渲染，不执行模型生成的 HTML。</p></header>"
        f"{content}<section class='instance-management'><h2>研究实例</h2>"
        "<p>查看每个实例的审批历史。</p>"
        f"{instance_content}</section>"
        "</main></body></html>"
    ).encode("utf-8")


def _render_instance_management(
    *,
    capability_token: str,
    expires_at: str,
    csrf_token: str,
    instances: tuple[object, ...],
) -> bytes:
    capability = html.escape(capability_token, quote=True)
    csrf = html.escape(csrf_token, quote=True)
    expiry = html.escape(expires_at)
    options = "".join(
        "<option value='"
        + html.escape(str(getattr(instance, "name", "")), quote=True)
        + "'>"
        + html.escape(str(getattr(instance, "title", "")))
        + " · "
        + html.escape(str(getattr(instance, "name", "")))
        + "</option>"
        for instance in instances
    )
    select_form = (
        "<form class='instance-command' method='post' action='/instances/select'>"
        f"<input type='hidden' name='capability' value='{capability}'>"
        f"<input type='hidden' name='csrf' value='{csrf}'>"
        "<label>现有实例<select name='name' required>"
        + options
        + "</select></label>"
        "<button type='submit'>进入所选实例</button></form>"
        if options
        else "<p class='empty-state'>当前没有可进入的研究实例。</p>"
    )
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>研究实例管理</title>"
        "<link rel='stylesheet' href='/static/style.css'></head><body>"
        "<main class='instance-page'><header><p class='eyebrow'>SciDiscovery</p>"
        "<h1>为当前科研会话选择实例</h1>"
        "<p>本页的提交会直接建立唯一实例绑定，不产生科学审批或执行授权。</p>"
        f"<time>链接有效期至 {expiry}</time></header>"
        "<section><h2>进入现有实例</h2>"
        f"{select_form}</section>"
        "<section><h2>创建新实例</h2>"
        "<form class='instance-command' method='post' action='/instances/create'>"
        f"<input type='hidden' name='capability' value='{capability}'>"
        f"<input type='hidden' name='csrf' value='{csrf}'>"
        "<label>稳定名称<input name='name' required maxlength='256' pattern='[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}'></label>"
        "<label>标题<input name='title' required maxlength='512'></label>"
        "<label>研究目标<textarea name='objective' required maxlength='8192'></textarea></label>"
        "<button type='submit'>创建并进入</button></form></section>"
        "</main></body></html>"
    ).encode("utf-8")


def _render_instance_page(
    instance: object,
    history: tuple[object, ...],
) -> bytes:
    name_raw = str(getattr(instance, "name", ""))
    name = html.escape(name_raw)
    title = html.escape(str(getattr(instance, "title", "")))
    objective = html.escape(str(getattr(instance, "objective", "")))
    state_value = str(getattr(instance, "state", ""))
    state = html.escape(
        {"active": "进行中", "proposed": "待创建", "binding": "待绑定"}.get(
            state_value, state_value
        )
    )
    created_at = html.escape(str(getattr(instance, "created_at", "")))

    history_rows = []
    for item in history:
        status_value = str(getattr(item, "status", "unknown"))
        status = html.escape(
            {
                "pending": "待审批",
                "decided": "已决定",
                "expired": "已过期",
                "cancelled_by_human": "已由用户取消",
                "unknown": "未知",
            }.get(status_value, status_value)
        )
        question = html.escape(str(getattr(item, "question", "审批事项")))
        kind_value = str(getattr(item, "kind", "review"))
        kind = html.escape(
            {
                "scientific_foundation": "科学基础审批",
                "execution_authorization": "执行授权审批",
                "review": "科研审批",
            }.get(kind_value, kind_value)
        )
        created = html.escape(str(getattr(item, "created_at", "")))
        selected = getattr(item, "selected_label", None)
        rationale = getattr(item, "rationale", None)
        decided_at = getattr(item, "decided_at", None)
        decision = (
            "<div class='history-decision'>"
            f"<strong>结果：{html.escape(str(selected))}</strong>"
            + (
                f"<p>理由：{html.escape(str(rationale))}</p>"
                if rationale
                else "<p>未填写理由。</p>"
            )
            + (f"<time>{html.escape(str(decided_at))}</time>" if decided_at else "")
            + "</div>"
            if selected is not None
            else "<p class='history-pending'>尚未作出决定。</p>"
        )
        review_path = getattr(item, "review_path", None)
        open_link = (
            f"<a class='history-open' href='{html.escape(str(review_path), quote=True)}'>打开审批</a>"
            if review_path
            else ""
        )
        history_rows.append(
            "<li class='history-item'><div class='history-heading'>"
            f"<h3>{question}</h3><span>{status}</span></div>"
            f"<p><code>{kind}</code><time>{created}</time></p>{decision}{open_link}</li>"
        )
    history_content = (
        "<ol class='approval-history'>" + "".join(history_rows) + "</ol>"
        if history_rows
        else "<p class='empty-state'>这个实例还没有审批记录。</p>"
    )

    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title} · 实例管理</title>"
        "<link rel='stylesheet' href='/static/style.css'></head><body>"
        "<main class='instance-page'><nav><a href='/'>← 返回审批首页</a></nav>"
        f"<header><p class='eyebrow'>研究实例 · {state}</p><h1>{title}</h1>"
        f"<code>{name}</code><p>{objective}</p><time>{created_at}</time></header>"
        f"<section><h2>历史审批结果</h2>{history_content}</section>"
        "</main></body></html>"
    ).encode("utf-8")


def _one(values: dict[str, list[str]], key: str) -> str | None:
    items = values.get(key)
    return items[0] if items is not None and len(items) == 1 else None


def _required(
    values: dict[str, list[str]], key: str, *, allow_blank: bool = False
) -> str:
    value = _one(values, key)
    if value is None or (not allow_blank and not value):
        raise ValueError(f"missing form field: {key}")
    return value


__all__ = ["ApprovalUI", "MAX_POST_BYTES"]
