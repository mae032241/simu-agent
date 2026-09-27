"""Create a genuine pre-settings archive using the unchanged installed version."""
import hashlib,json,sys
from pathlib import Path
import scidiscovery.artifact_agent.runtime as module
assert str(Path(module.__file__).resolve()).startswith('/opt/scidiscovery-m7/site/'),module.__file__
# Existing fixture helpers contain no production runtime; all scidiscovery imports
# above and below resolve to the old installed package in this separate process.
sys.path.insert(0,sys.argv[1])
from tests.operations.test_instance_archive_continuation import _hardened_system
from tests.operations.test_l5_hardened_run_backend import _invoke,_worker,_write_result
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive
root=Path(sys.argv[2]);root.mkdir(exist_ok=True)
catalog,runtime,instance,router=_hardened_system(root)
with runtime.runs._connect() as con:assert 'execution_profile_json' not in {row[1] for row in con.execute('PRAGMA table_info(runs)')}
_invoke(router,'legacy_result');worker=_worker(catalog,runtime)
worker.call_tool('worker_open_assignment',{});_write_result(worker)
assert worker.call_tool('worker_submit_result',{})['state']=='completed'
run_id=worker._run_id;runtime.runs.backend.release_transport(run_id,worker._transport_owner)
run=runtime.runs.status(run_id);original=runtime.artifacts.read(run.output_ref)
service=InstanceArchive(runtime);preview=service.preview(instance.instance_id);assert preview['ready'],preview
service.archive(instance.instance_id,preview['fingerprint'])
package=service.root/instance.instance_id
value={'old_runtime':module.__file__,'instance':instance.instance_id,'run_id':run_id,'output_sha256':hashlib.sha256(original).hexdigest(),
       'package_hashes':{str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file()}}
(root/'seed.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'legacy_archive_created':True,'old_runtime':module.__file__}))
