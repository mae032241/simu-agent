"""Frozen pre-migration figure identities; strict JSON remains core-owned."""
import hashlib

import pytest

from curve_figure_evidence.figure_evidence_validation import canonical_json


# Bytes and hashes captured from the removed figure encoder, not recomputed
# with another serializer. Production input_records use string keys and str/int.
VECTORS = [({'z': [None, True, False, 0, -4, 1.5, -0.0, 1e-07, 1e+20], 'a': '曲線 µ 😀\n'},
  '{"a":"曲線 µ 😀\\n","z":[null,true,false,0,-4,1.5,-0.0,1e-07,1e+20]}',
  '56caf2ad1b0efe83a903d3f575e483efe32e2f39aa9065f543e8b378802e9596'),
 ([{'data_item': '图/曲线.csv',
    'bytes': 17,
    'sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'media_type': 'text/csv'},
   {'data_item': 'manifest.json',
    'bytes': 9007199254740993,
    'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'media_type': 'application/json'}],
  '[{"bytes":17,"data_item":"图/曲线.csv","media_type":"text/csv","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},{"bytes":9007199254740993,"data_item":"manifest.json","media_type":"application/json","sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}]',
  '38264a0311ba9d79073640bc3f4a2c717c4afac25d767f5ef4cd530383d9b107'),
 ({'outer': {'β': 2, 'a': 1}, 'empty': []},
  '{"empty":[],"outer":{"a":1,"β":2}}',
  '6d87bc24ecb4d4c8f534e1736833a50c6a5a4dcc269590b3502aec18b45176e1'),
 ({}, '{}', '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a')]


@pytest.mark.parametrize("value,expected,digest", VECTORS)
def test_figure_identity_bytes_are_unchanged(value, expected, digest):
    encoded = canonical_json(value)
    assert encoded == expected.encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == digest
    if isinstance(value, dict):
        assert canonical_json(dict(reversed(tuple(value.items())))) == encoded


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), {"nested": float("nan")}, {"bytes": b"x"}, {"set": {1, 2}}])
def test_figure_encoder_still_rejects_non_json_values(value):
    with pytest.raises((ValueError, TypeError)):
        canonical_json(value)


def test_shared_encoder_rejects_non_string_keys():
    # Raw Python non-string keys are outside the supported JSON input domain.
    with pytest.raises(TypeError, match="keys to be strings"):
        canonical_json({1: "unsupported"})
