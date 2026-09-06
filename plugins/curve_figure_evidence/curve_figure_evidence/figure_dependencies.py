"""Offline, install-bound identities for the automatic figure toolchain."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


CONTRACT_PATH = Path(__file__).with_name("figure_dependencies.json")
PDF_COMMANDS = ("pdfinfo", "pdfimages", "pdftoppm")
UNSUPPLIED_CONTRACT = {
    "pillow_version": None, "poppler_version": None,
    "executables": {},
    "ocr": {"adapter": "tesseract --psm 11 -c tessedit_create_tsv=1", "version": None,
            "language": "eng",
            "supply_status": "unavailable"},
}


def load_contract() -> dict:
    if not CONTRACT_PATH.exists():
        return json.loads(json.dumps(UNSUPPLIED_CONTRACT))
    contract = json.loads(CONTRACT_PATH.read_bytes())
    if (set(contract) != set(UNSUPPLIED_CONTRACT)
            or not all(isinstance(contract[key], str) and contract[key]
                       for key in ("pillow_version", "poppler_version"))
            or set(contract["executables"]) != {*PDF_COMMANDS, "tesseract"}
            or set(contract["ocr"]) != set(UNSUPPLIED_CONTRACT["ocr"])
            or not isinstance(contract["ocr"]["version"], str) or not contract["ocr"]["version"]
            or contract["ocr"]["supply_status"] != "verified"
            or contract["ocr"]["language"] != "eng"
            or contract["ocr"]["adapter"] != UNSUPPLIED_CONTRACT["ocr"]["adapter"]):
        raise RuntimeError("invalid installed figure dependency contract")
    if not all(Path(value).is_absolute() for value in contract["executables"].values()):
        raise RuntimeError("figure executable paths must be absolute")
    return contract


def command_path(name: str) -> str:
    return RUNTIME_CONTRACT["executables"].get(name, name)


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    environment = {**os.environ, "OMP_NUM_THREADS": "1", "OMP_THREAD_LIMIT": "1"}
    environment.pop("TESSDATA_PREFIX", None)
    try:
        return subprocess.run(argv, check=True, capture_output=True, timeout=60,
                              env=environment)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"figure dependency call failed: {argv[0]}") from error


def _tool_version(name: str, executable: str) -> str:
    result = _run([executable, "--version" if name == "tesseract" else "-v"])
    lines = (result.stdout + result.stderr).decode().splitlines()
    fields = lines[0].split() if lines else []
    prefix = [name] if name == "tesseract" else [name, "version"]
    if len(fields) != len(prefix) + 1 or fields[:-1] != prefix:
        raise RuntimeError(f"cannot read {name} version")
    return fields[-1]


def verify_ocr(contract: dict) -> str:
    ocr = contract["ocr"]
    if ocr["supply_status"] != "verified":
        raise RuntimeError("OCR dependencies have not been supplied and verified")
    executable = contract["executables"]["tesseract"]
    version = _tool_version("tesseract", executable)
    if version != ocr["version"]:
        raise RuntimeError("Tesseract version differs from figure dependency contract")
    result = _run([executable, "--list-langs"])
    lines = [line.strip() for line in (result.stdout + result.stderr).decode().splitlines() if line.strip()]
    header = re.fullmatch(r'List of available languages(?: in ".*")? \(([0-9]+)\):', lines[0]) if lines else None
    languages = lines[1:]
    if (header is None or len(languages) != int(header[1])
            or len(set(languages)) != len(languages)
            or any(line.startswith("List of available languages") for line in languages)):
        raise RuntimeError("ambiguous OCR language list")
    if "eng" not in languages:
        raise RuntimeError("OCR language eng is unavailable")
    return f"tesseract {version}"


def ocr_command(contract: dict, image: Path) -> list[str]:
    return [contract["executables"]["tesseract"], str(image), "stdout",
            "-l", "eng", "--psm", "11", "-c", "tessedit_create_tsv=1"]


def verify_runtime(contract: dict, *, exercise: bool = False) -> None:
    from PIL import Image, ImageDraw, ImageFont, __version__

    if __version__ != contract["pillow_version"]:
        raise RuntimeError("Pillow version differs from figure dependency contract")
    for name in PDF_COMMANDS:
        if _tool_version(name, contract["executables"][name]) != contract["poppler_version"]:
            raise RuntimeError(f"{name} version differs from figure dependency contract")
    verify_ocr(contract)
    if exercise:
        with tempfile.TemporaryDirectory(prefix="scid-figure-preflight-") as directory:
            root = Path(directory)
            with Image.new("RGB", (100, 25), "white") as small:
                ImageDraw.Draw(small).text((5, 5), "12345", fill="black", font=ImageFont.load_default())
                image = small.resize((400, 100), Image.Resampling.LANCZOS)
            image.save(root / "probe.png")
            image.save(root / "probe.pdf", "PDF")
            image.close()
            _run([contract["executables"]["pdfinfo"], str(root / "probe.pdf")])
            _run([contract["executables"]["pdfimages"], "-png", str(root / "probe.pdf"), str(root / "embedded")])
            if not tuple(root.glob("embedded-*.png")):
                raise RuntimeError("pdfimages preflight produced no embedded image")
            _run([contract["executables"]["pdftoppm"], "-singlefile", "-scale-to", "400", "-png", str(root / "probe.pdf"), str(root / "rendered")])
            with Image.open(root / "rendered.png") as rendered:
                rendered.load()
            output = _run(ocr_command(contract, root / "probe.png")).stdout.decode()
            if not any(line.split("\t")[-1].strip() == "12345" for line in output.splitlines()[1:]):
                raise RuntimeError("OCR preflight did not recognize the supplied test image")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if args.installed:
        contract = load_contract()
    else:
        from PIL import __version__

        contract = json.loads(json.dumps(UNSUPPLIED_CONTRACT))
        contract["pillow_version"] = __version__
        for name in (*PDF_COMMANDS, "tesseract"):
            executable = shutil.which(name)
            if executable is None:
                raise RuntimeError(f"figure dependency unavailable in service PATH: {name}")
            contract["executables"][name] = str(Path(executable).resolve(strict=True))
        versions = {_tool_version(name, contract["executables"][name]) for name in PDF_COMMANDS}
        if len(versions) != 1:
            raise RuntimeError("Poppler tool versions differ")
        contract["poppler_version"] = versions.pop()
        contract["ocr"].update(version=_tool_version("tesseract", contract["executables"]["tesseract"]),
                               supply_status="verified")
    verify_runtime(contract, exercise=True)
    print(f"figure dependency preflight: pass; uid={os.geteuid()}; python={sys.executable}", file=sys.stderr)
    print(json.dumps(contract, sort_keys=True, separators=(",", ":")))


RUNTIME_CONTRACT = load_contract()


if __name__ == "__main__":
    main()
