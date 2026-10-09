"""Bounded exact local reading. No validation, evidence qualification or read ledger.

CLI returns exact text, with tool-owned disposable navigation.
The legacy Python page API retains explicit offsets for programmatic callers.
"""
from __future__ import annotations

import argparse
import hashlib
import fcntl
import os
import json
from pathlib import Path
import re
import sys
import tempfile


READ_INPUT_NAVIGATION = 4
SCIENTIFIC_COMPACT_VIEW = 1
SCIENTIFIC_PAGE_MIN_BYTES = 512
SCIENTIFIC_PAGE_MAX_BYTES = 8192
SCIENTIFIC_PAGE_DEFAULT_BYTES = 4096
CACHE_DIRECTORY = ".read-input"
MATERIAL_FILE_READING = (
    'For ordinary text, code and logs, use native read/search tools on bounded ranges of RETURNED_PATH. '
    'JSON may also use native tools; python tools/read_input.py RETURNED_PATH --file with --directory or '
    '--pointer is optional for exact structured selections. Expand decisive original context when needed '
    'and keep each display bounded.')


class Number(str):
    """Keep JSON number lexemes without a float conversion."""


def encode(value):
    if isinstance(value, Number):
        return str(value)
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k, ensure_ascii=False) + ':' + encode(v)
                              for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(encode(v) for v in value) + ']'
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def select(value, pointer):
    if not pointer:
        return value
    if not pointer.startswith('/') or re.search(r'~(?![01])', pointer):
        raise ValueError('invalid JSON Pointer')
    for part in pointer[1:].split('/'):
        key = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict):
            if key not in value:
                raise ValueError('JSON Pointer member is absent. Use --directory to discover actual keys; '
                    'omit --pointer for the root ("/" selects an empty-key member).')
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r'0|[1-9][0-9]*', key):
            if int(key) >= len(value):
                raise ValueError('JSON Pointer array index is out of range.')
            value = value[int(key)]
        else:
            raise ValueError('pointer does not identify a value')
    return value


def compact_scientific_fields(value, pointers):
    """Exact declared fields, with equal budgets and explicit partial structures.

    This is a mechanical selection, never a scientific conclusion or an original
    read attestation. Each field has its own allowance so a large early field
    cannot hide a later verdict, limitation or next action.
    """
    def size(item):
        return len(encode(item).encode('utf-8'))
    def projection(pointer, selected, budget, depth=0):
        count = size(selected)
        item = dict(pointer=pointer, size_bytes=count)
        if size(dict(item, status='selected', value=selected)) <= budget:
            return dict(item, status='selected', value=selected)
        item['status'] = 'omitted'
        if isinstance(selected, (dict, list)):
            item.update(status='projected', items=[], total_children=len(selected), omitted_children=len(selected))
            children = selected.items() if isinstance(selected, dict) else enumerate(selected)
            if depth < 2:
                for position, (key, child) in enumerate(children):
                    if position == 32:
                        break
                    child_pointer = pointer + '/' + str(key).replace('~', '~0').replace('/', '~1')
                    entry = projection(child_pointer, child, min(768, budget), depth + 1)
                    candidate = dict(item, items=[*item['items'], entry], omitted_children=item['omitted_children'] - 1)
                    if size(candidate) <= budget:
                        item = candidate
                    if len(item['items']) == 8:
                        break
        return item
    items = []
    for pointer in pointers:
        try:
            selected = select(value, pointer)
        except (ValueError, KeyError, IndexError):
            items.append(dict(pointer=pointer, status='missing'))
        else:
            # Complete prose answers are useful science. Large collections use
            # structure projections; scalar statements retain a separate bound.
            items.append(projection(pointer, selected, 4096 if not isinstance(selected, (dict, list)) else 1024))
    return dict(items=items, coverage='declared_fields', original_read='not_confirmed',
        instruction='Selected values are exact at their pointers. Projected structures are partial; omitted children and originals remain unread. Expand the original pointer or read the full source for evidence needed by the task.')


def public_boundary_record(record):
    """Retain owner provenance while excluding private control bindings."""
    result = dict(record)
    result.pop('artifact_ref', None)
    result.pop('producer_run_id', None)
    if 'producer' in result:
        producer = result['producer']
        result['producer'] = {key: producer[key] for key in ('output_name', 'operation_id') if producer.get(key)}
        if isinstance(result.get('declaration'), dict) and 'boundary_key' in result['declaration']:
            result['verification'] = 'unverified'
            result['interpretation_verification'] = 'unverified'
            checks = []
            for index, check in enumerate(result.get('source_checks', ())):
                check = dict(check)
                evidence = result['declaration'].get('evidence', ())
                quote = evidence[index].get('quote') if index < len(evidence) else None
                # Historical aggregate "matched" never certifies an absent
                # quote or the owner's interpretation. Keep sealed bytes intact.
                check.setdefault('source_location_verification', 'unverified')
                check.setdefault('quote_verification', 'absent' if quote is None else 'unverified')
                check['verification'] = 'matched' if check['quote_verification'] == 'matched' else 'unverified'
                check['verification_scope'] = 'quoted_bytes_only'
                checks.append(check)
            result['source_checks'] = checks
    if 'reference' in result or 'resolved_source' in result:
        result['verification_scope'] = 'declaration_identity_only'
    for field in ('source_checks', 'revision_checks'):
        if field in result:
            result[field] = [public_boundary_record(item) for item in result[field]]
    if isinstance(result.get('resolved_source'), dict):
        result['resolved_source'] = public_boundary_record(result['resolved_source'])
    if isinstance(result.get('declaration'), dict) and 'producer' in result['declaration']:
        result['declaration'] = public_boundary_record(result['declaration'])
    return result


def public_boundary_signal(signal):
    result = dict(signal)
    for field in ('boundary_declarations', 'boundary_references'):
        if field in result:
            result[field] = [public_boundary_record(item) for item in result[field]]
    return result


COMPACT_BOUNDARY_BYTES = 8192


def _boundary_metadata(entry):
    """Omit complete quote/interpretation together, retaining owner navigation."""
    record = entry.get('declaration', {}) if 'reference' in entry else entry
    authored = record.get('declaration', {})
    metadata = {key: entry[key] for key in
        ('reference', 'verification', 'verification_scope', 'interpretation_verification', 'effect', 'authority', 'instruction', 'producer') if key in entry}
    if record.get('interpretation_verification'):
        metadata['interpretation_verification'] = record['interpretation_verification']
    metadata['boundary_key'] = authored.get('boundary_key') or entry.get('reference', {}).get('boundary_key')
    if record.get('producer'):
        metadata['producer'] = record['producer']
    metadata['source_checks'] = []
    for check in record.get('source_checks', ())[:4]:
        check = dict(check)
        if len(check.get('locator', '').encode('utf-8')) > 768:
            check.pop('locator', None)
            check['locator_omitted'] = 'exact_locator_exceeds_compact_budget'
        if len(encode(metadata | {'source_checks': [*metadata['source_checks'], check]}).encode('utf-8')) > 2048:
            break
        metadata['source_checks'].append(check)
    metadata['source_checks_omitted'] = len(record.get('source_checks', ()))-len(metadata['source_checks'])
    metadata['omission'] = 'complete_quote_and_interpretation_omitted_together'
    metadata['owner_read'] = dict(view='boundaries', boundary_key=metadata['boundary_key'],
        **({'output_name': metadata['producer']['output_name']} if metadata.get('producer', {}).get('output_name') else {}),
        **({'source_key': entry['reference']['source_key']} if entry.get('reference', {}).get('source_key') else {}),
        instruction='Delegate clarification to the scientific owner with these exact source/declaration names. '
            'Use worker_reference_read(view="boundaries") on the bound source; list then read its returned reference. '
            'Citation bytes do not verify interpretation or authorize relaxation.')
    return metadata


def compact_handoff(handoff):
    """Keep complete sealed statements only; never shorten scientific prose."""
    result, omissions = public_boundary_signal(handoff), {}
    if isinstance(result.get('summary'), str) and len(result['summary'].encode('utf-8')) > 4096:
        result.pop('summary')
        omissions['summary'] = 'complete_statement_exceeds_4096_bytes'
    for field in ('assumptions', 'missing_inputs', 'next_actions'):
        entries = result.get(field, [])
        shown = [entry for entry in entries[:4] if len(entry.encode('utf-8')) <= 1024]
        result[field] = shown
        if len(shown) != len(entries):
            omissions[field] = len(entries) - len(shown)
    fields = ('boundary_declarations', 'boundary_references')
    entries = {field: result.pop(field, []) for field in fields}
    projected = {field: [] for field in fields}

    def fits(candidate):
        omitted = {field: len(entries[field])-len(candidate[field]) for field in fields}
        # Reserve the Root omission wrapper and its bounded delegation guidance;
        # ordinary handoff prose continues to have its separate existing budgets.
        return len(encode(candidate | {'omitted_items': omitted}).encode('utf-8')) + 512 <= COMPACT_BOUNDARY_BYTES

    for field in fields:
        for entry in entries[field][:4]:
            # Quote and interpretation stay in the same exact declaration. A
            # shared budget bounds both collections, including omission metadata.
            candidate = dict(projected, **{field: [*projected[field], entry]})
            if len(encode(entry).encode('utf-8')) > 4096 or not fits(candidate):
                candidate[field] = [*projected[field], _boundary_metadata(entry)]
            if fits(candidate):
                projected = candidate
        if entries[field]:
            result[field] = projected[field]
        if len(projected[field]) != len(entries[field]):
            omissions[field] = len(entries[field])-len(projected[field])
    return result, omissions


def compact_scheduler_fields(value, pointers):
    """Relay declared statements without opening structured scientific reports.

    Field identities belong to the frozen plugin contract. This projection only
    bounds their shape and bytes; it neither interprets nor rewrites their science.
    """
    items = []
    for pointer in pointers:
        try:
            selected = select(value, pointer)
        except (ValueError, KeyError, IndexError):
            items.append(dict(pointer=pointer, status='missing'))
            continue
        item = dict(pointer=pointer, size_bytes=len(encode(selected).encode('utf-8')))
        if isinstance(selected, list) and all(isinstance(entry, str) for entry in selected):
            shown = [entry for entry in selected[:4] if len(entry.encode('utf-8')) <= 1024]
            item.update(status='selected' if shown == selected else 'projected', value=shown,
                total_children=len(selected), omitted_children=len(selected)-len(shown))
        elif isinstance(selected, (dict, list)):
            item.update(status='omitted', total_children=len(selected),
                reason='structured_scientific_content_owned_by_worker')
        elif item['size_bytes'] <= 4096:
            item.update(status='selected', value=selected)
        else:
            item.update(status='omitted', reason='complete_statement_exceeds_4096_bytes')
        items.append(item)
    return dict(items=items, coverage='declared_scheduler_statements', original_read='not_confirmed',
        authority='sealed_owner_statements_not_scheduler_scientific_judgment',
        instruction='Omitted scientific content remains with its owner. Use the sealed handoff direction; '
            'delegate missing or conflicting direction with exact source names to a scientific Worker.')


def page(workspace, path, *, pointer=None, directory=False, offset=0, version=None, budget=SCIENTIFIC_PAGE_DEFAULT_BYTES):
    if not SCIENTIFIC_PAGE_MIN_BYTES <= budget <= SCIENTIFIC_PAGE_MAX_BYTES:
        raise ValueError(f'budget must be {SCIENTIFIC_PAGE_MIN_BYTES}..{SCIENTIFIC_PAGE_MAX_BYTES} bytes')
    if offset < 0:
        raise ValueError('offset outside selected text')
    root = Path(workspace).resolve()
    source = _within(root, path)
    raw = source.read_bytes()
    text = raw.decode('utf-8')
    identity = hashlib.sha256(raw).hexdigest()
    mode = 'directory' if directory else 'json' if pointer is not None else 'text'
    token = hashlib.sha256((identity + '\0' + mode + '\0' + (pointer or '')).encode()).hexdigest()
    if (offset and version is None) or (version is not None and version != token):
        raise ValueError('source or selection changed, or continuation version missing; restart at offset 0')
    text = _selected_text(raw, [pointer] if pointer is not None else [], directory, directory_details=False)
    if offset < 0 or offset > len(text):
        raise ValueError('offset outside selected text')
    base = dict(source=source.relative_to(root).as_posix(), sha256=identity, version=token,
                pointer=pointer, mode=mode, format='text_fragment', offset=offset,
                total_characters=len(text))

    def response(end):
        return {**base, 'fragment': text[offset:end], 'next_offset': end if end < len(text) else None,
                'complete': end == len(text)}

    def fits(end):
        return len((encode(response(end)) + '\n').encode('utf-8')) <= budget

    if not fits(offset):
        raise ValueError('source/selection metadata exceeds reply budget')
    # The end marker may be shorter than an intermediate numeric offset.
    if fits(len(text)):
        return response(len(text))
    low, high = offset, len(text) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if fits(middle):
            low = middle
        else:
            high = middle - 1
    if low == offset:
        raise ValueError('reply budget cannot fit metadata and next character')
    return response(low)


def readable_input(item):
    return (item.get('exposure') in {'full', 'on_demand', 'material'}
        and item.get('agent_visible') is not False
        and item.get('materialization') is None)


def shared_input(inputs, item):
    """A control-declared equivalent with the same directly readable metadata.

    same_source_as is generated from complete ArtifactRefs, never content hashes.
    This presentation/navigation hint grants no additional input permissions.
    """
    if not readable_input(item):
        return None
    name = item.get('same_source_as', item.get('source_name'))
    representatives = [value for value in inputs if value.get('source_name') == name]
    if len(representatives) != 1:
        return None
    representative = representatives[0]
    fields = ('media_type', 'schema_id', 'size_bytes', 'scientific_view')
    def compatible(value):
        return (readable_input(value)
            and all(value.get(field) == representative.get(field) for field in fields)
            and all(field in value for field in ('media_type', 'schema_id', 'size_bytes')))
    if (representative.get('same_source_as') or not compatible(representative)
            or not compatible(item)):
        return None
    if representative is item and not any(value.get('same_source_as') == name and compatible(value)
            for value in inputs if value is not item):
        return None
    return representative


def _source(root, name, file):
    if file or name == 'assignment.json':
        return _within(root, name), None
    else:
        assignment = _within(root, 'assignment.json')
        inputs = json.loads(assignment.read_text(encoding='utf-8')).get('inputs', [])
        matches = [item for item in inputs if item.get('source_name') == name]
        if not matches:
            matches = [item for item in inputs if item.get('port') == name]
        if not matches:
            matches = [item for item in inputs if item.get('relative_path') == name]
        if len(matches) != 1:
            raise ValueError('input missing or ambiguous; select one source_name from assignment.inputs')
        item = matches[0]
        source = _within(root, item['relative_path'])
        representative = shared_input(inputs, item)
        if representative is not None:
            try:
                return _within(root, representative['relative_path']), item['source_name']
            except (KeyError, ValueError):
                pass  # A missing or unsafe representative cannot widen this read.
        return source, None


def _within(root, relative):
    source = (root / relative).resolve()
    assignment = root / 'assignment.json'
    if relative != 'assignment.json' and assignment.is_file():
        inputs = json.loads(assignment.read_text(encoding='utf-8')).get('inputs', [])
        if any(item.get('exposure') == 'file_reference'
               and (root / item['relative_path']).resolve() == source for item in inputs):
            raise ValueError('file_reference input is metadata only; a declared control tool streams its exact bytes')
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError('source must be a file within this workspace')
    return source


def _plain_text_input(root, source):
    if not (root / 'assignment.json').exists():
        return False
    assignment = _within(root, 'assignment.json')
    inputs = json.loads(assignment.read_text(encoding='utf-8')).get('inputs', [])
    return any(item.get('relative_path') == source.relative_to(root).as_posix()
               and item.get('media_type', '').split(';', 1)[0].strip().lower() == 'text/plain'
               for item in inputs)


def _structure(value, pointer):
    kind = ('null' if value is None else 'boolean' if isinstance(value, bool) else
        'number' if isinstance(value, (Number, int, float)) else 'string' if isinstance(value, str) else
        'object' if isinstance(value, dict) else 'array')
    result = dict(pointer=pointer, type=kind)
    if isinstance(value, (dict, list)):
        result['count'] = len(value)
    elif kind == 'string':
        result['characters'] = len(value)
    return result


def directory_view(value, pointer):
    """Current-layer structure only; no values, subtree serialization or statistics."""
    result = _structure(value, pointer)
    if isinstance(value, dict):
        result['fields'] = [dict(key=key, **_structure(child,
            pointer + '/' + key.replace('~', '~0').replace('/', '~1'))) for key, child in value.items()]
    elif isinstance(value, list):
        result['index_range'] = [0, len(value) - 1] if value else []
        result['element_pointer_prefix'] = pointer + '/'
    return result


def _selected_text(raw, pointers, directory, *, directory_details=True):
    text = raw.decode('utf-8')
    if not pointers and not directory:
        return text
    def reject_constant(value):
        raise ValueError('non-JSON numeric constant: ' + value)
    value = json.loads(text, parse_int=Number, parse_float=Number, parse_constant=reject_constant)
    parts = []
    choices = pointers or ['']
    for index, pointer in enumerate(choices, 1):
        selected = select(value, pointer)
        if directory:
            selected = directory_view(selected, pointer) if directory_details else (
                list(selected) if isinstance(selected, dict) else
                list(range(len(selected))) if isinstance(selected, list) else [])
        # Ordered fields are individually labelled, never presented as one JSON value.
        parts.append((f'[field {index}]\n' if len(choices) > 1 else '') + encode(selected))
    return '\n'.join(parts)


def _navigation(total, start, end, handle, budget):
    # One short, shell-safe command replays this page; next_offset is a character
    # position in the selected text, while the whole reply is bounded in bytes.
    marker = 'more' if end < total else 'end'
    command = f'--selection {handle} --offset {start} --budget {budget}'
    following = f'; next_offset {end}' if end < total else ''
    return f'[read_input: {marker}; {command}{following}]\n'


def _display(text, start, end, handle, budget):
    return text[start:end] + '\n' + _navigation(len(text), start, end, handle, budget)


def _end(text, start, budget, handle):
    if len(_display(text, start, len(text), handle, budget).encode('utf-8')) <= budget:
        return len(text)
    low, high = start, len(text) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if len(_display(text, start, middle, handle, budget).encode('utf-8')) <= budget:
            low = middle
        else:
            high = middle - 1
    if low == start:
        raise ValueError('reply budget cannot fit the next character')
    return low


def _handle(key, fingerprint):
    # Disposable 128-bit navigation name, not an integrity or permission token.
    # Full source fingerprints are retained and checked separately.
    return hashlib.sha256((key + fingerprint).encode()).hexdigest()[:32]


def _startup_budget(root, source):
    if source != root / 'worker-start.json':
        return None
    config = root / 'tools/input-reader-settings.json'
    if not config.exists():
        return None
    value = json.loads(_within(root, 'tools/input-reader-settings.json').read_text())['startup_page_bytes']
    if type(value) is not int or not SCIENTIFIC_PAGE_MIN_BYTES <= value <= 262144:
        raise ValueError('invalid configured startup page budget')
    return value


def _scientific_descriptor(root, source):
    assignment = root / 'assignment.json'
    if not assignment.is_file():
        return None
    inputs = json.loads(_within(root, 'assignment.json').read_text(encoding='utf-8')).get('inputs', [])
    matches = [item for item in inputs if item.get('relative_path') == source.relative_to(root).as_posix()]
    if len(matches) != 1 or not readable_input(matches[0]):
        return None
    descriptor = matches[0].get('scientific_view')
    return dict(descriptor, handoff_pointer=f'/inputs/{inputs.index(matches[0])}/scientific_view/handoff') if descriptor else None


def read(workspace, name=None, *, pointers=None, directory=False, file=False,
         action='read', budget=None, selection_id=None, offset=None, full=False):
    """Exact model view; navigation is disposable, never a sealed-input attestation.

    Explicit character offsets replay the same page regardless of other reads.
    Legacy next/repeat/restart remain cursor navigation, not delivery acknowledgement.
    """
    if budget is not None and (type(budget) is not int or not SCIENTIFIC_PAGE_MIN_BYTES <= budget <= 262144):
        raise ValueError(f'budget must be {SCIENTIFIC_PAGE_MIN_BYTES}..262144 bytes; scientific inputs remain limited to {SCIENTIFIC_PAGE_MAX_BYTES}')
    if action not in {'read', 'next', 'repeat', 'restart'}:
        raise ValueError('unknown reading action')
    if offset is not None and (type(offset) is not int or offset < 0 or action != 'read'):
        raise ValueError('--offset must be a nonnegative character position, without legacy navigation flags')
    root = Path(workspace).resolve()
    if selection_id is not None:
        if (not isinstance(selection_id, str) or not re.fullmatch(r'[0-9a-f]{32}', selection_id)
                or (name is None and (pointers is not None or file or directory or full))):
            raise ValueError('--selection requires a returned handle; field flags require a complete source')
    implicit = name is None
    if implicit and selection_id is None and (action == 'read' or pointers is not None or file or directory or full):
        raise ValueError('specify a complete source selection, or use bare --next/--repeat/--restart')
    cache = root / CACHE_DIRECTORY
    if cache.is_symlink():
        raise ValueError('navigation cache must be task-local; use direct targeted reading')
    cache.mkdir(mode=0o700, exist_ok=True)
    # The cache is not authority. Avoid following cache-file symlinks beyond the workspace.
    flags = os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW
    with os.fdopen(os.open(cache / 'lock', flags, 0o600), 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = cache / 'navigation.json'
        if state_path.is_symlink():
            raise ValueError('navigation cache must be task-local; use direct targeted reading')
        try:
            state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
            if not isinstance(state, dict):
                raise ValueError('invalid navigation cache')
        except (ValueError, UnicodeError):
            if (selection_id is not None and name is None) or action not in {'read', 'restart'}:
                raise ValueError('navigation cache damaged; specify complete source and fields to recover') from None
            state = {}
        retained_entry = None
        if selection_id is not None:
            entries = [entry for key, entry in state.items()
                if re.fullmatch(r'[0-9a-f]{64}', key) and isinstance(entry, dict)
                and isinstance(entry.get('fingerprint'), str)
                and _handle(key, entry['fingerprint']) == selection_id]
            retained_entry = entries[0] if len(entries) == 1 else None
        restore = implicit
        if not implicit:
            source, source_alias = _source(root, name, file)
            retained = retained_entry.get('selection') if retained_entry is not None else None
            # A supplied source still goes through current path/input checks.
            # The handle may restore omitted fields only for that same source;
            # explicit selection flags continue to be checked against it below.
            restore = (selection_id is not None and pointers is None and not directory and not full
                and isinstance(retained, dict)
                and retained.get('path') == source.relative_to(root).as_posix())
        if restore:
            if selection_id is None:
                selection = state.get('current_selection')
            else:
                selection = retained_entry.get('selection') if retained_entry is not None else None
            if (not isinstance(selection, dict) or not isinstance(selection.get('path'), str)
                    or not isinstance(selection.get('pointers'), list)
                    or not all(isinstance(x, str) for x in selection['pointers'])
                    or type(selection.get('directory')) is not bool
                    or type(selection.get('budget')) is not int
                    or not SCIENTIFIC_PAGE_MIN_BYTES <= selection['budget'] <= 262144):
                raise ValueError('navigation selection missing; specify the complete source and fields once'
                    if selection_id is not None else 'no current selection; specify the source and fields once')
            source = _within(root, selection['path'])
            if implicit:
                source_alias = selection.get('source_alias')
            pointers, directory = selection['pointers'], selection['directory']
            overview = selection.get('scientific_overview', False)
            budget = selection['budget'] if budget is None else budget
        else:
            overview = not full and pointers is None and not directory and not file
            pointers = list(pointers or [])
        descriptor = _scientific_descriptor(root, source) if overview else None
        overview = bool(descriptor)
        startup_budget = _startup_budget(root, source)
        budget = (startup_budget or SCIENTIFIC_PAGE_DEFAULT_BYTES) if budget is None else budget
        if budget > max(startup_budget or 0, SCIENTIFIC_PAGE_MAX_BYTES):
            raise ValueError(f'budget exceeds configured startup limit or scientific-input limit of {SCIENTIFIC_PAGE_MAX_BYTES} bytes')
        selection = dict(path=source.relative_to(root).as_posix(), pointers=pointers,
                         directory=directory, budget=budget, scientific_overview=overview,
                         **({'source_alias': source_alias} if source_alias is not None else {}))
        key = hashlib.sha256(encode([selection['path'], pointers, directory, descriptor]).encode()).hexdigest()
        raw = source.read_bytes()
        fingerprint = hashlib.sha256(raw + (encode(descriptor).encode() if descriptor else b'')).hexdigest()
        previous = state.get(key)
        handle = _handle(key, fingerprint)
        if selection_id is not None and (selection_id != handle or
                (implicit and (not isinstance(previous, dict) or previous.get('fingerprint') != fingerprint))):
            if not implicit and retained_entry is not None:
                retained = retained_entry.get('selection')
                if isinstance(retained, dict) and selection['path'] == retained.get('path'):
                    retained_descriptor = _scientific_descriptor(root, source) if retained.get('scientific_overview') else None
                    retained_fingerprint = hashlib.sha256(raw + (encode(retained_descriptor).encode() if retained_descriptor else b'')).hexdigest()
                    if retained_fingerprint != retained_entry['fingerprint']:
                        raise ValueError('material changed during reading; reselect the source and fields at offset 0')
                raise ValueError('selection mismatch; replay: python tools/read_input.py '
                    f'--selection {selection_id} --offset {offset or 0} --budget {budget}')
            raise ValueError('material changed during reading; select the complete source and fields again')
        start = offset or 0
        if offset and selection_id is None and isinstance(previous, dict) and previous.get('fingerprint') != fingerprint:
            raise ValueError('material changed during reading; reselect the source at offset 0')
        if action in {'next', 'repeat'}:
            if (not isinstance(previous, dict) or
                any(type(previous.get(k)) is not int for k in ('start', 'end')) or
                not 0 <= previous['start'] <= previous['end']):
                raise ValueError('navigation cache missing or damaged; use --restart')
            if previous.get('fingerprint') != fingerprint:
                raise ValueError('material changed during reading; use --restart')
        if overview:
            payload = json.loads(raw.decode('utf-8'), parse_int=Number, parse_float=Number)
            view = compact_scientific_fields(payload, descriptor['pointers'])
            if descriptor.get('handoff') is not None:
                handoff, omissions = compact_handoff(descriptor['handoff'])
                for index, item in enumerate(view['items']):
                    if item.get('status') == 'selected' and type(item.get('value')) is str and item['value'] == handoff.get('summary'):
                        handoff.pop('summary')
                        handoff['summary_ref'] = dict(within='this_view', pointer=f'/items/{index}/value')
                        break
                view['sealed_handoff'] = handoff
                if omissions:
                    view['handoff_omissions'] = omissions
                    view['handoff_original'] = dict(source='assignment.json', pointer=descriptor['handoff_pointer'],
                        read='python tools/read_input.py assignment.json --pointer ' + descriptor['handoff_pointer'])
            view['original'] = dict(source=selection['path'], read='Use the source alias with --full or explicit --pointer; --directory navigates original fields.')
            text = encode(view)
        elif directory and not pointers and _plain_text_input(root, source):
            text = '[read_input: plain text; no field directory. Read the same source without --directory.]'
        else:
            text = _selected_text(raw, pointers, directory)
        if start > len(text):
            raise ValueError('offset outside selected text')
        reply = None
        if (action == 'read' and offset is None and source_alias is not None and isinstance(previous, dict)
                and previous.get('source_alias') not in {None, source_alias}
                and previous.get('fingerprint') == fingerprint
                and all(type(previous.get(k)) is int for k in ('start', 'end'))
                and 0 <= previous['start'] <= previous['end'] <= len(text)):
            start, end = previous['start'], previous['end']
            remaining = len(text) - end
            # A cross-alias hint offers an exact replay even after another source
            # becomes current. It never claims the retained page was delivered/read.
            retained = previous.get('selection')
            retained_budget = retained.get('budget', budget) if isinstance(retained, dict) else budget
            if type(retained_budget) is not int or not SCIENTIFIC_PAGE_MIN_BYTES <= retained_budget <= max(startup_budget or 0, SCIENTIFIC_PAGE_MAX_BYTES):
                raise ValueError('navigation cache damaged; recover with explicit source and --offset')
            reply = ('[read_input: same original selection; cached navigation is not proof of reading. '
                f'{remaining} characters remain after the retained page. '
                'Replay its command below; offset 0 rereads this selection.]\n'
                + _navigation(len(text), start, end, handle, retained_budget))
            if len(reply.encode('utf-8')) > budget:
                raise ValueError('reply budget cannot fit navigation; read with explicit --offset 0')
            selection['budget'] = retained_budget
        if action in {'next', 'repeat'}:
            if previous['end'] > len(text):
                raise ValueError('navigation cache damaged; use --restart')
            start = previous['start'] if action == 'repeat' else previous['end']
            if action == 'repeat':
                end = previous['end']
                retained = previous.get('selection')
                retained_budget = retained.get('budget', budget) if isinstance(retained, dict) else budget
                if type(retained_budget) is not int or not SCIENTIFIC_PAGE_MIN_BYTES <= retained_budget <= max(startup_budget or 0, SCIENTIFIC_PAGE_MAX_BYTES):
                    raise ValueError('navigation cache damaged; recover with explicit source and --offset')
                reply = _display(text, start, end, handle, retained_budget)
                selection['budget'] = retained_budget
                if len(reply.encode('utf-8')) > budget:
                    raise ValueError('repeat needs the previous display budget; or use --restart')
            elif start == len(text):
                start, end = previous['start'], previous['end']
                reply = _display(text, len(text), len(text), handle, budget)
        if reply is None:
            end = _end(text, start, budget, handle)
            reply = _display(text, start, end, handle, budget)
        state[key] = dict(fingerprint=fingerprint, start=start, end=end, selection=selection,
            **({'source_alias': source_alias} if source_alias is not None else {}))
        state['current_selection'] = selection
        fd, temporary = tempfile.mkstemp(dir=cache, prefix='.navigation-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(state, stream, ensure_ascii=False, separators=(',', ':'))
            os.replace(temporary, state_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return reply


def main():
    parser = argparse.ArgumentParser(prog="read_input.py", description=__doc__)
    parser.add_argument('name', nargs='?', help='source_name, unique port, registered relative_path or assignment.json; omit for current-selection navigation')
    parser.add_argument('--selection', dest='selection_id', help='returned content-bound navigation handle; replay it with --offset alone, or repeat the same source/--file without selection flags. After cache loss supply the complete source and fields to verify/recover it.')
    parser.add_argument('--file', action='store_true', help='explicit task-local file instead of input alias')
    parser.add_argument('--full', action='store_true', help='read the exact complete source instead of its declared scientific overview; preserve pagination')
    parser.add_argument('--pointer', dest='pointers', action='append', help='JSON Pointer; repeat for ordered fields')
    parser.add_argument('--offset', type=int, help='character position in selected text (not UTF-8 bytes); replay the same command for the same page, or use next_offset')
    parser.add_argument('--directory', action='store_true', help='current-layer field pointers, types and counts; arrays show index ranges without expanding elements. Exact byte sizes are not computed.')
    actions = parser.add_mutually_exclusive_group()
    for action in ('next', 'repeat', 'restart'):
        actions.add_argument('--' + action, dest='action', action='store_const', const=action)
    parser.set_defaults(action='read')
    parser.add_argument('--budget', type=int, help=f'Scientific inputs: {SCIENTIFIC_PAGE_MIN_BYTES}..{SCIENTIFIC_PAGE_MAX_BYTES} bytes, default {SCIENTIFIC_PAGE_DEFAULT_BYTES}. Controlled startup uses its configured page size. Use --selection with --offset to replay a page; next_offset selects the next page. Legacy bare navigation uses the last selection.')
    args = parser.parse_args()
    try:
        result = read(Path(__file__).resolve().parents[1], **vars(args))
    except (OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError, RecursionError) as error:
        # No absolute paths or source bodies in error responses. Failed reads don't
        # advance navigation and never reject a scientific submission.
        message = error.strerror if isinstance(error, OSError) else str(error)
        message = message.encode('utf-8')[:180].decode('utf-8', errors='ignore')
        print(f'[read_input error: {type(error).__name__}: {message}]')
        return 1
    print(result, end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
