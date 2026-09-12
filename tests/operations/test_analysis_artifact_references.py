"""Real Worker paths for saved calculations and Agent-authored derived evidence."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.layered_diagnosis import CalculationRecord
from scidiscovery.artifact_agent.interfaces.mcp_local_worker import LocalWorkerMCPRouter
from scidiscovery.operation_contract import DiagnosticError
from tests.operations.test_analysis_claim_scope import generic_worker, submit
from tests.operations.test_analysis_diagnostic_tool import request_for_diagnostic
from tests.operations.test_result_analysis_tool import limited_report, score_inputs
from tests.operations.test_tcad_result_analysis import analysis_system, open_analysis, raw_request, analysis_report


def cite(report, alias, key="calculation"):
    report["source_references"] = []
    report["calculation_records"] = []
    report["evidence"].append(dict(source_key=key, title="Saved analysis evidence",
        source_type="runtime_output", locator=alias))
    return report


def test_plot_failure_preserves_numbers_and_later_bound_plot_does_not_recompute(tmp_path):
    """A tiny staged task through publish, partial submit, exact binding and new Run."""
    system = analysis_system(tmp_path)
    worker, opened = open_analysis(system)
    root = Path(opened['workspace_path'])
    # Reproduce the old write order with no scientific computation.
    legacy = root / 'scratch/legacy.py'
    legacy.write_text('from pathlib import Path\nnumbers = 3\nimport fixture_plotter\nPath("lost.json").write_text(str(numbers))\n')
    assert subprocess.run([sys.executable, '-B', str(legacy)], cwd=legacy.parent,
        capture_output=True, timeout=5).returncode == 1
    assert not (legacy.parent / 'lost.json').exists()
    script = '''import json, os, sys
from pathlib import Path
def compute(method):
    if Path("numbers.json").exists() and json.loads(Path("numbers.json").read_text())["method"] == method:
        return
    count = int(Path("calls.txt").read_text()) if Path("calls.txt").exists() else 0
    Path("calls.txt").write_text(str(count + 1))
    Path("numbers.tmp").write_text(json.dumps({"method": method, "value": 3}))
    os.replace("numbers.tmp", "numbers.json")
def plot():
    import fixture_plotter
    fixture_plotter.render(json.loads(Path("numbers.json").read_text()))
if sys.argv[1] == "compute": compute(sys.argv[2])
else: plot()
'''
    scratch = root / 'scratch'; (scratch / 'analysis.py').write_text(script)
    subprocess.run([sys.executable, '-B', 'analysis.py', 'compute', 'fixture_v1'], cwd=scratch, check=True, timeout=5)
    numbers = (scratch / 'numbers.json').read_bytes()
    error = subprocess.run([sys.executable, '-B', 'analysis.py', 'plot'], cwd=scratch, capture_output=True, timeout=5)
    assert error.returncode == 1 and b'ModuleNotFoundError' in error.stderr
    assert (scratch / 'numbers.json').read_bytes() == numbers
    published = worker.call_tool('worker_analysis_publish_files', dict(source_aliases=['reference_material'],
        script_path='scratch/analysis.py', files=[dict(path='scratch/numbers.json', media_type='application/json'),
            dict(path='scratch/calls.txt', media_type='text/plain')], method='Tiny fixture unit; optional plot unavailable.'))
    assert submit(worker, opened, cite(analysis_report(), published['files'][0]['evidence_alias']))['state'] == 'completed'
    # A new controlled task binds the actual sealed files, not another Agent's memory.
    catalog, runtime, facade, request, artifacts, register = system
    request = deepcopy(request); request['name'] = 'plot_continuation'
    reference = next(i for i in request['inputs'] if i['port'] == 'reference_material')
    retained = [published['script'], *published['files']]
    reference['artifact_names'].extend('analysis.output.' + item['evidence_alias'] for item in retained)
    following, reopened = open_analysis((catalog, runtime, facade, request, artifacts, register))
    next_root = Path(reopened['workspace_path']); next_scratch = next_root / 'scratch'
    bindings = runtime.runs.status(following._run_id).inputs
    assignment = json.loads(Path(reopened['assignment_path']).read_text())
    for name, item in zip(('analysis.py', 'numbers.json', 'calls.txt'), retained):
        ref = runtime.runs.source_descriptor(runtime.runs.status(worker._run_id), item['evidence_alias']).artifact_ref
        alias = next(i.source_name for i in bindings if i.artifact_ref == ref)
        source = next(i['relative_path'] for i in assignment['inputs'] if i['source_name'] == alias)
        (next_scratch / name).write_bytes((next_root / source).read_bytes())
    # Only the plot implementation changes; numerical input/method and bytes stay fixed.
    (next_scratch / 'analysis.py').write_text(script.replace('    import fixture_plotter\n    fixture_plotter.render(json.loads(Path("numbers.json").read_text()))',
        '    from PIL import Image\n    data = json.loads(Path("numbers.json").read_text())\n    Image.new("RGB", (2,2)).save("plot.png")'))
    subprocess.run([sys.executable, '-B', 'analysis.py', 'plot'], cwd=next_scratch, check=True, timeout=5)
    assert (next_scratch / 'numbers.json').read_bytes() == numbers
    assert (next_scratch / 'calls.txt').read_text() == '1'
    data_alias = next(i.source_name for i in bindings if i.artifact_ref == runtime.runs.source_descriptor(
        runtime.runs.status(worker._run_id), published['files'][0]['evidence_alias']).artifact_ref)
    plotted = following.call_tool('worker_analysis_publish_files', dict(source_aliases=[data_alias], script_path='scratch/analysis.py',
        files=[dict(path='scratch/plot.png', media_type='image/png')], method='Render saved fixture numbers without fitting.'))
    assert submit(following, reopened, cite(analysis_report(), plotted['files'][0]['evidence_alias']))['state'] == 'completed'
    # The fixture's numerical-method change does invalidate its affected checkpoint.
    subprocess.run([sys.executable, '-B', 'analysis.py', 'compute', 'fixture_v2'], cwd=next_scratch, check=True, timeout=5)
    assert (next_scratch / 'calls.txt').read_text() == '2'


@pytest.mark.parametrize("domain", ["generic", "tcad"])
def test_reference_only_report_resolves_saved_score_without_copy_or_recalculation(tmp_path, monkeypatch, domain):
    if domain == "generic":
        worker, opened = generic_worker(tmp_path)
        request, name, report = score_inputs()[1], "worker_curve_score", limited_report()
    else:
        worker, opened = open_analysis(analysis_system(tmp_path))
        request, name, report = raw_request(), "worker_tcad_curve_score", analysis_report()
    reply = worker.call_tool(name, dict(record_key="saved", request=request))
    assert reply["status"] == "computed", reply
    alias = reply["calculation_ref"]
    saved = json.loads(worker.runs.read_tool_evidence(worker.runs.status(worker._run_id), alias))
    assert saved["request"] == request
    assert saved["attempt"] == CalculationRecord.model_validate_json(canonical_json(reply)).attempt.model_dump(mode="json")
    assert "calculation_ref" not in saved
    monkeypatch.setattr("curve_score.analysis_tool.evaluate_analysis_request", lambda **kw: pytest.fail("recomputed during submission"))
    report = cite(report, alias)
    report["objective_assessment"] = dict(objective_key="local_profile", status="inconclusive",
        comparison_keys=[request["comparison_spec"]["comparisons"][0]["comparison_key"]],
        evidence_keys=["calculation"], summary="Cited comparison is available without copying its record.")
    # Use the exact fixture objective, with no scientific mutation by the runtime.
    plan = json.loads(worker.runs.artifacts.read(next(i.artifact_ref for i in worker.runs.status(worker._run_id).inputs if i.port_name == "experiment_plan")))
    if plan.get("objective_key"):
        report["objective_assessment"]["objective_key"] = plan["objective_key"]
    else:
        report["objective_assessment"] = None
    assert submit(worker, opened, report)["state"] == "completed"
    sealed = json.loads(worker.runs.artifacts.read(worker.runs.status(worker._run_id).output_ref))
    assert sealed == report  # No copying of request, digest, values or receipt into scientific text.
    assert sealed["calculation_records"] == []


def test_full_257_point_diagnostic_does_not_shrink_to_fit_report(tmp_path):
    worker, opened = open_analysis(analysis_system(tmp_path))
    request = request_for_diagnostic(raw_request())
    request["comparison_spec"]["comparisons"][0]["evaluation_points"] = 257
    for source in request["sources"]:
        source["case_mapping_basis"] = dict(kind="evidence", rationale="bounded fixture rationale " * 70,
            evidence_refs=[dict(input_alias="experiment_plan", locator="fixture " * 30) for _ in range(8)])
    value = worker.call_tool("worker_tcad_curve_diagnose", dict(record_key="full_detail", request=request))
    record = value["record"]
    assert record["status"] == "computed", value
    details = json.loads(Path(value["details"]["path"]).read_text())
    assert len(details["localization"]["analyses"][0]["residual_trace"]) == 257
    old_layout = {**record, "result": details}
    with pytest.raises(ValueError, match="exceeds 32 KiB"):
        CalculationRecord.model_validate_json(canonical_json(old_layout))
    assert len(canonical_json(record)) < 32 * 1024
    assert submit(worker, opened, cite(analysis_report(), record["calculation_ref"]))["state"] == "completed"


def test_saved_calculations_use_artifact_identity_when_names_repeat(tmp_path):
    worker, opened = generic_worker(tmp_path)
    request = score_inputs()[1]
    first = worker.call_tool("worker_curve_score", dict(record_key="comparison", request=request))
    request["comparison_spec"]["comparisons"][0]["comparison_key"] = "second_comparison"
    second = worker.call_tool("worker_curve_score", dict(record_key="comparison", request=request))
    assert first["status"] == second["status"] == "computed"
    assert first["calculation_ref"] != second["calculation_ref"]
    report = cite(limited_report(), first["calculation_ref"], "first")
    cite(report, second["calculation_ref"], "second")
    assert submit(worker, opened, report)["state"] == "completed"


def test_rejected_score_needs_no_manual_failure_record(tmp_path):
    from tests.operations.test_score_request_contract import call_score
    worker, opened = open_analysis(analysis_system(tmp_path))
    request = raw_request()
    request["comparison_spec"]["comparisons"][0]["evaluation_points"] = 5000
    result = call_score(worker, request)
    assert result["error"]["data"]["diagnostics"][0]["phase"] == "tool_arguments"
    report = cite(analysis_report(), "tool_recovery_manifest", "calculation_limit")
    assert submit(worker, opened, report)["state"] == "completed"


def test_native_script_and_filtered_table_are_saved_and_consumed_by_curve_tool(tmp_path):
    worker, opened = generic_worker(tmp_path)
    workspace = Path(opened["output_directory"]).parent
    scratch = workspace / "scratch"; scratch.mkdir(exist_ok=True)
    raw = worker.runs.artifacts.read(next(i.artifact_ref for i in worker.runs.status(worker._run_id).inputs if i.port_name == "curve_bundle"))
    (scratch / "source.json").write_bytes(raw)
    script = '''import csv, json
from pathlib import Path
points = json.loads(Path("source.json").read_text())["series"][0]["points"]
selected = [p for p in points if p["x"] >= 0.5]
with Path("selected.csv").open("w") as f:
    w = csv.writer(f); w.writerow(["x", "y"])
    w.writerows((p["x"], p["y"]) for p in selected)
weights = [p["x"] + 1 for p in selected]
Path("weighted.json").write_text(json.dumps({"weighted_mean": sum(w*p["y"] for w,p in zip(weights, selected))/sum(weights), "count": len(selected)}))
'''
    (scratch / "analysis.py").write_text(script)
    subprocess.run([sys.executable, "analysis.py"], cwd=scratch, check=True, timeout=10)
    published = worker.call_tool("worker_analysis_publish_files", dict(source_aliases=["curve_bundle"],
        script_path="scratch/analysis.py", files=[dict(path="scratch/selected.csv", media_type="text/csv"),
            dict(path="scratch/weighted.json", media_type="application/json")],
        method="Select x >= 0.5; preserve the x+1 weighted mean separately from the curve comparison."))
    assert published["execution_proof"] == "agent_reported"
    alias = published["files"][0]["evidence_alias"]
    original = json.loads(raw)["series"][0]
    request = request_for_diagnostic(score_inputs()[1])
    reference, candidate = (request["comparison_spec"]["comparisons"][0][key] for key in ("reference_series", "candidate_series"))
    request["comparison_spec"]["comparisons"][0]["domain"]["start"] = 0.5
    request["sources"] = [dict(format="csv", input_alias=alias, series_key=name,
        case_key=original["case_key"], role=role, x_axis=original["x_axis"], y_axis=original["y_axis"],
        x_column="x", y_column="y") for name, role in ((reference, "reference"), (candidate, "candidate"))]
    result = worker.call_tool("worker_curve_score", dict(record_key="filtered_comparison", request=request))
    assert result["status"] == "computed", result
    report = cite(limited_report(), result["calculation_ref"])
    report = cite(report, published["files"][1]["evidence_alias"], "weighted_native_result")
    assert submit(worker, opened, report)["state"] == "completed"
    for file in [published["script"], *published["files"]]:
        stored = worker.runs.read_tool_evidence(worker.runs.status(worker._run_id), file["evidence_alias"])
        assert stored == Path(file["path"]).read_bytes()


@pytest.mark.parametrize("bad", ["outside", "symlink", "source"])
def test_publish_files_rejects_unbound_or_outside_files_without_blocking_analysis(tmp_path, bad):
    worker, opened = generic_worker(tmp_path)
    workspace = Path(opened["output_directory"]).parent
    scratch = workspace / "scratch"; scratch.mkdir(exist_ok=True)
    (scratch / "script.py").write_text("# fixture")
    (scratch / "out.csv").write_text("x,y\n0,1\n")
    args = dict(source_aliases=["curve_bundle"], script_path="scratch/script.py",
        files=[dict(path="scratch/out.csv", media_type="text/csv")], method="fixture")
    if bad == "outside": args["script_path"] = "../outside.py"
    if bad == "source": args["source_aliases"] = ["unbound"]
    if bad == "symlink":
        (scratch / "out.csv").unlink(); (scratch / "out.csv").symlink_to(scratch / "script.py")
    with pytest.raises(DiagnosticError):
        worker.call_tool("worker_analysis_publish_files", args)
    assert worker.runs.tool_evidence(worker._run_id) == []
    assert submit(worker, opened, limited_report())["state"] == "completed"


def test_saved_calculation_can_be_cited_next_round_with_current_alias(tmp_path, monkeypatch):
    system = analysis_system(tmp_path)
    catalog, runtime, root, request, _, _ = system
    worker, opened = open_analysis(system)
    result = worker.call_tool("worker_tcad_curve_score", dict(record_key="persisted", request=raw_request()))
    assert submit(worker, opened, cite(analysis_report(), result["calculation_ref"]))["state"] == "completed"
    second = deepcopy(request); second["name"] = "second_analysis"
    second["inputs"].extend([dict(port="prior_analysis", artifact_names=["analysis.output"]),
        dict(port="prior_analysis_manifest", artifact_names=["analysis.output.recovery_manifest"])])
    reference = next(i for i in second["inputs"] if i["port"] == "reference_material")
    reference["artifact_names"].append("analysis.output." + result["calculation_ref"])
    next_worker, next_opened = open_analysis((catalog, runtime, root, second, *system[4:]))
    monkeypatch.setattr("curve_score.analysis_tool.evaluate_analysis_request", lambda **kw: pytest.fail("historical score rerun"))
    assert submit(next_worker, next_opened, cite(analysis_report(), "reference_material_002"))["state"] == "completed"


def test_saved_calculation_survives_failed_run_without_manual_receipt_rewriting(tmp_path):
    from tests.operations.test_tcad_result_analysis import write_analysis
    system = analysis_system(tmp_path)
    catalog, runtime, root, request, _, _ = system
    worker, opened = open_analysis(system)
    scratch = Path(opened["output_directory"]).parent / "scratch"
    scratch.mkdir(exist_ok=True)
    raw = runtime.artifacts.read(system[4]["reference"].ref)
    (scratch / "analysis.py").write_text("# Identity-copy fixture; publication makes no execution claim.\n")
    (scratch / "derived.csv").write_bytes(raw)
    published = worker.call_tool("worker_analysis_publish_files", dict(source_aliases=["reference_material"],
        script_path="scratch/analysis.py", files=[dict(path="scratch/derived.csv", media_type="text/csv")],
        method="Identity copy to exercise retained script/data dependencies."))
    score_request = raw_request()
    score_request["sources"][1]["input_alias"] = published["files"][0]["evidence_alias"]
    result = worker.call_tool("worker_tcad_curve_score", dict(record_key="before_interruption", request=score_request))
    assert result["status"] == "computed", result
    report = cite(analysis_report(), result["calculation_ref"])
    write_analysis(opened, report)
    status = root.call_tool("run_status", {"name": "analysis"})
    failed = root.call_tool("run_record_failure", dict(name="analysis", reason="fixture interruption",
        expected_state="running", expected_last_activity_at=status["last_activity_at"]))
    assert failed["recovery"]["draft_available"]
    second = deepcopy(request); second.update(name="resumed_analysis", draft_from="analysis")
    next_worker, next_opened = open_analysis((catalog, runtime, root, second, *system[4:]))
    # Reopening must preserve dependencies even when every file is already adopted.
    next_opened = next_worker.call_tool("worker_open_assignment", {})
    assert next_worker.runs.tool_attempts(next_worker._run_id) == []
    derived = next_worker.runs.read_tool_evidence(next_worker.runs.status(next_worker._run_id),
        published["files"][0]["evidence_alias"])
    assert derived == raw
    assert submit(next_worker, next_opened, report)["state"] == "completed"
