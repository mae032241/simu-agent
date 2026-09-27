# R3 实施记录：串行执行与独立静态审查

## 当前结论

**A–D 代码候选已实现并完成独立静态审查；随后源码 29 案例、runner 15 案例、隔离安装与 512MB 本地流式传输已取得通过证据。连接恢复后，真实短 SProcess / SDevice 和SSH原生产物收集亦通过，本轮约定范围验收完成。**

最新状态由[安装与 512MB 验收记录](FOUR_MODULE_R3_FINAL_ACCEPTANCE_20260925.zh-CN.md)承接；用户已授权受限安装、构建和短 TCAD，临时安装目标按要求测试后删除，不改现有服务。

[受限源码验收与修复记录](FOUR_MODULE_R3_SOURCE_ACCEPTANCE_20260925.zh-CN.md)及[验收后候选](evidence/four-module-r3-20260925/source-acceptance-final-candidate.json)承接下列静态候选。验证采用串行、1GiB 单进程地址空间硬限制与 120 秒单项超时；发现 checkpoint 序列化问题和测试夹具合同缺口后局部修复、只续跑失败或未执行项，未在最终工作树重跑全部案例。原失败证据、静态候选和审查结论全部保留。

实施日期为 2026-09-24 至 2026-09-25，依据 [R3 主计划](FOUR_MODULE_SIMPLIFICATION_STRATEGY_R3.zh-CN.md)。用户明确要求串行以避免 OOM：每次仅一位子任务执行者或审查者运行，实施者结束后才启动独立审查；发现问题再交回实施者修复。最初实施与静态审查阶段未运行测试或 catalog；用户随后明确授权受限源码验证，才执行上述最小清单。该源码阶段没有执行安装、构建、全套测试或真实 solver；后续授权与安装结果见最新验收记录。

基线为 `5871a64e3585e00f98f5357aadef959d343758c5` 加前序文档、测试和兼容代码清理工作树。改动尚未提交；不能用裸 HEAD 或整个 HEAD diff 代替本轮精确候选，也不能把前序清理归入本轮新增改动。

## 已交付工作包

| 工作包 | 实际交付 | 独立静态审查 |
| --- | --- | --- |
| A 图证据完整作者 | `science.evidence.extract.figure.v3` 单作者完成 inspect/preview/save/Intake，独立 `science.figure.evidence.audit.v2` 审查后由新版 bundle 消费。删除旧双作者与公开 materialization；选定证据族绑定完整父链，保存恢复复用原件，文字修订可复用原族但需新审查。 | [首审](reviews/FOUR_MODULE_R3_A_IMPLEMENTATION_REVIEW_20260924.zh-CN.md)、[复审](reviews/FOUR_MODULE_R3_A_IMPLEMENTATION_REVIEW_20260924_FOLLOWUP.zh-CN.md)：恢复别名、文字修订复用及 validator 合同三项问题已静态关闭。 |
| B TCAD 配置内自主执行 | 管理员配置存储 ≤2,000,000,000 字节、执行墙钟 ≤3600 秒时策略授权；超额/禁用按配置处理。策略记录与人工批准分离，稳定预算归属、预留/结算和未知提交恢复接通；本地/远端监测总存储并停止进程组；SSH、归档、SDevice 输入及 CAS 流式传输；调试限额配置化并持久保存。 | [首审](reviews/FOUR_MODULE_R3_B_IMPLEMENTATION_REVIEW_20260924.zh-CN.md)、[复审](reviews/FOUR_MODULE_R3_B_IMPLEMENTATION_REVIEW_20260925_FOLLOWUP.zh-CN.md)：原六项及补充两项问题已静态关闭。 |
| C 连续分析与产物复用 | 数值计算先封存 checkpoint；绘图失败保留指标，同一诊断工具通过 `checkpoint_alias` 只重绘。复用校验算法、完整请求、文件摘要和 Artifact 身份。复用已有作者内调试和假设独立 critic/revision。 | [审查与修复复核](reviews/FOUR_MODULE_R3_C_IMPLEMENTATION_REVIEW_20260925.zh-CN.md)：现有图片校验的导入遗漏已静态关闭。 |
| D Root 与机械步骤内化 | 删除 `tcad.execution-plan.project.v1` 和 `tcad.reviewed-deck-package.v2` 两项公开 Operation。骨架审查读取项目内 execution_plan；`tcad.study.execute` 内部确定性准备并封存审查后的包。预检共用逻辑且只读，正式调用幂等封包；同步分析、角色、源指南与中英文文档。详细计划/SDevice 路线保留。 | [独立审查](reviews/FOUR_MODULE_R3_D_IMPLEMENTATION_REVIEW_20260925.zh-CN.md)：受影响路径未发现阻断项；D 对 B 的共享授权、预算、审批边界已重新检查。 |

最终 Operation ABI 为 **19**，TCAD job wire 为 **4**。`tcad.deck.review.v1` 的合同版本为 **4**，`tcad.study.execute` 的合同版本为 **3**；名字中的后缀与合同版本不能混用。旧 package 的 artifact schema 和 adapter profile 有内部消费者，删除的是公开机械 Operation，不是这些仍有效的合同。

## 原静态交付候选与证据

- [集成候选清单](evidence/four-module-r3-20260925/integrated-candidate.json)：四阶段合计 **92 个不同文件**，其中 **72 个 Python 文件**在最终集成状态再次通过 stdlib AST 解析。数量不包含本记录、审查报告和候选清单自身，也不代表整个工作树的修改数。
- [A 候选](evidence/four-module-r3-20260925/A-candidate.json)、[B 候选](evidence/four-module-r3-20260925/B-candidate.json)、[C 候选](evidence/four-module-r3-20260925/C-candidate.json)、[D 候选](evidence/four-module-r3-20260925/D-candidate.json)从各阶段审查绑定的临时清单原样归档，SHA256 未变。
- 静态交付时，按 A→B→C→D 顺序合并每个文件的最后候选身份，与当时工作树逐项重算匹配，无清单外的身份漂移。随后源码验收修改的 4 个文件由验收后候选记录，不覆盖原清单。共享文件的旧审查只适用于其旧候选；后续修改由相应阶段及 D 共享边界审查承接。
- 各阶段进行了 AST、JSON、引用/组件目标与 diff 静态检查；B 同时静态解析远端 Python 3.6 语法。静态符号或组件解析没有执行 catalog 编译。
- 阶段审查报告保留初次发现及修复候选，未将失败候选改写成通过。R2、独立规划细节及原计划审查保留原始字节与哈希。

集成候选清单 SHA256：`07441a00ce8da4048de4e43830b76d1127de306d24bcb7557cba1566eb4faa25`。

## 静态交付时列出的未验收内容（历史状态）

1. 安装后的 ABI19 catalog 与实际 Worker 交付、独立审查、下游消费闭环。
2. 策略变化、人工审批分支、并发预算预留/结算、重启和未知提交恢复的真实行为。
3. 本地/远端进程树终止、总存储计量、2GB 文件的真实传输与内存占用、SDevice 执行。
4. 分析检查点在真实失败 Run 恢复后的绘图和最终交付。

上述列表保留静态交付时的范围，后续部分项目已有验收证据，具体通过/未覆盖范围以最新验收记录为准；它们不属于原最小源码验证的证明。存储限制使用采样观测，存在采样间隔内超调，不宣称严格磁盘硬配额。尚未测量科研任务 token、耗时或成功率收益。

## 一项非阻断后续改进

D 审查指出同次 preflight/invoke 会重复准备确定性 payload。可在单次调用内复用已验证结果，仍保留提交前策略与预算实时重判。本轮保留该建议，未以跨请求缓存引入新的资格来源；没有将其标记为已修复。

## 下一步状态

本轮约定的分层验收已完成，真实短 SProcess/SDevice 与SSH小产物校验已取得证据；两端临时目录已清理，现有服务未更新。512MB 按用户要求替代本轮2GB实测，且仅在本地helper传输；不能据此声称2GB网络传输或完整外部LLM科研流程通过。无需重跑已通过项目、历史清理或恢复旧机械入口。
