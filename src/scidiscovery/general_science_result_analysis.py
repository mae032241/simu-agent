"""Independent interpretation of one exact experiment, without domain tools."""
from .artifact_agent.schema.cognitive import HypothesisProposal
from .artifact_agent.schema.common import canonical_json
from .artifact_agent.schema.layered_diagnosis import LayeredDiagnosisReport
from .artifact_agent.schema.scientific_progress import ScientificProgressProjection, ScientificProgressChange
from .general_science_agent_operations import _input, WORKSPACE_REF
from .general_science_experiment_task import ExperimentReport, validate_goal_inputs
from .operation_contract import SemanticRuleViolation, validate_evidence_source_aliases
from .operation_declaration import schema_resource, scientific_agent_operation, semantic_contract
from .operations.input_validation import parse_bound_json
from .plugin_runtime.calculations import analysis_evidence_aliases
from .operations.spec import (CallableComponent, ComponentRef, ComponentSpec,
    InputDerivationSpec, InputValidationSpec, OutputPortSpec, SemanticRuleSpec, ScientificProgressSpec)


def validate_inputs(sources):
    parse_bound_json(ExperimentReport, sources["experiment_results"], admission_port="subject")
    validate_goal_inputs(sources)


def validate_context(payload, sources, handoff):
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(payload), strict=True)
    proposal = parse_bound_json(HypothesisProposal, sources["hypothesis_portfolio"])
    known = set(sources) | set(sources.binding_descriptors)
    if any(item.input_alias not in known for item in report.source_references):
        raise SemanticRuleViolation("Analysis references must identify exact bound inputs.")
    aliases = analysis_evidence_aliases(report.evidence, report.source_references, known)
    if any(alias not in known for alias in aliases.values()):
        raise SemanticRuleViolation("Analysis evidence must resolve to an exact bound input.")
    validate_evidence_source_aliases(payload, known | set(aliases))
    if report.experiment_key is not None or report.plan_key is not None or any(
            item.experiment_key is not None or item.case_key is not None for item in report.source_references):
        raise SemanticRuleViolation("This generic analysis has no bound experiment plan or case identity; omit those keys.")
    keys = {item.hypothesis_key for item in proposal.hypotheses}
    if any(item.hypothesis_key not in keys for item in report.hypothesis_assessments):
        raise SemanticRuleViolation("Analysis may assess only hypotheses in the exact experiment's portfolio.")
    hypotheses = {item.hypothesis_key: item for item in proposal.hypotheses}
    for assessment in report.hypothesis_assessments:
        hypothesis = hypotheses[assessment.hypothesis_key]
        if not set(assessment.predictions_checked) <= {item.prediction_key for item in hypothesis.predictions} or not set(
                assessment.falsifiers_triggered) <= {item.falsifier_key for item in hypothesis.falsifiers}:
            raise SemanticRuleViolation("Analysis checks must name predictions or falsifiers in the exact hypothesis.")
    if report.objective_assessment is not None and report.objective_assessment.objective_key != proposal.research_objective_key:
        raise SemanticRuleViolation("Analysis objective must identify the exact hypothesis objective.")


def project_progress(payload, sources):
    """Copy the author's scientific outcomes; do not derive physical truth."""
    report = LayeredDiagnosisReport.model_validate_json(canonical_json(payload), strict=True)
    proposal = parse_bound_json(HypothesisProposal, sources['hypothesis_portfolio'])
    known = set(sources.binding_descriptors)
    aliases = analysis_evidence_aliases(report.evidence, report.source_references, known)
    def resolve(keys):
        return tuple(dict.fromkeys(aliases.get(key, key) for key in keys))
    changes = tuple(ScientificProgressChange(dimension=item.hypothesis_key, outcome=item.outcome,
        evidence_keys=resolve(item.evidence_keys)) for item in report.hypothesis_assessments
        if item.outcome in {'supports', 'contradicts'} and report.overall_verdict != 'invalid_study')
    assessment = report.progress_assessment
    outcome = assessment.outcome if assessment is not None else ('advance' if changes else 'unknown')
    evidence = resolve(assessment.evidence_keys) if assessment is not None else tuple(dict.fromkeys(
        key for change in changes for key in change.evidence_keys))
    return ScientificProgressProjection(outcome=outcome, question=proposal.stage_objective,
        answer=assessment.reason if assessment else report.summary,
        remaining_question=report.remaining_contradiction or '', evidence_keys=evidence, changes=changes)


PROMPT = """Analyze the exact sealed experiment_results against its original
hypothesis_portfolio and objective_source. Read the adopted stages and original
materials, distinguish observations, numerical validity and scientific
interpretation, and assess original predictions, falsifiers, challenged assumptions
and conflicts between proxy metrics and robust evidence. Challenge H-derived
evaluation proxies, candidate-selection strategies and evidence prerequisites
against the exact original user goal and constraints. They are scientific proposals,
not additional user requirements. Recommend explicit revision when unsupported;
preserve provenance and earlier declarations without silently changing user constraints.
Distinguish derived scientific rules from genuine original user constraints and
control permissions. Preserve those constraints and permissions; challenging a
derived proxy does not relax them. When a proposed direction changes
H's mechanisms, key assumptions, allowed data or validation boundaries, return it
to H for explicit revision before W executes that direction. Scope-exceeding ideas
and existing anomalous observations may be assessed without authorizing new tests.
Ask H to clarify missing or conflicting direction instead of making Root reconstruct it.
Judge the bounded answer
separately from global completion. Retain original requirements and cumulative
trial/stopping history from exact evidence; missing history limits completion claims.
Use remaining_contradiction and next_action to explain how evidence changes the
decision: continue tests within existing hypotheses and original criteria, revise
hypotheses if mechanisms, questions, criteria or research routes must change.
Scope negative findings to the tested route; local exhaustion does not establish
global exhaustion. When feasible within scope, constraints, budget and permissions,
recommend a distinct mechanism question and minimal discriminating contrast for
hypothesis formulation. Distinguish testable assumptions from required unobtainable
inputs. Unknown generalization limits claims. Retain the best eligible candidate under
original criteria and negative evidence; reject retries that cannot change the decision
and run-count filler. Recommend successful closeout only with supported global conditions,
or honest incomplete closeout with specific blockers or budget limits. Do not force
a new hypothesis or experiment; a better proxy alone does not settle the decision.
Reuse sufficient evidence. Native data processing and analysis calculations are allowed with their
sources and limitations. Do not launch experiments or formulate a new portfolio.
Return LayeredDiagnosisReport. Do not invent experiment/plan/objective keys when
their corresponding source is absent. Blocked or incomplete experiments can
support an inconclusive analysis, never fabricated successful observations.
Use payload.summary and payload.next_action to relay your finite outcome and
recommended complete next question, scientific role and exact source names, or
supported scientific closeout. Control copies those fields into the existing
compact handoff; do not author their duplicate handoff fields. Include limitations
in the formal report and optional handoff assumptions/missing_inputs. Keep
next_action complete within 1024 UTF-8 bytes and summary within 4096 bytes so Root
can schedule without reconstructing science. Respect declared experiment
contracts; no additional next stage or review is added.
Control binds exact sources; the Worker owns scientific judgments. This task
adds no execution authorization or mandatory review.
Start with the default output-form and sealed input overviews; use original input
directories for fields needed by a claim. An overview is partial and does not
establish inspection of omitted originals. Do not use
--full or batch cat/print complete schemas, hypotheses, reports, logs or arrays
as routine discovery. Select the exact fields needed for each claim, its original
criterion, contrary evidence and limitations; read their reference definitions.
For numerical verification, process complete data locally and return compact
checks, discrepancies and exact source references instead of printing raw arrays.
Expand only to resolve a specific missing fact or inconsistency, using bounded
pages and retaining omissions. Full inspection may be necessary for a claim;
avoid irrelevant traversal and do not omit failures or negative evidence to save context.
Keep the final report concise, without copying complete protocols or logs.
Cite exact retained evidence and state the finite conclusion, limitations and
remaining question. Plan necessary checks and delivery within the current budget
and assigned closeout allocation; missing evidence supports a limited assessment.
After verification, write the report and explicitly submit it through the startup
submit entry in the same code-mode call when available. A draft or completion chat
is not sealed delivery; inspect the returned state and repair declared rejections.
Use hypothesis_assessments with exact evidence_keys for the bounded findings.
When an outcome does not meet the goal or shows no_progress, check whether relevant
H-derived or source-unverified boundaries limit improvement. Use the retained
evidence to explain a recommendation to preserve the boundary or have H explicitly
revise it, through the existing report and next_action fields. This is not a required
review of every declaration. Current assigned H boundaries remain in force until
explicit revision; citation matches do not verify interpretation or grant authority.
When the decision did not change, use optional progress_assessment.outcome=no_progress
with its reason and evidence_keys; use unknown for unavailable assessment. New files,
parameter improvements or a passing verdict alone do not establish scientific
progress. Scientific assessment belongs to you,
not independent verification by control.
"""
from .artifact_agent.schema.role_result import BOUNDARY_GUIDANCE
PROMPT += BOUNDARY_GUIDANCE + """Reference the exact H declaration being challenged in handoff.boundary_references.
A's own boundary_declarations are interpretations or revision proposals, not new
applicable H boundaries. Recommend H revision with evidence; current W boundaries
remain in force until the explicit revised H portfolio is assigned.
"""
SCHEMA = schema_resource(LayeredDiagnosisReport, "scidiscovery.layered-diagnosis.v1")
CONTRACT = semantic_contract(SemanticRuleSpec("analysis.experiment_binding",
    "Interpret an exact sealed experiment using its original hypotheses and goal. References, assessed hypothesis identities and any declared prediction/falsifier keys must be bound. Optional progress_assessment judges the increment to the research decision, separately from whether evidence supports or contradicts a hypothesis. A owns evaluating outcomes, challenging derived proxies/selection rules against original user constraints, and recommending scientific followup or closeout through existing narrative/handoff fields. This does not change the user goal or qualification, which belongs to its existing authority."))
COMPONENTS = (
    ComponentSpec("result_analysis_prompt", "resource", __name__ + ":PROMPT"),
    ComponentSpec("result_analysis_schema", "resource", __name__ + ":SCHEMA"),
    ComponentSpec("result_analysis_contract", "resource", __name__ + ":CONTRACT"),
    ComponentSpec("result_analysis_inputs", "validator", __name__ + ":INPUTS"),
    ComponentSpec("result_analysis_validator", "validator", __name__ + ":VALIDATOR",
        resources=(ComponentRef("result_analysis_contract"),)),
    ComponentSpec("result_analysis_context", "validator", __name__ + ":CONTEXT",
        resources=(ComponentRef("result_analysis_contract"),)),
    ComponentSpec("result_analysis_progress", "projector", __name__ + ":PROGRESS"),
)
INPUTS = CallableComponent("validator", validate_inputs)
VALIDATOR = CallableComponent("validator", lambda raw: LayeredDiagnosisReport.model_validate_json(raw, strict=True))
CONTEXT = CallableComponent("validator", validate_context)
PROGRESS = CallableComponent("projector", project_progress)

OPERATION = scientific_agent_operation("science.result.analyze.v1",
    "Interpret one exact experiment and its tested hypotheses independently of execution.",
    "A sealed experiment has observations, failures or limitations needing scientific interpretation.",
    "Launching experiments, inventing unsupported evidence, or formulating a new hypothesis portfolio.",
    agent=ComponentRef("critic_agent"), workspace=WORKSPACE_REF,
    prompt=ComponentRef("result_analysis_prompt"), tools=(), native_view_image=True,
    decision_fields=("overall_verdict", "claim_allowed", "summary", "hypothesis_assessments", "limitations", "remaining_contradiction", "next_action", "progress_assessment"),
    scientific_progress=ScientificProgressSpec(stage="analysis", subject_port="experiment_results", objective_port="objective_source",
        projector=ComponentRef("result_analysis_progress"), source_ports=("hypothesis_portfolio",)),
    input_validation=InputValidationSpec(ComponentRef("result_analysis_inputs"), "analysis.experiment_binding",
        "Select an exact sealed experiment. Control retrieves its original hypothesis portfolio, global goal and scientific materials; unrelated sources never substitute."),
    inputs=(
        _input("subject", "Exact sealed experiment report to interpret.", "*", media_types=("*/*",), exposure="on_demand", usage="evidence_inventory"),
        _input("experiment_results", "Control-bound original experiment report.", "*", media_types=("*/*",), exposure="on_demand", usage="evidence_inventory").model_copy(update={
            "derivation": InputDerivationSpec(anchor_port="subject", producer_output_port="experiment")}),
        _input("hypothesis_portfolio", "The exact experiment's original hypotheses.", "scidiscovery.hypothesis-proposal.v2", exposure="on_demand", usage="evidence_inventory").model_copy(update={
            "derivation": InputDerivationSpec(anchor_port="experiment_results", producer_input_path=("hypothesis_portfolio",))}),
        _input("objective_source", "The exact experiment's original global goal.", "*", media_types=("*/*",), exposure="on_demand", usage="evidence_inventory").model_copy(update={
            "derivation": InputDerivationSpec(anchor_port="experiment_results", producer_input_path=("objective_source",))}),
        _input("experiment_materials", "Control-bound scientific source inventory of the exact experiment, including adopted stage materials.", "*", media_types=("*/*",), min_items=0, max_items=128, max_item_bytes=None, exposure="material", usage="evidence_inventory").model_copy(update={
            "derivation": InputDerivationSpec(anchor_port="experiment_results", producer_output_port="tool_evidence")}),
        _input("experiment_sources", "Exact original source inputs of the experiment; streamed without expanding large files.", "*", media_types=("*/*",), min_items=0, max_items=128, max_item_bytes=None, exposure="file_reference", usage="evidence_inventory").model_copy(update={
            "derivation": InputDerivationSpec(anchor_port="experiment_results", select="sources")}),
        _input("experiment_files", "Exact published experiment files, including implementation, logs and results; streamed on demand.", "*", media_types=("*/*",), min_items=0, max_items=128, max_item_bytes=None, exposure="file_reference", usage="evidence_inventory").model_copy(update={
            "derivation": InputDerivationSpec(anchor_port="experiment_results", producer_output_port="attachments")}),
        _input("scientific_materials", "Optional exact additional reference evidence for this interpretation.", "*", media_types=("*/*",), min_items=0, max_items=16, exposure="on_demand", usage="evidence_inventory"),
    ),
    outputs=(OutputPortSpec(name="analysis", description="Scientific interpretation of exact results and hypotheses.",
        schema="scidiscovery.layered-diagnosis.v1", media_types=("application/json",), codec=ComponentRef("json_codec"),
        schema_resource=ComponentRef("result_analysis_schema"), kind="layered_diagnosis", max_item_bytes=128*1024,
        validator=ComponentRef("result_analysis_validator"), validator_rule_id="analysis.experiment_binding",
        context_validator=ComponentRef("result_analysis_context"), context_rule_id="analysis.experiment_binding",
        context_sources=("experiment_results", "hypothesis_portfolio", "objective_source", "experiment_materials", "experiment_sources", "experiment_files", "scientific_materials"),
        semantic_contract=ComponentRef("result_analysis_contract")),),
    timeout=900, max_input_bytes=48*1024*1024, max_output_bytes=128*1024, max_files=1)
