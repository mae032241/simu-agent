# R3-C 通用确定性变换独立审查

审查日期：2026-08-28  
审查基线：`baseline/8765-codex@404aeb1`，叠加已经通过的 R0—R3-B 与当前 R3-C 工作树  
审查性质：未参与本轮实现的跨边界只读审查；实现、测试和计划均未由审查者修改

## 一、结论

**通过，允许进入 R3-D。**

首轮审查曾发现一个真实阻断：公开 `artifact_transform` 可以在显式注入
`ScientificStateTransformAdapter` 后，按旧 profile 执行已经迁入 catalog 的通用变换，所得
Artifact 也没有 operation id、版本和编译摘要。该路径实质上让旧 adapter 与
`CompiledCatalog` 同时拥有选择权威。

当前工作树已经在旧 adapter 的统一选择边界无条件拒绝全部八个已迁移通用 profile；拒绝发生在
扫描任何注入 adapter 之前，因而不是“当前默认恰好没有安装 adapter”的偶然成功。参数化负例和
Root 真实生命周期负例都在显式注入旧 adapter 的情况下通过。首轮阻断已经关闭。

除此之外，13 个 transform operation 均能对应当前调度合同或 readiness 消费者，没有发现完全
孤立的预造行为，也没有发现能在保持严格输入/输出 Schema、父链和失败关闭的同时安全合并的
operation。`public/support/internal/all` 是同一个不可变 `CompiledCatalog` 的确定性投影；默认
`public` 不再使 support 行为依赖猜测，因为调度合同已明确在需要确定性闭合时查询
`scope="support"`，再按端口和描述选择，最终仍由唯一 `operation_invoke` 精确调用。

本次通过不代表旧系统已经净减重。通用变换声明与旧 callable facade 暂时共存，领域
`artifact_transform` 兼容入口也仍存在；它们分别有 R3-D、R4、R5 的明确退出门。本轮只确认：已
迁移的通用变换不再由旧路径选择，且没有新增状态机、持久化权威或科学判断。

## 二、阻断项与非阻断边界

### 2.1 阻断项

无。

### 2.2 非阻断边界

1. `general_transform_operations.py` 为 13 个严格行为增加了约 927 行插件声明、固定 callable
   包装和 guard；旧 `ScientificStateTransformAdapter` 的实现尚未删除。因此 R3-C 证明的是
   “选择权威收敛”和“控制特判减少”，不是仓库总代码净下降。总代码净下降仍必须在 R5 验收，
   不能用本报告提前宣称完成。
2. 新测试已经实际穿过安装态目录和 Root transform 生命周期，并覆盖 intake、多输出、幂等、
   provisional 传播、修订、收据不读 payload、父链和通配失败关闭；但没有为 13 个 operation
   的每一个变体分别构造成功态科学夹具。其底层八类 callable 是既有确定性实现，变体只冻结
   不同 Schema/端口，因此该缺口不阻塞迁移门；R3-D 删除旧分支前宜为八类 executor 各保留一个
   成功态等价回归，避免未来只剩声明自洽测试。
3. `scheduler_topology._CAPABILITIES` 仍包含部分现有行为名称。这是计划明确留给 R5 删除的静态
   拓扑债务。当前 support 已能从 catalog 显式发现，因而不再是唯一触达路径；但在 R5 完成前，
   仍不能宣称新增领域已经做到“零 scheduler 修改”的最终验收。
4. 总体计划 R3-C 条目中的“`artifact_transform` 不再按 profile 搜索 adapter”应按当前实现
   理解为“对已迁移通用 profile 不再搜索”。尚未迁移的领域 profile 仍经旧入口搜索，待 R4
   迁移后删除。实施记录已经如实写明这一过渡边界；后续文档同步时宜把该句限定清楚。

## 三、独立执行的检查

| 检查 | 独立结果 |
| --- | --- |
| R3-C 重点专项：通用变换、安装调用、安装目录、基线 transform 生命周期 | `21 passed in 24.39s` |
| 完整 `pytest -q` | `147 passed in 46.17s` |
| `python -m compileall -q src tests/operations tests/artifact_agent` | 通过 |
| `git diff --check` | 通过 |
| 核心预算 | `spec.py / catalog.py / invoke.py = 332 / 449 / 410`，合计 `1191`，未超过 `1200` |
| 独立编译目录 | `all=31`、`public=15`、`support=13`、`internal=3` |
| 插件归属 | 31 项只来自 `builtin` 与 `general_science`；通用 Agent/transform 同属一个 `general_science` 定义 |
| R3-B Agent 摘要 | 当前 15 个 Agent operation 的摘要和 agent type 均与 text run8 已生成配置相同 |
| 生产派发搜索 | `CodexTaskDispatcher` 没有生产构造点；Root 默认仍只返回任务的 compiled agent type |

仓库仍没有逐项编号的“33/33”自动验证器。本报告按已经冻结的约束族做行为审查，不伪称运行了
不存在的脚本。

## 四、13 个 operation 的消费者与最小性

### 4.1 当前消费者

| 行为组 | Operation | 当前消费者证据 |
| --- | --- | --- |
| intake 拆分 | `science.intake.split.v1` | scheduler 明确调用；readiness 在 intake 后投影；安装态 Root 测试实际执行 |
| 目标投影 | `science.objective.project.v1` | readiness 在 foundation 后投影；support 目录公开完整端口与用途 |
| 候选资格 | `science.candidate.eligibility.v1` | scheduler 明确在 critic 与 audit 后调用；readiness 投影；精确父链负例 |
| 实验物化 | `science.experiment.materialize.v1` | scheduler 明确调用；readiness 投影；工程/科学两种端口形状负例 |
| 参数覆盖 | `science.parameter.coverage.v1` | scheduler 的参数证据链明确调用 |
| 知识更新 | `science.knowledge.update.validation.v1`、`science.knowledge.update.diagnosis.v1` | scheduler 分别按 validation/diagnosis 合同调用；diagnosis 变体也进入 readiness |
| 结构化修订应用 | intake、hypothesis-proposal、experiment 三个 `science.revision.apply.*.v1` | scheduler 根据精确目标 Schema 选择；intake 变体实际穿过 Root 生命周期 |
| 未变证据收据 | intake、hypothesis-proposal、experiment 三个 `science.evidence.receipt.*.v1` | scheduler 根据精确目标 Schema 选择；intake 变体实际验证父链和不读证据 payload |

因此不存在没有当前生产调度语义的第 14 种预造对象，也不存在 13 项中的完全孤立项。这里的
“消费者”包括模型可见 scheduler 合同和确定性 readiness；不把仅出现在测试 ID 列表中的声明算
作消费者。

### 4.2 为什么暂不合并

- 两个知识更新 operation 的第二输入 Schema 互斥。合并会重新引入 mode/union 分派，弱化编译
  期端口闭包。
- 三个 revision 与三个 receipt 分别冻结目标对象 Schema 和输出 validator。合并需要通配科学
  payload 或在 callable 内重新猜目标类型，正是本轮要删除的 profile 特判。
- receipt 与 revision 不能合并：前者只证明证据声明未变且必须登记大证据父链，后者实际读取
  base/patch 并产生完整对象和 diff；二者的 payload 可见性和输入资格不同。
- intake 拆分与 objective 投影的准入不同：前者允许 provisional intake 并传播不可声明状态，
  后者要求可作为 claim evidence 的 foundation。

所以 13 项虽然表面数量较多，但它们是严格合同变体的最短可辩护集合。继续增加新变体时仍须先
证明当前有 producer/consumer，不能把该判断扩张为通用预造许可。

## 五、单一插件、单一目录与安全投影

- `general_science_plugin.py:63-66,1753-1761` 将 transform 的组件和 operation 直接合入同一个
  `PluginDefinition`。安装入口仍只有 `pyproject.toml:26-28` 的 `builtin` 与
  `general_science`，没有 transform 专属插件入口或组件 entry point。
- `CompiledCatalog` 只保存一个不可变 operation 映射，`scheduler_projection()` 每次从该映射中
  生成视图（`operations/catalog.py:37-48`）。`catalog_scope` 不进入 `OperationSpec` 或摘要，
  而是由 `executor.kind` 和保留的 `builtin.test.*` 命名空间确定性推导
  （`operations/spec.py:255-312`）。因此四个 scope 不是四份注册表，也没有可漂移 visibility
  声明。
- Root 的 `operation_catalog` 只过滤上述同源投影；`scope="all"` 也不会产生另一套可调用对象
  （`mcp_root.py:1238-1247`）。精确执行始终重新从同一 catalog 解析 operation，再做调用期
  preflight（`mcp_root.py:1252-1272,2646-2719`）。
- 默认 `public` 只返回 15 个开放式科学 Agent，避免把确定性胶水与测试行为平铺给规划者。
  `roles/scheduler.md:74-93` 现在明确说明何时查询 `support`、如何按端口/描述选择，以及
  `internal/all` 的非规划用途。因此 support 是显式可发现的同源子集，不是隐藏 allowlist。

这满足“一个插件一次注册编译”和“默认目录降噪”两个目标；没有为了目录分层给 spec 增加第
十一个顶层字段。

## 六、adapter 权威与旧旁路复审

### 6.1 当前唯一选择路径

`operation_invoke` 先取得 exact compiled operation；transform 分支构造
`CompiledTransformAdapter` 并把已绑定调用传入既有 Artifact 生命周期。该适配器只接受当前
operation id，从 compiled 端口派生 nonqualifying 输入和 payload 可见项，调用的 executor 也是
compiled operation 唯一可达的组件（`operations/invoke.py:223-274`）。

`general_transform_operations.py:114-209` 虽然复用
`ScientificStateTransformAdapter.transform()`，但每个 wrapper 的 profile 是源码固定常量，运行
调用方不能选择或扩大它。外层的输入、输出、guard、限制和 validator 均来自对应
OperationSpec，而不是该 facade 的 profile 查询结果。

### 6.2 首轮旁路与修复

首轮独立负例把 `ScientificStateTransformAdapter()` 显式注入 `RootToolFacade`，直接调用旧
`artifact_transform` 的 intake-split profile，调用成功并生成缺少 operation 摘要的 Artifact。
这证明原测试中“默认 adapter 为空所以失败”不足以建立唯一权威。

修复后，`select_transform_adapter()` 在枚举任何 adapter 之前先调用同一个
`ScientificStateTransformAdapter.supports_transform_profile()`；八个已迁移 profile 全部直接返回
“requires operation_invoke”（`artifact_agent/transforms.py:717-731`）。这份保留集合与内部
facade 的真实支持集合同源，不是 Root 内新增的第二 operation allowlist。

`tests/operations/test_general_transform_operations.py:217-234` 参数化覆盖全部八个 profile；同文件
`:336-389` 又在 Root 真实 transform 生命周期中显式注入旧 adapter，确认 compiled
`operation_invoke` 正常，而 legacy 调用仍失败。该修复也不会误杀尚未迁移的 TCAD/curve-score
领域 adapter；它们仍暂时通过旧入口，退出边界为 R4。

据此，`ScientificStateTransformAdapter` 只保留 callable 实现职责，不再拥有已迁移行为的外部
选择权；旧 `artifact_transform` 不能绕过通用 catalog。

## 七、父链、资格、payload 与失败关闭

- 调用 preflight 要求输入端口集合与 spec 完全相同，检查基数、Schema、媒体类型、单项/总字节
  上限、current，并执行 compiled guards（`operations/invoke.py:70-151,275-302`）。没有运行期
  parameters 通道可改变行为。
- 候选资格要求 critic 和 audit 都包含 exact portfolio ref；科学实验意图只接受“仅 intent”或
  “intent 加完整三科学父对象”两种形状；revision patch 必须来自 exact base；receipt 的 revised
  object 与 diff 必须同时来自 exact base（`general_transform_operations.py:212-381`）。
- Root 是否允许非资格输入由 compiled consequence 与端口 usage 决定，而不是 legacy profile
  名字（`mcp_root.py:2680-2707`）。真正来自 provisional/failed/revise 输入的结果继续带
  `scientific_claim_admissible=false`，不能因确定性变换自动升级资格
  （`mcp_root.py:1427-1449,1543-1560`）。
- 唯一通配输入只存在于 receipt evidence collection，并固定为
  `schema=*`、`media=*/*`、`usage=evidence_inventory`、`exposure=handoff_only`；编译器拒绝把该
  通配口改成 full。`CompiledTransformAdapter` 不把 handoff-only evidence 交给 callable，Root 只
  将其 ref 登记进父链（`general_transform_operations.py:778-827`；
  `operations/invoke.py:249-256`；`mcp_root.py:1476-1496`）。
- transform 输出必须与 compiled 输出端口集合、基数、大小和 validator 完全一致；额外、缺失或
  非 bytes 输出均失败关闭（`operations/invoke.py:356-397`）。Artifact fingerprint 与 labels 记录
  operation id、version、digest，仍复用既有 CAS、父链和幂等绑定生命周期。

这些门只校验确定性合同，没有为候选排序、参数选择、假设形成、实验设计或诊断添加控制面科学
判断。

## 八、R3-B 与默认 Agent 派发未退化

- 当前 15 个 Agent operation 的完整 digest 和 `operation_agent_type` 与
  `.scidiscovery-state/r3-science-spawn-text-run8/project/.codex/agents/` 中的 15 份生成配置逐项
  一致。新增 transform 组件没有进入 Agent operation 的可达组件集合，因此没有改变 R3-B
  已审 prompt、工具、模型或权限摘要。
- Root 的 `task_prepare_dispatch` 仍只调用既有 `TaskService.prepare_dispatch` 并返回 Task 中冻结
  的 compiled agent type（`mcp_root.py:1989-1998`）。生产源码和部署入口没有
  `CodexTaskDispatcher` 构造点；默认仍是父调度者随后使用 `spawn_agent` 的快速闭环。保留的独立
  Codex 进程实现仍只是未接线的后续加固代码。
- R3-C 没有修改 Worker 输入、MCP namespace、媒体读取、受控写入、validate/finalize 或
  `inherited_prototype` 的边界。R3-B 的“提示行为约束而非硬隔离”结论仍原样有效，不能由本轮
  通过外推到真实 TCAD、生产凭据或不可逆副作用。

## 九、33 项约束族与设计目标判断

仓库将 33 项约束定义为行为结果矩阵，而不是 33 个实体。按约束族复核如下：

| 约束族 | 判断 | 依据 |
| --- | --- | --- |
| 唯一权威、不可变性、谱系 | 通过 | 已迁移通用变换只能从一个 compiled catalog 选择；Artifact/CAS、精确 parent refs、operation 摘要和幂等绑定继续复用 |
| 插件单一注册与启动期编译 | 通过 | Agent 与 transform 同属唯一 `general_science` 入口；组件只能经可达 operation 进入目录 |
| 默认拒绝与最小输入 | 通过 | 严格端口集合、Schema、媒体、大小、usage/exposure、current 和 guard；无参数扩权 |
| 科学责任与确定性边界 | 通过 | callable 只投影、合取、物化、应用补丁和生成收据；不新增假设、排序、参数选择或诊断 |
| 资格/current/人工决定 | 不退化 | provisional 只能传播为不可声明；没有新 qualification/current/approval 权威，低风险 transform 无人工审批 |
| CQRS、副作用与恢复 | 不退化 | transform 复用既有只读解析、CAS 注册和绑定；没有外部 adapter、执行授权旁路或第四状态机 |
| Worker/文件交接 | 不退化 | 本轮无新 Worker 通道；R3-B Agent 摘要与默认 spawn 路径未改变 |
| UI 与领域解耦 | 不退化 | Root/UI 无 13 项 allowlist；目录视图从 executor kind 推导，领域实现留在插件 callable |
| 轻控制面、快速闭环 | 当前阶段通过 | 一个查询、一个 preflight、一个 invoke；无新表、Receipt 状态机或审批；净删旧重量仍由 R3-D/R5 验收 |
| 复杂度预算 | 通过 | 三个冻结核心文件合计 1191 行；没有新增数据库表、顶层 registry、生命周期或 OperationSpec 字段 |

首轮旁路存在时，“唯一权威”约束族不通过；当前服务端拒绝与负例已使这一约束族闭合。没有发现
为了修复而引入新的科学实体、第二目录、领域 scheduler 白名单或可变运行状态。

## 十、最终裁定

**R3-C 通过，允许进入 R3-D。**

放行范围只包括按现有计划拆除 `TaskService/runtime` 中已经由 compiled Agent/transform 合同取代
的通用科学特判。R3-D 仍必须单独实现、测试和独立审查；本报告不允许提前迁移真实 TCAD
副作用、删除尚有领域消费者的 legacy adapter，或宣称 R5 的总体净减重已经完成。
