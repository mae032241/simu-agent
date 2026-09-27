"""Browser orchestration for storage maintenance; no scientific task authority."""
from __future__ import annotations

import hashlib
import json
import logging
import threading

LOGGER = logging.getLogger(__name__)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), default=str).encode()).hexdigest()


class WorkbenchManagement:
    """One in-flight maintenance action; durable archive progress lives in its service."""
    def __init__(self, archive, store, *, observer=None):
        self.archive, self.store, self.observer = archive, store, observer
        self._lock = threading.Lock()
        self._thread = None
        self._target = None
        self._errors = {}
        self._cleanup_results = {}

    def status(self, instance_id):
        status = dict(self.archive.status(instance_id))
        status["fingerprint"] = fingerprint(status)
        with self._lock:
            status["action_running"] = self._target == instance_id
            status["error"] = self._errors.get(instance_id) or status.get("error")
            status["cleanup_result"] = self._cleanup_results.get(instance_id)
        return status

    def preview(self, instance_id, action):
        if action == "archive":
            return self.archive.preview(instance_id)
        if action == "restore":
            return self.archive.restore_preview(instance_id)
        if action != "cleanup" or self.store is None:
            raise ValueError("unknown maintenance preview")
        value = self.store.cleanup_preview(instance_id)
        state = self.archive.status(instance_id)
        busy = []
        if state.get("storage_state") not in {"active", "restored"}:
            busy.append("实例正处于维护或归档状态；归档资料不属于缓存清理范围。")
        if self.observer is not None and self.observer.is_subscribed(instance_id):
            busy.append("实例仍有轨迹订阅，请关闭其轨迹页面后重试。")
        value.update(ready=not busy, busy=busy)
        return value

    def start(self, instance_id, action, expected):
        if action not in {"archive", "restore", "resume", "rollback", "cleanup"}:
            raise ValueError("unknown maintenance action")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ValueError("已有维护操作正在运行，请稍后刷新。")
            self._target = instance_id
            self._errors.pop(instance_id, None)
            self._thread = threading.Thread(target=self._execute,
                args=(instance_id, action, expected), name="instance-maintenance-ui", daemon=True)
            self._thread.start()

    def _execute(self, instance_id, action, expected):
        try:
            if action in {"archive", "restore"}:
                getattr(self.archive, action)(instance_id, expected)
            elif action == "cleanup":
                # Recheck fingerprint and occupancy in the same short exclusive boundary.
                with self.archive.gate.exclusive(instance_id):
                    self.archive.gate.ensure_available(instance_id)
                    value = self.preview(instance_id, action)
                    if not value["ready"]:
                        raise ValueError("；".join(value["busy"]))
                    result = self.store.cleanup(instance_id, expected)
                with self._lock:
                    self._cleanup_results[instance_id] = result
            else:
                # Archive service rechecks its own durable phase inside the operation.
                if fingerprint(self.archive.status(instance_id)) != expected:
                    raise ValueError("维护进度已变化，请刷新后重新确认。")
                getattr(self.archive, action)(instance_id)
        except Exception as error:
            LOGGER.exception("instance maintenance action %s failed", action)
            with self._lock:
                self._errors[instance_id] = {"action": action, "type": type(error).__name__, "message": str(error)[:4096]}
        finally:
            with self._lock:
                self._target = None

    def close(self):
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)
