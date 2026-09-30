"""Local S0 review aids. Text matches locate evidence; they never grade science.

CAS outputs are payloads. Stage content is selected by the existing tool receipt,
and final Run selection is a reviewer interpretation of an exact Root record.
Nothing here creates a production adoption, approval, task or execution.
"""
import hashlib
import json
import math
import random
import re
from pathlib import Path

try:
    from scripts.b6_evidence import digest, read, rows, verdict, write
except ModuleNotFoundError:
    from b6_evidence import digest, read, rows, verdict, write


REPORT = 'scidiscovery.experiment-report.v1'
INTAKE = 'scidiscovery.scientific-intake.v1'
FOUNDATION = 'scidiscovery.scientific-foundation.v1'
STAGE_KINDS = {'experiment_stage', 'experiment_implementation', 'experiment_debug', 'experiment_execution'}


def cas_payload(candidate, ref):
    path = Path(candidate)/'state/artifacts/sha256'/ref['sha256'][:2]/ref['sha256'][2:]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('sealed_bytes_mismatch')
    return json.loads(raw), str(path)


def decision_fields(payload, schema, *, kind=None):
    """Only declared scientific paths, without searching recursively for keys."""
    fields = {}
    if schema == REPORT:
        names = ('summary', 'outcome', 'limitations', 'remaining_question', 'adopted_stages')
    elif kind == 'experiment_stage':
        names = ('stage', 'conclusion', 'limitations', 'remaining_question', 'materials')
    elif kind == 'experiment_implementation':
        names = ('implementation', 'scientific_files')
    elif kind == 'experiment_debug':
        names = ('state', 'mode', 'summary', 'exit_code', 'missing_outputs')
    elif kind == 'experiment_execution':
        names = ('name', 'state', 'terminal_state', 'outputs')
    elif schema in {INTAKE, FOUNDATION}:
        foundation = payload.get('scientific_foundation', {}) if schema == INTAKE else payload
        prefix = '/scientific_foundation' if schema == INTAKE else ''
        for name in ('objective', 'summary', 'missing_inputs', 'open_questions', 'objective_contract', 'items', 'conflicts'):
            if name in foundation:
                fields[prefix+'/'+name] = foundation[name]
        if schema == INTAKE and 'current_contradiction' in payload.get('problem_frame', {}):
            fields['/problem_frame/current_contradiction'] = payload['problem_frame']['current_contradiction']
        return fields
    else:
        return fields
    return {'/'+name: payload[name] for name in names if name in payload}


def run_details(candidate, run_ids):
    wanted = set(run_ids)
    return [v for v in rows(candidate, 'runs',
        'SELECT run_id,operation_id,request_digest,inputs_json,created_at,completed_at,output_binding_name FROM runs ORDER BY created_at,run_id')
        if v['run_id'] in wanted]


def root_records(journey, control):
    """Label scheduler-owner observations separately from setup/audit Root.

    Autonomous events.log normally covers setup/audit notifications. It does not
    establish background-owner coverage; an unidentified owner remains missing.
    """
    journey = Path(journey)
    usage = read(journey/'usage.json') if (journey/'usage.json').exists() else {}
    setup_root = usage.get('root_thread')
    roots = set() if control else {setup_root}
    records = []
    if control:
        host = json.loads(control.get('host_json') or '{}')
        roots.add(host.get('thread_id'))
        checkpoint = json.loads(control.get('checkpoint_json') or '{}')
        roots.update(thread for thread, value in checkpoint.get('usage_records', {}).items() if value.get('role') == 'root')
        if checkpoint.get('report'):
            record = dict(source='scheduler_progression', path='/checkpoint/report',
                role='root' if roots - {None} else 'unattributed', content=checkpoint['report'])
            records.append({**record, 'record_digest': digest(record)})
    roots.discard(None)
    observed = roots | ({setup_root} if setup_root else set())
    path = journey/'fixture-logs/events.log'
    if path.exists():
        with path.open() as stream:
            for line_number, line in enumerate(stream, 1):
                event = json.loads(line)
                params = event.get('params', {})
                if params.get('threadId') not in observed:
                    continue
                role = 'root' if params['threadId'] in roots else 'setup_root'
                if event.get('method') == 'item/completed' and params.get('item', {}).get('type') in {
                        'mcpToolCall', 'dynamicToolCall', 'agentMessage'}:
                    record = dict(source='fixture-logs/events.log', line=line_number, role=role, content=params['item'])
                    records.append({**record, 'record_digest': digest(record)})
                elif event.get('method') in {'turn/started', 'turn/completed'}:
                    record = dict(source='fixture-logs/events.log', line=line_number, role=role,
                        content=dict(method=event['method'], turn=params.get('turn', {})))
                    records.append({**record, 'record_digest': digest(record)})
    return records


def background_records(journey, control):
    """Read the acceptance observer's scoped projections, not host stderr."""
    path = Path(journey)/'background-observations.jsonl'
    if not path.exists():
        return []
    instance = (control or {}).get('instance_id')
    objective = json.loads((control or {}).get('objective_ref_json') or 'null')
    records = []
    with path.open() as stream:
        for line, raw in enumerate(stream, 1):
            content = json.loads(raw)
            if content.get('version') != 1 or content.get('source') != 'external_acceptance_observation':
                raise ValueError('unsupported_background_observation')
            owner = content.get('owner') or {}
            scoped = (instance is not None and objective is not None and content.get('instance_id') == instance
                and content.get('objective_ref') == objective and content.get('mode') == 'background')
            identified = bool(owner.get('thread_id') and owner.get('platform_session'))
            record = dict(source='background-observations.jsonl', line=line,
                role='root' if scoped and identified else 'unattributed', content=content)
            records.append({**record, 'record_digest':digest(record)})
    return records


def collect(candidate, journey, sealed, details, before, control=None, adoption=None):
    """Bind local review inputs to sealed originals and available Root records."""
    outputs, stages, omissions, edges = [], [], [], []
    table = rows(candidate, 'runs', "SELECT 1 FROM sqlite_master WHERE type='table' AND name='run_tool_evidence'")
    receipts = rows(candidate, 'runs', 'SELECT run_id,record_json FROM run_tool_evidence ORDER BY run_id,ordinal') if table else []
    receipts = [(v['run_id'], json.loads(v['record_json'])) for v in receipts]
    by_id = {v['run_id']: v for v in details}
    for item in sealed:
        body, path = cas_payload(candidate, item['reference'])
        schema = item['reference'].get('schema_id')
        outputs.append(dict(run_id=item['run_id'], reference=item['reference'], path=path,
            fields=decision_fields(body, schema), supported=bool(decision_fields(body, schema))))
        if not outputs[-1]['supported']:
            omissions.append(dict(run_id=item['run_id'], reason='unsupported_output_schema'))
        inputs = json.loads(by_id[item['run_id']]['inputs_json'] or '[]')
        for bound in inputs:
            if bound.get('producer_run_id') in by_id:
                edges.append(dict(consumer=item['run_id'], producer=bound['producer_run_id'], port=bound['port_name'],
                    reference=bound['artifact_ref']))
        if schema != REPORT:
            continue
        for alias in body.get('adopted_stages', []):
            current = [(owner, r) for owner, r in receipts if owner == item['run_id'] and r['alias'] == alias]
            bound = next((v for v in inputs if v.get('source_name') == alias), None)
            matches = current or [(owner, r) for owner, r in receipts
                if bound and r['artifact_ref'] == bound['artifact_ref']]
            if len(matches) != 1 or matches[0][1].get('metadata', {}).get('kind') not in STAGE_KINDS:
                omissions.append(dict(run_id=item['run_id'], alias=alias, reason='adopted_receipt_missing_or_ambiguous'))
                continue
            owner, receipt = matches[0]
            content, path = cas_payload(candidate, receipt['artifact_ref'])
            kind = receipt['metadata']['kind']
            stages.append(dict(run_id=item['run_id'], producer_run_id=owner, alias=alias,
                reference=receipt['artifact_ref'], path=path, kind=kind,
                fields=decision_fields(content, receipt['artifact_ref'].get('schema_id'), kind=kind)))
    records = root_records(journey, control)+background_records(journey, control)
    selection = dict(status='not_observed', run_ids=[], reason='No explicit final adoption interpretation bound to a Root record.')
    if adoption is not None:
        if adoption.get('evidence_digest') != digest(sealed):
            raise ValueError('adoption_sealed_evidence_mismatch')
        selected = adoption.get('run_ids', [])
        record = next((v for v in records if v['record_digest'] == adoption.get('root_record_digest')), None)
        if (not selected or len(selected) != len(set(selected)) or not set(selected).issubset({v['run_id'] for v in outputs})
                or not record or not isinstance(adoption.get('reason'), str) or not adoption['reason'].strip()):
            raise ValueError('adoption_requires_exact_sealed_subjects_and_root_record')
        excerpt = adoption.get('root_excerpt')
        content = record['content']
        text = content.get('text') if content.get('type') == 'agentMessage' else content.get('summary')
        if not isinstance(excerpt, str) or not excerpt.strip() or not isinstance(text, str) or excerpt not in text:
            raise ValueError('adoption_requires_exact_root_conclusion_excerpt')
        selection = dict(status='interpreted', run_ids=selected, reason=adoption['reason'],
            root_record_digest=record['record_digest'], root_record_role=record['role'], root_excerpt=excerpt,
            authority='local reviewer interpretation; no production adoption fact')
    return dict(version=1, sealed_outputs=sealed, outputs=outputs, adopted_stages=stages, final_selection=selection,
        omissions=omissions, details=details, edges=edges, root_records=records,
        initial_check=dict(before_runs=before, coverage='before-runs references only',
            source_materials='not_observed', fresh_threads='not_observed', initial_context='not_observed'),
        control=dict(state=control.get('state'), reason=control.get('reason')) if control else None,
        background_observation_coverage=read(Path(journey)/'background-observation-coverage.json')
            if (Path(journey)/'background-observation-coverage.json').exists() else dict(
                status='observed_changes' if any(v['source'] == 'background-observations.jsonl' for v in records) else 'not_observed',
                scope='external acceptance polling; intervening events and native tool calls remain unobserved'))


def assess_domains(evidence, review, objective):
    if objective not in {'stagnation', 'negative'} or len(review['decisions']) != 5:
        raise ValueError('s0_requires_five_criteria_and_known_objective')
    statuses = []
    for index, item in enumerate(review['decisions']):
        score = item.get('score')
        floor = 2 if index == 4 else 1
        if score is None:
            expected = 'not_observed'
        elif type(score) is int and score in ({0, 2} if index == 4 else {0, 1, 2}):
            expected = 'passed' if score >= floor else 'failed'
        else:
            raise ValueError('invalid_s0_score')
        if item['status'] != expected:
            raise ValueError('s0_status_does_not_match_score')
        statuses.append(expected)
    science = [0, 1, 2, 4] if objective == 'stagnation' else [0, 1, 4]
    qualification = dict(science=verdict(dict(enumerate(statuses)), science),
        cross_task=statuses[2] if objective == 'negative' else 'not_observed', root_scheduling=statuses[3])
    selected = set(evidence['final_selection']['run_ids'])
    gaps = [v for v in evidence['omissions'] if v['run_id'] in selected]
    if qualification['science'] != 'failed' and (evidence['final_selection']['status'] != 'interpreted' or gaps):
        qualification['science'] = 'not_observed'
    if qualification['cross_task'] != 'failed' and objective == 'negative' and not evidence['edges']:
        qualification['cross_task'] = 'not_observed'
    # Worker prose and a final control state cannot prove Root behavior.
    actions = [r for r in evidence['root_records'] if r.get('role') == 'root'
        and r['content'].get('type') in {'mcpToolCall', 'dynamicToolCall'}]
    stopped = any(r.get('role') == 'root' and r['source'] == 'scheduler_progression' and r['content'].get('completed') is True
        for r in evidence['root_records']) and evidence['control'] == dict(state='stopped', reason='goal_completed')
    waited = waiting_observation(evidence['root_records'], {v['output_binding_name'] for v in evidence['details']},
        {v['run_id']:v['reference'] for v in evidence['sealed_outputs']})
    if qualification['root_scheduling'] != 'failed' and not actions and not stopped and not waited:
        qualification['root_scheduling'] = 'not_observed'
    if qualification['root_scheduling'] != 'failed' and objective == 'negative' and not waited:
        qualification['root_scheduling'] = 'not_observed'
    required = ['science', 'root_scheduling'] + (['cross_task'] if objective == 'negative' else [])
    qualification['overall'] = verdict(qualification, required)
    if review.get('qualification') not in (None, qualification):
        raise ValueError('s0_qualification_does_not_match_observed_domains')
    return qualification


def waiting_observation(records, output_names=(), run_refs=None):
    """Native status reads or externally observed background waiting windows.

    This observes one real window. Absence of duplicates still requires review;
    missing native events are not a complete tool trace.
    """
    live, windows, last_owner, last_time = set(), {}, None, -1
    for record in records:
        if record.get('source') == 'background-observations.jsonl':
            item = record['content']
            owner = item.get('owner') or {}
            key = (item.get('instance_id'), digest(item.get('objective_ref')), owner.get('thread_id'), owner.get('platform_session'))
            now = item.get('elapsed_seconds')
            if record.get('role') != 'root' or type(now) not in (int, float) or not math.isfinite(now) or now <= last_time:
                windows.clear()
                continue
            last_time = now
            if last_owner != key:
                windows.clear()
            last_owner = key
            runs = {v['run_id']:v for v in item.get('runs', []) if v.get('admitted')}
            resumed = (item.get('state') == 'active' and item.get('phase') == 'running'
                and item.get('runtime_status') == 'deciding' and bool(item.get('turn_id')))
            completed = (item.get('reason') == item.get('runtime_status') == 'goal_completed'
                and item.get('report_completed') is True and item.get('phase') == 'idle' and item.get('turn_id') is None)
            for run, opened_round in windows.items():
                sealed = runs.get(run, {})
                advanced = (item.get('state') == 'active' and item.get('phase') == 'idle' and item.get('runtime_status') == 'waiting'
                    and type(opened_round) is int and type(item.get('rounds')) is int
                    and item['rounds'] > opened_round and item.get('native_completion') == 'completed')
                if (sealed.get('state') == 'completed' and sealed.get('output_ref') is not None
                        and sealed['output_ref'] == (run_refs or {}).get(run) and (resumed or completed or advanced)):
                    return True
            if (item.get('state') == 'active' and item.get('phase') == 'idle' and item.get('runtime_status') == 'waiting'
                    and item.get('turn_id') is None):
                for run, value in runs.items():
                    if value.get('state') in {'queued', 'running'}:
                        windows.setdefault(run, item.get('rounds'))
            continue
        if record.get('role') != 'root':
            continue
        item = record['content']
        if item.get('type') != 'mcpToolCall' or item.get('tool') != 'scid_call' or item.get('status') != 'completed':
            continue
        arguments = item.get('arguments', {})
        if not isinstance(arguments, dict) or arguments.get('name') != 'run_status':
            continue
        result = item.get('result', {}).get('structuredContent', {})
        name = result.get('name')
        if name and result.get('state') in {'queued', 'running'}:
            live.add(name)
        elif name in live and result.get('state') == 'completed' and result.get('output_artifact_name') in output_names:
            return True
    return False


def parameter_predicate(role, values):
    """Optional reviewer numerical aid; role is explicit, never guessed from text."""
    projections = dict(a=(1.9, 2.1), b=(.9, 1.1), c=(7/60, 13/60))
    if role in {'exact_interpolation', 'feasible_example'}:
        if set(values) != {'a', 'b', 'c'}:
            raise ValueError('three_joint_parameters_required')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values()):
            raise ValueError('finite_numeric_parameters_required')
        a, b, c = (values[name] for name in ('a', 'b', 'c'))
        residuals = [b-1, a+b-3, 2*a+b-5, 3*a+b+6*c-8]
        return dict(predicate=role, holds=max(abs(v) for v in residuals) <= (1e-9 if role == 'exact_interpolation' else .1+1e-9),
            residuals=residuals, scope='local numerical predicate only')
    if role in {'complete_coordinate_projections', 'conservative_envelope'}:
        if set(values) != set(projections):
            raise ValueError('three_coordinate_ranges_required')
        if any(not isinstance(v, (list, tuple)) or len(v) != 2 or
                any(type(n) not in (int, float) or not math.isfinite(n) for n in v) for v in values.values()):
            raise ValueError('finite_numeric_ranges_required')
        exact = role == 'complete_coordinate_projections'
        holds = all(len(values[k]) == 2 and (all(abs(v-w) <= 1e-9 for v, w in zip(values[k], projections[k]))
            if exact else values[k][0] <= projections[k][0] and values[k][1] >= projections[k][1]) for k in projections)
        return dict(predicate=role, holds=holds, correlation='joint constraints still required; coordinate ranges are not a Cartesian feasible set',
            scope='local numerical predicate only')
    raise ValueError('unknown_parameter_role')


def auto_checks(evidence, objective):
    selected = set(evidence['final_selection']['run_ids'])
    documents = [*evidence['outputs'], *evidence['adopted_stages']]
    patterns = ({'S-A1':r'不可辨识|不能区分|无法区分|non.?identif|indistinguishable',
        'S-A2':r'\bc\s*[=≈]', 'S-A3':r'胜出|应选|唯一|正确机制', 'S-A4':r'\b[ab]\s*[=≈]',
        'S-A5':r'新.*观测|追加|建议|additional', 'S-A6':r'测得|实测|observed|measured',
        'S-A7':r'误差|重复|error|repeat'} if objective == 'stagnation' else {
        'N-B1':r'排除|不可行|不相容|infeasible', 'N-B2':r'区间|LP|极小极大|SSR|残差|residual',
        'N-B3':r'\bc\s*[=≈∈]|可行|相关|包络|插值', 'N-B4':r'唯一|证明|因果|限制|alternative',
        'N-B5':r'剔除|降权|离群|放宽|outlier', 'N-B6':r'实测|测得|observed|measured',
        'N-B10':r'新.*观测|建议|区分|additional'})
    checks = {}
    for key, pattern in patterns.items():
        hits = []
        for doc in documents:
            for path, value in doc['fields'].items():
                # Whole declared values are preserved; matches have no semantic authority.
                text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                if re.search(pattern, text, re.I):
                    hits.append(dict(run_id=doc['run_id'], path=path, text=text,
                        final_adopted=doc['run_id'] in selected, stage_alias=doc.get('alias')))
        checks[key] = dict(status='hit' if hits else 'miss', blocking=False, evidence=hits)
    prefix = 'S-A' if objective == 'stagnation' else 'N-B'
    if objective == 'stagnation':
        checks['S-A8'] = dict(status='data', blocking=False, tasks=len(evidence['details']), edges=evidence['edges'])
        checks['S-A10'] = dict(status='data' if any(v.get('role') == 'root' for v in evidence['root_records']) else 'not_observed', blocking=False,
            records=evidence['root_records'], control=evidence['control'])
    else:
        checks['N-B7'] = dict(status='hit' if evidence['edges'] else 'not_observed', blocking=False,
            evidence=evidence['edges'], limitation='Binding alone does not prove new scientific progress.')
        observed = waiting_observation(evidence['root_records'], {v['output_binding_name'] for v in evidence['details']},
            {v['run_id']:v['reference'] for v in evidence['sealed_outputs']})
        checks['N-B8'] = dict(status='hit' if observed else 'not_observed', blocking=False, records=evidence['root_records'],
            coverage=evidence.get('background_observation_coverage'),
            limitation='Bounded external observations or native reads establish one window; reviewer judges efficiency and duplicate dispatch. Final state alone is insufficient.')
    checks[prefix+'9'] = dict(status='not_observed', blocking=False, initial_check=evidence['initial_check'],
        limitation='Missing sources or zero retrieved_source do not prove no network use or no historical contamination; native tool coverage is partial.')
    return dict(verdict='not_observed', checks=checks, blocking_failures=[],
        scope='Text localization only; every scientific and scheduling decision requires review.')


def redact(text, identifiers, transformations, location):
    """Replace exact declared identifiers, preserving scientific vocabulary."""
    exact = {v:r for v,r in identifiers.items() if v and v != r and v not in {'候选', 'candidate', 'baseline'}}
    if not exact:
        return text
    pattern = r'(?<![\w.-])(?:'+'|'.join(re.escape(v) for v in sorted(exact, key=lambda v:-len(v)))+r')(?![\w.-])'
    def replace(match):
        value = match.group()
        transformations.append(dict(location=location, original=value, replacement=exact[value],
            offset=match.start(), reason='explicit run/thread/group/version identifier'))
        return exact[value]
    return re.sub(pattern, replace, text)


def package(root, manifest, reports):
    """Generate one immutable local blind batch; costs remain in the reports."""
    ready = {case: report for case, report in reports.items() if report.get('scoring_evidence')}
    if not ready:
        raise ValueError('no_s0_sealed_evidence_to_package')
    rubric_digest = digest(manifest['config']['quality'])
    seed = hashlib.sha256((rubric_digest+''.join(sorted(v['review_template']['evidence_digest'] for v in ready.values()))).encode()).hexdigest()
    ordered = sorted(ready)
    random.Random(seed).shuffle(ordered)
    destination = Path(root)/'blind'
    destination.mkdir(mode=0o700, exist_ok=False)
    key, batch = {}, dict(version=1, seed=seed, rubric_digest=rubric_digest, packages=[])
    for index, case in enumerate(ordered, 1):
        report = ready[case]
        evidence = report['scoring_evidence']
        blind_id = f'S0-{index:02d}'
        folder = destination/blind_id
        folder.mkdir(mode=0o700)
        config = manifest['config']['cases'][case]
        ranks = {v['run_id']: f'T{i}' for i, v in enumerate(evidence['details'], 1)}
        identifiers = {**ranks, case: blind_id}
        identifiers.update({v['output_binding_name']:ranks[v['run_id']]+'.output' for v in evidence['details']
            if v.get('output_binding_name')})
        for record in evidence['root_records']:
            item = record['content']
            for name in ('threadId', 'thread_id', 'id'):
                if isinstance(item.get(name), str):
                    identifiers[item[name]] = '[record-id]'
        # Only explicitly labelled group/version metadata is hidden; words like
        # "candidate", "候选", and "baseline" remain intact in scientific prose.
        identifiers.update({f'arm={config.get("arm")}':'arm=[hidden]',
            f'case={case}':f'case={blind_id}'})
        benchmark = manifest['config'].get('benchmark', {})
        for name in ('baseline_commit', 'candidate_commit'):
            if benchmark.get(name):
                identifiers[str(benchmark[name])] = '[version-id]'
        transformations, delivery, trajectory = [], [], []
        selected = set(evidence['final_selection']['run_ids'])
        for doc in [*evidence['outputs'], *evidence['adopted_stages']]:
            label = ranks[doc['run_id']]+(' adopted stage' if doc.get('alias') else '')
            adoption = 'final reviewer selection' if doc['run_id'] in selected else 'final adoption pending or unselected'
            delivery.append(f'### {label} ({adoption}; CAS {doc["reference"]["sha256"][:12]})')
            for path, value in doc['fields'].items():
                # Executable/project paths and implementation bodies remain in
                # exact CAS originals, outside the scientific blind excerpt.
                if path in {'/implementation', '/scientific_files', '/outputs'}:
                    delivery.append(f'{path}: omitted; consult exact CAS original if needed')
                    continue
                text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                delivery.append(path+'\n'+redact(text, identifiers, transformations, label+path))
        outputs = {v['run_id']:v for v in evidence['outputs']}
        completion = sorted(evidence['details'], key=lambda d:(d.get('completed_at') or '~', d['run_id']))
        completed = {v['run_id']:i for i,v in enumerate(completion, 1)}
        for item in evidence['details']:
            label = ranks[item['run_id']]
            incoming = [ranks[e['producer']]+'.'+e['port'] for e in evidence['edges'] if e['consumer'] == item['run_id']]
            fields = outputs[item['run_id']]['fields']
            text = f'{label} | {item["operation_id"]} | inputs: {", ".join(incoming) or "no observed earlier task binding"} | '+str(fields.get('/outcome', 'not observed'))+' | '+str(fields.get('/summary', ''))[:120]+f' | completion order {completed[item["run_id"]]}'
            trajectory.append(redact(text, identifiers, transformations, label))
        files = dict(objective=manifest['config']['objectives'][config['objective']],
            delivery='\n\n'.join(delivery), trajectory='\n'.join(trajectory))
        (folder/'objective.txt').write_text(files['objective'])
        (folder/'delivery.md').write_text(files['delivery'])
        (folder/'trajectory.md').write_text(files['trajectory'])
        # Auto evidence has private identifiers for local audit. The blind copy
        # contains only normalized text locators and task statistics.
        checks = report['auto_checks']
        blind_checks = {'scope':checks['scope'], 'verdict':'not_observed', 'checks':{}}
        for name, check in checks['checks'].items():
            hits = [dict(task=ranks[h['run_id']], path=h['path'],
                text=redact(h['text'], identifiers, transformations, name), final_adopted=h['final_adopted'])
                for h in check.get('evidence', []) if 'path' in h]
            blind_checks['checks'][name] = dict(status=check['status'], blocking=False, evidence=hits)
        write(folder/'auto_checks.json', blind_checks)
        package_digest = digest(dict(files=files, auto_checks=blind_checks, evidence_digest=report['review_template']['evidence_digest']))
        score = dict(report['review_template'], blind=dict(blind_id=blind_id, package_digest=package_digest,
            intact=False, redactions=len(transformations), leak_notes='Scientific excerpts partially blinded; Root trajectory is reviewed separately.'))
        write(folder/'score.json', score)
        key[blind_id] = dict(case=case, evidence_digest=score['evidence_digest'], package_digest=package_digest,
            transformations=transformations)
        batch['packages'].append(dict(blind_id=blind_id, package_digest=package_digest))
    write(Path(root)/'blind-key.json', key)
    (Path(root)/'blind-key.json').chmod(0o600)
    write(Path(root)/'blind-manifest.json', batch)
    return batch


def validate_blind_review(root, case, review):
    blind = review['blind']
    key = read(Path(root)/'blind-key.json').get(blind.get('blind_id'))
    if not key or key['case'] != case or key['evidence_digest'] != review['evidence_digest']:
        raise ValueError('blind_review_case_or_evidence_mismatch')
    folder = Path(root)/'blind'/blind['blind_id']
    files = dict(objective=(folder/'objective.txt').read_text(), delivery=(folder/'delivery.md').read_text(),
        trajectory=(folder/'trajectory.md').read_text())
    actual = digest(dict(files=files, auto_checks=read(folder/'auto_checks.json'), evidence_digest=review['evidence_digest']))
    if actual != key['package_digest'] or actual != blind.get('package_digest'):
        raise ValueError('blind_package_changed')
