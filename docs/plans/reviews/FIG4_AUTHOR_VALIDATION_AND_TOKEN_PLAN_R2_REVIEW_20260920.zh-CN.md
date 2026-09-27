# Fig4 作者验证与 token 整改计划 R2：独立工程复审

结论：**REVISE（限定 WP1 的三处设计补齐）**。无已证实 P0。R2 已实质关闭前轮其余四项计划问题；成功诊断交付从未选路径推进到明确附件方案，但来源信任锚、诊断身份投影和可交付字节预算仍需落到现有接口。无需先实现才准许计划通过，也无需扩建通用框架。本结论不代表科研或实现验收。

审查对象：`docs/plans/FIG4_AUTHOR_VALIDATION_AND_TOKEN_REMEDIATION_PLAN_20260920.zh-CN.md`；核实 SHA256 为 `c311f343d9eee16aba3ea8d39ee1c706704f5bc1603acdc949288b0044d9b950`。R1 快照 SHA256 为 `d61575bf921f7c021e609926d2aafbc4ecf9270b7e48f51ee9bfcf65284a4104`，与前轮报告绑定一致。

本次为新的独立 reviewer，只读核验适用 AGENTS、R2/R1、指定三个工程证据 JSON 和相关源码/测试定义，使用 scid-cross-boundary-review、karpathy-guidelines。没有运行测试、模型、科研 MCP、solver 或部署，没有把 327 项既有脏记录当作本轮差异。唯一写入是本报告。以下源码位置均相对仓库根。

## P1-1：控制生成要求尚缺作者工作区之外的可验证来源锚

计划位置：§2 第42–44行、§5 第103行。

源码证据：`plugins/tcad_artifact/tcad_artifact/local_debug_service.py:226–340` 将诊断记录、报告和原始输出写进作者工作区；`operation_workspace.py:748–759` 从该目录读取报告。`plugin.py:378` 允许 author 使用 inherited_prototype 原生 shell。`src/scidiscovery/artifact_agent/service/local_workspace.py:501` 的写入函数防止符号链接等不安全写入，并设置文件模式，但这并非独立于原生作者的内容真实性锚；同一身份拥有文件时，0400 本身不能阻止 chmod 后改写或在可写目录替换。现有工具状态位于 `mcp_local_worker.py:86,609` 的进程内 `_tool_state`，而 `src/scidiscovery/operations/workspace.py:86–102` 的 finalizer request 没有此状态读取接口。

可达问题：若只在 `diagnostic-*.json` 中增加输出 sha256，再让 finalizer 从同一工作区读取报告和输出，作者同时替换两者即可保持 hash 自洽。它证明两份工作区字节一致，不能证明字节来自那次受控调用。R2 正确禁止“只凭同名文件”，但尚未选定 finalizer 实际如何取得不会随作者文件一起被改掉的来源记录。新增跨 Run 附件会把这一空缺固化为 reviewer 所信赖的原件来源。

最小修订：明确复用现有开发调用/服务受控状态中的哪一份记录作为权威、finalizer 如何按当前 Run 与精确调用读取，并把收集时的输出路径/字节 hash、诊断模式、源码与声明及入口绑定纳入该记录。工作区报告只是可读副本，最终封存前与权威记录核对；任一缺失、替换或服务重启丢失锚，明确为无法证明来源，而不从报告文件自我恢复可信性。可采用局部依赖注入/已有受控存储入口；不要求新数据库、签名体系或通用状态机。若现有 native 权限有能够阻止替换的实际独立保护，应在计划指出该入口与边界，不能仅引用文件权限。增加“报告和输出一起篡改”的窄反例即可，无需测试恶意主机管理员。

## P2-1：须明确诊断 hash 的排除项，避免自引用和历史失效

计划位置：§2 第43–45行。

源码证据：`project_packager.py:668–682` 用 `project_debug_sha256` 验证 attestation；该函数当前仅排除两个 attestation 与 `materialization_report`，其余模型字段全部进入诊断项目 hash。`local_debug_service.py:220` 在诊断启动时记录它。`project_packager.py:1139–1145` 则以完整序列化项目计算 `PackagedTCADProject.project_sha256` 和 package digest；`1149–1177` 的生产归档只写 `project.files`、解析输入及 job。这些身份不能混为一谈。

可达问题：附件内报告包含诊断项目 hash，而新增附件若仍进入 `project_debug_sha256`，就出现报告生成后挂入附件导致 attestation 失效，甚至形成自引用。仅说“不进入源码身份”不解决这个 hash，因为它还覆盖声明与调用。即使附件为空，Pydantic 默认新增 `development_diagnostics: []` 也会使旧项目的诊断 hash 改变。R2 的旧字节不变原则正确，但不能只在最终 Artifact 写出时排除空值。

最小修订：写明 `project_debug_sha256` 显式排除 `development_diagnostics`（包括空默认值），保持原 source/declarations/invocation 诊断投影；完整新 Artifact 身份包含附件，附件变化产生新对象且不继承旧 review。明确运行包现有完整项目 hash 可以继续因新项目变化，而 tar/job 内容不携带附件；不要为了缓存命中改写既有 reviewed package 的绑定含义。旧项目的解析、诊断校验及相关 canonical 序列化均须保持原兼容规则。无需设计新 hash 算法或迁移历史对象。

## P2-2：诊断可收集上限高于成功成果可容纳上限，缺少前置选量规则

计划位置：§2 第40、43行；WP1 第103行。

源码证据：`plugin.py:390,405` 的 author 单成果和总输出都是 **8 MiB**，最终 envelope 在 `operation_workspace.py:802–806` 再校验总限额。`debug_adapter.py:42–58` 允许 initialization 输出总量最高 **8 MiB**，单文件也可达 8 MiB；`project_packager.py:719–735` 的 AttemptFile 支持原始 8 MiB，base64 编码约增至 10.67 MiB，尚未计算源码、控制报告与 JSON 转义。现有 gap 的 `_attempt_files` 还允许较大的局部收集预算，不能直接作为成功输出可装入的证明。

可达问题：当前允许的一份较大二进制诊断，在求解成功、预算已经花费后，必然无法封存在 8 MiB 的成功成果内。R2 规定“不提高限额、超限报错”能防止假成功，但没有避免这种可以事先知道的无谓拒绝，也没有说明如何从多个受控调用中选出“本次验收所用”集合。

最小修订：计划固定确定性选集依据（当前验收采用的准确调用及其 output_names，旧失败/旧源码记录不自动全收）；在既有启动/输出选择入口暴露或核算最终 envelope 的剩余预算，计入 UTF-8/JSON/base64 开销，选择可交付的小量原件。不能为了尺寸静默删掉所依赖原件；无法在预算内获得足够观察则保留明确缺口。无需新增附件选择表、额度服务或放宽总限额。实现验收覆盖一个小诊断成功跨 Run 和一个收集许可内但封存不可容纳的边界，证明后者得到及时准确的限制说明。

## 前轮五项逐项结论

| 前轮问题 | R2 计划层状态 | 依据 |
|---|---|---|
| P1 成功诊断原件跨 Run 可达 | **部分关闭** | 已选 `development_diagnostics: tuple[AttemptFile, ...]`、reviewer只读恢复、元数据剔除正文；仍有上述来源锚、hash和预算补齐项。 |
| P1 动态验证负控不足 | **关闭** | §5.1 要求同 exit 0/文件齐全的正负观察、作者自主选择诊断、真实封存后独立 reviewer 判断；不把答案写进材料，失败不得以 token 收益遮盖。 |
| P2 768 MiB被误称硬隔离 | **关闭** | §5 wrapper 与 `compiled_worker_process_guard.py:91–139` 一致，明确采样和追踪边界、超限停止后续模型、缺测分层。 |
| P2 summary/detail及invoke兼容不明确 | **关闭** | §4 保留 detail 原件，仅精简 summary；按四类 executor 保留各自身份/绑定/审批信息。真实分支见 `mcp_root_operation_routes.py:235–276`；现有 detail 原样断言见 `tests/operations/test_mcp_response_views.py:19–32`。 |
| P2 引用缓存/全根扫描 | **关闭** | §4 第82行明确无缓存、无全根 manifest 扫描；沿用精确失败、当前权限与计费，unknown 不被升级成永久不可用，符合 `reference_access.py:210–266,433–464` 的职责。 |

“关闭”指设计问题已回答，不代表实现已完成或测试已通过。

## 可继续实施的设计与仅属实现验收的要求

附件方案总体合理：现有成功 Artifact 已是 reviewer 的声明输入，复用这个输入与 AttemptFile 编码比新增 Artifact 类型/绑定端口更小。现有 gap 恢复函数可复用安全路径和解码逻辑，但不能直接调用全 reports 扫描。当前无更简单的既有成功附件入口能自动补齐来源与跨 Run 交付。

R2 已要求附件不进入 `files`、生产 tar/job，不进入 `deck/project.json` 默认正文；应据此修改 `operation_workspace.py:457–465` 当前仅剔除 files 的元数据构造。revision 旧附件放历史只读导航，不能被 `_author_metadata` 或恢复流程升级成当前证明。一般输入文件仍可能保存完整不可变 Artifact，按需显式读取全文合法；默认 assignment/Run 状态应走导航或选定字段，不得为了省 token 改掉完整原件。这些已有要求足以作为实现验收，不另列计划阻断。

正负控应通过工具选择后交付观察，不能提前给 author “负例无效”的答案。两版本任务固定，不要求旧版本拥有新附件能力：旧链无法跨 Run 提供原件本身就是待记录的基线缺陷，仍记录其真实退出/错误，不补造可比成功。每组至少两对、交替顺序、固定模型/预算/fixture、样本全保留、去重及 compaction 分段均可实施；WP0 冻结时将正负任务配比与作者/审查子成本写入现有采样清单即可，不需新测量框架。

三个指定工程 JSON 支持累计输入20143380、缓存19499136、344请求和 Root 净增长80893的口径；它们没有旧版完整 Worker A/B，也不能替代峰值窗口测量。R2 正确区分①跨 Run 工程链、②作者/reviewer 行为、③token、④真实 SProcess 动态能力。768 MiB缺测只影响对应证据结论，不能伪称②③通过，也不应阻止已完成的①如实报告。

开发授权、独立审查、网页审批与求解预算边界均保持原合同；部署或生产执行不由本计划授权。真实连续边界/J是否成立仍由科学 Agent 判断；禁止新增 Time 字符串或非零 J 机械门。权限不足或预算不能获得区分性观察时交付 implementation_gap 合理。无需提前运行科研证明计划通过。

## 最小下一步

仅在 WP1 补三段：权威记录如何到 finalizer；诊断 hash/完整 Artifact/运行包身份的明确投影；现有 8 MiB 内的选集和前置预算处理。随后对这些增量复审即可；不要求扩大 WP2–WP4、不要求现在运行模型或 solver，也不要求重写已有框架。
