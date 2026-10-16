"""Frozen common originals cross the actual cov launcher's file-only boundary."""
import copy
import importlib.util
from pathlib import Path

import pytest

from execution_fixtures import execution_registry, remote_registry
from test_nonlocal_execution_observation import case, run
from test_history_handoff import finish
from scidiscovery.research_loop import contracts as c, execution


def prepared(tmp_path, monkeypatch):
    spec=importlib.util.spec_from_file_location('managed_cov_launcher',Path(__file__).resolve().parents[2]/'scripts/acceptance/rootless_cov_launcher.py')
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    root,job,config,cli=case(tmp_path,monkeypatch)
    # Identical bytes under distinct call/descriptor identities must stay distinct.
    for label in ('P','Q'):run(root,cli,label)
    finish(root,2,'W',[1],mechanism_findings=[dict(mechanism=label,basis='observed',finding='Bounded synthetic evidence.') for label in ('P','Q')])
    job=c.build_job(root,3,'A',[1,2])
    return launcher,root,job


def test_frozen_managed_outputs_mount_with_exact_descriptor_and_no_backend_reload(tmp_path,monkeypatch,remote_registry):
    from scidiscovery.research_loop import experiments
    launcher,root,job=prepared(tmp_path,monkeypatch)
    monkeypatch.setattr(experiments,'load',lambda *a,**kw:pytest.fail('launcher must not query backend'))
    mounts=launcher.direct_materials(dict(scene_root=str(root)),c.workspace(root,3),root/'jobs/003.json')
    assert len(mounts)==2
    assert [target for _,target in mounts]==[str(c.workspace(root,3)/row['path']) for row in job['direct_materials']]
    assert all('observed-originals' in source for source,_ in mounts)
    assert all(Path(source).read_bytes().startswith(b'opaque remote package') for source,_ in mounts)


@pytest.mark.parametrize('fault',['call','name','source','proof','digest','size','symlink','duplicate'])
def test_managed_exports_reject_unbound_or_changed_originals(tmp_path,monkeypatch,remote_registry,fault):
    launcher,root,job=prepared(tmp_path,monkeypatch)
    job=copy.deepcopy(job);item=job['direct_materials'][0];source=Path(item['source'])
    if fault=='call':item['path']=item['path'].replace(source.parts[-3],'different-call')
    elif fault=='name':item['path']=str(Path(item['path']).with_name('not-the-collected-name'))
    elif fault=='source':
        outside=tmp_path/'private';outside.write_bytes(source.read_bytes());item['source']=str(outside)
    elif fault=='proof':
        seal=c.read(execution.record(root,2)/'result-identity.json');path=root/seal['observations']['path']
        value=c.read(path);value['managed_calls'][0]['outputs'][0]['name']='other-descriptor';c.write(path,value)
    elif fault=='digest':item['sha256']='f'*64
    elif fault=='size':item['size_bytes']+=1
    elif fault=='symlink':
        source.chmod(0o600);data=source.read_bytes();source.unlink();other=tmp_path/'same-bytes';other.write_bytes(data);source.symlink_to(other)
    elif fault=='duplicate':job['direct_materials'].append(dict(item))
    c.write(root/'jobs/003.json',job)
    with pytest.raises((ValueError,OSError)):
        launcher.direct_materials(dict(scene_root=str(root)),c.workspace(root,3),root/'jobs/003.json')
