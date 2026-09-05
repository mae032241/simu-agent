# R3 总体独立审查

审查日期：2026-08-28  
审查对象：`baseline/8765-codex@404aeb1` 叠加当前 R0—R3 工作树  
审查性质：未参与实现的跨边界、简化性与 33 项约束只读审查  
最终结论：**第二轮复审通过，允许进入 R4-A**

## 一、结论先行

R3 已经完成了最重要的软件收敛骨架：默认安装态只有一个编译目录，三种 scope 是同一
`CompiledCatalog` 的投影；核心 wheel 实测为 `public=15 / support=13 / internal=0 /
all=28`；显式架构夹具才增加三个 internal operation；support 编译规则没有误杀 public
transform；通用 Agent、deterministic transform、Root 调用、Task、Worker、Artifact 与 Codex
生成配置大体都从同一份 operation 摘要派生。49 项首轮聚焦、修复后的 52 项聚焦和首轮
全仓 162 项均通过。

但当前实现尚不能证明 `OperationSpec` 是完整的行为闭包。存在三项可达的功能阻断和一项
冻结复杂度完成门违约：

1. `ReviewSpec` 只参与编译和目录展示，正式输入准入不验证独立审查是否闭合；
2. producer 的 `explore`/internal 后果和下游用途上限没有统一投影到 Agent 产物，未来插件可把
   非权威产物重新声明为 `claim_evidence`；
3. structured revision 仍按核心 schema 名称和五项 Literal 目标二次授权，新领域无法只靠插件
   注册受控修订；
4. 当前 `spec/catalog/invoke = 341/454/410`，合计 `1205`，同时超过冻结的 `spec<=320`、
   `catalog<=450` 和总量 `<=1200` 完成门，实施记录中的旧数值已经失真。

本轮发现的 operation 来源 schema 白名单双权威已开始按 `OutputPortSpec.evidence_paths` 修复，
Operation 任务不再进入 legacy schema switch；方向正确，但 collection、未知来源类型和
`TaskOutputSpec` 冻结仍未闭合，详见 2.3。以上问题必须在同一 R3 返工中关闭并重新独立复审，
不能转移到 R4 再由 TCAD 插件补硬编码。

## 二、按影响排序的发现

### P0-1：独立审查关系没有进入运行时准入，科学质量门可直接绕过

**合同与证据**

- `operations/spec.py:191-198` 声明 `ReviewSpec`；
- `operations/catalog.py:323-395` 只验证 reviewer 存在、不同 Agent、端口兼容和无环；
- `operations/spec.py:287-320` 只把 `requires_independent_review` 投影给 scheduler；
- 全仓对 `reviewer_operation`、`subject_outputs` 的生产引用止于上述编译/投影代码，没有
  operation admission 消费者；
- `artifact_agent/interfaces/mcp_root.py:2581-2619` 的正式输入准入只检查
  `scientific_claim_admissible=false`、失败 runtime attestation 和非资格 handoff，不检查 exact
  reviewer operation、被审 parent 或 review verdict；
- `artifact_agent/service/tasks.py:6249-6258` 的 Agent 产物标签只有 operation id/version/digest/
  authority digest，没有“待审”或 review closure；
- `general_science_plugin.py:1022-1026` 明确要求 `science.evidence.extract.v1` 由
  `science.evidence.audit.intake.v1` 审查，但该声明对运行时没有约束力。

**可达场景**

`science.evidence.extract.v1` 完成后，调度者可以不调用 intake audit，直接把输出传入
`science.intake.split.v1`。该 support Operation 在
`general_transform_operations.py:493-523` 只绑定 intake，本身没有审查输入或 guard；所得
foundation 随后能以 `claim_evidence` 进入 `science.objective.project.v1`，因为原 Agent 输出未
被标为 nonqualifying。于是“extract → audit → 正式科学链”在控制层实际退化成了提示词约定。

同样，`science.experiment.design.v1 → science.experiment.materialize.v1` 生成的完整计划没有
任何通用准入事实要求 `science.object.review.v1`；R4 若直接给 TCAD author 增加另一个手写门，
就会重建本次重构要删除的纵向特判。

**违反的冻结约束**

- 总体计划 5.5：Agent 新证据、主张、实验设计或解释在升格前必须闭合独立审查；
- 总体计划 20.3、21.2：只有 spec 显式开启审查检查，下游正式用途要求 exact reviewer Artifact；
- 33 项 `AUTH-003`：review、qualification、admission 必须共同消费同一 operation contract；
- 多角色科学责任：“产出者—独立审查者”不能只存在于 scheduler prose。

**最小修复与完成证据**

不要新增 review 数据库、资格状态机或第二 registry。应在同一 compiled contract 中声明正式
consumer 的 subject port、review Artifact port、reviewer operation 和允许 verdict，复用现有
Artifact labels、exact parent refs 与一次 preflight 验证。至少增加两个真实 Root 负例：

1. extract 后未绑定 audit，正式 foundation/objective 输入失败；绑定审查另一 revision 仍失败；
2. materialized experiment 未绑定 exact object review，TCAD/正式执行前置输入失败；exact review
   通过后才成功。

### P0-2：`explore` 与 producer 用途上限只在 Transform 路径生效，Agent/internal 产物可被提升

**合同与证据**

- `operations/invoke.py:236-247` 只在 `CompiledTransformAdapter` 计算 explore 或非
  `claim_evidence` 输入；
- `artifact_agent/interfaces/mcp_root.py:1318-1329,1432-1439` 只给 transform 的非资格派生输出
  加 `scientific_claim_admissible=false`；
- Agent 完成路径的 `_operation_labels()`（`tasks.py:6249-6258`）不投影
  `spec.consequence`；
- `OutputPortSpec` 没有 `allowed_input_usages` 或等价 producer 上限；Root 只相信未来 consumer
  自己声明的 `InputPortSpec.usage`；
- 显式架构夹具的 `builtin.test.agent` 是 `internal + explore`，而
  `builtin.test.transform` 甚至是 `internal + scientific`
  （`builtin_plugin.py:401-470`）。虽然它们不在默认 wheel 中，但这准确暴露了同一合同缺口。

**可达场景**

任何新领域插件都可以注册一个 `explore` Agent，得到未带 nonqualifying 标签的 Artifact；另一个
public Operation 再把相同 schema 的输入声明为 `claim_evidence`，当前 preflight 会接受。显式
安装 architecture fixture 时，内部测试输出也可由另一个插件以同样方式消费。scope 本来就不是
第二权限系统，因此不能靠“internal 默认不展示”防止 claim 提升；必须由同一 producer/consumer
合同闭合用途。

这违反 `AUTH-003:110-124` 对 producer `allowed_input_usages` 的明确要求，以及计划中“explore
结果不能直接支持 claim、internal 不得形成 claim-admissible 产物”的定义。

**最小修复与完成证据**

在输出端口声明并摘要绑定允许的下游 usage，或至少将 `consequence=explore` 编译为统一的
producer 上限；Agent、Transform 和 internal 使用同一个 Artifact-use gate。增加组合插件负例：
explore/internal 输出作为 `claim_evidence` 必须失败，作为允许的 `prior_signal`/
`evidence_inventory` 可以成功；public scientific transform 不应被误禁。

### P1-1：structured revision 仍由 core schema 白名单授权，新领域必须修改核心

**证据**

- `artifact_agent/schema/structured_revision.py:12-18` 的 `RevisionTargetSchema` 是五个核心
  schema 的 Literal；
- `artifact_agent/schema/task.py:44-49` 让 `TaskRevisionSpec.target_schema` 依赖该 Literal；
- `artifact_agent/schema/task.py:76-93` 通过输出 schema id
  `scidiscovery.structured-revision.v1` 反推 revision 是否开启；
- `operations/catalog.py:212-225` 重复同一 schema-id 等价判断；
- `operations/invoke.py:193-206` 虽从 OutputPortSpec 派生 revision，最终仍被上述 core Literal
  限制。

**可达场景**

新领域插件声明 `domain.sample.v1` 对象、受限 JSON Pointer 和 revision Agent 时，编译会在构造
`TaskRevisionSpec(target_schema="domain.sample.v1")` 失败。插件只能修改核心 Literal，或放弃
现有受控 patch/apply 生命周期，恰好重现“安装一个领域插件仍要改 core schema/TaskService”的
问题。

**最小修复**

`TaskRevisionSpec.target_schema` 使用普通受限 schema identifier；revision 启用只由
OutputPortSpec 的显式 revision contract 决定，不再由 output schema id 推断。目标对象解析、
验证和 apply 使用该 Operation 可达的 codec/validator 组件；不建立一个新的全局 revision target
registry。增加一个测试域 schema 的编译、Worker patch 校验、确定性 apply 成功与越界失败用例，
且不修改任何 core Literal。

### P1-2：新的 evidence-path 修复仍未覆盖完整输出边界

原实现的 `tasks.py:5653-5691` schema switch 确实是 AUTH-003/ROLE-001 所禁止的双权威。当前
工作树已在 `OutputPortSpec` 增加摘要绑定的 `evidence_paths`，并让 Operation 任务优先走该
合同（`tasks.py:5670-5704`），legacy schema switch 只留给非 Operation 桥。这个方向应保留。

但当前仍有三处缺口：

1. `evidence_paths` 位于每一个 OutputPortSpec，TaskService 却只取
   `operation_primary_output(compiled)`（`tasks.py:5674-5678`）；collection 端口声明的来源路径会
   被静默忽略，编译器也未拒绝该声明；
2. `tasks.py:5751-5805` 对未知 `source_type` 只要是字符串就静默接受；领域 schema 可声明
   `bare_url` 等类型绕过冻结。应明确绑定策略：`web_snapshot` 必须匹配本 attempt 冻结快照，
   `frozen_input/user_statement/runtime_output` 必须匹配 task-local 输入，`inference` 等非来源类型
   必须被显式列为不绑定；未知类型失败关闭；
3. `evidence_paths` 没有固化进 `TaskOutputSpec`，运行时通过 task authority 回查当前 catalog。
   这虽有 operation digest 保护，但不满足 `ROLE-001` 的字面冻结要求，也使卸载后的历史任务校验
   依赖目录仍存在。应投影进 TaskOutputSpec，或给出等价的不可变合同快照与卸载恢复证明。

修复字段已使 `OPERATION_ABI_VERSION` 升到 4，因此旧 ABI3 的真实 Agent 运行不再证明当前摘要。
稳定后至少重跑一个真实 Agent 文件闭环，并实际证明带 evidence 的 frozen input/web snapshot
成功与未冻结来源失败。

### P2-1：复杂度预算和实施记录均已失真

独立实测：

| 文件 | 冻结分项上限 | 当前 |
| --- | ---: | ---: |
| `operations/spec.py` | 320 | 341 |
| `operations/catalog.py` | 450 | 454 |
| `operations/invoke.py` | 430 | 410 |
| 合计 | 1200 | 1205 |

总体计划 17 节明确写明分项预算不得再次挪用，超过上限须先证明不能通过复用或删除兼容分支
解决；实施记录仍写旧的 `319/449/428` 或 `331/449/410`。R3 的目标是轻控制面，这不是纯文档
瑕疵。应在上述修复中抽取/删除重复逻辑，使三个文件同时回到冻结门内，并更新实测值；如果确有
不可删除的最小新增，必须由计划先给出可审计理由，而不是默许预算漂移。

## 三、已通过的边界

以下判断在本轮返工中不得退化：

1. 默认 installed catalog 实测 `public=15 / support=13 / internal=0 / all=28`；
2. `pyproject.toml:26-28` 只有 `CORE_PLUGIN` 和 `general_science` 两个生产入口；CORE_PLUGIN 本身
   零 operation，显式 architecture fixture 才包含三个 `builtin.test.*`；
3. 28 个生产 operation 在默认/测试组合中的定义和摘要不因测试插件相互覆盖；测试 operation
   未进入默认 Codex/MCP/ready/UI 生产安装路径；
4. `catalog_scope` 属于同一 OperationSpec 和摘要，Root 目录与 readiness 只是同一 catalog 的
   过滤投影，没有第二 scope registry 或 scope 权限表；
5. support 编译约束正确拒绝 Agent、Effect 和 review，并没有禁止 public transform；
6. `operation_preflight` 与 `operation_invoke` 共享 exact 编译对象；Agent 任务权限、Worker 工具、
   原生工具策略、网络、上下文、输出 schema/validator 和 Artifact 标签均与摘要绑定；
7. 已迁移通用 transform 的 legacy `artifact_transform` 旁路继续失败关闭；
8. Worker 仍拥有科学内容，控制层只做结构、来源、谱系、权限、审查/审批和生命周期机械门，
   readiness 没有恢复固定科研 DAG；
9. R2 的 `inherited_prototype` 边界仍被诚实标为提示级最小权限原型，未伪称平台硬隔离。

## 四、R4 前允许保留的非阻塞迁移债务

在上述阻断关闭后，下列债务可诚实留到 R4，不应被本报告误写成已完成：

- `evidence_extractor + device-parameter-evidence` 和专用
  `device_parameter_evidence_auditor` 两个设备参数桥；
- `tcad_deck_author`、`tcad_deck_reviewer` 两个 TCAD legacy role；
- 文档列出的精确 domain-only TCAD/curve `artifact_transform` profiles；
- TCAD author/reviewer/materialize/package/effect/score 的插件单入口迁移；
- compiled `ApprovalContract.projector` 驱动领域 UI，而不是现有领域 renderer 特判；
- checked-in `.codex` 旧快照和 R2 worker-process 加固代码，但受支持安装必须继续从同一 catalog
  重新生成并验证；
- R5 对 legacy role/context/profile 表、旧 callable facade 和总代码量的最终净删除。

这些桥目前有精确角色/上下文/profile 边界，未发现已迁移 generic operation 可通过它们恢复第二
创建权威；因此它们本身不阻断 R4。真正阻断 R4 的是上文三项通用合同缺口：如果带着它们迁移
TCAD，R4 只能再次用领域 guard/白名单缝补。

## 五、独立执行证据

| 检查 | 结果 |
| --- | --- |
| 首轮聚焦 catalog/general science/transform | `49 passed in 29.81s` |
| evidence-path 修复后同组聚焦 | `52 passed in 28.33s` |
| 首轮完整 `pytest -q` | `162 passed in 55.33s` |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| 默认 installed catalog | `15 / 13 / 0 / 28` |

自动化全绿不能覆盖本报告的三条语义旁路：现有 reviewer 测试只证明 producer 指向兼容 reviewer
并保留父链，没有测试“未审正式消费必须拒绝”；现有 provisional 测试集中于 transform 传播，
没有组合 explore Agent producer 与 claim consumer；revision 测试只覆盖五个已写入核心 Literal
的对象。ABI4 修复稳定后必须重跑全仓及新的负例，且由于 operation digest 已变化，需要一份当前
摘要的真实 Agent 运行证据。

## 六、首轮裁定（历史记录）

以下裁定记录 2026-08-28 首轮审查当时的工作树，已经由第七节的第二轮结论取代。

**打回，不允许进入 R4-A。**

返工只能复用现有 OperationSpec、compiled catalog、Artifact parent/labels、TaskOutputSpec 和统一
preflight；不得为 review、output usage、evidence binding 或 revision 新建数据库表、第二注册表、
角色/schema/profile 白名单或领域 scheduler 分支。四项完成门全部关闭、当前 ABI 的回归和真实
Agent 证据通过后，再由本独立审查者复审并决定是否写出“通过，允许进入 R4-A”。

## 七、第二轮独立复审（2026-08-29）

### 7.1 结论

首轮列出的 P0、P1 和 P2 阻塞已经在 R3 内关闭。本轮没有发现阻塞 R4-A 的双权威、通用
旁路或复杂度完成门违约。

**通过，允许进入 R4-A。**

该结论只授权按已冻结计划开始 R4-A 的 TCAD 插件注册入口迁移，不代表 R4-B—R4-D、真实
外部求解执行、生产级 Worker 硬隔离、完整 TCAD 闭环或第二领域扩展性已经完成。

### 7.2 首轮阻塞关闭核验

| 首轮发现 | 当前实现与可达行为 | 第二轮判断 |
| --- | --- | --- |
| P0-1 `ReviewSpec` 只编译、不准入 | `ReviewSpec.accepted_verdicts` 默认仅接受 `pass`，并随 `reviewer_operation`、`reviewer_input_port` 和 `subject_outputs` 进入摘要（`operations/spec.py:179-183`）；Agent 任务输出冻结同一审查合同（`operations/invoke.py:168-231`、`artifact_agent/schema/task.py:155-164`）；Root 的统一生产者准入同时核对 exact reviewer operation、exact reviewer input port、exact subject ref 和允许结论（`artifact_agent/interfaces/mcp_root.py:2610-2646`），TaskService 从已完成 reviewer 任务及其 scheduler signal 验证这些事实（`artifact_agent/service/tasks.py:5838-5862`）。`revise` 等未接受结论的负例以及 TCAD author 缺少 exact plan review 的负例均已加入并通过。 | 已关闭；审查是 OperationSpec 输出合同的一部分，不是第二资格系统。 |
| P0-2 producer 用途可被 consumer 重新声明 | 每个 `OutputPortSpec` 必须显式声明非空 `allowed_input_usages`（`operations/spec.py:83-109`），该值进入摘要和不可变 Task 输出合同（`operations/invoke.py:188-231`）；编译器拒绝 explore/internal 输出支持 `claim_evidence`（`operations/catalog.py:223-227`）；Root 对 Operation 调用与暂留 legacy `task_schedule` 共同调用 `_validate_producer_output_admission`（`artifact_agent/interfaces/mcp_root.py:1573-1579,2583-2646`）。receipt、revision diff、review 和机械报告已按最小用途收窄，伪装成 claim evidence 的组合负例通过。 | 已关闭；scope 仍只是规划视图，用途准入来自同一输出合同。 |
| P1-1 structured revision 依赖核心 schema 白名单 | `TaskRevisionSpec` 以普通 schema identifier 冻结 `target_schema`、`patch_codec`、`target_codec` 和受限 JSON Pointer（`artifact_agent/schema/task.py:44-68`）；编译器直接从 revision output/base port 的已注册 codec 构造并验证合同（`operations/catalog.py:206-222`），调用器将其冻结进 Task（`operations/invoke.py:205-231`）。核心不再按 `StructuredRevision` schema 名或固定目标 Literal 推断授权。 | 已关闭；新领域的受控修订不要求修改核心 schema 枚举。 |
| P1-2 evidence path 未完整冻结 | `evidence_paths` 是输出端口摘要字段且进入 Task 输出快照（`operations/spec.py:83-109`、`operations/invoke.py:221-231`）；集合端口声明 evidence path 在编译期失败（`operations/catalog.py:200-205`）；Operation 任务只按快照 JSON Pointer 查找来源（`artifact_agent/service/tasks.py:5661-5685`），未知 `source_type` 失败关闭。真实 frozen input 成功、伪造/未知来源失败的测试均通过；legacy schema 白名单只保留给非 Operation 桥。 | 已关闭；Operation 来源校验没有回查 schema-name 注册表。 |
| P2-1 三个核心文件超预算 | 独立实测 `spec.py=320`、`catalog.py=450`、`invoke.py=430`，合计 `1200`，分别和总体计划冻结上限相等。 | 已关闭；没有挪用分项预算。 |

本轮还额外检查了一个首轮修复后暴露的跨边界问题：Operation 产物如果进入暂留 legacy
`task_schedule`，不能绕开 producer usage/review 合同。当前两条创建路径已经共用上述同一
准入函数。TCAD 的 `experiment_review` 只是可选、`handoff_only` 的 exact witness 端口
（`plugins/tcad_artifact/tcad_artifact/context_policies.py:10-17`）；当 `experiment_plan` 来自正式
Operation 时，Root 仍强制绑定其 exact pass review。未审计划被拒绝，绑定另一个对象或拒绝
结论也不能满足门禁；这没有形成 TCAD 专用审查权威。

### 7.3 单一目录、三种视图与安装态核验

独立从源码编译默认生产组合和显式架构夹具，结果如下：

| 编译组合 | public | support | internal | all |
| --- | ---: | ---: | ---: | ---: |
| 默认生产：`CORE_PLUGIN + general_science` | 15 | 13 | 0 | 28 |
| 显式架构测试夹具 | 15 | 13 | 3 | 31 |

`CORE_PLUGIN.operations` 为 0，`ARCHITECTURE_TEST_PLUGIN.operations` 为 3；新增项仅为
`builtin.test.agent`、`builtin.test.effect`、`builtin.test.transform`。显式夹具组合中的 28 个
生产 operation id 与 digest 和默认组合逐一相同。`CORE_PLUGIN` 与测试夹具的拆分见
`builtin_plugin.py:279-295,515-540`，安装态入口测试覆盖默认 wheel、显式 fixture wheel 和
无源码扫描反例。

`public/support/internal/all` 由同一个 `CompiledCatalog.scheduler_projection()` 按
`catalog_scope` 过滤，未发现第二 scope 注册表、权限位或独立编译结果。support 仍只允许
deterministic transform，并拒绝 Agent、Effect 和人工 approval；它可以声明由 public reviewer
完成的科学审查要求（`operations/catalog.py:233-235`）。public transform 未被误禁。默认生产
目录没有测试 operation，因此 Codex Agent 生成、Worker MCP 配置、readiness、Root
`operation_catalog`、preflight/invoke 和未来 UI 投影都无法从默认安装态取得这三项测试行为。

### 7.4 跨边界与 33 项约束族判断

本轮按计划第 12 节列出的 33 项行为约束族复核，而没有伪称仓库存在一个“33/33”验证脚本：

- **单一行为权威**：Operation identity、端口、组件、资源、原生工具、网络、限制、审查、用途、
  后果和 revision codec 均由一次启动编译及摘要冻结；preflight 与 invoke 使用 exact 编译对象。
- **最小上下文与授权**：输入 exposure/usage、输出后续用途和 Worker 工具集合均在同一 Task
  快照中；本轮用途收窄避免 receipt/diff/review 等非科学主对象扩大成 claim evidence。
- **科学责任边界**：Agent 仍负责开放式科学内容，Transform 只做确定性变换，Effect/adapter
  承担外部副作用；控制层只验证合同、来源、谱系、审查、审批和生命周期，没有新增科学状态机、
  固定阶段 DAG 或控制层科学裁决。
- **多角色与独立审查**：生产者和 reviewer 是两个精确 Operation 任务；reviewer 必须消费 exact
  subject，且其结论必须属于 producer 声明的接受集合。prior result、相似 schema 或另一 revision
  不能替代审查。
- **插件单入口与通专分离**：通用科学 operation 通过统一插件入口编译；默认 core 不携带测试
  operation。当前设备参数、TCAD role 和 domain-only transform 明确标为 R4 迁移债务，没有被
  误称为已插件化。
- **人类决定与执行边界**：本次返工没有新增审批写入口，也没有把 chat/Agent verdict 当作 UI
  决定；Effect 仍需外部动作级 ApprovalContract。真实求解和生产 credential 未因原型 Agent
  通过而放行。
- **恢复、谱系与不可变性**：TaskOutputSpec 保留 operation authority/digest 及完整输出合同；
  exact review 与 producer policy 从已完成任务或 exact digest/port 恢复，不依赖 scheduler prose
  或可变角色默认值。

未发现本轮修复新增数据库表、资格状态机、schema 名白名单、角色黑名单或另一组 producer
policy。虽然 Root 和 TaskService 仍承载 8765 的历史兼容面，但新增规则集中在一条共享 producer
admission 上，属于 R4 迁移期间必要的最小过桥，不是另一套权限系统。

### 7.5 独立执行证据

| 检查 | 第二轮结果 |
| --- | --- |
| `pytest -q tests/operations` | `134 passed in 46.13s` |
| `pytest -q` | `167 passed in 60.38s` |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| 默认/fixture 目录与摘要比较 | `15/13/0/28`、`15/13/3/31`；28 个生产摘要一致 |
| 核心复杂度门 | `320/450/430`，合计 `1200` |

当前 ABI4 真实 Codex 证据位于
`deliverables/debug-evidence/r3-science-agent-text-abi4-run3/qualification-report.json`。独立读取
报告及其事件、final message 和两份 session evidence 后确认：24 项检查全真，Root 观察任务为
`completed`；真实 `spawn_agent`、无父上下文继承、唯一 exact Worker server、父会话零
Root/Worker 调用、任务内原生读取/图像/PDF、注册 PDF 工具、无网络和无未声明分析均通过。
operation digest 为
`68dfbae6a8e4ec07448b168a635892eae3f4a7d29cf8b6e41f017ceb2c3e3f0c`，与当前源码编译结果一致；
事件、final message 和 session 文件的实算 SHA-256 均与报告记录一致。run1/run2 只保留为中间
历史，不作为当前 ABI 通过证据。

### 7.6 进入 R4 后必须关闭的非阻塞债务

以下问题不阻断“进入 R4-A”，但不得在后续状态中静默宣称已经解决：

1. **R4-A**：把设备参数专用提取/审查桥和 TCAD author/reviewer 的 role、context、工具与资源迁入
   TCAD 插件统一入口；迁移后删除核心中的 legacy role/context 注册，不再扩展当前过桥。
2. **R4-B/R4-C**：把严格 domain-only 的 TCAD、curve `artifact_transform` profiles 和外部执行
   adapter 编译为 OperationSpec 组件，并删除旧 transform/entry-point/facade；当前通用 profile
   已失败关闭，但 legacy transform 本身尚未具有通用输出端口用途合同。
3. **R4-D**：让 UI 从 compiled ApprovalContract projector 生成领域字段；当前 UI 仍包含历史领域
   renderer，不能把“Operation 后端已统一”表述成“UI 已插件化”。
4. **R5**：完成旧角色表、context/profile 表、scheduler topology 和总代码量的净删除。本轮只证明
   `spec/catalog/invoke` 冻结预算达标，未证明整个控制面已经比 8765 更小。
5. **R6**：把 `inherited_prototype` 从提示词白名单升级为平台/进程级强隔离，并用第二领域插件、
   非核心 schema revision 和组合安装测试证明低成本扩展；当前结论不把提示约束冒充硬权限。
6. **R7**：更新 `docs/ARCHITECTURE.zh-CN.md` 与安装、运维、真实 TCAD 闭环记录。该文档当前仍是
   8765 历史架构真相，现阶段以已冻结总体计划和 R3 实施记录为重构权威。

R4 不得为关闭这些债务重新引入领域 scheduler 分支、operation 私有注册表、schema 名白名单、
第二 review/qualification 权威或 Worker 自由发现工具；若迁移需要其中任何一项，应立即打回
架构设计而不是追加兼容层。
