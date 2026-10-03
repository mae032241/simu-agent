"""Read-only proof of first resolution of an exact, predeclared scientific test.

Registered evaluators provide the public CalculationValidation projection.
Control verifies exact original bindings and paired receipts. This proves a
bounded test resolution, not physical truth or relative optimization.
"""
import json
import math

from pydantic import ValidationError

from ..schema.common import canonical_json, canonical_sha256
from ..schema.experiment import ExperimentPortfolio
from ..schema.layered_diagnosis import LayeredDiagnosisReport
from ..schema.refs import ArtifactRef
from ..schema.validation import evaluate_threshold
from ..schema.validation import ReviewedTestConclusion
from ...operations.input_validation import ValidationSources
from .calculation_proof import controlled_calculation
from .tool_evidence import calculation_sources


def freeze_criteria(artifacts, inputs):
    """Exact typed input identities, frozen by creation before any Worker result."""
    return [item.artifact_ref.model_dump(mode='json') for item in inputs
        if item.artifact_ref.schema_id == 'scidiscovery.experiment-portfolio.v1']


_SEALING_PROOF_MAX_REFS = 64


def _prior_sealed_sources(artifacts, required, measured):
    """Prove exact originals were sealed before each source via immutable parents.

    This proves sealing order, not generation time or scientific authenticity.
    A shared cache bounds the whole proof to 64 distinct original envelopes.
    """
    required, cache = set(required), {}
    if not required or not measured:
        return 'sealing_order_unproven'
    try:
        for source in measured:
            if source in required:
                return 'sealing_order_unproven'  # A source is not its own ancestor.
            if source not in cache:
                if len(cache) >= _SEALING_PROOF_MAX_REFS:
                    return 'sealing_order_proof_omitted'
                cache[source] = artifacts.catalog(source)
            seen, active, found = set(), {source}, set()
            stack = [(source, iter(cache[source].parent_refs))]
            while stack:
                parent = next(stack[-1][1], None)
                if parent is None:
                    ref, _ = stack.pop()
                    active.remove(ref)
                    seen.add(ref)
                    continue
                if parent in active:
                    return 'sealing_order_lineage_inconsistent'
                if parent in seen:
                    continue
                if parent not in cache:
                    if len(cache) >= _SEALING_PROOF_MAX_REFS:
                        return 'sealing_order_proof_omitted'
                    cache[parent] = artifacts.catalog(parent)
                if parent in required:
                    found.add(parent)
                    if required <= found:
                        break
                active.add(parent)
                stack.append((parent, iter(cache[parent].parent_refs)))
            if not required <= found:
                return 'sealing_order_unproven'
        return None
    except _proof_errors():
        return 'sealing_order_original_unavailable_or_inconsistent'


def _cited(report, alias):
    references = {item.source_key: item.input_alias for item in report.source_references}
    evidence = {item.source_key: references.get(item.source_key, item.locator.split(':', 1)[0])
        for item in report.evidence}
    # The exact scientific observation must cite this calculation, not merely
    # list an unused score somewhere in its evidence inventory.
    return any(evidence.get(key, references.get(key, key)) == alias
        for key in report.gates.observation.evidence_keys)


def _resolution_key(portfolio, plan, check):
    # Exact thresholds verify an outcome, but changing the cutoff cannot make
    # repeated exploration novel. Structured experimental conditions can.
    proposals = [p for p in portfolio.proposals if p.experiment_key == plan.experiment_key]
    if len(proposals) != 1:
        raise ValueError('Resolution family requires one exact experiment proposal.')
    proposal = proposals[0]
    return canonical_sha256(dict(
        metric=check.evaluator_metric, profile=check.evaluator_profile,
        evaluation_mode=check.evaluation_mode,
        cases=sorted([dict(role=case.scientific_role, settings=sorted(
            [s.model_dump() for s in case.settings], key=lambda s: s['name'])) for case in proposal.cases], key=canonical_json),
        factors=sorted([factor.model_dump(exclude={'rationale'}) for factor in proposal.changed_factors], key=lambda f: f['name'])))


def _metric_resolutions(portfolio, plan, record):
    validation = record.validation
    if validation is None or validation.experiment_key != plan.experiment_key or validation.plan_key != plan.plan_key:
        return []
    checks = {item.check_key: (dimension_name, item) for dimension_name in ('numerical', 'physical', 'experimental')
        for item in getattr(plan, dimension_name).checks if item.evaluation_mode == 'deterministic_threshold'
        and item.evaluator_profile == validation.evaluator_profile}
    outcomes = {item.check_key: item for item in validation.results}
    if len(outcomes) != len(validation.results):
        return []
    def verified_value(check, result):
        if check.threshold is None or result.evaluation_mode != check.evaluation_mode:
            return None
        if result.unit != check.threshold.unit or type(result.observed_value) not in {int, float} or not math.isfinite(result.observed_value):
            return None
        passed = evaluate_threshold(result.observed_value, check.threshold, observed_unit=result.unit)
        return passed if result.status in {'pass', 'fail'} and passed == (result.status == 'pass') else None
    numeric_valid = all(check.check_key in checks and check.check_key in outcomes
        and verified_value(check, outcomes[check.check_key]) is True for check in plan.numerical.checks)
    resolutions = []
    for result in validation.results:
        selected = checks.get(result.check_key)
        if not selected or result.status not in {'pass', 'fail'}:
            continue
        dimension, check = selected
        passed = verified_value(check, result)
        if passed is None or (dimension == 'numerical' and not passed) or (dimension != 'numerical' and not numeric_valid):
            continue
        resolutions.append(dict(key=_resolution_key(portfolio, plan, check), check_key=check.check_key,
            result=result.status, basis='predeclared_controlled_threshold', metric=check.metric))
    return resolutions


def verified_progress(runs, value):
    """A completed exact output and paired receipts only; no writes or qualification."""
    unknown = dict(status='unknown', reason='no_supported_predeclared_test', resolutions=[])
    if value.state != 'completed' or value.output_ref is None:
        return unknown
    if value.output_ref.schema_id in {'scidiscovery.experiment-review.v1', 'scidiscovery.scientific-review.v1'}:
        return _review_progress(runs, value)
    if value.output_ref.schema_id != 'scidiscovery.layered-diagnosis.v1':
        return unknown
    criteria = (value.recovery_policy or {}).get('progress_criteria', [])
    if not criteria:
        return unknown
    try:
        report = LayeredDiagnosisReport.model_validate_json(runs.artifacts.read(value.output_ref), strict=True)
        if report.gates.prerequisite_status != 'pass' or report.gates.observation.status not in {'pass', 'fail'}:
            return dict(unknown, reason='scientific_observation_not_evaluable')
        paired = [ref for ref in runs.artifacts.catalog(value.output_ref).parent_refs
            if ref.schema_id == 'scidiscovery.tool-evidence-manifest.v1']
        if len(paired) != 1:
            return dict(unknown, reason='completed_output_has_no_exact_calculation_manifest')
        snapshot = runs.artifacts.read(paired[0])
        from ..schema.tool_evidence import ToolEvidenceManifest
        manifest = ToolEvidenceManifest.model_validate_json(snapshot)
        descriptors = {item.source_name: runs.source_descriptor(value, item.source_name) for item in value.inputs}
        sources = ValidationSources({name: b'' for name in descriptors}, descriptors, tool_snapshot=snapshot)
        resolutions = []
        aliases = []
        for receipt in manifest.records:
            alias, metadata = receipt.get('alias'), receipt.get('metadata', {})
            if not isinstance(alias, str) or not alias or not isinstance(metadata, dict):
                return dict(unknown, reason='calculation_receipt_identity_missing_or_invalid')
            aliases.append(alias)
        if len(set(aliases)) != len(aliases):
            return dict(unknown, reason='calculation_receipt_identity_ambiguous')
        for receipt in manifest.records:
            alias = receipt['alias']
            if receipt.get('metadata', {}).get('kind') != 'calculation_record' or not _cited(report, alias):
                continue
            if not isinstance(receipt.get('artifact_ref'), dict):
                return dict(unknown, reason='calculation_receipt_original_missing')
            calculation_ref = ArtifactRef.model_validate(receipt['artifact_ref'])
            record = controlled_calculation(runs.artifacts.read(calculation_ref), receipt)
            if record.status != 'computed' or record.validation is None or record.attempt is None or record.attempt.proof_kind != 'current':
                continue
            attempts = [a for a in manifest.attempts if a.attempt_key == record.attempt.attempt_key]
            if len(attempts) != 1:
                return dict(unknown, reason='calculation_attempt_missing_or_ambiguous')
            attempt = attempts[0]
            calculation_sources(record, sources)
            validation = record.validation
            if not {validation.plan_source, validation.conditions_source, *validation.result_sources} <= set(attempt.read_sources):
                continue
            condition = descriptors.get(validation.conditions_source)
            if condition is None or condition.artifact_ref not in {i.artifact_ref for i in value.inputs}:
                continue  # A tool-authored post-hoc condition is not a frozen input.
            for raw_ref in criteria:
                ref = ArtifactRef.model_validate(raw_ref)
                if ref not in {item.artifact_ref for item in value.inputs} or descriptors.get(validation.plan_source) is None or descriptors[validation.plan_source].artifact_ref != ref:
                    continue
                portfolio = ExperimentPortfolio.model_validate_json(runs.artifacts.read(ref), strict=True)
                plans = [plan for plan in portfolio.validation_plans if plan.plan_key == report.plan_key
                    and plan.experiment_key == report.experiment_key]
                if len(plans) != 1 or portfolio.study_kind != report.study_kind:
                    continue
                # Immutable exact parents prove sealing order independently of
                # registration clocks; actual reads come from the controlled attempt.
                measured = [descriptors[name].artifact_ref for name in validation.result_sources if name in descriptors
                    and record.input_digests.get(name) == descriptors[name].sha256]
                reason = _prior_sealed_sources(runs.artifacts, (ref, condition.artifact_ref), measured)
                if len(measured) != len(validation.result_sources) or reason:
                    unknown = dict(unknown, reason=reason or 'sealing_order_unproven')
                    continue
                resolutions.extend(_metric_resolutions(portfolio, plans[0], record))
        return dict(status='verified_test_resolution' if resolutions else 'unknown',
            reason='first_resolution_requires_consumption_and_deduplication' if resolutions else unknown['reason'], resolutions=resolutions,
            output=value.output_ref.model_dump(mode='json'))
    except _proof_errors() as error:
        # Optional progress cannot make an otherwise accepted task unreadable.
        return dict(unknown, reason='progress_proof_unavailable_or_inconsistent', error=type(error).__name__)


def _proof_errors():
    from ..storage.sqlite import ArtifactRegistryError
    from ..storage.cas import CASIntegrityError
    from .run_outputs import RunCheckerError
    from ...operation_contract import SemanticRuleViolation
    from ...operations.invoke import OperationInvocationError
    from .run_records import RunError
    return (ValidationError, ValueError, RunCheckerError, SemanticRuleViolation,
        ArtifactRegistryError, CASIntegrityError, OperationInvocationError, RunError)


def _review_progress(runs, value):
    """Qualified exact-object review, with one unambiguous prior scientific test."""
    unknown = dict(status='unknown', reason='review_quality_is_not_test_progress', resolutions=[])
    classification = (value.recovery_policy or {}).get('task_classification') or {}
    if not isinstance(classification, dict):
        return unknown
    subjects = classification.get('subjects', [])
    if (classification.get('kind') != 'independent_review' or not isinstance(subjects, (list, tuple))
            or len(subjects) != 1 or not isinstance(subjects[0], dict) or 'ref' not in subjects[0]):
        return unknown
    try:
        review = json.loads(runs.artifacts.read(value.output_ref))
        if not isinstance(review, dict) or review.get('verdict') != 'pass' or not review.get('scientific_test'):
            return unknown
        conclusion = ReviewedTestConclusion.model_validate_json(canonical_json(review['scientific_test']), strict=True)
        if conclusion.result.evaluation_mode != 'reviewed_qualitative' or conclusion.result.status not in {'pass', 'fail'}:
            return unknown
        compiled = runs.compiled_operation(value)
        with runs._connect() as db:
            identity = db.execute('SELECT platform_session,thread_id FROM worker_connections WHERE run_id=?', (value.run_id,)).fetchone()
            if identity is None:
                return unknown
            runs.worker_connections._require_independent(db, value, identity['platform_session'], identity['thread_id'])
        subject = ArtifactRef.model_validate(subjects[0]['ref'])
        if subject.schema_id != 'scidiscovery.layered-diagnosis.v1' or subject not in {
                i.artifact_ref for i in value.inputs if i.port_name in compiled.spec.independent_review_ports}:
            return unknown
        cited = {item.artifact_ref for item in value.inputs if item.source_name in conclusion.result.evidence_keys}
        if cited != {subject}:
            return dict(unknown, reason='reviewed_test_does_not_cite_exact_subject')
        producer = runs.completed_for_output(subject)
        if producer is None or producer.instance_id != value.instance_id or producer.output_ref != subject:
            return unknown
        report = LayeredDiagnosisReport.model_validate_json(runs.artifacts.read(subject), strict=True)
        assessment = report.objective_assessment
        if (report.gates.prerequisite_status != 'pass' or assessment is None
                or assessment.status != conclusion.result.status or report.plan_key != conclusion.plan_key
                or report.experiment_key != conclusion.experiment_key):
            return unknown
        for raw_ref in (producer.recovery_policy or {}).get('progress_criteria', []):
            ref = ArtifactRef.model_validate(raw_ref)
            portfolio = ExperimentPortfolio.model_validate_json(runs.artifacts.read(ref), strict=True)
            plans = [p for p in portfolio.validation_plans if p.plan_key == report.plan_key and p.experiment_key == report.experiment_key]
            if len(plans) != 1 or portfolio.objective_key != assessment.objective_key:
                continue
            plan = plans[0]
            checks = [c for dimension in (plan.numerical, plan.physical, plan.experimental) for c in dimension.checks]
            if (len(checks) != 1 or checks[0].evaluation_mode != 'reviewed_qualitative'
                    or checks[0].check_key != conclusion.result.check_key):
                continue
            inputs = [i.artifact_ref for i in producer.inputs if i.port_name in {'experiment_results', 'solver_outputs', 'execution_result'}]
            reason = _prior_sealed_sources(runs.artifacts, (ref,), inputs)
            if reason:
                unknown = dict(unknown, reason=reason)
                continue
            check = checks[0]
            return dict(status='verified_test_resolution', reason='qualified_independent_exact_test_conclusion',
                resolutions=[dict(key=_resolution_key(portfolio, plan, check), check_key=check.check_key,
                    result=assessment.status, basis='independent_exact_scientific_judgment', metric=check.metric)],
                output=value.output_ref.model_dump(mode='json'))
        return unknown
    except _proof_errors() as error:
        return dict(unknown, reason='independent_progress_proof_unavailable', error=type(error).__name__)
