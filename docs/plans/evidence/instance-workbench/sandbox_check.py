"""Verify the UI's narrow write roots in an isolated equivalent mount sandbox."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile

repository = Path.cwd()
if len(sys.argv) == 3 and sys.argv[1] == "--inside":
    root = Path(sys.argv[2])
    project, state = root / "project", root / "state"
    from scidiscovery.artifact_agent.runtime import open_runtime
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
    for path in (project / "forbidden", repository / "forbidden-workbench-probe"):
        try:
            path.write_bytes(b"must not be writable")
        except OSError:
            pass
        else:
            raise AssertionError("write escaped allowed roots")
    runtime = open_runtime(project_root=project, state_root=state,
        local_workspace_root=project / ".scidiscovery-runs", approval_receipt_secret=b"s" * 32)
    instance = runtime.scheduler_bindings.create_instance(name="sandbox", title="Fixture", objective="Original fixture")
    original = runtime.artifacts.register(b"sandbox original", ArtifactRegistration(kind="fixture",
        schema_id="fixture.v1", payload_schema_version=1, creator=runtime.actor, media_type="text/plain"),
        idempotency_key="sandbox.original")
    runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace="artifact", name="original", object_id=original.artifact_id)
    service = InstanceArchive(runtime)
    for _ in range(2):
        preview = service.preview(instance.instance_id)
        assert preview["ready"], preview
        service.archive(instance.instance_id, preview["fingerprint"])
        assert service.archived_model(instance.instance_id).artifacts.read(original.ref) == b"sandbox original"
        preview = service.restore_preview(instance.instance_id)
        assert preview["ready"], preview
        service.restore(instance.instance_id, preview["fingerprint"])
        assert runtime.artifacts.read(original.ref) == b"sandbox original"
    print(json.dumps({"mount_sandbox": True, "workspace_and_source_readonly": True,
        "write_roots": ["state", "local_workspaces", "archive/instances"], "round_trips": 2,
        "actual_systemd_unit": False, "scientific_execution_started": False}))
else:
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        print(json.dumps({"supported": False, "reason": "bubblewrap unavailable"}))
        raise SystemExit(77)
    with tempfile.TemporaryDirectory(prefix="workbench-sandbox-") as temporary:
        root = Path(temporary)
        project, state = root / "project", root / "state"
        state.mkdir()
        local, archive = project / ".scidiscovery-runs", project / ".scidiscovery-archive/instances"
        local.mkdir(parents=True)
        archive.mkdir(parents=True)
        paths = [repository / relative for relative in ("src", "plugins/tcad_artifact", "plugins/curve_score", "plugins/curve_figure_evidence")]
        command = [bwrap, "--die-with-parent", "--unshare-all", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
        for path in (state, local, archive):
            command.extend(["--bind", str(path), str(path)])
        command.extend(["--setenv", "PYTHONPATH", os.pathsep.join(map(str, paths)),
                        "--setenv", "PYTHONDONTWRITEBYTECODE", "1", sys.executable,
                        str(Path(__file__).resolve()), "--inside", str(root)])
        result = subprocess.run(command, cwd=repository, capture_output=True, text=True, timeout=60)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
