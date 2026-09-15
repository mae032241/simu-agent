"""Compare exact source-checkout action/tool contracts before and after UI work."""
from __future__ import annotations

import hashlib
from importlib.metadata import EntryPoint, EntryPoints
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
for relative in ("src", "plugins/tcad_artifact", "plugins/curve_score", "plugins/curve_figure_evidence", "."):
    sys.path.insert(0, str(ROOT / relative))

from tests.conftest import _SOURCE_FULL_PLUGINS
from scidiscovery.operations import catalog
from scidiscovery.operations.tooling import operation_tool_contracts, operation_worker_tool_names
from scidiscovery.artifact_agent.interfaces.mcp_root import root_tools_for_backend


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


selected = _SOURCE_FULL_PLUGINS
if "--figure" in sys.argv[2:]:
    selected = EntryPoints((*selected, EntryPoint(name="curve_figure_evidence",
        value="curve_figure_evidence.plugin:PLUGIN", group="scidiscovery.plugins")))
catalog.entry_points = lambda: selected
catalog.compile_installed_catalog.cache_clear()
compiled = catalog.compile_installed_catalog()
result = {"catalog_digest": compiled.digest(), "operations": {}, "root_tools": {}}
for name in sorted(compiled.operation_ids()):
    op = compiled.operation(name)
    item = {"digest": op.digest, "spec_digest": digest(op.spec.model_dump(mode="json"))}
    if op.spec.executor.kind == "agent":
        item["worker_tools"] = {key: digest(value) for key, value in
            operation_tool_contracts(op, operation_worker_tool_names(op)).items()}
    result["operations"][name] = item
for backend in ("local", "hardened"):
    result["root_tools"][backend] = {tool.name: digest(tool.schema())
        for tool in root_tools_for_backend(backend)}
target = Path(sys.argv[1])
target.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
print(json.dumps({"output": str(target), "operations": len(result["operations"]),
    "catalog_digest": result["catalog_digest"]}))
