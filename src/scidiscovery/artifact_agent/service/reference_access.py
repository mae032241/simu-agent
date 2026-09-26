"""Bound, one-hop reference access; retained objects never become new products."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
import uuid

from ..schema.common import canonical_json
from ..schema.refs import ArtifactRef
from .run_records import RunStateConflict, timestamp


class ReferenceAccessError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _digest(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _ref(value):
    return value if isinstance(value, ArtifactRef) else ArtifactRef.model_validate(value)


def _portable_response(response):
    # The current workspace path is a delivery address, not durable evidence.
    return {key: value for key, value in response.items() if key != 'file_path'}


def _escape(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def _pointer(value, pointer):
    if not pointer:
        return value
    if not pointer.startswith('/'):
        raise ReferenceAccessError('reference_selector_invalid', 'Expected a JSON Pointer.')
    for part in pointer[1:].split('/'):
        if '~' in part.replace('~0', '').replace('~1', ''):
            raise ReferenceAccessError('reference_selector_invalid', 'Invalid JSON Pointer escape.')
        key = part.replace('~1', '/').replace('~0', '~')
        try:
            value = value[int(key)] if isinstance(value, list) and key.isdigit() else value[key]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ReferenceAccessError('reference_selector_missing', f'JSON Pointer does not resolve: {pointer}') from error
    return value


def _matches(value, path, locator=''):
    if not path:
        yield locator, value
        return
    token, *rest = path
    if token == '*':
        items = enumerate(value) if isinstance(value, list) else value.items() if isinstance(value, dict) else ()
        for key, child in items:
            yield from _matches(child, rest, locator + '/' + _escape(key))
    elif isinstance(value, dict) and token in value:
        yield from _matches(value[token], rest, locator + '/' + _escape(token))


def _calculation_origin(manifest, calculation):
    """Choose one exact attempt namespace, including a sealed recovery origin."""
    from ..schema.tool_evidence import ToolEvidenceManifest
    proof = ToolEvidenceManifest.model_validate_json(canonical_json(manifest)) if isinstance(manifest, dict) else manifest
    origins = [proof]
    if proof.recovery is not None:
        origins.extend([proof.recovery, *proof.recovery.ancestors])
    candidates = {}
    for origin in origins:
        attempts = [a for a in origin.attempts if a.attempt_key == calculation.attempt.attempt_key
                    and a.request_digest == _digest(calculation.request)]
        if len(attempts) != 1:
            continue
        if all(name in origin.bindings and origin.bindings[name].artifact_ref.sha256 == digest
               for name, digest in calculation.input_digests.items()):
            candidates[_digest({'bindings': origin.bindings, 'attempts': origin.attempts})] = (origin, attempts[0])
    if len(candidates) != 1:
        raise ReferenceAccessError('reference_attempt_unpaired', 'Calculation attempt origin is missing or ambiguous.')
    return next(iter(candidates.values()))


class ReferenceAccessMixin:
    def reference_access_records(self, run_id):
        with self._connect() as connection:
            rows = connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=? ORDER BY ordinal', (run_id,)).fetchall()
        return [record for row in rows if (record := json.loads(row[0])).get('record_type') == 'reference_access']

    def _reference_policy(self, value, policy=None):
        from ...operations.tooling import operation_worker_tools
        policies = [tool.reference_policy for tool in operation_worker_tools(self._compiled(value))
                    if getattr(tool, 'reference_policy', None) is not None]
        if len(policies) != 1 or (policy is not None and policy != policies[0]):
            raise ReferenceAccessError('reference_capability_missing', 'This Operation has no matching reference access capability.')
        return policies[0]

    def _reference_scope(self, connection, run_id):
        current = run_id
        seen = set()
        instance = self._row(connection, current)['instance_id']
        while current not in seen:
            seen.add(current)
            row = self._row(connection, current)
            if row['instance_id'] != instance:
                raise ReferenceAccessError('reference_instance_mismatch', 'Recovery scope crosses an instance.')
            parent = row['draft_from_run_id'] or row['resume_from_run_id']
            if not parent:
                return current
            current = parent
            if len(seen) >= 128:
                break
        raise ReferenceAccessError('reference_recovery_invalid', 'Recovery scope is cyclic or exceeds its bound.')

    def _reference_events(self, connection, scope):
        # Indexed activity kinds bound the scan; each scope's own immutable tag
        # survives loss of a formerly authorized root input.
        rows = connection.execute("SELECT activity,diagnostic_json FROM run_activity WHERE activity IN ('reference_read_reserved','reference_read_settled','reference_material_reserved','reference_io_reserved') AND json_extract(CAST(diagnostic_json AS TEXT),'$.budget_scope')=?", (scope,)).fetchall()
        return [(row['activity'], record) for row in rows
                if (record := json.loads(row['diagnostic_json'])).get('budget_scope') == scope]

    def _reference_usage(self, connection, scope):
        events = self._reference_events(connection, scope)
        reservations = {r['reservation_id']: r for kind, r in events if kind == 'reference_read_reserved'}
        settlements = {r['reservation_id']: r for kind, r in events if kind == 'reference_read_settled'}
        return {
            'calls': len(reservations),
            'response_bytes': sum(settlements.get(key, r)['response_bytes'] for key, r in reservations.items()),
            'seconds': sum(settlements.get(key, r)['seconds'] for key, r in reservations.items()),
            'io_bytes': sum(r['bytes'] for kind, r in events if kind == 'reference_io_reserved'),
            'materials': {r['ref_key']: r['bytes'] for kind, r in events if kind == 'reference_material_reserved'},
        }

    def _reference_event(self, connection, run_id, kind, value):
        self._append_activity(connection, run_id, kind, timestamp(), canonical_json(value))

    def _reference_running(self, connection, run_id):
        row = self._row(connection, run_id)
        if row['state'] != 'running' or row['accepted_candidate_digest'] is not None:
            raise RunStateConflict('Run no longer accepts reference access')

    def _reference_reserve(self, value, request, policy):
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            self._reference_running(connection, value.run_id)
            scope = self._reference_scope(connection, value.run_id)
            usage = self._reference_usage(connection, scope)
            seconds = min(policy.max_call_seconds, policy.max_io_seconds - usage['seconds'])
            if usage['calls'] >= policy.max_calls or seconds <= 0 or usage['response_bytes'] + request.limit > policy.max_response_bytes:
                raise ReferenceAccessError('reference_budget_exhausted', 'Reference call, time or response budget exhausted.')
            reservation = {'reservation_id': uuid.uuid4().hex, 'budget_scope': scope,
                           'response_bytes': request.limit, 'seconds': seconds}
            self._reference_event(connection, value.run_id, 'reference_read_reserved', reservation)
            return reservation

    def _reference_read_bytes(self, value, ref, policy, call, *, material=False):
        self._reference_deadline(call)
        envelope = self.artifacts.catalog(ref)
        if envelope.size_bytes > policy.max_file_bytes:
            raise ReferenceAccessError('reference_file_limit', 'Original exceeds the declared single-file byte limit.')
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            self._reference_running(connection, value.run_id)
            usage = self._reference_usage(connection, call['budget_scope'])
            key = _digest(ref.model_dump(mode='json'))
            if material and key not in usage['materials']:
                if sum(usage['materials'].values()) + envelope.size_bytes > policy.max_unique_bytes:
                    raise ReferenceAccessError('reference_material_limit', 'Unique original-material budget exhausted.')
                self._reference_event(connection, value.run_id, 'reference_material_reserved', {
                    'budget_scope': call['budget_scope'], 'reservation_id': call['reservation_id'],
                    'ref_key': key, 'bytes': envelope.size_bytes})
            if usage['io_bytes'] + envelope.size_bytes > policy.max_io_bytes:
                raise ReferenceAccessError('reference_io_limit', 'Cumulative original IO budget exhausted.')
            self._reference_event(connection, value.run_id, 'reference_io_reserved', {
                'budget_scope': call['budget_scope'], 'reservation_id': call['reservation_id'], 'bytes': envelope.size_bytes})
        raw = self.artifacts.read(ref)
        self._reference_deadline(call)
        if len(raw) != envelope.size_bytes or hashlib.sha256(raw).hexdigest() != ref.sha256:
            raise ReferenceAccessError('reference_integrity_failure', 'Original size or hash differs from its exact Ref.')
        return raw

    @staticmethod
    def _reference_deadline(call):
        if time.monotonic() > call['deadline']:
            raise ReferenceAccessError('reference_time_limit', 'Reference IO exceeded its reserved time; no source was committed.')

    def _reference_roots(self, value):
        visible = {port.name for port in self._compiled(value).spec.inputs if port.agent_visible and port.exposure not in {'handoff_only', 'file_reference'}}
        return tuple(item for item in value.inputs if item.port_name in visible)

    def _reference_alias(self, value, target):
        visible = next((item.source_name for item in self._reference_roots(value) if item.artifact_ref == target), None)
        if visible is not None:
            return visible
        existing = next((r['alias'] for r in self.reference_access_records(value.run_id)
                         if _ref(r['artifact_ref']) == target), None)
        return existing or 'reference_' + _digest(target.model_dump(mode='json'))[:24]

    @staticmethod
    def _reference_request_key(value, request, policy, root, chain, source):
        return 'reference:' + _digest({'run': value.run_id, 'operation': value.operation_digest,
            'policy': asdict(policy), 'root': root.model_dump(mode='json'), 'chain': chain,
            'source_ref': source.model_dump(mode='json'), 'request': request.model_dump(mode='json')})

    def _reference_current_material(self, value, alias):
        visible = {port.name for port in self._compiled(value).spec.outputs if port.agent_visible}
        record = next((item for item in self.tool_evidence(value.run_id) if item['alias'] == alias), None)
        if record is None:
            return None
        envelope = self.artifacts.catalog(_ref(record['artifact_ref']))
        if (envelope.labels.get('operation_output_port') not in visible
                or envelope.schema_id == 'scidiscovery.tool-evidence-manifest.v1'):
            return None
        return record

    def _reference_source(self, value, alias, policy):
        source = next((item for item in self._reference_roots(value) if item.source_name == alias), None)
        if source is not None:
            return source.artifact_ref, source.artifact_ref, []
        material = self._reference_current_material(value, alias)
        if material is not None:
            ref = _ref(material['artifact_ref'])
            return ref, ref, []
        record = next((r for r in self.reference_access_records(value.run_id) if r['alias'] == alias), None)
        if record is None or record['policy_digest'] != _digest(asdict(policy)) or record['operation_digest'] != value.operation_digest:
            raise ReferenceAccessError('reference_source_unknown', 'Source is not a frozen input or a current committed access alias.')
        root = _ref(record['root_ref'])
        if root not in {item.artifact_ref for item in self._reference_roots(value)}:
            raise ReferenceAccessError('reference_root_missing', 'The exact frozen root is no longer bound.')
        return _ref(record['artifact_ref']), root, record['chain']

    def _reference_pair(self, value, source_ref, policy, call, root_ref=None):
        producer = self.completed_for_output(source_ref)
        authorized_manifest = None
        if producer is None:
            receipts = [r for r in self.reference_access_records(value.run_id)
                        if _ref(r['artifact_ref']) == source_ref and (root_ref is None or _ref(r['root_ref']) == root_ref)]
            pairings = {(r.get('proof_run_id') or r['authorizing_run_id'],
                         canonical_json(r.get('proof_manifest_ref') or r['authorizing_manifest_ref'])) for r in receipts}
            if len(pairings) == 1:
                producer_id, manifest_raw = next(iter(pairings))
                producer = self.status(producer_id)
                authorized_manifest = _ref(json.loads(manifest_raw))
        if producer is None or producer.state != 'completed' or producer.output_ref is None:
            raise ReferenceAccessError('reference_producer_missing', 'Source has no exact completed producer; bind required originals explicitly.')
        if producer.instance_id != value.instance_id:
            raise ReferenceAccessError('reference_instance_mismatch', 'Source producer belongs to another instance.')
        candidates = []
        for ref in self.artifacts.catalog(producer.output_ref).parent_refs:
            if ref.schema_id == 'scidiscovery.tool-evidence-manifest.v1':
                envelope = self.artifacts.catalog(ref)
                if envelope.labels.get('tool_producer_run') == producer.run_id:
                    candidates.append(ref)
        if len(candidates) != 1 or (authorized_manifest is not None and candidates[0] != authorized_manifest):
            raise ReferenceAccessError('reference_manifest_unpaired', 'Expected one exact producer-bound manifest.')
        manifest_ref = candidates[0]
        manifest = json.loads(self._reference_read_bytes(value, manifest_ref, policy, call))
        bindings = manifest.get('bindings', {})
        records = manifest.get('records', [])
        if not isinstance(bindings, dict) or not isinstance(records, list):
            raise ReferenceAccessError('reference_manifest_invalid', 'Producer manifest has invalid bindings or records.')
        # Every binding must remain an exact parent of this producer manifest.
        parents = self.artifacts.catalog(manifest_ref).parent_refs
        for binding in bindings.values():
            if _ref(binding['artifact_ref']) not in parents:
                raise ReferenceAccessError('reference_manifest_unpaired', 'Manifest binding is not an exact manifest parent.')
        selected = None
        if source_ref != producer.output_ref:
            matches = [record for record in records if _ref(record['artifact_ref']) == source_ref]
            if len(matches) != 1:
                raise ReferenceAccessError('reference_record_unpaired', 'Tool original is not uniquely recorded in its producer manifest.')
            selected = matches[0]
        return producer, manifest, selected, manifest_ref

    def _reference_calculation_origin(self, value, manifest, calculation, policy, call):
        alias = calculation.attempt.manifest_alias
        if alias != 'tool_recovery_manifest':
            binding = manifest.get('bindings', {}).get(alias)
            if binding is None:
                raise ReferenceAccessError('reference_attempt_unpaired', 'Calculation proof manifest is not bound in its sealed report.')
            proof_ref = _ref(binding['artifact_ref'])
            proof_owner = self.artifacts.catalog(proof_ref).labels.get('tool_producer_run')
            if proof_ref.schema_id != 'scidiscovery.tool-evidence-manifest.v1' or not proof_owner:
                raise ReferenceAccessError('reference_manifest_unpaired', 'Calculation proof is not a producer-bound manifest.')
            producer = self.status(proof_owner)
            if producer.output_ref is None:
                raise ReferenceAccessError('reference_manifest_unpaired', 'Calculation proof producer has no sealed report.')
            _, manifest, _, paired_ref = self._reference_pair(value, producer.output_ref, policy, call)
            if paired_ref != proof_ref:
                raise ReferenceAccessError('reference_manifest_unpaired', 'Calculation proof differs from its producer manifest.')
        return _calculation_origin(manifest, calculation)

    def _reference_edges(self, value, source_ref, policy, call, pointer=None, reference=None, root_ref=None):
        producer, manifest, selected, manifest_ref = self._reference_pair(value, source_ref, policy, call, root_ref)
        raw = self._reference_read_bytes(value, source_ref, policy, call)
        rules = [rule for rule in policy.rules if rule.schema_id == source_ref.schema_id]
        aliases = []
        sections = []
        alias_mapping = {}
        alias_scopes = {}
        scoped_bindings = manifest.get('bindings', {})
        scoped_records = manifest.get('records', [])
        known_aliases = set(scoped_bindings) | {r['alias'] for r in scoped_records}
        if rules or (selected and selected.get('metadata', {}).get('kind') == 'calculation_record'):
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeError) as error:
                raise ReferenceAccessError('reference_schema_invalid', 'Declared structured reference source is not valid JSON.') from error
            if source_ref.schema_id == 'scidiscovery.layered-diagnosis.v1':
                from types import SimpleNamespace
                from .analysis_artifacts import analysis_evidence_aliases
                references = [SimpleNamespace(**item) for item in document.get('source_references', ())]
                evidence = [SimpleNamespace(**item) for item in document.get('evidence', ())]
                known = set(manifest.get('bindings', {})) | {r['alias'] for r in manifest.get('records', ())}
                alias_mapping = analysis_evidence_aliases(evidence, references, known)
            for rule in rules:
                if rule.producer_input_alias is not None:
                    aliases.append(('/@producer_inputs/' + _escape(rule.producer_input_alias),
                                    rule.producer_input_alias, None))
                    continue
                for locator, item in _matches(document, rule.path.lstrip('/').split('/')):
                    if rule.selected_only:
                        section = locator.rsplit('/', 1)[0]
                        if reference is None and (not pointer or section != pointer):
                            if (not pointer or section.startswith(pointer + '/')) and section not in sections:
                                sections.append(section)
                            continue
                    if pointer and not (locator == pointer or locator.startswith(pointer + '/')):
                        continue
                    if rule.keys and isinstance(item, dict):
                        if rule.selected_only:
                            calculation = _pointer(document, section)
                            if calculation.get('attempt') is not None:
                                from .calculation_proof import ControlledCalculationRecord as CalculationRecord, controlled_calculation
                                origin, _ = self._reference_calculation_origin(value, manifest,
                                    CalculationRecord.model_validate_json(canonical_json(calculation)), policy, call)
                                bindings = {name: binding.model_dump(mode='json')
                                            for name, binding in origin.bindings.items()}
                                # Scope each edge, not the report: separate calculations
                                # may use the same alias for different original inputs.
                                alias_scopes.update((locator + '/' + _escape(alias), (bindings, []))
                                                    for alias in item)
                        aliases.extend((locator + '/' + _escape(alias), alias, digest) for alias, digest in item.items())
                    elif isinstance(item, str):
                        if rule.locator_prefix and item.split(':', 1)[0] not in known_aliases:
                            # A locator can describe a position within source_key;
                            # only an actual bound prefix is another source claim.
                            continue
                        alias = item.split(':', 1)[0] if rule.locator_prefix else alias_mapping.get(item, item)
                        aliases.append((locator, alias, None))
            if selected and selected.get('metadata', {}).get('kind') == 'calculation_record':
                from .calculation_proof import controlled_calculation
                calculation = controlled_calculation(raw, selected)
                origin, _ = _calculation_origin(manifest, calculation)
                scoped_bindings = {name: binding.model_dump(mode='json') for name, binding in origin.bindings.items()}
                scoped_records = []
                aliases.extend(('/sources/' + _escape(alias), alias, digest)
                    for alias, digest in calculation.input_digests.items())
        if selected:
            aliases.extend(('/@metadata/derived_from/' + str(index), alias, None)
                           for index, alias in enumerate(selected.get('metadata', {}).get('derived_from', ())))
        edges = []
        for locator, alias, expected_digest in aliases:
            self._reference_deadline(call)
            bindings, records = alias_scopes.get(locator, (scoped_bindings, scoped_records))
            candidates = []
            if alias in bindings:
                candidates.append(_ref(bindings[alias]['artifact_ref']))
            candidates.extend(_ref(record['artifact_ref']) for record in records if record.get('alias') == alias)
            candidates = list(dict.fromkeys(candidates))
            if len(candidates) != 1:
                edges.append({'locator': locator, 'alias': alias, 'error': 'reference_binding_missing' if not candidates else 'reference_binding_ambiguous'})
                continue
            target = candidates[0]
            if expected_digest is not None and expected_digest != target.sha256:
                edges.append({'locator': locator, 'alias': alias, 'error': 'reference_digest_mismatch'})
                continue
            edge = {'source_ref': source_ref.model_dump(mode='json'), 'locator': locator,
                    'target_ref': target.model_dump(mode='json')}
            handle = 'ref_' + _digest(edge)
            if reference is not None and handle != reference:
                continue
            target_producer = self.completed_for_output(target)
            if target_producer is not None and target_producer.instance_id != value.instance_id:
                edges.append({'locator': locator, 'alias': alias, 'error': 'reference_instance_mismatch'})
                continue
            target_envelope = self.artifacts.catalog(target)
            original_id = target_envelope.labels.get('tool_producer_run')
            if target_producer is None and original_id and any(
                    _ref(r['artifact_ref']) == target for r in self.tool_evidence(original_id)):
                target_producer = self.status(original_id)
                if target_producer.instance_id != value.instance_id:
                    edges.append({'locator': locator, 'alias': alias, 'error': 'reference_instance_mismatch'})
                    continue
            original_proof = None
            if any(_ref(r['artifact_ref']) == target for r in manifest.get('records', ())):
                original_proof = (producer.run_id, manifest_ref.model_dump(mode='json'))
            else:
                inherited = {(r.get('proof_run_id'), canonical_json(r.get('proof_manifest_ref')))
                    for r in manifest.get('accesses', ()) if r.get('alias') == alias
                    and _ref(r['artifact_ref']) == target and r.get('proof_manifest_ref') is not None}
                if len(inherited) > 1:
                    edges.append({'locator': locator, 'alias': alias, 'error': 'reference_proof_ambiguous'})
                    continue
                if inherited:
                    origin_run, origin_ref = next(iter(inherited))
                    original_proof = (origin_run, json.loads(origin_ref))
            if (original_proof is None and target_producer is not None
                    and target_producer.state == 'completed' and target_producer.output_ref != target):
                original_run, _, original_record, original_manifest = self._reference_pair(value, target, policy, call)
                if original_record is not None:
                    original_proof = (original_run.run_id, original_manifest.model_dump(mode='json'))
            edges.append({'reference': handle, 'locator': locator, 'alias': alias,
                          'media_type': target_envelope.media_type, 'size_bytes': target_envelope.size_bytes,
                          '_edge': edge, '_producer': target_producer.run_id if target_producer else None,
                          '_manifest_ref': manifest_ref.model_dump(mode='json'), '_manifest_run': producer.run_id,
                          '_proof_run': original_proof[0] if original_proof else None,
                          '_proof_manifest': original_proof[1] if original_proof else None})
        return edges, sections

    def _reference_settle(self, connection, value, call, response, *, request_key=None):
        encoded = canonical_json(response)
        if len(encoded) > call['response_bytes']:
            raise ReferenceAccessError('reference_response_limit', 'Encoded reference response exceeds the requested byte budget.')
        self._reference_event(connection, value.run_id, 'reference_read_settled', {
            'budget_scope': call['budget_scope'], 'reservation_id': call['reservation_id'],
            'response_bytes': len(encoded), 'seconds': max(0, time.monotonic() - call['started']),
            'request_key': request_key, 'response': _portable_response(response)})

    def _reference_delivery_response(self, run_id, response):
        response = _portable_response(response)
        if response.get('provided', {}).get('kind') == 'file_access':
            response['file_path'] = str(self.backend.open(run_id).root / '.reference-access' / (response['source'] + '.bin'))
        return response

    def _reference_publish_file(self, run_id, response, raw):
        if 'file_path' not in response:
            return
        # The exact CAS object and response are committed first. A crash before
        # materialization is recovered by replay; no uncommitted file is exposed.
        from .local_workspace import write_control_workspace_file
        write_control_workspace_file(self.backend.open(run_id).root,
            Path('.reference-access') / (response['source'] + '.bin'),
            raw, replace=True, mode=0o400, create_parents=True)

    def reference_read(self, run_id, request, policy):
        value = self._require_running(run_id)
        policy = self._reference_policy(value, policy)
        try:
            call = self._reference_reserve(value, request, policy)
        except ReferenceAccessError as error:
            return {'state': 'rejected', 'code': error.code, 'message': str(error)}
        call['started'] = time.monotonic()
        call['deadline'] = call['started'] + call['seconds']
        committed = False
        source_authorized = False
        try:
            source, root, chain = self._reference_source(value, request.source, policy)
            source_authorized = True
            if len(chain) >= policy.max_depth:
                raise ReferenceAccessError('reference_depth_limit', 'Reference chain reached the declared depth limit.')
            request_key = self._reference_request_key(value, request, policy, root, chain, source)
            with self._connect() as connection:
                existing = connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=? AND evidence_key=?', (run_id, request_key)).fetchone()
            if existing:
                original_record = json.loads(existing[0])
                response = self._reference_delivery_response(run_id, original_record['response'])
                raw = b''
                if 'file_path' in response:
                    raw = self._reference_read_bytes(value, _ref(original_record['artifact_ref']), policy, call, material=True)
                with self._connect() as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    self._reference_running(connection, run_id)
                    self._reference_settle(connection, value, call, response, request_key=request_key)
                committed = True
                self._reference_publish_file(run_id, response, raw)
                return response
            current_material = self._reference_current_material(value, request.source)
            if current_material is not None:
                # The current Run already owns this immutable scientific source;
                # reading it does not create another provenance receipt or alias.
                edges = [{'reference': 'content', 'alias': request.source,
                    'media_type': current_material['media_type'], 'size_bytes': current_material['size_bytes'],
                    '_edge': {'target_ref': current_material['artifact_ref']}}]
                sections = []
            else:
                edges, sections = self._reference_edges(value, source, policy, call, request.pointer if request.action == 'list' else None,
                    request.reference if request.action == 'read' else None, root)
            if request.action == 'list':
                items = [{k: v for k, v in edge.items() if not k.startswith('_')} for edge in edges]
                items.extend({'section': section, 'action': 'list', 'pointer': section} for section in sections)
                page = []
                response = {'source': request.source, 'action': 'list', 'references': page, 'next_cursor': None, 'omitted': 0}
                for item in items[request.cursor:request.cursor + 8]:
                    page.append(item)
                    response.update(next_cursor=request.cursor + len(page), omitted=max(0, len(items) - request.cursor - len(page)))
                    if len(canonical_json(response)) > request.limit:
                        page.pop()
                        break
                if request.cursor < len(items) and not page:
                    raise ReferenceAccessError('reference_response_limit', 'This directory entry needs a larger response limit.')
                next_cursor = request.cursor + len(page)
                response.update(next_cursor=next_cursor if next_cursor < len(items) else None, omitted=max(0, len(items) - next_cursor))
                with self._connect() as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    self._reference_running(connection, run_id)
                    self._reference_deadline(call)
                    self._reference_settle(connection, value, call, response, request_key=request_key)
                return response
            # Selected inline calculation edges are resolved only by the exact
            # locator encoded by a directory handle, never by guessed aliases.
            matches = [edge for edge in edges if edge.get('reference') == request.reference]
            if len(matches) != 1:
                raise ReferenceAccessError('reference_handle_invalid', 'Reference handle is not uniquely authorized by this exact source.')
            selected = matches[0]
            edge = selected['_edge']
            target = _ref(edge['target_ref'])
            raw = self._reference_read_bytes(value, target, policy, call, material=True)
            alias = request.source if current_material is not None else self._reference_alias(value, target)
            response = {'action': 'read', 'source': alias, 'media_type': selected['media_type'],
                        'provided': {'pointer': request.pointer, 'offset': request.offset, 'characters': 0}, 'next_offset': None, 'omitted': False}
            envelope = self.artifacts.catalog(target)
            textual = envelope.media_type.startswith('text/') or 'json' in envelope.media_type
            if textual and request.delivery == 'fragment':
                try:
                    text = raw.decode('utf-8')
                    if request.pointer is not None:
                        text = canonical_json(_pointer(json.loads(text), request.pointer)).decode('utf-8')
                except (UnicodeError, ValueError) as error:
                    if isinstance(error, ReferenceAccessError):
                        raise
                    raise ReferenceAccessError('reference_text_invalid', 'Selected original is not valid UTF-8/JSON.') from error
                if request.offset > len(text):
                    raise ReferenceAccessError('reference_selector_missing', 'Character offset exceeds the selected text.')
                remaining = text[request.offset:]
                lo, hi = 0, min(len(remaining), request.limit)
                while lo < hi:
                    count = (lo + hi + 1) // 2
                    response['provided']['characters'] = count
                    response.update(fragment=remaining[:count], next_offset=request.offset + count if count < len(remaining) else None, omitted=count < len(remaining))
                    if len(canonical_json(response)) <= request.limit:
                        lo = count
                    else:
                        hi = count - 1
                response.update(fragment=remaining[:lo], next_offset=request.offset + lo if lo < len(remaining) else None, omitted=lo < len(remaining))
                if remaining and not lo:
                    raise ReferenceAccessError('reference_response_limit', 'Response budget cannot hold the selected range.')
                response['provided']['characters'] = lo
            else:
                if 'native_workspace' not in getattr(self.backend, 'capabilities', ()):
                    raise ReferenceAccessError('file_access_unavailable' if textual else 'binary_file_access_unavailable',
                        'This backend has no native read-only file access; bind a supported representation explicitly.')
                if request.pointer is not None or request.offset:
                    raise ReferenceAccessError('reference_selector_invalid', 'Binary originals require an unselected file-access request.')
                workspace = self.backend.open(run_id)
                response.update(file_path=str(workspace.root / '.reference-access' / (alias + '.bin')))
                response['provided']['kind'] = 'file_access'
            if current_material is not None:
                self._reference_deadline(call)
                with self._connect() as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    self._reference_running(connection, run_id)
                    self._reference_settle(connection, value, call, response, request_key=request_key)
                committed = True
                self._reference_publish_file(run_id, response, raw)
                return response
            record = {'record_type': 'reference_access', 'alias': alias, 'artifact_ref': target.model_dump(mode='json'),
                'media_type': envelope.media_type, 'size_bytes': envelope.size_bytes, 'access_run_id': run_id,
                'producer_run_id': selected['_producer'], 'authorizing_manifest_ref': selected['_manifest_ref'],
                'authorizing_run_id': selected['_manifest_run'], 'proof_run_id': selected['_proof_run'],
                'proof_manifest_ref': selected['_proof_manifest'], 'root_ref': root.model_dump(mode='json'),
                'chain': [*chain, edge], 'operation_digest': value.operation_digest, 'policy_digest': _digest(asdict(policy)),
                'request': request.model_dump(mode='json'),
                'selector': {'pointer': request.pointer, 'offset': request.offset, 'limit': request.limit, 'delivery': request.delivery},
                'provided': response['provided'], 'request_key': request_key, 'response': _portable_response(response), 'budget_scope': call['budget_scope']}
            self._reference_deadline(call)
            recovery = self.recovery_tool_proof(value)
            with self._connect() as connection:
                connection.execute('BEGIN IMMEDIATE')
                self._reference_running(connection, run_id)
                existing = connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=? AND evidence_key=?', (run_id, request_key)).fetchone()
                if existing:
                    response = self._reference_delivery_response(run_id, json.loads(existing[0])['response'])
                else:
                    current = [json.loads(row[0]) for row in connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=?', (run_id,))]
                    scoped = [json.loads(r[0]) for r in connection.execute(
                        "SELECT record_json FROM run_tool_evidence WHERE json_extract(CAST(record_json AS TEXT),'$.budget_scope')=?", (call['budget_scope'],))]
                    facts = {r.get('adopted_from', r['request_key']) for r in scoped if r.get('record_type') == 'reference_access'}
                    fact_key = request_key
                    if (sum(r.get('record_type') == 'reference_access' for r in current) >= policy.max_records
                            or (fact_key not in facts and len(facts) >= policy.max_records)):
                        raise ReferenceAccessError('reference_record_limit', 'Reference access record budget exhausted.')
                    if any(item.source_name == alias and item.artifact_ref != target for item in value.inputs) or any(
                            r['alias'] == alias and r.get('record_type') != 'reference_access' for r in current):
                        raise ReferenceAccessError('reference_alias_conflict', 'Controlled reference alias conflicts with an existing source.')
                    snapshot = self._encode_evidence_snapshot(value,
                        [r for r in current if r.get('record_type') != 'reference_access'],
                        [*[r for r in current if r.get('record_type') == 'reference_access'], record],
                        recovery, self.tool_attempts(run_id))
                    if len(snapshot) > 1024 * 1024:
                        raise ReferenceAccessError('reference_manifest_limit', 'Controlled source manifest would exceed its byte limit.')
                    ordinal = len(current) + 1
                    connection.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)', (run_id, ordinal, request_key, canonical_json(record), alias))
                self._reference_settle(connection, value, call, response, request_key=request_key)
            committed = True
            self._reference_publish_file(run_id, response, raw)
            self._refresh_evidence_schema(run_id)
            return response
        except (ReferenceAccessError, RunStateConflict, ValueError, KeyError, OSError) as error:
            response = {'state': 'rejected', 'code': getattr(error, 'code', 'reference_run_closed' if isinstance(error, RunStateConflict) else 'reference_unavailable'), 'message': str(error)}
            if source_authorized and response['code'] in {'reference_producer_missing', 'reference_manifest_unpaired'}:
                workspace = self.backend.open(run_id)
                path = workspace.input_paths.get(request.source)
                if path is None:
                    record = next((r for r in self.reference_access_records(run_id) if r['alias'] == request.source), None)
                    if record is not None and record['response'].get('provided', {}).get('kind') == 'file_access':
                        path = workspace.root / '.reference-access' / (request.source + '.bin')
                response['reference_availability'] = 'unavailable_for_this_pairing'
                response['original_access'] = {'source': request.source, 'file_path': str(path) if path is not None else None,
                    'instruction': 'Read the already authorized original at this path using a selected range; original readability does not imply expandable references. Preserve this exact pairing error; do not repeat unchanged discovery or infer permanent absence from other failures.'}
            if not committed:
                with self._connect() as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    self._reference_settle(connection, value, call, response)
            return response

    def _reference_not_adopted(self, value, record, reason):
        with self._connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            diagnostic = {'request_key': record['request_key'], 'reason': reason}
            raw = canonical_json(diagnostic)
            if not connection.execute("SELECT 1 FROM run_activity WHERE run_id=? AND activity='reference_access_not_adopted' AND diagnostic_json=?",
                                      (value.run_id, raw)).fetchone():
                self._reference_event(connection, value.run_id, 'reference_access_not_adopted', diagnostic)

    def adopt_reference_access(self, run_id):
        from ...reference_tools import ReferenceReadRequest
        from .run_outputs import RunCheckerError
        value = self.status(run_id)
        links = self.recovery_links(run_id)
        previous = links['draft_from_run_id'] or links['resume_from_run_id']
        if not previous:
            return
        previous_value = self.status(previous)
        if previous_value.instance_id != value.instance_id:
            raise RunCheckerError('reference recovery belongs to another instance', category='integrity_failure')
        try:
            policy = self._reference_policy(value)
        except ReferenceAccessError:
            for record in self.reference_access_records(previous):
                self._reference_not_adopted(value, record, 'reference_capability_missing')
            return
        visible_roots = self._reference_roots(value)
        recovery = self.recovery_tool_proof(value)
        for original in self.reference_access_records(previous):
            root = _ref(original['root_ref'])
            if root not in {item.artifact_ref for item in visible_roots}:
                self._reference_not_adopted(value, original, 'reference_root_missing')
                continue
            if original['policy_digest'] != _digest(asdict(policy)):
                self._reference_not_adopted(value, original, 'reference_policy_changed_requires_revalidation')
                continue
            chain = original['chain']
            if (not chain or len(chain) > policy.max_depth or _ref(chain[0]['source_ref']) != root
                    or _ref(chain[-1]['target_ref']) != _ref(original['artifact_ref'])
                    or any(_ref(left['target_ref']) != _ref(right['source_ref']) for left, right in zip(chain, chain[1:]))
                    or original['operation_digest'] != previous_value.operation_digest):
                raise RunCheckerError('preserved reference chain is inconsistent', category='integrity_failure')
            # The previous immutable control receipt already proved each edge
            # under this exact extraction policy. Same root Ref preserves that
            # proof; adoption does not fabricate a new Worker delivery or IO.
            target = _ref(original['artifact_ref'])
            self.artifacts.catalog(target)
            alias = self._reference_alias(value, target)
            source = _ref(chain[-1]['source_ref'])
            source_alias = self._reference_alias(value, source)
            request = ReferenceReadRequest(source=source_alias, action='read',
                reference='ref_' + _digest(chain[-1]), **original['selector'])
            key = self._reference_request_key(value, request, policy, root, chain[:-1], source)
            response = {**_portable_response(original['response']), 'source': alias}
            if response.get('provided', {}).get('kind') == 'file_access':
                if 'native_workspace' not in getattr(self.backend, 'capabilities', ()):
                    self._reference_not_adopted(value, original, 'binary_file_access_unavailable')
                    continue
            record = {**original, 'alias': alias, 'access_run_id': run_id, 'operation_digest': value.operation_digest,
                      'request_key': key, 'request': request.model_dump(mode='json'), 'response': response,
                      'adopted_from': original.get('adopted_from', original['request_key'])}
            with self._connect() as connection:
                connection.execute('BEGIN IMMEDIATE')
                self._reference_running(connection, run_id)
                scope = self._reference_scope(connection, run_id)
                if scope != original['budget_scope']:
                    raise RunCheckerError('preserved reference budget scope differs', category='integrity_failure')
                if connection.execute('SELECT 1 FROM run_tool_evidence WHERE run_id=? AND evidence_key=?', (run_id, key)).fetchone():
                    continue
                current = [json.loads(row[0]) for row in connection.execute('SELECT record_json FROM run_tool_evidence WHERE run_id=?', (run_id,))]
                accesses = [r for r in current if r.get('record_type') == 'reference_access']
                if len(accesses) >= policy.max_records:
                    raise RunCheckerError('preserved reference records exceed declared limit', category='integrity_failure')
                snapshot = self._encode_evidence_snapshot(value, [r for r in current if r.get('record_type') != 'reference_access'],
                    [*accesses, record], recovery, self.tool_attempts(run_id))
                if len(snapshot) > 1024 * 1024:
                    raise RunCheckerError('preserved reference manifest exceeds byte limit', category='integrity_failure')
                connection.execute('INSERT INTO run_tool_evidence VALUES (?,?,?,?,?)',
                    (run_id, len(current) + 1, key, canonical_json(record), alias))

    def reference_calculation_sources(self, value, alias, *, validation_deadline=None, validation_budget=None):
        """Mechanical replay context in the original namespace, never Worker inputs."""
        from ...operations.input_validation import ValidationSources
        from .calculation_proof import ControlledCalculationRecord as CalculationRecord, controlled_calculation
        from .run_outputs import InputBindingDescriptor, RunCheckerError
        from ..schema.tool_evidence import ToolEvidenceManifest
        records = [r for r in self.reference_access_records(value.run_id) if r['alias'] == alias]
        if not records:
            return None
        record = records[0]
        policy = self._reference_policy(value)
        if (record['operation_digest'] != value.operation_digest or record['policy_digest'] != _digest(asdict(policy))
                or _ref(record['root_ref']) not in {item.artifact_ref for item in self._reference_roots(value)}):
            raise RunCheckerError('reference calculation authority is no longer current', category='integrity_failure')
        deadline = validation_deadline if validation_deadline is not None else time.monotonic() + policy.max_io_seconds
        budget = validation_budget if validation_budget is not None else {}
        def read(ref):
            envelope = self.artifacts.catalog(ref)
            budget['bytes'] = budget.get('bytes', 0) + envelope.size_bytes
            if envelope.size_bytes > policy.max_file_bytes or budget['bytes'] > policy.max_io_bytes:
                raise RunCheckerError('reference calculation mechanical IO exceeds limit', category='integrity_failure')
            if time.monotonic() >= deadline:
                raise TimeoutError('reference calculation validation deadline exceeded')
            raw = self.artifacts.read(ref)
            if time.monotonic() >= deadline:
                raise TimeoutError('reference calculation validation deadline exceeded')
            if len(raw) != envelope.size_bytes or hashlib.sha256(raw).hexdigest() != ref.sha256:
                raise RunCheckerError('reference calculation original changed', category='integrity_failure')
            return raw
        manifest_ref = _ref(record.get('proof_manifest_ref') or record['authorizing_manifest_ref'])
        producer = self.status(record.get('proof_run_id') or record['authorizing_run_id'])
        if (producer.state != 'completed' or producer.instance_id != value.instance_id or producer.output_ref is None
                or manifest_ref not in self.artifacts.catalog(producer.output_ref).parent_refs
                or self.artifacts.catalog(manifest_ref).labels.get('tool_producer_run') != producer.run_id):
            raise RunCheckerError('reference calculation producer manifest is unpaired', category='integrity_failure')
        manifest = ToolEvidenceManifest.model_validate_json(read(manifest_ref))
        target = _ref(record['artifact_ref'])
        exact = [r for r in manifest.records if _ref(r['artifact_ref']) == target
                 and r.get('metadata', {}).get('kind') == 'calculation_record']
        if len(exact) != 1:
            return None
        calculation = controlled_calculation(read(target), exact[0])
        if calculation.attempt is None:
            raise RunCheckerError('reference calculation has no controlled attempt', category='integrity_failure')
        origin, attempt = _calculation_origin(manifest, calculation)
        sources, descriptors = {}, {}
        for name in attempt.read_sources:
            binding = origin.bindings.get(name)
            if binding is None:
                raise RunCheckerError('reference calculation read-source binding is missing', category='integrity_failure')
            ref = binding.artifact_ref
            envelope = self.artifacts.catalog(ref)
            sources[name] = read(ref)
            descriptors[name] = InputBindingDescriptor(source_name=name, port_name=binding.port_name,
                artifact_ref=ref, media_type=envelope.media_type, size_bytes=envelope.size_bytes,
                sha256=ref.sha256, output_name=envelope.labels.get('logical_name'),
                parent_refs=envelope.parent_refs, labels=tuple(envelope.labels.items()))
        proof = {'schema_version': 1, 'bindings': origin.bindings, 'attempts': origin.attempts,
                 'records': list(manifest.records)}
        if calculation.attempt.proof_kind == 'recovery':
            if manifest.recovery is None:
                raise RunCheckerError('reference calculation recovery proof is missing', category='integrity_failure')
            proof['recovery'] = manifest.recovery
        return ValidationSources(sources, descriptors, validation_deadline=deadline, tool_snapshot=canonical_json(proof))
