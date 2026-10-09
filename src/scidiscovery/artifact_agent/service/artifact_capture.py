"""Task-local immutable capture maps; inventory is navigation, never science."""
import codecs
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import stat
from tempfile import TemporaryDirectory
import time

from ...agent_execution_settings import AttachmentSettings
from ...operation_contract import ToolInputError
from ...operations.spec import CaptureSources
from ...operations.tooling import reference_policy
from ...plugin_runtime.workspace import _open_workspace_parent, _SECRET, _MACHINE_PATH
from ..schema.common import canonical_json
from ..schema.refs import ArtifactRef
from .attachments import _source, snapshot_file, attachment_item, retain_attachments
from .run_records import RunStateConflict


def _root(name):
    path = PurePosixPath(name)
    if (path.is_absolute() or len(path.parts) < 2 or path.parts[0] != 'scratch'
            or str(path) != name or any(part.startswith('.') or part in {'tmp','cache'}
                or re.search(r'credential|password|secret|token|private[-_]key|api[_-]?key', part, re.I) for part in path.parts[1:])):
        raise ToolInputError('capture_scope_invalid', 'Declare a real task-local subdirectory below scratch/; whole scratch and external paths are unavailable')
    return path


def require_scientific_aliases(runs, run, aliases):
    for alias in aliases:
        record = runs.sealed_material_record(run, alias)
        if record is None:
            descriptor = runs.source_descriptor(run, alias)
            envelope = runs.artifacts.catalog(descriptor.artifact_ref)
            producer_id = envelope.labels.get('tool_producer_run')
            if producer_id:
                producer = runs.status(producer_id)
                originals = [r for r in runs.tool_evidence(producer_id) if r['artifact_ref'] == descriptor.artifact_ref.model_dump(mode='json')]
                if producer.instance_id != run.instance_id or len(originals) != 1:
                    raise ToolInputError('capture_source_unconfirmed', 'Scientific material has no exact original receipt in this task scope')
                record = originals[0]
        if record is not None and (record.get('metadata', {}).get('provenance_status') == 'unknown'
                or record.get('metadata', {}).get('kind') == 'capture_inventory'):
            raise ToolInputError('capture_source_unconfirmed', 'Capture inventory or a file with unconfirmed scientific sources is readable navigation, not scientific evidence; declare its actual batch sources and seal a new receipt')


class _Guard:
    def __init__(self, media, limit, *, record_limit=True):
        self.limit, self.tail, self.line, self.whitespace = limit, b'', 0, 0
        self.record_limit = record_limit
        self.media, self.header, self.marker = media, b'', 0
        self.decoder = codecs.getincrementaldecoder('utf-8')() if media.startswith('text/') or media in {'application/json','application/xml','application/javascript'} else None

    def feed(self, chunk):
        self.header = (self.header + chunk)[:16]
        value = self.tail + chunk
        if _SECRET.search(value) or _MACHINE_PATH.search(value):
            raise ToolInputError('capture_private_content', 'File contains apparent private content')
        # Whitespace can connect a sensitive prefix across arbitrarily many
        # newlines. Reject an unbounded prefix instead of dropping it from tail.
        for match in re.finditer(rb'\s+|\S+', chunk):
            data = match.group()
            if data[:1].isspace():
                self.whitespace += len(data)
                if self.whitespace > self.limit // 2:
                    raise ToolInputError('capture_safety_unavailable', 'Sensitive-prefix scan exceeds its bounded record policy')
            else:
                self.whitespace = 0
        for match in re.finditer(rb'[A-Za-z ]+|[^A-Za-z ]+', chunk):
            data = match.group()
            self.marker = self.marker + len(data) if data[:1] == b' ' or data[:1].isalpha() else 0
            if self.marker > self.limit:
                raise ToolInputError('capture_safety_unavailable', 'Private-key marker scan exceeds its bounded record policy')
        if self.decoder is not None:
            try:
                self.decoder.decode(chunk)
            except UnicodeDecodeError as error:
                raise ToolInputError('capture_safety_unavailable', 'Text file is not UTF-8') from error
            lines = chunk.split(b'\n')
            if self.record_limit and (self.line + len(lines[0]) > self.limit or any(len(line) > self.limit for line in lines[1:])):
                raise ToolInputError('capture_safety_unavailable', 'Text record exceeds the bounded safety policy')
            self.line = self.line + len(lines[0]) if len(lines) == 1 else len(lines[-1])
        self.tail = value[-self.limit:]

    def finish(self):
        signatures = {'image/png':self.header.startswith(b'\x89PNG\r\n\x1a\n'),
            'image/jpeg':self.header.startswith(b'\xff\xd8\xff'),
            'image/gif':self.header.startswith((b'GIF87a',b'GIF89a')),
            'image/webp':self.header.startswith(b'RIFF') and self.header[8:12] == b'WEBP'}
        if self.media in signatures and not signatures[self.media]:
            raise ToolInputError('capture_safety_unavailable', 'Image format does not match its declared type')
        if self.decoder is not None:
            try:
                self.decoder.decode(b'', final=True)
            except UnicodeDecodeError as error:
                raise ToolInputError('capture_safety_unavailable', 'Text file ends with incomplete UTF-8') from error


def _media(path):
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {'.py','.cmd','.par','.log','.txt','.md','.sh','.r','.f','.f90','.c','.h','.yaml','.yml','.jsonl'}:
        return 'text/plain'
    media = mimetypes.guess_type(path)[0]
    return media if media in {'application/json','text/csv','text/plain','image/png','image/jpeg','image/gif','image/webp'} else None


def explicit_capture_guard(runs, run, locator, snapshot, media):
    contract = runs._compiled(run).spec.artifact_capture
    if contract is None:
        return
    # Lack of automatic support is a coverage gap, not withdrawal of existing
    # authorized explicit binary publication. Apply known format safety only.
    automatic_media = _media(locator)
    guard = _Guard(automatic_media or media, contract.max_record_bytes,
        record_limit=automatic_media is not None and any(PurePosixPath(locator).is_relative_to(PurePosixPath(root)) for root in contract.roots))
    with snapshot.open('rb') as source:
        while chunk := source.read(min(65536, contract.max_record_bytes)):
            guard.feed(chunk)
    guard.finish()


def _listing(workspace, roots, contract, check):
    entries, identities, count, complete = [], [], 0, True
    def visit(fd, root):
        nonlocal count, complete
        with os.scandir(fd) as iterator:
            for entry in iterator:
                check()
                count += 1
                if count > contract.max_entries:
                    complete = False
                    return
                path = str(root / entry.name)
                info = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                identities.append((hashlib.sha256(path.encode()).hexdigest(), info.st_mode, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
                private = (entry.name.startswith('.') or re.search(r'(?:credential|password|secret|token|private[-_]key|api[_-]?key)', entry.name, re.I))
                if private or entry.name in {'cache','tmp','assignment','schema','inputs','candidates','recovery-draft'} or entry.name in {'result.json','tool-evidence.json','capture-index.json'} or entry.name.endswith(('.tmp','.temp','.partial','~','.swp')):
                    entries.append({'status':'excluded'})
                elif stat.S_ISDIR(info.st_mode):
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        visit(child, root / entry.name)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    entries.append({'path':path, 'size_bytes':info.st_size, 'status':'pending'})
                else:
                    entries.append({'path':path, 'status':'unsupported_file'})
                if not complete:
                    return
    for root in roots:
        descriptors = []
        try:
            descriptors, fd = _open_workspace_parent(workspace, Path(root) / '_capture')
            info = os.fstat(fd)
            identities.append((hashlib.sha256(root.encode()).hexdigest(), info.st_mode, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
            visit(fd, PurePosixPath(root))
        except (OSError, RuntimeError):
            complete = False
            entries.append({'path':root, 'status':'scope_unavailable'})
        finally:
            for fd in reversed(descriptors):
                os.close(fd)
        if count > contract.max_entries:
            break
    return entries, sorted(identities), complete


def _slots(value, tokens):
    if not tokens:
        return
    if isinstance(value, dict):
        keys = list(value) if tokens[0] == '*' else [tokens[0]]
    elif isinstance(value, list):
        keys = range(len(value)) if tokens[0] == '*' else [int(tokens[0])]
    else:
        return
    for key in keys:
        if isinstance(value, dict) and key not in value or isinstance(value, list) and key >= len(value):
            continue
        if len(tokens) == 1:
            yield value, key
        else:
            yield from _slots(value[key], tokens[1:])


def output_reference_paths(compiled):
    from .run_assignment import operation_primary_output
    port = operation_primary_output(compiled)
    paths = [path + '/*/source_key' for path in port.evidence_paths]
    policy = reference_policy(compiled)
    paths.extend(rule.path for rule in policy.rules if rule.schema_id == port.schema_id
        and not (rule.producer_input_alias or rule.locator_prefix or rule.keys or rule.selected_only)) if policy else None
    return tuple(dict.fromkeys(paths))


def _resolve(runs, run, reference, index, records):
    if reference.startswith('run:'):
        raise ToolInputError('capture_reference_invalid', 'run: is navigation only; cite an exact file or original alias and its existing locator')
    if reference.startswith('file@'):
        stage, separator, locator = reference[5:].partition(':')
        original = runs.sealed_material_record(run, stage)
        if not separator or original is None or original.get('metadata', {}).get('kind') != 'experiment_stage':
            raise ToolInputError('capture_reference_invalid', 'Use the exact returned sealed stage reference')
        producer = runs.status(original['producer_run_id'])
        alias = original['metadata'].get('capture_index')
        receipt = next((r for r in runs.tool_evidence(producer.run_id) if r['alias'] == alias), None)
        if receipt is None or receipt['metadata'].get('kind') != 'capture_inventory':
            raise ToolInputError('capture_reference_unsealed', 'This exact stage has no sealed capture map')
        index = receipt['metadata'].get('capture_map')
        if index is None:
            raise ToolInputError('capture_reference_unsealed', 'This exact stage has no control-owned capture map')
    elif reference.startswith('file:'):
        locator = reference[5:]
    else:
        require_scientific_aliases(runs, run, (reference,))
        return reference
    if index is None:
        raise ToolInputError('capture_reference_unsealed', 'File reference has no capture map for this seal; use an exact sealed alias or submit the scientific draft')
    candidates = [entry for entry in index['entries'] if entry.get('path') == locator]
    if '/' not in locator:
        if locator in {item.source_name for item in run.inputs} | {record['alias'] for record in records}:
            raise ToolInputError('capture_reference_ambiguous', 'Basename conflicts with an alias; use the exact task-relative file path')
        candidates = [entry for entry in index['entries'] if PurePosixPath(entry.get('path','')).name == locator]
    if len(candidates) != 1:
        raise ToolInputError('capture_reference_ambiguous', 'File is missing or ambiguous in this exact capture; use its full task-relative path')
    entry = candidates[0]
    if entry['status'] != 'retained':
        raise ToolInputError('capture_reference_incomplete', 'Referenced file was not retained; repair the reported capture gap before scientific delivery')
    matches = [record for record in records if record.get('publication_key') == entry['publication_key'] and record['artifact_ref'] == entry['artifact_ref']]
    if not matches:
        # A map is navigation only. An exact frozen input independently grants
        # scope to this particular original; it does not grant the entire map.
        inputs = [binding for binding in run.inputs if binding.artifact_ref.model_dump(mode='json') == entry['artifact_ref']]
        if len(inputs) == 1:
            require_scientific_aliases(runs, run, (inputs[0].source_name,))
            return inputs[0].source_name
    if len(matches) != 1:
        raise ToolInputError('capture_reference_scope', 'The exact captured file receipt is outside this task available scope')
    alias = matches[0]['alias']
    require_scientific_aliases(runs, run, (alias,))
    return alias


def capture_science(runs, run_id, document, paths, declarations=(), *, workspace, capture_new=True):
    run = runs._require_running(run_id)
    if run.accepted_candidate_digest is not None:
        raise RunStateConflict('Run already accepted its immutable scientific candidate')
    contract = runs._compiled(run).spec.artifact_capture
    if contract is None:
        return document, {}
    document = json.loads(canonical_json(document))
    from pydantic import ValidationError
    try:
        batches = [CaptureSources.model_validate_json(canonical_json(item), strict=True) for item in declarations]
    except ValidationError as error:
        raise ToolInputError('capture_scope_invalid', 'Repair the capture_sources batch declaration to match its task-local contract') from error
    roots = tuple(dict.fromkeys((*contract.roots, *(root for batch in batches for root in batch.directories))))
    if len(roots) > 4:
        raise ToolInputError('capture_scope_invalid', 'At most four declared task-local capture directories')
    for root in roots:
        _root(root)
    # A declared nested batch changes source association, not enumeration scope.
    roots = tuple(root for root in roots if not any(root != parent and
        PurePosixPath(root).is_relative_to(PurePosixPath(parent)) for parent in roots))
    base = tuple(binding.source_name for binding in run.inputs if binding.port_name in contract.required_source_ports)
    for batch in batches:
        if any(alias.startswith(('file:','file@','run:')) for alias in batch.source_aliases):
            raise ToolInputError('capture_source_unconfirmed', 'Batch sources must already be sealed exact aliases')
        require_scientific_aliases(runs, run, batch.source_aliases)
        for alias in batch.source_aliases:
            runs.source_descriptor(run, alias)
    index, metadata = None, {}
    records = runs.tool_evidence(run_id)
    cited_files, scientific_sources = set(), []
    for path in paths:
        for owner, key in _slots(document, path.lstrip('/').split('/')):
            reference = owner[key]
            if not isinstance(reference, str):
                continue
            if reference.startswith('file:'):
                cited_files.add(reference[5:])
            elif not reference.startswith(('file@','run:')):
                require_scientific_aliases(runs, run, (reference,))
                runs.source_descriptor(run, reference)
                scientific_sources.append(reference)
    if capture_new:
        deadline = time.monotonic() + min(contract.max_seconds, max(0, (datetime.fromisoformat(run.deadline_at.replace('Z','+00:00')) - datetime.now(timezone.utc)).total_seconds()))
        def check():
            if time.monotonic() >= deadline:
                raise ToolInputError('capture_deadline', 'Capture exhausted its bounded time; preserve files and repair delivery without rerunning the experiment')
        entries, initial, complete = _listing(workspace, roots, contract, check)
        entries.sort(key=lambda entry:(entry.get('path', ''), entry['status']))
        # Empty unchanged directories do not manufacture index receipts.
        if entries or not complete:
            settings = AttachmentSettings.model_validate((run.recovery_policy or {}).get('attachments', {}))
            with TemporaryDirectory(prefix='scid-capture-') as temporary:
                staged, total = [], 0
                for number, entry in enumerate(entries):
                    if entry['status'] != 'pending':
                        if entry['status'] != 'excluded':
                            complete = False
                        continue
                    locator = entry['path']
                    media = _media(locator)
                    if media is None:
                        entry['status'] = 'metadata_only'
                        complete = False
                        continue
                    associated = [tuple(batch.source_aliases) for batch in batches if any(PurePosixPath(locator).is_relative_to(_root(root)) for root in (batch.directories or contract.roots))]
                    conflict = len(set(associated)) > 1
                    # Existing declared scientific sources belong only to newly
                    # cited files in this declaration, never all captured siblings.
                    adopted = associated[0] if associated and not conflict else (
                        scientific_sources if locator in cited_files or PurePosixPath(locator).name in cited_files else ())
                    native = document.get('native_execution')
                    implementation = (native.get('implementation') if isinstance(native, dict) else None)
                    native_files = (native.get('results', []) + native.get('logs', [])) if isinstance(native, dict) else []
                    native_source = (implementation,) if implementation and not implementation.startswith(('file:','file@','run:')) and any(
                        ref == 'file:' + locator or ref == 'file:' + PurePosixPath(locator).name for ref in native_files) else ()
                    aliases = tuple(dict.fromkeys((*base, *adopted, *native_source)))
                    target = Path(temporary) / str(number)
                    try:
                        with _source(workspace, locator) as source:
                            digest, size = snapshot_file(source, target, settings, check, total=total,
                                guard=_Guard(media, contract.max_record_bytes))
                        if not associated and not adopted and not native_source:
                            # A normalized retry can carry the exact previous
                            # immutable file version without its authoring form.
                            # Reuse only a unique matching source identity; never
                            # pick the newest receipt or infer from a directory.
                            available = {binding.artifact_ref:binding.source_name for binding in run.inputs}
                            available.update({ArtifactRef.model_validate(record['artifact_ref']):record['alias'] for record in records})
                            identities = set()
                            for record in records:
                                metadata = record.get('metadata', {})
                                if (metadata.get('capture_mode') != 'auto_captured' or metadata.get('locator') != locator
                                        or record['artifact_ref']['sha256'] != digest or record['media_type'] != media
                                        or metadata.get('provenance_status') != 'known'):
                                    continue
                                original = runs.status(runs.artifacts.catalog(ArtifactRef.model_validate(record['artifact_ref'])).labels['tool_producer_run'])
                                refs = tuple(runs.source_descriptor(original, alias).artifact_ref for alias in metadata['derived_from'])
                                if all(ref in available for ref in refs):
                                    identities.add(tuple(sorted(available[ref] for ref in refs)))
                            if len(identities) == 1:
                                aliases = tuple(dict.fromkeys((*base, *next(iter(identities)))))
                            elif len(identities) > 1:
                                conflict = True
                        item = attachment_item(runs, run, target, digest, size, media,
                            {'kind':'scientific_attachment','file_name':PurePosixPath(locator).name,'locator':locator,
                             'purpose':'Automatically retained scientific file','origin':'agent_authored',
                             'capture_mode':'auto_captured','execution_attestation':'unavailable',
                             'provenance_status':'known' if aliases and not conflict else 'unknown',
                             'scientific_claim_admissible':bool(aliases and not conflict)}, aliases if not conflict else ())
                        staged.append(item)
                        total += size
                        entry.update(status='retained', publication_key=item['key'])
                    except (OSError, RuntimeError, ToolInputError) as error:
                        entry['status'] = 'incomplete'
                        entry['reason'] = error.details[0]['code'] if isinstance(error, ToolInputError) else 'capture_gap'
                        complete = False
                _, final, final_complete = _listing(workspace, roots, contract, check)
                index = {'roots':list(roots),'entries':entries,'coverage':'complete' if complete and final_complete and initial == final else 'incomplete',
                    'coverage_changed':initial != final,'attempt_inventory':'not_declared','source_declarations':[batch.model_dump(mode='json') for batch in batches]}
                _, retained, index_key = retain_attachments(runs, run, staged, settings, check, inventory=index, temporary=temporary)
                records = runs.tool_evidence(run_id)
                metadata = {'capture_index':retained[index_key]['alias'], 'capture_coverage':index['coverage']}
                metadata['capture_counts'] = {status:sum(entry['status'] == status for entry in entries)
                    for status in sorted({entry['status'] for entry in entries})}
    cited = []
    for path in paths:
        for owner, key in _slots(document, path.lstrip('/').split('/')):
            if isinstance(owner[key], str):
                owner[key] = _resolve(runs, run, owner[key], index, records)
                cited.append(owner[key])
    if metadata:
        metadata['author_cited'] = list(dict.fromkeys(cited))
    return document, metadata


def capture_candidate(runs, run, *, final_submission):
    compiled = runs._compiled(run)
    if compiled.spec.artifact_capture is None:
        return
    from ...plugin_runtime.workspace import read_control_workspace_file
    workspace = runs.backend.open(run.run_id)
    try:
        document = json.loads(read_control_workspace_file(workspace.root, Path('output/result.json'),
            max_bytes=compiled.spec.limits.max_output_bytes))
    except (ValueError, FileNotFoundError):
        return  # The existing finalizer/validator owns malformed scientific forms.
    if not isinstance(document, dict) or not isinstance(document.get('payload'), dict):
        return
    had_declaration = 'capture_sources' in document
    declarations = document.pop('capture_sources', ())
    if not isinstance(declarations, (list, tuple)) or len(declarations) > 4:
        raise ToolInputError('capture_scope_invalid', 'capture_sources must contain at most four scientific batch declarations')
    normalized, _ = capture_science(runs, run.run_id, document,
        tuple('/payload/' + path.lstrip('/') for path in output_reference_paths(compiled)), declarations,
        workspace=workspace.root, capture_new=final_submission)
    if final_submission or normalized != document or had_declaration:
        runs.backend.write_primary_output(run.run_id, canonical_json(normalized))


def draft_capture_schema(envelope, compiled):
    """Extend only declared citation leaves in the existing authoring schema."""
    from copy import deepcopy
    navigation = {'type':'string','maxLength':256,'pattern':r'^(?:file:[^\r\n]+|file@[^:\r\n]+:[^\r\n]+)$'}
    def walk(node, tokens, root):
        if not isinstance(node, dict):
            return
        if '$id' in node:
            root = node
        if '$ref' in node and node['$ref'].startswith('#/'):
            target = root
            for token in node['$ref'][2:].split('/'):
                target = target[token.replace('~1','/').replace('~0','~')]
            node.update(deepcopy(target))
            node.pop('$ref', None)
        for branch in node.get('allOf', ()) or node.get('anyOf', ()):
            walk(branch, tokens, root)
        if not tokens:
            return
        if tokens[0] == '*':
            walk(node.get('items'), tokens[1:], root)
        else:
            properties = node.get('properties', {})
            if tokens[0] not in properties:
                return
            if len(tokens) == 1:
                properties[tokens[0]] = {'anyOf':[properties[tokens[0]], deepcopy(navigation)]}
            else:
                walk(properties[tokens[0]], tokens[1:], root)
    for path in output_reference_paths(compiled):
        walk(envelope, ['payload', *path.lstrip('/').split('/')], envelope)
    envelope['properties']['capture_sources'] = {'type':'array','maxItems':4,
        'items':CaptureSources.model_json_schema(mode='validation'),
        'description':'Optional actual sources and task-local scope of a scientific batch; control consumes this declaration before sealing. No per-file publication form.'}
    return envelope
