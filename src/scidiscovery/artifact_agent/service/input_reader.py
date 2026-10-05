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


READ_INPUT_NAVIGATION = 2
CACHE_DIRECTORY = ".read-input"


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


def page(workspace, path, *, pointer=None, directory=False, offset=0, version=None, budget=4096):
    if not 512 <= budget <= 8192:
        raise ValueError('budget must be 512..8192 bytes')
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
    text = _selected_text(raw, [pointer] if pointer is not None else [], directory)
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
    fields = ('media_type', 'schema_id', 'size_bytes')
    def compatible(value):
        return (readable_input(value)
            and all(field in value and value[field] == representative.get(field) for field in fields))
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
    assignment = root / 'assignment.json'
    if relative != 'assignment.json' and assignment.is_file():
        inputs = json.loads(assignment.read_text(encoding='utf-8')).get('inputs', [])
        if any(item.get('exposure') == 'file_reference' and item.get('relative_path') == str(relative) for item in inputs):
            raise ValueError('file_reference input is metadata only; a declared control tool streams its exact bytes')
    source = (root / relative).resolve()
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


def _selected_text(raw, pointers, directory):
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
            selected = (list(selected) if isinstance(selected, dict) else
                        list(range(len(selected))) if isinstance(selected, list) else [])
        # Ordered fields are individually labelled, never presented as one JSON value.
        parts.append((f'[field {index}]\n' if len(choices) > 1 else '') + encode(selected))
    return '\n'.join(parts)


def _display(text, start, end):
    marker = 'more; --next' if end < len(text) else 'end'
    return text[start:end] + f'\n[read_input: {marker}]\n'


def _end(text, start, budget):
    if len(_display(text, start, len(text)).encode('utf-8')) <= budget:
        return len(text)
    low, high = start, len(text) - 1
    while low < high:
        middle = (low + high + 1) // 2
        if len(_display(text, start, middle).encode('utf-8')) <= budget:
            low = middle
        else:
            high = middle - 1
    if low == start:
        raise ValueError('reply budget cannot fit the next character')
    return low


def _startup_budget(root, source):
    if source != root / 'worker-start.json':
        return None
    config = root / 'tools/input-reader-settings.json'
    if not config.exists():
        return None
    value = json.loads(_within(root, 'tools/input-reader-settings.json').read_text())['startup_page_bytes']
    if type(value) is not int or not 512 <= value <= 262144:
        raise ValueError('invalid configured startup page budget')
    return value


def read(workspace, name=None, *, pointers=None, directory=False, file=False,
         action='read', budget=None):
    """Exact model view; navigation is disposable, never a sealed-input attestation.

    Consume a selection sequentially. After an uncertain reply use repeat, not next;
    if a later next already advanced it, restart. No delivery acknowledgement exists.
    """
    if budget is not None and (type(budget) is not int or not 512 <= budget <= 262144):
        raise ValueError('budget must be 512..262144 bytes; scientific inputs remain limited to 8192')
    if action not in {'read', 'next', 'repeat', 'restart'}:
        raise ValueError('unknown reading action')
    root = Path(workspace).resolve()
    implicit = name is None
    if implicit and (action == 'read' or pointers is not None or file or directory):
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
            if action not in {'read', 'restart'}:
                raise ValueError('navigation cache damaged; use --restart') from None
            state = {}
        if implicit:
            selection = state.get('current_selection')
            if (not isinstance(selection, dict) or not isinstance(selection.get('path'), str)
                    or not isinstance(selection.get('pointers'), list)
                    or not all(isinstance(x, str) for x in selection['pointers'])
                    or type(selection.get('directory')) is not bool
                    or type(selection.get('budget')) is not int
                    or not 512 <= selection['budget'] <= 262144):
                raise ValueError('no current selection; specify the source and fields once')
            source = _within(root, selection['path'])
            source_alias = selection.get('source_alias')
            pointers, directory = selection['pointers'], selection['directory']
            budget = selection['budget'] if budget is None else budget
        else:
            source, source_alias = _source(root, name, file)
            pointers = list(pointers or [])
        startup_budget = _startup_budget(root, source)
        budget = (startup_budget or 4096) if budget is None else budget
        if budget > max(startup_budget or 0, 8192):
            raise ValueError('budget exceeds configured startup limit or scientific-input limit of 8192 bytes')
        selection = dict(path=source.relative_to(root).as_posix(), pointers=pointers,
                         directory=directory, budget=budget,
                         **({'source_alias': source_alias} if source_alias is not None else {}))
        key = hashlib.sha256(encode([selection['path'], pointers, directory]).encode()).hexdigest()
        raw = source.read_bytes()
        fingerprint = hashlib.sha256(raw).hexdigest()
        previous = state.get(key)
        start = 0
        if action in {'next', 'repeat'}:
            if (not isinstance(previous, dict) or
                any(type(previous.get(k)) is not int for k in ('start', 'end')) or
                not 0 <= previous['start'] <= previous['end']):
                raise ValueError('navigation cache missing or damaged; use --restart')
            if previous.get('fingerprint') != fingerprint:
                raise ValueError('material changed during reading; use --restart')
        if directory and not pointers and _plain_text_input(root, source):
            text = '[read_input: plain text; no field directory. Read the same source without --directory.]'
        else:
            text = _selected_text(raw, pointers, directory)
        reply = None
        if (action == 'read' and source_alias is not None and isinstance(previous, dict)
                and previous.get('source_alias') not in {None, source_alias}
                and previous.get('fingerprint') == fingerprint
                and all(type(previous.get(k)) is int for k in ('start', 'end'))
                and 0 <= previous['start'] <= previous['end'] <= len(text)):
            start, end = previous['start'], previous['end']
            remaining = len(text) - end
            reply = ('[read_input: same original selection; cached navigation is not proof of reading. '
                '--repeat recovers the last page; --restart rereads from the beginning. '
                f'{remaining} characters remain after that page; --next continues.]\n'
                + ('[read_input: more; --next]\n' if remaining else '[read_input: end]\n'))
        if action in {'next', 'repeat'}:
            if previous['end'] > len(text):
                raise ValueError('navigation cache damaged; use --restart')
            start = previous['start'] if action == 'repeat' else previous['end']
            if action == 'repeat':
                end = previous['end']
                reply = _display(text, start, end)
                if len(reply.encode('utf-8')) > budget:
                    raise ValueError('repeat needs the previous display budget; or use --restart')
            elif start == len(text):
                start, end = previous['start'], previous['end']
                reply = '[read_input: end]\n'
        if reply is None:
            end = _end(text, start, budget)
            reply = _display(text, start, end)
        state[key] = dict(fingerprint=fingerprint, start=start, end=end,
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
    parser.add_argument('--file', action='store_true', help='explicit task-local file instead of input alias')
    parser.add_argument('--pointer', dest='pointers', action='append', help='JSON Pointer; repeat for ordered fields')
    parser.add_argument('--directory', action='store_true', help='list only direct keys')
    actions = parser.add_mutually_exclusive_group()
    for action in ('next', 'repeat', 'restart'):
        actions.add_argument('--' + action, dest='action', action='store_const', const=action)
    parser.set_defaults(action='read')
    parser.add_argument('--budget', type=int, help='Scientific inputs: 512..8192 bytes, default 4096. Controlled startup uses its configured page size. Use --next for remaining text; bare navigation retains the budget.')
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
