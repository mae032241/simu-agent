# Agent 上下文与工具开销修复计划 R3

2026-09-18 后续提案：[Root 上下文边界与可选预检修订计划 R1](ROOT_CONTEXT_BOUNDARY_REVISION_PLAN_20260918.zh-CN.md)接管 Root 读取、可选预检与等待的下一轮方案，现已完成源码、定向及隔离安装验证与独立审查，真实模型 token 对照因启动内存限制未完成，尚未部署；详见[实施记录](evidence/mcp-response-levels/ROOT_CONTEXT_BOUNDARY_IMPLEMENTATION_20260918.zh-CN.md)。下文已完成实测保留；“preflight/invoke 暂不改”等待办取舍由新提案重新评估，现行安装规则在实施前不变。

### 新增待办：实际科研 Worker 批量展开材料（2026-09-17）

用户已要求记录：[实测、触发行为与最小修复验收](evidence/mcp-response-levels/FIG4_BATCH_READING_TOKEN_20260917.zh-CN.md)。计划审查、TCAD 作者、源码审查的末次输入分别达到 52.0k、63.1k、68.3k；应优先核对科研任务中批量全量读取，而不是继续只裁剪静态前言。当前仅记录，尚未实施或证明节省。总体目标引用、完整原件访问、科学核查和执行权限必须保留。该真实节点证据补充此前简化样本的覆盖结论。


2026-09-17 最新状态：统一 MCP、25 个科学 Operation 对应 3 种平台权限角色，以及 Root 启动指令按需加载已安装。独立新进程实测初始输入 **20,178 → 17,077 token**；catalog 后 **21,882 → 18,911**，describe 后 **23,025 → 20,035**。这仅证明启动及发现路径，不能代表科研全过程。证据见 [启动指令拆分计量](evidence/mcp-response-levels/SCHEDULER_PROMPT_SPLIT_20260917.json)。Fig4 仍暂停。

### 独立全局扫描后的下一步（2026-09-17）

以[全局独立审计](evidence/mcp-response-levels/GLOBAL_AGENT_TOKEN_AUDIT_20260917.zh-CN.md)为当前优先级依据：11 处角色 Schema 路径修正已实施（编译核对实际影响 16 个 Agent Operation，含通过拼接继承提示的实验设计；原审计少计一项），随后有界补测一个非分析任务和一个失败续接场景。新写入兼容字段为 P2 候选，公共前言归位已完成源码修改（见下文），不直接按长度裁剪 Worker 接手材料；未发现需要新增通用机制的依据。该项导航修正的定向和安装检查已通过，四个已部署生产文件已核对一致，见[实施记录](evidence/mcp-response-levels/ROLE_SCHEMA_NAVIGATION_FIX_20260917.zh-CN.md)；历史兼容字段候选尚未实施。 非分析/失败续接的安装版真实模型覆盖已完成：分别 6/7 请求、累计输入 103,249/124,767，末次输入 21,066/21,864；均一次提交、无 Worker 错误，续接实际读取并保留草稿。这是不同场景的覆盖而非节省 A/B，未发现本样本需要立即修复的重复读取，见[覆盖计量](evidence/mcp-response-levels/NON_ANALYSIS_RECOVERY_MEASUREMENT_20260917.zh-CN.md)。

最新读取相关安装文件及工作区 results.md 已与源码逐字节核对一致。隔离模型样本已有收益/反例，生产全流程、其他角色及长期收益仍未验证；不能把两者混称“尚未验证”。下文原候选表保留探索历史，不代表全部仍待实现。

公共前言归位现已完成源码修改：19 个角色各减少 258～419 字符，25 个角色的总体目标/进展公共指令及输入端口均保留，输出合同除 Operation 摘要外不变；15 个定向用例通过。已部署，安装版 25 个角色边界核对和 2 个生命周期检查通过；本轮真实 token A/B 已完成：均 6 请求、一次提交，累计输入 103,402 → 103,288（仅 −0.11%），末次输入少 3 token；功能通过但未证明实质或稳定的节省。见[实测](evidence/mcp-response-levels/ROLE_PREAMBLE_MODEL_RESULT_20260917.json)。剩余明确候选是新写入历史兼容字段；其他角色与长链待按实际冗余取证。见[实施与边界核对](evidence/mcp-response-levels/ROLE_PREAMBLE_SCOPE_20260917.zh-CN.md)。

### 当前剩余工作（取代旧记录中的待办状态）

| 项目 | 当前状态与下一步 |
| --- | --- |
| 统一 MCP、静态角色、Root 启动指令 | 已实施、已部署、已有新进程测量，不重复改造。 |
| 新写入合同与 Operation 详情裁剪 | 已实施并安装；详情发现有实测，真实 Worker 的返工变化尚未验证。 |
| Worker 相关工具合同重复读取 | 已改为读取器自动记录最近完整合同，Agent 仅指定工具名；无差异链，提供 `--full`。不新增 MCP 或科学状态。定向及安装测试通过，隔离真实 A/B 已通过：末次输入减少 2,467 token（11.5%）；已核对安装文件与源码一致；完整交接待验收，见[自动复用修正](evidence/mcp-response-levels/TOOL_CONTRACT_READING_AUTOMATIC_20260917.zh-CN.md)。 |
| Worker 接手材料与完整交付成本 | 安装版隔离模型交接已完成：Worker 一次提交成功，Root 正确选执行诊断。Worker 净增 13,641，Root 净增 3,544；75.3% Worker 增量集中于角色/接手/Schema 两批读取。首轮已仅压缩三处分析提示，角色文字减少 26.7%，合同/科学 Schema 不变；安装版/源码对照已完成：Worker 最终输入少 4.4%，但多一轮请求导致两阶段累计输入增加 8.5%，整体节省未达标。该轮后的测试桥修正和 Schema 按需读取已完成，旧问题保留为成本反例；见[实测](evidence/mcp-response-levels/ANALYSIS_PROMPT_TRIM_MODEL_RESULT_20260917.json)。见[裁剪记录](evidence/mcp-response-levels/ANALYSIS_PROMPT_TRIM_20260917.zh-CN.md)。测试桥接不是原生传输 A/B，见[实测](evidence/mcp-response-levels/HANDOFF_MODEL_RESULT_20260917.json)。 |
| Root 读取正式成果 | 已定位空指针全文被当成索引、路径前缀猜测和全文后补读。公共合同/指南已修正，查询行为不变；定向与安装检查通过。同一封存报告的 Root A/B 已完成：两组均 4 请求、相同读取路径，累计输入 58,142 → 58,656（+0.9%），未通过节省验收。后续已修正绑定读取时机和分析 signal 的固定响应路径，保留 detail 入口；旧封存记录不变。新版同 payload 对照已通过本样本：Root 请求 4 → 3，累计输入 58,592 → 42,663（−27.2%），未再例行展开 detail，判断正确且无错误；不代表生产长期收益。见[最小修复](evidence/mcp-response-levels/ROOT_DETAIL_READING_FIX_20260917.zh-CN.md)；见[本轮记录](evidence/mcp-response-levels/ROOT_RESULT_READING_20260917.zh-CN.md)。 |
| preflight/invoke | 已在一次编排中复用原请求，减少模型搬运；没有证据要求再合并准入，暂不改控制协议。 |
| 等待、失败/恢复与历史接续 | 新 Worker 经新 Run 读取失败草稿的安装版覆盖已通过，草稿保留且一次提交成功，无重复轮询或提交重试。原 Agent 线程复用、生产科研长链仍未由本次测量验证。 |
| 全局 Apps 等启动开销 | 前次分项测得约 2.3k，但属于用户全局环境；不擅自关闭，也不冒称框架可删除。 |

合同读取真实模型 A/B 已运行，但**未通过优化验收**：完整组最终输入 21,639，差异组 21,640；两组第二次调用均未传 known_tool/known_digest，因此都返回完整合同。字段理解检查通过，实际节省未证明。见[实际结果](evidence/mcp-response-levels/CONTRACT_MODEL_AB_RESULT_20260917.json)。据此已将基准管理移入读取器，新版真实 A/B 已通过：诊断读取净增量 4,219 → 1,748，末次输入 21,531 → 19,064；见[新版实测](evidence/mcp-response-levels/CONTRACT_MODEL_AB_AUTOMATIC_RESULT_20260917.json)。不能把静态差异大小视为真实 Worker 效果；隔离 Worker→Root 交接已有验收，生产科研全流程仍未验收。

最新源码进展：只读输出 Schema 按需阅读的同源真实模型 A/B 已完成。两组一次提交成功、Root 正确选执行诊断；累计输入 275,912 → 176,799（−35.9%），请求 14 → 10，Worker 末次输入 −23.9%。按需组一次路径读取错误后自行恢复，无提交拒绝。单样本且存在请求/阅读路径差异，不宣称全部收益来自 Schema 或生产长期收益。Root 结果导航及 detail 后续修复现已完成，下一步以顶部独立审计排序为准。见[本轮记录](evidence/mcp-response-levels/OUTPUT_SCHEMA_READING_20260917.zh-CN.md)与[逐请求结果](evidence/mcp-response-levels/OUTPUT_SCHEMA_READING_MODEL_RESULT_20260917.json)。生产部署与 Fig4 全流程未由本次测量验收。

每项实施后做串行定向测试；跨安装边界补 wheel 验证。实际模型遥测可用时记录逐请求输入及新增量；不可用则明确区分参考分词计数与真实 usage。整体计划尚未全部验收。

下文保留 R3 的问题边界与候选原则。[R3 首轮及后续处置记录](evidence/mcp-response-levels/R3_INSTALLED_ACCEPTANCE_AND_FOLLOWUP_CUTS.zh-CN.md)是历史阶段记录；[R2 快照](evidence/mcp-response-levels/TOKEN_PLAN_R2_SUPERSEDED.zh-CN.md)只供追溯，不恢复已撤销的全量 shell 包装或预检票据方案。

## 1. 修正问题定义

本轮要优化的是：科研 Root 调度一次有意义的行动、Worker 完成工作、Root 读懂结果并选定后续方向的成本。框架开发会话中的源码阅读、安装排查和测试输出另行统计，不拿它们证明科研框架的主要开销，也不拿工程命令裁剪作为科研优化验收。

“用完即弃的材料不默认进入 Root”保留为交接原则，但不是全量包装工具、删减科学证据或新增总结角色的理由。Worker 为完成判断需要读取原始材料；需要减少的是无效阅读、跨角色重复和机械中转，不是所有原件阅读。

## 2. 当前证据能说明什么

| 证据 | 结论 | 不能推出 |
| --- | --- | --- |
| 工程窗口 73 条工具返回共 312,528 字符，其中 shell 类 304,363 | 该工程会话读取源码/测试/部署材料过宽 | 科研 MCP 或 Worker 的消耗占比 |
| 统一 MCP 首轮 A/B：12,717 → 12,726 input token | 单样本初始上下文未下降 | 静态工具 Schema 减少等于初始 token 节省 |
| 统一 MCP 后续发现样本：最后请求 18,577 → 14,328 input token | 该发现路径上下文减少约 23% | 全科研流程节省 23% 或费用同比下降 |
| author 缺口节点读取 21,486 → 1,937 字符（含导航） | 现有按需读取能显著减轻该节点 | 所有节点都省 91% |
| design 节点读取 14,872 → 9,740 字符 | 该节点仍展开了完整方法/变量等大字段 | 这些内容全无用，或可固定削减某个比例 |
| Worker 提示/Schema 静态较大 | 值得核对实际加载与重复 | 25 个角色同时进入每个 Worker、或 Worker 已被证明是最大项 |
| 新 design 合同仍暴露旧 validation_plan，但新提交要求 validation_intent | 有确定的契约混淆与返工风险 | 所有重试均由此导致，或其 token 占比已知 |

依据：[Root 节点](evidence/mcp-response-levels/ROOT_CONTEXT_MEASUREMENT.zh-CN.md)、[design 节点](evidence/mcp-response-levels/DESIGN_CONTEXT_MEASUREMENT.zh-CN.md)、[首轮 A/B](evidence/mcp-response-levels/INITIAL_CONTEXT_AB_MEASUREMENT.zh-CN.md)、[后续 A/B](evidence/mcp-response-levels/FOLLOWUP_CONTEXT_AB_MEASUREMENT.zh-CN.md)。字符和 token 分开；长历史存量、单轮增量、累计输入、缓存命中分别报告。

## 3. 实施顺序

### 第一步：做一次有界的科研交接成本核对

优先消费已保存的节点测量和运行日志，在程序中统计，不再把整段原日志输出给 Root。补齐一条“发现/读取 Operation → 绑定/创建 → Worker 接手/工作/提交 → Root 读取/选下一步”的完整记录。只统计用于下一步选择的读取，不创建下一轮仿真。

分别核对：

- Root：固定输入、目录/合同读取、请求与响应、轮询、决策所需成果读取。
- Worker：固定提示、assignment/Schema/原始材料实际读取、工具使用、成果输出、拒绝后重试。
- 交接：同一正文是否在提示、assignment、原件、提交和 Root 摘要中重复；哪些是必要的独立判断，哪些是机械复制。
- 指标：实际模型 input/cached input/output（有日志才报告）、净上下文增长、工具调用数、重复读取、失败/重试及最终任务是否完成。

历史记录必须标注运行版本，不能冒充最新版本效果。缺少最新可比记录时，用开发夹具做一个有界、无求解器副作用的同任务对照；不为统计启动完整科研闭环。Fig4 保持暂停，不读取实例来继续研究。无法取得真实 token 遥测时，只报告已测字符与未知项，不编造框架占比。

退出条件：形成一张按角色和动作划分的成本表，选出一个已证实且可避免的最大项。不扩展为通用遥测系统，也不等待覆盖所有角色后才修复。

### 第二步：在现有高价值候选中，只实施第一项有证据的修复

以下是候选与依赖关系，不是已经测出的成本排名：

| 候选 | 改动位置与方式 | 必须保持 |
| --- | --- | --- |
| 调用合同冗余 | `mcp_response_views.py`、compiled catalog 的原投影；去重复机器元数据，保留选中能力完整调用规则 | 同一编译来源、端口/边界/审批预算完整可见，无第二份手写合同 |
| preflight/invoke 重复 | `mcp_root_operation_routes.py` 与对应调用提示；若实际重复成本成立，正常 invoke 内部完成一次准入，preflight 作显式诊断 | 冻结配置、精确绑定、幂等并发、恢复预算与审批；实现验收前仍按现行两步规则运行 |
| Worker 新合同混入旧写法 | `operation_declaration.py`、`schema/experiment_intent.py`、`schema/layered_diagnosis.py` 及生产/消费点；新写入只给当前格式，历史在原读取边界处理 | 旧封存记录仍可读取，不能自动补 pass；错误仍准确 |
| 接手材料重复 | 平台提示生成、assignment/task view 原生成点；删除重复正文，原件精确引用，已有机械字段由程序传递 | 不削弱 Worker 对当前目标、证据与任务的理解，不新增 Agent 手写 handoff |
| Root 读取成果过宽 | 复用 run_status/output_paths/导航，必要时由原领域投影选择已有正式字段 | 结论、证据范围、限制、假设评价、剩余矛盾足以决定演化/设计/诊断/停止，不只剩 verdict |

若某个候选未观测到实际冗余，不为完成表格而修改。合同一致性缺陷可作为独立正确性修复，不谎称其 token 收益已测出。

### 第三步：用同一个节点验证，再决定下一项

- 相同模型、推理强度、任务输入和上下文起点，串行比较一次完整交接，不比较长旧会话与新短会话。
- 全部往返和新增上下文都计入，不能只缩短首页却迫使 Worker/Root 连续补读。
- 看是否减少重复读取、机械抄写和拒绝重试，同时仍能正确判断科学结论与后续分支。
- 小样本只报告小样本收益；需要证明稳定行为时重复相同有界场景，不用一次幸运输出宣称长期改善。
- 通过后才处理成本表中的下一项。已有统一 MCP 不重复改造，提示文字裁剪降为随相关修改完成的附带工作。

## 4. 明确不做

- 不把工程 shell 输出治理列为科研框架第一优先级，不新建通用 shell 捕获器。
- 不全量重写 MCP 返回，不增加服务、状态机、响应缓存数据库、预检票据或强制摘要 Operation。
- 不用控制层生成科学解释，不把建议字段自动转成研究路由。
- 不为省 token 删除独立审查、授权、来源、准确错误或必要原件。
- 不追加“响应太长就拒绝任务”的校验，不为提高缓存命中发送暖缓存请求。
- 不将 17.7 万 token 的混合开发会话归因于框架科研流程；历史存量不会因一次代码修改自动消失。

## 5. 验收和资源边界

首先验证被修改行为的正常路径、真实错误、缺失/空/遗漏、原件可读和权限边界；按改动选择现有定向测试。串行执行，进程树内存上限 768 MiB，不跑全量套件或求解器。跨生成配置/安装边界时补隔离安装检查。

交付必须分别说明：源码是否完成、是否部署、行为是否通过、真实 token 是否测得。上一轮 7.63% 的固定提示字符缩减不替代这些验收。研究结论、恢复和诊断能力不得退化。

首轮执行证据：[交接核对与设计合同修复](evidence/mcp-response-levels/R3_HANDOFF_COST_AND_CONTRACT_FIX.zh-CN.md)。后续已逐项检查接手材料、Root 读取、新输出合同、Operation 详情、预检调用、工具合同复用、等待和历史接续；仅保留有依据的裁剪，不为完成候选表重构准入或增加交接层。详细处置与未完成事项见上述后续执行记录。未开启新科研 Run 或求解器执行，已有若干有界真实模型样本；其他角色和生产长期效果仍待验证。
