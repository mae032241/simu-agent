from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

from deploy.install_transaction import (
    begin_transaction,
    mark_managed_directory,
    rollback_transaction,
)

def test_primary_installer_has_valid_shell_syntax() -> None:
    project_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        ["bash", "-n", str(project_root / "deploy/install.sh")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_one_backend_value_drives_daemon_platform_and_install_verification() -> None:
    project_root = Path(__file__).resolve().parents[2]
    installer = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    unit = (
        project_root / "deploy/systemd/scidiscovery-control.service.in"
    ).read_text(encoding="utf-8")
    approval_unit = (
        project_root / "deploy/systemd/scidiscovery-approval-ui.service.in"
    ).read_text(encoding="utf-8")
    daemon = (
        project_root
        / "src/scidiscovery/artifact_agent/interfaces/mcp_daemon.py"
    ).read_text(encoding="utf-8")
    cli = (
        project_root / "src/scidiscovery/artifact_agent/interfaces/cli.py"
    ).read_text(encoding="utf-8")

    assert 'WORKER_BACKEND="${SCID_WORKER_BACKEND:-local}"' in installer
    assert "SCID_WORKER_BACKEND must be local or hardened" in installer
    assert "'worker_backend': '$WORKER_BACKEND'" in installer
    assert 'worker_backend=worker_backend' in installer
    assert '--worker-backend "@WORKER_BACKEND@"' in unit
    assert '--worker-backend "@WORKER_BACKEND@"' in approval_unit
    assert 'choices=("local", "hardened")' in daemon
    assert "worker_backend=args.worker_backend" in daemon
    assert 'choices=("local", "hardened")' in cli
    assert "worker_backend=args.worker_backend" in cli
    assert 'worker_backend=getattr(args, "worker_backend", "local")' in cli


def test_rendered_units_share_only_the_local_run_workspace(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "deploy/install.sh"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def render(backend: str) -> tuple[str, str]:
        output = tmp_path / backend
        completed = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; render_units "$2"',
                "bash",
                str(script),
                str(output),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={
                **os.environ,
                "SCID_WORKSPACE": str(workspace),
                "SCID_PYTHON": sys.executable,
                "SCID_WORKER_BACKEND": backend,
                "SCID_STATE_ROOT": str(tmp_path / "state"),
                "SCID_INSTALL_ROOT": str(tmp_path / "install"),
                "SCID_CONFIG_ROOT": str(tmp_path / "config"),
                "SCID_BACKUP_ROOT": str(tmp_path / "backups"),
            },
            timeout=10,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        return (
            (output / "scidiscovery-control.service").read_text("utf-8"),
            (output / "scidiscovery-approval-ui.service").read_text("utf-8"),
        )

    local_control, local_ui = render("local")
    local_root = str(workspace / ".scidiscovery-runs")
    assert local_root in local_control
    assert local_root in local_ui
    assert '--worker-backend "local"' in local_ui

    hardened_control, hardened_ui = render("hardened")
    assert local_root not in hardened_control
    assert local_root not in hardened_ui
    assert '--local-workspace-root' not in hardened_control
    assert '--worker-backend "hardened"' in hardened_ui


def test_installer_previews_core_only_and_explicit_tcad_paths(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "deploy/install.sh"

    def preview(name: str, plugins: str, backend: str = "local") -> str:
        root = tmp_path / name
        workspace = root / "workspace"
        workspace.mkdir(parents=True)
        service_user = subprocess.run(
            ["id", "-un"], check=True, capture_output=True, text=True
        ).stdout.strip()
        environment = {
            **os.environ,
            "SCID_WORKSPACE": str(workspace),
            "SCID_PYTHON": sys.executable,
            "SCID_SERVICE_USER": service_user,
            "SCID_SERVICE_GROUP": subprocess.run(
                ["id", "-gn"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "SCID_PLUGINS": plugins,
            "SCID_WORKER_BACKEND": backend,
            "SCID_INSTALL_ROOT": str(root / "install"),
            "SCID_STATE_ROOT": str(root / "state"),
            "TCAD_STATE_ROOT": str(root / "tcad-state"),
            "SCID_CONFIG_ROOT": str(root / "config"),
            "SCID_BACKUP_ROOT": str(root / "backups"),
        }
        completed = subprocess.run(
            [str(script), "--dry-run"],
            cwd=project_root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        return completed.stdout

    core = preview("core", "")
    assert "Selected plugins: none" in core
    assert "scidiscovery-control.service" in core
    assert "tcad-control.service" not in core
    assert "Worker backend: local" in core

    hardened = preview("hardened", "", "hardened")
    assert "Worker backend: hardened" in hardened
    assert "deployment preview: pass" in hardened

    tcad = preview("tcad", "tcad_artifact,curve_score")
    assert "Selected plugins: tcad_artifact,curve_score" in tcad
    assert "scidiscovery-control.service" in tcad
    assert "tcad-control.service" in tcad

    figure = preview("figure", "curve_score,curve_figure_evidence")
    assert (
        "Selected plugins: curve_score,curve_figure_evidence" in figure
    )


def test_tcad_runtime_configuration_is_owned_and_executed_by_plugin(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    helper = project_root / "plugins/tcad_artifact/deploy/configure_runtime.py"
    policy = tmp_path / "tcad-policy.json"
    plugin_config = tmp_path / "tcad-plugin.json"
    state_root = tmp_path / "state"
    socket = tmp_path / "tcad.sock"
    state_root.mkdir()

    completed = subprocess.run(
        [
            sys.executable,
            str(helper),
            "--policy",
            str(policy),
            "--plugin-config",
            str(plugin_config),
            "--state-root",
            str(state_root),
            "--socket",
            str(socket),
        ],
        cwd=project_root,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                (
                    str(project_root / "src"),
                    str(project_root / "plugins/tcad_artifact"),
                )
            ),
        },
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    configured_policy = json.loads(policy.read_text(encoding="utf-8"))
    configured_transport = json.loads(plugin_config.read_text(encoding="utf-8"))
    assert configured_policy["allowed_input_roots"] == [
        str(state_root / "execution-exchange")
    ]
    assert configured_transport == {
        "transport": "socket",
        "socket_path": str(socket),
    }


def test_core_install_retires_and_rollback_restores_tcad_surfaces(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    skill = tmp_path / "codex/skills/sentaurus-tcad-code"
    transport = tmp_path / "bin/scidiscovery-tcad-transport"
    unit = tmp_path / "systemd/tcad-control.service"
    skill.mkdir(parents=True)
    transport.parent.mkdir(parents=True)
    unit.parent.mkdir(parents=True)
    (skill / "SKILL.md").write_text("managed TCAD Skill\n", encoding="utf-8")
    mark_managed_directory(skill, name="codex-skill-sentaurus-tcad-code")
    transport.write_text("managed TCAD transport\n", encoding="utf-8")
    unit.write_text("managed TCAD unit\n", encoding="utf-8")
    transaction = tmp_path / "transaction"
    begin_transaction(
        transaction,
        targets=(
            ("codex-skill-sentaurus-tcad-code", skill),
            ("tcad-transport-cli", transport),
            ("unit-tcad-control", unit),
        ),
    )

    completed = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; ROLLBACK_ARMED=1; '
            'TRANSACTION_ROOT="$5"; '
            'retire_inactive_tcad_surfaces "$2" "$3" "$4"',
            "bash",
            str(project_root / "deploy/install.sh"),
            str(transport),
            str(unit),
            str(skill),
            str(transaction),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert not skill.exists()
    assert not transport.exists()
    assert not unit.exists()

    rollback_transaction(transaction)
    assert (skill / "SKILL.md").read_text(encoding="utf-8") == (
        "managed TCAD Skill\n"
    )
    assert transport.read_text(encoding="utf-8") == "managed TCAD transport\n"
    assert unit.read_text(encoding="utf-8") == "managed TCAD unit\n"


def test_upgrade_removes_legacy_worker_unit_and_rollback_restores_it(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    unit = tmp_path / "systemd/scidiscovery-worker.service"
    unit.parent.mkdir(parents=True)
    unit.write_text("legacy worker unit\n", encoding="utf-8")
    transaction = tmp_path / "transaction"
    begin_transaction(
        transaction,
        targets=(("unit-scidiscovery-worker", unit),),
    )

    completed = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; TRANSACTION_ROOT="$3"; '
            'retire_legacy_worker_unit "$2"',
            "bash",
            str(project_root / "deploy/install.sh"),
            str(unit),
            str(transaction),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert not unit.exists()
    rollback_transaction(transaction)
    assert unit.read_text(encoding="utf-8") == "legacy worker unit\n"


def test_tcad_surface_retirement_rejects_unowned_or_unbound_skill(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "deploy/install.sh"

    def attempt(
        name: str, *, mark: bool, bind: bool, tamper: bool = False
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        root = tmp_path / name
        skill = root / "skills/sentaurus-tcad-code"
        transport = root / "bin/scidiscovery-tcad-transport"
        unit = root / "systemd/tcad-control.service"
        skill.mkdir(parents=True)
        transport.parent.mkdir(parents=True)
        unit.parent.mkdir(parents=True)
        (skill / "SKILL.md").write_text(name, encoding="utf-8")
        transport.write_text(name, encoding="utf-8")
        unit.write_text(name, encoding="utf-8")
        if mark:
            mark_managed_directory(skill, name="codex-skill-sentaurus-tcad-code")
        if tamper:
            (skill / "SKILL.md").write_text(f"{name}-changed", encoding="utf-8")
        transaction = root / "transaction"
        targets = (
            (("codex-skill-sentaurus-tcad-code", skill),) if bind else ()
        ) + (
            ("tcad-transport-cli", transport),
            ("unit-tcad-control", unit),
        )
        begin_transaction(transaction, targets=targets)
        completed = subprocess.run(
            [
                "bash", "-c",
                'source "$1"; ROLLBACK_ARMED=1; TRANSACTION_ROOT="$5"; '
                'retire_inactive_tcad_surfaces "$2" "$3" "$4"',
                "bash", str(script), str(transport), str(unit), str(skill),
                str(transaction),
            ],
            cwd=project_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed, skill

    unowned, unowned_skill = attempt("unowned", mark=False, bind=True)
    assert unowned.returncode != 0
    assert unowned_skill.is_dir()
    assert "ownership is unavailable" in unowned.stderr

    unbound, unbound_skill = attempt("unbound", mark=True, bind=False)
    assert unbound.returncode != 0
    assert unbound_skill.is_dir()
    assert "not bound to the active install transaction" in unbound.stderr

    changed, changed_skill = attempt(
        "changed", mark=True, bind=True, tamper=True
    )
    assert changed.returncode != 0
    assert changed_skill.is_dir()
    assert "ownership or content has changed" in changed.stderr


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
    assert tuple(
        (project_root / "plugins/tcad_artifact/tcad_artifact").rglob(
            "remote_runner_py36*.pyc"
        )
    ) == ()


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


def test_installer_probes_compiled_operation_authority_without_fixed_counts() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert "probe_mcp()" in script
    assert '"$CONTROL_SOCKET" "" root' in script
    assert '"$WORKER_SOCKET" "$worker_id" worker' not in script
    retired = script.split("retire_old_deployment()", 1)[1].split(
        "install_packages()", 1
    )[0]
    assert "scidiscovery-worker.service" in retired
    for operation_tool in (
        "operation_catalog",
        "operation_preflight",
        "operation_invoke",
    ):
        assert operation_tool in script
    for retired in (
        "task_schedule",
        "artifact_transform",
        "approval_request_create",
        "execution_request_create",
        "execution_approval_request_create",
    ):
        assert retired in script
    assert "assert len(ROOT_TOOLS)" not in script
    assert "assert len(WORKER_TOOLS)" not in script
    assert "--worker-id ideator" not in script
    assert 'http://127.0.0.1:${APPROVAL_PORT}/")" == 200' in script


def test_installer_activates_only_explicitly_selected_domain_skills() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert "install_platform_skills" in script
    assert "sentaurus-tcad-code" in script
    assert "scientific-paper-evidence" not in script
    assert 'source="${SOURCE_ROOT}/skills/${skill}"' in script
    assert 'target="${skill_root}/${skill}"' in script
    assert 'for skill in "${PLATFORM_SKILLS[@]}"' in script
    assert '${service_home}/.codex/skills' in script
    assert '.claude' not in script
    assert 'SCID_PLATFORM must be codex' in script
    assert 'readonly PLUGIN_SPECIFICATION="${SCID_PLUGINS:-}"' in script
    assert "declare -a PLATFORM_SKILLS=()" in script
    assert "PLATFORM_SKILLS+=(sentaurus-tcad-code)" in script
    assert 'if [[ "$TCAD_ENABLED" -eq 1' in script
    assert "import tcad_artifact" not in script
    assert "deploy/plugin_selection.py" in script
    assert 'SCID_ENABLE_INGAAS_FIG4' not in script


def test_installer_separates_source_repository_from_project_workspace() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert 'readonly SOURCE_ROOT=' in script
    assert 'readonly WORKSPACE="${SCID_WORKSPACE:-${SOURCE_ROOT}/workspace/default}"' in script
    assert 'readonly LOCAL_WORKSPACE_ROOT="${WORKSPACE}/.scidiscovery-runs"' in script
    assert '[[ "$WORKSPACE" != "$SOURCE_ROOT" ]]' in script
    assert '"${SOURCE_ROOT}/deploy/systemd/scidiscovery-control.service.in"' in script
    assert '"PROJECT_ROOT=${WORKSPACE}"' in script
    assert 'local_workspace_args="--local-workspace-root \\"${LOCAL_WORKSPACE_ROOT}\\""' in script
    assert '"LOCAL_WORKSPACE_ARGS=${local_workspace_args}"' in script
    assert '@LOCAL_WORKSPACE_ARGS@' in (
        project_root / "deploy/systemd/scidiscovery-control.service.in"
    ).read_text(encoding="utf-8")
    assert "'codex', source_root" in script
    assert "codex_config_root=source_root / '.codex'" in script
    assert "'claude'" not in script
    assert 'rm -rf "$WORKSPACE/.codex"' in script


def test_installer_rejects_unsafe_local_workspace_roots(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / ".scidiscovery-runs").symlink_to(outside, target_is_directory=True)
    environment = {
        **os.environ,
        "SCID_WORKSPACE": str(workspace),
        "SCID_PYTHON": sys.executable,
    }
    symbolic = subprocess.run(
        [str(project_root / "deploy/install.sh"), "--dry-run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        timeout=10,
        check=False,
    )
    assert symbolic.returncode != 0
    assert "must not be a symbolic link" in symbolic.stderr

    (workspace / ".scidiscovery-runs").unlink()
    overlap = subprocess.run(
        [str(project_root / "deploy/install.sh"), "--dry-run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **environment,
            "SCID_STATE_ROOT": str(workspace / ".scidiscovery-runs/state"),
        },
        timeout=10,
        check=False,
    )
    assert overlap.returncode != 0
    assert "must not overlap SCID_STATE_ROOT" in overlap.stderr
    script_text = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    assert "create_local_workspace_root" in script_text
    assert "os.O_NOFOLLOW" in script_text
    assert 'os.mkdir(".scidiscovery-runs", mode=0o700, dir_fd=parent)' in script_text


def test_atomic_local_workspace_creation_refuses_a_late_symlink(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir(mode=0o755)
    (workspace / ".scidiscovery-runs").symlink_to(
        outside, target_is_directory=True
    )
    before_mode = outside.stat().st_mode
    completed = subprocess.run(
        [
            "bash",
            "-c",
            f"source {project_root / 'deploy/install.sh'}; "
            "create_local_workspace_root",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "SCID_WORKSPACE": str(workspace),
            "SCID_PYTHON": sys.executable,
            "SCID_SERVICE_USER": subprocess.run(
                ["id", "-un"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "SCID_SERVICE_GROUP": subprocess.run(
                ["id", "-gn"], check=True, capture_output=True, text=True
            ).stdout.strip(),
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode != 0
    assert outside.stat().st_mode == before_mode


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


def test_installer_recompiles_and_validates_codex_profile_around_service_start() -> None:
    """A checked-in .codex snapshot is never the deployment authority."""

    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")

    install_all = script.index("install_all() {")
    configure = script.index("    configure_platform", install_all)
    service_start = script.index("    systemctl enable --now", install_all)
    verify = script.index("    verify_installation", service_start)
    assert configure < service_start < verify

    configure_platform = script.index("configure_platform() {")
    initialize = script.index("initialize_platform(", configure_platform)
    next_function = script.index("\ninstall_units() {", initialize)
    assert initialize < next_function
    assert "codex_config_root=source_root / '.codex'" in script[
        configure_platform:next_function
    ]

    verify_installation = script.index("verify_installation() {")
    validate = script.index("validate_installation_profile(", verify_installation)
    verify_end = script.index("\nbegin_install_transaction() {", validate)
    assert validate < verify_end


def test_installer_repairs_only_mutable_database_ownership_before_start() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")

    assert "normalize_database_ownership" in script
    assert 'directories=("${SCID_STATE}/database")' in script
    assert 'directories+=("$TCAD_STATE")' in script
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
    assert 'parsed_version("PyYAML")' not in script
    assert "scidiscovery.research_state" not in script
    assert "research/current.yaml" not in script
    assert 'parsed_version("Pillow")' in script
    assert 'base Python requires Pillow>=10,<13' in script
    assert 'parsed_version("jsonschema")' in script
    assert 'base Python requires jsonschema>=4,<5' in script
    assert 'parsed_version("setuptools")' in script
    assert "from packaging.version import Version" in script
    assert "--no-input --no-index" in script
    assert "--no-deps --no-build-isolation" in script
    assert "--progress-bar off --upgrade" in script
    assert '--target "$stage" "${package_roots[@]}"\n        >/dev/null' not in script
    assert '"$SOURCE_ROOT/skills"' in script
    assert "installed package is missing the scientific paper evidence tool" not in script
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
        "approval-secret=${CONFIG_ROOT}/approval-receipt.key",
        "framework-codex=${SOURCE_ROOT}/.codex",
        "framework-agents=${SOURCE_ROOT}/AGENTS.md",
        "workspace-codex=${WORKSPACE}/.codex",
        "codex-skill-${skill}=",
        "unit-${unit%.service}",
        "artifact_agent runs approvals executions scheduler-bindings",
        "db-tcad-submissions",
    ):
        assert target in script
    assert "for skill in sentaurus-tcad-code" in script
    assert "retire_inactive_tcad_surfaces" in script
    assert "claude-skill-" not in script
    assert "active-units.txt" in script
    assert "enabled-units.txt" in script
    assert "trap 'rollback_install $?' ERR" in script
    assert 'chown "$SERVICE_USER:$SERVICE_GROUP" "$secret"' in script
    assert 'chmod 0600 "$secret"' in script


def test_curve_figure_capability_is_plugin_owned_not_a_platform_skill() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = (project_root / "deploy/install.sh").read_text(encoding="utf-8")
    metadata = (project_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "scientific-paper-evidence" not in script
    assert "scientific-paper-evidence" not in metadata
    assert (
        project_root
        / "plugins/curve_score/curve_score/figure_worker_tool.py"
    ).is_file()
    optional_metadata = (
        project_root / "plugins/curve_figure_evidence/pyproject.toml"
    ).read_text(encoding="utf-8")
    assert 'curve_figure_evidence = "curve_figure_evidence.plugin:PLUGIN"' in (
        optional_metadata
    )
    assert '"scidiscovery-curve-score>=0.2.1"' in optional_metadata
    assert (
        '[[ " ${SELECTED_PLUGINS[*]} " == *" curve_figure_evidence "* ]]'
        in script
    )
    assert 'command -v pdfimages' in script
    assert 'command -v pdftoppm' in script
    assert '"Pillow>=10,<13"' in metadata
    assert '"jsonschema>=4,<5"' in metadata


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
    install_root = tmp_path / "install"
    state_root = tmp_path / "state"
    tcad_state_root = tmp_path / "tcad-state"
    config_root = tmp_path / "config"
    backup_root = tmp_path / "backups"
    skill_root = tmp_path / "skills"
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
            "SCID_INSTALL_ROOT": str(install_root),
            "SCID_STATE_ROOT": str(state_root),
            "TCAD_STATE_ROOT": str(tcad_state_root),
            "SCID_CONFIG_ROOT": str(config_root),
            "SCID_BACKUP_ROOT": str(backup_root),
            "SCID_APPROVAL_PORT": "18765",
            "SCID_CODEX_SKILL_ROOT": str(skill_root),
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
    assert "SCID_WEB_FETCH_ALLOW_FAKE_IP=1" not in output
    assert f"SCID_TCAD_COMMAND_CONFIG={command_config}" in output
    assert f"SCID_INSTALL_ROOT={install_root}" in output
    assert f"SCID_STATE_ROOT={state_root}" in output
    assert f"TCAD_STATE_ROOT={tcad_state_root}" in output
    assert f"SCID_CONFIG_ROOT={config_root}" in output
    assert f"SCID_BACKUP_ROOT={backup_root}" in output
    assert "SCID_APPROVAL_PORT=18765" in output
    assert f"SCID_CODEX_SKILL_ROOT={skill_root}" in output
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
    assert (
        "SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence,ingaas_fig4"
        in output
    )
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
    assert '--plugin-config \\"tcad_artifact=${CONFIG_ROOT}/tcad-plugin.json\\"' in installer
    assert "configure_tcad_runtime" in installer
    assert "plugins/tcad_artifact/deploy/configure_runtime.py" in installer
    assert '[[ ! "$value" =~ [[:cntrl:]]' in installer
    assert '"$value" != *\'$\'* && "$value" != *\'@\'*' in installer
    assert "printf -v quoted_python '%q' \"$PYTHON\"" in installer
    assert "printf -v quoted_site_root '%q' \"$SITE_ROOT\"" in installer
    assert "PYTHONPATH=${quoted_site_root} ${quoted_python}" in installer


def test_default_deployment_has_no_central_worker_service() -> None:
    project_root = Path(__file__).resolve().parents[2]
    assert not (
        project_root / "deploy/systemd/scidiscovery-worker.service.in"
    ).exists()
    cleanup = (project_root / "deploy/cleanup_legacy_services.sh").read_text(
        encoding="utf-8"
    )
    current = cleanup.split("readonly -a CURRENT_UNITS=(", 1)[1].split(")", 1)[0]
    retired = cleanup.split("readonly -a RETIRED_UNITS=(", 1)[1].split(")", 1)[0]
    assert "scidiscovery-worker.service" not in current
    assert "scidiscovery-worker.service" in retired


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
    assert not (output / "plugins/table_observation").exists()
    assert not (
        output / "src/scidiscovery/artifact_agent/service/agent_dispatch.py"
    ).exists()
    assert not (output / "src/scidiscovery/platforms/codex_worker.py").exists()
    assert not (output / "experiments/worker_process_v2").exists()
    current_decisions = {
        "OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md",
        "R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md",
        "R5_S_PRODUCTION_CODE_SIMPLIFICATION_PLAN.zh-CN.md",
    }
    assert {
        path.name for path in (output / "docs/plans").glob("*.md")
    } == current_decisions
    assert {
        path.name for path in (output / "docs/plans/reviews").glob("*.md")
    } == {
        "R5_S1_PRODUCTION_BOUNDARY_INDEPENDENT_REVIEW.zh-CN.md"
    }
    assert (
        output
        / "docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md"
    ).is_file()
    assert (
        output / "docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml"
    ).is_file()
    assert not (output / "docs/plans/README.md").exists()
    assert not (
        output / "docs/plans/TCAD_AGENT_REAUDIT_REMEDIATION_PLAN.zh-CN.md"
    ).exists()
    assert (output / "deploy/install_transaction.py").is_file()
    assert (output / "deploy/init_workspace.sh").is_file()
    assert (
        output / "plugins/curve_score/curve_score/figure_worker_tool.py"
    ).is_file()
    assert (
        output
        / "plugins/curve_figure_evidence/curve_figure_evidence/plugin.py"
    ).is_file()
    assert not (output / "skills/scientific-paper-evidence").exists()
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
    assert not (output / "archive").exists()
    assert not (output / "workspace").exists()
    assert not (output / "deliverables").exists()
    assert not (output / "123").exists()
    assert not (output / ".codex").exists()
    assert not any(output.rglob("r5_g_*.py"))
    assert not any(output.rglob("test_r5_g_*_runner.py"))
    assert not any(output.rglob("__pycache__"))
    manifest = output / "MANIFEST.sha256"
    entries = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    readme = output / "README.md"
    assert entries["README.md"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    assert set(entries) == {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path != manifest
    }
    assert output.with_suffix(".tar.gz").is_file()
