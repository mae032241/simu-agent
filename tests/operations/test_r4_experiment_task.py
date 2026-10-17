"""Bounded source regressions for the complete experiment's compiled entry."""
from scidiscovery.operations.catalog import compile_catalog


def test_complete_experiment_compiles_with_one_domain_provider(monkeypatch):
    import scidiscovery.operations.catalog as compiler
    original = compiler._build_compiled_catalog
    def assert_reachable(*args):
        unused = [key for key, value in args[1].items() if key not in args[-1] and not value.spec.public]
        assert not unused, "Unreferenced declarations: " + ", ".join(unused)
        return original(*args)
    monkeypatch.setattr(compiler, "_build_compiled_catalog", assert_reachable)
    from scidiscovery.builtin_plugin import CORE_PLUGIN as builtin
    from scidiscovery.general_science_plugin import PLUGIN as science
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_score.plugin import PLUGIN as curve
    catalog = compile_catalog((builtin, science, curve, tcad))
    experiment = catalog.operation("science.experiment.v1")
    assert experiment.spec.executor.capability.plugin_id == "tcad_artifact"
    assert {tool.name for tool in experiment.worker_tools} >= {
        "worker_experiment_stage", "worker_experiment_prepare", "worker_experiment_execute"}
    assert experiment.spec.review is None
    assert {port.name for port in experiment.spec.inputs} == {
        "subject", "hypothesis_portfolio", "objective_source", "scientific_materials", "prior_experiment", "scientific_files", "user_context"}
    assert next(p for p in experiment.spec.inputs if p.name == "objective_source").derivation is not None


def test_completed_experiment_requires_linked_control_observations():
    import json
    import pytest
    from scidiscovery.general_science_experiment_task import validate_completion
    from scidiscovery.operations.input_validation import ValidationSources
    from scidiscovery.operation_contract import SemanticRuleViolation
    payload = dict(summary="Result", outcome="completed", limitations=[], remaining_question="", adopted_stages=[])
    def sources(records):
        return ValidationSources({"execution": b'{"state":"collected","terminal_state":"succeeded"}'}, {},
            tool_snapshot=json.dumps({"records": records}).encode())
    with pytest.raises(SemanticRuleViolation, match="collected execution"):
        validate_completion(payload, sources([]), {})
    records = [
        {"alias": "implementation", "metadata": {"kind": "experiment_implementation"}},
        {"alias": "execution", "tool_name": "worker_experiment_execute", "metadata": {"kind": "experiment_execution", "implementation": "implementation"}},
        {"alias": "validity", "metadata": {"kind": "experiment_stage", "stage": "validity", "derived_from": ["execution"]}},
    ]
    payload["adopted_stages"] = [r["alias"] for r in records]
    validate_completion(payload, sources(records), {})
    records[1]["metadata"]["implementation"] = "different_implementation"
    with pytest.raises(SemanticRuleViolation):
        validate_completion(payload, sources(records), {})
    payload.update(outcome="blocked", adopted_stages=[])
    validate_completion(payload, sources([]), {})


import pytest


def test_debug_recovery_cancellation_preserves_original_budget(tmp_path):
    import json
    from types import SimpleNamespace
    from tcad_artifact.local_debug_service import LocalTCADDebugService, _record_key
    from scidiscovery.artifact_agent.schema.common import canonical_sha256
    subject = "control-goal-subject"
    calls = []
    adapter = SimpleNamespace(lookup_submission=lambda descriptor: ("external_debug", "running"),
        status=lambda external: "running",
        cancel=lambda external: calls.append(external) or "cancelled")
    service = LocalTCADDebugService(adapter=adapter, exchange_root=tmp_path)
    directory = tmp_path / "budgets"
    directory.mkdir()
    path = directory / (canonical_sha256({"subject":subject}) + ".json")
    record = {"run_id":"original_run", "run_name":"debug", "state":"accepted", "external_run_id":None}
    ledger = {"schema_version":2, "reserved_wall_seconds":30, "runs":{}, "reservations":{_record_key("original_run", "debug"):{
        "record":record, "submission":{"schema_version":1, "name":"submitted", "local_path":"/private/submission",
        "sha256":"b"*64, "size_bytes":1, "media_type":"application/json"}}}}
    path.write_text(json.dumps(ledger))
    inputs = subject
    assert not service.experiment_activity({"unrelated_run"}, inputs, cancel=True)
    assert calls == []
    assert service.experiment_activity({"original_run", "recovered_run"}, inputs)
    assert json.loads(path.read_text()) == ledger
    assert not service.experiment_activity({"original_run", "recovered_run"}, inputs, cancel=True)
    after = json.loads(path.read_text())
    assert after["reserved_wall_seconds"] == 30 and after["reservations"] == ledger["reservations"]
    assert calls == ["external_debug"]
    assert not service.experiment_activity({"original_run", "recovered_run"}, inputs, cancel=True)
    assert calls == ["external_debug"]


def test_scientific_implementation_and_package_share_constraints():
    import json
    import pytest
    from pydantic import ValidationError
    from tcad_artifact.experiment_capability import Implementation
    from tcad_artifact.project_packager import DeckProjectDraft
    public = Implementation.model_json_schema()
    private = DeckProjectDraft.model_json_schema()
    for name in ("entrypoint", "files", "arguments", "input_slots", "resource_limits"):
        assert public["properties"][name] == private["properties"][name]
    assert not {"tool_profile", "capability_sha256", "schema_version", "expected_outputs", "collect_generated_outputs"}.intersection(public["properties"])
    source = dict(solver_kind="sdevice", files=[{"relative_path":"main.cmd","content":"# standalone"}],
        entrypoint="main.cmd", resource_limits=dict(wall_time_seconds=1,cpu_time_seconds=1,
        max_memory_bytes=1024,max_output_bytes=1024,max_storage_bytes=1024))
    for change in ({"entrypoint":""}, {"entrypoint":"absent.cmd"},
        {"entrypoint":"main.txt","files":[{"relative_path":"main.txt","content":"# invalid direct entrypoint"}]},
        {"arguments":["x"]*257},
        {"input_slots":[{"semantic_name":"grid","target_relative_path":"grid.tdr","media_type":"application/octet-stream"}]*4097},
        {"expected_outputs":[{"name":"observation","relative_path":"out.txt","media_type":"text/plain","max_bytes":1}]*4097}):
        value = {**source,**change}
        for model, extra in ((Implementation,{}),(DeckProjectDraft,{"tool_profile":"configured", "capability_sha256":"a"*64})):
            with pytest.raises(ValidationError):
                model.model_validate_json(json.dumps({**value,**extra}),strict=True)


def test_execution_package_version_is_declared_and_enters_identity(monkeypatch):
    from dataclasses import replace
    from scidiscovery.builtin_plugin import CORE_PLUGIN
    from scidiscovery.general_science_plugin import PLUGIN as science
    from tcad_artifact.plugin import PLUGIN as tcad
    from curve_score.plugin import PLUGIN as curve
    import tcad_artifact.experiment_capability as provider
    declared = provider.CAPABILITY
    assert declared.execution_package_schema_version == 2
    digests = []
    for version in (1, 2, 3):
        monkeypatch.setattr(provider, 'CAPABILITY', replace(declared, execution_package_schema_version=version))
        catalog = compile_catalog((CORE_PLUGIN, science, curve, tcad))
        operation = catalog.operation('science.experiment.v1')
        digests.append(operation.digest)
        capability = operation.implementations['tcad_artifact:experiment_capability']
        assert capability.execution_package_schema_version == version
    assert len(set(digests)) == 3
