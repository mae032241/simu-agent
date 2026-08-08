"""Minimal loopback HTTP server for direct human decisions."""

from __future__ import annotations

import ipaddress
import html
import secrets
import socket
import threading
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
)
from ..storage import CASIntegrityError
from .render import ReviewContext, render_review


MAX_POST_BYTES = 64 * 1024
STATIC_ROOT = Path(__file__).with_name("static")


class ApprovalUI:
    def __init__(
        self,
        service: ApprovalService,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        local_identity: LocalIdentityRef | None = None,
        bindings: SchedulerBindingService | None = None,
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
            return self._respond(
                handler,
                HTTPStatus.OK,
                _render_dashboard(
                    self.service.list_requests(status="pending", limit=100),
                    context_for=self._review_context,
                ),
                "text/html; charset=utf-8",
            )
        parts = [part for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query, strict_parsing=True)
        token = _one(query, "token")
        try:
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
                    ),
                    "text/html; charset=utf-8",
                )
            if len(parts) == 3 and parts[0] == "subject" and token:
                review = self.service.review(parts[1], access_token=token)
                index = int(parts[2])
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
        except (ApprovalAccessDenied, ValueError, IndexError):
            return self._error(handler, HTTPStatus.FORBIDDEN)
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
            proposal = self.bindings.find_instance_proposal_by_approval(
                approval_id=approval_id
            )
            if proposal is not None:
                return ReviewContext(
                    instance_name=proposal.name,
                    instance_title=proposal.title,
                    instance_objective=proposal.objective,
                    approval_name="实例创建审批",
                    approval_logical_name="research_instance_registration",
                    approval_revision=1,
                    instance_status="proposed",
                )
            binding_request = (
                self.bindings.find_session_binding_request_by_approval(
                    approval_id=approval_id
                )
            )
            if binding_request is None:
                return None
            candidates = self.bindings.session_binding_candidates(
                request_id=binding_request.request_id
            )
            return ReviewContext(
                instance_name="待用户选择",
                instance_title="MCP 进程绑定",
                instance_objective=(
                    f"从 {len(candidates)} 个可用研究实例中选择当前进程的独占归属。"
                ),
                approval_name="进程绑定审批",
                approval_logical_name="research_session_binding",
                approval_revision=1,
                instance_status="binding",
            )
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
        if len(parts) != 3 or parts[0] != "review" or parts[2] != "decision":
            return self._error(handler, HTTPStatus.NOT_FOUND)
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
            if self.bindings is not None:
                self.bindings.apply_instance_proposal_decision(
                    approval_id=parts[1],
                    selected_option=selected,
                )
                self.bindings.apply_session_binding_decision(
                    approval_id=parts[1],
                    selected_option=selected,
                )
        except (UnicodeDecodeError, ValueError, ApprovalAccessDenied):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        except ApprovalExpired:
            return self._error(handler, HTTPStatus.GONE)
        except (ApprovalError, CASIntegrityError, SchedulerBindingError):
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

    def _error(self, handler: BaseHTTPRequestHandler, status: HTTPStatus) -> None:
        self._respond(
            handler,
            status,
            f"{status.value} {status.phrase}\n".encode(),
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
            "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
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


def _render_dashboard(items: tuple[object, ...], *, context_for) -> bytes:
    rows = []
    for item in items:
        review_path = getattr(item, "review_path", None)
        if review_path is None:
            continue
        kind = html.escape(str(getattr(item, "kind", "review")))
        question = html.escape(str(getattr(item, "question", "待审批事项")))
        created_at = html.escape(str(getattr(item, "created_at", "")))
        href = html.escape(str(review_path), quote=True)
        context = context_for(str(getattr(item, "approval_id", "")))
        if context is None:
            instance = (
                "<div class='approval-instance approval-instance-unbound'>"
                "<span>未绑定 ResearchInstance</span></div>"
            )
            approval_name = "旧审批"
        else:
            context_label = (
                "待创建研究实例"
                if context.instance_status == "proposed"
                else (
                    "待绑定研究实例"
                    if context.instance_status == "binding"
                    else "研究实例"
                )
            )
            instance = (
                "<div class='approval-instance'>"
                f"<span class='approval-instance-label'>{context_label}</span>"
                f"<strong>{html.escape(context.instance_title)}</strong>"
                f"<code>{html.escape(context.instance_name)}</code></div>"
            )
            approval_name = context.approval_name
        rows.append(
            "<li class=\"approval-item\">"
            f"<a href=\"{href}\">{instance}"
            "<div class='approval-summary'>"
            f"<h2>{question}</h2>"
            "<p>"
            f"<span class='approval-kind'>{kind}</span>"
            f"<span>审批项：<code>{html.escape(approval_name)}</code></span>"
            f"<time>{created_at}</time></p></div>"
            "<span class='approval-open' aria-hidden='true'>查看</span>"
            "</a></li>"
        )
    content = (
        "<ul class=\"approval-list\">" + "".join(rows) + "</ul>"
        if rows
        else "<p class=\"empty-state\">当前没有待审批事项。</p>"
    )
    return (
        "<!doctype html><html lang=\"zh-CN\"><head>"
        "<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>科学任务审批</title><link rel=\"stylesheet\" href=\"/static/style.css\">"
        "</head><body><main class=\"approval-dashboard\">"
        "<header><p class=\"eyebrow\">SciDiscovery</p><h1>待审批事项</h1>"
        "<p>选择一项查看冻结内容、参数和可视化结果。</p></header>"
        f"{content}</main></body></html>"
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
