# R5-M6 重复治理合同整体闭合证据

状态：M6-A—M6-D 均已分别通过独立审查；整体组合回归完成，等待 M6 独立终审；M7 未放行

## 1. 整体结论候选

M6 没有建立新的科研状态机，而是删除四处重复权威：

1. 实例创建/会话选择不再伪装成科学 Approval；
2. 同一输入组的资格合同不再复制到每个端口；
3. 生产者不再预测所有未来下游用途；
4. Effect 不再要求调度器调用第二个公共工具重建同一审批合同。

四项合并后，默认主干仍只有：一个插件入口、一个启动期编译目录、一个 preflight、一个 invoke、一个
RunService、一个 Artifact/current 权威、一个 ApprovalService 和一个 ExecutionService。M6 没有
增加目录、注册表、数据库、守护进程或运行状态。

## 2. A—D 的最终边界

### M6-A：直接实例管理

- 保留 ResearchInstance、session binding、语义 revision 和 scientific current CAS；
- loopback UI 以短期本地 capability 直接创建/选择并原子绑定会话；
- 删除实例/会话提案审批工具和三张专用提案/候选表；
- 调度 Agent、Worker 和聊天仍不能创建、选择或切换实例。

### M6-B：Operation 级输入准入

- `InputPortSpec` 删除 cohort、approval kind/options/providers 四个重复字段；
- 每个 Operation 最多一个可选 `InputAdmissionSpec`，区分 all-or-none members 与精确 approval
  subjects；
- 通用 preflight 在领域 guard 前检查成员完整性；Root 只查询同一编译资格合同；
- guard 中的隐藏成员集合已删除，普通无 admission Operation 没有资格状态成本。

### M6-C：消费者拥有用途

- `OutputPortSpec.allowed_input_usages` 及所有生产者未来用途清单删除；
- Root 只消费精确 producer id/version/digest/output port、编译 reviewer edge、下游输入用途、直接
  revision/change request 和 Operation 级准入；
- consumer-only 新用途不改变 producer digest；未审查 subject、旧 revision 和不匹配 reviewer 仍
  失败关闭；
- 没有全局用途图、跨插件拓扑表或领域分支。

### M6-D：Effect 自动建立待决定审批

- Effect 的 `operation_invoke` 创建 Execution 后，以同一编译合同幂等建立唯一 pending Approval，
  返回 request-specific loopback URL；
- 公开 `execution_approval_request_create` 删除；用户决定、显式 `execution_start` 和有界
  `execution_sync` 仍相互分离；
- Approval id/幂等键稳定绑定不可变 `execution_id`，提交/绑定窗口重复故障不会产生第二权威；
- Effect subject tuple 在编译期固定为 ExecutionRequest→payload，与 projector、决定和 authorize
  一致。

## 3. 完成门逐项核对

| M6 完成门 | 当前唯一事实与证据 | 结论候选 |
|---|---|---|
| Artifact、Run、current、Approval、Execution 各一个权威 | `ArtifactService`、`RunService`、`SchedulerBindingService` current CAS、`ApprovalService`、`ExecutionService`；无第二表/路由 | 通过 |
| 普通探索无 cohort/approval/execution 状态成本 | 无 `input_admission` 即不查询资格；Local 探索后 Approval 列表为空；普通 Agent 不创建 Execution | 通过 |
| 实例创建/选择仅由显式用户入口 | Root 只读返回管理 URL；loopback UI capability 执行直接事务；聊天/Worker 无写入口 | 通过 |
| 科学资格与执行授权保持两个决定 | qualification Approval Operation 与 `execution_authorization` 分属不同合同、subjects 和决定 | 通过 |
| readiness 与 invoke 同一绑定 | 两者都调用 `_prepare_operation_call`；invoke 只在成功预检后的同一 BoundOperationCall 上创建行为 | 通过 |
| Root 工具、表和规约字段净减少 | 见第 4 节 | 通过 |
| A—D 可独立审查和回溯 | 每项有独立证据、首次 FAIL/返工记录和最终 PASS 报告；旧 verdict 不被覆盖 | 通过 |

本表是终审候选，不代替未参与实现者的最终判断。

## 4. 可复算的净复杂度

### 4.1 Root 工具

M0 冻结为 30 个；当前为 26 个。M6-A 删除三个实例审批化入口，M6-D 删除一个 Effect 审批二步
入口。Local/Hardened 继续投影同一集合，没有后端专用第二工具表。

### 4.2 数据库事实

M0 的五个通用 owner 共 20 表；当前全新运行时为 15 表：

```text
Artifact   3: artifact_envelopes, artifact_links, idempotency_records
Scheduler  5: scheduler_bindings, scheduler_instances, scheduler_observations,
              scheduler_scientific_selections, scheduler_sessions
Run        2: run_activity, runs
Approval   4: approval_decisions, approval_requests, decision_attempts, used_nonces
Execution  1: executions
```

其中 M1 删除两张重复事件表，M6-A 删除三张实例/会话提案候选表；M6-B/C/D 新增表为零。显式
Hardened transport 和领域 adapter 的私有状态不进入默认通用数据库，也不是第二科学权威。

### 4.3 Operation 合同

M6 前 `InputPortSpec` 的 16 字段当前为 12，删除四个重复资格字段；`OutputPortSpec` 从 18 字段降为
17，删除未来用途预测；`OperationSpec` 从 11 增至 12，只增加一个可选 `input_admission`。三类合同
合计净减 4 个字段。ABI 因结构变化从 9 经 10 升到 11；生产路径没有历史双读。

### 4.4 整个 R5-M 当前规模

M0 为 146 个生产 Python 文件、50,023 行；当前为 141 文件、46,717 行，净减 5 文件、3,306 行。
当前 operations 包 8 文件、2,100 行，唯一 `catalog.py` 734 行；未突破既有 8 文件/2,103 行和 738
行门。默认五插件由 220 组件/46 Operation 收敛为 186 组件/43 Operation；可选论文图插件只有显式
安装才加入完整纵向能力。

## 5. 组合回归

在 7 GiB 虚拟内存上限、串行无并行执行：

```text
pytest -q \
  tests/operations/test_m6a_direct_instance_management.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/artifact_agent/test_artifact_audit.py
52 passed in 54.61s
```

当前完整串行回归由实现者与 M6-D 全新独立复审者分别执行：

```text
257 passed in 113.30s
257 passed in 113.22s
```

M6-D 首次审查的 B1/B2 反例在全新复审中分别以五次提交/绑定故障仍单请求、反向 projector 合同零
Execution/Approval 写入拒绝而通过。M6-B 首审的隐藏 all-or-none guard 集合、M6-A 的 capability/分页
缺口也都保留失败报告和最终修复证据。

## 6. 仍然明确保留的限制

- `SEC-002`：Local `spawn_agent` 的原生工具不可见性仍不是平台强制沙箱事实，保持 `known_issue`；
- M6 不证明真实 TCAD 科学准确率或远程 solver 可用性；这些属于 M7 真实纵向验收；
- 33 项注册表中的历史 `pending_review` 不因本阶段测试数自动晋级；
- M7 安装矩阵、真实 Agent/TCAD 闭环、外部 Effect UI 实际操作和最终发布验收仍未放行。

## 7. 审查索引

- M6-A：`R5_M6A_DIRECT_INSTANCE_MANAGEMENT_IMPLEMENTATION_EVIDENCE.zh-CN.md` 与
  `R5_M6A_DIRECT_INSTANCE_MANAGEMENT_INDEPENDENT_REREVIEW.zh-CN.md`；
- M6-B：`R5_M6B_OPERATION_INPUT_ADMISSION_IMPLEMENTATION_EVIDENCE.zh-CN.md`、首次 FAIL 与独立复审；
- M6-C：`R5_M6C_PRODUCER_TOPOLOGY_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md` 与独立 PASS；
- M6-D：`R5_M6D_EFFECT_AUTO_APPROVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`、首次 FAIL 与全新独立复审。

M6 整体终审必须重新检查当前组合字节，不能把四个局部 PASS 简单相加；只有终审明确 PASS 才可放行
M7。

## 8. 整体终审失败后的返工

2026-09-02 的首次整体终审结论为 FAIL，原报告保存在
`../reviews/R5_M6_OVERALL_INDEPENDENT_FINAL_REVIEW.zh-CN.md`。它发现两个局部审查组合后才暴露的阻断：

1. Execution 行和 request Artifact 已提交、Execution 语义 binding 尚未提交时，相同 Effect 调用重放
   仍会生成随机新 Execution；
2. Approval `status/list`、loopback 页面 GET 和 Execution `status/list` 中仍混有过期落库、访问令牌
   轮换和结果 binding 发布。

返工没有增加恢复表、后台清理状态机、Root 工具或 Operation 字段：

- Root 用实例、最终语义名和完整调用指纹派生稳定 `execution_id`；`ExecutionService.create` 对该身份做
  完整请求与标签重放校验。连续三次在 Execution 创建提交后注入 binding 故障，始终只有一个
  Execution 和一个 `execution_request` Artifact，恢复后同一对象被绑定并只建立一个 Approval，
  adapter submit 为零；
- Approval 业务过期改为纯读的有效状态投影，`status/list/request_summary/review` 不再落库过期；
  dashboard 不再隐式轮换 token/CSRF。过期访问链接只能由 loopback、同源和 CSRF 保护的显式 POST
  续期，且没有新增 Root 调度工具；
- `execution_status/list` 只投影已经存在的结果 binding。结果 manifest 的语义发布移到显式、幂等的
  `execution_sync` 或 `execution_outputs` 命令边界；
- 新增数据库前后摘要反例，覆盖业务过期 Approval、过期 UI token、Root approval status/list、真实
  dashboard/review GET、已 collected 但尚未发布 result binding 的 Execution status/list，以及显式
  token 续期和结果发布正例。

返工后的串行验证均设置 7 GiB 虚拟内存上限：

```text
审批/执行精确反例：18 passed in 13.02s
M6 组合与 UI 扩展：59 passed in 56.75s
跨边界扩展：116 passed in 74.93s
完整回归：260 passed in 113.55s
git diff --check HEAD：通过
```

当前生产 Python 为 141 文件、46,845 行；operations 仍为 8 文件、2,100 行，`catalog.py` 仍为
734 行。新增行来自显式 UI 续期命令和精确反例所需的窄实现，没有新增生产文件、数据库表、Root
工具、Operation 字段或第二 registry。

本节只形成新的终审候选，不覆盖首次整体 FAIL，也不自行放行 M7。必须由未参与上述返工的全新审查者
复验两个反例并明确 PASS。

## 9. 第一次返工复审失败后的 B3 修复

全新返工复审报告 `../reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW.zh-CN.md` 确认首次 B1/B2 已关闭，
但结论仍为 FAIL：当 `execution_request` Artifact 已提交、Execution 行尚未插入时，动态
`created_at` 会令相同稳定幂等键的重试产生不同字节并永久冲突。

第二次返工仍沿用同一身份原则，没有增加协调器或补偿状态：

- `execution_request` Artifact id 由稳定 `execution_id` 精确派生；
- 行不存在时只按该精确 Artifact id 读取候选，不按 kind、payload、labels 或相似内容扫描；
- 取回的请求必须逐项匹配 execution id、executor、preparation profile、payload ref、compiled
  identity，以及 Artifact 的 kind、Schema、版本、媒体类型、creator、parent、labels 和保密级别；
- 验证后使用冻结请求原字节（包括第一次提交的 `created_at`）再次调用原 Artifact 幂等登记。只有原
  idempotency record 与 registration 完全一致才会重放成功；缺记录或任一字段漂移继续 fail-closed；
- Execution 插入使用同身份的幂等插入，随后再次核对 request/payload/executor，不新增表或恢复事实。

新增精确回归连续三次在 Artifact 真正提交后抛错：每次均保持 0 Execution、1 request Artifact、0
Approval、无 binding、submit 0；第四次相同 `operation_invoke` 恢复为 1 Execution、1 request、1
binding、1 Approval、submit 0。随机 orphan 仍不会被收养，已有行的五类字段漂移负例继续关闭。

当前验证：精确审批/执行 `19 passed`，M6+UI 组合 `60 passed`，跨边界 `116 passed`，完整串行
`261 passed in 112.50s`，`git diff --check HEAD` 通过；生产 Python 141 文件、46,959 行，operations
8 文件、2,100 行。第二名全新独立复审尚未完成，故 M7 仍未放行。

## 10. 第二次返工复审失败后的 B4 修复

第二名全新审查者在
`../reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW_ROUND2.zh-CN.md` 中确认 B3 及首次 B1/B2 均转绿，
但仍判 FAIL：已有 Execution 行、语义 binding 尚未建立时，恢复分支只验证 request Artifact，没有
再次核对创建它的原 Artifact idempotency record；删除或损坏该记录后仍会建立 binding 和 Approval。

B4 不需要新恢复概念。当前修复让 existing-row 分支在返回前执行与 no-row 分支完全相同的登记重放：

- request ref 必须等于由稳定 `execution_id` 派生的精确 Artifact id；
- 冻结 request bytes 和完整 Artifact 元数据验证通过后，用同一 `ArtifactRegistration` 和
  `execution:<execution_id>:request` key 调用现有 `ArtifactService.register`；
- registry 必须返回同一精确 ref。原记录缺失时触发 Artifact identity conflict，hash/bytes/registration
  错误时触发 idempotency 或 registry integrity error；任何错误都发生在 binding、Approval 和 submit
  之前；
- 没有新增校验表、恢复状态、Root 工具或后台审计路径。

新增两个已有行精确负例，分别删除原 idempotency record 和损坏 request hash。两者均失败关闭并保持
Execution 未绑定、Approval 为零、submit 为零。精确审批/执行 `21 passed`，M6+UI 组合
`62 passed`，跨边界 `116 passed`，完整串行 `263 passed in 114.37s`，`git diff --check HEAD` 通过；
生产 Python 为 141 文件、46,970 行。第三名全新独立复审尚未执行，因此 M7 仍未放行。

## 11. M6 最终独立放行

第三名全新审查者完成报告
`../reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW_ROUND3.zh-CN.md`，结论 **PASS**，阻断 0、新增非阻断
0。它独立复验两个跨库窗口、请求/Artifact/幂等记录负例、随机 orphan、同/异请求并发、全库查询
纯读与结构门；串行结果为精确 `21 passed`、M6 组合 `62 passed`、跨边界 `116 passed`、完整
`263 passed`。

三份历史整体 FAIL 原样保留。M6 现已完成，唯一放行范围是进入 M7；本记录不宣称 M7 或 R5-M 完成。
