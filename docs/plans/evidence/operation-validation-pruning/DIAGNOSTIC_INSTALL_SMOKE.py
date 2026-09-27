"""Bounded offline wheel smoke for the two analysis configurations only."""
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import venv

repo=Path("/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2")
reuse = len(sys.argv) > 1
root=Path(sys.argv[1]) if reuse else Path(tempfile.mkdtemp(prefix="scid-diagnostic-install-"))
wheelhouse=root/"wheels"; wheelhouse.mkdir(exist_ok=True)
clean_env={**os.environ,"PYTHONPATH":"","PYTHONNOUSERSITE":"1"}
ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", "build")
sources=[]
for name, files, trees in (
    ("core", ("pyproject.toml","README.md"), ("src","roles","deploy/systemd")),
    ("curve", ("plugins/curve_score/pyproject.toml",), ("plugins/curve_score/curve_score",)),
    ("tcad", ("plugins/tcad_artifact/pyproject.toml",), ("plugins/tcad_artifact/tcad_artifact","plugins/tcad_artifact/deploy","plugins/tcad_artifact/config")),
):
    if reuse:
        continue
    stage=root/("source-"+name); stage.mkdir()
    prefix=repo if name=="core" else repo/"plugins"/("curve_score" if name=="curve" else "tcad_artifact")
    for relative in (*files,*trees):
        source=repo/relative; target=stage/source.relative_to(prefix)
        if source.is_dir():
            shutil.copytree(source,target,ignore=ignore)
        else:
            target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
    sources.append(stage)
    subprocess.run([sys.executable,"-m","pip","wheel","--no-deps","--no-build-isolation","--no-index",
                    "--wheel-dir",str(wheelhouse),str(stage)],
                   cwd=root,env=clean_env,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    print("Built",name,flush=True)

fixtures=runpy.run_path(str(repo/"tests/operations/conftest.py"))
dependencies=fixtures["_supply_runtime_dependencies"]
envs={}
wheels=list(wheelhouse.glob("*.whl"))
core=next(p for p in wheels if p.name.startswith("scidiscovery-"))
curve=next(p for p in wheels if p.name.startswith("scidiscovery_curve_score-"))
tcad=next(p for p in wheels if p.name.startswith("tcad_artifact-"))
for name, selected in (("curve",(core,curve)),("full",(core,curve,tcad))):
    target=root/name
    if not reuse:
        venv.EnvBuilder(with_pip=True,system_site_packages=False).create(target)
        dependencies(target)
    python=target/"bin/python"
    subprocess.run([str(python),"-m","pip","install","--no-deps","--no-index",*map(str,selected)],
                   cwd=root,env=clean_env,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    work=root/(name+"-work"); work.mkdir(exist_ok=True)
    envs[name]=(python,work)
    print("Installed isolated",name,flush=True)

def probe(environment,source):
    python,work=envs[environment]
    env={**os.environ,"PYTHONPATH":"","PYTHONNOUSERSITE":"1"}
    code="import sys\nfrom pathlib import Path\nassert "+repr(str(repo))+" not in sys.path\n"+source
    result=subprocess.run([str(python),"-c",code],cwd=work,env=env,
                          capture_output=True,text=True,timeout=180)
    if result.returncode:
        print(result.stdout,result.stderr,flush=True)
        raise RuntimeError("installed probe failed: "+environment)
    return result.stdout

checks=runpy.run_path(str(repo/"tests/operations/test_analysis_tool_installed.py"))
for environment in ("curve","full"):
    checks["test_installed_analysis_catalog_and_worker_projection"](probe,environment)
    print("PASS installed tools and image-permission projection:",environment,flush=True)
checks["test_installed_generic_score_runs_without_tcad"](probe)
print("PASS installed generic scoring, residual localization and readable PNG without TCAD",flush=True)
checks["test_installed_catalog_identity_matches_source"](probe,root,"full")
print("PASS installed full catalog identity equals exact source",flush=True)
print("ARTIFACT_ROOT",root,flush=True)
