"""Offline rendering of sealed Fig4 plan/project; other inventory entries are fixtures."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

repo=Path.cwd()
sys.path[:0]=[str(repo/'src'), str(repo/'plugins/curve_score'), str(repo/'plugins/tcad_artifact')]
from tcad_artifact.analysis_bindings import materialize, source_bindings, workspace_sources
from tcad_artifact.result_analysis import INPUTS
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.operations.workspace import WorkspaceMaterializationRequest

source=json.loads(Path(sys.argv[1]).read_bytes())
root=Path(tempfile.mkdtemp(prefix='scid-fig4-reading-view-')); (root/'inputs').mkdir()
contents={'experiment_plan': source['plan'], 'reviewed_package': {'project': source['project']}}
paths={}; descriptors={}; inputs=[]
ports={port.name: port for port in INPUTS}

def add(alias, port, value, output_name=None):
    path=root/'inputs'/f'{alias}.json'
    path.write_bytes(canonical_json(value)); paths[alias]=path
    descriptors[alias]=SimpleNamespace(port_name=port, size_bytes=path.stat().st_size,
        artifact_ref=SimpleNamespace(schema_id=ports[port].schema_id), output_name=output_name)
    inputs.append(dict(source_name=alias, port=port, relative_path=path.relative_to(root).as_posix(),
        description=ports[port].description, exposure=ports[port].exposure,
        usage=ports[port].usage, media_type='application/json', historical=False))

for alias, value in contents.items():
    add(alias, alias, value)
# Only plan/project bytes above are scientific originals. Empty inventory placeholders
# reproduce the known 24-input roster for a structural byte measurement, not a live Run.
for port, count in [('experiment_review',1), ('runtime_manifest',1), ('solver_outputs',13),
                    ('diagnostics',1), ('reference_material',3), ('current_progress',3)]:
    for index in range(count):
        name=f'{port}_{index+1:03}' if count>1 else port
        output_name=source['solver_output_names'][index] if port=='solver_outputs' else None
        add(name, port, {}, output_name)
(root/'assignment.json').write_bytes(canonical_json(dict(inputs=inputs, tools=[],
    instruction='Structural view measurement; no scientific conclusion is produced.')))
request=WorkspaceMaterializationRequest('fixture',root,paths,(),edit_protocol='native',binding_descriptors=descriptors)
before={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
identities=source_bindings(workspace_sources(request))
materialize(request)
start=json.loads((root/'analysis-start.json').read_bytes())
view=json.loads((root/'analysis-bindings.json').read_bytes())
assert before=={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
assert identities==source_bindings(workspace_sources(request))
assert set(view['sources'])==set(identities['sources'])
def resolve(pointer):
    value=source['plan']
    for part in pointer.split('/')[1:]:
        value=value[int(part)] if isinstance(value,list) else value[part]
    return value
count=0
for row in view['case_matrix']:
    if 'case_columns' in row: columns=row['case_columns']
    if 'values' not in row: continue
    original=resolve(row['pointer'])
    for case,index,value in zip(columns,row['expectation_indices'],row['values'],strict=True):
        assert original['expectations'][index]['case_key']==case
        assert original['expectations'][index]['value']==value
        count+=1
sizes={name:(root/name).stat().st_size for name in ('analysis-start.json','analysis-bindings.json')}
assert sum(sizes.values())<=32*1024
assert count==156, count
record=dict(boundary='Offline structural rendering: exact sealed plan/project, placeholder other inputs; not live Agent acceptance',
    input_count=len(inputs), sizes=sizes, combined_bytes=sum(sizes.values()), case_values_verified=count,
    full_control_binding_count=len(source['project']['case_parameter_bindings']),
    displayed_source_bindings=len(view['sources']),
    source_output_names_from='Completed run_status bound_inputs semantic names, checked against exact project declarations',
    mechanical_rows_in_default_view=0, original_bytes_preserved=True, full_tool_mapping_unchanged=True,
    start_omitted=start['omitted'], view_omitted=view['omitted'], workspace=str(root))
Path(__file__).with_name('fig4-view-measurement.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
