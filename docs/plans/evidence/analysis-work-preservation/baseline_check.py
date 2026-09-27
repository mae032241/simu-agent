"""Reproduce unrelated legacy failures against the saved pre-change source."""
from pathlib import Path
import json, shutil, subprocess, sys, tempfile
base=Path(__file__).resolve().parent;repo=base.parents[3]
root=Path(tempfile.mkdtemp(prefix='scid-analysis-before-'))
ignore=shutil.ignore_patterns('build','__pycache__','*.pyc','*.egg-info','.pytest_cache')
for name in ('src','plugins','tests','roles'):
 shutil.copytree(repo/name,root/name,ignore=ignore)
for name in ('pyproject.toml','conftest.py'):
 if (repo/name).exists():shutil.copyfile(repo/name,root/name)
for name in json.loads((base/'baseline.json').read_text()):
 source=base/'baseline'/name
 target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(source,target)
print('Using saved pre-change sources',flush=True)
selection=sys.argv[1:] or ['tests/operations/test_l2_run_invariants.py','-k',
 'candidate_binding_crash or status_is_pure_and_failure or tool_projection_identity or real_process_failure_isolation']
result=subprocess.run([sys.executable,'-m','pytest','-q',*selection],cwd=root,timeout=90)
print('Baseline return code:',result.returncode,flush=True)
sys.exit(result.returncode)
