"""One derived owner entry; originals and complete tool contracts stay on demand."""
from __future__ import annotations

import json
from pathlib import Path

from ..schema.common import canonical_json
from .local_workspace import WorkspaceError, read_control_workspace_file, write_control_workspace_file
from ..schema.role_result import REFERENCE_MARKER, split_reference
from .input_reader import (shared_input, MATERIAL_FILE_READING, SCIENTIFIC_PAGE_MIN_BYTES,
    SCIENTIFIC_PAGE_MAX_BYTES, SCIENTIFIC_PAGE_DEFAULT_BYTES)
GUIDE_READ = 'python tools/read_input.py worker-context.json --file --pointer /guides/'
GROUP_MEMBER_LIMIT = 16


READER_CORE = ('Read with python tools/read_input.py SOURCE (exact source_name): its sealed overview when '
    'scientific_overview_available, else page 1; overviews are partial. --directory lists fields; repeatable --pointer /FIELD '
    'selects exact original content; --full reads the whole original; --budget {low}..{high} (default {default}). Each page '
    'ends with its continuation (--selection, --offset, next_offset). Expand fields needed for claims, limitations and '
    'contrary evidence; originals support conclusions and reading grants no qualification; artifact_name is navigation only. '
    'Recovery and alias details: guide reader.')
TOOLS_CORE = ('Before calling a tool read its complete contract: python tools/read_tool_contract.py TOOL or '
    'scid_describe; retain unchanged contracts.')
SAME_SOURCE_CORE = (' same_source_as names the representative of one exact frozen original: read it once. Each alias keeps '
    'its own purpose and citation permissions; equivalence grants no review or qualification.')


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


def _group_members(document: dict, group: dict) -> dict:
    """Every member once with its exact source_name; shared display fields stated once."""
    members = []
    for pointer in group['pointers']:
        item = dict(document['inputs'][int(pointer.rsplit('/', 1)[1])])
        if item.get('materialization') is not None:
            # A stream-only metadata path is not a readable location.
            item.pop('relative_path', None)
        item.pop('artifact_name', None)  # Navigation only; complete metadata stays at the pointer.
        members.append(item)
    common = {key: members[0][key] for key in ('description', 'artifact_name_usage', 'exposure', 'historical',
        'materialization', 'materialize_tool', 'media_type', 'reference_availability', 'schema_id', 'usage')
        if key in members[0] and all(key in item and item[key] == members[0][key] for item in members)}
    return dict(group, **common,
        members=[{key: value for key, value in item.items() if key not in common} for item in members])


def _with_input_groups(document: dict, assignment: dict, members=False) -> dict:
    groups = assignment.get('input_groups', [])
    if not groups:
        return _with_input_templates(document)
    grouped = {pointer for group in groups for pointer in group['pointers']}
    candidate = dict(document, inputs=[item for index, item in enumerate(document['inputs'])
        if f'/inputs/{index}' not in grouped], reading=dict(document['reading']))
    candidate['input_groups'] = [_group_members(document, group)
        if members and len(group['pointers']) <= GROUP_MEMBER_LIMIT else dict(group, count=len(group['pointers']),
        read='python tools/read_input.py assignment.json --pointer ' + group['pointers'][0]) for group in groups]
    if all('members' in group for group in candidate['input_groups']):
        candidate['reading']['inputs'] += (
            ' input_groups list every member with its exact source_name, including failures, negative results and '
            'historical limitations; fields shared by all members are stated once on the group. Collections may be primary '
            'evidence; grouping implies no relevance or priority judgment. Inspect the members needed for your claims and '
            'contrary evidence. Complete frozen metadata: python tools/read_input.py assignment.json --pointer POINTER '
            '(repeatable). Ungrouped inputs alone do not prove complete evidence coverage.')
        candidate = _with_input_templates(candidate)
        original = _with_input_templates(document)
        return candidate if len(canonical_json(candidate)) < len(canonical_json(original)) else original
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


INLINE_ITEM_BYTES, INLINE_TOTAL_BYTES = 512, 4096
LEDGER_VIEW_BYTES, INVENTORY_BYTES, OVERVIEW_ENTRIES = 32 * 1024, 256 * 1024, 64
OBSERVED_TOTAL_BYTES = 24 * 1024
OBSERVED_BASIS = ('Public capture-inventory projections and losslessly re-encoded derived ledger views of bound inputs. '
    'Values are author_reported and unverified; hypothesis association is unknown unless exactly declared. '
    'stage_materials: bound stage receipts whose exact materials include the entry ([] = none). '
    'source_name null: not bound to this task. A source absent here must be read as an original. '
    'reference values are the producing task\'s aliases (reference_namespace), not citations here; cite source_name. '
    'same_entry_as: the exact object is listed once, under that inventory.')


def _ledger_view(raw):
    """Exact lossless re-encoding: shared fields once, value columns once."""
    records = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    if not records or not all(isinstance(item, dict) and isinstance(item.get('values', {}), dict) for item in records):
        return None
    common = {key: value for key, value in records[0].items()
        if all(key in item and item[key] == value for item in records[1:])}
    columns = list(dict.fromkeys(key for item in records for key in item.get('values', {})))
    rows = []
    for item in records:
        row = {key: value for key, value in item.items() if key not in common}
        values = row.get('values')
        if isinstance(values, dict) and values and list(values) == columns:
            row['values'] = [values[key] for key in columns]
        rows.append(row)
    return dict(common=common, value_columns=columns, records=rows)


def _stage_material_refs(runs, record, raw):
    """Exact refs of one stage receipt's materials, resolved in its producer's own namespace."""
    body = json.loads(raw)
    aliases = list(body.get('materials') or ())
    comparison = body.get('comparison') or {}
    aliases += [comparison.get('prediction'), *(comparison.get('observations') or ())]
    sources = record.get('source_refs', {})
    return {sources[alias] for alias in aliases if isinstance(alias, str) and alias in sources}


def _support_marker(error):
    return 'unavailable:generation_error:' + type(error).__name__


def open_support(runs, status, assignment: dict) -> dict:
    """Mechanical startup support from exact bound refs; nothing is selected by name or recency.

    Each item is generated independently; a failure is an explicit support_status
    marker, never a silent absence. Bound originals remain readable either way.
    """
    visible = {item['source_name'] for item in assignment.get('inputs', ())}
    bindings = [item for item in status.inputs if item.source_name in visible and item.exposure != 'handoff_only']
    # One representative per exact ArtifactRef, preferring a directly readable alias.
    first, duplicates = {}, {}
    for item in sorted(bindings, key=lambda value: value.exposure == 'file_reference'):
        first.setdefault(item.artifact_ref, item.source_name)
    for item in bindings:
        if first[item.artifact_ref] != item.source_name:
            duplicates[item.source_name] = first[item.artifact_ref]
    support, marks = dict(exact_duplicates=duplicates), {}
    try:
        support['inline_inputs'] = _inline_inputs(runs, bindings, duplicates)
    except Exception as error:  # noqa: BLE001 - orientation never blocks open
        marks['inline_inputs'] = _support_marker(error)
    try:
        observed = _observed_results(runs, status, bindings, first, duplicates)
        if observed:
            support['observed_results'] = observed
    except Exception as error:  # noqa: BLE001
        marks['observed_results'] = _support_marker(error)
    if marks:
        support['support_status'] = dict(marks, basis='Listed startup aids were not generated; their content is '
            'unknown, not empty. Every bound original remains readable.')
    return support


def _inline_inputs(runs, bindings, duplicates):
    inline, total = {}, 0
    for item in bindings:
        if item.source_name in duplicates or not (item.media_type.startswith('text/') or item.media_type == 'application/json'):
            continue
        envelope = runs.artifacts.catalog(item.artifact_ref)
        if envelope.size_bytes > INLINE_ITEM_BYTES or total + envelope.size_bytes > INLINE_TOTAL_BYTES:
            continue
        try:
            inline[item.source_name] = runs.artifacts.read(item.artifact_ref).decode('utf-8')
        except (OSError, ValueError):
            continue  # Ordinary reading remains available.
        total += envelope.size_bytes
    return inline


def _observed_results(runs, status, bindings, first, duplicates):
    from ..schema.refs import ArtifactRef
    from .sealed_materials import resolve_material
    from ...operation_contract import DiagnosticError
    inventories, stages, unresolved = [], [], []
    for item in bindings:
        if item.source_name in duplicates or item.media_type != 'application/json':
            continue
        if runs.artifacts.catalog(item.artifact_ref).labels.get('tool_producer_run') is None:
            continue
        try:
            record = resolve_material(runs, status, item.source_name)
        except DiagnosticError:
            unresolved.append(dict(source_name=item.source_name, reason='material_receipt_unverifiable'))
            continue  # Keep unknown receipt provenance explicit; ordinary original reading remains available.
        kind = (record or {}).get('metadata', {}).get('kind')
        if kind == 'capture_inventory':
            inventories.append((item, record))
        elif kind == 'experiment_stage':
            try:
                stages.append((item.source_name, _stage_material_refs(runs, record, runs.artifacts.read(item.artifact_ref))))
            except (OSError, ValueError, AttributeError, TypeError):
                stages.append((item.source_name, None))
    sources, omitted, size, seen = [], unresolved, 0, {}
    for item, record in inventories:
        private = record['metadata'].get('capture_map') or {}
        if runs.artifacts.catalog(item.artifact_ref).size_bytes > INVENTORY_BYTES:
            omitted.append(dict(source_name=item.source_name, reason='inventory_too_large'))
            continue
        try:
            public = json.loads(runs.artifacts.read(item.artifact_ref))
        except (OSError, ValueError):
            omitted.append(dict(source_name=item.source_name, reason='inventory_unreadable'))
            continue
        entries, mapped = public.get('entries', []), private.get('entries', [])
        if (len(entries) != len(mapped) or len(entries) > OVERVIEW_ENTRIES
                or any(a.get('path') != b.get('path') for a, b in zip(entries, mapped))):
            omitted.append(dict(source_name=item.source_name, reason='inventory_not_overviewable'))
            continue
        overview = {key: public[key] for key in ('coverage', 'coverage_changed', 'attempt_inventory', 'roots',
            'source_declarations') if key in public}
        # reference values belong to the producing task's namespace, never this task's citations.
        overview['reference_namespace'] = 'producer_task'
        shown, ledgers = [], []
        inventory_seen = dict(seen)  # Commit only once this inventory is actually delivered.
        for entry, original in zip(entries, mapped):
            entry = dict(entry)
            ref = ArtifactRef.model_validate(original['artifact_ref']) if original.get('artifact_ref') else None
            if ref is not None and ref in inventory_seen:
                # The same exact object was already listed by another inventory: one copy.
                shown.append(dict(path=entry.get('path'), status=entry.get('status'), same_entry_as=inventory_seen[ref]))
                continue
            if ref is not None:
                inventory_seen[ref] = item.source_name
            entry['source_name'] = first.get(ref) if ref is not None else None
            if stages and ref is not None:
                entry['stage_materials'] = [name for name, refs in stages if refs and ref in refs]
            if (entry['source_name'] is not None and entry.get('representation') == 'derived_projection'
                    and runs.artifacts.catalog(ref).size_bytes <= LEDGER_VIEW_BYTES):
                try:
                    view = _ledger_view(runs.artifacts.read(ref))
                except (OSError, ValueError):
                    view = None
                locators = [row.get('locator', (view or {}).get('common', {}).get('locator'))
                    for row in (view or {}).get('records', ())]
                if view is not None and locators == [row.get('locator') for row in entry.get('record_positions', ())]:
                    # Records carry the same locators and statuses: one copy, in the ledger view.
                    entry.pop('record_positions', None)
                    ledgers.append(dict(source_name=entry['source_name'], kind='ledger_view', **view))
            shown.append(entry)
        if not stages:
            overview['stage_materials'] = 'unknown_no_bound_stage_receipt'
        elif any(refs is None for _, refs in stages):
            overview['stage_materials'] = 'incomplete_unreadable_stage_receipt: ' + ', '.join(
                name for name, refs in stages if refs is None)
        candidates = [dict(source_name=item.source_name, kind='capture_inventory', **overview, entries=shown)]
        candidates += [ledger for ledger in ledgers if ledger['source_name'] not in {s['source_name'] for s in sources}]
        for candidate in candidates:
            cost = len(canonical_json(candidate))
            if size + cost > OBSERVED_TOTAL_BYTES:
                omitted.append(dict(source_name=candidate['source_name'], reason='overview_byte_limit'))
                continue
            size += cost
            sources.append(candidate)
            if candidate['kind'] == 'capture_inventory':
                seen = inventory_seen
    if not sources and not omitted:
        return None
    result = dict(basis=OBSERVED_BASIS, sources=sources)
    if omitted:
        result['omitted'] = omitted
        result['omitted_read'] = ('Each omitted source is a bound original. For input exposure=file_reference, '
            'call worker_materialize_input(source_name=SOURCE_NAME) then read its returned relative_path; '
            'otherwise python tools/read_input.py SOURCE_NAME --full.')
    return result


def startup_document(assignment: dict, domain: dict | None = None, *, reader_navigation=4, reader_directory_details=True,
                     reader_scientific_view=False, on_demand=False) -> dict:
    # No independent contract registry or scientific summarization. Copy complete
    # instructions from the frozen assignment and plugin manifest, once per view.
    # on_demand (current reader only) delivers each exact object once: tiny
    # originals inline, other originals and unneeded complete guides by locator.
    result = {key: assignment[key] for key in (
        'operation', 'instruction', 'scientific_intent', 'role_instructions', 'narrative_instruction',
        'execution_requirements', 'task_network_policy',
    ) if assignment.get(key) is not None}
    duplicates = assignment.get('exact_duplicates', {}) if on_demand else {}
    inline = assignment.get('inline_inputs', {}) if on_demand else {}
    inputs = [dict(item, same_source_as=duplicates[item['source_name']])
        if item.get('source_name') in duplicates and 'same_source_as' not in item else item
        for item in assignment.get('inputs', ())]
    guides = {}
    frozen_role_note = None
    if on_demand and isinstance(result.get('role_instructions'), str):
        # Complete detailed rules stay in assignment.json and one exact read away.
        core, sections = split_reference(result['role_instructions'])
        if sections:
            result['role_instructions'] = core
            guides['role_reference'] = sections
    elif isinstance(result.get('role_instructions'), str) and REFERENCE_MARKER in result['role_instructions']:
        # A frozen reader keeps the exact complete text; say where its [name] sections are.
        frozen_role_note = ('role_instructions is complete here: each checklist [name] refers to the ## name section '
            'after [[on-demand reference]] in the same text; there is no separate guide for this reader.')
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
        elif item.get('source_name') in duplicates:
            # An exact streamed duplicate: its representative entry carries the bytes.
            item = {key: value for key, value in item.items()
                if key not in {'relative_path', 'media_type', 'schema_id', 'size_bytes', 'artifact_name'}}
        elif item.get('source_name') in inline:
            # Complete exact original no larger than its own index entry.
            item = dict(item, text=inline[item['source_name']])
        if reader_scientific_view and 'scientific_view' in item:
            item = {key: value for key, value in item.items() if key != 'scientific_view'}
            item['scientific_overview_available'] = True
        result['inputs'].append(item)
    result['output'] = {
        'relative_path': assignment.get('output', {}).get('relative_path', 'output/result.json'),
        'form': assignment.get('output', {}).get('schema_path', 'schema/result.schema.json'),
        'read': 'python tools/read_output_schema.py',
        'instruction': 'Read the default overview for required/optional fields and shared rules, then --field NAME '
            'for each authored payload field and its full reference closure (not the payload wrapper). '
            'Optional fields need not be filled merely because they exist. Preserve necessary evidence, limitations '
            'and conditional rules; control completes mechanical fields. Keep combined displays bounded. '
            'Retain unchanged definitions; refresh after schema changes or context loss. '
            '--full restores the complete form, including any handoff, when a contract question requires it.',
    }
    if 'worker_submit_result' in assignment.get('tools', ()):
        result['output']['submit'] = dict(name='worker_submit_result', arguments={})
        result['output']['closeout'] = (
            'Writing result.json leaves a draft. After a successful write, explicitly call scid_call with the '
            'submit arguments above immediately in the same code-mode call when available: await the write, '
            'then submission, then display state/diagnostics. A failed write must not submit. '
            'Only completed is sealed delivery; repair rejected drafts and explicitly resubmit. '
            'An uncertain submission must not be replayed; completion chat is transport only.')
    if 'worker_publish_files' in assignment.get('tools', ()):
        result['output']['attachments'] = (
            'Keep CSV/JSON/images/scripts and other deliverables below scratch/. Publish them with worker_publish_files '
            'using paths, scientific purpose and exact source aliases; control assigns types, hashes and bindings. '
            'Write only the form to output/result.json; do not put attachments in output/ or embed files in narrative fields. '
            'Publication retains bytes and provenance, not scientific validation. Returned references are reusable evidence.')
        if assignment.get('artifact_capture'):
            directories = assignment['artifact_capture']['directories']
            result['artifact_capture'] = dict(assignment['artifact_capture'])
            locations = ', '.join(directory + '/' for directory in directories)
            result['output']['attachments'] = (f'Write scientific files to the declared directories: {locations}; '
                'stages and final submission capture that declared scope. '
                f'Cite file:{directories[0]}/path, or file@<sealed-stage-reference>:{directories[0]}/path for an older version; '
                'declare actual batch sources with capture_sources when needed. run: is navigation only; scratch/cache/ and scratch/tmp/ are outside capture. '
                'worker_publish_files remains available for authorized explicit or early publication.')
            if assignment['artifact_capture'].get('ledgers'):
                result['output']['attachments'] += (' Host-declared logical ledgers are captured as safe derived views at these seals; '
                    'raw originals are unavailable and reported values remain unverified.')
    result['reading'] = {
        'inputs': 'JSON: locate needed fields with python tools/read_input.py SOURCE --directory, '
            'then exact --pointer selections. Use exact source_name in tools and citations; artifact_name is navigation only. '
            'Complete selected fields needed for claims, limitations and contrary evidence. Omitted originals remain unread; '
            'do not batch whole files. '
            + ('--directory lists current-layer field pointers, types and counts; arrays show index ranges, not elements. '
                'Inspect actual fields before combining displays; do not guess names. '
                if reader_directory_details else '--directory lists JSON keys; ')
            + f'Scientific pages accept --budget {SCIENTIFIC_PAGE_MIN_BYTES}..{SCIENTIFIC_PAGE_MAX_BYTES} bytes '
            f'(default {SCIENTIFIC_PAGE_DEFAULT_BYTES}); worker-start.json uses its separately configured startup page size. '
            '--pointer /FIELD is repeatable. Omit --pointer for the root; / selects an empty-key member. '
            + ('Every page, including end, returns --selection HANDLE --offset START --budget BYTES and optional next_offset. '
                'It replays that exact page after any other reads; set START to next_offset for the next page. '
                'Offsets count characters in the selected text; page limits count UTF-8 bytes including the marker. '
                'If navigation is lost, add the complete SOURCE/file/pointer/directory selection to --selection/--offset; '
                'changed sources require reselection at offset 0. '
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
            + 'Originals support conclusions; reading guidance grants no qualification.',
        'tools': 'Read only the selected complete contract with python tools/read_tool_contract.py TOOL '
            'or scid_describe, including inputSchema, definitions, defaults, limits and descriptions. '
            'JSON Patch responses reference the last full response, never a prior delta. '
            'Retain unchanged contracts; --full restores lost context.',
    }
    if reader_scientific_view:
        result['reading']['inputs'] = (
            'Read SOURCE once for its sealed scientific overview when scientific_overview_available is true: '
            'the producer handoff and declared exact fields support task orientation. Projected structures are partial; '
            'omitted originals remain unread. --full reads the original with pagination; explicit --pointer and '
            '--directory always select original content. Expand the fields needed for this task, including limitations '
            'and contrary evidence. Sources without a declared overview retain exact paged reading. '
            + result['reading']['inputs'])
    if on_demand and reader_navigation == 4 and reader_directory_details:
        # The complete guidance stays one exact read away; page replies print their own continuation.
        guides['reader'] = result['reading']['inputs']
        result['reading']['inputs'] = READER_CORE.format(low=SCIENTIFIC_PAGE_MIN_BYTES, high=SCIENTIFIC_PAGE_MAX_BYTES,
            default=SCIENTIFIC_PAGE_DEFAULT_BYTES)
    if any('text' in item for item in result['inputs']):
        result['reading']['inputs'] += ' An input text is its complete exact original.'
    if 'worker_experiment_execute' in assignment.get('tools', ()):
        result['reading']['execution'] = ('Before remote work read the complete worker_experiment_execute contract, '
            'including required review, authorization, uncertain submission and recovery rules. '
            'Native local work retains its declared permissions.')
    if 'worker_read_history' in assignment.get('tools', ()):
        result['reading']['history'] = ('attempt_memory is a bounded attributed overview, not consumed originals or verification. '
            'For older tasks read the complete worker_read_history contract, then follow next_before; '
            'preserve missing ancestry and exact revision_scope. Use declared reference tools for allowed originals '
            'or bind them as scientific inputs. Changed conditions may justify retry.')
    if any('same_source_as' in item for item in inputs):
        complete = (
            ' same_source_as identifies one frozen original under multiple visible aliases: use its representative reading entry once. '
            'Cross-alias selection reuses navigation only, not proof of reading; replay retained pages using the complete selection guidance above. '
            'Each alias retains its own purpose and citation permissions; equivalence grants no review or qualification.')
        if 'reader' in guides:
            guides['reader'] += complete
            result['reading']['inputs'] += SAME_SOURCE_CORE
        else:
            result['reading']['inputs'] += complete
    for key in ('tools', 'reference_access', 'attempt_memory', 'revision', 'recovery_draft', 'budget'):
        if assignment.get(key) is not None:
            result[key] = assignment[key]
    if (assignment.get('budget') or {}).get('checkpoint') is not None:
        result['reading']['checkpoint'] = (
            'budget.checkpoint and experiment tool replies carry the same calendar-fragment index and due flag; '
            'repeated indexes are one reminder, not new requests or scientific progress. At the next safe boundary, '
            'reassess your exact sealed stages and this task decision. If answered or evidence requires changing the '
            'hypothesis, mechanism, question, route or original criterion, safely seal a bounded final and explicitly '
            'submit for analysis. An affordable discriminating test within the original hypothesis and criteria may '
            'continue; ordinary score reordering alone does not require handoff. Preserve original criteria, failures '
            'and cumulative global history. The reminder grants no time, cancellation or replay authority; finish or '
            'reconcile accepted execution through existing controls, retaining unknown outcomes. It cannot interrupt '
            'a long native command. Final analysis requires completed output; a stage preview is not that output.')
    if domain:
        result['workspace'] = {key: domain[key] for key in ('manifest', 'paths', 'read_paths', 'patch_contract') if key in domain}
    if 'worker_materialize_input' in assignment.get('tools', ()):
        files = ('Inputs marked controlled_tool_stream_only are bound files, not missing evidence. '
            'Call worker_materialize_input with source_name and use its returned relative_path, not the metadata path. '
            + MATERIAL_FILE_READING + ' Keep combined displays bounded to avoid batch truncation; '
            'use native tools for PDFs/images/tables or necessary code/log review.')
        if on_demand and 'reader' in guides and not any(item.get('materialization') is not None for item in inputs):
            # No streamed input: the materialize reply repeats its reading guidance when used.
            guides['reader'] += ' Files: ' + files
        else:
            result['reading']['files'] = files
    if on_demand and 'reader' in guides:
        # Tool mechanics are owned by each complete tool contract; keep one copy on demand.
        detail = {'reading_tools': result['reading'].pop('tools', None), 'history': result['reading'].pop('history', None),
            'reference_access': result.pop('reference_access', None)}
        guides['tools'] = ' '.join(f'[{name}] {value}' for name, value in detail.items() if value)
        result['reading']['tools'] = TOOLS_CORE + (' worker_read_history pages are attributed navigation, not '
            'verified originals.' if detail['history'] else '') + (' worker_reference_read lists/reads allowed '
            'originals and boundary declarations of bound reports; availability is unknown until checked.'
            if detail['reference_access'] else '') + ' Details: guide tools.'
    if frozen_role_note and isinstance(result.get('reading'), dict):
        result['reading']['role'] = frozen_role_note
    for key in ('observed_results', 'support_status'):
        if assignment.get(key) and on_demand:
            result[key] = assignment[key]
    if guides:
        result['guides'] = [dict(name=name, size_bytes=len(text.encode('utf-8')), read=GUIDE_READ + name)
            for name, text in guides.items() if isinstance(text, str)]
        if 'role_reference' in guides:
            result['guides'].append(dict(name='role_reference', read=GUIDE_READ + 'role_reference/SECTION',
                sections={name: len(text.encode('utf-8')) for name, text in guides['role_reference'].items()},
                use='Read a section when its [name] checklist item applies; repeat --pointer to read several at once. The frozen assignment keeps the identical full text.'))
        result['_guide_texts'] = guides
    if not reader_navigation:
        return _with_input_templates(result)
    return _with_input_groups(result, assignment, members=on_demand)


def compact_startup_document(document: dict) -> dict:
    """Task, permissions and exact input inventory first; optional detail by pointer."""
    from .attempt_memory import memory_navigation
    result = dict(document)
    detail = lambda pointer: 'python tools/read_input.py worker-context.json --file --pointer ' + pointer
    if 'attempt_memory' in result:
        result['attempt_memory'] = memory_navigation(result['attempt_memory'],
            read=dict(command=detail('/attempt_memory'), meaning='Exact open-time overview; not consumed originals.'))
    return result


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
        reader_scientific_view = b'\nSCIENTIFIC_COMPACT_VIEW = 1\n' in helper
    except (OSError, ValueError, WorkspaceError):
        reader_navigation = 0
        reader_directory_details = False
        reader_scientific_view = False
    # Keep task/input/form order in this derived entry, ahead of historical attempts.
    document = startup_document(assignment, domain, reader_navigation=reader_navigation,
        reader_directory_details=reader_directory_details, reader_scientific_view=reader_scientific_view,
        on_demand=reader_navigation == 4)
    # Memory is refreshed at open time; assignment.json retains its original
    # snapshot. Save omitted context before advertising exact read pointers.
    context = {key: document[key] for key in ('attempt_memory',) if key in document}
    if '_guide_texts' in document:
        context['guides'] = document.pop('_guide_texts')
    write_control_workspace_file(workspace.root, Path('worker-context.json'), canonical_json(context),
        replace=True, mode=0o400)
    if reader_navigation == 4:
        document = compact_startup_document(document)
    return write_control_workspace_file(workspace.root, Path('worker-start.json'),
        json.dumps(document, ensure_ascii=False, allow_nan=False,
            separators=(',', ':')).encode('utf-8'), replace=True, mode=0o400)
