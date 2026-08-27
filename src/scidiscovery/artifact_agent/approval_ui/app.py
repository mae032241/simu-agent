"""Minimal loopback HTTP server for direct human decisions."""

from __future__ import annotations

import hashlib
import html
import ipaddress
import logging
import secrets
import socket
import threading
import time
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
from ..service.instance_admin import (
    InstanceAdministrationError,
    InstanceAdministrationService,
    InstanceDeletionBlocked,
)
from ..service.maintenance import MaintenanceBusy, StateMaintenanceLock
from ..service.orphan_admin import (
    CONFIRM_ORPHAN_CLEANUP,
    OrphanAdministrationError,
    OrphanAdministrationService,
    OrphanCleanupBlocked,
    OrphanCleanupReceipt,
)
from ..storage import CASIntegrityError
from .render import ReviewContext, _safe_raster_preview, render_review


MAX_POST_BYTES = 64 * 1024
DESTRUCTIVE_TOKEN_TTL_SECONDS = 15 * 60
MAX_DESTRUCTIVE_TOKENS = 16
STATIC_ROOT = Path(__file__).with_name("static")
LOGGER = logging.getLogger(__name__)


class ApprovalUI:
    def __init__(
        self,
        service: ApprovalService,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        local_identity: LocalIdentityRef | None = None,
        bindings: SchedulerBindingService | None = None,
        instance_admin: InstanceAdministrationService | None = None,
        orphan_admin: OrphanAdministrationService | None = None,
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
        self.instance_admin = instance_admin
        self.orphan_admin = orphan_admin
        self.maintenance = maintenance
        self.session_id = f"ui_{secrets.token_hex(16)}"
        self._instance_delete_tokens: dict[str, dict[str, tuple[float, str]]] = {}
        self._instance_delete_lock = threading.Lock()
        self._orphan_cleanup_tokens: dict[str, tuple[float, str]] = {}
        self._orphan_cleanup_lock = threading.Lock()
        self._last_orphan_cleanup: OrphanCleanupReceipt | None = None
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
            application_failures = (
                self.bindings.decision_application_failures()
                if self.bindings is not None
                else ()
            )
            orphan_plan = self.orphan_admin.plan() if self.orphan_admin is not None else None
            orphan_token = None
            orphan_receipt = None
            if orphan_plan is not None:
                with self._orphan_cleanup_lock:
                    orphan_token = _issue_destructive_token(
                        self._orphan_cleanup_tokens,
                        fingerprint=_plan_fingerprint(orphan_plan),
                    )
                    orphan_receipt = self._last_orphan_cleanup
            return self._respond(
                handler,
                HTTPStatus.OK,
                _render_dashboard(
                    self.service.list_requests(status="pending", limit=100),
                    context_for=self._review_context,
                    instances=instances,
                    application_failures=application_failures,
                    orphan_plan=orphan_plan,
                    orphan_token=orphan_token,
                    orphan_receipt=orphan_receipt,
                ),
                "text/html; charset=utf-8",
            )
        parts = [part for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query, strict_parsing=True)
        token = _one(query, "token")
        try:
            if len(parts) == 2 and parts[0] == "instance":
                if self.bindings is None or self.instance_admin is None:
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
                plan = self.instance_admin.plan(instance_id=instance.instance_id)
                with self._instance_delete_lock:
                    delete_token = _issue_destructive_token(
                        self._instance_delete_tokens.setdefault(
                            instance.instance_id, {}
                        ),
                        fingerprint=_plan_fingerprint(plan),
                    )
                return self._respond(
                    handler,
                    HTTPStatus.OK,
                    _render_instance_page(
                        instance,
                        tuple(history),
                        plan=plan,
                        delete_token=delete_token,
                    ),
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
                    ),
                    "text/html; charset=utf-8",
                )
            if len(parts) == 3 and parts[0] == "preview" and token:
                review = self.service.review(parts[1], access_token=token)
                index = int(parts[2])
                if not 0 <= index < len(review.subjects):
                    raise IndexError("preview subject index is out of range")
                envelope, content = review.subjects[index]
                preview = _safe_raster_preview(content, envelope.media_type)
                if preview is None:
                    return self._error(handler, HTTPStatus.NOT_FOUND)
                media_type, _, _ = preview
                return self._respond(
                    handler,
                    HTTPStatus.OK,
                    content,
                    media_type,
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
        except (ApprovalAccessDenied, ValueError, IndexError):
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
        if parts == ["maintenance", "orphans", "delete"]:
            return self._handle_orphan_cleanup(handler)
        if len(parts) == 3 and parts[0] == "instance" and parts[2] == "delete":
            return self._handle_instance_delete(handler, instance_id=parts[1])
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
                    try:
                        self.bindings.apply_instance_proposal_decision(
                            approval_id=parts[1],
                            selected_option=selected,
                        )
                        self.bindings.apply_session_binding_decision(
                            approval_id=parts[1],
                            selected_option=selected,
                        )
                    except SchedulerBindingError as error:
                        self.bindings.record_decision_application_failure(
                            approval_id=parts[1], error=str(error)
                        )
                        return self._error(
                            handler,
                            HTTPStatus.CONFLICT,
                            "人工决定已经不可变地记录，但实例状态应用失败；"
                            "请在首页查看审批应用异常。",
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

    def _handle_instance_delete(
        self, handler: BaseHTTPRequestHandler, *, instance_id: str
    ) -> None:
        if self.instance_admin is None:
            return self._error(handler, HTTPStatus.NOT_FOUND)
        if not self._valid_origin(handler.headers.get("Origin")):
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
            token = _required(form, "delete_token")
            confirmation_name = _required(form, "instance_name")
            if _required(form, "confirm") != "delete_instance":
                raise ValueError("confirmation mismatch")
            with self._exclusive_maintenance():
                plan = self.instance_admin.plan(instance_id=instance_id)
                with self._instance_delete_lock:
                    if not _destructive_token_matches(
                        self._instance_delete_tokens.get(instance_id, {}),
                        token,
                        fingerprint=_plan_fingerprint(plan),
                    ):
                        raise ValueError("deletion token mismatch")
                self.instance_admin.delete(
                    instance_id=instance_id,
                    confirmation_name=confirmation_name,
                )
            with self._instance_delete_lock:
                tokens = self._instance_delete_tokens.get(instance_id)
                if tokens is not None:
                    tokens.pop(token, None)
                    if not tokens:
                        self._instance_delete_tokens.pop(instance_id, None)
        except (InstanceDeletionBlocked, MaintenanceBusy) as error:
            return self._error(handler, HTTPStatus.CONFLICT, str(error))
        except (UnicodeDecodeError, ValueError, InstanceAdministrationError):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        except SchedulerInstanceNotFound:
            return self._error(handler, HTTPStatus.NOT_FOUND)
        except OSError:
            LOGGER.exception("instance deletion failed in the filesystem")
            return self._error(
                handler,
                HTTPStatus.CONFLICT,
                "实例删除未完成：运行目录无法安全移除，请检查服务日志后重试。",
            )
        self._respond(
            handler,
            HTTPStatus.SEE_OTHER,
            b"",
            "text/plain; charset=utf-8",
            extra_headers={"Location": "/?deleted=1"},
        )

    def _handle_orphan_cleanup(self, handler: BaseHTTPRequestHandler) -> None:
        if self.orphan_admin is None:
            return self._error(handler, HTTPStatus.NOT_FOUND)
        if not self._valid_origin(handler.headers.get("Origin")):
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
            token = _required(form, "maintenance_token")
            if _required(form, "confirm") != "cleanup_orphans":
                raise ValueError("confirmation mismatch")
            confirmation = _required(form, "confirmation")
            with self._exclusive_maintenance():
                plan = self.orphan_admin.plan()
                with self._orphan_cleanup_lock:
                    if not _destructive_token_matches(
                        self._orphan_cleanup_tokens,
                        token,
                        fingerprint=_plan_fingerprint(plan),
                    ):
                        raise ValueError("maintenance token mismatch")
                receipt = self.orphan_admin.delete(confirmation=confirmation)
            with self._orphan_cleanup_lock:
                self._orphan_cleanup_tokens.pop(token, None)
                self._last_orphan_cleanup = receipt
        except (OrphanCleanupBlocked, MaintenanceBusy) as error:
            return self._error(handler, HTTPStatus.CONFLICT, str(error))
        except (UnicodeDecodeError, ValueError, OrphanAdministrationError):
            return self._error(handler, HTTPStatus.FORBIDDEN)
        except OSError:
            LOGGER.exception("orphan cleanup failed in the filesystem")
            return self._error(
                handler,
                HTTPStatus.CONFLICT,
                "孤儿清理未完成：运行目录无法安全移除，请检查服务日志后重试。",
            )
        self._respond(
            handler,
            HTTPStatus.SEE_OTHER,
            b"",
            "text/plain; charset=utf-8",
            extra_headers={"Location": "/?orphans_cleaned=1"},
        )

    def _shared_maintenance(self):
        return (
            self.maintenance.shared()
            if self.maintenance is not None
            else nullcontext()
        )

    def _exclusive_maintenance(self):
        return (
            self.maintenance.exclusive(blocking=False)
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


def _plan_fingerprint(plan: object) -> str:
    return hashlib.sha256(repr(plan).encode("utf-8")).hexdigest()


def _issue_destructive_token(
    tokens: dict[str, tuple[float, str]], *, fingerprint: str
) -> str:
    now = time.monotonic()
    expired = [token for token, (expires_at, _) in tokens.items() if expires_at <= now]
    for token in expired:
        tokens.pop(token, None)
    while len(tokens) >= MAX_DESTRUCTIVE_TOKENS:
        oldest = min(tokens, key=lambda token: tokens[token][0])
        tokens.pop(oldest, None)
    token = secrets.token_urlsafe(32)
    tokens[token] = (now + DESTRUCTIVE_TOKEN_TTL_SECONDS, fingerprint)
    return token


def _destructive_token_matches(
    tokens: dict[str, tuple[float, str]], token: str, *, fingerprint: str
) -> bool:
    record = tokens.get(token)
    if record is None:
        return False
    expires_at, expected_fingerprint = record
    if expires_at <= time.monotonic():
        tokens.pop(token, None)
        return False
    return secrets.compare_digest(expected_fingerprint, fingerprint)


def _render_dashboard(
    items: tuple[object, ...],
    *,
    context_for,
    instances: tuple[object, ...] = (),
    application_failures: tuple[tuple[str, str, str], ...] = (),
    orphan_plan: object | None = None,
    orphan_token: str | None = None,
    orphan_receipt: object | None = None,
) -> bytes:
    rows = []
    for item in items:
        review_path = getattr(item, "review_path", None)
        if review_path is None:
            continue
        kind_value = str(getattr(item, "kind", "review"))
        kind = html.escape(
            {
                "scientific_foundation": "科学基础审批",
                "execution_authorization": "执行授权审批",
                "instance_creation": "研究实例创建审批",
                "research_instance_registration": "研究实例创建审批",
                "session_binding": "进程绑定审批",
                "research_session_binding": "进程绑定审批",
                "review": "科研审批",
            }.get(kind_value, kind_value)
        )
        question = html.escape(str(getattr(item, "question", "待审批事项")))
        created_at = html.escape(str(getattr(item, "created_at", "")))
        href = html.escape(str(review_path), quote=True)
        context = context_for(str(getattr(item, "approval_id", "")))
        if context is None:
            instance = (
                "<div class='approval-instance approval-instance-unbound'>"
                "<span>未绑定研究实例</span></div>"
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
    maintenance_content = _render_orphan_maintenance(
        orphan_plan, token=orphan_token, receipt=orphan_receipt
    )
    application_failure_content = ""
    if application_failures:
        failure_rows = "".join(
            "<li><code>"
            + html.escape(approval_id)
            + "</code><span>"
            + html.escape(
                "实例创建" if object_type == "instance_proposal" else "进程绑定"
            )
            + "</span><p>"
            + html.escape(error)
            + "</p></li>"
            for approval_id, object_type, error in application_failures
        )
        application_failure_content = (
            "<section class='application-failures'><h2>审批应用异常</h2>"
            "<p>人工决定已保存，但对应实例状态尚未成功应用。</p><ul>"
            + failure_rows
            + "</ul></section>"
        )
    return (
        "<!doctype html><html lang=\"zh-CN\"><head>"
        "<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>科学任务审批</title><link rel=\"stylesheet\" href=\"/static/style.css\">"
        "</head><body><main class=\"approval-dashboard\">"
        "<header><p class=\"eyebrow\">SciDiscovery</p><h1>待审批事项</h1>"
        "<p>智能体只提交结构化科研对象；本页由固定代码按白名单数据格式渲染，不执行模型生成的 HTML。</p></header>"
        f"{content}<section class='instance-management'><h2>研究实例</h2>"
        "<p>查看每个实例的审批历史，或显式清理悬空实例。</p>"
        f"{instance_content}</section>{application_failure_content}"
        f"{maintenance_content}</main></body></html>"
    ).encode("utf-8")


def _render_orphan_maintenance(
    plan: object | None, *, token: str | None, receipt: object | None
) -> str:
    if plan is None or token is None:
        return ""
    counts = (
        ("孤儿任务", len(tuple(getattr(plan, "orphan_task_ids", ())))),
        ("孤儿审批", len(tuple(getattr(plan, "orphan_approval_ids", ())))),
        ("孤儿执行", len(tuple(getattr(plan, "orphan_execution_ids", ())))),
        ("科研对象注册", len(tuple(getattr(plan, "artifact_refs", ())))),
        ("工作进程目录", len(tuple(getattr(plan, "stale_workspace_names", ())))),
        ("执行交换目录", len(tuple(getattr(plan, "stale_exchange_names", ())))),
        ("执行结果目录", len(tuple(getattr(plan, "stale_executor_run_names", ())))),
        ("提交标记", len(tuple(getattr(plan, "stale_submission_names", ())))),
    )
    blockers = tuple(getattr(plan, "blockers", ()))
    count_cards = "".join(
        "<div><dt>" + html.escape(label) + "</dt><dd>" + str(value) + "</dd></div>"
        for label, value in counts
    )
    blocker_content = (
        "<div class='delete-blockers'><strong>当前不能清理：</strong><ul>"
        + "".join(f"<li>{html.escape(str(value))}</li>" for value in blockers)
        + "</ul></div>"
        if blockers
        else ""
    )
    total = sum(value for _, value in counts)
    disabled = " disabled" if blockers or total == 0 else ""
    receipt_content = ""
    if receipt is not None:
        deleted = sum(
            int(getattr(receipt, field, 0))
            for field in (
                "deleted_tasks",
                "deleted_approvals",
                "deleted_executions",
                "deleted_artifact_registrations",
                "deleted_workspaces",
                "deleted_exchange_directories",
                "deleted_executor_runs",
                "deleted_submission_markers",
            )
        )
        verification_ok = (
            bool(getattr(receipt, "database_integrity_ok", False))
            and bool(getattr(receipt, "artifact_integrity_ok", False))
            and int(getattr(receipt, "remaining_cas_orphans", -1)) == 0
        )
        receipt_content = (
            "<div class='maintenance-receipt'><strong>最近一次清理完成</strong>"
            f"<p>共移除 {deleted} 个控制记录或运行条目；"
            f"完整性校验：{'通过' if verification_ok else '需要检查'}。</p></div>"
        )
    return (
        "<section class='maintenance-management'><h2>系统维护</h2>"
        "<p>这里只清理没有研究实例归属的控制状态和终态运行目录，不触及项目 workspace。"
        "刷新页面即可重新扫描。</p>"
        f"{receipt_content}<dl class='maintenance-counts'>{count_cards}</dl>"
        f"{blocker_content}"
        "<form class='orphan-cleanup' method='post' action='/maintenance/orphans/delete'>"
        f"<input type='hidden' name='maintenance_token' value='{html.escape(token, quote=True)}'>"
        "<input type='hidden' name='confirm' value='cleanup_orphans'>"
        f"<label>输入 <code>{CONFIRM_ORPHAN_CLEANUP}</code> 以确认"
        f"<input name='confirmation' autocomplete='off' required{disabled}></label>"
        f"<button class='danger' type='submit'{disabled}>清理孤儿状态</button></form></section>"
    )


def _render_instance_page(
    instance: object,
    history: tuple[object, ...],
    *,
    plan: object,
    delete_token: str,
) -> bytes:
    instance_id = html.escape(str(getattr(instance, "instance_id", "")), quote=True)
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
                "instance_creation": "研究实例创建审批",
                "research_instance_registration": "研究实例创建审批",
                "session_binding": "进程绑定审批",
                "research_session_binding": "进程绑定审批",
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

    bindings = tuple(getattr(plan, "bindings", ()))
    shared = tuple(getattr(plan, "shared_bindings", ()))
    blockers = tuple(getattr(plan, "blockers", ()))
    counts = {
        "任务": len(tuple(getattr(plan, "exclusive_task_ids", ()))),
        "审批": len(tuple(getattr(plan, "exclusive_approval_ids", ()))),
        "执行": len(tuple(getattr(plan, "exclusive_execution_ids", ()))),
        "直接科研对象": len(tuple(getattr(plan, "exclusive_artifact_ids", ()))),
    }
    count_text = "，".join(f"{label} {value}" for label, value in counts.items())
    blocker_content = (
        "<div class='delete-blockers'><strong>当前不能删除：</strong><ul>"
        + "".join(f"<li>{html.escape(str(value))}</li>" for value in blockers)
        + "</ul></div>"
        if blockers
        else ""
    )
    disabled = " disabled" if blockers else ""
    delete_form = (
        f"<form class='instance-delete' method='post' action='/instance/{instance_id}/delete'>"
        f"<input type='hidden' name='delete_token' value='{html.escape(delete_token, quote=True)}'>"
        "<input type='hidden' name='confirm' value='delete_instance'>"
        f"<label>输入实例名 <code>{name}</code> 以确认"
        f"<input name='instance_name' autocomplete='off' required{disabled}></label>"
        f"<button class='danger' type='submit'{disabled}>永久删除实例</button></form>"
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
        "<section class='danger-zone'><h2>删除实例</h2>"
        f"<p>将移除 {len(bindings)} 条实例绑定及专属控制记录（{count_text}）。"
        f"其他实例仍引用的 {len(shared)} 个共享对象会保留。实例专属 CAS 字节仅在没有其他注册引用时清理。"
        "</p>"
        f"{blocker_content}{delete_form}</section></main></body></html>"
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
