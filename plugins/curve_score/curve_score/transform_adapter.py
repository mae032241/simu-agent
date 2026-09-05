"""Domain-neutral deterministic curve transforms."""

from __future__ import annotations

import hashlib
from typing import Mapping

from .schema import (
    CurveBundle,
    CurveExperimentContract,
    CurveReferenceComparisonSupport,
    CurveComparisonSpec,
    CurveReferenceCoverageBundle,
    CurveReferenceCoverageReport,
    CurveReferenceOperatorSupport,
    CurveSeries,
    CurveSeriesDeclaration,
    curve_crossings,
    curve_series_domain_reason,
    curve_units_equivalent,
    evaluate_curve_consistency,
    validate_curve_experiment_contract,
)
from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.artifact_agent.schema.experiment import (
    ExperimentPortfolio,
    ValidationPlan,
)
from .objective import (
    ResearchObjectiveContract,
    evaluate_objective_coverage,
)
from .figure_evidence_normalizer import (
    FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
    normalize_figure_evidence,
)
from .plotter import render_curve_comparison_overview


CURVE_SCORE_OPERATION = "scidiscovery.curve-score.v1"


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


def bundle_figure_evidence_outputs(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
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
        profile=FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
    )
    return {
        "curve_bundle": (bundle.canonical_json(),),
        "normalization_audit": (
            canonical_json(
                {
                    "schema_version": 1,
                    "profile": FIGURE_EVIDENCE_BUNDLE_PROFILE_V2,
                    "series": [item.as_dict() for item in audits],
                }
            ),
        ),
    }


def score_curve_bundle_outputs(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    fixed = {"curve_bundle", "curve_contract", "experiment_plan"}
    reference_inputs = {
        name for name in inputs if name.startswith("reference_curve__")
    }
    if (
        not fixed.issubset(inputs)
        or "reference_curve__" in reference_inputs
        or set(inputs) != fixed | reference_inputs
    ):
        raise ValueError(
            "curve score requires curve_bundle, curve_contract, experiment_plan, "
            "and optional reference_curve__* inputs"
        )
    comparison_spec, validation_plan, validation_check_keys = _comparison_spec(
        inputs["experiment_plan"],
        inputs["curve_contract"],
        expected_evaluator_profile=CURVE_SCORE_OPERATION,
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
    return {
        "metric_report": (report.canonical_json(),),
        "merged_curve_bundle": (bundle.canonical_json(),),
        "score_audit": (
            canonical_json(
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
        ),
        "comparison_plot": (plot.content,),
    }


def curve_reference_coverage_outputs(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    fixed = {"experiment_plan", "curve_contract"}
    reference_inputs = {
        name for name in inputs if name.startswith("reference_curve__")
    }
    if (
        set(inputs) != fixed | reference_inputs
        or not reference_inputs
        or "reference_curve__" in reference_inputs
    ):
        raise ValueError(
            "curve reference coverage requires experiment_plan, curve_contract, "
            "and one or more "
            "reference_curve__* inputs"
        )
    comparison_spec, _, _ = _comparison_spec(
        inputs["experiment_plan"], inputs["curve_contract"]
    )
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
    return {"coverage_report": (report.canonical_json(),)}


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


def objective_coverage_outputs(
    inputs: Mapping[str, bytes],
) -> dict[str, tuple[bytes, ...]]:
    fixed = {"objective", "experiment_plan"}
    contract_inputs = {
        name for name in inputs if name.startswith("curve_contract__")
    }
    reference_inputs = {
        name for name in inputs if name.startswith("reference_curve__")
    }
    if (
        set(inputs) != fixed | reference_inputs | contract_inputs
        or "reference_curve__" in reference_inputs
        or "curve_contract__" in contract_inputs
    ):
        raise ValueError(
            "objective coverage requires objective, experiment_plan, and only "
            "curve_contract__* and optional reference_curve__* inputs"
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
    contracts = tuple(
        CurveExperimentContract.model_validate_json(inputs[name], strict=True)
        for name in sorted(contract_inputs)
    )
    report = evaluate_objective_coverage(
        objective, portfolio, contracts, bundles
    )
    return {"coverage_report": (report.canonical_json(),)}
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
    curve_contract: bytes,
    *,
    expected_evaluator_profile: str | None = None,
) -> tuple[CurveComparisonSpec, ValidationPlan, tuple[str, ...]]:
    portfolio = ExperimentPortfolio.model_validate_json(
        experiment_plan, strict=True
    )
    contract = CurveExperimentContract.model_validate_json(
        curve_contract, strict=True
    )
    plan = next(
        item
        for item in portfolio.validation_plans
        if item.experiment_key == contract.experiment_key
    )
    validation_check_keys = validate_curve_experiment_contract(
        contract,
        portfolio,
        expected_evaluator_profile=expected_evaluator_profile,
    )
    return (
        contract.comparison_spec,
        plan,
        validation_check_keys,
    )


__all__ = [
    "CURVE_SCORE_OPERATION",
    "bundle_figure_evidence_outputs",
    "curve_reference_coverage_outputs",
    "objective_coverage_outputs",
    "score_curve_bundle_outputs",
]
