BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS artifact_envelopes (
    artifact_id TEXT PRIMARY KEY,
    payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    kind TEXT NOT NULL,
    schema_id TEXT NOT NULL,
    payload_schema_version INTEGER NOT NULL CHECK(payload_schema_version >= 1),
    media_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    envelope_json BLOB NOT NULL,
    envelope_sha256 TEXT NOT NULL CHECK(length(envelope_sha256) = 64),
    UNIQUE (artifact_id, payload_sha256, kind, schema_id)
);

CREATE TABLE IF NOT EXISTS artifact_links (
    source_artifact_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK(relation IN ('parent', 'supersedes', 'task')),
    position INTEGER NOT NULL CHECK(position >= 0),
    target_artifact_id TEXT NOT NULL,
    target_sha256 TEXT NOT NULL CHECK(length(target_sha256) = 64),
    target_kind TEXT NOT NULL,
    target_schema_id TEXT NOT NULL,
    PRIMARY KEY (source_artifact_id, relation, position),
    UNIQUE (source_artifact_id, relation, target_artifact_id),
    FOREIGN KEY (source_artifact_id)
        REFERENCES artifact_envelopes(artifact_id),
    FOREIGN KEY (target_artifact_id, target_sha256, target_kind, target_schema_id)
        REFERENCES artifact_envelopes(artifact_id, payload_sha256, kind, schema_id)
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    request_json BLOB NOT NULL,
    request_sha256 TEXT NOT NULL CHECK(length(request_sha256) = 64),
    artifact_id TEXT NOT NULL UNIQUE,
    response_json BLOB NOT NULL,
    response_sha256 TEXT NOT NULL CHECK(length(response_sha256) = 64),
    created_at TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifact_envelopes(artifact_id)
);

CREATE INDEX IF NOT EXISTS artifact_envelopes_catalog_idx
    ON artifact_envelopes(kind, schema_id, created_at, artifact_id);
CREATE INDEX IF NOT EXISTS artifact_links_target_idx
    ON artifact_links(target_artifact_id);

CREATE TRIGGER IF NOT EXISTS artifact_envelopes_deny_update
BEFORE UPDATE ON artifact_envelopes BEGIN
    SELECT RAISE(ABORT, 'artifact_envelopes is append-only');
END;
CREATE TRIGGER IF NOT EXISTS artifact_envelopes_deny_delete
BEFORE DELETE ON artifact_envelopes BEGIN
    SELECT RAISE(ABORT, 'artifact_envelopes is append-only');
END;

CREATE TRIGGER IF NOT EXISTS artifact_links_deny_update
BEFORE UPDATE ON artifact_links BEGIN
    SELECT RAISE(ABORT, 'artifact_links is append-only');
END;
CREATE TRIGGER IF NOT EXISTS artifact_links_deny_delete
BEFORE DELETE ON artifact_links BEGIN
    SELECT RAISE(ABORT, 'artifact_links is append-only');
END;

CREATE TRIGGER IF NOT EXISTS idempotency_records_deny_update
BEFORE UPDATE ON idempotency_records BEGIN
    SELECT RAISE(ABORT, 'idempotency_records is append-only');
END;
CREATE TRIGGER IF NOT EXISTS idempotency_records_deny_delete
BEFORE DELETE ON idempotency_records BEGIN
    SELECT RAISE(ABORT, 'idempotency_records is append-only');
END;

PRAGMA user_version = 1;
COMMIT;
