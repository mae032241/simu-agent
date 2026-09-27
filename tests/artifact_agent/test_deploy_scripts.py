from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from deploy.install_transaction import (
    _directory_digest,
    _verify_managed_directory,
    begin_transaction,
    mark_managed_directory,
    remove_transaction_target,
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
        if "curve_figure_evidence" in plugins:
            environment.update(_figure_supply(root))
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
    all_domains = preview("all-domains", "tcad_artifact,curve_score,curve_figure_evidence")
    assert "Selected plugins: tcad_artifact,curve_score,curve_figure_evidence" in all_domains


@pytest.mark.parametrize("phase", ["preview", "configure_platform"])
@pytest.mark.parametrize("directory", ["plain", "O'Brien space"])
@pytest.mark.parametrize("nested", [False, True])
def test_installer_passes_platform_paths_as_data(tmp_path: Path, phase: str, directory: str, nested: bool) -> None:
    """Run the actual shell functions with a harmless initializer and no install effects."""
    project_root = Path(__file__).resolve().parents[2]
    root = tmp_path / directory
    source = root / "source"
    (source / "deploy").mkdir(parents=True)
    script = source / "deploy/install.sh"
    shutil.copyfile(project_root / "deploy/install.sh", script)
    package = source / "src/scidiscovery"
    (package / "operations").mkdir(parents=True)
    (package / "__init__.py").touch()
    (package / "operations/__init__.py").touch()
    (package / "platforms.py").write_text(
        "import json, os\n"
        "def initialize_platform(platform, root, **kwargs):\n"
        "    kwargs.pop('operation_catalog', None)\n"
        "    with open(os.environ['SCID_TEST_CALLS'], 'a') as stream:\n"
        "        stream.write(json.dumps(dict(platform=platform, root=root, **kwargs), default=str) + '\\n')\n",
        encoding="utf-8",
    )
    (package / "operations/catalog.py").write_text(
        "class Catalog:\n"
        "    def runtime_plugin_ids(self): return ('tcad_artifact',)\n"
        "def compile_installed_catalog(): return Catalog()\n",
        encoding="utf-8",
    )
    site = root / "install/site"
    shutil.copytree(source / "src", site)
    workspace = (source if nested else root) / "workspace"
    workspace.mkdir()
    launch = root / "launch"
    launch.mkdir()
    python = root / "python"
    python.symlink_to(sys.executable)
    calls_path = root / "calls.jsonl"
    completed = subprocess.run(
        ["bash", "-c", '''
source "$1"
render_units() { touch "$1/fake.service"; }
systemd-analyze() { :; }
install() { :; }
chown() { :; }
backup_legacy_user_entrypoints() { :; }
install_platform_skills() { :; }
prepare_managed_platform_paths() { :; }
runuser() { shift 3; "$@"; }
TCAD_ENABLED=1
"$2"
''', "bash", str(script), phase],
        env={
            **os.environ,
            "SCID_WORKSPACE": str(workspace),
            "SCID_CODEX_LAUNCH_ROOT": str(launch),
            "SCID_PYTHON": str(python),
            "SCID_INSTALL_ROOT": str(root / "install"),
            "SCID_CONFIG_ROOT": str(root / "config"),
            "SCID_STATE_ROOT": str(root / "state"),
            "SCID_BACKUP_ROOT": str(root / "backups"),
            "SCID_WORKER_BACKEND": "hardened",
            "SCID_TEST_CALLS": str(calls_path),
            "TMPDIR": str(root),
        },
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    calls = [json.loads(line) for line in calls_path.read_text("utf-8").splitlines()]
    assert [call["root"] for call in calls] == [str(path) for path in (
        [source, launch] if nested else [source, workspace, launch]
    )]
    for call in calls:
        assert call["platform"] == "codex"
        assert call["python_executable"] == str(python)
        assert call["state_root"] == str(root / "state")
        assert call["local_workspace_root"] == str(workspace / ".scidiscovery-runs")
        assert call["control_socket"] == "/run/scidiscovery/control.sock"
        assert call["worker_backend"] == "hardened"
        assert call["runtime_plugin_configs"] == {"tcad_artifact": str(root / "config/tcad-plugin.json")}
        if phase == "configure_platform":
            assert call["python_path"] == str(site)
            assert call["codex_config_root"] == str(Path(call["root"]) / ".codex")
        else:
            assert call["dry_run"] is True
            assert Path(call["codex_config_root"]).is_relative_to(root)


def _figure_supply(root: Path) -> dict[str, str]:
    """Expose the real pdfimages binary through the simulated service PATH."""
    binary = root / "figure-bin"
    binary.mkdir()
    (binary / "pdfimages").symlink_to(shutil.which("pdfimages"))
    for name, body in {
        "systemd-path": f"printf '%s\\n' '{binary}'\n",
        "systemctl": "exit 0\n",
    }.items():
        command = binary / name
        command.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        command.chmod(0o755)
    return {"PATH": f"{binary}:{os.environ['PATH']}"}


def test_figure_preflight_exercises_exact_pdf_image_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    import runpy

    project = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("PATH", _figure_supply(tmp_path)["PATH"])
    monkeypatch.setattr(sys, "argv", ["figure_dependencies.py"])
    runpy.run_path(str(project / "plugins/curve_figure_evidence/curve_figure_evidence/figure_dependencies.py"),
                   run_name="__main__")


@pytest.mark.parametrize("failure", [
    "missing_pdfimages", "service_path", "service_python",
    "manager_ansi_quoted", "manager_double_quoted", "manager_backslash",
    "manager_whitespace", "manager_control", "manager_relative",
    "manager_empty_segment", "manager_leading_empty", "manager_trailing_empty",
    "manager_empty",
])
def test_figure_dependency_failure_precedes_install_transaction(tmp_path: Path, failure: str) -> None:
    project = Path(__file__).resolve().parents[2]
    environment = {**os.environ, **_figure_supply(tmp_path),
        "SCID_WORKSPACE": str(tmp_path), "SCID_PYTHON": sys.executable,
        "SCID_SERVICE_USER": subprocess.check_output(["id", "-un"], text=True).strip(),
        "SCID_SERVICE_GROUP": subprocess.check_output(["id", "-gn"], text=True).strip()}
    binary = tmp_path / "figure-bin"
    expected = ""
    if failure == "missing_pdfimages":
        (binary / "pdfimages").unlink()
        expected = "unavailable in service PATH: pdfimages"
    elif failure == "service_path":
        # The operator still resolves pdfimages from /usr/bin, the service cannot.
        (binary / "pdfimages").unlink()
        assert shutil.which("pdfimages", path=environment["PATH"])
        expected = "unavailable in service PATH: pdfimages"
    elif failure.startswith("manager_"):
        manager_path = {
            "manager_ansi_quoted": "$'/g4/service tools:/usr/bin:/bin'",
            "manager_double_quoted": '"/usr/bin:/bin"',
            "manager_backslash": r"/g4/service\ tools:/usr/bin:/bin",
            "manager_whitespace": "/g4/service tools:/usr/bin:/bin",
            "manager_control": "/usr/bin:\t/bin",
            "manager_relative": "/usr/bin:relative:/bin",
            "manager_empty_segment": "/usr/bin::/bin",
            "manager_leading_empty": ":/usr/bin:/bin",
            "manager_trailing_empty": "/usr/bin:/bin:",
            "manager_empty": "",
        }[failure]
        (binary / "systemctl").write_text(
            f"#!{sys.executable}\nprint({'PATH=' + manager_path!r})\n", encoding="utf-8")
        expected = "unsafe systemd service PATH"
    else:
        from PIL import Image  # Only the operator environment supplies Pillow.
        assert Image
        venv.EnvBuilder(with_pip=False, symlinks=True).create(tmp_path / "service-python")
        environment["SCID_PYTHON"] = str(tmp_path / "service-python/bin/python")
        expected = "No module named 'PIL'"
    completed = subprocess.run([
        "bash", "-c", '''source "$1"
SELECTED_PLUGINS=(curve_figure_evidence)
require_root() { :; }
validate_source() { :; }
validate_base_python() { :; }
install_packages() { touch "$WORKSPACE/build-entered"; }
begin_install_transaction() { touch "$WORKSPACE/transaction-entered"; }
rollback_install() { touch "$WORKSPACE/rollback-entered"; }
install_all
''', "bash", str(project / "deploy/install.sh")],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert completed.returncode != 0
    assert expected in completed.stderr
    assert "before installation transaction" in completed.stderr
    assert not any((tmp_path / name).exists() for name in (
        "build-entered", "transaction-entered", "rollback-entered"))


def test_service_python_accepts_plain_systemd_manager_path(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[2]
    service_path = subprocess.check_output(["systemd-path", "search-binaries-default"], text=True).strip()
    environment = {**os.environ, **_figure_supply(tmp_path),
        "SCID_WORKSPACE": str(tmp_path), "SCID_PYTHON": sys.executable}
    (tmp_path / "figure-bin/systemctl").write_text(
        f"#!{sys.executable}\nprint({'PATH=' + service_path!r})\n", encoding="utf-8")
    completed = subprocess.run([
        "bash", "-c", 'source "$1"; service_python "" -c \'import os; print(os.environ["PATH"])\'',
        "bash", str(project / "deploy/install.sh")],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == service_path


def test_figure_installed_preflight_rechecks_the_frozen_contract(
    tmp_path: Path,
) -> None:
    project = Path(__file__).resolve().parents[2]
    environment = {**os.environ, **_figure_supply(tmp_path),
        "SCID_WORKSPACE": str(tmp_path), "SCID_PYTHON": sys.executable}
    site = tmp_path / "site"
    shutil.copytree(project / "plugins/curve_figure_evidence/curve_figure_evidence", site / "curve_figure_evidence",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    completed = subprocess.run(["bash", "-c", '''source "$1"
SELECTED_PLUGINS=(curve_figure_evidence)
validate_figure_dependencies
printf '%s\\n' "$FIGURE_DEPENDENCY_CONTRACT" > "$2/curve_figure_evidence/figure_dependencies.json"
validate_figure_dependencies "$2"
"$SCID_PYTHON" -c 'import json,sys; p=sys.argv[1]; v=json.load(open(p)); v["poppler_version"]="different"; open(p,"w").write(json.dumps(v))' "$2/curve_figure_evidence/figure_dependencies.json"
validate_figure_dependencies "$2"
''', "bash", str(project / "deploy/install.sh"), str(site)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert completed.returncode != 0
    assert completed.stderr.count("figure dependency preflight: pass") == 2
    assert "pdfimages version differs" in completed.stderr
    contract = json.loads((site / "curve_figure_evidence/figure_dependencies.json").read_bytes())
    assert set(contract) == {"pillow_version", "poppler_version", "executables"}
    assert set(contract["executables"]) == {"pdfimages"}
    assert all(Path(path).is_absolute() for path in contract["executables"].values())


def test_figure_preflight_observes_dependencies_without_identity_inputs(
    tmp_path: Path,
) -> None:
    project = Path(__file__).resolve().parents[2]
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SCID_FIGURE_")}
    environment.update(_figure_supply(tmp_path))
    environment.update(SCID_WORKSPACE=str(tmp_path), SCID_PYTHON=sys.executable)
    completed = subprocess.run([
        "bash", "-c", 'source "$1"; SELECTED_PLUGINS=(curve_figure_evidence); validate_figure_dependencies',
        "bash", str(project / "deploy/install.sh")],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    contract = json.loads(completed.stdout.removeprefix("Verified figure dependencies: "))
    from PIL import __version__
    assert contract["pillow_version"] == __version__
    assert contract["poppler_version"]
    assert set(contract["executables"]) == {"pdfimages"}


def test_installer_rejects_removed_case_plugin_before_installation(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    completed = subprocess.run(
        [str(project_root / "deploy/install.sh"), "--dry-run"],
        cwd=project_root,
        env={**os.environ, "SCID_PLUGINS": "tcad_artifact,curve_score,curve_figure_evidence,ingaas_fig4",
             "SCID_WORKSPACE": str(workspace), "SCID_PYTHON": sys.executable},
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert completed.returncode != 0
    assert "unknown local plugin: ingaas_fig4" in completed.stderr


def test_tcad_runtime_configuration_is_owned_and_executed_by_plugin(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    helper = project_root / "plugins/tcad_artifact/deploy/configure_runtime.py"
    policy = tmp_path / "tcad-policy.json"
    supplied_policy = json.loads((project_root / "plugins/tcad_artifact/config/execution-policy.example.json").read_text())
    supplied_policy["allowed_input_roots"] = [str(tmp_path / "state/execution-exchange")]
    policy.write_text(json.dumps(supplied_policy))
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


@pytest.mark.parametrize("transport,policy_kind,valid_adapter,success", [
    ("socket", "current", True, True),
    ("socket", "legacy", True, False),
    ("socket", "missing", True, False),
    ("command", "current", True, True),
    ("command", "legacy", True, True),
    ("command", "missing", True, True),
    ("command", "legacy", False, False),
])
def test_installer_configures_only_selected_tcad_transport(
    tmp_path: Path, transport: str, policy_kind: str, valid_adapter: bool, success: bool,
) -> None:
    project = Path(__file__).resolve().parents[2]
    config = tmp_path / "config"
    config.mkdir()
    site = tmp_path / "install/site"
    site.mkdir(parents=True)
    for package, source in (
        ("scidiscovery", project / "src/scidiscovery"),
        ("tcad_artifact", project / "plugins/tcad_artifact/tcad_artifact"),
    ):
        (site / package).symlink_to(source, target_is_directory=True)
    policy = config / "tcad-policy.json"
    if policy_kind != "missing":
        data = json.loads((project / "plugins/tcad_artifact/config/execution-policy.example.json").read_text())
        if policy_kind == "legacy":
            for key in ("agent_execution_policy", "runner", "debug"):
                del data[key]
        policy.write_text(json.dumps(data))
    before = policy.read_bytes() if policy.exists() else None
    adapter = config / "adapter.json"
    adapter.write_text(json.dumps({"executable": "/usr/bin/true"} if valid_adapter else {}))
    plugin = config / "tcad-plugin.json"
    plugin.write_text('{"previous":"configuration"}')
    permissions = tmp_path / "permissions.log"
    result = subprocess.run([
        "bash", "-c", '''
source "$1"
chown() { printf '%s\\n' "$@" >> "$PERMISSIONS_LOG"; }
chmod() { printf '%s\\n' "$@" >> "$PERMISSIONS_LOG"; }
configure_tcad_runtime
''', "bash", str(project / "deploy/install.sh")],
        cwd=project, capture_output=True, text=True, timeout=15,
        env={**os.environ, "SCID_PYTHON": sys.executable,
             "SCID_INSTALL_ROOT": str(site.parent), "SCID_CONFIG_ROOT": str(config),
             "SCID_TCAD_COMMAND_CONFIG": str(adapter) if transport == "command" else "",
             "PERMISSIONS_LOG": str(permissions)},
    )
    assert (result.returncode == 0) == success, result.stderr
    assert (policy.read_bytes() if policy.exists() else None) == before
    if success:
        expected = ({"transport": "command", "command_config_path": str(adapter)}
                    if transport == "command" else
                    {"transport": "socket", "socket_path": "/run/scidiscovery-tcad/control.sock"})
        assert json.loads(plugin.read_text()) == expected
        touched = permissions.read_text().splitlines()
        assert str(plugin) in touched
        assert (str(policy) in touched) == (transport == "socket")
    else:
        assert json.loads(plugin.read_text()) == {"previous": "configuration"}
        assert not permissions.exists()


def test_skill_install_integrity_removal_and_rollback(tmp_path: Path) -> None:
    import grp
    import pwd

    project_root = Path(__file__).resolve().parents[2]
    # Copy real installer entry points, but exercise directory transactions with
    # tiny synthetic resources. The release smoke pins the real manual bytes.
    fixture_root = tmp_path / "source"
    (fixture_root / "deploy").mkdir(parents=True)
    for script in ("install.sh", "install_transaction.py"):
        shutil.copy2(project_root / "deploy" / script, fixture_root / "deploy" / script)
    source = fixture_root / "skills/sentaurus-tcad-code"
    for relative in ("SKILL.md", "scripts/manual_extract.py",
                     "references/manuals/catalog.json", "references/manuals/topics.json",
                     "references/manuals/R-2020.09/sprocess_ug.pdf"):
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((relative + "\n").encode())
    skill_root = tmp_path / "skills"
    skill = skill_root / "sentaurus-tcad-code"
    name = "codex-skill-sentaurus-tcad-code"
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; install_platform_skill "$2" codex "$3" sentaurus-tcad-code',
         "bash", str(fixture_root / "deploy/install.sh"), str(tmp_path / "backup"), str(skill_root)],
        cwd=project_root, capture_output=True, text=True, timeout=30,
        env={**os.environ, "SCID_PYTHON": sys.executable,
             "SCID_SERVICE_USER": pwd.getpwuid(os.getuid()).pw_name,
             "SCID_SERVICE_GROUP": grp.getgrgid(os.getgid()).gr_name},
    )
    assert result.returncode == 0, result.stderr
    assert _directory_digest(skill) == _directory_digest(source)
    _verify_managed_directory(skill, name=name)
    for relative in ("references/manuals/R-2020.09/sprocess_ug.pdf",
                     "references/manuals/topics.json", "references/manuals/catalog.json",
                     "scripts/manual_extract.py", "SKILL.md"):
        target = skill / relative
        original = target.read_bytes()
        target.write_bytes(original + b"\nchanged\n")
        with pytest.raises(RuntimeError, match="content has changed"):
            _verify_managed_directory(skill, name=name)
        target.write_bytes(original)
    link = skill / "outside-link"
    link.symlink_to(tmp_path)
    with pytest.raises(RuntimeError, match="symlink"):
        _verify_managed_directory(skill, name=name)
    link.unlink()
    transaction = tmp_path / "transaction"
    begin_transaction(transaction, targets=((name, skill),))
    remove_transaction_target(transaction, name=name, path=skill, managed_directory_name=name)
    assert not skill.exists()
    rollback_transaction(transaction)
    _verify_managed_directory(skill, name=name)
    assert _directory_digest(skill) == _directory_digest(source)


def test_install_transaction_sqlite_snapshot_restore_remains_compatible(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "database/existing.sqlite3"
    existing.parent.mkdir(parents=True)
    with sqlite3.connect(existing) as connection:
        connection.execute("CREATE TABLE records (value TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO records VALUES ('before')")
    missing = tmp_path / "database/missing.sqlite3"
    outside = tmp_path / "outside-launcher"
    outside.write_text("old launcher\n", encoding="utf-8")
    launcher = tmp_path / "bin/launcher"
    launcher.parent.mkdir()
    launcher.symlink_to(outside)
    missing_config = tmp_path / "config/new.json"
    transaction = tmp_path / "transaction"
    begin_transaction(
        transaction,
        targets=(("launcher", launcher), ("missing-config", missing_config)),
        databases=(("existing", existing), ("missing", missing)),
    )
    launcher.unlink()
    launcher.write_text("new launcher\n", encoding="utf-8")
    missing_config.parent.mkdir()
    missing_config.write_text("new config\n", encoding="utf-8")
    with sqlite3.connect(existing) as connection:
        connection.execute("INSERT INTO records VALUES ('after')")
    with sqlite3.connect(missing) as connection:
        connection.execute("CREATE TABLE records (value TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO records VALUES ('after')")
    for database in (existing, missing):
        for suffix in ("-wal", "-shm"):
            Path(str(database) + suffix).write_bytes(suffix.encode())

    rollback_transaction(transaction)

    with sqlite3.connect(existing) as connection:
        assert connection.execute("SELECT value FROM records").fetchall() == [("before",)]
    assert not missing.exists()
    assert launcher.is_symlink()
    assert launcher.read_text(encoding="utf-8") == "old launcher\n"
    assert not missing_config.exists()
    for database in (existing, missing):
        assert not Path(str(database) + "-wal").exists()
        assert not Path(str(database) + "-shm").exists()


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
    bytecode_before = set((project_root / "plugins/tcad_artifact/tcad_artifact").rglob("remote_runner_py36*.pyc"))
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
    assert set(
        (project_root / "plugins/tcad_artifact/tcad_artifact").rglob(
            "remote_runner_py36*.pyc"
        )
    ) == bytecode_before


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
                "max_transfer_bytes": 1024 * 1024,
                "transfer_chunk_bytes": 65536,
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
                "max_transfer_bytes": 1024 * 1024,
                "transfer_chunk_bytes": 65536,
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
                "max_transfer_bytes": 1024 * 1024,
                "transfer_chunk_bytes": 65536,
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


def test_actual_install_root_context_probe_checks_installed_gateway_views(tmp_path):
    project = Path(__file__).resolve().parents[2]
    site = tmp_path / "install/site"
    site.mkdir(parents=True)
    fixture = site / "context_probe_fixture.py"
    fixture.write_text(r'''
import json
import sys

catalog_seen = False
for line in sys.stdin:
    request = json.loads(line)
    name = request["params"]["name"]
    arguments = request["params"]["arguments"]
    if name == "scid_catalog":
        catalog_seen = True
        value = {"operations": [{"operation_id": "science.fixture.v1", "purpose": "fixture"}], "complete": True, "next_before": None}
    elif arguments["name"] == "scid_describe":
        value = {"inputSchema": {"properties": {"view": {"enum": ["full", "invoke"]}, "surface":{"default":"research"}}}}
    elif arguments["name"] == "run_status":
        value = {"inputSchema": {"properties": {"intent": {
            "enum": ["decision", "status", "navigation", "full"], "default":"decision"
        }}}}
    elif arguments["name"] == "artifact_catalog":
        value = {"inputSchema": {"properties": {"view": {
            "enum": ["summary", "detail", "parents", "producer_inputs"]
        }}}}
    elif not catalog_seen:
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {
            "code": -32000, "message": "operation crossed installation probe sessions"}}), flush=True)
        continue
    else:
        value = {"view": "invoke", "operations": [{
            "operation_id": arguments["name"], "contract_view_version": "invoke.scientific.v2",
            "inputs": [], "revision_policy": {"max_revisions": 0},
        }]}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"],
        "result": {"structuredContent": value}}), flush=True)
''', encoding="utf-8")
    completed = subprocess.run(
        [
            "bash", "-c",
            'source "$1"; probe_root_context_contract context_probe_fixture unused',
            "bash", str(project / "deploy/install.sh"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        env={
            **os.environ,
            "SCID_PYTHON": sys.executable,
            "SCID_INSTALL_ROOT": str(site.parent),
            "PYTHONPATH": str(tmp_path / "unrelated"),
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert "Root context contract probe: pass (science.fixture.v1" in completed.stdout


@pytest.mark.parametrize("case,accepted", [
    ("unified", True), ("legacy", False), ("missing", False), ("extra", False), ("tcad", True),
])
def test_actual_install_mcp_probe_uses_installed_gateway_contract(tmp_path, case, accepted):
    from scidiscovery.artifact_agent.interfaces.mcp_gateway import GATEWAY_TOOLS
    project = Path(__file__).resolve().parents[2]
    site = tmp_path / "install/site"
    site.mkdir(parents=True)
    (site / "scidiscovery").symlink_to(project / "src/scidiscovery", target_is_directory=True)
    names = list(GATEWAY_TOOLS)
    if case == "legacy":
        names = ["operation_catalog", "operation_preflight", "operation_invoke"]
    elif case == "missing":
        names.remove("scid_call")
    elif case == "extra":
        names.append("worker_open_assignment")
    elif case == "tcad":
        names = [f"tcad_{i}" for i in range(5)]
    payload = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": n} for n in names]}}
    (site / "probe_fixture.py").write_text("import json\nprint(json.dumps(" + repr(payload) + "))\n")
    completed = subprocess.run([
        "bash", "-c", 'source "$1"; probe_mcp probe_fixture unused "" "$2"',
        "bash", str(project / "deploy/install.sh"), "5" if case == "tcad" else "root",
    ], cwd=tmp_path, capture_output=True, text=True, timeout=15,
       env={**os.environ, "SCID_PYTHON": sys.executable, "SCID_INSTALL_ROOT": str(site.parent),
            "PYTHONPATH": str(tmp_path / "unrelated")})
    assert (completed.returncode == 0) is accepted, completed.stderr
    if accepted:
        assert "MCP tool probe: pass" in completed.stdout
    else:
        assert "MCP tool authority mismatch: root; missing=" in completed.stderr
        assert "unexpected=" in completed.stderr


def test_installer_previews_an_explicit_codex_launch_root(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    launch_root = tmp_path / "launch"
    workspace.mkdir()
    launch_root.mkdir()
    completed = subprocess.run(
        [str(project_root / "deploy/install.sh"), "--dry-run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "SCID_WORKSPACE": str(workspace),
            "SCID_CODEX_LAUNCH_ROOT": str(launch_root),
            "SCID_PYTHON": sys.executable,
            "SCID_INSTALL_ROOT": str(tmp_path / "install"),
            "SCID_STATE_ROOT": str(tmp_path / "state"),
            "SCID_CONFIG_ROOT": str(tmp_path / "config"),
            "SCID_BACKUP_ROOT": str(tmp_path / "backups"),
        },
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "deployment preview: pass" in completed.stdout
    assert not (launch_root / ".codex").exists()
    assert not (launch_root / "AGENTS.md").exists()


def test_installer_rejects_a_missing_codex_launch_root(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    completed = subprocess.run(
        [str(project_root / "deploy/install.sh"), "--dry-run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "SCID_WORKSPACE": str(workspace),
            "SCID_CODEX_LAUNCH_ROOT": str(tmp_path / "missing"),
            "SCID_PYTHON": sys.executable,
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode != 0
    assert "SCID_CODEX_LAUNCH_ROOT must name an existing absolute directory" in completed.stderr


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
        '"$CODEX_LAUNCH_ROOT/.codex"',
        '"$SOURCE_ROOT/AGENTS.md"',
        '"$WORKSPACE/AGENTS.md"',
        '"$CODEX_LAUNCH_ROOT/AGENTS.md"',
    ):
        assert managed_path in script
    assert ".claude" not in script
    assert "CLAUDE.md" not in script
    assert 'chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WORKSPACE"' not in script
    assert 'managed platform directory contains a symlink' in script
    configure = script.index("configure_platform() {")
    prepare = script.index("    prepare_managed_platform_paths", configure)
    create_source = script.index(
        '    install -d -o "$SERVICE_USER" -g "$SERVICE_GROUP" -m 0755 "$SOURCE_ROOT/.codex"',
        configure,
    )
    create_launch = script.index(
        '            "$CODEX_LAUNCH_ROOT/.codex"', create_source
    )
    assert prepare < create_source < create_launch


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
        "launch-codex=${CODEX_LAUNCH_ROOT}/.codex",
        "launch-agents=${CODEX_LAUNCH_ROOT}/AGENTS.md",
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


@pytest.mark.parametrize("explicit_tcad_state", [False, True])
def test_generic_reinstaller_passes_resolved_configuration(tmp_path: Path, explicit_tcad_state: bool) -> None:
    project_root = Path(__file__).resolve().parents[2]
    wrapper = project_root / "deploy/reinstall.sh"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command_config = tmp_path / "command-adapter.json"
    command_config.write_text("{}\n", encoding="utf-8")
    remote_config = tmp_path / "remote-runner.json"
    remote_config.write_text("{}\n", encoding="utf-8")
    install_root = tmp_path / "install"
    state_root = tmp_path / "state"
    tcad_state_root = tmp_path / "tcad-state" if explicit_tcad_state else state_root / "tcad"
    config_root = tmp_path / "config"
    backup_root = tmp_path / "backups"
    skill_root = tmp_path / "skills"
    launch_root = tmp_path / "launch"
    launch_root.mkdir()
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
            "SCID_REMOTE_RUNNER_CONFIG": str(remote_config),
            "SCID_INSTALL_ROOT": str(install_root),
            "SCID_STATE_ROOT": str(state_root),
            "TCAD_STATE_ROOT": str(tcad_state_root) if explicit_tcad_state else "",
            "SCID_CONFIG_ROOT": str(config_root),
            "SCID_BACKUP_ROOT": str(backup_root),
            "SCID_APPROVAL_PORT": "18765",
            "SCID_CODEX_SKILL_ROOT": str(skill_root),
            "SCID_CODEX_LAUNCH_ROOT": str(launch_root),
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
    assert f"SCID_REMOTE_RUNNER_CONFIG={remote_config}" in output
    assert f"SCID_INSTALL_ROOT={install_root}" in output
    assert f"SCID_STATE_ROOT={state_root}" in output
    assert f"TCAD_STATE_ROOT={tcad_state_root}" in output
    assert f"SCID_CONFIG_ROOT={config_root}" in output
    assert f"SCID_BACKUP_ROOT={backup_root}" in output
    assert "SCID_APPROVAL_PORT=18765" in output
    assert f"SCID_CODEX_SKILL_ROOT={skill_root}" in output
    assert f"SCID_CODEX_LAUNCH_ROOT={launch_root}" in output
    assert str(project_root / "deploy/install.sh") in output
    assert output[-1] == "install"


@pytest.mark.parametrize("transport,override", [
    ("socket", ""), ("socket", "legacy"),
    ("command", ""), ("command", "legacy"), ("command", "unused-relative"),
])
def test_installer_only_manages_local_tcad_state(tmp_path: Path, transport: str, override: str) -> None:
    project = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = tmp_path / "state"
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    sentinel = legacy / "submissions.sqlite3"
    sentinel.write_bytes(b"existing state must not be moved or rewritten")
    legacy_mode = legacy.stat().st_mode
    command_config = tmp_path / "command.json"
    command_config.write_text("{}")
    # Execute real installer branches, recording privileged filesystem calls
    # and transaction targets instead of modifying the host installation.
    python = tmp_path / "python"
    python.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
if sys.argv[1].endswith("/deploy/install_transaction.py"):
    assert sys.argv[2] == "begin"
    Path(os.environ["SCID_WORKSPACE"], "transaction.json").write_text(json.dumps(sys.argv[3:]))
    Path(sys.argv[sys.argv.index("--root") + 1]).mkdir(parents=True)
else:
    os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])
''')
    python.chmod(0o755)
    tcad_state = str(legacy) if override == "legacy" else override
    completed = subprocess.run([
        "bash", "-c", '''source "$1"
require_sources
render_units "$WORKSPACE/units"
for fn in require_root validate_source validate_base_python validate_figure_dependencies \
    install_packages retire_old_deployment retire_inactive_tcad_surfaces activate_packages \
    create_local_workspace_root ensure_secret ensure_agent_settings configure_tcad_runtime install_units \
    configure_platform verify_installation complete_install_transaction remote_tcad_runtime; do
    eval "$fn() { :; }"
done
install() { printf 'install %s\\n' "$*" >> "$WORKSPACE/mutations"; }
chown() { printf 'chown %s\\n' "$*" >> "$WORKSPACE/mutations"; }
find() { :; }
systemctl() { :; }
rollback_install() { exit "$1"; }
install_all
trap - ERR INT TERM
''', "bash", str(project / "deploy/install.sh")],
        cwd=tmp_path, capture_output=True, text=True, timeout=20,
        env={**os.environ, "SCID_WORKSPACE": str(workspace), "SCID_PYTHON": str(python),
             "SCID_PLUGINS": "tcad_artifact,curve_score", "SCID_WORKER_BACKEND": "local",
             "SCID_CODEX_LAUNCH_ROOT": "", "SCID_CODEX_SKILL_ROOT": str(tmp_path / "skills"),
             "SCID_INSTALL_ROOT": str(tmp_path / "install"), "SCID_STATE_ROOT": str(state),
             "SCID_CONFIG_ROOT": str(tmp_path / "config"), "SCID_BACKUP_ROOT": str(tmp_path / "backups"),
             "TCAD_STATE_ROOT": tcad_state,
             "SCID_TCAD_COMMAND_CONFIG": str(command_config) if transport == "command" else ""},
    )
    assert completed.returncode == 0, completed.stderr
    targets = json.loads((workspace / "transaction.json").read_text())
    mutations = (workspace / "mutations").read_text().splitlines()
    unit = workspace / "units/tcad-control.service"
    expected_state = legacy if override == "legacy" else state / "tcad"
    if transport == "socket":
        assert f'--state-root "{expected_state}"' in unit.read_text()
        assert f"db-tcad-submissions={expected_state}/submissions.sqlite3" in targets
        # Directory activation and ownership normalization both use this root.
        assert sum(line.endswith(" " + str(expected_state)) for line in mutations) == 2
    else:
        assert not unit.exists()
        assert not any("db-tcad-submissions=" in target for target in targets)
        assert not any(line.endswith(" " + str(path)) for line in mutations
                       for path in (legacy, state / "tcad", "/var/lib/scidiscovery-tcad", tcad_state) if path)
    assert sentinel.read_bytes() == b"existing state must not be moved or rewritten"
    assert legacy.stat().st_mode == legacy_mode


def test_three_domain_plugins_delegate_to_generic_reinstaller(tmp_path: Path) -> None:
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
            "SCID_PLUGINS": "tcad_artifact,curve_score,curve_figure_evidence",
            "SCID_TCAD_COMMAND_CONFIG": str(command_config),
        },
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout.splitlines()
    assert (
        "SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence"
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


@pytest.mark.installed
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
    assert {path.name for path in (output / "plugins").iterdir() if path.is_dir()} == {
        "curve_score", "curve_figure_evidence", "tcad_artifact",
    }
    assert not (output / "deploy/apply_ingaas_fig4_profile.sh").exists()
    assert not tuple(output.rglob("figure_geometry.json"))
    assert not (
        output / "src/scidiscovery/artifact_agent/service/agent_dispatch.py"
    ).exists()
    assert not (output / "src/scidiscovery/platforms/codex_worker.py").exists()
    assert not (output / "experiments/worker_process_v2").exists()
    # The release manifest is the explicit publication policy; archived research
    # documents outside it must not leak into the generated repository.
    import runpy
    release = runpy.run_path(str(project_root / "scripts/build_git_release.py"))
    assert {path.relative_to(output).as_posix()
            for path in (output / "docs").rglob("*") if path.is_file()} == set(release["DOCUMENTS"])
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
        output / "plugins/curve_figure_evidence/curve_figure_evidence/figure_worker_tool.py"
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
    assert not (output / "docs/plans").exists()
    # Independent consumer requirements: do not derive these from the builder's
    # own allowlists, which previously made missing CI/test inputs invisible.
    required = (
        "docs/PLUGIN_RUNTIME_API.md", "tests/conftest.py", "tests/operations/conftest.py",
        "tests/fixtures/plugins/blind_csv_operation_plugin/blind_csv_plugin/plugin.py",
        "tests/fixtures/plugins/architecture_operation_plugin/pyproject.toml",
        "tests/fixtures/plugins/table_observation_plugin/pyproject.toml",
        "scripts/run_tests.py", "scripts/test_resources.json", "scripts/test_resources_ci.json",
        "scripts/compiled_worker_process_guard.py", "scripts/run_compiled_codex_worker.py",
        "scripts/l4_live_tcad_revision_probe.py", "scripts/l4_live_tcad_agent_probe.py",
        "scripts/l4_tcad_transport_fixture.py",
    )
    assert all((output / relative).is_file() for relative in required)
    expected_tests = {p.relative_to(project_root / "tests") for p in
                      (project_root / "tests").rglob("*") if p.is_file()
                      and not any(part in release["IGNORED_NAMES"] or
                                  part.endswith(release["IGNORED_SUFFIXES"])
                                  for part in p.relative_to(project_root / "tests").parts)}
    assert {p.relative_to(output / "tests") for p in (output / "tests").rglob("*")
            if p.is_file()} == expected_tests
    for relative in ("docs/ARCHITECTURE.md", "docs/ARCHITECTURE.zh-CN.md",
                     "docs/PLUGIN_RUNTIME_API.md", "docs/RELEASE.md", "docs/RELEASE.zh-CN.md"):
        document = output / relative
        text = document.read_text()
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in link:
                continue
            target, _, anchor = link.partition("#")
            linked = document.parent / target if target else document
            assert linked.is_file(), (relative, link)
            if anchor:
                assert f'id="{anchor}"' in linked.read_text(), (relative, link)
        assert "plans/RESEARCH_TASK_REFACTOR_R4" not in text
    for relative in release["DOCUMENT_PROJECTIONS"]:
        assert entries[relative] == hashlib.sha256((output / relative).read_bytes()).hexdigest()

    receipt_root = Path(os.environ["SCID_TEST_LOG_DIR"])
    receipt_root.mkdir(parents=True, exist_ok=True)
    (receipt_root / "release-manifest.log").write_text(manifest.read_text())

    # The outer resource runner already holds the serial lock and supervises
    # this entire descendant tree. Forward that lock, never nest another runner.
    lock_fd = int(os.environ["SCID_TEST_LOCK_FD"])
    def check_release(lane, *targets, collect=False):
        command = [sys.executable, "-B", "-m", "pytest", "-q", "--tb=short",
                   "-o", "addopts=", "-p", "no:cacheprovider", "--test-lane", lane]
        if collect:
            command.append("--collect-only")
        command.extend(targets or ("tests",))
        log_root = Path(os.environ["SCID_TEST_LOG_DIR"])
        log_root.mkdir(parents=True, exist_ok=True)
        label = f"release-{lane}-{'collection' if collect else 'checks'}"
        command.extend(["--basetemp", str(Path(os.environ["TMPDIR"]) / label)])
        log_path = log_root / f"{label}.log"
        # Stream under the outer runner's sampled fixture-log budget.
        with log_path.open("wb") as log:
            checked = subprocess.run(command, cwd=output, env=dict(os.environ),
                                     pass_fds=(lock_fd,), stdout=log, stderr=subprocess.STDOUT,
                                     timeout=120, check=False)
        with log_path.open("rb") as log:
            log.seek(max(0, log_path.stat().st_size - 4096))
            diagnostic = log.read(4096).decode("utf-8", errors="replace")
        assert checked.returncode == 0, diagnostic
    for lane in ("source", "installed", "process"):
        check_release(lane, collect=True)
    check_release("source", "tests/operations/test_l4_live_tcad_revision_evidence.py",
                  "tests/operations/test_plugin_canonical_identity.py")
    check_release("installed",
        "tests/operations/test_catalog_installed_entrypoint.py::test_clean_installed_core_compiles_only_the_single_plugin_group",
        "tests/operations/test_catalog_installed_entrypoint.py::test_installed_figure_tool_executes_packaged_image_dependencies",
        "tests/operations/test_catalog_installed_entrypoint.py::test_installed_tcad_resolves_its_declared_curve_dependency")


@pytest.mark.parametrize('status,exit_code,accepted', [('200', 0, True), ('503', 0, False), ('000', 28, False)])
def test_approval_health_probe_has_timeout_and_reports_failure(tmp_path, status, exit_code, accepted):
    script = Path(__file__).resolve().parents[2] / 'deploy/install.sh'
    command = '''source "$1"
curl() {
    [[ "$*" == *'--connect-timeout 3'* && "$*" == *'--max-time 10'* && "$*" == *'--noproxy *'* ]] || return 99
    printf '%s' "$PROBE_STATUS"
    return "$PROBE_EXIT"
}
journalctl() { printf 'fixture: Address already in use\n'; }
probe_approval_ui
'''
    result = subprocess.run(['bash', '-c', command, 'bash', str(script)], cwd=tmp_path,
        capture_output=True, text=True, timeout=5,
        env={**os.environ, 'PROBE_STATUS': status, 'PROBE_EXIT': str(exit_code)})
    assert (result.returncode == 0) is accepted, result.stderr
    assert '(10s timeout)' in result.stdout
    if exit_code:
        assert 'timed out' in result.stderr and 'Address already in use' in result.stderr
    elif not accepted:
        assert 'HTTP 503' in result.stderr


def test_release_document_projection_preserves_sources_and_is_idempotent(tmp_path):
    import runpy
    release = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/build_git_release.py"))
    for relative, replacements in release["DOCUMENT_PROJECTIONS"].items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(original for original, _ in replacements))
    release["_project_documents"](tmp_path)
    expected = {p: (tmp_path / p).read_bytes() for p in release["DOCUMENT_PROJECTIONS"]}
    release["_project_documents"](tmp_path)
    assert expected == {p: (tmp_path / p).read_bytes() for p in expected}
    (tmp_path / "docs/ARCHITECTURE.md").write_text("unrecognized current reference")
    with pytest.raises(ValueError, match="projection drift"):
        release["_project_documents"](tmp_path)


@pytest.mark.parametrize("content", ["/home/" + "private-person/state",
                                       "192." + "168.1.1", "BEGIN " + "PRIVATE KEY"])
def test_release_scan_still_rejects_sensitive_test_fixtures(tmp_path, content):
    import runpy
    release = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/build_git_release.py"))
    path = tmp_path / "tests/fixtures/injected.txt"
    path.parent.mkdir(parents=True)
    path.write_text(content)
    with pytest.raises(RuntimeError, match="release scan failed"):
        release["_scan_release"](tmp_path)
