import os,runpy,subprocess,sys,tempfile,venv
from pathlib import Path
repo=Path.cwd()
root=Path(tempfile.mkdtemp(prefix='scid-handoff-installed-'))
def run(args,**kw):
 p=subprocess.run(args,cwd=root,capture_output=True,text=True,timeout=120,**kw)
 if p.returncode: raise RuntimeError(p.stdout+'\n'+p.stderr)
 return p.stdout
release=root/'source'
run([sys.executable,str(repo/'scripts/build_git_release.py'),'--source',str(repo),'--output',str(release)])
wheels=root/'wheels';wheels.mkdir()
for source in (release,release/'plugins/curve_score',release/'plugins/tcad_artifact'):
 run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--no-index','-w',str(wheels),str(source)])
envroot=root/'venv';venv.EnvBuilder(with_pip=True,system_site_packages=False).create(envroot)
runpy.run_path(str(repo/'tests/operations/conftest.py'))['_supply_runtime_dependencies'](envroot)
python=envroot/'bin/python'
run([str(python),'-m','pip','install','--no-index','--no-deps',*map(str,wheels.glob('*.whl'))])
env=dict(os.environ);env.pop('PYTHONPATH',None);env['PYTHONNOUSERSITE']='1'
def probe(name,source):
 assert name=='full'
 prefix='from pathlib import Path\nimport sys,scidiscovery\nassert Path(scidiscovery.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())\n'
 return run([str(python),'-c',prefix+source],env=env)
ns=runpy.run_path(str(repo/'tests/operations/test_analysis_tool_installed.py'))
ns['test_installed_analysis_catalog_and_worker_projection'](probe,'full')
print('PASS isolated full wheel catalog, shared contexts, gap schema and Worker projection')
print('Evidence environment:',root)
