"""Sequential, read-only Codex replay of legacy versus compact invoke contracts.

This is a structural request-construction pilot, not scientific admission or a
live MCP/Run test. Run from a normal writable WSL terminal for Codex usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


REPO = Path(__file__).resolve().parents[1]
INSTALLED_SITE = Path("/opt/scidiscovery-m7/site")
SOURCE_SITE = REPO / "src"
CASES = {
    "figure": ("science.evidence.extract.figure.v3",
               ("research_objective", "prior_draft", "change_request")),
    "hypothesis": ("science.hypothesis.revise.v1",
                   ("experiment_results", "current_progress")),
    "tcad_revision": ("tcad.deck.author.revise.v1",
                      ("device_grid", "current_progress", "experiment_plan",
                       "curve_contract", "user_context")),
}
ORDER = ("A1", "B1", "B2", "A2")


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value: object) -> str:
    return hashlib.sha256(compact_json(value).encode()).hexdigest()


def expand(contract: dict) -> dict:
    result = dict(contract)
    defaults = result.pop("defaults", {})
    for field in ("contract_view_version", "defaults_rule", "full"):
        result.pop(field, None)
    for collection in ("inputs", "outputs"):
        if collection in result:
            result[collection] = [
                {**defaults.get(collection, {}), **port}
                for port in result[collection]
            ]
    return result


def emit_contract(case: str) -> None:
    # Child process only: PYTHONPATH pins the old installed or new source core.
    from scidiscovery.artifact_agent.interfaces import mcp_response_views as views
    from scidiscovery.operations.catalog import compile_catalog
    from scidiscovery.operations.spec import scheduler_operation_view
    from tests.operations.test_l4_local_tcad import (
        CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN, TCAD_PLUGIN,
    )
    from tests.operations.test_l2_run_invariants import BLIND_CSV_PLUGIN
    from curve_figure_evidence.plugin import PLUGIN as FIGURE_PLUGIN

    catalog = compile_catalog((CORE_PLUGIN, SCIENCE_PLUGIN, CURVE_PLUGIN,
                               TCAD_PLUGIN, FIGURE_PLUGIN, BLIND_CSV_PLUGIN))
    compiled = catalog.operation(CASES[case][0])
    declaration = views.operation_detail(
        scheduler_operation_view(compiled.spec).model_dump(mode="json", by_alias=True)
    )
    declaration["operation_digest"] = compiled.digest
    contract = views.operation_invoke_contract(
        declaration, revision_policy=views.operation_revision_policy(compiled.spec))
    print(compact_json({"module": str(Path(views.__file__).resolve()),
                        "catalog_digest": catalog.digest(), "contract": contract}))


def projection(case: str, arm: str) -> dict:
    site = INSTALLED_SITE if arm == "A" else SOURCE_SITE
    if not site.is_dir():
        raise RuntimeError(f"{arm} site is unavailable: {site}")
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(map(str, (
        site, REPO, REPO / "plugins/curve_score", REPO / "plugins/tcad_artifact",
        REPO / "plugins/curve_figure_evidence",
        REPO / "tests/fixtures/plugins/blind_csv_operation_plugin",
    )))
    done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "_emit", case],
                          cwd="/tmp", env=env, capture_output=True, text=True,
                          timeout=60, check=False)
    if done.returncode:
        raise RuntimeError(f"{arm}/{case} projection failed: {done.stderr.strip()}")
    value = json.loads(done.stdout)
    if not Path(value["module"]).is_relative_to(site):
        raise RuntimeError(f"{arm}/{case} imported the wrong core: {value['module']}")
    return value


def scenario(contract: dict, case: str) -> tuple[str, dict[str, list[str]]]:
    relevant = set(CASES[case][1])
    ports = contract["inputs"]
    names = {port["name"] for port in ports}
    if not relevant <= names:
        raise RuntimeError(f"{case} relevant optional ports are absent: {relevant - names}")
    inventory = {}
    expected = {}
    for port in ports:
        name = port["name"]
        minimum = port["min_items"]
        maximum = port["max_items"]
        if name in relevant and minimum:
            raise RuntimeError(f"{case}/{name} is not optional")
        count = max(1, minimum)
        if name in relevant and maximum >= 2:
            count = 2
        artifacts = [f"ab_{name}_{index}" for index in range(1, count + 1)]
        inventory[name] = artifacts
        if minimum or name in relevant:
            expected[name] = artifacts
    task = (
        "Construct arguments for a hypothetical scid_call(name=operation_preflight); "
        "do not call tools or create a Run. All listed artifacts hypothetically exist, "
        "are current, and match their named port schema. Bind every required input "
        "(derive requiredness from the contract, including any defaults). Bind optional "
        "inputs only when listed in relevant_optional_ports. For each selected port, "
        "use every listed artifact name in order. Do not invent names or ports. "
        "Return only one JSON object with exactly name, operation_id, inputs; "
        "inputs is a list of {port, artifact_names}. No markdown.\n"
        f"name: ab.invoke.{case}\n"
        f"operation_id: {CASES[case][0]}\n"
        f"relevant_optional_ports: {compact_json(CASES[case][1])}\n"
        f"available_bindings: {compact_json(inventory)}\n"
        f"scid_describe_invoke_contract: {compact_json(contract)}\n"
    )
    return task, expected


def grade(message: str | None, case: str, expected: dict[str, list[str]],
          unexpected_items: list[str]) -> dict:
    if message is None:
        return {"ok": False, "error": "missing agent message"}
    try:
        value = json.loads(message)
    except json.JSONDecodeError as error:
        return {"ok": False, "error": f"not JSON: {error.msg}"}
    if not isinstance(value, dict) or set(value) != {"name", "operation_id", "inputs"}:
        return {"ok": False, "error": "incorrect top-level shape"}
    if value["name"] != f"ab.invoke.{case}" or value["operation_id"] != CASES[case][0]:
        return {"ok": False, "error": "wrong name or operation_id"}
    inputs = value["inputs"]
    if not isinstance(inputs, list) or any(
        not isinstance(item, dict) or set(item) != {"port", "artifact_names"}
        or not isinstance(item["port"], str)
        or not isinstance(item["artifact_names"], list)
        or any(not isinstance(name, str) for name in item["artifact_names"])
        for item in inputs
    ):
        return {"ok": False, "error": "incorrect inputs shape"}
    observed = {item["port"]: item["artifact_names"] for item in inputs}
    if len(observed) != len(inputs):
        return {"ok": False, "error": "duplicate input port"}
    if unexpected_items:
        return {"ok": False, "error": f"unexpected tool/items: {unexpected_items}"}
    return {"ok": observed == expected,
            "missing_ports": sorted(set(expected) - set(observed)),
            "extra_ports": sorted(set(observed) - set(expected)),
            "wrong_bindings": sorted(name for name in expected.keys() & observed.keys()
                                     if expected[name] != observed[name])}


def parse_jsonl(path: Path, case: str, expected: dict[str, list[str]]) -> dict:
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
              if line.strip()]
    completions = [event for event in events if event.get("type") == "turn.completed"]
    failures = [event for event in events if event.get("type") == "turn.failed"]
    items = [event["item"] for event in events if event.get("type") == "item.completed"]
    unexpected = [item.get("type", "unknown") for item in items
                  if item.get("type") != "agent_message"]
    messages = [item.get("text") for item in items if item.get("type") == "agent_message"]
    if len(completions) != 1 or failures:
        return {"grade": {"ok": False, "error": "turn did not complete exactly once"},
                "usage": None, "unexpected_items": unexpected}
    usage = completions[0].get("usage")
    if not isinstance(usage, dict):
        return {"grade": {"ok": False, "error": "missing usage"},
                "usage": None, "unexpected_items": unexpected}
    usage = {key: usage.get(key) for key in (
        "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
        "output_tokens", "reasoning_output_tokens")}
    if all(isinstance(usage[key], int) for key in ("input_tokens", "cached_input_tokens",
                                                  "output_tokens")):
        usage["noncached_input_tokens"] = usage["input_tokens"] - usage["cached_input_tokens"]
    return {"grade": grade(messages[-1] if messages else None, case, expected, unexpected),
            "usage": usage, "unexpected_items": unexpected}


def run_codex(prompt: str, path: Path, model: str, effort: str) -> tuple[int, str, float]:
    command = ["codex", "exec", "--ephemeral", "--ignore-user-config",
               "--skip-git-repo-check", "-C", "/tmp", "-m", model,
               "-c", f'model_reasoning_effort="{effort}"', "-s", "read-only",
               "--json", "-"]
    started = time.monotonic()
    done = subprocess.run(command, input=prompt, text=True, capture_output=True,
                          cwd="/tmp", timeout=300, check=False)
    path.write_text(done.stdout, encoding="utf-8")
    path.with_suffix(".stderr").write_text(done.stderr, encoding="utf-8")
    return done.returncode, done.stderr.strip(), time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true",
                        help="check contract equality and prompts without model calls")
    parser.add_argument("--out-dir", type=Path,
                        help="new output directory; must not already exist")
    parser.add_argument("--model", default="gpt-6-sol")
    parser.add_argument("--effort", choices=("low", "medium", "high"), default="low")
    args = parser.parse_args()
    output = args.out_dir or Path(tempfile.mkdtemp(prefix="scid-root-invoke-ab-"))
    if args.out_dir:
        output.mkdir(parents=True, exist_ok=False)
    manifest = {"kind": "invoke-structural-pilot", "model": args.model,
                "effort": args.effort, "schedule": list(ORDER), "cases": {}}
    prompts = {}
    for case in CASES:
        old, new = projection(case, "A"), projection(case, "B")
        if old["catalog_digest"] != new["catalog_digest"]:
            raise RuntimeError(f"{case}: catalog digest differs across arms")
        if sha256(old["contract"]) != sha256(expand(new["contract"])):
            raise RuntimeError(f"{case}: expanded compact contract differs from installed legacy")
        if new["contract"].get("contract_view_version") != "invoke.compact.v1":
            raise RuntimeError(f"{case}: candidate is not compact invoke v1")
        expected_prompt = {}
        for arm, value in (("A", old), ("B", new)):
            prompt, expected = scenario(old["contract"], case) if arm == "A" else scenario(
                expand(new["contract"]), case)
            # Keep the task and inventory identical; replace only the contract.
            contract_text = compact_json(old["contract"])
            replacement = compact_json(value["contract"])
            prompt = prompt.replace("scid_describe_invoke_contract: " + contract_text,
                                    "scid_describe_invoke_contract: " + replacement)
            expected_prompt[arm] = expected
            prompts[(case, arm)] = prompt
            (output / f"{case}_{arm}.prompt.txt").write_text(prompt, encoding="utf-8")
        if expected_prompt["A"] != expected_prompt["B"]:
            raise RuntimeError(f"{case}: expected mappings differ across arms")
        manifest["cases"][case] = {
            "operation_id": CASES[case][0], "catalog_digest": old["catalog_digest"],
            "legacy_sha256": sha256(old["contract"]),
            "compact_sha256": sha256(new["contract"]),
            "prompt_bytes": {arm: len(prompts[(case, arm)].encode()) for arm in ("A", "B")},
            "expected": expected_prompt["A"], "runs": {},
        }
    (output / "manifest.json").write_text(compact_json(manifest) + "\n", encoding="utf-8")
    print(f"prepared: {output}", flush=True)
    for case, record in manifest["cases"].items():
        print(f"  {case}: prompt A={record['prompt_bytes']['A']} B={record['prompt_bytes']['B']} bytes",
              flush=True)
    if args.prepare_only:
        return 0
    for case in CASES:
        for label in ORDER:
            arm = label[0]
            path = output / f"{case}_{label}.jsonl"
            print(f"running {case} {label} ...", flush=True)
            code, stderr, seconds = run_codex(prompts[(case, arm)], path,
                                             args.model, args.effort)
            if code:
                raise RuntimeError(f"{case}/{label}: Codex exited {code}; stderr={stderr}; log={path}")
            result = parse_jsonl(path, case, manifest["cases"][case]["expected"])
            result["seconds"] = round(seconds, 2)
            manifest["cases"][case]["runs"][label] = result
            (output / "manifest.json").write_text(compact_json(manifest) + "\n",
                                                    encoding="utf-8")
            usage = result["usage"] or {}
            print(f"  ok={result['grade']['ok']} input={usage.get('input_tokens')} "
                  f"noncached={usage.get('noncached_input_tokens')} "
                  f"output={usage.get('output_tokens')}", flush=True)
    print(f"complete: {output / 'manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "_emit":
        emit_contract(sys.argv[2])
    else:
        raise SystemExit(main())
