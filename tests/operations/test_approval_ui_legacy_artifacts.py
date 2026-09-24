"""UI-only reads of immutable Task-era envelopes do not reopen Task control."""

import hashlib
import http.client
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlencode, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.app import ApprovalUI
from scidiscovery.artifact_agent.approval_ui.legacy_artifacts import (
    LegacyUIArtifactEnvelope, UIReadableArtifactRegistry,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.approval import ApprovalOption
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.storage.sqlite import RegistryIntegrityError


def _legacy_envelope(database, envelope, *, task_ref=None, confidentiality=None):
    value = envelope.model_dump(mode="python")
    value.update(artifact_id="legacy_" + envelope.artifact_id, task_ref=task_ref,
        confidentiality=confidentiality or envelope.confidentiality)
    legacy = LegacyUIArtifactEnvelope.model_validate(value)
    raw = legacy.canonical_json()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO artifact_envelopes (artifact_id, payload_sha256, size_bytes, kind, "
            "schema_id, payload_schema_version, media_type, created_at, envelope_json, envelope_sha256) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (legacy.artifact_id, legacy.sha256, legacy.size_bytes, legacy.kind,
                legacy.schema_id, legacy.payload_schema_version, legacy.media_type,
                legacy.created_at, raw, hashlib.sha256(raw).hexdigest()),
        )
    return legacy


def _request(base, method, path, *, form=None):
    parsed = urlparse(base)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    headers = {}
    payload = None
    if form is not None:
        payload = urlencode(form)
        headers = {"Origin": base, "Content-Type": "application/x-www-form-urlencoded"}
    connection.request(method, path, body=payload, headers=headers)
    response = connection.getresponse()
    status, raw = response.status, response.read()
    connection.close()
    return status, raw


def test_legacy_approval_is_readable_only_in_ui_and_cannot_record_a_new_decision(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32))
    subject = runtime.artifacts.register(b"{}", ArtifactRegistration(
        kind="test_subject", schema_id="test.subject.v1", payload_schema_version=1,
        media_type="application/json", creator=runtime.actor), idempotency_key="legacy-ui:subject")
    launch = runtime.approvals.create_request(
        approval_id="legacy_ui_review", kind="test_review", subject_refs=(subject.ref,),
        question="Inspect the frozen subject?", options=(
            ApprovalOption(option_id="approve", label="Approve", description="Approve it.", requires_rationale=False),
            ApprovalOption(option_id="reject", label="Reject", description="Reject it.", requires_rationale=False)),
        requested_by=runtime.actor, idempotency_key="legacy-ui:approval")
    review = runtime.approvals.review(launch.approval_id, access_token=launch.access_token)
    artifact_database = tmp_path / "state/database/artifact_agent.sqlite3"
    approvals_database = tmp_path / "state/database/approvals.sqlite3"
    old_request = runtime.artifacts.catalog(launch.approval_request_ref)
    legacy_request = _legacy_envelope(artifact_database, old_request)
    with sqlite3.connect(approvals_database) as connection:
        reference = legacy_request.ref.canonical_json()
        connection.execute("UPDATE approval_requests SET request_ref_json=?, request_ref_sha256=? WHERE approval_id=?",
            (reference, hashlib.sha256(reference).hexdigest(), launch.approval_id))
    with pytest.raises(RegistryIntegrityError, match="envelope schema validation failed"):
        runtime.artifacts.catalog(legacy_request.ref)

    runtime.artifacts.registry = UIReadableArtifactRegistry(artifact_database)
    assert runtime.artifacts.catalog(legacy_request.ref).canonical_json() == legacy_request.canonical_json()
    ui = ApprovalUI(runtime.approvals)
    base = ui.start()
    try:
        status, _ = _request(base, "GET", "/")
        assert status == 200
        status, page = _request(base, "GET", launch.review_path)
        assert status == 200 and "该审批入口已停用".encode() in page
        assert b"submit-decision" not in page
        status, _ = _request(base, "POST", f"/review/{launch.approval_id}/decision", form={
            "token": launch.access_token, "csrf": review.csrf_token,
            "nonce": review.decision_nonce, "selected_option": "approve",
            "rationale": "", "confirm": "confirm"})
        assert status == 409
        assert runtime.approvals.status(launch.approval_id).status == "pending"
        # Archived requests live outside the active registry; frozen review
        # rendering must not attempt another lookup there.
        monkeypatch.setattr(ui, "_approval_frozen", lambda _: True)
        original_catalog = runtime.artifacts.catalog
        def catalog_subject_only(ref):
            if ref == legacy_request.ref:
                raise AssertionError("frozen review consulted active request registry")
            return original_catalog(ref)
        monkeypatch.setattr(runtime.artifacts, "catalog", catalog_subject_only)
        status, page = _request(base, "GET", launch.review_path)
        assert status == 200 and b"submit-decision" not in page
    finally:
        ui.stop()


def test_ui_legacy_decoder_checks_exact_bytes_and_task_private_provenance(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=tmp_path / "state")
    current = runtime.artifacts.register(b"legacy", ArtifactRegistration(
        kind="test_subject", schema_id="test.subject.v1", payload_schema_version=1,
        media_type="text/plain", creator=runtime.actor), idempotency_key="legacy-ui:private")
    database = tmp_path / "state/database/artifact_agent.sqlite3"
    legacy = _legacy_envelope(database, current, task_ref=current.ref, confidentiality="task_private")
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM artifact_envelopes WHERE artifact_id=?",
            (legacy.artifact_id,)).fetchone()
    decoded = UIReadableArtifactRegistry._decode_envelope_row(row)
    assert decoded.task_ref == current.ref and decoded.confidentiality == "task_private"
    assert decoded.content_hash == legacy.content_hash
    with pytest.raises(RegistryIntegrityError, match="hash mismatch"):
        UIReadableArtifactRegistry._decode_envelope_row({**dict(row), "envelope_sha256": "0" * 64})
    malformed = {**json.loads(row["envelope_json"]), "unexpected": True}
    raw = canonical_json(malformed)
    with pytest.raises(RegistryIntegrityError, match="legacy envelope schema validation failed"):
        UIReadableArtifactRegistry._decode_envelope_row({**dict(row), "envelope_json": raw,
            "envelope_sha256": hashlib.sha256(raw).hexdigest()})
    assert "task_ref" not in current.model_dump()
