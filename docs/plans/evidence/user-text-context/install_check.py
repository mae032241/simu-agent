import json, subprocess, sys, venv
from pathlib import Path
repo=Path.cwd(); out=Path(__file__).parent; build=out/'installed';build.mkdir()
source=build/'source';wheels=build/'wheels';wheels.mkdir()
log=(build/'build.log').open('w')
def run(args,timeout=150):
    subprocess.run(list(map(str,args)),cwd=build,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
run([sys.executable,repo/'scripts/build_git_release.py','--source',repo,'--output',source])
for path in (source,source/'plugins/tcad_artifact',source/'plugins/curve_score',source/'plugins/curve_figure_evidence'):
    run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',wheels,path])
environment=build/'venv';venv.EnvBuilder(with_pip=True,system_site_packages=False).create(environment)
sys.path.insert(0,str(repo))
from tests.operations.conftest import _supply_runtime_dependencies,_copy_runtime_distribution
_supply_runtime_dependencies(environment)
site=environment/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'site-packages'
for name in ('pytest','pluggy','iniconfig','packaging','pygments'):
    _copy_runtime_distribution(name,site)
python=environment/'bin/python'
run([python,'-m','pip','install','--no-index','--no-deps',*sorted(wheels.glob('*.whl'))])
probe=subprocess.run([str(python),str(out/'install_probe.py'),str(repo)],cwd=build,capture_output=True,text=True,timeout=150)
(out/'installed-probe.stdout').write_text(probe.stdout);(out/'installed-probe.stderr').write_text(probe.stderr)
print(probe.stdout);print(probe.stderr);probe.check_returncode()
