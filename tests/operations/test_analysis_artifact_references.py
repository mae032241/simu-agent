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
    manifest = facade.call_tool('artifact_catalog', {
        'name': 'analysis.output.recovery_manifest', 'view': 'parents', 'parent_limit': 16})
    assert 'manifest_projection' not in manifest
    records = runtime.runs.tool_evidence(worker._run_id)
    assert len(records) == 3
    record = next(item for item in records if item['alias'] == published['script']['evidence_alias'])
    assert record['tool_name'] == 'worker_analysis_publish_files'
    assert record['metadata']['method'] == 'Tiny fixture unit; optional plot unavailable.'
    assert any(parent['artifact_name'] == 'analysis.output.' + record['alias'] for parent in manifest['parents'])
    assert 'artifact_ref' not in json.dumps(manifest)
    request = deepcopy(request); request['name'] = 'plot_continuation'
    reference = next(i for i in request['inputs'] if i['port'] == 'reference_material')
    retained = [published['script'], *published['files']]
    reference['artifact_names'].extend('analysis.output.' + item['evidence_alias'] for item in retained)
    following, reopened = open_analysis((catalog, runtime, facade, request, artifacts, register))
    next_root = Path(reopened['workspace_path']); next_scratch = next_root / 'scratch'
    bindings = runtime.runs.status(following._run_id).inputs
    assignment = json.loads(Path(reopened['assignment_path']).read_text())
    navigation = next(item for item in assignment['inputs']
        if item['artifact_name'] == 'analysis.output.' + published['script']['evidence_alias'])
    assert navigation['artifact_name_usage'] == 'navigation_only'
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
    with pytest.raises(DiagnosticError):
        following.call_tool('worker_analysis_publish_files', dict(
            source_aliases=[navigation['artifact_name']], script_path='scratch/analysis.py',
            files=[dict(path='scratch/plot.png', media_type='image/png')],
            method='Navigation names are not tool aliases.'))
    data_alias = next(i.source_name for i in bindings if i.artifact_ref == runtime.runs.source_descriptor(
        runtime.runs.status(worker._run_id), published['files'][0]['evidence_alias']).artifact_ref)
    plotted = following.call_tool('worker_analysis_publish_files', dict(source_aliases=[data_alias], script_path='scratch/analysis.py',
        files=[dict(path='scratch/plot.png', media_type='image/png')], method='Render saved fixture numbers without fitting.'))
    assert submit(following, reopened, cite(analysis_report(), plotted['files'][0]['evidence_alias']))['state'] == 'completed'
    # The fixture's numerical-method change does invalidate its affected checkpoint.
    subprocess.run([sys.executable, '-B', 'analysis.py', 'compute', 'fixture_v2'], cwd=next_scratch, check=True, timeout=5)
    assert (next_scratch / 'calls.txt').read_text() == '2'






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
    for file, original_path in zip([published["script"], *published["files"]],
                                   ("analysis.py", "selected.csv", "weighted.json"), strict=True):
        stored = worker.runs.read_tool_evidence(worker.runs.status(worker._run_id), file["evidence_alias"])
        assert "path" not in file
        assert stored == (scratch / original_path).read_bytes()


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
