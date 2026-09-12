"""Components for domain-neutral experiment Operations.

This module owns executable components and resources only.  Operation
declarations live in ``general_science_experiment_operations`` so plugin
registration remains a single, explicit composition step.
"""

from __future__ import annotations

from scidiscovery.operations.input_validation import parse_bound_json

from .operations.input_validation import OperationInvocationError

from collections.abc import Mapping
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from .artifact_agent.schema.common import canonical_json
from .artifact_agent.schema.cognitive import CriticReview
from .artifact_agent.schema.experiment import ExperimentPortfolio, validate_experiment_portfolio
from .artifact_agent.schema.execution_context import ExecutionContext
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

EXPERIMENT_PROMPT = """Deliver the implementation information needed by the current task in the plan:
values and units, or a reproducible derivation with all required operands and evidence.
Do not assign an unbound source-table audit to an author or make later analysis a
blanket implementation gate. Do not perform all missing research yourself: defer,
narrow, change a supported method, or report infeasibility with reasons. A revision
must substantively address the gap, not rename it or transfer it to another role.
Return exactly one RoleResultEnvelope whose payload is
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
For each proposal preserve the complete objectives and select a nonempty exact
current_objectives subset. A complete ExperimentPortfolio must include its exact
overall objective in every proposal's objectives. Expand only this round's
current objectives into cases, variables, observables, resources, and validation;
do not put placeholders for future work into execution fields. In
value_assessment.rationale explain coverage, deferred objectives, minimality,
and the conditions for later work; use priority_rationale to explain this round's
selection order. Explain any changed objective selection in a complete revision.
Independently judge whether uncovered original targets undermine the current
experiment's validity, identifiability, or allowed claims. Deferral alone is not
a mechanical blocker: state the scientific consequence and remaining conditions.
When progress, results, or analysis are supplied, use their exact visible content
to justify the selection and distinguish numerical failure from missing evidence.
These feedback inputs are optional; if absent, limit the corresponding claims
and never imply that prior results have been checked.
"""

EXPERIMENT_DESIGN_PROMPT = EXPERIMENT_PROMPT + """When execution_context is
bound, read that immutable input and justify the design's feasibility only from
its explicit implementation kind, backend, release label, public arguments,
capability statements, and limitations. Treat it as declared capability data,
not permission to execute tools. If it is absent or does not declare a required
capability, state that unresolved feasibility condition in the existing
resource judgment and handoff; do not invent execution support.
Choose an installed Skill whose description matches the task and execution
context. Skills explain methods, while execution_context declares environment
support. If a required Skill is unavailable, record that feasibility gap in the
resource judgment and handoff.
"""

OBJECT_REVIEW_PROMPT = """Independently assess task deliverability from the inputs actually handed downstream.
If a necessary implementation input or supported method is missing, request correction;
do not PASS while transferring that unresolved obligation to the author. Ordinary
later initialization, numerical checks and execution approval remain later actions.
Return exactly one RoleResultEnvelope whose payload is
the ScientificReview required by output.schema.json. Independently review the
complete supplied experiment plan without mutating it. The verdict is a
scientific assessment, not human approval or qualification. Report the
smallest bounded correction for each material defect.
Compare the complete objectives, current_objectives, cases, validation, resource
judgment, value_assessment.rationale, and priority_rationale. When an original
research_objective is supplied, independently assess its mandatory_targets and
closure_requirements against the current selection and deferred work; do not
infer the original contract from the plan's own description. Judge whether
uncovered targets affect this experiment's validity, identifiability, or allowed
claims, and state the conditions for later work. Partial coverage alone does not
force a negative verdict. When execution_context or feedback is supplied, assess
feasibility and the stated selection using those exact inputs. These inputs are
optional: if absent, limit the affected conclusions and do not claim independent
verification. Cite only actual visible input aliases in evidence.source_key,
including experiment_plan; never cite an unbound original or feedback item.
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


def _experiment_inputs(sources: dict[str, bytes]) -> None:
    from .artifact_agent.schema.experiment import validate_experiment_input_objective
    try:
        validate_experiment_input_objective(sources)
    except ValueError as error:
        raise OperationInvocationError("input_hypothesis_objective_mismatch", port="hypothesis_portfolio") from error
    execution_context = sources.get("execution_context")
    if execution_context is not None:
        parse_bound_json(ExecutionContext, execution_context, admission_port="execution_context")
    critic = parse_bound_json(CriticReview, sources["critic_review"], admission_port="critic_review")
    if critic.disposition not in {
        "ready_for_experiment",
        "design_model_counterfactual",
    }:
        raise OperationInvocationError("input_critic_disposition_invalid", port="critic_review")


def _experiment_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    validate_experiment_design_intent_task_output(payload, sources, handoff)


def _experiment_revision_inputs(sources: dict[str, bytes]) -> None:
    review = parse_bound_json(ScientificReview, sources["change_request"], admission_port="change_request")
    if review.review_target != "experiment_portfolio":
        raise OperationInvocationError("input_review_target_invalid", port="change_request", field="/review_target")


def _experiment_revision_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    del handoff
    revised = ExperimentPortfolio.model_validate_json(
        canonical_json(payload), strict=True
    )
    prior = parse_bound_json(ExperimentPortfolio, sources["prior_draft"])
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


def _object_review_inputs(sources: dict[str, bytes]) -> None:
    plan = parse_bound_json(ExperimentPortfolio, sources["experiment_plan"], admission_port="experiment_plan")
    raw_objective = sources.get("research_objective")
    if raw_objective is not None:
        objective = parse_bound_json(ResearchObjectiveContract, raw_objective,
                                     admission_port="research_objective")
        if (
            plan.objective_key != objective.objective_key
            or plan.objective != objective.statement
        ):
            raise OperationInvocationError("input_plan_objective_mismatch", port="research_objective")
    execution_context = sources.get("execution_context")
    if execution_context is not None:
        parse_bound_json(ExecutionContext, execution_context, admission_port="execution_context")


def _object_review_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    review = ScientificReview.model_validate_json(canonical_json(payload), strict=True)
    if review.review_target != "experiment_portfolio":
        raise SemanticRuleViolation("scientific review target differs from the bound object")
    expected_verdict = "blocked" if review.verdict == "reject" else review.verdict
    if handoff.get("verdict") != expected_verdict:
        raise SemanticRuleViolation("review handoff verdict differs from payload verdict")
    if any(item.source_key not in sources for item in review.evidence):
        raise SemanticRuleViolation(
            "review evidence source_key must name an actual visible input alias"
        )


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
    execution_context_schema = schema_resource(
        ExecutionContext, "scidiscovery.execution-context.v1"
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
            "form one internally closed design intent. Each proposal declares "
            "nonempty objectives and a nonempty exact current_objectives subset; "
            "only this round's goals expand into executable cases and validation. "
            "value_assessment.rationale explains coverage, deferral, minimality and "
            "later conditions; priority_rationale explains the current ordering."
            " The designer chooses the experiment shape; study_kind does not impose "
            "a minimum case count, comparison design, or fixed validation dimensions."
        ),
        context_constraint=(
            "The objective key and selected hypothesis keys must match the exact "
            "objective, portfolio, and critic review inputs. When an optional "
            "execution context is bound, it must match its declared strict schema. "
            "The Agent judges the effect of uncovered original targets on current "
            "validity, identifiability and claims; full target coverage is not a "
            "per-round mechanical requirement. Optional feedback supports only "
            "conclusions justified by its actual supplied content."
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
            "threshold units, and priority order must remain mutually consistent. "
            "Every proposal's objectives include the exact overall objective "
            "and its nonempty current_objectives are an exact subset. "
            "Explain selection changes, coverage, deferral, minimality and later "
            "conditions in value_assessment.rationale and priority_rationale; expand "
            "only current goals into cases and validation. A comparison may select "
            "a subset of declared cases, factors and observables; its own references, "
            "values and units must remain valid."
            " Scientific and engineering labels do not prescribe case counts or validation dimensions."
        ),
        context_constraint=(
            "The complete replacement must preserve the prior experiment identity "
            "and answer the exact review whose target is experiment_portfolio. "
            "The Agent judges how uncovered targets affect the current experiment; "
            "objective selection is not permanently frozen and missing optional "
            "feedback limits conclusions rather than preventing submission."
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
            "The review must assess the exact supplied experiment without mutating it. "
            "If research_objective is supplied, its key and statement must match "
            "the plan. If execution_context is supplied, parse its strict schema. "
            "Every evidence.source_key must name an actual visible input alias, "
            "including actual collection aliases. Independently assess original "
            "mandatory targets and closure, current selection, deferral, feasibility "
            "and supplied feedback; judge how uncovered targets affect current "
            "validity, identifiability and claims. Optional absent inputs limit "
            "conclusions without imposing a hidden submission requirement."
        ),
        payload_rule_id="experiment.review.verdict_consistency",
        context_rule_id="experiment.review.subject_binding",
    )
    experiment_prompt = OPERATION_AGENT_PREAMBLE + EXPERIMENT_PROMPT
    experiment_design_prompt = OPERATION_AGENT_PREAMBLE + EXPERIMENT_DESIGN_PROMPT
    object_review_prompt = OPERATION_AGENT_PREAMBLE + OBJECT_REVIEW_PROMPT


class ExperimentComponents:
    experiment_inputs = CallableComponent("validator", _experiment_inputs)
    experiment_revision_inputs = CallableComponent("validator", _experiment_revision_inputs)
    object_review_inputs = CallableComponent("validator", _object_review_inputs)
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
        "experiment_inputs", "experiment_revision_inputs", "object_review_inputs",
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
                    else "input-boundary-r4:v1"
                    if name in {"experiment_context", "experiment_revision_context", "object_review_context"}
                    else None
                ),
                public=False,
            )
        )
    public_resources = {
        "execution_context_schema",
        "experiment_portfolio_schema",
        "research_objective_schema",
        "scientific_review_schema",
    }
    for name in (
        "research_objective_schema",
        "experiment_intent_schema",
        "execution_context_schema",
        "experiment_portfolio_schema",
        "scientific_review_schema",
        "materialization_report_schema",
        "experiment_design_semantic_contract",
        "experiment_revision_semantic_contract",
        "scientific_review_semantic_contract",
        "experiment_prompt",
        "experiment_design_prompt",
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
