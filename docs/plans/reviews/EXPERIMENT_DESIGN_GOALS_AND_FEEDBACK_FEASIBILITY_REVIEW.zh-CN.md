# 实验设计目标列表与研究反馈方案独立可行性审查

日期：2026-09-08。结论：**REVISE**。

方案方向可行。目标清单、本轮子集和原 Artifact 反馈可以复用现有模型、物化、Run 文件及独立审查机制，无需新增阶段状态机、服务、包装对象或 public Operation。两项实施前需确定的修正均可容纳于已列七个生产文件；本次未发现必须增加第八个生产文件的实际调用者。**七文件范围作为修订后的实现预算可信，不等于影响仅限七个文件或设计 Operation。**

本报告是工程方案审查，不是科学结论、实施验收或部署许可。未修改计划、生产代码、测试及其他文档，未发起科学 Operation、调用 Worker 工具或执行 solver。

## 1. 审查对象与限定

- 方案：[EXPERIMENT_DESIGN_GOALS_AND_FEEDBACK_MINIMAL_PLAN.zh-CN.md](../EXPERIMENT_DESIGN_GOALS_AND_FEEDBACK_MINIMAL_PLAN.zh-CN.md)。首尾核验 SHA-256 均为 `bd8ae03c1fe4347c270fa820709b2551b882596a0967d635a408e0188122a644`。
- 源码根：`123/scidiscovery-e5.2`；分支 `refactor/m7-pre-e5.2`；首尾 HEAD 均为 `2edac5d317a74056869a567bd0daa7f556ecbc85`。
- 按当前脏工作树审查。工作树包含既有修改、删除和未跟踪生产文件，尤其已修改的实验组件与未跟踪的 `curve_contract_compiler.py`；结论不能归属于仅 checkout 上述 HEAD 的源码，也不是对全部既有差异的复审。
- 已读工作区及源码根 AGENTS.md。本任务受父任务的独立工程审查范围约束，不进入交互科研调度或 Worker 生命周期。
- 使用 `scid-cross-boundary-review`、`scid-find-simplifications`、`scid-change-scope-checks` 和 `karpathy-guidelines`；参照当前架构、设计宪章、约束登记、计划索引及相关插件说明，旧审计仅作为历史材料。

## 2. 实施前应修订的事项

### R1 — P1：删除总体覆盖强制校验后，承接该判断的审查者缺少原目标合同

**位置。** 方案第 70、74 行；`src/scidiscovery/general_science_experiment_operations.py:117` 的 object review 输入目前只有 `experiment_plan`；`src/scidiscovery/artifact_agent/schema/experiment.py:405` 的 Portfolio 保存总体文本和 key，不保存原 `mandatory_targets`、`closure_requirements`；`src/scidiscovery/artifact_agent/schema/experiment_intent.py:331`、`:427` 只把原 statement 复制到物化计划。待删除的全集覆盖判断位于 `src/scidiscovery/artifact_agent/schema/experiment.py:550`。

**触发条件。** 原目标包含 A、B 两项 mandatory target，本轮只研究 A。按方案移除 blanket coverage 后该局部设计可提交；首轮没有历史反馈，或续轮只提供旧计划与实验结果时，review 得到的材料仍不包含原合同中 B 的强制性和闭合条件。方案允许这种输入组合，也明确要求 reviewer 判断本轮覆盖、暂缓项及其合理性。

**影响。** Reviewer 能审查计划内部一致性，但不能独立核对作者是否漏掉或误述了总体强制项；要求作者在 rationale 自述不足以恢复独立证据。若严格执行方案的“关键依据缺席不能无保留 PASS”，这类合法局部计划的该项审查只能保留意见。该缺口针对本次新增的目标选择审查责任，不要求借此补齐所有既有科研上下文。

**最小修正。** 在既有 review 声明中增加可选、只读、精确类型的 `research_objective` 输入，复用原 Artifact，保留 `prior_signal` 的原 admission；调度说明要求审查科学计划的本轮覆盖和暂缓项时绑定与设计同一份原目标合同。工程计划仍可不绑定。组件中的 review 提示和同源语义合同明确：有原合同则比较 key、statement、mandatory targets 与闭合要求；缺少它时说明该判断的限制，不能声称已独立核实整体覆盖。不要将缺席可选端口写成隐藏的提交异常。另一种同样小的修正是明确复用只读反馈端口绑定原合同，但必须在方案中写明用途、确切绑定和数量预算，不能继续依赖未声明的父链读取。

`execution_context` 仍保持可选：仅当当前目标选择依赖其中某项能力或限制时复用该原件供 reviewer 查阅；本报告不要求强制新增全部设计上下文。以上仅涉及已列 `general_science_experiment_operations.py`、`general_science_experiment_components.py`、`roles/scheduler.md`。

**回归口径。** 原合同 A+B、当前计划 A、后续目标 B：review 文件包含精确原合同；替换为另一份同 key、不同 mandatory targets 的原件必须改变绑定指纹，并可被审查识别。没有历史反馈的首轮 design 仍合法；没有 research objective 的工程 review 仍合法；缺席原合同不得触发未声明的 KeyError 或隐藏必需输入。

### R2 — P1：共享 inventory 准入语义必须有明确的编译身份变更，不能只依赖实验 Schema 自然传播

**位置。** 方案第 90、94、114、151、153 行；拟修改循环位于 `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1326`，旧合同检查位于同文件 `:1457`。`src/scidiscovery/operations/catalog.py:135` 只为 resource/workspace 计算内容摘要，普通 callable 不按实现源码散列；同文件 `:713`、`:724` 将声明、资源、review/provider 与 `OPERATION_ABI_VERSION` 纳入编译摘要。现有 ABI 在 `src/scidiscovery/operations/spec.py:10` 为 `16`。

**触发条件。** 对全部 Agent `evidence_inventory` 增加 producer gate 例外，却只更新实验的 Schema/提示和端口、保留 ABI。既有证据审计、图证据和参数提取等 Agent 的输入声明及可达实验资源可能完全不变，但它们对已退休或未审查产物的 admission 已改变。改变 Python 循环本身不会自动使这些 Operation 的 digest 改变。

**影响。** 同一个编译身份将代表两种不同的输入资格语义。仅比较 design、materialize、review 的新 Schema 身份不足以覆盖这项共享控制合同变化。方案已经要求按真实合同检查决定 ABI；本次源码追踪的结论是，保留 ABI 且不增加其他身份覆盖机制的实现不可接受。

**最小修正。** 在已列 `operations/spec.py` 中明确提升共享 Operation ABI；不新增一套按操作名或源码摘要的兼容机制。计划第 5 节和 P4 应据此写明：除实验资源的自然传播外，ABI 变更将使当前目录全部 Operation 身份退休，并重新生成 profile/Worker 配置。无需改插件版本、Operation ID 或部署脚本。

**部署与恢复限定。** `src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py:84` 对旧身份返回 `contract_retired`；`src/scidiscovery/artifact_agent/service/runs.py:952`、`:1061` 不允许旧合同 Run/恢复草稿作为新合同继续。原科学基础的 producer identity 和 approval provider 也需重新核对，不能预设“仅重审一次旧计划即可恢复”；旧产物的直接 review 仍可能先在 producer gate 被拒绝。应按新目录从仍可接纳的确切来源重新建立必要资格链，或记录该部署验收尚未恢复。保留旧记录只读，不将 feedback 例外用于必需资格输入。既有安装/新会话路径可以承载这一改变，但本次未执行部署。

**回归口径。** 比较完整前后 catalog：至少包含不依赖实验 Schema 的现有 inventory Agent，不能保留旧 digest；验证旧 qualified/claim/revision/effect 绑定和旧 approval 不被继承，而旧产物作为 Agent inventory 可读。新旧运行不能凭相同语义名或恢复草稿跨合同复用。

## 3. 非阻断的具体实施注意项

### N1 — P2：review 新增 inventory 会改变可引用的 source_key，须明确处理

`general_science_agent_operations.py:130` 为 ScientificReview 默认声明 `/evidence`；`operation_contract.py:293` 的投影只允许可见 `evidence_inventory` 的实际别名；`:390` 在没有此类绑定时把 evidence 的 `maxItems` 设为 0。被审 `experiment_plan` 的用途是 `prior_signal`，因此被排除。

已用当前函数作纯内存探针复现：原 review 的 evidence 上限为 128；增加一个可选可见 inventory 后，无反馈时变为 0；有 `current_progress` 时 source_key 仅允许 `current_progress`，不能引用 `experiment_plan`。探针用当前已允许的 typed opaque inventory 激活相同投影，未修改 wildcard 校验或运行中的 catalog。

这**不等于所有无反馈 review 都失败**：`schema/research_cycle.py:115` 的 evidence 默认为空，`schema/scientific_output.py:36` 的 finding evidence_keys 也可为空。但先前合法的计划引用会变成 `runtime.schema` 拒绝，Reviewer 也不能用结构化 citation 指出计划本身的问题。

建议在七文件范围内明确口径：若保留计划原件引用，为此 review 显式配置 `evidence_paths=()`，并在已列组件的可见语义合同与 context validator 中将引用校验绑定到该次实际可见别名（含计划和反馈）；这样无需扩大通用投影实现。若选择仅允许 feedback 出现在 evidence，提示必须明示计划内问题用 findings 描述，测试须覆盖这种限制。不要把 experiment_plan 改成 inventory 来修复引用，这会同时绕过被审主体的 producer 合同检查。该选择应在实现前确定，但空 evidence 本身不是方案方向的阻断。

### N2 — 目标字段约束要同时覆盖首次物化与完整对象修订

`general_science_experiment_components.py:145` 的 revision context 保护总体身份，不逐项保护 proposal 目标；`:259` 的 revision 语义资源会继续被完整对象 validator 消费。实施时应在已列 `experiment.py` 的 Portfolio/Proposal 模型中验证非空、唯一、子集及每个 proposal 包含精确 `portfolio.objective`；不能仅在首次 materializer 插入总体文本。同步同一文件中的 revision 提示/语义说明，允许独立审查要求的目标修正，要求后续目标的变更有理由，不把全部目标永远冻结为不可修改集合。

这些是方案已要求的保留/校验规则的具体落点，不要求改变 revise 的端口形状或增加目标 ID。16/17 项上限与 64 KiB 总输出上限同时生效，不表示每项都可同时写满 8192 字符。

### N3 — 现有总体 coverage 是单份计划的评价，不能宣称已实现跨轮自动累计闭合

`curve_score/objective.py:126` 只接收一份 Portfolio，`:149` 用它验证每份 curve contract，`:160` 枚举所有 mandatory targets，`:303` 汇总缺失/失败；`curve_score/schema.py:529` 要求 contract 的实验与验证计划确实在该 Portfolio 中。A 轮、B 轮各自通过不会自动形成一份总体 PASS，不能把旧 A contract 任意塞给仅含 B 的新计划。

这是保留现有科学资格边界，与本方案要求“局部通过不成为总体通过”一致。本次无需新增累计目标状态或评分服务。实施验收只证明续轮能读取旧目标和结果、形成新计划；最终整体闭合仍须满足原评价路径的完整输入，未满足时保留未决。不要把“目标清单承接”写成“现有 evaluator 已能自动合并多轮研究”。

## 4. 已追踪且可复用的调用链

| 路径 | 证据与判断 |
| --- | --- |
| design → intent → materializer → Portfolio | `experiment_intent.py:136`、`:320`、`:405`、`:480`；design 提交先物化再调用同一目标校验（`:469`）。两个目标列表及删除全集覆盖循环均可在两份已列 schema 文件中完成。 |
| 首次计划与 revision | `general_science_experiment_operations.py:140`、`:176`；revise 仍输出完整 Portfolio 并走原 review edge。新字段自动进入复制草稿和严格 Schema，旧 schema 只作历史 inventory，不需要输入 union 或静默补默认值。 |
| wildcard → preflight → Worker 文件 | `operations/spec.py:115` 当前只容许 handoff-only wildcard；`operations/invoke.py:153`、`:180`、`:297` 保留重复对象、数量、单项/总大小、schema/media、current 检查。`runs.py:235` 与 `run_assignment.py:40` 只排除 handoff_only，on_demand 原件会写入 assignment 指向的输入文件。 |
| 只读性与父链 | `local_workspace.py:147` 将输入原字节以 `0400` 写入；`runs.py:848` 把全部冻结输入登记为父引用，故 plan → intent → feedback 不需二次绑定。这是现有可信本地后端的文件约束，不是新增强沙箱。 |
| producer gate 例外 | 在 `mcp_root_operation_routes.py:1326` 进入 `_operation_output_contract` 前，仅对 Agent inventory 跳过该 producer 资格判断可行。外围实例解析、preflight、cohort、revision、claim 门保持；`:1121` 的 claim 禁止与 `:834` 的 Transform 非合格传播不需删除。 |
| 历史 current 与封存 | `run_current.py:79`、`:87` 已按 require_current 冻结 anchors；反馈默认不要求 current 即可读历史，显式要求仍必须保持。失败 Run 草稿没有正常已登记输出的身份，不能以本例外作为读取来源。 |
| 局部 curve 与 TCAD | `curve_contract_compiler.py:115` 已按本 proposal 的 observables 选择 objective targets；`project_packager.py:1307` 按当前计划全部 comparison variables/cases 校验。搜索生产目标调用者未发现使用已拟移除的 `proposal.objective` 的领域消费者，因此暂不需要修改 TCAD/curve 算法。 |
| 下一轮设计 | 已冻结前一计划与新反馈作为新 design 的输入、由 Agent 生成新列表即可。来源/指纹沿既有链传播；后续目标如何调整是科学审查责任，不能由控制代码推断完成或推进阶段。 |

可见 wildcard 必须同时采用 `media_types=("*/*",)` 和现有 wildcard schema resource；只写 `schema="*"` 而沿 helper 默认 JSON media type 会被 `InputPortSpec.issue` 拒绝。方案已有 wildcard 意图足以支持这一实现细节，无需新增生产文件。review 的输入总预算也需同步覆盖原计划与选定反馈，不能沿用现有 2 MiB 而宣称每项 8 MiB 可用。

## 5. 现有 Agent inventory 消费者与范围结论

以当前源码注册的 core/general/curve/TCAD/figure 五插件编译得到 49 个 Operation，其中 **9 个 Agent** 使用 inventory：

| 消费者 | inventory 内容与保持的边界 |
| --- | --- |
| curve contract design / review | `reference_bundle`（`curve_score/science_operations.py:441`、`:511`）；是严格解析和合同复算的参考数据，不能据只读例外宣称它已获资格；后续确定性消费门保持。 |
| evidence audit / audit.intake | 原 `source_material`（`general_science_agent_operations.py:290`、`:334`）；审计原件用途，主审对象和 qualification 保持各自原门。 |
| figure request prepare | 原 paper source（`figure_science_operations.py:357`）；新增例外不会产生 solver 或审批授权。 |
| figure extract / audit | 原 paper、request、manifest、report、panel、overlay、CSV（同文件 `:365`、`:416`）；完整确定性 family 检查位于 Root `:1131`，不能一并跳过。历史不一致 family 因而仍可拒绝，这不是新 design/review 三组自由只读反馈的隐藏条件。 |
| parameter extract / audit | 原 source 和审查所用 checklist/参数/source catalog（`parameter_operations.py:957`、`:1038`）；主审 package、intake、coverage 与既有 exact family/审批合同保留。 |

这些端口都将受到共享 producer 例外影响；本次未发现必须把某个 inventory 改成新的资格端口才能完成方案的确定性证据。但这不是全局门禁可以随意放宽的证明。回归必须覆盖上述消费者的主审对象、完整 family、Transform、claim 和 effect 负控，特别不能把新例外写成跳过整个 `_validate_operation_input_admission`。

**文件范围判断：** R1、R2 和 N1 的最小修正可以落在现有七文件内；N2 是这七文件中既有 validator/提示的同步。没有确认需增加的生产文件。测试 fixture、架构与调度文档、生成 profile 及 catalog 影响面大于七文件属于已声明验证/发布范围，不应算作新服务或领域算法改造。“不新增公共行为”宜改成“不新增 public Operation”，因为允许历史 inventory 读取本身就是新的公共 admission 行为。

## 6. 实际验证与尚未验证

| 实际执行 | 结果与限定 |
| --- | --- |
| `sha256sum`、`git rev-parse HEAD`、`git branch --show-current`、`git status --short` | 计划与基线匹配；已识别脏树，不视为干净 HEAD 验收。 |
| `rg`、带行号源码读取、AGENTS/技能/架构/调用者追踪 | 覆盖上列设计、物化、审查、准入、文件、资格、curve/TCAD 和身份/恢复接口；没有逐项审计全部无关脏树差异。 |
| `PYTHONPATH=src:plugins/tcad_artifact:plugins/curve_score:plugins/curve_figure_evidence python -B -`，调用 `compile_catalog((CORE_PLUGIN, GENERAL, CURVE, TCAD, FIGURE))` 并枚举 Agent inventory | 成功，49 个 Operation、9 个 inventory Agent；约 0.94 秒。只编译源码声明，无 runtime/实例/Run 创建。不是安装态 wheel 证明。 |
| 同一 Python 环境的纯内存 review Schema 投影探针 | 成功复现 N1，约 1 秒；仅复制 compiled spec 并加合法 typed opaque inventory，调用现有 `operation_port_json_schema`。未实现方案或绕过实际 catalog admission。 |
| `ps -eo pid,comm,args` 检查测试/solver 进程 | 未发现既有 pytest、solver 或构建进程；未另起测试。 |
| `git diff --check` | 通过；这是当前已跟踪差异的空白检查，不代表未跟踪方案已实施。 |

**未执行：** pytest、全套回归、wheel/build/install、架构验证脚本、Root preflight/invoke 集成、实际 Worker 文件读写、审批 UI、部署恢复和 TCAD solver。本任务只审查方案；未改生产实现，源码与局部投影已足以定位以上修正，再跑现状全套不能证明拟议方案。计划 P2/P3 中的真实 Root→Local 文件正负例、针对 R1/R2/N1 的回归及共享接口实施后的分批串行全套/安装态验证仍需由实施阶段完成。

审查时七个文件摘要（供后续确认本报告所对照的脏树内容）：

```text
067296cf1e3c43d4d285a13628b387705a0c484112499aef8e799a63dedc6cce  src/scidiscovery/artifact_agent/schema/experiment_intent.py
b0fd47dbccdc90980fe808a19524db773c2e99e1f9671d088494211eb0b7d0b2  src/scidiscovery/artifact_agent/schema/experiment.py
f942c088bf39223d27731b390460774ba67b163adfa4bc05a6ddc221333276e2  src/scidiscovery/general_science_experiment_operations.py
e6b82e00c79d8d03ac1f23f7a4534653e5703d73f29bad9b04793cad55b37625  src/scidiscovery/general_science_experiment_components.py
acc76c1627604c9e8885d4e18273fea2c1a65f4ff13b3787c5e30ea84bc5453d  src/scidiscovery/operations/spec.py
76e70304c3e46a74ef63d932e461d4fc0c9e8d4f4d30a377993977e00d7e5205  src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py
c2b3fe51de3dec22d339c888456b82c86142190ad89a85425c1495ccf3ba2cc5  roles/scheduler.md
```
