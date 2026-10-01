"""Immutable Root judgments, separate from Worker science and qualification."""
import base64
import json

from ..schema.artifact import ArtifactRegistration
from .artifacts import is_scientific_original
from ..schema.common import canonical_json, canonical_sha256
from ..schema.refs import ActorRef, ArtifactRef
from ..schema.scientific_progress import ScientificIntent, ProgressAssessment


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
        sequence = db.execute('SELECT coalesce(max(sequence),0)+1 FROM scheduler_terminal_deliveries WHERE instance_id=?',
            (row['instance_id'],)).fetchone()[0]
        updated = db.execute('INSERT INTO scheduler_terminal_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(instance_id,goal_key,run_id) DO UPDATE SET '
            'delivery_json=excluded.delivery_json,host_json=excluded.host_json,turn_id=excluded.turn_id,'
            'consumed_boundary=excluded.consumed_boundary '
            'WHERE scheduler_terminal_deliveries.consumed_boundary IS NULL',
            (sequence, row['instance_id'], goal_key, item['run_id'], item['name'], json.dumps(objective),
             json.dumps(item['terminal']), json.dumps(item['delivery']), row['host_json'], turn,
             decision.get('boundary')))
        if updated.rowcount and decision.get('boundary'):
            delivery = db.execute('SELECT sequence FROM scheduler_terminal_deliveries '
                'WHERE instance_id=? AND goal_key=? AND run_id=?',
                (row['instance_id'], goal_key, item['run_id'])).fetchone()
            _update_fact(db, row['instance_id'], goal_key, item['run_id'], dict(
                sequence=delivery['sequence'], task_name=item['name'], terminal=item['terminal'],
                intent=item.get('scientific_intent'), delivery=item['delivery']))
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
        reason=value.reason)
    if value.state in {'failed', 'timed_out'}:
        failure = runs.diagnostic_summary(value).get('failure') or {}
        terminal['failure_key'] = (dict(operation_id=value.operation_id, operation_digest=value.operation_digest,
            category=failure['category'], code=failure['code'])
            if failure.get('category') and failure.get('code') else None)
        terminal['failure_classification'] = 'recorded_diagnostic' if terminal['failure_key'] else 'unknown'
    return terminal


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
        item['observation_role'] = 'background' if record['run_id'] in observation.get('background', {}) else 'observed'
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


def shadow_policy(row):
    from ...agent_execution_settings import ProgressionSettings
    frozen = json.loads(row['config_json']).get('effective', {}).get('progression', {})
    defaults = ProgressionSettings().model_dump()
    keys = ('progress_mode', 'no_progress_threshold', 'refinement_threshold', 'observation_gap_threshold',
        'progress_reassessment_limit', 'progress_pause_on_persistent_gap', 'max_tasks')
    policy = {key: frozen.get(key, defaults[key]) for key in keys}
    # Old goals must explicitly restart to adopt a newly introduced policy.
    if 'progress_mode' not in frozen:
        policy['progress_mode'] = 'off'
    return policy


def freeze_observation_scope(db, row, reader, bindings):
    """Freeze exact pre-start terminal identities once per goal, under scheduling lock.

    Existing consumption and admissions remain observed. Neither a restart nor a
    new host may turn those tasks into background or replenish their allowance.
    The JSON lives in the existing archived progress state, including in off mode.
    """
    objective = ArtifactRef.model_validate_json(row['objective_ref_json'])
    goal_key = canonical_sha256(objective)
    previous = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], goal_key)).fetchone()
    state = json.loads(previous['state_json']) if previous else {}
    if 'observation_scope' in state:
        return
    checkpoint = json.loads(row['checkpoint_json'])
    observed = {item['run_id'] for item in db.execute('SELECT run_id FROM scheduler_terminal_deliveries '
        'WHERE instance_id=? AND goal_key=?', (row['instance_id'], goal_key))}
    observed.update(item['run_id'] for item in checkpoint.get('admissions', {}).values()
        if item.get('run_id') and item.get('objective_ref') == objective.model_dump(mode='json'))
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
        max_observed_tasks=limits['max_tasks'] + len(observed | ongoing),
        related_omitted=bool(omitted or len(related) > 16))
    db.execute('INSERT INTO scheduler_progress_shadow VALUES(?,?,?) '
        'ON CONFLICT(instance_id,goal_key) DO UPDATE SET state_json=excluded.state_json',
        (row['instance_id'], goal_key, json.dumps(state)))


def observation_facts(db, row, goal_key, policy, state):
    """One ordered, cumulative selection for counters and assist snapshots."""
    scope = state.get('observation_scope', {})
    background = scope.get('background', {})
    limit = scope.get('max_observed_tasks', policy['max_tasks'])
    # Explicit human scopes add their exact accepted tasks to the observation
    # capacity, without increasing the frozen background admission allowance.
    checkpoint = json.loads(dict(row).get('checkpoint_json', '{}'))
    limit += sum(bool(item.get('interactive_session_id')) and item.get('objective_ref') ==
        json.loads(row['objective_ref_json']) for item in checkpoint.get('admissions', {}).values())
    exclusion = (' AND d.run_id NOT IN (' + ','.join('?' for _ in background) + ')') if background else ''
    records = db.execute('SELECT f.fact_json FROM scheduler_terminal_deliveries d '
        'JOIN scheduler_progress_facts f USING(instance_id,goal_key,run_id) '
        'WHERE d.instance_id=? AND d.goal_key=? AND d.consumed_boundary IS NOT NULL' + exclusion +
        ' ORDER BY d.sequence LIMIT ?', (row['instance_id'], goal_key, *background, limit + 1)).fetchall()
    return [json.loads(item['fact_json']) for item in records[:limit]], len(records) > limit


def reduce_shadow(facts, *, advances=None, known_evidence=()):
    """Content identity detects reuse, never scientific truth or semantic equivalence."""
    counts = dict(consumed=0, no_progress=0, refinement=0, coverage_gap=0, unchanged_evidence=0,
        repeated_failure=0)
    refs = {canonical_sha256(ref) for ref in known_evidence}
    digests = {ref['sha256'] for ref in known_evidence}
    failure = None
    for fact in facts:
        counts['consumed'] += 1
        assessment = fact.get('assessment') or {}
        classification = assessment.get('classification', 'unknown')
        supported = assessment.get('supported', False)
        evidence = assessment.get('evidence', []) if supported else []
        novel = any(canonical_sha256(item['ref']) not in refs and item['ref']['sha256'] not in digests
            for item in evidence)
        refs.update(canonical_sha256(item['ref']) for item in evidence)
        digests.update(item['ref']['sha256'] for item in evidence)
        counts['unchanged_evidence'] = 0 if novel else counts['unchanged_evidence'] + 1
        gap = not fact.get('intent') or not supported or classification == 'unknown'
        counts['coverage_gap'] = counts['coverage_gap'] + 1 if gap else 0
        if classification == 'no_progress' and supported:
            counts['no_progress'] += 1
        elif classification == 'advance' and supported and novel:
            counts['no_progress'] = 0
            if advances is not None:
                advances.append(fact['sequence'])
        counts['refinement'] = counts['refinement'] + 1 if (fact.get('intent') or {}).get('intent') == 'refine' else 0
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
    advances = []
    counts = reduce_shadow(facts, advances=advances, known_evidence=[item['output']
        for item in prior.get('observation_scope', {}).get('background', {}).values() if item['output']])
    notices = prior.get('notices', [])
    dispositions = prior.get('dispositions', [])
    resolved = {item['notice_id'] for item in dispositions}
    thresholds = dict(no_progress=policy['no_progress_threshold'], refinement=policy['refinement_threshold'],
        coverage_gap=policy['observation_gap_threshold'], unchanged_evidence=policy['observation_gap_threshold'],
        repeated_failure=policy['observation_gap_threshold'])
    for reason, threshold in thresholds.items():
        active = next((item for item in reversed(notices) if item['reason'] == reason and item['id'] not in resolved), None)
        # Only a newly consumed, supported advance can close a cause episode.
        # Late assessments update current counts, never withdraw old notices.
        if active and counts[reason] < threshold and any(
                sequence > prior.get('through_sequence', 0) for sequence in advances):
            dispositions.append(dict(notice_id=active['id'], state='new_evidence_after_trigger',
                through_sequence=facts[-1]['sequence']))
            active = None
        if counts[reason] < threshold or active:
            continue
        notices.append(dict(id=canonical_sha256(dict(goal=goal_key, reason=reason,
            sequence=facts[-1]['sequence'])), reason=reason,
            trigger_counts=counts.copy(), policy=policy, through_sequence=facts[-1]['sequence'],
            task_names=[item['task_name'] for item in facts],
            assessment_refs=[item['assessment']['assessment_ref'] for item in facts if item.get('assessment')],
            would_act='refinement_hint' if reason == 'refinement' else 'reassess_at_safe_boundary',
            state='shadow_recorded', dispatch_changed=False))
    assist = prior.get('assist', [])
    if assist and assist[-1]['state'] not in {'resolved', 'withdrawn'}:
        episode = assist[-1]
        # Only a subsequent consumed scientific result ends a delivered episode.
        # Corrections to the original trigger never refund its allowance.
        checkpoint = json.loads(dict(row).get('checkpoint_json', '{}'))
        human_episodes = {item.get('episode_id') for item in
            checkpoint.get('human_continuations', []) + checkpoint.get('interactive_sessions', [])}
        if ((episode.get('delivered') or episode['id'] in human_episodes)
                and any(sequence > max(episode['snapshot']['through_sequence'],
                prior.get('through_sequence', 0)) for sequence in advances)
                and not _active_causes(counts, policy)):
            episode.update(state='resolved', resolved_through=facts[-1]['sequence'])
    state = dict(assist=assist, counts=counts, notices=notices, dispositions=dispositions, through_sequence=facts[-1]['sequence'] if facts else 0,
        omitted=omitted)
    if 'observation_scope' in prior:
        state['observation_scope'] = prior['observation_scope']
    encoded = json.dumps(state, sort_keys=True)
    if not previous or json.loads(previous['state_json']) != state:
        db.execute('INSERT INTO scheduler_progress_shadow VALUES(?,?,?) '
            'ON CONFLICT(instance_id,goal_key) DO UPDATE SET state_json=excluded.state_json',
            (row['instance_id'], goal_key, encoded))



def _active_causes(counts, policy):
    return [reason for reason, threshold in dict(no_progress=policy['no_progress_threshold'],
        coverage_gap=policy['observation_gap_threshold'], unchanged_evidence=policy['observation_gap_threshold'],
        repeated_failure=policy['observation_gap_threshold']).items() if counts.get(reason, 0) >= threshold]


def human_continuation_active(row, checkpoint):
    """UI consent applies to exactly one goal, owner and control generation."""
    records = checkpoint.get('human_continuations', [])
    if not records:
        return False
    consent = records[-1]
    return (row['state'] == 'active' and row['mode'] == 'interactive'
        and consent['generation'] == row['generation']
        and consent['session_key'] == row['owner_session']
        and consent['objective_ref_json'] == row['objective_ref_json'])


def independent_interactive_active(row, checkpoint):
    records = checkpoint.get('interactive_sessions', [])
    if not records:
        return False
    consent = records[-1]
    return (row['state'] == 'active' and row['mode'] == 'interactive'
        and consent['generation'] == row['generation']
        and consent['session_key'] == row['owner_session']
        and consent['objective_ref_json'] == row['objective_ref_json'])


def assist_transition(db, row, checkpoint, *, event, admission=None):
    """Shared transaction for native receipts, admission and safe decision boundaries.

    One episode buys one decision turn and optionally one accepted complete task.
    The task's terminal delivery gets a result-consumption turn, never another task
    allowance. Submitted-unknown versions stay frozen and use native recovery.
    """
    policy = shadow_policy(row)
    if policy['progress_mode'] != 'assist' or not row['objective_ref_json']:
        return None
    goal_key = canonical_sha256(json.loads(row['objective_ref_json']))
    record = db.execute('SELECT state_json FROM scheduler_progress_shadow WHERE instance_id=? AND goal_key=?',
        (row['instance_id'], goal_key)).fetchone()
    if not record:
        return None
    state = json.loads(record['state_json'])
    if 'counts' not in state:
        return None
    original = canonical_json(state)
    episodes = state.setdefault('assist', [])
    episode = episodes[-1] if episodes and episodes[-1]['state'] not in {'resolved', 'withdrawn'} else None
    handoff = checkpoint.get('human_handoff') or {}
    if handoff.get('goal_key') == goal_key and handoff.get('state') in {'prepared', 'submitted_unknown', 'delivered'}:
        if event == 'admission':
            return 'scientific_progress_handoff_consumption_only'
        if event == 'submit':
            handoff['state'] = 'submitted_unknown'
        if event == 'confirm' and checkpoint.get('turn_id'):
            handoff.update(state='delivered', turn_id=checkpoint['turn_id'],
                host=json.loads(row['host_json'] or 'null'))
        if event == 'turn_completed' and handoff.get('turn_id') == checkpoint.get('turn_id'):
            handoff['state'] = 'completed'
        else:
            return None
    if (event == 'admission' and (independent_interactive_active(row, checkpoint)
            or human_continuation_active(row, checkpoint))
            and (not episode or episode['state'] != 'submitted_unknown')):
        # A human control decision is not new evidence or another reassessment.
        return None
    causes = _active_causes(state['counts'], policy)
    candidate = None
    if event in {'prepare', 'admission', 'submit', 'confirm'}:
        # Current consumed facts, not the immutable historical shadow triggers.
        evidence, omitted = observation_facts(db, row, goal_key, policy, state)
        candidate = dict(causes=causes, counts=state['counts'].copy(), policy=policy,
            through_sequence=state['through_sequence'], task_names=[item['task_name'] for item in evidence],
            terminal_evidence=[dict(task_name=item['task_name'], output=item['terminal'].get('output'))
                for item in evidence],
            assessment_refs=[item['assessment']['assessment_ref'] for item in evidence if item.get('assessment')],
            omitted=omitted)
    if (episode and episode['state'] == 'prepared' and candidate is not None
            and canonical_sha256(candidate) != episode['candidate_version']):
        episode.update(state='withdrawn', disposition='candidate_changed_before_submission')
        episode = None
    if event in {'prepare', 'admission'} and episode is None and causes:
        episode = dict(id=canonical_sha256(dict(goal=goal_key, episode=len(episodes),
            through=state['through_sequence'])), state='prepared', reassessments=0,
            snapshot=candidate, candidate_version=canonical_sha256(candidate),
            prepared_round=checkpoint.get('rounds', 0)+1)
        episodes.append(episode)
    if event == 'submit':
        if episode is None or (episode['state'] == 'prepared' and checkpoint.get('progress_notice') != episode['id']):
            db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=? AND goal_key=?',
                (json.dumps(state), row['instance_id'], goal_key))
            return 'scientific_progress_candidate_changed'
        if episode['state'] == 'prepared':
            # Durable before native turn/start. This version is now the exact
            # attempted brief; receipt is still unknown and submission is never replayed.
            episode.update(state='submitted_unknown', submitted_version=episode['candidate_version'])
    if episode and event == 'confirm' and episode['state'] == 'submitted_unknown':
        if (checkpoint.get('phase') == 'running' and checkpoint.get('turn_id')
                and checkpoint.get('progress_notice') == episode['id']):
            current = canonical_sha256(candidate) == episode['submitted_version']
            episode.update(state='delivered' if current else 'withdrawn', reassessments=1 if current else 0,
                delivered=dict(turn_id=checkpoint['turn_id'], round=checkpoint['rounds'],
                    host=json.loads(row['host_json'] or 'null'), boundary='decision_brief',
                    candidate_version=episode['submitted_version'],
                    control_eligible=current, disposition='current' if current else 'changed_before_confirmation'))
    if (episode and event == 'admission' and episode['state'] == 'submitted_unknown'
            and checkpoint.get('progress_notice') == episode['id'] and not episode.get('task_name')):
        episode['task_name'] = admission
    if episode is None:
        if canonical_json(state) != original:
            db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=? AND goal_key=?',
                (json.dumps(state), row['instance_id'], goal_key))
        return None
    if episode.get('delivered') and episode['state'] not in {'resolved', 'withdrawn'}:
        task = episode.get('task_name')
        accepted = checkpoint.get('admissions', {}).get(task, {}) if task else {}
        consumed = (db.execute('SELECT consumed_boundary FROM scheduler_terminal_deliveries '
            'WHERE instance_id=? AND goal_key=? AND run_id=?',
            (row['instance_id'], goal_key, accepted.get('run_id'))).fetchone() if task else None)
        if task and consumed and consumed['consumed_boundary']:
            episode.update(state='exhausted', ended_at='adjusted_task_consumed')
        elif event == 'turn_completed' and checkpoint.get('turn_id') == episode['delivered']['turn_id']:
            episode.update(state='awaiting_result' if task else 'exhausted', ended_at='reassessment_turn_completed')
        elif event == 'admission' and episode['state'] == 'delivered' and not task:
            episode['task_name'] = admission
    if canonical_json(state) != original:
        db.execute('UPDATE scheduler_progress_shadow SET state_json=? WHERE instance_id=? AND goal_key=?',
            (json.dumps(state), row['instance_id'], goal_key))
    if episode['state'] == 'exhausted' and policy['progress_pause_on_persistent_gap']:
        return 'scientific_progress_persistent_gap'
    if event == 'admission' and episode['state'] == 'prepared':
        return ('scientific_progress_reassessment_pending: ' + ', '.join(episode['snapshot']['causes'])
            + ('. Pause and confirm human continuation in the management UI; '
               if row['mode'] == 'interactive' else
               '. End the current turn to receive the evidence and reassess at the next brief; ')
            + 'do not create another ordinary task. Accepted work remains available.')
    if event == 'admission' and episode.get('task_name') != admission and episode['state'] in {
            'submitted_unknown', 'delivered', 'awaiting_result'}:
        return 'scientific_progress_waiting_for_adjusted_task'
    return None


def assist_view(state):
    episodes = state.get('assist', [])
    if not episodes:
        return dict(state='observing', reassessments=0)
    episode = episodes[-1]
    snapshot = episode['snapshot']
    return dict(id=episode['id'], state=episode['state'], reassessments=episode['reassessments'],
        causes=snapshot['causes'], trigger_counts=snapshot['counts'],
        through_sequence=snapshot['through_sequence'], policy=snapshot['policy'],
        task_names=snapshot['task_names'][-5:], task_names_omitted=max(0, len(snapshot['task_names'])-5),
        assessment_count=len(snapshot['assessment_refs']), history_omitted=len(episodes)-1,
        history_read=dict(tool='progression_status', delivery_limit=8, progress_limit=4),
        original_reads=[dict(tool='run_status', name=name, intent='decision') for name in snapshot['task_names'][-5:]],
        adjusted_task=episode.get('task_name'), delivery='confirmed' if episode.get('delivered') else 'unconfirmed',
        delivery_disposition=(episode.get('delivered') or {}).get('disposition'),
        control_eligible=(episode.get('delivered') or {}).get('control_eligible', False),
        instruction='Reconsider the cited evidence and limitations. You may choose one complete adjusted task; '
            'its result must support progress before further dispatch. A changed plan alone does not resolve the causes. '
            'Scientific intent and assessments remain optional. In assist mode, missing them can count as '
            'an observation gap and pause further dispatch. Novel cited bytes with a Root advance judgment '
            'are not an independent determination of scientific progress.')


def shadow_projection(*, bindings, row):
    policy = shadow_policy(row)
    state = bindings.progress_shadow(instance_id=row['instance_id'],
        objective_ref=ArtifactRef.model_validate_json(row['objective_ref_json'])) or {}
    scope = state.get('observation_scope', {})
    # Notice snapshots stay in the DB; the common public projection is bounded.
    return dict(mode=policy['progress_mode'], policy=policy, counts=state.get('counts', reduce_shadow([])),
        assist=assist_view(state),
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
            'verified for scientific stagnation. Different payloads with cited advance judgments can evade that signal.',
            'Refinement is a hint. Optional intent or assessments may still produce observation-gap protection in assist mode.',
            'Code-mode wrapped results are unobserved; new terminal results may arrive only in the next brief.',
            'Direct completion or stop may omit that next brief; no same-turn hard stop is claimed.'])
