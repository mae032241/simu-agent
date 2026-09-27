"""One derived owner entry; originals and complete tool contracts stay on demand."""
from __future__ import annotations

import json
from pathlib import Path

from ..schema.common import canonical_json
from .local_workspace import read_control_workspace_file, write_control_workspace_file


def startup_document(assignment: dict, domain: dict | None = None) -> dict:
    # No independent contract registry or scientific summarization. Copy complete
    # instructions from the frozen assignment and plugin manifest, once per view.
    result = {key: assignment[key] for key in (
        'operation', 'instruction', 'role_instructions', 'narrative_instruction',
        'budget', 'inputs', 'reference_access', 'revision', 'recovery_draft', 'tools',
    ) if assignment.get(key) is not None}
    result['output'] = {
        'relative_path': assignment.get('output', {}).get('relative_path', 'output/result.json'),
        'form': assignment.get('output', {}).get('schema_path', 'schema/result.schema.json'),
        'read': 'python tools/read_output_schema.py',
        'instruction': 'This is the authoring form. Supply only its fields; control completes mechanical fields. '
            '--field NAME selects a payload field (not the payload wrapper). --full reads the complete authoring form, '
            'including any required handoff. Combine needed fields in one call. The reader supplements retained definitions; '
            'refresh after schema changes or context loss. Read field meanings, shared rules and reference definitions before writing.',
    }
    result['reading'] = {
        'inputs': 'Use source_name with python tools/read_input.py SOURCE. --directory lists JSON keys; '
            '--pointer /FIELD selects a known field (repeat for multiple fields). Omit --pointer to read the root; / is an empty-key member. '
            'Continue with bare --next; --repeat recovers a lost reply and --restart rereads the selection. '
            'Follow remaining pages; originals, not excerpts, support conclusions. Use source_name in tools and citations; artifact_name is navigation only.',
        'tools': 'Read only the selected complete contract with python tools/read_tool_contract.py TOOL '
            'or scid_describe, including inputSchema, definitions, defaults, limits and descriptions. '
            'JSON Patch responses reference the last full response, never a prior delta. '
            'Retain unchanged contracts; --full restores lost context.',
    }
    if domain:
        result['workspace'] = {key: domain[key] for key in ('manifest', 'paths', 'read_paths', 'patch_contract') if key in domain}
    return result


def write_worker_start(workspace, assignment: dict) -> Path:
    domain = None
    if workspace.domain_workspace_path is not None:
        domain = json.loads(read_control_workspace_file(workspace.root,
            Path('domain-workspace.json'), max_bytes=1024 * 1024))
    return write_control_workspace_file(workspace.root, Path('worker-start.json'),
        canonical_json(startup_document(assignment, domain)), replace=True, mode=0o400)
