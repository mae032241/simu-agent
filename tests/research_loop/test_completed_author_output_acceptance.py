"""Pure retained completed-output implementation identity checks."""
from pathlib import Path

import pytest

from scidiscovery.research_loop import author_closeout as author,contracts as c
from test_author_closeout_successor import pure_upgrade


def retain_successor(root,step,directory):
    directory.mkdir();path=author.successor_path(root,step);value=c.read(path);files=[]
    for number,item in enumerate(value['implementation']):
        source=Path(item['path']);target=directory/f'{number:02d}-{source.name}'
        target.write_bytes(source.read_bytes());target.chmod(0o400)
        files.append(dict(original_path=item['path'],sha256=item['sha256'],retained=str(target),size_bytes=target.stat().st_size))
    manifest=directory/'manifest.json'
    c.write(manifest,dict(successor_receipt=dict(path=str(path),sha256=c.digest(path)),files=files))
    manifest.chmod(0o400)
    return manifest








@pytest.mark.parametrize('tamper',['manifest','retained','current','other_successor','missing_file'])
def test_completed_output_code_upgrade_requires_both_exact_implementation_generations(pure_upgrade,tmp_path,tamper):
    root,old,successor,code,_=pure_upgrade
    path=author.successor_path(root,1);c.write(path,successor)
    manifest=retain_successor(root,1,tmp_path/'retained-successor')
    saved=c.read(manifest)
    code.write_text('new completed-output implementation')
    value=dict(version=1,scope='completed_author_output_code_upgrade',step=1,attempt=2,
        successor=author._ref(root,path),retained_manifest=author._host_ref(manifest),
        retained_files=[author._host_ref(item['retained']) for item in saved['files']],
        implementation=author._implementation_refs(c.settings(root)),authorization_note='One output acceptance.',authorization_statement='Accept only the returned bytes.')
    assert author._validate_output_upgrade(root,value)==value
    if tamper=='manifest':manifest.chmod(0o600);c.write(manifest,dict(files=[]))
    elif tamper=='retained':
        target=Path(saved['files'][0]['retained']);target.chmod(0o600);target.write_text('not old bytes')
    elif tamper=='current':code.write_text('unapproved current bytes')
    elif tamper=='other_successor':c.write(path,dict(successor,step=2))
    else:value['retained_files']=value['retained_files'][:-1]
    with pytest.raises(ValueError):author._validate_output_upgrade(root,value)
