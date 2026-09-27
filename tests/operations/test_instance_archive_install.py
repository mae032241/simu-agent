import grp
import os
from pathlib import Path
import pwd
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _install_function(workspace, *arguments):
    return subprocess.run(["bash", "-c", 'source "$1"; shift; "$@"', "bash",
        str(ROOT / "deploy/install.sh"), *arguments], capture_output=True, text=True, timeout=10,
        env={**os.environ, "SCID_WORKSPACE": str(workspace), "SCID_PYTHON": sys.executable,
             "SCID_SERVICE_USER": pwd.getpwuid(os.getuid()).pw_name,
             "SCID_SERVICE_GROUP": grp.getgrgid(os.getgid()).gr_name})


@pytest.mark.parametrize("symlink_part", [None, ".scidiscovery-archive", "instances"])
def test_archive_directory_creation_is_narrow_and_refuses_symlinks(tmp_path, symlink_part):
    workspace, outside = tmp_path / "workspace", tmp_path / "outside"
    workspace.mkdir(mode=0o711)
    outside.mkdir(mode=0o711)
    original_workspace, original_outside = workspace.stat().st_mode, outside.stat().st_mode
    archive = workspace / ".scidiscovery-archive"
    if symlink_part == ".scidiscovery-archive":
        archive.symlink_to(outside, target_is_directory=True)
    elif symlink_part == "instances":
        archive.mkdir()
        (archive / "instances").symlink_to(outside, target_is_directory=True)
    result = _install_function(workspace, "create_instance_archive_root")
    assert (result.returncode == 0) is (symlink_part is None), result.stderr
    assert workspace.stat().st_mode == original_workspace
    assert outside.stat().st_mode == original_outside
    if symlink_part is None:
        assert (archive / "instances").is_dir()
        assert (archive / "instances").stat().st_mode & 0o777 == 0o750


def test_only_approval_service_can_write_fixed_archive_root(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output = tmp_path / "units"
    result = _install_function(workspace, "render_units", str(output))
    assert result.returncode == 0, result.stderr
    ui = (output / "scidiscovery-approval-ui.service").read_text()
    control = (output / "scidiscovery-control.service").read_text()
    exact = str(workspace / ".scidiscovery-archive" / "instances")
    assert f'"{exact}"' in next(line for line in ui.splitlines() if line.startswith("ReadWritePaths="))
    assert exact not in control
    assert f'--local-workspace-root "{workspace / ".scidiscovery-runs"}"' in ui
    assert "@INSTANCE_ARCHIVE_ROOT@" not in ui
