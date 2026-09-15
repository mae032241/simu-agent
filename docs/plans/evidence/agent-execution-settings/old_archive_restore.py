"""Restore a real old installed archive with the isolated candidate installation."""
import hashlib,json,sys
from pathlib import Path
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
import scidiscovery
assert '/scid-execution-settings-installed/venv/' in scidiscovery.__file__
root=Path(sys.argv[1]);evidence=Path(sys.argv[2]);seed=json.loads((root/'seed.json').read_text())
runtime=open_runtime(project_root=root/'project',state_root=root/'state',worker_backend='hardened')
service=InstanceArchive(runtime);preview=service.restore_preview(seed['instance']);assert preview['ready'],preview
service.restore(seed['instance'],preview['fingerprint'])
run=runtime.runs.status(seed['run_id']);assert run.execution_profile is None
assert hashlib.sha256(runtime.artifacts.read(run.output_ref)).hexdigest()==seed['output_sha256']
assert runtime.scheduler_bindings.agent_settings(seed['instance'])=={'settings':{},'revision':0,'updated_at':None}
package=service.root/seed['instance']
assert {str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file()}==seed['package_hashes']
value={'old_runtime':seed['old_runtime'],'candidate_runtime':scidiscovery.__file__,'restored':True,'historical_profile':None,
       'old_result_bytes_unchanged':True,'archive_bytes_unchanged':True,'instance_overrides_restored_as_empty':True}
(evidence/'OLD_INSTALLED_ARCHIVE_RESTORE.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
