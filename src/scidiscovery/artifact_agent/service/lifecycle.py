"""Serial daemon maintenance independent of Worker or Root polling."""
from __future__ import annotations

import logging
import threading

_LOG = logging.getLogger(__name__)


class LifecycleReconciler:
    def __init__(self, *, runs, bridge, settings):
        self.runs, self.bridge, self.settings = runs, bridge, settings
        self._run_cursor = self._execution_cursor = ""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="scid-lifecycle", daemon=True)

    def tick(self):
        size = self.settings.batch_size
        ids = self.runs.expired_active_ids(after=self._run_cursor, limit=size)
        self._run_cursor = ids[-1] if len(ids) == size else ""
        for run_id in ids:
            if self._stop.is_set():
                return
            try:
                self.runs.reconcile_expired_active(run_ids=(run_id,),
                    reason="Run deadline expired during control lifecycle reconciliation")
            except Exception as error:
                # One archived/busy/broken workspace must not starve other jobs.
                _LOG.warning("Run lifecycle reconciliation deferred (%s)", type(error).__name__)
        executions = self.bridge.executions
        ids = executions.observation_candidates(after=self._execution_cursor, limit=size)
        self._execution_cursor = ids[-1] if len(ids) == size else ""
        for execution_id in ids:
            if self._stop.is_set():
                return
            try:
                owner = self.runs.scheduler_bindings.find_owner(namespace="execution", object_id=execution_id)
                if owner is None:
                    continue
                instance, _ = owner
                if instance.state != "active":
                    continue
                with self.runs.instance_maintenance.guard(instance.instance_id):
                    self.bridge.sync(execution_id=execution_id,
                        diagnostic_scope="instance:" + instance.instance_id)
            except Exception as error:
                _LOG.warning("Execution observation deferred (%s)", type(error).__name__)

    def _loop(self):
        while not self._stop.wait(self.settings.interval_seconds):
            try:
                self.tick()
            except Exception as error:
                _LOG.warning("Lifecycle pass deferred (%s)", type(error).__name__)

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1)
