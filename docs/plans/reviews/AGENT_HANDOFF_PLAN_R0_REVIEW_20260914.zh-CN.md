# Agent 信息交接修复计划 R0 独立工程复审

日期：2026-09-14。结论：**需小幅修订，整体方向与 P1—P5 次序合理，不需要重写计划。**

审查对象为 `docs/plans/AGENT_HANDOFF_INFORMATION_REPAIR_PLAN.zh-CN.md` R0（196 行）及其在当前源码中的可实施路径。仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`；HEAD：`2d252a9b9d703919e47e7146b5c4c5c4e0dd8316`。以下代码路径相对此仓库，行号指本次读取的工作树。已保留既有四个源码/测试修改、计划及用户 Fig4 文档；未修改任何仓库文件。

采用 `scid-cross-boundary-review`、`scid-find-simplifications`；读取计划、原独立源码审查、架构、科学设计宪章及约束登记表，并独立追踪 Root、assignment、Local/Hardened open、finalizer、seal、组件身份及下游物化源码。未调用科学控制面或 Worker 工具，未运行测试、编译、solver，未读取生产状态或实际 Worker 目录，未派生其他 Agent。本文是工程计划审查，不是科学结论或实现验收。

## 一、必须修订

### R1：P4 未闭合自动作者模板到 gap 提交的默认入口

**计划位置：** 第 123—128 行，尤其第 124 行仅明确调整审查模板，第 125 行允许缺省 handoff/机械字段，第 126—127 行保留错误类型拒绝和显式摘要，第 131 行承诺只写一份正式摘要即可完成。

**源码证据：**

- `plugins/tcad_artifact/tcad_artifact/operation_workspace.py:471—486`：新作者工作区自动创建 `deck/handoff.json`，其中 `verdict` 与 `summary` 都是 JSON `null`，其余字段为空数组。
- 同文件 `:619—630`：gap finalizer 读取该文件，当前只投影 blocked verdict，再进行严格 `RoleHandoff` 校验。
- `src/scidiscovery/artifact_agent/schema/role_result.py:21—26`：summary 必须是非空字符串；`null` 不是缺失值。
- `operation_workspace.py:643—646`：完整项目仍严格读取 handoff。

**可达情景：** 新作者打开真实物化工作区后，按新提示只填写合法的 `deck/gap.json`，不修改平台已生成的 handoff。即使实施者按 R0 增加“缺字段时补齐”的逻辑，`summary` 仍以错误类型存在；保留显式字段与拒绝错误类型的要求会继续拒绝它。若用覆盖所有 `null` 的办法补齐，则又把控制模板与用户错误混为一谈，违背第 126 行。

**影响：** P4 的主要收益无法由默认入口兑现，Worker 仍须识别并删除控制层的机械占位字段；仅用手工删除字段/文件的单元样本可以通过，但不能证明真实交接减少了机械工作。

**最小修正：** 把新作者 handoff 模板明确纳入 P4：新模板省略 summary/verdict，仅保留其他现有字段。gap finalizer 补齐缺失机械字段；完整项目分支仍要求作者提供正式 handoff。已有显式非字符串 summary、非法 JSON 等继续报告原位置，不进行全局 `null` 宽容。无需更改 RoleHandoff 或新增草稿 Schema。

**最小验收：** 通过真实 workspace materialization 创建新作者任务，保持生成的 handoff 原样，只写合法 gap 后提交到 completed；对应完整项目若不填写 handoff 则仍拒绝。再保留一项显式 `summary: null`/损坏 JSON 负例，证明“省略”与“损坏”确实分开。此正例应加入现有 gap 用例，不增加另一套测试框架。

### R2：P4 的共享 finalizer 行为身份需要落到实际声明文件

**计划位置：** 第 115—119 行的主要文件范围、第 129 行“新组件按既有编译身份机制更新”、第 158 行范围外先修计划的限制。

**源码证据：**

- `src/scidiscovery/general_science_components.py:413—465`：共享 `RESULT_FINALIZER` 的实际 `ComponentSpec("result_finalizer", ...)` 在此注册，当前没有 `configuration_identity`；R0 的文件范围未列该声明位置。
- `src/scidiscovery/artifact_agent/service/result_materialization.py:91—92`：外层调用 `materialize_general_result`，P4 要改变其内部投影行为。
- `src/scidiscovery/operations/catalog.py:137—154`：callable finalizer 不产生 resource digest；这里没有自动函数体或递归 helper 摘要。
- 同文件 `:757—779`：编译 digest 包含组件声明与 resource digest。
- `src/scidiscovery/artifact_agent/service/runs.py:1348—1355`：旧 Run 与当前编译合同的隔离依赖其 operation version/digest。

**可达情景与证据边界：** 只修改 finalizer 函数体，不会改变这个组件的声明身份。R0 同时计划修改通用 prompt 和 ScientificReview Schema 描述，因此本次受影响的科学审查 Operation 总 digest 很可能通过这些资源变化而改变；**不能据此声称本次所有旧 Run 必定被新 finalizer 接管**。缺口在于第 129 行承诺的“组件身份更新”尚未指定真实所有者，容易依赖恰好同时修改的 prompt 作为间接保护；计划又要求范围外改动先修订。

**最小修正：** 在 P4 文件范围增加 `general_science_components.py` 的共享 result_finalizer 声明，为改变行为的 finalizer 显式更新既有 `configuration_identity`。TCAD 对应组件在已经列入的 `plugin.py:524—546` 按同样机制处理。无须新增代码散列器、注册表、版本状态机或扩大 Operation 科学版本。

**最小验收：** 在既有编译/身份检查中验证变更后的组件及受影响 Operation 身份改变，旧 Run 不由新合同重新提交；旧完成 Artifact 仍可读取。无需遍历所有历史 Run。

## 二、可选增强与实施时必须兑现的现有要求

### O1：P2 的选读能省正文，但未知字段仍缺少导航；可用一层按需索引补齐

**计划位置：** 第 65—89 行，特别第 81 行超预算只返回指针/大小，第 88 行要求按输出类型读取相关正式子树。

**已确认事实：** `mcp_root_instance_routes.py:247—285` 的 artifact_catalog 只有名字、schema、字节数、parents 等元数据；`operations/spec.py:436—460` 的 Root catalog 输出端口投影没有完整字段 Schema；`mcp_root_run_routes.py:130—158` 当前唯一正式正文读取是完整 payload。schema 名称本身不能列出一个未见输出的真实键和数组索引。

**触发情景：** Root 第一次遇到新的/历史的较大输出类型，选读 `/summary` 返回 missing，选读根超过 32 KiB。R0 允许完整读取，所以科学内容没有变得不可达；但此场景只能猜路径或回到全量正文，不能据现有计划宣称未知输出同样获得有界导航收益。已有层级较深的 plan 和带 files 的 project 比平面 review 更明显。

**建议的最小选项：** 对本次已解析、因超预算而 omitted 的 selected 对象/数组，附有界的一层 child pointer/type/size 和遗漏计数；空指针可用来请求根导航。只在该 selected 分支返回，不让 `output_paths=[]` 为了索引读取正文，不生成递归树、摘要或新 schema 注册表。已知路径仍直接选读；未知路径可导航；巨大单个字符串继续允许完整读取作为明确后备。

这是可用性增强，**不是现有 full fallback 导致的科学正确性 blocker**。更小的可接受方案是明写“未知字段直接完整读取，选读收益只承诺已知路径”，避免猜路径循环。若采用一层导航，则增加一个未知 schema 大对象经根导航读到正式字段的入口用例，并在 P0/P2 比较同一阅读任务的总回复字节及往返次数，不能只比较一份工具回复。

### O2：P2 要显式保护 scheduler_signal_status 与展示方式的独立性

`mcp_root_run_routes.py:62—68` 当前用 `output is not None` 判断 signal availability。若 selected/omitted 分支按计划不再填完整 sealed_output，而照搬此判断，可能出现真实 signal 存在却报告 unavailable。

R0 第 70、77—83、93 行已经要求保留 signal 与原成果状态，这个问题属于该承诺的直接实现检查，**不需要新增一个功能或独立架构修改**。建议验收表明列 available/historical 输出各自的 omitted/selected 情景：展示方式改变不改变 signal 的真实可用性，缺 signal 也不能被伪造为存在。

## 三、P1—P5 可实施性结论

| 项目 | 结论与依据 | 是否需扩大范围 |
| --- | --- | --- |
| P1 源码注释交付 | 合理。现有 project files 会封存并物化到 review；`project_packager.py:630—647` 的 source digest 含完整注释字节，`operation_workspace.py:690—725` 校验当前 attestation，能保护“注释之后的当前证明”。 | 不需要新端口、附件、项目字段或注释门禁。 |
| P2 Root 省略/选读 | 单参数区分 null/[]/指针列表清楚；元数据与科学值分开、保留 full fallback、子树整体省略均合适。真实入口仅需扩展 Root Input 与 facade；可选导航见 O1。 | 不需要新的 Root 工具、科学摘要或存储迁移。 |
| P3 Local 合同按需 | 合理。`mcp_local_worker.py:325—344` 的 start_here 条件确实造成非分析角色内联；`run_assignment.py:78` 已持有准确合同，`codex.py:465—474` 已要求读所选合同。取消 start_here 对合同 pointer 的限制即可。 | 不需要新合同文件/解析协议；Hardened 保留内联是正确边界。 |
| P4 摘要单写 | 限定三类有正式 summary 的类型正确。`runs.py:1018—1026` 先 finalizer 再 seal，`run_assignment.py:159—170` 仍提供严格封存 envelope，允许草稿省略机械字段具有真实实现路径。 | 先修 R1、R2。不要推广到 CriticReview、EvidenceAudit、完整项目。 |
| P5 分析指导单载体 | 当前源链成立：`analysis_workspace.py:172,245—249` 提供完整指导；curve 的两项 analysis Operation 使用该 workspace，TCAD `analysis_bindings.py:173—175` 调用同一 materializer。把 prompt 拼接换短导航符合现有读取链。 | 不需要改公开 workspace 默认输出；不同受支持组合的核对/保留原提示要求足够。 |

ScientificReview 的草稿省略说明放在现有 payload Schema 资源 description，经过 `result_schema_json` 的 payload 替换后对 Worker 可见；无需为此放宽封存 Schema。这里描述的是流程事实，不是新增强制科学字段。TCAD 可用现有 patch_contract 声明同一事实。

## 四、兼容、平台与验收范围

R0 正确保留旧默认 run_status、历史 payload、旧显式 handoff、Local 老 assignment fallback、Hardened 内联、恢复预算及当前 attestation。它没有把“历史可读”误作“历史可按新合同提交”。P5 也限定当前已注册的三个分析角色，未假定全部插件或所有 Hardened 角色都支持本地文件读取。

P0 与第 162—175 行的定向检查足以作为实现验收骨架：存在真实 materialization→submit→completed、wheel/stdio、原件未读的负证据、非法科学字段、恢复及历史路径，并明确不跑 solver/full suite。应加入 R1 的 untouched 自动模板正例、R2 的实际组件身份检查，并把 O2 信号状态放入原有 B 组；除此之外未发现需要新增测试体系、全量矩阵或并发测试的证据。

token 目标的表述是诚实的：P0 测 UTF-8 字节而不伪装真实 token，第 184 行在恢复研究后才记录实际平台计量。计划实施期间能证明减少特定默认回复和双写义务，不能先证明总模型 token 降低。若选择 O1，记录相同读取任务的总字节与工具往返即可判断是否只是把一次大回复换成多个无效请求；无需额外观测系统。

## 五、审批建议

先以最小 R1 修订关闭 P4 的新作者模板与组件身份责任位置，然后做一次只检查这些变化及其与 P2/P3/P5 交叉影响的复审。P2 一层导航可以纳入这次小修，也可明确限定选读收益后保持原 full fallback。没有证据要求重建交接系统、增加摘要 Agent、统一草稿校验器、取消独立审查或扩张原计划五项范围。

本报告仅记录 R0 计划与源码的静态工程评估；不表示实施、安装或隔离测试已通过。
