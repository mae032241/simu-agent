"""Adaptive solver frames are collected from actual files, not guessed names."""

import hashlib

import pytest

from tcad_artifact import remote_runner_py36
from tcad_artifact.operation_workspace import _attempt_files
from tcad_artifact.project_packager import (
    ReviewedDeckPackage, RuntimeOutputRecord, TCADRuntimeManifest,
    attest_runtime_contract, deck_project_diff,
)
from tcad_artifact.worker import _collect_outputs
from tests.operations.test_runtime_plugin_configuration import _reviewed_package


@pytest.mark.parametrize("collector", [_collect_outputs, remote_runner_py36._collect_expected])
def test_collects_all_adaptive_frames_and_skips_unchanged_inputs(tmp_path, collector):
    source = tmp_path / "main.cmd"
    source.write_bytes(b"solver input")
    original = {"relative_path": "main.cmd", "size_bytes": source.stat().st_size,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    frames = tmp_path / "frames"
    frames.mkdir()
    for index in range(79):
        (frames / f"movie_{index:04d}.tdr").write_bytes(f"frame {index}".encode())
    records = collector(tmp_path if collector is _collect_outputs else str(tmp_path), [],
                        {"max_output_bytes": 4096}, archive_entries=[original],
                        collect_generated_outputs=True)
    assert len(records) == 79
    assert [item["relative_path"] for item in records] == [
        f"frames/movie_{index:04d}.tdr" for index in range(79)
    ]
    assert all(item["name"] == "generated_" + hashlib.sha256(
        item["relative_path"].encode()).hexdigest() for item in records)


@pytest.mark.parametrize("collector", [_collect_outputs, remote_runner_py36._collect_expected])
def test_generated_capture_fails_closed_on_budget_and_symlink(tmp_path, collector):
    frame = tmp_path / "frame.tdr"
    frame.write_bytes(b"frame")
    root = tmp_path if collector is _collect_outputs else str(tmp_path)
    with pytest.raises(RuntimeError, match="total output exceeds job limit"):
        collector(root, [], {"max_output_bytes": 4}, collect_generated_outputs=True)
    frame.unlink()
    frame.symlink_to(tmp_path / "other.tdr")
    (tmp_path / "other.tdr").write_bytes(b"other")
    with pytest.raises((OSError, RuntimeError, ValueError)):
        collector(root, [], {"max_output_bytes": 4096}, collect_generated_outputs=True)


@pytest.mark.parametrize("collector", [_collect_outputs, remote_runner_py36._collect_expected])
def test_generated_capture_rejects_empty_set(tmp_path, collector):
    root = tmp_path if collector is _collect_outputs else str(tmp_path)
    with pytest.raises(RuntimeError, match="no generated output files"):
        collector(root, [], {"max_output_bytes": 4096}, collect_generated_outputs=True)


@pytest.mark.parametrize("collector", [_collect_outputs, remote_runner_py36._collect_expected])
def test_changed_staged_input_is_not_silently_excluded(tmp_path, collector):
    source = tmp_path / "main.cmd"
    source.write_bytes(b"before")
    original = {"relative_path": "main.cmd", "size_bytes": 6,
                "sha256": hashlib.sha256(b"before").hexdigest()}
    source.write_bytes(b"after")
    root = tmp_path if collector is _collect_outputs else str(tmp_path)
    records = collector(root, [], {"max_output_bytes": 4096},
                        archive_entries=[original], collect_generated_outputs=True)
    assert [item["relative_path"] for item in records] == ["main.cmd"]


@pytest.mark.parametrize("collector", [_collect_outputs, remote_runner_py36._collect_expected])
def test_generated_capture_rejects_symlinked_directory(tmp_path, collector):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "frame.tdr").write_bytes(b"frame")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    root = tmp_path if collector is _collect_outputs else str(tmp_path)
    with pytest.raises(RuntimeError, match="not a real directory"):
        collector(root, [], {"max_output_bytes": 4096}, collect_generated_outputs=True)


def test_runtime_attestation_accepts_only_manifest_named_generated_files():
    package = ReviewedDeckPackage.model_validate_json(_reviewed_package(), strict=True)
    project = package.project.model_copy(update={"collect_generated_outputs": True,
                                              "expected_outputs": ()})
    assert "collect_generated_outputs" in deck_project_diff(
        package.project, project)["frozen_field_changes"]
    package = package.model_copy(update={"project": project})
    raw = b"adaptive frame"
    path = "frames/movie_0079.tdr"
    name = "generated_" + hashlib.sha256(path.encode()).hexdigest()
    record = RuntimeOutputRecord(name=name, relative_path=path,
                                 media_type="application/octet-stream",
                                 sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
    manifest = TCADRuntimeManifest(started_at=None, completed_at="2026-09-24T00:00:00Z",
                                   terminal_state="succeeded", exit_code=0,
                                   error="", outputs=(record,))
    assert attest_runtime_contract(package, manifest,
                                   output_payloads={name: raw}).verdict == "pass"
    wrong = manifest.model_copy(update={"outputs": (record.model_copy(update={"name": "frame_79"}),)})
    assert attest_runtime_contract(package, wrong).verdict == "fail"


def test_gap_snapshot_keeps_diagnostic_manifest_without_duplicating_raw_frames(tmp_path):
    deck = tmp_path / "deck"
    (deck / "files").mkdir(parents=True)
    (deck / "files/main.cmd").write_text("puts ready\n")
    (deck / "reports/init").mkdir(parents=True)
    (deck / ("reports/init/generated_" + "a" * 64)).write_bytes(b"x" * (17 * 1024 * 1024))
    (deck / "reports/diagnostic-init.json").write_text('{"frames":79}')
    attempt = _attempt_files(deck)
    assert {item.relative_path for item in attempt} == {
        "files/main.cmd", "reports/diagnostic-init.json"
    }


def test_installed_generated_capture_has_the_same_directory_contract(installed_probe):
    installed_probe('full', r'''
from pathlib import Path
from tempfile import TemporaryDirectory
from tcad_artifact.worker import _collect_outputs
from tcad_artifact import remote_runner_py36

with TemporaryDirectory() as temporary:
    root = Path(temporary)
    frames = root / 'frames'
    frames.mkdir()
    for index in range(79):
        (frames / ('movie_%04d.tdr' % index)).write_bytes(b'frame')
    local = _collect_outputs(root, [], {'max_output_bytes': 4096}, collect_generated_outputs=True)
    remote = remote_runner_py36._collect_expected(str(root), [], {'max_output_bytes': 4096}, collect_generated_outputs=True)
    assert local == remote
    assert len(local) == 79
''')
