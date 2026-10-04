"""Public-view and inert artifact handoff boundaries; no training or unpickling."""
import hashlib
import json

import pytest

from scripts import prepare_covshift_local as local


def prepared(tmp_path, monkeypatch):
    original = tmp_path / 'original'; original.mkdir()
    for name in local.PUBLIC:
        path = original / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'public fixture\n')
    meta = original / 'environment/harness/meta.json'
    meta.write_text(json.dumps(dict(public='keep', **{k:'sensitive fixture' for k in local.PRIVATE_META_KEYS})))
    (meta.parent / 'gen_dataset.py').write_text('must not export')
    # Real git provenance is covered by the actual public prepare evidence.
    monkeypatch.setattr(local.subprocess, 'check_output', lambda *a, **k:local.REVISION + '\n')
    monkeypatch.setattr(local.subprocess, 'run', lambda *a, **k:None)
    root = tmp_path / 'prepared'; manifest = local.prepare(root, original)
    return root, manifest


def test_preparation_reproduces_public_meta_view_without_generator(tmp_path, monkeypatch):
    root, manifest = prepared(tmp_path, monkeypatch)
    exported = root / 'public/environment/harness/meta.json'
    assert json.loads(exported.read_text()) == {'public':'keep'}
    assert not (exported.parent / 'gen_dataset.py').exists()
    assert set(manifest['public_files_sha256']) == set(local.PUBLIC)
    assert manifest['original_public_files_sha256']['environment/harness/meta.json'] != manifest['public_files_sha256']['environment/harness/meta.json']
    assert not manifest['launch_ready']
    local.verify_public(root, manifest)


@pytest.mark.parametrize('change', ['added_generator', 'changed_data', 'symlink', 'private_meta'])
def test_changed_public_view_rejected_before_namespace(tmp_path, monkeypatch, change):
    root, manifest = prepared(tmp_path, monkeypatch)
    harness = root / 'public/environment/harness'
    if change == 'added_generator': (harness / 'gen_dataset.py').write_text('extra')
    elif change == 'changed_data': (harness / 'train.csv').write_text('changed')
    elif change == 'symlink':
        path = harness / 'train.csv'; path.unlink(); path.symlink_to(root / 'host-private/canary.txt')
    else:
        path = harness / 'meta.json'; path.write_text(json.dumps({'noise_sigma':'must not export'}))
        manifest['public_files_sha256']['environment/harness/meta.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises((ValueError, OSError)): local.verify_public(root, manifest)


def test_handoff_has_no_inherited_nbody_two_mb_model_limit_or_unpickle(tmp_path, monkeypatch):
    root, _ = prepared(tmp_path, monkeypatch)
    (root / 'output/submitted.json').write_text('{"run_id":1}')
    # Deliberately not a pickle: trusted host must transfer bytes without loading it.
    raw = b'not a pickle' * 200_000
    assert len(raw) > 2_000_000
    (root / 'output/submitted_model.pkl').write_bytes(raw)
    result = local.handoff(root)
    assert result['submitted_model.pkl']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert (root / 'submission/submitted_model.pkl').read_bytes() == raw
    assert not json.loads((root / 'handoff.json').read_text())['trusted_host_unpickled']


def test_nonregular_model_rejected_before_either_handoff_file(tmp_path, monkeypatch):
    root, _ = prepared(tmp_path, monkeypatch)
    (root / 'output/submitted.json').write_text('{}')
    (root / 'output/submitted_model.pkl').symlink_to(root / 'host-private/canary.txt')
    with pytest.raises(OSError): local.handoff(root)
    assert not list((root / 'submission').iterdir())
