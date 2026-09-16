"""Isolated synthetic behavior probe; no production state or fixture new Agent outputs.
Only the pre-existing foundation human decision is stubbed in this test runtime.
Every new proposal/critic/design must be authored and sealed by its compiled Worker.
"""
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
BASE = Path('/tmp/scid-feedback-closeout')
SITE = BASE / 'site'
for path in (REPO, REPO/'src', REPO/'plugins/curve_score', REPO/'plugins/tcad_artifact', REPO/'plugins/curve_figure_evidence'):
    sys.path.insert(0, str(path))
from scidiscovery.artifact_agent.runtime import open_runtime
from scidiscovery.artifact_agent.interfaces.mcp_root import RootMCPRouter, RootToolFacade
from scidiscovery.artifact_agent.schema.common import canonical_json
from scidiscovery.agent_execution_settings import AgentSettings, DefaultSettings
from scidiscovery.platforms.codex import initialize
from tests.operations.test_general_transform_operations import _intake
from tests.operations.test_agent_contract_alignment import experiment_case


def _register(rt, instance, *, name, raw, kind, schema, parents=()):
    from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
    envelope=rt.artifacts.register(raw, ArtifactRegistration(kind=kind,schema_id=schema,
        payload_schema_version=1,media_type='application/json',creator=rt.actor,parent_refs=parents),
        idempotency_key=instance.instance_id+':'+name)
    rt.scheduler_bindings.bind(instance=instance.instance_id,namespace='artifact',name=name,object_id=envelope.artifact_id)
    return envelope


def runtime():
    return open_runtime(project_root=BASE/'project', state_root=BASE/'state', approval_receipt_secret=b'isolated-test-only-00000000000000',
        agent_settings=AgentSettings(defaults=DefaultSettings(narrative_language='zh-CN')))


def router(rt, instance_id):
    # Synthetic acceptance fixture ONLY. No approval is written, no production
    # binding is used, and no execution/approval Operation is invoked by this probe.
    foundation_id=rt.scheduler_bindings.resolve(instance=instance_id,namespace='artifact',name='scientific_foundation')
    foundation=rt.artifacts.get_by_id(foundation_id).ref
    rt.approvals.are_subjects_approved_by_provider = lambda subjects, **k: (
        tuple(subjects)==(foundation,) and k.get('kind')=='scientific_foundation'
        and tuple(k.get('accepted_options',()))==('approve',)
        and tuple(p.operation_id for p in k.get('accepted_providers',()))==('science.evidence.qualify.v1',))
    return RootMCPRouter(RootToolFacade(rt.artifacts, rt.intake, runs=rt.runs,
        approvals=rt.approvals, executions=rt.executions, bindings=rt.scheduler_bindings,
        instance=instance_id, operation_catalog=rt.operation_catalog))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def prepare():
    BASE.mkdir(exist_ok=False)
    SITE.mkdir()
    (BASE/'project').mkdir()
    for name, source in [('scidiscovery',REPO/'src/scidiscovery'),
                         ('curve_score',REPO/'plugins/curve_score/curve_score'),
                         ('tcad_artifact',REPO/'plugins/tcad_artifact/tcad_artifact')]:
        (SITE/name).symlink_to(source, target_is_directory=True)
    metadata=SITE/'scid_probe-0.0.dist-info'; metadata.mkdir()
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: scid-probe\nVersion: 0.0\n')
    (metadata/'entry_points.txt').write_text('[scidiscovery.plugins]\nbuiltin = scidiscovery.builtin_plugin:CORE_PLUGIN\ngeneral_science = scidiscovery.general_science_plugin:PLUGIN\ncurve_score = curve_score.plugin:PLUGIN\ntcad_artifact = tcad_artifact.plugin:PLUGIN\n')
    rt=runtime()
    initialize(BASE/'project', python_executable=sys.executable, python_path=SITE,
        control_socket=BASE/'unused.sock', state_root=BASE/'state',
        local_workspace_root=BASE/'project/.scidiscovery-runs', operation_catalog=rt.operation_catalog)
    _, sources = experiment_case.__wrapped__()
    objective=json.loads(sources['research_objective'])
    objective['statement']='在给定合成系统与误差范围内评价当前响应解释，并设计能推进判断的最小后续研究。'
    objective['closure_requirements'][0]['description']='比较候选解释与独立的合成观测，明确可判断和不可判断的范围。'
    controls={}
    for case in ('b1','b2','b3'):
        instance=rt.scheduler_bindings.create_instance(name=case,title='Synthetic behavior '+case,
            objective=objective['statement'])
        controls[case]=instance.instance_id
        original=_intake().model_dump(mode='json')
        foundation=original['scientific_foundation']
        foundation.update(title='合成响应试验基础', objective=objective['statement'], objective_contract=objective,
            summary='工程验收的人工合成数据，不是论文或真实器件事实。输入 x 和响应 y 均无量纲，x 可在 [-1,2] 取值；每项有效观测的绝对误差不超过 0.02。研究可使用解析预测、已绑定数据或建议新测量，无需外部求解器。')
        foundation['evidence']=[dict(source_key='benchmark_spec',source_type='frozen_input',title='Synthetic benchmark specification',locator='scientific_foundation.summary and items')]
        foundation['items']=[dict(item_key='target',item_type='target_data',epistemic_status='inference',
            statement='已知校准在零输入下稳定。合成观测值与执行状态以绑定原始记录为准；本基础不预先指定解释。',
            scope='仅用于当前合成验收；不能外推到真实物理系统。',rationale='这是人为规定的合成验收条件，不是文献事实。',evidence_keys=['benchmark_spec'])]
        f=_register(rt,instance,name='scientific_foundation',raw=canonical_json(foundation),kind='scientific_foundation',schema='scidiscovery.scientific-foundation.v1')
        frame=original['problem_frame']; frame.update(title='合成响应模型比较',objective=objective['statement'],
            scientific_question='当前候选能否解释给定响应与新记录？下一项有用的研究是什么？',
            current_contradiction='旧候选的适用性需要结合本轮反馈重新判断。',scope='无量纲合成响应 x in [-1,2]。',
            stop_conditions=['证据不足时明确结论范围和缺口；不虚构追加观测。'])
        frame['observables'][0].update(observable_key='response',description='无量纲 y 随 x 的变化',acceptance_relevance='比较原始合成响应')
        frame['claim_boundary']=dict(allowed_claim='仅就合成记录评价候选解释与研究价值。',required_conditions=['区分观测与推断，并保留误差和适用范围。'])
        for name,payload,schema,kind in [('problem_frame',frame,'scidiscovery.problem-frame.v1','problem_frame'),('research_objective',objective,'scidiscovery.research-objective.v1','research_objective')]:
            _register(rt,instance,name=name,raw=canonical_json(payload),schema=schema,kind=kind,parents=(f.ref,))
        previous=json.loads(sources['hypothesis_portfolio']); previous.update(stage_objective='评价响应模型',contradiction='现有记录尚不能闭合模型比较。')
        h=previous['hypotheses'][0]; h.update(hypothesis_key='linear',statement='y=a*x，固定 a=2。',mechanism='响应与输入成正比且通过原点。',scope='无量纲 x in [-1,2]。')
        h['predictions']=[dict(prediction_key='linear_response',observable='response',expected_outcome='x=0,1,2 时 y=0,2,4。')]
        h['falsifiers']=[dict(falsifier_key='linear_mismatch',observable='response',rejection_condition='有效响应与预测的差异超过已知绝对误差 0.02。')]
        if case=='b3':
            other=json.loads(json.dumps(h)); other.update(hypothesis_key='quadratic',statement='y=x+x*x。',mechanism='线性和二次响应项叠加。')
            other['predictions']=[dict(prediction_key='quadratic_response',observable='response',expected_outcome='x=0,1,2 时 y=0,2,6。')]
            other['falsifiers']=[dict(falsifier_key='quadratic_mismatch',observable='response',rejection_condition='有效观测偏离 y=x+x*x 超过 0.02。')]
            previous['hypotheses'].append(other)
        _register(rt,instance,name='previous_hypotheses',raw=canonical_json(previous),kind='hypothesis_portfolio',schema='scidiscovery.hypothesis-proposal.v2',parents=(f.ref,))
        if case=='b1':
            observation=dict(record_kind='synthetic_independent_measurement',state='succeeded',exit_code=0,
                points=[[0,1],[1,3],[2,5]],absolute_error_bound=0.02,
                calibration=dict(zero_reference=0.0,absolute_error_bound=0.005),
                repeated_points=[[0,1.001],[1,2.999],[2,5.001]],
                implementation_verification='输入输出配对与单位已经独立核对；解析读数，无求解器离散误差。')
        elif case=='b2':
            observation=dict(record_kind='synthetic_solver_attempt',state='failed',exit_code=2,
                error='Newton iteration failed to converge before producing valid output.',points=[],
                stale_partial_preview=[[0,0],[1,7]],preview_valid=False,reference_measurements=[])
        else:
            observation=dict(record_kind='synthetic_independent_measurement',state='succeeded',exit_code=0,
                points=[[0,0],[1,2]],absolute_error_bound=0.02,other_measurements_available=False)
        result=_register(rt,instance,name='experiment_results',raw=canonical_json(observation),kind='benchmark_observation',schema='benchmark.observation.v1',parents=(f.ref,))
        analysis=dict(record_kind='synthetic_prior_analysis',summary='整理本轮记录，尚未完成候选解释评价。',
            observation_source='experiment_results',limitations=['这是一份测试给定的历史记录，不是新 Agent 的结论。'],
            overall_verdict='invalid_study' if case=='b2' else 'inconclusive')
        _register(rt,instance,name='result_analysis',raw=canonical_json(analysis),kind='benchmark_history',schema='benchmark.history.v1',parents=(result.ref,))
    save(BASE/'instances.json',controls)
    save(BASE/'catalog.json', {key:rt.operation_catalog.operation(key).digest for key in rt.operation_catalog.operation_ids()})
    print(json.dumps({'prepared':str(BASE),'cases':list(controls)}))


def action(case, stage):
    rt=runtime(); instance=json.loads((BASE/'instances.json').read_text())[case]; root=router(rt,instance)
    current=root.call_tool('instance_current',{}); assert current['state']=='active',current
    if stage=='status':
        names=root.call_tool('run_list', {'limit':100})['runs']
        result=[]
        for row in names:
            status=root.call_tool('run_status',dict(name=row['name'],view='detail',output_paths=[],diagnostic_after=0,diagnostic_limit=100))
            path=BASE/(case+'-'+row['name']+'-status.json')
            saved=json.loads(path.read_text()) if path.exists() else {}
            if status['state']=='completed' and not saved.get('sealed_output'):
                status=root.call_tool('run_status',dict(name=row['name'],view='detail',diagnostic_after=0,diagnostic_limit=100))
                save(path,status)
            elif status['state']!='completed':
                save(path,status)
            result.append({k:status.get(k) for k in ('name','state','reason','output_artifact_name')})
        print(json.dumps(result,ensure_ascii=False)); return
    selection=json.loads((BASE/'selected_runs.json').read_text()) if (BASE/'selected_runs.json').exists() else {}
    proposal_name=selection.get(case,{}).get('proposal','proposal')
    common=dict(scientific_foundation='scientific_foundation',experiment_results='experiment_results',result_analysis='result_analysis')
    if stage=='proposal':
        operation='science.hypothesis.propose.v1'; ports=dict(common,problem_frame='problem_frame',previous_hypotheses='previous_hypotheses')
    elif stage=='critic':
        operation='science.hypothesis.criticize.v1'; ports=dict(common,hypothesis_portfolio=proposal_name+'.output',previous_hypotheses='previous_hypotheses')
    elif stage=='design':
        operation='science.experiment.design.v1'; ports=dict(common,research_objective='research_objective',hypothesis_portfolio=proposal_name+'.output',critic_review='critic.output')
    else: raise ValueError(stage)
    declaration=root.call_tool('operation_catalog',dict(operation_id=operation,view='detail'))
    save(BASE/(case+'-'+stage+'-contract.json'),declaration)
    request=dict(name=stage,operation_id=operation,inputs=[dict(port=k,artifact_names=[v]) for k,v in ports.items()],
        instruction='根据绑定的原始记录完成本角色任务，给出有来源且有范围的判断。此为合成科研行为验收，不访问生产实例。')
    checked=root.call_tool('operation_preflight',request); save(BASE/(case+'-'+stage+'-preflight.json'),checked)
    if not checked['admissible']: print(json.dumps(checked,ensure_ascii=False)); return
    queued=root.call_tool('operation_invoke',checked['normalized_request']); save(BASE/(case+'-'+stage+'-invoke.json'),queued)
    profile=queued['result']['execution_profile']['profile']
    command=[sys.executable,str(REPO/'scripts/run_compiled_codex_worker.py'),'--project-root',str(BASE/'project'),
        '--agent-type',queued['result']['agent_type'],'--model',profile['model'],'--reasoning-effort',profile['reasoning_effort'],
        '--memory-limit-mib','1024','--receipt-name',case+'_'+stage]
    save(BASE/(case+'-'+stage+'-command.json'),command)
    print(json.dumps({'queued':stage,'case':case,'profile':profile,'command_file':str(BASE/(case+'-'+stage+'-command.json'))}))

if __name__=='__main__':
    if sys.argv[1]=='prepare': prepare()
    else: action(*sys.argv[1:])
