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
    def validate_admission(self, bound, *, instance_id, max_attempts=None,
                           scientific_signature=None, reserved_output_fingerprint=None, connection=None):
        if connection is None:
            with self._connect() as db:
                return self.validate_admission(bound, instance_id=instance_id,
                    max_attempts=max_attempts, scientific_signature=scientific_signature, reserved_output_fingerprint=reserved_output_fingerprint, connection=db)
        self.worker_connections.review_authors(connection, bound.compiled,
            self._input_bindings(bound), instance_id)
        if connection.execute("SELECT 1 FROM runs WHERE operation_digest=? AND state IN ('queued','running') LIMIT 1",
                              (bound.compiled.digest,)).fetchone():
            raise OperationInvocationError("operation_busy",
                message="This Operation has an active task. Wait for that task to finish; do not spawn a Worker or repeat the request while it is occupied.")
        active = connection.execute("SELECT run_id,review_wait_json FROM runs WHERE instance_id=? AND state IN ('queued','running')",
                                    (instance_id,)).fetchall()
        ports = bound.compiled.spec.independent_review_ports
        subjects = [i.artifact.ref.model_dump(mode='json') for i in bound.inputs if i.port_name in ports]
        owners = []
        for item in active:
            wait = json.loads(item['review_wait_json'] or 'null')
            if (wait and not wait.get('reviewer_run_id')
                    and bound.compiled.spec.operation_id == wait['request']['operation_id']
                    and subjects == [wait['subject_ref']]):
                owners.append(item['run_id'])
        if len(owners) > 1:
            raise OperationInvocationError("review_dependency_ambiguous",
                message="Several tasks await this exact review; resolve task ownership before dispatch.")
        review_owner = owners[0] if owners else None
        row = self.scheduler_bindings.progression_status(instance_id=instance_id, internal=True)
        if row.get('mode') != 'background':
            return review_owner
        checkpoint = json.loads(row['checkpoint_json'])
        limits = json.loads(row['config_json'])['effective']['progression']
        if active and (len(active) != 1 or review_owner is None):
            raise OperationInvocationError("background_task_busy",
                message="Background progression permits one complete task at a time. Only the exact independent review requested by its waiting owner may run before that task finishes.")
        admissions = checkpoint.get('admissions', {})
        reserved = [item for item in admissions.values() if item['state'] == 'prepared'
            and not item.get('interactive_session_id')
            and reserved_output_fingerprint is not None
            and item['output_fingerprint'] == reserved_output_fingerprint
            and item.get('scientific_signature') == scientific_signature]
        if any(item['state'] == 'prepared' and item not in reserved for item in admissions.values()):
            raise OperationInvocationError('background_admission_pending',
                message='A prior task admission is unresolved; reconcile it before creating more work.')
        from .scheduling_control import background_task_count
        if background_task_count(checkpoint) - len(reserved) >= limits['max_tasks']:
            raise OperationInvocationError("background_task_budget_exhausted",
                message="The frozen task budget is exhausted, including independent review tasks.")
        if not reserved:
            from .progression_budget import require_task_budget
            require_task_budget(checkpoint, limits)
        for prior in checkpoint.get('admissions', {}).values():
            if (scientific_signature and prior.get('scientific_signature') == scientific_signature
                    and prior.get('run_id') and self.status(prior['run_id']).state == 'failed'):
                raise OperationInvocationError("background_unchanged_task_failed",
                    message="The same task failed with unchanged inputs and instruction; use its recovery contract or change the scientific request.")
        if max_attempts is not None and max_attempts > limits['max_attempts']:
            raise OperationInvocationError("background_attempt_budget_exceeded",
                message="Requested attempts exceed the frozen background limit.")
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
            wait = dict(subject_ref=ref, request=request, requested_at=timestamp())
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
