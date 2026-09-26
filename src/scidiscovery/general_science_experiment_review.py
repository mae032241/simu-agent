"""Optional independent assessment of a sealed experiment or implementation."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .general_science_agent_operations import BASE_TOOLS, _input
from .operation_declaration import schema_resource, scientific_agent_operation, semantic_contract
from .operations.spec import CallableComponent, ComponentRef, ComponentSpec, OutputPortSpec, SemanticRuleSpec


class ExperimentReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    verdict: Literal["pass", "revise", "blocked", "inconclusive"]
    summary: str = Field(min_length=1, max_length=8192)
    findings: tuple[str, ...] = Field(default=(), max_length=32)
    limitations: tuple[str, ...] = Field(default=(), max_length=32)


PROMPT = """Independently assess the exact sealed subject and requested scientific
question using the supplied materials. A subject can be evidence, a hypothesis, parameter evidence, an analysis, an experiment report, design stage or solver implementation. For solver code, use the relevant installed
domain Skill. Assess scientific and implementation defects that matter to the
requested claim; explain unavailable evidence and uncertainty. Do not demand a
fixed preflight, initialization, review witness, or old plan/skeleton format.
Stage submission and independent assessment do not grant execution authorization.
Return the declared ExperimentReview; use revise, blocked or inconclusive when
the subject cannot support the requested claim. Do not edit the reviewed subject.
"""
SCHEMA = schema_resource(ExperimentReview, "scidiscovery.experiment-review.v1")
CONTRACT = semantic_contract(SemanticRuleSpec("experiment.review",
    "Assess only the exact supplied scientific subject and requested claims. Findings may question the science; unrequested templates and fixed diagnostic sequences are not pass conditions."))
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
    agent=ComponentRef("critic_agent"), workspace=ComponentRef("experiment_task_workspace"),
    prompt=ComponentRef("experiment_review_prompt"), tools=BASE_TOOLS,
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
