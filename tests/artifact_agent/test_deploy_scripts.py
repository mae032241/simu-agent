from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

from scidiscovery.artifact_agent.interfaces.mcp_root import ROOT_TOOLS
from scidiscovery.artifact_agent.interfaces.mcp_worker import WORKER_TOOLS


def test_ssh_runner_installer_cleans_up_without_scope_error(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    remote_root = tmp_path / "remote/.scidiscovery"
    fake_ssh = tmp_path / "ssh"
    fake_ssh.write_text(
        f"""#!{sys.executable}
import os
import pathlib
import sys
import tarfile

root = pathlib.Path(os.environ["SCID_FAKE_REMOTE_ROOT"])
root.mkdir(parents=True)
assert "tcad@192.0.2.34" in sys.argv
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
    for member in archive:
        assert member.mtime == 0
        archive.extract(member, root)
print("fake SSH extraction: pass")
""",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o750)
    fake_vmrun = tmp_path / "vmrun"
    fake_vmrun.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdout.buffer.write(b'192.0.2.34\\r\\n')\n",
        encoding="utf-8",
    )
    fake_vmrun.chmod(0o750)
    environment = {
        **os.environ,
        "SCID_PROJECT_ROOT": str(project_root),
        "SCID_SSH_EXE": str(fake_ssh),
        "SCID_SSH_IDENTITY": "unused-test-key",
        "SCID_SSH_DESTINATION_FALLBACK": "tcad@192.0.2.10",
        "SCID_VMRUN_EXE": str(fake_vmrun),
        "SCID_VMX_PATH": "fixture.vmx",
        "SCID_SSH_HOST_KEY_ALIAS": "test-vm",
        "SCID_SSH_KNOWN_HOSTS": "unused-known-hosts",
        "SCID_REMOTE_RUNNER_ROOT": str(remote_root),
        "SCID_FAKE_REMOTE_ROOT": str(remote_root),
    }
    completed = subprocess.run(
        [str(project_root / "deploy/install_ssh_tcad_runner.sh"), "install"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "unbound variable" not in completed.stderr
    assert "fake SSH extraction: pass" in completed.stdout
    runner = remote_root / "bin/scidiscovery-tcad-ssh-runner"
    assert runner.is_file()
    assert runner.read_bytes().startswith(b"#!/usr/bin/env python3\n")
    assert runner.stat().st_mode & 0o111
    config = json.loads((remote_root / "config/runner.json").read_text())
    assert config["exchange_root"] == str(remote_root / "exchange")
    assert config["result_root"] == str(remote_root / "state/runs")


def test_installer_probes_the_current_root_tool_count() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    match = re.search(
        r'probe_mcp scidiscovery\.artifact_agent\.interfaces\.mcp_proxy "\$CONTROL_SOCKET" (\d+)',
        script,
    )
    assert match is not None
    assert int(match.group(1)) == len(ROOT_TOOLS)
    assert f"assert len(ROOT_TOOLS) == {len(ROOT_TOOLS)}" in script
    assert f"assert len(WORKER_TOOLS) == {len(WORKER_TOOLS)}" in script
    assert (
        f'assert len(json.load(sys.stdin)["result"]["tools"]) == {len(WORKER_TOOLS)}'
        in script
    )
    assert 'http://127.0.0.1:${APPROVAL_PORT}/")" == 200' in script


def test_installer_activates_independent_sentaurus_code_skill_for_each_platform() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert "install_platform_skills" in script
    assert 'source="${WORKSPACE}/skills/sentaurus-tcad-code"' in script
    assert '${service_home}/.codex/skills' in script
    assert '${service_home}/.claude/skills' in script
    assert 'SCID_PLATFORM must be codex, claude, or both' in script
    assert 'SCID_ENABLE_INGAAS_FIG4 must be 0 or 1' in script


def test_worker_service_allows_bounded_fetch_while_analysis_unshares_network() -> None:
    project_root = Path(__file__).resolve().parents[2]
    template = (
        project_root / "deploy/systemd/scidiscovery-worker.service.in"
    ).read_text(encoding="utf-8")
    assert "PrivateNetwork=true" not in template
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK" in template
    assert "SCIDISCOVERY_ANALYSIS_NETWORK_ISOLATED=1" not in template
    assert "TasksMax=128" in template
    assert "MemoryMax=3G" in template


def test_control_service_allows_wsl_windows_transport_vsock() -> None:
    project_root = Path(__file__).resolve().parents[2]
    template = (
        project_root / "deploy/systemd/scidiscovery-control.service.in"
    ).read_text(encoding="utf-8")
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_VSOCK" in template


def test_deployment_sources_are_machine_neutral() -> None:
    project_root = Path(__file__).resolve().parents[2]
    paths = [
        project_root / "deploy/install.sh",
        project_root / "deploy/install_ssh_tcad_runner.sh",
        *sorted((project_root / "plugins/tcad_artifact/config").glob("*.json")),
    ]
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert not re.search(
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b",
        rendered,
    )
    assert not re.search(
        r"(?:/home/(?!user(?:/|$)|tcad(?:/|$))[A-Za-z0-9._-]+/|"
        r"C:[/\\]Users[/\\](?!user(?:[/\\]|$))[A-Za-z0-9._-]+[/\\])",
        rendered,
        re.IGNORECASE,
    )
    assert 'SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"' in rendered


def test_git_release_builder_emits_clean_manifested_source(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "scidiscovery-agent"
    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts/build_git_release.py"),
            "--source",
            str(project_root),
            "--output",
            str(output),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (output / "README.md").is_file()
    assert (output / "README.zh-CN.md").is_file()
    assert (output / "docs/INSTALL.md").is_file()
    assert (output / "docs/INSTALL.zh-CN.md").is_file()
    assert not (output / "research").exists()
    assert not (output / ".codex").exists()
    assert not any(output.rglob("__pycache__"))
    manifest = output / "MANIFEST.sha256"
    entries = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    readme = output / "README.md"
    assert entries["README.md"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    assert output.with_suffix(".tar.gz").is_file()
