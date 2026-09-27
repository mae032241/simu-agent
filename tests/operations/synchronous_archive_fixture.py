"""Archive format tests with explicitly synchronous, in-process fixture writers.

This substitute proves format/transaction behavior only. Production Local writer
quiescence remains fail-closed and is tested through the unmodified service.
"""
from contextlib import contextmanager
from functools import wraps
from unittest.mock import patch

from scidiscovery.artifact_agent.service import instance_archive as archive_module
from scidiscovery.artifact_agent.service.instance_maintenance import InstanceMaintenanceBusy


class SynchronousFixtureArchive(archive_module.InstanceArchive):
    def __init__(self, runtime, *args, **kwargs):
        super().__init__(runtime, *args, **kwargs)


def _synchronous(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        original = archive_module.backend_writer_guards

        @contextmanager
        def fixture_writers(runtime, run_ids, execution_ids):
            if runtime is not self.runtime or not getattr(runtime.runs, "_synchronous_archive_fixture", False):
                with original(runtime, run_ids, execution_ids) as proof:
                    yield proof
                return
            # Every write in this fixture is synchronous Python in this process;
            # its tests never spawn a native Worker. Still reject any live Run or
            # mismatched historical identity and retain the real execution locks.
            for run_id in run_ids:
                value = runtime.runs.status(run_id)
                backend = runtime.runs.backend
                reason = ("run_nonterminal" if value.state not in {"completed", "failed"}
                          else "backend_identity_unavailable" if (
                              value.backend_id != backend.backend_id
                              or value.backend_version != backend.backend_version
                              or value.backend_capabilities != backend.capabilities) else None)
                if reason:
                    raise InstanceMaintenanceBusy(details=[{"kind": "run", "id": run_id, "reason": reason}])
                for path in backend.exact_workspace_paths(run_id):
                    assert not (path / 'scratch/.analysis-process').exists()
            with original(runtime, (), execution_ids) as proof:
                yield proof

        with patch.object(archive_module, 'backend_writer_guards', fixture_writers):
            return method(self, *args, **kwargs)
    return call


for _name in ('preview', 'archive', 'restore_preview', 'restore', 'resume'):
    setattr(SynchronousFixtureArchive, _name, _synchronous(getattr(archive_module.InstanceArchive, _name)))
