"""One isolated wheel environment and real local Worker stdio for three analyses."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

repository = Path.cwd()
evidence = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp(prefix='scid-handoff-installed-'))
sys.path.insert(0, str(repository))
from tests.operations.conftest import _supply_runtime_dependencies, _copy_runtime_distribution


def run(command, **kwargs):
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=65, **kwargs)
    if result.returncode:
        raise RuntimeError(f'exit {result.returncode}:\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}')
    return result.stdout


release = root/'source'
run([sys.executable, str(repository/'scripts/build_git_release.py'), '--source', str(repository), '--output', str(release)])
wheelhouse = root/'wheels'; wheelhouse.mkdir()
for source in (release, release/'plugins/tcad_artifact', release/'plugins/curve_score', release/'plugins/curve_figure_evidence'):
    run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--wheel-dir', str(wheelhouse), str(source)])
environment = root/'venv'
venv.EnvBuilder(with_pip=False, system_site_packages=False).create(environment)
_supply_runtime_dependencies(environment)
site = environment/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
for package in ('pytest', 'pluggy', 'iniconfig', 'packaging', 'pygments'):
    _copy_runtime_distribution(package, site)
run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', '--no-compile', '--target', str(site),
    *map(str, wheelhouse.glob('*.whl'))])
baseline = json.loads((evidence/'source-baseline.json').read_text())
packaged = {}
for item in baseline['files']:
    name = item['path']
    if name.startswith('src/'):
        installed = site/Path(name).relative_to('src')
    elif name.startswith('plugins/') and name.endswith('.py'):
        installed = site/Path(*Path(name).parts[2:])
    else:
        continue
    assert installed.read_bytes() == (repository/name).read_bytes(), name
    packaged[name] = hashlib.sha256(installed.read_bytes()).hexdigest()
probe = r'''
import json, subprocess, sys, tempfile
from pathlib import Path
import scidiscovery, tcad_artifact, curve_score
from scidiscovery.operations.catalog import compile_installed_catalog
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
catalog = compile_installed_catalog()
sys.path.append(REPOSITORY)  # Only fixture helpers; production imports stay in the wheel environment.
from tests.operations import test_tcad_result_analysis as tcad
from tests.operations import test_m2_curve_analysis_boundary as curve
from tests.operations.test_analysis_claim_scope import generic_worker, precomputed_worker
from tests.operations.test_analysis_handoff_report import compact_report
from curve_score.science_operations import Components
tcad.compile_catalog = lambda plugins: catalog
curve.compile_catalog = lambda plugins: catalog
records = []
for kind, operation_id, alias in (
    ('tcad', 'tcad.result.analyze.v1', 'runtime_manifest'),
    ('generic', 'science.result.diagnose.v1', 'experiment_results'),
    ('curve_error', 'science.result.diagnose.curve-error.v1', 'curve_analysis_package')):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        if kind == 'tcad':
            worker, opened = tcad.open_analysis(tcad.analysis_system(root))
        elif kind == 'generic':
            worker, opened = generic_worker(root)
        else:
            package = Components.curve_error_analysis.implementation(
                {name: (raw,) for name, raw in curve._inputs().items()})['curve_analysis_package'][0]
            _, runtime, instance, facade = curve._root(root)
            artifact = runtime.artifacts.register(package, ArtifactRegistration(kind='fixture',
                schema_id='scidiscovery.curve-diagnostic-analysis.v1', payload_schema_version=1,
                media_type='application/json', creator=runtime.actor), idempotency_key='fixed-package')
            runtime.scheduler_bindings.bind(instance=instance.instance_id, namespace='artifact', name='fixed_package', object_id=artifact.artifact_id)
            facade.call_tool('operation_invoke', dict(name='precomputed', operation_id=operation_id,
                instruction='Interpret the exact fixture package.', inputs=[dict(port='curve_analysis_package', artifact_names=['fixed_package'])]))
        runs = runtime.runs if kind == 'curve_error' else worker.runs
        run_id = runtime.scheduler_bindings.resolve(instance=instance.instance_id, namespace='run', name='precomputed') if kind == 'curve_error' else worker._run_id
        assert runs.status(run_id).operation_digest == catalog.operation(operation_id).digest, kind
        command = [sys.executable, '-I', '-m', 'scidiscovery.artifact_agent.interfaces.mcp_local_worker',
            '--state-root', str(root/'state'), '--local-workspace-root', str(runs.backend.root),
            '--operation-id', operation_id, '--operation-digest', catalog.operation(operation_id).digest]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def rpc(index, name):
            process.stdin.write(json.dumps(dict(jsonrpc='2.0', id=index, method='tools/call', params=dict(name=name, arguments={})))+'\n')
            process.stdin.flush()
            reply = json.loads(process.stdout.readline())
            assert 'error' not in reply, (kind, reply)
            return reply['result']['structuredContent']
        try:
            opened = rpc(1, 'worker_open_assignment')
            workspace = Path(opened['workspace_path'])
            domain = json.loads(Path(opened['domain_workspace_path']).read_bytes())
            assert domain['patch_contract']['draft_may_omit'] == ['/handoff']
            start = Path(opened['start_here_path']); assert start.is_file()
            draft = compact_report(alias)
            (workspace/'output/result.json').write_bytes(canonical_json(dict(schema_version=1, payload=draft)))
            submitted = rpc(2, 'worker_submit_result')
        finally:
            process.stdin.close()
            process.wait(timeout=10)
        assert process.returncode == 0, process.stderr.read()
        assert submitted['state'] == 'completed', submitted
        state = runs.status(run_id)
        assert state.signal.verdict == 'inconclusive' and 'payload.summary' in state.signal.summary
        sealed = json.loads(runs.artifacts.read(state.output_ref))
        assert sealed['summary'] == draft['summary'] and sealed.get('gates') is None
        records.append(dict(operation_id=operation_id, state=submitted['state'], start_bytes=start.stat().st_size))
for module in list(sys.modules.values()):
    name = getattr(module, '__name__', '')
    if name.split('.')[0] in {'scidiscovery', 'tcad_artifact', 'curve_score'} and getattr(module, '__file__', None):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix)), module.__file__
print(json.dumps(dict(catalog_count=len(catalog.operation_ids()), stdio=records, real_agent=False)))
'''.replace('REPOSITORY', repr(str(repository)))
script = root/'probe.py'; script.write_text(probe)
clean = {**os.environ, 'PYTHONNOUSERSITE': '1'}
clean.pop('PYTHONPATH', None); clean.pop('SCIDISCOVERY_ROLE_DIR', None)
record = json.loads(run([str(environment/'bin/python'), '-I', str(script)], env=clean))
record.update(status='pass', root=str(root), packaged_source_sha256=packaged,
    boundary='Installed local Worker stdio with fixture tasks; no live Agent, daemon, VM or solver')
(evidence/'installed-smoke.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
