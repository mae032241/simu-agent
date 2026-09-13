"""Persistent exact-object approval requests and UI-only decisions."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from ..schema.approval import (
    CompiledApprovalIdentity,
    ApprovalOption,
    ApprovalPresentation,
    ApprovalRequest,
    HumanDecision,
    LocalIdentityRef,
    ReviewManifest,
    ReviewDocument,
    ReviewSubject,
    parse_json_pointer,
    subject_set_sha256,
)
from ..schema.artifact import ArtifactEnvelope, ArtifactRegistration
from ..schema.common import canonical_json
from ..schema.refs import ActorRef, ArtifactRef
from .artifacts import ArtifactService


class ApprovalError(RuntimeError):
    pass


class ApprovalAccessDenied(ApprovalError):
    pass


class ApprovalExpired(ApprovalError):
    pass


class ApprovalAlreadyDecided(ApprovalError):
    pass


class ApprovalNonceConflict(ApprovalError):
    pass


class ApprovalIdempotencyConflict(ApprovalError):
    pass


@dataclass(frozen=True)
class ApprovalLaunch:
    approval_id: str
    approval_request_ref: ArtifactRef
    access_token: str

    @property
    def review_path(self) -> str:
        return f"/review/{self.approval_id}?token={self.access_token}"

    def url(self, base_url: str) -> str:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("approval UI base URL must be loopback HTTP")
        return base_url.rstrip("/") + self.review_path


@dataclass(frozen=True)
class ApprovalStatusView:
    approval_request_ref: ArtifactRef
    status: str
    decision_ref: ArtifactRef | None
    review_path: str | None


@dataclass(frozen=True)
class ApprovalListItem:
    approval_id: str
    kind: str
    question: str
    status: str
    created_at: str
    review_path: str | None
    access_expired: bool = False
    selected_option: str | None = None
    selected_label: str | None = None
    rationale: str | None = None
    decided_at: str | None = None


@dataclass(frozen=True)
class ApprovalReview:
    request_ref: ArtifactRef
    request: ApprovalRequest
    manifest: ReviewManifest
    subjects: tuple[tuple[ArtifactEnvelope, bytes], ...]
    status: str
    decision_ref: ArtifactRef | None
    csrf_token: str
    decision_nonce: str


@dataclass(frozen=True)
class _PreparedDecision:
    decided_at: str
    ui_session_id: str


class ApprovalService:
    def __init__(
        self,
        *,
        artifacts: ArtifactService,
        database_path: Path | str,
        service_actor: ActorRef,
        receipt_secret: bytes,
    ) -> None:
        if type(receipt_secret) is not bytes or len(receipt_secret) < 32:
            raise ValueError("approval receipt secret must contain at least 32 bytes")
        self.artifacts = artifacts
        self.database_path = _state_path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.service_actor = service_actor
        self._receipt_secret = receipt_secret
        self._initialize()

    def create_request(
        self,
        *,
        approval_id: str,
        kind: str,
        subject_refs: tuple[ArtifactRef, ...],
        question: str,
        options: tuple[ApprovalOption, ...],
        requested_by: ActorRef,
        idempotency_key: str,
        expires_at: str | None = None,
        presentation: ApprovalPresentation | None = None,
        review_document: ReviewDocument | None = None,
        compiled_identity: CompiledApprovalIdentity | None = None,
        now: datetime | None = None,
    ) -> ApprovalLaunch:
        self._verify_presentation(presentation, subject_refs)
        self._verify_review_document(review_document, subject_refs)
        request_input = canonical_json(
            {
                "operation": "approval.create",
                "approval_id": approval_id,
                "kind": kind,
                "subject_refs": subject_refs,
                "question": question,
                "options": options,
                "requested_by": requested_by,
                "expires_at": expires_at,
                "presentation": presentation,
                "review_document": review_document,
                "compiled_identity": compiled_identity,
            }
        )
        request_input_sha = hashlib.sha256(request_input).hexdigest()
        current = _now(now)
        if expires_at is not None and _parse_time(expires_at) <= current:
            raise ApprovalExpired("approval request expiry is not in the future")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                "SELECT * FROM approval_requests WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if replay is not None:
                if replay["create_request_sha256"] != request_input_sha or replay["create_request_json"] != request_input:
                    raise ApprovalIdempotencyConflict(
                        "approval idempotency key has different request bytes"
                    )
                launch = ApprovalLaunch(
                    replay["approval_id"],
                    _parse_ref(replay["request_ref_json"], replay["request_ref_sha256"]),
                    replay["access_token"],
                )
                connection.execute("ROLLBACK")
                return launch

            access_token = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            decision_nonce = secrets.token_urlsafe(32)
            manifest = self._build_manifest(approval_id, subject_refs)
            manifest_envelope = self.artifacts.register(
                manifest.canonical_json(),
                ArtifactRegistration(
                    artifact_id=f"review_manifest_{approval_id}",
                    kind="review_manifest",
                    schema_id="scidiscovery.review-manifest",
                    payload_schema_version=1,
                    media_type="application/json",
                    creator=self.service_actor,
                    parent_refs=subject_refs,
                    confidentiality="approval_only",
                ),
                idempotency_key=f"approval-manifest:{idempotency_key}",
            )
            request = ApprovalRequest(
                approval_id=approval_id,
                kind=kind,
                subject_refs=subject_refs,
                subject_set_sha256=subject_set_sha256(subject_refs),
                question=question,
                options=options,
                review_manifest_ref=manifest_envelope.ref,
                requested_by=requested_by,
                expires_at=expires_at,
                nonce_hash=_secret_hash(decision_nonce),
                presentation=presentation,
                review_document=review_document,
                compiled_identity=compiled_identity,
            )
            request_envelope = self.artifacts.register(
                request.canonical_json(),
                ArtifactRegistration(
                    artifact_id=f"approval_request_{approval_id}",
                    kind="approval_request",
                    schema_id="scidiscovery.approval-request",
                    payload_schema_version=1,
                    media_type="application/json",
                    creator=self.service_actor,
                    parent_refs=subject_refs + (manifest_envelope.ref,),
                    confidentiality="approval_only",
                ),
                idempotency_key=f"approval-request:{idempotency_key}",
            )
            access_expires = min(
                current + timedelta(hours=1),
                _parse_time(expires_at) if expires_at is not None else current + timedelta(hours=1),
            )
            recorded_at = _timestamp(current)
            connection.execute(
                """
                INSERT INTO approval_requests (
                    approval_id, request_ref_json, request_ref_sha256, status,
                    decision_ref_json, decision_ref_sha256, access_token,
                    access_token_hash, csrf_token, csrf_token_hash,
                    decision_nonce, nonce_hash, access_expires_at, expires_at,
                    idempotency_key, create_request_json, create_request_sha256,
                    created_at
                ) VALUES (?, ?, ?, 'pending', NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    request_envelope.ref.canonical_json(),
                    request_envelope.ref.content_hash,
                    access_token,
                    _secret_hash(access_token),
                    csrf_token,
                    _secret_hash(csrf_token),
                    decision_nonce,
                    _secret_hash(decision_nonce),
                    _timestamp(access_expires),
                    expires_at,
                    idempotency_key,
                    request_input,
                    request_input_sha,
                    recorded_at,
                ),
            )
            connection.execute("COMMIT")
            return ApprovalLaunch(approval_id, request_envelope.ref, access_token)
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def status(self, approval_id: str, *, now: datetime | None = None) -> ApprovalStatusView:
        current = _now(now)
        with self._connect() as connection:
            row = self._request_row(connection, approval_id)
        effective_status = self._effective_status(row, current)
        reference = _parse_ref(row["request_ref_json"], row["request_ref_sha256"])
        decision = (
            _parse_ref(row["decision_ref_json"], row["decision_ref_sha256"])
            if row["decision_ref_json"] is not None
            else None
        )
        review_path = (
            f"/review/{approval_id}?token={row['access_token']}"
            if effective_status == "pending"
            and current < _parse_time(row["access_expires_at"])
            else None
        )
        return ApprovalStatusView(reference, effective_status, decision, review_path)

    def has_request(self, approval_id: str) -> bool:
        if not isinstance(approval_id, str) or not approval_id:
            raise ValueError("approval identity is invalid")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM approval_requests WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        return row is not None

    def are_subjects_approved_by_provider(
        self,
        subject_refs: tuple[ArtifactRef, ...],
        *,
        kind: str,
        accepted_options: tuple[str, ...],
        accepted_providers: tuple[CompiledApprovalIdentity, ...],
        allow_compatible_provider: bool = False,
    ) -> bool:
        """Match an exact decision; research may reuse the same approval contract."""

        if (
            not subject_refs
            or len(subject_refs) != len(set(subject_refs))
            or not accepted_providers
            or len(accepted_providers) != len(set(accepted_providers))
        ):
            raise ValueError("provider-aware approval contract is incomplete")
        for reference in subject_refs:
            self.artifacts.verify(reference)
        accepted = set(accepted_providers)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT request_ref_json, request_ref_sha256,
                       decision_ref_json, decision_ref_sha256
                FROM approval_requests
                WHERE status = 'decided' AND decision_ref_json IS NOT NULL
                ORDER BY created_at DESC
                """
            ).fetchall()
        for row in rows:
            request_ref = _parse_ref(
                row["request_ref_json"], row["request_ref_sha256"]
            )
            decision_ref = _parse_ref(
                row["decision_ref_json"], row["decision_ref_sha256"]
            )
            try:
                request = ApprovalRequest.model_validate_json(
                    self.artifacts.read(request_ref), strict=True
                )
                decision = HumanDecision.model_validate_json(
                    self.artifacts.read(decision_ref), strict=True
                )
            except ValidationError as error:
                raise ApprovalError("stored approval qualification is invalid") from error
            identity = request.compiled_identity
            provider_matches = identity in accepted or (
                allow_compatible_provider
                and kind != "execution_authorization"
                and identity is not None
                and any(
                    identity.operation_id == provider.operation_id
                    and identity.operation_version == provider.operation_version
                    and identity.approval_contract_digest == provider.approval_contract_digest
                    for provider in accepted
                )
            )
            if (
                provider_matches
                and request.kind == kind
                and decision.approval_request_ref == request_ref
                and decision.subject_refs == request.subject_refs
                and decision.subject_set_sha256 == request.subject_set_sha256
                and decision.selected_option in accepted_options
                and all(reference in decision.subject_refs for reference in subject_refs)
            ):
                return True
        return False

    def list_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        now: datetime | None = None,
        excluded_kinds: tuple[str, ...] = (),
    ) -> tuple[ApprovalListItem, ...]:
        """Return a bounded newest-first recovery view."""

        current = _now(now)
        allowed = {"pending", "decided", "expired", "cancelled_by_human"}
        if status is not None and status not in allowed:
            raise ValueError("unknown approval status")
        if not 1 <= limit <= 100:
            raise ValueError("approval list limit must be between 1 and 100")
        if any(not isinstance(kind, str) or not kind for kind in excluded_kinds):
            raise ValueError("excluded approval kind is invalid")
        excluded = frozenset(excluded_kinds)
        query_prefix = (
            "SELECT approval_id, request_ref_json, request_ref_sha256, created_at "
            "FROM approval_requests"
        )
        items: list[ApprovalListItem] = []
        cursor: tuple[str, str] | None = None
        page_size = 100
        while len(items) < limit:
            conditions = []
            parameters: list[object] = []
            if cursor is not None:
                conditions.append(
                    "(created_at < ? OR (created_at = ? AND approval_id < ?))"
                )
                parameters.extend((cursor[0], cursor[0], cursor[1]))
            query = query_prefix
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC, approval_id DESC LIMIT ?"
            parameters.append(page_size)
            with self._connect() as connection:
                rows = tuple(connection.execute(query, tuple(parameters)).fetchall())
            if not rows:
                break
            cursor = (str(rows[-1]["created_at"]), str(rows[-1]["approval_id"]))
            for row in rows:
                approval_id = str(row["approval_id"])
                request_ref = _parse_ref(
                    row["request_ref_json"], row["request_ref_sha256"]
                )
                if self._load_request(request_ref).kind in excluded:
                    continue
                view = self.status(approval_id, now=current)
                if status is not None and view.status != status:
                    continue
                items.append(self.request_summary(approval_id, now=current))
                if len(items) == limit:
                    break
        return tuple(items)

    def request_summary(
        self, approval_id: str, *, now: datetime | None = None
    ) -> ApprovalListItem:
        """Return one bounded request summary, including its terminal decision."""

        current = _now(now)
        view = self.status(approval_id, now=current)
        request = self._load_request(view.approval_request_ref)
        selected_option = None
        selected_label = None
        rationale = None
        decided_at = None
        if view.decision_ref is not None:
            decision = self._load_decision(view.decision_ref)
            selected_option = decision.selected_option
            rationale = decision.rationale
            decided_at = decision.decided_at
            option = next(
                (
                    item
                    for item in request.options
                    if item.option_id == decision.selected_option
                ),
                None,
            )
            selected_label = option.label if option is not None else selected_option
        with self._connect() as connection:
            row = self._request_row(connection, approval_id)
        review_path = view.review_path
        if view.status != "pending":
            review_path = f"/history/{approval_id}?token={row['access_token']}"
        return ApprovalListItem(
            approval_id=approval_id,
            kind=request.kind,
            question=request.question,
            status=view.status,
            created_at=row["created_at"],
            review_path=review_path,
            access_expired=(
                view.status == "pending"
                and current >= _parse_time(row["access_expires_at"])
            ),
            selected_option=selected_option,
            selected_label=selected_label,
            rationale=rationale,
            decided_at=decided_at,
        )

    def refresh_access(
        self, approval_id: str, *, now: datetime | None = None
    ) -> ApprovalLaunch:
        """Explicitly renew an expired pending-review link."""

        current = _now(now)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = self._request_row(connection, approval_id)
            effective_status = self._effective_status(row, current)
            if effective_status == "expired":
                raise ApprovalExpired("approval request has expired")
            if effective_status != "pending":
                raise ApprovalAlreadyDecided(
                    f"approval request is terminal: {effective_status}"
                )
            request_ref = _parse_ref(
                row["request_ref_json"], row["request_ref_sha256"]
            )
            if current < _parse_time(row["access_expires_at"]):
                launch = ApprovalLaunch(
                    approval_id, request_ref, row["access_token"]
                )
                connection.execute("ROLLBACK")
                return launch
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            access_expires = current + timedelta(hours=1)
            if row["expires_at"] is not None:
                access_expires = min(access_expires, _parse_time(row["expires_at"]))
            connection.execute(
                """
                UPDATE approval_requests SET access_token = ?, access_token_hash = ?,
                    csrf_token = ?, csrf_token_hash = ?, access_expires_at = ?
                WHERE approval_id = ? AND status = 'pending'
                """,
                (
                    token,
                    _secret_hash(token),
                    csrf,
                    _secret_hash(csrf),
                    _timestamp(access_expires),
                    approval_id,
                ),
            )
            connection.execute("COMMIT")
            return ApprovalLaunch(approval_id, request_ref, token)
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def review(
        self,
        approval_id: str,
        *,
        access_token: str,
        now: datetime | None = None,
    ) -> ApprovalReview:
        current = _now(now)
        with self._connect() as connection:
            row = self._request_row(connection, approval_id)
        effective_status = self._effective_status(row, current)
        self._validate_access(
            row,
            access_token,
            current,
            allow_terminal=True,
            effective_status=effective_status,
        )
        request_ref = _parse_ref(row["request_ref_json"], row["request_ref_sha256"])
        request = self._load_request(request_ref)
        manifest = self._load_manifest(request.review_manifest_ref)
        subjects = tuple(
            (self.artifacts.catalog(ref), self.artifacts.read(ref))
            for ref in request.subject_refs
        )
        self._verify_manifest(manifest, subjects)
        decision_ref = (
            _parse_ref(row["decision_ref_json"], row["decision_ref_sha256"])
            if row["decision_ref_json"] is not None
            else None
        )
        return ApprovalReview(
            request_ref,
            request,
            manifest,
            subjects,
            effective_status,
            decision_ref,
            row["csrf_token"],
            row["decision_nonce"],
        )

    def record_ui_decision(
        self,
        *,
        approval_id: str,
        access_token: str,
        csrf_token: str,
        decision_nonce: str,
        selected_option: str,
        rationale: str,
        decided_by: LocalIdentityRef,
        ui_session_id: str,
        now: datetime | None = None,
    ) -> ArtifactRef:
        submitted_at = _now(now)
        prepared = self._prepare_decision_attempt(
            approval_id=approval_id,
            access_token=access_token,
            csrf_token=csrf_token,
            decision_nonce=decision_nonce,
            selected_option=selected_option,
            rationale=rationale,
            decided_by=decided_by,
            ui_session_id=ui_session_id,
            submitted_at=submitted_at,
        )
        decision_time = _parse_time(prepared.decided_at)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = self._request_row(connection, approval_id)
            self._validate_access(row, access_token, submitted_at, allow_terminal=True)
            if not hmac.compare_digest(row["csrf_token_hash"], _secret_hash(csrf_token)):
                raise ApprovalAccessDenied("CSRF token is invalid")
            if not hmac.compare_digest(row["nonce_hash"], _secret_hash(decision_nonce)):
                raise ApprovalAccessDenied("decision nonce is invalid for this request")
            request_ref = _parse_ref(row["request_ref_json"], row["request_ref_sha256"])
            request = self._load_request(request_ref)
            if request.nonce_hash != row["nonce_hash"]:
                raise ApprovalAccessDenied("request nonce binding is inconsistent")
            if row["status"] in {"decided", "cancelled_by_human"}:
                existing_ref = _parse_ref(row["decision_ref_json"], row["decision_ref_sha256"])
                existing = self._load_decision(existing_ref)
                if (
                    existing.selected_option == selected_option
                    and existing.rationale == rationale
                    and existing.decided_by == decided_by
                ):
                    connection.execute("ROLLBACK")
                    return existing_ref
                raise ApprovalNonceConflict("decision nonce was already used with different content")
            if row["status"] == "expired":
                raise ApprovalExpired("approval request has expired")
            if row["status"] != "pending":
                raise ApprovalAlreadyDecided(f"approval request is terminal: {row['status']}")
            if row["expires_at"] is not None and decision_time >= _parse_time(row["expires_at"]):
                raise ApprovalExpired("approval request has expired")
            option = next(
                (option for option in request.options if option.option_id == selected_option),
                None,
            )
            if option is None:
                raise ApprovalAccessDenied("selected option is not registered")
            if option.requires_rationale and not rationale.strip():
                raise ApprovalAccessDenied("selected option requires a rationale")
            self._verify_request_subjects(request)
            receipt_payload = canonical_json(
                {
                    "request_ref": request_ref,
                    "subject_set_sha256": request.subject_set_sha256,
                    "selected_option": selected_option,
                    "rationale": rationale,
                    "decided_by": decided_by,
                    "nonce_hash": request.nonce_hash,
                    "csrf_hash": row["csrf_token_hash"],
                    "ui_session_id": prepared.ui_session_id,
                }
            )
            receipt = hmac.new(
                self._receipt_secret, receipt_payload, hashlib.sha256
            ).hexdigest()
            decision = HumanDecision(
                decision_id=f"decision_{request.nonce_hash[:32]}",
                approval_request_ref=request_ref,
                subject_refs=request.subject_refs,
                subject_set_sha256=request.subject_set_sha256,
                selected_option=selected_option,
                rationale=rationale,
                decided_by=decided_by,
                decided_at=prepared.decided_at,
                ui_receipt=receipt,
            )
            decision_envelope = self.artifacts.register(
                decision.canonical_json(),
                ArtifactRegistration(
                    artifact_id=f"human_{decision.decision_id}",
                    kind="human_decision",
                    schema_id="scidiscovery.human-decision",
                    payload_schema_version=1,
                    media_type="application/json",
                    creator=ActorRef(actor_id=decided_by.identity_id, actor_type="local_human"),
                    parent_refs=(request_ref,) + request.subject_refs,
                    confidentiality="approval_only",
                ),
                idempotency_key=f"human-decision:{approval_id}:{request.nonce_hash}",
            )
            connection.execute(
                """
                INSERT INTO used_nonces (nonce_hash, approval_id, decision_ref_json, used_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    request.nonce_hash,
                    approval_id,
                    decision_envelope.ref.canonical_json(),
                    prepared.decided_at,
                ),
            )
            terminal = option.terminal_state
            cursor = connection.execute(
                """
                UPDATE approval_requests
                SET status = ?, decision_ref_json = ?, decision_ref_sha256 = ?
                WHERE approval_id = ? AND status = 'pending'
                """,
                (
                    terminal,
                    decision_envelope.ref.canonical_json(),
                    decision_envelope.ref.content_hash,
                    approval_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ApprovalAlreadyDecided("approval request changed concurrently")
            connection.execute(
                """
                INSERT INTO approval_decisions (
                    decision_id, approval_id, decision_ref_json,
                    decision_ref_sha256, selected_option, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    approval_id,
                    decision_envelope.ref.canonical_json(),
                    decision_envelope.ref.content_hash,
                    selected_option,
                    decision.decided_at,
                ),
            )
            connection.execute("COMMIT")
            return decision_envelope.ref
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _prepare_decision_attempt(
        self,
        *,
        approval_id: str,
        access_token: str,
        csrf_token: str,
        decision_nonce: str,
        selected_option: str,
        rationale: str,
        decided_by: LocalIdentityRef,
        ui_session_id: str,
        submitted_at: datetime,
    ) -> _PreparedDecision:
        binding = canonical_json(
            {
                "approval_id": approval_id,
                "selected_option": selected_option,
                "rationale": rationale,
                "decided_by": decided_by,
            }
        )
        binding_hash = hashlib.sha256(binding).hexdigest()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = self._request_row(connection, approval_id)
            self._validate_access(row, access_token, submitted_at, allow_terminal=True)
            if not hmac.compare_digest(row["csrf_token_hash"], _secret_hash(csrf_token)):
                raise ApprovalAccessDenied("CSRF token is invalid")
            nonce_hash = _secret_hash(decision_nonce)
            if not hmac.compare_digest(row["nonce_hash"], nonce_hash):
                raise ApprovalAccessDenied("decision nonce is invalid for this request")
            existing = connection.execute(
                "SELECT * FROM decision_attempts WHERE nonce_hash = ?",
                (nonce_hash,),
            ).fetchone()
            if existing is not None:
                if existing["binding_sha256"] != binding_hash or existing["binding_json"] != binding:
                    raise ApprovalNonceConflict(
                        "decision nonce was already bound to different content"
                    )
                prepared = _PreparedDecision(
                    existing["decided_at"], existing["ui_session_id"]
                )
                connection.execute("ROLLBACK")
                return prepared
            request_ref = _parse_ref(row["request_ref_json"], row["request_ref_sha256"])
            request = self._load_request(request_ref)
            option = next(
                (item for item in request.options if item.option_id == selected_option),
                None,
            )
            if option is None:
                raise ApprovalAccessDenied("selected option is not registered")
            if option.requires_rationale and not rationale.strip():
                raise ApprovalAccessDenied("selected option requires a rationale")
            if row["status"] not in {"pending", "decided", "cancelled_by_human"}:
                raise ApprovalAlreadyDecided(f"approval request is terminal: {row['status']}")
            if row["expires_at"] is not None and submitted_at >= _parse_time(row["expires_at"]):
                raise ApprovalExpired("approval request has expired")
            decided_at = _timestamp(submitted_at)
            connection.execute(
                """
                INSERT INTO decision_attempts (
                    nonce_hash, approval_id, binding_json, binding_sha256,
                    ui_session_id, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    nonce_hash,
                    approval_id,
                    binding,
                    binding_hash,
                    ui_session_id,
                    decided_at,
                ),
            )
            connection.execute("COMMIT")
            return _PreparedDecision(decided_at, ui_session_id)
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _build_manifest(
        self, approval_id: str, refs: tuple[ArtifactRef, ...]
    ) -> ReviewManifest:
        subjects = []
        for ref in refs:
            envelope = self.artifacts.verify(ref)
            raw = self.artifacts.read(ref)
            base_type = envelope.media_type.split(";", 1)[0].strip().lower()
            structured = base_type == "application/json"
            pointers: tuple[str, ...] = ()
            if structured:
                try:
                    value = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ApprovalError("structured approval subject is invalid JSON") from error
                pointers = tuple(_json_pointers(value))
            subjects.append(
                ReviewSubject(
                    artifact_ref=ref,
                    size_bytes=envelope.size_bytes,
                    media_type=envelope.media_type,
                    envelope_sha256=envelope.content_hash,
                    structured_json=structured,
                    json_pointers=pointers,
                )
            )
        return ReviewManifest(approval_id=approval_id, subjects=tuple(subjects))

    def _verify_request_subjects(self, request: ApprovalRequest) -> None:
        manifest = self._load_manifest(request.review_manifest_ref)
        subjects = tuple(
            (self.artifacts.catalog(ref), self.artifacts.read(ref))
            for ref in request.subject_refs
        )
        self._verify_manifest(manifest, subjects)
        self._verify_presentation(request.presentation, request.subject_refs)
        self._verify_review_document(request.review_document, request.subject_refs)

    def _verify_presentation(
        self,
        presentation: ApprovalPresentation | None,
        subject_refs: tuple[ArtifactRef, ...],
    ) -> None:
        if presentation is None:
            return
        parsed_subjects: dict[int, object] = {}
        for translation in presentation.translations:
            index = translation.subject_index
            value = parsed_subjects.get(index)
            if value is None:
                envelope = self.artifacts.catalog(subject_refs[index])
                if envelope.media_type.split(";", 1)[0].strip().lower() != "application/json":
                    raise ApprovalError(
                        "display translation subject must be structured JSON"
                    )
                try:
                    value = json.loads(self.artifacts.read(subject_refs[index]))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ApprovalError(
                        "display translation subject is invalid JSON"
                    ) from error
                parsed_subjects[index] = value
            target = _json_pointer_value(value, translation.json_pointer)
            if not isinstance(target, str):
                raise ApprovalError(
                    "display translation target must be an existing JSON string"
                )

    def _verify_review_document(
        self,
        document: ReviewDocument | None,
        subject_refs: tuple[ArtifactRef, ...],
    ) -> None:
        if document is None:
            return
        parsed_subjects: dict[int, object] = {}
        for section in document.sections:
            for item in section.items:
                if item.subject_index >= len(subject_refs):
                    raise ApprovalError("review document subject index is out of range")
                if item.json_pointer is None:
                    continue
                index = item.subject_index
                if index not in parsed_subjects:
                    envelope = self.artifacts.catalog(subject_refs[index])
                    if (
                        envelope.media_type.split(";", 1)[0].strip().lower()
                        != "application/json"
                    ):
                        raise ApprovalError(
                            "review document pointer subject must be structured JSON"
                        )
                    try:
                        parsed_subjects[index] = json.loads(
                            self.artifacts.read(subject_refs[index])
                        )
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise ApprovalError(
                            "review document pointer subject is invalid JSON"
                        ) from error
                _json_pointer_value(
                    parsed_subjects[index], item.json_pointer
                )

    def _verify_manifest(
        self,
        manifest: ReviewManifest,
        subjects: tuple[tuple[ArtifactEnvelope, bytes], ...],
    ) -> None:
        if len(manifest.subjects) != len(subjects):
            raise ApprovalError("review manifest subject count mismatch")
        for expected, (envelope, raw) in zip(manifest.subjects, subjects, strict=True):
            if expected.artifact_ref != envelope.ref:
                raise ApprovalError("review manifest exact subject mismatch")
            if expected.size_bytes != len(raw) or expected.envelope_sha256 != envelope.content_hash:
                raise ApprovalError("review manifest metadata mismatch")
            if expected.structured_json:
                value = json.loads(raw)
                if tuple(_json_pointers(value)) != expected.json_pointers:
                    raise ApprovalError("review manifest JSON coverage mismatch")

    def _load_request(self, reference: ArtifactRef) -> ApprovalRequest:
        raw = self.artifacts.read(reference)
        try:
            request = ApprovalRequest.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise ApprovalError("ApprovalRequest payload is invalid") from error
        if request.canonical_json() != raw:
            raise ApprovalError("ApprovalRequest payload is not canonical")
        return request

    def _load_manifest(self, reference: ArtifactRef) -> ReviewManifest:
        raw = self.artifacts.read(reference)
        try:
            manifest = ReviewManifest.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise ApprovalError("ReviewManifest payload is invalid") from error
        if manifest.canonical_json() != raw:
            raise ApprovalError("ReviewManifest payload is not canonical")
        return manifest

    def _load_decision(self, reference: ArtifactRef) -> HumanDecision:
        raw = self.artifacts.read(reference)
        try:
            decision = HumanDecision.model_validate_json(raw, strict=True)
        except ValidationError as error:
            raise ApprovalError("HumanDecision payload is invalid") from error
        if decision.canonical_json() != raw:
            raise ApprovalError("HumanDecision payload is not canonical")
        return decision

    @staticmethod
    def _validate_access(
        row: sqlite3.Row,
        access_token: str,
        now: datetime,
        *,
        allow_terminal: bool,
        effective_status: str | None = None,
    ) -> None:
        if not hmac.compare_digest(row["access_token_hash"], _secret_hash(access_token)):
            raise ApprovalAccessDenied("approval access token is invalid")
        status = effective_status or row["status"]
        if allow_terminal and status != "pending":
            return
        if now >= _parse_time(row["access_expires_at"]):
            raise ApprovalAccessDenied("approval access token has expired")
        if not allow_terminal and status != "pending":
            raise ApprovalAlreadyDecided(f"approval request is terminal: {status}")

    @staticmethod
    def _effective_status(row: sqlite3.Row, now: datetime) -> str:
        if (
            row["status"] == "pending"
            and row["expires_at"] is not None
            and now >= _parse_time(row["expires_at"])
        ):
            return "expired"
        return str(row["status"])

    @staticmethod
    def _request_row(connection: sqlite3.Connection, approval_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM approval_requests WHERE approval_id = ?", (approval_id,)
        ).fetchone()
        if row is None:
            raise ApprovalAccessDenied("approval request does not exist")
        return row

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS approval_requests (
                    approval_id TEXT PRIMARY KEY,
                    request_ref_json BLOB NOT NULL,
                    request_ref_sha256 TEXT NOT NULL CHECK(length(request_ref_sha256)=64),
                    status TEXT NOT NULL CHECK(status IN ('pending','decided','expired','cancelled_by_human')),
                    decision_ref_json BLOB,
                    decision_ref_sha256 TEXT,
                    access_token TEXT NOT NULL,
                    access_token_hash TEXT NOT NULL CHECK(length(access_token_hash)=64),
                    csrf_token TEXT NOT NULL,
                    csrf_token_hash TEXT NOT NULL CHECK(length(csrf_token_hash)=64),
                    decision_nonce TEXT NOT NULL,
                    nonce_hash TEXT NOT NULL UNIQUE CHECK(length(nonce_hash)=64),
                    access_expires_at TEXT NOT NULL,
                    expires_at TEXT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    create_request_json BLOB NOT NULL,
                    create_request_sha256 TEXT NOT NULL CHECK(length(create_request_sha256)=64),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approval_decisions (
                    decision_id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    decision_ref_json BLOB NOT NULL,
                    decision_ref_sha256 TEXT NOT NULL CHECK(length(decision_ref_sha256)=64),
                    selected_option TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    FOREIGN KEY (approval_id) REFERENCES approval_requests(approval_id)
                );
                CREATE TABLE IF NOT EXISTS used_nonces (
                    nonce_hash TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    decision_ref_json BLOB NOT NULL,
                    used_at TEXT NOT NULL,
                    FOREIGN KEY (approval_id) REFERENCES approval_requests(approval_id)
                );
                CREATE TABLE IF NOT EXISTS decision_attempts (
                    nonce_hash TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL UNIQUE,
                    binding_json BLOB NOT NULL,
                    binding_sha256 TEXT NOT NULL CHECK(length(binding_sha256)=64),
                    ui_session_id TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    FOREIGN KEY (approval_id) REFERENCES approval_requests(approval_id)
                );
                CREATE TRIGGER IF NOT EXISTS approval_decisions_deny_update
                BEFORE UPDATE ON approval_decisions BEGIN
                    SELECT RAISE(ABORT, 'approval_decisions is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS approval_decisions_deny_delete
                BEFORE DELETE ON approval_decisions BEGIN
                    SELECT RAISE(ABORT, 'approval_decisions is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS used_nonces_deny_update
                BEFORE UPDATE ON used_nonces BEGIN
                    SELECT RAISE(ABORT, 'used_nonces is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS used_nonces_deny_delete
                BEFORE DELETE ON used_nonces BEGIN
                    SELECT RAISE(ABORT, 'used_nonces is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS decision_attempts_deny_update
                BEFORE UPDATE ON decision_attempts BEGIN
                    SELECT RAISE(ABORT, 'decision_attempts is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS decision_attempts_deny_delete
                BEFORE DELETE ON decision_attempts BEGIN
                    SELECT RAISE(ABORT, 'decision_attempts is append-only');
                END;
                """
            )
            connection.execute("PRAGMA foreign_keys = ON")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, isolation_level=None, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection


def _json_pointers(value: object, pointer: str = "") -> list[str]:
    if isinstance(value, dict):
        if not value:
            return [pointer]
        result = []
        for key in sorted(value):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            result.extend(_json_pointers(value[key], pointer + "/" + escaped))
        return result
    if isinstance(value, list):
        if not value:
            return [pointer]
        result = []
        for index, item in enumerate(value):
            result.extend(_json_pointers(item, pointer + f"/{index}"))
        return result
    return [pointer]


def _json_pointer_value(value: object, pointer: str) -> object:
    current = value
    try:
        parts = parse_json_pointer(pointer)
    except ValueError as error:
        raise ApprovalError("JSON pointer is invalid") from error
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        valid_index = part == "0" or (
            bool(part)
            and part[0] in "123456789"
            and all(character in "0123456789" for character in part[1:])
        )
        if isinstance(current, list) and valid_index:
            index = int(part)
            if index < len(current):
                current = current[index]
                continue
        raise ApprovalError("display translation JSON pointer does not exist")
    return current


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_ref(raw: object, expected_hash: object) -> ArtifactRef:
    if type(raw) is not bytes or type(expected_hash) is not str:
        raise ApprovalError("approval reference storage is malformed")
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ApprovalError("approval reference hash mismatch")
    try:
        reference = ArtifactRef.model_validate_json(raw, strict=True)
    except ValidationError as error:
        raise ApprovalError("approval reference storage is invalid") from error
    if reference.canonical_json() != raw:
        raise ApprovalError("approval reference storage is not canonical")
    return reference


def _state_path(value: Path | str) -> Path:
    if not isinstance(value, (Path, str)) or str(value) == ":memory:" or str(value).startswith("file:"):
        raise ValueError("approval state requires an explicit filesystem path")
    return Path(value).expanduser().absolute()


def _now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("time must be timezone aware")
    return current.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


__all__ = [
    "ApprovalAccessDenied",
    "ApprovalAlreadyDecided",
    "ApprovalError",
    "ApprovalExpired",
    "ApprovalIdempotencyConflict",
    "ApprovalLaunch",
    "ApprovalListItem",
    "ApprovalNonceConflict",
    "ApprovalReview",
    "ApprovalService",
    "ApprovalStatusView",
]
