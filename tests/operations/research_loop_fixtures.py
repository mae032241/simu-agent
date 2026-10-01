"""Explicit trusted UI setup and synthetic measured usage for source fixtures."""
import json


def authorize_loop(runtime, instance_id, session_key, objective_name):
    bindings = runtime.scheduler_bindings
    row = bindings.progression_status(instance_id=instance_id, internal=True)
    cp = json.loads(row.get('checkpoint_json', '{}'))
    if cp.get('current_loop_id') and json.loads(row['config_json']) == bindings.control_settings(instance_id):
        return
    if row['state'] not in {'idle', 'paused', 'stopped'}:
        bindings.progression_command(instance_id=instance_id, session_key=session_key, command='pause')
    ref = runtime.artifacts.get_by_id(bindings.resolve(instance=instance_id, namespace='artifact', name=objective_name)).ref
    proposal = bindings.loop_authorization_proposal(instance_id=instance_id, session_key=session_key)
    bindings.authorize_loop_from_ui(instance_id=instance_id, session_key=session_key,
        confirmation_binding=proposal['confirmation_binding'], objective_name=objective_name, objective_ref=ref)


def measured_fixture_usage(worker):
    """A fixture's deterministic task supplies actual-format native counters."""
    run = worker.runs.status(worker._run_id)
    loop_id = (run.recovery_policy or {}).get('loop_id')
    if not loop_id:
        return
    bindings = worker.runs.scheduler_bindings
    row = bindings.progression_status(instance_id=run.instance_id, internal=True)
    cp = json.loads(row['checkpoint_json'])
    host = json.loads(row.get('host_json') or 'null')
    identities = list(worker.runs.native_identities(run.run_id))
    if host:
        identities += [dict(thread_id=host['thread_id'], role='root')]
    from scidiscovery.platforms.codex_usage import observe_usage, usage_summary
    from scidiscovery.artifact_agent.service.research_loops import loop_usage
    records = cp.get('usage_records', {})
    for identity in identities:
        thread = identity['thread_id']
        prior = records.get(thread)
        if prior and prior.get('pending_observation'):
            prior = None
        amount = ((prior or {}).get('high_water', {}).get('input_tokens') or 0) + 10
        output = ((prior or {}).get('high_water', {}).get('output_tokens') or 0) + 1
        record = observe_usage(dict(threadId=thread, tokenUsage=dict(total=dict(
            inputTokens=amount, cachedInputTokens=0, outputTokens=output))),
            previous=prior, role=identity['role'], owner=run.instance_id, outcome='running')
        records[thread] = dict(record, loop_id=loop_id)
    bindings.observe_progression(instance_id=run.instance_id, expected_host=host,
        changes=dict(usage_records=records, usage_summary=usage_summary(list(loop_usage(dict(cp, usage_records=records)).values()))))
