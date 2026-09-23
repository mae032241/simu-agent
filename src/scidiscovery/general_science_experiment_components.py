"""Components for domain-neutral experiment Operations.

This module owns executable components and resources only.  Operation
declarations live in ``general_science_experiment_operations`` so plugin
registration remains a single, explicit composition step.
"""

from __future__ import annotations

import json

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
    ExperimentScientificSkeleton,
    HistoricalExperimentDesignIntent,
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
from .operation_contract import SemanticRuleViolation, validate_evidence_source_aliases
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
the scientific object required by the schema identified by assignment.output.schema_path. Without prior_draft,
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
current_objectives subset. For a complete ExperimentPortfolio, the workspace
finalizer copies its overall objective into each proposal's objectives and derives
resource_estimate.case_count from cases. Expand only this round's
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
Separate declared execution support from registered analysis tools and development
diagnostics: availability of one does not establish the others. A finite mathematical
model, an installed Skill, or an author role does not establish a registered executor.
Do not transfer a missing execution route to the author as an implementation task.
Narrow or defer that part of the design, or deliver the implementation gap in the
existing feasibility fields; unknown support is not physical counterevidence.
Concrete source implementation and numerical validation belong to later authoring
and diagnostics; do not claim them established by a capability declaration.
Choose an installed Skill whose description matches the task and execution
context. Skills explain methods, while execution_context declares environment
support. If a required Skill is unavailable, record that feasibility gap in the
resource judgment and handoff.
"""

OBJECT_REVIEW_PROMPT = """If scientific_skeleton is bound, review its scientific adequacy as experiment_scientific_skeleton; concrete cases, code and numerical checklists belong to the later author and are not required now. This optional early verdict cannot replace the later comprehensive project review.
For a legacy experiment_plan, independently assess task deliverability from the inputs actually handed downstream.
If a necessary implementation input or supported method is missing, request correction;
do not PASS while transferring that unresolved obligation to the author. Ordinary
later initialization, numerical checks and execution approval remain later actions.
A faithfully bounded implementation gap is reviewable; judge whether the proposed
claims and next action respect it. Do not require runtime evidence for source code
that has not yet been authored, or treat an unknown executor as a failed mechanism.
Return exactly one RoleResultEnvelope whose payload is
the ScientificReview required by the schema identified by assignment.output.schema_path. Independently review the
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


def _skeleton_inputs(sources):
    _experiment_inputs(sources)
    prior = sources.get("prior_skeleton")
    change = sources.get("skeleton_change_basis")
    if (prior is None) != (change is None):
        raise OperationInvocationError("input_skeleton_revision_pair_required", port="prior_skeleton")
    if prior is not None:
        parse_bound_json(ExperimentScientificSkeleton, prior, admission_port="prior_skeleton")


def _skeleton_context(payload, sources, handoff):
    from .artifact_agent.schema.cognitive import HypothesisProposal
    skeleton = ExperimentScientificSkeleton.model_validate_json(canonical_json(payload), strict=True)
    hypotheses = HypothesisProposal.model_validate_json(sources["hypothesis_portfolio"], strict=True)
    if not set(skeleton.selected_hypothesis_keys) <= {h.hypothesis_key for h in hypotheses.hypotheses}:
        raise SemanticRuleViolation("skeleton selects a hypothesis absent from the supplied portfolio")


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
        or set(revised.selected_hypothesis_keys)
        != set(prior.selected_hypothesis_keys)
        or {item.experiment_key for item in revised.proposals}
        != {item.experiment_key for item in prior.proposals}
    ):
        raise SemanticRuleViolation(
            "experiment revision cannot change the prior experiment identity"
        )


def _object_review_inputs(sources: dict[str, bytes]) -> None:
    if ("experiment_plan" in sources) == ("scientific_skeleton" in sources):
        raise OperationInvocationError("input_review_subject_exact_one", port="experiment_plan")
    if "scientific_skeleton" in sources:
        parse_bound_json(ExperimentScientificSkeleton, sources["scientific_skeleton"], admission_port="scientific_skeleton")
    else:
        parse_bound_json(ExperimentPortfolio, sources["experiment_plan"], admission_port="experiment_plan")
    raw_objective = sources.get("research_objective")
    if raw_objective is not None:
        parse_bound_json(ResearchObjectiveContract, raw_objective,
                         admission_port="research_objective")
    execution_context = sources.get("execution_context")
    if execution_context is not None:
        parse_bound_json(ExecutionContext, execution_context, admission_port="execution_context")


def _object_review_context(
    payload: dict[str, Any], sources: dict[str, bytes], handoff: dict[str, Any]
) -> None:
    review = ScientificReview.model_validate_json(canonical_json(payload), strict=True)
    expected_target = "experiment_scientific_skeleton" if "scientific_skeleton" in sources else "experiment_portfolio"
    if review.review_target != expected_target:
        raise SemanticRuleViolation("scientific review target differs from the bound object")
    expected_verdict = "blocked" if review.verdict == "reject" else review.verdict
    if handoff.get("verdict") != expected_verdict:
        raise SemanticRuleViolation("review handoff verdict differs from payload verdict")
    validate_evidence_source_aliases(payload, sources)


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
    experiment_skeleton_schema = schema_resource(ExperimentScientificSkeleton, "scidiscovery.experiment-scientific-skeleton.v1")
    experiment_skeleton_prompt = OPERATION_AGENT_PREAMBLE + """Design a scientific skeleton for the exact original research objective and this round's current objectives.
State competing explanations, controls, changed and held conditions, observables,
discrimination criteria with necessary thresholds and evidence or reproducible basis,
immutable scientific conditions, stop conditions and unresolved feasibility limits.
Select only reviewed hypotheses. Do not enumerate engineering cases, raw paths or
numerical checklists merely to make the skeleton executable. The author owns the
concrete ExperimentPortfolio, source, discretization, initialization and authorized
development validation. A scientific variable remains scientific even if it is a time
step or mesh. Do not invent facts or execution support. Bound prior_skeleton and
skeleton_change_basis identify an intentional new design; explain the change in the
handoff without inheriting any old review. A semantic conflict first requires a bounded
scientific judgment about its effect; do not turn an unsupported requirement into
repeated implementation searches. Deliver the assigned scientific skeleton only.
"""
    experiment_skeleton_semantic_contract = scientific_semantic_contract(
        "experiment.skeleton", "State the scientific decision without preassigning author implementation choices.",
        "The skeleton grants no execution or scientific claim permission.",
        required_inputs=("research_objective", "hypothesis_portfolio", "critic_review"),
        payload_constraint="State current objectives, scientific comparisons, criteria and basis, frozen conditions and stops; concrete cases and numerical implementation belong to the author.",
        context_constraint="Select hypotheses only from the bound portfolio; preserve the original objective through immutable inputs. Explain any intentional change from the exact prior skeleton and change basis.",
        payload_rule_id="experiment.skeleton.structure", context_rule_id="experiment.skeleton.binding",
    )
    research_objective_schema = schema_resource(
        ResearchObjectiveContract, "scidiscovery.research-objective.v1"
    )
    experiment_intent_schema = schema_resource(
        ExperimentDesignIntent, "scidiscovery.experiment-design-intent.v1"
    )
    experiment_intent_read_schema = schema_resource(
        HistoricalExperimentDesignIntent, "scidiscovery.experiment-design-intent.v1"
    )
    execution_context_schema = schema_resource(
        ExecutionContext, "scidiscovery.execution-context.v1"
    )
    experiment_portfolio_schema = schema_resource(
        ExperimentPortfolio, "scidiscovery.experiment-portfolio.v1"
    )
    scientific_review_schema = json.dumps({
        **json.loads(schema_resource(ScientificReview, "scidiscovery.scientific-review.v1")),
        "description": "Formal ScientificReview payload of the sealed envelope. In the draft envelope, "
            "/handoff or its /summary and /verdict may be omitted: the workspace finalizer derives "
            "handoff verdict from payload.verdict (reject maps to blocked) and a short reference "
            "to payload.summary. Existing explicit summary/notes are preserved. This is a draft "
            "omission, not a relaxation of the sealed RoleResultEnvelope Schema.",
    }, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    materialization_report_schema = schema_resource(
        ExperimentPlanMaterializationReport,
        "scidiscovery.experiment-plan-materialization.v1",
    )
    experiment_design_semantic_contract = scientific_semantic_contract(
        "experiment.design",
        "Bind a new intent or complete revised plan to its exact scientific context.",
        "The intent selects only hypotheses from the bound portfolio; control retains the original research objective reference.",
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
            " Observable prose is not an identity registry and need not be copied "
            "verbatim between declarations. An explicit baseline_case_key selects "
            "the comparison baseline regardless of its descriptive case role; "
            "when omitted, control derives it only from one unambiguous declared "
            "baseline/control case. A frozen variable must be constant within its "
            "declared comparison; distinct blocks need their own stated scope."
        ),
        context_constraint=(
            "Selected hypothesis keys must refer to the bound portfolio. Control "
            "projects the global objective reference during materialization; the "
            "Agent need not copy its key or statement. When an optional "
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
            "Each proposal's nonempty current_objectives are a subset of its "
            "declared goals; the overall objective is available by bound reference. "
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
        required_inputs=(),
        payload_constraint=(
            "The review must satisfy its declared structural Schema and use "
            "unambiguous hypothesis identities. Source references do not require "
            "duplicated citation ledger entries."
        ),
        context_constraint=(
            "The review_target is experiment_scientific_skeleton when scientific_skeleton is bound, otherwise experiment_portfolio. A skeleton review assesses scientific choices without requiring author-owned concrete cases or numerical checklists. The review must assess the exact supplied experiment without mutating it. "
            "Input objective and execution-context compatibility belong to preflight. "
            "Every evidence.source_key and findings[].evidence_keys reference must name an actual visible input alias, "
            "including actual collection aliases. Independently assess original "
            "mandatory targets and closure, current selection, deferral, feasibility "
            "and supplied feedback; judge how uncovered targets affect current "
            "validity, identifiability and claims. Optional absent inputs limit "
            "conclusions without imposing a hidden submission requirement."
        ),
        payload_rule_id="experiment.review.structure",
        context_rule_id="experiment.review.subject_binding",
    )
    experiment_prompt = OPERATION_AGENT_PREAMBLE + EXPERIMENT_PROMPT
    experiment_design_prompt = OPERATION_AGENT_PREAMBLE + EXPERIMENT_DESIGN_PROMPT
    object_review_prompt = OPERATION_AGENT_PREAMBLE + OBJECT_REVIEW_PROMPT


class ExperimentComponents:
    skeleton_inputs = CallableComponent("validator", _skeleton_inputs)
    skeleton_validator = CallableComponent("validator", _strict_validator(ExperimentScientificSkeleton))
    skeleton_context = CallableComponent("validator", _skeleton_context)
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
        "skeleton_validator": ("experiment_skeleton_semantic_contract",),
        "skeleton_context": ("experiment_skeleton_semantic_contract",),
        "experiment_validator": ("experiment_design_semantic_contract",),
        "review_validator": ("scientific_review_semantic_contract",),
        "experiment_context": ("experiment_design_semantic_contract",),
        "experiment_revision_context": ("experiment_revision_semantic_contract",),
        "object_review_context": ("scientific_review_semantic_contract",),
        "experiment_portfolio_validator": ("experiment_revision_semantic_contract",),
    }
    for name in (
        "skeleton_inputs", "skeleton_validator", "skeleton_context",
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
        "experiment_skeleton_schema",
        "execution_context_schema",
        "experiment_portfolio_schema",
        "research_objective_schema",
        "scientific_review_schema",
    }
    for name in (
        "experiment_skeleton_schema", "experiment_skeleton_prompt", "experiment_skeleton_semantic_contract",
        "research_objective_schema",
        "experiment_intent_schema",
        "experiment_intent_read_schema",
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
