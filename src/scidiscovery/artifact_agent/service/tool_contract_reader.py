"""Read this workspace's exact tool contracts, reusing the last full response.

Only a small disposable reading receipt is saved in scratch; contract bytes remain
in the immutable assignment. A delta references the most recent full response,
never another delta. Use --full if that response is no longer in your context.
No network, framework imports, scientific state or permission changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def changes(before, after, path=""):
    if canonical(before) == canonical(after):
        return []
    if not isinstance(before, dict) or not isinstance(after, dict):
        return [{"op": "replace", "path": path, "value": after}]
    patch = []
    for key in sorted(before.keys() | after.keys()):
        pointer = path + "/" + key.replace("~", "~0").replace("/", "~1")
        if key not in after:
            patch.append({"op": "remove", "path": pointer})
        elif key not in before:
            patch.append({"op": "add", "path": pointer, "value": after[key]})
        else:
            patch.extend(changes(before[key], after[key], pointer))
    return patch


def read_contract(contracts, name, *, known_tool=None, known_digest=None):
    target = contracts[name]
    full = {"format": "full", "name": name, "sha256": digest(target), "contract": target}
    base = contracts.get(known_tool)
    if base is None or known_digest != digest(base):
        return full
    delta = {"format": "json_patch", "name": name, "sha256": full["sha256"],
             "base": {"name": known_tool, "sha256": known_digest},
             "patch": changes(base, target)}
    return delta if len(canonical(delta)) < len(canonical(full)) else full


class ContractReader:
    """Own mechanical reuse metadata; callers choose only a tool and full/delta view."""

    def __init__(self, contracts, receipt=None, *, scope=""):
        self.contracts = contracts
        self.receipt = dict(receipt) if isinstance(receipt, dict) else {}
        self.fingerprint = digest({"scope": scope, "contracts": contracts})

    def read(self, name, *, full=False):
        current = (not full and self.receipt.get("fingerprint") == self.fingerprint
                   and isinstance(self.receipt.get("base_name"), str)
                   and isinstance(self.receipt.get("base_digest"), str))
        result = read_contract(self.contracts, name,
            known_tool=self.receipt.get("base_name") if current else None,
            known_digest=self.receipt.get("base_digest") if current else None)
        if result["format"] == "full":
            self.receipt = {"fingerprint": self.fingerprint,
                            "base_name": name, "base_digest": result["sha256"]}
        return result


def load_receipt(path):
    try:
        if path.is_symlink():
            return None
        with path.open() as stream:
            return json.loads(stream.read(4096))
    except (OSError, ValueError):
        return None


def save_receipt(path, receipt):
    temporary = None
    try:
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(canonical(receipt))
        os.replace(temporary, path)
    except OSError:
        # Failure of this disposable optimization must not reject the task.
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Tool name in this assignment's tool_contracts")
    parser.add_argument("--full", action="store_true", help="Read the complete contract after context loss or when needed")
    args = parser.parse_args()
    # Installed under workspace/tools; no caller-supplied file or network path.
    assignment = Path(__file__).resolve().parents[1] / "assignment.json"
    try:
        raw = assignment.read_text()
        contracts = json.loads(raw)["tool_contracts"]
        scratch = assignment.parent / "scratch"
        receipt_path = scratch / ".tool-contract-reading.json"
        # Never follow a scratch symlink outside the assigned workspace.
        cache_enabled = not scratch.is_symlink()
        reader = ContractReader(contracts, load_receipt(receipt_path) if cache_enabled else None,
                                scope=canonical([str(assignment.parent), digest(raw)]))
        result = reader.read(args.name, full=args.full)
    except (OSError, KeyError, ValueError) as error:
        parser.exit(1, f"Cannot read assigned tool contract: {error}\n")
    print(canonical(result), flush=True)
    if cache_enabled:
        save_receipt(receipt_path, reader.receipt)


if __name__ == "__main__":
    main()
