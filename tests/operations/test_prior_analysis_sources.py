"""An old alias is a replay locator, never a current input identity."""
from dataclasses import replace
import hashlib
import json

import pytest

from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.input_validation import (
    InputBindingDescriptor, ValidationSources, prior_analysis_sources, OperationInvocationError,
)


def bindings(*, fallback=False, legacy=False,
             raw=b"same bytes, distinct identity is possible", previous=b"{}"):
    def ref(name, raw, schema="opaque"):
        return ArtifactRef(artifact_id=name, schema_id=schema, kind="evidence",
                           sha256=hashlib.sha256(raw).hexdigest())
    original = ref("artifact_original", raw)
    copy = ref("artifact_copy", raw)
    payload = {"schema_version":1,"records":[]}
    if legacy:
        payload["records"] = [{"alias":"old_curve","artifact_ref":original.model_dump(mode="json")}]
    else:
        payload["bindings"] = {
            "old_curve":{"artifact_ref":original.model_dump(mode="json"),"port_name":"solver_outputs"}}
    manifest = canonical_json(payload)
    proof = ref("artifact_proof", manifest, "scidiscovery.tool-evidence-manifest.v1")
    prior = ref("artifact_prior", previous, "scidiscovery.layered-diagnosis.v1")
    def desc(alias, port, identity, payload, parents=(), producer=None, labels=()):
        return InputBindingDescriptor(alias, port, identity, "application/json", len(payload),
            identity.sha256, parent_refs=parents, labels=labels, producer_run_id=producer)
    port = "recovery_manifest" if fallback else "prior_analysis_manifest"
    sources = {"previous":previous, "proof":manifest, "new_curve":raw, "old_curve":raw}
    descriptors = {
        "previous":desc("previous","prior_analysis",prior,previous,(proof,),"run_prior"),
        "proof":desc("proof",port,proof,manifest,(original,),"run_prior",(("operation_output_port","recovery_manifest_output"),)),
        "new_curve":desc("new_curve","solver_outputs",original,raw),
        "old_curve":desc("old_curve","solver_outputs",copy,raw),
    }
    return sources, descriptors


def replace_manifest(contents, descriptors, payload):
    raw = canonical_json(payload)
    old = descriptors["proof"]
    digest = hashlib.sha256(raw).hexdigest()
    identity = old.artifact_ref.model_copy(update={"sha256":digest})
    contents["proof"] = raw
    descriptors["proof"] = replace(old, artifact_ref=identity, sha256=digest, size_bytes=len(raw))
    descriptors["previous"] = replace(descriptors["previous"], parent_refs=(identity,))


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("legacy", [False, True])
def test_exact_prior_proof_maps_identity_without_alias_collision(fallback, legacy):
    contents, descriptors = bindings(fallback=fallback, legacy=legacy)
    sources = ValidationSources(contents, descriptors)
    projection = prior_analysis_sources(sources)
    assert projection["manifest_alias"] == "proof"
    assert sources.prior_source_bindings == {"old_curve":"new_curve"}
    assert sources.binding_descriptors["old_curve"].artifact_ref != sources.binding_descriptors["new_curve"].artifact_ref
    assert set(sources) == set(contents)
    with pytest.raises(TypeError):
        sources.prior_source_bindings["old_curve"] = "old_curve"


@pytest.mark.parametrize("defect", ["producer", "parent", "missing_producer", "port",
                                     "missing_prior", "missing_manifest", "unproven_binding",
                                     "explicit_mismatch"])
@pytest.mark.parametrize("legacy", [False, True])
def test_wrong_pair_never_falls_back_or_matches_only_digest(defect, legacy):
    contents, descriptors = bindings(legacy=legacy)
    if defect == "producer":
        descriptors["proof"] = replace(descriptors["proof"], producer_run_id="another_run")
    elif defect == "parent":
        descriptors["previous"] = replace(descriptors["previous"], parent_refs=())
    elif defect == "missing_producer":
        descriptors["previous"] = replace(descriptors["previous"], producer_run_id=None)
    elif defect == "port":
        descriptors["proof"] = replace(descriptors["proof"], labels=())
    elif defect == "missing_prior":
        descriptors.pop("previous")
    elif defect == "missing_manifest":
        descriptors.pop("proof")
        contents.pop("proof")
    elif defect == "unproven_binding":
        descriptors["proof"] = replace(descriptors["proof"], parent_refs=())
    else:
        descriptors["fallback"] = replace(descriptors["proof"], source_name="fallback", port_name="recovery_manifest")
        contents["fallback"] = contents["proof"]
        descriptors["proof"] = replace(descriptors["proof"], producer_run_id="another_run")
    with pytest.raises(OperationInvocationError) as rejected:
        prior_analysis_sources(ValidationSources(contents, descriptors))
    message = rejected.value.details[0]["message"]
    expected = {
        "producer": "same_producer", "parent": "direct_parent",
        "missing_producer": "prior_producer", "port": "recovery_output_port",
        "missing_prior": "prior analysis primary", "missing_manifest": "direct recovery manifest",
        "unproven_binding": "not its direct parent", "explicit_mismatch": "same_producer",
    }[defect]
    assert expected in message




@pytest.mark.parametrize("defect", ["explicit_empty_bindings", "incomplete_identity", "missing_alias"])
def test_legacy_records_cannot_supply_a_missing_or_overridden_identity(defect):
    contents, descriptors = bindings(legacy=True)
    manifest = json.loads(contents["proof"])
    if defect == "explicit_empty_bindings":
        manifest["bindings"] = {}
    elif defect == "incomplete_identity":
        manifest["records"][0]["artifact_ref"].pop("artifact_id")
    else:
        manifest["records"][0].pop("alias")
    replace_manifest(contents, descriptors, manifest)
    assert ValidationSources(contents, descriptors).prior_source_bindings == {}


def test_legacy_conflicting_record_aliases_are_rejected():
    contents, descriptors = bindings(legacy=True)
    manifest = json.loads(contents["proof"])
    copy = descriptors["old_curve"].artifact_ref
    manifest["records"].append({"alias":"old_curve", "artifact_ref":copy.model_dump(mode="json")})
    replace_manifest(contents, descriptors, manifest)
    descriptors["proof"] = replace(descriptors["proof"], parent_refs=(descriptors["new_curve"].artifact_ref, copy))
    with pytest.raises(OperationInvocationError, match="prior_manifest_binding_mismatch") as rejected:
        prior_analysis_sources(ValidationSources(contents, descriptors))
    assert "conflicting exact artifacts" in rejected.value.details[0]["message"]


@pytest.mark.parametrize("legacy", [False, True])
def test_shared_original_recovery_uses_frozen_port_not_alias_order(legacy):
    contents, descriptors = bindings(legacy=legacy)
    descriptors["context"] = replace(descriptors["new_curve"], source_name="context", port_name="user_context")
    contents["context"] = contents["new_curve"]
    if legacy:
        # Old receipts lack a port: do not guess between multiple exact matches.
        with pytest.raises(OperationInvocationError, match="input_artifact_duplicate"):
            prior_analysis_sources(ValidationSources(contents, descriptors))
    else:
        assert ValidationSources(contents, descriptors).prior_source_bindings == {"old_curve": "new_curve"}


def test_recovered_calculation_resolves_shared_original_by_receipt_port():
    from scidiscovery.artifact_agent.service.calculation_proof import ControlledCalculationRecord
    from scidiscovery.artifact_agent.service.tool_evidence import calculation_sources
    contents, descriptors = bindings()
    original = descriptors["new_curve"]
    record = ControlledCalculationRecord(record_key="interrupted", request={}, algorithm_version="fixture-v1",
        status="error", reason_code="interrupted", input_digests={"old_curve": original.sha256},
        attempt={"manifest_alias": "tool_recovery_manifest", "attempt_key": "attempt", "proof_kind": "recovery"})
    proof = {"recovery": {"source_request_digest": "0" * 64, "operation_digest": "0" * 64,
        "draft_digest": "0" * 64, "bindings": {"old_curve": {
            "artifact_ref": original.artifact_ref.model_dump(mode="json"), "port_name": "solver_outputs"}},
        "attempts": [{"attempt_key": "attempt", "tool_name": "fixture", "operation_digest": "0" * 64,
            "request_digest": hashlib.sha256(canonical_json({})).hexdigest(), "state": "interrupted",
            "read_sources": ["old_curve"]}]}}
    sources = ValidationSources({"context": contents["new_curve"], "new_curve": contents["new_curve"]},
        {"context": replace(original, source_name="context", port_name="user_context"), "new_curve": original},
        tool_snapshot=canonical_json(proof))
    recovered = calculation_sources(record, sources)
    assert recovered.binding_descriptors["old_curve"].port_name == "solver_outputs"
    assert recovered["old_curve"] == contents["new_curve"]
