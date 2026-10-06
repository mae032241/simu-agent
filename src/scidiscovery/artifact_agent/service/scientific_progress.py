"""Immutable Root judgments, separate from Worker science and qualification."""
import base64
import json

from ..schema.artifact import ArtifactRegistration
from .artifacts import is_scientific_original
from ..schema.common import canonical_json, canonical_sha256
from ..schema.refs import ActorRef, ArtifactRef
from ..schema.scientific_progress import ScientificIntent, ProgressAssessment
from .research_progress import cycle_facts, progress_families

EXPLORATION_KEY = 'consumed_exploration_window'


PROGRESS_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_progress_assessments (
    sequence INTEGER NOT NULL,
    instance_id TEXT NOT NULL REFERENCES scheduler_instances(instance_id),
    goal_key TEXT NOT NULL,
    run_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    revision INTEGER NOT NULL,
    artifact_ref_json TEXT NOT NULL,
    PRIMARY KEY(instance_id, sequence),
    UNIQUE(instance_id, goal_key, run_id, revision)
);
CREATE INDEX IF NOT EXISTS scheduler_progress_goal
ON scheduler_progress_assessments(instance_id, goal_key, sequence);
CREATE TABLE IF NOT EXISTS scheduler_terminal_deliveries (
    sequence INTEGER NOT NULL,
    instance_id TEXT NOT NULL REFERENCES scheduler_instances(instance_id),
    goal_key TEXT NOT NULL,
    run_id TEXT NOT NULL,
    task_name TEXT NOT NULL,
    objective_ref_json TEXT NOT NULL,
    terminal_json TEXT NOT NULL,
    delivery_json TEXT NOT NULL,
    host_json TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    consumed_boundary TEXT,
    PRIMARY KEY(instance_id, goal_key, run_id),
    UNIQUE(instance_id, sequence)
);
CREATE INDEX IF NOT EXISTS scheduler_terminal_goal
ON scheduler_terminal_deliveries(instance_id, goal_key, sequence);
CREATE TABLE IF NOT EXISTS scheduler_progress_facts (
    instance_id TEXT NOT NULL REFERENCES scheduler_instances(instance_id),
    goal_key TEXT NOT NULL,
    run_id TEXT NOT NULL,
    fact_json TEXT NOT NULL,
    PRIMARY KEY(instance_id, goal_key, run_id)
);
CREATE TABLE IF NOT EXISTS scheduler_progress_shadow (
    instance_id TEXT NOT NULL REFERENCES scheduler_instances(instance_id),
    goal_key TEXT NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY(instance_id, goal_key)
);
"""


def observe_deliveries(db, row, checkpoint, *, boundary=None):
    """Trusted control facts; a confirmed native identity is required even for early admission.

    Prepared content survives an uncertain submission, but is not a consumption.
    Re-delivery may attach an unconsumed task to a later confirmed turn.
    """
    decision = checkpoint.get('terminal_delivery')
    if not decision:
        return
    if boundary:
        decision['boundary'] = boundary
    turn = checkpoint.get('turn_id')
    if not turn or checkpoint.get('phase') != 'running':
        return
    objective = decision['objective_ref']
    goal_key = canonical_sha256(objective)
    changed = False
    for item in decision['items']:
        if item['terminal']['state'] not in {'completed', 'failed', 'timed_out', 'cancelled', 'canceled'}:
            continue
        if item.get('delivery', {}).get('coverage') == 'omitted':
            continue  # A hidden brief item is not an actual delivery.
        sequence = db.execute('SELECT coalesce(max(sequence),0)+1 FROM scheduler_terminal_deliveries WHERE instance_id=?',
            (row['instance_id'],)).fetchone()[0]
        delivery_value = dict(item['delivery'], observation_role=_delivery_role(db, row, item['run_id'], item['terminal']))
        updated = db.execute('INSERT INTO scheduler_terminal_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(instance_id,goal_key,run_id) DO UPDATE SET '
            'delivery_json=excluded.delivery_json,host_json=excluded.host_json,turn_id=excluded.turn_id,'
            'consumed_boundary=excluded.consumed_boundary '
            'WHERE scheduler_terminal_deliveries.consumed_boundary IS NULL',
            (sequence, row['instance_id'], goal_key, item['run_id'], item['name'], json.dumps(objective),
             json.dumps(item['terminal']), json.dumps(delivery_value), row['host_json'], turn,
             decision.get('boundary')))
        if updated.rowcount and decision.get('boundary'):
            delivery = db.execute('SELECT sequence FROM scheduler_terminal_deliveries '
                'WHERE instance_id=? AND goal_key=? AND run_id=?',
                (row['instance_id'], goal_key, item['run_id'])).fetchone()
            # Navigation position is assigned when the delivery is prepared.
            # Consumption gets its own position only at this confirmed boundary,
            # in the same serialized control transaction as the delivery update.
            consumption = db.execute("SELECT coalesce(max(json_extract(fact_json,'$.consumption_sequence')),0)+1 "
                'FROM scheduler_progress_facts WHERE instance_id=?', (row['instance_id'],)).fetchone()[0]
            _update_fact(db, row['instance_id'], goal_key, item['run_id'], dict(
                consumption_sequence=consumption, delivery_sequence=delivery['sequence'],
                task_name=item['name'], terminal=item['terminal'],
                task_classification=item['terminal'].get('task_classification'),
                observation_role=delivery_value['observation_role'], run_id=item['run_id'],
                intent=item.get('scientific_intent'), delivery=delivery_value))
            changed = True
    if changed:
        refresh_shadow(db, row, goal_key)


def terminal_delivery_view(records):
    return [dict(task_name=item['task_name'], state=json.loads(item['terminal_json'])['state'],
        delivery=json.loads(item['delivery_json']),
        consumption='settled' if item['consumed_boundary'] else 'awaiting_decision_boundary',
        assessment='not_inferred_from_delivery', read=dict(tool='run_status', name=item['task_name'], intent='decision'))
        for item in records]


def terminal_fact(runs, value):
    """Freeze trusted machine diagnostics; failure prose is explanation only."""
    terminal = dict(state=value.state, output=value.output_ref.model_dump(mode='json') if value.output_ref else None,
        reason=value.reason, task_classification=(value.recovery_policy or {}).get('task_classification'))
    from .verified_progress import verified_progress
    terminal['verified_progress'] = verified_progress(runs, value)
    from .research_progress import research_progress
    terminal['scientific_progress'] = research_progress(runs, value)
    terminal['terminal_event'] = terminal_position(runs, instance_id=value.instance_id, run_id=value.run_id)
    if value.state in {'failed', 'timed_out'}:
        failure = runs.diagnostic_summary(value).get('failure') or {}
        terminal['failure_key'] = (dict(operation_id=value.operation_id, operation_digest=value.operation_digest,
            category=failure['category'], code=failure['code'])
            if failure.get('category') and failure.get('code') else None)
        terminal['failure_classification'] = 'recorded_diagnostic' if terminal['failure_key'] else 'unknown'
    return terminal


def terminal_position(runs, *, instance_id, run_id=None):
    """The existing committed terminal event is a causal position, not wall time."""
    with runs._connect() as db:
        return db.execute("SELECT coalesce(max(a.rowid),0) FROM run_activity a JOIN runs r ON r.run_id=a.run_id "
            "WHERE r.instance_id=? AND (? IS NULL OR r.run_id=?) AND r.state IN ('completed','failed') "
            "AND a.recorded_at=r.completed_at AND a.activity=CASE r.state WHEN 'completed' "
            "THEN 'completion_committed' ELSE 'framework_failure' END", (instance_id, run_id, run_id)).fetchone()[0]


def background_snapshot(runs, *, instance_id, observed=()):
    """Bounded optional proof knowledge; the high water covers all terminal identities."""
    from .verified_progress import verified_progress, _proof_errors
    upper = terminal_position(runs, instance_id=instance_id)
    with runs._connect() as db:
        query = ("FROM runs r JOIN run_activity a ON a.run_id=r.run_id "
            "WHERE r.instance_id=? AND r.state='completed' AND a.activity='completion_committed' "
            "AND a.recorded_at=r.completed_at AND a.rowid<=? "
            'AND r.run_id NOT IN (SELECT value FROM json_each(?)) ')
        args = (instance_id, upper, json.dumps(sorted(observed)))
        candidate_count = db.execute('SELECT count(*) '+query, args).fetchone()[0]
        records = db.execute('SELECT r.run_id '+query+'ORDER BY a.rowid LIMIT 16', args).fetchall()
    keys, cycles, checked, unavailable = set(), set(), [], []
    for item in records:
        try:
            terminal = terminal_fact(runs, runs.status(item['run_id']))
            proof = terminal['verified_progress']
        except _proof_errors() as error:
            proof = dict(status='unknown', reason='background_proof_unavailable', error=type(error).__name__)
            terminal = dict(verified_progress=proof)
        progress = terminal.get('scientific_progress') or {}
        if (any(part in proof.get('reason', '') for part in ('unavailable', 'inconsistent', 'missing', 'ambiguous', 'invalid'))
                or any(part in progress.get('reason', '') for part in
                    ('unavailable', 'inconsistent', 'missing_or_ambiguous', 'invalid', 'omitted', 'projector_failed'))):
            unavailable.append(item['run_id'])
        else:
            checked.append(item['run_id'])
        keys.update(part['key'] for part in progress_families(dict(terminal=terminal)))
        if progress.get('stage') == 'analysis' and progress.get('cycle_key'):
            cycles.add(progress['cycle_key'])
    return dict(terminal_upper=upper, known_resolutions=sorted(keys)[:128], known_cycles=sorted(cycles)[:128], checked_runs=checked,
        unavailable_runs=unavailable, candidate_count=candidate_count, proof_omitted=candidate_count > 16 or len(keys) > 128,
        family_omitted=len(keys) > 128,
        proof_coverage='bounded_unknown' if candidate_count > 16 or unavailable or len(keys) > 128 else 'complete')


def _delivery_role(db, row, run_id, terminal):
    # Once actually observed, a goal revision cannot relabel a Run as background.
    previous = db.execute('SELECT fact_json FROM scheduler_progress_facts WHERE instance_id=? AND run_id=? '
        "AND json_extract(fact_json,'$.consumption_sequence') IS NOT NULL ORDER BY "
        "json_extract(fact_json,'$.consumption_sequence') LIMIT 1", (row['instance_id'], run_id)).fetchone()
    if previous:
        return json.loads(previous['fact_json']).get('observation_role', 'observed')
    record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], EXPLORATION_KEY)).fetchone()
    state = json.loads(record['state_json']) if record else {}
    history = state.get('background_history')
    if history is not None:
        if run_id in state.get('observed_before_start', []):
            return 'observed'
        position = terminal.get('terminal_event')
        if type(position) is not int or position <= 0:
            return 'unknown'
        return 'background' if position <= history['terminal_upper'] else 'observed'
    # Existing exact scope identities remain meaningful, but do not invent a
    # high water for a scope frozen before this field was introduced.
    scopes = [json.loads(item['state_json']).get('observation_scope', {}) for item in db.execute(
        'SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=?', (row['instance_id'],))]
    if any(run_id in scope.get('background', {}) for scope in scopes):
        return 'background'
    return 'unknown' if any(scope.get('related_omitted') for scope in scopes) else 'observed'


def delivery_coverage(projection):
    return dict(coverage=projection.get('output_delivery', 'terminal_status') if projection else 'omitted',
        original_read='not_confirmed', omissions={key: projection[key] for key in (
            'scheduler_signal_omissions', 'content_unavailable', 'default_output_unavailable') if key in projection}
            if projection else {'reason': 'brief_capacity'})


def terminal_delivery_page(*, bindings, row, cursor=None, limit=8):
    if not 1 <= limit <= 8:
        raise ValueError('invalid delivery pagination')
    if not row.get('objective_ref_json'):
        if cursor is not None:
            raise ValueError('Delivery cursor requires its frozen goal.')
        return dict(items=[], next_cursor=None, omitted=False)
    scope = canonical_sha256(dict(kind='terminal_delivery', instance=row['instance_id'],
        objective=json.loads(row['objective_ref_json'])))
    after = 0
    if cursor is not None:
        try:
            position = json.loads(base64.b64decode(cursor, altchars=b'-_', validate=True))
            after = position['after']
            if position['scope'] != scope or type(after) is not int or after <= 0:
                raise ValueError('wrong scope')
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError('Invalid delivery cursor; restart history for this frozen goal.') from error
    records = bindings.terminal_deliveries(instance_id=row['instance_id'],
        objective_ref=ArtifactRef.model_validate_json(row['objective_ref_json']), after=after, limit=limit+1)
    observation = (bindings.progress_shadow(instance_id=row['instance_id'],
        objective_ref=ArtifactRef.model_validate_json(row['objective_ref_json'])) or {}).get('observation_scope', {})
    page = dict(items=[], next_cursor=None, omitted=False, continuation=None)
    for index, record in enumerate(records[:limit]):
        next_cursor = (base64.urlsafe_b64encode(canonical_json(dict(scope=scope, after=record['sequence']))).decode()
            if index+1 < len(records) else None)
        item = terminal_delivery_view([record])[0]
        item['observation_role'] = json.loads(record['delivery_json']).get('observation_role',
            'background' if record['run_id'] in observation.get('background', {}) else 'observed')
        candidate = dict(items=[*page['items'], item], next_cursor=next_cursor,
            omitted=next_cursor is not None, continuation=dict(tool='progression_status', delivery_cursor=next_cursor,
                delivery_limit=limit) if next_cursor else None)
        if len(canonical_json(candidate)) > 16384:
            if not page['items']:
                raise ValueError('Delivery record exceeds page capacity.')
            break
        page = candidate
    return page


def _freeze(artifacts, kind, body, parents, previous=None):
    return artifacts.register(canonical_json(body), ArtifactRegistration(
        kind=kind, schema_id=f'scidiscovery.{kind.replace("_", "-")}.v1',
        payload_schema_version=1, media_type='application/json',
        creator=ActorRef(actor_type='service', actor_id='scientific_progress'),
        parent_refs=tuple(dict.fromkeys(parents)), supersedes_ref=previous,
        confidentiality='run_private', labels={'authority': 'root_judgment_not_scientific_qualification'}),
        idempotency_key=f'{kind}:{canonical_sha256(body)}').ref


def freeze_intent(artifacts, bound, instance_id, run_id):
    intent = ScientificIntent.model_validate(bound.scientific_intent).model_dump()
    return _freeze(artifacts, 'scientific_intent',
        dict(schema_version=1, instance_id=instance_id, run_id=run_id, intent=intent),
        [item.artifact.ref for item in bound.inputs])


def read_intent(artifacts, value):
    ref = (value.recovery_policy or {}).get('scientific_intent_ref')
    return (json.loads(artifacts.read(ArtifactRef.model_validate(ref)))['intent'] if ref else None)



def goal_bound_runs(checkpoint, objective):
    """Only exact persisted goal bindings can establish checkpoint membership.

    Older checkpoints without these bindings need the frozen-source lookup.
    Admissions remain cumulative for budget and in-flight recovery purposes.
    """
    related = dict(checkpoint.get('relevant_runs', {})) if (
        checkpoint.get('relevant_runs_objective_ref') == objective) else {}
    related.update({name: value['run_id'] for name, value in checkpoint.get('admissions', {}).items()
        if value.get('run_id') and value.get('objective_ref') == objective})
    return related


def require_experiment_analysis(*, db, row, checkpoint, artifacts, runs, navigation_limit):
    """A final goal disposition consumes analyses of its exact accepted experiments."""
    from ..schema.layered_diagnosis import LayeredDiagnosisReport
    if not row['objective_ref_json']:
        return
    objective = json.loads(row['objective_ref_json'])
    related = goal_bound_runs(checkpoint, objective)
    if artifacts is None or runs is None:
        raise ValueError('Goal completion requires the bound scientific result services.')
    experiments, omitted = runs.goal_experiment_runs(instance_id=row['instance_id'], objective=objective,
        related_run_ids=set(related.values()), limit=navigation_limit)
    if omitted:
        raise ValueError('Goal experiment scope is incomplete; repair its exact bindings or report completed=false.')
    for run_id in experiments:
        experiment = runs.status(run_id)
        if experiment.state in {'queued', 'running'}:
            raise ValueError('An accepted experiment is still in flight or its scientific contract is unavailable. '
                'Report completed=false while its result and analysis remain outstanding.')
        if experiment.state != 'completed':
            continue
        covered = False
        analyses = runs.related_runs(instance_id=row['instance_id'], artifact_ref=experiment.output_ref, limit=101)
        for analysis in analyses:
            if (analysis.state != 'completed' or analysis.output_ref is None
                    or analysis.output_ref.schema_id != 'scidiscovery.layered-diagnosis.v1'):
                continue
            if not any(item.artifact_ref == experiment.output_ref and item.usage in {'claim_evidence', 'evidence_inventory'}
                       for item in analysis.inputs):
                continue
            LayeredDiagnosisReport.model_validate_json(artifacts.read(analysis.output_ref), strict=True)
            covered = True
            break
        if not covered:
            raise ValueError('An accepted experiment lacks a completed analysis of its exact report'
                + ('; analysis navigation is incomplete' if len(analyses) == 101 else '')
                + '. Dispatch its analysis, or report completed=false with the remaining limitation.')


def record_assessments(*, db, row, assessments, bindings, artifacts, runs):
    """Called inside the same scheduling guard/transaction as the goal report."""
    if not assessments:
        return []
    if not row['objective_ref_json']:
        raise ValueError('Start an explicit frozen goal before recording its progress.')
    objective = ArtifactRef.model_validate_json(row['objective_ref_json'])
    goal_key = canonical_sha256(objective)
    checkpoint = json.loads(row['checkpoint_json'])
    related = set(goal_bound_runs(checkpoint, objective.model_dump(mode='json')).values())
    validated, seen = [], set()
    for raw in assessments:
        assessment = ProgressAssessment.model_validate(raw)
        run_id = bindings.resolve(instance=row['instance_id'], namespace='run', name=assessment.task_name)
        if run_id in seen:
            raise ValueError('Assess a task at most once per report; corrections use a later report.')
        seen.add(run_id)
        value = runs.status(run_id)
        if run_id not in related:
            from .progression_records import goal_admission_run
            exact = goal_admission_run(db, row['instance_id'], assessment.task_name,
                objective.model_dump(mode='json'), bindings=bindings)
            if exact:
                related.add(exact)
        if run_id not in related:
            limits = json.loads(row['config_json']).get('effective', {}).get('progression', {})
            candidates, _ = runs.goal_related_runs(instance_id=row['instance_id'], artifact_ref=objective,
                limit=101, source_limit=limits.get('related_source_limit', 128))
            related.update(item.run_id for item in candidates)
        if value.instance_id != row['instance_id'] or run_id not in related:
            raise ValueError('Task is not associated with this exact frozen goal; retain unknown rather than infer a binding.')
        if value.state in {'queued', 'running'}:
            raise ValueError('Progress assessment consumes a terminal task; report a waiting condition in summary instead.')
        evidence = []
        for name in assessment.evidence_names:
            ref = artifacts.get_by_id(bindings.resolve(instance=row['instance_id'], namespace='artifact', name=name)).ref
            catalog = artifacts.catalog(ref)
            if not is_scientific_original(catalog):
                raise ValueError('Evidence must be a visible scientific original, not private control records.')
            evidence.append(dict(name=name, ref=ref.model_dump(mode='json')))
        validated.append((assessment, value, evidence))
    receipts = []
    for assessment, value, evidence in validated:
        previous = db.execute('SELECT * FROM scheduler_progress_assessments WHERE instance_id=? AND goal_key=? '
            'AND run_id=? ORDER BY revision DESC LIMIT 1', (row['instance_id'], goal_key, value.run_id)).fetchone()
        previous_ref = ArtifactRef.model_validate_json(previous['artifact_ref_json']) if previous else None
        content = dict(assessment=assessment.model_dump(),
            output_ref=value.output_ref.model_dump(mode='json') if value.output_ref else None, evidence=evidence)
        if previous_ref:
            prior = json.loads(artifacts.read(previous_ref))
            if all(prior[key] == content[key] for key in content):
                receipts.append(dict(task_name=assessment.task_name, revision=previous['revision'], state='unchanged'))
                continue
        parents = [objective] + ([value.output_ref] if value.output_ref else [])
        parents.extend(ArtifactRef.model_validate(item['ref']) for item in evidence)
        revision = previous['revision'] + 1 if previous else 1
        body = dict(schema_version=1, objective_ref=objective.model_dump(mode='json'),
            run_id=value.run_id, source_session=row['owner_session'], revision=revision,
            previous=previous_ref.model_dump(mode='json') if previous_ref else None, **content)
        ref = _freeze(artifacts, 'progress_assessment', body, parents, previous_ref)
        sequence = db.execute('SELECT coalesce(max(sequence),0)+1 FROM scheduler_progress_assessments WHERE instance_id=?',
            (row['instance_id'],)).fetchone()[0]
        db.execute('INSERT INTO scheduler_progress_assessments '
            '(instance_id,goal_key,run_id,task_name,revision,artifact_ref_json,sequence) VALUES(?,?,?,?,?,?,?)',
            (row['instance_id'], goal_key, value.run_id, assessment.task_name, revision, ref.model_dump_json(), sequence))
        supported = content['output_ref'] is not None and any(
            item['ref'] == content['output_ref'] for item in evidence)
        _update_fact(db, row['instance_id'], goal_key, value.run_id, dict(assessment=dict(
            classification=assessment.outcome if supported else 'unknown', supported=supported,
            evidence=evidence, revision=revision, assessment_ref=ref.model_dump(mode='json'))))
        receipts.append(dict(task_name=assessment.task_name, revision=revision, state='recorded'))
    if any(item['state'] == 'recorded' for item in receipts):
        refresh_shadow(db, row, goal_key)
    return receipts


def assessment_projection(artifacts, row):
    body = json.loads(artifacts.read(ArtifactRef.model_validate_json(row['artifact_ref_json'])))
    assessment = body['assessment']
    supported = body['output_ref'] is not None and any(item['ref'] == body['output_ref'] for item in body['evidence'])
    # A named output establishes provenance, not the truth of the Root judgment.
    return dict(task_name=row['task_name'], revision=row['revision'], authority='root_judgment',
        assessment=assessment, classification=assessment['outcome'] if supported else 'unknown',
        evidence_support='sealed_output_referenced' if supported else 'missing_task_output',
        scientific_validity='not_mechanically_verified')


def progress_page(*, bindings, artifacts, row, cursor=None, limit=4):
    if not 1 <= limit <= 8:
        raise ValueError('invalid progress pagination')
    if not row.get('objective_ref_json'):
        if cursor is not None:
            raise ValueError('Progress cursor requires its frozen goal.')
        return dict(items=[], next_cursor=None)
    scope = canonical_sha256(dict(instance=row['instance_id'], objective=json.loads(row['objective_ref_json'])))
    after = 0
    if cursor is not None:
        try:
            position = json.loads(base64.b64decode(cursor, altchars=b'-_', validate=True))
            after = position['before']
            if position['scope'] != scope or type(after) is not int or after <= 0:
                raise ValueError('wrong scope')
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError('Invalid progress cursor; restart history for this frozen goal.') from error
    records = bindings.progress_assessments(instance_id=row['instance_id'],
        objective_ref=ArtifactRef.model_validate_json(row['objective_ref_json']), after=after, limit=limit+1)
    from ...agent_execution_settings import ProgressionSettings
    limits = json.loads(row['config_json']).get('effective', {}).get('progression', {})
    budget = limits.get('progress_read_bytes', ProgressionSettings().progress_read_bytes)
    page = dict(items=[], next_cursor=None, authority='root_judgment_not_worker_conclusion',
        missing_assessment='unknown', continuation=dict(tool='progression_status', progress_limit=limit))
    for index, record in enumerate(records[:limit]):
        candidate = dict(page, items=[*page['items'], assessment_projection(artifacts, record)],
            next_cursor=base64.urlsafe_b64encode(canonical_json(dict(scope=scope, before=record['sequence']))).decode()
                if index+1 < len(records) else None)
        if len(canonical_json(candidate)) > budget:
            if not page['items']:
                raise ValueError('Progress record exceeds configured page capacity.')
            break
        page = candidate
    return page


def _update_fact(db, instance_id, goal_key, run_id, change):
    previous = db.execute('SELECT fact_json FROM scheduler_progress_facts '
        'WHERE instance_id=? AND goal_key=? AND run_id=?', (instance_id, goal_key, run_id)).fetchone()
    fact = json.loads(previous['fact_json']) if previous else {}
    fact.update(change)
    db.execute('INSERT INTO scheduler_progress_facts VALUES(?,?,?,?) '
        'ON CONFLICT(instance_id,goal_key,run_id) DO UPDATE SET fact_json=excluded.fact_json',
        (instance_id, goal_key, run_id, json.dumps(fact)))


def _consumption_high_water(db, instance_id):
    record = db.execute("SELECT coalesce(max(json_extract(f.fact_json,'$.consumption_sequence')),0) AS position, "
        "sum(CASE WHEN json_type(f.fact_json,'$.consumption_sequence')='integer' "
        "AND json_extract(f.fact_json,'$.consumption_sequence')>0 THEN 0 ELSE 1 END) AS invalid "
        'FROM scheduler_terminal_deliveries d LEFT JOIN scheduler_progress_facts f '
        'USING(instance_id,goal_key,run_id) WHERE d.instance_id=? AND d.consumed_boundary IS NOT NULL',
        (instance_id,)).fetchone()
    if record['invalid']:
        raise ValueError('Incompatible progress state: confirmed consumption position is missing; use a new empty state root.')
    return record['position']


def _consumed_fact(record):
    fact = json.loads(record['fact_json'])
    position = fact.get('consumption_sequence')
    if type(position) is not int or position <= 0:
        raise ValueError('Confirmed delivery requires its actual consumption position.')
    # Reducers and window watermarks use consumption only. Delivery cursors keep
    # the original terminal_deliveries.sequence and never change meaning.
    return dict(fact, sequence=position)


def shadow_policy(row):
    from ...agent_execution_settings import ProgressionSettings
    frozen = json.loads(row['config_json']).get('effective', {}).get('progression', {})
    defaults = ProgressionSettings().model_dump()
    keys = ('progress_mode', 'no_progress_threshold', 'refinement_threshold', 'observation_gap_threshold',
        'max_tasks', 'max_reviews')
    policy = {key: frozen.get(key, defaults[key]) for key in keys}
    # A prior grant did not authorize the new checkpoint. It remains legacy
    # behavior until an explicit new loop configuration contains this key.
    policy['unverified_progress_threshold'] = frozen.get('unverified_progress_threshold')
    # Old goals must explicitly restart to adopt a newly introduced policy.
    if 'progress_mode' not in frozen:
        policy['progress_mode'] = 'off'
    return policy


def freeze_observation_scope(db, row, reader, bindings, *, background_reader=None):
    """Freeze exact pre-start terminal identities once per goal, under scheduling lock.

    Existing consumption and admissions remain observed. Neither a restart nor a
    new host may turn those tasks into background or replenish their allowance.
    The JSON lives in the existing archived progress state, including in off mode.
    """
    objective = ArtifactRef.model_validate_json(row['objective_ref_json'])
    goal_key = canonical_sha256(objective)
    if shadow_policy(row)['unverified_progress_threshold'] is not None:
        through = _consumption_high_water(db, row['instance_id'])
        db.execute('INSERT OR IGNORE INTO scheduler_progress_shadow VALUES(?,?,?)',
            (row['instance_id'], EXPLORATION_KEY, json.dumps(dict(initial_sequence=through,
                window_start_sequence=through, through_sequence=through, counts={}, notices=[], dispositions=[]))))
    previous = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], goal_key)).fetchone()
    state = json.loads(previous['state_json']) if previous else {}
    if 'observation_scope' in state:
        return
    checkpoint = json.loads(row['checkpoint_json'])
    observed = {item['run_id'] for item in db.execute('SELECT run_id FROM scheduler_terminal_deliveries '
        'WHERE instance_id=?', (row['instance_id'],))}
    observed.update(item['run_id'] for item in checkpoint.get('admissions', {}).values()
        if item.get('run_id') and item.get('state') == 'accepted')
    frozen_scopes = []
    for item in db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=?', (row['instance_id'],)):
        existing = json.loads(item['state_json'])
        if 'observation_scope' in existing:
            frozen_scopes.append(existing['observation_scope'])
            observed.update(existing['observation_scope'].get('initial_observed', []))
    global_record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], EXPLORATION_KEY)).fetchone()
    if global_record:
        global_state = json.loads(global_record['state_json'])
        if 'background_history' not in global_state and not frozen_scopes and background_reader:
            global_state.update(background_history=background_reader(instance_id=row['instance_id'], observed=observed),
                observed_before_start=sorted(observed))
            db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=? AND goal_key=?',
                (json.dumps(global_state), row['instance_id'], EXPLORATION_KEY))
    limits = json.loads(row['config_json'])['effective']['progression']
    related, omitted = reader(instance_id=row['instance_id'], artifact_ref=objective,
        limit=17, source_limit=limits['related_source_limit'])
    background, relevant, ongoing = {}, {}, set()
    for run in related[:16]:
        name = bindings.find_name(instance=row['instance_id'], namespace='run', object_id=run.run_id)
        if not name:
            omitted = True
            continue
        relevant[name] = run.run_id
        if run.state in {'queued', 'running'}:
            ongoing.add(run.run_id)
        elif run.run_id not in observed:
            background[run.run_id] = dict(task_name=name,
                output=run.output_ref.model_dump(mode='json') if run.output_ref else None)
    # The pre-existing observed/running set is finite and independent of the new
    # task admission allowance. No moving window can make old bytes novel again.
    state['observation_scope'] = dict(background=background, relevant_runs=relevant,
        initial_observed=sorted(observed | ongoing),
        max_observed_tasks=limits['max_tasks'] + limits['max_reviews'] + len(observed | ongoing),
        related_omitted=bool(omitted or len(related) > 16))
    db.execute('INSERT INTO scheduler_progress_shadow VALUES(?,?,?) '
        'ON CONFLICT(instance_id,goal_key) DO UPDATE SET state_json=excluded.state_json',
        (row['instance_id'], goal_key, json.dumps(state)))


def observation_facts(db, row, goal_key, policy, state):
    """One ordered, cumulative selection for counters and assist snapshots."""
    scope = state.get('observation_scope', {})
    background = scope.get('background', {})
    limit = scope.get('max_observed_tasks', policy['max_tasks'])
    checkpoint = json.loads(dict(row).get('checkpoint_json', '{}'))
    if checkpoint.get('current_loop_id'):
        # Authorization extends the finite read capacity, never the scientific
        # window or a prior trigger. Include later loops on this same goal.
        limit = max(limit, len(scope.get('initial_observed', [])) + sum(
            sum(record['config']['effective']['progression'][key] for key in ('max_tasks', 'max_reviews'))
            for record in checkpoint.get('loop_authorizations', {}).values()))
    exclusion = (' AND d.run_id NOT IN (' + ','.join('?' for _ in background) + ')') if background else ''
    selected = [item['run_id'] for item in checkpoint.get('admissions', {}).values()
        if item.get('run_id') and item.get('interactive_session_id')]
    if selected:
        exclusion += ' AND d.run_id NOT IN (' + ','.join('?' for _ in selected) + ')'
    _consumption_high_water(db, row['instance_id'])
    records = db.execute('SELECT f.fact_json FROM scheduler_terminal_deliveries d '
        'JOIN scheduler_progress_facts f USING(instance_id,goal_key,run_id) '
        'WHERE d.instance_id=? AND d.goal_key=? AND d.consumed_boundary IS NOT NULL '
        "AND coalesce(json_extract(f.fact_json,'$.observation_role'),'observed')='observed'" + exclusion +
        " ORDER BY json_extract(f.fact_json,'$.consumption_sequence') LIMIT ?",
        (row['instance_id'], goal_key, *background, *selected, limit + 1)).fetchall()
    return [_consumed_fact(item) for item in records[:limit]], len(records) > limit


def reduce_shadow(facts, *, advances=None, known_evidence=(), known_resolutions=(), known_cycles=(), allow_root_advance=False,
                  allow_new_resolution=True):
    """Content identity detects reuse, never scientific truth or semantic equivalence."""
    counts = dict(consumed=0, no_progress=0, refinement=0, coverage_gap=0, unchanged_evidence=0,
        repeated_failure=0)
    duplicates = []
    facts, awaiting = cycle_facts(facts, known_cycles=known_cycles, duplicates=duplicates)
    counts['awaiting_analysis'] = awaiting
    counts['repeated_analysis'] = len(duplicates)
    refs = {canonical_sha256(ref) for ref in known_evidence}
    digests = {ref['sha256'] for ref in known_evidence}
    failure = None
    resolved_checks = set(known_resolutions)
    for fact in facts:
        verified = progress_families(fact)
        new_resolution = allow_new_resolution and any(item['key'] not in resolved_checks for item in verified)
        resolved_checks.update(item['key'] for item in verified)
        if (fact.get('task_classification') or {}).get('kind') == 'independent_review':
            if new_resolution:
                for key in counts:
                    if key not in {'consumed', 'awaiting_analysis', 'repeated_analysis'}:
                        counts[key] = 0
                if advances is not None:
                    advances.append(fact['sequence'])
            continue  # Delivery and assessment history remain; review is not a new exploration.
        counts['consumed'] += 1
        scientific = fact['terminal'].get('scientific_progress') or {}
        assessment = (dict(classification=scientific.get('outcome', 'unknown'), supported=scientific.get('status') == 'worker_assessed',
            evidence=scientific.get('evidence', [])) if scientific.get('stage') == 'analysis' else fact.get('assessment') or {})
        classification = assessment.get('classification', 'unknown')
        if scientific.get('stage') == 'analysis' and classification == 'advance' and not new_resolution:
            # A supported directional judgment may repeat a known family. Its
            # science remains intact, but it supplies no new decision increment
            # even when the legacy policy has no exploration-window reducer.
            classification = 'unknown'
        supported = assessment.get('supported', False)
        evidence = assessment.get('evidence', []) if supported else []
        novel = any(canonical_sha256(item['ref']) not in refs and item['ref']['sha256'] not in digests
            for item in evidence)
        refs.update(canonical_sha256(item['ref']) for item in evidence)
        digests.update(item['ref']['sha256'] for item in evidence)
        counts['unchanged_evidence'] = 0 if novel else counts['unchanged_evidence'] + 1
        gap = (not fact.get('intent') and scientific.get('stage') != 'analysis') or not supported or classification == 'unknown'
        counts['coverage_gap'] = counts['coverage_gap'] + 1 if gap else 0
        if classification == 'no_progress' and supported:
            counts['no_progress'] += 1
        if new_resolution or (allow_root_advance and scientific.get('stage') != 'analysis'
                and classification == 'advance' and supported and novel):
            counts['no_progress'] = 0
            counts['refinement'] = counts['coverage_gap'] = counts['unchanged_evidence'] = 0
            counts['repeated_analysis'] = sum(item['sequence'] > fact['sequence'] for item in duplicates)
            if advances is not None:
                advances.append(fact['sequence'])
        counts['refinement'] = counts['refinement'] + 1 if (fact.get('intent') or {}).get('intent') == 'refine' else 0
        if new_resolution:
            counts['refinement'] = 0
        terminal = fact['terminal']
        current = terminal.get('failure_key') if terminal['state'] in {'failed', 'timed_out'} else None
        counts['repeated_failure'] = (counts['repeated_failure'] + 1 if current == failure else 1) if current else 0
        failure = current
    return counts


def refresh_shadow(db, row, goal_key):
    """Only consumption/assessment mutations call this bounded replay, never reads/ticks.

    The frozen observation scope separates background from the task allowance.
    """
    policy = shadow_policy(row)
    if policy['progress_mode'] == 'off':
        return
    previous = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], goal_key)).fetchone()
    prior = json.loads(previous['state_json']) if previous else {}
    facts, omitted = observation_facts(db, row, goal_key, policy, prior)
    window_start = prior.get('window_start_sequence', 0)
    prior_through = prior.get('through_sequence', 0)
    prior_facts, facts = [f for f in facts if f['sequence'] <= window_start], [f for f in facts if f['sequence'] > window_start]
    advances = []
    background_keys, background_complete = _background_knowledge(db, row)
    counts = reduce_shadow(facts, advances=advances, allow_root_advance=policy['unverified_progress_threshold'] is None,
        allow_new_resolution=background_complete,
        known_cycles=[*_background_cycles(db, row), *((fact['terminal'].get('scientific_progress') or {}).get('cycle_key')
            for fact in prior_facts if (fact['terminal'].get('scientific_progress') or {}).get('stage') == 'analysis')],
        known_resolutions=[*background_keys, *[resolution['key'] for fact in prior_facts
            for resolution in progress_families(fact)]], known_evidence=[item['output']
        for item in prior.get('observation_scope', {}).get('background', {}).values() if item['output']] +
        [item['ref'] for fact in prior_facts if (fact.get('assessment') or {}).get('supported')
            for item in fact['assessment'].get('evidence', [])])
    notices = list(prior.get('notices', []))
    dispositions = list(prior.get('dispositions', []))
    resolved = {item['notice_id'] for item in dispositions}
    thresholds = dict(no_progress=policy['no_progress_threshold'], refinement=policy['refinement_threshold'],
        coverage_gap=policy['observation_gap_threshold'], unchanged_evidence=policy['observation_gap_threshold'],
        repeated_failure=policy['observation_gap_threshold'])
    thresholds['awaiting_analysis'] = policy['observation_gap_threshold']
    thresholds['repeated_analysis'] = policy['observation_gap_threshold']
    for reason, threshold in thresholds.items():
        active = next((item for item in reversed(notices) if item['reason'] == reason and item['id'] not in resolved
            and item['policy']['progress_mode'] == policy['progress_mode']), None)
        # Only a newly consumed, supported advance can close a cause episode.
        # Late assessments update current counts, never withdraw old notices.
        if active and counts[reason] < threshold and any(
                sequence > max(window_start, active['through_sequence'], prior_through) for sequence in advances):
            dispositions.append(dict(notice_id=active['id'], state='new_evidence_after_trigger',
                through_sequence=facts[-1]['sequence']))
            active = None
        if counts[reason] < threshold or active:
            continue
        notices.append(dict(id=canonical_sha256(dict(goal=goal_key, reason=reason,
            sequence=facts[-1]['sequence'], mode=policy['progress_mode'])), reason=reason,
            trigger_counts=counts.copy(), policy=policy, through_sequence=facts[-1]['sequence'],
            task_names=[item['task_name'] for item in facts],
            assessment_refs=[item['assessment']['assessment_ref'] for item in facts if item.get('assessment')],
            would_act='refinement_hint' if reason == 'refinement' and policy['unverified_progress_threshold'] is None else 'pause_dispatch',
            state='shadow_recorded', dispatch_changed=False))
    state = dict(counts=counts, notices=notices, dispositions=dispositions,
        through_sequence=max([window_start, *(fact['sequence'] for fact in facts)]),
        window_start_sequence=window_start, omitted=omitted)
    if 'observation_scope' in prior:
        state['observation_scope'] = prior['observation_scope']
    encoded = json.dumps(state, sort_keys=True)
    if not previous or json.loads(previous['state_json']) != state:
        db.execute('INSERT INTO scheduler_progress_shadow VALUES(?,?,?) '
            'ON CONFLICT(instance_id,goal_key) DO UPDATE SET state_json=excluded.state_json',
            (row['instance_id'], goal_key, encoded))
    refresh_exploration(db, row, goal_key)


def exploration_facts(db, row):
    """Same durable consumption ledger, once per Run across goal revisions."""
    checkpoint = json.loads(dict(row).get('checkpoint_json', '{}'))
    limits = json.loads(row['config_json']).get('effective', {}).get('progression', {})
    capacity = max(limits.get('max_tasks', 8) + limits.get('max_reviews', 2),
        len(checkpoint.get('admissions', {})), sum(
            value['config']['effective']['progression']['max_tasks'] + value['config']['effective']['progression']['max_reviews']
            for value in checkpoint.get('loop_authorizations', {}).values()))
    excluded = {item['run_id'] for item in checkpoint.get('admissions', {}).values()
        if item.get('interactive_session_id') and item.get('run_id')}
    initial_record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], EXPLORATION_KEY)).fetchone()
    initial = json.loads(initial_record['state_json']).get('initial_sequence', 0) if initial_record else 0
    _consumption_high_water(db, row['instance_id'])
    exclusion = (' AND run_id NOT IN (' + ','.join('?' for _ in excluded) + ')') if excluded else ''
    # Choose each Run's first actual consumption across all goals before either
    # the initial window or the bounded read. Later re-deliveries cannot occupy
    # the prefix or make a previously consumed Run novel after a UI window.
    selected = db.execute("WITH consumed AS (SELECT d.run_id,f.fact_json, "
        "json_extract(f.fact_json,'$.consumption_sequence') AS position, "
        "row_number() OVER (PARTITION BY d.run_id ORDER BY json_extract(f.fact_json,'$.consumption_sequence')) AS occurrence "
        'FROM scheduler_terminal_deliveries d JOIN scheduler_progress_facts f USING(instance_id,goal_key,run_id) '
        'WHERE d.instance_id=? AND d.consumed_boundary IS NOT NULL) '
        "SELECT fact_json FROM consumed WHERE occurrence=1 AND position>? "
        "AND coalesce(json_extract(fact_json,'$.observation_role'),'observed')='observed'" + exclusion +
        ' ORDER BY position LIMIT ?', (row['instance_id'], initial, *excluded, capacity + 1)).fetchall()
    return [_consumed_fact(item) for item in selected[:capacity]], len(selected) > capacity


def _background_knowledge(db, row):
    record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], EXPLORATION_KEY)).fetchone()
    state = json.loads(record['state_json']) if record else {}
    history = state.get('background_history', {})
    keys = set(history.get('known_resolutions', []))
    # Background tasks outside the startup proof budget can still provide exact
    # known families when actually delivered. They never produce new progress.
    for item in db.execute("SELECT DISTINCT json_extract(value.value,'$.key') AS family FROM scheduler_progress_facts f, "
        "json_each(f.fact_json,'$.terminal.verified_progress.resolutions') value WHERE f.instance_id=? "
        "AND json_extract(f.fact_json,'$.observation_role')='background' "
        "AND json_extract(f.fact_json,'$.terminal.verified_progress.status')='verified_test_resolution' LIMIT 129",
        (row['instance_id'],)):
        keys.add(item['family'])
    for item in db.execute("SELECT DISTINCT json_extract(value.value,'$.key') AS family FROM scheduler_progress_facts f, "
        "json_each(f.fact_json,'$.terminal.scientific_progress.families') value WHERE f.instance_id=? "
        "AND json_extract(f.fact_json,'$.observation_role')='background' "
        "AND json_extract(f.fact_json,'$.terminal.scientific_progress.status')='worker_assessed' LIMIT 129",
        (row['instance_id'],)):
        keys.add(item['family'])
    # Omitted or corrupt background proof is explicit uncertainty about novelty,
    # not an execution gate or evidence of scientific failure.
    checked = history.get('checked_runs', [])
    additional = db.execute("SELECT count(DISTINCT run_id) FROM scheduler_progress_facts WHERE instance_id=? "
        "AND json_extract(fact_json,'$.observation_role')='background' "
        "AND json_extract(fact_json,'$.terminal.verified_progress.reason') NOT LIKE '%unavailable%' "
        "AND json_extract(fact_json,'$.terminal.verified_progress.reason') NOT LIKE '%inconsistent%' "
        "AND json_extract(fact_json,'$.terminal.verified_progress.reason') NOT LIKE '%missing%' "
        "AND json_extract(fact_json,'$.terminal.verified_progress.reason') NOT LIKE '%ambiguous%' "
        "AND coalesce(json_extract(fact_json,'$.terminal.scientific_progress.reason'),'') NOT LIKE '%unavailable%' "
        "AND coalesce(json_extract(fact_json,'$.terminal.scientific_progress.reason'),'') NOT LIKE '%inconsistent%' "
        "AND coalesce(json_extract(fact_json,'$.terminal.scientific_progress.reason'),'') NOT LIKE '%omitted%' "
        "AND coalesce(json_extract(fact_json,'$.terminal.scientific_progress.reason'),'') NOT LIKE '%projector_failed%' "
        "AND run_id NOT IN (SELECT value FROM json_each(?))", (row['instance_id'], json.dumps(checked))).fetchone()[0]
    # Checking every Run cannot recover families discarded from its proof.
    # Preserve that uncertainty even when a later bounded read has 128 keys.
    # Earlier snapshots without the specific flag cannot prove which omission
    # occurred, so their generic omission remains conservative uncertainty.
    family_omitted = history.get('family_omitted', history.get('proof_omitted', False))
    complete = not family_omitted and len(checked) + additional >= history.get('candidate_count', 0) and len(keys) <= 128
    return keys, complete


def _background_cycles(db, row):
    record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], EXPLORATION_KEY)).fetchone()
    history = json.loads(record['state_json']).get('background_history', {}) if record else {}
    cycles = set(history.get('known_cycles', []))
    cycles.update(item['cycle'] for item in db.execute(
        "SELECT DISTINCT json_extract(fact_json,'$.terminal.scientific_progress.cycle_key') AS cycle "
        "FROM scheduler_progress_facts WHERE instance_id=? AND json_extract(fact_json,'$.observation_role')='background' "
        "AND json_extract(fact_json,'$.terminal.scientific_progress.stage')='analysis' LIMIT 129", (row['instance_id'],)))
    return cycles


def refresh_exploration(db, row, goal_key):
    policy = shadow_policy(row)
    if policy['unverified_progress_threshold'] is None:
        return
    record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], EXPLORATION_KEY)).fetchone()
    prior = json.loads(record['state_json']) if record else {}
    facts, omitted = exploration_facts(db, row)
    initial = prior.get('initial_sequence', 0)
    start = prior.get('window_start_sequence', initial)
    background_keys, background_complete = _background_knowledge(db, row)
    resolved_checks, advances, unverified, research = set(background_keys), [], 0, 0
    through = max([start, *(f['sequence'] for f in facts)])
    duplicates = []
    facts, awaiting = cycle_facts(facts, start=start, known_cycles=_background_cycles(db, row), duplicates=duplicates)
    worker_changes, strong_changes = set(), set()
    for fact in facts:
        resolutions = progress_families(fact)
        fresh = background_complete and any(item['key'] not in resolved_checks for item in resolutions)
        resolved_checks.update(item['key'] for item in resolutions)
        proof = fact['terminal'].get('verified_progress') or {}
        strong_changes.update(item['key'] for item in proof.get('resolutions', []) if proof.get('status') == 'verified_test_resolution')
        worker_changes.update(item['key'] for item in (fact['terminal'].get('scientific_progress') or {}).get('families', []))
        if fact['sequence'] <= start:
            continue
        review = (fact.get('task_classification') or {}).get('kind') == 'independent_review'
        if not review:
            research += 1
            unverified += 1
        if fresh:
            unverified = 0
            advances.append(fact['sequence'])
    counts = dict(unverified_progress=unverified, consumed_research_tasks=research,
        verified_test_resolutions=len(strong_changes - background_keys),
        assessed_scientific_changes=len(worker_changes - background_keys), awaiting_analysis=awaiting,
        repeated_analysis=sum(item['sequence'] > max([start, *advances]) for item in duplicates))
    notices, dispositions = list(prior.get('notices', [])), list(prior.get('dispositions', []))
    resolved = {item['notice_id'] for item in dispositions}
    for notice in notices:
        if notice['id'] not in resolved and any(sequence > max(notice['through_sequence'], prior.get('through_sequence', 0))
                for sequence in advances):
            dispositions.append(dict(notice_id=notice['id'], state='new_supported_result_after_trigger', through_sequence=through))
            resolved.add(notice['id'])
    thresholds = dict(unverified_progress=policy['unverified_progress_threshold'],
        awaiting_analysis=policy['observation_gap_threshold'], repeated_analysis=policy['observation_gap_threshold'])
    for reason, threshold in thresholds.items():
        active = next((item for item in reversed(notices) if item['reason'] == reason and item['id'] not in resolved
            and item['policy']['progress_mode'] == policy['progress_mode']), None)
        if counts[reason] >= threshold and not active:
            notices.append(dict(id=canonical_sha256(dict(instance=row['instance_id'], reason=reason,
                    sequence=through, mode=policy['progress_mode'])),
                goal_key=goal_key, reason=reason, trigger_counts=counts.copy(), policy=policy,
                through_sequence=through, would_act='pause_dispatch', state='shadow_recorded', dispatch_changed=False))
    state = dict(initial_sequence=initial, window_start_sequence=start, through_sequence=through,
        counts=counts, notices=notices, dispositions=dispositions, omitted=omitted,
        scope='instance_consumed_research_across_goals_and_loops')
    for key in ('background_history', 'observed_before_start'):
        if key in prior:
            state[key] = prior[key]
    state['background_proof_coverage'] = 'complete' if background_complete else 'bounded_unknown'
    if state != prior:
        db.execute('INSERT INTO scheduler_progress_shadow VALUES(?,?,?) '
            'ON CONFLICT(instance_id,goal_key) DO UPDATE SET state_json=excluded.state_json',
            (row['instance_id'], EXPLORATION_KEY, json.dumps(state)))



def interactive_consent_active(row, checkpoint, collection):
    """UI consent applies to exactly one goal, owner and control generation."""
    records = checkpoint.get(collection, [])
    if not records:
        return False
    consent = records[-1]
    return (row['state'] == 'active' and row['mode'] == 'interactive'
        and consent['generation'] == row['generation']
        and consent['session_key'] == row['owner_session']
        and consent['objective_ref_json'] == row['objective_ref_json'])


def human_continuation_active(row, checkpoint):
    return interactive_consent_active(row, checkpoint, 'human_continuations')


def independent_interactive_active(row, checkpoint):
    return interactive_consent_active(row, checkpoint, 'interactive_sessions')


def scientific_pause(db, row, checkpoint):
    """Unresolved assist triggers are facts, shared by every dispatch entry."""
    if independent_interactive_active(row, checkpoint):
        return None  # Exact UI authorization permits manual work, never clears background triggers.
    causes = []
    for record in db.execute('SELECT goal_key,state_json FROM scheduler_progress_shadow WHERE instance_id=?',
            (row['instance_id'],)):
        state = json.loads(record['state_json'])
        resolved = {item['notice_id'] for item in state.get('dispositions', [])}
        causes.extend(dict(goal_key=item.get('goal_key', record['goal_key']), progress_state_key=record['goal_key'], id=item['id'], reason=item['reason'],
            through_sequence=state.get('through_sequence', 0)) for item in state.get('notices', [])
            if item['id'] not in resolved and item['would_act'] == 'pause_dispatch'
            and item['policy']['progress_mode'] == 'assist')
    return dict(causes=causes) if causes else None


def open_observation_window(db, row):
    """UI decision moves only the consumed start; old triggers remain immutable."""
    goal_key = canonical_sha256(json.loads(row['objective_ref_json']))
    record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], goal_key)).fetchone()
    state = json.loads(record['state_json']) if record else {}
    policy = shadow_policy(row)
    facts, _ = observation_facts(db, row, goal_key, policy, state)
    through = max([0, *(fact['sequence'] for fact in facts)])
    resolved = {item['notice_id'] for item in state.get('dispositions', [])}
    state.setdefault('dispositions', []).extend(dict(notice_id=item['id'], state='human_continue',
        through_sequence=through) for item in state.get('notices', []) if item['id'] not in resolved)
    state['window_start_sequence'] = through
    db.execute('INSERT INTO scheduler_progress_shadow VALUES(?,?,?) '
        'ON CONFLICT(instance_id,goal_key) DO UPDATE SET state_json=excluded.state_json',
        (row['instance_id'], goal_key, json.dumps(state)))
    refresh_shadow(db, row, goal_key)
    record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], EXPLORATION_KEY)).fetchone()
    if record:
        state = json.loads(record['state_json'])
        global_facts, _ = exploration_facts(db, row)
        through = max([through, *(fact['sequence'] for fact in global_facts)])
        resolved = {item['notice_id'] for item in state.get('dispositions', [])}
        state['dispositions'].extend(dict(notice_id=item['id'], state='human_continue', through_sequence=through)
            for item in state['notices'] if item['id'] not in resolved)
        state['window_start_sequence'] = through
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=? AND goal_key=?',
            (json.dumps(state), row['instance_id'], EXPLORATION_KEY))
        refresh_exploration(db, row, goal_key)
    return through


def shadow_projection(*, bindings, row):
    policy = shadow_policy(row)
    state = bindings.progress_shadow(instance_id=row['instance_id'],
        objective_ref=ArtifactRef.model_validate_json(row['objective_ref_json'])) or {}
    scope = state.get('observation_scope', {})
    # Notice snapshots stay in the DB; the common public projection is bounded.
    return dict(mode=policy['progress_mode'], policy=policy, counts=state.get('counts', reduce_shadow([])),
        position_basis='first_confirmed_consumption', counting_basis='one_exact_interpreted_question',
        background_proof_coverage=state.get('background_proof_coverage', 'complete'),
        window_start_sequence=state.get('window_start_sequence', 0),
        notices=[{key: item[key] for key in ('id', 'reason', 'trigger_counts', 'through_sequence', 'would_act', 'state',
            'dispatch_changed')} for item in state.get('notices', [])[-5:]],
        notices_omitted=max(0, len(state.get('notices', []))-5),
        dispositions=state.get('dispositions', [])[-5:],
        dispositions_omitted=max(0, len(state.get('dispositions', []))-5),
        delivery_history_read=dict(tool='progression_status', delivery_limit=8),
        notice_history_coverage='recent_only',
        through_sequence=state.get('through_sequence', 0), omitted=state.get('omitted', False),
        observation_scope=dict(background_tasks=len(scope.get('background', {})),
            initial_observed_tasks=len(scope.get('initial_observed', [])),
            max_observed_tasks=scope.get('max_observed_tasks', policy['max_tasks']),
            related_omitted=scope.get('related_omitted', False),
            background_role='read_only_history_and_known_evidence_not_progress_counts'),
        authority='control_observation_not_scientific_judgment',
        limitations=['Exact references and payload digests detect identical evidence, not semantic paraphrases.',
            'Assist observes process, citation coverage and repeated failures; Root judgments are not independently '
            'verified for scientific stagnation. The unverified window requires direction confirmation, not a stagnation verdict.',
            'First source-bound Worker assessments of a scientific dimension can clear the observation window; '
            'this is not independent scientific verification. Stable objective/dimension/outcome identities detect '
            'reuse, not semantic novelty across renamed questions. Repeated local optimization and new files alone do not clear it. '
            'Stronger predeclared test proofs remain supported. Their prior sealing requires '
            'exact plan and quantitative conditions (plan alone for independent qualitative review) as immutable ancestors '
            'of every observed input. Each proof checks at most 64 distinct original envelopes; absent, damaged or '
            'incompletely covered lineage remains unknown. Registration timestamps are not order proof. Sealing and '
            'controlled evaluation do not prove original generation time, source novelty or scientific authenticity. '
            'Relative improvement is not supported.',
            'Optional intent or assessments may produce process signals; new Root judgments or new bytes are not verified progress.',
            'Code-mode wrapped results are unobserved; new terminal results may arrive only in the next brief.',
            'Direct completion or stop may omit that next brief; no same-turn hard stop is claimed.'])
