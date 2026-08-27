"""Transform adapter for deterministic SProcess curve scoring."""

from __future__ import annotations

import hashlib
from typing import Mapping

from scidiscovery.artifact_agent.schema.curve_score import (
    CurveBundle,
    CurveReferenceComparisonSupport,
    CurveComparisonSpec,
    CurveInterval,
    CurveReferenceCoverageBundle,
    CurveReferenceCoverageReport,
    CurveReferenceOperatorSupport,
    CurveSeries,
    CurveSeriesDeclaration,
    curve_crossings,
    curve_series_domain_reason,
    curve_units_equivalent,
    evaluate_curve_consistency,
    validate_curve_comparison_declaration_contract,
)
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.experiment import (
    ExperimentPortfolio,
    ValidationPlan,
    curve_validation_check_keys,
)
from scidiscovery.artifact_agent.schema.scientific_objective import (
    ResearchObjectiveContract,
    evaluate_objective_coverage,
)
from scidiscovery.artifact_agent.transforms import TransformOutput
from tcad_artifact.project_packager import RuntimeAttestation

from .normalizer import (
    SProcessLogSourceSpec,
    SProcessSeriesSpec,
    normalize_sprocess_log,
    source_spec_from_comparison_spec,
)
from .figure_evidence_normalizer import (
    FIGURE_EVIDENCE_BUNDLE_PROFILE,
    FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
    normalize_figure_evidence,
)
from .plx_normalizer import (
    PLX_NORMALIZER_PROFILE,
    SProcessPLXSourceSpec,
    normalize_sprocess_plx,
)
from .plotter import render_curve_comparison_overview


SPROCESS_NORMALIZE_PROFILE = "scidiscovery.curve-normalize.sprocess-log.v1"
CURVE_CONSISTENCY_PROFILE = "scidiscovery.curve-consistency.v1"
CURVE_SCORE_SPROCESS_PROFILE = "scidiscovery.curve-score.sprocess-log.v1"
SPROCESS_PLX_BUNDLE_PROFILE = "scidiscovery.curve-bundle.sprocess-plx.v1"
CURVE_SCORE_PROFILE = "scidiscovery.curve-score.v1"
CURVE_REFERENCE_COVERAGE_PROFILE = "scidiscovery.curve-reference-coverage.v1"
OBJECTIVE_COVERAGE_PROFILE = "scidiscovery.objective-coverage.v1"


class CurveScoreTransformAdapter:
    @staticmethod
    def supports_transform_profile(profile: str) -> bool:
        return profile in {
            SPROCESS_NORMALIZE_PROFILE,
            PLX_NORMALIZER_PROFILE,
            CURVE_CONSISTENCY_PROFILE,
            CURVE_SCORE_SPROCESS_PROFILE,
            SPROCESS_PLX_BUNDLE_PROFILE,
            FIGURE_EVIDENCE_BUNDLE_PROFILE,
            FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
            CURVE_SCORE_PROFILE,
            CURVE_REFERENCE_COVERAGE_PROFILE,
            OBJECTIVE_COVERAGE_PROFILE,
        }

    @staticmethod
    def required_input_parentage(profile: str) -> tuple[tuple[str, str], ...]:
        if profile == CURVE_SCORE_SPROCESS_PROFILE:
            return (("runtime_attestation", "solver_output"),)
        return ()

    @staticmethod
    def required_input_parentage_for_inputs(
        profile: str, input_names: tuple[str, ...]
    ) -> tuple[tuple[str, str], ...]:
        if profile == SPROCESS_PLX_BUNDLE_PROFILE:
            return tuple(
                ("runtime_attestation", name)
                for name in input_names
                if name.startswith("solver_output__")
            )
        if profile in {
            FIGURE_EVIDENCE_BUNDLE_PROFILE,
            FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
        }:
            return (
                ("validation_report", "figure_manifest"),
                *tuple(
                    ("validation_report", name)
                    for name in input_names
                    if name.startswith("curve_table__")
                ),
            )
        if profile == CURVE_SCORE_PROFILE:
            return (
                ("curve_bundle", "runtime_attestation"),
                ("curve_bundle", "experiment_plan"),
            )
        if profile == OBJECTIVE_COVERAGE_PROFILE:
            return (("experiment_plan", "objective"),)
        return CurveScoreTransformAdapter.required_input_parentage(profile)

    @staticmethod
    def nonqualifying_input_names(
        profile: str, input_names: tuple[str, ...]
    ) -> tuple[str, ...]:
        if profile not in {
            FIGURE_EVIDENCE_BUNDLE_PROFILE,
            FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
        }:
            return ()
        return tuple(
            name
            for name in input_names
            if name in {"figure_manifest", "validation_report"}
            or name.startswith("curve_table__")
        )

    @staticmethod
    def transform(
        *, profile: str, inputs: Mapping[str, bytes]
    ) -> tuple[TransformOutput, ...]:
        if profile == SPROCESS_NORMALIZE_PROFILE:
            if set(inputs) != {"source_spec", "solver_output"}:
                raise ValueError(
                    "SProcess curve normalization requires source_spec and solver_output"
                )
            bundle, audit = normalize_sprocess_log(
                inputs["solver_output"],
                SProcessLogSourceSpec.model_validate_json(
                    inputs["source_spec"], strict=True
                ),
            )
            return _normalization_outputs(bundle, audit.canonical_json())
        if profile == PLX_NORMALIZER_PROFILE:
            if set(inputs) != {"source_spec", "solver_output"}:
                raise ValueError(
                    "SProcess PLX normalization requires source_spec and solver_output"
                )
            bundle, audit = normalize_sprocess_plx(
                inputs["solver_output"],
                SProcessPLXSourceSpec.model_validate_json(
                    inputs["source_spec"], strict=True
                ),
            )
            return _normalization_outputs(bundle, audit.canonical_json())
        if profile == CURVE_CONSISTENCY_PROFILE:
            if set(inputs) != {"curve_bundle", "comparison_spec"}:
                raise ValueError(
                    "curve consistency requires curve_bundle and comparison_spec"
                )
            report = evaluate_curve_consistency(
                CurveBundle.model_validate_json(inputs["curve_bundle"], strict=True),
                CurveComparisonSpec.model_validate_json(
                    inputs["comparison_spec"], strict=True
                ),
            )
            return (_report_output(report.canonical_json(), scientific=False),)
        if profile == SPROCESS_PLX_BUNDLE_PROFILE:
            return _bundle_sprocess_plx(inputs)
        if profile in {
            FIGURE_EVIDENCE_BUNDLE_PROFILE,
            FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
        }:
            return _bundle_figure_evidence(inputs, profile=profile)
        if profile == CURVE_SCORE_PROFILE:
            return _score_curve_bundle(inputs)
        if profile == CURVE_REFERENCE_COVERAGE_PROFILE:
            return _curve_reference_coverage(inputs)
        if profile == OBJECTIVE_COVERAGE_PROFILE:
            return _objective_coverage(inputs)
        if profile != CURVE_SCORE_SPROCESS_PROFILE:
            raise ValueError("unsupported curve-score transform profile")
        fixed = {"solver_output", "runtime_attestation"}
        reference_inputs = {
            name for name in inputs if name.startswith("reference_curve__")
        }
        if (
            not fixed.union({"experiment_plan"}).issubset(inputs)
            or "reference_curve__" in reference_inputs
            or set(inputs) - fixed - {"experiment_plan"} - reference_inputs
            not in (set(), {"source_spec"})
        ):
            raise ValueError(
                "SProcess curve score requires solver_output, runtime_attestation, "
                "experiment_plan, and optional source_spec and "
                "reference_curve__* inputs"
            )
        attestation = RuntimeAttestation.model_validate_json(
            inputs["runtime_attestation"], strict=True
        )
        if attestation.verdict != "pass":
            raise ValueError("curve score requires a passing runtime attestation")
        comparison_spec, validation_plan, validation_check_keys = _comparison_spec(
            inputs["experiment_plan"],
            expected_evaluator_profile=CURVE_SCORE_SPROCESS_PROFILE,
        )
        source_spec = (
            SProcessLogSourceSpec.model_validate_json(
                inputs["source_spec"], strict=True
            )
            if "source_spec" in inputs
            else source_spec_from_comparison_spec(comparison_spec)
        )
        solver_bundle, audit = normalize_sprocess_log(
            inputs["solver_output"], source_spec
        )
        reference_bundles = tuple(
            (
                name,
                CurveBundle.model_validate_json(inputs[name], strict=True),
            )
            for name in sorted(reference_inputs)
        )
        reference_bundles = _select_reference_bundles(
            reference_bundles, comparison_spec
        )
        _validate_reference_bundle_declarations(reference_bundles, comparison_spec)
        bundle = _merge_curve_inputs(solver_bundle, reference_bundles)
        report = evaluate_curve_consistency(
            bundle,
            comparison_spec,
            validation_plan_sha256=canonical_sha256(validation_plan),
            covered_validation_check_keys=validation_check_keys,
        )
        return (
            _report_output(report.canonical_json(), scientific=True),
            TransformOutput(
                label="curve_bundle",
                content=bundle.canonical_json(),
                kind="curve_bundle",
                schema="scidiscovery.curve-bundle.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
            TransformOutput(
                label="audit",
                content=canonical_json(
                    {
                        "schema_version": 1,
                        "comparison_spec_sha256": canonical_sha256(
                            comparison_spec
                        ),
                        "validation_plan_sha256": canonical_sha256(
                            validation_plan
                        ),
                        "covered_validation_check_keys": list(
                            validation_check_keys
                        ),
                        "solver_normalization": audit.model_dump(mode="json"),
                        "reference_inputs": [
                            {
                                "source_name": name,
                                "curve_bundle_sha256": canonical_sha256(reference),
                                "series_keys": [
                                    item.series_key for item in reference.series
                                ],
                            }
                            for name, reference in reference_bundles
                        ],
                    }
                ),
                kind="curve_score_audit",
                schema="scidiscovery.curve-score-audit.v1",
                payload_schema_version=1,
                media_type="application/json",
            ),
        )


def _merge_curve_inputs(
    solver_bundle: CurveBundle,
    references: tuple[tuple[str, CurveBundle], ...],
) -> CurveBundle:
    bundles = (solver_bundle, *(item[1] for item in references))
    return CurveBundle(
        source_profile="scidiscovery.curve-score-inputs.v1",
        source_digests=tuple(
            sorted(
                {
                    digest
                    for bundle in bundles
                    for digest in (
                        *bundle.source_digests,
                        canonical_sha256(bundle),
                    )
                }
            )
        ),
        series=tuple(series for bundle in bundles for series in bundle.series),
    )


def _bundle_sprocess_plx(inputs: Mapping[str, bytes]) -> tuple[TransformOutput, ...]:
    fixed = {"runtime_attestation", "experiment_plan"}
    solver_inputs = {
        name for name in inputs if name.startswith("solver_output__")
    }
    if (
        not fixed.issubset(inputs)
        or not solver_inputs
        or "solver_output__" in solver_inputs
        or set(inputs) != fixed | solver_inputs
    ):
        raise ValueError(
            "SProcess PLX bundling requires runtime_attestation, experiment_plan, "
            "and solver_output__<series_key> inputs"
        )
    attestation = RuntimeAttestation.model_validate_json(
        inputs["runtime_attestation"], strict=True
    )
    if attestation.verdict != "pass":
        raise ValueError("curve score requires a passing runtime attestation")
    comparison_spec, _, _ = _comparison_spec(inputs["experiment_plan"])
    all_solver_declarations = tuple(
        item
        for item in comparison_spec.series_declarations
        if item.source == "solver_output"
    )
    compared_series = {
        series_key
        for comparison in comparison_spec.comparisons
        for series_key in (
            comparison.reference_series,
            comparison.candidate_series,
        )
    }
    solver_declarations = tuple(
        item for item in all_solver_declarations if item.series_key in compared_series
    )
    required_solver_inputs = {
        f"solver_output__{item.series_key}" for item in solver_declarations
    }
    declared_solver_inputs = {
        f"solver_output__{item.series_key}" for item in all_solver_declarations
    }
    if not required_solver_inputs.issubset(solver_inputs) or not solver_inputs.issubset(
        declared_solver_inputs
    ):
        missing = sorted(required_solver_inputs - solver_inputs)
        unexpected = sorted(solver_inputs - declared_solver_inputs)
        raise ValueError(
            "PLX inputs must cover every compared solver series and no undeclared "
            "solver series; "
            f"missing={missing}, unexpected={unexpected}"
        )

    normalized: list[CurveBundle] = []
    normalization_audits: list[dict[str, object]] = []
    for declaration in solver_declarations:
        source_name = f"solver_output__{declaration.series_key}"
        bundle, audit = normalize_sprocess_plx(
            inputs[source_name],
            SProcessPLXSourceSpec(
                series=SProcessSeriesSpec(
                    series_key=declaration.series_key,
                    case_key=declaration.case_key,
                    role=declaration.role,
                    x_axis=declaration.x_axis,
                    y_axis=declaration.y_axis,
                    min_points=declaration.min_points,
                    max_points=declaration.max_points,
                ),
                required_intervals=_required_series_intervals(
                    comparison_spec, declaration.series_key
                ),
            ),
            source_name=source_name,
        )
        bundle = bundle.model_copy(
            update={
                "series": tuple(
                    item.model_copy(
                        update={"scientific_role": declaration.scientific_role}
                    )
                    for item in bundle.series
                )
            }
        )
        normalized.append(bundle)
        normalization_audits.append(
            {
                "source_name": source_name,
                **audit.model_dump(mode="json"),
            }
        )
    solver_bundle = CurveBundle(
        source_profile=PLX_NORMALIZER_PROFILE,
        source_digests=tuple(
            sorted({digest for bundle in normalized for digest in bundle.source_digests})
        ),
        series=tuple(series for bundle in normalized for series in bundle.series),
    )
    return (
        TransformOutput(
            label="primary",
            content=solver_bundle.canonical_json(),
            kind="curve_bundle",
            schema="scidiscovery.curve-bundle.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
        TransformOutput(
            label="audit",
            content=canonical_json(
                {
                    "schema_version": 1,
                    "comparison_spec_sha256": canonical_sha256(comparison_spec),
                    "ignored_uncompared_solver_inputs": sorted(
                        solver_inputs - required_solver_inputs
                    ),
                    "solver_normalizations": normalization_audits,
                }
            ),
            kind="curve_normalization_audit",
            schema="scidiscovery.curve-normalization-audit.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
    )


def _bundle_figure_evidence(
    inputs: Mapping[str, bytes],
    *,
    profile: str,
) -> tuple[TransformOutput, ...]:
    fixed = {"figure_manifest", "validation_report"}
    table_inputs = {name for name in inputs if name.startswith("curve_table__")}
    if (
        not fixed.issubset(inputs)
        or not table_inputs
        or "curve_table__" in table_inputs
        or set(inputs) != fixed | table_inputs
    ):
        raise ValueError(
            "figure evidence bundling requires figure_manifest, validation_report, "
            "and curve_table__<panel_key>__<series_key> inputs"
        )
    bundle, audits = normalize_figure_evidence(
        manifest_content=inputs["figure_manifest"],
        validation_report_content=inputs["validation_report"],
        curve_tables={name: inputs[name] for name in table_inputs},
        profile=profile,
    )
    return (
        TransformOutput(
            label="primary",
            content=bundle.canonical_json(),
            kind="curve_bundle",
            schema="scidiscovery.curve-bundle.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
        TransformOutput(
            label="audit",
            content=canonical_json(
                {
                    "schema_version": 1,
                    "profile": profile,
                    "series": [item.as_dict() for item in audits],
                }
            ),
            kind="figure_evidence_curve_normalization_audit",
            schema="scidiscovery.figure-evidence-curve-normalization-audit.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
    )


def _required_series_intervals(
    comparison_spec: CurveComparisonSpec, series_key: str
) -> tuple[CurveInterval, ...]:
    declared = sorted(
        (comparison.domain.start, comparison.domain.stop)
        for comparison in comparison_spec.comparisons
        if series_key
        in {comparison.reference_series, comparison.candidate_series}
    )
    merged: list[CurveInterval] = []
    for start, stop in declared:
        if merged and start <= merged[-1].stop:
            merged[-1] = CurveInterval(
                start=merged[-1].start,
                stop=max(stop, merged[-1].stop),
            )
        else:
            merged.append(CurveInterval(start=start, stop=stop))
    return tuple(merged)


def _score_curve_bundle(inputs: Mapping[str, bytes]) -> tuple[TransformOutput, ...]:
    fixed = {"curve_bundle", "runtime_attestation", "experiment_plan"}
    reference_inputs = {
        name for name in inputs if name.startswith("reference_curve__")
    }
    if (
        not fixed.issubset(inputs)
        or "reference_curve__" in reference_inputs
        or set(inputs) != fixed | reference_inputs
    ):
        raise ValueError(
            "curve score requires curve_bundle, runtime_attestation, "
            "experiment_plan, and optional reference_curve__* inputs"
        )
    attestation = RuntimeAttestation.model_validate_json(
        inputs["runtime_attestation"], strict=True
    )
    if attestation.verdict != "pass":
        raise ValueError("curve score requires a passing runtime attestation")
    comparison_spec, validation_plan, validation_check_keys = _comparison_spec(
        inputs["experiment_plan"],
        expected_evaluator_profile=CURVE_SCORE_PROFILE,
    )
    solver_bundle = CurveBundle.model_validate_json(
        inputs["curve_bundle"], strict=True
    )
    _validate_solver_bundle_declarations(solver_bundle, comparison_spec)
    reference_bundles = tuple(
        (
            name,
            CurveBundle.model_validate_json(inputs[name], strict=True),
        )
        for name in sorted(reference_inputs)
    )
    reference_bundles = _select_reference_bundles(
        reference_bundles, comparison_spec
    )
    _validate_reference_bundle_declarations(reference_bundles, comparison_spec)
    bundle = _merge_curve_inputs(solver_bundle, reference_bundles)
    report = evaluate_curve_consistency(
        bundle,
        comparison_spec,
        validation_plan_sha256=canonical_sha256(validation_plan),
        covered_validation_check_keys=validation_check_keys,
    )
    plot = render_curve_comparison_overview(bundle, comparison_spec, report)
    plot_sha256 = hashlib.sha256(plot.content).hexdigest()
    return (
        _report_output(report.canonical_json(), scientific=True),
        TransformOutput(
            label="curve_bundle",
            content=bundle.canonical_json(),
            kind="curve_bundle",
            schema="scidiscovery.curve-bundle.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
        TransformOutput(
            label="audit",
            content=canonical_json(
                {
                    "schema_version": 1,
                    "comparison_spec_sha256": canonical_sha256(comparison_spec),
                    "validation_plan_sha256": canonical_sha256(validation_plan),
                    "covered_validation_check_keys": list(validation_check_keys),
                    "curve_bundle_sha256": canonical_sha256(solver_bundle),
                    "comparison_plot": {
                        "label": "comparison_plot",
                        "sha256": plot_sha256,
                        "bytes": len(plot.content),
                        "merged_curve_bundle_sha256": canonical_sha256(bundle),
                        "metric_report_sha256": canonical_sha256(report),
                        "plotted_comparison_keys": list(
                            plot.plotted_comparison_keys
                        ),
                        "omitted_comparison_keys": list(
                            plot.omitted_comparison_keys
                        ),
                    },
                    "reference_inputs": [
                        {
                            "source_name": name,
                            "curve_bundle_sha256": canonical_sha256(reference),
                            "series_keys": [
                                item.series_key for item in reference.series
                            ],
                        }
                        for name, reference in reference_bundles
                    ],
                }
            ),
            kind="curve_score_audit",
            schema="scidiscovery.curve-score-audit.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
        TransformOutput(
            label="comparison_plot",
            content=plot.content,
            kind="curve_comparison_plot",
            schema="scidiscovery.curve-comparison-plot.v1",
            payload_schema_version=1,
            media_type="image/png",
        ),
    )


def _curve_reference_coverage(
    inputs: Mapping[str, bytes],
) -> tuple[TransformOutput, ...]:
    fixed = {"experiment_plan"}
    reference_inputs = {
        name for name in inputs if name.startswith("reference_curve__")
    }
    if (
        set(inputs) != fixed | reference_inputs
        or not reference_inputs
        or "reference_curve__" in reference_inputs
    ):
        raise ValueError(
            "curve reference coverage requires experiment_plan and one or more "
            "reference_curve__* inputs"
        )
    comparison_spec, _, _ = _comparison_spec(inputs["experiment_plan"])
    bundles = tuple(
        (
            name,
            CurveBundle.model_validate_json(inputs[name], strict=True),
        )
        for name in sorted(reference_inputs)
    )
    actual: dict[str, tuple[str, CurveBundle, CurveSeries]] = {}
    for source_name, bundle in bundles:
        for series in bundle.series:
            if series.series_key in actual:
                raise ValueError(
                    f"curve library series is supplied more than once: "
                    f"{series.series_key}"
                )
            actual[series.series_key] = (source_name, bundle, series)
    required_declarations = {
        item.series_key: item
        for item in comparison_spec.series_declarations
        if item.source == "reference_input"
    }
    required = set(required_declarations)
    dispositions = {
        item.series_key: item.disposition
        for item in comparison_spec.reference_dispositions
    }
    mapped = {key for key, value in dispositions.items() if value == "compare"}
    excluded = {key for key, value in dispositions.items() if value == "exclude"}
    missing = required - set(actual)
    unmapped = set(actual) - set(dispositions)
    unknown = set(dispositions) - set(actual)
    declaration_mismatches = {
        series_key
        for series_key, declaration in required_declarations.items()
        if series_key in actual
        and not _reference_series_matches_declaration(
            actual[series_key][2], declaration
        )
    }
    comparison_support = _reference_comparison_support(comparison_spec, actual)
    report = CurveReferenceCoverageReport(
        schema_version="scidiscovery.curve-reference-coverage.v1",
        status=(
            "pass"
            if not missing
            and not unmapped
            and not unknown
            and not declaration_mismatches
            and not any(item.status == "fail" for item in comparison_support)
            and mapped == required
            else "fail"
        ),
        experiment_plan_sha256=canonical_sha256(
            ExperimentPortfolio.model_validate_json(
                inputs["experiment_plan"], strict=True
            )
        ),
        comparison_spec_sha256=canonical_sha256(comparison_spec),
        bundles=tuple(
            CurveReferenceCoverageBundle(
                source_name=name,
                source_profile=bundle.source_profile,
                bundle_sha256=canonical_sha256(bundle),
                series_keys=tuple(item.series_key for item in bundle.series),
            )
            for name, bundle in bundles
        ),
        required_reference_series=tuple(sorted(required)),
        mapped_reference_series=tuple(sorted(mapped)),
        excluded_reference_series=tuple(sorted(excluded)),
        missing_declared_reference_series=tuple(sorted(missing)),
        unmapped_bundle_series=tuple(sorted(unmapped)),
        unknown_disposition_series=tuple(sorted(unknown)),
        declaration_mismatch_series=tuple(sorted(declaration_mismatches)),
        comparison_support=comparison_support,
    )
    return (
        TransformOutput(
            label="primary",
            content=report.canonical_json(),
            kind="curve_reference_coverage",
            schema="scidiscovery.curve-reference-coverage.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
    )


def _reference_comparison_support(
    comparison_spec: CurveComparisonSpec,
    actual: Mapping[str, tuple[str, CurveBundle, CurveSeries]],
) -> tuple[CurveReferenceComparisonSupport, ...]:
    declarations = {
        item.series_key: item for item in comparison_spec.series_declarations
    }
    results: list[CurveReferenceComparisonSupport] = []
    for comparison in comparison_spec.comparisons:
        declaration = declarations.get(comparison.reference_series)
        if declaration is None or declaration.source != "reference_input":
            continue
        found = actual.get(comparison.reference_series)
        if found is None:
            continue
        series = found[2]
        domain_reason = curve_series_domain_reason(series, comparison.domain)
        operators: list[CurveReferenceOperatorSupport] = []
        if domain_reason is None:
            for operator in comparison.operators:
                if operator.kind not in {"crossing_shift", "width_shift"}:
                    continue
                assert operator.level is not None
                level_crossings: tuple[float, ...] | None = None
                second_level_crossings: tuple[float, ...] | None = None
                level_count: int | None = None
                second_level_count: int | None = None
                reason_code: str | None = None
                try:
                    level_crossings = curve_crossings(
                        series,
                        operator.level,
                        operator.crossing_direction,
                        comparison.domain,
                        comparison.interpolation,
                    )
                    level_count = len(level_crossings)
                    if operator.second_level is not None:
                        second_level_crossings = curve_crossings(
                            series,
                            operator.second_level,
                            operator.crossing_direction,
                            comparison.domain,
                            comparison.interpolation,
                        )
                        second_level_count = len(second_level_crossings)
                except ValueError as error:
                    reason_code = str(error)
                if reason_code is None and level_count != 1:
                    reason_code = "level_crossing_count_not_one"
                if reason_code is None and second_level_count not in {None, 1}:
                    reason_code = "second_level_crossing_count_not_one"
                operators.append(
                    CurveReferenceOperatorSupport(
                        comparison_key=comparison.comparison_key,
                        operator_key=operator.operator_key,
                        series_key=series.series_key,
                        status="fail" if reason_code is not None else "pass",
                        level_crossing_count=level_count,
                        second_level_crossing_count=second_level_count,
                        level_crossings=level_crossings,
                        second_level_crossings=second_level_crossings,
                        reason_code=reason_code,
                    )
                )
        failed = domain_reason is not None or any(
            item.status == "fail" for item in operators
        )
        results.append(
            CurveReferenceComparisonSupport(
                comparison_key=comparison.comparison_key,
                reference_series=series.series_key,
                status="fail" if failed else "pass",
                domain_reason_code=domain_reason,
                operators=tuple(operators),
            )
        )
    return tuple(results)


def _objective_coverage(inputs: Mapping[str, bytes]) -> tuple[TransformOutput, ...]:
    fixed = {"objective", "experiment_plan"}
    reference_inputs = {
        name for name in inputs if name.startswith("reference_curve__")
    }
    if (
        set(inputs) != fixed | reference_inputs
        or "reference_curve__" in reference_inputs
    ):
        raise ValueError(
            "objective coverage requires objective, experiment_plan, and only "
            "optional reference_curve__* inputs"
        )
    objective = ResearchObjectiveContract.model_validate_json(
        inputs["objective"], strict=True
    )
    portfolio = ExperimentPortfolio.model_validate_json(
        inputs["experiment_plan"], strict=True
    )
    bundles = tuple(
        (
            name,
            CurveBundle.model_validate_json(inputs[name], strict=True),
        )
        for name in sorted(reference_inputs)
    )
    report = evaluate_objective_coverage(objective, portfolio, bundles)
    return (
        TransformOutput(
            label="primary",
            content=report.canonical_json(),
            kind="objective_coverage",
            schema="scidiscovery.objective-coverage.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
    )
def _validate_solver_bundle_declarations(
    bundle: CurveBundle, comparison_spec: CurveComparisonSpec
) -> None:
    compared_series = {
        series_key
        for comparison in comparison_spec.comparisons
        for series_key in (
            comparison.reference_series,
            comparison.candidate_series,
        )
    }
    expected = {
        item.series_key: item
        for item in comparison_spec.series_declarations
        if item.source == "solver_output" and item.series_key in compared_series
    }
    actual = {item.series_key: item for item in bundle.series}
    if set(actual) != set(expected):
        raise ValueError("curve bundle must cover the exact compared solver series")
    for series_key, declaration in expected.items():
        series = actual[series_key]
        if (
            series.case_key != declaration.case_key
            or series.role != declaration.role
            or series.scientific_role != declaration.scientific_role
            or series.x_axis != declaration.x_axis
            or series.y_axis != declaration.y_axis
            or not declaration.min_points <= len(series.points) <= declaration.max_points
        ):
            raise ValueError(
                f"curve bundle series differs from declaration: {series_key}"
            )


def _validate_reference_bundle_declarations(
    bundles: tuple[tuple[str, CurveBundle], ...],
    comparison_spec: CurveComparisonSpec,
) -> None:
    expected = {
        item.series_key: item
        for item in comparison_spec.series_declarations
        if item.source == "reference_input"
    }
    actual: dict[str, CurveSeries] = {}
    for _, bundle in bundles:
        for series in bundle.series:
            if series.series_key in actual:
                raise ValueError(
                    f"reference series is supplied more than once: {series.series_key}"
                )
            actual[series.series_key] = series
    if set(actual) != set(expected):
        raise ValueError("reference bundles must cover the exact declared series")
    for series_key, declaration in expected.items():
        series = actual[series_key]
        if not _reference_series_matches_declaration(series, declaration):
            raise ValueError(
                f"reference bundle series differs from declaration: {series_key}"
            )


def _reference_series_matches_declaration(
    series: CurveSeries, declaration: CurveSeriesDeclaration
) -> bool:
    return bool(
        curve_units_equivalent(series.x_axis.unit, declaration.x_axis.unit)
        and series.x_axis.scale == declaration.x_axis.scale
        and curve_units_equivalent(series.y_axis.unit, declaration.y_axis.unit)
        and series.y_axis.scale == declaration.y_axis.scale
        and (
            series.availability.status == "unavailable"
            and not series.points
            or series.availability.status == "available"
            and declaration.min_points <= len(series.points) <= declaration.max_points
        )
    )


def _select_reference_bundles(
    bundles: tuple[tuple[str, CurveBundle], ...],
    comparison_spec: CurveComparisonSpec,
) -> tuple[tuple[str, CurveBundle], ...]:
    """Select only agent-declared references from complete curve libraries."""

    declarations = {
        item.series_key: item
        for item in comparison_spec.series_declarations
        if item.source == "reference_input"
    }
    required = set(declarations)
    found: dict[str, tuple[str, CurveBundle, CurveSeries]] = {}
    for source_name, bundle in bundles:
        for series in bundle.series:
            if series.series_key not in required:
                continue
            if series.series_key in found:
                raise ValueError(
                    f"reference series is supplied more than once: {series.series_key}"
                )
            found[series.series_key] = (source_name, bundle, series)
    missing = sorted(required - set(found))
    if missing:
        raise ValueError(
            "reference curve inputs are missing declared reference series; "
            f"missing={missing}"
        )
    selected: list[tuple[str, CurveBundle]] = []
    for source_name, bundle in bundles:
        series = tuple(
            item.model_copy(
                update={
                    "scientific_role": declarations[item.series_key].scientific_role
                }
            )
            for item in bundle.series
            if item.series_key in required
            and found[item.series_key][0] == source_name
        )
        if not series:
            continue
        selected.append(
            (
                source_name,
                CurveBundle(
                    source_profile=bundle.source_profile,
                    source_digests=bundle.source_digests,
                    series=series,
                ),
            )
        )
    return tuple(selected)


def _comparison_spec(
    experiment_plan: bytes,
    *,
    expected_evaluator_profile: str | None = None,
) -> tuple[CurveComparisonSpec, ValidationPlan, tuple[str, ...]]:
    portfolio = ExperimentPortfolio.model_validate_json(
        experiment_plan, strict=True
    )
    declared = tuple(
        proposal
        for proposal in portfolio.proposals
        if proposal.curve_comparison_spec is not None
    )
    if len(declared) != 1:
        raise ValueError(
            "experiment plan must declare exactly one curve comparison spec"
        )
    proposal = declared[0]
    plan = next(
        item
        for item in portfolio.validation_plans
        if item.experiment_key == proposal.experiment_key
    )
    assert proposal.curve_comparison_spec is not None
    validate_curve_comparison_declaration_contract(
        proposal.curve_comparison_spec
    )
    evaluator_profiles = {
        check.evaluator_profile
        for dimension in (plan.numerical, plan.physical, plan.experimental)
        for check in dimension.checks
        if check.evaluation_mode == "deterministic_threshold"
    }
    if (
        expected_evaluator_profile is not None
        and evaluator_profiles
        and evaluator_profiles != {expected_evaluator_profile}
    ):
        raise ValueError(
            "experiment plan deterministic checks require a different curve-score "
            "profile"
        )
    return (
        proposal.curve_comparison_spec,
        plan,
        curve_validation_check_keys(proposal, plan),
    )


def _normalization_outputs(
    bundle: CurveBundle, audit_content: bytes
) -> tuple[TransformOutput, ...]:
    return (
        TransformOutput(
            label="primary",
            content=bundle.canonical_json(),
            kind="curve_bundle",
            schema="scidiscovery.curve-bundle.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
        TransformOutput(
            label="audit",
            content=audit_content,
            kind="curve_normalization_audit",
            schema="scidiscovery.curve-normalization-audit.v1",
            payload_schema_version=1,
            media_type="application/json",
        ),
    )


def _report_output(content: bytes, *, scientific: bool) -> TransformOutput:
    return TransformOutput(
        label="primary",
        content=content,
        kind="metric_report" if scientific else "curve_consistency_report",
        schema="scidiscovery.curve-consistency-report.v1",
        payload_schema_version=1,
        media_type="application/json",
    )


__all__ = [
    "CURVE_CONSISTENCY_PROFILE",
    "CURVE_SCORE_PROFILE",
    "CURVE_REFERENCE_COVERAGE_PROFILE",
    "CURVE_SCORE_SPROCESS_PROFILE",
    "FIGURE_EVIDENCE_BUNDLE_PROFILE",
    "FIGURE_EVIDENCE_BUNDLE_PROFILE_V2",
    "OBJECTIVE_COVERAGE_PROFILE",
    "PLX_NORMALIZER_PROFILE",
    "SPROCESS_PLX_BUNDLE_PROFILE",
    "SPROCESS_NORMALIZE_PROFILE",
    "CurveScoreTransformAdapter",
]
