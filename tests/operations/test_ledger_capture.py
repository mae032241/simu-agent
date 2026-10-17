"""Host-only stable observation, safe derived views, exact identity and readers."""

import pytest

from scidiscovery.agent_execution_settings import parse_settings
from scidiscovery.artifact_agent.schema.common import canonical_json

FIELDS = {'run_id':'int', 'ok':'bool', 'started_at':'int', 'metric':'str',
    'val_acc':'float', 'val_score':'float', 'wall_seconds':'float'}
PRIVATE_SCRIPT = '/home/' + 'fixture/private/script.py'
PRIVATE_MODEL = '/opt/exp/private/model.bin'


def row(number=1, **updates):
    return {'run_id':number, 'ok':number != 3, 'started_at':1234 + number,
        'metric':'validation', 'val_acc':0.5, 'val_score':-float(number), 'wall_seconds':1.0,
        'script':PRIVATE_SCRIPT, 'model_path':PRIVATE_MODEL, **updates}


def config(path, *, name='evidence', operation='science.evidence.extract.v1', **updates):
    return {'capture':{'allowed_roots':[str(path.parent)], 'tasks':{name:{'operation_id':operation,
        'ledgers':[{'logical_name':'covshift_results', 'path':str(path), 'fields':FIELDS,
            'name_field':'run_id', 'status_field':'ok', 'redacted_fields':['script','model_path'], **updates}]}}}}


@pytest.mark.parametrize('field',['password','api_key','secret','access_token'])
def test_configured_private_export_names_are_rejected_and_cannot_be_aliased(tmp_path,field):
    path = tmp_path/'source.jsonl'
    path.write_bytes(canonical_json({**row(),field:'abcdefghijklmnop'})+b'\n')
    value = config(path,fields={**FIELDS,field:'str'})
    with pytest.raises(ValueError,match='Invalid host ledger declaration'):
        parse_settings(value)
    # fields maps each exact source key to its scalar type; it has no rename or
    # source selector through which a password could become a harmless key.
    value = config(path,fields={**FIELDS,'note':{'source':field,'kind':'str'}})
    with pytest.raises(ValueError): parse_settings(value)
