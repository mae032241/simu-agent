"""Stream explicit scientific deliverables into the existing Run receipt/CAS path."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import mimetypes
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory

from ...agent_execution_settings import AttachmentSettings
from ...plugin_runtime.workspace import _open_workspace_parent
from ..schema.artifact import ArtifactRegistration
from ..schema.common import canonical_json
from .run_records import RunStateConflict


@contextmanager
def _source(workspace, name):
    path = Path(name)
    if path.is_absolute() or len(path.parts) < 2 or path.parts[0] != 'scratch' or '..' in path.parts:
        raise ValueError('Publish files below scratch/. Move extra output files there; output/ holds only result.json and runtime receipts.')
    descriptors, parent = _open_workspace_parent(workspace, path)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('Attachment is not a regular file')
            yield stream
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def publish_attachments(runs, run_id, request, *, workspace):
    run = runs._require_running(run_id)
    from ...operations.tooling import tool_evidence_ports
    port = tool_evidence_ports(runs._compiled(run)).get('attachments')
    if port is None:
        raise ValueError('This task has no attachment publication capability')
    settings = AttachmentSettings.model_validate((run.recovery_policy or {}).get('attachments', {}))
    aliases = tuple(dict.fromkeys(request.source_aliases))
    sources = tuple(runs.source_descriptor(run, alias).artifact_ref for alias in aliases)
    parents = tuple(dict.fromkeys((*[item.artifact_ref for item in run.inputs], *sources)))
    if len({item.path for item in request.files}) != len(request.files):
        raise ValueError('Duplicate attachment paths in one request')
    deadline = datetime.fromisoformat(run.deadline_at.replace('Z', '+00:00'))
    def check_budget():
        if datetime.now(timezone.utc) >= deadline:
            raise TimeoutError('Attachment publication exceeded the remaining task time')
    staged = []
    # Snapshot through non-symlink handles; RAM use is one configured chunk.
    with TemporaryDirectory(prefix='scid-attachments-') as temporary:
        total = 0
        for index, item in enumerate(request.files):
            check_budget()
            target = Path(temporary) / str(index)
            with _source(workspace, item.path) as source, target.open('xb') as output:
                before = os.fstat(source.fileno())
                if before.st_size > settings.max_item_bytes or total + before.st_size > settings.max_total_bytes:
                    raise ValueError(f'Attachment budget exceeded: per-file {settings.max_item_bytes}, total {settings.max_total_bytes} bytes')
                digest, size = hashlib.sha256(), 0
                while chunk := source.read(settings.chunk_bytes):
                    check_budget()
                    size += len(chunk)
                    if size > settings.max_item_bytes or total + size > settings.max_total_bytes:
                        raise ValueError('Attachment grew beyond the configured byte budget')
                    digest.update(chunk); output.write(chunk)
                after = os.fstat(source.fileno())
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError('Attachment changed while being published; finish writing before publication')
            total += size
            media = ('text/plain' if Path(item.path).suffix.lower() in {'.py', '.cmd', '.par', '.log', '.txt', '.md', '.sh'}
                     else mimetypes.guess_type(item.path)[0] or 'application/octet-stream')
            metadata = {'kind': 'scientific_attachment', 'file_name': Path(item.path).name,
                'purpose': item.purpose, 'derived_from': list(aliases), 'origin': 'agent_authored'}
            # Aliases are navigation: retries/recovery identify sources by exact Refs.
            key = hashlib.sha256(canonical_json({'sha256': digest.hexdigest(),
                'metadata': {k:v for k,v in metadata.items() if k != 'derived_from'},
                'sources': sorted((ref.model_dump(mode='json') for ref in set(sources)), key=canonical_json), 'media_type': media,
                'output_port': 'attachments'})).hexdigest()
            staged.append((target, digest.hexdigest(), size, media, metadata, key))
        staged = list({item[-1]: item for item in staged}.values())
        recovery = runs.recovery_tool_proof(run)
        attempts = runs.tool_attempts(run_id)
        result = []
        with runs._connect() as connection:
            import json
            connection.execute('BEGIN IMMEDIATE')
            row = runs._row(connection, run_id)
            if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
                raise RunStateConflict('Run no longer accepts scientific attachments')
            records = [json.loads(r[0]) for r in connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=?',(run_id,))]
            attachments = [r for r in records if r.get('output_port') == 'attachments']
            existing = {r[0]: json.loads(r[1]) for r in connection.execute('SELECT evidence_key,record_json FROM run_tool_evidence WHERE run_id=?',(run_id,))}
            new = [item for item in staged if item[-1] not in existing]
            if (len(attachments) + len(new) > settings.max_files
                    or len(records) + len(new) > 128
                    or sum(r['size_bytes'] for r in attachments) + sum(item[2] for item in new) > settings.max_total_bytes):
                raise ValueError('The task attachment count or total byte budget would be exceeded')
            for path, digest, size, media, metadata, key in staged:
                check_budget()
                if key in existing:
                    record = existing[key]
                else:
                    ordinal = len(records) + 1
                    number = ordinal
                    reserved = {r['alias'] for r in records} | {i.source_name for i in run.inputs}
                    while f'attachment_{number:03d}' in reserved:
                        number += 1
                    alias = f'attachment_{number:03d}'
                    envelope = runs.artifacts.register_file(path, ArtifactRegistration(kind=port.kind,
                        schema_id=port.schema_id, payload_schema_version=1, media_type=media, creator=runs.service_actor,
                        parent_refs=parents, labels={'operation_id':run.operation_id, 'operation_version':run.operation_version,
                            'operation_digest':run.operation_digest, 'operation_output_port':'attachments',
                            'tool_name':'worker_publish_files', 'tool_producer_run':run_id, 'source_origin':'agent_authored'},
                        confidentiality='run_private'), expected_sha256=digest, expected_size=size,
                        idempotency_key=f'run:{run_id}:attachment:{key}', chunk_bytes=settings.chunk_bytes,
                        check_budget=check_budget)
                    record = {'alias':alias, 'artifact_ref':envelope.ref.model_dump(mode='json'),
                        'source_ref':sources[0].model_dump(mode='json'), 'media_type':media, 'size_bytes':size,
                        'metadata':metadata, 'tool_name':'worker_publish_files', 'output_port':'attachments', 'publication_key':key}
                    connection.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',
                        (run_id, ordinal, key, canonical_json(record), alias))
                    records.append(record); existing[key] = record
                result.append({'reference':record['alias'], 'file_name':metadata['file_name'],
                    'purpose':metadata['purpose'], 'media_type':media, 'size_bytes':size})
            snapshot = runs._encode_evidence_snapshot(run,
                [r for r in records if r.get('record_type') != 'reference_access'],
                [r for r in records if r.get('record_type') == 'reference_access'], recovery, attempts)
            from ..schema.tool_evidence import ToolEvidenceManifest
            ToolEvidenceManifest.model_validate_json(snapshot)
            if len(snapshot) > 1024 * 1024:
                raise ValueError('Controlled source manifest would exceed its byte limit')
        runs._refresh_evidence_schema(run_id)
        return {'state':'retained', 'files':result, 'qualification':'not_evaluated'}
