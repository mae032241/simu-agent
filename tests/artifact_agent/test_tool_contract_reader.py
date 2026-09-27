import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scidiscovery.artifact_agent.service.local_workspace import LocalTrustedBackend
from scidiscovery.artifact_agent.service.tool_contract_reader import ContractReader, changes, digest, read_contract, load_receipt, save_receipt


def apply_patch(base, patch):
    value = copy.deepcopy(base)
    for item in patch:
        if item["path"] == "":
            value = item["value"]
            continue
        keys = [k.replace("~1", "/").replace("~0", "~") for k in item["path"][1:].split("/")]
        parent = value
        for key in keys[:-1]:
            parent = parent[key]
        if item["op"] == "remove":
            del parent[keys[-1]]
        else:
            parent[keys[-1]] = copy.deepcopy(item["value"])
    return value


@pytest.mark.parametrize("target", [
    {"a/b": {"~key": [1, 2]}, "removed": None},
    {"a/b": {"~key": False}, "added": {"enum": ["x", "y"]}},
    {"a/b": {"~key": 1}},
    {"a/b": {"~key": 1.0}},
])
def test_exact_roundtrip_including_escaped_pointers_and_json_types(target):
    base = {"a/b": {"~key": True}, "removed": "old"}
    restored = apply_patch(base, changes(base, target))
    assert digest(restored) == digest(target)


def test_stale_missing_base_and_expensive_patch_return_full_contract():
    contracts = {"a": {"title": "old"}, "b": {"title": "new"}}
    for options in ({}, {"known_tool": "a", "known_digest": "stale"},
                    {"known_tool": "missing", "known_digest": digest(contracts["a"])},
                    {"known_tool": "a", "known_digest": digest(contracts["a"])}):
        answer = read_contract(contracts, "b", **options)
        assert answer["format"] == "full"
        assert answer["contract"] == contracts["b"]
    with pytest.raises(KeyError):
        read_contract(contracts, "unauthorized")


def test_materialized_reader_is_standalone_read_only_and_workspace_scoped(tmp_path):
    contracts = {"score": {"inputSchema": {"description": "shared " * 1000, "required": ["x"]}}}
    contracts["diagnose"] = copy.deepcopy(contracts["score"])
    contracts["diagnose"]["inputSchema"]["required"] = ["x", "y"]
    assignment = json.dumps({"tool_contracts": contracts}).encode()
    backend = LocalTrustedBackend(tmp_path / "backend")
    workspace = backend.prepare(run_id="run_reader", inputs=(), assignment=assignment, result_schema=b"{}")
    script = workspace.root / "tools/read_tool_contract.py"
    assert script.is_file() and script.stat().st_mode & 0o222 == 0
    command = [sys.executable, "-I", str(script)]
    first = json.loads(subprocess.check_output(command + ["score"], timeout=10))
    assert first["format"] == "full"
    command += ["diagnose"]
    reply = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=10, check=True)
    answer = json.loads(reply.stdout)
    assert answer["format"] == "json_patch"
    assert apply_patch(contracts["score"], answer["patch"]) == contracts["diagnose"]
    refreshed = json.loads(subprocess.check_output(command + ["--full"], timeout=10))
    assert refreshed["contract"] == contracts["diagnose"]
    receipt = workspace.root / "scratch/.tool-contract-reading.json"
    receipt.write_text("corrupt")
    assert json.loads(subprocess.check_output(command, timeout=10))["format"] == "full"
    assert workspace.assignment_path.read_bytes() == assignment
    failed = subprocess.run([sys.executable, "-I", str(script), "../../outside"],
                            capture_output=True, text=True, timeout=10)
    assert failed.returncode == 1 and not failed.stdout
    assert "Cannot read assigned tool contract" in failed.stderr


def test_automatic_reuse_has_no_delta_chains_and_full_refresh_changes_base():
    contracts = {name: {"shared": "same " * 1000, "name": name}
                 for name in ("score", "diagnose", "third")}
    reader = ContractReader(contracts)
    assert reader.read("score")["format"] == "full"
    for name in ("diagnose", "third"):
        answer = reader.read(name)
        assert answer["base"]["name"] == "score"
        assert apply_patch(contracts["score"], answer["patch"]) == contracts[name]
    assert reader.read("diagnose", full=True)["format"] == "full"
    assert reader.read("third")["base"]["name"] == "diagnose"


def test_receipt_is_disposable_scoped_and_invalidated_by_contract_changes(tmp_path):
    contracts = {name: {"shared": "same " * 1000, "name": name}
                 for name in ("score", "diagnose")}
    first = ContractReader(contracts, scope="workspace1")
    first.read("score")
    path = tmp_path / "scratch/receipt.json"
    save_receipt(path, first.receipt)
    receipt = load_receipt(path)
    assert ContractReader(contracts, receipt, scope="workspace1").read("diagnose")["format"] == "json_patch"
    assert ContractReader(contracts, receipt, scope="workspace2").read("diagnose")["format"] == "full"
    changed = copy.deepcopy(contracts)
    changed["score"]["shared"] += "changed"
    assert ContractReader(changed, receipt, scope="workspace1").read("diagnose")["format"] == "full"
    for bad in (None, [], {**receipt, "base_name": []}, {**receipt, "base_digest": "stale"}):
        assert ContractReader(contracts, bad, scope="workspace1").read("diagnose")["format"] == "full"
    path.write_text("invalid")
    assert load_receipt(path) is None
    # An unwritable receipt location cannot prevent reading a complete contract.
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("file")
    save_receipt(blocked / "receipt.json", first.receipt)
    assert load_receipt(blocked / "receipt.json") is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_tool_reader_rejects_nonfinite_contract_json(value):
    with pytest.raises(ValueError, match="Out of range float"):
        read_contract({"tool": {"inputSchema": {"default": value}}}, "tool")


def test_finite_unicode_reading_identity_preserves_existing_bytes():
    import hashlib
    expected = '{"default":1.5,"title":"温度"}'.encode("utf-8")
    result = read_contract({"tool": {"default": 1.5, "title": "温度"}}, "tool")
    assert result["sha256"] == hashlib.sha256(expected).hexdigest()
