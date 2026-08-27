# 科学操作契约与知识闭环整改实施交接

更新日期：2026-08-21

状态：核心整改已实施，部署前 hermetic 全量回归通过；尚未重装、重启或执行真实 Sentaurus
运行监督。

## 1. 交接目标

本轮整改不重写整个 SciDiscovery 引擎，而是在现有不可变 Artifact、任务上下文策略、
确定性 transform、人工审批和角色 Schema 之上，补齐一个最小但可执行的“科学操作契约核”。
它必须关闭当前已经复现的跨层绕过，并打通以下完整链路：

```text
approved evidence / parameters
  -> parameter uncertainty
  -> hypothesis and experiment design
  -> bounded revision
  -> materialized experiment plan
  -> reviewed implementation and execution
  -> deterministic scoring and strict diagnosis
  -> single-head knowledge update
```

本计划解决的不是单个校验器漏项，而是同一科学约束被分散表达后，各层可以分别“局部合法”、
组合起来却产生非法流程的问题。

## 2. 已确认的根因

当前协议意图同时散落在 scheduler 指令、角色提示、Schema validator、context policy、Root
入口门禁、readiness 和 transform 中。系统缺少一个机器可检查的操作级契约，因此存在以下
结构性问题：

1. **局部类型安全不等于流程类型安全。** 单个输入和输出可能都能通过 Schema，但没有一处
   统一声明某项有科学副作用的操作必须由哪些输入、父链、审批和上下文 profile 共同限定。
2. **任务别名承担了控制语义。** `source_name` 原本只是 worker 可见的任务局部科学别名，
   部分门禁却用它判断 current/type；更换别名即可绕过陈旧对象检查。
3. **`parent_refs` 混合三种关系。** 数据依赖、科学资格绑定和修订历史共用一个集合，导致
   structured revision 后的对象无法继续证明原始目标、假设和资格父链。
4. **横切能力被做成纵向特例。** 参数证据、参数不确定性和结构化修订分别可用，但组合后
   同时触发 Root 的完整参数组要求和 revision profile 的输入数上限，形成策略死锁。
5. **宽松默认 profile 可形成安全降级。** 严格 TCAD diagnosis profile 有完整输入约束，
   但默认 diagnostician profile 仍可生成能够影响科学主张的结果。
6. **审批仍偏向“对象成员检查”。** 除器件参数路径外，控制面没有统一证明一次科学审批
   覆盖了完整 extraction、附件、来源快照和独立 audit 的不可变闭包。
7. **知识状态不是当前控制模型中的一等对象。** transform 输出 kind、readiness 识别 kind
   和 topology 期望 kind 不一致，也没有单一 current head，历史状态可被再次分叉。
8. **current 检查和提交不是原子操作。** 任务创建、transform 注册、执行启动和知识迁移
   都可能在“检查 current”之后、“提交或外部副作用”之前遭遇 current 切换。
9. **测试集中于模块内正例。** 已有测试能证明局部实现工作，却没有覆盖 profile 降级、
   别名绕过、部分审批、伪造父链、陈旧知识分支和并发 current 切换。

## 3. 已复现缺陷基线

下表中的负例必须先转成失败测试；修复不能只依赖角色自觉遵守提示词。

| 优先级 | 缺陷 | 已观察行为 | 主要落点 |
|---|---|---|---|
| P0 | 默认 diagnosis 绕过严格上下文 | 无 runtime/control/package 父链的 metric 可经默认 profile 完成，且 claim evaluability 被接受 | `core_context_policies.py`、`interfaces/mcp_root.py`、`schema/layered_diagnosis.py` |
| P0 | 部分 scientific foundation 可审批 | 只有 foundation 本体、没有 extraction/附件/audit 的请求仍可进入 pending | `interfaces/mcp_root.py` |
| P0 | 空预测可推动假设状态 | `predictions_checked=[]` 仍可形成 decisive assessment 并把假设推进为 supported | `schema/validation.py`、`schema/layered_diagnosis.py`、`schema/knowledge.py` |
| P0 | critic 可漏审候选 | portfolio 含假设时，空 review rows 仍能通过部分路径 | `schema/cognitive.py` |
| P0 | current 可由别名绕过 | canonical alias 下的陈旧 objective 被拒绝，改为 `study_goal` 后任务可创建 | `interfaces/mcp_root.py` |
| P0 | 知识状态不可见且可分叉 | transform 生成 `knowledge_state_projection`，readiness/topology 查找 `knowledge_state`；没有 current knowledge head | `transforms.py`、`schema/research_cycle.py`、`scheduler_topology.py` |
| P1 | 修订后的 intent 无法物化 | apply 结果只直接指向 base 与 patch，materializer 要求 revised intent 直接拥有 objective/hypothesis/eligibility 父链 | `transforms.py`、`interfaces/mcp_root.py` |
| P1 | 参数感知修订形成策略死锁 | 不传参数组时 Root 拒绝；传完整组时 revision profile 超过 `max_inputs` | `interfaces/mcp_root.py`、`core_context_policies.py` |
| P1 | current 检查存在 TOCTOU | current 读取和任务/transform/执行提交不在同一比较并交换边界内 | `interfaces/mcp_root.py`、daemon/store 边界 |

相关聚焦测试此前均能通过，说明现有测试没有覆盖上述组合边界；“测试总数通过”不能作为这些
问题已关闭的证据。

## 4. 必须成立的四项系统不变量

1. 宽松 profile 只能产生 `advisory` 结果，不能建立科学主张、推进知识状态或授权外部执行。
2. current、审批和 lineage 判定只使用 Artifact 实际类型、不可变引用与操作契约；
   `source_name` 永远只是 worker 局部别名。
3. 受控修订必须保留可验证的语义 lineage；下游不要求 worker 复制父链，也不把任意祖先
   自动视为有效资格。
4. 知识状态必须是实例内单一 current head；每次迁移从精确 head 出发并原子替换，禁止从
   历史状态静默分叉。

## 5. 设计决策

### 5.1 最小 `ScientificOperationContract`

新增一个控制面拥有、启动时可静态检查的操作契约登记表。首轮只覆盖有科学或外部副作用的
高风险操作，不替换现有 `TaskContextPolicy`：后者继续负责 exposure、输入大小和输入数量，
前者负责“此操作是否有资格发生”。

建议字段：

```text
operation_key
allowed_roles
allowed_context_profiles
allowed_effects
required_inputs
output_schemas
lineage_policy
approval_policy
```

`allowed_effects` 至少区分：

- `advisory`
- `scientific_claim`
- `knowledge_transition`
- `external_execution`

首批登记操作：

| operation | 主要效果 | 核心资格 |
|---|---|---|
| `tcad_result_diagnosis` | scientific claim | 精确 plan、成功 runtime attestation、control equivalence、metric report、共同 reviewed package lineage；若检验假设则还需 portfolio |
| `candidate_eligibility` | scientific claim | 同一 portfolio 的 critic 与 evidence audit，必要时完整参数不确定性组 |
| `experiment_intent_revision` | advisory | 精确 revision base、change request、合法 patch producer；参数感知时绑定完整 approved parameter group 和 current uncertainty |
| `experiment_plan_materialization` | scientific claim | intent 的可验证语义 lineage，精确 objective/portfolio/eligibility，或明确的纯工程 intent |
| `scientific_foundation_approval` | scientific claim | 一个完整、不可变、已独立审计的 review bundle |
| `knowledge_update` | knowledge transition | 严格 diagnosis、精确 current knowledge head、有效预测映射和适用的 hypothesis assessment |
| `tcad_execution_start` | external execution | 精确 reviewed package、专用 execution approval、未变化的 current generation |

启动时执行契约一致性检查：

- 契约要求的输入必须被对应 context profile 接纳；
- profile 的 `min_inputs` 不得大于 `max_inputs`；
- 有 `scientific_claim`、`knowledge_transition` 或 `external_execution` 效果的操作不得绑定
  宽松默认 profile；
- 输出 Schema 与允许的效果必须相容；
- 缺少 lineage 或 approval policy 的有副作用操作使服务启动失败，而不是运行时降级。

### 5.2 语义 lineage resolver

不要把所有祖先都自动提升为资格，也不要要求修订结果复制原对象全部父引用。新增一个只理解
控制面生成边的 resolver：

```text
revised object
  -> deterministic structured-revision apply
  -> exact base object + exact patch
  -> base object's qualified semantic inputs
```

resolver 必须验证：

- patch 来自契约允许且已完成的角色任务；
- patch 直接针对所声明的 base；
- revised object 与 diff 来自同一次 deterministic apply；
- 参数感知修订使用的是当时精确 current uncertainty；
- 只有契约列出的受控边可以穿透，普通 parent 不能伪造语义祖先。

experiment plan materialization、candidate eligibility、package 和后续资格检查共用这一实现，
避免各入口重新发明父链规则。

### 5.3 完整科学审批束

把 scientific foundation 的资格从“某 Artifact 出现在一次已批准请求中”提升为控制面拥有的
不可变 review bundle。bundle 至少绑定：

- final scientific foundation；
- final extraction primary；
- `task_outputs` 返回的全部附件；
- 全部冻结来源快照；
- deterministic coverage/validation report；
- final independent evidence audit。

器件参数路径现有的 exact-set 检查迁移到同一通用机制。旧的 foundation-only 审批记录保留
历史可见性，但不再为新任务提供 scientific qualification。

### 5.4 current generation 与 CAS

为每个实例增加控制面内部、单调递增的 selection generation。该值不进入 worker assignment，
也不成为 scheduler 需要管理的标识。

以下敏感操作在开始时读取 generation，在提交、注册或触发副作用前比较并交换：

- effectful task schedule；
- deterministic transform 注册；
- approval/execution request 的资格冻结；
- `execution_start`；
- knowledge transition。

如果中途 current 发生变化，操作失败并要求调用方重新读取 readiness；不得把旧检查结果提交到
新 current 上下文。

### 5.5 单头知识状态

- 新对象统一使用 `knowledge_state` kind；
- `knowledge_state_projection` 只作为旧记录读取兼容，不再生成；
- readiness 从 current knowledge 投影 contradiction、next task mode、hypothesis state 和
  parameter state；
- 没有知识状态时，只允许精确初始 portfolio 初始化一次；
- 后续 update 必须直接消费精确 current head；
- transform 注册新状态并以 CAS 原子替换 head；
- 缺失、歧义或历史 head 一律 fail closed。

## 6. 实施顺序

### P0：先锁定失败基线

先增加会在当前代码上失败的公共生命周期测试，不修改生产逻辑：

1. 默认 diagnosis 不得建立 claim 或触发 knowledge update；
2. 缺少 runtime/control/package lineage 的 metric 不得完成严格 diagnosis；
3. foundation-only 审批不得取得资格；
4. 空 `predictions_checked` 不得产生支持/反驳结论；
5. portfolio 存在候选时空 critic review 必须拒绝；
6. 陈旧 objective 无论使用何种 `source_name` 都必须拒绝；
7. revised intent 能经受控 lineage 被 materialize；
8. 参数感知 revision 能绑定完整参数上下文并完成 apply；
9. 新 knowledge state 能出现在 readiness 中；
10. 从历史 knowledge state 更新必须拒绝；
11. current 在检查与提交之间切换时，敏感操作必须 CAS 失败。

验收：每个已复现缺陷都有一个直接负例，失败原因指向预期控制边界，而非偶然 Schema 错误。

### P1：引入操作契约核

- 建立 contract 数据结构、登记表和启动一致性检查；
- 给 Root 高风险入口分配 `operation_key`；
- 保留现有 context policy 的资源约束职责；
- 默认 profile 显式标记为 `advisory`；
- 先只迁移第 5.1 节的七项操作，避免无边界大重构。

验收：删除或弱化任一必需 profile 输入时，静态检查或契约测试立即失败；不能退回默认 profile。

### P2：关闭 diagnosis、prediction、critic 和 approval 边界

- 默认 diagnostician 只能返回 advisory/fail/inconclusive/revise；
- `claim_allowed=true` 或 `knowledge_update_applicability=required` 必须来自严格操作契约；
- 提取一个公共 TCAD study exact-lineage predicate，供 scheduling、readiness 和 knowledge
  update 共同使用；
- plan 中每个科学假设至少对应一个预注册 prediction；
- `supports`、`contradicts`、`inconclusive` assessment 至少检查一个属于该假设且出现在精确
  plan 中的 prediction；只有 `invalid`/`not_tested` 可为空；
- critic 对 portfolio hypothesis key 做无条件集合相等检查，再按是否存在 uncertainty 检查
  参数矩阵；
- 建立完整 scientific review bundle，统一 approval qualification。

验收：默认 profile、空预测、空 critic、部分审批和孤立 metric 的全部负例通过；严格正例不回归。

### P3：移除别名控制语义并加入 CAS

- `source_name` 只保留在 assignment 和科学证据引用中；
- current 检查改用 Artifact envelope kind、Schema、input usage 与 operation contract；
- `claim_evidence` 和 operational 输入必须 current；`revision_base`、`prior_signal` 可明确读取历史；
- 增加内部 selection generation 和事务/CAS API；
- task schedule、transform、execution request/start、knowledge update 接入同一 API。

验收：更换别名不能改变资格；并发切换 current 时不产生任务、Artifact 或外部执行副作用。

### P4：打通 revision 与参数上下文

- 实现第 5.2 节的受控 lineage resolver；
- experiment plan materializer 和后续资格检查改用 resolver；
- 扩展参数感知 experiment-design revision profile，使其接收完整 approved parameter group、
  `parameter_uncertainty`、revision base 和 change request；
- 调整 `max_inputs` 和总字节上限到该完整上下文的实测值，不使用无限上限；
- structured apply 只读取 base、patch 和必要 uncertainty；其他参数对象作为资格上下文，
  不由 transform 重写；
- 增加纵向测试：approved parameters → uncertainty → intent → bounded revision → apply →
  materialized plan。

验收：修订对象保持原始科学语义父链，参数组既不能缺失，也不会因 profile 自相矛盾被拒绝。

### P5：完成知识闭环

- 统一新旧 kind 映射并停止生成旧 kind；
- 把 knowledge current head 纳入实例选择模型；
- readiness 只从 current head 派生知识能力；
- knowledge transform 使用严格 diagnosis 和 exact planned prediction；
- 注册与 head 切换处于同一事务/CAS；
- 明确初始化、正常更新、无适用评估和冲突失败四条路径。

验收：知识状态在 readiness 可见；连续更新形成单链；历史分叉、空评估和 profile 降级均失败。

### P6：协议级回归与兼容迁移

建立两条完整控制面 E2E：

1. **无参数科学流程**：foundation bundle → portfolio → critic/audit → eligibility → intent →
   plan → reviewed package → execution → score → strict diagnosis → knowledge update。
2. **参数感知修订流程**：parameter extraction/coverage/audit/approval → uncertainty → portfolio →
   intent → bounded revision → materialization → 后续严格链路。

每条 E2E 至少增加以下对抗变体：别名替换、陈旧 current、profile 降级、部分审批、伪造
parentage、空 prediction/review、陈旧 knowledge head、并发 current 切换。

验收：聚焦负例、两条 E2E、并发/CAS 测试和完整现有测试集全部通过。

## 7. 预计代码落点

以下是实现导航，不表示必须按文件机械拆分：

| 责任 | 预计文件/模块 |
|---|---|
| 操作契约定义与静态检查 | 新增 `artifact_agent/scientific_operation_contracts.py`，或放入一个职责单一的现有 control-policy 模块 |
| context profile 资源边界 | `src/scidiscovery/artifact_agent/core_context_policies.py` |
| Root 入口、current、审批、transform、执行门禁 | `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` |
| diagnosis 资格和预测完整性 | `src/scidiscovery/artifact_agent/schema/layered_diagnosis.py`、`schema/validation.py` |
| critic 集合完整性 | `src/scidiscovery/artifact_agent/schema/cognitive.py` |
| knowledge kind、迁移和 reducer | `src/scidiscovery/artifact_agent/schema/knowledge.py`、`schema/research_cycle.py`、`transforms.py` |
| readiness/topology | `src/scidiscovery/scheduler_topology.py` 及 readiness 投影实现 |
| selection generation 持久化 | 实例 store/SQLite migration 与 daemon 事务边界 |
| 协议和对抗测试 | `tests/artifact_agent/` 下现有对应测试模块及新增纵向测试模块 |

不要先改角色提示词来“修复”控制面漏洞。提示词只在机器契约完成后同步行为说明。

## 8. 数据迁移与兼容策略

- 不删除、不原地改写历史 Artifact、审批或 parent refs；
- 旧 `knowledge_state_projection` 可读取并映射为 legacy knowledge view，但新 transform 只生成
  `knowledge_state`；
- 旧 foundation-only approval 保留审计可见性，但 readiness 将其标为
  `human_review_required`，不能直接 qualify 新工作；
- 旧默认-profile pass diagnosis 保留记录，但不得建立 claim 或驱动新 knowledge update，
  必要时投影为 `revision_required`/不可评估；
- lineage resolver 解释受控 revision 边，不批量复制或重写历史 `parent_refs`；
- SQLite 增加 selection generation 时提供显式 migration，现有实例从确定的初始 generation
  开始；
- 迁移期间任何无法唯一识别 complete bundle、current head 或严格 lineage 的对象均 fail
  closed，不猜测绑定关系。

## 9. 风险控制

| 风险 | 控制方式 |
|---|---|
| 契约核演变成第二套工作流引擎 | 只描述高风险操作的资格和效果；拓扑选择仍由 scheduler/readiness 完成 |
| lineage resolver 过度追溯并误授信 | 只穿透控制面已知的 deterministic revision edge，使用 allowlist |
| CAS 只防写入、不防外部副作用 | `execution_start` 必须在 adapter 调用前完成最终 CAS/事务占位 |
| 完整审批束导致旧任务全部停摆 | 保留历史读取，明确要求重新组成 review bundle，不静默继承资格 |
| 参数 profile 再次超限 | 用真实完整上下文测量输入数与字节，建立边界测试后再设上限 |
| 修复打断工程型无假设任务 | 契约明确区分 scientific intent 与纯 engineering intent；后者不伪造 objective/hypothesis 输入 |

## 10. 明确不在本轮范围内

- 不重写整个 scheduler 或引入固定阶段图；
- 不重构 Artifact 存储/CAS 为全新数据库；
- 不改变 TCAD 物理模型、solver adapter 或评分算法；
- 不做大规模 UI 重设计；若完整 review bundle 需要展示，只增加必要的分组、状态和来源链接；
- 不以增加角色提示词代替控制面强制；
- 不重新处理与本轮契约无关的历史科学结果。

## 11. 完成标准

只有同时满足以下条件，才能把本计划标记为完成：

- 第 3 节每个已复现问题都有自动化负例且已通过；
- 默认 diagnosis 不能建立科学 claim 或推进 knowledge；
- 不完整 scientific approval 不能提供资格；
- 别名替换和并发 current 切换不能绕过门禁；
- 参数感知 intent revision 能完整 materialize；
- knowledge state 在 readiness 可见、单头、不可从历史分叉；
- 两条协议级 E2E 与 CAS 并发测试通过；
- 完整现有测试集通过；
- 行为不依赖 worker 自愿遵守提示词；
- 迁移测试证明旧记录可读但不会被静默授予新资格。

## 12. 建议的提交顺序

为便于审查和回退，按下列独立提交推进：

1. 仅加入复现测试；
2. 操作契约核与静态一致性检查；
3. diagnosis/critic/prediction/approval 边界；
4. Artifact 类型判定、selection generation 与 CAS；
5. revision lineage resolver 和参数感知 profile；
6. knowledge kind、single-head 与 readiness；
7. E2E、迁移兼容、文档和部署资格。

在第 7 步全部通过前，不进行重装或重启；本轮交接也没有授权部署。

## 13. 接手后的第一步

从第 3 节的九类缺陷建立测试矩阵，优先提交“当前代码必然失败”的 P0 测试。随后实现
`ScientificOperationContract` 的最小登记表，并只接入 `tcad_result_diagnosis`，验证
“默认 profile 只能 advisory”这一安全闭包。该纵向薄片通过后，再逐项迁移其他六类操作，
不要一开始同时重构全部 Root 入口。

## 14. 2026-08-21 实施记录

本节记录本计划实施后的实际状态。前述第 1—13 节继续保留为设计依据和回归边界。

### 14.1 已完成的控制面修改

- 新增 `scientific_operation_contracts.py`，登记首批七类高风险操作，启动时校验 effect、
  lineage、approval policy、严格 worker context profile 的必需输入和输入上限；默认 diagnosis
  仅允许 advisory，严格 TCAD profile 才能建立 scientific claim。
- diagnosis 现在强制绑定精确 experiment plan、成功 runtime attestation、control equivalence 和
  complete-plan metric report；校验顺序保留具体 objective、prediction、parameter 和 metric
  错误的可诊断性，但缺少 TCAD gate 最终仍 fail closed。
- decisive hypothesis assessment 禁止空 `predictions_checked`；critic review 必须与精确
  hypothesis portfolio 做无条件 key 集合相等检查。
- current 判定改用 Artifact kind/schema/usage，不再依赖 worker 局部 `source_name`；历史用途
  `revision_base`、`change_request` 和 `prior_signal` 保留显式只读语义。
- scientific foundation 审批创建和后续资格判定都重新验证同一个完整不可变 bundle：intake、
  foundation、原始来源、全部提取附件/冻结来源以及独立 audit 必须同时被审计和批准。历史
  foundation-only/intake-only 决策仍可查看，但不再授予新任务资格。
- 参数感知 experiment-design revision profile 允许完整 approved parameter group、current
  uncertainty、revision base 和 change request；deterministic structured revision resolver 只穿透
  经重新执行验证的 apply edge，修订后的 intent 可继续 materialize。
- knowledge transform 只生成 `knowledge_state` kind，并自动选择为单一 current head；后续更新
  必须消费精确 current head，历史 head 分叉被拒绝。旧 `knowledge_state_projection` 以
  `revision_required` 只读视图出现在 readiness 中，不能自动成为 current。
- selection generation 已持久化。current 切换和任务、transform、科学审批、execution request、
  `execution_start` 的最终提交通过跨进程 selection guard 互斥；guard 内再次校验 generation，
  进程异常退出时锁由内核释放。

### 14.2 已增加或强化的回归边界

- 默认 diagnosis 降级、孤立 metric、缺 runtime/control、空 prediction、空 critic、别名替换、
  部分审批、历史审批静默授信、伪造 revision parentage、参数 revision profile 死锁、陈旧
  knowledge head 和 current 并发切换均有直接负例。
- 完整 foundation bundle 在 UI 决策前保持 pending，决策后才进入 qualified；漏掉原始来源、
  attachment、audit 或精确 audit usage 均拒绝。
- 参数感知纵向路径覆盖 approved parameter group → uncertainty → intent revision →
  deterministic apply → experiment plan materialization。
- 执行侧保留 hermetic shell-runner 生命周期 E2E；严格 TCAD diagnosis、知识迁移与执行边界由
  精确 lineage/contract 测试覆盖。真实 Sentaurus 求解不属于本次未授权的部署前测试。

### 14.3 验证结果与部署边界

- `pytest -q`：`832 passed`；耗时约 108 s。
- 仅有 6 条既有 `remote_runner_py36.py` 中 `datetime.utcnow()` 的弃用警告，无测试失败。
- `python -m compileall -q src/scidiscovery/artifact_agent tests/artifact_agent`：通过。
- `git diff --check`：通过。
- 当前环境未安装 Black，因此没有声称执行 Black 检查。
- 本轮没有执行 `deploy/reinstall.sh`、systemd 重启、数据库删除或历史 Artifact 重写。部署后仍应
  运行一次真实 UI 审批、current 切换和授权执行冒烟测试；旧的部分审批需要重新组成完整 bundle，
  旧 knowledge projection 需要通过新 deterministic update 路径重新投影。
