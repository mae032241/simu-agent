"""Optional engineering feedback on a confirmed call, never scientific qualification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from scidiscovery.operations.execution import AdapterCapability
from . import budget, experiments as e

KEY = 'isolated_replay'
INTENT = 'engineering-check.intent.json'
OUTCOME = 'engineering-check.outcome.json'
STATES = {'sample_replay_ok', 'dependency_error', 'inconclusive', 'unsupported', 'not_run', 'unknown'}


def acceptance(config, adapter):
    """Bind an optional declaration and the original call's deadline before submit."""
    matches = [item for item in adapter.capabilities() if item.key == KEY]
    if not matches:
        return dict(status='unsupported', note='optional_isolated_replay_not_declared')
    if len(matches) != 1 or not isinstance(matches[0], AdapterCapability):
        raise e.IntegrityError('Ambiguous engineering replay capability')
    item = matches[0]
    policy = json.loads(item.content)
    if (item.kind != 'engineering' or not callable(getattr(adapter, 'replay_check', None))
            or not isinstance(policy, dict) or not isinstance(policy.get('check_scope'), dict)
            or any(type(policy.get(key)) not in (int, float) or not 0 < policy[key] < float('inf')
                   for key in ('max_seconds', 'feedback_seconds'))):
        raise e.IntegrityError('Invalid optional engineering replay declaration')
    stamp = budget.clock_stamp()
    seconds = config.get('max_seconds')
    return dict(version=1, capability=dict(key=item.key, schema_id=item.schema_id,
        payload_schema_version=item.payload_schema_version, media_type=item.media_type,
        sha256=hashlib.sha256(item.content).hexdigest(), policy=policy),
        boot_id=stamp['boot_id'], deadline_boottime=(stamp['at_boottime'] + seconds
            if type(seconds) in (int, float) and 0 < seconds < float('inf') else None))


def _deadline(config, bound):
    stamp = budget.clock_stamp()
    deadline = bound.get('deadline_boottime')
    if (bound.get('boot_id') != stamp['boot_id'] or type(deadline) not in (int, float)
            or not 0 < deadline < float('inf')):
        return None
    mode = config.get('admission', {}).get('mode')
    if mode == 'soft':
        if e.review_status(config)['requested']:
            return None
        review = json.loads(e.read(Path(config['admission']['directory']) / 'review.json'))
        deadline = min(deadline, review['deadline_boottime'])
    elif mode != 'hard':
        return None
    policy = bound['capability']['policy']
    deadline = min(stamp['at_boottime'] + policy['max_seconds'], deadline - policy['feedback_seconds'])
    return deadline if deadline > stamp['at_boottime'] else None


def _preview(directory, accepted):
    bound = accepted.get('engineering_check')
    if bound is None:
        return dict(status='not_run', note='original_call_has_no_bound_engineering_check')
    if bound.get('status') == 'unsupported':
        return bound
    scope = bound['capability']['policy']['check_scope']
    result = dict(status='not_run', note='engineering_check_not_observed', check_scope=scope)
    if (directory / INTENT).exists():
        result.update(status='unknown', note='accepted_engineering_check_has_no_verified_outcome')
        if (directory / OUTCOME).exists():
            value = json.loads(e.read(directory / OUTCOME))
            intent = json.loads(e.read(directory / INTENT))
            if (value['intent_sha256'] != e.proof(directory / INTENT)['sha256']
                    or intent['accepted_sha256'] != e.proof(directory / 'accepted.json')['sha256']
                    or intent['completed_sha256'] != e.proof(directory / 'completed.json')['sha256']):
                raise e.IntegrityError('Engineering feedback differs from its original call')
            original = value['result']
            result.update({key: original[key] for key in ('status', 'note', 'samples', 'stage', 'cleanup_confirmed', 'completion') if key in original})
            if 'diagnostic' in original:
                raw = str(original['diagnostic']).encode()
                result['diagnostic'] = raw[:1024].decode(errors='ignore')
                result['diagnostic_omitted_bytes'] = original.get('diagnostic_omitted_bytes', 0) + max(0, len(raw) - 1024)
    return result


def public(config, call_id):
    """A bounded read-only view; query never starts a replay."""
    try:
        records = e.Records(config)
        return _preview(records.directory(call_id), records.accepted(call_id))
    except (OSError, ValueError, KeyError, TypeError):
        return dict(status='unknown', note='engineering_feedback_original_unavailable')


def complete(config, adapter, call_id, observation):
    """One optional call after confirmed terminal evidence; never repeat an intent.

    All failures here remain engineering feedback. They cannot erase the accepted
    experiment, change its result or change the successful experiment's CLI code.
    """
    if observation is None:
        return
    records = e.Records(config)
    directory = records.directory(call_id)
    try:
        with records.lease('engineering-' + call_id + '.lock'):
            accepted = records.accepted(call_id)
            bound = accepted.get('engineering_check')
            if bound is None or bound.get('status') == 'unsupported' or (directory / INTENT).exists():
                return
            # record_observation already verified the complete backend originals.
            # Reuse that fact; only the small accepted/completed bindings need
            # rechecking here, not every model/log/public data file again.
            if (observation['accepted'] != e.proof(directory / 'accepted.json')
                    or observation['completed'] != e.proof(directory / 'completed.json')):
                raise e.IntegrityError('Engineering check has no exact confirmed completion')
            declared = [item for item in adapter.capabilities() if item.key == KEY]
            available = (len(declared) == 1 and hashlib.sha256(declared[0].content).hexdigest() == bound['capability']['sha256'])
            deadline = _deadline(config, bound)
            intent = dict(accepted_sha256=e.proof(directory / 'accepted.json')['sha256'],
                completed_sha256=e.proof(directory / 'completed.json')['sha256'],
                check=bound, deadline_boottime=deadline)
            e.write(directory / INTENT, intent)
            if not available:
                result = dict(status='not_run', note='original_engineering_capability_unavailable', cleanup_confirmed=True)
            elif observation['status'] != 'known_success':
                result = dict(status='not_run', note='original_execution_not_successful', cleanup_confirmed=True)
            elif deadline is None or deadline <= time.clock_gettime(time.CLOCK_BOOTTIME):
                result = dict(status='not_run', note='original_budget_or_feedback_margin_unavailable', cleanup_confirmed=True)
            else:
                def process(phase, identity):
                    e.write(directory / 'engineering-check.process.json', dict(phase=phase, identity=identity))
                try:
                    result = adapter.replay_check(call_id, deadline_boottime=deadline, on_process=process)
                except Exception as error:
                    result = dict(status='unknown', note='engineering_check_unverified', cleanup_confirmed=False,
                        diagnostic=type(error).__name__ + ': ' + str(error))
                if (not isinstance(result, dict) or result.get('status') not in STATES
                        or type(result.get('cleanup_confirmed')) is not bool
                        or not isinstance(result.get('note'), str)):
                    result = dict(status='unknown', note='invalid_engineering_check_result', cleanup_confirmed=False)
                if not result['cleanup_confirmed']:
                    result = dict(result, status='unknown')
            e.write(directory / OUTCOME, dict(intent_sha256=e.proof(directory / INTENT)['sha256'], result=result))
    except Exception:
        return  # The original scientific result and every already-written receipt remain intact.
