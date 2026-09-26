"""Reopen only the configured TCAD adapter for bounded development collection."""
from __future__ import annotations

import base64
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

from scidiscovery.plugin_runtime.collection import CollectionContext, run_bounded, watch_parent
from scidiscovery.plugin_runtime.diagnostics import exception_facts
from scidiscovery.operations.runtime_plugins import RuntimePluginContext
from .debug_contract import (
    DEVELOPMENT_ARTIFACT_LIMIT_BYTES,
    CollectedTCADDebugRun,
    CollectedTCADDebugFile,
    TCADSourceDiagnostic,
)


def collect(runtime: RuntimePluginContext, external_run_id: str, *, context: CollectionContext, limits):
    reader, writer = os.pipe()
    try:
        packet = {"plugin_id": runtime.plugin_id, "config_path": str(runtime.config_path),
            "config": runtime.config_bytes.decode(), "state_root": str(runtime.state_root),
            "external_run_id": external_run_id, "budget": context.wire(), "limits": limits, "parent_fd": reader}
        response = run_bounded([sys.executable, "-m", __name__], input=json.dumps(packet).encode(),
            timeout=context.remaining_seconds(), context=context, pass_fds=(reader,),
            max_output_bytes=DEVELOPMENT_ARTIFACT_LIMIT_BYTES, timeout_kind="debug_collection_total")
        if response.returncode:
            error = subprocess.CalledProcessError(response.returncode, "TCAD debug collection",
                output=response.stdout, stderr=response.stderr)
            try:
                error.engineering = json.loads(response.stdout)["engineering"]
            except (ValueError, KeyError):
                pass
            raise error
        value = json.loads(response.stdout)
        value["files"] = tuple(CollectedTCADDebugFile(**{**item,
            "content": base64.b64decode(item["content"], validate=True)}) for item in value["files"])
        if value.get("source_diagnostic") is not None:
            value["source_diagnostic"] = TCADSourceDiagnostic(**value["source_diagnostic"])
        return CollectedTCADDebugRun(**value)
    finally:
        os.close(reader); os.close(writer)


def main():
    packet = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    watch_parent(packet["parent_fd"], stop)
    context = CollectionContext(**packet["budget"], stopped=stop.is_set)
    try:
        context.remaining_seconds()
        from .runtime_plugin import build_runtime
        from .debug_adapter import TCADDevelopmentDebugBridge
        runtime = RuntimePluginContext(plugin_id=packet["plugin_id"], mode="control",
            config_path=Path(packet["config_path"]), config_bytes=packet["config"].encode(),
            state_root=Path(packet["state_root"]))
        adapter = build_runtime(runtime).execution_adapters["tcad"]
        method = getattr(adapter, "collect_with_budget", None)
        descriptors = (method(packet["external_run_id"], context=context) if callable(method)
            else adapter.collect(packet["external_run_id"]))
        result = TCADDevelopmentDebugBridge(adapter)._collected_run(descriptors, context=context, limits=packet["limits"])
        value = asdict(result)
        for item in value["files"]:
            item["content"] = base64.b64encode(item["content"]).decode()
        context.remaining_seconds()
        print(json.dumps(value), flush=True)
        return 0
    except Exception as error:
        # Raw stderr remains with the parent call's private engineering record.
        current = error
        while current is not None:
            raw = getattr(current, "stderr", None)
            if isinstance(raw, bytes) and raw:
                sys.stderr.buffer.write(raw[:8 * 1024 * 1024])
                break
            current = current.__cause__
        print(json.dumps({"engineering": exception_facts(error, layer="tcad_debug_collection", action="collect")}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
