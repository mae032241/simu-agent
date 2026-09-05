# R5 E1 论文图五操作拓扑独立审查

日期：2026-09-04

结论：**PASS**  
阻断项：**0**  
是否放行 E2：**是，仅放行既定 E2 科学保真度工作，不放行部署或端到端实验。**

## 1. 审查范围与口径

本次只审查 E1 是否把不可运行的集合式图 Agent 重切为可编译、可运行、来源可重放的五操作拓扑。
E2 的真实 Fig.4 线跟踪/遮挡/逐点资格算法、E3 的审批投影等价、E4 部署、E5 真实 Codex Agent
工具调用和 UI 可读性均不作为 E1 阻断。

工作树包含大量早于 E1 的未提交改动，因此无法把整个 `HEAD` 差异误称为 E1 独占差异。本审查按
E1 证据文件声明的论文图插件源码、插件入口和对应测试追踪实际边界，并保持只读；唯一写入是本审查
文件。

## 2. 逐项结论

### 2.1 五操作拓扑已经闭合

编译目录中实际得到：

| Operation | 视图 | 执行种类 | 输出 |
|---|---|---|---|
| `science.figure.request.prepare.v1` | public | Agent | 单一 `figure_request` |
| `science.figure.evidence.materialize.v1` | support | Transform | manifest、panel、overlay、table、report |
| `science.evidence.extract.figure.v2` | public | Agent | 单一 `scientific_intake` |
| `science.figure.evidence.audit.v1` | public | Agent | 单一 `evidence_audit` |
| `scidiscovery.curve-bundle.figure-evidence.v2` | support | Transform | bundle、normalization audit |

五项在 `LocalTrustedBackend` 上的不可用原因均为空。请求、Intake、审查三个 Agent 都只有一个非集合
主输出；机械附件与最终 bundle 的多输出只由 Transform 产生。实现没有为此修改 Run 生命周期、集合
提交、数据库或 MCP 路由，符合 ROLE-001/002、DET-001/002 和本轮奥卡姆边界。

### 2.2 OperationSpec 仍是唯一能力事实源

类型化请求由同一个 `FigureDigitizationRequest` 模型派生 JSON Schema；该 Schema 同时被请求输出、
物化输入和最终打包输入引用。请求输出绑定了可见的 payload/context rule、精确
`paper_source` 上下文和插件工具。编译后的 Worker Schema 实际包含完整 source/axis/series 字段、
`curve.figure.request.internal_consistency`、`curve.figure.request.source_binding` 及对应 checker；未发现
提示词专用 Schema、Root 图名分支或第二能力表。

可选插件仍只有 `scidiscovery.plugins` 下的
`curve_figure_evidence = curve_figure_evidence.plugin:PLUGIN` 一个入口；五项 Operation 及所需窄组件均由
该入口一次声明。默认 core、curve-only 和 TCAD 组合不会注册论文图操作，符合 AUTH-003、PLG-001/002。

### 2.3 PDF 来源与正式重放可审计

PDF 工具只从 Operation 精确绑定的输入路径工作；它有页数、页内图像数、像素数和超时上限，返回
全文图像号、页内号、PDF object/generation、尺寸与规范化 PNG 摘要，只把预览写入当前 Run 的
`.operation-tools/figures` 并设为只读。请求 JSON 不含预览路径。

请求提交的上下文校验会从绑定的 `paper_source` 独立恢复所选对象并校验源摘要、对象身份、恢复图
摘要和尺寸；正式物化 Transform 再调用同一纯恢复逻辑重放，输出 source panel 为正式 Artifact。
因此临时预览不是证据来源，也不能绕过正式重放。

独立以冻结 PDF 第 6 页连续恢复两次，结果逐字节一致：对象 `240 0` 为 2100×812、PNG 摘要
`9bbd94220ee55c5d475223d4175c763d7767d7feb8f1242855c7850c23200815`；对象 `241 0` 为
1000×815、PNG 摘要
`88358eb5658c75cf7eddb3cb71fab5f2f8d5bf0d6e7252481193142adb19be5a`。第二项与 E0 冻结的 Fig.4
身份一致，未发现 `/tmp` 或旧 CSV 进入正式请求/产物父链。

### 2.4 ReviewSpec 和最终 parentage 精确

Intake Agent 的 `ReviewSpec` 只把 `scientific_intake` 映射到审查者同名端口；审查 Operation 的其余
端口显式列出同一来源、请求、manifest、report、panel、overlay 和所有 tables。Intake 和审查输出的
context validator 也分别声明了这些完整来源，不靠隐式 `all_inputs`。

最终 guard 同时核对：请求由精确请求 Operation 产生且以 source 为父；机械附件具有同一物化调用
指纹并以 source/request 为精确父；Intake 由新单输出 Operation 产生并覆盖完整家族；通过的审查由
独立图审查 Operation 产生并覆盖 Intake 与完整家族。控制面的通用 producer-contract admission 还会
核对当前 Operation version/digest 和精确 review edge。

除已有测试中的“缺审查”和“换 Intake revision”负例外，本审查另以临时控制面实例混入另一次
物化调用的 overlay，`operation_preflight` 得到 `guard_rejected/figure_parentage`；正向调用第五个
打包 Transform 实际产生 `CurveBundle` 与 normalization audit。未发现只为测试放行的 parentage
旁路。

### 2.5 旧集合生产路径已退出

论文图插件和相关生产测试中不再注册 `science.evidence.extract.figure.v1`、
`science.evidence.audit.figure.v1`、`worker_curve_figure_digitize` 或
`worker_curve_figure_validate`。保留的 `figure_worker_tool.py` 只有只读来源检查工具。诊断目录也不再
出现旧集合 Agent，因此不存在新旧两条正式数字化生产路径并存的问题。

## 3. 独立执行的证据

1. E1 聚焦测试：`79 passed in 29.52s`。
2. 干净 wheel 安装态领域工具探针：`1 passed in 39.50s`；实际从已安装目录编译请求 Operation 并调用
   注册的图源检查工具。
3. 冻结 Fig.4 PDF 同页连续恢复：两次对象、尺寸、PNG 摘要和字节数一致。
4. 临时真实 Root 路径探针：完整五操作合成链的最终打包成功；跨物化调用混入 overlay 在 preflight
   失败关闭。
5. `git diff --check`：通过。

仓库中没有 `scripts/validate_architecture_constraints.py`，因此未运行该脚本；改以完整阅读当前 33 项
约束、核对数量为 33，并按本轮受影响边界逐项审查。这不是 E1 阻断，但后续若恢复该自动校验入口，
不得把本次缺失脚本写成“已自动验证”。

## 4. 非阻断项与 E2 边界

1. 当前逐列颜色跟踪仍把成功序列全部写成 `qualified/eligible`，也不能表达 Fig.4 的种子走廊、局部
   定义域、遮挡共享支持和“红线可用、黑线未决”。这是计划已明确的 E2 P0，不得以本次 PASS 宣称
   科学保真度已通过。
2. 当前请求形状尚不能完整表达“缺少身份或标定时的结构化未决结果”；E2 在扩充局部定义域、遮挡和
   逐序列状态时必须同时闭合该科学不确定性表达，不能让 Agent 为满足必填字段而猜测。它不阻断 E2
   开始，但阻断 E2 结束。
3. 持久化测试目前只对最终打包做到正向 preflight，未把本审查执行的正向 invoke 和跨家族负例固化
   为回归。建议在 E2 改动该路径时一并固化，不需要为此新增测试框架、状态或注册表。
4. 安装态探针证明“已安装工具可执行”，尚不证明真实 Codex Agent 会选择并成功调用它；该证据按
   计划属于 E5，不能提前宣称。

## 5. 放行决定

E1 已解决原集合式 Agent 无法调度、请求合同隐藏、PDF 临时截图旁路、Intake producer 缺失和最终
审查父链不精确这五类结构阻断。实现局限在可选插件及复用的曲线实现，没有扩大核心控制面，也未用
兼容层或测试特判掩盖问题。

因此本审查以 **0 个阻断项通过 E1，并放行既定 E2**。E2 只能处理当前 Fig.4 连续线所需的科学
保真度与上述最小回归补强；不得趁机扩展通用图理解、Agent 集合、部署/UI、强隔离或新的控制状态。
