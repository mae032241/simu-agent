#!/usr/bin/env python3
"""Deterministically score the frozen sentaurus-tcad-code forward evaluation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "tcad_skill_ab"


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _criterion(name: str, passed: bool, weight: int = 1) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "weight": weight}


def _authoring(directory: Path) -> dict[str, object]:
    source_path = directory / "authoring" / "candidate.cmd"
    report_path = directory / "authoring" / "report.json"
    source = source_path.read_text(encoding="utf-8")
    report = _read_json(report_path)
    folded = source.casefold()
    procedure = re.search(r"(?m)^\s*proc\s+(\w*case\w*)\s+", source, re.I)
    procedure_name = procedure.group(1) if procedure else ""
    calls = (
        re.findall(rf"(?m)^\s*{re.escape(procedure_name)}\s+([^\n#]+)", source)
        if procedure_name
        else []
    )
    solution = re.search(
        r"(?mi)^\s*solution\b[^\n]*\bname\s*=\s*TracerInventory\b[^\n]*$",
        source,
    )
    solution_is_unconditional = bool(
        solution
        and re.search(r"\badd\b", solution.group(0), re.I)
        and re.search(r"\bsolve\b", solution.group(0), re.I)
        and "ifpresent" not in solution.group(0).casefold()
    )
    solution_before_procedure = bool(
        solution and procedure and solution.start() < procedure.start()
    )
    compact = re.sub(r"\s+", "", source)
    criteria = [
        _criterion("direct_solver_deck", not source.startswith("#!") and not re.search(r"(?m)^\s*(?:exec\s+)?sprocess\b", source), 2),
        _criterion("custom_solution", solution_is_unconditional, 2),
        _criterion("solution_declared_once_before_case_dispatch", source.casefold().count("solution name=tracerinventory") == 1 and solution_before_procedure, 2),
        _criterion("conservative_equation", "ddt(tracerinventory)" in folded and "grad(tracerinventory)" in folded, 2),
        _criterion("fresh_case_structure", bool(procedure) and "line clear" in folded, 2),
        _criterion("two_declared_cases", len(calls) == 2 and "low_D" in source and "high_D" in source, 2),
        _criterion("case_diffusivities", bool(re.search(r"\b1(?:\.0+)?e-14\b", source, re.I)) and bool(re.search(r"\b2(?:\.0+)?e-14\b", source, re.I)), 2),
        _criterion("explicit_geometry_units", bool(re.search(r"location=0(?:\.0+)?<um>", compact, re.I)) and bool(re.search(r"location=2(?:\.0+)?<um>", compact, re.I)) and bool(re.search(r"location=2\.0*2<um>", compact, re.I))),
        _criterion("explicit_process_units", "400<C>" in source and "10<s>" in source and "1<s>" in source),
        _criterion("initial_and_boundary_values", "1e18" in source and "Fixed_" in source and "Equation_" in source and re.search(r"init\s+concentration\s*=\s*0\s+field\s*=\s*TracerInventory", source, re.I) is not None),
        _criterion("raw_profile_selection", "SetPlxList" in source and "TracerInventory" in source and "WritePlx" in source, 2),
        _criterion("case_distinct_outputs", bool(re.search(r"WritePlx[^\n]*\$\{?case", source, re.I)) or ("low_D.plx" in source and "high_D.plx" in source), 2),
        _criterion("no_embedded_analysis", not any(token in folded for token in ("score", "threshold", "verdict", "metrics.csv", "resample"))),
        _criterion("bounded_manual_use", isinstance(report.get("manual_queries"), int) and 0 <= int(report["manual_queries"]) <= 2),
    ]
    earned = sum(int(item["weight"]) for item in criteria if item["passed"])
    maximum = sum(int(item["weight"]) for item in criteria)
    return {"earned": earned, "maximum": maximum, "criteria": criteria, "bytes": len(source.encode("utf-8"))}


def _diagnosis(directory: Path) -> dict[str, object]:
    patched_path = directory / "diagnosis" / "patched.cmd"
    report_path = directory / "diagnosis" / "report.json"
    original = (FIXTURE / "broken.cmd").read_text(encoding="utf-8")
    patched = patched_path.read_text(encoding="utf-8")
    report = _read_json(report_path)
    original_lines = original.splitlines()
    patched_lines = patched.splitlines()
    changed = sum(1 for a, b in zip(original_lines, patched_lines) if a != b) + abs(len(original_lines) - len(patched_lines))
    expected = original.replace("MaxTimestep=1<s>", "maxstep=1<s>")
    criteria = [
        _criterion("earliest_layer_parser", any(token in str(report.get("earliest_layer", "")).casefold() for token in ("parser", "syntax")), 2),
        _criterion("first_error_preserved", "MaxTimestep" in str(report.get("first_error", "")) and "FastMarchUnknown" in str(report.get("first_error", "")), 2),
        _criterion("exact_minimal_patch", patched == expected, 4),
        _criterion("one_changed_line", changed == 1 and report.get("changed_lines") == 1, 2),
        _criterion("no_scientific_interpretation", not any(token in str(report.get("summary", "")).casefold() for token in ("hypothesis rejected", "physical model invalid", "curve mismatch"))),
        _criterion("bounded_manual_use", isinstance(report.get("manual_queries"), int) and 0 <= int(report["manual_queries"]) <= 1),
    ]
    earned = sum(int(item["weight"]) for item in criteria if item["passed"])
    maximum = sum(int(item["weight"]) for item in criteria)
    return {"earned": earned, "maximum": maximum, "criteria": criteria, "changed_lines": changed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("arm", type=Path, help="directory containing authoring/ and diagnosis/")
    args = parser.parse_args()
    try:
        authoring = _authoring(args.arm)
        diagnosis = _diagnosis(args.arm)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"valid": False, "error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    earned = int(authoring["earned"]) + int(diagnosis["earned"])
    maximum = int(authoring["maximum"]) + int(diagnosis["maximum"])
    print(json.dumps({"valid": True, "earned": earned, "maximum": maximum, "fraction": earned / maximum, "authoring": authoring, "diagnosis": diagnosis}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
