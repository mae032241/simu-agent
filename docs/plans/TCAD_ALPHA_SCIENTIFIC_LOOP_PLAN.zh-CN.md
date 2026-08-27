# TCAD Agent Alpha 科学闭环架构复审与修复计划

## 1. 结论与优先级校准

本轮复审把唯一主目标改为：**先让一个真实、可恢复、可审计的 TCAD 科学闭环从头到尾连续跑通**。
当前系统不是“没有科学能力”，也不是需要推倒重来。它已经具备不可变 Artifact、独立 deck
审查、显式求解器 capability、人工执行审批、真实 SProcess 运行、确定性 Fig.4 scorer、分层诊断
Schema、知识状态归约和可迁移 Bundle 等关键构件。2026-08-05 的 Fig.4 `f=0` 控制运行还提供了
一次真实 Sentaurus SProcess R2020.09 证据：PLX、TDR、log 和 manifest 均已收集，冻结 scorer
在 `baseline_recovery` 门失败，H1 被证伪，没有模型被接受。

因此，旧复审中“尚未形成完整科学闭环”的核心判断仍然成立，但若把当前系统描述为“几乎不可用”
或继续将部署加固、完整安全矩阵和通用 SDevice DAG 与科学闭环同列 P0，就过于严苛。更准确的判断是：

> 当前架构是“已经跑通过真实求解器半环、科学对象较丰富，但应用层连接和权威状态回写尚未闭合”
> 的 alpha 前状态。最大风险不是局部 shell/path 安全，而是同一研究 case 的 review、执行、运行时
> 资格、评分、诊断和 checkpoint 没有被一条精确父链连续绑定。

本计划取代“生产交付全部门槛同时收口”的排序。旧计划继续作为完整工程 backlog，不能再阻塞 alpha。

## 2. 本轮核查范围与事实基线

本轮重新核查了控制面、scheduler topology、role/context 合同、TCAD packager/adapter、执行结果收集、
runtime attestation、Fig.4 scorer、知识归约、研究状态工具、三类闭环测试，以及当前 InGaAs/InAlAs
工作区的真实运行记录和活动 Bundle。

### 2.1 已证实可用的基础

- `research/current.yaml` 通过状态校验，当前有 511 条 run ledger 记录；权威科学阶段是
  `fig4_sprocess_baseline_provenance_diagnosis`。
- 活动 Bundle `fig4_baseline_provenance_20260806.bundle` 已通过完整性验证，包含 16 个精确绑定对象，
  Bundle SHA-256 为
  `684d106dac3baa3026051300c8112d7fecd79cb41d96ed6212b59e511be018e3`。
- Bundle 已包含历史基线原始 PLX/log/manifest/deck、候选真实 PLX/TDR/log/manifest、deck author/review
  产物、确定性 metrics/residuals/diff 和独立 evidence audit。
- 当前未决输入只有 `baseline_provenance_diagnosis` 和 `research_checkpoint_projection`。
- targeted 回归覆盖 Bundle、动态 readiness、scheduler topology、Artifact transform、进程执行桥和
  Fig.4 scorer，共 26 项通过；上一轮代码修复后的全量基线为 `322 passed`。
- 生产 `TCADExecutorAdapter` 已只接受 `tcad.reviewed-deck-package.v2`，真实执行输出也会登记成
  可按逻辑名解析的 Artifact。

这些事实意味着断网不妨碍先完成 alpha 的后半环；现有真实运行证据足以用于离线诊断、checkpoint
和恢复性验证。网络恢复后再做一次受限真实 replay，而不是现在等待外部环境。

### 2.2 Alpha 成功的定义

alpha 的“闭环成功”不等于模型通过，更不等于通用 SProcess→SDevice 平台已经生产合格。一次
科学假设被证伪、研究无效或结果不确定，只要结论可追溯且产生明确下一动作，也算成功闭环。

一个 alpha loop 必须满足：

1. 从一个冻结的科学矛盾、假设/比较合同和精确输入集合开始。
2. 使用经过独立 review、绑定显式 capability 且经人工授权的 package；对于离线续跑，可使用
   已经由同一合同产生并冻结的真实执行证据。
3. 收集一次直接 SProcess 调用的 solver 原生输出及 transport manifest/log。
4. 从这次执行实际收集的 manifest 和输出生成 runtime attestation，不能手工注册替代品。
5. 确定性 scorer 生成 metric report。
6. diagnostician 在严格输入合同下生成 `LayeredDiagnosisReport`。
7. 确定性归约产生 knowledge update/state；若研究不涉及假设状态变化，也必须显式记录
   `not_applicable` 和下一动作。
8. 一个显式 checkpoint 操作把本次诊断投影到 `research/runs.jsonl` 和 `research/current.yaml`，
   且保持“未接受模型”边界。
9. 新进程或导入后只靠已登记对象即可恢复到正确下一动作，不依赖聊天记忆或人工抄写摘要。
10. 上述对象属于同一个 loop/case/revision 父链；其他历史对象不能让该 loop 虚假显示为完成。

## 3. 当前架构的主要不足

### P0-1：没有“一次科学闭环”的精确、可恢复状态对象

`scientific_readiness` 当前按 ResearchInstance 中“每个语义名的最新修订”汇总 Artifact kind，再按
kind 集合推导可执行动作。它不知道某个 experiment、reviewed package、execution result、runtime
attestation、metric report 和 diagnosis 是否属于同一个 case 和同一次 revision。

这会产生两类 alpha 级错误：

- 旧的、不相关的 `execution_result` 或 `metric_report` 可以让新实验看起来已经可评估。
- 聚合 inventory 能列出下一能力，却不能回答“Fig.4 这一次 loop 已经走到哪一步、缺少哪个精确父对象”。

不应为此建设通用 workflow 引擎。alpha 只需要一个窄的 `ScientificLoopRecord`：绑定 loop key、case key
和各阶段精确 ArtifactRef，并由确定性校验器推导阶段。

### P0-2：生产对象命名与 scheduler ontology 已经漂移

当前代码中至少存在以下直接不一致：

| 位置 | 当前合同 | 实际生产对象/transform | 后果 |
|---|---|---|---|
| reviewer role | topology 期待 `deck_review` | role 输出 `tcad_project_review` | 真实 review 不会解锁 packager；测试靠手工登记 kind 掩盖问题 |
| reviewed packager | topology 只要求 project + review | v2 transform 还强制 capability | readiness 会过早建议一个必然失败的动作 |
| runtime attestation | topology 表达 package + execution result | transform 实际还需要 collected runtime manifest 和输出 payload | “执行完成”不能自动、精确地转成 runtime 资格 |
| control equivalence | topology 表达 experiment + project | materializer 实际需要 comparison contract + reviewed package + case | 建议能力与可调用接口不一致 |
| knowledge closure | topology/readiness 使用 `knowledge_state` | transform 输出 `knowledge_update` 和 `knowledge_state_projection` | 诊断后的闭环状态在 readiness 中不可见 |
| execution planning | 已有 `StudyExecutionPlan` Schema | 没有生产 service、root tool 或 topology 接入 | 只是可验证数据结构，不能驱动一次执行 |

此外，`ArtifactKind` 尚未覆盖 solver capability、realization snapshot、study execution plan 等已经出现的
生产概念。alpha 先统一单案例垂直链使用的最小 ontology；多案例计划对象暂不强行接入主路径。

### P0-3：现有测试分别证明了三个“半闭环”，没有一条纵向集成证据

- `test_scientific_loop_smoke.py` 从手工 JobSpec 执行后直接调度 diagnosis，没有通过 v2 reviewed
  package、实际 runtime attestation、scorer 和 checkpoint。
- `e2e/test_process_execution_loop.py` 使用 v2 package 和两个 daemon 完成审批/执行/收集，但止于
  `collected`。
- `test_fig4_clean_mock_loop.py` 在内存中验证 control equivalence、diagnosis 和 knowledge update，
  没有执行层。

这些测试都各自有价值，但 `322 passed` 不能等价于“一个科学 loop 已闭合”。alpha 必须新增一条
纵向测试，使用现有真实 production service/transform，而不是再造第四个测试专用编排器。

### P0-4：真实 execution outputs 没有被连续送入 runtime attestation

TCAD collect 已经返回 `tcad_log` 和 `tcad_manifest`，控制面也能将每个输出绑定为 Artifact；runtime
attestation transform 也存在。但当前 process E2E 在 collection 后停止，attestation 测试使用手工注册
的 manifest，尚未证明“刚收集的 manifest/output → attestation”这一跳。

另一个失败路径缺口是：预启动取消等 manifest 的 `started_at` 为 `null`，而
`TCADRuntimeManifest.started_at` 强制为字符串。这使失败执行不能通过统一证据路径进入诊断。alpha
只需允许合法的未启动终态并明确其 gate 结果，不扩张成完整故障分类系统。

### P0-5：diagnostician 和 deck author 的关键输入仍主要靠 prompt 约束

deck reviewer 已有严格的 context profiles；experiment designer 也有控制面策略。diagnostician 和
deck author 没有 role-specific context policy，因而默认允许额外或缺失输入。对当前 Fig.4 来说，
scheduler 可以在没有冻结 metrics/audit 或没有同一执行父链时调度诊断，最终 Schema 仍可能合法。

alpha 只新增两个窄 profile：

- `fig4-baseline-provenance.v1`：精确要求冻结 target、历史/候选原始证据、metrics、residuals、deck diff
  和 evidence audit。
- `executed-study.v1`：精确要求 experiment/hypothesis、reviewed package、execution result、runtime
  attestation、metric report 和 control report（声明不适用时用类型化占位，而不是省略）。

author profile 只覆盖单案例 SProcess 所需的 foundation、experiment、capability；SDevice profile 放到
后续里程碑。

### P0-6：CAS 科学状态与工作区权威 checkpoint 之间没有应用桥

知识 transform 能产生 `knowledge_update` 和 `knowledge_state_projection`，但 `research_state` CLI
只有 `validate`、`refresh` 和 `format`：`refresh` 仅重新计算现有文件哈希和 ledger 计数。它不能从
一个精确 diagnosis/knowledge projection 生成终态 run 记录，也不能更新 `current.yaml` 中的
contradiction、verdict、blockers 和 next action。

当前活动 Bundle 已明确把 `research_checkpoint_projection` 列为未决输入，说明这不是推测，而是
真实工作区的当前断点。alpha 需要一个显式、可预览、原子应用的 checkpoint 命令；不能让 Agent
自由编辑 YAML/JSONL，也不能让导入 Bundle 自动修改工作区。

### P0-7：现有 Fig.4 loop 的最后两步尚未完成

真实 f=0 运行已经完成执行、收集和评分，但活动 Bundle 仍缺独立 provenance diagnosis 和权威
checkpoint。因此这是最短、最真实的 alpha 闭环目标。先完成它，比先新增一次仿真或继续拟合物理
参数更能验证架构。

### P1：SProcess→SDevice 尚不能通过生产路径

`ReviewedDeckPackage` 已能表达 `ResolvedProjectInput`，单元测试也证明二进制字节可被密封；但生产
transform `_package_reviewed_project` 只接受 project/review/capability，并构造空的 resolved inputs。
生产 execution adapter 调用 packager 时也不提供 CAS 中的二进制 payload。因此需要 TDR 输入的真实
SDevice project 仍不能经 v2 路径执行。

这是 alpha 的下一阶段，而不是当前 P0。先闭合单案例 SProcess；随后再增加控制面拥有的二进制输入
解析/staging service 和最小 SProcess→SDevice smoke。不要先实现通用 DAG 或猜测 TDR 格式。

### P2：需要保留但不阻塞 alpha 的问题

- 锁定 wheelhouse、公开发布许可证决策、完整 root/systemd 故障注入矩阵。
- 通用多案例调度、跨发行版 TDR metadata provider、完整 PLT/TDR parser 资格矩阵。
- 报告中 solver 原生输出与 transport 派生 log/manifest 的计数术语；当前报告称“四个声明输出”，
  更准确应拆成两个项目声明输出和两个 transport 证据输出。
- 所有部署路径、权限和服务隔离的进一步加固。

这些事项不删除，也不撤销已有最小安全边界；只从 alpha 主路径移出。

## 4. 修复策略：一条窄垂直链，而不是再铺横向能力

### 4.1 最小对象

新增 `ScientificLoopRecord v1`，只做精确绑定和阶段投影，不自动决定科学任务顺序：

```text
loop_key + case_key + objective/contradiction
  -> experiment/hypothesis refs
  -> reviewed_package + capability refs
  -> approval + execution_result refs
  -> runtime_attestation ref
  -> metric/control refs
  -> diagnosis ref
  -> optional knowledge_update/state refs
  -> checkpoint ref
```

阶段由已绑定、父链一致且 payload 合格的字段确定：

```text
frozen -> reviewed -> authorized -> collected -> runtime_qualified
       -> scored -> diagnosed -> checkpointed
```

失败不是脱离状态机：`runtime_failed`、`invalid_study`、`falsified` 和 `inconclusive` 是诊断/verdict，
只要 checkpoint 已写入，loop 仍可处于 `checkpointed`。这避免为了“成功”掩盖负结果。

### 4.2 控制面职责

- root tool 只接收当前 ResearchInstance 内的语义 Artifact 名称，控制面解析并写入精确 ArtifactRef。
- 每次 bind 都验证 schema、kind、case、revision 和父链；不允许 worker 填 Artifact ID/摘要。
- `scientific_readiness` 暂时保留为全局 inventory，但 UI/scheduler 判断某次闭环是否完成时必须读取
  `scientific_loop_status(loop_name)`。
- 不在 alpha 中实现自动 workflow scheduler；scheduler 仍决定下一动作，loop record 只提供事实状态。

### 4.3 Checkpoint 职责

增加 `ResearchCheckpoint v1` 和显式 apply 流程：

1. 确定性 transform 从 loop record、diagnosis、knowledge projection 和当前状态摘要生成 checkpoint。
2. `research-checkpoint preview` 展示将追加的 run event 和 `current.yaml` 字段差异，不写文件。
3. `research-checkpoint apply` 验证输入 ref、当前 source digest 和未接受模型边界，以临时文件 + rename
   原子追加 `runs.jsonl` 并更新 `current.yaml`。
4. apply 后立即运行现有 `research_state validate`；失败则恢复两个文件，不能留下半更新。
5. 同一 checkpoint 摘要重复 apply 必须幂等；冲突的旧状态摘要必须失败。

checkpoint 只投影 Agent 已给出的、Schema 验证过的判断，不自行创造或接受科学模型。

## 5. 实施里程碑

### Alpha-0：断网条件下闭合现有 Fig.4 后半环（最高优先级）

目标：不启动新 solver，使用已验证活动 Bundle 完成 diagnosis → knowledge/not-applicable → checkpoint →
restart/resume。

任务：

1. 新增 Fig.4 baseline provenance diagnosis context profile，并用现有 16 个 Artifact 中的最小精确集合
   调度 diagnostician。
2. 对 diagnosis 的 evidence keys、首个失败 gate、claim_allowed=false、H1/后续机制判断停止规则做
   确定性校验。
3. 创建最小 `ScientificLoopRecord`，把已有真实 execution、metrics、audit 和新 diagnosis 绑定为同一
   case 父链。
4. 实现 `ResearchCheckpoint` preview/apply，把结论追加到 ledger 并更新当前矛盾/下一动作；保持
   `accepted_model=false`。
5. 导出 successor active Bundle，未决项不再包含本轮 diagnosis/checkpoint，而是明确记录下一项
   科学动作。
6. 关闭进程后重新导入/选择该 Bundle，证明 status 为 `checkpointed` 且 next action 一致。

验收：

- 原 Bundle 仍能验证，且不会被原地篡改。
- diagnosis 只能读取 profile 允许的精确输入；删掉、替换或跨 revision 任一输入都会失败。
- checkpoint preview 的 run event/current diff 可重复，apply 原子、幂等。
- `research_state validate` 通过，ledger 只新增预期终态事件。
- 新进程恢复后无需聊天上下文即可说明：基线恢复失败、无模型接受、下一步是什么。

预计工作量：1–2 个工程日。此里程碑完成即证明“冻结真实证据可以闭环”，但尚不证明新执行可以自动
贯穿全链。

### Alpha-1：单案例 SProcess 真正纵向贯通

目标：从 reviewed package 到 checkpoint 只使用生产 service/transform 完成一次连续链。

任务按依赖顺序：

1. 统一最小 ontology：修正 `tcad_project_review`/`deck_review`、capability、runtime manifest/output、
   realization 和 knowledge projection 的 kind/Schema 映射。
2. 修正 `_CAPABILITIES`，使每条建议能力的输入名和实际 transform 完全一致；对暂未接入的
   `StudyExecutionPlan` 不给出虚假建议。
3. 增加 `ScientificLoopRecord` root operations：create/bind/status；绑定时做精确父链验证。
4. 将 `execution_outputs` 返回的真实 `tcad_manifest` 和 solver 输出直接送入 runtime attestation；
   为未启动终态定义合法 manifest/gate 语义。
5. 为单案例 SProcess author 和 executed-study diagnostician 增加严格 context profile。
6. 增加一条纵向 process E2E：v2 package → approval → direct fake solver → collection → runtime
   attestation → deterministic scorer → diagnosis fixture → knowledge reducer → checkpoint preview/apply →
   restart。fake solver 只用于 CI 证明控制链，不声明 Sentaurus 物理合格。
7. 用现有真实 Fig.4 对象跑相同的 collection 之后半链；网络恢复后再做一次预算受限的真实
   SProcess replay，确认没有测试专用旁路。

验收：

- 纵向测试中任何阶段的输出必须是下一阶段的精确父对象；注入一个同 kind 的旧 Artifact 不能解锁。
- 实际 collected manifest，而不是手工 fixture manifest，产生 runtime attestation。
- runtime gate 失败仍能进入 diagnosis/checkpoint，但不能进入物理解释或 claim accepted。
- `scientific_loop_status` 和 `scientific_readiness` 对该 loop 无矛盾；闭环完成以 lineage status 为准。
- CI fake-solver 纵向测试、现有 Fig.4 fixture 和全量回归均通过。
- 真实 replay 只要求得到可辩护 verdict，不要求模型通过；无远端网络时记录为外部资格门，不阻塞代码合并。

预计工作量：3–5 个工程日。

### Alpha-2：最小 SProcess→SDevice 文件链

前置：Alpha-1 完成。目标是验证上游 TDR 能以不可变二进制 Artifact 成为下游 SDevice 输入，不建设
通用多案例平台。

任务：

1. 增加控制面 owned 的 `resolve_project_inputs`/packaging service，从语义名解析精确 ArtifactRef，
   校验摘要、size、media type 和目标相对路径，并向 packager 提供 bytes。
2. reviewed package 的父链覆盖 project、review、capability 和全部 resolved inputs；执行 adapter 不得
   自行查询 CAS。
3. 只接入一个 case、两个 execution units 的最小 `StudyExecutionPlan` service；上游必须 collected 且
   runtime qualified 才能绑定下游 TDR。
4. 用合成二进制哨兵完成 CI staging/E2E；它只证明字节链，不证明 TDR 格式或 SDevice 科学有效。
5. 有匹配许可证、版本和真实 TDR capability 时再做一个最小 SDevice smoke。

验收：

- 上游失败、未 attested、TDR 被替换或目标路径不一致时，下游不能授权。
- 打包前后 TDR 字节摘要一致，SDevice `Grid` 引用与 staged 文件完全一致。
- SProcess 和 SDevice 始终是两次直接 solver 调用，不能包进 shell/nested launcher。

预计工作量：3–5 个工程日；真实 SDevice 资格不作为 Alpha-0/1 的完成门槛。

### Beta backlog：恢复生产化排序

Alpha-1 完成后才恢复旧计划中的完整工作流：

- 多案例/并行 DAG 和失败传播通用化。
- 版本化 PLX/PLT/TDR parser provider 与跨发行版资格矩阵。
- 锁定 wheelhouse、目标机 root/systemd 故障注入、公开许可证决策和发布冻结。
- 更完整的路径/权限/隔离加固与交付文档。
- 暗电流、光学及五层器件科学研究的后续模型闭环。

## 6. 实施任务表

| ID | 优先级 | 任务 | 前置 | 完成证据 |
|---|---:|---|---|---|
| A0-1 | P0 | Fig.4 provenance diagnosis profile 与任务 | 已有活动 Bundle | 严格输入正反测试 + 合法 diagnosis |
| A0-2 | P0 | `ScientificLoopRecord v1` 最小 Schema/status | A0-1 可并行 | 同 kind 跨链对象不能解锁 |
| A0-3 | P0 | `ResearchCheckpoint v1` preview/apply | A0-1、A0-2 | 原子/幂等/冲突回归 + state validate |
| A0-4 | P0 | successor Bundle 与重启恢复 | A0-3 | 新进程恢复正确 next action |
| A1-1 | P0 | ontology/topology 对齐 | A0 可并行设计 | role 输出可直接解锁真实 transform |
| A1-2 | P0 | collected outputs → runtime attestation | A1-1 | process E2E 不再手工造 manifest |
| A1-3 | P0 | author/diagnostician 严格 context | A1-1 | 缺失/多余/错 Schema 输入失败 |
| A1-4 | P0 | 一条生产纵向 E2E | A0-3、A1-1..3 | reviewed→checkpoint 全链通过 |
| A1-5 | P0 外部资格 | 真实 SProcess replay | 网络/VM/license | 同路径产生可辩护 verdict |
| A2-1 | P1 | CAS 二进制 input resolver/packager | Alpha-1 | 字节和父链一致性测试 |
| A2-2 | P1 | 最小两单元 execution plan 接入 | A2-1 | 上游 gate 控制下游授权 |
| A2-3 | P1 外部资格 | 真实 SDevice smoke | capability/license | 独立直接调用并收集 |

## 7. 测试与证据策略

### 7.1 必须新增的失败回归

1. 用旧 execution result 搭配当前 experiment 时，loop 不能显示 `collected`。
2. 真实 reviewer 输出 `tcad_project_review` 后，packager 不再因 kind 别名漂移而卡住。
3. 缺 capability 时 readiness 不建议 v2 packaging。
4. 手工注册的同名 runtime manifest 不能替代当前 execution output。
5. 预启动取消能形成合法失败 attestation 和 diagnosis。
6. diagnostician 缺 metrics/audit 或加入未授权 Artifact 时不能调度。
7. knowledge transform 输出在 loop status 中可见，且不会被错误当成另一个 Schema。
8. checkpoint 在 `runs.jsonl` 已变化后拒绝应用旧 preview。
9. checkpoint 写入中途故障时两个权威文件均保持原版本。
10. 重启后闭环状态和 next action 不依赖内存、session 或对话。

### 7.2 测试分层

1. Schema/纯函数：loop record、stage reducer、checkpoint projection。
2. service/transform：语义名解析、父链、runtime attestation、context profiles。
3. 临时目录进程 E2E：使用 direct fake solver 串完整链。
4. 冻结真实证据：导入 Fig.4 Bundle 完成后半环。
5. 外部资格：网络恢复后真实 SProcess replay；SDevice 放到 Alpha-2。

任何 mock/fake 只能证明控制链，不能声明 Sentaurus 版本、许可证、deck 物理或科学模型合格。反过来，
真实 solver run 也不能替代 checkpoint/restart 的控制链测试。

## 8. Alpha-1 退出清单

以下条目必须同时满足，才能称为“alpha 科学闭环已跑通”：

- [ ] 活动 Fig.4 provenance diagnosis 已完成，claim 保持不允许。
- [ ] 权威 ledger/current checkpoint 已通过确定性命令更新和校验。
- [ ] `ScientificLoopRecord` 绑定同一 case/revision 的完整父链。
- [ ] 一条 process E2E 从 v2 reviewed package 连续运行到 checkpoint。
- [ ] runtime attestation 来自该次实际 collected manifest/output。
- [ ] scorer、diagnosis、knowledge/checkpoint 不依赖人工复制 Artifact 内容或 ID。
- [ ] 负结果/失败执行仍能闭环，且不会被解释成物理证据。
- [ ] restart/import 恢复到相同 verdict 和 next action。
- [ ] 全量测试通过，没有删除已有 review/approval/capability/immutable evidence 边界。
- [ ] 资格文档区分 CI 控制链、冻结真实证据和新真实 replay 三种证据等级。

## 9. 明确不做与决策边界

- 不在 Alpha-0/1 中继续拟合 Fig.4、暗电流或光学参数，也不接受新物理模型。
- 不为一次闭环建立通用工作流语言、通用 parser 平台或全量多案例 scheduler。
- 不因追求速度绕过独立 review、显式 capability、人工执行审批、不可变 Artifact 或 runtime gate。
- 不把网络、VM 或许可证暂时不可用误判为本地架构未完成；外部资格单独记录。
- 不让导入 Bundle 自动改写工作区；checkpoint 必须显式 preview/apply。
- 不在没有合格 capability 时猜测 TDR 二进制格式。
- 不用发布安全细节阻塞 Alpha-0/1；一旦发现会破坏证据身份、审批边界或工作区权威状态的问题，
  仍按 P0 立即处理。

## 10. 与上一版计划的关系

[新版本复审整改计划](TCAD_AGENT_REAUDIT_REMEDIATION_PLAN.zh-CN.md) 中已经完成的单位、claim 投影、
reviewed package v2、显式 capability、输入 Schema、运行时 gate、部署事务等成果继续保留。其未完成项
按以下方式重排：

- 直接进入本计划 P0：真实 runtime 串接、严格 diagnosis context、权威 checkpoint、纵向 E2E。
- 延后到 Alpha-2：生产二进制 TDR staging 和最小 SProcess→SDevice。
- 延后到 Beta：通用多案例 DAG、完整 parser/provider、wheelhouse、目标机故障矩阵和发布冻结。

上一版计划仍是工程 backlog 和历史决策依据；从本计划生效起，不再用其 B/C/D 全部完成作为 alpha
科学闭环的前置条件。

## 11. 执行记录

### 2026-08-08：A0-1 上下文与调度门槛

- 已新增 `scidiscovery.diagnosis.fig4-baseline-provenance.v1`，严格限定 15 个诊断输入：冻结目标、
  历史/候选 PLX、两侧 log/manifest、历史 deck、候选 project/review、metrics、residuals、diff 和
  evidence audit；不向 diagnostician 暴露本轮不需要的 TDR。
- 缺失输入、额外输入、错误 Schema 和错误 exposure 均有失败回归；现有 diagnostician 默认模式暂时
  保持兼容，避免本步骤无关的全局迁移。
- 已将真实 `fig4_baseline_provenance_20260806` Bundle 导入隔离 ResearchInstance 并实际创建任务；
  16 个 Artifact 成功绑定，任务状态为 `ready`，worker assignment 精确携带该 profile 和 15 个输入。
- 全量回归为 `325 passed`。
- 尚未生成 `LayeredDiagnosisReport`：科学内容必须由独立 diagnostician worker 产出，scheduler/root
  不得代写。因此 A0-1 的工程门槛已经完成，科学输出与其确定性校验是下一动作；在该输出完成前不将
  A0-1 标记为全部验收完成，也不开始 checkpoint 投影。
