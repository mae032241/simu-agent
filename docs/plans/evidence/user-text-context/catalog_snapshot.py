import sys,json
from pathlib import Path
r=Path.cwd();sys.path[:0]=[str(r/p) for p in ('src','.','plugins/tcad_artifact','plugins/curve_score','plugins/curve_figure_evidence')]
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from tcad_artifact.plugin import PLUGIN as TCAD
from curve_score.plugin import PLUGIN as CURVE
from curve_figure_evidence.plugin import PLUGIN as FIGURE
c=compile_catalog((CORE_PLUGIN,GENERAL,TCAD,CURVE,FIGURE))
rows=[dict(digest=o.digest,spec=o.spec.model_dump(mode="json")) for o in (c.operation(name) for name in c.operation_ids())]
Path(sys.argv[1]).write_text(json.dumps(rows,indent=2));print(f"{len(rows)} declarations saved")
