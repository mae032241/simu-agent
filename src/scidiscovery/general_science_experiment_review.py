"""Optional independent assessment of a sealed experiment or implementation."""
from pydantic import BaseModel, ConfigDict, Field

from .general_science_agent_operations import _input
from .operation_declaration import schema_resource, scientific_agent_operation, semantic_contract
from .operations.spec import CallableComponent, ComponentRef, ComponentSpec, OutputPortSpec, SemanticRuleSpec
from .artifact_agent.schema.validation import ReviewedTestConclusion
from .operations.review_rules import ReviewVerdict, REVIEW_INSTRUCTION


class ExperimentReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    verdict: ReviewVerdict
    summary: str = Field(min_length=1, max_length=8192)
    findings: tuple[str, ...] = Field(default=(), max_length=32)
    limitations: tuple[str, ...] = Field(default=(), max_length=32)
    scientific_test: ReviewedTestConclusion | None = Field(default=None,
        description="Optional explicit independent judgment of one exact predeclared scientific test in the reviewed subject. Reuse its experiment_key, plan_key and check_key; state the observation, result and evidence aliases. Quality pass alone is not test progress. For verified progress, prior sealing requires the exact frozen plan to be an immutable ancestor of each actual observation input of the reviewed diagnosis. Each sealing proof checks at most 64 distinct original envelopes; absent, damaged or incompletely covered lineage leaves progress unknown. Registration timestamps are not order proof. Control checks original identities and independence, not original generation time, source novelty or scientific authenticity; this field cannot establish deterministic numerical proof.")


PROMPT = """Independently assess the exact sealed subject and requested scientific
question using the supplied materials. A subject can be evidence, a hypothesis, parameter evidence, an analysis, an experiment report, design stage or solver implementation. For solver code, use the relevant installed
domain Skill. Assess scientific and implementation defects that matter to the
requested claim; explain unavailable evidence and uncertainty. Do not demand a
fixed preflight, initialization, review witness, or old plan/skeleton format.
Stage submission and independent assessment do not grant execution authorization.
Return the declared ExperimentReview; use revise, blocked or inconclusive when
the subject cannot support the requested claim. Do not edit the reviewed subject.
If judging a specific predeclared qualitative test, scientific_test may preserve
its exact experiment/plan/check names, observed conclusion and source aliases.
Read the exact subject and prior criterion through the declared reference tool.
Omit it for general quality review or when the test evidence is unavailable.
An overall pass alone is not scientific progress; this field is optional and
does not authorize work, renew budgets or require a review to unlock dispatch.
"""
SCHEMA = schema_resource(ExperimentReview, "scidiscovery.experiment-review.v1")
CONTRACT = semantic_contract(SemanticRuleSpec("experiment.review",
    REVIEW_INSTRUCTION))
VALIDATOR = CallableComponent("validator", lambda raw: ExperimentReview.model_validate_json(raw, strict=True))
COMPONENTS = (
    ComponentSpec("experiment_review_prompt", "resource", __name__ + ":PROMPT"),
    ComponentSpec("experiment_review_schema", "resource", __name__ + ":SCHEMA"),
    ComponentSpec("experiment_review_contract", "resource", __name__ + ":CONTRACT"),
    ComponentSpec("experiment_review_validator", "validator", __name__ + ":VALIDATOR",
        resources=(ComponentRef("experiment_review_contract"),)),
)
OPERATION = scientific_agent_operation("science.object.review.v1",
    "Independently assess one exact scientific object when review is useful.",
    "A sealed scientific subject has a bounded review question.", "Authoring, execution authorization, or adding undeclared formatting gates.",
    decision_fields=("verdict", "summary", "limitations", "findings"),
    agent=ComponentRef("critic_agent"), workspace=ComponentRef("experiment_task_workspace"),
    prompt=ComponentRef("experiment_review_prompt"), tools=(),
    inputs=(_input("subject", "Exact sealed scientific object to assess.", "*",
        media_types=("*/*",), exposure="on_demand", usage="evidence_inventory"),
        _input("scientific_materials", "Optional objective, evidence and observations needed for this review question.", "*",
            media_types=("*/*",), min_items=0, max_items=16, exposure="on_demand", usage="evidence_inventory")),
    outputs=(OutputPortSpec(name="scientific_review", description="Independent bounded scientific assessment.",
        schema="scidiscovery.experiment-review.v1", media_types=("application/json",), codec=ComponentRef("json_codec"),
        schema_resource=ComponentRef("experiment_review_schema"), kind="scientific_review", max_item_bytes=65536,
        validator=ComponentRef("experiment_review_validator"), validator_rule_id="experiment.review",
        semantic_contract=ComponentRef("experiment_review_contract")),),
    timeout=900, max_input_bytes=32*1024*1024, max_output_bytes=65536, max_files=1)
OPERATION = OPERATION.model_copy(update={"independent_review_ports": ("subject",)})
