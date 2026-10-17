from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from tcad_artifact.project_packager import ExecutionPackage, ProjectExpectedOutput
from tcad_artifact.result_analysis import evaluate_tcad_request

_TCAD = json.loads((Path(__file__).parents[1] / 'fixtures/tcad_analysis_package.json').read_text())
_CURVE = runpy.run_path(str(Path(__file__).with_name('test_m2_curve_analysis_boundary.py')))


def analysis_materials(*, mapped=True, state='succeeded', output_names=('A', 'B'), plan=None):
    plan = plan or _CURVE['_plan']()
    value = deepcopy(_TCAD['project'])
    value['expected_outputs'] = [dict(name=name, relative_path=name+'.plx',
        media_type='application/x-synopsys-plx', max_bytes=32*1024*1024,
        **({'experiment_key': 'implementation_check', 'case_key': 'baseline'} if mapped else {}))
        for name in output_names]
    package = ExecutionPackage.model_validate_json(canonical_json({
        'schema_version': 2, 'project': value, 'review': _TCAD['review'],
        'capability': _TCAD['capability'],
    }), strict=True)
    plx = b'"carrier"\n0 1e10\n0.5 1e11\n1 1e12\n'
    csv = b'depth,carrier,original_group\n0,1e10,g1\n0.5,1e11,g2\n1,1e12,g3\n'
    manifest = dict(started_at=None, completed_at='2026-09-09T00:00:00Z', terminal_state=state,
        exit_code=0 if state == 'succeeded' else 1, error='' if state == 'succeeded' else 'fixture failure',
        outputs=[dict(name=name,relative_path=name+'.plx',media_type='application/x-synopsys-plx',
            sha256=hashlib.sha256(plx).hexdigest(),size_bytes=len(plx)) for name in output_names])
    return plan, package, canonical_json(manifest), plx, csv


def raw_request(*, alias='solver_outputs_001'):
    spec = _CURVE['_contract']().comparison_spec.model_dump(mode='json')
    axes = dict(x_axis={'name':'depth','unit':'um','scale':'linear'},
                y_axis={'name':'carrier','unit':'cm^-3','scale':'log10'})
    return dict(comparison_spec=spec, sources=[
        dict(input_alias=alias,format='sprocess_plx',output_name='A',
             experiment_key='implementation_check',case_key='baseline',series_key='candidate',
             role='candidate',dataset_name='carrier',**axes),
        dict(input_alias='reference_material',format='csv',series_key='reference',case_key='baseline',
             role='reference',x_column='depth',y_column='carrier',**axes),
    ])


def test_optional_output_case_keys_are_paired():
    output=dict(name='A',relative_path='A.plx',media_type='application/x-synopsys-plx',max_bytes=4096)
    ProjectExpectedOutput(**output)
    with pytest.raises(ValueError,match='declared together'):
        ProjectExpectedOutput(**output,case_key='baseline')
    ProjectExpectedOutput(**output,experiment_key='implementation_check',case_key='baseline')


@pytest.mark.parametrize('source_index', [0, 1])
def test_tcad_unknown_weighting_mapping_is_a_request_error(source_index):
    _, _, _, plx, csv = analysis_materials()
    request = raw_request()
    request['sources'][source_index]['weight_column'] = 'original_group'
    record = evaluate_tcad_request(record_key='weighted', request=request,
        sources={'solver_outputs_001': plx, 'reference_material': csv})
    assert record.status == 'unavailable'
    assert record.reason_code == 'invalid_arguments'
    assert record.result is None and not record.input_digests


@pytest.mark.parametrize('raw', [b'"carrier"\n' + b'0 1\n' * 66000,
    b'"carrier"\n0 1\x0b0 1', b'"carrier"\n0 1\xe2\x80\xa80 1'],
    ids=['row-limit', 'vertical-tab', 'unicode-line-separator'])
def test_raw_admission_bounds_rows_before_parser_allocation(raw, monkeypatch):
    import tcad_artifact.result_analysis as analysis
    def forbidden(*args, **kwargs):
        pytest.fail('unbounded raw rows reached the parser')
    monkeypatch.setattr(analysis, 'normalize_sprocess_plx', forbidden)
    _, _, _, _, csv = analysis_materials()
    record = evaluate_tcad_request(record_key='bounded', request=raw_request(),
        sources={'solver_outputs_001': raw, 'reference_material': csv})
    assert record.status == ('error' if record.reason_code == 'source_line_limit' else 'unsupported')
    assert record.result is None
    assert record.reason_code in {'source_line_limit', 'source_line_separator_unsupported'}
