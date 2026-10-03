"""Bounded derived memory of exact terminal tasks; never scientific authority."""
from contextlib import closing
import json

from ...agent_execution_settings import MaterialInputSettings
from ...operations.tooling import operation_worker_tools
from ..schema.common import canonical_json, canonical_sha256
from ..schema.refs import ArtifactRef
from .run_records import RunStateConflict, RunContractUnavailable
from ..storage.cas import CASIntegrityError
from ..storage.sqlite import ArtifactNotFoundError


class AttemptMemoryMixin:
    def _freeze_memory(self, db, row):
        if row['memory_scope_json'] is not None:
            return
        self._attach_scheduler(db)
        name = db.execute("SELECT name FROM scheduler_control.scheduler_bindings WHERE instance=? AND namespace='run' AND object_id=? ORDER BY created_at,name LIMIT 1",
            (row['instance_id'], row['run_id'])).fetchone()
        missing=None
        try:
            scope = self.attempt_history_scope(instance_id=row['instance_id'], state=None, limit=8,
                source_run_id=row['run_id'], source_name=name[0] if name else None, connection=db)
        except RunStateConflict:
            scope=None
            missing='exact_history_missing_or_conflicting'
        memory = dict(available=scope is not None, scope=scope, unavailable=missing,
            budgets=MaterialInputSettings.model_validate(json.loads(row['recovery_policy_json'] or '{}').get('input_materials', {})).model_dump())
        if scope is None and name:
            admission=db.execute("SELECT record_json FROM scheduler_control.scheduler_progression_details WHERE instance_id=? AND collection='admissions' AND record_key=?", (row['instance_id'],name[0])).fetchone()
            admission=json.loads(admission[0]) if admission else {}
            if admission.get('state')=='accepted' and admission.get('run_id')==row['run_id'] and admission.get('objective_ref'):
                memory['objective_ref']=admission['objective_ref']
                goal=db.execute("SELECT name FROM scheduler_control.scheduler_bindings WHERE instance=? AND namespace='artifact' AND object_id=? ORDER BY name LIMIT 1", (row['instance_id'],memory['objective_ref']['artifact_id'])).fetchone()
                memory['objective_name']=goal[0] if goal else None
        db.execute('UPDATE runs SET memory_scope_json=? WHERE run_id=? AND memory_scope_json IS NULL',
            (canonical_json(memory), row['run_id']))

    def _worker_memory_binding(self, run_id):
        with closing(self._connect()) as db:
            row = db.execute('SELECT instance_id,state,memory_scope_json FROM runs WHERE run_id=?', (run_id,)).fetchone()
        if row is None or row['state'] != 'running':
            raise RunStateConflict('History requires this exact running assignment.')
        memory = json.loads(row['memory_scope_json']) if row['memory_scope_json'] else dict(available=False)
        if memory.get('scope') and memory['scope']['instance_id'] != row['instance_id']:
            raise RunStateConflict('Frozen memory belongs to another instance.')
        return memory

    def _memory_visible_inputs(self, row, budget):
        try:
            compiled = self.operation_catalog.operation(row['operation_id'])
            if compiled.digest != row['operation_digest']:
                return [], 'historical_visibility_contract_unavailable'
        except KeyError:
            return [], 'historical_visibility_contract_unavailable'
        visible = {p.name for p in compiled.spec.inputs if p.agent_visible and p.exposure != 'handoff_only'}
        if row['inputs_json'] is None:
            return [], 'input_index_byte_budget'
        try:
            inputs=json.loads(row['inputs_json'])
            if not isinstance(inputs,list) or any(not isinstance(i,dict) for i in inputs):
                return [], 'input_index_invalid'
            result = [dict(original_name=i['source_name'], artifact_name=i['artifact_name']) for i in inputs if i['port_name'] in visible]
        except (ValueError, KeyError, TypeError):
            return [], 'input_index_invalid'
        return (result, None) if len(canonical_json(result)) <= budget else ([], 'input_index_byte_budget')

    def _memory_audience(self, value):
        # The compiled contract, not an Operation's spelling, defines review.
        return 'reviewer' if self._compiled(value).spec.independent_review_ports else 'worker'

    def _memory_item(self, scope, record, *, audience, budget):
        with closing(self._connect()) as db:
            # Exact binding lookup, not a whole-instance Run/material scan.
            identity = self.scheduler_bindings.resolve(instance=scope['instance_id'], namespace='run', name=record['name'])
            row = db.execute('SELECT run_id,instance_id,operation_id,operation_digest,output_binding_name,output_ref_json,'
                'CASE WHEN length(signal_json)<=? THEN signal_json END AS signal_json,'
                'CASE WHEN length(inputs_json)<=? THEN inputs_json END AS inputs_json,'
                "json_extract(CAST(recovery_policy_json AS TEXT),'$.scientific_intent_ref') AS intent_ref FROM runs WHERE instance_id=? AND run_id=?",
                (budget, budget * 4, scope['instance_id'], identity)).fetchone()
        if row is None:
            raise RunStateConflict('Exact memory task is unavailable.')
        item = dict(name=record['name'], state=record['state'], completed_at=record['completed_at'],
            result_nature='sealed_worker_delivery' if record['state']=='completed' else 'engineering_failure_not_scientific_negation',
            omissions=[], original_read='not_confirmed')
        if audience == 'root':
            item['read'] = dict(tool='run_status', name=record['name'], intent='decision')
            item['navigation'] = dict(tool='run_status', name=record['name'], intent='navigation')
        else:
            item['original'] = dict(tool='worker_reference_read', history_task=record['name'], action='list')
        inputs, omitted = self._memory_visible_inputs(row, budget//3)
        item['frozen_inputs'] = inputs
        if omitted:
            item['omissions'].append(omitted)
        if audience == 'reviewer':
            item['projection'] = 'neutral_terminal_index; author conclusions and scheduler judgments withheld'
            return item
        if record['state'] == 'failed':
            item['failure_category'] = record.get('failure_category')
            item['summary'] = 'Task ended in an engineering failure; scientific conclusion remains unavailable.'
        else:
            from .run_records import parse_stored_signal
            saved = parse_stored_signal(row['signal_json'])
            signal = saved.model_dump(mode='json') if saved else None
            if row['output_ref_json'] is None:
                signal=None
                item['result_nature']='terminal_fact_without_sealed_report'
                item['omissions'].append('sealed_report_missing')
            item['summary'] = signal['summary'] if signal else 'Sealed delivery; handoff omitted or unavailable.'
            if signal:
                item['worker_verdict'] = signal['verdict']
                limits={key:signal[key] for key in ('assumptions','missing_inputs') if signal.get(key)}
                if limits:
                    item['worker_limits'] = limits
            else:
                item['omissions'].append('worker_handoff_invalid' if row['signal_json'] is not None else 'worker_handoff_missing_or_byte_budget')
            item['omissions'].append('full_report_conditions_and_limitations_require_original')
            self._memory_scientific_fields(item, row, budget//3, read_bytes=budget*4)
        if row['intent_ref']:
            try:
                intent=ArtifactRef.model_validate_json(row['intent_ref'])
            except ValueError:
                item['omissions'].append('scientific_intent_ref_invalid')
            else:
                self._memory_excerpt(item, 'scientific_intent', intent, budget//3, member='intent', read_bytes=budget)
        # A historical judgment belongs to that task's accepted goal, even when
        # the current frozen index also contains explicit revision ancestors.
        goal=record.get('objective_ref_json')
        if goal is None and scope.get('objective_ref'):
            with self.scheduler_bindings._connect() as db:
                admission=db.execute("SELECT json_extract(record_json,'$.objective_ref') FROM scheduler_progression_details WHERE instance_id=? AND collection='admissions' AND record_key=? AND json_extract(record_json,'$.state')='accepted' AND json_extract(record_json,'$.run_id')=?",
                    (scope['instance_id'],record['name'],row['run_id'])).fetchone()
                goal=admission[0] if admission else None
        if goal:
            with self.scheduler_bindings._connect() as db:
                judgment = db.execute('SELECT artifact_ref_json,revision FROM scheduler_progress_assessments WHERE instance_id=? AND goal_key=? AND run_id=? AND sequence<=? ORDER BY sequence DESC LIMIT 1',
                    (scope['instance_id'], canonical_sha256(json.loads(goal)), row['run_id'], scope.get('assessment_upper', 2**63-1))).fetchone()
            if judgment:
                item['root_judgment_revision'] = judgment['revision']
                item['root_judgment_authority'] = 'root_judgment_not_scientific_validation; revisions may correct or overturn prior judgments'
                try:
                    judgment_ref=ArtifactRef.model_validate_json(judgment['artifact_ref_json'])
                except ValueError:
                    item['omissions'].append('root_judgment_original_unavailable')
                else:
                    self._memory_excerpt(item, 'root_judgment', judgment_ref, budget//3, member='assessment', read_bytes=budget)
                if 'root_judgment' in item:
                    item['root_judgment'] = dict(outcome=item['root_judgment']['outcome'], evidence_support=item['root_judgment'].get('evidence_support','unknown'), details='unavailable_in_this_projection; not_a_scientific_original')
        if any('invalid' in gap or 'unavailable' in gap or 'missing' in gap for gap in item['omissions']):
            item['content_coverage']='partial_unknown; healthy entries remain available'
        # Drop complete excerpts, with an explicit gap; never clip a conclusion.
        for field in ('worker_limits', 'root_judgment', 'scientific_intent', 'summary', 'scientific_fields', 'frozen_inputs'):
            if len(canonical_json(item)) <= budget:
                break
            if field in item:
                item.pop(field)
                item['omissions'].append(field+'_byte_budget')
                if field=='scientific_fields':
                    item.pop('scientific_negative',None)
        return item

    def _memory_scientific_fields(self, item, row, budget, *, read_bytes):
        """Copy complete declared decision fields, never infer from prose/verdict."""
        from .run_read_projection import _pointer_value
        try:
            compiled=self.operation_catalog.operation(row['operation_id'])
        except KeyError:
            item['omissions'].append('scientific_fields_contract_unavailable')
            return
        if compiled.digest!=row['operation_digest'] or not row['output_ref_json']:
            item['omissions'].append('scientific_fields_original_unavailable')
            return
        try:
            ref=ArtifactRef.model_validate_json(row['output_ref_json'])
            if self.artifacts.catalog(ref).size_bytes>read_bytes:
                item['omissions'].append('scientific_fields_original_byte_budget')
                return
            body=json.loads(self.artifacts.read(ref))
            if not isinstance(body,dict):
                raise ValueError('Sealed scientific payload is not an object.')
            fields={}
            for name in compiled.spec.decision_fields:
                pointer=name if name.startswith('/') else '/'+name.replace('~','~0').replace('/','~1')
                if pointer=='/summary':
                    continue  # The saved handoff already supplies the one summary.
                try:
                    value=_pointer_value(body,pointer)
                except (KeyError,IndexError):
                    continue
                if value is not None and value not in ([],{}):
                    fields[pointer]=value
            if ref.schema_id=='scidiscovery.layered-diagnosis.v1':
                from ..schema.layered_diagnosis import LayeredDiagnosisReport
                report=LayeredDiagnosisReport.model_validate_json(canonical_json(body),strict=True)
                for key in ('experiment_key','plan_key','objective_assessment','hypothesis_assessments'):
                    if body.get(key):
                        fields['/'+key]=body[key]
                if report.study_kind=='scientific' and any(h.outcome=='contradicts' for h in report.hypothesis_assessments):
                    item['scientific_negative']='worker_hypothesis_contradiction_under_report_conditions'
            if fields and len(canonical_json(fields))<=budget:
                item['scientific_fields']=fields
                item['scientific_authority']='sealed_worker_conclusion_not_controlled_verification'
            else:
                item.pop('scientific_negative',None)
                item['omissions'].append('scientific_fields_byte_budget' if fields else 'scientific_knowledge_or_unresolved_fields_not_provided')
        except (OSError,ValueError,KeyError,CASIntegrityError,ArtifactNotFoundError):
            item.pop('scientific_negative',None)
            item['omissions'].append('scientific_fields_original_unavailable')

    def _memory_excerpt(self, item, field, ref, budget, *, member, read_bytes):
        try:
            if self.artifacts.catalog(ref).size_bytes > read_bytes:
                item['omissions'].append(field+'_byte_budget')
                return
            body = json.loads(self.artifacts.read(ref))
            if not isinstance(body,dict) or not isinstance(body.get(member),dict):
                raise ValueError('The optional control excerpt is not an object.')
            if field=='root_judgment':
                from ..schema.scientific_progress import ProgressAssessment
                ProgressAssessment.model_validate(body[member])
                if not isinstance(body.get('evidence',[]),list) or any(not isinstance(e,dict) for e in body.get('evidence',[])):
                    raise ValueError('Optional judgment evidence is not an object list.')
            if len(canonical_json(body[member])) > budget:
                item['omissions'].append(field+'_byte_budget')
            else:
                item[field] = body[member]
                if field=='root_judgment':
                    supported=body.get('output_ref') is not None and any(e.get('ref')==body['output_ref'] for e in body.get('evidence',()))
                    item[field]={**item[field], 'evidence_support':'sealed_output_referenced' if supported else 'missing_task_output'}
        except (OSError, ValueError, KeyError, CASIntegrityError, ArtifactNotFoundError):
            item['omissions'].append(field+'_original_unavailable')

    def memory_page(self, scope, *, audience='root', page_bytes=16384, continuation=None):
        records = self.attempt_history_page(scope)
        response = dict(runs=[], next_before=None, coverage='exact_frozen_terminal_tasks_newest_first',
            revision_scope=scope.get('lineage',dict(coverage='legacy_exact_goal_only; frozen_scope_not_expanded')),
            terminal_source_missing=scope['terminal_source_missing'], original_read='not_confirmed',
            scientific_summary='attributed_existing_excerpts_not_new_synthesis',
            limitations='Memory is navigation, not original consumption, qualification or a retry gate. Historical original_name values belong to their tasks, not current citation aliases. Conditions, conflicts and missing evidence require originals; this time index does not identify every important experience.')
        for index, record in enumerate(records[:scope['limit']]):
            item = self._memory_item(scope, record, audience=audience, budget=min(2048, max(512, page_bytes//4)))
            next_before = record['name'] if index+1 < len(records) else None
            candidate = dict(response, runs=[*response['runs'],item], next_before=next_before)
            if continuation:
                candidate.update(continuation=continuation(record) if next_before else None,
                    next_before=(continuation(record) or {}).get('before') if next_before else None)
            if len(canonical_json(candidate)) > page_bytes:
                if not response['runs']:
                    return dict(runs=[], next_before=None, unavailable='memory_page_byte_budget', original_read='not_confirmed')
                break
            response = candidate
        return response

    def worker_history(self, run_id, *, before=None, limit=8):
        memory = self._worker_memory_binding(run_id)
        if not memory['available']:
            return dict(runs=[], next_before=None, **self._memory_unavailable(memory.get('unavailable') or 'no_exact_goal_or_recorded_recovery_source'))
        scope = dict(memory['scope'], limit=limit, after=None)
        if before:
            record = self._memory_terminal(scope, before)
            scope['after'] = [record['completed_at'], record['terminal_event']]
        try:
            value = self.status(run_id)
            response = self.memory_page(scope, audience=self._memory_audience(value), page_bytes=memory['budgets']['original_read_page_bytes'])
        except RunStateConflict:
            return dict(runs=[],next_before=None,**self._memory_unavailable('frozen_history_missing_or_conflicting'))
        allowed = any(t.reference_policy is not None for t in operation_worker_tools(self._compiled(value)))
        response['original_access'] = 'worker_reference_read' if allowed else 'unavailable: bind needed originals as declared scientific inputs'
        if not allowed:
            for item in response['runs']:
                item.pop('original',None)
        return self._bounded_memory(response, memory['budgets']['original_read_page_bytes'])

    def _memory_terminal(self, scope, name):
        with closing(self._connect()) as db:
            self._attach_scheduler(db)
            tables, where, args = self._attempt_history_terminals(scope)
            row = db.execute('SELECT r.run_id,b.name,r.state,r.completed_at,a.rowid AS terminal_event,'
                "json_extract(a.diagnostic_json,'$.category') AS failure_category FROM "+tables+' WHERE '+where+' AND b.name=?', (*args,name)).fetchone()
        if row is None:
            raise RunStateConflict('Task is not in this assignment\'s exact frozen terminal history.')
        return dict(row)

    def memory_overview(self, scope, *, audience, page_bytes, current=None, exclude=()):
        # Recent entries and up to two exact input/recovery links. No similarity,
        # recency fallback, model summarization, or instance-wide source grant.
        records = self.attempt_history_page(dict(scope, limit=3, after=None))[:3]
        with closing(self._connect()) as db:
            self._attach_scheduler(db)
            tables, where, args = self._attempt_history_terminals(scope)
            failures=[] if audience=='reviewer' else [dict(r) for r in db.execute('SELECT b.name,r.state,r.completed_at,a.rowid AS terminal_event,'
                "json_extract(a.diagnostic_json,'$.category') AS failure_category FROM "+tables+' WHERE '+where+
                " AND r.state='failed' ORDER BY r.completed_at,a.rowid LIMIT 1", args).fetchall()]
            scientific=[] if audience=='reviewer' else [dict(r) for r in db.execute('SELECT b.name,r.state,r.completed_at,a.rowid AS terminal_event,'
                "json_extract(a.diagnostic_json,'$.category') AS failure_category FROM "+tables+' WHERE '+where+
                " AND r.state='completed' AND json_extract(r.output_ref_json,'$.schema_id')='scidiscovery.layered-diagnosis.v1' ORDER BY r.completed_at,a.rowid LIMIT 2", args).fetchall()]
        relevant = []
        if current is not None:
            try:
                refs = [i.artifact_ref.model_dump(mode='json') for i in self._reference_roots(current)]
            except (RunContractUnavailable,KeyError):
                refs=[]
            parents = [p for p in self.recovery_links(current.run_id).values() if p]
            with closing(self._connect()) as db:
                self._attach_scheduler(db)
                tables, where, args = self._attempt_history_terminals(scope)
                # This optional affinity lookup must not evaluate malformed
                # historical JSON. CASE guards each JSON function explicitly;
                # SQL/lock errors and exact goal/Run binding checks still escape.
                inputs="CASE WHEN json_valid(CAST(r.inputs_json AS TEXT)) THEN CASE WHEN json_type(CAST(r.inputs_json AS TEXT))='array' THEN CAST(r.inputs_json AS TEXT) ELSE '[]' END ELSE '[]' END"
                object_input="CASE WHEN i.type='object' THEN i.value ELSE '{}' END"
                linked = db.execute('SELECT b.name,r.state,r.completed_at,a.rowid AS terminal_event,'
                    "json_extract(a.diagnostic_json,'$.category') AS failure_category FROM "+tables+' WHERE '+where+
                    " AND (r.run_id IN (SELECT value FROM json_each(?)) OR (NOT EXISTS (SELECT 1 FROM json_each("+inputs+") bad WHERE bad.type<>'object') AND EXISTS (SELECT 1 FROM json_each("+inputs+") i JOIN json_each(?) exact ON json_extract("+object_input+",'$.artifact_ref.artifact_id')=json_extract(exact.value,'$.artifact_id') AND json_extract("+object_input+",'$.artifact_ref.sha256')=json_extract(exact.value,'$.sha256')))) ORDER BY r.completed_at,a.rowid LIMIT 2",
                    (*args,json.dumps(parents),json.dumps(refs))).fetchall()
                relevant = [dict(r) for r in linked]
        overview = dict(recent=[], exact_source_related=[], failure_boundaries=[], history=dict(tool='worker_read_history') if audience!='root' else None,
            revision_scope=scope.get('lineage',dict(coverage='legacy_exact_goal_only; frozen_scope_not_expanded')),
            coverage='recent_and_few_exact_source_links; important_history_not_exhaustively_selected',
            limitations='Engineering failure is not scientific rejection; Root judgment is not validation. Changed conditions can justify retry. Historical original_name values belong to their tasks, not current citation aliases. Excerpts omit full report limitations; read originals before conclusions.')
        seen=set(exclude)
        if audience!='reviewer':
            overview['scientific_negative_candidates']=[]
            overview['scientific_negative_coverage']='at_most_two_earliest_typed_diagnoses; missing_or_oversize_excerpts_unknown; not_all_important_negative_results'
        for label, candidates in (('failure_boundaries',failures),('scientific_negative_candidates',scientific),('exact_source_related',relevant),('recent',records)):
            for record in candidates:
                if record['name'] in seen:
                    continue
                item=self._memory_item(scope,record,audience=audience,budget=min(2048,max(512,page_bytes//6)))
                if label=='scientific_negative_candidates' and not item.get('scientific_negative'):
                    continue
                seen.add(record['name'])
                overview[label].append(item)
                if len(canonical_json(overview))>page_bytes:
                    overview[label].pop()
                    overview['entries_omitted']='byte_budget; continue the frozen time index'
        return self._bounded_memory(overview, page_bytes)

    @staticmethod
    def _memory_unavailable(reason):
        return dict(unavailable=reason, coverage='unknown_not_empty',
            repair='Scheduler must restore exact historical bindings/originals if needed. Continue the accepted task with its bound originals; history is optional navigation.')

    @staticmethod
    def _bounded_memory(response, budget):
        if len(canonical_json(response)) <= budget:
            return response
        bounded=dict(history=response.get('history',dict(tool='worker_read_history')),
            omissions='memory_byte_budget; a complete entry cannot fit; bind needed originals as inputs; summaries are not evidence')
        if response.get('objective'):
            bounded['objective']=response['objective']
            if len(canonical_json(bounded))>budget:
                bounded['objective']={k:v for k,v in response['objective'].items() if k!='original'}
                bounded['objective']['omitted']='objective_byte_budget; bind original as scientific input'
        return bounded

    def _memory_objective(self, memory, value):
        overview={}
        goal_scope=memory.get('scope') or memory
        objective=goal_scope.get('objective_ref')
        if objective:
            ref=ArtifactRef.model_validate(objective)
            bound=next((i.source_name for i in self._reference_roots(value) if i.artifact_ref==ref),None)
            overview['objective']=dict(source_name=bound) if bound else dict(name=goal_scope.get('objective_name'), usage='overall task objective; navigation, not a citation alias')
            if not bound:
                try:
                    if self.artifacts.catalog(ref).size_bytes <= memory['budgets']['startup_read_page_bytes']//4:
                        overview['objective']['original']=self.artifacts.read(ref).decode('utf-8')
                    else:
                        overview['objective']['omitted']='objective_byte_budget; bind the objective as scientific input for original access'
                except (OSError, ValueError, CASIntegrityError):
                    overview['objective']['omitted']='objective_original_unavailable'
        return overview

    def worker_memory(self, run_id):
        memory=self._worker_memory_binding(run_id)
        value=self.status(run_id)
        if not memory['available']:
            response={**self._memory_unavailable(memory.get('unavailable') or 'no_exact_goal_or_recorded_recovery_source'),**self._memory_objective(memory,value)}
            return self._bounded_memory(response,memory.get('budgets',MaterialInputSettings().model_dump())['startup_read_page_bytes'])
        try:
            overview=self.memory_overview(memory['scope'], audience=self._memory_audience(value), page_bytes=memory['budgets']['startup_read_page_bytes'], current=value)
        except RunStateConflict:
            response={**self._memory_unavailable('frozen_history_missing_or_conflicting'),**self._memory_objective(memory,value)}
            return self._bounded_memory(response,memory['budgets']['startup_read_page_bytes'])
        allowed=any(t.reference_policy is not None for t in operation_worker_tools(self._compiled(value)))
        overview.update(self._memory_objective(memory,value))
        overview['original_access']='worker_reference_read' if allowed else 'unavailable: bind originals as scientific inputs'
        if not allowed:
            for item in (*overview.get('recent',()),*overview.get('exact_source_related',()),*overview.get('failure_boundaries',()),*overview.get('scientific_negative_candidates',())):
                item.pop('original',None)
        return self._bounded_memory(overview, memory['budgets']['startup_read_page_bytes'])
