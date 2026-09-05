from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN
from curve_score.plugin import PLUGIN as CURVE_PLUGIN
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.interfaces.mcp_root_shared import RootToolError
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL_PLUGIN
from scidiscovery.operations.catalog import compile_catalog

from tests.operations.test_curve_figure_digitization_tool import _request
from tests.operations.test_general_transform_operations import _intake


REQUEST = "science.figure.request.prepare.v1"
MATERIALIZE = "science.figure.evidence.materialize.v1"
EXTRACTION = "science.evidence.extract.figure.v2"
AUDIT = "science.figure.evidence.audit.v1"
BUNDLE = "scidiscovery.curve-bundle.figure-evidence.v2"


def _envelope(payload: object, *, verdict: str = "pass") -> bytes:
    return canonical_json(
        {
            "schema_version": 1,
            "handoff": {
                "verdict": verdict,
                "summary": "The exact bounded figure family was handled.",
            },
            "payload": payload,
        }
    )


def _system(tmp_path: Path):
    catalog = compile_catalog((CORE_PLUGIN, GENERAL_PLUGIN, CURVE_PLUGIN, FIGURE_PLUGIN))
    project = tmp_path / "project"
    project.mkdir()
    runtime = open_runtime(
        project_root=project,
        state_root=tmp_path / "state",
        approval_receipt_secret=os.urandom(32),
        worker_backend="local",
    )
    runtime.runs.operation_catalog = catalog
    instance = runtime.scheduler_bindings.create_instance(
        name="m5_figure_review",
        title="M5 figure review closure",
        objective="Require one exact independent audit before normalization.",
    )
    root = RootMCPRouter(
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
    return catalog, runtime, instance, root


def _register(runtime, instance, *, name: str, content: bytes, kind: str,
              schema_id: str, media_type: str, parent_refs=(), labels=None,
              supersedes_ref=None):
    envelope = runtime.artifacts.register(
        content,
        ArtifactRegistration(
            kind=kind,
            schema_id=schema_id,
            payload_schema_version=1,
            media_type=media_type,
            creator=runtime.actor,
            parent_refs=tuple(parent_refs),
            supersedes_ref=supersedes_ref,
            labels=labels or {},
        ),
        idempotency_key=f"m5-figure:{name}",
    )
    runtime.scheduler_bindings.bind(
        instance=instance.instance_id,
        namespace="artifact",
        name=name,
        object_id=envelope.artifact_id,
    )
    return envelope


def _complete_agent(catalog, runtime, root, *, operation_id: str, name: str,
                    inputs: list[dict[str, object]], payload: object,
                    verdict: str = "pass") -> str:
    request = {
        "name": name,
        "operation_id": operation_id,
        "inputs": inputs,
        "instruction": "Handle only the exact bound figure family.",
    }
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    root.call_tool("operation_invoke", request)
    compiled = catalog.operation(operation_id)
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    primary = next(port for port in compiled.spec.outputs if port.collection is None)
    if primary.evidence_paths and any(
        port.usage == "evidence_inventory" and port.exposure != "handoff_only"
        for port in compiled.spec.inputs
    ):
        assignment = json.loads(Path(opened["assignment_path"]).read_text("utf-8"))
        expected_sources = sorted(
            item["source_name"]
            for item in assignment["inputs"]
            if item["usage"] == "evidence_inventory"
        )
        envelope_schema = json.loads(
            Path(
                opened["workspace_path"], "schema", "result.schema.json"
            ).read_text("utf-8")
        )
        payload_schema = envelope_schema["properties"]["payload"]
        for evidence_path in primary.evidence_paths:
            assert _source_key_enum(payload_schema, evidence_path) == expected_sources
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(payload, verdict=verdict)
    )
    submitted = worker.call_tool("worker_submit_result", {})
    assert submitted["state"] == "completed", submitted
    return root.call_tool("run_status", {"name": name})["output_artifact_name"]


def _source_key_enum(schema: dict[str, object], pointer: str) -> list[str]:
    def resolve(value: object) -> dict[str, object]:
        assert isinstance(value, dict)
        reference = value.get("$ref")
        if reference is None:
            return value
        assert isinstance(reference, str) and reference.startswith("#/$defs/")
        target = schema["$defs"]
        assert isinstance(target, dict)
        resolved = target[reference.removeprefix("#/$defs/")]
        return resolve(resolved)

    current: object = schema
    for token in pointer.removeprefix("/").split("/"):
        properties = resolve(current)["properties"]
        assert isinstance(properties, dict)
        current = properties[token]
    items = resolve(current)["items"]
    assert isinstance(items, dict)
    all_of = items["allOf"]
    assert isinstance(all_of, list)
    projection = all_of[-1]
    assert isinstance(projection, dict)
    properties = projection["properties"]
    assert isinstance(properties, dict)
    source_key = properties["source_key"]
    assert isinstance(source_key, dict)
    values = source_key["enum"]
    assert isinstance(values, list)
    return values


def _intake_payload() -> dict[str, object]:
    value = _intake().model_dump(mode="json")
    value["scientific_foundation"]["evidence"] = [
        {
            "source_key": "figure_manifest",
            "source_type": "frozen_input",
            "title": "Deterministic figure manifest",
            "locator": "figure_manifest:exact",
        }
    ]
    for item in value["scientific_foundation"]["items"]:
        if item["epistemic_status"] in {"paper_fact", "user_definition", "runtime_observation"}:
            item["evidence_keys"] = ["figure_manifest"]
    return value


def _audit_payload(
    *,
    status: str = "pass",
    check_key: str = "figure_family",
    basis: str = "The source, request, manifest, report, panel, overlay and table agree.",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "checks": [
            {
                "check_key": check_key,
                "subject": "The Intake is bound to the exact validated family.",
                "status": status,
                "basis": basis,
                "evidence_keys": ["figure_manifest"],
            }
        ],
        "evidence": [
            {
                "source_key": "figure_manifest",
                "source_type": "frozen_input",
                "locator": "figure_manifest:exact",
            }
        ],
    }


def _bindings(names: dict[str, list[str]], *, include_intake: str | None = None,
              include_audit: str | None = None) -> list[dict[str, object]]:
    values = []
    if include_intake is not None:
        values.append({"port": "scientific_intake", "artifact_names": [include_intake]})
    if include_audit is not None:
        values.append({"port": "evidence_audit", "artifact_names": [include_audit]})
    values.extend(
        {"port": port, "artifact_names": artifacts}
        for port, artifacts in names.items()
    )
    return values


def _revision_bindings(
    names: dict[str, list[str]], *, prior_draft: str, change_request: str
) -> list[dict[str, object]]:
    return [
        *_bindings(names),
        {"port": "prior_draft", "artifact_names": [prior_draft]},
        {"port": "change_request", "artifact_names": [change_request]},
    ]


def _two_series_source_and_request(
    *, marker: int = 255
) -> tuple[bytes, dict[str, object]]:
    image = Image.new("RGB", (12, 12), "white")
    image.putpixel((0, 0), (marker, marker, marker))
    for x in range(1, 10):
        image.putpixel((x, 10 - x), (255, 0, 0))
    for x in range(1, 9):
        image.putpixel((x, 9 - x), (0, 0, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    source = stream.getvalue()
    request = json.loads(_request(source))
    second = json.loads(json.dumps(request["series"][0]))
    second.update(
        series_key="second",
        label="Second",
        color="#0000ff",
        visible_label="Second",
        seeds=[[1.0, 8.0], [8.0, 1.0]],
    )
    request["series"].append(second)
    return source, request


def _binding_counts(runtime, instance) -> tuple[int, int]:
    return tuple(
        len(
            runtime.scheduler_bindings.list(
                instance=instance.instance_id, namespace=namespace
            )
        )
        for namespace in ("run", "artifact")
    )


def test_request_submit_rejects_shared_support_without_covered_endpoints(
    tmp_path: Path,
) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    image = Image.new("RGB", (12, 12), "white")
    for x in range(1, 10):
        image.putpixel((x, 5), (255, 0, 0))
    for x in range(1, 4):
        image.putpixel((x, 4), (0, 0, 0))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    source_raw = stream.getvalue()
    _register(
        runtime,
        instance,
        name="paper_source",
        content=source_raw,
        kind="paper_source",
        schema_id="opaque",
        media_type="image/png",
    )
    payload = json.loads(_request(source_raw))
    payload["series"] = [
        {
            **payload["series"][0],
            "series_key": "covered",
            "label": "Covered black line",
            "color": "#000000",
            "visible_label": "Covered",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 4.0], [9.0, 6.0]],
        },
        {
            **payload["series"][0],
            "series_key": "visible",
            "label": "Visible red line",
            "visible_label": "Visible",
            "binding_bbox": [1, 3, 10, 7],
            "seeds": [[1.0, 5.0], [9.0, 5.0]],
        },
    ]
    payload["shared_support"] = [
        {
            "group_key": "red_over_black",
            "visible_series": "visible",
            "covered_series": ["covered"],
            "pixel_ranges": [[4, 6]],
            "mode": "overdraw",
            "covered_eligible": False,
            "max_endpoint_distance_px": 2.0,
        }
    ]
    request = {
        "name": "invalid_request",
        "operation_id": REQUEST,
        "inputs": [{"port": "paper_source", "artifact_names": ["paper_source"]}],
        "instruction": "Prepare the exact bounded figure request.",
    }
    assert root.call_tool("operation_preflight", request)["admissible"] is True
    root.call_tool("operation_invoke", request)
    compiled = catalog.operation(REQUEST)
    worker = LocalWorkerMCPRouter(
        runtime.runs,
        operation_id=compiled.spec.operation_id,
        operation_digest=compiled.digest,
    )
    opened = worker.call_tool("worker_open_assignment", {})
    Path(opened["output_directory"], "result.json").write_bytes(
        _envelope(payload)
    )
    rejected = worker.call_tool("worker_submit_result", {})
    assert rejected["state"] == "rejected"
    assert {item["rule_id"] for item in rejected["diagnostics"]} == {
        "curve.figure.request.source_binding"
    }
    assert any(
        "covered-series endpoints" in item["message"]
        for item in rejected["diagnostics"]
    )


def test_five_operation_figure_family_requires_exact_review(tmp_path: Path) -> None:
    catalog, runtime, instance, root = _system(tmp_path)
    source_raw, request_payload = _two_series_source_and_request()
    source = _register(
        runtime,
        instance,
        name="paper_source",
        content=source_raw,
        kind="paper_source",
        schema_id="opaque",
        media_type="image/png",
    )

    request_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=REQUEST,
        name="figure_request",
        inputs=[{"port": "paper_source", "artifact_names": ["paper_source"]}],
        payload=request_payload,
    )
    request_artifact = runtime.artifacts.get_by_id(
        runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="artifact",
            name=request_name,
        )
    )
    assert request_artifact.parent_refs == (source.ref,)

    materialized = root.call_tool(
        "operation_invoke",
        {
            "name": "figure_materialization",
            "operation_id": MATERIALIZE,
            "inputs": [
                {"port": "paper_source", "artifact_names": ["paper_source"]},
                {"port": "figure_request", "artifact_names": [request_name]},
            ],
        },
    )
    by_port: dict[str, list[str]] = {}
    for output in materialized["result"]["outputs"]:
        by_port.setdefault(output["kind"], []).append(output["artifact_name"])
    names = {
        "paper_source": ["paper_source"],
        "figure_request": [request_name],
        "figure_manifest": by_port["figure_evidence_manifest"],
        "validation_report": by_port["figure_evidence_validation_report"],
        "source_panels": by_port["figure_source_panel"],
        "audit_overlays": by_port["figure_audit_overlay"],
        "curve_tables": by_port["digitized_curve_table"],
    }
    assert {key: len(value) for key, value in names.items()} == {
        "paper_source": 1,
        "figure_request": 1,
        "figure_manifest": 1,
        "validation_report": 1,
        "source_panels": 1,
        "audit_overlays": 1,
        "curve_tables": 2,
    }

    complete_inputs = _bindings(names)
    missing_table = [
        (
            {**item, "artifact_names": item["artifact_names"][:-1]}
            if item["port"] == "curve_tables"
            else item
        )
        for item in complete_inputs
    ]
    invalid_request = {
        "name": "figure_intake_missing_table",
        "operation_id": EXTRACTION,
        "inputs": missing_table,
        "instruction": "Handle only the exact bound figure family.",
    }
    before = _binding_counts(runtime, instance)
    rejected = root.call_tool("operation_preflight", invalid_request)
    assert rejected["admissible"] is False
    assert rejected["reason_code"] == "input_producer_family_mismatch"
    assert rejected["port"] == "curve_tables"
    assert _binding_counts(runtime, instance) == before
    with pytest.raises(RootToolError, match="input_producer_family_mismatch"):
        root.call_tool("operation_invoke", invalid_request)
    assert _binding_counts(runtime, instance) == before

    assert root.call_tool(
        "operation_preflight",
        {
            "name": "generic_single_sibling",
            "operation_id": "science.evidence.extract.v1",
            "inputs": [
                {
                    "port": "source_material",
                    "artifact_names": names["source_panels"],
                }
            ],
            "instruction": "Inspect only the exact supplied source panel.",
        },
    )["admissible"] is True

    second_source_raw, second_request_payload = _two_series_source_and_request(
        marker=254
    )
    _register(
        runtime,
        instance,
        name="second_paper_source",
        content=second_source_raw,
        kind="paper_source",
        schema_id="opaque",
        media_type="image/png",
    )
    second_request_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=REQUEST,
        name="second_figure_request",
        inputs=[
            {
                "port": "paper_source",
                "artifact_names": ["second_paper_source"],
            }
        ],
        payload=second_request_payload,
    )
    second_materialized = root.call_tool(
        "operation_invoke",
        {
            "name": "second_figure_materialization",
            "operation_id": MATERIALIZE,
            "inputs": [
                {
                    "port": "paper_source",
                    "artifact_names": ["second_paper_source"],
                },
                {
                    "port": "figure_request",
                    "artifact_names": [second_request_name],
                },
            ],
        },
    )
    second_by_port: dict[str, list[str]] = {}
    for output in second_materialized["result"]["outputs"]:
        second_by_port.setdefault(output["kind"], []).append(
            output["artifact_name"]
        )
    second_names = {
        "paper_source": ["second_paper_source"],
        "figure_request": [second_request_name],
        "figure_manifest": second_by_port["figure_evidence_manifest"],
        "validation_report": second_by_port["figure_evidence_validation_report"],
        "source_panels": second_by_port["figure_source_panel"],
        "audit_overlays": second_by_port["figure_audit_overlay"],
        "curve_tables": second_by_port["digitized_curve_table"],
    }

    negative_bindings = {
        "wrong_source": [
            (
                {**item, "artifact_names": ["second_paper_source"]}
                if item["port"] == "paper_source"
                else item
            )
            for item in complete_inputs
        ],
        "wrong_request": [
            (
                {**item, "artifact_names": [second_request_name]}
                if item["port"] == "figure_request"
                else item
            )
            for item in complete_inputs
        ],
        "mixed_invocation": [
            (
                {
                    **item,
                    "artifact_names": [
                        names["curve_tables"][0],
                        second_by_port["digitized_curve_table"][1],
                    ],
                }
                if item["port"] == "curve_tables"
                else item
            )
            for item in complete_inputs
        ],
    }
    for case, inputs in negative_bindings.items():
        rejected = root.call_tool(
            "operation_preflight",
            {
                "name": f"figure_intake_{case}",
                "operation_id": EXTRACTION,
                "inputs": inputs,
                "instruction": "Handle only the exact bound figure family.",
            },
        )
        assert rejected["admissible"] is False
        assert rejected["reason_code"] == "input_producer_family_mismatch"

    intake_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=EXTRACTION,
        name="figure_intake",
        inputs=_bindings(names),
        payload=_intake_payload(),
    )
    incomplete_audit = root.call_tool(
        "operation_preflight",
        {
            "name": "figure_audit_missing_table",
            "operation_id": AUDIT,
            "inputs": _bindings(
                {**names, "curve_tables": names["curve_tables"][:-1]},
                include_intake=intake_name,
            ),
            "instruction": "Audit only the exact bound figure family.",
        },
    )
    assert incomplete_audit["admissible"] is False
    assert incomplete_audit["reason_code"] == "input_producer_family_mismatch"
    change_request_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=AUDIT,
        name="figure_audit_change_request",
        inputs=_bindings(names, include_intake=intake_name),
        payload=_audit_payload(
            status="fail",
            check_key="figure_wording",
            basis="One bounded statement overstates the exact table status.",
        ),
        verdict="blocked",
    )

    generic_revision = root.call_tool(
        "operation_preflight",
        {
            "name": "generic_figure_revision",
            "operation_id": "science.intake.revise.v1",
            "inputs": [
                {"port": "prior_draft", "artifact_names": [intake_name]},
                {
                    "port": "change_request",
                    "artifact_names": [change_request_name],
                },
                {"port": "source_material", "artifact_names": ["paper_source"]},
            ],
            "instruction": "This generic contract must not bypass the figure family.",
        },
    )
    assert generic_revision["admissible"] is False
    assert generic_revision["reason_code"] == (
        "input_revision_review_contract_mismatch"
    )

    half_request = {
        "name": "figure_revision_half_context",
        "operation_id": EXTRACTION,
        "inputs": [
            *_bindings(names),
            {"port": "prior_draft", "artifact_names": [intake_name]},
        ],
        "instruction": "The incomplete revision context must be rejected.",
    }
    before = _binding_counts(runtime, instance)
    half_revision = root.call_tool("operation_preflight", half_request)
    assert half_revision["admissible"] is False
    assert half_revision["reason_code"] == "input_cohort_incomplete"
    with pytest.raises(RootToolError, match="input_cohort_incomplete"):
        root.call_tool("operation_invoke", half_request)
    assert _binding_counts(runtime, instance) == before

    wrong_family_request = {
        "name": "figure_revision_wrong_family",
        "operation_id": EXTRACTION,
        "inputs": _revision_bindings(
            second_names,
            prior_draft=intake_name,
            change_request=change_request_name,
        ),
        "instruction": "The revision must retain its original figure family.",
    }
    before = _binding_counts(runtime, instance)
    wrong_family = root.call_tool("operation_preflight", wrong_family_request)
    assert wrong_family["admissible"] is False
    assert wrong_family["reason_code"] == "guard_rejected"
    with pytest.raises(RootToolError, match="guard_rejected"):
        root.call_tool("operation_invoke", wrong_family_request)
    assert _binding_counts(runtime, instance) == before

    revised_payload = _intake_payload()
    revised_payload["scientific_foundation"]["summary"] = (
        "One target is frozen; its table status is stated without overclaim."
    )
    revised_intake_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=EXTRACTION,
        name="figure_intake_revision_1",
        inputs=_revision_bindings(
            names,
            prior_draft=intake_name,
            change_request=change_request_name,
        ),
        payload=revised_payload,
    )

    same_issue_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=AUDIT,
        name="figure_audit_same_issue",
        inputs=_bindings(names, include_intake=revised_intake_name),
        payload=_audit_payload(
            status="fail",
            check_key="figure_wording",
            basis="Different prose reports the same unresolved check.",
        ),
        verdict="blocked",
    )
    same_issue_request = {
        "name": "figure_revision_no_progress",
        "operation_id": EXTRACTION,
        "inputs": _revision_bindings(
            names,
            prior_draft=revised_intake_name,
            change_request=same_issue_name,
        ),
        "instruction": "Repeated unresolved dimensions must stop.",
    }
    before = _binding_counts(runtime, instance)
    same_issue = root.call_tool("operation_preflight", same_issue_request)
    assert same_issue["admissible"] is False
    assert same_issue["reason_code"] == "revision_no_progress"
    with pytest.raises(RootToolError, match="revision_no_progress"):
        root.call_tool("operation_invoke", same_issue_request)
    assert _binding_counts(runtime, instance) == before

    second_issue_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=AUDIT,
        name="figure_audit_second_issue",
        inputs=_bindings(names, include_intake=revised_intake_name),
        payload=_audit_payload(
            status="fail",
            check_key="figure_limit",
            basis="A distinct bounded limitation still needs explicit wording.",
        ),
        verdict="blocked",
    )
    revised_payload_2 = json.loads(json.dumps(revised_payload))
    revised_payload_2["scientific_foundation"]["summary"] += (
        " Digitization limits remain explicit."
    )
    revised_intake_name_2 = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=EXTRACTION,
        name="figure_intake_revision_2",
        inputs=_revision_bindings(
            names,
            prior_draft=revised_intake_name,
            change_request=second_issue_name,
        ),
        payload=revised_payload_2,
    )
    third_issue_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=AUDIT,
        name="figure_audit_third_issue",
        inputs=_bindings(names, include_intake=revised_intake_name_2),
        payload=_audit_payload(
            status="fail",
            check_key="figure_scope",
            basis="A third distinct issue is used only to prove the revision cap.",
        ),
        verdict="blocked",
    )
    over_limit_request = {
        "name": "figure_revision_over_limit",
        "operation_id": EXTRACTION,
        "inputs": _revision_bindings(
            names,
            prior_draft=revised_intake_name_2,
            change_request=third_issue_name,
        ),
        "instruction": "The bounded revision limit must stop this call.",
    }
    before = _binding_counts(runtime, instance)
    over_limit = root.call_tool("operation_preflight", over_limit_request)
    assert over_limit["admissible"] is False
    assert over_limit["reason_code"] == "revision_limit_reached"
    with pytest.raises(RootToolError, match="revision_limit_reached"):
        root.call_tool("operation_invoke", over_limit_request)
    assert _binding_counts(runtime, instance) == before

    audit_name = _complete_agent(
        catalog,
        runtime,
        root,
        operation_id=AUDIT,
        name="figure_audit_final",
        inputs=_bindings(names, include_intake=revised_intake_name_2),
        payload=_audit_payload(),
    )

    old_audit = root.call_tool(
        "operation_preflight",
        {
            "name": "curve_bundle_with_old_audit",
            "operation_id": BUNDLE,
            "inputs": _bindings(
                names,
                include_intake=revised_intake_name_2,
                include_audit=change_request_name,
            ),
        },
    )
    assert old_audit["admissible"] is False
    assert old_audit["reason_code"] == "guard_rejected"

    valid_request = {
        "name": "curve_bundle",
        "operation_id": BUNDLE,
        "inputs": _bindings(
            names, include_intake=revised_intake_name_2, include_audit=audit_name
        ),
    }
    assert root.call_tool("operation_preflight", valid_request)["admissible"] is True

    split = root.call_tool(
        "operation_invoke",
        {
            "name": "figure_intake_split",
            "operation_id": "science.intake.split.v1",
            "inputs": [
                {
                    "port": "scientific_intake",
                    "artifact_names": [revised_intake_name_2],
                },
                {"port": "evidence_audit", "artifact_names": [audit_name]},
            ],
        },
    )["result"]["outputs"]
    foundation_name = next(
        item["artifact_name"]
        for item in split
        if item["output_label"] == "scientific_foundation"
    )
    problem_frame_name = next(
        item["artifact_name"]
        for item in split
        if item["kind"] == "problem_frame"
    )
    frozen_family = [
        *names["paper_source"],
        *names["figure_request"],
        *names["figure_manifest"],
        *names["validation_report"],
        *names["source_panels"],
        *names["audit_overlays"],
        *names["curve_tables"],
    ]
    qualification_request = {
        "name": "qualify_figure_intake",
        "operation_id": "science.evidence.qualify.v1",
        "inputs": [
            {
                "port": "scientific_foundation",
                "artifact_names": [foundation_name],
            },
            {
                "port": "extraction_primary",
                "artifact_names": [revised_intake_name_2],
            },
            {"port": "frozen_sources", "artifact_names": frozen_family},
            {"port": "evidence_audit", "artifact_names": [audit_name]},
        ],
    }
    assert root.call_tool(
        "operation_preflight", qualification_request
    )["admissible"] is True
    assert root.call_tool(
        "operation_invoke", qualification_request
    )["result"]["status"] == "pending"

    approval_count = len(runtime.approvals.list_requests(limit=100))
    incomplete_qualification = {
        **qualification_request,
        "name": "qualify_figure_without_curve_table",
        "inputs": [
            (
                {**item, "artifact_names": frozen_family[:-1]}
                if item["port"] == "frozen_sources"
                else item
            )
            for item in qualification_request["inputs"]
        ],
    }
    incomplete = root.call_tool(
        "operation_preflight", incomplete_qualification
    )
    assert incomplete["admissible"] is False
    assert incomplete["reason_code"] == "approval_projector_failed"
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count
    with pytest.raises(RootToolError, match="approval_projector_failed"):
        root.call_tool("operation_invoke", incomplete_qualification)
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count

    wrong_split_qualification = {
        **qualification_request,
        "name": "qualify_figure_with_problem_frame",
        "inputs": [
            (
                {
                    **item,
                    "artifact_names": [foundation_name, problem_frame_name],
                }
                if item["port"] == "scientific_foundation"
                else item
            )
            for item in qualification_request["inputs"]
        ],
    }
    wrong_split = root.call_tool(
        "operation_preflight", wrong_split_qualification
    )
    assert wrong_split["admissible"] is False
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count

    _register(
        runtime,
        instance,
        name="replacement_source",
        content=b"replacement source",
        kind="paper_source",
        schema_id="opaque",
        media_type="image/png",
    )
    replaced_source_qualification = {
        **qualification_request,
        "name": "qualify_figure_with_replaced_source",
        "inputs": [
            (
                {
                    **item,
                    "artifact_names": ["replacement_source", *frozen_family[1:]],
                }
                if item["port"] == "frozen_sources"
                else item
            )
            for item in qualification_request["inputs"]
        ],
    }
    replaced = root.call_tool(
        "operation_preflight", replaced_source_qualification
    )
    assert replaced["admissible"] is False
    assert replaced["reason_code"] == "approval_projector_failed"
    assert len(runtime.approvals.list_requests(limit=100)) == approval_count

    missing_audit = {
        **valid_request,
        "name": "curve_bundle_missing_audit",
        "inputs": _bindings(names, include_intake=revised_intake_name_2),
    }
    missing = root.call_tool("operation_preflight", missing_audit)
    assert missing["admissible"] is False
    assert missing["port"] == "evidence_audit"

    intake_id = runtime.scheduler_bindings.resolve(
        instance=instance.instance_id,
        namespace="artifact",
        name=revised_intake_name_2,
    )
    intake = runtime.artifacts.get_by_id(intake_id)
    revised = _register(
        runtime,
        instance,
        name="figure_intake_revision",
        content=b"{}",
        kind="scientific_intake",
        schema_id="scidiscovery.scientific-intake.v1",
        media_type="application/json",
        parent_refs=intake.parent_refs,
        labels=intake.labels,
        supersedes_ref=intake.ref,
    )
    stale = root.call_tool(
        "operation_preflight",
        {
            **valid_request,
            "name": "curve_bundle_stale_review",
            "inputs": _bindings(
                names,
                include_intake="figure_intake_revision",
                include_audit=audit_name,
            ),
        },
    )
    assert revised.ref != intake.ref
    assert stale["admissible"] is False
