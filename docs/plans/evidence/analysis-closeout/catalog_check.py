"""Compile the configured production plugins without starting any research work."""
import json
from pathlib import Path
import sys

base = Path(__file__).resolve().parent
repo = base.parents[3]
for path in (repo / 'src', repo / 'plugins/curve_score', repo / 'plugins/tcad_artifact', repo / 'plugins/curve_figure_evidence'):
    sys.path.insert(0, str(path))
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operations.workspace import operation_workspace_hooks
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD
from curve_figure_evidence.plugin import PLUGIN as FIGURE
from tcad_artifact import analysis_bindings
from curve_score import analysis_workspace

catalog = compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD, FIGURE))
tcad = operation_workspace_hooks(catalog.operation('tcad.result.analyze.v1'))
generic = operation_workspace_hooks(catalog.operation('science.result.diagnose.v1'))
assert tcad['workspace_materializer'] is analysis_bindings.materialize
assert tcad['workspace_finalizer'] is analysis_bindings.finalize
assert tcad['workspace_snapshotter'] is generic['workspace_snapshotter'] is analysis_workspace.snapshot
result = {'operations': len(catalog.operation_ids()), 'tcad_shared_binding_hooks': True, 'shared_snapshot': True}
(base / 'catalog-check.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
