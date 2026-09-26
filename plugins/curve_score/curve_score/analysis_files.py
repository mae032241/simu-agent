"""Preserve Agent-authored analysis scripts and derived files in the same Run."""
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from scidiscovery.artifact_agent.service.analysis_artifacts import publish_analysis_file
from scidiscovery.artifact_agent.service.local_workspace import WorkspaceError, read_control_workspace_file
from scidiscovery.operation_contract import DiagnosticError, contract_diagnostic
from scidiscovery.operations.tooling import WorkerToolDefinition

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


class AnalysisFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(description="Path relative to the opened workspace root, e.g. scratch/results.csv; regular file below scratch/, no symlinks.")
    media_type: Literal["text/csv", "application/json", "text/plain", "image/png"]


class PublishAnalysisFiles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_aliases: Annotated[tuple[str, ...], Field(min_length=1, max_length=40,
        description="Bound input or current/adopted tool-evidence aliases used by this derivation. Workspace helper indexes are not sources unless exposed as bound inputs or adopted evidence.")]
    script_path: str = Field(description="Path relative to the opened workspace root, e.g. scratch/analysis.py; UTF-8 script below scratch/. Publication does not attest execution.")
    files: Annotated[tuple[AnalysisFile, ...], Field(min_length=1, max_length=8)]
    method: Annotated[str, Field(min_length=1, max_length=1024,
        description="Short scientific method summary; full procedure belongs in the saved script and report.")]


def publish_files(request, context):
    """Seal declared local bytes, not a claim that the script was executed."""
    error_path = "$"
    try:
        sources = tuple(dict.fromkeys(request.source_aliases))
        for index, alias in enumerate(request.source_aliases):
            error_path = f"$.source_aliases[{index}]"
            context.source_descriptor(alias)
        error_path = "$"
        def read(name, limit, field):
            path = Path(name)
            if path.is_absolute() or not path.parts or path.parts[0] != "scratch":
                raise ValueError(f"{field}: path is relative to the workspace root and must start with scratch/ (e.g. scratch/analysis.py or scratch/results.csv)")
            return read_control_workspace_file(context.workspace, path, max_bytes=limit)
        script = read(request.script_path, 1024 * 1024, "script_path")
        script.decode("utf-8")
        # Admit the whole local byte set before registering any file.
        files = []
        total = len(script)
        for index, item in enumerate(request.files):
            raw = read(item.path, min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total), f"files[{index}].path")
            total += len(raw)
            if item.media_type != "image/png":
                raw.decode("utf-8")
            files.append((item, raw))
        saved_script = publish_analysis_file(context, script, media_type="text/plain",
            kind="analysis_script", sources=sources, suffix=".py" if request.script_path.endswith(".py") else ".txt",
            metadata={"method": request.method, "execution_proof": "agent_reported", "file_name": Path(request.script_path).name})
        outputs = []
        for item, raw in files:
            suffix = {"text/csv": ".csv", "application/json": ".json", "text/plain": ".txt", "image/png": ".png"}[item.media_type]
            saved = publish_analysis_file(context, raw, media_type=item.media_type,
                kind="analysis_derived", sources=(*sources, saved_script["evidence_alias"]), suffix=suffix,
                metadata={"script_alias": saved_script["evidence_alias"], "method": request.method,
                          "execution_proof": "agent_reported", "file_name": Path(item.path).name})
            outputs.append({**saved, "media_type": item.media_type})
        return {"status": "retained", "script": saved_script, "files": outputs,
                "execution_proof": "agent_reported"}
    except (ValueError, OSError, WorkspaceError) as error:
        raise DiagnosticError("analysis files could not be retained", details=(contract_diagnostic(
            "analysis_file_unavailable", phase="tool_execution", affected_action="tool_call",
            repairable=True, path=error_path, message=str(error)[:512]),)) from error


GUIDANCE = """
Cite returned calculation_ref in evidence_keys or optional evidence source_key/locator.
List the returned alias with worker_reference_read, then read its content reference.
Numerical evidence is sealed by the tool; reports cite its alias without copying records. If a tool rejects the
request, report its reason and scientific limitation. For historical reuse, select the
prior analysis and use its cited scientific materials; original provenance is resolved
by the service.

When built-in methods cannot express required selection or weighting, use permitted
bounded native analysis. Preserve scripts and derived results with
worker_analysis_publish_files; read its contract for workspace-relative paths and
size limits. Cite sources and explain method/selection/weighting and limits once.
Returned data aliases are immediately usable for scoring/diagnostics and later
reference_material, not original solver_outputs. Publication proves retained bytes
and lineage, not execution or scientific validity. Do not relabel exploratory
statistics as preregistered tests.

When the scientific judgment compares reference and candidate curves and bound data
and an available plotting implementation are sufficient, publish a reference/candidate
overlay PNG by default. Add a residual plot only when its distribution affects the
judgment. Choose the scale and residual definition scientifically. Axes must state
units, legends must bind curve identities, and plotted bounds must equal the actual
comparison domain. Cite each returned image evidence alias in the formal report and
state which conclusion or limitation it supports. Plots supplement numerical records,
sources and the formal conclusion; they never replace them.

Before plotting, test parsing and one small work unit; atomically save each completed
unit (temporary file then replace). Separate compute from plot: plot reads saved
numbers, never implicitly refits. Check only needed plotting dependencies or use an
available implementation. On import/render failure preserve numbers and the exact
error; report why the figure is absent, then retry plotting alone or deliver limited
findings. Reuse checkpoints only when inputs/method/parameters match; numerical changes
recompute affected units and retain old versions. Partial writes and process exit
success are not completed science.

Read domain-workspace.json for the optional observed computation launcher. Timeout is
clipped to the Run deadline minus adjustable submission reserve. Use measured unit
time for bounded batches; if retry cannot fit, publish completed units and gaps.
Timing, launcher, scoring and plots are not submission prerequisites. On continuation,
read assignment.recovery_draft and its coverage manifest; use only that immutable
subset copied to new scratch. Empty scratch does not establish missing recovery.
"""

TOOL = WorkerToolDefinition(name="worker_analysis_publish_files",
    description="Retain a task-local analysis script and derived CSV/JSON/text/PNG files with declared source lineage. Returns reusable evidence aliases; does not execute code or attest its result. Script <=1 MiB; files <=16 MiB each, <=32 MiB per call, within the Run collection budget.",
    input_model=PublishAnalysisFiles, capability="analysis.publish_files", contextual_handler=publish_files,
    evidence_ports=("tool_evidence", "recovery_manifest_output"))
