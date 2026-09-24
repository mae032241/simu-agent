"""Optional inspection and acceptance of original terminal execution products."""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from scidiscovery.operations.tooling import WorkerToolDefinition
from scidiscovery.operation_declaration import schema_resource
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.artifact_agent.schema.refs import ArtifactRef
from scidiscovery.artifact_agent.service.run_outputs import RunCheckerError
from scidiscovery.artifact_agent.service.local_workspace import write_control_workspace_file
from .project_packager import ReviewedDeckPackage, TCADRuntimeManifest

class InspectRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    execution_result: str = 'execution_result'
    relative_path: str | None = Field(default=None,max_length=1024)

class AcceptRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    evidence_alias: str = Field(min_length=1,max_length=128)
    output_name: str = Field(min_length=1,max_length=256)
    rationale: str = Field(min_length=1,max_length=4096)
    evidence_aliases: list[str] = Field(min_length=1,max_length=16)

from scidiscovery.artifact_agent.service.tool_evidence import (
    ToolEvidenceManifest as RecoveryManifest, TOOL_EVIDENCE_SCHEMA as RECOVERY_SCHEMA,
)

EXECUTION_SCHEMA=canonical_json({'$id':'scidiscovery.execution-result','type':'object'}).decode()

class OutputInspectionService:
    def __init__(self, adapter): self.adapter=adapter

    def inspect(self, scope, relative_path, *, max_bytes, timeout=None, deadline_monotonic=None):
        if scope['executor'] != 'tcad_artifact:tcad':
            return {'status':'unsupported','reason':'execution_adapter'}
        if deadline_monotonic is None:
            deadline_monotonic=time.monotonic()+timeout
        return self.adapter.inspect_outputs(scope['external_run_id'],relative_path,max_bytes=max_bytes,
            deadline_monotonic=deadline_monotonic)


def _file(raw, context, alias):
    relative=Path('scratch/controlled-evidence')/alias
    write_control_workspace_file(context.workspace,relative,raw,replace=(context.workspace/relative).exists(),mode=0o400,create_parents=True)
    return str(context.workspace/relative)


def _inspect(context, source_alias, path, *, run_deadline, consume=None):
    try:
        context.input_ref(source_alias)
    except ValueError as error:
        if str(error) != "tool requested an undeclared Run input":
            raise
        return {"status": "unavailable", "reason": "execution_result_not_bound",
                "message": str(error), "source_alias": source_alias,
                "repair": "Root must register this exact execution with execution_outputs, then bind its result_artifact_name to the declared execution_result port in a new analysis Run. Frozen inputs cannot be amended; bounded analysis may state this limitation."}
    service=context.services.get('tcad.output_inspection')
    if service is None:
        return {'status':'unavailable','reason':'inspection_service_unavailable'}
    scope=context.execution_scope(source_alias)
    if scope['payload_ref'] != context.input_ref('reviewed_package'):
        return {'status':'unavailable','reason':'execution_project_mismatch'}
    package=ReviewedDeckPackage.model_validate_json(context.read_input('reviewed_package'),strict=True)
    budget=context.io_budget(reserve=True)
    started=time.monotonic()
    deadline=min(started+budget['remaining_seconds'],run_deadline)
    timeout=deadline-started
    if timeout < 1 or budget['remaining_bytes'] < 1:
        budget=context.io_budget(used_bytes=-budget['remaining_bytes'],used_seconds=-budget['remaining_seconds'])
        return {'status':'limit_exceeded','reason':'inspection_budget','budget':budget}
    project_remaining=max(0,package.project.resource_limits.max_output_bytes-(256*1024*1024-budget['remaining_bytes']))
    limit=min(32*1024*1024,budget['remaining_bytes'],project_remaining)
    if limit < 1:
        context.io_budget(used_bytes=-budget['remaining_bytes'],used_seconds=-budget['remaining_seconds'])
        return {'status':'limit_exceeded','reason':'project_output_budget'}
    transferred=limit if path is not None else 0
    def check_budget():
        if time.monotonic() >= deadline:
            error=TimeoutError("inspection IO budget exhausted during local evidence processing")
            error.timeout_kind="inspection_io"
            raise error
    try:
        response=service.inspect(scope,path,max_bytes=limit,deadline_monotonic=deadline)
        transferred=response.get('file',{}).get('size_bytes',0)
        if path is None and response.get('status')=='available':
            listed={item['relative_path'] for item in response.get('files',())}
            declarations=[]
            for output in package.project.expected_outputs:
                item={'output_name':output.name,'declared_path':output.relative_path,'listed':output.relative_path in listed}
                if len(declarations)>=256 or len(canonical_json({**response,'declared_outputs':declarations+[item]}))>60*1024:
                    break
                declarations.append(item)
            response.update(declared_outputs=declarations,declarations_truncated=len(declarations)<len(package.project.expected_outputs))
        check_budget()
        if consume is not None and response.get("status")=="available" and "file" in response:
            response=consume(response,check_budget)
        check_budget()
    finally:
        budget=context.io_budget(used_bytes=transferred-budget['remaining_bytes'],used_seconds=time.monotonic()-started-budget['remaining_seconds'])
    return {**response,'budget':budget}


def inspect_tool(request,context):
    run_deadline=time.monotonic()+context.remaining_seconds
    def consume(reply,check_budget):
        descriptor=reply['file']; path=Path(descriptor['local_path'])
        if path.is_symlink() or descriptor['size_bytes']>32*1024*1024:
            return {'status':'unavailable','reason':'file_scope_or_size'}
        chunks=[]; size=0; digest=hashlib.sha256()
        with path.open('rb') as stream:
            while True:
                check_budget()
                chunk=stream.read(min(1024*1024,32*1024*1024+1-size))
                check_budget()
                if not chunk:break
                size+=len(chunk); chunks.append(chunk); digest.update(chunk)
                if size>32*1024*1024:break
        raw=b''.join(chunks)
        if size!=descriptor['size_bytes'] or digest.hexdigest()!=descriptor['sha256']:
            return {'status':'changed_since_inspection','reason':'file_changed'}
        check_budget()
        record=context.accept_evidence(raw=raw,media_type=descriptor['media_type'],source_alias=request.execution_result,
            metadata={'relative_path':reply['relative_path'],'output_name':None,'historical_integrity':'not_attested'})
        check_budget()
        return {'status':'available','evidence_alias':record['alias'],'relative_path':reply['relative_path'],
                'sha256':descriptor['sha256'],'size_bytes':len(raw),'local_path':_file(raw,context,record['alias'])}
    try:
        response = _inspect(context,request.execution_result,request.relative_path,run_deadline=run_deadline,consume=consume)
        if request.relative_path is None and response.get('status') == 'available':
            raw = canonical_json(response)
            details = _file(raw, context, 'inspection-' + hashlib.sha256(raw).hexdigest() + '.json')
            response = dict(response)
            for field in ('files', 'declared_outputs'):
                items = response.get(field, [])
                response[field] = items[:10]
                response[field + '_omitted'] = max(0, len(items)-10)
            response['details_path'] = details
        return response
    except RunCheckerError:
        raise
    except Exception as error:
        if 'unknown runner tool' in str(error) or 'unsupported TCAD transport' in str(error):
            return {'status':'unsupported','reason':'inspection_transport_unsupported'}
        # The shared Worker boundary retains engineering causes and readable
        # diagnostics. A failed optional tool never fails scientific submission.
        raise


def accept_tool(request,context):
    run_deadline=time.monotonic()+context.remaining_seconds
    try:
        prior=next((r for r in context.evidence() if r['alias']==request.evidence_alias),None)
        if prior is None:
            return {'status':'not_found','reason':'candidate_not_inspected'}
        package=ReviewedDeckPackage.model_validate_json(context.read_input('reviewed_package'),strict=True)
        expected=next((e for e in package.project.expected_outputs if e.name==request.output_name),None)
        generated = None
        if expected is None and package.project.collect_generated_outputs:
            manifest=TCADRuntimeManifest.model_validate_json(context.read_input('runtime_manifest'),strict=True)
            generated=next((item for item in manifest.outputs if item.name==request.output_name
                and item.name=='generated_'+hashlib.sha256(item.relative_path.encode('utf-8')).hexdigest()),None)
        if expected is None and generated is None:
            return {'status':'not_found','reason':'output_not_in_capture_manifest'}
        declared_path=expected.relative_path if expected is not None else generated.relative_path
        media_type=expected.media_type if expected is not None else generated.media_type
        byte_limit=expected.max_bytes if expected is not None else package.project.resource_limits.max_output_bytes
        experiment_key=expected.experiment_key if expected is not None else None
        case_key=expected.case_key if expected is not None else None
        if generated is not None and prior['metadata']['relative_path']!=declared_path:
            return {'status':'not_found','reason':'output_path_mismatch'}
        def consume(reply,check_budget):
            for alias in request.evidence_aliases:
                check_budget(); context.read_evidence(alias)
            check_budget()
            raw=context.read_evidence(prior['alias'])
            check_budget()
            if len(raw)>byte_limit:
                return {'status':'limit_exceeded','reason':'project_output_bytes'}
            if reply['file']['sha256']!=prior['artifact_ref']['sha256'] or reply['file']['size_bytes']!=len(raw):
                return {'status':'changed_since_inspection','reason':'candidate_changed'}
            if generated is not None and (len(raw)!=generated.size_bytes or hashlib.sha256(raw).hexdigest()!=generated.sha256):
                return {'status':'changed_since_capture','reason':'manifest_digest_mismatch'}
            record=context.accept_evidence(raw=raw,media_type=media_type,metadata={**prior['metadata'],
                'output_name':request.output_name,'declared_path':declared_path,'rationale':request.rationale,
                'evidence_aliases':request.evidence_aliases,'experiment_key':experiment_key,'case_key':case_key})
            check_budget()
            return {'status':'accepted','evidence_alias':record['alias'],'output_name':request.output_name,
                    'local_path':_file(raw,context,record['alias']),'size_bytes':len(raw)}
        return _inspect(context,'execution_result',prior['metadata']['relative_path'],run_deadline=run_deadline,consume=consume)
    except ValueError as error:
        if 'ambiguous_mapping' in str(error):
            return {'status':'ambiguous_mapping','reason':'ambiguous_mapping'}
        if str(error) in {'file_bytes','metadata_bytes','evidence_budget'}:
            return {'status':'limit_exceeded','reason':str(error)}
        raise
    except RunCheckerError:
        raise
    except Exception as error:
        if 'unknown runner tool' in str(error) or 'unsupported TCAD transport' in str(error):
            return {'status':'unsupported','reason':'inspection_transport_unsupported'}
        raise

INSPECT_TOOL=WorkerToolDefinition(name='worker_tcad_inspect_outputs',description='Optionally list or inspect original files of the bound terminal execution_result. No solver, editing or renaming. A selected file yields a controlled evidence alias and read-only copy; unavailable inspection permits limited analysis.',input_model=InspectRequest,capability='tcad.analysis.inspect_outputs',contextual_handler=inspect_tool,optional_services=('tcad.output_inspection',),evidence_ports=('tool_evidence','recovery_manifest_output'))
ACCEPT_TOOL=WorkerToolDefinition(name='worker_tcad_accept_output',description='Accept a previously inspected file from the exact output capture manifest or a legacy declaration. Rechecks bytes and source path; no scientific success is granted.',input_model=AcceptRequest,capability='tcad.analysis.accept_output',contextual_handler=accept_tool,optional_services=('tcad.output_inspection',),evidence_ports=('tool_evidence','recovery_manifest_output'))
