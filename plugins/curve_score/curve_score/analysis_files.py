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
Cite a scoring/diagnostic tool's returned calculation_ref directly in evidence_keys,
or use it as the source_key/locator of an optional evidence item.
The control layer has already saved its complete record and receipt;
do not copy requests, digests, attempt metadata or result arrays into the report.
Keep calculation_records empty for new calls. A separate evidence or source_references
entry is optional; multiple locators for one source are allowed. Legacy inline records
remain readable. If a request is rejected before a calculation_ref exists, cite
tool_recovery_manifest and explain the reported failure; do not construct a
calculation record or copy the attempt receipt. To reuse a prior calculation, bind its saved calculation file
and the paired prior analysis/manifest with the original sources, then cite the
current file alias; receipt and historical alias handling belong to control.
When built-in tools cannot express a needed row selection, weighting or other
analysis method, use the allowed bounded native analysis tools. Preserve the
script and derived tables/results with worker_analysis_publish_files; its paths
are relative to the workspace root (scratch/analysis.py, scratch/results.csv),
files are at most 16 MiB each and 32 MiB per call,
and the script is at most 1 MiB. Cite source aliases and describe the scientific
method once. Returned derived-data aliases are readable by the scoring and
diagnostic tools immediately and can be bound in a later Run's reference_material
inventory; they are derived analysis data, not original solver_outputs. Publication
preserves bytes and declared derivation, not proof of execution or scientific
validity. Report weighting/selection rules and limitations; do not relabel an
exploratory curve statistic as a different preregistered statistic.

Preserve completed numerical work before optional plotting. Test parsing and one
small independent work unit first; atomically write each complete unit using a
temporary file followed by replace. Keep compute and plot entry points separate:
plot reads saved numbers and must never implicitly restart fitting. Check only the
plot library actually used, or choose an available implementation. A plot import
or rendering error permits a limited report with saved numbers and the concrete
error; repair and retry plotting alone. Missing plots do not erase numerical work.
Reuse a complete checkpoint only when its inputs, numerical method and parameters
still match. Plot-only changes do not invalidate numbers; numerical changes require
recomputing affected units and preserving the old version. Do not count partial
writes or process exit success as a completed scientific result.
Read domain-workspace.json for the optional local computation launcher. Its request
timeout is clipped to the current Run deadline minus your adjustable submission
reserve. Use measured work-unit time to choose the next bounded batch. Do not start
a retry that cannot fit; publish completed units and explain remaining work instead.
Timing, this launcher, scoring and plotting are not prerequisites to submission.
On a new Run, read assignment.recovery_draft and its coverage manifest before
continuing; use only that immutable subset, copied into the new scratch directory.
An empty new scratch directory says nothing about whether recovery was delivered.
"""

TOOL = WorkerToolDefinition(name="worker_analysis_publish_files",
    description="Retain a task-local analysis script and derived CSV/JSON/text/PNG files with declared source lineage. Returns reusable evidence aliases; does not execute code or attest its result. Script <=1 MiB; files <=16 MiB each, <=32 MiB per call, within the Run collection budget.",
    input_model=PublishAnalysisFiles, capability="analysis.publish_files", contextual_handler=publish_files,
    evidence_ports=("tool_evidence", "recovery_manifest_output"))
