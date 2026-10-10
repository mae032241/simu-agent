"""Stream scientific files through the shared snapshot, CAS and receipt boundary."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory

from ...agent_execution_settings import AttachmentSettings
from ...operations.spec import json_projection
from ...operation_contract import ToolInputError
from ...plugin_runtime.workspace import _open_workspace_parent
from ..schema.artifact import ArtifactRegistration
from ..schema.refs import ArtifactRef
from ..schema.common import canonical_json
from .run_records import RunStateConflict


@contextmanager
def _source(workspace, name):
    path = Path(name)
    if path.is_absolute() or len(path.parts) < 2 or path.parts[0] != 'scratch' or '..' in path.parts:
        raise ToolInputError("attachment_publication_invalid", 'Publish files below scratch/. Move extra output files there; output/ holds only result.json and runtime receipts.')
    descriptors, parent = _open_workspace_parent(workspace, path)
    try:
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError as error:
            raise ToolInputError("attachment_file_missing", "Finish writing the attachment below scratch/ before publication.") from error
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ToolInputError("attachment_publication_invalid", 'Attachment is not a regular file')
            yield stream
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def snapshot_file(source, target, settings, check_budget, *, total=0, guard=None, on_read=None):
    """One chunk in memory; observable mutation is a delivery gap, not a retry."""
    before = os.fstat(source.fileno())
    if before.st_size > settings.max_item_bytes or total + before.st_size > settings.max_total_bytes:
        raise ToolInputError("attachment_publication_invalid", 'Attachment byte budget exceeded')
    digest, size = hashlib.sha256(), 0
    with target.open('xb') as output:
        while True:
            read_bytes = settings.chunk_bytes
            if on_read is not None:
                check_budget()
                # Exact IO allowance: no extra EOF probe at the boundary. The
                # final fstat below still rejects a truncated or growing source.
                read_bytes = min(read_bytes, settings.max_item_bytes - size,
                    settings.max_total_bytes - total - size)
                if read_bytes <= 0:
                    break
            chunk = source.read(read_bytes)
            if not chunk:
                break
            if on_read is not None:
                on_read(len(chunk))
            check_budget()
            size += len(chunk)
            if size > settings.max_item_bytes or total + size > settings.max_total_bytes:
                raise ToolInputError("attachment_publication_invalid", 'Attachment grew beyond the byte budget')
            if guard is not None:
                guard.feed(chunk)
            digest.update(chunk)
            output.write(chunk)
        if guard is not None:
            guard.finish()
    after = os.fstat(source.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ToolInputError("attachment_publication_invalid", 'Attachment changed while being published')
    return digest.hexdigest(), size


def attachment_item(runs, run, path, digest, size, media, metadata, aliases, *, task_scope_restricted=False):
    sources = tuple(dict.fromkeys(runs.source_descriptor(run, alias).artifact_ref for alias in aliases))
    from .artifact_capture import require_scientific_aliases
    require_scientific_aliases(runs, run, aliases)
    metadata = {**metadata, 'derived_from': list(aliases)}
    if metadata.get('capture_mode') == 'auto_captured' and metadata.get('kind') == 'scientific_attachment':
        from ...operations.tooling import reference_policy
        from .scientific_usage import scientific_use_restricted
        restricted = task_scope_restricted or (bool(sources) and scientific_use_restricted(runs,
            sources, policy=reference_policy(runs._compiled(run))))
        metadata['scientific_claim_admissible'] = bool(sources) and metadata.get('provenance_status') != 'unknown' and not restricted
    identity = {key: value for key, value in metadata.items() if key != 'derived_from'}
    if metadata.get('capture_mode') == 'auto_captured':
        identity.pop('purpose', None)
    policy = (run.recovery_policy or {}).get('capture')
    key = hashlib.sha256(canonical_json({'sha256': digest, 'metadata': identity,
        **({'capture_policy_digest': policy['digest']} if policy and metadata.get('capture_mode') == 'auto_captured' else {}),
        'sources': sorted((ref.model_dump(mode='json') for ref in sources), key=canonical_json),
        'media_type': media, 'output_port': 'attachments',
        **({'capture_contract': json_projection(runs._compiled(run).spec.artifact_capture)}
           if metadata.get('capture_mode') == 'auto_captured' else {})})).hexdigest()
    return dict(path=path, digest=digest, size=size, media=media, metadata=metadata, sources=sources, key=key)


def retain_attachments(runs, run, staged, settings, check_budget, *, inventory=None, temporary=None):
    """Register outside the lock; receipts, index and direct edges commit together."""
    from ...operations.tooling import reference_policy, tool_evidence_ports
    from .scientific_usage import scientific_use_restricted, retain_source_edges, _context_identity
    from ...reference_tools import ReferencePolicy
    port = tool_evidence_ports(runs._compiled(run)).get('attachments')
    if port is None:
        raise ToolInputError('attachment_publication_invalid', 'This task has no attachment capability')
    source_policy = reference_policy(runs._compiled(run))
    edge_context = _context_identity(runs, source_policy or ReferencePolicy())
    staged = list({item['key']: item for item in staged}.values())
    recovery, attempts = runs.recovery_tool_proof(run), runs.tool_attempts(run.run_id)
    def check_receipt_budget(existing):
        records = list(existing.values())
        attachments = [r for r in records if r.get('output_port') == 'attachments']
        new = [item for item in staged if item['key'] not in existing]
        if (any(item['size'] > settings.max_item_bytes for item in new)
                or len(attachments) + len(new) > settings.max_files
                or sum(r.get('record_type') != 'reference_access' for r in records) + len(new) > 128
                or sum(r['size_bytes'] for r in attachments) + sum(item['size'] for item in new) > settings.max_total_bytes):
            raise ToolInputError('attachment_publication_invalid', 'Attachment count or total byte budget exceeded')
    with runs._connect() as connection:
        known = {row[0]: json.loads(row[1]) for row in connection.execute(
            'SELECT evidence_key,record_json FROM run_tool_evidence WHERE run_id=?', (run.run_id,))}
    check_receipt_budget(known)
    prepared = {}
    def register(item):
        if item['key'] in known:
            return ArtifactRef.model_validate(known[item['key']]['artifact_ref'])
        unknown = item['metadata'].get('provenance_status') == 'unknown' or item['metadata'].get('kind') == 'capture_inventory'
        restricted = (item['metadata'].get('scientific_claim_admissible') is False or
            (scientific_use_restricted(runs, item['sources'], policy=source_policy) if item['sources'] and not unknown else False))
        parents = tuple(dict.fromkeys((*[binding.artifact_ref for binding in run.inputs], *item['sources'])))
        ref = runs.artifacts.register_file(item['path'], ArtifactRegistration(kind=port.kind,
            schema_id=port.schema_id, payload_schema_version=1, media_type=item['media'], creator=runs.service_actor,
            parent_refs=parents, labels={'operation_id':run.operation_id, 'operation_version':run.operation_version,
                'operation_digest':run.operation_digest, 'operation_output_port':'attachments',
                'tool_name':'worker_publish_files', 'tool_producer_run':run.run_id, 'source_origin':'agent_authored',
                **({'scientific_claim_admissible':'false'} if restricted or unknown else {})},
            confidentiality='run_private'), expected_sha256=item['digest'], expected_size=item['size'],
            idempotency_key=f"run:{run.run_id}:attachment:{item['key']}", chunk_bytes=settings.chunk_bytes,
            check_budget=check_budget).ref
        prepared[item['key']] = ref
        return ref
    for item in staged:
        check_budget()
        register(item)
    index_key = None
    predicted = {key:record['alias'] for key,record in known.items()}
    if inventory is not None:
        reserved = {record['alias'] for record in known.values()} | {binding.source_name for binding in run.inputs}
        ordinal = len(known)
        for item in staged:
            if item['key'] not in predicted:
                ordinal += 1
                number = ordinal
                while f'attachment_{number:03d}' in reserved:
                    number += 1
                predicted[item['key']] = f'attachment_{number:03d}'
                reserved.add(predicted[item['key']])
        for entry in inventory['entries']:
            key = entry.get('publication_key')
            if key:
                entry['artifact_ref'] = (ArtifactRef.model_validate(known[key]['artifact_ref']) if key in known else prepared[key]).model_dump(mode='json')
                entry['reference'] = predicted[key]
        # The immutable control map remains receipt metadata. Original readers
        # see navigation aliases and coverage, never internal Refs or keys.
        def public_entry(entry):
            # New source observation identity is private, including nested keys.
            if isinstance(entry, dict):
                return {key:public_entry(value) for key,value in entry.items()
                    if key not in {'artifact_ref','publication_key','sha256','private_source'}}
            if isinstance(entry, list):
                return [public_entry(value) for value in entry]
            return entry
        public = public_entry(inventory)
        raw = canonical_json(public)
        if len(raw) > 1048576:
            raise ToolInputError('capture_inventory_limit', 'Capture index exceeds its encoded budget; narrow the declared batch')
        target = Path(temporary) / 'capture-index'
        target.write_bytes(raw)
        item = attachment_item(runs, run, target, hashlib.sha256(raw).hexdigest(), len(raw), 'application/json',
            {'kind':'capture_inventory', 'file_name':'capture-index.json', 'purpose':'Capture navigation only',
             'origin':'control_inventory', 'capture_mode':'auto_captured', 'provenance_status':'unknown',
             'scientific_claim_admissible':False, 'capture_map':inventory}, ())
        index_key = item['key']
        staged.append(item)
        check_receipt_budget(known)
        register(item)
    result, committed = [], {}
    with runs._connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = runs._row(connection, run.run_id)
        if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
            raise RunStateConflict('Run no longer accepts scientific attachments')
        stored = connection.execute('SELECT evidence_key,record_json FROM run_tool_evidence WHERE run_id=? ORDER BY ordinal', (run.run_id,)).fetchall()
        existing = {r[0]:json.loads(r[1]) for r in stored}
        records = list(existing.values())
        check_receipt_budget(existing)
        for item in staged:
            check_budget()
            key, metadata, sources = item['key'], item['metadata'], item['sources']
            if key in existing:
                record = existing[key]
            else:
                ordinal = len(records) + 1
                number = ordinal
                reserved = {r['alias'] for r in records} | {binding.source_name for binding in run.inputs}
                while f'attachment_{number:03d}' in reserved:
                    number += 1
                alias = f'attachment_{number:03d}'
                record = {'alias':alias, 'artifact_ref':prepared[key].model_dump(mode='json'),
                    'source_ref':sources[0].model_dump(mode='json') if sources else None,
                    'media_type':item['media'], 'size_bytes':item['size'], 'metadata':metadata,
                    'tool_name':'worker_publish_files', 'output_port':'attachments', 'publication_key':key}
                connection.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',
                    (run.run_id, ordinal, key, canonical_json(record), alias))
                records.append(record)
                existing[key] = record
            if index_key is not None and key in predicted and record['alias'] != predicted[key]:
                raise ToolInputError('capture_snapshot_changed', 'A concurrent successful receipt changed capture navigation; preserve sealed work and retry delivery without rerunning execution')
            if sources and metadata.get('provenance_status') != 'unknown' and metadata.get('kind') != 'capture_inventory':
                retain_source_edges(runs, run, ArtifactRef.model_validate(record['artifact_ref']), sources,
                    record=record, connection=connection, context=edge_context)
            committed[key] = record
            result.append({'reference':record['alias'], 'file_name':metadata['file_name'],
                'purpose':metadata['purpose'], 'media_type':item['media'], 'size_bytes':item['size']})
        runs._encode_evidence_snapshot(run, [r for r in records if r.get('record_type') != 'reference_access'],
            [r for r in records if r.get('record_type') == 'reference_access'], recovery, attempts)
    runs._refresh_evidence_schema(run.run_id)
    return {'state':'retained', 'files':result, 'qualification':'not_evaluated'}, committed, index_key


def publish_attachments(runs, run_id, request, *, workspace):
    run = runs._require_running(run_id)
    if run.accepted_candidate_digest is not None:
        raise RunStateConflict('Run already accepted its immutable scientific candidate')
    settings = AttachmentSettings.model_validate((run.recovery_policy or {}).get('attachments', {}))
    aliases = tuple(dict.fromkeys(request.source_aliases))
    if len({item.path for item in request.files}) != len(request.files):
        raise ToolInputError('attachment_publication_invalid', 'Duplicate attachment paths')
    deadline = datetime.fromisoformat(run.deadline_at.replace('Z', '+00:00'))
    def check_budget():
        if datetime.now(timezone.utc) >= deadline:
            raise TimeoutError('Attachment publication exceeded remaining task time')
    with TemporaryDirectory(prefix='scid-attachments-') as temporary:
        staged, total = [], 0
        for index, item in enumerate(request.files):
            check_budget()
            target = Path(temporary) / str(index)
            with _source(workspace, item.path) as source:
                digest, size = snapshot_file(source, target, settings, check_budget, total=total)
            total += size
            media = ('text/plain' if Path(item.path).suffix.lower() in {'.py','.cmd','.par','.log','.txt','.md','.sh'}
                else mimetypes.guess_type(item.path)[0] or 'application/octet-stream')
            from .artifact_capture import explicit_capture_guard
            explicit_capture_guard(runs, run, item.path, target, media)
            staged.append(attachment_item(runs, run, target, digest, size, media,
                {'kind':'scientific_attachment', 'file_name':Path(item.path).name, 'locator':item.path,
                 'purpose':item.purpose, 'origin':'agent_authored'}, aliases))
        return retain_attachments(runs, run, staged, settings, check_budget)[0]
