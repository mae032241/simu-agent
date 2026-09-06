from __future__ import annotations

import json

import pytest


_EXPECTED_OPERATION_IDS = [
    "science.evidence.audit.intake.v1",
    "science.evidence.audit.v1",
    "science.evidence.extract.v1",
    "science.evidence.qualify.v1",
    "science.evidence.revise-from-critic.v1",
    "science.experiment.design.v1",
    "science.experiment.materialize.v1",
    "science.experiment.revise.v1",
    "science.hypothesis.criticize.v1",
    "science.hypothesis.propose.v1",
    "science.hypothesis.revise.v1",
    "science.intake.revise.v1",
    "science.intake.split.v1",
    "science.object.review.v1",
    "science.objective.project.v1",
]

_EXPECTED_CURVE_OPERATION_IDS = [
    "scidiscovery.curve-reference-coverage.v1",
    "scidiscovery.curve-score.v1",
    "scidiscovery.objective-coverage.v1",
]

_EXPECTED_CURVE_SCIENCE_OPERATION_IDS = [
    "science.curve.error.analyze.v1",
    "science.curve.contract.design.v1",
    "science.curve.contract.review.v1",
    "science.result.diagnose.curve-error.v1",
    "science.result.diagnose.v1",
]

_EXPECTED_FIGURE_OPERATION_IDS = [
    "scidiscovery.curve-bundle.figure-evidence.v2",
    "science.figure.request.prepare.v1",
    "science.figure.evidence.materialize.v1",
    "science.evidence.extract.figure.v2",
    "science.figure.evidence.audit.v1",
]

_EXPECTED_TCAD_PARAMETER_OPERATION_IDS = [
    "science.parameter.coverage.v1",
    "science.parameter.uncertainty.v1",
    "science.parameters.qualify.exception.v1",
    "science.parameters.qualify.pass.v1",
]


_DETECTOR_RESOURCE_PROBE = r'''
import json
from importlib.metadata import entry_points
from unittest.mock import patch

import curve_score.figure_science_operations as figure_contracts
from scidiscovery.operations.catalog import PLUGIN_ENTRY_POINT_GROUP, compile_catalog
from scidiscovery.operations.spec import ComponentRef, ComponentSpec

plugins = globals().get("plugins") or tuple(entry.load() for entry in sorted(
    entry_points(group=PLUGIN_ENTRY_POINT_GROUP), key=lambda entry: entry.name,
))
figure = next(plugin for plugin in plugins if plugin.plugin_id == "curve_figure_evidence")
request_id = "science.figure.request.prepare.v1"
materialize_id = "science.figure.evidence.materialize.v1"
request = next(op for op in figure.operations if op.operation_id == request_id)
materialize = next(op for op in figure.operations if op.operation_id == materialize_id)
context = request.outputs[0].context_validator
transform = materialize.executor.component
assert context is not None
assert context.plugin_id in (None, figure.plugin_id)
assert transform.plugin_id in (None, figure.plugin_id)
resource = ComponentRef("detector_contract_probe")
consumers = {context.component_id, transform.component_id}
variant = figure.model_copy(update={"components": tuple(
    component.model_copy(update={"resources": (*component.resources, resource)})
    if component.component_id in consumers else component
    for component in figure.components
) + (ComponentSpec(
    resource.component_id, "resource",
    "curve_score.figure_science_operations:DETECTOR_CONTRACT_PROBE",
),)})
assert sum(component.component_id in consumers for component in variant.components) == 2
variants = tuple(variant if plugin is figure else plugin for plugin in plugins)
contract = {"detector_version": "probe-v1", "ocr_model_sha256": "a" * 64}
catalogs = []
for payload in (contract, {**contract, "detector_version": "probe-v2"},
                {**contract, "ocr_model_sha256": "b" * 64}):
    content = json.dumps(payload, sort_keys=True).encode()
    # Only the in-memory resource bytes change; compiler and callables stay intact.
    with patch.object(figure_contracts, "DETECTOR_CONTRACT_PROBE", content, create=True):
        catalog = compile_catalog(variants)
        assert compile_catalog(variants).digest() == catalog.digest()
    for operation_id in (request_id, materialize_id):
        compiled = catalog.operation(operation_id)
        key = f"{figure.plugin_id}:{resource.component_id}"
        assert key in compiled.component_ids
        assert compiled.implementations[key] == content
    catalogs.append(catalog)
baseline = catalogs[0]
curve_ids = [op_id for op_id in baseline.operation_ids()
             if baseline.operation(op_id).plugin_id == "curve_score"]
assert curve_ids
for changed in catalogs[1:]:
    assert changed.operation_ids() == baseline.operation_ids()
    for operation_id in (request_id, materialize_id):
        assert changed.operation(operation_id).digest != baseline.operation(operation_id).digest
    for operation_id in curve_ids:
        assert changed.operation(operation_id).digest == baseline.operation(operation_id).digest
assert not hasattr(figure_contracts, "DETECTOR_CONTRACT_PROBE")
'''


def test_installed_detector_resource_uses_existing_compilation_edges(installed_probe) -> None:
    installed_probe("figure", _DETECTOR_RESOURCE_PROBE + r'''
import sys
from pathlib import Path
assert Path(figure_contracts.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert {plugin.plugin_id for plugin in plugins} == {
    "builtin", "general_science", "curve_score", "curve_figure_evidence",
}
''')


@pytest.mark.parametrize("environment", ("full", "figure"))
def test_installed_agent_input_and_checker_contracts_align(installed_probe, environment) -> None:
    output = installed_probe(environment, r'''
import importlib
from importlib.metadata import entry_points
from pathlib import Path
import sys
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operation_contract import operation_port_json_schema

for entry in entry_points(group="scidiscovery.plugins"):
    module = importlib.import_module(entry.value.split(":")[0])
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
catalog = compile_installed_catalog()
agents = []
for operation_id in catalog.operation_ids():
    compiled = catalog.operation(operation_id)
    if compiled.spec.executor.kind != "agent":
        continue
    agents.append(operation_id)
    inputs = {port.name: port for port in compiled.spec.inputs}
    for port in compiled.spec.outputs:
        schema = operation_port_json_schema(compiled, port)
        contract = schema["x-scidiscovery-validation-contract"]
        semantic = schema["x-scidiscovery-semantic-constraints"]
        rule_ids = {rule["rule_id"] for rule in semantic["rules"]}
        assert set(port.context_sources) <= inputs.keys()
        assert all(inputs[name].exposure in {"full", "on_demand"} for name in port.context_sources)
        for checker in contract["checkers"]:
            assert checker["rule_id"] in rule_ids
        assert {item["port"] for item in contract["context_sources"]} == set(port.context_sources)
design = catalog.operation("science.experiment.design.v1").spec
assert next(port for port in design.inputs if port.name == "critic_review").exposure == "full"
assert next(port for port in design.inputs if port.name == "scientific_foundation").exposure == "handoff_only"
objective = catalog.operation("science.objective.project.v1").spec
assert objective.inputs[0].required_non_null_fields == ("objective_contract",)
assert agents
print("installed contracts aligned")
''')
    assert output.strip() == "installed contracts aligned"


def test_installed_e52_core_and_tcad_contracts_are_packaged(installed_probe) -> None:
    output = installed_probe("full", r'''
import json
from jsonschema.validators import validator_for

from scidiscovery.artifact_agent.schema.research_objective import (
    ObjectiveClosureRequirement,
)
from scidiscovery.operations.catalog import compile_installed_catalog

schema = ObjectiveClosureRequirement.model_json_schema(mode="validation")
validator_type = validator_for(schema)
validator_type.check_schema(schema)
validator = validator_type(schema)
valid = {
    "requirement_key": "comparison",
    "description": "Require one exact comparison.",
    "requirement_type": "comparison_present",
    "comparison_purposes": ["target_fit"],
}
invalid = {
    "requirement_key": "comparison",
    "description": "Require one exact comparison.",
    "requirement_type": "comparison_present",
}
assert not tuple(validator.iter_errors(valid))
assert tuple(validator.iter_errors(invalid))
assert schema["properties"]["target_keys"]["uniqueItems"] is True
assert schema["properties"]["comparison_purposes"]["uniqueItems"] is True
assert schema["properties"]["validation_check_keys"]["uniqueItems"] is True

catalog = compile_installed_catalog()
audit = catalog.operation("science.evidence.audit.v1")
rules = json.loads(
    audit.implementations["general_science:evidence_audit_semantic_contract"]
)["rules"]
descriptions = "\n".join(rule["description"] for rule in rules)
assert "faithful to the exact sources" in descriptions
assert "not whether those sources are sufficient" in descriptions

extraction = catalog.operation("tcad.parameter.evidence.extract.v1")
usages = {port.name: port.usage for port in extraction.spec.inputs}
assert usages["required_parameter_checklist"] == "prior_signal"
assert usages["source_material"] == "evidence_inventory"
for operation_id in (
    "science.parameters.qualify.pass.v1",
    "science.parameters.qualify.exception.v1",
):
    assert catalog.operation(operation_id).spec.version == "2"
print("installed E5.2 core and TCAD contracts present")
''')
    assert output.strip() == "installed E5.2 core and TCAD contracts present"


def test_installed_e52_curve_contracts_are_packaged(installed_probe) -> None:
    output = installed_probe("figure", r'''
from curve_score.figure_digitization_contract import FigureLineTracking
from curve_score.figure_evidence_validation import VALIDATOR_VERSION
from scidiscovery.operations.catalog import compile_installed_catalog

assert VALIDATOR_VERSION == "6"
tracking = FigureLineTracking.model_json_schema(mode="validation")
legacy = tracking["properties"]["overdraw_candidate_endpoint_distance_px"]
assert legacy["default"] == 8.0
assert "deprecated" in legacy["description"].lower()

catalog = compile_installed_catalog()
audit = catalog.operation("science.figure.evidence.audit.v1")
prompt = audit.implementations["curve_figure_evidence:figure_audit_prompt"]
assert "not whether that family is sufficient" in prompt
assert "shared dependency" in prompt
print("installed E5.2 curve contracts present")
''')
    assert output.strip() == "installed E5.2 curve contracts present"


def test_installed_semantic_figure_compiler_includes_frozen_geometry(installed_probe) -> None:
    output = installed_probe("ingaas", r'''
import json
from importlib.resources import files
from ingaas_fig4.figure_compilation import GEOMETRY, OPERATION
from scidiscovery.operations.catalog import compile_installed_catalog
geometry_path = files("ingaas_fig4").joinpath("figure_geometry.json")
assert json.loads(geometry_path.read_text()) == json.loads(GEOMETRY)
assert json.loads(GEOMETRY)["source_sha256"] == "750c8cb5944ed9fe25c5072db084bb0194ed682d5e1ea40f25103f4aa89c05c3"
catalog = compile_installed_catalog()
assert catalog.operation(OPERATION.operation_id).spec.catalog_scope == "support"
selection = catalog.operation("science.figure.request.prepare.v1")
assert selection.spec.outputs[0].schema_id == "scidiscovery.figure-extraction-intent.v1"
assert selection.spec.outputs[0].name == "figure_intent"
print("installed semantic figure compiler and frozen geometry present")
''')
    assert output.strip() == "installed semantic figure compiler and frozen geometry present"


def test_installed_evidence_alias_schema_matches_local_worker_submit(
    installed_probe,
) -> None:
    installed_probe(
        "core",
        r'''
import json
import tempfile
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_local_worker import (
    LocalWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json

root_dir = Path(tempfile.mkdtemp(prefix="installed-e52-alias-"))
project = root_dir / "project"
project.mkdir()
(project / "AGENTS.md").write_text("# Installed E5.2 alias probe\n", encoding="utf-8")
runtime = open_runtime(
    project_root=project,
    state_root=root_dir / "state",
    worker_backend="local",
)
catalog = runtime.operation_catalog
instance = runtime.scheduler_bindings.create_instance(
    name="installed_e52_alias",
    title="Installed E5.2 source alias probe",
    objective="Prove one compiled source alias is visible and executable.",
)

foundation = canonical_json({
    "title": "Bounded foundation",
    "objective": "Audit one bounded premise.",
    "summary": "The premise is explicitly marked as an assumption.",
    "items": [{
        "item_key": "premise",
        "item_type": "assumption",
        "epistemic_status": "assumption",
        "statement": "The supplied line is the bounded context.",
        "scope": "Installed probe only.",
        "rationale": "The audit must remain tied to its frozen input.",
    }],
})

def register(name, content, *, kind, schema_id, media_type):
    artifact = runtime.artifacts.register(
        content,
        ArtifactRegistration(
            kind=kind,
            schema_id=schema_id,
            payload_schema_version=1,
            media_type=media_type,
            creator=runtime.actor,
        ),
        idempotency_key=f"installed-e52:{name}",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name=name,
        object_id=artifact.artifact_id,
    )

register(
    "foundation",
    foundation,
    kind="scientific_foundation",
    schema_id="scidiscovery.scientific-foundation.v1",
    media_type="application/json",
)
register(
    "paper_001",
    b"one bounded source line\n",
    kind="paper_source",
    schema_id="opaque",
    media_type="text/plain",
)
router = RootMCPRouter(
    RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    )
)
request = {
    "name": "audit",
    "operation_id": "science.evidence.audit.v1",
    "inputs": [
        {"port": "scientific_foundation", "artifact_names": ["foundation"]},
        {"port": "source_material", "artifact_names": ["paper_001"]},
    ],
    "instruction": "Audit only the exact bound source.",
}
assert router.call_tool("operation_preflight", request)["admissible"] is True
assert router.call_tool("operation_invoke", request)["result"]["state"] == "queued"
compiled = catalog.operation("science.evidence.audit.v1")
worker = LocalWorkerMCPRouter(
    runtime.runs,
    operation_id=compiled.spec.operation_id,
    operation_digest=compiled.digest,
)
opened = worker.call_tool("worker_open_assignment", {})
result_schema = json.loads(
    Path(opened["workspace_path"], "schema", "result.schema.json").read_text("utf-8")
)
source_key = result_schema["properties"]["payload"]["properties"]["evidence"][
    "items"
]["allOf"][-1]["properties"]["source_key"]
assert source_key["enum"] == ["source_material"]
# The workspace copy is only a Worker aid.  Expanding it must not expand the
# authoritative schema rebuilt by submit from the frozen Run binding.
source_key["enum"].append("invented_source")
schema_path = Path(opened["workspace_path"], "schema", "result.schema.json")
schema_path.chmod(0o600)
schema_path.write_bytes(canonical_json(result_schema))

def result(source_name):
    return canonical_json({
        "schema_version": 1,
        "handoff": {
            "verdict": "pass",
            "summary": "The bounded statement is faithful to the exact source.",
        },
        "payload": {
            "schema_version": 1,
            "checks": [{
                "check_key": "source_fidelity",
                "subject": "The statement remains bounded to the supplied line.",
                "status": "pass",
                "basis": "The exact frozen line is available.",
                "evidence_keys": [source_name],
            }],
            "evidence": [{
                "source_key": source_name,
                "source_type": "frozen_input",
                "locator": f"{source_name}:line-1",
            }],
        },
    })

output = Path(opened["output_directory"], "result.json")
output.write_bytes(result("invented_source"))
rejected = worker.call_tool("worker_submit_result", {})
assert rejected["state"] == "rejected"
assert {item["rule_id"] for item in rejected["diagnostics"]} == {"runtime.schema"}
assert router.call_tool("run_status", {"name": "audit"})["state"] == "running"

output.write_bytes(result("source_material"))
completed = worker.call_tool("worker_submit_result", {})
assert completed["state"] == "completed"
''',
    )


_INSTALLED_CURVE_TOOL_PROBE = r'''
import hashlib
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
import curve_score
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(curve_score.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
image = Image.new("RGB", (12, 12), "white")
ImageDraw.Draw(image).line([(1, 9), (9, 1)], fill="#ff0000", width=1)
stream = io.BytesIO()
image.save(stream, format="PNG")
class Context:
    def __init__(self):
        self.workspace = Path(tempfile.mkdtemp(prefix="installed-figure-"))
        self.source = self.workspace / "source.png"
        self.source.write_bytes(stream.getvalue())
        self.remaining_seconds = 30
        self.events = []
    def input_path(self, name):
        assert name == "paper_source"
        return self.source
    def input_media_type(self, name):
        assert name == "paper_source"
        return "image/png"
    def input_ref(self, name):
        assert name == "paper_source"
        return ArtifactRef(
            artifact_id="installed_source",
            sha256=hashlib.sha256(stream.getvalue()).hexdigest(),
            kind="paper_source",
            schema_id="opaque",
        )
    def record_activity(self, event): self.events.append(event)

tool = {
    item.name: item for item in operation_worker_tools(
        compile_installed_catalog().operation("science.figure.request.prepare.v1")
    )
}["worker_curve_figure_inspect_source"]
context = Context()
result = tool.contextual_handler(
    tool.input_model(),
    context,
)
assert len(result["images"]) == 1
assert Path(result["images"][0]["local_path"]).is_file()
assert result["images"][0]["access"] == "read_only"
assert context.events == ["deterministic_analysis_completed"]
'''


_INSTALLED_TCAD_TOOL_PROBE = r'''
import sys
from pathlib import Path

import tcad_artifact
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(tcad_artifact.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
tool = {
    item.name: item for item in operation_worker_tools(
        compile_installed_catalog().operation("tcad.deck.author.initial.v1")
    )
}["worker_tcad_debug_run"]
class Service:
    def run(self, context, *, run_name, mode):
        assert (run_name, mode) == ("probe", "preflight")
        return {"state": "completed", "scientific_claim_admissible": False}
class Context:
    def require_service(self, name):
        assert name == "tcad.development_debug"
        return Service()
result = tool.contextual_handler(
    tool.input_model(run_name="probe", mode="preflight"),
    Context(),
)
assert result == {"state": "completed", "scientific_claim_admissible": False}
'''


def test_clean_installed_core_compiles_only_the_single_plugin_group(installed_probe) -> None:
    output = installed_probe(
        "core",
        r'''
import importlib
from importlib.metadata import entry_points
import scidiscovery.builtin_plugin as builtin_plugin
from scidiscovery.operations.catalog import (
    PLUGIN_ENTRY_POINT_GROUP,
    compile_installed_catalog,
)

assert not hasattr(builtin_plugin, "ARCHITECTURE_TEST_PLUGIN")
for module_name in (
    "architecture_operation_test_plugin",
    "scidiscovery.artifact_agent.service.agent_dispatch",
    "scidiscovery.platforms.codex_worker",
):
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError(f"core-only install exposed {module_name}")

selected = tuple(sorted(
    entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP),
    key=lambda item: item.name,
))
assert [(item.name, item.value) for item in selected] == [
    ("builtin", "scidiscovery.builtin_plugin:CORE_PLUGIN"),
    ("general_science", "scidiscovery.general_science_plugin:PLUGIN"),
]
catalog = compile_installed_catalog()
assert compile_installed_catalog() is catalog
try:
    import scidiscovery.artifact_agent.schema.device_parameters  # noqa: F401
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("core-only install exposed the TCAD parameter schema")
assert not any("parameter" in item for item in catalog.operation_ids())
print("\n".join(catalog.operation_ids()))
''',
    )
    assert output.splitlines() == _EXPECTED_OPERATION_IDS


def test_architecture_operations_require_the_explicit_test_plugin(
    installed_probe,
) -> None:
    output = installed_probe(
        "architecture",
        r'''
from importlib.metadata import entry_points
from scidiscovery.operations.catalog import (
    PLUGIN_ENTRY_POINT_GROUP,
    compile_installed_catalog,
)

selected = tuple(sorted(
    entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP),
    key=lambda item: item.name,
))
assert [(item.name, item.value) for item in selected] == [
    (
        "architecture_fixture",
        "architecture_operation_test_plugin.plugin:ARCHITECTURE_TEST_PLUGIN",
    ),
    ("builtin", "scidiscovery.builtin_plugin:CORE_PLUGIN"),
    ("general_science", "scidiscovery.general_science_plugin:PLUGIN"),
]
catalog = compile_installed_catalog()
production_digests = {
    operation_id: catalog.operation(operation_id).digest
    for operation_id in catalog.operation_ids()
    if not operation_id.startswith("builtin.test.")
}
assert len(production_digests) == 15
print("\n".join(catalog.operation_ids()))
''',
    )
    assert output.splitlines() == [
        "builtin.test.agent",
        "builtin.test.effect",
        "builtin.test.transform",
        *_EXPECTED_OPERATION_IDS,
    ]


def test_architecture_plugin_does_not_change_production_operation_digests(
    installed_probe,
) -> None:
    source = r'''
import json
from scidiscovery.operations.catalog import compile_installed_catalog

catalog = compile_installed_catalog()
print(json.dumps({
    operation_id: catalog.operation(operation_id).digest
    for operation_id in catalog.operation_ids()
    if not operation_id.startswith("builtin.test.")
}, sort_keys=True))
'''
    core = json.loads(installed_probe("core", source))
    architecture = json.loads(installed_probe("architecture", source))
    assert len(core) == 15
    assert architecture == core


def test_codex_profiles_follow_the_installed_catalog_without_scope_filters(
    installed_probe,
) -> None:
    source = r'''
import json
import sys
import tempfile
from pathlib import Path

from scidiscovery.platforms import initialize_platform

root = Path(tempfile.mkdtemp(prefix="catalog-profile-"))
(root / "AGENTS.md").write_text("# Test\n", encoding="utf-8")
initialize_platform(
    "codex",
    root,
        python_executable=Path(sys.executable),
        control_socket=root / "control.sock",
                codex_config_root=root / ".codex",
)
print(json.dumps(sorted(
    path.stem for path in (root / ".codex" / "agents").glob("op_*.toml")
    if "builtin_test" in path.stem
)))
'''
    assert json.loads(installed_probe("core", source)) == []
    architecture_profiles = json.loads(installed_probe("architecture", source))
    assert len(architecture_profiles) == 1
    assert architecture_profiles[0].startswith("op_builtin_test_agent_")


def test_legacy_domain_entry_points_are_not_an_operation_discovery_fallback(
    installed_probe,
) -> None:
    output = installed_probe(
        "full",
        r'''
from scidiscovery.operations.catalog import compile_installed_catalog

catalog = compile_installed_catalog()
print("\n".join(catalog.operation_ids()))
''',
    )
    assert output.splitlines() == sorted([
        *_EXPECTED_CURVE_OPERATION_IDS,
        *_EXPECTED_CURVE_SCIENCE_OPERATION_IDS,
        *_EXPECTED_OPERATION_IDS,
        *_EXPECTED_TCAD_PARAMETER_OPERATION_IDS,
        "tcad.control-equivalence.v1",
        "tcad.curve-bundle.sprocess-log.v1",
        "tcad.curve-bundle.sprocess-plx.v1",
        "tcad.deck-project-compare.v1",
        "tcad.deck-review-validate.v1",
        "tcad.deck.author.initial.v1",
        "tcad.deck.author.revise.v1",
        "tcad.deck.author.runtime-failure.v1",
        "tcad.deck.review.v1",
        "tcad.parameter.evidence.audit.v1",
        "tcad.parameter.evidence.expand.v1",
        "tcad.parameter.evidence.extract.v1",
        "tcad.realization-snapshot-materialize.v1",
        "tcad.reviewed-deck-package.v2",
        "tcad.runtime-attestation.v1",
        "tcad.study.execute",
    ])


def test_clean_domain_wheel_matrix_has_exact_plugin_ownership(installed_probe) -> None:
    source = r'''
from importlib.metadata import entry_points
from scidiscovery.operations.catalog import PLUGIN_ENTRY_POINT_GROUP, compile_installed_catalog

catalog = compile_installed_catalog()
plugins = sorted(item.name for item in entry_points().select(group=PLUGIN_ENTRY_POINT_GROUP))
print(",".join(plugins))
print("\n".join(catalog.operation_ids()))
'''
    curve = installed_probe("curve", source).splitlines()
    assert curve[0] == "builtin,curve_score,general_science"
    assert set(curve[1:]) == {
        *_EXPECTED_OPERATION_IDS,
        *_EXPECTED_CURVE_OPERATION_IDS,
        *_EXPECTED_CURVE_SCIENCE_OPERATION_IDS,
    }
    assert not set(_EXPECTED_FIGURE_OPERATION_IDS) & set(curve[1:])
    figure = installed_probe("figure", source).splitlines()
    assert figure[0] == (
        "builtin,curve_figure_evidence,curve_score,general_science"
    )
    assert set(figure[1:]) == {
        *_EXPECTED_OPERATION_IDS,
        *_EXPECTED_CURVE_OPERATION_IDS,
        *_EXPECTED_CURVE_SCIENCE_OPERATION_IDS,
        *_EXPECTED_FIGURE_OPERATION_IDS,
    }
    table = installed_probe("table", source).splitlines()
    assert table[0] == "builtin,general_science,table_observation"
    assert set(table[1:]) == {
        *_EXPECTED_OPERATION_IDS,
        "science.table.observation.analyze.v1",
        "science.table.observation.review.v1",
    }
    tcad = installed_probe("tcad_resolved", source).splitlines()
    assert tcad[0] == "builtin,curve_score,general_science,tcad_artifact"
    assert "science.evidence.extract.figure.v1" not in tcad[1:]
    assert "tcad.curve-bundle.sprocess-plx.v1" in tcad[1:]


def test_clean_installed_domain_tools_execute_the_packaged_implementations(
    installed_probe,
) -> None:
    installed_probe("figure", _INSTALLED_CURVE_TOOL_PROBE)
    installed_probe(
        "table",
        r'''
import sys
from pathlib import Path

import table_observation
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_worker_tools

assert Path(table_observation.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
tool = {
    item.name: item for item in operation_worker_tools(
        compile_installed_catalog().operation("science.table.observation.analyze.v1")
    )
}["worker_table_summarize"]
class Context:
    def __init__(self): self.events = []
    def read_input(self, name):
        assert name == "observation_table"
        return b"sample,value\na,1\nb,3\n"
    def record_activity(self, event): self.events.append(event)
context = Context()
result = tool.contextual_handler(
    tool.input_model(),
    context,
)
assert result["rows"] == 2
assert result["numeric_columns"][0]["mean"] == 2.0
assert context.events == ["deterministic_analysis_completed"]
''',
    )
    installed_probe("tcad_resolved", _INSTALLED_TCAD_TOOL_PROBE)
    installed_probe("full", _INSTALLED_TCAD_TOOL_PROBE)


def test_clean_installed_pure_mcp_plugin_completes_a_hardened_run(
    installed_probe,
) -> None:
    installed_probe(
        "blind_csv",
        r'''
import json
import sys
import tempfile
import tomllib
from pathlib import Path

import blind_csv_plugin
from blind_csv_plugin.contracts import CSV_SCHEMA_PROBE
from scidiscovery.artifact_agent.interfaces.mcp_hardened_worker import (
    HardenedWorkerMCPRouter,
)
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.tooling import (
    operation_agent_type,
    operation_worker_server_name,
)
from scidiscovery.platforms import initialize_platform

assert Path(blind_csv_plugin.__file__).resolve().is_relative_to(
    Path(sys.prefix).resolve()
)
root = Path(tempfile.mkdtemp(prefix="installed-hardened-"))
project = root / "project"
project.mkdir()
(project / "AGENTS.md").write_text("# Installed Hardened probe\n", encoding="utf-8")
runtime = open_runtime(
    project_root=project,
    state_root=root / "state",
    worker_backend="hardened",
)
catalog = runtime.operation_catalog
compiled = catalog.operation("blind.csv.observe.v1")
instance = runtime.scheduler_bindings.create_instance(
    name="installed_hardened",
    title="Installed Hardened probe",
    objective="Complete one installed pure-MCP Operation through Hardened.",
)
raw = b"sample,value\na,1\nb,3\n"
source = runtime.artifacts.register(
    raw,
    ArtifactRegistration(
        kind="blind_csv_input",
        schema_id="blind.opaque.v1",
        payload_schema_version=1,
        media_type="text/csv",
        creator=runtime.actor,
    ),
    idempotency_key="installed:hardened:source",
)
runtime.scheduler_bindings.bind(
    instance=instance.instance_id,
    namespace="artifact",
    name="source_csv",
    object_id=source.artifact_id,
)
root_router = RootMCPRouter(
    RootToolFacade(
        runtime.artifacts,
        runtime.intake,
        runs=runtime.runs,
        approvals=runtime.approvals,
        executions=runtime.executions,
        bindings=runtime.scheduler_bindings,
        instance=instance.instance_id,
        operation_catalog=catalog,
    )
)
invoked = root_router.call_tool(
    "operation_invoke",
    {
        "name": "observation",
        "operation_id": compiled.spec.operation_id,
        "inputs": [
            {"port": "source_table", "artifact_names": ["source_csv"]}
        ],
        "instruction": "Make one bounded observation from the exact CSV.",
    },
)
assert invoked["result"]["state"] == "queued"

initialize_platform(
    "codex",
    project,
    python_executable=Path(sys.executable),
    control_socket=root / "control.sock",
    state_root=runtime.state_root,
    worker_backend="hardened",
    operation_catalog=catalog,
)
profile = tomllib.loads(
    project.joinpath(
        ".codex/agents", f"{operation_agent_type(compiled)}.toml"
    ).read_text(encoding="utf-8")
)
server = profile["mcp_servers"][operation_worker_server_name(compiled)]
assert server["args"][:2] == [
    "-m",
    "scidiscovery.artifact_agent.interfaces.mcp_hardened_worker",
]

worker = HardenedWorkerMCPRouter(
    runtime.runs,
    operation_id=compiled.spec.operation_id,
    operation_digest=compiled.digest,
)
opened = worker.call_tool("worker_open_assignment", {})
assert opened["write_protocol"] == "server_file_tools"
assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
assignment_tools = tuple(sorted(assignment["tools"]))
profile_tools = tuple(sorted(server["enabled_tools"]))
router_tools = tuple(sorted(item["name"] for item in worker.list_tools()))
assert assignment_tools == profile_tools == router_tools
structure = worker.call_tool("worker_csv_summarize", {})
assert structure["numeric_means"] == {"value": 2.0}
result = canonical_json(
    {
        "schema_version": 1,
        "handoff": {"verdict": "pass", "summary": "Bounded result."},
        "payload": {
            "schema_probe": CSV_SCHEMA_PROBE,
            "structure": structure,
            "interpretation": "The bounded arithmetic mean is two.",
            "limitations": ["Two rows do not establish causality."],
        },
    }
).decode("utf-8")
worker.call_tool(
    "worker_file_write_begin",
    {"relative_path": "output/result.json", "operation": "create"},
)
worker.call_tool("worker_file_write_chunk", {"content": result})
worker.call_tool("worker_file_write_commit", {})
assert worker.call_tool("worker_submit_result", {})["state"] == "completed"
status = root_router.call_tool("run_status", {"name": "observation"})
assert status["state"] == "completed"
assert status["backend"] == "hardened_worker"
assert status["output_artifact_name"] == "observation.output"
''',
    )


def test_installed_component_import_failure_has_a_stable_reason_code(
    installed_probe,
) -> None:
    installed_probe(
        "broken",
        r'''
from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

try:
    compile_installed_catalog()
except CatalogCompileError as error:
    assert error.reason_code == "component_implementation_error", error
    assert error.plugin_id == "broken", error
    assert error.field == "broken_transform", error
else:
    raise AssertionError("the installed broken plugin unexpectedly compiled")
''',
    )


def test_installed_invalid_unicode_resource_has_a_stable_reason_code(
    installed_probe,
) -> None:
    installed_probe(
        "invalid_unicode",
        r'''
from scidiscovery.operations.catalog import CatalogCompileError, compile_installed_catalog

try:
    compile_installed_catalog()
except CatalogCompileError as error:
    assert error.reason_code == "component_resource_digest_invalid", error
    assert error.plugin_id == "invalid_unicode", error
    assert error.field == "invalid_resource", error
else:
    raise AssertionError("the installed invalid-unicode plugin unexpectedly compiled")
''',
    )
