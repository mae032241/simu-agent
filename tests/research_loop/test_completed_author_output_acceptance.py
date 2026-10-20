"""Exact completed-output authorization independent of installed tool source."""
import pytest

from scidiscovery.research_loop import author_closeout as author,contracts as c
from test_author_closeout_successor import pure_upgrade


def test_completed_output_authorization_allows_tool_upgrade_but_binds_successor(pure_upgrade):
    root,old,successor,code,_=pure_upgrade
    path=author.successor_path(root,1);c.write(path,successor)
    value=dict(version=1,scope='completed_author_output_code_upgrade',step=1,attempt=2,
        successor=author._ref(root,path),authorization_note='One output acceptance.',
        authorization_statement='Accept only the returned bytes.')
    assert author._validate_output_upgrade(root,value)==value
    code.write_text('upgraded completed-output runtime')
    assert author._validate_output_upgrade(root,value)==value
    c.write(path,dict(successor,step=2))
    with pytest.raises(ValueError):author._validate_output_upgrade(root,value)
