"""Offline, install-bound dependencies for exact PDF image recovery."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


CONTRACT_PATH = Path(__file__).with_name("figure_dependencies.json")
PDF_COMMANDS = ("pdfimages",)
UNSUPPLIED_CONTRACT = {
    "pillow_version": None,
    "poppler_version": None,
    "executables": {},
}


def load_contract() -> dict:
    if not CONTRACT_PATH.exists():
        return json.loads(json.dumps(UNSUPPLIED_CONTRACT))
    contract = json.loads(CONTRACT_PATH.read_bytes())
    if (
        set(contract) != set(UNSUPPLIED_CONTRACT)
        or not all(
            isinstance(contract[key], str) and contract[key]
            for key in ("pillow_version", "poppler_version")
        )
        or set(contract["executables"]) != set(PDF_COMMANDS)
        or not all(
            Path(value).is_absolute()
            for value in contract["executables"].values()
        )
    ):
        raise RuntimeError("invalid installed figure dependency contract")
    return contract


def command_path(name: str) -> str:
    return RUNTIME_CONTRACT["executables"].get(name, name)


def _run(argv: list[str]) -> subprocess.CompletedProcess[bytes]:
    environment = {
        **os.environ,
        "OMP_NUM_THREADS": "1",
        "OMP_THREAD_LIMIT": "1",
    }
    try:
        return subprocess.run(
            argv,
            check=True,
            capture_output=True,
            timeout=60,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"figure dependency call failed: {argv[0]}") from error


def _poppler_version(executable: str) -> str:
    result = _run([executable, "-v"])
    lines = (result.stdout + result.stderr).decode().splitlines()
    fields = lines[0].split() if lines else []
    if len(fields) != 3 or fields[:2] != ["pdfimages", "version"]:
        raise RuntimeError("cannot read pdfimages version")
    return fields[-1]


def verify_runtime(contract: dict, *, exercise: bool = False) -> None:
    from PIL import Image, __version__ as pillow_version

    if pillow_version != contract["pillow_version"]:
        raise RuntimeError("Pillow version differs from figure dependency contract")
    executable = contract["executables"]["pdfimages"]
    if _poppler_version(executable) != contract["poppler_version"]:
        raise RuntimeError("pdfimages version differs from figure dependency contract")
    if not exercise:
        return
    with tempfile.TemporaryDirectory(prefix="scid-figure-preflight-") as directory:
        root = Path(directory)
        with Image.new("RGB", (100, 25), "white") as image:
            image.save(root / "probe.pdf", "PDF")
        _run(
            [
                executable,
                "-png",
                str(root / "probe.pdf"),
                str(root / "embedded"),
            ]
        )
        if not tuple(root.glob("embedded-*.png")):
            raise RuntimeError("pdfimages preflight produced no embedded image")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if args.installed:
        contract = load_contract()
    else:
        from PIL import __version__ as pillow_version

        executable = shutil.which("pdfimages")
        if executable is None:
            raise RuntimeError(
                "figure dependency unavailable in service PATH: pdfimages"
            )
        resolved = str(Path(executable).resolve(strict=True))
        contract = {
            "pillow_version": pillow_version,
            "poppler_version": _poppler_version(resolved),
            "executables": {"pdfimages": resolved},
        }
    verify_runtime(contract, exercise=True)
    print(
        f"figure dependency preflight: pass; uid={os.geteuid()}; python={sys.executable}",
        file=sys.stderr,
    )
    print(json.dumps(contract, sort_keys=True, separators=(",", ":")))


RUNTIME_CONTRACT = load_contract()


if __name__ == "__main__":
    main()
