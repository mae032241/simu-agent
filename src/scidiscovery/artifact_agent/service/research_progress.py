"""Bind a declared public scientific projection to the existing consumption ledger.

Plugins copy scientific judgments; control supplies exact cycle/source identities.
Nothing here independently verifies science or treats new bytes as progress.
"""
import json

from ..schema.common import canonical_sha256
from ..schema.scientific_progress import ScientificProgressProjection
from ...operations.input_validation import ValidationSources


def research_progress(runs, value):
    unknown = dict(status='unknown', reason='scientific_progress_not_declared', families=[])
    result = unknown
    if value.state != 'completed' or value.output_ref is None:
        return dict(unknown, reason='no_completed_scientific_output')
    from .verified_progress import _proof_errors
    try:
        compiled = runs.compiled_operation(value)
        declaration = compiled.spec.scientific_progress
        if declaration is None:
            return unknown
        by_port = {port.name: [item for item in value.inputs if item.port_name == port.name]
            for port in compiled.spec.inputs}
        def selected(port):
            items = by_port.get(port, [])
            return items[0].artifact_ref if len(items) == 1 else None
        subject = selected(declaration.subject_port)
        objective = selected(declaration.objective_port)
        if declaration.subject_port and subject is None:
            return dict(unknown, reason='scientific_progress_subject_missing_or_ambiguous')
        result = dict(unknown, stage=declaration.stage,
            cycle_key=canonical_sha256(subject or value.output_ref),
            closes=[], awaiting=[], authority='worker_assessment_with_control_bound_sources',
            scientific_validity='not_independently_verified')
        output_key = canonical_sha256(value.output_ref)
        if declaration.stage in {'preparation', 'experiment'}:
            # A new completed preparation is an observation obligation. Merely
            # waiting for its Worker, approval or external execution is no event.
            return dict(result, status='awaiting_analysis', reason='completed_work_awaits_interpretation',
                awaiting=[output_key], closes=[canonical_sha256(subject)] if subject else [])
        result['closes'] = [canonical_sha256(subject)] if subject else []
        if subject:
            producer = runs.completed_for_output(subject)
            producer_spec = runs.compiled_operation(producer).spec.scientific_progress if producer is not None else None
            if producer_spec and producer_spec.stage == 'experiment':
                result['closes'].extend(canonical_sha256(item.artifact_ref) for item in producer.inputs
                    if item.port_name == producer_spec.subject_port)
        descriptors = {item.source_name: runs.source_descriptor(value, item.source_name) for item in value.inputs}
        # Analysis may co-cite its own published calculations/materials. Use the
        # manifest paired to this exact completed output, never mutable drafts
        # or a newly reconstructed receipt set. These supplement observations;
        # a new attachment alone cannot establish an advance.
        from ..schema.refs import ArtifactRef
        from ..schema.tool_evidence import ToolEvidenceManifest
        paired = [ref for ref in runs.artifacts.catalog(value.output_ref).parent_refs
            if ref.schema_id == 'scidiscovery.tool-evidence-manifest.v1'
            and runs.artifacts.catalog(ref).labels.get('tool_producer_run') == value.run_id]
        if len(paired) > 1:
            return dict(result, reason='scientific_progress_material_manifest_ambiguous')
        if paired:
            manifest = ToolEvidenceManifest.model_validate_json(runs.artifacts.read(paired[0]))
            records = (*manifest.records, *manifest.accesses)
            aliases = [record.get('alias') for record in records]
            if any(not isinstance(alias, str) or not alias or alias in descriptors for alias in aliases) or len(set(aliases)) != len(aliases):
                return dict(result, reason='scientific_progress_material_identity_ambiguous')
            for record in records:
                ref = ArtifactRef.model_validate(record['artifact_ref'])
                descriptor = runs.source_descriptor(value, record['alias'])
                if (descriptor.artifact_ref != ref or descriptor.size_bytes != record['size_bytes']
                        or descriptor.media_type != record['media_type']):
                    return dict(result, reason='scientific_progress_material_receipt_mismatch')
                runs.artifacts.verify(ref)
                # Reference accesses can be legitimate co-citations without
                # claiming that the analysis produced their original source.
                if record.get('record_type') == 'reference_access' or subject in descriptor.parent_refs:
                    descriptors[record['alias']] = descriptor
        selected_sources = [item for item in value.inputs if item.port_name in declaration.source_ports]
        if sum(descriptors[item.source_name].size_bytes for item in selected_sources) > 128 * 1024:
            return dict(result, reason='scientific_progress_source_projection_omitted')
        sources = ValidationSources({item.source_name: runs.artifacts.read(item.artifact_ref)
            for item in selected_sources}, descriptors)
        projector = declaration.projector
        implementation = compiled.implementations[f'{projector.plugin_id or compiled.plugin_id}:{projector.component_id}']
        payload = json.loads(runs.artifacts.read(value.output_ref))
        try:
            projected = implementation(payload, sources)
        except Exception:
            return dict(result, reason='scientific_progress_projector_failed')
        projection = ScientificProgressProjection.model_validate(projected)
        # Only the exact subject and sources derived from it can support the
        # completed question; optional unrelated references cannot renew it.
        allowed_ports = set()
        for port in compiled.spec.inputs:
            current, seen, output_derived = port, set(), False
            while current.name not in seen:
                seen.add(current.name)
                if current.name == declaration.subject_port:
                    if output_derived:
                        allowed_ports.add(port.name)
                    break
                if current.derivation is None:
                    break
                rule = current.derivation
                # Original goal/hypotheses/conditions are valid co-citations,
                # but producer inputs alone are not completed observations.
                if rule.producer_input_path or rule.select == 'sources':
                    break
                output_derived = output_derived or rule.producer_output_port is not None
                current = next(item for item in compiled.spec.inputs if item.name == current.derivation.anchor_port)
        observation_aliases = {item.source_name for item in value.inputs
            if item.artifact_ref == subject or item.port_name in allowed_ports}
        def bound(keys):
            return bool(keys) and all(key in descriptors for key in keys) and any(
                key in observation_aliases for key in keys)
        families = []
        for change in projection.changes:
            if bound(change.evidence_keys):
                families.append(dict(key=canonical_sha256(dict(objective={field: getattr(objective, field)
                    for field in ('kind', 'schema_id', 'sha256')} if objective else None,
                    dimension=change.dimension, outcome=change.outcome)), dimension=change.dimension, outcome=change.outcome))
        supported = bound(projection.evidence_keys)
        outcome = projection.outcome
        if not supported or (outcome == 'advance' and (not families or objective is None)):
            outcome = 'unknown'
        evidence_keys = tuple(dict.fromkeys((*projection.evidence_keys,
            *(key for change in projection.changes for key in change.evidence_keys))))
        return dict(result, status='worker_assessed' if outcome != 'unknown' else 'unknown',
            reason='source_bound_worker_assessment' if outcome != 'unknown' else 'missing_supported_scientific_change_or_assessment',
            outcome=outcome, question=projection.question, answer=projection.answer,
            remaining_question=projection.remaining_question,
            evidence=[dict(alias=key, ref=descriptors[key].artifact_ref.model_dump(mode='json'))
                for key in evidence_keys if key in descriptors],
            families=families if outcome == 'advance' else [])
    except (*_proof_errors(), KeyError, TypeError, AttributeError):
        # Optional coverage cannot make otherwise accepted scientific work unreadable.
        return dict(result, status='unknown', reason='scientific_progress_projection_unavailable_or_inconsistent')


def cycle_facts(facts, *, start=0, known_cycles=(), duplicates=None):
    """One interpreted exact question, or one unsupported standalone result.

    Replaying this same ledger after restart deduplicates analysis revisions.
    Preparation/experiment obligations stay visible without masquerading as
    three failed scientific attempts. Waiting does not produce a terminal fact.
    """
    cycles, pending, closed, selected = set(known_cycles), set(), set(), []
    for fact in facts:
        progress = fact['terminal'].get('scientific_progress') or {}
        for key in progress.get('closes', []):
            closed.add(key)
            pending.discard(key)
        if progress.get('status') == 'awaiting_analysis':
            if fact['sequence'] > start:
                pending.update(key for key in progress.get('awaiting', []) if key not in closed)
            continue
        cycle = progress.get('cycle_key')
        if cycle and cycle in cycles:
            if duplicates is not None and fact['sequence'] > start:
                duplicates.append(fact)
            continue
        if cycle:
            cycles.add(cycle)
        selected.append(fact)
    return selected, len(pending)


def progress_families(fact):
    terminal = fact['terminal']
    proof = terminal.get('verified_progress') or {}
    strong = proof.get('resolutions', []) if proof.get('status') == 'verified_test_resolution' else []
    progress = terminal.get('scientific_progress') or {}
    assessed = progress.get('families', []) if progress.get('status') == 'worker_assessed' else []
    return [*strong, *assessed]


def public_progress(progress):
    """Bounded decision metadata; originals remain in the sealed report."""
    fields = ('status', 'reason', 'stage', 'outcome', 'authority', 'scientific_validity')
    result = {key: progress[key] for key in fields if key in progress}
    evidence = progress.get('evidence', [])
    result.update(evidence_aliases=[item['alias'] for item in evidence[:8]],
        evidence_omitted=max(0, len(evidence)-8),
        counting_basis=('one_exact_interpreted_subject' if progress.get('stage') == 'analysis'
            else 'completed_work_awaits_interpretation' if progress.get('stage') in {'preparation', 'experiment'}
            else 'completed_task_observation_without_scientific_adapter'),
        novelty_limit='Stable scientific dimensions detect reuse; semantic novelty and native execution truth are not independently verified.')
    return result
