"""Export declarative reachability, without opening a research runtime."""
from pathlib import Path
import sys,json,tomllib
root=Path(__file__).resolve().parents[4]
mode=sys.argv[1]
if mode=='source':
 for path in tomllib.loads((root/'pyproject.toml').read_text())['tool']['pytest']['ini_options']['pythonpath']:
  sys.path.insert(0,str(root/path))
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD
from curve_figure_evidence.plugin import PLUGIN as FIGURE
from scidiscovery.operations.catalog import compile_catalog
import scidiscovery.operations.spec as module
out={'provenance':str(Path(module.__file__).resolve()),'catalogs':{}}
for name,plugins in [('default',(CORE_PLUGIN,GENERAL,CURVE,TCAD)),('figure',(CORE_PLUGIN,GENERAL,CURVE,TCAD,FIGURE))]:
 catalog=compile_catalog(plugins)
 entries=[]
 for opid,op in sorted(catalog._operations.items()):
  entries.append({'operation_id':opid,'digest':op.digest,
   'input_validation':getattr(op.spec,'input_validation',None).model_dump(mode='json') if getattr(op.spec,'input_validation',None) else None,
   'components':{key:value.model_dump(mode='json') for key,value in sorted(op.component_specs.items())},
   'component_ids':op.component_ids,
   'inputs':[p.model_dump(mode='json') for p in op.spec.inputs],
   'outputs':[p.model_dump(mode='json') for p in op.spec.outputs]})
 out['catalogs'][name]=entries
p=Path(__file__).with_name('catalog-'+mode+'.json');p.write_text(json.dumps(out,indent=2))
print(mode,out['provenance'], {k:len(v) for k,v in out['catalogs'].items()})
