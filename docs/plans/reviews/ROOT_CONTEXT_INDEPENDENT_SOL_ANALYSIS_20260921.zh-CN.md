# Root 上下文消耗独立分析（Sol）

日期：2026-09-21。范围：只读工程分析；未修改生产源码，未调用科研 MCP、模型或 solver，未推进 Fig4 执行。分析窗口固定为 `2026-09-21T02:17:37.302Z` 至 `03:14:03.720Z`（后者不含），即用户“开始吧，完成实际流程验收”到首次询问 Root 消耗之前。

关联证据：

- 既有初步结论：[ROOT_CONTEXT_FINDINGS.zh-CN.md](../evidence/scientific-skeleton-author-20260920/fig4-live-20260921/ROOT_CONTEXT_FINDINGS.zh-CN.md)
- 本次流式元数据结果：[root-context-independent-sol.json](../evidence/scientific-skeleton-author-20260920/fig4-live-20260921/root-context-independent-sol.json)
- 本次可复算脚本：[root_context_independent_audit.py](../evidence/scientific-skeleton-author-20260920/fig4-live-20260921/root_context_independent_audit.py)
- 实际流程记录：[OBSERVATIONS.zh-CN.md](../evidence/scientific-skeleton-author-20260920/fig4-live-20260921/OBSERVATIONS.zh-CN.md)

## 结论

Root 的高消耗不是一个已修复功能的简单回归，也不是 wait 回复过大。它是三个边界同时暴露后的结果：

1. 以前的优化主要覆盖启动、单个结果读取和短交接；本次在一个不压缩的 Root 会话里连续走过 9 个不同 Operation、6 份不同指南、多个结果 Schema 和一条历史来源链。按需加载降低了短路径起点，却没有限制完整长链的**唯一材料累计**。
2. 控制层虽已提供 index、selected values 和父链分页，但仍把 index/status 不需要的 `scheduler_signal`、恢复/执行/诊断元数据重复投影给 Root，也没有直接投影“这个产物的精确 producer input 端口”。Root 因而承担了机械导航。
3. Root 同一科学调度线程还承载了 UI 源码诊断和 native usage 计量。Codex 平台会保留模型生成的 JS/JSON 调用参数和工具回复；把完整结果交给 `text(...)` 后，所谓 orchestration storage 并不会隔离这些内容。

先前结论的主要数字正确，但有一项重要归因缺失：78,732 token 的净增长中，前 149 个响应的模型输出合计 21,909 token，随后会成为输入；其中推理输出只有 2,718 token。工具调用 JS/JSON、协作调用和面向用户消息都在这 21,909 内，不能只用其 48,390 个字符另列为旁项，也不能再与 output token 相加。扣除这项后的 56,823 token 只是“外部新增内容与平台序列化变化”的合并边界，仍不能按字符精确分给各工具。

因此优先修复应是：先让控制层按请求目的投影 Run 回复并投影 producer inputs，再提供由同一编译合同生成的“可调用合同视图”；Root 继续负责科学选择。不要重做统一 MCP 或 preflight 省略，也不要新建摘要 Agent、科学图或调度状态机。

## 1. 独立计量与对初步证据的纠正

### 1.1 Native usage

| 指标 | 本次复算 |
|---|---:|
| 请求数 | 150 |
| 首请求 input | 59,357 token |
| 末请求／峰值 input | 138,089 token |
| 窗口净增长 | 78,732 token |
| 累计 input | 15,654,599 token |
| 累计 cached input | 15,550,976 token |
| 累计 uncached input | 103,623 token |
| 累计 output | 22,272 token |
| 累计 reasoning output | 2,788 token |
| 末请求前已生成、可回入上下文的 output | 21,909 token |
| 其中 reasoning output | 2,718 token |

逐请求 input 单调上升，没有观察到 input reset。首请求的 59,357 已包含历史会话，不是 SciDiscovery 空启动成本；末次峰值也不能与 1,565 万累计 input 混为一谈。缓存累计只说明 150 次请求反复携带既有前缀，不是本次上下文净增长的主要口径。

`21,909 + 56,823 = 78,732` 是原生计量上的边界分解：前者是先前模型响应的精确 token 数，后者包含工具结果、child/user 输入及请求序列化变化。它不是 tokenizer 对每个工具块的归因公式，但足以否定“78.7k 基本都由工具正文直接换算而来”。推理输出只有 2,718，隐藏推理也不是本次大头。

### 1.2 可见工具返回

工具可见正文仍是 193,208 字符，与初步结论一致。独立解析的主要类别如下：

| 类别 | 块数 | 字符 | 性质 |
|---|---:|---:|---|
| `run_status` | 16 | 48,094 | 科学选读、索引及重复控制元数据混合 |
| 9 份不同 Operation 合同 | 9 | 44,363 | 一次性；大部分是端口语义 |
| 6 份指南的 4 次合并读取 | 4 | 22,931 | 一次性指令，不是科学证据 |
| 精确父链导航 | 11 | 19,591 | 来源身份必要，手工逐跳表示是机械成本 |
| UI 源码/定位输出 | 4 | 15,546 | 不属于科学调度 |
| 接口合同 | 7 | 9,373 | 一次性调用规则 |
| invoke 返回 | 11 | 7,801 | 创建身份、冻结配置、审批入口等 |
| catalog 导航 | 2 | 6,652 | 一次性选择入口 |
| 计量脚本源码 | 2 | 5,258 | 验收工具，不属于科学判断 |
| exec wrapper | 83 | 3,901 | 平台包装 |
| usage 摘要 | 16 | 2,273 | 验收计量 |
| wait 回复 | 44 | 2,139 | 正文很小 |

前四类为 134,979 字符，占工具可见正文约 69.9%，但其中合同、指南和部分父链是按当前合同必须读取的唯一材料，不能全部标作浪费。

初步证据中的核心分类——`run_status` 48,094、合同 44,363、父链 19,591、wait 2,139——得到独立复现。指南/UI/普通 shell 的切分略有修正，因为同一个 `functions.exec` 输出可能连接 Markdown、多个 JSON 对象和 wrapper；本次脚本按内部对象分段，避免按整个块中的一个关键词覆盖其他内容。

既有 [root_context_audit.py](../evidence/scientific-skeleton-author-20260920/fig4-live-20260921/root_context_audit.py) 当前直接对完整工具文本执行 `json.loads(s)`，但 native trace 中 `exec` 回复以 `Script completed ... Output:` 包装，且有多个结果直接连接。按现文件重跑不能复现其保存的细分类。本次脚本显式剥离 wrapper、扫描已知顶层响应且只导出元数据；既有 JSON 的核心总量可用，原脚本本身不应继续作为可复算证明。

### 1.3 模型自己生成的调用内容

助手工具参数共 48,390 字符：`exec` 38,210，collaboration 10,180。按用途，科学编排 JS/JSON 约 19,985 字符，其他 exec 约 13,569，collaboration 非 wait 约 9,301，指南读取 1,676，计量 1,749，UI 调试 1,231，wait 参数 879。

这些字符已包含在模型 output 的 token 计量中，不能再次加到 21,909 token。它们说明为什么只缩短 MCP 返回还不够：模型每次生成长 JS/JSON、spawn/follow-up 参数，也会扩大下一轮输入。仓库能减少调用次数、参数形状和返回内容；仓库不能改变 Codex 平台把模型输出和工具回复记入会话的方式。

## 2. 哪些必要，哪些可避免

### 必要科学与权威信息

- 9 个 Operation 都不同，且没有重复 describe 同一合同。合同的 `inputs` 字段合计约 26,656 字符，占合同正文约 60.1%；这些端口名、用途、资格、暴露方式和可选输入语义决定 Root 能绑定什么，不能整块删除。
- `run_status` 中 `selected_output` 合计 18,749 字符。它们是 formal conclusion、限制、剩余矛盾、审查处置等原始科学字段，不能用控制层摘要替代。
- 每个科学结果的 `scheduler_signal` 至少需要与正式正文一起读取一次。它记录 verdict、assumptions、missing inputs 和 suggested next actions，但自身不是完整科学正文。
- 来源身份、原始目标、精确审查对象和审批 URL 必须保留；节省上下文不允许改写父链、继承旧审查或用 chat 批准执行。

### 已证实的机械或重复负担

- `run_status` 的 48,094 字符中，`selected_output` 18,749、`scheduler_signal` 9,168、`output_index` 6,135，其余约 14,042 是状态、配置、恢复、诊断和导航字段。至少 6 条 index→selected 路径重复投影了同一 signal，约 4,055 字符。index 只用于找路径，不需要科学 signal 正文。
- 父链 19,591 字符承担的是精确身份恢复，但当前返回缺少 producer input 端口映射。Root 必须逐个看 schema/kind/producer 后再猜应沿哪个父节点继续；端口与保存输入的对应关系是控制层已有事实，不是科学判断。
- 9 份合同中的“完全相同字段值”重复约 3,753 字符（不含 JSON key/分隔符），远小于 44,363。故不能把合同大头归为通用 boilerplate；真正可下沉的是 Root 调用不需要的 Worker native policy、控制限额和重复 availability 元数据，所有输入端口与跨端口规则仍须保留。
- 6 份指南均为一次读取，没有发现同指南反复读取。它们把启动成本转为长链累计成本；部分内容与主 scheduler prompt 重复，但不是本次最大可避免项。
- UI/计量相关可见输出至少 23,077 字符（UI 15,546、计量源码 5,258、usage 摘要 2,273），另有对应调用参数。它们属于验收和用户插入的工程问题，不应驻留在长期科学调度上下文。
- wait 回复本身只有 2,139 字符。44 个发出 wait 的模型响应合计 output 3,865 token；从这些响应到下一请求的 input 增长合计 6,521 token，其中还可能包含完成通知和 child 消息。它不是零成本，但只占净增长的有限部分，且主要来自 44 次模型唤醒，不是 wait 消息正文过长。

## 3. 为什么此前精简没有挡住

### 不是简单回归

当前源码和 trace 都证明既有机制仍在工作：

- `scid_catalog` 只给摘要，`scid_describe` 才读取选中合同；9 个合同各一次。
- 本次没有 preflight→invoke 两步重复准入。
- `run_status` 已支持 index、selected values 和 `output_paths=[]`；`artifact_catalog` 已支持分页 parents。
- Root 没有把完整 author 诊断数组展开到上下文。

没有版本对照证明这些功能发生回归。把它称为“回归”会误导修复方向。

### 主要是实际路径未覆盖和验收指标过窄

此前 A/B 多数是一个 Operation、一个已知报告或一次短交接。它们证明了局部路径变短，却没有覆盖一个 Root 会话连续经过假设、批判、骨架、作者、审查、修订、复审、打包和审批请求的唯一合同累计。既有总结也已经诚实记录：Root 单结果修复主要减少了一次请求，长链收益未证实。

本次每个 Operation 的完整合同、未知输出 Schema 的 index、每个新角色的指南都各有合理触发。短夹具把“默认不全量返回”和“同一结果不重复 detail”当作主要成功指标，未把“多种不同材料在不压缩会话中累计”作为验收主指标。

### 有控制层缺口，也有 Root 执行与任务隔离问题

- 控制层缺口：`RootRunRoutes.run_status` 无条件组装 signal；`run_summary` 又在 index、selected、polling 各视图保留 signal、恢复和诊断字段。指南无法保证模型每次自行删掉这些字节。
- 合同缺口：Operation 只提供完整 scheduler projection，没有“调用所需的完整视图”；`mcp_gateway.describe` 对 Operation 直接硬编码 `operation_catalog(view="detail")`。
- Root 执行问题：Root 用 `functions.exec` 合并调用后，仍将完整结果交给 `text(...)`。主提示虽要求只 emit 决策字段，但没有服务端投影时，这是一条软约束。
- 任务隔离问题：UI 源码诊断和计量脚本读取进入同一科学 Root。用户临时加入 UI 问题可以解释其发生，但不能把这部分算成科学框架必需开销。

所以原因不是单选“提示执行不当”或“代码回归”：主要是长链覆盖缺失和指标选择错误，叠加两个真实响应投影缺口及一次 Root 线程范围污染。

## 4. 当前生产路径与责任边界

### Operation 合同

- [`mcp_gateway.py:150`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_gateway.py) 的 `UnifiedMCPRouter.describe` 在 Operation 名称上直接调用 `operation_catalog(view="detail")`。
- [`mcp_root_operation_routes.py:68`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py) 从唯一 `CompiledCatalog.scheduler_projection()` 生成 scheduler 视图；这是正确权威来源。
- [`spec.py:455`](../../../src/scidiscovery/operations/spec.py) 的 `SchedulerOperationView` 同时包含调用端口、科学用途、输出、Worker native policy、控制限额和审批元数据。
- [`mcp_response_views.py:29`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_response_views.py) 的 `operation_detail` 目前只删除 `accepts_actions` 与两份已由端口表达的 required/optional 列表。

完整 Operation 合同必须由同一个编译对象随时可取，但“完整可获取”不等于每次调用前都要把所有输出说明、Worker native policy、文件/网络限额和通用运行元数据送进 Root 当前上下文。Root 需要的是**完整可调用合同**：所有输入端口、基数、用途、暴露、current/qualification 要求、跨端口 admission/validation、revision/review/approval 边界、后果和精确 Operation 身份。Worker 工具权限和封存限额仍由编译合同与控制层执行，可以在 full/debug 视图按需取得。

要避免“隐藏要求”拒绝，调用视图不能手写或摘要：必须由 `SchedulerOperationView`/compiled spec 同源投影，并在编译期证明每条 input admission/validation 所依赖的端口和规则都出现在视图。invoke 仍对同一个 compiled object 完整校验；任何可修复拒绝必须引用调用视图中存在的 rule/path。这样是一个权威的两个投影，不是第二份合同。

### Run 结果

- [`mcp_root_run_routes.py:127`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py) 的 `run_status` 先组装完整生命周期、bound inputs、native observation、payload/index/selection，随后在 176–183 行无条件附加 signal。
- [`mcp_response_views.py:77`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_response_views.py) 的 `run_summary` 对 index、selected 和 polling 保留同一组 execution profile、recovery、diagnostic、signal 字段。
- [`mcp_root.py:174`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_root.py) 已有 `output_mode`/`output_paths`，因此无需新增结果服务或摘要 Agent；只需让现有响应投影知道此次请求是 lifecycle、navigation 还是 decision。

控制层负责机械字段与原值选择，Root 负责决定读哪些科学字段并解释它们。index 不应重复 signal；status-only polling 不应返回 signal 正文；decision 读取应在同一次响应返回 state、精确 selected values 和一次 signal。完整 detail 保持可用。

### 来源恢复

- [`mcp_root_instance_routes.py:288`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py) 的 `artifact_catalog` 只按 direct parent 返回 name/schema/kind/producer。
- 控制层已经在 [`mcp_root_run_routes.py:138`](../../../src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py) 从冻结 `RunStatus.inputs` 投影 `bound_inputs`，并有 `RunService.completed_for_output` 查精确 producer Run。

新增的最小能力应是对一个精确 Artifact 投影其**即时 producer inputs**：端口名、冻结顺序、当前实例语义名或明确 null、producer Run/Operation 是否可用。Root 决定哪个端口与当前科学目标相关，并按需继续一跳。不要在控制层递归寻找“真正目标”、按 schema 名猜科学相关性、自动绑定候选或保存新的 lineage 状态。它只是把已存 Run 输入从无端口 parents 还原成端口化读视图。

## 5. 按收益／风险排序的最小修订批次

### 批次 0：先修计量与线程范围，不改生产协议

做法：以后 native trace 聚合在 Root 之外运行，只向 Root 返回固定数值摘要；UI/源码诊断交给独立工程线程，Root 只接收一段结论和文件位置。保留本次流式脚本作为证据工具，不安装为科学 Operation，也不让它读科学 payload。

不改：Run、Artifact、Operation、审批、恢复、科学结果。兼容成本为零。

验收：同一科学区间中 Root 的工具分类不再出现 meter source、usage 脚本和 UI source；这些数据另存且仍能按 response id 复算。不要把减少的工程输出冒充生产 MCP 优化。

### 批次 1：让 `run_status` 按请求目的投影

落点：`RunStatusInput`、`RootRunRoutes.run_status`、`run_summary`/`root_response`，以及 `test_root_context_boundary.py`、`test_run_status_output_selection.py`、`test_mcp_response_views.py`。

最小行为：

- `output_paths=[]` 或 index 响应只返回生命周期／导航必需字段和 `scheduler_signal_status`，不返回 signal 正文；失败时保留精确 error/diagnostic reference。
- selected/decision 响应返回 completed state、精确值、origin/omission 和一次 signal。
- detail/full 继续提供完整绑定、恢复、native observation、timing 和原件。
- 可先用 additive `response_profile` 或 `include_scheduler_signal` 保持旧客户端默认，再让 unified Root 明确选择；部署验证后才考虑改变默认。

不改：`SchedulerSignal` Schema、formal payload、Run 生命周期、资格/current、错误记录、恢复数据。不会新增缓存或状态。

兼容成本：低到中。旧调用仍能要求 full；新 Root 路径需同步接口说明和 results guide。风险是过度裁剪失败诊断，必须以失败/超时/历史 Run 负例封闭。

量化验收：用本次 16 个已保存响应离线重放，`selected_output` 和 decision signal 的 canonical bytes 必须相同；index/polling 中 signal 正文为 0，signal status 仍准确；同一 Run 的一次 decision 读取不重复 signal。记录新旧 `run_status` 字符数对照，以 48,094 为本样本基线，但不预先承诺比例。

### 批次 2：投影即时 producer input 端口，替代无端口的手工父链浏览

落点：`ArtifactCatalogInput`、`RootInstanceRoutes.artifact_catalog`，复用 `RunService.completed_for_output` 和现有 binding reverse lookup；响应层与 `inputs.md`；测试扩展 `test_root_draft_routes.py`、`test_historical_compatibility_paths.py`、`test_m6a_direct_instance_management.py`。

最小行为：增加只读 `producer_inputs` 视图，返回一个精确产物的直接 producer Operation/Run 及保存的输入端口映射。历史 producer 不可用、transform 无可证明端口分组、未绑定 parent、跨实例时分别明确，不退回猜测。parents 原视图保留。

不改：Artifact parent refs、Run inputs、current、qualification、producer identity；不递归、不自动选 objective、不自动 bind、不建立 lineage 数据库。

兼容成本：低到中，纯加法读视图。transform 历史输入若不能从原记录证明就保持 unavailable，不能用当前 catalog 猜旧合同。

量化验收：对本次同一冻结节点恢复出完全相同的 objective/foundation/problem frame/previous hypotheses 名称集合及端口来源；响应字符低于现有 11 次 parents 合计 19,591，调用次数不增加；null/历史/多 producer/实例隔离负例通过。未降低时不宣称收益。

### 批次 3：增加同源的“完整可调用合同”视图

落点：`DescribeInput`/`UnifiedMCPRouter.describe`、`SchedulerOperationView` 的投影函数、`operation_detail`；测试扩展 `test_unified_mcp.py`、`test_mcp_response_views.py`、`test_compiled_declaration_consumers.py`、installed catalog 入口。

最小行为：`scid_describe` 对 Operation 支持 `invoke` 与 `full`。`invoke` 由同一 compiled declaration 生成，包含 Root 构造合法请求和理解后果所需的全部字段；`full` 保留现在的完整 detail。兼容期默认保持 full，由新 scheduler 明确请求 invoke。

不改：统一 MCP 的三个工具、CompiledCatalog 权威、OperationSpec 校验、preflight/invoke 路径、Worker 合同、审查/审批/恢复边界。该批次不得再次把“统一 MCP”或“省略 preflight”计为新收益。

兼容成本：中。投影遗漏会制造隐藏要求，因此必须做全 catalog 一致性检查：每个 public Operation 的 required/optional ports、all-or-none groups、input admission/validation、revision/review/approval 和 side-effect consequence 都可从 invoke 视图定位；正负 invoke 的 rule/path 不得超出视图。完整合同仍可获取。

量化验收：本次 9 个 Operation 的 invoke 视图与 full 44,363 字符并列统计；实际请求零新增 `missing hidden requirement` 类拒绝，绑定与创建身份一致。只报告实测差值，不承诺百分比。

### 批次 4：仅在前三批后仍频繁 index 时，给输出合同声明 decision paths

这是风险较高的后续项，不应先做。由插件在既有输出合同中声明 formal conclusion、limitations、remaining contradiction 等精确 JSON Pointer；编译器验证路径与 Schema，同一 `run_status` decision 视图返回原值。控制层不生成摘要、不判断重要性。

落点会跨 `OutputPortSpec`/编译 catalog、通用和 TCAD Operation 声明、run_status 与 installed tests。若该字段进入 Operation digest，新 Operation 代际必须按历史兼容规则处理，旧 Artifact 仍可全文/index 读取且不续资格。

不改：科学内容、signal verdict、独立 review、原始 payload、Root 的科学解释。不要用核心内置 schema 名或 `/verdict` 猜所有领域。

量化验收：本次未知 Schema 的 6,135 字符 index 应在声明覆盖的 Operation 上消失，selected 原值与一次 signal 保持完全相同；未声明/历史 Schema 仍可靠 index/full。先做确定性 replay，再决定是否值得承担 digest 与插件升级成本。

### 批次 5：最后收敛指南和 Root 调用写法

前三批把机械保证放进控制层后，再删 `roles/scheduler.md`、`results.md`、`inputs.md`、`research.md` 中已由接口保证的重复说明，保留科学决策、审批、独立审查和失败关闭规则。提供短的标准 spawn/attach/begin 模板，Worker 仍从正式 assignment 读取任务，不在 chat 重述科学材料。

不改：指南按需安装机制、角色分工、完整原件入口。不要把提示词裁剪当主修复，也不要恢复已删除的 role registry。

验收：6 份指南的当前 22,931 字符作为本样本基线；安装版逐字节生成检查、真实接口负例和同任务 Root 行为均通过。若请求数或补读增加，字符减少不算通过。

## 6. 平台约束与仓库可控范围

仓库内可改：MCP 返回投影、编译合同视图、端口化 producer input 读视图、指南和调用形状、将 UI/计量移出调度线程。

仓库内不能保证：

- Codex 是否把 `functions.exec` 的 JS、nested tool 参数和回复保留在会话；本次已经保留。
- cached input 的计费策略、cache block 边界和平台何时 compaction。
- `wait_agent` 是否能在不唤醒模型的情况下等待事件。当前 44 次 wait 的消息体很小；若平台未来提供“事件到达才恢复模型”的等待原语会有帮助，但不是本仓库应伪装实现的功能。

因此不要新增 server-side“Root 记忆缓存”、调用收据状态机或自动 compaction 控制器。它们会复制平台上下文或控制权威。正确边界是服务端只返回本次用途所需的原值和机械身份，Root 保留科学判断。

## 7. 后续真实验收口径

本报告没有启动 A/B。以后每个批次先做低资源 deterministic replay 和真实安装正负例；只有这些通过后，才在明确授权下做 native 对照。

Native 对照必须固定：

- Root 模型与推理强度（本次 trace 为 `gpt-6-astra` / `medium`）；
- 完全相同的初始历史或同一标准化新会话起点；
- 相同 catalog/安装 digest、实例快照、输入 Artifact 和用户文本；
- 相同阶段边界：从接受实际验收请求到创建同一待审批 execution request，不启动 solver；
- 相同 UI/计量处理方式，工程插话单列；
- 相同平台工具集合和通知策略。

每组分别报告首请求 input、末次/峰值 input、净增长、请求数、output/reasoning output、工具可见字符、错误/拒绝、最终科学对象与审批对象。累计 input、cached input 和 uncached input 另列，不能替代窗口峰值或净增长。compaction/input reset 时分段，不能把压缩前后直接相减。至少两组配对后再判断波动；没有实测就不给节省百分比。

功能通过条件始终优先：同一原始目标、来源、科学结论、限制、剩余矛盾、独立 review、精确审批对象和恢复入口仍可获得；任何隐藏要求、额外拒绝、错误对象绑定或科学路径改变都使 token 对照无效。

## 8. 本次只读验证

本次只运行流式元数据脚本和静态源码核查；脚本逐行读取 native JSONL，不导出隐藏思维、完整 transcript、审批 token、身份秘密或科学大正文。没有运行测试、模型、科研 MCP、solver、安装、部署或 Git 操作。新增文件只有本报告、独立分析脚本及其 JSON 结果。
