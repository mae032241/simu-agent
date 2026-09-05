# R5-L0 实现候选独立审查

日期：2026-08-31  
审查者：`r5s_s0_independent_review`（未参与 L0 实现）  
结论：**不通过；不得放行 L1**

## 1. 审查范围

本轮绑定以下候选：

- 总计划摘要：`fe7e357e2956a73fe30630969faa6fa1e0d5e692073906a8265575a54da3577a`；
- L0 分类与冻结证据摘要：`0f1b01b748e9f6bb413172e311c601767daf84d124a4786df3ffd6f1d70016af`；
- L 架构首轮评审摘要：`d6d1babda0b203c3291b9f4ec24ee76d9116f34981f95857891c542816f42096`；
- L 架构第二轮评审摘要：`765b93dfced29bf7feb151d4160491e082a9e7ceb3dc1fe88761d2b996e664e6`；
- S2 起点清单：208 项，清单摘要
  `96740af4dcce821dc376adfb41e9f8bd5cf026a566c7bc8e2b4caf3d67347e53`。

由于当前工作树包含 R0—R5 多阶段未提交成果，本轮没有把相对 `HEAD` 的巨大历史差异冒充 L0
差异，而是逐项复算 S2 起点清单。结果为：208 项中 28 项内容变化、0 项缺失，生产范围只新增
`src/scidiscovery/operations/lifecycle.py`；即 L0/S2 当前生产候选共有 29 个变更或新增路径。

## 2. 已确认正确的实现边界

1. `AgentLifecycleProtocol` 已有一个编译器拥有的声明源。`PermissionTemplate`、Operation digest、Task
   authority、Codex profile 和 Worker Router 均能从编译 Operation 投影生命周期；插件生命周期名称
   碰撞在目录编译时失败关闭。
2. Worker 对外只列 `worker_open_assignment`、`worker_heartbeat`、`worker_submit_result` 三个固有动作；
   PDF、analysis、web、文件编辑和 TCAD debug 仍是 Operation 精确注册的能力，没有被合入巨型
   submit 接口。
3. 当前 `worker_submit_result` 在一个外部调用中执行校验、seal 和完成；校验失败仍保持可修改。
   `validate_output_file` 和 `finalize_file` 虽仍存在于旧 `TaskService` 内部，但已经不再是 Worker MCP
   动作。
4. 手工 checkpoint 名称已从生产代码、角色、Schema reason 和 activity 允许表退出；自动
   `validation_rejected`、`operation_tool_candidate/result` 与 `finalization_candidate` 快照仍保留。
5. 当前没有 `LocalTrustedBackend`、`RunService` 或把旧 `TaskService` 包进 backend 的新包装器。
   L0 文件也明确承认这些尚未实现，没有把旧 Task 路径伪称为目标架构。
6. Local 原生工具隔离仍被如实标记为 `SEC-002 known_issue`；本轮没有发现以提示词禁令冒充技术
   沙箱的发布声明。

这些正确点说明总体纠偏方向成立，但不能消除以下 L0 阻断。

## 3. 阻断项

### 3.1 四类账本不是可复算的逐符号账本，并且存在互斥分类

L0 证据第 8—10 行声明“所有变化按可执行符号或合同字段归类”，实际正文却没有列出 28 个变更路径
和 1 个新增路径的终点清单，也没有给出逐路径的变更符号与类别。更严重的是，所谓精确符号中存在
错误名称和互斥归类：

- 第 53 行写 `TaskTokenService.issue_dispatch_capability`，当前生产符号实际为
  `TaskTokenService.issue`；
- 第 57 行写 `WorkerProxyLeaseKeeper`，当前实现实际为
  `mcp_worker_proxy._AutomaticLeaseKeeper`；
- 第 55—56 行把 `TaskService.prepare_dispatch` 和 `claim_next` 冻结为 Hardened 精确调度能力，第
  101 行又把 role queue 列为从默认路径撤回；
- `prepare_dispatch`/`claim_next` 实际建立按角色普通队列，Router 在没有 exact capability 时会回退
  到 `claim_next`。`test_worker_exact_dispatch.py::test_role_queue_claim_next_remains_available` 还明确保护
  该旧行为。它不是计划第 231—237 行定义的 exact Hardened 能力，也与第 226—227 行“不回退共享
  角色队列”冲突。

影响：L1—L4 无法从账本确定普通 role queue 是应防腐保留还是应退出默认路径；后续极易把旧的非精确
领任务路径带入 Hardened，或为了通过“全部测试”长期保留一个目标架构明确排除的兼容入口。这直接
影响单一调度权威、最小上下文和奥卡姆式删除门。

最小修正边界：

1. 增加 L0 终点生产清单，包含当前 209 项及清单摘要；
2. 对 29 个变化/新增路径逐项列出真正变化的顶层符号或合同字段及唯一分类；同一文件可以多类，但
   同一职责不能同时“加固保留”和“默认撤回”；
3. 使用真实符号名；将 `prepare_exact_dispatch`、`claim_exact`、exact capability/session 恢复列入
   Hardened，将 `prepare_dispatch`、`claim_next`、无 capability 的 Router role-queue fallback 及其
   保活测试列入撤回账本；
4. 明确哪些测试保护目标能力，哪些测试只是迁移期见证并必须在 L6 删除，不能把整个测试文件笼统
   冻结。

### 3.2 Hardened 恢复没有被足够的防腐测试冻结

S2 第三轮独立设计审查第 26—29 行把以下内容列为实现硬门：真实 daemon 重启，并覆盖 seal 后、
Artifact 登记后 CAS 前、completed 响应丢失；同进程 Router 单测不能替代。

当前 L0 防腐清单只引用 `test_broker_restart_restores_only_the_same_session_without_renewal`。该测试在同一
pytest 进程中重新构造 runtime 和 `WorkerBrokerRouter`，没有启动、终止和重启真实 daemon，也没有
覆盖上述三个提交崩溃窗口。仓库测试中没有找到对这些窗口的其他实现。L0 证据第 72—75 行却把
`submit_result` 的响应丢失重放和同 attempt 恢复写成已经冻结的机制。

影响：L1—L4 会继续修改编译目录、Worker 工具投影、运行插件和 TCAD context；在缺少真实恢复基线
时，“每阶段运行防腐测试”无法检测这些修改是否破坏加固后端。317 项通过不能证明从未被测试的崩溃
边界。

最小修正边界：在不增加新状态或新权威的前提下，先增加可重复的进程级测试，至少覆盖：

1. seal 已持久化、Task 仍为 finalizing 后重启并只完成相同 manifest；
2. Artifact 已幂等登记、Task CAS 尚未完成后重启；
3. Task 已 completed、响应丢失后重启并返回相同完成投影；
4. 错误 task/attempt/worker/proxy/authority/session 及超过 hard deadline 均失败关闭；
5. 恢复不创建第二 session、不续绝对期限，finalizing 期间只能 submit。

上述测试必须进入 L1—L4 的防腐清单；否则不得把 Hardened 描述为已冻结。

### 3.3 生命周期单一投影缺少先前明确要求的合同回归

生产实现静态上已有单一声明，但测试没有闭合 S2 第三轮评审第 22—23 行列出的全部验收：

- 未找到插件注册 `worker_open_assignment`/`worker_heartbeat`/`worker_submit_result` 时得到
  `agent_lifecycle_tool_collision` 的负例；
- 未找到生命周期 input Schema、capability 或协议版本变化会改变 Agent Operation digest 的回归；
- 现有测试分别观察 catalog、Task、Codex、Router 和部署，但没有一个精确断言证明五者的名称、
  capability 与协议摘要来自同一编译投影；
- 未找到仓库外 fixture 注册并成功调用 `worker_run_analysis` 的正例；现有 installed fixture 只验证
  未注册 analysis 被拒绝；
- 多个闭环测试第一次 submit 只断言 `valid is True`，第二次才断言 `state=completed`。实现确实在
  第一次调用完成，但测试没有直接冻结“一次调用即完成”的合同。

影响：L1 将直接修改最小合同投影和盲插件。如果这些测试不先落地，第二注册表、摘要漂移、部署
硬编码和“表面三动作、实际仍二段提交”都可能在全量测试继续通过时重新出现，影响 `AUTH-003`、
`ROLE-002`、`IMM-002` 与插件低成本接入目标。

最小修正边界：只补聚焦合同测试，不增加生产抽象。测试应覆盖生命周期碰撞、协议/Schema 摘要进入
Operation digest、Task/Codex/Router/deploy 一致性、外部 analysis fixture 正向调用，以及第一次
`worker_submit_result` 直接返回 completed、校验失败后修正再提交的语义。

## 4. 33 项约束与奥卡姆判断

- `OperationSpec` 单一授权、插件领域边界、不可变 Artifact、Worker 科学内容所有权和 Local 安全
  缺口披露方向没有退化；
- 当前未新增第二目录、第二 preflight、第二 invoke、第二 current 或新科学状态机；
- `AgentLifecycleProtocol` 是为消除插件重复声明而增加的一个小值对象，具有真实消费者，不构成过度
  设计；
- 但 role queue 的双重分类会保留非精确兼容入口，违反奥卡姆原则；缺少摘要/恢复测试时不能声称
  `AUTH-003`、`ROLE-002`、`RES-002` 和 `MIG-002` 已由 L0 证明。

因此，问题不在需要继续增加实体，而在删除账本和测试见证尚不精确。修复不得借机实现 RunService、
Local backend、RecoveryPolicy 或新的恢复状态。

## 5. 独立测试证据

本轮在串行、低内存条件下运行：

1. `git diff --check`：通过；
2. 生命周期、目录、精确派发、Router、运行插件、Agent 合同和 Worker authority 聚焦集合：
   `67 passed in 36.85s`；
3. `PYTHONDONTWRITEBYTECODE=1 pytest -q tests/operations`：
   `280 passed in 96.23s`；
4. `PYTHONDONTWRITEBYTECODE=1 pytest -q tests/artifact_agent/test_platform_configuration.py
   tests/artifact_agent/test_deploy_scripts.py`：`37 passed in 5.55s`。

没有运行真实 Codex Agent、真实 TCAD solver 或真实 daemon 崩溃恢复；其中前两项不是 L0 科学验收，
真实 daemon 恢复则是当前缺失的阻断测试，不能写成“未运行但已由单测证明”。

## 6. 允许的下一步

**只允许修订 L0 分类/终点清单并补上述最小合同与恢复测试，然后重新独立复审。不得开始 L1，不得
实现 LocalTrustedBackend、RunService、盲 CSV 插件、TCAD 新闭环或 L5 加固迁移。**

复审通过门是：29 个变化路径可逐项复算；role queue 与 exact dispatch 不再互相矛盾；真实 daemon
恢复和生命周期单一投影有直接测试；现有 280+37 回归继续通过。测试数量本身不替代语义核验。
