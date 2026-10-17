"""No solver: exact persisted diagnostic ownership through real archive IO."""
import fcntl
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json, canonical_sha256
from scidiscovery.operations.runtime_plugins import ArchiveStorage, ArchiveStorageSelection


@dataclass
class DiagnosticContext:
    run_id: str
    operation_id: str
    workspace: Path
    output_directory: Path
    service: object

    def require_service(self, name):
        assert name == 'tcad.development_debug'
        return self.service


def configure(runtime, service, tmp_path):
    path = tmp_path / 'tcad.json'
    # Archive ownership discovery must not connect this deliberately absent socket.
    path.write_text(json.dumps(dict(transport='socket', socket_path=str(tmp_path / 'never-connect.sock'))))
    service.plugin_configs = {'tcad_artifact': path}
    return runtime.state_root / 'local-tcad-debug'


def bytes_under(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def test_collected_real_debug_service_records_fit_the_readonly_inventory(tmp_path, monkeypatch):
    from dataclasses import replace
    from tests.operations.test_debug_task_identity import fixture
    from tcad_artifact import debug_archive
    instance = 'ins_fixture'
    subject = canonical_sha256({'instance': instance})
    debugger, adapter, context, _ = fixture(tmp_path, monkeypatch)
    prepare = adapter.prepare
    def exact_submission(**kwargs):
        prepared = prepare(**kwargs)
        source = Path(prepared.submission.local_path)
        return replace(prepared, submission=prepared.submission.model_copy(update={
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}))
    monkeypatch.setattr(adapter, 'prepare', exact_submission)
    root = debugger.exchange_root
    current = context('first')
    debugger.run(current, run_name='probe', mode='preflight', budget_subject=subject)
    adapter.states['1'] = 'succeeded'
    debugger.run(current, run_name='probe', mode='preflight', budget_subject=subject)
    before = bytes_under(root)
    selected = debug_archive.inspect(root, instance, ('first',), lambda _: instance)
    assert not selected.unsupported, selected
    assert len(selected.paths) == 4
    assert bytes_under(root) == before
