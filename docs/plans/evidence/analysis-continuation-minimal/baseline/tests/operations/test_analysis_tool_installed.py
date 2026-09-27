"""Analysis contracts and controlled result submission from installed wheels."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("environment", ["full", "all_domains"])
def test_installed_catalog_identity_matches_source(installed_probe, tmp_path, environment):
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as GENERAL
    from curve_score.plugin import PLUGIN as CURVE
    from tcad_artifact.plugin import PLUGIN as TCAD
    from curve_figure_evidence.plugin import PLUGIN as FIGURE
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.tooling import operation_agent_type
    output = installed_probe(environment, r'''
import json
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_agent_type
catalog = compile_installed_catalog()
print(json.dumps({key: dict(digest=catalog.operation(key).digest,
    agent_type=operation_agent_type(catalog.operation(key)) if catalog.operation(key).spec.executor.kind == "agent" else None)
    for key in catalog.operation_ids()}, sort_keys=True))
''')
    catalog = compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD) + ((FIGURE,) if environment == "all_domains" else ()))
    expected = {key:dict(digest=catalog.operation(key).digest,
        agent_type=operation_agent_type(catalog.operation(key)) if catalog.operation(key).spec.executor.kind == "agent" else None)
        for key in catalog.operation_ids()}
    assert json.loads(output) == expected
    (tmp_path / "catalog.json").write_text(output)


@pytest.mark.parametrize("entry", ["local_worker", "hardened_worker", "proxy"])
def test_installed_stdio_errors_share_protocol_diagnostics(installed_probe, entry):
    installed_probe("blind_csv", "entry = " + repr(entry) + r'''
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from scidiscovery.operations.catalog import compile_installed_catalog
root = Path(tempfile.mkdtemp(prefix="installed-protocol-"))
command = [sys.executable, "-m", "scidiscovery.artifact_agent.interfaces.mcp_" + entry]
if entry == "proxy":
    command += ["--socket", str(root / "unavailable.sock")]
else:
    operation = compile_installed_catalog().operation("blind.csv.observe.v1")
    command += ["--state-root", str(root), "--operation-id", operation.spec.operation_id,
                "--operation-digest", operation.digest]
    if entry == "local_worker":
        command += ["--local-workspace-root", str(root / "workspaces")]
valid = json.dumps(dict(jsonrpc="2.0", id=3, method="tools/list"))
process = subprocess.run(command, input='["SECRET_PROTOCOL_VALUE"]\n{\n' + valid + '\n',
    text=True, capture_output=True, timeout=30)
assert process.returncode == 0, process.stderr
responses = [json.loads(line) for line in process.stdout.splitlines()]
assert len(responses) == 3 and "SECRET_PROTOCOL_VALUE" not in process.stdout
for response in responses[:2]:
    diagnostic = response["error"]["data"]["diagnostics"][0]
    assert diagnostic["phase"] == "protocol" and diagnostic["code"] == "invalid_protocol_request"
if entry == "proxy":
    assert responses[-1]["error"]["data"]["diagnostics"][0]["code"] == "runtime_failure"
else:
    assert responses[-1]["result"]["tools"]
''')


@pytest.mark.parametrize("environment", ("curve", "full"))
def test_installed_analysis_catalog_and_worker_projection(installed_probe, environment):
    installed_probe(environment, "environment = " + repr(environment) + r'''
import importlib.util
import sys
import tempfile
import tomllib
from pathlib import Path
import curve_score.analysis_tool as analysis_tool
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import (
    operation_agent_type, operation_local_worker_tool_names,
    operation_worker_server_name,
)
from scidiscovery.platforms import initialize_platform
assert Path(analysis_tool.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
catalog = compile_installed_catalog()
generic = catalog.operation("science.result.diagnose.v1")
ports = {p.name: p for p in generic.spec.inputs}
assert {name for name, p in ports.items() if p.min_items} == {
    "experiment_plan", "experiment_review", "experiment_results",
}
assert ports["metric_report"].min_items == ports["curve_bundle"].min_items == 0
assert "curve_contract" not in ports
assert "worker_curve_score" in operation_local_worker_tool_names(generic)
assert "worker_curve_diagnose" in operation_local_worker_tool_names(generic)
assert "worker_analysis_publish_files" in operation_local_worker_tool_names(generic)
operations = [generic, catalog.operation("science.result.diagnose.curve-error.v1")]
if environment == "curve":
    assert importlib.util.find_spec("tcad_artifact") is None
    assert "tcad.result.analyze.v1" not in catalog.operation_ids()
else:
    import tcad_artifact.result_analysis as tcad_analysis
    assert Path(tcad_analysis.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    domain = catalog.operation("tcad.result.analyze.v1")
    domain_ports = {p.name: p for p in domain.spec.inputs}
    assert {name for name, p in domain_ports.items() if p.min_items} == {
        "experiment_plan", "experiment_review", "reviewed_package", "runtime_manifest",
    }
    assert domain_ports["solver_outputs"].min_items == 0
    assert domain_ports["solver_outputs"].max_items == 32
    assert "curve_bundle" not in domain_ports and "metric_report" not in domain_ports
    assert "worker_tcad_curve_score" in operation_local_worker_tool_names(domain)
    assert "worker_tcad_curve_diagnose" in operation_local_worker_tool_names(domain)
    assert "worker_analysis_publish_files" in operation_local_worker_tool_names(domain)
    from scidiscovery.platforms.codex import _operation_runtime_plugin_configs
    configured = {"tcad_artifact": Path("/fixture/tcad.json")}
    assert _operation_runtime_plugin_configs(domain, configured) == tuple(configured.items())
    assert {"worker_tcad_inspect_outputs", "worker_tcad_accept_output"} <= set(operation_local_worker_tool_names(domain))
    operations.append(domain)
    from scidiscovery.operation_declaration import RESEARCH_WORK_CONTEXT
    from scidiscovery.operations.invoke import operation_port_json_schema
    for operation_id in ("science.experiment.design.v1", "science.experiment.revise.v1",
                         "science.object.review.v1", "tcad.deck.author.initial.v1", "tcad.deck.review.v1",
                         "science.result.diagnose.v1", "tcad.result.analyze.v1"):
        item = catalog.operation(operation_id)
        prompt = item.spec.executor.prompt
        key = f"{prompt.plugin_id or item.plugin_id}:{prompt.component_id}"
        assert RESEARCH_WORK_CONTEXT in item.implementations[key]
        inputs = {port.name: port for port in item.spec.inputs}
        assert inputs["current_progress"].usage == "evidence_inventory"
        if "experiment_review" in inputs:
            assert inputs["experiment_review"].exposure == "on_demand"
            assert "experiment_review" in item.spec.outputs[0].context_sources
    author = catalog.operation("tcad.deck.author.initial.v1")
    schema = operation_port_json_schema(author, author.spec.outputs[0])
    assert "ImplementationGap" in schema["$defs"] and author.spec.version == "2"
project = Path(tempfile.mkdtemp(prefix="installed-analysis-projection-"))
(project / "AGENTS.md").write_text("# Installed analysis projection\n")
initialize_platform(
    "codex", project, python_executable=Path(sys.executable),
    control_socket=project / "control.sock", worker_backend="local",
    operation_catalog=catalog,
)
for compiled in operations:
    assert compiled.spec.executor.native_tools.view_image
    profile = tomllib.loads((project / ".codex" / "agents" /
        (operation_agent_type(compiled) + ".toml")).read_text())
    server = profile["mcp_servers"][operation_worker_server_name(compiled)]
    assert set(server["enabled_tools"]) == set(operation_local_worker_tool_names(compiled))
    assert 'tool_contracts' in profile['developer_instructions']
    assert 'native view_image for task-local images' in profile['developer_instructions']
print("installed analysis projection verified")
''')


def test_installed_generic_score_runs_without_tcad(installed_probe):
    # Only serialized scientific fixture bytes cross into the isolated interpreter.
    from tests.operations.test_m2_curve_analysis_boundary import _inputs

    inputs = _inputs()
    request = {
        "sources": [{"input_alias": "curve_bundle", "format": "bundle"}],
        "comparison_spec": json.loads(inputs["curve_contract"])["comparison_spec"],
    }
    installed_probe("curve", "bundle_bytes = " + repr(inputs["curve_bundle"]) +
                    "\nrequest = " + repr(request) + r'''
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from curve_score.analysis_tool import replay_calculation
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools
assert importlib.util.find_spec("tcad_artifact") is None
compiled = compile_installed_catalog().operation("science.result.diagnose.v1")
tool = next(t for t in operation_worker_tools(compiled) if t.name == "worker_curve_score")
class Context:
    remaining_seconds = 120
    workspace = Path(tempfile.mkdtemp(prefix="installed-diagnostic-"))
    output_directory = workspace / "output"
    output_collections = ("tool_evidence", "recovery_manifest_output")
    saved = {}
    def finish_attempt(self, **values):
        return None
    def read_evidence(self, alias):
        assert alias == "curve_bundle"
        return bundle_bytes
    def accept_evidence(self, **values):
        assert values["derived_from"] == ("curve_bundle",)
        assert values["media_type"] in {"image/png", "application/json"}
        alias = f"tool_evidence_{len(self.saved) + 1:03d}"
        self.saved[alias] = values["raw"]
        return {"alias": alias}
record = tool.contextual_handler(tool.input_model(record_key="installed", request=request), Context())
assert record["status"] == "computed", record
assert record["result"]["aggregate_status"] == "fail"
assert json.loads(Context.saved[record["calculation_ref"]])["request"] == request
replay_calculation(CalculationRecord.model_validate(record), {"curve_bundle": bundle_bytes})
diagnostic_tool = next(t for t in operation_worker_tools(compiled) if t.name == "worker_curve_diagnose")
request["comparison_spec"]["comparisons"] = request["comparison_spec"]["comparisons"][:1]
request["comparison_spec"]["comparisons"][0]["operators"] = request["comparison_spec"]["comparisons"][0]["operators"][:1]
request["comparison_spec"]["comparisons"][0]["evaluation_points"] = 65
diagnostic = diagnostic_tool.contextual_handler(diagnostic_tool.input_model(record_key="installed_diagnostic", request=request), Context())
assert diagnostic["record"]["status"] == "computed", diagnostic
assert json.loads(Path(diagnostic["details"]["path"]).read_bytes())["localization"]["analyses"][0]["residual_trace"]
assert diagnostic["record"]["calculation_ref"] in Context.saved
assert Path(diagnostic["images"][0]["path"]).read_bytes().startswith(b"\x89PNG")
assert not any(name.startswith("tcad_artifact") for name in sys.modules)
print("installed generic score and residual diagnostic run without TCAD")
''')


def test_installed_hardened_open_contract_and_typed_edit_error(installed_probe):
    installed_probe('blind_csv', r'''
import json
import tempfile
from pathlib import Path
from blind_csv_plugin.plugin import PLUGIN as BLIND
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.interfaces.mcp import MCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import HardenedWorkerMCPRouter
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.operation_contract import DiagnosticError, contract_diagnostic
scratch = Path(tempfile.mkdtemp(prefix='installed-hardened-contract-'))
project = scratch / 'project'
project.mkdir()
runtime = open_runtime(project_root=project, state_root=scratch / 'state', worker_backend='hardened')
# Isolate the existing file-tool transport from the CSV review's native read
# requirement. This fixture does not claim that review runs on Hardened.
author, reviewer = BLIND.operations
fixture = BLIND.model_copy(update={'operations': (author.model_copy(update={'review': None}), reviewer)})
catalog = compile_catalog((CORE_PLUGIN, GENERAL, fixture))
runtime.runs.operation_catalog = catalog
instance = runtime.scheduler_bindings.create_instance(name='transport', title='Transport fixture', objective='Verify installed contract delivery.')
root = RootMCPRouter(RootToolFacade(runtime.artifacts, runtime.intake, runs=runtime.runs,
    approvals=runtime.approvals, executions=runtime.executions, bindings=runtime.scheduler_bindings,
    instance=instance.instance_id, operation_catalog=catalog))
source = runtime.artifacts.register(b'sample,value\na,1\nb,3\n', ArtifactRegistration(kind='fixture',
    schema_id='blind.opaque.v1', payload_schema_version=1, media_type='text/csv', creator=runtime.actor), idempotency_key='source')
runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name='source', object_id=source.artifact_id)
request = dict(name='transport', operation_id=author.operation_id, instruction='Read the exact file tool contracts.',
    inputs=[dict(port='source_table', artifact_names=['source'])])
assert root.call_tool('operation_preflight', request)['admissible']
root.call_tool('operation_invoke', request)
compiled = catalog.operation(author.operation_id)
worker = HardenedWorkerMCPRouter(runtime.runs, operation_id=author.operation_id, operation_digest=compiled.digest)
rpc = MCPRouter(worker, name='installed-hardened')
def call(name, arguments):
    return rpc.handle(dict(jsonrpc='2.0', id=1, method='tools/call', params=dict(name=name, arguments=arguments)))
opened = call('worker_open_assignment', {})['result']['structuredContent']
contracts = opened['tool_contracts']
assert contracts == json.loads(Path(opened['assignment_path']).read_bytes())['tool_contracts']
assert contracts == {tool['name']: {k: tool[k] for k in ('description', 'inputSchema')} for tool in worker.list_tools()}
detail = contract_diagnostic('declared_edit_failure', phase='tool_execution', affected_action='tool_call', message='The declared edit cannot be completed.')
def failed_edit(*args):
    raise DiagnosticError('typed edit error', details=(detail,))
worker._editor.chunk = failed_edit
assert call('worker_file_write_chunk', dict(content='{}'))['error']['data']['diagnostics'] == [detail]
print('installed Hardened contract and typed error verified')
''')


def test_installed_generic_no_score_worker_seals_failed_result(installed_probe):
    from tests.operations.test_m2_curve_analysis_boundary import _plan
    from tests.operations.test_result_analysis_tool import limited_report

    installed_probe("curve", "plan_bytes = " + repr(_plan().canonical_json()) +
                    "\nreport = " + repr(limited_report()) + r'''
import tempfile
from pathlib import Path
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.catalog import compile_installed_catalog
scratch = Path(tempfile.mkdtemp(prefix="installed-generic-analysis-"))
project = scratch / "project"
project.mkdir()
(project / "AGENTS.md").write_text("# Installed generic analysis fixture\n")
runtime = open_runtime(project_root=project, state_root=scratch / "state", worker_backend="local")
catalog = compile_installed_catalog()
instance = runtime.scheduler_bindings.create_instance(
    name="analysis", title="Installed no-score analysis", objective="Check bounded failed-result analysis.",
)
root = RootMCPRouter(RootToolFacade(
    runtime.artifacts, runtime.intake, runs=runtime.runs, approvals=runtime.approvals,
    executions=runtime.executions, bindings=runtime.scheduler_bindings,
    instance=instance.instance_id, operation_catalog=catalog,
))
def register(name, schema, raw, parents=()):
    artifact = runtime.artifacts.register(raw, ArtifactRegistration(
        kind="fixture", schema_id=schema, payload_schema_version=1,
        media_type="application/json", creator=runtime.actor, parent_refs=parents,
        labels={"scientific_claim_admissible": "true"},
    ), idempotency_key="installed-analysis:" + name)
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name=name, object_id=artifact.artifact_id)
    return artifact

def invoke(name, operation_id, inputs):
    request = {"name": name, "operation_id": operation_id, "inputs": [
        {"port": key, "artifact_names": [value]} for key, value in inputs.items()
    ], "instruction": "Analyze only exact bound fixture results."}
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    assert root.call_tool("operation_invoke", request)["result"]["state"] == "queued"
    compiled = catalog.operation(operation_id)
    worker = LocalWorkerMCPRouter(runtime.runs, operation_id=operation_id, operation_digest=compiled.digest)
    opened = worker.call_tool("worker_open_assignment", {})
    assert opened['tool_contracts'] == {tool['name']: {k: tool[k] for k in ('description', 'inputSchema')}
                                      for tool in worker.list_tools()}
    return worker, opened

def submit(worker, opened, payload, verdict):
    Path(opened["output_directory"], "result.json").write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": verdict, "summary": "Bounded fixture analysis."}, "payload": payload,
    }))
    result = worker.call_tool("worker_submit_result", {})
    assert result["state"] == "completed", result

plan = register("plan", "scidiscovery.experiment-portfolio.v1", plan_bytes)
worker, opened = invoke("review", "science.object.review.v1", {"experiment_plan": "plan"})
submit(worker, opened, {"review_target": "experiment_portfolio", "verdict": "pass", "summary": "Bounded fixture plan is coherent."}, "pass")
review = root.call_tool("run_status", {"name": "review"})
register("actual_result", "opaque", b"Execution failed before observable output.", (plan.ref,))
worker, opened = invoke("analysis", "science.result.diagnose.v1", {
    "experiment_plan": "plan", "experiment_review": review["output_artifact_name"], "experiment_results": "actual_result",
})
assert "worker_curve_score" in {item["name"] for item in worker.list_tools()}
submit(worker, opened, report, "blocked")
status = root.call_tool("run_status", {"name": "analysis"})
assert status["state"] == "completed"
assert status["sealed_output"]["payload"]["overall_verdict"] == "invalid_study"
assert not status["sealed_output"]["payload"]["calculation_records"]
print("installed generic failed-result analysis sealed without scoring")
''')


def test_installed_raw_tcad_worker_score_identity_and_submit_without_replay(installed_probe):
    import ast
    from tests.operations import test_tcad_result_analysis as fixtures
    from tests.operations.test_m2_curve_analysis_boundary import _contract, _diagnosis

    # Serialize fixture artifacts on the host; import every runtime implementation
    # in the child from its wheels. Reuse only test function text, never sys.path.
    materials = {}
    for mapped, state in ((True, "succeeded"), (True, "failed")):
        plan, package, manifest, plx, csv = fixtures.analysis_materials(mapped=mapped, state=state)
        materials[(mapped, state)] = (plan.canonical_json(), package.model_dump_json().encode(), manifest, plx, csv)
    source = Path(fixtures.__file__).read_text("utf-8")
    selected = {
        "analysis_system", "analysis_report", "raw_request", "open_analysis", "write_analysis",
        "test_raw_plx_csv_same_worker_score_and_submit",
        "test_failed_execution_zero_outputs_no_score_can_seal",
        "test_same_worker_rejects_wrong_name_case_or_score",
    }
    functions = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name in selected:
            text = ast.get_source_segment(source, node)
            text = text.replace("compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN))", "compile_installed_catalog()")
            text = text.replace("_CURVE['_diagnosis']().model_dump(mode='json')", "deepcopy(report_fixture)")
            text = text.replace("_CURVE['_contract']().comparison_spec.model_dump(mode='json')", "deepcopy(spec_fixture)")
            if node.name == 'open_analysis':
                text = text.replace('return worker,opened',
                    "assert opened['tool_contracts'] == json.loads(Path(opened['assignment_path']).read_bytes())['tool_contracts']\n"
                    "    assert opened['tool_contracts'] == {tool['name']: {k: tool[k] for k in ('description', 'inputSchema')} for tool in worker.list_tools()}\n"
                    "    return worker,opened")
            functions.append(text)
    assert len(functions) == len(selected)
    preamble = r'''
from copy import deepcopy
import json
import sys
import tempfile
from pathlib import Path
import scidiscovery.artifact_agent.service.runs as installed_runs
import tcad_artifact.result_analysis as installed_analysis
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.experiment import ExperimentPortfolio
from scidiscovery.operations.catalog import compile_installed_catalog
from tcad_artifact.project_packager import ReviewedDeckPackage
for module in (installed_runs, installed_analysis):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
def analysis_materials(*, mapped=True, state="succeeded"):
    plan, package, manifest, plx, csv = materials[(mapped, state)]
    return (ExperimentPortfolio.model_validate_json(plan, strict=True),
        ReviewedDeckPackage.model_validate_json(package, strict=True), manifest, plx, csv)
'''
    output = installed_probe("full", "materials = " + repr(materials) +
        "\nreport_fixture = " + repr(_diagnosis().model_dump(mode="json")) +
        "\nspec_fixture = " + repr(_contract().comparison_spec.model_dump(mode="json")) +
        preamble + "\n\n".join(functions) + r'''
scratch = Path(tempfile.mkdtemp(prefix="installed-raw-analysis-"))
def case(name):
    path = scratch / name
    path.mkdir()
    return path
test_raw_plx_csv_same_worker_score_and_submit(case("raw"))
test_failed_execution_zero_outputs_no_score_can_seal(case("failed"), "failed")
test_same_worker_rejects_wrong_name_case_or_score(case("name"), "name")
print("installed raw PLX/CSV Worker scoring and receipt submission verified without replay")
''')
    assert output.strip() == "installed raw PLX/CSV Worker scoring and receipt submission verified without replay"
