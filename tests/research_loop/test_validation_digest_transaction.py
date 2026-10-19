"""Explicit synchronous validation can reuse unchanged SHA reads, never verdicts."""
import hashlib
import os

import pytest

from scidiscovery.research_loop import contracts as c


def counter(monkeypatch):
    original=c._stream_digest;calls=[]
    def counted(path):
        calls.append(path);return original(path)
    monkeypatch.setattr(c,'_stream_digest',counted)
    return calls


def test_digest_transaction_is_opt_in_nested_and_call_scoped(tmp_path,monkeypatch):
    path=tmp_path/'original';path.write_bytes(b'first');calls=counter(monkeypatch)
    expected=c.digest(path);assert c.digest(path)==expected and len(calls)==2
    with c.verified_digests():
        assert c.digest(path)==expected
        with c.verified_digests():assert c.digest(path)==expected
        assert c.digest(path)==expected and len(calls)==3
    assert c.digest(path)==expected and len(calls)==4
    with c.verified_digests():assert c.digest(path)==expected
    assert len(calls)==5


def test_digest_transaction_clears_on_exception(tmp_path,monkeypatch):
    path=tmp_path/'original';path.write_text('original');calls=counter(monkeypatch)
    with pytest.raises(RuntimeError):
        with c.verified_digests():
            c.digest(path);raise RuntimeError('Interrupted verifier')
    c.digest(path);c.digest(path)
    assert len(calls)==3


@pytest.mark.parametrize('mutation',['same_size_restore_mtime','atomic_replace','symlink_rebind'])
def test_digest_transaction_rehashes_changed_original(tmp_path,monkeypatch,mutation):
    path=tmp_path/'original';path.write_bytes(b'first')
    if mutation=='symlink_rebind':
        target=tmp_path/'target';path.rename(target);path.symlink_to(target)
    calls=counter(monkeypatch)
    with c.verified_digests():
        old=c.digest(path);before=path.stat()
        if mutation=='same_size_restore_mtime':
            path.write_bytes(b'other');os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        elif mutation=='atomic_replace':
            replacement=tmp_path/'replacement';replacement.write_bytes(b'other')
            os.utime(replacement,ns=(before.st_atime_ns,before.st_mtime_ns));replacement.replace(path)
        else:
            target=tmp_path/'other-target';target.write_bytes(b'other');path.unlink();path.symlink_to(target)
        assert c.digest(path)!=old
        assert c.digest(path)==hashlib.sha256(b'other').hexdigest()
        assert len(calls)==2


def test_digest_transaction_rejects_mutation_during_hash(tmp_path,monkeypatch):
    path=tmp_path/'original';path.write_bytes(b'first');original=c._stream_digest
    def changing(path):
        value=original(path);path.write_bytes(b'other');return value
    monkeypatch.setattr(c,'_stream_digest',changing)
    with c.verified_digests():
        with pytest.raises(ValueError,match='changed during digest validation'):c.digest(path)
        assert not c._digest_transaction.get()


def test_digest_transaction_memory_is_bounded(tmp_path):
    with c.verified_digests():
        for number in range(4100):
            path=tmp_path/str(number);path.write_bytes(b'fixture');c.digest(path)
        assert len(c._digest_transaction.get())==4096
    assert c._digest_transaction.get() is None
