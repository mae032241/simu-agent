"""Native experiment delivery through real source entry points, without a solver."""
import json
import hashlib
from types import SimpleNamespace

import pytest

from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as SCIENCE_PLUGIN
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.general_science_experiment_task import validate_completion
from scidiscovery.operations.input_validation import InputBindingDescriptor, ValidationSources
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.operation_contract import SemanticRuleViolation


@pytest.fixture
def installed(monkeypatch):
    import scidiscovery.operations.catalog as compiler
    def set_plugins(plugins):
        class Entries(tuple):
            def select(self, **kwargs):
                assert kwargs == {"group": compiler.PLUGIN_ENTRY_POINT_GROUP}
                return self
        entries = Entries(SimpleNamespace(name=p.plugin_id, load=lambda p=p: p) for p in plugins)
        monkeypatch.setattr(compiler, "entry_points", lambda: entries)
        compile_installed_catalog.cache_clear()
    monkeypatch.delenv("SCID_AGENT_SETTINGS_FILE", raising=False)
    set_plugins((CORE_PLUGIN, SCIENCE_PLUGIN))
    yield set_plugins
    compile_installed_catalog.cache_clear()


def test_stage_source_rejects_bytes_that_differ_from_frozen_identity():
    import hashlib
    from scidiscovery.general_science_experiment_task import _read_stage_source
    context = SimpleNamespace(source_descriptor=lambda alias: SimpleNamespace(size_bytes=2, port_name="attachments",
        artifact_ref=SimpleNamespace(sha256=hashlib.sha256(b"{}").hexdigest())),
        read_evidence=lambda alias: b"[]", read_input=lambda alias: b"[]")
    with pytest.raises(SemanticRuleViolation, match="frozen original"):
        _read_stage_source(context, "attachment")


def _chain_sources():
    """Small exact receipt graph; bodies carry the same namespace as receipts."""
    def record(alias, kind, tool_name, **metadata):
        return {"alias": alias, "tool_name": tool_name, "metadata": {"kind": kind, **metadata}}
    records = [record("remote_impl", "experiment_implementation", "worker_experiment_prepare"),
        record("remote_exec", "experiment_execution", "worker_experiment_execute", implementation="remote_impl"),
        record("remote_valid", "experiment_stage", "worker_experiment_stage", stage="validity", derived_from=["remote_exec"]),
        record("code", "scientific_attachment", "worker_publish_files"),
        record("log", "scientific_attachment", "worker_publish_files"),
        record("result", "scientific_attachment", "worker_publish_files"),
        record("native_impl", "experiment_stage", "worker_experiment_stage", stage="implementation", derived_from=["code"]),
        record("native_exec", "experiment_stage", "worker_experiment_stage", stage="execution", origin="worker_native",
            execution_attestation="unavailable", implementation="native_impl", execution_state="succeeded", derived_from=["native_impl", "log", "result"]),
        record("native_valid", "experiment_stage", "worker_experiment_stage", stage="validity", derived_from=["native_exec"])]
    bodies = {"remote_exec": {"state": "collected", "terminal_state": "succeeded"},
        "native_impl": {"stage": "implementation", "conclusion": "Implemented.", "materials": ["code"]},
        "native_exec": {"stage": "execution", "conclusion": "Ran.", "native_execution": {
            "implementation": "native_impl", "state": "succeeded", "logs": ["log"], "results": ["result"]}}}
    for alias in ("remote_valid", "native_valid"):
        bodies[alias] = {"stage": "validity", "conclusion": "Assessed."}
    report = {"summary": "Mixed steps.", "outcome": "completed", "remaining_question": "",
        "adopted_stages": [r["alias"] for r in records if r["alias"] not in {"code", "log", "result"}]}
    return records, bodies, report


def _validated_sources(records, bodies, *, missing_original=None):
    """Bind real fixture bytes to their original published attachment receipts."""
    raw = {name: json.dumps(body).encode() for name, body in bodies.items()}
    raw.update(remote_impl=b'{"fixture":"remote implementation"}', code=b"print('fixture')\n",
               log=b"fixture execution completed\n", result=b'{"fixture_result":true}')
    refs = {name: ArtifactRef(artifact_id="art_" + name, sha256=hashlib.sha256(data).hexdigest(),
        kind="scientific_attachment" if name in {"code", "log", "result"} else "experiment_stage",
        schema_id="scidiscovery.fixture-native-chain.v1")
        for name, data in raw.items()}
    descriptors = {}
    for item in records:
        alias = item["alias"]
        if alias not in refs:
            continue  # Unadopted exploration is deliberately not a completed chain.
        item["artifact_ref"] = refs[alias].model_dump(mode="json")
        item["source_refs"] = {name: ref.model_dump(mode="json") for name, ref in refs.items()}
        attachment = item["metadata"]["kind"] == "scientific_attachment"
        item["output_port"] = "attachments" if attachment else "stage"
        descriptors[alias] = InputBindingDescriptor(source_name=alias, port_name="evidence",
            artifact_ref=refs[alias], media_type="application/octet-stream" if attachment else "application/json",
            size_bytes=len(raw[alias]), sha256=refs[alias].sha256)
    originals = {item["alias"]: item for item in records if item["alias"] != missing_original}
    return ValidationSources(raw, descriptors, tool_snapshot=json.dumps({"records": records}).encode(),
        sealed_material_resolver=originals.get)


@pytest.mark.parametrize("damage", (None, "wrong_version", "orphan", "running", "failed", "remote_running", "remote_failed", "missing_result", "fake_receipt", "ordinary_file", "missing_original", "unknown_provenance"))
def test_mixed_execution_checks_each_adopted_chain(damage):
    records, bodies, report = _chain_sources()
    native = next(r for r in records if r["alias"] == "native_exec")
    if damage == "wrong_version":
        native["metadata"]["implementation"] = "other_version"
    elif damage == "orphan":
        records[-1]["metadata"]["derived_from"] = ["remote_exec"]
    elif damage in {"running", "failed"}:
        bodies["native_exec"]["native_execution"]["state"] = damage
    elif damage == "remote_running":
        bodies["remote_exec"]["state"] = "running"
    elif damage == "remote_failed":
        bodies["remote_exec"]["terminal_state"] = "failed"
    elif damage == "missing_result":
        bodies["native_exec"]["native_execution"]["results"] = []
    elif damage == "fake_receipt":
        records[1]["tool_name"] = "worker_publish_files"
    elif damage == "ordinary_file":
        records[4]["tool_name"] = "worker_experiment_stage"
    elif damage == "unknown_provenance":
        records[3]["metadata"]["provenance_status"] = "unknown"
    sources = _validated_sources(records, bodies, missing_original="code" if damage == "missing_original" else None)
    if damage is None:
        validate_completion(report, sources, {})
    else:
        with pytest.raises(SemanticRuleViolation):
            validate_completion(report, sources, {})


def test_unadopted_exploration_does_not_require_a_chain():
    records, bodies, report = _chain_sources()
    records.append({"alias": "debug_exploration", "metadata": {"kind": "experiment_stage", "stage": "execution"}})
    sources = _validated_sources(records, bodies)
    validate_completion(report, sources, {})


# A second installed provider contributes the existing remote tools and executor.
# This tests selection/identity without installing or running a backend.
