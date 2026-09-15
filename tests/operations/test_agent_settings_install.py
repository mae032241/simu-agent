"""First-create and upgrade preservation through the real installer function."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_settings_first_create_upgrade_preserve_and_symlink_rejection(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    # Only ownership needs root; exercise real file creation without changing ownership.
    command = ["bash", "-c", 'source "$1"; chown() { :; }; ensure_agent_settings',
               "bash", str(ROOT / "deploy/install.sh")]
    env = {**os.environ, "SCID_CONFIG_ROOT": str(config), "SCID_PYTHON": sys.executable}
    def run():
        return subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert run().returncode == 0
    path = config / "agent-settings.json"
    assert json.loads(path.read_text())["defaults"]["narrative_language"] == "zh-CN"
    assert path.stat().st_mode & 0o777 == 0o640
    user_bytes = b'{"defaults":{"model":"custom-model","narrative_language":"en"}}\n'
    path.write_bytes(user_bytes)
    assert run().returncode == 0
    assert path.read_bytes() == user_bytes
    path.unlink()
    outside = tmp_path / "outside.json"
    outside.write_bytes(user_bytes)
    path.symlink_to(outside)
    assert run().returncode != 0
    assert outside.read_bytes() == user_bytes


def test_both_service_units_use_same_global_settings_file(tmp_path):
    from tests.operations.test_instance_archive_install import _install_function
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    units = tmp_path / "units"
    result = _install_function(workspace, "render_units", str(units))
    assert result.returncode == 0, result.stderr
    paths = []
    for name in ("control", "approval-ui"):
        lines = (units / f"scidiscovery-{name}.service").read_text().splitlines()
        paths.append(next(line for line in lines if "SCID_AGENT_SETTINGS_FILE=" in line))
    assert paths[0] == paths[1]
    assert "@AGENT_SETTINGS_FILE@" not in paths[0]
