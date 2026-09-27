# 2026-09-12 独立工程复盘与可用性审查

审查日期：2026-09-12。审查者未参与本轮实现；独立读取当天证据并追踪当前源码。没有修改生产代码、测试、安装或控制状态，没有调用科学 Operation，没有重新判断科学数值。

## 按影响排序的发现

### F1 · P1 · 当前线上恢复缺陷仍然存在；源码修复与真实恢复验收尚未闭合

**已确认的线上问题，候选源码已修，部署及修复后真实恢复未验证。** `fig4_curve_diagnostic_continuation_1` 的 preflight 通过，Worker 打开时因 `preserved evidence receipt differs from its origin` 失败，尚未开始计算或提交。它确实消耗了一个恢复尝试；零提交拒绝不能说明任务正常进入了工作区。

当前源码将两件事分开：按原注册 producer 检查旧收据是否真实，再检查旧来源是否适用于新绑定。有效但当前不适用的成果继续保留为草稿。位置为 `tool_evidence.py:554–585`，打开失败的落点为 `runs.py:505–513`。原别名回到原 producer 解释，避免把中间恢复 Run 的重排别名当成旧来源。这是正确的职责修复，没有必要要求新分析绑定所有旧依赖，也不能把真正损坏的旧收据作为可信证据导入。

本轮隔离三 wheel/stdio 证明这条修复路径可运行；线上真实成功的另一 Run 使用的是更新前代码且未走失败草稿恢复。因此，**不能将真实曲线分析 completed 写成这项恢复修复已在线验收通过**。旧现场错误没有记录索引，不能事后断言具体是哪条依赖缺失；代码复现解释的是相同机制及另一跨轮别名缺陷。

最小处置是安装候选、重启并核对实际代码，然后以新 Run 验证一次有意义的有限恢复，确认打开、未采用清单、可编辑副本及局部复用。旧失败 Run 保持失败，不增加全局准入规则，不重跑已经完成的 60 个拟合单元。此项是部署后使用恢复功能的验收条件，**不是反对部署修复的理由**。

证据：[现场失败控制返回](live-recovery-open-failed.json)、[隔离安装脚本](installed_smoke.py)、[安装结果](installed-smoke.json)、[现场验收](LIVE_VERIFICATION.zh-CN.md)。源码：[tool_evidence.py](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/src/scidiscovery/artifact_agent/service/tool_evidence.py:554)、[runs.py](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/src/scidiscovery/artifact_agent/service/runs.py:505)。

### F2 · P2 · 未采用收据的提示只覆盖直接上一轮，连续恢复仍有来源交接缺口

**源码确认的适用边界，未运行新复现；不构成本次部署阻断。** 可达场景是：A 保存证据；B 从 A 恢复，但不绑定该证据依赖，因此合法跳过采用；B 再失败；C 从 B 恢复，即使重新绑定了 A 的依赖，也只枚举 B 的 `tool_evidence`。B 没有采用的 A 收据不在这个表中，因此 C 不会自动采用它，`recovery_evidence_status` 也不会再列出那条更早的未采用记录。

位置为 `tool_evidence.py:530–534`、`:545–547`、`:582–585`。B 的新快照只把 B 的收据写入 `output/tool-evidence.json`（`:415–425`、`:464–474`）；分析快照仅遍历 output/scratch，不递归复制 recovery-draft。已有 recovery proof 保存的是计算尝试及其绑定，不是所有未采用收据的清单。

这不是 A 的原件或注册 Artifact 被删除，也不是草稿绕过控制自动成为证据：A 的恢复源仍保留，安全 scratch 副本还可能继续传递；但 C 的入口不再交付完整的未采用历史。调度者需要回到 A 的恢复源，绑定真实依赖并遵守预算；若已有相应封存成果，则可显式绑定那份成果及其配套清单。不能让 Worker 从私有存储自行找回旧收据，也不能仅因字节相同就更换来源身份。

最小建议是先明确当前字段为“直接恢复来源”的采用情况，续接时保留原来源选择；若实际多轮任务反复触发，再利用现有恢复清单保留有界的遗漏来源指针。无需通用依赖图或自动提升旧证据资格。当前测试的多轮分支位于 `test_analysis_continuation.py:187–194`，只在 `keep_original=True` 时继续下一次恢复，**没有覆盖先不采用、再继续恢复的分支**。

源码：[状态投影与采用入口](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/src/scidiscovery/artifact_agent/service/tool_evidence.py:523)、[快照范围](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/plugins/curve_score/curve_score/analysis_workspace.py:174)、[现有组合用例](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/tests/operations/test_analysis_continuation.py:158)。

### F3 · P2 · 原生观测得到实质改善，但仍不是所有错误或所有资源的完整记录

**旧线上漏记已有现场证据；新补丁修复了已完成启动器命令之间的错误历史。** 最新真实分析的封存方法报告了一次相对输出路径 `FileNotFoundError`，修正后局部重试；Root 只保留最后成功的原生命令。新实现保留最多八项错误，成功不擦除之前失败，Root 只投影错误类型、退出状态和有界日志指针。`local_process_observation.py:108–135` 与 `mcp_root_run_routes.py:37–47` 在这一点上正确，未把工程错误变成科学拒绝或提交前提。

仍有三个明确边界：

- 直接平台调用不经过 launcher；脚本模式在 `:189–199` 检查脚本路径及取得锁，早于记录建立。这些入口自身出错也不会进入已完成命令历史。不能把 `coverage=local_launcher` 或空摘要解释成完整无错证明。
- `effective_timeout` 在 `:67` 仍以 1 MiB 读取 assignment；超过上限时 `:71–72` 回退到调用者 timeout，**不再按 Run 截止时间及封存余量裁剪**。assignment 本身由 `run_assignment.py:34–94` 内联工具合同，工具合同描述/Schema 没有同一个 1 MiB 总限额；所以较大合法插件合同可触发此路径。显式 timeout 仍生效，控制层 Run 到期判断仍存在，不等于无限执行或逾期成果可提交。当前约 33.9 KiB 的测量夹具没有触发；这是本轮之前已存在的边界，未运行新复现。
- launcher 的 512 MiB 是 `RLIMIT_AS` 每进程地址空间限制（`:153–156`）；`RUSAGE_CHILDREN.ru_maxrss` 是该 launcher 观察到的子进程高水位，不是整个科学 Run 的进程树同时峰值。工程 `check.py` 另有进程树 RSS 看门狗。两者不能互相替代证明。

最小建议是统一 launcher 与已生成 assignment 的读取边界，保留明确的预算来源；仅在实际有诊断需要时补记录 launcher 的入口失败。报告继续区分工程测试资源、原生计算、Agent 阅读和推理时间。缺少完整观测不应成为科学任务准入或提交条件。

证据：[真实完成返回](live-curve-completed.json)、[启动器所属测试](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/tests/operations/test_local_process_observation.py:121)、[启动器](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/src/scidiscovery/artifact_agent/service/local_process_observation.py:62)、[assignment 生成](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/src/scidiscovery/artifact_agent/service/run_assignment.py:34)。

### F4 · P2 · 有界研究任务已经可完成，整体科研目标与原执行缺陷仍未完成

**封存结果明确支持的剩余工作，不是新的框架校验问题。** 今天完成了 60/60 形貌单元及三图，后续诊断完成两次真实曲线工具调用并报告查看两图；但 48 个数字化角点全部不合格，正式带不确定度的判断及机制识别仍不可判定。原外部执行的 failed/97 与无 `_fps` 声明路径不匹配也没有被本轮源码修复。

不能用 completed、零提交拒绝、工具 computed 或中央曲线差异替代整体目标完成。下一步若要不确定度判断，应由科学证据/设计角色处理现有方法缺口并独立审查；若要继续执行，则对原声明路径做有界作者修正及匹配审查。该结论来自封存输出，审查者没有重新计算或评价科学方法。

证据：[Fig.4 真实闭环](../scheduler-attempt-budget/LIVE_FIG4.zh-CN.md)、[最新封存状态](live-curve-completed.json)。

## 范围与基线

仓库为 `123/scidiscovery-e5.2`，HEAD 为 `2edac5d317a74056869a567bd0daa7f556ecbc85`，工作树含大量此前未提交改动。**没有把 HEAD 全 diff 归为今天或本轮新增。**

当天事件链以 `docs/plans/README.md` 的当前入口及五组证据为依据：operation-validation-reaudit、analysis-work-preservation、scheduler-attempt-budget、analysis-continuation-minimal、analysis-closeout。最新回合精确范围是 [baseline.json](baseline.json)、[changed-files.json](changed-files.json) 和 [implementation.patch](implementation.patch) 所列六个生产文件、两个测试文件；patch SHA256 为 `f9dab09a8d5313cf6341b605292523a24918e2113c5a01c1406a9b2ea8b19c48`。父调度者并行完成证据索引与八文件 after_sha256 核对，本报告独立承担源码语义审查，不把该索引核对视为科学复核。

使用 `scid-cross-boundary-review` 与 `scid-change-scope-checks`，检查了：共享 workspace 入口及 native/legacy 返回；scratch 恢复与只读原件；launcher→Root 摘要；工具注册、采用、快照、Worker open 与 submit；历史案例映射→工具请求→实际收据→最终来源引用；恢复预算预检/创建；资格检查与历史分析读取；wheel、插件 entry point、安装脚本及真实 stdio 入口。没有覆盖无关平台全矩阵。

## 今天问题的分类与根因

| 类别 | 已确认事件与根因 | 修复效果及应保留的边界 |
| --- | --- | --- |
| 输入与输出职责混用 | 曲线目标/计划配对拖到提交；历史工程包读取触发执行资格；图像 unresolved 被要求已有完整恢复字段；机械副本让 Agent 手抄 | 目标/计划输入检查移到 preflight；历史读取保留结构与身份、执行资格显式调用；缺口可以保存；唯一来源字段机械生成。输出对新主张引用、案例与收据的一致性仍必要 |
| 不必要的输出关系门槛 | 同名 evidence/source_references 双表约束；已有四条 PLX 案例关系没有复用，使真实续接临近截止重复填表 | 删除冗余双表门槛；从 exact prior/manifest 及同 plan/package cohort 生成条件性映射。新科学 basis 不覆盖，冲突不猜测 |
| 恢复与接口问题 | 默认工作保全范围不足；恢复副本/父目录只读导致脚本或运行锁写入失败；新活动观测与历史日志需分开；不存在的恢复路径被公布；旧来源缺失被当成损坏 | output/scratch 有界保全；副本可编辑、原件只读；跳过活动观测目录；可选路径依实际存在返回 null；不适用与损坏分开。既有快照已排除非白名单 lock/stop，不能将复制旧锁视为已定位根因；仍不能恢复从未写盘的内存数值 |
| Agent 使用及任务设计 | 约八分钟后才落下完整脚本；正值检查和 tuple/dict 错误；数值之后才导入绘图库/写数值；已知一次约354秒，剩约303秒仍从头重算 | 逐单元保存、绘图只读检查点、依赖在昂贵计算前检查、按剩余时间预留封存。不能简单归因缺 matplotlib，也不能靠更多重试掩盖任务过大 |
| 调度预算 | 默认累计两次使仍有有效草稿的局部补算无法继续 | 显式 max_attempts 成为新请求的一部分；同一请求预检/创建一致，旧 Run 不变，第三次真实完成。扩额不增加单次时间或自动证明研究可完成 |
| 观测与诊断 | MCP 摘要看不到原生异常；旧 launcher 后续成功覆盖先前失败；输出定位只给 $.payload；旧恢复错误无记录索引 | 具体字段/记录位置和有界错误历史改善可修复性；旧历史仍有信息缺口，不能倒写为已知或无错 |
| 科学不可判定 | 全部角点失效、缺合格不确定度合同及区分机制的对照 | 允许封存有限/负面结论是正确行为。控制层不能自动换角点、排序删行、生成物理判定来“通过” |
| 安装差异 | 同一天经历多个源码、隔离包、用户安装版本；最后成功 Run 未使用最新收尾补丁 | 每个结论绑定其实际版本；最新源码通过工程验收不等于生产已修复 |

真实拒绝也应区分：原执行计划与回顾性计划绑错的 `result_analysis_parentage` 拒绝、派生文件不在 `scratch/...` 的发布拒绝、`comparison_keys` 错指未注册评分记录的拒绝都有必要的身份或文件边界目的；当时提示不足，部分机械填表本可避免。最后一个 Run 零提交拒绝不能覆盖全天这些事件。历史“续接入口没有交付草稿”的归因已由后续时间线收窄为未证实：当时打印 assignment 没有读取该字段。

证据：[职责移位完成](../operation-validation-reaudit/RESPONSIBILITY_PLACEMENT_COMPLETION.zh-CN.md)、[安装后实际事件](../operation-validation-reaudit/RESPONSIBILITY_PLACEMENT_POSTINSTALL.zh-CN.md)、[超时原生命令时间线](../operation-validation-reaudit/ANALYSIS_TIMEOUT_ROOT_CAUSE.zh-CN.md)、[工作保全实施](../analysis-work-preservation/IMPLEMENTATION.zh-CN.md)、[预算修复与现场](../scheduler-attempt-budget/LIVE_FIG4.zh-CN.md)。

## 修复正确性与边界核查

**共享入口与恢复副本。** `analysis_workspace.py:44–74` 使用既有安全快照筛选，经 no-follow 工作区写入生成 0600 文件/0700 目录，跳过整个原运行观测目录。`:99–143` 对入口按实际 UTF-8 字节有界追加，短摘录仍指向原文；`:160–170` 将可选恢复路径统一为实际 coverage。`mcp_local_worker.py:247–266` 只有存在 start 文件及冻结合同才走简明接口，否则保留旧合同回退。新入口没有替代原始目标、完整 Schema 或工具合同。

**工具证据采用与打开。** preflight/draft 校验在 `runs.py:1320–1375` 验证实例、Operation、backend、失败恢复源和冻结文件清单；打开在 `:505` 才执行收据采用。因此 preflight 通过不承诺一切存储和原件在打开时必然可用。最新修复没有把额外依赖要求塞回 preflight。逐条采用从原 producer 解别名，按真实 Artifact 身份判断适用，并在 `tool_evidence.py:601、606` 把已经采用的父证据加入可用集合，后续派生产物可继续采用。它没有按文件同名或相同 bytes 跨 Artifact 身份复用。损坏字节、错误 source_ref 的负控仍拒绝；工作区伪造 receipt 也不是控制注册表。真正的 origin 错误是工程失败，改写科学输出不能修好它。

这里的完整性依赖现有控制注册表和不可变 catalog，不是在有权篡改控制数据库的攻击者面前重新证明所有历史；本轮没有声称新的加固隔离能力。只读草稿、可编辑副本、可信工具证据和允许执行是不同边界，源码没有因恢复成功而授予执行权限。

**机械案例映射与最终封存。** `analysis_bindings.py:23–89` 要求精确 prior/manifest、相同 plan/package，原数据及 evidence basis 均可按 Artifact 身份映射；多案例歧义留为不可继承。`:118–161` 只补机械缺省字段，不覆盖显式新 basis，且尊重原输出字节上限。`result_analysis.py:224–296` 在实际 score/diagnose 前按同一来源视图解析 case，原请求没有被赋值重写；提交在 `:420–455` 核查本次主张和 locator。`calculation_sources` 核查受控尝试与来源，而不重算数值。由于历史 basis 仍是条件性科学主张，机械继承不等于新增独立审查通过。

**职责移位有真实代码支撑。** 曲线输入关系在 `science_operations.py:126–136` 的显式输入检查；合同输出检查仍验证新选择的编译结果。`ReviewedDeckPackage._package_identity` 保留能力/槽位关系，执行资格位于 `project_packager.py:850–854` 的显式函数，打包/执行消费者继续调用，TCAD 分析读取不再调用。`result_materialization.py:33–73` 生成唯一来源副本及已有固定含义的 handoff；不由控制层选择下一科学目标。图像请求上下文在 `figure_science_operations.py:164–175` 对 ready 另行要求完整信息，unresolved 仍须匹配原文件。

**恢复预算。** `runs.py:1377–1416` 严格接受正整数，以恢复树计算累计 used，显式值写进新请求/策略并由后继继承；创建事务再计数。真实闭环证明一次合理扩额能利用已有50个单元仅补10个；它没有证明无限续接或增加预算就是最佳科学动作。

**安装路径。** 隔离 smoke 先建净发布目录，再构建核心/curve_score/tcad_artifact 三 wheel，通过隔离解释器编译 installed entry points，实际以 `python -I -m ...mcp_local_worker` stdio 打开和提交，并比较安装字节。不是纯源码 import 冒充安装。它仍以手工工程 fixture 构造输入和 Root runtime，未走用户机器 systemd、socket/proxy、UI 绑定及真实 Agent 全链。生产 `deploy/install.sh:480–505` 安装所选包，`:519–549` 编译 installed catalog，`:784` 后生成平台配置；三包安装路径与生产选择机制有对应关系，但这不是执行过完整生产 reinstall 的证据。

## 验收证据能支持到哪里

| 证据 | 可支持的判断 | 不支持的外推 |
| --- | --- | --- |
| 最新定向日志 | 74项恢复/观测/诊断通过；扩展167项通过；最后两所属文件29项通过，含额外旧快照路径用例；合计242个不同通过项 | 不能把重复运行相加；不能称全量套件通过 |
| 扩展4失败及基线复现 | 本轮基线同样失败：两处旧异常文本、一处旧 preflight 完整字典、一处旧符号链接错误文本；不是本轮新增回归 | 它们仍是未清理的测试债务，不能删除日志或永久标“环境问题” |
| check.py/JSONL | 检查串行，512 MiB地址空间及进程树看门狗、150秒单次；最高300875776 bytes，约286.94 MiB，无 watchdog stop | 不证明真实科学 Agent 全进程树峰值，更不证明512MiB合法输入的全链内存上限 |
| 50 Operation源码编译、45 Operation三包安装 | 所选声明编译及实际安装模块/stdio路径可用；前一轮独立审查发现的大包2MiB隐性限制已关闭 | 五插件编译不等于五插件全现场；三包 smoke 不证明未安装插件及所有后端 |
| installed_smoke.py | 失败后恢复、可编辑副本、仅补图、未采用收据提示、历史映射、原请求不变及封存可组合 | 极小数值/2×2图片工程 fixture 不证明真实复杂科研复用正确；本轮现场仍须补恢复 |
| 新真实曲线 completed | 同生产 Run 两个已注册 worker_tcad_curve_diagnose calculation_record，零提交拒绝，有限报告封存 | 不证明最新补丁已部署；不证明全科研目标完成或整个过程零错误 |
| 956 vs33907 bytes | 同 fixture、同 Run、同输入的简明/旧返回接口 A/B；约97.18%少返回字节 | 不证明 Agent 总阅读量、总推理量或耗时按同比例下降 |

本审查只读日志，没有运行新测试、构建、压力用例或 solver，避免和其他活动叠加资源。观察了 `check-1789215111793835429.log`、`check-1789215197075834517.log`、`check-1789215368078306832.log`、`check-1789216118191043062.log` 及最终 smoke 记录；`git diff --check` 为实施者已保存的通过结果。本次新增报告不改变生产证据。全量套件未跑，一项压力测试明确 deselected；没有将它们写成通过。源码路径可证明的 F2/F3 条件分支没有另行运行复现。

最新 [控制返回](live-curve-completed.json) 的 `calculation_records=[]` 与两个已注册计算对象并不矛盾：主结果使用 `calculation_ref` 引用。Root artifact metadata 能证明实际注册工具及同 Run 来源；原请求省略机械字段、读两图来自封存方法说明，Root 未直接读取 opaque 请求正文或重新验证图像理解。隔离 stdio 则有确定性原请求相等断言。两类证据互补，但强度不同。

此前 [独立实现审查](../analysis-continuation-minimal/IMPLEMENTATION_REVIEW.zh-CN.md) 只授权其七文件最终字节；本轮没有继承该 PASS。该审查曾找出并关闭合法大 package 被2MiB读取门槛阻断的问题，说明独立审查有实际价值。本轮实施者在 IMPLEMENTATION 中明确没有冒称新的独立审查；本报告是这次新增独立判断。

## 是否已是初步可用科研助手

**可以称为“在明确领域、精确输入和有人工调度介入下，初步可用的科研助手”。还不适合称为可靠自主完成开放科研目标的系统。**

支持这一判断的是实际结果：失败执行材料可用于有限分析而不改写执行历史；已有数字被保存并在新 Run 复用；60个单元和图表最终封存；可选工具真实被调用；不确定度方案失败可以形成可追溯的不可判定结论。这些能力超出了单次聊天总结。

Fig.4 的有限结论及48角点方法不适用，与框架运行失败是两类事实。通过独立审查的计划仍可能在实际数据上不可行；审查通过没有保证科学方法可用或研究成功。本轮能够把该失败方法明确封存，是助手的有效交付，不能据此追认原审查充分发现了这项风险。后续优先利用已保存结果修订方法或做限定验证；本报告不要求为部署收尾新增审查 Operation，也不要求必须做新实验。

实际不足也很具体：今天要人工辨别原计划与回顾性计划、核对精确父链、安装和重启多轮版本、区分草稿已保全与原目录仍需保留、决定预算和局部续接；恢复副本/父目录只读导致脚本或运行锁写入失败，错误路径和重复映射也曾把工程工作推给科学 Agent，新活动观测与历史日志仍需分开。最小入口减少了重复返回，但9分钟或14分42秒的真实任务没有分阶段对照，阅读/准备成本尚未证明稳定下降。科学总进度仍依赖调度者从四个 current_progress 槽、prior分析、审查和目标原件拼出当前范围；completed 不能自动替其判定总体完成。

插件边界有实际耦合：TCAD 包显式依赖 curve_score，并直接复用它的 workspace、分析收据及图像诊断能力，三个 wheel 联合验收是合理的。当前证据没有证明其他求解器或长时间通用研究也能使用相同路径；无需为了这一缺口立即增加全领域抽象。优先把当前 TCAD/曲线路径的安装后恢复和可观测行为做稳。

## 最小后续优先级与部署意见

1. **建议部署本轮收尾补丁。** 未发现六生产文件增量新增的必要正确性阻断；主要改动消除实际无效打开失败并改善诊断，未扩大科学准入/提交门槛。安装后核对版本，用新 Run 验证F1的真实恢复；只有这一步完成，才能宣称现场恢复缺陷已修复。
2. **继续科研时按封存缺口选一个有限动作。** 不重算已完成60单元；正式不确定度判断、机制对照与原输出声明路径分别由相应科学/作者角色处理。不要将科学不可判定当作控制层需“放行”的失败。
3. **小范围补齐F2/F3的交接与预算边界。** 先明确直接上一轮恢复提示的范围，保留原恢复来源选择；统一有效 assignment 的读取预算。无需增加新状态机、通用依赖图或全局观测准入门槛。
4. **下次触及所属模块时处理四项旧测试断言。** 对照真实已变接口更新预期，保留身份错误仍被拒绝的断言；不要为凑全绿删除必要负控。无需为了本次小补丁先跑无界全矩阵。

此意见是对今天真实路径及最新精确增量的有界工程判断。**未发现新增部署阻断，与框架仍有已知缺陷、现场验收待补，是同时成立的结论；不构成全框架无缺陷或科学结论正确性保证。**
