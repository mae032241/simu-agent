"""Compile actual registrations for this bounded engineering audit; no runtime writes."""
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src'), *(str(ROOT / 'plugins' / name) for name in ('curve_score', 'tcad_artifact', 'curve_figure_evidence'))]
from scidiscovery.builtin_plugin import CORE_PLUGIN
from scidiscovery.general_science_plugin import PLUGIN as GENERAL
from curve_score.plugin import PLUGIN as CURVE
from tcad_artifact.plugin import PLUGIN as TCAD
from curve_figure_evidence.plugin import PLUGIN as FIGURE
from scidiscovery.operations.catalog import compile_catalog
from scidiscovery.operation_contract import operation_output_validation_contract

catalog = compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD, FIGURE))
rows = []
for name in sorted(catalog.operation_ids()):
    compiled = catalog.operation(name)
    spec = compiled.spec
    owners = []
    for key, impl in compiled.implementations.items():
        try:
            source = inspect.getsourcefile(impl)
            if source:
                owners.append({'component': key, 'callable': getattr(impl, '__qualname__', type(impl).__name__),
                               'file': str(Path(source).resolve().relative_to(ROOT)), 'line': inspect.getsourcelines(impl)[1]})
        except (TypeError, ValueError, OSError):
            pass
    rows.append({'operation_id': name, 'executor': spec.executor.kind, 'scope': spec.catalog_scope,
        'inputs': [port.model_dump(mode='json') for port in spec.inputs],
        'outputs': [port.model_dump(mode='json') for port in spec.outputs],
        'input_validation': spec.input_validation.model_dump(mode='json') if spec.input_validation else None,
        'guards': [guard.model_dump(mode='json') for guard in spec.guards],
        'agent_output_contracts': [operation_output_validation_contract(compiled, port) for port in spec.outputs[:1]] if spec.executor.kind == 'agent' else [],
        'component_owners': owners})
output = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('CATALOG_AFTER.json')).resolve()
output.write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'operations': len(rows), 'public_agents': sum(row['executor']=='agent' and row['scope']=='public' for row in rows),
                  'callable_owner_entries': sum(len(row['component_owners']) for row in rows), 'output': str(output.relative_to(ROOT))}))
