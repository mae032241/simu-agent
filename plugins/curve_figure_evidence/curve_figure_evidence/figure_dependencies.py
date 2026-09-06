"""Offline, install-bound identities for the automatic figure toolchain."""

from __future__ import annotations

import argparse
import hashlib
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
    "pillow_version": "12.1.1", "poppler_version": "22.02.0",
    "executables": {},
    "ocr": {"adapter": "tesseract --psm 11 -c tessedit_create_tsv=1", "version": None,
            "model_path": None, "model_sha256": None, "language": "eng",
            "supply_status": "unavailable"},
}


def load_contract() -> dict:
    if not CONTRACT_PATH.exists():
        return json.loads(json.dumps(UNSUPPLIED_CONTRACT))
    contract = json.loads(CONTRACT_PATH.read_bytes())
    if (set(contract) != set(UNSUPPLIED_CONTRACT)
            or contract["pillow_version"] != "12.1.1"
            or contract["poppler_version"] != "22.02.0"
            or set(contract["executables"]) != {*PDF_COMMANDS, "tesseract"}
            or set(contract["ocr"]) != set(UNSUPPLIED_CONTRACT["ocr"])
            or contract["ocr"]["supply_status"] != "verified"
            or contract["ocr"]["language"] != "eng"
            or contract["ocr"]["adapter"] != UNSUPPLIED_CONTRACT["ocr"]["adapter"]):
        raise RuntimeError("invalid installed figure dependency contract")
    _validate_model_binding(contract["ocr"])
    if not all(Path(value).is_absolute() for value in contract["executables"].values()):
        raise RuntimeError("figure executable paths must be absolute")
    return contract


def _validate_model_binding(ocr: dict) -> None:
    if not isinstance(ocr["version"], str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", ocr["version"]):
        raise RuntimeError("SCID_FIGURE_TESSERACT_VERSION must specify an exact executable version")
    path = Path(ocr["model_path"] or "")
    if not path.is_absolute() or path.name != "eng.traineddata":
        raise RuntimeError("SCID_FIGURE_OCR_MODEL_PATH must be an absolute eng.traineddata path")
    if not isinstance(ocr["model_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", ocr["model_sha256"]):
        raise RuntimeError("SCID_FIGURE_OCR_MODEL_SHA256 must specify the supplied model SHA-256")


def command_path(name: str) -> str:
    return RUNTIME_CONTRACT["executables"].get(name, name)


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, check=True, capture_output=True, timeout=60,
                              env={**os.environ, "OMP_NUM_THREADS": "1", "OMP_THREAD_LIMIT": "1"})
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"figure dependency call failed: {argv[0]}") from error


def verify_ocr(contract: dict) -> str:
    ocr = contract["ocr"]
    if ocr["supply_status"] != "verified":
        raise RuntimeError("OCR model identity has not been supplied and verified")
    _validate_model_binding(ocr)
    model = Path(ocr["model_path"])
    try:
        if not model.is_file():
            raise OSError("model is not a regular file")
        with model.open("rb") as stream:
            checksum = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                checksum.update(chunk)
            digest = checksum.hexdigest()
    except OSError as error:
        raise RuntimeError("OCR model file is missing or unreadable") from error
    if digest != ocr["model_sha256"]:
        raise RuntimeError("OCR model SHA-256 differs from figure dependency contract")
    result = _run([contract["executables"]["tesseract"], "--version"])
    first_line = (result.stdout + result.stderr).decode().splitlines()[0]
    if first_line.split() != ["tesseract", ocr["version"]]:
        raise RuntimeError("Tesseract version differs from figure dependency contract")
    return f"{first_line}; eng sha256={digest}"


def ocr_command(contract: dict, image: Path) -> list[str]:
    return [contract["executables"]["tesseract"], str(image), "stdout",
            "--tessdata-dir", str(Path(contract["ocr"]["model_path"]).parent),
            "-l", "eng", "--psm", "11", "-c", "tessedit_create_tsv=1"]


def verify_runtime(contract: dict, *, exercise: bool = False) -> None:
    from PIL import Image, ImageDraw, ImageFont, __version__

    if __version__ != contract["pillow_version"]:
        raise RuntimeError("Pillow version differs from figure dependency contract")
    for name in PDF_COMMANDS:
        result = _run([contract["executables"][name], "-v"])
        first_line = (result.stdout + result.stderr).decode().splitlines()[0].split()
        if first_line[:3] != [name, "version", contract["poppler_version"]]:
            raise RuntimeError(f"{name} version differs from figure dependency contract")
    verify_ocr(contract)
    if exercise:
        with tempfile.TemporaryDirectory(prefix="scid-figure-preflight-") as directory:
            root = Path(directory)
            image = Image.new("RGB", (400, 100), "white")
            ImageDraw.Draw(image).text((20, 20), "12345", fill="black", font=ImageFont.load_default(size=42))
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
    parser.add_argument("--version")
    parser.add_argument("--model-path")
    parser.add_argument("--model-sha256")
    args = parser.parse_args()
    if args.installed:
        contract = load_contract()
    else:
        contract = json.loads(json.dumps(UNSUPPLIED_CONTRACT))
        for name in (*PDF_COMMANDS, "tesseract"):
            executable = shutil.which(name)
            if executable is None:
                raise RuntimeError(f"figure dependency unavailable in service PATH: {name}")
            contract["executables"][name] = str(Path(executable).resolve(strict=True))
        contract["ocr"].update(version=args.version, model_path=args.model_path,
                               model_sha256=args.model_sha256, supply_status="verified")
    verify_runtime(contract, exercise=True)
    print(f"figure dependency preflight: pass; uid={os.geteuid()}; python={sys.executable}", file=sys.stderr)
    print(json.dumps(contract, sort_keys=True, separators=(",", ":")))


RUNTIME_CONTRACT = load_contract()


if __name__ == "__main__":
    main()
