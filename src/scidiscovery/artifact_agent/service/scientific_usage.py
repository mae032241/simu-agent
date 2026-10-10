"""Scientific-use restrictions follow declared citations and exact tool receipts."""
import json
import time
import sqlite3
from dataclasses import asdict
from collections import OrderedDict
from contextlib import closing
from types import SimpleNamespace

from ..schema.common import canonical_json, canonical_sha256
from .reference_proofs import MAX_SNAPSHOT_BYTES

from ...operations.tooling import reference_policy
from ...operations.invoke import OperationInvocationError
from ...reference_tools import ReferencePolicy
from ..schema.refs import ArtifactRef
from .reference_access import ReferenceAccessError, _matches, _pointer
from .run_records import RunContractUnavailable, RunError, RunNotFound, RunStateConflict
from .scheduler_bindings import SchedulerBindingError


class ScientificProvenanceError(ValueError):
    pass


def output_sources(runs, value, compiled, port_name, raw, *, bindings=None):
    """Use the same explicit citation declarations as forms and reference access."""
    port = next(port for port in compiled.spec.outputs if port.name == port_name)
    policy = reference_policy(compiled)
    rules = [rule for rule in policy.rules if rule.schema_id == port.schema_id] if policy else []
    if not port.evidence_paths and not rules:
        return ()
    document = json.loads(raw)
    if bindings is None:
        bindings = {item.source_name: item.artifact_ref for item in value.inputs}
        bindings.update((record['alias'], ArtifactRef.model_validate(record['artifact_ref']))
                        for record in (*runs.tool_evidence(value.run_id), *runs.reference_access_records(value.run_id)))
    # This runtime-owned alias records attempts/rejections, not scientific inputs.
    from ...operations.tooling import tool_evidence_ports
    diagnostics = ({'tool_recovery_manifest'} - bindings.keys()) if tool_evidence_ports(compiled) else set()
    known = set(bindings) | diagnostics
    aliases = []
    for path in port.evidence_paths:
        try:
            citations = _pointer(document, path)
        except ReferenceAccessError as error:
            if error.code != 'reference_selector_missing':
                raise
            # Validated scientific forms may omit their optional citation ledger.
            # Direct evidence keys are still covered by the declared rules below.
            continue
        aliases.extend(citation['source_key'] for citation in citations)
    mapping = {}
    if port.schema_id == 'scidiscovery.layered-diagnosis.v1':
        from types import SimpleNamespace
        from .analysis_artifacts import analysis_evidence_aliases
        mapping = analysis_evidence_aliases(
            [SimpleNamespace(**item) for item in document.get('evidence', ())],
            [SimpleNamespace(**item) for item in document.get('source_references', ())], known)
    for rule in rules:
        if rule.producer_input_alias is not None:
            aliases.append(rule.producer_input_alias)
            continue
        for _, item in _matches(document, rule.path.lstrip('/').split('/')):
            if rule.selected_only:
                raise ScientificProvenanceError('Selected calculation provenance requires its exact receipt.')
            if rule.keys and isinstance(item, dict):
                for alias, digest in item.items():
                    if alias not in bindings or bindings[alias].sha256 != digest:
                        raise ScientificProvenanceError('Scientific citation digest is not exactly bound.')
                aliases.extend(item)
            elif isinstance(item, str):
                if rule.locator_prefix:
                    item = item.split(':', 1)[0]
                    if item not in known:
                        continue
                aliases.append(mapping.get(item, item))
    if any(alias not in known for alias in aliases):
        raise ScientificProvenanceError('Scientific citation has no exact source binding.')
    return tuple(dict.fromkeys(bindings[alias] for alias in aliases if alias not in diagnostics))


EDGE_ACTIVITY = 'scientific_source_edges_v1'


def _context_identity(runs, policy):
    return canonical_sha256({'version': 1, 'policy': asdict(policy),
                            'catalog': runs.operation_catalog.scientific_provenance_digest()})


def _owner_identity(value, ref, record=None):
    return canonical_sha256({'run_id': value.run_id, 'instance_id': value.instance_id,
        'operation_digest': value.operation_digest, 'subject': ref,
        'receipt': record, 'inputs': [(i.source_name, i.artifact_ref) for i in value.inputs]})


def retain_source_edges(runs, value, ref, sources, *, record=None, connection, context=None):
    """Write only direct control-checked edges in their owner's success transaction."""
    policy = reference_policy(runs._compiled(value)) or ReferencePolicy()
    envelope = runs.artifacts.catalog(ref)
    key = canonical_sha256({'context': context or _context_identity(runs, policy),
                           'owner': _owner_identity(value, ref, record)})
    document = {'version': 1, 'check_key': key, 'artifact_ref': ref.model_dump(mode='json'),
                'own_restricted': envelope.labels.get('scientific_claim_admissible') == 'false',
                'sources': [source.model_dump(mode='json') for source in dict.fromkeys(sources)]}
    document['edge_digest'] = canonical_sha256(document)
    raw = canonical_json(document)
    if len(raw) > MAX_SNAPSHOT_BYTES:
        return  # Optional acceleration never truncates evidence or makes a verdict.
    existing = connection.execute("SELECT 1 FROM run_activity WHERE run_id=? AND activity=? "
        "AND CASE WHEN length(diagnostic_json)<=? THEN "
        "json_extract(CAST(diagnostic_json AS TEXT),'$.check_key') END=? LIMIT 1",
        (value.run_id, EDGE_ACTIVITY, MAX_SNAPSHOT_BYTES, key)).fetchone()
    if existing is None:
        from .run_records import timestamp
        runs._append_activity(connection, value.run_id, EDGE_ACTIVITY, timestamp(), raw)


class _Check:
    def __init__(self, runs, limits):
        self.runs, self.limits = runs, limits
        self.context = _context_identity(runs, limits)
        self.started = time.monotonic()
        self.remaining_bytes = min(limits.max_unique_bytes, limits.max_io_bytes)
        self.producers, self.receipts, self.aliases = {}, {}, {}
        self.owner_bytes = 0
        self.owner_limit = MAX_SNAPSHOT_BYTES
        self.owner_sizes = OrderedDict()

    def budget(self, size=0):
        self.remaining_bytes -= size
        if size > self.limits.max_file_bytes or self.remaining_bytes < 0:
            raise ScientificProvenanceError('Scientific provenance exceeds its byte bound.')
        if time.monotonic() - self.started >= self.limits.max_io_seconds:
            raise ScientificProvenanceError('Scientific provenance exceeds its time bound.')

    def retain_owner(self, run_id, size):
        # Keep recent owners, never all historical receipt collections. A later
        # revisit is a bounded reread charged again to the total I/O/time budget.
        while self.owner_bytes + size > self.owner_limit:
            expired = next((key for key in self.owner_sizes if key != run_id), None)
            if expired is None:
                raise ScientificProvenanceError('Scientific provenance exceeds its owner work-set byte bound.')
            self.owner_bytes -= self.owner_sizes.pop(expired)
            for cache in (self.producers, self.receipts, self.aliases):
                cache.pop(expired, None)
        self.owner_bytes += size
        self.owner_sizes[run_id] = self.owner_sizes.get(run_id, 0) + size
        self.owner_sizes.move_to_end(run_id)

    def producer(self, run_id):
        if run_id not in self.producers:
            # This checker never SELECTs/hydrates full RunStatus. Guard the exact
            # required columns before fetching their bounded projection; unrelated
            # request/recovery/settings/approval carriers remain in SQLite.
            columns = ('run_id', 'instance_id', 'operation_id', 'operation_version',
                       'operation_digest', 'state', 'output_ref_json', 'inputs_json')
            lengths = '+'.join(f'COALESCE(length(CAST({column} AS BLOB)),0)' for column in columns)
            with closing(self.runs._connect()) as connection:
                connection.execute('PRAGMA query_only=ON')
                connection.execute('BEGIN')
                row = connection.execute(f'SELECT {lengths} AS size FROM runs WHERE run_id=?',
                                         (run_id,)).fetchone()
                if row is None:
                    raise RunNotFound('Run does not exist')
                size = row['size']
                self.budget(size)
                if size > MAX_SNAPSHOT_BYTES:
                    raise ScientificProvenanceError('Scientific provenance exceeds its owner projection byte bound.')
                row = connection.execute("SELECT run_id,instance_id,operation_id,operation_version,"
                    "operation_digest,state,output_ref_json,"
                    "(SELECT json_group_array(json_object('source_name',json_extract(value,'$.source_name'),"
                    "'port_name',json_extract(value,'$.port_name'),"
                    "'artifact_ref',json(json_extract(value,'$.artifact_ref')))) FROM json_each(inputs_json)) "
                    "AS inputs FROM runs WHERE run_id=?", (run_id,)).fetchone()
            # Charge only the retained projection to the recent-owner cache. Its
            # full input carrier was bounded and reserved before SQL/JSON parsing.
            projected_size = sum(len(item.encode('utf-8')) if isinstance(item, str) else len(item)
                                 for item in row if item is not None)
            self.retain_owner(run_id, projected_size)
            document = {key: row[key] for key in columns[:6]}
            document['output_ref'] = (ArtifactRef.model_validate_json(row['output_ref_json'])
                                      if row['output_ref_json'] is not None else None)
            document['inputs'] = tuple(SimpleNamespace(source_name=item['source_name'], port_name=item['port_name'],
                artifact_ref=ArtifactRef.model_validate(item['artifact_ref'])) for item in json.loads(row['inputs']))
            self.producers[run_id] = SimpleNamespace(**document)
        self.owner_sizes.move_to_end(run_id)
        return self.producers[run_id]

    def primary(self, ref):
        # Exact primary ownership, with uniqueness preserved. The manifest branch
        # checks its exact membership against this same bounded primary owner.
        with closing(self.runs._connect()) as connection:
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            rows = connection.execute("SELECT length(CAST(run_id AS BLOB)) AS size FROM runs "
                "WHERE state='completed' AND output_ref_json=? LIMIT 2", (ref.canonical_json(),)).fetchall()
            if len(rows) > 1:
                raise RunStateConflict('multiple Runs claim the same exact output')
            if not rows:
                return None
            self.budget(rows[0]['size'])
            if rows[0]['size'] > MAX_SNAPSHOT_BYTES:
                raise ScientificProvenanceError('Scientific provenance exceeds its owner projection byte bound.')
            run_id = connection.execute("SELECT run_id FROM runs WHERE state='completed' "
                "AND output_ref_json=? LIMIT 1", (ref.canonical_json(),)).fetchone()[0]
        producer = self.producer(run_id)
        if producer.state != 'completed' or producer.output_ref != ref:
            raise ScientificProvenanceError('Exact scientific output ownership changed.')
        return producer

    def records(self, run_id):
        if run_id not in self.receipts:
            # One read-only snapshot for lengths and the streamed collection.
            # A legal concurrent receipt/access writer cannot extend this snapshot.
            with closing(self.runs._connect()) as connection:
                connection.execute('PRAGMA query_only=ON')
                connection.execute('BEGIN')
                size = connection.execute('SELECT COALESCE(sum(length(CAST(record_json AS BLOB))),0) '
                    'FROM run_tool_evidence WHERE run_id=?', (run_id,)).fetchone()[0]
                self.budget()
                if size > self.limits.max_file_bytes or size > self.remaining_bytes:
                    raise ScientificProvenanceError('Scientific provenance exceeds its byte bound.')
                self.retain_owner(run_id, size)
                records, consumed = [], 0
                for row in connection.execute('SELECT record_json FROM run_tool_evidence '
                                              'WHERE run_id=? ORDER BY ordinal', (run_id,)):
                    raw = row[0]
                    actual = len(raw.encode('utf-8')) if isinstance(raw, str) else len(raw)
                    consumed += actual
                    if consumed > size:
                        raise ScientificProvenanceError('Scientific receipt snapshot size is inconsistent.')
                    self.budget(actual)  # Before parsing, charge the actual fetched carrier.
                    records.append(json.loads(raw))
                if consumed != size:
                    raise ScientificProvenanceError('Scientific receipt snapshot size is inconsistent.')
            self.receipts[run_id] = records
        return self.receipts[run_id]

    def bindings(self, producer):
        if producer.run_id not in self.aliases:
            bindings = {i.source_name: i.artifact_ref for i in producer.inputs}
            bindings.update((record['alias'], ArtifactRef.model_validate(record['artifact_ref']))
                for record in self.records(producer.run_id))
            self.retain_owner(producer.run_id, len(canonical_json(bindings)))
            self.aliases[producer.run_id] = bindings
        return self.aliases[producer.run_id]

    def cached(self, producer, ref, envelope, record=None):
        key = canonical_sha256({'context': self.context, 'owner': _owner_identity(producer, ref, record)})
        try:
            with self.runs._connect() as connection:
                rows = connection.execute("SELECT length(diagnostic_json) AS size, "
                    "CASE WHEN length(diagnostic_json)<=? THEN diagnostic_json END AS document "
                    "FROM run_activity WHERE run_id=? AND activity=? "
                    "AND (length(diagnostic_json)>? OR CASE WHEN length(diagnostic_json)<=? THEN "
                    "json_extract(CAST(diagnostic_json AS TEXT),'$.check_key') END=?) LIMIT 2",
                    (MAX_SNAPSHOT_BYTES, producer.run_id, EDGE_ACTIVITY,
                     MAX_SNAPSHOT_BYTES, MAX_SNAPSHOT_BYTES, key)).fetchall()
        except sqlite3.Error as error:
            raise ScientificProvenanceError('Scientific source edge check is unreadable.') from error
        if not rows:
            return None
        if len(rows) != 1 or rows[0]['document'] is None:
            raise ScientificProvenanceError('Scientific source edge check is ambiguous or oversized.')
        self.budget(rows[0]['size'])
        try:
            document = json.loads(rows[0]['document'])
            digest = document.pop('edge_digest')
            if digest != canonical_sha256(document):
                raise ValueError('edges')
            if (document['version'] != 1 or document['check_key'] != key
                    or ArtifactRef.model_validate(document['artifact_ref']) != ref
                    or document['own_restricted'] is not
                    (envelope.labels.get('scientific_claim_admissible') == 'false')):
                raise ValueError('identity')
            return tuple(ArtifactRef.model_validate(source) for source in document['sources'])
        except (ValueError, KeyError, TypeError) as error:
            raise ScientificProvenanceError('Scientific source edge check is invalid.') from error


def scientific_use_restricted(runs, references, *, ignore_labels=(), policy=None):
    """Reuse control-checked direct edges; still verify every ancestor's ownership.

    No aggregate verdict, review, permission, or historical unknown is cached.
    Total time, read bytes and encoded graph work bound the cold/warm path; the
    reference tool's 128-call quota is not an accumulated historical object quota.
    """
    limits = policy or ReferencePolicy()
    check = _Check(runs, limits)
    pending, seen, scheduled = [], set(), set()
    work_bytes = 0

    def add(ref, uncertain=False):
        nonlocal work_bytes
        item = (ref, uncertain)
        if item not in seen and item not in scheduled:
            size = len(canonical_json({'ref': ref, 'uncertain': uncertain}))
            if work_bytes + size > MAX_SNAPSHOT_BYTES:
                raise ScientificProvenanceError('Scientific provenance exceeds its work-set byte bound.')
            work_bytes += size
            scheduled.add(item)
            pending.append((ref, uncertain, size))

    for ref in references:
        add(ref)
    while pending:
        check.budget()
        ref, uncertain, size = pending.pop()
        visit = (ref, uncertain)
        scheduled.remove(visit)
        if visit in seen:
            work_bytes -= size
            continue
        seen.add(visit)  # Its encoded identity remains charged until this check ends.
        envelope = runs.artifacts.catalog(ref)
        if ref not in ignore_labels and envelope.labels.get('scientific_claim_admissible') == 'false':
            if uncertain:
                raise ScientificProvenanceError('Historical ancestors include restricted material, but exact scientific citations are unavailable.')
            return True
        if uncertain:
            for parent in envelope.parent_refs:
                add(parent, True)
            continue
        producer_id = envelope.labels.get('tool_producer_run')
        if producer_id:
            try:
                producer = check.producer(producer_id)
            except RunError as error:
                raise ScientificProvenanceError('Scientific receipt producer is unavailable.') from error
            if (envelope.schema_id == 'scidiscovery.tool-evidence-manifest.v1'
                    and envelope.labels.get('operation_output_port') == 'recovery_manifest_output'
                    and envelope.labels.get('operation_digest') == producer.operation_digest
                    and producer.state == 'completed' and producer.output_ref is not None
                    and ref in runs.artifacts.catalog(producer.output_ref).parent_refs
                    and (manifest_owner := check.primary(producer.output_ref)) is not None
                    and manifest_owner.run_id == producer.run_id):
                add(producer.output_ref)
                continue
            records = [record for record in check.records(producer_id)
                       if record.get('record_type') != 'reference_access' and ArtifactRef.model_validate(record['artifact_ref']) == ref]
            if len(records) != 1:
                raise ScientificProvenanceError('Scientific file has no unique exact producer receipt.')
            record = records[0]
            metadata = record.get('metadata', {})
            if (metadata.get('capture_mode') == 'auto_captured'
                    and metadata.get('kind') == 'scientific_attachment'
                    and metadata.get('capture_source_scope') != 'task_inputs_v1'):
                # Legacy sealed bytes remain readable, but cached adopted edges
                # cannot certify the missing conservative task-scope check.
                raise ScientificProvenanceError('Automatic file scientific scope is unconfirmed; reseal within its authorized original input scope.')
            cached = check.cached(producer, ref, envelope, record)
            if cached is not None:
                for source in cached:
                    add(source)
                continue
            aliases = record.get('metadata', {}).get('derived_from', ())
            if aliases:
                try:
                    sources = tuple(check.bindings(producer)[alias] for alias in aliases)
                    if any(source not in envelope.parent_refs for source in sources):
                        raise ScientificProvenanceError('Scientific receipt source is not an exact parent.')
                    for source in sources:
                        add(source)
                except (ValueError, KeyError) as error:
                    raise ScientificProvenanceError('Scientific receipt source is unavailable.') from error
            elif record.get('source_ref') is not None:
                add(ArtifactRef.model_validate(record['source_ref']))
            continue
        producer = check.primary(ref)
        if producer is None or producer.output_ref != ref:
            if envelope.labels.get('transform_profile') is None:
                # A missing completed producer cannot turn its old output into a raw leaf.
                if envelope.labels.get('operation_output_port') is not None:
                    raise ScientificProvenanceError('Scientific output producer is unavailable.')
                continue
            try:
                owner = runs.scheduler_bindings.find_owner(namespace='artifact', object_id=ref.artifact_id)
                if owner is None:
                    raise ScientificProvenanceError('Exact Transform creation binding is unavailable.')
                instance, binding = owner
                family = runs.input_origins(instance.instance_id)._transform_output_family(
                    binding.name, envelope, verify_inputs=False)
            except (SchedulerBindingError, OperationInvocationError) as error:
                raise ScientificProvenanceError('Exact Transform source family is unavailable.') from error
            if family is None or family.producer_kind != 'transform':
                raise ScientificProvenanceError('Exact Transform source family is unavailable or ambiguous.')
            if family.contract_availability != 'current':
                for parent in envelope.parent_refs:
                    add(parent, True)
                continue
            for item in family.producer_inputs:
                add(item.ref)
            continue
        try:
            compiled = runs.compiled_operation(producer)
        except RunContractUnavailable:
            for parent in envelope.parent_refs:
                add(parent, True)
            continue
        port_name = envelope.labels.get('operation_output_port')
        port = next((port for port in compiled.spec.outputs if port.name == port_name), None)
        producer_policy = reference_policy(compiled)
        if port is None:
            raise ScientificProvenanceError('Exact scientific output port is unavailable.')
        if not port.evidence_paths and not (producer_policy and any(rule.schema_id == ref.schema_id for rule in producer_policy.rules)):
            continue
        cached = check.cached(producer, ref, envelope)
        if cached is None:
            check.budget(envelope.size_bytes)
            cached = output_sources(runs, producer, compiled, port_name, runs.artifacts.read(ref),
                                    bindings=check.bindings(producer))
        for source in cached:
            add(source)
    check.budget()
    return False
