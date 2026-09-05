"""Reviewable device parameters with deterministic source cross-validation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, Field, model_validator

from scidiscovery.artifact_agent.schema.artifact import UtcRfc3339
from scidiscovery.artifact_agent.schema.common import Identifier, SchemaModel, canonical_json
from scidiscovery.artifact_agent.schema.scientific_foundation import SourceType
from scidiscovery.artifact_agent.schema.units import (
    supported_unit_spellings,
    unit_definition,
)


def canonical_scientific_decimal(value: str | int | float | Decimal) -> str:
    """Return one exact, non-lossy scientific-notation decimal spelling."""

    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("parameter value must be a finite decimal") from error
    if not parsed.is_finite():
        raise ValueError("parameter value must be a finite decimal")
    if parsed.is_zero():
        return "0e+0"
    sign, raw_digits, exponent = parsed.as_tuple()
    digits = list(raw_digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    adjusted = exponent + len(digits) - 1
    mantissa = str(digits[0])
    if len(digits) > 1:
        mantissa += "." + "".join(str(item) for item in digits[1:])
    return f"{'-' if sign else ''}{mantissa}e{adjusted:+d}"


def _validate_scientific_decimal(value: str) -> str:
    canonical_scientific_decimal(value)
    return value


ScientificDecimal = Annotated[
    str,
    Field(
        min_length=4,
        max_length=256,
        pattern=r"^-?(?:0|[1-9])(?:\.[0-9]+)?e[+-](?:0|[1-9][0-9]*)$",
        description=(
            "Finite scientific-notation decimal string; trailing mantissa "
            "zeros are permitted."
        ),
    ),
    AfterValidator(_validate_scientific_decimal),
]
UnitName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        json_schema_extra={"enum": list(supported_unit_spellings())},
    ),
]

ParameterCategory = Literal[
    "geometry",
    "material",
    "composition",
    "doping",
    "process",
    "physics_model",
    "contact_boundary",
    "initial_condition",
]
ParameterCoverageStatus = Literal[
    "confirmed",
    "authoritative_single",
    "single_source",
    "not_comparable",
    "conflict",
    "missing",
    "assumed",
]


class ParameterCondition(SchemaModel):
    name: Identifier
    value: str = Field(min_length=1, max_length=1024)
    unit: UnitName | None = None

    @model_validator(mode="after")
    def _numeric_condition_uses_scientific_notation(self) -> ParameterCondition:
        if self.unit is not None:
            _validate_scientific_decimal(self.value)
            unit_definition(self.unit, label="parameter condition unit")
        return self


class ParameterAgreementRule(SchemaModel):
    kind: Literal["exact", "absolute_tolerance", "relative_tolerance"]
    tolerance: ScientificDecimal | None = None

    @model_validator(mode="after")
    def _tolerance_matches_rule(self) -> ParameterAgreementRule:
        if self.kind == "exact" and self.tolerance is not None:
            raise ValueError("exact parameter agreement cannot declare tolerance")
        if self.kind != "exact" and self.tolerance is None:
            raise ValueError("tolerant parameter agreement requires tolerance")
        if self.tolerance is not None and Decimal(self.tolerance) < 0:
            raise ValueError("parameter agreement tolerance must be nonnegative")
        return self


class DeviceParameterRequirement(SchemaModel):
    parameter_key: Identifier
    display_name: str = Field(min_length=1, max_length=512)
    category: ParameterCategory
    device_scope: str = Field(min_length=1, max_length=1024)
    material: str | None = Field(default=None, min_length=1, max_length=512)
    canonical_unit: UnitName
    criticality: Literal["required", "recommended", "optional"] = "required"
    minimum_independent_sources: int = Field(default=2, ge=1, le=8)
    allow_authoritative_single: bool = True
    assumption_policy: Literal[
        "forbidden", "review_only_bounded_tuning"
    ] = "forbidden"
    agreement_rule: ParameterAgreementRule
    required_condition_names: tuple[Identifier, ...] = Field(
        default=(), max_length=32
    )

    @model_validator(mode="after")
    def _requirement_is_valid(self) -> DeviceParameterRequirement:
        unit_definition(self.canonical_unit, label="parameter canonical unit")
        if len(self.required_condition_names) != len(
            set(self.required_condition_names)
        ):
            raise ValueError("parameter required condition names must be unique")
        return self


class DeviceParameterRequirementSet(SchemaModel):
    requirement_set_key: Identifier
    title: str = Field(min_length=1, max_length=2048)
    device_key: Identifier
    objective: str = Field(min_length=1, max_length=8192)
    parameters: tuple[DeviceParameterRequirement, ...] = Field(
        min_length=1, max_length=512
    )

    @model_validator(mode="after")
    def _parameter_keys_are_unique(self) -> DeviceParameterRequirementSet:
        keys = tuple(item.parameter_key for item in self.parameters)
        if len(keys) != len(set(keys)):
            raise ValueError("device parameter requirement keys must be unique")
        return self


class EvidenceSourceCatalogEntry(SchemaModel):
    source_key: Identifier
    source_type: SourceType
    title: str = Field(min_length=1, max_length=2048)
    source_class: Literal[
        "primary_paper",
        "secondary_paper",
        "authoritative_database",
        "standard",
        "manufacturer_datasheet",
        "user_source",
        "runtime_source",
    ]
    work_key: str = Field(min_length=1, max_length=1024)
    doi: str | None = Field(default=None, min_length=3, max_length=512)
    authors: tuple[str, ...] = Field(default=(), max_length=64)
    publication_year: int | None = Field(default=None, ge=1000, le=9999)
    original_url: str | None = Field(default=None, min_length=1, max_length=4096)
    final_url: str | None = Field(default=None, min_length=1, max_length=4096)
    accessed_at: UtcRfc3339 | None = None

    @model_validator(mode="after")
    def _source_identity_is_consistent(self) -> EvidenceSourceCatalogEntry:
        if self.doi is not None:
            normalized = self.doi.lower().removeprefix("https://doi.org/")
            if self.work_key != f"doi:{normalized}":
                raise ValueError("DOI source work_key must use its normalized DOI")
        if self.source_type == "web_snapshot" and any(
            item is None
            for item in (self.original_url, self.final_url, self.accessed_at)
        ):
            raise ValueError("web source catalog entry requires exact URL metadata")
        for label, value in (
            ("original", self.original_url),
            ("final", self.final_url),
        ):
            if value is None:
                continue
            try:
                parsed = urlsplit(value)
            except ValueError as error:
                raise ValueError(f"source {label} URL is invalid") from error
            if (
                parsed.scheme.lower() != "https"
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError(
                    f"source {label} URL must be an authenticated-free HTTPS URL"
                )
        if len(self.authors) != len(set(self.authors)):
            raise ValueError("source authors must be unique")
        return self


class EvidenceSourceCatalog(SchemaModel):
    catalog_key: Identifier
    sources: tuple[EvidenceSourceCatalogEntry, ...] = Field(
        default=(), max_length=512
    )

    @model_validator(mode="after")
    def _source_keys_are_unique(self) -> EvidenceSourceCatalog:
        keys = tuple(item.source_key for item in self.sources)
        if len(keys) != len(set(keys)):
            raise ValueError("evidence source catalog keys must be unique")
        return self


class DeviceParameterObservation(SchemaModel):
    source_key: Identifier
    reported_value: ScientificDecimal
    reported_unit: UnitName
    conditions: tuple[ParameterCondition, ...] = Field(default=(), max_length=32)
    locator: str = Field(min_length=1, max_length=4096)
    evidence_mode: Literal[
        "direct_measurement",
        "direct_report",
        "authoritative_database",
        "derived",
    ]

    @model_validator(mode="after")
    def _observation_is_valid(self) -> DeviceParameterObservation:
        unit_definition(self.reported_unit, label="reported parameter unit")
        names = tuple(item.name for item in self.conditions)
        if len(names) != len(set(names)):
            raise ValueError("parameter observation condition names must be unique")
        return self


class DeviceParameterTuningSpec(SchemaModel):
    """Reviewed discrete alternatives that may be mapped into experiment cases."""

    purpose: Literal["uncertainty_sweep", "calibration"]
    basis: Literal["conflicting_sources", "engineering_prior", "human_review"]
    candidate_values: tuple[ScientificDecimal, ...] = Field(
        min_length=2, max_length=64
    )
    rationale: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def _candidate_values_are_numerically_unique(
        self,
    ) -> DeviceParameterTuningSpec:
        if len({Decimal(item) for item in self.candidate_values}) != len(
            self.candidate_values
        ):
            raise ValueError(
                "parameter tuning candidate values must be numerically unique"
            )
        return self


class DeviceParameterClaim(SchemaModel):
    parameter_key: Identifier
    selected_value: ScientificDecimal
    unit: UnitName
    conditions: tuple[ParameterCondition, ...] = Field(default=(), max_length=32)
    epistemic_status: Literal["paper_fact", "user_defined", "assumption"]
    observations: tuple[DeviceParameterObservation, ...] = Field(
        default=(), max_length=64
    )
    selection_rationale: str = Field(min_length=1, max_length=4096)
    tuning: DeviceParameterTuningSpec | None = None

    @model_validator(mode="after")
    def _claim_is_valid(self) -> DeviceParameterClaim:
        unit_definition(self.unit, label="selected parameter unit")
        names = tuple(item.name for item in self.conditions)
        if len(names) != len(set(names)):
            raise ValueError("parameter claim condition names must be unique")
        if self.epistemic_status == "paper_fact" and not self.observations:
            raise ValueError("paper parameter claim requires source observations")
        if self.tuning is None:
            return self
        candidates = {Decimal(item) for item in self.tuning.candidate_values}
        if Decimal(self.selected_value) not in candidates:
            raise ValueError(
                "parameter tuning candidate values must include the selected baseline"
            )
        if (
            self.tuning.basis == "engineering_prior"
            and self.epistemic_status != "assumption"
        ):
            raise ValueError(
                "engineering-prior tuning must be declared as an assumption"
            )
        if self.tuning.basis == "conflicting_sources":
            if len(self.observations) < 2:
                raise ValueError(
                    "conflicting-source tuning requires at least two observations"
                )
            observed = {
                _decimal_in_unit(item.reported_value, item.reported_unit, self.unit)
                for item in self.observations
            }
            if not candidates.issubset(observed):
                raise ValueError(
                    "conflicting-source tuning candidates must be exact observed values"
                )
        return self


class DeviceParameterSet(SchemaModel):
    parameter_set_key: Identifier
    requirement_set_key: Identifier
    title: str = Field(min_length=1, max_length=2048)
    objective: str = Field(min_length=1, max_length=8192)
    claims: tuple[DeviceParameterClaim, ...] = Field(default=(), max_length=512)

    @model_validator(mode="after")
    def _claim_keys_are_unique(self) -> DeviceParameterSet:
        keys = tuple(item.parameter_key for item in self.claims)
        if len(keys) != len(set(keys)):
            raise ValueError("device parameter claim keys must be unique")
        return self


class ParameterSourceComparison(SchemaModel):
    source_key: Identifier
    work_key: str = Field(min_length=1, max_length=1024)
    normalized_value: ScientificDecimal
    unit: str = Field(min_length=1, max_length=128)
    comparable: bool
    agrees: bool | None = None
    reason: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def _agreement_requires_comparability(self) -> ParameterSourceComparison:
        if self.comparable != (self.agrees is not None):
            raise ValueError("parameter source agreement requires comparability")
        return self


class DeviceParameterCoverageItem(SchemaModel):
    parameter_key: Identifier
    status: ParameterCoverageStatus
    selected_value: ScientificDecimal | None = None
    canonical_unit: str = Field(min_length=1, max_length=128)
    independent_source_count: int = Field(ge=0, le=512)
    comparisons: tuple[ParameterSourceComparison, ...] = Field(
        default=(), max_length=64
    )
    summary: str = Field(min_length=1, max_length=4096)


class DeviceParameterCoverageReport(SchemaModel):
    requirement_set_key: Identifier
    parameter_set_key: Identifier
    source_catalog_key: Identifier
    status: Literal["pass", "review_required", "fail"]
    items: tuple[DeviceParameterCoverageItem, ...] = Field(
        min_length=1, max_length=512
    )
    confirmed_count: int = Field(ge=0, le=512)
    review_count: int = Field(ge=0, le=512)
    blocking_count: int = Field(ge=0, le=512)


ParameterUncertaintyClass = Literal[
    "fixed", "bounded_tunable", "blocking_unbounded", "deferred_unused"
]


class ParameterUncertaintyItem(SchemaModel):
    parameter_key: Identifier
    classification: ParameterUncertaintyClass
    selected_value: ScientificDecimal | None = None
    canonical_unit: str = Field(min_length=1, max_length=128)
    candidate_values: tuple[ScientificDecimal, ...] = Field(
        default=(), max_length=64
    )
    rationale: str = Field(min_length=1, max_length=2048)

    @model_validator(mode="after")
    def _classification_has_exact_values(self) -> ParameterUncertaintyItem:
        if self.classification == "bounded_tunable":
            if self.selected_value is None or len(self.candidate_values) < 2:
                raise ValueError(
                    "bounded parameter uncertainty requires a baseline and candidates"
                )
        elif self.candidate_values:
            raise ValueError(
                "only bounded parameter uncertainty may declare candidates"
            )
        return self


class ParameterUncertaintyProjection(SchemaModel):
    requirement_set_key: Identifier
    parameter_set_key: Identifier
    status: Literal["ready", "blocking_unbounded"]
    items: tuple[ParameterUncertaintyItem, ...] = Field(
        min_length=1, max_length=512
    )

    @model_validator(mode="after")
    def _projection_is_consistent(self) -> ParameterUncertaintyProjection:
        keys = tuple(item.parameter_key for item in self.items)
        if len(keys) != len(set(keys)):
            raise ValueError("parameter uncertainty keys must be unique")
        has_blocker = any(
            item.classification == "blocking_unbounded" for item in self.items
        )
        if (self.status == "blocking_unbounded") != has_blocker:
            raise ValueError("parameter uncertainty status differs from its items")
        return self


def _decimal_in_unit(value: str, source_unit: str, target_unit: str) -> Decimal:
    source = unit_definition(source_unit, label="reported parameter unit")
    target = unit_definition(target_unit, label="parameter canonical unit")
    if source.dimension != target.dimension:
        raise ValueError(
            f"incompatible parameter units: {source_unit} and {target_unit}"
        )
    parsed = Decimal(value)
    si_value = parsed * Decimal(str(source.scale_to_si)) + Decimal(
        str(source.offset_to_si)
    )
    return (si_value - Decimal(str(target.offset_to_si))) / Decimal(
        str(target.scale_to_si)
    )


def _conditions_match(
    required_names: tuple[str, ...],
    selected: tuple[ParameterCondition, ...],
    observed: tuple[ParameterCondition, ...],
) -> bool:
    selected_by_name = {item.name: item for item in selected}
    observed_by_name = {item.name: item for item in observed}
    for name in required_names:
        left = selected_by_name.get(name)
        right = observed_by_name.get(name)
        if left is None or right is None:
            return False
        if left.unit is None or right.unit is None:
            if (left.value, left.unit) != (right.value, right.unit):
                return False
            continue
        try:
            converted = _decimal_in_unit(right.value, right.unit, left.unit)
        except ValueError:
            return False
        if converted != Decimal(left.value):
            return False
    return True


def _agrees(
    observed: Decimal,
    selected: Decimal,
    rule: ParameterAgreementRule,
) -> bool:
    difference = abs(observed - selected)
    if rule.kind == "exact":
        return difference == 0
    assert rule.tolerance is not None
    tolerance = Decimal(rule.tolerance)
    if rule.kind == "absolute_tolerance":
        return difference <= tolerance
    if selected == 0:
        return difference == 0
    return difference / abs(selected) <= tolerance


def evaluate_device_parameter_coverage(
    requirements: DeviceParameterRequirementSet,
    parameters: DeviceParameterSet,
    catalog: EvidenceSourceCatalog,
) -> DeviceParameterCoverageReport:
    """Compare exact reported values without performing scientific selection."""

    if parameters.requirement_set_key != requirements.requirement_set_key:
        raise ValueError("device parameter set targets a different requirement set")
    requirement_by_key = {
        item.parameter_key: item for item in requirements.parameters
    }
    claims = {item.parameter_key: item for item in parameters.claims}
    unknown = set(claims) - set(requirement_by_key)
    if unknown:
        raise ValueError(
            "device parameter set contains unknown requirements: "
            + ", ".join(sorted(unknown))
        )
    sources = {item.source_key: item for item in catalog.sources}
    items: list[DeviceParameterCoverageItem] = []
    blocking = 0
    review = 0
    confirmed = 0
    for requirement in requirements.parameters:
        claim = claims.get(requirement.parameter_key)
        if claim is None:
            status: ParameterCoverageStatus = "missing"
            if requirement.criticality == "required":
                blocking += 1
            elif requirement.criticality == "recommended":
                review += 1
            items.append(
                DeviceParameterCoverageItem(
                    parameter_key=requirement.parameter_key,
                    status=status,
                    canonical_unit=requirement.canonical_unit,
                    independent_source_count=0,
                    summary="No parameter claim covers this requirement.",
                )
            )
            continue
        selected = _decimal_in_unit(
            claim.selected_value, claim.unit, requirement.canonical_unit
        )
        if not set(requirement.required_condition_names).issubset(
            {item.name for item in claim.conditions}
        ):
            status = "not_comparable"
            comparisons: list[ParameterSourceComparison] = []
            independent_count = 0
        elif claim.epistemic_status == "assumption":
            status = "assumed"
            comparisons = []
            independent_count = 0
        else:
            comparisons = []
            independent_works: set[str] = set()
            authoritative_works: set[str] = set()
            any_disagreement = False
            comparable_count = 0
            for observation in claim.observations:
                try:
                    source = sources[observation.source_key]
                except KeyError as error:
                    raise ValueError(
                        "parameter observation references an unknown source"
                    ) from error
                normalized = _decimal_in_unit(
                    observation.reported_value,
                    observation.reported_unit,
                    requirement.canonical_unit,
                )
                comparable = _conditions_match(
                    requirement.required_condition_names,
                    claim.conditions,
                    observation.conditions,
                )
                agrees = (
                    _agrees(normalized, selected, requirement.agreement_rule)
                    if comparable
                    else None
                )
                if comparable:
                    comparable_count += 1
                    independent_works.add(source.work_key)
                    if source.source_class in {
                        "authoritative_database",
                        "standard",
                    }:
                        authoritative_works.add(source.work_key)
                    any_disagreement = any_disagreement or agrees is False
                comparisons.append(
                    ParameterSourceComparison(
                        source_key=observation.source_key,
                        work_key=source.work_key,
                        normalized_value=canonical_scientific_decimal(normalized),
                        unit=requirement.canonical_unit,
                        comparable=comparable,
                        agrees=agrees,
                        reason=(
                            "Source value agrees with the selected value."
                            if agrees is True
                            else "Source value conflicts with the selected value."
                            if agrees is False
                            else "Source conditions do not match the selected conditions."
                        ),
                    )
                )
            independent_count = len(independent_works)
            if comparable_count == 0:
                status = "not_comparable"
            elif any_disagreement:
                status = "conflict"
            elif independent_count >= requirement.minimum_independent_sources:
                status = "confirmed"
            elif requirement.allow_authoritative_single and authoritative_works:
                status = "authoritative_single"
            else:
                status = "single_source"
        tuning_requires_review = claim.tuning is not None and status in {
            "confirmed",
            "authoritative_single",
        }
        if status == "confirmed":
            confirmed += 1
        elif status in {"single_source", "assumed"}:
            review += 1
        elif status in {"conflict", "not_comparable", "missing"}:
            reviewable_conflict = (
                status == "conflict"
                and claim.tuning is not None
                and claim.tuning.basis == "conflicting_sources"
            )
            if requirement.criticality == "required" and not reviewable_conflict:
                blocking += 1
            else:
                review += 1
        if tuning_requires_review:
            review += 1
        tuning_summary = (
            " Structured tuning candidates require human review."
            if claim.tuning is not None
            else ""
        )
        items.append(
            DeviceParameterCoverageItem(
                parameter_key=requirement.parameter_key,
                status=status,
                selected_value=canonical_scientific_decimal(selected),
                canonical_unit=requirement.canonical_unit,
                independent_source_count=independent_count,
                comparisons=tuple(comparisons),
                summary=(
                    f"Parameter coverage status is {status} with "
                    f"{independent_count} independent comparable source(s)."
                    f"{tuning_summary}"
                ),
            )
        )
    overall = "fail" if blocking else "review_required" if review else "pass"
    return DeviceParameterCoverageReport(
        requirement_set_key=requirements.requirement_set_key,
        parameter_set_key=parameters.parameter_set_key,
        source_catalog_key=catalog.catalog_key,
        status=overall,
        items=tuple(items),
        confirmed_count=confirmed,
        review_count=review,
        blocking_count=blocking,
    )


def project_parameter_uncertainty(
    requirements: DeviceParameterRequirementSet,
    parameters: DeviceParameterSet,
    coverage: DeviceParameterCoverageReport,
) -> ParameterUncertaintyProjection:
    """Project reviewed parameter evidence into one deterministic use gate."""

    if parameters.requirement_set_key != requirements.requirement_set_key:
        raise ValueError("device parameter set targets a different requirement set")
    if (
        coverage.requirement_set_key != requirements.requirement_set_key
        or coverage.parameter_set_key != parameters.parameter_set_key
    ):
        raise ValueError("parameter coverage targets a different parameter set")
    requirement_by_key = {
        item.parameter_key: item for item in requirements.parameters
    }
    claim_by_key = {item.parameter_key: item for item in parameters.claims}
    coverage_by_key = {item.parameter_key: item for item in coverage.items}
    if set(claim_by_key) - set(requirement_by_key):
        raise ValueError("parameter set contains an unknown requirement")
    if set(coverage_by_key) != set(requirement_by_key):
        raise ValueError("parameter coverage does not exactly cover requirements")

    items: list[ParameterUncertaintyItem] = []
    for requirement in requirements.parameters:
        claim = claim_by_key.get(requirement.parameter_key)
        covered = coverage_by_key[requirement.parameter_key]
        if covered.canonical_unit != requirement.canonical_unit:
            raise ValueError("parameter coverage canonical unit differs")
        if claim is None:
            classification: ParameterUncertaintyClass = (
                "blocking_unbounded"
                if requirement.criticality == "required"
                else "deferred_unused"
            )
            items.append(
                ParameterUncertaintyItem(
                    parameter_key=requirement.parameter_key,
                    classification=classification,
                    canonical_unit=requirement.canonical_unit,
                    rationale=(
                        "A required parameter has no selected bounded value."
                        if classification == "blocking_unbounded"
                        else "The absent non-required parameter is not used downstream."
                    ),
                )
            )
            continue

        selected = canonical_scientific_decimal(
            _decimal_in_unit(
                claim.selected_value, claim.unit, requirement.canonical_unit
            )
        )
        tuning_allowed = (
            claim.tuning is not None
            and requirement.assumption_policy == "review_only_bounded_tuning"
        )
        if tuning_allowed:
            assert claim.tuning is not None
            candidates = tuple(
                canonical_scientific_decimal(
                    _decimal_in_unit(value, claim.unit, requirement.canonical_unit)
                )
                for value in claim.tuning.candidate_values
            )
            items.append(
                ParameterUncertaintyItem(
                    parameter_key=requirement.parameter_key,
                    classification="bounded_tunable",
                    selected_value=selected,
                    canonical_unit=requirement.canonical_unit,
                    candidate_values=candidates,
                    rationale=(
                        "The exact requirement permits the reviewed discrete tuning set."
                    ),
                )
            )
            continue

        fixed = (
            claim.tuning is None
            and claim.epistemic_status != "assumption"
            and covered.status
            in {"confirmed", "authoritative_single", "single_source"}
        )
        items.append(
            ParameterUncertaintyItem(
                parameter_key=requirement.parameter_key,
                classification="fixed" if fixed else "blocking_unbounded",
                selected_value=selected,
                canonical_unit=requirement.canonical_unit,
                rationale=(
                    "The selected value is fixed by the reviewed evidence set."
                    if fixed
                    else (
                        "A tuning declaration is not permitted by its exact requirement."
                        if claim.tuning is not None
                        else "The selected value remains unresolved or assumed."
                    )
                ),
            )
        )

    result = tuple(items)
    return ParameterUncertaintyProjection(
        requirement_set_key=requirements.requirement_set_key,
        parameter_set_key=parameters.parameter_set_key,
        status=(
            "blocking_unbounded"
            if any(item.classification == "blocking_unbounded" for item in result)
            else "ready"
        ),
        items=result,
    )


def validate_device_parameter_requirement_set(
    value: dict[str, object],
) -> dict[str, object]:
    return DeviceParameterRequirementSet.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def validate_device_parameter_set(value: dict[str, object]) -> dict[str, object]:
    return DeviceParameterSet.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


def validate_evidence_source_catalog(value: dict[str, object]) -> dict[str, object]:
    return EvidenceSourceCatalog.model_validate_json(
        canonical_json(value), strict=True
    ).model_dump(mode="json")


__all__ = [
    "DeviceParameterClaim",
    "DeviceParameterCoverageItem",
    "DeviceParameterCoverageReport",
    "DeviceParameterObservation",
    "DeviceParameterRequirement",
    "DeviceParameterRequirementSet",
    "DeviceParameterSet",
    "DeviceParameterTuningSpec",
    "EvidenceSourceCatalog",
    "EvidenceSourceCatalogEntry",
    "ParameterAgreementRule",
    "ParameterCondition",
    "ParameterCoverageStatus",
    "ParameterSourceComparison",
    "ScientificDecimal",
    "canonical_scientific_decimal",
    "evaluate_device_parameter_coverage",
    "validate_device_parameter_requirement_set",
    "validate_device_parameter_set",
    "validate_evidence_source_catalog",
]
