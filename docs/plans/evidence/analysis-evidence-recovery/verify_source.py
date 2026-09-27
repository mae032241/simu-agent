"""Verify the exact task increment against its P0 source snapshot."""
from pathlib import Path
import ast
import difflib
import hashlib
import json
import subprocess
import tarfile

base = Path(__file__).resolve().parent
root = base.parents[3]
records = json.loads((base/'baseline.json').read_text())
with tarfile.open(base/'baseline.tar.gz') as archive:
    before = {item.name: archive.extractfile(item).read() for item in archive if item.isfile()}
paths = set(records['files'])
for prefix in ('src','plugins','tests','roles','docs','deploy'):
    paths.update(str(p.relative_to(root)) for p in (root/prefix).rglob('*')
                 if p.is_file() and p.suffix in {'.py','.md','.sh'} and 'evidence' not in p.parts)
changed = {}
patch = []
for name in sorted(paths):
    old = before.get(name,b'')
    path = root/name
    new = path.read_bytes() if path.exists() else b''
    if new == old:
        continue
    if name in records['files']:
        assert hashlib.sha256(old).hexdigest() == records['files'][name]
    changed[name] = {'before': hashlib.sha256(old).hexdigest() if name in before else None,
                     'after': hashlib.sha256(new).hexdigest() if path.exists() else None,
                     'bytes':len(new)}
    if path.suffix == '.py':
        ast.parse(new,filename=name)
    patch.extend(difflib.unified_diff(old.decode().splitlines(keepends=True),new.decode().splitlines(keepends=True),
        fromfile='a/'+name if name in before else '/dev/null',tofile='b/'+name if path.exists() else '/dev/null'))
(base/'implementation.patch').write_text(''.join(patch))
ast.parse((root/'plugins/tcad_artifact/tcad_artifact/remote_runner_py36.py').read_text(),feature_version=(3,6))
subprocess.run(['git','diff','--check'],cwd=root,check=True)
subprocess.run(['git','apply','--check','--reverse',str(base/'implementation.patch')],cwd=root,check=True)
plan = root/'docs/plans/ANALYSIS_CONTROLLED_EVIDENCE_RECOVERY_PLAN.zh-CN.md'
assert hashlib.sha256(plan.read_bytes()).hexdigest() == records['plan_sha256']
result={'base_head':records['head'],'plan_sha256':records['plan_sha256'],'changed_files':changed,
        'python_ast':'pass','remote_python36_syntax':'pass','git_diff_check':'pass','increment_reverse_check':'pass'}
(base/'source-check.json').write_text(json.dumps(result,indent=2))
print('Exact increment:',len(changed),'files; Python AST, Python 3.6 syntax, whitespace and reverse patch checks passed.')
