"""Delayed collection and historical provenance must preserve exact deliveries."""
import json
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('missing_required', [False, True])
def test_missing_later_case_preserves_completed_generated_files(tmp_path, missing_required):
    from tcad_artifact.remote_runner_py36 import _collect_expected
    raw = tmp_path / 'finished-case.plx'
    raw.write_bytes(b'previous case completed\n')
    if not missing_required:
        (tmp_path / 'later-case.plx').write_bytes(b'last case completed\n')
    records, errors = [], []
    _collect_expected(str(tmp_path), [{'name': 'later_case', 'relative_path': 'later-case.plx',
        'capture': 'workspace_file', 'required': True, 'max_bytes': 1024, 'media_type': 'text/plain'}],
        {'max_output_bytes': 4096, 'transfer_chunk_bytes': 1024}, records, errors,
        archive_entries=(), collect_generated_outputs=True)
    assert 'finished-case.plx' in {item['relative_path'] for item in records}
    assert bool(errors) == missing_required  # Partial bytes never turn failure into success.
