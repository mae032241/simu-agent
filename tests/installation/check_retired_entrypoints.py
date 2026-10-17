"""Explicit, zero-install core wheel check after retirement of the service stack."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile


def test_core_wheel_exposes_only_thin_commands_without_legacy_applications(tmp_path):
    project = Path(__file__).resolve().parents[2]
    stage = tmp_path / 'source'
    stage.mkdir()
    for name in ('pyproject.toml', 'README.md'):
        shutil.copy2(project / name, stage / name)
    shutil.copytree(project / 'src', stage / 'src',
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.egg-info', 'build'))
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    built = subprocess.run([sys.executable, '-c',
        'from setuptools.build_meta import build_wheel; build_wheel(' + repr(str(wheels)) + ')'],
        cwd=stage, capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    wheel, = wheels.glob('*.whl')
    unpacked = tmp_path / 'unpacked'
    with zipfile.ZipFile(wheel) as archive:
        assert not any(name.startswith(('scidiscovery/artifact_agent/interfaces/',
            'scidiscovery/artifact_agent/approval_ui/',
            'scidiscovery/artifact_agent/service/')) for name in archive.namelist())
        for name in ('runtime', 'execution_bridge', 'runtime_plugin_bindings', 'worker_services',
                     'state_format', 'portable_bundle'):
            assert f'scidiscovery/artifact_agent/{name}.py' not in archive.namelist()
        for name in ('analysis_artifacts', 'calculation_proof', 'pdf_tool'):
            assert f'scidiscovery/operations/{name}.py' in archive.namelist()
        assert not any('/share/scidiscovery/roles/' in name or
            '/share/scidiscovery/deploy/systemd/' in name for name in archive.namelist())
        archive.extractall(unpacked)
    environment = {**os.environ, 'PYTHONPATH': str(unpacked), 'PYTHONNOUSERSITE': '1'}
    probe = subprocess.run([sys.executable, '-c', r'''
from importlib.metadata import distribution
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys

package = distribution('scidiscovery')
assert Path(package.locate_file('')).resolve() == Path(sys.argv[1]).resolve()
scripts = {entry.name: entry for entry in package.entry_points if entry.group == 'console_scripts'}
assert set(scripts) == {'scid-research', 'scid-experiment'}
for entry in scripts.values():
    assert callable(entry.load())
    result = subprocess.run([sys.executable, '-m', entry.value.split(':')[0], '--help'],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and 'usage:' in result.stdout, result.stderr
for name in ('scidiscovery.artifact_agent.interfaces', 'scidiscovery.artifact_agent.approval_ui',
             'scidiscovery.artifact_agent.service', 'scidiscovery.artifact_agent.runtime',
             'scidiscovery.artifact_agent.execution_bridge', 'scidiscovery.artifact_agent.runtime_plugin_bindings',
             'scidiscovery.artifact_agent.worker_services', 'scidiscovery.artifact_agent.state_format',
             'scidiscovery.artifact_agent.portable_bundle',
             'scidiscovery.platforms.codex', 'scidiscovery.platforms.codex_root_host'):
    assert find_spec(name) is None, name
assert not any(entry.group == 'scidiscovery.instance_views' for entry in package.entry_points)
''', str(unpacked)], cwd=tmp_path, env=environment,
        capture_output=True, text=True, timeout=30, check=False)
    assert probe.returncode == 0, probe.stdout + probe.stderr
