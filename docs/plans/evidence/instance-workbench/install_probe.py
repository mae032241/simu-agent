import hashlib
from importlib.metadata import entry_points
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

from scidiscovery.artifact_agent.approval_ui import app
from scidiscovery.artifact_agent.approval_ui.access import access_cookie
from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.approval_ui.trajectory import TrajectoryStore
from scidiscovery.artifact_agent.interfaces.mcp_root import root_tools_for_backend
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.operations.tooling import operation_tool_contracts, operation_worker_tool_names


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


catalog = compile_installed_catalog()
snapshot = {"catalog_digest": catalog.digest(), "operations": {}, "root_tools": {}}
for name in sorted(catalog.operation_ids()):
    operation = catalog.operation(name)
    value = {"digest": operation.digest, "spec_digest": digest(operation.spec.model_dump(mode="json"))}
    if operation.spec.executor.kind == "agent":
        value["worker_tools"] = {key: digest(item) for key, item in
            operation_tool_contracts(operation, operation_worker_tool_names(operation)).items()}
    snapshot["operations"][name] = value
for backend in ("local", "hardened"):
    snapshot["root_tools"][backend] = {tool.name: digest(tool.schema()) for tool in root_tools_for_backend(backend)}
assert snapshot == json.loads(Path(sys.argv[1]).read_text()), "installed Operation or tool contract changed"
providers = entry_points().select(group="scidiscovery.instance_views")
assert {entry.name for entry in providers} == {"general_science", "tcad_artifact"}
for entry in providers:
    assert callable(entry.load())
help_result = subprocess.run([sys.executable, "-I", "-m", "scidiscovery.artifact_agent.interfaces.cli",
    "serve-approval-ui", "--help"], capture_output=True, text=True, check=True, timeout=15)
assert "--local-workspace-root" in help_result.stdout and "--plugin-config" in help_result.stdout
for module in tuple(sys.modules.values()):
    if getattr(module, "__name__", "").startswith(("scidiscovery.", "tcad_artifact.")) and getattr(module, "__file__", None):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), module.__file__

with tempfile.TemporaryDirectory(prefix="workbench-installed-state-") as temporary:
    project, state = Path(temporary) / "workspace", Path(temporary) / "state"
    project.mkdir()
    runtime = open_runtime(project_root=project, state_root=state, approval_receipt_secret=b"s" * 32)
    instance = runtime.scheduler_bindings.create_instance(name="installed.ui", title="Installed fixture", objective="Original frozen fixture objective")
    original = runtime.artifacts.register(b"original frozen bytes", ArtifactRegistration(kind="fixture",
        schema_id="fixture.original.v1", payload_schema_version=1, creator=runtime.actor, media_type="text/plain"), idempotency_key="original.fixture")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="original", object_id=original.artifact_id)
    model = InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions, operation_catalog=catalog)
    archive = InstanceArchive(runtime)
    ui = app.ApprovalUI(runtime.approvals, bindings=runtime.scheduler_bindings, read_model=model,
        instance_management_secret=b"s" * 32, maintenance=runtime.maintenance,
        instance_archive=archive, trajectory_store=TrajectoryStore(state / "ui/workbench.sqlite3"))
    url = urlparse(ui.start())
    cookie = access_cookie(instance.instance_id, ui.browser_access.issue(instance.instance_id, maintenance=True)).split(";", 1)[0]
    def get(path):
        connection = http.client.HTTPConnection(url.hostname, url.port, timeout=10)
        connection.request("GET", path, headers={"Cookie": cookie})
        response = connection.getresponse()
        value = response.status, response.read()
        connection.close()
        return value
    try:
        for path in ("/static/workbench.js", "/static/style.css", f"/instance/{instance.instance_id}/manage"):
            assert get(path)[0] == 200, path
        preview = archive.preview(instance.instance_id)
        assert preview["ready"], preview
        archive.archive(instance.instance_id, preview["fingerprint"])
        assert get(f"/instance/{instance.instance_id}")[0] == 200
        status, raw = get(f"/instance/{instance.instance_id}/evidence/{original.artifact_id}?format=download")
        assert status == 200 and raw == b"original frozen bytes"
        preview = archive.restore_preview(instance.instance_id)
        assert preview["ready"], preview
        archive.restore(instance.instance_id, preview["fingerprint"])
        assert runtime.artifacts.read(original.ref) == raw
    finally:
        ui.stop()
print(json.dumps({"installed_contracts_identical": len(snapshot["operations"]),
    "providers": sorted(entry.name for entry in providers), "static_files_http": True,
    "archive_browse_restore": True, "scientific_execution_started": False}))
