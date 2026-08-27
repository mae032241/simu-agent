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


def test_tcad_deployment_examples_declare_both_direct_solvers() -> None:
    project_root = Path(__file__).resolve().parents[2]
    for relative in (
        "plugins/tcad_artifact/config/remote-runner.example.json",
        "plugins/tcad_artifact/config/execution-policy.example.json",
    ):
        value = json.loads((project_root / relative).read_text(encoding="utf-8"))
        direct = {
            item["solver_kind"]: item
            for item in value["tools"]
            if item["solver_kind"] in {"sprocess", "sdevice"}
        }
        assert set(direct) == {"sprocess", "sdevice"}
        assert direct["sprocess"]["executable"].endswith("/sprocess")
        assert direct["sdevice"]["executable"].endswith("/sdevice")
        assert len({item["profile_id"] for item in direct.values()}) == 2
        assert all(item["release_evidence"] for item in direct.values())


def test_ssh_runner_installer_cleans_up_without_scope_error(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    private_config = tmp_path / "private-runner.json"
    private_config.write_bytes(
        (
            project_root
            / "plugins/tcad_artifact/config/remote-runner.example.json"
        ).read_bytes()
    )
    private_value = json.loads(private_config.read_text(encoding="utf-8"))
    private_value["tools"][0]["executable"] = "/private/bin/sprocess"
    private_value["tools"][1]["executable"] = "/private/bin/sdevice"
    private_config.write_text(json.dumps(private_value), encoding="utf-8")
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
        "SCID_REMOTE_RUNNER_CONFIG": str(private_config),
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


def test_ssh_runner_install_requires_an_explicit_private_config(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    fake_ssh = tmp_path / "ssh"
    fake_ssh.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    fake_ssh.chmod(0o750)

    completed = subprocess.run(
        [str(project_root / "deploy/install_ssh_tcad_runner.sh"), "install"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            key: value
            for key, value in {
                **os.environ,
                "SCID_PROJECT_ROOT": str(project_root),
                "SCID_PYTHON": sys.executable,
                "SCID_SSH_EXE": str(fake_ssh),
                "SCID_SSH_DESTINATION": "tcad@192.0.2.34",
            }.items()
            if key != "SCID_REMOTE_RUNNER_CONFIG"
        },
        timeout=10,
        check=False,
    )

    assert completed.returncode == 66
    assert "SCID_REMOTE_RUNNER_CONFIG" in completed.stderr


def test_ssh_runner_install_rejects_an_unedited_example_copy(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    private_config = tmp_path / "private-runner.json"
    private_config.write_bytes(
        (
            project_root
            / "plugins/tcad_artifact/config/remote-runner.example.json"
        ).read_bytes()
    )
    private_config.chmod(0o600)
    fake_ssh = tmp_path / "ssh"
    fake_ssh.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    fake_ssh.chmod(0o750)

    completed = subprocess.run(
        [str(project_root / "deploy/install_ssh_tcad_runner.sh"), "install"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "SCID_PROJECT_ROOT": str(project_root),
            "SCID_PYTHON": sys.executable,
            "SCID_SSH_EXE": str(fake_ssh),
            "SCID_SSH_DESTINATION": "tcad@192.0.2.34",
            "SCID_REMOTE_RUNNER_CONFIG": str(private_config),
        },
        timeout=10,
        check=False,
    )

    assert completed.returncode != 0
    assert "unedited byte-for-byte copy" in completed.stderr


def test_ssh_runner_code_upgrade_reuses_transport_and_preserves_config(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    remote_root = tmp_path / "remote/scidiscovery-tcad"
    (remote_root / "bin").mkdir(parents=True)
    (remote_root / "config").mkdir()
    remote_runner = remote_root / "bin/scidiscovery-tcad-ssh-runner"
    remote_runner.write_bytes(b"#!/usr/bin/env python3\n# old runner\n")
    remote_runner.chmod(0o750)
    remote_config = remote_root / "config/runner.json"
    config_bytes = b'{"private":"must-remain-byte-identical"}\n'
    remote_config.write_bytes(config_bytes)

    resolver = tmp_path / "resolve-vm"
    resolver.write_text(
        f"#!{sys.executable}\nprint('192.0.2.34')\n",
        encoding="utf-8",
    )
    resolver.chmod(0o750)
    fake_ssh = tmp_path / "ssh"
    fake_ssh.write_text(
        f"""#!{sys.executable}
import os
import pathlib
import sys
import tarfile

root = pathlib.Path(os.environ["SCID_FAKE_REMOTE_ROOT"])
assert "tcad@192.0.2.34" in sys.argv
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as archive:
    names = []
    for member in archive:
        names.append(member.name)
        archive.extract(member, root)
    assert names == [
        "bin",
        "bin/scidiscovery-tcad-ssh-runner",
    ]
    assert all(not name.startswith("config") for name in names)
print("fake SSH code-only extraction: pass")
""",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o750)
    transport = tmp_path / "tcad-transport.json"
    transport.write_text(
        json.dumps(
            {
                "ssh_executable": str(fake_ssh),
                "identity_file": None,
                "destination": "tcad@192.0.2.10",
                "destination_resolver": [str(resolver)],
                "port": 22,
                "host_key_alias": "test-vm",
                "known_hosts_file": str(tmp_path / "known_hosts"),
                "remote_helper": str(remote_runner),
                "remote_config": str(remote_config),
                "remote_exchange_root": str(remote_root / "exchange"),
                "connect_timeout_seconds": 5,
                "operation_timeout_seconds": 30,
                "max_transfer_bytes": 1024 * 1024,
            }
        ),
        encoding="utf-8",
    )
    transport.chmod(0o640)

    completed = subprocess.run(
        [
            str(project_root / "deploy/install_ssh_tcad_runner.sh"),
            "upgrade-code",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "SCID_PROJECT_ROOT": str(project_root),
            "SCID_PYTHON": sys.executable,
            "SCID_TCAD_TRANSPORT_CONFIG": str(transport),
            "SCID_FAKE_REMOTE_ROOT": str(remote_root),
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "fake SSH code-only extraction: pass" in completed.stdout
    assert remote_config.read_bytes() == config_bytes
    assert remote_runner.read_bytes() == (
        project_root
        / "plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py"
    ).read_bytes()


def test_ssh_runner_code_upgrade_rejects_mismatched_remote_binding(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    fake_ssh = tmp_path / "ssh"
    fake_ssh.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    fake_ssh.chmod(0o750)
    transport = tmp_path / "tcad-transport.json"
    transport.write_text(
        json.dumps(
            {
                "ssh_executable": str(fake_ssh),
                "destination": "tcad@192.0.2.10",
                "remote_helper": "/home/tcad/scidiscovery-tcad/bin/scidiscovery-tcad-ssh-runner",
                "remote_config": "/home/tcad/other/config/runner.json",
                "remote_exchange_root": "/home/tcad/scidiscovery-tcad/exchange",
            }
        ),
        encoding="utf-8",
    )
    transport.chmod(0o640)

    completed = subprocess.run(
        [
            str(project_root / "deploy/install_ssh_tcad_runner.sh"),
            "upgrade-code",
            "--dry-run",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "SCID_PROJECT_ROOT": str(project_root),
            "SCID_PYTHON": sys.executable,
            "SCID_TCAD_TRANSPORT_CONFIG": str(transport),
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode != 0
    assert "remote_config must remain under the runner root" in completed.stderr


def test_ssh_runner_full_install_reuses_active_transport(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    remote_root = tmp_path / "remote/scidiscovery-tcad"
    remote_root.mkdir(parents=True)
    resolver = tmp_path / "resolve-vm"
    resolver.write_text(
        f"#!{sys.executable}\nprint('192.0.2.44')\n",
        encoding="utf-8",
    )
    resolver.chmod(0o750)
    fake_ssh = tmp_path / "ssh"
    fake_ssh.write_text(
        f"""#!{sys.executable}
import io
import os
import subprocess
import sys
import tarfile

assert "tcad@192.0.2.44" in sys.argv
payload = sys.stdin.buffer.read()
with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
    names = archive.getnames()
assert names == [
    "bin",
    "bin/scidiscovery-tcad-ssh-runner",
    "config",
    "config/runner.json",
]
completed = subprocess.run(
    sys.argv[-1],
    shell=True,
    input=payload,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    check=False,
)
sys.stdout.buffer.write(completed.stdout)
sys.stderr.buffer.write(completed.stderr)
raise SystemExit(completed.returncode)
""",
        encoding="utf-8",
    )
    fake_ssh.chmod(0o750)
    remote_runner = remote_root / "bin/scidiscovery-tcad-ssh-runner"
    remote_config = remote_root / "config/runner.json"
    transport = tmp_path / "tcad-transport.json"
    transport.write_text(
        json.dumps(
            {
                "ssh_executable": str(fake_ssh),
                "destination": "tcad@192.0.2.10",
                "destination_resolver": [str(resolver)],
                "remote_helper": str(remote_runner),
                "remote_config": str(remote_config),
                "remote_exchange_root": str(remote_root / "exchange"),
            }
        ),
        encoding="utf-8",
    )
    transport.chmod(0o640)
    private_config = tmp_path / "private-runner.json"
    value = json.loads(
        (
            project_root
            / "plugins/tcad_artifact/config/remote-runner.example.json"
        ).read_text(encoding="utf-8")
    )
    fake_tools = tmp_path / "tools"
    fake_tools.mkdir()
    for item in value["tools"]:
        executable = fake_tools / item["solver_kind"]
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o750)
        item["executable"] = str(executable)
        item["environment"] = {}
    private_config.write_text(json.dumps(value), encoding="utf-8")
    private_config.chmod(0o600)

    completed = subprocess.run(
        [
            str(project_root / "deploy/install_ssh_tcad_runner.sh"),
            "install-from-transport",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "SCID_PROJECT_ROOT": str(project_root),
            "SCID_PYTHON": sys.executable,
            "SCID_TCAD_TRANSPORT_CONFIG": str(transport),
            "SCID_REMOTE_RUNNER_CONFIG": str(private_config),
            "SCID_FAKE_REMOTE_ROOT": str(remote_root),
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "SSH TCAD runner transport install: pass" in completed.stdout
    installed = json.loads(remote_config.read_text(encoding="utf-8"))
    assert installed["exchange_root"] == str(remote_root / "exchange")
    assert installed["state_root"] == str(remote_root / "state")
    assert installed["result_root"] == str(remote_root / "state/runs")
    assert {item["solver_kind"] for item in installed["tools"]} == {
        "sprocess",
        "sdevice",
    }


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


def test_installer_activates_independent_sentaurus_code_skill_for_codex() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert "install_platform_skills" in script
    assert "sentaurus-tcad-code" in script
    assert "scientific-paper-evidence" in script
    assert 'source="${SOURCE_ROOT}/skills/${skill}"' in script
    assert 'target="${skill_root}/${skill}"' in script
    assert 'for skill in "${PLATFORM_SKILLS[@]}"' in script
    assert '${service_home}/.codex/skills' in script
    assert '.claude' not in script
    assert 'SCID_PLATFORM must be codex' in script
    assert 'readonly PLUGIN_SPECIFICATION="${SCID_PLUGINS:-tcad_artifact,curve_score}"' in script
    assert "deploy/plugin_selection.py" in script
    assert 'SCID_ENABLE_INGAAS_FIG4' not in script


def test_installer_separates_source_repository_from_project_workspace() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert 'readonly SOURCE_ROOT=' in script
    assert 'readonly WORKSPACE="${SCID_WORKSPACE:-${SOURCE_ROOT}/workspace/default}"' in script
    assert '[[ "$WORKSPACE" != "$SOURCE_ROOT" ]]' in script
    assert '"${SOURCE_ROOT}/deploy/systemd/scidiscovery-control.service.in"' in script
    assert '"PROJECT_ROOT=${WORKSPACE}"' in script
    assert "'codex', source_root" in script
    assert "codex_config_root=source_root / '.codex'" in script
    assert "'claude'" not in script
    assert 'rm -rf "$WORKSPACE/.codex"' in script


def test_platform_configuration_repairs_only_managed_path_permissions() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")

    assert "prepare_managed_platform_paths" in script
    for managed_path in (
        '"$SOURCE_ROOT/.codex"',
        '"$WORKSPACE/.codex"',
        '"$SOURCE_ROOT/AGENTS.md"',
        '"$WORKSPACE/AGENTS.md"',
    ):
        assert managed_path in script
    assert ".claude" not in script
    assert "CLAUDE.md" not in script
    assert 'chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE"' not in script
    assert 'managed platform directory contains a symlink' in script
    assert "    prepare_managed_platform_paths\n    runuser" in script


def test_installer_repairs_only_mutable_database_ownership_before_start() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")

    assert "normalize_database_ownership" in script
    assert 'directories=("${SCID_STATE}/database" "$TCAD_STATE")' in script
    assert "-maxdepth 1 -type l -name '*.sqlite3*'" in script
    assert "-maxdepth 1 -type f -name '*.sqlite3*'" in script
    assert 'chown -R "$SERVICE_USER:$SERVICE_GROUP" "$SCID_STATE"' not in script
    install_all = script.index("install_all() {")
    normalize = script.index("    normalize_database_ownership", install_all)
    service_start = script.index("    systemctl enable --now", install_all)
    assert normalize < service_start


def test_installer_builds_local_packages_offline_before_stopping_services() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert "validate_base_python" in script
    assert 'parsed_version("pydantic")' in script
    assert 'parsed_version("PyYAML")' in script
    assert 'parsed_version("Pillow")' in script
    assert 'base Python requires Pillow>=10,<13' in script
    assert 'parsed_version("setuptools")' in script
    assert "from packaging.version import Version" in script
    assert "--no-input --no-index" in script
    assert "--no-deps --no-build-isolation" in script
    assert "--progress-bar off --upgrade" in script
    assert '--target "$stage" "${package_roots[@]}"\n        >/dev/null' not in script
    assert '"$SOURCE_ROOT/skills"' in script
    assert "installed package is missing the scientific paper evidence tool" in script
    install_all = script.index("install_all() {")
    package_install = script.index("    install_packages", install_all)
    transaction_begin = script.index("    begin_install_transaction", install_all)
    retire_services = script.index("    retire_old_deployment", install_all)
    package_activation = script.index("    activate_packages", install_all)
    installation_probe = script.index("    verify_installation", install_all)
    transaction_complete = script.index("    complete_install_transaction", install_all)
    assert package_install < transaction_begin < retire_services < package_activation
    assert package_activation < installation_probe < transaction_complete
    assert "scidiscovery.runtime_identity write" in script
    assert "scidiscovery.runtime_identity verify" in script


def test_installer_transaction_covers_every_mutated_release_surface() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")

    assert "begin_install_transaction" in script
    assert "rollback_install" in script
    assert "complete_install_transaction" in script
    assert "install_transaction.py\" begin" in script
    assert "install_transaction.py\" rollback" in script
    assert "install_transaction.py\" seal" in script
    for target in (
        "site=${SITE_ROOT}",
        "scid-cli=/usr/local/bin/scid",
        "tcad-transport-cli=/usr/local/bin/scidiscovery-tcad-transport",
        "tcad-policy=${CONFIG_ROOT}/tcad-policy.json",
        "task-secret=${CONFIG_ROOT}/task-token.key",
        "approval-secret=${CONFIG_ROOT}/approval-receipt.key",
        "framework-codex=${SOURCE_ROOT}/.codex",
        "framework-agents=${SOURCE_ROOT}/AGENTS.md",
        "workspace-codex=${WORKSPACE}/.codex",
        "codex-skill-${skill}=",
        "unit-${unit%.service}",
        "artifact_agent task_tokens tasks approvals executions scheduler-bindings",
        "db-tcad-submissions",
    ):
        assert target in script
    assert "claude-skill-" not in script
    assert "active-units.txt" in script
    assert "enabled-units.txt" in script
    assert "trap 'rollback_install $?' ERR" in script
    assert 'chown "$SERVICE_USER:$SERVICE_GROUP" "$secret"' in script
    assert 'chmod 0600 "$secret"' in script


def test_installer_requires_paper_evidence_runtime_sources_and_tools() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    metadata = (project_root / "pyproject.toml").read_text(encoding="utf-8")

    for relative in (
        "skills/scientific-paper-evidence/SKILL.md",
        "skills/scientific-paper-evidence/agents/openai.yaml",
        "skills/scientific-paper-evidence/references/digitization-spec.md",
        "skills/scientific-paper-evidence/scripts/digitize_plot.py",
        "skills/scientific-paper-evidence/scripts/render_curve_support.py",
        "skills/scientific-paper-evidence/scripts/validate_evidence_bundle.py",
    ):
        assert relative in script
    assert 'command -v pdfimages' in script
    assert 'command -v pdftoppm' in script
    assert '"Pillow>=10,<13"' in metadata


def test_installer_requires_release_matched_tcad_manual_skill_sources() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")

    for relative in (
        "skills/sentaurus-tcad-code/references/control-materialization.md",
        "skills/sentaurus-tcad-code/references/diagnostics.md",
        "skills/sentaurus-tcad-code/references/execution-contract.md",
        "skills/sentaurus-tcad-code/references/review.md",
        "skills/sentaurus-tcad-code/references/sdevice.md",
        "skills/sentaurus-tcad-code/references/sprocess.md",
        "skills/sentaurus-tcad-code/references/sprocess-r2020.09-recipes.md",
        "skills/sentaurus-tcad-code/references/manuals/catalog.json",
        "skills/sentaurus-tcad-code/references/manuals/topics.json",
        "skills/sentaurus-tcad-code/references/manuals/R-2020.09/sprocess_ug.pdf",
        "skills/sentaurus-tcad-code/references/manuals/R-2020.09/sdevice_ug.pdf",
        "skills/sentaurus-tcad-code/references/manuals/R-2020.09/sentaurus_relnote.pdf",
        "skills/sentaurus-tcad-code/scripts/manual_search.py",
        "skills/sentaurus-tcad-code/scripts/manual_extract.py",
    ):
        assert relative in script


def test_generic_reinstaller_passes_resolved_configuration(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    wrapper = project_root / "deploy/reinstall.sh"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command_config = tmp_path / "command-adapter.json"
    command_config.write_text("{}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_sudo = fake_bin / "sudo"
    fake_sudo.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    fake_sudo.chmod(0o750)
    completed = subprocess.run(
        [str(wrapper), "reinstall"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "SCID_WORKSPACE": str(workspace),
            "SCID_PYTHON": sys.executable,
            "SCID_SERVICE_USER": "test-user",
            "SCID_SERVICE_GROUP": "test-group",
            "SCID_PLATFORM": "codex",
            "SCID_PLUGINS": "tcad_artifact,curve_score",
            "SCID_WEB_FETCH_ALLOW_FAKE_IP": "1",
            "SCID_TCAD_COMMAND_CONFIG": str(command_config),
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout.splitlines()
    assert f"SCID_WORKSPACE={workspace}" in output
    assert f"SCID_PYTHON={sys.executable}" in output
    assert "SCID_SERVICE_USER=test-user" in output
    assert "SCID_SERVICE_GROUP=test-group" in output
    assert "SCID_PLATFORM=codex" in output
    assert "SCID_PLUGINS=tcad_artifact,curve_score" in output
    assert "SCID_WEB_FETCH_ALLOW_FAKE_IP=1" in output
    assert f"SCID_TCAD_COMMAND_CONFIG={command_config}" in output
    assert str(project_root / "deploy/install.sh") in output
    assert output[-1] == "install"


def test_ingaas_profile_delegates_to_generic_reinstaller(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    wrapper = project_root / "deploy/apply_ingaas_fig4_profile.sh"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command_config = tmp_path / "command-adapter.json"
    command_config.write_text("{}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_sudo = fake_bin / "sudo"
    fake_sudo.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    fake_sudo.chmod(0o750)
    completed = subprocess.run(
        [str(wrapper), "reinstall"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "SCID_WORKSPACE": str(workspace),
            "SCID_PYTHON": sys.executable,
            "SCID_SERVICE_USER": "test-user",
            "SCID_SERVICE_GROUP": "test-group",
            "SCID_PLATFORM": "codex",
            "SCID_TCAD_COMMAND_CONFIG": str(command_config),
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout.splitlines()
    assert "SCID_PLUGINS=tcad_artifact,curve_score,ingaas_fig4" in output
    assert f"SCID_TCAD_COMMAND_CONFIG={command_config}" in output
    assert str(project_root / "deploy/install.sh") in output
    assert output[-1] == "install"


def test_legacy_cleanup_script_preserves_current_service_roots() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (
        project_root / "deploy/cleanup_legacy_services.sh"
    ).read_text(encoding="utf-8")
    assert "--dry-run" in script
    assert 'clean) [[ "$(id -u)" -eq 0 ]]' in script
    assert "validate_current_installation" in script
    assert "systemctl is-active --quiet" in script
    assert "/var/lib/artifact-agent-vnext" in script
    assert "/opt/artifact-agent-vnext" in script
    assert "/var/lib/tcad-control" in script
    assert "/opt/tcad-control" in script
    assert 'rm -rf --one-file-system -- "$path"' in script
    assert 'delete_tree "$CURRENT_INSTALL_ROOT"' not in script
    assert 'delete_tree "$CURRENT_CONFIG_ROOT"' not in script
    assert 'delete_tree "$CURRENT_STATE_ROOT"' not in script
    assert "SCID_BACKUPS_TO_KEEP" in script


def test_workspace_initializer_creates_only_project_scoped_directories(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace_root = tmp_path / "workspace"
    completed = subprocess.run(
        [str(project_root / "deploy/init_workspace.sh"), "paper_case"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "SCID_WORKSPACE_ROOT": str(workspace_root)},
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    created = workspace_root / "paper_case"
    assert (created / "inputs/papers").is_dir()
    assert (created / "research").is_dir()
    assert (created / "results").is_dir()
    assert (created / "runtime").is_dir()
    assert (created / "sentaurus").is_dir()
    assert not any(path.is_file() for path in created.rglob("*"))
    assert created.stat().st_mode & 0o777 == 0o750
    assert all(
        path.stat().st_mode & 0o777 == 0o750
        for path in created.rglob("*")
        if path.is_dir()
    )


def test_systemd_templates_use_directive_appropriate_path_quoting() -> None:
    project_root = Path(__file__).resolve().parents[2]
    templates = tuple((project_root / "deploy/systemd").glob("*.service.in")) + (
        project_root
        / "plugins/tcad_artifact/deploy/systemd/tcad-control.service.in",
    )
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in templates)
    installer = (project_root / "deploy/install.sh").read_text(encoding="utf-8")

    assert 'WorkingDirectory=@PROJECT_ROOT@' in rendered
    assert 'WorkingDirectory="@PROJECT_ROOT@"' not in rendered
    assert 'Environment="PYTHONPATH=@PYTHONPATH@"' in rendered
    assert '--project-root "@PROJECT_ROOT@"' in rendered
    assert 'ReadWritePaths="@STATE_ROOT@"' in rendered
    assert "validate_systemd_value" in installer
    assert 'command -v systemd-analyze' in installer
    assert 'systemd-analyze verify "$stage"/*.service' in installer
    assert 'adapter_args="--tcad-command-config \\"${TCAD_COMMAND_CONFIG}\\""' in installer
    assert '[[ ! "$value" =~ [[:cntrl:]]' in installer
    assert '"$value" != *\'$\'* && "$value" != *\'@\'*' in installer
    assert "printf -v quoted_python '%q' \"$PYTHON\"" in installer
    assert "printf -v quoted_site_root '%q' \"$SITE_ROOT\"" in installer
    assert "PYTHONPATH=${quoted_site_root} ${quoted_python}" in installer


def test_worker_service_allows_bounded_fetch_while_analysis_unshares_network() -> None:
    project_root = Path(__file__).resolve().parents[2]
    template = (
        project_root / "deploy/systemd/scidiscovery-worker.service.in"
    ).read_text(encoding="utf-8")
    assert "PrivateNetwork=true" not in template
    assert (
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK AF_VSOCK"
        in template
    )
    assert "SCIDISCOVERY_ANALYSIS_NETWORK_ISOLATED=1" not in template
    assert (
        "Environment=SCID_WEB_FETCH_ALLOW_FAKE_IP=@WEB_FETCH_ALLOW_FAKE_IP@"
        in template
    )
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
    assert 'SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"' in rendered
    assert "-name build" in (project_root / "deploy/install.sh").read_text(
        encoding="utf-8"
    )


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
    assert (output / "docs/TCAD_QUALIFICATION_STATUS.md").is_file()
    assert (
        output / "docs/plans/TCAD_AGENT_REAUDIT_REMEDIATION_PLAN.zh-CN.md"
    ).is_file()
    assert (output / "deploy/install_transaction.py").is_file()
    assert (output / "deploy/init_workspace.sh").is_file()
    digitizer = output / "skills/scientific-paper-evidence/scripts/digitize_plot.py"
    assert digitizer.is_file()
    assert digitizer.stat().st_mode & 0o111
    validator = (
        output
        / "skills/scientific-paper-evidence/scripts/validate_evidence_bundle.py"
    )
    assert validator.is_file()
    assert validator.stat().st_mode & 0o111
    renderer = (
        output
        / "skills/scientific-paper-evidence/scripts/render_curve_support.py"
    )
    assert renderer.is_file()
    assert renderer.stat().st_mode & 0o111
    assert (
        output / "skills/scientific-paper-evidence/references/digitization-spec.md"
    ).is_file()
    manual_root = output / "skills/sentaurus-tcad-code/references/manuals"
    for relative, digest in (
        (
            "R-2020.09/sprocess_ug.pdf",
            "bcaf5cfe87bd276a2068fa6681a0b62b2526512b65a710a660d892c45ceaf5d9",
        ),
        (
            "R-2020.09/sdevice_ug.pdf",
            "dae2c94b29c92705d3b8d6124c2f0ab595541ed48e4b220a425f72fac42794ce",
        ),
        (
            "R-2020.09/sentaurus_relnote.pdf",
            "0e6679154406b2d12356be28ab901a3786f48ca9b91b14f6769ada508bdbfbf9",
        ),
    ):
        manual = manual_root / relative
        assert manual.is_file()
        assert hashlib.sha256(manual.read_bytes()).hexdigest() == digest
    for name in ("manual_search.py", "manual_extract.py"):
        helper = output / "skills/sentaurus-tcad-code/scripts" / name
        assert helper.is_file()
        assert helper.stat().st_mode & 0o111
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
