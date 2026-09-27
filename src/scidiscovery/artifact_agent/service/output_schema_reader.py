"""Read exact sections of the Agent authoring form; never validate or rewrite it.

Default: envelope, payload fields, shared rules and required reference closure.
--field NAME also expands that payload field's complete reference closure.
--definitions-only adds field details to an already retained current overview.
--full returns the complete authoring form, never the sealed artifact schema.
--field names a field inside payload, not an envelope member such as handoff.
The CLI keeps only
disposable task-local reading metadata; no scientific state or framework imports.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import fcntl
import os
import tempfile
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, unquote

MAPS = {'properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas', 'dependencies'}
SINGLE = {'items', 'additionalItems', 'additionalProperties', 'unevaluatedProperties',
          'unevaluatedItems', 'propertyNames', 'contains', 'not', 'if', 'then', 'else'}
ARRAYS = {'allOf', 'anyOf', 'oneOf', 'prefixItems'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def pointer(key):
    return str(key).replace('~', '~0').replace('/', '~1')


def children(node, path):
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        location = path + '/' + pointer(key)
        if key in MAPS and isinstance(value, dict):
            for name, child in value.items():
                if isinstance(child, (dict, bool)):
                    yield key, name, child, location + '/' + pointer(name)
        elif key in SINGLE and isinstance(value, (dict, bool)):
            yield key, None, value, location
        elif key in ARRAYS | {'items'} and isinstance(value, list):
            for index, child in enumerate(value):
                yield key, None, child, location + '/' + str(index)


def read_schema(schema, fields=(), *, full=False, definitions_only=False):
    """A reading view, not a replacement JSON Schema. Keep every original rule."""
    origin = {'source': 'schema/result.schema.json',
              'sha256': hashlib.sha256(canonical(schema).encode()).hexdigest()}
    complete = {**origin, 'format': 'full', 'schema': schema}
    if full:
        return complete
    payload = schema.get('properties', {}).get('payload', {}) if isinstance(schema, dict) else {}
    if not isinstance(schema, dict) or schema.get('type') != 'object' or not isinstance(payload, dict) or payload.get('type') != 'object':
        return {**complete, 'fallback': 'unsupported envelope shape'}
    properties = payload.get('properties', {})
    for name in fields:
        if name not in properties:
            raise ValueError('Unknown payload field: ' + name + '. Choose from: '
                + ', '.join(properties) + '. Omit --field for the overview; --full includes handoff. '
                'Do not pass the payload wrapper as a field.')
    nodes, resources, bases, definitions = {}, {'': ''}, {}, []

    def index(node, path='', base=''):
        if isinstance(node, dict) and '$id' in node:
            base = urljoin(base, node['$id'])
            if base in resources and resources[base] != path:
                raise ValueError('ambiguous schema resource: ' + base)
            resources[base] = path
        nodes[path], bases[path] = node, base
        if isinstance(node, dict) and any(k in node for k in ('$dynamicRef', '$recursiveRef', '$anchor', '$dynamicAnchor')):
            raise ValueError('dynamic or anchored schema reference requires full reading')
        for key, name, child, location in children(node, path):
            if key in {'$defs', 'definitions'}:
                definitions.append(location)
            index(child, location, base)

    def resolve(ref, path):
        resource, fragment = urldefrag(urljoin(bases[path], ref))
        if resource not in resources or (fragment and not fragment.startswith('/')):
            raise ValueError('nonlocal or anchored reference: ' + ref)
        target = resources[resource] + unquote(fragment)
        if target not in nodes:
            raise ValueError('unresolved reference: ' + ref)
        return target

    expanded, visited = {}, set()

    def references(node, path, *, required_only=False):
        if not isinstance(node, dict):
            return
        if '$ref' in node:
            target = resolve(node['$ref'], path)
            if target not in visited:
                visited.add(target)
                expanded[target] = copy.deepcopy(nodes[target])
                references(nodes[target], target)  # Complete closure, including cycles.
        for key, name, child, location in children(node, path):
            if key in {'$defs', 'definitions'}:
                continue
            if required_only and key == 'properties' and name not in node.get('required', []):
                continue
            references(child, location, required_only=required_only and key == 'properties')

    def outline(node, path=''):
        value = copy.deepcopy(node)
        if isinstance(value, dict):
            value.pop('$defs', None)
            value.pop('definitions', None)
            for key, name, child, location in children(node, path):
                if key in {'$defs', 'definitions'}:
                    continue
                if key in MAPS:
                    value[key][name] = outline(child, location)
                elif isinstance(node[key], list):
                    value[key][int(location.rsplit('/', 1)[1])] = outline(child, location)
                else:
                    value[key] = outline(child, location)
        return value

    try:
        index(schema)
        if not definitions_only:
            references(schema, '', required_only=True)
        for name in fields:
            references(properties[name], '/properties/payload/properties/' + pointer(name))
    except ValueError as error:
        return {**complete, 'fallback': str(error)}
    result = {**origin, 'format': 'reading_sections',
        'instruction': 'Reading view, not a validator. Before authoring a field, read its full reference closure with --field. Retain the current overview and shared rules; refresh after schema changes. --full returns all originals.',
        'definitions': expanded}
    if definitions_only:
        result['fields'] = {name: copy.deepcopy(properties[name]) for name in fields}
        result['requires'] = 'Current overview of this same source; field details do not replace shared constraints.'
    else:
        result['overview'] = outline(schema)
        result['unexpanded_definitions'] = [p for p in definitions if p not in expanded]
    return result if len(canonical(result)) < len(canonical(complete)) else complete


class SchemaReader:
    """Tool-owned deduplication, not proof of receipt or model memory."""
    def __init__(self, schema, receipt=None):
        self.schema = schema
        self.fingerprint = hashlib.sha256(canonical(schema).encode()).hexdigest()
        valid = (isinstance(receipt, dict) and receipt.get('fingerprint') == self.fingerprint
                 and receipt.get('overview') is True
                 and type(receipt.get('full')) is bool
                 and isinstance(receipt.get('definitions'), list)
                 and all(isinstance(x, str) for x in receipt['definitions']))
        self.receipt = receipt if valid else None

    def read(self, fields=(), *, full=False):
        retained = self.receipt is not None and not full
        view = read_schema(self.schema, fields, full=full, definitions_only=retained)
        if retained and self.receipt['full']:
            result = {'format': 'retained', 'instruction': 'Use the retained full schema; --full rereads it after loss.'}
        elif retained and view['format'] == 'reading_sections':
            definitions = {p:v for p,v in view['definitions'].items()
                           if p not in self.receipt['definitions']}
            result = {'format': 'supplement', 'definitions': definitions,
                'instruction': 'Add these definitions to the retained current overview and earlier definitions; --full restores all rules after loss.'}
            self.receipt = {**self.receipt, 'definitions': sorted(set(self.receipt['definitions']) | set(definitions))}
        else:
            result = {k:v for k,v in view.items() if k not in {'sha256', 'source'}}
            self.receipt = {'fingerprint': self.fingerprint, 'overview': True,
                           'full': view['format'] == 'full',
                           'definitions': sorted(view.get('definitions', {}))}
        return result


def workspace_view(root, fields=(), *, full=False, definitions_only=False):
    # Re-read current bytes on each call, including after tool-evidence refresh.
    schema = json.loads((root/'schema/result.schema.json').read_text(encoding='utf-8'))
    if definitions_only:
        return {k:v for k,v in read_schema(schema, fields, definitions_only=True).items()
                if k not in {'sha256', 'source'}}
    cache = root/'.read-input'
    try:
        if cache.is_symlink():
            raise OSError('nonlocal reading cache')
        cache.mkdir(mode=0o700, exist_ok=True)
        with os.fdopen(os.open(cache/'schema.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            receipt_path = cache/'schema.json'
            if receipt_path.is_symlink():
                raise OSError('nonlocal reading cache')
            try:
                receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                receipt = None
            reader = SchemaReader(schema, receipt)
            result = reader.read(fields, full=full)
            fd, temporary = tempfile.mkstemp(dir=cache, prefix='.schema-')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(canonical(reader.receipt))
                os.replace(temporary, receipt_path)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return result
    except OSError:
        # Never emit a supplement if its navigation state could not be preserved.
        return SchemaReader(schema).read(fields, full=full)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--field', action='append', default=[], help='Payload field to read, repeatable')
    parser.add_argument('--definitions-only', action='store_true')
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        result = workspace_view(root, args.field, full=args.full, definitions_only=args.definitions_only)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Cannot read output schema: {error}\n')
    print(canonical(result))


if __name__ == '__main__':
    main()
