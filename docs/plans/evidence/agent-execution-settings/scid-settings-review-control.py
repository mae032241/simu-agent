import sys; sys.path[:0] = ["/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2", "/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/src"]
from pathlib import Path
import tempfile, sqlite3, json, hashlib
from tests.operations.test_instance_archive import archive_system, save_archive
from scidiscovery.agent_execution_settings import EXECUTION_SETTINGS_COLUMNS
from scidiscovery.artifact_agent.service.instance_archive import InstanceArchive

with tempfile.TemporaryDirectory(prefix='scid-settings-review-') as directory:
    runtime, service, instance, _ = archive_system.__wrapped__(Path(directory))
    save_archive(service, instance)
    runtime.scheduler_bindings._initialize()
    runtime.runs._initialize()
    preview = service.restore_preview(instance)
    assert preview['ready'], preview
    def fault(point):
        if point == 'after_restore_copy':
            raise OSError('test: before database switch')
    service._fault = fault
    try:
        service.restore(instance, preview['fingerprint'])
    except OSError as error:
        print('restore fault:', str(error))
    service = InstanceArchive(runtime)
    print('index state:', service.status(instance)['storage_state'])
    print('database instance state:', runtime.scheduler_bindings.get_instance(instance_id=instance).state)
    try:
        result = service.rollback(instance)
        print('rollback:', result['storage_state'])
    except Exception as error:
        print('rollback incorrectly rejected:', type(error).__name__, str(error))
