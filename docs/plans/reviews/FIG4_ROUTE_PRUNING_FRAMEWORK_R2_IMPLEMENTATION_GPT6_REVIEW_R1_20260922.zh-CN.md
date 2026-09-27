# Fig.4 路线剪枝框架 R2 独立实现效果复审 R1

审查日期：2026-09-22。Reviewer：GPT-6 Astra / xhigh；独立于计划作者、Sol 实施者、R0 Reviewer 和 Sol 修复者。

**Verdict：REVISE（修复效果级）。P1：0；P2：1；P3：0。**

R0 的 P2-1、P2-2、P3-1 已关闭；P2-3 的 distribution minimum、五种隔离组合、site/指南/配置文件恢复及双 reader 解析已得到真实执行证据，但实际 installer 的控制数据库回滚边界仍未闭合。本次两个串行 pytest 批次合计 **22 passed、0 failed**；另一个定向隔离探针复现了数据库回滚丢失快照后新增 Artifact 登记及绑定的行为。测试全绿不足以覆盖该缺口。

本报告只评价工程修复，不判定 Fig.4 路线科学成败，不要求补做 R2 后置的真实模型科学剪枝、live 部署或 token A/B。未部署、未访问生产实例、未启动科研 Run、未运行真实 solver。

## 唯一未关闭 finding

### P2-1（继承 R0 P2-3）：回滚夹具避开真实控制数据库，无法证明新结果保留与资格不恢复

**位置：** [安装态测试](../../../tests/operations/test_catalog_installed_entrypoint.py) L188–247、270–287；[实际 installer](../../../deploy/install.sh) L1238–1247、1272–1274、1336–1339、1359–1369；[回滚实现](../../../deploy/install_transaction.py) L58–75；[UI read model](../../../src/scidiscovery/artifact_agent/approval_ui/read_model.py) L174–182；[修复记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_REVIEW_R0_REMEDIATION_SOL_20260922.zh-CN.md) L32–33。

**缺陷与可达场景：** 新测试的事务只包含 `site`、`.codex`、`AGENTS.md` 三个 path；`reader-state` 的 Artifact/binding 数据库在事务之外。它自行切换目录，再直接调用 `rollback_transaction`，因此可以证明这三个目标被恢复，却不能证明实际 installer 的完整事务保留新结果。真实 `begin_install_transaction` 还快照 `artifact_agent/runs/approvals/executions/scheduler-bindings` 数据库；`rollback_transaction` 会删除当前数据库并恢复快照。实际入口在停止旧服务之前建快照，又在 `verify_installation`、事务 seal 之前启动新服务。若这些窗口发生登记/封存，后续验证失败就会恢复到登记之前。所查入口没有关闭这两个窗口的写入隔离。

**独立证据：** 本轮使用真实 `ArtifactService`、`SchedulerBindingService` 和 `begin_transaction(..., databases=...)` / `rollback_transaction` 在临时目录复现：先登记 old v1 并建快照，再登记 new v1，随后回滚。结果为 `before_rollback_artifacts=2`、`after_rollback_artifacts=1`；新 Artifact 的 `get_by_id` 返回 `ArtifactNotFoundError`，新绑定消失，旧绑定保留。这证明登记/寻址丢失；没有把仍可能存在的 CAS 字节误称为已物理删除。精确重放命令在下文。

此外，测试的 Run 是 `SimpleNamespace`，`Runs` 也是内存替身，`approvals=None`、`executions=None`、`operation_catalog=None`。其两次 `qualification.state == not_evaluated` 来自 `InstanceReadModel.node` 无条件设置的只读展示标记，没有经过真实 qualification、审查/审批或下游 admission。因此该断言不能支撑“回滚没有恢复资格”；本轮没有观察到实际资格被恢复，也不以此宣称已经复现权限绕过。

**影响：** R2 §8 的“不删除新结果、不借回滚恢复资格”尚无可信闭环，修复记录把只读 UI 标记提升成了控制边界证明。这不是要求生产部署或模型试验，而是 R0 已要求的本地工程回滚验收。数据库恢复机制在 HEAD 已存在，`deploy/install_transaction.py` 相对 HEAD 无修改；本报告不归因其为本轮新引入的生产缺陷。

**最小修复方向：** 让隔离故障测试沿实际 installer 的事务 target/database 集合及失败路径执行，保留完整控制状态；在数据库快照后尝试一次受控登记，证明生产入口会阻止该写入，或回滚仍保留该对象与绑定。若依赖停写保证，需把停写建立在快照之前并持续到验收完成；若采用只回退程序/配置而保留科学状态，则需验证相应兼容边界。资格部分应对真实冻结身份、资格/审查/审批状态及下游 admission 做前后核对，不能使用 UI 的固定 `not_evaluated` 替代。同步收窄修复记录 L33 的主张。无需扩展到科学 Run 或 live 部署。

## R0 逐项闭环核验

| R0 项 | R1 判定 | 已确认的工程证据与边界 |
|---|---|---|
| P2-1：真实提交、读取、HTTP、建议与停止 | **关闭** | 三 producer 在同一 Worker 上先拒绝 keyed 缺项，再合法封存；八个原 pointer/值、metadata 和 signal 同响应校验；同一合法 v1 覆盖三个 HTTP 入口及转义；建议反事实控制其他科学输入；停止读取无新工作。细节见下。 |
| P2-2：四失败及历史归因 | **关闭** | 四个原失败 selector 均独立复测通过，保留语义断言并实际运行后半段；原实施记录明确“历史时序不可核证”。当前正负例和真实调用路径支持当前因果边界，不追认实施前基线。 |
| P2-3：cohort / 回滚 | **部分关闭，保留上项 P2** | 五组合确实安装并执行真实 shell validator；三个文件目标恢复到 old 摘要，新旧 installed reader 均解析两份 v1。控制数据库保留和资格边界未得到该测试证明。 |
| P3-1：HypothesisAssessment 字段方向 | **关闭** | fixture 使用 `outcome` 和非空 `evidence_keys`；原实施记录 L136 已正确记为“把正确字段 outcome 错写为 status”。R0 报告未改。 |

### P2-1 的具体证据

1. [decision-contract](../../../tests/operations/test_analysis_decision_contract.py) L38–72、122–186：generic 与 curve-error 经真实 MCP `worker_submit_result` helper，TCAD 直接经 Worker router 提交。三个负例均得到 `state=rejected` 和 `$.payload.objective_assessment`；随后同 Worker 提交 `inconclusive + objective fail + claim_allowed=false`，hypothesis 使用真实 `outcome/evidence_keys`，三者均 completed。不是直接 validator 的替代证明。
2. 同文件 L160–186：一个 `run_status(response_profile="decision")` 同时断言 completed、signal available/verdict、v1 metadata、选中 Artifact 名、八 pointer 的顺序/selected 状态/原值；再用同一绑定读封存字节逐字段比较。八字段为 `/summary`、`/overall_verdict`、`/claim_allowed`、`/objective_assessment`、`/hypothesis_assessments`、`/limitations`、`/remaining_contradiction`、`/next_action`。
3. [HTTP 测试](../../../tests/operations/test_instance_approval_presentation.py) L24–71：先经 `LayeredDiagnosisReport.model_validate_json` 解析合法 v1，同一 Artifact 作为 Run 输出、Artifact 节点及真实 Approval request 的 subject，经启动的 HTTP server 读取三入口；核对独特原文、`<script>` 转义及无 `prune/剪枝` 派生文本。补充 [provider 测试](../../../tests/operations/test_instance_presentations.py) L61–79 保留 `claim_allowed=False`、原 pointer 和不改写 payload 的断言。HTTP fixture 的 Run/read-model 与 view entrypoints 有替身；这里证明真实 HTTP 路由/展示集成，不冒充真实模型或生产 browser。
4. [下一 design 测试](../../../tests/operations/test_result_analysis_tool.py) L229–306：两份真实封存分析在移除 `next_action` 后 payload 完全相等；同一 foundation/objective/hypothesis/critic 原件和相同 instruction 下，两个 design preflight 均 admissible、invoke 均创建 Run，各自冻结对应 analysis Artifact。先合法完成第一个 design，避免既有 slot gate 混入反事实。foundation approval 为明确 fixture stub，不把它算成真实审批资格验证。
5. [停止测试](../../../tests/operations/test_analysis_decision_contract.py) L189–227：decision read 前后比较权威 Run 列表、命名 execution/approval bindings 和 Artifact ID 列表，全部不变；真实 [decision 读取路径](../../../src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py) L128–151、283–300 只读取/投影 completed 内容，没有创建下一 Operation、Execution 或审批的调用。该 runtime 没有配置外部 Execution service，binding 检查不是真实 adapter 调用计数；结论限于 fixture 允许停止及当前读取路径无该副作用，不证明生产 scheduler 会自主停止。

### P2-2 与 P3 的具体证据

| 原 control | 实际修复和本轮覆盖 |
|---|---|
| A：generic wrong-round preflight | [测试](../../../tests/operations/test_result_analysis_tool.py) L164–183 分别断言 `input_result_plan_mismatch`、`input_review_plan_mismatch`；保留 result/review 缺父链及错误 operation/output-port label 四个负例。没有改成泛化成功或删除断言。 |
| B：no-contract author → review → package → execute preflight | [plan producer fixture](../../../tests/operations/test_l4_local_tcad.py) L1869–1882 保留 `revision.outputs[1:]` 的 control-owned collection，符合原 catalog/tool-evidence 合同；[纵向用例](../../../tests/operations/test_tcad_result_analysis.py) L329–339 实际到达 `tcad.study.execute` preflight 并断言 admissible，末尾 `assert reached` 执行通过。未放宽 compiler。 |
| C：curve-error compact submit | [helper](../../../tests/operations/test_analysis_handoff_report.py) L44–58 按真实工具集合判断绘图职责：有 `worker_analysis_publish_files` 才要求 overlay/axes/alias 指令；无工具的 curve-error 同时断言无对应职责文本。该参数用例已越过旧失败点，完成提交及后续封存断言。 |
| D：native error 留存 | [continuation 用例](../../../tests/operations/test_analysis_continuation.py) L147–166 显式请求 `--display raw`，再运行成功命令、封存、读取 completed detail；保留 attempt_count=2、error_count=1、最新 FileNotFoundError/原日志和无敏感路径泄漏断言，全部执行通过。 |
| P3：字段方向 | [真实 Schema](../../../src/scidiscovery/artifact_agent/schema/validation.py) L26–36 是 `outcome` 与非空 evidence_keys；修正的 UI/HTTP/Worker fixture 与之相符；[原实施记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md) L136 修正方向正确。 |

[原实施记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_R2_SOL_20260922.zh-CN.md) L120–155 保留旧失败观察值并撤回“已证实实施前 dirty baseline”的归因；[修复记录](../evidence/fig4-route-pruning-r2-20260922/IMPLEMENTATION_REVIEW_R0_REMEDIATION_SOL_20260922.zh-CN.md) L7、19–26 与此一致。当前可重放证据是上述四 selector 及三 producer 缺项→合法提交的正负对照；它们证明当前合同/修复效果，不恢复丢失的历史 patch 时序。本轮没有声称重新构造完整实施前 dirty tree。

### P2-3 已关闭的部分

[installer](../../../deploy/install.sh) L509–554 实际读取 stage 的 distribution metadata，以 `packaging.Requirement` / version specifier 执行 minimum 检查，并拒绝解析到 stage 外的 package；L597 把它接在 staged packages 验证阶段。`install_all` L1336–1339 在事务和退役服务前调用 `install_packages`，因此并非只有测试使用、生产入口遗漏的孤立 helper。

[隔离矩阵](../../../tests/operations/test_catalog_installed_entrypoint.py) L69–139 从精确 HEAD archive 构建 old wheels、从当前 release fixture 取得 new wheels，五次独立 `--target` 安装后调用真实 shell `validate_distribution_cohort`：

| 组合 | 实际结果 |
|---|---|
| C0/K0/T0 | 允许 |
| C1/K0/T0 | 允许 |
| C1/K1/T1 | 允许 |
| C0/K1/T1 | 拒绝，含 `scidiscovery-curve-score==0.2.2 requires scidiscovery>=0.1.1` |
| C1/K0/T1 | 拒绝，含 `tcad-artifact==0.1.1 requires scidiscovery-curve-score>=0.2.2` |

这里 C0 是 Git HEAD 构建的可归属工程 cohort，不是原实施前 dirty-tree wheel，也不证明生产当前装的是该 cohort。`--no-deps` 只负责隔离组合构造，实际 minimum 由后续生产 helper 拒绝，已修复 R0 指出的仅检查字符串缺口。

同测试 L141–165 由各自 installed core 生成 old/new 平台配置；L260–287 的真实 transaction 模块恢复 site、`.codex` 摘要与 AGENTS 原字节，old/new reader 均 strict 解析 old/new v1，并读取同一持久 Artifact/binding 状态。此结论仅覆盖所列路径与解析能力，不能扩大为上方 finding 涉及的控制数据库回滚或 qualification 保证。

## 范围、规范与候选身份

实际仓库为 `123/scidiscovery-e5.2`，分支 `refactor/m7-pre-e5.2`，HEAD 为 `943c4626f8490530e9318eb9fbb409d2670908b9`；审查当前未提交候选，相对 HEAD 检查 staged、unstaged、untracked。初始工作树为 125 个 tracked 修改、272 个 untracked 条目、无 staged/deleted；其中目录条目不等于文件数。未猜测 remote base，未把整个 dirty diff 归给修复者。

完整阅读外层及仓库 AGENTS、[R2 计划](../FIG4_ROUTE_PRUNING_FRAMEWORK_PLAN_R2_20260922.zh-CN.md)、[R0 报告](FIG4_ROUTE_PRUNING_FRAMEWORK_R2_IMPLEMENTATION_GPT6_REVIEW_R0_20260922.zh-CN.md)、两份实施记录及指定四个 SKILL.md。使用 `scid-cross-boundary-review` 追踪 producer→封存→Root/UI→后继 admission 与真实 installer；`scid-change-scope-checks` 选择最小串行复测；`scid-decision-corpus-maintenance` 区分规范、候选、自报台账和历史审查；`karpathy-guidelines` 限制为只新增本报告。未生成或修改任何实现/测试/旧文档。

文档 owner：双语 Architecture 与 R5-N/AGENTS 仍为规范；R2 是活动方案；两份 Sol 记录是各自候选的实施台账；R0 保留当时 REVISE，本 R1 仅对当前修复候选作部分闭环判定。没有将历史审查覆写为通过。

六个 R2 生产/指南文件的 SHA-256 与 R0 报告完全相同：shared validator、analysis workspace、TCAD result analysis、general-science provider、research/results guides。v1 Schema/validation/run_signal/role_result 相对 HEAD 无差异；本轮安装态合同测试确认 producer version `4/2/2`、PluginDefinition 原版本以及 support Transform version `1` / digest `0630777b4a8d874bb1b842b02834df8c6994a932498422ea2c2df5a88f6176ad`。定向搜索及入口检查未见新增 diagnosis v2、prune/continuation enum、stop pointer、route key/fingerprint、硬科学 admission 或第二路线权威。

| 当前候选文件 | SHA-256 |
|---|---|
| deploy/install.sh | `27579055745e8a3c9424e107dc3c0a3c614cea0a56302d8b1119232822621819` |
| deploy/install_transaction.py | `c21de5f9238abc928f9d2e9440d544a492f22e1f3cf7e0f8530c650828eb0f3a` |
| tests/operations/test_analysis_decision_contract.py | `5cc50cc2c5ea70f4841d0d3e81ac3486d478fe5f35b6a4f1e0326dd8abd56a4a` |
| tests/operations/test_catalog_installed_entrypoint.py | `e6f57890c694ef8145ebd652f9bfdfa8f5fa73f4dd41ea1b111b1a711898cabd` |
| tests/operations/test_instance_approval_presentation.py | `fd1c90a1d57bf95c7d5af65847585daabfcc4cc5b07ed6a14d02b9d32c4fbc25` |
| tests/operations/test_result_analysis_tool.py | `27a076e042cd9ab7451b2993c848dc7e67eaca17c616115fe956d69bc7dd72b5` |
| 原实施记录 | `d1c2e196ee927f219b7f9738ead5fc41f60c90ee200241ae48b22a078ce1caf0` |
| 修复记录 | `4d0818e818f8051227d13ae0fb5b4072f5f368d9bc475b59e4bfe77a8f60f664` |

## 实际复测命令与结果

遵守 [R5-N](../R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md) L72–82：批次串行，安装态矩阵只运行一个合并批次，未与其他审查/安装测试叠加；每批前要求 `MemAvailable >= 8388608 KiB`，实际为 14957860 / 14972768 KiB。设置 `ulimit -v 6291456`；两批退出后进程检查未发现遗留 pytest/pip/本地观测子进程。没有全量 pytest。

共同执行前缀（从仓库根）：

```bash
test "$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)" -ge 8388608
ulimit -v 6291456
env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 MALLOC_ARENA_MAX=2 \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /usr/bin/time -v timeout 180 python -m pytest -q -p no:cacheprovider \
  tests/operations/test_analysis_decision_contract.py \
  tests/operations/test_result_analysis_tool.py::test_generic_compiled_preflight_accepts_no_score_and_rejects_wrong_round \
  tests/operations/test_result_analysis_tool.py::test_no_score_real_review_worker_submit_then_next_design_reads_sealed_report \
  tests/operations/test_tcad_result_analysis.py::test_no_contract_author_review_package_execute_preflight \
  'tests/operations/test_analysis_handoff_report.py::test_other_analysis_operations_finalize_compact_drafts_through_mcp[curve_error]' \
  tests/operations/test_analysis_continuation.py::test_native_read_error_survives_success_and_is_visible_in_completed_root_status \
  tests/operations/test_instance_approval_presentation.py::test_legal_diagnosis_fields_render_escaped_without_route_badges_in_three_http_entries \
  tests/operations/test_instance_presentations.py::test_general_objective_plan_review_and_analysis_preserve_original_facts \
  tests/artifact_agent/test_deploy_scripts.py::test_primary_installer_has_valid_shell_syntax \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_builds_local_packages_offline_before_stopping_services \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_transaction_covers_every_mutated_release_surface \
  tests/operations/test_agent_contract_alignment.py::test_analysis_producer_versions_publish_one_keyed_scope_rule_without_changing_support_transform \
  tests/artifact_agent/test_scheduler_guides.py
```

**PASS：18 passed in 14.86s；exit 0；wall 15.32s；MaxRSS 151596 KiB。**

安装态使用相同环境及内存设置，timeout 改为 300：

```bash
env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 MALLOC_ARENA_MAX=2 \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /usr/bin/time -v timeout 300 python -m pytest -q -p no:cacheprovider \
  tests/operations/test_catalog_installed_entrypoint.py::test_installer_rejects_incompatible_route_pruning_wheel_cohorts \
  tests/operations/test_catalog_installed_entrypoint.py::test_installed_route_pruning_cohort_keeps_plugin_identity_and_v1_reader \
  tests/operations/test_catalog_installed_entrypoint.py::test_installed_gateway_returns_full_and_invoke_from_one_compiled_contract \
  tests/operations/test_catalog_installed_entrypoint.py::test_installed_scheduler_guides_use_context_projection_paths
```

**PASS：4 passed in 51.45s；exit 0；wall 51.72s；MaxRSS 92404 KiB。** 此批安装实际 wheels，gateway 用例是 installed Python router 集成，不称为本轮新测的 stdio proxy/daemon 链。

发现实际 database 集合与测试不同后，追加唯一有决策意义的隔离反例。命令仍在同一 6 GiB 地址空间限制下执行，先通过相同 MemAvailable 检查：

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 MALLOC_ARENA_MAX=2 \
  /usr/bin/time -v timeout 60 python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from deploy.install_transaction import begin_transaction, rollback_transaction
from scidiscovery.artifact_agent.schema.artifact import ArtifactRegistration
from scidiscovery.artifact_agent.schema.refs import ActorRef
from scidiscovery.artifact_agent.service.artifacts import ArtifactService
from scidiscovery.artifact_agent.service.scheduler_bindings import SchedulerBindingService
from scidiscovery.artifact_agent.storage import ArtifactNotFoundError

with TemporaryDirectory(prefix='fig4-r1-rollback-') as directory:
    root = Path(directory)
    database = root / 'artifact_agent.sqlite3'
    bindings_database = root / 'scheduler-bindings.sqlite3'
    artifacts = ArtifactService.open(cas_root=root / 'cas', database_path=database)
    bindings = SchedulerBindingService(bindings_database)
    instance = bindings.create_instance(name='probe', title='Rollback probe', objective='Engineering fixture only')
    actor = ActorRef(actor_id='probe', actor_type='service')
    registration = ArtifactRegistration(kind='fixture', schema_id='scidiscovery.layered-diagnosis.v1', payload_schema_version=1, media_type='application/json', creator=actor)
    def register(name):
        raw = ('{"study_kind":"engineering","experiment_key":"fixture","plan_key":"fixture","summary":"' + name + '","overall_verdict":"inconclusive","claim_allowed":false}').encode()
        artifact = artifacts.register(raw, registration, idempotency_key=name)
        bindings.bind(instance=instance.instance_id, namespace='artifact', name=name, object_id=artifact.artifact_id)
        return artifact
    old = register('before_snapshot')
    transaction = root / 'transaction'
    begin_transaction(transaction, targets=(), databases=(('db-artifact_agent', database), ('db-scheduler-bindings', bindings_database)))
    new = register('after_snapshot')
    before = len(artifacts.list_artifacts())
    rollback_transaction(transaction)
    restored = ArtifactService.open(cas_root=root / 'cas', database_path=database)
    restored_bindings = SchedulerBindingService(bindings_database)
    assert restored.get_by_id(old.artifact_id).artifact_id == old.artifact_id
    try:
        restored.get_by_id(new.artifact_id)
    except ArtifactNotFoundError:
        missing = True
    else:
        missing = False
    remaining = restored_bindings.list(instance=instance.instance_id, namespace='artifact')
    assert missing and [item.name for item in remaining] == ['before_snapshot']
    print({'before_rollback_artifacts': before, 'after_rollback_artifacts': len(restored.list_artifacts()), 'new_artifact_lookup': 'ArtifactNotFoundError', 'remaining_bindings': [item.name for item in remaining], 'preserves_post_snapshot_result': False})
PY
```

**反例复现成功，所检查的“保留快照后结果”属性 FAIL**；程序 exit 0 表示观察符合反例断言，不是该保证通过。wall 0.33s；MaxRSS 47844 KiB。没有调用生产 installer、systemd、真实科研 Worker 或 solver。

另运行了仓库定位/status/diff、定向调用点与禁止机制搜索、关键文件 SHA-256、`git diff --check`。外层路径不是 Git 仓库，首次在那里执行 `git status` 得到 `fatal: not a git repository`；随后定位到上述真实仓库，无工作树操作。

## 未运行项、残余风险与交付检查

未运行全量 pytest、全 operations、science-control bench、生产 browser/服务切换、真实 external execution、solver、Fig.4 exact 原件审计、真实 Root replay/production Worker 科学行为或 token A/B；这些不是本轮四项修复复审所需的后置工作。未重复 R0 已运行且相应生产文件摘要未变的全部 prior/replay/reference/historical 集合。真实安装状态、并发写入隔离及资格回滚仍受本次 P2 限制；未授予发布或部署 PASS。

未发现本轮 conditional assessment/guide/UI 修复新增其他跨边界 P1/P2。ordinary advice 仍无行动权威，历史 v1 仍可读；工程 fixture 的停止不等于模型已学会剪枝，已安装 reader 解析不等于科学 qualification。全部 R0 finding 闭合前，不将 R2 标记为完整工程验收通过。

部署状态：**未部署**；仅临时目录中的 wheel 安装和工程存储探针。Root、Sol 实施者/修复者、本 Reviewer token：**不可观测、未估算**；未取得可唯一归属的原生 usage/trace，RSS 与耗时只作资源记录。

报告完整性：本报告 25 个 Markdown 本地链接已逐项解析，文件存在；无未填占位符。全工作树 `git diff --check` 无诊断、exit 0；本报告相对 `/dev/null` 的 no-index whitespace 检查无诊断、exit 1 仅表示新文件有内容差异。交付前复核上述候选摘要未变化。本轮只新增本报告，未提交、还原、覆盖、整理或改写其他作者文件。
