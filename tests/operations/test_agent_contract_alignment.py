from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentDesignIntent
from scidiscovery.artifact_agent.schema.research_cycle import ScientificIntake
from scidiscovery.artifact_agent.schema.research_objective import (
    ObjectiveClosureRequirement,
)
from scidiscovery.artifact_agent.service.local_workspace import SealedFile, SealedWorkspace
from scidiscovery.artifact_agent.service.run_outputs import (
    RunCheckerError,
    RunOutputError,
    validate_run_output,
)
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_experiment_components import _experiment_context
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.general_science_resources import Resources
from scidiscovery.operation_contract import SemanticRuleViolation
from scidiscovery.operations import catalog as catalog_module
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import (
    InvocationArtifact,
    operation_port_json_schema,
    operation_primary_output,
    preflight_operation,
)
from tcad_artifact.plugin import PLUGIN as TCAD_PLUGIN
from tcad_artifact.parameter_operations import ParameterEvidencePackage
from curve_figure_evidence.figure_science_operations import AUDIT_PROMPT as FIGURE_AUDIT_PROMPT


def _catalog():
    return compile_catalog(
        (CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN)
    )


def test_all_backend_tool_contracts_equal_actual_mcp_schemas_and_resolve_refs():
    from types import SimpleNamespace
    from jsonschema import Draft202012Validator
    from curve_figure_evidence.plugin import PLUGIN as FIGURE
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import HardenedWorkerMCPRouter
    from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
    from scidiscovery.artifact_agent.service.hardened_workspace import HardenedWorkerBackend
    from scidiscovery.operations.tooling import operation_tool_contracts
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN, FIGURE))
    checked = set()
    for key in catalog.operation_ids():
        compiled = catalog.operation(key)
        if compiled.spec.executor.kind != 'agent':
            continue
        for backend, router_type in ((LocalTrustedBackend, LocalWorkerMCPRouter),
                                     (HardenedWorkerBackend, HardenedWorkerMCPRouter)):
            router = router_type(SimpleNamespace(operation_catalog=catalog, backend=backend, worker_connections=SimpleNamespace()),
                operation_id=key, operation_digest=compiled.digest)
            contracts = operation_tool_contracts(compiled, backend.assignment_tool_names(compiled))
            assert contracts == {tool['name']: {k: tool[k] for k in ('description', 'inputSchema')}
                                 for tool in router.list_tools()}
            for name, contract in contracts.items():
                schema = contract['inputSchema']
                Draft202012Validator.check_schema(schema)
                def check_refs(node):
                    if isinstance(node, dict):
                        if '$ref' in node:
                            assert node['$ref'].startswith('#/')
                            target = schema
                            for token in node['$ref'][2:].split('/'):
                                target = target[token.replace('~1', '/').replace('~0', '~')]
                        for child in node.values(): check_refs(child)
                    elif isinstance(node, list):
                        for child in node: check_refs(child)
                check_refs(schema)
                checked.add(name)
    assert {'worker_curve_score', 'worker_tcad_curve_score', 'worker_curve_figure_preview'} <= checked


@pytest.mark.parametrize('backend_kind', ['local', 'hardened'])
@pytest.mark.parametrize('legacy', [False, True])
def test_open_delivers_frozen_contracts_and_same_identity_legacy_fallback(tmp_path, monkeypatch, backend_kind, legacy):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
    from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import HardenedWorkerMCPRouter
    from scidiscovery.artifact_agent.service import runs as runs_module
    from scidiscovery.operations.tooling import operation_tool_contracts
    from tests.operations.test_tcad_result_analysis import analysis_system
    router_type = LocalWorkerMCPRouter
    if backend_kind == 'hardened':
        # TCAD analysis has collection outputs and is Local-only. Exercise the
        # file-tool transport with no scientific review chain in this fixture.
        # The original CSV review requires native reading and remains unsupported.
        from tests.operations.test_l5_hardened_run_backend import _system
        from blind_csv_plugin.plugin import PLUGIN as BLIND
        author, reviewer = BLIND.operations
        transport_fixture = BLIND.model_copy(update={'operations': (
            author.model_copy(update={'review': None}), reviewer)})
        catalog, runtime, _, root = _system(tmp_path, blind_plugin=transport_fixture)
        request = dict(name='contracts', operation_id='blind.csv.observe.v1',
            inputs=[dict(port='source_table', artifact_names=['source_csv'])], instruction='Read the declared contract.')
        router_type = HardenedWorkerMCPRouter
    else:
        catalog, runtime, root, request, _, _ = analysis_system(tmp_path)
    if legacy:
        original = runs_module.assignment_json
        def old_assignment(*args, **kwargs):
            value = json.loads(original(*args, **kwargs))
            del value['tool_contracts']
            return canonical_json(value)
        monkeypatch.setattr(runs_module, 'assignment_json', old_assignment)
    root.call_tool('operation_invoke', request)
    compiled = catalog.operation(request['operation_id'])
    worker = router_type(runtime.runs, operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool('worker_open_assignment', {})
    path = Path(opened['assignment_path'])
    frozen = path.read_bytes()
    assignment = json.loads(frozen)
    assert all("port" not in item and "artifact_ref" not in item for item in assignment["inputs"])
    if backend_kind == 'hardened':
        contracts = opened['tool_contracts']  # No native file read: necessary inline contract.
    else:
        contracts = json.loads(Path(opened['tool_contracts_path']).read_bytes())
        if opened['tool_contracts_pointer']:
            contracts = contracts['tool_contracts']
    if backend_kind == 'local' and not legacy:
        assert 'tool_contracts' not in opened
        assert opened['tool_contracts_pointer'] == '/tool_contracts'
        assert Path(opened['start_here_path']).is_file()
    assert contracts == operation_tool_contracts(compiled, runtime.runs.backend.assignment_tool_names(compiled))
    assert set(contracts) == set(assignment['tools'])
    if legacy:
        assert 'tool_contracts' not in assignment
    else:
        assert assignment['tool_contracts'] == contracts
    if backend_kind == 'local':
        request_schema = contracts['worker_tcad_curve_score']['inputSchema']
        assert request_schema['$defs']['AnalysisCurveComparison']['properties']['evaluation_points']['maximum'] == 4096
        assert '12288' in request_schema['$defs']['TCADScoreRequest']['description']
    else:
        assert 'worker_file_write_chunk' in contracts
    reopened = worker.call_tool('worker_open_assignment', {})
    if backend_kind == 'local':
        assert reopened['tool_contracts_path'] == opened['tool_contracts_path']
    else:
        assert reopened['tool_contracts'] == contracts
    assert path.read_bytes() == frozen
    if backend_kind == 'hardened' and not legacy:
        from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
        from scidiscovery.operation_contract import DiagnosticError, contract_diagnostic
        detail = contract_diagnostic('declared_edit_failure', phase='tool_execution', affected_action='tool_call',
            message='The declared edit cannot be completed.')
        def failed_edit(*args):
            raise DiagnosticError('typed edit failure', details=(detail,))
        monkeypatch.setattr(worker._editor, 'chunk', failed_edit)
        reply = MCPRouter(worker, name='hardened').handle(dict(jsonrpc='2.0', id=1, method='tools/call',
            params=dict(name='worker_file_write_chunk', arguments=dict(content='{}'))))
        assert reply['error']['data']['diagnostics'] == [detail]
    if backend_kind == 'local' and legacy:
        from scidiscovery.artifact_agent.interfaces.mcp_worker_protocol import WorkerToolError
        original_operation = type(catalog).operation
        def new_contract(self, name):
            item = original_operation(self, name)
            return replace(item, digest='f' * 64) if name == compiled.spec.operation_id else item
        monkeypatch.setattr(type(catalog), 'operation', new_contract)
        with pytest.raises(WorkerToolError):
            worker.call_tool('worker_open_assignment', {})
        assert path.read_bytes() == frozen


def test_one_tool_field_change_reaches_compiled_mcp_assignment_and_execution(tmp_path, monkeypatch):
    from pydantic import Field, create_model
    import tcad_artifact.result_analysis as analysis
    from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
    from scidiscovery.operations.tooling import operation_agent_type
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, raw_request

    original = analysis.TOOL
    identities = []
    for limit in (4, 8):
        # One provider declaration changes; every consumer must see the new
        # field bound and the real Worker must enforce it before computation.
        model = create_model('ChangedScoreInput', __base__=analysis.TCADScoreInput,
                             record_key=(str, Field(min_length=1, max_length=limit)))
        monkeypatch.setattr(analysis, 'TOOL', replace(original, input_model=model))
        directory = tmp_path / str(limit)
        directory.mkdir()
        system = analysis_system(directory)
        worker, opened = open_analysis(system)
        compiled = system[0].operation('tcad.result.analyze.v1')
        identities.append((compiled.digest, operation_agent_type(compiled)))
        declared = next(tool for tool in compiled.worker_tools if tool.name == original.name).schema()
        actual = next(tool for tool in worker.list_tools() if tool['name'] == original.name)
        assert actual == declared
        contract = {key: actual[key] for key in ('description', 'inputSchema')}
        assert json.loads(Path(opened['tool_contracts_path']).read_bytes())['tool_contracts'][original.name] == contract
        assert json.loads(Path(opened['assignment_path']).read_bytes())['tool_contracts'][original.name] == contract
        assert contract['inputSchema']['properties']['record_key']['maxLength'] == limit
        router = MCPRouter(worker, name='declaration-change')
        call = dict(jsonrpc='2.0', id=1, method='tools/call', params=dict(
            name=original.name, arguments=dict(record_key='probe', request=raw_request())))
        reply = router.handle(call)
        if limit == 4:
            detail = reply['error']['data']['diagnostics'][0]
            assert detail['path'] == '$.record_key' and '4' in detail['message']
            call['params']['arguments']['record_key'] = 'ok'
            reply = router.handle(call)
        assert json.loads(reply['result']['content'][0]['text'])['status'] == 'computed'
    assert identities[0][0] != identities[1][0]
    assert identities[0][1] == identities[1][1]  # shared native profile; contract digest still changes


def test_root_parameters_and_catalog_inputs_share_declared_constraints():
    from types import MappingProxyType
    from jsonschema import Draft202012Validator
    from scidiscovery.artifact_agent.interfaces.mcp_root import OperationCallInput
    from scidiscovery.operations.invoke import OperationInvocationError
    from scidiscovery.operations.spec import scheduler_operation_view
    schema = OperationCallInput.model_json_schema()
    validator = Draft202012Validator(schema)
    compiled = _catalog().operation('science.result.diagnose.v1')
    payload = dict(name='parameters', operation_id=compiled.spec.operation_id, inputs=[], instruction='Check parameters.')
    for parameters in (None, {}, {'unexpected': 1}):
        request = payload if parameters is None else {**payload, 'parameters': parameters}
        if parameters:
            assert list(validator.iter_errors(request))
            with pytest.raises(ValidationError):
                OperationCallInput.model_validate_json(canonical_json(request))
        else:
            validator.validate(request)
            assert OperationCallInput.model_validate_json(canonical_json(request)).parameters == {}
    with pytest.raises(OperationInvocationError) as caught:
        preflight_operation(compiled, name='parameters', instruction='Check parameters.',
            artifacts_by_port={p.name: () for p in compiled.spec.inputs}, parameters=MappingProxyType({'unexpected': 1}))
    assert caught.value.reason_code == 'parameters_not_declared'
    view = scheduler_operation_view(compiled.spec).model_dump(mode='json', by_alias=True)
    keys = ('usage', 'exposure', 'require_current', 'media_types', 'max_item_bytes')
    for projected in view['inputs']:
        port = next(p for p in compiled.spec.inputs if p.name == projected['name'])
        expected = port.model_dump(mode='json')
        assert {k: projected[k] for k in keys} == {k: expected[k] for k in keys}
    assert all(not set(keys).intersection(port) for port in view['outputs'])


def test_declared_output_relationship_reports_the_visible_rule_and_missing_field():
    from scidiscovery.artifact_agent.schema.layered_diagnosis import AnalysisSourceReference, CalculationRecord
    from scidiscovery.operation_contract import validation_diagnostics
    for model, raw, field in (
        (AnalysisSourceReference, dict(source_key='source', input_alias='raw', experiment_key='experiment'), 'case_key'),
        (CalculationRecord, dict(record_key='calculation', request={}, algorithm_version='v1', status='computed'), 'result'),
    ):
        schema = model.model_json_schema()
        with pytest.raises(ValidationError) as caught:
            model.model_validate_json(canonical_json(raw))
        details = validation_diagnostics(caught.value, schema=schema, phase='output_payload', action='submit')
        assert details[0]['path'] == '$.' + field
        assert details[0]['message'] in json.dumps(schema)


def test_every_public_agent_exposes_one_compiled_output_contract() -> None:
    catalog = _catalog()
    agents = tuple(
        catalog.operation(operation_id)
        for operation_id in catalog.operation_ids()
        if catalog.operation(operation_id).spec.catalog_scope == "public"
        and catalog.operation(operation_id).spec.executor.kind == "agent"
    )
    assert agents
    for compiled in agents:
        port = operation_primary_output(compiled)
        schema = operation_port_json_schema(compiled, port)
        semantic = schema["x-scidiscovery-semantic-constraints"]
        validation = schema["x-scidiscovery-validation-contract"]
        assert semantic["schema_version"] == 1
        assert semantic["rules"]
        assert len({item["rule_id"] for item in semantic["rules"]}) == len(
            semantic["rules"]
        )
        assert validation["operation_id"] == compiled.spec.operation_id
        assert validation["operation_digest"] == compiled.digest
        assert validation["output_port"] == port.name
        assert "runtime.schema" in {
            item["rule_id"] for item in validation["rules"]
        }
        checkers = {item["phase"]: item["rule_id"] for item in validation["checkers"]}
        assert "payload" in checkers
        assert set(checkers.values()) <= {
            item["rule_id"] for item in semantic["rules"]
        }


def test_audit_contracts_distinguish_fidelity_from_evidence_sufficiency() -> None:
    general = Resources.auditor_prompt
    semantic = Resources.evidence_audit_semantic_contract
    for text in (general, semantic, FIGURE_AUDIT_PROMPT):
        assert "忠实" in text or "faithful" in text
        assert "pass" in text
        assert "fail" in text
        assert "unknown" in text
        assert "not_applicable" in text
        assert "充分" in text or "sufficient" in text


@pytest.fixture
def experiment_case():
    critic = canonical_json(
        {"disposition": "ready_for_experiment", "schema_version": 2}
    )
    objective = canonical_json(
        {
            "objective_key": "objective_expected",
            "intent": "mechanism_discrimination",
            "statement": "Distinguish one bounded mechanism.",
            "closure_requirements": [
                {
                    "requirement_key": "comparison_required",
                    "description": "Compare the bounded candidates.",
                    "requirement_type": "comparison_present",
                    "comparison_purposes": ["mechanism_separation"],
                }
            ],
        }
    )
    hypotheses = canonical_json(
        {
            "schema_version": 2,
            "research_objective_key": "objective_expected",
            "stage_objective": "Separate one bounded mechanism.",
            "contradiction": "The supplied evidence does not distinguish it.",
            "hypotheses": [
                {
                    "hypothesis_key": "hypothesis_a",
                    "statement": "A bounded mechanism changes the response.",
                    "mechanism": "The mechanism has one finite intervention.",
                    "scope": "Only the supplied system.",
                    "predictions": [
                        {
                            "prediction_key": "prediction_a",
                            "observable": "response",
                            "expected_outcome": "The response changes.",
                        }
                    ],
                    "falsifiers": [
                        {
                            "falsifier_key": "falsifier_a",
                            "observable": "response",
                            "rejection_condition": "The response does not change.",
                        }
                    ],
                }
            ],
        }
    )
    intent = {
        "study_kind": "scientific",
        "objective_key": "objective_wrong",
        "selected_hypothesis_keys": ["hypothesis_a"],
        "proposals": [
            {
                "experiment_key": "experiment_a",
                "objectives": ["Distinguish one bounded mechanism."],
                "current_objectives": ["Distinguish one bounded mechanism."],
                "hypothesis_keys": ["hypothesis_a"],
                "frozen_invariants": ["Use the same bounded system."],
                "cases": [
                    {
                        "case_key": "baseline",
                        "scientific_role": "baseline",
                        "purpose": "Establish the baseline.",
                    },
                    {
                        "case_key": "perturbation",
                        "scientific_role": "perturbation",
                        "purpose": "Apply the bounded intervention.",
                    },
                ],
                "baseline_case_key": "baseline",
                "variables": [
                    {
                        "variable_key": "intervention",
                        "scientific_path": "model.intervention",
                        "factor_type": "physical",
                        "comparison_role": "intended_change",
                        "unit": "1",
                        "baseline_value": 0,
                        "case_overrides": [
                            {"case_key": "perturbation", "value": 1}
                        ],
                        "equivalence_rule": "exact",
                        "rationale": "The intervention distinguishes the candidates.",
                    }
                ],
                "required_observables": ["response"],
                "identifiability_claims": [
                    {
                        "hypothesis_key": "hypothesis_a",
                        "observable": "response",
                        "distinguishing_outcome": "The response changes.",
                        "decision_rule": "Compare the two bounded cases.",
                        "ambiguity_conditions": ["A case cannot complete."],
                        "smallest_resolving_control": "Repeat the failed case.",
                    }
                ],
                "prediction_tests": [
                    {
                        "hypothesis_key": "hypothesis_a",
                        "prediction_key": "prediction_a",
                        "observable": "response",
                        "expected_result": "The response changes.",
                        "falsifying_result": "The response does not change.",
                    }
                ],
                "validation_intent": {
                    "numerical": {"rationale": "Check numerical completion."},
                    "physical": {"rationale": "Check the bounded response."},
                    "experimental": {"rationale": "No additional observation."},
                },
                "resource_estimate": {
                    "relative_cost": "low",
                    "runtime_basis": "Two bounded cases.",
                },
                "stop_conditions": ["Stop after both cases."],
                "value_assessment": {
                    "evidence_support": "medium",
                    "discrimination_power": "medium",
                    "information_gain": "medium",
                    "cost": "low",
                    "added_free_parameters": 1,
                    "rationale": "One bounded comparison tests the mechanism.",
                },
            }
        ],
        "priority_order": ["experiment_a"],
        "priority_rationale": "Only one bounded experiment is required.",
    }
    return intent, {
        "critic_review": critic,
        "research_objective": objective,
        "hypothesis_portfolio": hypotheses,
    }


@pytest.mark.parametrize('key', [None, 'legacy_display_key'])
def test_experiment_context_does_not_require_copying_global_key(experiment_case, key) -> None:
    intent, sources = experiment_case
    intent['objective_key'] = key
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    _experiment_context(intent, sources, {})
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    raw, _ = materialize_experiment_plan({
        'experiment_design_intent': canonical_json(intent),
        'research_objective': sources['research_objective'],
        'hypothesis_portfolio': sources['hypothesis_portfolio'],
    })
    assert json.loads(raw)['objective_key'] == json.loads(sources['research_objective'])['objective_key']


@pytest.mark.parametrize("model_kind,limit", (("intent", 16), ("proposal", 17)))
@pytest.mark.parametrize("field", ("objectives", "current_objectives"))
@pytest.mark.parametrize("defect", ("missing", "empty", "blank", "long", "too_many"))
def test_experiment_goal_lists_enforce_exact_bounds(
    experiment_case, model_kind, limit, field, defect,
) -> None:
    from scidiscovery.artifact_agent.schema.experiment import ExperimentProposal
    from scidiscovery.artifact_agent.schema.experiment_intent import (
        ExperimentProposalIntent, materialize_experiment_design_intent,
    )
    from scidiscovery.artifact_agent.schema.research_objective import ResearchObjectiveContract

    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    if model_kind == "intent":
        model, proposal = ExperimentProposalIntent, intent["proposals"][0]
    else:
        plan = materialize_experiment_design_intent(
            ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True),
            ResearchObjectiveContract.model_validate_json(sources["research_objective"], strict=True),
        )
        model, proposal = ExperimentProposal, plan.proposals[0].model_dump(mode="json")
    if defect == "missing":
        proposal.pop(field)
    else:
        proposal[field] = {
            "empty": [], "blank": [""], "long": ["x" * 8193],
            "too_many": [f"goal {index}" for index in range((limit if field == "objectives" else 16) + 1)],
        }[defect]
    with pytest.raises(ValidationError):
        model.model_validate_json(canonical_json(proposal), strict=True)


def test_experiment_goal_subset_is_verbatim_and_python_uses_tuples(experiment_case) -> None:
    from scidiscovery.artifact_agent.schema.experiment_intent import ExperimentProposalIntent

    intent, _ = experiment_case
    proposal = intent["proposals"][0]
    proposal.update(objectives=["  Exact goal\n"], current_objectives=["Exact goal"])
    with pytest.raises(ValidationError, match="exact subset"):
        ExperimentProposalIntent.model_validate_json(canonical_json(proposal), strict=True)
    proposal["current_objectives"] = list(proposal["objectives"])
    value = ExperimentProposalIntent.model_validate_json(canonical_json(proposal), strict=True)
    assert value.objectives == value.current_objectives == ("  Exact goal\n",)
    with pytest.raises(ValidationError, match="tuple"):
        ExperimentProposalIntent.model_validate(proposal, strict=True)


def _partial_experiment(experiment_case):
    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    objective = json.loads(sources["research_objective"])
    objective["mandatory_targets"] = [
        {"target_key": key, "observable": observable,
         "support_requirement": "complete_observation", "evidence_item_keys": [key],
         "rationale": "The original objective retains this obligation."}
        for key, observable in (("current_response", "response"), ("future_response", "future observable"))
    ]
    objective["closure_requirements"].append({
        "requirement_key": "all_targets", "requirement_type": "target_coverage",
        "description": "Overall closure still requires both targets.",
        "target_keys": ["current_response", "future_response"],
    })
    sources["research_objective"] = canonical_json(objective)
    proposal = intent["proposals"][0]
    proposal.update(objectives=["Test the response now.", "Test the future observable after evidence is available."],
                    current_objectives=["Test the response now."])
    proposal["value_assessment"]["rationale"] = (
        "The response comparison is sufficient for this bounded inference. "
        "Defer the future observable until its evidence is available; overall closure remains open."
    )
    return intent, sources










@pytest.mark.parametrize("global_already_present", (False, True))
def test_materialization_and_revision_preserve_goal_text_and_rationales(
    experiment_case, global_already_present,
) -> None:
    from scidiscovery.artifact_agent.transforms import materialize_experiment_plan
    from scidiscovery.general_science_experiment_components import _experiment_revision_context

    intent, inputs = _partial_experiment(experiment_case)
    global_objective = json.loads(inputs["research_objective"])["statement"]
    proposal = intent["proposals"][0]
    local_goals = ["  Current response\n", "Future response; requires additional evidence."]
    proposal["objectives"] = [local_goals[0], global_objective, local_goals[1]] if global_already_present else local_goals
    proposal["current_objectives"] = [local_goals[0]]
    proposal["value_assessment"]["rationale"] += "\n  Keep exact scientific wording."
    intent["priority_rationale"] = "  First resolve the response.\nThen reassess the evidence condition."
    args = {"experiment_design_intent": canonical_json(intent),
            "research_objective": inputs["research_objective"],
            "hypothesis_portfolio": inputs["hypothesis_portfolio"]}
    raw, report = materialize_experiment_plan(args)
    assert materialize_experiment_plan(args) == (raw, report)
    plan = ExperimentPortfolio.model_validate_json(raw, strict=True)
    assert plan.proposals[0].objectives == (global_objective, *local_goals)
    assert plan.proposals[0].current_objectives == (local_goals[0],)
    assert plan.proposals[0].value_assessment.rationale == proposal["value_assessment"]["rationale"]
    assert plan.priority_rationale == intent["priority_rationale"]
    assert len(plan.proposals[0].cases) == 2
    assert plan.proposals[0].required_observables == ("response",)
    assert ExperimentPortfolio.model_validate_json(plan.canonical_json(), strict=True) == plan
    revised = plan.model_dump(mode="json")
    revised["proposals"][0]["objectives"].append("Reassess a bounded follow-up after review.")
    sources = {"prior_draft": raw, "change_request": canonical_json({
        "review_target": "experiment_portfolio", "verdict": "revise",
        "summary": "Retain the condition for one later follow-up.",
    })}
    _experiment_revision_context(revised, sources, {})
    assert revised["proposals"][0]["value_assessment"]["rationale"] == proposal["value_assessment"]["rationale"]
    assert revised["priority_rationale"] == intent["priority_rationale"]
    revised["proposals"][0]["objectives"].remove(global_objective)
    ExperimentPortfolio.model_validate_json(canonical_json(revised), strict=True)
    _experiment_revision_context(revised, sources, {})


def test_experiment_materialized_constraints_are_correctable(experiment_case) -> None:
    intent, sources = experiment_case
    intent["objective_key"] = "objective_expected"
    variable = intent["proposals"][0]["variables"][0]
    variable["baseline_value"] = False
    variable["case_overrides"][0]["value"] = 0
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    with pytest.raises(SemanticRuleViolation, match="intended_change variable must vary"):
        _experiment_context(intent, sources, {})


@pytest.fixture
def engineering_case(experiment_case):
    intent, sources = experiment_case
    intent.update(study_kind="engineering", objective_key=None,
                  engineering_objective="Check one bounded numerical case.",
                  selected_hypothesis_keys=[])
    proposal = intent["proposals"][0]
    proposal.update(objectives=[intent["engineering_objective"]],
                    current_objectives=[intent["engineering_objective"]],
                    hypothesis_keys=[], cases=proposal["cases"][:1],
                    baseline_case_key=None, variables=[],
                    identifiability_claims=[], prediction_tests=[])
    ExperimentDesignIntent.model_validate_json(canonical_json(intent), strict=True)
    return intent, sources


def _experiment_run(tmp_path, sources):
    from tests.operations.test_general_transform_operations import _intake, _register, _root

    catalog = _catalog()
    compiled = catalog.operation("science.experiment.design.v1")
    runtime, instance, _ = _root(tmp_path, catalog=catalog)
    runtime.runs.operation_catalog = catalog
    content = {"scientific_foundation": _intake().scientific_foundation.canonical_json(), **sources}
    envelopes = {}
    artifacts = {}
    for port in compiled.spec.inputs:
        if port.min_items == 0 and port.name not in content:
            artifacts[port.name] = ()
            continue
        parents = (() if port.name == "scientific_foundation" else
                   (envelopes["scientific_foundation"].ref,))
        if port.name == "critic_review":
            parents += (envelopes["hypothesis_portfolio"].ref,)
        envelope = _register(runtime, instance, name=port.name, raw=content[port.name],
                             kind=port.name, schema=port.schema_id, parents=parents)
        envelopes[port.name] = envelope
        artifacts[port.name] = (InvocationArtifact(
            artifact_name=port.name, ref=envelope.ref, schema_id=envelope.schema_id,
            media_type=envelope.media_type, size_bytes=envelope.size_bytes,
            parent_refs=envelope.parent_refs,
        ),)
    bound = preflight_operation(compiled, name="experiment", artifacts_by_port=artifacts,
                                instruction="Check the exact experiment output contract.", read_artifact=runtime.artifacts.read)
    # Exercise the real Run submission lifecycle independently of UI admission.
    run_id = runtime.runs.schedule(
        bound, instance_id=instance.instance_id, output_binding_name="experiment",
        output_logical_name="experiment", output_revision=1,
        output_binding_fingerprint="a" * 64,
    )
    _, workspace = runtime.runs.open(operation_id=compiled.spec.operation_id,
                                     operation_digest=compiled.digest)
    return runtime, run_id, workspace.output_directory / "result.json"


def _experiment_envelope(intent):
    return canonical_json({
        "schema_version": 1,
        "payload": intent,
        "handoff": {"verdict": "pass", "summary": "One bounded design."},
    })


def _validate_experiment_submission(tmp_path, intent, sources, *, compiled=None):
    content = _experiment_envelope(intent)
    (tmp_path / "result.json").write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    sealed = SealedWorkspace(
        backend="test", backend_version="1", run_id="experiment-contract",
        digest=digest, root=tmp_path,
        files=(SealedFile(relative_path="result.json", media_type="application/json",
                          size_bytes=len(content), sha256=digest),),
    )
    return validate_run_output(
        compiled or _catalog().operation("science.experiment.design.v1"), sealed,
        input_source_ports={name: name for name in sources}, input_bytes=sources,
    )


def test_experiment_context_does_not_reclassify_invalid_inputs() -> None:
    with pytest.raises(ValueError) as error:
        _experiment_context({}, {"critic_review": b"{}"}, {})
    assert not isinstance(error.value, SemanticRuleViolation)


def test_threshold_unit_vocabulary_is_visible_in_the_json_schema() -> None:
    schema = ExperimentPortfolio.model_json_schema(mode="validation")
    unit_schema = schema["$defs"]["MetricThreshold"]["properties"]["unit"]
    assert "1" in unit_schema["enum"]
    assert "dimensionless" in unit_schema["enum"]
    assert "probability" not in unit_schema["enum"]

    parameter_schema = ParameterEvidencePackage.model_json_schema(mode="validation")
    requirement_unit = parameter_schema["$defs"]["DeviceParameterRequirement"][
        "properties"
    ]["canonical_unit"]
    claim_unit = parameter_schema["$defs"]["DeviceParameterClaim"]["properties"][
        "unit"
    ]
    assert requirement_unit["enum"] == claim_unit["enum"]
    assert "1" in requirement_unit["enum"]
    assert "probability" not in requirement_unit["enum"]


@pytest.mark.parametrize(
    ("requirement_type", "fields", "accepted"),
    (
        (None, {"target_keys": ["target_a"]}, True),
        ("target_coverage", {"target_keys": ["target_a"]}, True),
        ("target_coverage", {}, False),
        (
            "target_coverage",
            {"target_keys": ["target_a"], "comparison_purposes": ["target_fit"]},
            False,
        ),
        ("comparison_present", {"comparison_purposes": ["target_fit"]}, True),
        (
            "comparison_present",
            {
                "target_keys": ["target_a"],
                "comparison_purposes": ["target_fit"],
            },
            True,
        ),
        ("comparison_present", {}, False),
        (
            "comparison_present",
            {
                "comparison_purposes": ["target_fit"],
                "validation_check_keys": ["check_a"],
            },
            False,
        ),
        (
            "validation_check_present",
            {"validation_check_keys": ["check_a"]},
            True,
        ),
        ("validation_check_present", {}, False),
        (
            "validation_check_present",
            {
                "validation_check_keys": ["check_a"],
                "target_keys": ["target_a"],
            },
            False,
        ),
        ("target_coverage", {"target_keys": ["target_a", "target_a"]}, True),
        (
            "comparison_present",
            {"comparison_purposes": ["target_fit", "target_fit"]},
            True,
        ),
        (
            "validation_check_present",
            {"validation_check_keys": ["check_a", "check_a"]},
            True,
        ),
    ),
)
def test_objective_closure_schema_matches_strict_model_acceptance(
    requirement_type, fields, accepted,
) -> None:
    from jsonschema.validators import validator_for

    payload = {
        "requirement_key": "closure_a",
        "description": "Close one bounded objective condition.",
        **fields,
    }
    if requirement_type is not None:
        payload["requirement_type"] = requirement_type

    try:
        ObjectiveClosureRequirement.model_validate_json(
            canonical_json(payload), strict=True
        )
        model_accepts = True
    except Exception:
        model_accepts = False

    direct_schema = ObjectiveClosureRequirement.model_json_schema(mode="validation")
    nested_schema = ScientificIntake.model_json_schema(mode="validation")["$defs"][
        "ObjectiveClosureRequirement"
    ]
    for schema in (direct_schema, nested_schema):
        validator_type = validator_for(schema)
        validator_type.check_schema(schema)
        schema_accepts = not tuple(validator_type(schema).iter_errors(payload))
        assert schema_accepts is accepted
    assert model_accepts is accepted


def test_evidence_source_projection_uses_exact_bound_context_aliases() -> None:
    compiled = _catalog().operation("tcad.parameter.evidence.extract.v1")
    port = operation_primary_output(compiled)
    schema = operation_port_json_schema(
        compiled,
        port,
        input_source_ports={
            "required_parameter_checklist": "required_parameter_checklist",
            "source_material_001": "source_material",
            "source_material_002": "source_material",
        },
    )
    evidence = schema["properties"]["scientific_intake"]["$ref"]
    intake = schema["$defs"][evidence.removeprefix("#/$defs/")]
    foundation_ref = intake["properties"]["scientific_foundation"]["$ref"]
    foundation = schema["$defs"][foundation_ref.removeprefix("#/$defs/")]
    item_projection = foundation["properties"]["evidence"]["items"]["allOf"][-1]
    assert item_projection["properties"]["source_key"]["enum"] == [
        "required_parameter_checklist",
        "source_material_001",
        "source_material_002",
    ]
    validation = schema["x-scidiscovery-validation-contract"]
    usages = {
        item["port"]: item["usage"] for item in validation["context_sources"]
    }
    assert usages == {
        "required_parameter_checklist": "evidence_inventory",
        "previous_evidence": "evidence_inventory",
        "source_material": "evidence_inventory",
        "user_context": "prior_signal",
    }


def test_empty_optional_inventory_still_allows_citing_the_bound_review_subject() -> None:
    compiled = _catalog().operation("science.evidence.audit.v1")
    port = operation_primary_output(compiled)
    static_schema = operation_port_json_schema(compiled, port)
    assert static_schema["properties"]["evidence"].get("maxItems") == 32

    bound_schema = operation_port_json_schema(
        compiled,
        port,
        input_source_ports={"scientific_foundation": "scientific_foundation"},
    )
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(bound_schema)
    payload = {"evidence": [{"source_key": "scientific_foundation", "source_type": "frozen_input", "locator": "/items/0"}]}
    validator.validate(payload)
    payload["evidence"][0]["source_key"] = "unbound_source"
    assert list(validator.iter_errors(payload))


def test_corrupt_assignment_does_not_fall_back_to_a_new_tool_contract(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.interfaces.mcp_local_worker import WorkerToolError
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis
    worker, opened = open_analysis(analysis_system(tmp_path))
    path = Path(opened['assignment_path'])
    path.chmod(0o600)
    path.write_text('{broken assignment')
    def forbidden():
        pytest.fail('corrupt assignment was silently replaced by a contract fallback')
    monkeypatch.setattr(worker, '_assignment_tool_contracts', forbidden)
    with pytest.raises(WorkerToolError) as error:
        worker.call_tool('worker_open_assignment', {})
    assert 'JSONDecodeError' in str(error.value.engineering)
