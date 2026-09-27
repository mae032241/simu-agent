"""Preserve Agent-authored analysis scripts and derived files in the same Run."""
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from scidiscovery.plugin_runtime.workspace import WorkspaceError, read_control_workspace_file
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
        saved_script = context.publish_analysis_file(script, media_type="text/plain",
            kind="analysis_script", sources=sources, suffix=".py" if request.script_path.endswith(".py") else ".txt",
            metadata={"method": request.method, "execution_proof": "agent_reported", "file_name": Path(request.script_path).name})
        outputs = []
        for item, raw in files:
            suffix = {"text/csv": ".csv", "application/json": ".json", "text/plain": ".txt", "image/png": ".png"}[item.media_type]
            saved = context.publish_analysis_file(raw, media_type=item.media_type,
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
Cite calculation_ref aliases without copying tool records. Read selected originals
through worker_reference_read; control resolves provenance. A rejected or unavailable
calculation limits the conclusion, not submission of supported finite findings.
When built-in methods cannot express required selection/weighting, use permitted
bounded native analysis. Retain scripts and derived files with
worker_analysis_publish_files; its complete contract owns paths and size limits.
Explain method, selection, weighting and limitations once. Returned aliases support
scoring and later reference_material, not original solver_outputs. Publication proves
retained bytes and lineage, not execution or scientific validity. Distinguish
exploration from preregistered tests.
For reference/candidate comparisons, publish an overlay when bound data and an
available plotting implementation suffice; add residuals only when useful to the
judgment. Choose scales scientifically, label units/identities and actual comparison
domain, and cite each image's contribution. Plots supplement numbers and conclusions.
Test parsing and a small unit first. Save completed numerical units atomically and
plot from saved numbers; never refit merely to repair a plot. On rendering failure,
retain numbers/errors and retry plotting alone or deliver limitations. Reuse only
when inputs/method/parameters match; numerical changes recompute affected units,
retaining old versions. Partial files or exit success do not prove completed science.
Startup workspace/recovery sections own the optional launcher and saved-work
navigation. Budget remaining time for delivery; preserve completed units and gaps.
Timing, launcher, scoring and plots are not submission prerequisites.
"""


TOOL = WorkerToolDefinition(name="worker_analysis_publish_files",
    description="Retain a task-local analysis script and derived CSV/JSON/text/PNG files with declared source lineage. Returns reusable evidence aliases; does not execute code or attest its result. Script <=1 MiB; files <=16 MiB each, <=32 MiB per call, within the Run collection budget.",
    input_model=PublishAnalysisFiles, capability="analysis.publish_files", contextual_handler=publish_files,
    evidence_ports=("tool_evidence", "recovery_manifest_output"))
