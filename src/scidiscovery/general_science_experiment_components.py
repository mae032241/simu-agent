"""Components for domain-neutral experiment Operations.

This module owns executable components and resources only.  Operation
declarations live in ``general_science_experiment_operations`` so plugin
registration remains a single, explicit composition step.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .artifact_agent.schema.common import canonical_json
from .artifact_agent.schema.cognitive import CriticReview
from .artifact_agent.schema.experiment import ExperimentPortfolio, validate_experiment_portfolio
from .artifact_agent.schema.experiment_intent import (
    ExperimentDesignIntent,
    ExperimentPlanMaterializationReport,
    validate_experiment_design_intent,
    validate_experiment_design_intent_task_output,
)
from .artifact_agent.schema.research_cycle import (
    ScientificReview,
    validate_scientific_review,
)
from .artifact_agent.schema.research_objective import ResearchObjectiveContract
from .artifact_agent.transforms import (
    materialize_experiment_plan,
    project_research_objective,
)
from .operation_declaration import (
    OPERATION_AGENT_PREAMBLE,
    RequiredParentage,
    payload_validator,
    schema_resource,
    scientific_semantic_contract,
)
from .operation_contract import SemanticRuleViolation
from .operations.spec import (
    CallableComponent,
    ComponentRef,
    ComponentSpec,
)

EXPERIMENT_PROMPT = """Return exactly one RoleResultEnvelope whose payload is
the scientific object required by output.schema.json. Without prior_draft,
produce the compact ExperimentDesignIntent: select only reviewed hypotheses and
design the smallest bounded study that states controls, interventions,
observables, predictions, falsifiers, numerical decision criteria, extraction
or reduction algorithms, uncertainty propagation, resource judgment, and stop
conditions. When the critic requests a model counterfactual, define the bounded
variables, equations or model family, boundary conditions, outputs, and
decision rule needed by a registered domain implementation; do not implement or
execute the domain model yourself.
With prior_draft and change_request, output/result.json is a copy-on-write draft
of the exact prior ExperimentPortfolio. Edit only fields required by the bounded
review, complete its new handoff, and submit the entire revised object, not a
patch. Preserve supported fields; never inherit a verdict or invent candidates.
"""

OBJECT_REVIEW_PROMPT = """Return exactly one RoleResultEnvelope whose payload is
the ScientificReview required by output.schema.json. Independently review the
complete supplied experiment plan without mutating it. The verdict is a
scientific assessment, not human approval or qualification. Report the
smallest bounded correction for each material defect.
"""


def _agent_marker() -> None:
    return None


def _strict_validator(model: type[BaseModel]) -> Callable[[bytes], None]:
    def validate(raw: bytes) -> None:
        model.model_validate_json(raw, strict=True)

    return validate


_MATERIALIZATION_PARENTAGE = RequiredParentage(
    (
        ("experiment_design_intent", "scientific_foundation"),
        ("experiment_design_intent", "research_objective"),
        ("experiment_design_intent", "hypothesis_portfolio"),
        ("experiment_design_intent", "critic_review"),
        ("research_objective", "scientific_foundation"),
        ("hypothesis_portfolio", "scientific_foundation"),
        ("critic_review", "scientific_foundation"),
        ("critic_review", "hypothesis_portfolio"),
    )
)


def _materialization_lineage(inputs: tuple[Any, ...], parameters: Mapping[str, Any]) -> bool:
    if parameters:
        return False
    if not any(item.port_name == "scientific_foundation" for item in inputs):
        return True
    return _MATERIALIZATION_PARENTAGE(inputs, parameters)


def _experiment_portfolio_validator(raw: bytes) -> None:
    try:
        value = ExperimentPortfolio.model_validate_json(raw, strict=True)
        validate_experiment_portfolio(value.model_dump(mode="json"))
    except ValidationError as error:
        raise SemanticRuleViolation(str(error)) from error


def _experiment_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    critic = CriticReview.model_validate_json(sources["critic_review"], strict=True)
    if critic.disposition not in {
        "ready_for_experiment",
        "design_model_counterfactual",
    }:
        raise SemanticRuleViolation("critic review does not support experiment design")
    validate_experiment_design_intent_task_output(payload, sources, handoff)


def _experiment_revision_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    del handoff
    revised = ExperimentPortfolio.model_validate_json(
        canonical_json(payload), strict=True
    )
    prior = ExperimentPortfolio.model_validate_json(
        sources["prior_draft"], strict=True
    )
    review = ScientificReview.model_validate_json(
        sources["change_request"], strict=True
    )
    if review.review_target != "experiment_portfolio":
        raise SemanticRuleViolation("experiment revision requires an experiment portfolio review")
    if (
        revised.study_kind != prior.study_kind
        or revised.objective_key != prior.objective_key
        or revised.objective != prior.objective
        or set(revised.selected_hypothesis_keys)
        != set(prior.selected_hypothesis_keys)
        or {item.experiment_key for item in revised.proposals}
        != {item.experiment_key for item in prior.proposals}
    ):
        raise SemanticRuleViolation(
            "experiment revision cannot change the prior experiment identity"
        )


def _object_review_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    if "experiment_plan" not in sources:
        raise SemanticRuleViolation("review target is absent")
    review = ScientificReview.model_validate_json(canonical_json(payload), strict=True)
    if review.review_target != "experiment_portfolio":
        raise SemanticRuleViolation("scientific review target differs from the bound object")
    expected_verdict = "blocked" if review.verdict == "reject" else review.verdict
    if handoff.get("verdict") != expected_verdict:
        raise SemanticRuleViolation("review handoff verdict differs from payload verdict")


def _one(values: Mapping[str, tuple[bytes, ...]], name: str) -> bytes:
    items = values.get(name, ())
    if len(items) != 1:
        raise ValueError(f"transform input {name} must contain exactly one item")
    return items[0]


def _objective_project(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    if set(values) != {"scientific_foundation"}:
        raise ValueError("research objective projection requires scientific_foundation")
    return {
        "research_objective": (
            project_research_objective(_one(values, "scientific_foundation")),
        )
    }


def _experiment_materialize(
    values: Mapping[str, tuple[bytes, ...]],
) -> dict[str, tuple[bytes, ...]]:
    inputs = {
        name: _one(values, name)
        for name in values
        if name not in {"scientific_foundation", "critic_review"}
    }
    plan, report = materialize_experiment_plan(inputs)
    return {
        "experiment_plan": (plan,),
        "materialization_report": (report,),
    }


class ExperimentResources:
    research_objective_schema = schema_resource(
        ResearchObjectiveContract, "scidiscovery.research-objective.v1"
    )
    experiment_intent_schema = schema_resource(
        ExperimentDesignIntent, "scidiscovery.experiment-design-intent.v1"
    )
    experiment_portfolio_schema = schema_resource(
        ExperimentPortfolio, "scidiscovery.experiment-portfolio.v1"
    )
    scientific_review_schema = schema_resource(
        ScientificReview, "scidiscovery.scientific-review.v1"
    )
    materialization_report_schema = schema_resource(
        ExperimentPlanMaterializationReport,
        "scidiscovery.experiment-plan-materialization.v1",
    )
    experiment_design_semantic_contract = scientific_semantic_contract(
        "experiment.design",
        "Bind a new intent or complete revised plan to its exact scientific context.",
        "The intent selects only hypotheses from the bound portfolio and preserves the exact research objective.",
        required_inputs=(
            "research_objective",
            "hypothesis_portfolio",
            "critic_review",
        ),
        payload_constraint=(
            "Selected hypotheses, controls, interventions, observables, predictions, "
            "falsifiers, metrics, uncertainty, resources, and stop conditions must "
            "form one internally closed design intent."
        ),
        context_constraint=(
            "The objective key and selected hypothesis keys must match the exact "
            "objective, portfolio, and critic review inputs."
        ),
        payload_rule_id="experiment.design.intent_closure",
        context_rule_id="experiment.design.objective_and_hypothesis_binding",
    )
    experiment_revision_semantic_contract = scientific_semantic_contract(
        "experiment.revision",
        "A revision is a complete replacement object, never a patch or inherited verdict.",
        "Revise only the exact prior experiment in response to its bound independent review.",
        required_inputs=("prior_draft", "change_request"),
        payload_constraint=(
            "Study kind, objective and hypothesis keys, proposal keys, case settings, "
            "changed factors, intended comparison variables, validation plans, "
            "threshold units, and priority order must remain mutually consistent."
        ),
        context_constraint=(
            "The complete replacement must preserve the prior experiment identity "
            "and answer the exact review whose target is experiment_portfolio."
        ),
        payload_rule_id="experiment.revision.case_and_validation_closure",
        context_rule_id="experiment.revision.review_target",
    )
    scientific_review_semantic_contract = scientific_semantic_contract(
        "experiment.review",
        "Review the complete supplied experiment without mutating it.",
        "The review verdict is not a human approval decision.",
        required_inputs=("experiment_plan",),
        payload_constraint=(
            "Review target, verdict, issue severities, and disposition must form one "
            "internally consistent scientific review."
        ),
        context_constraint=(
            "The review must assess the exact supplied experiment without mutating it."
        ),
        payload_rule_id="experiment.review.verdict_consistency",
        context_rule_id="experiment.review.subject_binding",
    )
    experiment_prompt = OPERATION_AGENT_PREAMBLE + EXPERIMENT_PROMPT
    object_review_prompt = OPERATION_AGENT_PREAMBLE + OBJECT_REVIEW_PROMPT


class ExperimentComponents:
    experiment_validator = CallableComponent(
        "validator", payload_validator(validate_experiment_design_intent)
    )
    review_validator = CallableComponent(
        "validator", payload_validator(validate_scientific_review)
    )
    experiment_context = CallableComponent("validator", _experiment_context)
    experiment_revision_context = CallableComponent(
        "validator", _experiment_revision_context
    )
    object_review_context = CallableComponent("validator", _object_review_context)
    experiment_agent = CallableComponent("agent", _agent_marker)
    objective_project = CallableComponent("transform", _objective_project)
    experiment_materialize = CallableComponent("transform", _experiment_materialize)
    objective_validator = CallableComponent(
        "validator", _strict_validator(ResearchObjectiveContract)
    )
    experiment_portfolio_validator = CallableComponent(
        "validator", _experiment_portfolio_validator
    )
    materialization_report_validator = CallableComponent(
        "validator", _strict_validator(ExperimentPlanMaterializationReport)
    )
    experiment_science_cohort = CallableComponent(
        "guard",
        RequiredParentage(
            (
                ("research_objective", "scientific_foundation"),
                ("hypothesis_portfolio", "scientific_foundation"),
                ("critic_review", "scientific_foundation"),
                ("critic_review", "hypothesis_portfolio"),
            ),
        ),
    )
    experiment_lineage = CallableComponent(
        "guard",
        _materialization_lineage,
    )


def component_specs() -> tuple[ComponentSpec, ...]:
    values: list[ComponentSpec] = []
    semantic_resources = {
        "experiment_validator": ("experiment_design_semantic_contract",),
        "review_validator": ("scientific_review_semantic_contract",),
        "experiment_context": ("experiment_design_semantic_contract",),
        "experiment_revision_context": ("experiment_revision_semantic_contract",),
        "object_review_context": ("scientific_review_semantic_contract",),
        "experiment_portfolio_validator": ("experiment_revision_semantic_contract",),
    }
    for name in (
        "experiment_validator",
        "review_validator",
        "experiment_context",
        "experiment_revision_context",
        "object_review_context",
        "experiment_agent",
        "objective_project",
        "experiment_materialize",
        "objective_validator",
        "experiment_portfolio_validator",
        "materialization_report_validator",
        "experiment_science_cohort",
        "experiment_lineage",
    ):
        component = getattr(ExperimentComponents, name)
        values.append(
            ComponentSpec(
                name,
                component.kind,
                f"scidiscovery.general_science_experiment_components:ExperimentComponents.{name}",
                resources=tuple(
                    ComponentRef(resource)
                    for resource in semantic_resources.get(name, ())
                ),
                configuration_identity=(
                    f"general-experiment:{name}:v1"
                    if component.kind in {"transform", "guard"}
                    else None
                ),
                public=False,
            )
        )
    public_resources = {
        "experiment_portfolio_schema",
        "research_objective_schema",
        "scientific_review_schema",
    }
    for name in (
        "research_objective_schema",
        "experiment_intent_schema",
        "experiment_portfolio_schema",
        "scientific_review_schema",
        "materialization_report_schema",
        "experiment_design_semantic_contract",
        "experiment_revision_semantic_contract",
        "scientific_review_semantic_contract",
        "experiment_prompt",
        "object_review_prompt",
    ):
        values.append(
            ComponentSpec(
                name,
                "resource",
                f"scidiscovery.general_science_experiment_components:ExperimentResources.{name}",
                public=name in public_resources,
            )
        )
    return tuple(values)


COMPONENTS = component_specs()

__all__ = ["COMPONENTS", "ExperimentComponents", "ExperimentResources"]
