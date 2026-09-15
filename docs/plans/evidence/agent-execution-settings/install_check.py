"""Build four wheels serially, then retain one isolated installation for P6 probes."""
import json, os, subprocess, sys, venv
from pathlib import Path
repo=Path.cwd(); evidence=Path(__file__).resolve().parent
base=Path(os.environ.get('SCID_SETTINGS_INSTALL_ROOT','/tmp/scid-execution-settings-installed'));base.mkdir(exist_ok=True)
source=base/'source'; wheels=base/'wheels'; wheels.mkdir(exist_ok=True)
with (evidence/os.environ.get('SCID_SETTINGS_BUILD_LOG','installed-build.log')).open('w') as log:
 def run(args):subprocess.run([str(a) for a in args],cwd=base,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=150)
 run([sys.executable,repo/'scripts/build_git_release.py','--source',repo,'--output',source])
 for package in (source,source/'plugins/tcad_artifact',source/'plugins/curve_score',source/'plugins/curve_figure_evidence'):
  run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',wheels,package])
 environment=base/'venv';venv.EnvBuilder(with_pip=True,system_site_packages=False).create(environment)
 sys.path.insert(0,str(repo))
 from tests.operations.conftest import _supply_runtime_dependencies, _copy_runtime_distribution
 _supply_runtime_dependencies(environment)
 site=environment/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
 for name in ('pytest','pluggy','iniconfig','packaging','pygments'):_copy_runtime_distribution(name,site)
 python=environment/'bin/python'
 run([python,'-m','pip','install','--no-index','--no-deps',*sorted(wheels.glob('*.whl'))])
 result={'installed_wheels':len(list(wheels.glob('*.whl'))),'python':str(python),'site':str(site),'source':str(source),'system_site_packages':False}
 (evidence/'INSTALLED.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
