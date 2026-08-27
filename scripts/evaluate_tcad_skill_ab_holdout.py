#!/usr/bin/env python3
"""Score the frozen SDevice author/review holdout without running a solver."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _item(name: str, passed: bool, weight: int = 1) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "weight": weight}


def _score(items: list[dict[str, object]]) -> dict[str, object]:
    maximum = sum(int(item["weight"]) for item in items)
    earned = sum(int(item["weight"]) for item in items if item["passed"])
    return {"earned": earned, "maximum": maximum, "criteria": items}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("arm", type=Path)
    args = parser.parse_args()
    try:
        source = (args.arm / "authoring" / "candidate.cmd").read_text(encoding="utf-8")
        author = _json(args.arm / "authoring" / "report.json")
        review = _json(args.arm / "review" / "report.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"valid": False, "error": str(error)}, sort_keys=True))
        return 2
    folded = source.casefold()
    authoring = _score([
        _item("direct_sdevice_source", not source.startswith("#!") and not re.search(r"(?m)^\s*(?:exec\s+)?sdevice\b", source), 2),
        _item("exact_grid_and_raw_paths", all(value in source for value in ("mesh.tdr", "results/device.tdrdat", "results/device.plt", "results/device.log")), 2),
        _item("exact_contacts", re.search(r'Name\s*=\s*"anode"[^}]*Voltage\s*=\s*0(?:\.0+)?', source, re.I | re.S) is not None and re.search(r'Name\s*=\s*"cathode"[^}]*Voltage\s*=\s*0(?:\.0+)?', source, re.I | re.S) is not None, 2),
        _item("minimal_physics", all(token in folded for token in ("fermi", "dopingdependence", "srh")) and not any(token in folded for token in ("avalanche", "optical", "auger", "radiative")), 2),
        _item("solve_order", folded.find("poisson") < folded.find("coupled") < folded.find("quasistationary"), 2),
        _item("cathode_goal", re.search(r'Goal\s*\{[^}]*Name\s*=\s*"cathode"[^}]*Voltage\s*=\s*0\.5', source, re.I | re.S) is not None, 2),
        _item("explicit_sweep_controls", all(re.search(rf"\b{name}\s*=", source, re.I) for name in ("InitialStep", "MinStep", "MaxStep", "Increment", "Decrement")), 2),
        _item("required_plot_fields", all(token.casefold() in folded for token in ("eDensity", "hDensity", "Potential", "ElectricField", "eCurrent", "hCurrent")), 2),
        _item("no_embedded_analysis", not any(token in folded for token in ("score", "threshold", "verdict", "python", "nohup"))),
        _item("bounded_manual_use", isinstance(author.get("manual_queries"), int) and 0 <= int(author["manual_queries"]) <= 2),
    ])
    findings = " ".join(str(item) for item in review.get("findings", []))
    reviewing = _score([
        _item("revise_not_ready", review.get("verdict") == "revise" and review.get("execution_ready") is False, 3),
        _item("contact_mismatch_found", "cathod" in findings and "cathode" in findings, 4),
        _item("bounded_finding_set", isinstance(review.get("findings"), list) and 1 <= len(review["findings"]) <= 2, 2),
        _item("no_runtime_or_scientific_overreach", not any(token in (findings + " " + str(review.get("summary", ""))).casefold() for token in ("ran the solver", "hypothesis rejected", "curve mismatch", "add avalanche"))),
        _item("bounded_manual_use", isinstance(review.get("manual_queries"), int) and 0 <= int(review["manual_queries"]) <= 1),
    ])
    earned = int(authoring["earned"]) + int(reviewing["earned"])
    maximum = int(authoring["maximum"]) + int(reviewing["maximum"])
    print(json.dumps({"valid": True, "earned": earned, "maximum": maximum, "fraction": earned / maximum, "authoring": authoring, "review": reviewing}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
