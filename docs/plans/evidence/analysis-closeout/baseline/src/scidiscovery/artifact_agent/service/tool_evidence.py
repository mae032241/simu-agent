"""Run-owned, opt-in evidence obtained by registered tools (never mutable inputs)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from pydantic import Field
from typing import Any, Literal
from ..schema.common import SchemaModel, ContractDiagnostic, Sha256, Identifier
from ...operation_declaration import schema_resource
from ...operation_contract import DiagnosticError, contract_diagnostic
from ...operations.tooling import tool_evidence_ports
from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_json
from ..schema.refs import ArtifactRef
from .run_outputs import InputBindingDescriptor, RunCheckerError
from .run_records import RunStateConflict


class ToolSourceBinding(SchemaModel):
    artifact_ref: ArtifactRef
    port_name: Identifier


class ToolAttempt(SchemaModel):
    attempt_key: Identifier
    tool_name: Identifier
    operation_digest: Sha256
    request_digest: Sha256
    state: Literal["started", "completed", "rejected", "interrupted"]
    result_status: Identifier | None = None
    reason_code: Identifier | None = None
    result_digest: Sha256 | None = None
    read_sources: tuple[Identifier, ...] = Field(default=(), max_length=128)
    sources_digest: Sha256 | None = None
    diagnostics: tuple[ContractDiagnostic, ...] = Field(default=(), max_length=8)


class ToolAttemptProof(SchemaModel):
    bindings: dict[str, ToolSourceBinding] = Field(default_factory=dict, max_length=128)
    attempts: tuple[ToolAttempt, ...] = Field(default=(), max_length=64)


class ToolRecoveryOrigin(ToolAttemptProof):
    source_request_digest: Sha256
    operation_digest: Sha256
    draft_digest: Sha256


class ToolRecoveryProof(ToolRecoveryOrigin):
    # Each origin keeps its own alias and attempt namespace. The existing total
    # attempt budget bounds this flat history; no recursive proof expansion.
    ancestors: tuple[ToolRecoveryOrigin, ...] = Field(default=(), max_length=64)


def _recovery_origins(proof):
    return (proof, *proof.ancestors) if proof is not None else ()


def _recovery_attempt_count(proof):
    return sum(len(origin.attempts) for origin in _recovery_origins(proof))


class ToolEvidenceManifest(ToolAttemptProof):
    records: tuple[dict[str, Any], ...] = Field(default=(), max_length=32)
    recovery: ToolRecoveryProof | None = None


TOOL_EVIDENCE_SCHEMA = schema_resource(ToolEvidenceManifest, "scidiscovery.tool-evidence-manifest.v1")


def calculation_record_content(record):
    """Receipt metadata does not change the historical numerical result format."""
    return record.model_dump(mode="json", exclude={"attempt", "diagnostics"})


def calculation_sources(record, sources):
    """Verify recorded results and their exact bound sources without recalculating.

    This consumes frozen evidence only. It does not admit inputs or call tools.
    """
    from dataclasses import replace
    from ...operation_contract import SemanticRuleViolation
    from ...operations.input_validation import ValidationSources, prior_analysis_sources
    from ..schema.layered_diagnosis import LayeredDiagnosisReport
    prior = prior_analysis_sources(sources)
    current_raw = getattr(sources, "tool_snapshot", None)
    historical = False
    proof_raw = current_raw
    if record.attempt is not None:
        alias = record.attempt.manifest_alias
        if alias == "tool_recovery_manifest":
            if current_raw is None:
                raise SemanticRuleViolation("calculation attempt has no current control manifest")
        elif prior is not None and alias == prior["manifest_alias"]:
            proof_raw = sources[alias]
            historical = True
        else:
            raise SemanticRuleViolation("calculation attempt references an unpaired proof manifest")
    elif prior is not None:
        previous = LayeredDiagnosisReport.model_validate_json(sources[prior["analysis_alias"]])
        historical = any(canonical_json(calculation_record_content(r)) == canonical_json(calculation_record_content(record))
                         for r in previous.calculation_records)
        if historical:
            proof_raw = sources[prior["manifest_alias"]]
    if record.attempt is None and current_raw is not None and not historical:
        raise SemanticRuleViolation("current calculation requires its controlled attempt receipt")
    view = sources
    if historical:
        aliases = prior["source_bindings"]
        descriptors = getattr(sources, "binding_descriptors", {})
        view = ValidationSources({old:sources[new] for old,new in aliases.items()},
            {old:replace(descriptors[new], source_name=old) for old,new in aliases.items()},
            validation_deadline=getattr(sources, "validation_deadline", None))
    if record.attempt is None:
        # Receipt-free legacy results must be unchanged members of the exact
        # sealed prior analysis. Current computed results require tool evidence.
        if record.status == "computed":
            if not historical:
                raise SemanticRuleViolation("computed calculation requires a controlled receipt or exact sealed historical record")
            descriptors = getattr(view, "binding_descriptors", {})
            if any(alias not in descriptors or descriptors[alias].sha256 != digest
                   for alias, digest in record.input_digests.items()):
                raise SemanticRuleViolation("historical calculation source is not exactly bound")
        return view
    proof = ToolEvidenceManifest.model_validate_json(proof_raw)
    if record.attempt.proof_kind == "recovery":
        if proof.recovery is None:
            raise SemanticRuleViolation("calculation recovery proof is missing or changed")
        last_error = None
        for origin in _recovery_origins(proof.recovery):
            try:
                # Alias scopes are never merged across failed Runs. A record
                # must match one complete controlled origin and current bytes.
                descriptors = getattr(sources, "binding_descriptors", {})
                aliases = {}
                for old, binding in origin.bindings.items():
                    matches = [name for name, descriptor in descriptors.items()
                               if descriptor.artifact_ref == binding.artifact_ref]
                    if len(matches) > 1:
                        raise SemanticRuleViolation("recovery source identity is ambiguous")
                    if matches:
                        aliases[old] = matches[0]
                recovery_view = ValidationSources({old:sources[new] for old,new in aliases.items()},
                    {old:replace(descriptors[new], source_name=old) for old,new in aliases.items()},
                    validation_deadline=getattr(sources, "validation_deadline", None))
                return _calculation_attempt_sources(record, origin, recovery_view)
            except SemanticRuleViolation as error:
                last_error = error
        raise last_error
    return _calculation_attempt_sources(record, proof, view)


def _calculation_attempt_sources(record, proof, view):
    from ...operation_contract import SemanticRuleViolation
    attempt = next((a for a in proof.attempts if a.attempt_key == record.attempt.attempt_key), None)
    if attempt is None or attempt.state == "started":
        raise SemanticRuleViolation("calculation attempt has no terminal control evidence")
    if hashlib.sha256(canonical_json(record.request)).hexdigest() != attempt.request_digest:
        raise SemanticRuleViolation("calculation request differs from its recorded attempt")
    bindings = {}
    descriptors = getattr(view, "binding_descriptors", {})
    for alias in attempt.read_sources:
        binding = proof.bindings.get(alias)
        descriptor = descriptors.get(alias)
        if binding is None or descriptor is None or binding.artifact_ref != descriptor.artifact_ref:
            raise SemanticRuleViolation("calculation attempt source is not exactly bound for replay")
        bindings[alias] = binding.model_dump(mode="json")
    if (attempt.sources_digest is not None or attempt.state != "interrupted") and hashlib.sha256(canonical_json(bindings)).hexdigest() != attempt.sources_digest:
        raise SemanticRuleViolation("calculation attempt read-source proof differs")
    if any(alias not in bindings or digest != bindings[alias]["artifact_ref"]["sha256"]
           for alias,digest in record.input_digests.items()):
        raise SemanticRuleViolation("calculation digest does not identify a source actually read")
    if attempt.state == "completed":
        if record.status != attempt.result_status or record.reason_code != attempt.reason_code:
            raise SemanticRuleViolation("calculation outcome differs from the actual tool response")
        if hashlib.sha256(canonical_json(calculation_record_content(record))).hexdigest() != attempt.result_digest:
            raise SemanticRuleViolation("calculation record differs from the actual tool response")
    elif attempt.state == "rejected":
        if (record.status not in {"unavailable", "error"} or not attempt.diagnostics
                or record.reason_code != attempt.diagnostics[0].code):
            raise SemanticRuleViolation("rejected arguments cannot establish an unsupported format or successful result")
    else:
        if record.status != "error" or record.reason_code != "interrupted":
            raise SemanticRuleViolation("an interrupted call has no confirmed tool outcome")
    allowed = {canonical_json(d) for d in attempt.diagnostics}
    if any(canonical_json(d) not in allowed for d in record.diagnostics):
        raise SemanticRuleViolation("calculation diagnostics differ from the controlled attempt")
    if record.status != "computed" and attempt.diagnostics and not record.diagnostics:
        raise SemanticRuleViolation("failed calculation must preserve its controlled failure phase")
    return view


class ToolAttemptLimit(DiagnosticError):
    def __init__(self):
        super().__init__("tool attempt budget exhausted", details=(contract_diagnostic(
            "tool_attempt_limit", phase="tool_execution", affected_action="tool_call",
            message="This Run has reached its bounded tool attempt budget."),))


class ToolEvidenceMixin:
    def source_descriptor(self, value, alias):
        source = next((item for item in value.inputs if item.source_name == alias), None)
        if source is not None:
            envelope = self.artifacts.catalog(source.artifact_ref)
            producer = self.completed_for_output(source.artifact_ref)
            return InputBindingDescriptor(source_name=alias, port_name=source.port_name,
                artifact_ref=source.artifact_ref, media_type=envelope.media_type,
                size_bytes=envelope.size_bytes, sha256=source.artifact_ref.sha256,
                output_name=envelope.labels.get("logical_name"), parent_refs=envelope.parent_refs,
                labels=tuple(envelope.labels.items()), producer_run_id=producer.run_id if producer else None)
        record = next((r for r in self.tool_evidence(value.run_id) if r["alias"] == alias), None)
        if record is None: raise ValueError("unknown controlled source alias")
        ref = ArtifactRef.model_validate(record["artifact_ref"])
        envelope = self.artifacts.catalog(ref)
        return InputBindingDescriptor(source_name=alias, port_name="tool_evidence", artifact_ref=ref,
            media_type=record["media_type"], size_bytes=record["size_bytes"], sha256=ref.sha256,
            output_name=record["metadata"].get("output_name"), parent_refs=envelope.parent_refs,
            labels=tuple(envelope.labels.items()))

    def begin_tool_attempt(self, run_id, tool, arguments):
        from .run_records import timestamp
        value = self._require_running(run_id)
        request = arguments.get("request", arguments) if isinstance(arguments, dict) else arguments
        digest = hashlib.sha256(canonical_json(request)).hexdigest()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, run_id)
            if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
                raise RunStateConflict("candidate no longer accepts tool attempts")
            count = connection.execute("SELECT COUNT(*) FROM run_activity WHERE run_id=? AND activity='tool_attempt_started'", (run_id,)).fetchone()[0]
            recovery = self.recovery_tool_proof(value)
            if count + _recovery_attempt_count(recovery) >= 64:
                raise ToolAttemptLimit()
            record = ToolAttempt(attempt_key=f"attempt_{count+1:03d}", tool_name=tool.name,
                operation_digest=value.operation_digest, request_digest=digest, state="started")
            connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES (?,?,?,?)",
                (run_id,"tool_attempt_started",timestamp(),canonical_json(record)))
        return record.model_dump(mode="json")

    def finish_tool_attempt(self, run_id, attempt, *, sources, result_status=None,
                            reason_code=None, response=None, diagnostics=(), rejected=False):
        from .run_records import timestamp
        value = self._require_running(run_id)
        # Finalize once against the actual receipt budget, before any consumer
        # publishes details. Keep the safe in-process diagnostics for the reply.
        normalized = self._sanitize_diagnostic(value, {"category": "tool_failed",
            "tool_name": attempt["tool_name"], "details": diagnostics}, repairable=False)
        details = tuple(normalized.get("details", ()))[:8]
        record = ToolAttempt.model_validate_json(canonical_json({**attempt,
            "state":"rejected" if rejected else "completed", "result_status":result_status,
            "reason_code":reason_code, "result_digest":hashlib.sha256(canonical_json(response)).hexdigest() if response is not None else None,
            "read_sources":sorted(sources), "sources_digest":hashlib.sha256(canonical_json(sources)).hexdigest(),
            "diagnostics":details,
        }))
        raw = canonical_json(record)
        while len(raw) > 4096 and record.diagnostics:
            record = record.model_copy(update={"diagnostics":record.diagnostics[:-1]})
            raw = canonical_json(record)
        if len(raw)>4096 or ((rejected or result_status != "computed") and not record.diagnostics):
            raise RunCheckerError("tool attempt metadata exceeds its bound", category="checker_failure")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, run_id)
            if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
                raise RunStateConflict("candidate no longer accepts tool attempts")
            previous = connection.execute("SELECT diagnostic_json FROM run_activity WHERE run_id=? AND activity='tool_attempt_started'", (run_id,)).fetchall()
            if not any(json.loads(r[0]) == attempt for r in previous):
                raise RunStateConflict("attempt was not started by this Run")
            completed = connection.execute("SELECT diagnostic_json FROM run_activity WHERE run_id=? AND activity='tool_attempt_completed'", (run_id,)).fetchall()
            if any(json.loads(r[0])["attempt_key"] == record.attempt_key for r in completed):
                raise RunStateConflict("attempt already has a terminal receipt")
            connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES (?,?,?,?)",
                (run_id,"tool_attempt_completed",timestamp(),raw))
        reference = {"manifest_alias":"tool_recovery_manifest", "attempt_key":record.attempt_key}
        return reference, details[:len(record.diagnostics)]

    def record_tool_attempt_read(self, run_id, attempt, sources):
        """Retain actual reads even if execution ends before a terminal response."""
        from .run_records import timestamp
        record = {**attempt, "read_sources":sorted(sources),
                  "sources_digest":hashlib.sha256(canonical_json(sources)).hexdigest()}
        raw = canonical_json(ToolAttempt.model_validate_json(canonical_json(record)))
        if len(raw) > 4096:
            raise RunCheckerError("tool attempt read metadata exceeds its bound", category="checker_failure")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._row(connection, run_id)
            if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
                raise RunStateConflict("candidate no longer accepts read receipts")
            connection.execute("INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES (?,?,?,?)",
                (run_id,"tool_attempt_read",timestamp(),raw))

    def tool_attempts(self, run_id):
        with self._connect() as connection:
            rows = connection.execute("SELECT activity,diagnostic_json FROM run_activity WHERE run_id=? AND activity IN ('tool_attempt_started','tool_attempt_read','tool_attempt_completed') ORDER BY rowid",(run_id,)).fetchall()
        attempts = {}
        for row in rows:
            record = json.loads(row['diagnostic_json']); attempts[record['attempt_key']] = record
        # A receipt without a terminal response proves only an interrupted/unknown call.
        return [{**r, "state":"interrupted"} if r['state']=="started" else r for r in attempts.values()]

    def tool_evidence(self, run_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT record_json FROM run_tool_evidence WHERE run_id=? ORDER BY ordinal", (run_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def evidence_sources(self, run_id: str, only_alias: str | None = None):
        contents = {}; descriptors = {}
        for record in self.tool_evidence(run_id):
            if only_alias is not None and record['alias'] != only_alias:
                continue
            ref = ArtifactRef.model_validate(record['artifact_ref'])
            try:
                raw = self.artifacts.read(ref)
                envelope = self.artifacts.catalog(ref)
            except Exception as error:
                raise RunCheckerError('tool evidence is unavailable', category='integrity_failure') from error
            alias = record['alias']
            if hashlib.sha256(raw).hexdigest() != ref.sha256:
                raise RunCheckerError('tool evidence changed', category='integrity_failure')
            contents[alias] = raw
            descriptors[alias] = self.source_descriptor(self.status(run_id), alias)
        return contents, descriptors

    def read_tool_evidence(self, value, alias):
        contents, _ = self.evidence_sources(value.run_id, only_alias=alias)
        if alias in contents:
            return contents[alias]
        raise ValueError('unknown controlled evidence alias')

    def prior_source_bindings(self, value):
        from ...operations.input_validation import ValidationSources
        contents = {i.source_name:self.artifacts.read(i.artifact_ref) for i in value.inputs
                    if i.port_name in {'prior_analysis_manifest', 'recovery_manifest'}}
        descriptors = {i.source_name:self.source_descriptor(value, i.source_name) for i in value.inputs}
        return ValidationSources(contents, descriptors).prior_source_bindings

    def accept_tool_evidence(self, run_id: str, *, tool_name: str, allowed_ports: tuple[str, ...],
                             raw: bytes, media_type: str, metadata: dict, source_alias: str = 'execution_result',
                             derived_from: tuple[str, ...] = ()) -> dict:
        value = self._require_running(run_id)
        compiled = self._compiled(value)
        ports = tool_evidence_ports(compiled)
        if 'tool_evidence' not in allowed_ports or 'tool_evidence' not in ports:
            raise ValueError('tool evidence capability is not declared')
        if derived_from:
            # Only registered tools reach this callback. Derived evidence has
            # exact current input/evidence parents; it is not a solver product.
            derived_refs = tuple(self.source_descriptor(value, alias).artifact_ref for alias in derived_from)
            source_ref = derived_refs[0]
            metadata = {**metadata, 'derived_from': list(derived_from)}
        else:
            source = next((item for item in value.inputs if item.source_name == source_alias), None)
            if source is None or source.artifact_ref.schema_id != 'scidiscovery.execution-result':
                raise ValueError('tool evidence needs the bound execution result')
            source_ref = source.artifact_ref
            derived_refs = ()
        parent_refs = [item.artifact_ref for item in value.inputs]
        for ref in derived_refs:
            if ref not in parent_refs:
                parent_refs.append(ref)
        port = ports['tool_evidence']
        if len(raw) > min(port.max_item_bytes, 32 * 1024 * 1024):
            raise ValueError('file_bytes')
        if len(canonical_json(metadata)) > 8192:
            raise ValueError('metadata_bytes')
        key = hashlib.sha256(canonical_json({'sha256':hashlib.sha256(raw).hexdigest(), 'metadata':metadata, 'source':source_ref.model_dump(mode='json')})).hexdigest()
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = self._row(connection, run_id)
            if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
                raise RunStateConflict('Run no longer accepts tool evidence')
            existing = connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=? AND evidence_key=?',(run_id,key)).fetchone()
            if existing:
                return json.loads(existing[0])
            records = [json.loads(r[0]) for r in connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=?',(run_id,))]
            if len(records) >= min(port.max_items,32) or sum(r['size_bytes'] for r in records)+len(raw) > min(port.collection.max_total_bytes,256*1024*1024):
                raise ValueError('evidence_budget')
            if metadata.get('output_name') and any(r['metadata'].get('output_name')==metadata['output_name'] for r in records):
                raise ValueError('ambiguous_mapping')
            reserved = {r['alias'] for r in records}
            for item in value.inputs:
                if item.port_name == 'recovery_manifest':
                    reserved.update(r['alias'] for r in json.loads(self.artifacts.read(item.artifact_ref)).get('records', ()))
            ordinal=len(records)+1
            number=ordinal
            while f'tool_evidence_{number:03d}' in reserved:
                number+=1
            alias=f'tool_evidence_{number:03d}'
            artifact=self.artifacts.register(raw,ArtifactRegistration(kind=port.kind,schema_id=port.schema_id,
                payload_schema_version=1,media_type=media_type,creator=self.service_actor,
                parent_refs=tuple(parent_refs),
                labels={'operation_id':value.operation_id,'operation_digest':value.operation_digest,'operation_version':value.operation_version,
                        'operation_output_port':'tool_evidence','tool_name':tool_name,'tool_producer_run':run_id,
                        **({'analysis_artifact_kind':metadata['kind']} if metadata.get('kind') in
                           {'calculation_record', 'calculation_details', 'analysis_script', 'analysis_derived'} else {}),
                        **({'logical_name':metadata['output_name']} if metadata.get('output_name') else {})},confidentiality='run_private'),
                idempotency_key=f'run:{run_id}:tool:{key}').ref
            record={'alias':alias,'artifact_ref':artifact.model_dump(mode='json'),'source_ref':source_ref.model_dump(mode='json'),
                    'media_type':media_type,'size_bytes':len(raw),'metadata':metadata,'tool_name':tool_name}
            connection.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',(run_id,ordinal,key,canonical_json(record),alias))
        self._refresh_evidence_schema(run_id)
        return record

    def _refresh_evidence_schema(self, run_id):
        from .run_assignment import result_schema_json
        value=self.status(run_id); compiled=self._compiled(value)
        workspace=self.backend.open(run_id)
        # The schema is a generated projection, never a replacement for the input bindings.
        mapping = self.validation_source_ports(value)
        schema=result_schema_json(compiled,input_source_ports=mapping)
        from .local_workspace import write_control_workspace_file
        write_control_workspace_file(workspace.root, Path('schema/result.schema.json'), schema, replace=True, mode=0o400)

    def _evidence_snapshot(self, run_id):
        value = self.status(run_id)
        records = self.tool_evidence(run_id)
        bindings = {item.source_name:{"schema_version":1,"artifact_ref":item.artifact_ref.model_dump(mode="json"), "port_name":item.port_name} for item in value.inputs}
        bindings.update({r['alias']:{"schema_version":1,"artifact_ref":r['artifact_ref'], "port_name":"tool_evidence"} for r in records})
        recovery = self.recovery_tool_proof(value)
        attempts = self.tool_attempts(run_id)
        if len(attempts) + _recovery_attempt_count(recovery) > 64:
            raise RunCheckerError('tool attempt proof budget exceeded')
        return canonical_json({'schema_version':1,'records':records,'bindings':bindings,
            'attempts':attempts, 'recovery':recovery})

    def recovery_tool_proof(self, value):
        """Read only the original verified recovery store, never Worker copies."""
        with self._connect() as connection:
            row = self._row(connection, value.run_id)
            source_id = row['draft_from_run_id'] or row['resume_from_run_id']
        if not source_id or not tool_evidence_ports(self._compiled(value)):
            return None
        source = self.status(source_id)
        manifest = source.recovery_draft
        if not manifest:
            return None
        draft = self._verify_draft(source, manifest['draft_digest'])
        layout = next((item for item in draft.files if item.relative_path == 'analysis-recovery.json'), None)
        path = 'tool-evidence.json'
        if layout and layout.size_bytes <= 64 * 1024:
            if json.loads((draft.root / layout.relative_path).read_bytes()).get('format') == 'analysis-work-v1':
                path = 'output/tool-evidence.json'
        entry = next((item for item in draft.files if item.relative_path == path), None)
        if entry is None:
            return None
        if entry.size_bytes > 1024 * 1024:
            raise RunCheckerError('recovery tool proof exceeds limit', category='integrity_failure')
        raw = (draft.root / entry.relative_path).read_bytes()
        if len(raw) != entry.size_bytes or hashlib.sha256(raw).hexdigest() != entry.sha256:
            raise RunCheckerError('recovery tool proof changed', category='integrity_failure')
        previous = ToolEvidenceManifest.model_validate_json(raw)
        if previous.attempts:
            if len(previous.attempts) + _recovery_attempt_count(previous.recovery) > 64:
                raise RunCheckerError('tool attempt proof budget exceeded')
            ancestors = tuple(ToolRecoveryOrigin.model_validate(
                origin.model_dump(exclude={"ancestors"}))
                for origin in _recovery_origins(previous.recovery))
            return ToolRecoveryProof(bindings=previous.bindings, attempts=previous.attempts,
                source_request_digest=source.request_digest, operation_digest=source.operation_digest,
                draft_digest=draft.digest, ancestors=ancestors)
        return previous.recovery

    def _prepare_evidence_snapshot(self, run_id):
        value=self.status(run_id)
        if not tool_evidence_ports(self._compiled(value)):
            return
        workspace=self.backend.open(run_id)
        raw=self._evidence_snapshot(run_id)
        if len(raw)>1024*1024:
            raise RunCheckerError('tool evidence manifest exceeds limit')
        from .local_workspace import write_control_workspace_file
        path=Path('output/tool-evidence.json')
        write_control_workspace_file(workspace.root, path, raw, replace=(workspace.root/path).exists(), mode=0o400)

    def _evidence_manifest(self, value):
        records=self.tool_evidence(value.run_id)
        compiled=self._compiled(value)
        ports=tool_evidence_ports(compiled)
        if not ports: return None
        port=ports['recovery_manifest_output']
        return self.artifacts.register(self._evidence_snapshot(value.run_id),ArtifactRegistration(
            kind=port.kind,schema_id=port.schema_id,payload_schema_version=1,media_type='application/json',creator=self.service_actor,
            parent_refs=tuple(item.artifact_ref for item in value.inputs)+tuple(ArtifactRef.model_validate(r['artifact_ref']) for r in records),
            labels={'operation_id':value.operation_id,'operation_digest':value.operation_digest,'operation_version':value.operation_version,
                    'operation_output_port':'recovery_manifest_output','tool_producer_run':value.run_id},confidentiality='run_private'),
            idempotency_key=f'run:{value.run_id}:tool-manifest:{hashlib.sha256(self._evidence_snapshot(value.run_id)).hexdigest()}').ref

    def evidence_output_refs(self, value):
        if value.state!='completed' or value.output_ref is None:
            return []
        refs=[(r['alias'],ArtifactRef.model_validate(r['artifact_ref'])) for r in self.tool_evidence(value.run_id)]
        # Read the registered parent rather than rebuilding it with a new installed contract.
        for ref in self.artifacts.catalog(value.output_ref).parent_refs:
            if (ref.schema_id=='scidiscovery.tool-evidence-manifest.v1'
                    and self.artifacts.catalog(ref).labels.get('tool_producer_run') == value.run_id):
                refs.append(('recovery_manifest',ref))
        return refs

    def tool_io_budget(self, run_id, *, used_bytes=0, used_seconds=0.0, reserve=False):
        from datetime import datetime, timezone
        self._require_running(run_id)
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            rows = connection.execute("SELECT activity FROM run_activity WHERE run_id=? AND activity LIKE 'evidence_io:%'", (run_id,)).fetchall()
            consumed_bytes = sum(int(r[0].split(':')[1]) for r in rows)
            consumed_ms = sum(int(r[0].split(':')[2]) for r in rows)
            remaining = {'remaining_bytes': max(0, 256*1024*1024-consumed_bytes),
                         'remaining_seconds': max(0, 120-consumed_ms/1000)}
            if reserve:
                # Reserve before remote I/O. A crashed call conservatively spends its
                # reservation; another process cannot concurrently borrow that budget.
                used_bytes = remaining['remaining_bytes']
                used_seconds = remaining['remaining_seconds']
            if used_bytes or used_seconds:
                connection.execute('INSERT INTO run_activity(run_id,activity,recorded_at,diagnostic_json) VALUES (?,?,?,?)',
                    (run_id, 'evidence_io:%d:%d' % (used_bytes, round(used_seconds*1000)),
                     datetime.now(timezone.utc).isoformat(), None))
        return remaining if reserve else {
            'remaining_bytes': max(0, remaining['remaining_bytes']-used_bytes),
            'remaining_seconds': max(0, remaining['remaining_seconds']-used_seconds)}

    def adopt_tool_evidence(self, run_id):
        value=self.status(run_id)
        if not tool_evidence_ports(self._compiled(value)):
            return
        with self._connect() as connection:
            source_id=value.draft_from_run_id or self._row(connection,run_id)["resume_from_run_id"]
        if not source_id:
            return
        source=self.status(source_id)
        previous=self.tool_evidence(source_id)
        if not previous:
            return
        original=next((i.artifact_ref for i in source.inputs if i.port_name=='execution_result'),None)
        current=next((i.artifact_ref for i in value.inputs if i.port_name=='execution_result'),None)
        if source.instance_id!=value.instance_id:
            raise RunCheckerError('preserved tool evidence belongs to another execution',category='integrity_failure')
        port = tool_evidence_ports(self._compiled(value)).get('tool_evidence')
        if port is None or len(previous) > port.max_items or sum(r['size_bytes'] for r in previous) > port.collection.max_total_bytes:
            raise RunCheckerError('preserved evidence exceeds this operation capability',category='integrity_failure')
        available_refs = {item.artifact_ref for item in value.inputs}
        for record in previous:
            ref=ArtifactRef.model_validate(record['artifact_ref'])
            try:
                raw=self.artifacts.read(ref)
            except Exception as error:
                raise RunCheckerError('preserved evidence bytes unavailable', category='integrity_failure') from error
            if hashlib.sha256(raw).hexdigest()!=ref.sha256:
                raise RunCheckerError('preserved evidence bytes changed',category='integrity_failure')
            derived = record['metadata'].get('derived_from', ())
            if derived:
                parents = tuple(self.source_descriptor(source, alias).artifact_ref for alias in derived)
                origin_matches = all(ref in available_refs for ref in parents) and record['source_ref'] == parents[0].model_dump(mode='json')
            else:
                origin_matches = original is not None and original == current and record['source_ref'] == original.model_dump(mode='json')
            if len(raw) > port.max_item_bytes or not origin_matches:
                raise RunCheckerError('preserved evidence receipt differs from its origin',category='integrity_failure')
            if record['alias'] in {item.source_name for item in value.inputs}:
                raise RunCheckerError('preserved evidence alias conflicts with current input',category='integrity_failure')
            key = hashlib.sha256(canonical_json({'sha256':ref.sha256,
                'metadata':record['metadata'], 'source':record['source_ref']})).hexdigest()
            # Adopt the exact receipt and CAS reference. Re-registering these bytes
            # would falsely make the new Run their original collecting producer.
            with self._connect() as connection:
                connection.execute('BEGIN IMMEDIATE')
                row = self._row(connection,run_id)
                if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
                    raise RunStateConflict('Run no longer accepts preserved evidence')
                found = connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=? AND evidence_key=?',(run_id,key)).fetchone()
                if found:
                    if json.loads(found[0]) != record:
                        raise RunCheckerError('preserved receipt conflicts with current receipt',category='integrity_failure')
                    available_refs.add(ref)
                    continue
                ordinal = connection.execute('SELECT COUNT(*) FROM run_tool_evidence WHERE run_id=?',(run_id,)).fetchone()[0]+1
                connection.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',
                    (run_id,ordinal,key,canonical_json(record),record['alias']))
            available_refs.add(ref)

    def validation_source_ports(self, value):
        """Expected source wiring comes from bindings/receipts, never descriptors."""
        ports={item.source_name:item.port_name for item in value.inputs}
        records=self.tool_evidence(value.run_id)
        ports.update({r['alias']:'tool_evidence' for r in records})
        if tool_evidence_ports(self._compiled(value)):
            ports['tool_recovery_manifest']='recovery_manifest_output'
        return ports
