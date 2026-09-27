from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from architecture_operation_test_plugin.plugin import ARCHITECTURE_TEST_PLUGIN
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.invoke import BoundInput, BoundOperationCall, InvocationArtifact


def _running_candidate(tmp_path, monkeypatch, checker):
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project, state_root=tmp_path / "state", worker_backend="local",
        local_workspace_root=project / ".runs",
    )
    agent = ARCHITECTURE_TEST_PLUGIN.operations[0]
    visible = agent.inputs[0].model_copy(update={"max_items": 2})
    hidden = visible.model_copy(update={"name": "hidden", "exposure": "handoff_only", "max_items": 1})
    plugin = ARCHITECTURE_TEST_PLUGIN.model_copy(update={"operations": (
        agent.model_copy(update={"inputs": (visible, hidden)}),
        *ARCHITECTURE_TEST_PLUGIN.operations[1:],
    )})
    catalog = compile_catalog((plugin,))
    runtime.runs.operation_catalog = catalog
    compiled = catalog.operation("builtin.test.agent")
    instance = runtime.scheduler_bindings.create_instance(
        name="metadata", title="Metadata", objective="Check exact input descriptors.",
    )
    envelopes = []
    bindings = []
    for name, port in (("a", "agent_input"), ("b", "agent_input"), ("secret", "hidden")):
        envelope = runtime.artifacts.register(
            b"{}", ArtifactRegistration(
                kind="fixture_input", schema_id=visible.schema_id, payload_schema_version=1,
                media_type="application/json", creator=runtime.actor,
                labels={"logical_name": name, "private_label": "not exposed"},
            ), idempotency_key=f"metadata:{name}",
        )
        envelopes.append(envelope)
        runtime.scheduler_bindings.bind(
            instance=instance.instance_id, namespace="artifact", name=name,
            object_id=envelope.artifact_id,
        )
        bindings.append(BoundInput(
            port_name=port, source_name=name, artifact_name=name,
            artifact=InvocationArtifact(
                artifact_name=name, ref=envelope.ref, schema_id=envelope.schema_id,
                media_type=envelope.media_type, size_bytes=envelope.size_bytes,
            ), exposure="handoff_only" if port == "hidden" else visible.exposure,
            usage=visible.usage,
        ))
    run_id = runtime.runs.schedule(
        BoundOperationCall(compiled, "metadata", tuple(bindings), "Verify metadata."),
        instance_id=instance.instance_id, output_binding_name="metadata.output",
        output_logical_name="metadata.output", output_revision=1,
        output_binding_fingerprint="a" * 64,
    )
    _, workspace = runtime.runs.open(operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    (workspace.root / "output/result.json").write_bytes(canonical_json({
        "schema_version": 1, "handoff": {"verdict": "pass", "summary": "Checked inputs."},
        "payload": {"input_seen": True, "network_denied": True, "sibling_read_denied": True,
                    "tool_result": "fixture-inspected:registered-domain-tool"},
    }))
    implementations = dict(compiled.implementations)
    implementations["architecture_fixture:context_validator"] = checker
    patched = replace(compiled, implementations=implementations)
    monkeypatch.setattr(runtime.runs, "_compiled", lambda value: patched)
    return runtime, run_id, envelopes


@pytest.mark.parametrize("entry", ["candidate", "submit"])
def test_run_service_supplies_exact_filtered_descriptors(tmp_path: Path, monkeypatch, entry):
    seen = []

    def checker(payload, sources, handoff):
        seen.append(sources)

    runtime, run_id, envelopes = _running_candidate(tmp_path, monkeypatch, checker)
    if entry == "candidate":
        runtime.runs.validate_candidate(run_id)
    else:
        assert runtime.runs.submit(run_id) == ("completed", ())
    assert len(seen) == 1
    sources = seen[0]
    assert isinstance(sources, dict)
    assert sources == {"a": b"{}", "b": b"{}"}
    assert hasattr(sources, "binding_descriptors"), "RunService discards exact input identity before context validation"
    assert isinstance(sources.validation_deadline, float)
    descriptors = sources.binding_descriptors
    assert set(descriptors) == set(sources)
    for name, envelope in zip(("a", "b"), envelopes):
        descriptor = descriptors[name]
        assert descriptor.source_name == name
        assert descriptor.port_name == "agent_input"
        assert descriptor.artifact_ref == envelope.ref
        assert descriptor.media_type == envelope.media_type
        assert descriptor.size_bytes == envelope.size_bytes
        assert descriptor.sha256 == envelope.sha256
        assert descriptor.output_name == name
    assert descriptors["a"].artifact_ref != descriptors["b"].artifact_ref
    assert descriptors["a"].sha256 == descriptors["b"].sha256


def test_descriptors_are_deeply_readonly_and_legacy_dict_reads_work(tmp_path, monkeypatch):
    from dataclasses import FrozenInstanceError
    from pydantic import ValidationError

    seen = []

    def legacy_checker(payload, sources, handoff):
        assert list(sources.keys()) == ["a", "b"]
        assert list(sources.items()) == [("a", b"{}"), ("b", b"{}")]
        assert sources.get("a") == b"{}"
        assert payload["input_seen"] and handoff["verdict"] == "pass"
        seen.append(sources)

    runtime, run_id, _ = _running_candidate(tmp_path, monkeypatch, legacy_checker)
    runtime.runs.validate_candidate(run_id)
    assert runtime.runs.submit(run_id) == ("completed", ())
    assert len(seen) == 2
    sources = seen[0]
    descriptor = sources.binding_descriptors["a"]
    with pytest.raises(TypeError):
        sources.binding_descriptors["a"] = descriptor
    with pytest.raises(AttributeError):
        sources.binding_descriptors = {}
    with pytest.raises(AttributeError):
        sources.validation_deadline = 0
    with pytest.raises(FrozenInstanceError):
        descriptor.output_name = "b"
    with pytest.raises(ValidationError):
        descriptor.artifact_ref.artifact_id = "replacement"
    assert seen[1].binding_descriptors == sources.binding_descriptors
    assert seen[1].binding_descriptors is not sources.binding_descriptors


@pytest.mark.parametrize("defect", ["missing", "ref", "media_type", "bytes", "size", "sha256"])
def test_registry_binding_faults_are_engineering_errors(tmp_path, monkeypatch, defect):
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError

    runtime, run_id, envelopes = _running_candidate(tmp_path, monkeypatch, lambda *args: None)
    original_catalog = runtime.artifacts.catalog
    original_read = runtime.artifacts.read

    def catalog(reference):
        if reference == envelopes[0].ref:
            if defect == "missing":
                raise LookupError("record missing")
            if defect == "ref":
                return envelopes[1]
            if defect in {"media_type", "size", "sha256"}:
                updates = {"media_type": "text/plain"} if defect == "media_type" else (
                    {"size_bytes": 999} if defect == "size" else {"sha256": "0" * 64}
                )
                return envelopes[0].model_copy(update=updates)
        return original_catalog(reference)

    monkeypatch.setattr(runtime.artifacts, "catalog", catalog)
    if defect == "bytes":
        monkeypatch.setattr(runtime.artifacts, "read", lambda reference: b"corrupt" if reference == envelopes[0].ref else original_read(reference))
    with pytest.raises(RunCheckerError):
        runtime.runs.validate_candidate(run_id)
    assert runtime.runs.status(run_id).state == "failed"
    assert runtime.runs.status(run_id).state == "failed"


@pytest.mark.parametrize("defect", ["missing", "alias", "port", "null"])
def test_descriptor_wiring_faults_fail_both_submission_paths(tmp_path, monkeypatch, defect):
    from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError

    runtime, run_id, _ = _running_candidate(tmp_path, monkeypatch, lambda *args: None)
    original_inputs = runtime.runs._validation_inputs

    def damaged_inputs(value):
        contents, descriptors = original_inputs(value)
        if defect == "missing":
            descriptors.pop("a")
        elif defect == "null":
            descriptors["a"] = None
        elif defect == "alias":
            descriptors["a"] = replace(descriptors["a"], source_name="b")
        else:
            descriptors["a"] = replace(descriptors["a"], port_name="hidden")
        return contents, descriptors

    monkeypatch.setattr(runtime.runs, "_validation_inputs", damaged_inputs)
    with pytest.raises(RunCheckerError):
        runtime.runs.validate_candidate(run_id)
    assert runtime.runs.status(run_id).state == "failed"


def test_reopened_run_keeps_exact_refs_after_same_content_registration(tmp_path, monkeypatch):
    seen = []
    runtime, run_id, envelopes = _running_candidate(
        tmp_path, monkeypatch, lambda payload, sources, handoff: seen.append(sources),
    )
    runtime.runs.validate_candidate(run_id)
    replacement = runtime.artifacts.register(
        b"{}", ArtifactRegistration(
            kind="fixture_input", schema_id="scidiscovery.architecture-test.v1", payload_schema_version=1,
            media_type="application/json", creator=runtime.actor,
            labels={"logical_name": "a"},
        ), idempotency_key="replacement:A",
    )
    assert replacement.ref != envelopes[0].ref
    compiled = runtime.runs._compiled(runtime.runs.status(run_id))
    status, _ = runtime.runs.reopen(operation_id=compiled.spec.operation_id, operation_digest=compiled.digest)
    assert status.run_id == run_id
    assert runtime.runs.submit(run_id) == ("completed", ())
    assert seen[0].binding_descriptors == seen[1].binding_descriptors
    assert seen[1].binding_descriptors["a"].artifact_ref == envelopes[0].ref


def test_missing_output_name_still_allows_context_validation(tmp_path, monkeypatch):
    seen = []
    runtime, run_id, _ = _running_candidate(
        tmp_path, monkeypatch, lambda payload, sources, handoff: seen.append(sources),
    )
    original_catalog = runtime.artifacts.catalog
    monkeypatch.setattr(runtime.artifacts, "catalog", lambda reference: original_catalog(reference).model_copy(update={"labels": {}}))
    runtime.runs.validate_candidate(run_id)
    assert runtime.runs.submit(run_id) == ("completed", ())
    assert all(item.output_name is None for sources in seen for item in sources.binding_descriptors.values())


def test_validation_sources_owns_its_descriptor_mapping(tmp_path, monkeypatch):
    from scidiscovery.artifact_agent.service.run_outputs import ValidationSources

    runtime, run_id, _ = _running_candidate(tmp_path, monkeypatch, lambda *args: None)
    contents, descriptors = runtime.runs._validation_inputs(runtime.runs.status(run_id))
    sources = ValidationSources(contents, descriptors)
    descriptors.clear()
    assert set(sources.binding_descriptors) == set(contents)


@pytest.mark.parametrize('wrong,port,relation', [
    ('package', 'runtime_manifest', 'execution_package'),
    ('manifest', 'runtime_manifest', 'execution_package'),
    ('diagnostics', 'diagnostics', 'execution_id'),
])
def test_analysis_input_relationship_error_survives_both_entry_points(tmp_path, wrong, port, relation):
    from copy import deepcopy
    from tests.operations.test_tcad_result_analysis import analysis_system
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    system = analysis_system(tmp_path)
    _, runtime, root, request, artifacts, register = system
    original = deepcopy(request)
    before_runs = root.call_tool('run_list', {})
    if wrong == 'review':
        register('other_plan', runtime.artifacts.read(artifacts['plan'].ref), artifacts['plan'].schema_id)
        next(i for i in request['inputs'] if i['port'] == 'experiment_plan')['artifact_names'] = ['other_plan']
    elif wrong == 'package':
        register('other_package', runtime.artifacts.read(artifacts['package'].ref), artifacts['package'].schema_id)
        next(i for i in request['inputs'] if i['port'] == 'execution_package')['artifact_names'] = ['other_package']
    elif wrong == 'manifest':
        register('other_manifest', runtime.artifacts.read(artifacts['manifest'].ref), 'opaque')
        next(i for i in request['inputs'] if i['port'] == 'runtime_manifest')['artifact_names'] = ['other_manifest']
    else:
        register('foreign_log', b'fixture failure', 'opaque', media='text/plain')
        request['inputs'].append(dict(port='diagnostics', artifact_names=['foreign_log']))
    rejected = root.call_tool('operation_preflight', request)
    assert rejected['admissible'] is False
    with pytest.raises(RootToolError) as error:
        root.call_tool('operation_invoke', request)
    assert error.value.details[0]['path'] == '$.inputs.' + port
    assert relation in error.value.details[0]['message']
    assert error.value.details[0] in rejected['diagnostics']
    assert root.call_tool('run_list', {}) == before_runs
    register('new_analysis_plan', runtime.artifacts.read(artifacts['plan'].ref), artifacts['plan'].schema_id)
    original['inputs'].append(dict(port='current_progress', artifact_names=['new_analysis_plan']))
    assert root.call_tool('operation_preflight', original)['admissible']


def test_analysis_assignment_projects_compiled_port_descriptions_and_deadline(tmp_path):
    import json
    from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    assignment = json.loads(Path(opened['assignment_path']).read_text())
    ports = {p.name: p.description for p in system[0].operation('tcad.result.analyze.v1').spec.inputs}
    assert assignment['budget']['deadline_at'] == system[1].runs.status(worker._run_id).deadline_at
    assert assignment['inputs']
    for item in assignment['inputs']:
        assert 'port' not in item  # Mechanical bindings stay inside control.
        assert item['description'] in ports.values()


def test_unexpected_guard_exception_remains_engineering_failure(tmp_path):
    from scidiscovery.operations.invoke import _run_guards
    from scidiscovery.operations.input_validation import OperationEngineeringError
    from tests.operations.test_tcad_result_analysis import analysis_system
    compiled = analysis_system(tmp_path)[0].operation('tcad.result.analyze.v1')
    implementations = dict(compiled.implementations)
    def broken(*args):
        raise ValueError('unexpected checker defect')
    implementations['tcad_artifact:result_analysis_parentage'] = broken
    with pytest.raises(OperationEngineeringError, match='guard_failed'):
        _run_guards(replace(compiled, implementations=implementations), (), {})
