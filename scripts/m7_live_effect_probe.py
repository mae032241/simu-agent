#!/usr/bin/env python3
"""Run one persistent M7 Effect through the real loopback approval UI."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse


REPOSITORY = Path(__file__).resolve().parents[1]
import scidiscovery
from scidiscovery.artifact_agent.approval_ui import ApprovalUI
from scidiscovery.artifact_agent.execution_bridge import ExecutionBridge
from scidiscovery.artifact_agent.service.execution_collection import ExecutionCollection
from scidiscovery.artifact_agent.interfaces.mcp_root import (
    RootMCPRouter,
    RootToolFacade,
)
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.runtime_plugin_bindings import (
    load_runtime_plugin_contributions,
)
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.approval import ApprovalRequest
from scidiscovery.artifact_agent.service.executions import (
    ExecutionApprovalError,
)
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.invoke import effect_operation_plan


EFFECT_OPERATION = "m7.fixture.frozen-copy.v1"
EXECUTION_NAME = "m7_frozen_copy"
INSTANCE_NAME = "m7_live_effect"
MANIFEST_PATH = REPOSITORY / "tests/fixtures/m7_effect/manifest.json"


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_json(path: Path, value: object) -> None:
    _write_new(
        path,
        (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
    )


def _replace_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        _write_json(temporary, value)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_manifest(catalog) -> dict[str, object]:
    manifest = json.loads(MANIFEST_PATH.read_text("utf-8"))
    operation = manifest.get("operation")
    request = manifest.get("request")
    output = manifest.get("output")
    files = manifest.get("plugin_files")
    if not all(
        isinstance(value, expected)
        for value, expected in (
            (operation, dict),
            (request, dict),
            (output, dict),
            (files, list),
        )
    ):
        raise RuntimeError("M7 Effect manifest is incomplete")
    compiled = catalog.operation(EFFECT_OPERATION)
    plan = effect_operation_plan(compiled)
    if (
        catalog.runtime_plugin_ids() != ("m7_effect_fixture",)
        or compiled.spec.catalog_scope != "public"
        or compiled.spec.executor.kind != "effect"
        or operation.get("plugin_id") != compiled.plugin_id
        or operation.get("plugin_version") != "0.0.1"
        or operation.get("operation_id") != compiled.spec.operation_id
        or operation.get("operation_version") != compiled.spec.version
        or operation.get("operation_digest") != compiled.digest
        or operation.get("runtime_binding") != plan.executor
    ):
        raise RuntimeError("installed M7 Effect identity differs from its frozen manifest")
    for item in files:
        if not isinstance(item, dict):
            raise RuntimeError("M7 Effect plugin file manifest is invalid")
        path = REPOSITORY / str(item.get("path"))
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise RuntimeError("M7 Effect plugin source differs from its frozen manifest")
    for item in (request, output):
        path = REPOSITORY / str(item.get("path"))
        if (
            not path.is_file()
            or _sha256(path) != item.get("sha256")
            or path.stat().st_size != item.get("size_bytes")
        ):
            raise RuntimeError("M7 Effect data differs from its frozen manifest")
    return manifest


def _register_request(runtime, instance_id: str, manifest: dict[str, object]) -> None:
    request = manifest["request"]
    assert isinstance(request, dict)
    raw = (REPOSITORY / str(request["path"])).read_bytes()
    envelope = runtime.artifacts.register(
        raw,
        ArtifactRegistration(
            kind="m7_effect_request",
            schema_id="m7.fixture-effect-request.v1",
            payload_schema_version=1,
            media_type="application/json",
            creator=runtime.actor,
        ),
        idempotency_key="m7-live-effect:replay-request",
    )
    runtime.scheduler_bindings.bind(
        instance=instance_id,
        namespace="artifact",
        name="replay_request",
        object_id=envelope.artifact_id,
    )


def _request() -> dict[str, object]:
    return {
        "name": EXECUTION_NAME,
        "operation_id": EFFECT_OPERATION,
        "inputs": [
            {"port": "request", "artifact_names": ["replay_request"]}
        ],
    }


def _outputs_match(
    runtime,
    instance_id: str,
    outputs: list[dict[str, object]],
    manifest: dict[str, object],
) -> tuple[bool, list[dict[str, object]]]:
    expected = manifest["output"]
    assert isinstance(expected, dict)
    if len(outputs) != 1 or outputs[0].get("output_label") != expected["logical_name"]:
        return False, []
    verified: list[dict[str, object]] = []
    for output in outputs:
        label = output.get("output_label")
        artifact_name = output.get("artifact_name")
        if not isinstance(label, str) or not isinstance(artifact_name, str):
            return False, []
        artifact_id = runtime.scheduler_bindings.resolve(
            instance=instance_id,
            namespace="artifact",
            name=artifact_name,
        )
        envelope = runtime.artifacts.get_by_id(artifact_id)
        raw = runtime.artifacts.read(envelope.ref)
        digest = hashlib.sha256(raw).hexdigest()
        if (
            digest != expected["sha256"]
            or len(raw) != expected["size_bytes"]
            or output.get("size_bytes") != expected["size_bytes"]
            or output.get("media_type") != expected["media_type"]
        ):
            return False, []
        verified.append(
            {
                "logical_name": label,
                "media_type": output["media_type"],
                "sha256": digest,
                "size_bytes": len(raw),
            }
        )
    return True, verified


def _loopback_url_is_readable(url: str, *, port: int) -> bool:
    parsed = urlparse(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "localhost"
        or parsed.port != port
    ):
        return False
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        target = parsed.path
        if parsed.query:
            target += "?" + parsed.query
        connection.request("GET", target, headers={"Host": f"localhost:{port}"})
        response = connection.getresponse()
        response.read()
        return response.status == 200
    finally:
        connection.close()


def _wait_for_decision(router: RootMCPRouter, *, timeout_seconds: int) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    approval_status: dict[str, object] | None = None
    while time.monotonic() < deadline:
        approval_status = router.call_tool(
            "approval_status", {"name": f"{EXECUTION_NAME}.approval"}
        )
        if approval_status.get("status") != "pending":
            break
        time.sleep(0.5)
    if approval_status is None or approval_status.get("status") == "pending":
        raise RuntimeError("human Effect decision timed out")
    if approval_status.get("selected_option") not in {
        "authorize_execution",
        "authorize_execution_with_exception",
    }:
        raise RuntimeError("Effect was not authorized in the loopback UI")
    return approval_status


def _collect_effect(
    *,
    root: Path,
    runtime,
    router: RootMCPRouter,
    catalog,
    manifest: dict[str, object],
    instance_id: str,
    approval_status: dict[str, object],
    start_before_decision_blocked: bool,
    resumed_same_pending_approval: bool,
) -> dict[str, object]:
    started = router.call_tool("execution_start", {"name": EXECUTION_NAME}, surface="execution")
    synced = router.call_tool("execution_sync", {"name": EXECUTION_NAME}, surface="execution")
    router.call_tool("execution_collect", {"name": EXECUTION_NAME}, surface="execution")
    deadline = time.monotonic() + 605
    while True:
        status = router.call_tool("execution_status", {"name": EXECUTION_NAME}, surface="execution")
        if status["state"] == "collected":
            break
        if status.get("collection", {}).get("state") not in {"running", "stopping", "stop_pending"} or time.monotonic() >= deadline:
            raise RuntimeError(f"Effect collection did not complete: {status.get('collection')}")
        time.sleep(.1)
    outputs = router.call_tool(
        "execution_outputs", {"name": EXECUTION_NAME}
    , surface="execution").get("outputs")
    if not isinstance(outputs, list):
        raise RuntimeError("Effect outputs are missing")
    outputs_match, verified_outputs = _outputs_match(
        runtime, instance_id, outputs, manifest
    )
    compiled = catalog.operation(EFFECT_OPERATION)
    approval_contract = compiled.spec.review.approval
    approval_identity = compiled.approval_identity
    assert approval_contract is not None and approval_identity is not None
    evidence = {
        "approval_contract_digest": approval_identity.approval_contract_digest,
        "approval_decided_in_loopback_ui": True,
        "approval_selected_option": approval_status["selected_option"],
        "approval_subjects_exact": True,
        "catalog_digest": catalog.digest(),
        "effect_operation_id": EFFECT_OPERATION,
        "effect_operation_digest": compiled.digest,
        "effect_operation_version": compiled.spec.version,
        "execution_collected": synced.get("state") == "collected",
        "execution_started_explicitly": started.get("state") == "submitted",
        "installed_runtime_binding_loaded": True,
        "invoke_created_execution_and_approval": True,
        "outputs": verified_outputs,
        "outputs_match_frozen_manifest": outputs_match,
        "preflight_admissible": True,
        "resumed_same_pending_approval": resumed_same_pending_approval,
        "schema_version": 1,
        "start_before_decision_blocked": start_before_decision_blocked,
    }
    if not all(
        value is True
        for key, value in evidence.items()
        if key
        not in {
            "approval_contract_digest",
            "resumed_same_pending_approval",
            "approval_selected_option",
            "catalog_digest",
            "effect_operation_digest",
            "effect_operation_id",
            "effect_operation_version",
            "outputs",
            "schema_version",
        }
    ):
        raise RuntimeError(f"Effect evidence is incomplete: {evidence}")
    _write_json(root / "final-evidence.json", evidence)
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True), flush=True)
    return evidence


def run(root: Path, *, timeout_seconds: int, ui_port: int) -> dict[str, object]:
    root = root.expanduser().absolute()
    installed_root = Path(scidiscovery.__file__).resolve()
    if not installed_root.is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError("M7 Effect probe requires an installed isolated runtime")
    if root.is_symlink() or (root.exists() and any(root.iterdir())):
        raise RuntimeError("run root must be new or empty")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    project = root / "project"
    state = root / "state"
    project.mkdir()
    state.mkdir()
    approval_secret = secrets.token_bytes(32)
    _write_new(root / "approval.secret", approval_secret)
    config_path = root / "m7-effect-plugin.json"
    frozen_output = REPOSITORY / "tests/fixtures/m7_effect/frozen-output.txt"
    _write_json(
        config_path,
        {
            "frozen_output_path": str(frozen_output),
            "frozen_output_sha256": _sha256(frozen_output),
        },
    )

    installed_catalog = compile_installed_catalog()
    runtime = open_runtime(
        project_root=project,
        state_root=state,
        approval_receipt_secret=approval_secret,
    )
    assert runtime.approvals is not None and runtime.executions is not None
    catalog = runtime.runs.operation_catalog
    if catalog.digest() != installed_catalog.digest():
        raise RuntimeError("runtime and startup installed catalogs differ")
    manifest = _frozen_manifest(catalog)
    contributions = load_runtime_plugin_contributions(
        catalog,
        {"m7_effect_fixture": config_path},
        mode="control",
        state_root=state,
    )
    if set(contributions.execution_adapters) != {
        "m7_effect_fixture:adapter"
    }:
        raise RuntimeError("installed M7 Effect runtime binding is incomplete")
    bridge = ExecutionBridge(
        runtime.executions,
        adapters=contributions.execution_adapters,
    )
    instance = runtime.scheduler_bindings.create_instance(
        name=INSTANCE_NAME,
        title="M7 外部 Effect 环回审批验收",
        objective="验证精确人工授权、显式启动、同步和冻结输出收集。",
    )
    _register_request(runtime, instance.instance_id, manifest)

    ui = ApprovalUI(runtime.approvals, host="127.0.0.1", port=ui_port)
    bound_url = ui.start()
    actual_port = urlparse(bound_url).port
    assert actual_port is not None
    base_url = f"http://localhost:{actual_port}"
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
            approval_base_url=base_url,
            execution_bridge=bridge,
            execution_collection=ExecutionCollection(runtime.executions,
                plugin_configs={"m7_effect_fixture": str(config_path)}),
        )
    )
    request = _request()
    try:
        if router.call_tool("execution_list", {"limit": 100}, surface="execution")["executions"]:
            raise RuntimeError("fresh Effect root already contains an execution")
        if router.call_tool(
            "approval_list", {"status": None, "limit": 100}
        )["approvals"]:
            raise RuntimeError("fresh Effect root already contains an approval")
        preflight = router.call_tool("operation_preflight", request)
        if preflight.get("admissible") is not True:
            raise RuntimeError(f"Effect preflight rejected: {preflight}")
        invoked = router.call_tool("operation_invoke", request)
        result = invoked.get("result")
        if not isinstance(result, dict) or result.get("state") != "created":
            raise RuntimeError("Effect invoke did not create one execution")
        approval = result.get("approval")
        if not isinstance(approval, dict) or approval.get("status") != "pending":
            raise RuntimeError("Effect invoke did not create one pending approval")
        review_url = approval.get("review_url")
        if not isinstance(review_url, str) or not review_url.startswith(base_url):
            raise RuntimeError("Effect invoke returned no exact loopback review URL")
        executions = router.call_tool("execution_list", {"limit": 100}, surface="execution")["executions"]
        approvals = router.call_tool(
            "approval_list", {"status": None, "limit": 100}
        )["approvals"]
        if len(executions) != 1 or len(approvals) != 1:
            raise RuntimeError("Effect invoke did not create one execution and approval")
        execution_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="execution",
            name=EXECUTION_NAME,
        )
        approval_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="approval",
            name=f"{EXECUTION_NAME}.approval",
        )
        token = parse_qs(urlparse(review_url).query)["token"][0]
        review = runtime.approvals.review(approval_id, access_token=token)
        exact_subjects = runtime.executions.approval_subject_refs(execution_id)
        if tuple(subject.ref for subject, _ in review.subjects) != exact_subjects:
            raise RuntimeError("Effect approval has different frozen subjects")

        start_before_decision_blocked = False
        try:
            router.call_tool("execution_start", {"name": EXECUTION_NAME}, surface="execution")
        except ExecutionApprovalError:
            start_before_decision_blocked = True
        if not start_before_decision_blocked:
            raise RuntimeError("execution started without a UI decision")

        _write_json(
            root / "pending.json",
            {
                "operation_id": EFFECT_OPERATION,
                "review_url": review_url,
                "warning": "只授权测试适配器复制一个冻结文件；不运行求解器。",
            },
        )
        if not _loopback_url_is_readable(review_url, port=actual_port):
            raise RuntimeError("loopback Effect review page is not readable")
        print(f"M7_EFFECT_REVIEW_URL={review_url}", flush=True)

        approval_status = _wait_for_decision(
            router, timeout_seconds=timeout_seconds
        )
        return _collect_effect(
            root=root,
            runtime=runtime,
            router=router,
            catalog=catalog,
            manifest=manifest,
            instance_id=instance.instance_id,
            approval_status=approval_status,
            start_before_decision_blocked=start_before_decision_blocked,
            resumed_same_pending_approval=False,
        )
    finally:
        router.facade.execution_collection.close()
        ui.stop()


def resume(root: Path, *, timeout_seconds: int, ui_port: int) -> dict[str, object]:
    root = root.expanduser().absolute()
    installed_root = Path(scidiscovery.__file__).resolve()
    if not installed_root.is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError("M7 Effect probe requires an installed isolated runtime")
    if (
        not root.is_dir()
        or not (root / "pending.json").is_file()
        or (root / "final-evidence.json").exists()
    ):
        raise RuntimeError("resume root must contain one unfinished Effect probe")
    project = root / "project"
    state = root / "state"
    approval_secret = (root / "approval.secret").read_bytes()
    if len(approval_secret) != 32:
        raise RuntimeError("stored approval secret is invalid")
    config_path = root / "m7-effect-plugin.json"
    if not config_path.is_file():
        raise RuntimeError("stored M7 Effect plugin configuration is missing")

    installed_catalog = compile_installed_catalog()
    runtime = open_runtime(
        project_root=project,
        state_root=state,
        approval_receipt_secret=approval_secret,
    )
    assert runtime.approvals is not None and runtime.executions is not None
    catalog = runtime.runs.operation_catalog
    if catalog.digest() != installed_catalog.digest():
        raise RuntimeError("runtime and startup installed catalogs differ")
    manifest = _frozen_manifest(catalog)
    contributions = load_runtime_plugin_contributions(
        catalog,
        {"m7_effect_fixture": config_path},
        mode="control",
        state_root=state,
    )
    if set(contributions.execution_adapters) != {
        "m7_effect_fixture:adapter"
    }:
        raise RuntimeError("installed M7 Effect runtime binding is incomplete")
    bridge = ExecutionBridge(
        runtime.executions,
        adapters=contributions.execution_adapters,
    )
    instance = runtime.scheduler_bindings.select_instance(name=INSTANCE_NAME)

    ui = ApprovalUI(runtime.approvals, host="127.0.0.1", port=ui_port)
    bound_url = ui.start()
    actual_port = urlparse(bound_url).port
    assert actual_port is not None
    base_url = f"http://localhost:{actual_port}"
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
            approval_base_url=base_url,
            execution_bridge=bridge,
            execution_collection=ExecutionCollection(runtime.executions,
                plugin_configs={"m7_effect_fixture": str(config_path)}),
        )
    )
    try:
        preflight = router.call_tool("operation_preflight", _request())
        if preflight.get("admissible") is not True:
            raise RuntimeError(f"resumed Effect preflight rejected: {preflight}")
        executions = router.call_tool("execution_list", {"limit": 100}, surface="execution")["executions"]
        approvals = router.call_tool(
            "approval_list", {"status": None, "limit": 100}
        )["approvals"]
        if (
            len(executions) != 1
            or executions[0].get("state") != "created"
            or len(approvals) != 1
            or approvals[0].get("status") != "pending"
        ):
            raise RuntimeError("resume root does not contain one pending Effect")
        approval_status = router.call_tool(
            "approval_status", {"name": f"{EXECUTION_NAME}.approval"}
        )
        approval_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="approval",
            name=f"{EXECUTION_NAME}.approval",
        )
        execution_id = runtime.scheduler_bindings.resolve(
            instance=instance.instance_id,
            namespace="execution",
            name=EXECUTION_NAME,
        )
        exact_subjects = runtime.executions.approval_subject_refs(execution_id)
        stored_status = runtime.approvals.status(approval_id)
        stored_request = ApprovalRequest.model_validate_json(
            runtime.artifacts.read(stored_status.approval_request_ref), strict=True
        )
        if stored_request.subject_refs != exact_subjects:
            raise RuntimeError("resumed Effect approval subjects changed")

        start_before_decision_blocked = False
        try:
            router.call_tool("execution_start", {"name": EXECUTION_NAME}, surface="execution")
        except ExecutionApprovalError:
            start_before_decision_blocked = True
        if not start_before_decision_blocked:
            raise RuntimeError("resumed execution started without a UI decision")
        review_url = approval_status.get("review_url")
        access_refresh_required = not isinstance(review_url, str)
        page_url = base_url + "/" if access_refresh_required else review_url
        assert isinstance(page_url, str)
        if not _loopback_url_is_readable(page_url, port=actual_port):
            raise RuntimeError("resumed loopback Effect approval page is not readable")
        _replace_json(
            root / "pending.json",
            {
                "access_refresh_required": access_refresh_required,
                "operation_id": EFFECT_OPERATION,
                "review_url": page_url,
                "warning": (
                    "访问凭证已到期；请先在审批首页刷新链接，再决定是否授权。"
                    if access_refresh_required
                    else "只授权测试适配器复制一个冻结文件；不运行求解器。"
                ),
            },
        )
        print(f"M7_EFFECT_REVIEW_URL={page_url}", flush=True)
        approval_status = _wait_for_decision(
            router, timeout_seconds=timeout_seconds
        )
        return _collect_effect(
            root=root,
            runtime=runtime,
            router=router,
            catalog=catalog,
            manifest=manifest,
            instance_id=instance.instance_id,
            approval_status=approval_status,
            start_before_decision_blocked=start_before_decision_blocked,
            resumed_same_pending_approval=True,
        )
    finally:
        router.facade.execution_collection.close()
        ui.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--ui-port", type=int, default=0)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout_seconds <= 86400:
        parser.error("--timeout-seconds must be between 1 and 86400")
    if not 0 <= args.ui_port <= 65535:
        parser.error("--ui-port must be between 0 and 65535")
    action = resume if args.resume else run
    action(
        args.root,
        timeout_seconds=args.timeout_seconds,
        ui_port=args.ui_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
