"""Shared read-only admission and durable, exact review dependencies.

RunService owns the transaction. Preflight calls the same decision without a
write; creation repeats it under the Run lock. Native identity remains attach's
responsibility. No reviewer identity or private reference is authored by Root.
"""
import json

from ...operations.invoke import OperationInvocationError
from ..schema.common import canonical_json
from .run_records import RunStateConflict, timestamp


class RunAdmissionMixin:
    def task_classification(self, compiled, inputs, *, instance_id, connection=None):
        """Compiled subject ports and verified authorship confer review status.

        The actual reviewer is independently checked at native attachment. Names,
        scientific intent and Root declarations do not affect this decision.
        """
        if connection is None:
            with self._connect() as db:
                return self.task_classification(compiled, inputs, instance_id=instance_id, connection=db)
        contract = self.operation_catalog.operation(compiled.spec.operation_id)
        if contract.digest != compiled.digest or contract.spec != compiled.spec:
            raise OperationInvocationError('operation_contract_unavailable',
                message='Task classification requires the current compiled contract; caller declarations cannot grant review allowances.')
        authors = self.worker_connections.review_authors(connection, compiled, inputs, instance_id)
        subjects = [dict(port=item.port_name, ref=item.artifact_ref.model_dump(mode='json'))
            for item in inputs if item.port_name in compiled.spec.independent_review_ports]
        if not subjects or not authors:
            return dict(kind='research')
        return dict(kind='independent_review', operation_digest=compiled.digest, subjects=subjects)

    def requested_review_owner(self, bound, *, instance_id, connection=None):
        if connection is None:
            with self._connect() as db:
                return self.requested_review_owner(bound, instance_id=instance_id, connection=db)
        active = connection.execute("SELECT run_id,review_wait_json FROM runs WHERE instance_id=? AND state IN ('queued','running')",
            (instance_id,)).fetchall()
        ports = bound.compiled.spec.independent_review_ports
        subjects = [i.artifact.ref.model_dump(mode='json') for i in bound.inputs if i.port_name in ports]
        owners = []
        for item in active:
            wait = json.loads(item['review_wait_json'] or 'null')
            expected_inputs = sorted((item['port'], name) for item in (wait or {}).get('request', {}).get('inputs', []) for name in item['artifact_names'])
            visible = {port.name for port in bound.compiled.spec.inputs if port.agent_visible and port.derivation is None}
            actual_inputs = sorted((item.port_name, item.artifact_name) for item in bound.inputs if item.port_name in visible)
            if (wait and not wait.get('operation_digest')
                    and bound.compiled.spec.operation_id == wait['request']['operation_id']
                    and subjects == [wait['subject_ref']]):
                raise OperationInvocationError('review_dependency_unfrozen',
                    message='The saved review dependency has no frozen reviewer contract. Finish or archive it on the previous release; old authorization is not migrated.')
            if (wait and not wait.get('reviewer_run_id')
                    and wait.get('operation_digest') == bound.compiled.digest
                    and expected_inputs == actual_inputs
                    and bound.instruction == wait['request']['instruction']
                    and bound.scientific_intent == wait['request'].get('scientific_intent')
                    and bound.compiled.spec.operation_id == wait['request']['operation_id']
                    and subjects == [wait['subject_ref']]):
                owners.append(item['run_id'])
        if len(owners) > 1:
            raise OperationInvocationError("review_dependency_ambiguous",
                message="Several tasks await this exact review; resolve task ownership before dispatch.")
        return owners[0] if owners else None

    def validate_admission(self, bound, *, instance_id, max_attempts=None,
                           scientific_signature=None, reserved_output_fingerprint=None, connection=None, session_key=None):
        if connection is None:
            with self._connect() as db:
                self._attach_scheduler(db)
                return self.validate_admission(bound, instance_id=instance_id,
                    max_attempts=max_attempts, scientific_signature=scientific_signature, reserved_output_fingerprint=reserved_output_fingerprint, connection=db, session_key=session_key)
        classification = self.task_classification(bound.compiled, self._input_bindings(bound),
            instance_id=instance_id, connection=connection)
        if connection.execute("SELECT 1 FROM runs WHERE operation_digest=? AND state IN ('queued','running') LIMIT 1",
                              (bound.compiled.digest,)).fetchone():
            raise OperationInvocationError("operation_busy",
                message="This Operation has an active task. Wait for that task to finish; do not spawn a Worker or repeat the request while it is occupied.")
        active = connection.execute("SELECT run_id,review_wait_json FROM runs WHERE instance_id=? AND state IN ('queued','running')",
                                    (instance_id,)).fetchall()
        review_owner = self.requested_review_owner(bound, instance_id=instance_id, connection=connection)
        from .progression_records import read_control_row
        row = read_control_row(connection, instance_id, schema='scheduler_control.')
        if row is None:
            return review_owner
        checkpoint = json.loads(row['checkpoint_json'])
        from .research_loops import current_loop
        if current_loop(checkpoint) and self.scheduler_bindings.control_settings(instance_id) != json.loads(row['config_json']):
            raise OperationInvocationError('loop_configuration_changed',
                message='The research loop retains its frozen configuration; direct creation and recovery cannot replace it.')
        from .scheduling_control import require_control_admission
        require_control_admission(connection, row, checkpoint, session_key=session_key,
            continuation=('run', review_owner) if review_owner else None,
            reservation=(reserved_output_fingerprint, scientific_signature) if reserved_output_fingerprint else None,
            now=self.scheduler_bindings.control_now(), schema='scheduler_control.',
            background_busy=bool(active and (len(active) != 1 or review_owner is None)),
            task_kind=classification['kind'])
        from .research_loops import current_loop
        if row['mode'] != 'background' and not current_loop(checkpoint):
            return review_owner
        limits = json.loads(row['config_json'])['effective']['progression']
        for prior in checkpoint.get('admissions', {}).values():
            if (scientific_signature and prior.get('scientific_signature') == scientific_signature
                    and prior.get('run_id') and self.status(prior['run_id']).state == 'failed'):
                raise OperationInvocationError("background_unchanged_task_failed",
                    message="The same task failed with unchanged inputs and instruction; use its recovery contract or change the scientific request.")
        if max_attempts is not None and max_attempts > limits['max_attempts']:
            raise OperationInvocationError("background_attempt_budget_exceeded",
                message="Requested attempts exceed the frozen background limit.")
        if current_loop(checkpoint):
            from .research_loops import loop_usage
            records = loop_usage(checkpoint)
            prior = [item for item in checkpoint.get('admissions', {}).values()
                if item.get('loop_id') == current_loop(checkpoint) and item['state'] == 'accepted'
                    and (item.get('usage_source') != 'frontend_unconnected' or limits['token_policy'] == 'strict')]
            identities = [self.native_identities(item['run_id']) for item in prior]
            expected = {identity['thread_id'] for group in identities for identity in group}
            if (any(not group for group in identities) or expected - records.keys()
                    or any(record['role'] == 'unattributed' or (not record.get('pending_observation')
                        and (record['coverage'] != 'observed' or record['has_gaps'])) for record in records.values())
                    or (prior and any(record.get('pending_observation') for record in records.values()))):
                raise OperationInvocationError('loop_usage_unavailable',
                    message='Accepted loop work has incomplete native usage; reconcile its original observations before creating more work.')
        return review_owner

    def request_implementation_review(self, run_id, subject_ref, request):
        """Persist a control-generated request; repeats do not reset its outcome."""
        run = self.running_task(run_id)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state,review_wait_json FROM runs WHERE run_id=?', (run_id,)).fetchone()
            if row is None or row['state'] != 'running':
                raise RunStateConflict('Review requests require the running experiment owner.')
            old = json.loads(row['review_wait_json'] or 'null')
            ref = subject_ref.model_dump(mode='json')
            if old and old['subject_ref'] == ref:
                return
            if old and old.get('reviewer_run_id') and self.status(old['reviewer_run_id']).state in {'queued','running'}:
                raise RunStateConflict('Finish the outstanding independent review before requesting another implementation review.')
            wait = dict(subject_ref=ref, request=request, requested_at=timestamp(),
                operation_digest=self.operation_catalog.operation(request['operation_id']).digest)
            db.execute('UPDATE runs SET review_wait_json=? WHERE run_id=?', (canonical_json(wait),run.run_id))

    def review_wait(self, run_id):
        with self._connect() as db:
            row = db.execute('SELECT state,review_wait_json FROM runs WHERE run_id=?',(run_id,)).fetchone()
            if row is None or row['state'] not in {'queued','running'} or not row['review_wait_json']:
                return None
            wait = json.loads(row['review_wait_json'])
            reviewer = db.execute('SELECT state FROM runs WHERE run_id=?', (wait.get('reviewer_run_id'),)).fetchone()
        return {**wait, 'state': reviewer['state'] if reviewer else 'requested'}

    def review_wait_projection(self, run_id):
        wait = self.review_wait(run_id)
        if wait is None:
            return None
        result = {'state':wait['state'], 'request':wait['request'],
            'instruction':'Dispatch only this exact independent review while the experiment owner waits. When it finishes, read its sealed conclusion and notify the existing owner to continue the same task.'}
        if wait.get('reviewer_run_id'):
            run = self.status(run_id)
            result['review_name'] = self.scheduler_bindings.find_name(instance=run.instance_id,
                namespace='run', object_id=wait['reviewer_run_id'])
        return result

    @staticmethod
    def bind_requested_review(connection, owner_id, reviewer_id):
        if owner_id is None:
            return
        row = connection.execute('SELECT review_wait_json FROM runs WHERE run_id=?',(owner_id,)).fetchone()
        wait = json.loads(row['review_wait_json'])
        wait['reviewer_run_id'] = reviewer_id
        connection.execute('UPDATE runs SET review_wait_json=? WHERE run_id=?',(canonical_json(wait),owner_id))

    def worker_review_wait(self, run_id, tool_name, arguments):
        """Suspend controlled work while waiting; retain reads and cancellation.

        Native shell remains a declared prototype permission, not an OS sandbox.
        The owner is instructed to wait; this protects framework side effects.
        """
        wait = self.review_wait(run_id)
        if wait is None or wait['state'] in {'completed','failed'}:
            return None
        if tool_name in {'worker_open_assignment','worker_heartbeat','worker_submit_result',
                         'worker_reference_read','worker_materialize_input'}:
            return None
        if tool_name == 'worker_experiment_execute' and arguments.get('action') in {'capabilities','review','status','logs','read','export','cancel'}:
            return None
        if tool_name == 'worker_helper' and arguments.get('action') == 'release':
            return None
        if tool_name == 'worker_experiment_debug' and arguments.get('action') in {'status','cancel'}:
            return None
        return {'state':'waiting_for_review', 'review_state':wait['state'],
            'instruction':'Wait for the scheduler to complete the exact independent review, then read its sealed outcome with worker_experiment_execute(action=review, implementation=<the same alias>) and continue this same task. Do not spawn another experiment or repeat preparation.'}
