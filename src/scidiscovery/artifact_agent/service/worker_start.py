"""One derived owner entry; originals and complete tool contracts stay on demand."""
from __future__ import annotations

import json
from pathlib import Path

from ..schema.common import canonical_json
from .local_workspace import WorkspaceError, read_control_workspace_file, write_control_workspace_file
from .input_reader import (shared_input, MATERIAL_FILE_READING, SCIENTIFIC_PAGE_MIN_BYTES,
    SCIENTIFIC_PAGE_MAX_BYTES, SCIENTIFIC_PAGE_DEFAULT_BYTES)


def _with_input_templates(document: dict) -> dict:
    inputs = document['inputs']
    groups = {}
    for index, item in enumerate(inputs):
        if isinstance(item.get('description'), str):
            groups.setdefault(item['description'], []).append(index)
    projected, templates = list(inputs), []
    fields = ('description', 'artifact_name_usage', 'materialization', 'materialize_tool', 'usage', 'exposure', 'historical',
        'reference_availability')
    for positions in groups.values():
        if len(positions) < 2:
            continue
        items = [inputs[index] for index in positions]
        first = items[0]
        common = {key: first[key] for key in fields if key in first and isinstance(first[key], (str, bool))
            and all(key in item and type(item[key]) is type(first[key]) and item[key] == first[key] for item in items)}
        compact = [{**{key: value for key, value in item.items() if key not in common}, 'template': len(templates)}
            for item in items]
        if len(canonical_json(compact)) + len(canonical_json(common)) >= len(canonical_json(items)):
            continue
        templates.append(common)
        for index, item in zip(positions, compact):
            projected[index] = item
    if templates:
        reading = dict(document['reading'])
        candidate = dict(document, inputs=projected, reading=reading)
        candidate['input_templates'] = templates
        reading['inputs'] += (' Each input inherits omitted fields from input_templates at its own template value '
            '(zero-based, not its inputs position); explicit item fields take precedence. Shared display rules do not imply '
            'a common source, port, permission or validation. Use each exact source_name; artifact_name stays in that entry.')
        # Include template references and their one-time explanation in the net
        # size check; small indexes keep the original flat display.
        if len(canonical_json(candidate)) < len(canonical_json(document)):
            return candidate
    return document


def _with_input_groups(document: dict, assignment: dict) -> dict:
    groups = assignment.get('input_groups', [])
    if not groups:
        return _with_input_templates(document)
    grouped = {pointer for group in groups for pointer in group['pointers']}
    candidate = dict(document, inputs=[item for index, item in enumerate(document['inputs'])
        if f'/inputs/{index}' not in grouped], reading=dict(document['reading']))
    candidate['input_groups'] = [dict(group, count=len(group['pointers']),
        read='python tools/read_input.py assignment.json --pointer ' + group['pointers'][0]) for group in groups]
    candidate['reading']['inputs'] += (
        ' input_groups retain every member of each derived collection, including failures, negative results and historical limitations. '
        'Collections may be primary evidence required for the conclusion; grouping implies no relevance or priority judgment. '
        'Inspect the groups needed for your claims and contrary evidence. '
        'Each exact pointer selects complete input metadata from frozen assignment.json; use a returned pointer with '
        'python tools/read_input.py assignment.json --pointer, then its source_name or controlled materialize tool. '
        'Repeat --pointer for selected entries; preserve pagination. Ungrouped inputs alone do not prove complete evidence coverage.')
    candidate = _with_input_templates(candidate)
    original = _with_input_templates(document)
    # Count complete UTF-8 views, including navigation and templates. Small
    # inventories keep the existing display rather than paying group overhead.
    return candidate if len(canonical_json(candidate)) < len(canonical_json(original)) else original


def startup_document(assignment: dict, domain: dict | None = None, *, reader_navigation=4, reader_directory_details=True) -> dict:
    # No independent contract registry or scientific summarization. Copy complete
    # instructions from the frozen assignment and plugin manifest, once per view.
    result = {key: assignment[key] for key in (
        'operation', 'instruction', 'scientific_intent', 'role_instructions', 'narrative_instruction',
        'execution_requirements', 'task_network_policy',
    ) if assignment.get(key) is not None}
    inputs = assignment.get('inputs', ())
    result['inputs'] = []
    for item in inputs:
        representative = shared_input(inputs, item)
        if representative is not None and representative is not item:
            # Preserve each alias's purpose, provenance and citation permissions.
            # Only repeated readable metadata moves to the single representative.
            shared = {'relative_path', 'media_type', 'schema_id', 'size_bytes'}
            if item.get('reference_availability') == representative.get('reference_availability'):
                shared.add('reference_availability')
            item = {key: value for key, value in item.items() if key not in shared}
        result['inputs'].append(item)
    result['output'] = {
        'relative_path': assignment.get('output', {}).get('relative_path', 'output/result.json'),
        'form': assignment.get('output', {}).get('schema_path', 'schema/result.schema.json'),
        'read': 'python tools/read_output_schema.py',
        'instruction': 'Start with the default reader overview: it gives required fields, optional fields and shared rules. '
            'Supply fields needed for your scientific conclusions; optional fields need not be filled merely because they exist. '
            'Preserve necessary evidence, limitations and applicable conditional rules; control completes mechanical fields. '
            '--field NAME selects a payload field (not the payload wrapper). After context loss, restart with the overview '
            'and needed fields. --full reads the complete authoring form, including any required handoff; '
            'use it only when a specific unresolved contract question requires complete inspection, not as the default. '
            'Combine only needed fields; keep combined native output bounded. The reader supplements retained definitions; '
            'refresh after schema changes or context loss. Read field meanings, shared rules and reference definitions before writing.',
    }
    if 'worker_submit_result' in assignment.get('tools', ()):
        result['output']['submit'] = dict(name='worker_submit_result', arguments={})
        result['output']['closeout'] = (
            'Writing result.json leaves a draft. When your evidence assessment and draft are ready, explicitly call '
            'scid_call with the submit arguments above immediately after the successful write, in the same code-mode '
            'call when available: await the write, then await submission, then display its returned state/diagnostics. '
            'Do not wait for another model turn just to submit. A failed write must not submit. '
            'Only completed is sealed delivery; repair a rejected draft and explicitly resubmit. '
            'An uncertain submission is not permission to replay it; completion chat is not submission.')
    if 'worker_publish_files' in assignment.get('tools', ()):
        result['output']['attachments'] = (
            'Keep CSV/JSON/images/scripts and other deliverables below scratch/. Publish them with worker_publish_files '
            'using paths, scientific purpose and exact source aliases; control assigns types, hashes and bindings. '
            'Write only the form to output/result.json; do not put attachments in output/ or embed files in narrative fields. '
            'Publication retains bytes and provenance, not scientific validation. Returned references are reusable evidence.')
    result['reading'] = {
        'inputs': 'For JSON, first locate needed fields with python tools/read_input.py SOURCE --directory, '
            'then read exact --pointer selections. Use each returned source_name; review complete originals when necessary '
            'through bounded pages rather than batching whole files into one native output. '
            + ('--directory lists current-layer field pointers, types and counts; arrays show index ranges, not elements. '
                'Exact byte sizes are not computed. Inspect actual fields before combining displays; do not filter by guessed names. '
                if reader_directory_details else '--directory lists JSON keys; ')
            + f'Scientific pages accept --budget {SCIENTIFIC_PAGE_MIN_BYTES}..{SCIENTIFIC_PAGE_MAX_BYTES} bytes '
            f'(default {SCIENTIFIC_PAGE_DEFAULT_BYTES}); worker-start.json uses its separately configured startup page size. '
            '--pointer /FIELD selects a known field (repeat for multiple fields). Omit --pointer to read the root; / is an empty-key member. '
            + ('Every page, including end, returns --selection HANDLE --offset START --budget BYTES and optional next_offset. '
                'The command replays that exact page after any other reads; change START to next_offset for the next page. '
                'Offsets count characters in the selected text; page limits count UTF-8 bytes including the marker. '
                'Read only the source fields needed for your claims; there is no requirement to traverse unrelated fields. '
                'If navigation is lost, add the complete SOURCE/file/pointer/directory selection to the retained --selection/--offset command; '
                'a changed source requires reselecting it at offset 0. '
                if reader_navigation == 4 else
                'This frozen reader uses explicit continuation: repeat the same SOURCE, --file, all --pointer and '
                '--directory flags and the page --budget with --next/--repeat/--restart. '
                'After parallel or interleaved reads, do not use bare navigation or change field flags. '
                'Version 3 also accepts its returned --selection handle with those navigation flags; '
                'use explicit selection for alias recovery notices and end pages that lack a handle. '
                if reader_navigation == 3 else
                'This frozen reader uses explicit continuation: repeat the same SOURCE, --file, all --pointer and '
                '--directory flags and the page --budget with --next/--repeat/--restart. '
                'After parallel or interleaved reads, do not use bare navigation or change field flags. ')
            + 'Complete the selected content needed for your claims; originals support conclusions. Use source_name in tools and citations; artifact_name is navigation only.',
        'tools': 'Read only the selected complete contract with python tools/read_tool_contract.py TOOL '
            'or scid_describe, including inputSchema, definitions, defaults, limits and descriptions. '
            'JSON Patch responses reference the last full response, never a prior delta. '
            'Retain unchanged contracts; --full restores lost context.',
    }
    if 'worker_experiment_execute' in assignment.get('tools', ()):
        result['reading']['execution'] = ('Before remote work read the complete worker_experiment_execute contract, '
            'including required review, authorization, uncertain submission and recovery rules. '
            'Native local work retains its declared permissions.')
    if 'worker_read_history' in assignment.get('tools', ()):
        result['reading']['history'] = ('attempt_memory is a bounded attributed overview, not consumed originals or verification. '
            'For older tasks read the complete worker_read_history contract, then follow next_before; '
            'preserve missing ancestry and exact revision_scope. Use declared reference tools for allowed originals '
            'or bind them as scientific inputs. Changed conditions may justify retry.')
    if any('same_source_as' in item for item in assignment.get('inputs', ())):
        result['reading']['inputs'] += (
            ' same_source_as identifies one frozen original under multiple visible aliases: use its representative reading entry once. '
            'Cross-alias selection reuses navigation only, not proof of reading; replay retained pages using the complete selection guidance above. '
            'Each alias retains its own purpose and citation permissions; equivalence grants no review or qualification.')
    for key in ('tools', 'reference_access', 'attempt_memory', 'revision', 'recovery_draft', 'budget'):
        if assignment.get(key) is not None:
            result[key] = assignment[key]
    if domain:
        result['workspace'] = {key: domain[key] for key in ('manifest', 'paths', 'read_paths', 'patch_contract') if key in domain}
    if 'worker_materialize_input' in assignment.get('tools', ()):
        result['reading']['files'] = (
            'Inputs marked controlled_tool_stream_only are bound files, not missing evidence. '
            'Call worker_materialize_input with source_name and use its returned relative_path, not the metadata path. '
            + MATERIAL_FILE_READING + ' Keep combined displays bounded to avoid batch truncation; '
            'use native tools for PDFs/images/tables or necessary code/log review.')
    return _with_input_groups(result, assignment) if reader_navigation else _with_input_templates(result)


def write_worker_start(workspace, assignment: dict, *, startup_page_bytes=16384) -> Path:
    domain = None
    if workspace.domain_workspace_path is not None:
        domain = json.loads(read_control_workspace_file(workspace.root,
            Path('domain-workspace.json'), max_bytes=1024 * 1024))
    write_control_workspace_file(workspace.root, Path('tools/input-reader-settings.json'),
        canonical_json(dict(startup_page_bytes=startup_page_bytes)), replace=True, mode=0o400)
    # Existing workspaces retain their frozen helper bytes and compatible guidance.
    try:
        helper = read_control_workspace_file(workspace.root, Path('tools/read_input.py'), max_bytes=64 * 1024)
        reader_navigation = next((version for version in (4, 3, 2, 1)
            if f'\nREAD_INPUT_NAVIGATION = {version}\n'.encode() in helper), 0)
        reader_directory_details = b'\ndef directory_view(' in helper
    except (OSError, ValueError, WorkspaceError):
        reader_navigation = 0
        reader_directory_details = False
    # Keep task/input/form order in this derived entry, ahead of historical attempts.
    return write_control_workspace_file(workspace.root, Path('worker-start.json'),
        json.dumps(startup_document(assignment, domain, reader_navigation=reader_navigation,
            reader_directory_details=reader_directory_details), ensure_ascii=False, allow_nan=False,
            separators=(',', ':')).encode('utf-8'), replace=True, mode=0o400)
