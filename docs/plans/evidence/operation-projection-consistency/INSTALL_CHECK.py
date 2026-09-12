"""Bounded offline wheel/entry-point checks for the R1 projection repair.

Run through RESOURCE_GUARD.py from the repository root. Only four isolated
environments are built; no installed production service or research instance is
modified. Existing installed test functions supply assertions and clean imports.
"""
from pathlib import Path
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import venv

ROOT = Path.cwd()
EVIDENCE = ROOT / 'docs/plans/evidence/operation-projection-consistency'
WORK = Path(tempfile.mkdtemp(prefix='scid-projection-installed-'))
clean = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK='1', PYTHONNOUSERSITE='1')
clean.pop('PYTHONPATH', None)
clean.pop('SCIDISCOVERY_ROLE_DIR', None)


def command(*args):
    result = subprocess.run(args, cwd=WORK, env=clean, text=True, capture_output=True, timeout=180)
    if result.returncode:
        print(result.stdout)
        print(result.stderr)
        result.check_returncode()


helpers = runpy.run_path(str(ROOT / 'tests/operations/conftest.py'))
release = WORK / 'source-release'
command(sys.executable, str(ROOT / 'scripts/build_git_release.py'), '--source', str(ROOT), '--output', str(release))
wheelhouse = WORK / 'wheels'
wheelhouse.mkdir()
blind = WORK / 'blind-fixture'
shutil.copytree(ROOT / 'tests/fixtures/plugins/blind_csv_operation_plugin', blind,
                ignore=shutil.ignore_patterns('build', '*.egg-info', '__pycache__'))
for source in (release, release / 'plugins/curve_score', release / 'plugins/tcad_artifact',
               release / 'plugins/curve_figure_evidence', blind):
    command(sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
            '--wheel-dir', str(wheelhouse), str(source))
wheels = list(wheelhouse.glob('*.whl'))


def wheel(prefix):
    return next(str(p) for p in wheels if p.name.startswith(prefix))


core = wheel('scidiscovery-0')
curve = wheel('scidiscovery_curve_score-')
tcad = wheel('tcad_artifact-')
figure = wheel('scidiscovery_curve_figure_evidence-')
blind = wheel('scidiscovery_blind_csv_test_plugin-')
environments = {}
for name, selected in {'curve': (core, curve), 'full': (core, curve, tcad),
                       'all_domains': (core, curve, tcad, figure), 'blind_csv': (core, blind)}.items():
    path = WORK / name
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(path)
    helpers['_supply_runtime_dependencies'](path)
    python = path / 'bin/python'
    command(str(python), '-m', 'pip', 'install', '--no-index', '--no-deps', *selected)
    workdir = WORK / (name + '-workdir')
    workdir.mkdir()
    environments[name] = helpers['InstalledEnvironment'](python=python, workdir=workdir)
metadata = {
    'workdir': str(WORK),
    'wheels': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels},
    'environments': {k: {'python': str(v.python), 'workdir': str(v.workdir)} for k, v in environments.items()},
}
(EVIDENCE / 'INSTALL_BUNDLE.json').write_text(json.dumps(metadata, indent=2) + '\n')
probe = helpers['installed_probe'].__wrapped__(environments)
checks = runpy.run_path(str(ROOT / 'tests/operations/test_analysis_tool_installed.py'))
completed = []


def check(name, *args):
    checks[name](probe, *args)
    completed.append({'name': name, 'arguments': list(map(str, args))})
    (EVIDENCE / 'INSTALLED_CHECKS.json').write_text(json.dumps(completed, indent=2) + '\n')
    print('PASS', name, *args, flush=True)


for environment in ('full', 'all_domains'):
    check('test_installed_catalog_identity_matches_source', WORK, environment)
for entry in ('local_worker', 'hardened_worker', 'proxy'):
    check('test_installed_stdio_errors_share_protocol_diagnostics', entry)
for environment in ('curve', 'full'):
    check('test_installed_analysis_catalog_and_worker_projection', environment)
check('test_installed_generic_score_runs_without_tcad')
check('test_installed_hardened_open_contract_and_typed_edit_error')
check('test_installed_generic_no_score_worker_seals_failed_result')
check('test_installed_raw_tcad_worker_score_identity_replay_and_submit')
print(json.dumps({'status': 'PASS', 'checks': len(completed), 'workdir': str(WORK)}))
