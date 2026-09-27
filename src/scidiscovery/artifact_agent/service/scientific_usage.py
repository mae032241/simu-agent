"""Scientific-use restrictions follow declared citations and exact tool receipts."""
import json

from ...operations.tooling import reference_policy
from ...reference_tools import ReferencePolicy
from ..schema.refs import ArtifactRef
from .reference_access import _matches, _pointer
from .run_records import RunError


class ScientificProvenanceError(ValueError):
    pass


def output_sources(runs, value, compiled, port_name, raw):
    """Use the same explicit citation declarations as forms and reference access."""
    port = next(port for port in compiled.spec.outputs if port.name == port_name)
    policy = reference_policy(compiled)
    rules = [rule for rule in policy.rules if rule.schema_id == port.schema_id] if policy else []
    if not port.evidence_paths and not rules:
        return ()
    document = json.loads(raw)
    bindings = {item.source_name: item.artifact_ref for item in value.inputs}
    bindings.update((record['alias'], ArtifactRef.model_validate(record['artifact_ref']))
                    for record in (*runs.tool_evidence(value.run_id), *runs.reference_access_records(value.run_id)))
    # This runtime-owned alias records attempts/rejections, not scientific inputs.
    diagnostics = {alias for alias, source_port in runs.validation_source_ports(value).items()
                   if source_port == 'recovery_manifest_output' and alias not in bindings}
    known = set(bindings) | diagnostics
    aliases = []
    for path in port.evidence_paths:
        aliases.extend(citation['source_key'] for citation in _pointer(document, path))
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


def scientific_use_restricted(runs, references, *, ignore_labels=(), policy=None):
    """Read bounded immutable provenance, never every parent or mutable name.

    Old unlabelled files are resolved through their original control receipt.
    Copies of producer labels do not establish receipt ownership. Handoff verdicts
    stay with admission's exact-review policy; this checks source restrictions.
    """
    limits = policy or ReferencePolicy()
    pending, seen = list(references), set()
    remaining_bytes = limits.max_unique_bytes
    while pending:
        ref = pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        if len(seen) > limits.max_calls:
            raise ScientificProvenanceError('Scientific provenance exceeds its object bound.')
        envelope = runs.artifacts.catalog(ref)
        if ref not in ignore_labels and envelope.labels.get('scientific_claim_admissible') == 'false':
            return True
        producer_id = envelope.labels.get('tool_producer_run')
        if producer_id:
            try:
                producer = runs.status(producer_id)
            except RunError as error:
                raise ScientificProvenanceError('Scientific receipt producer is unavailable.') from error
            records = [record for record in runs.tool_evidence(producer_id)
                       if ArtifactRef.model_validate(record['artifact_ref']) == ref]
            if len(records) != 1:
                raise ScientificProvenanceError('Scientific file has no unique exact producer receipt.')
            record = records[0]
            aliases = record.get('metadata', {}).get('derived_from', ())
            if aliases:
                try:
                    sources = tuple(runs.source_descriptor(producer, alias).artifact_ref for alias in aliases)
                    if any(source not in envelope.parent_refs for source in sources):
                        raise ScientificProvenanceError('Scientific receipt source is not an exact parent.')
                    pending.extend(sources)
                except ValueError as error:
                    raise ScientificProvenanceError('Scientific receipt source is unavailable.') from error
            elif record.get('source_ref') is not None:
                pending.append(ArtifactRef.model_validate(record['source_ref']))
            continue
        producer = runs.completed_for_output(ref)
        if producer is None or producer.output_ref != ref:
            continue
        try:
            compiled = runs._compiled(producer)
        except RunError as error:
            raise ScientificProvenanceError('Exact scientific output contract is unavailable.') from error
        port_name = envelope.labels.get('operation_output_port')
        port = next((port for port in compiled.spec.outputs if port.name == port_name), None)
        policy = reference_policy(compiled)
        if port is None:
            raise ScientificProvenanceError('Exact scientific output port is unavailable.')
        if not port.evidence_paths and not (policy and any(rule.schema_id == ref.schema_id for rule in policy.rules)):
            continue
        remaining_bytes -= envelope.size_bytes
        if remaining_bytes < 0 or envelope.size_bytes > limits.max_file_bytes:
            raise ScientificProvenanceError('Scientific provenance exceeds its byte bound.')
        pending.extend(output_sources(runs, producer, compiled, port_name, runs.artifacts.read(ref)))
    return False
