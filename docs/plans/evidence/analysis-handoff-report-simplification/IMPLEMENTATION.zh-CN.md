# 分析接手与交付简化：实施记录

日期：2026-09-13，状态更新于2026-09-14。工程修改和限定验证完成；[最终独立实现审查 PASS](IMPLEMENTATION_REVIEW_R0.zh-CN.md)。用户安装后，真实简版分析提交与下一轮设计预检通过；现场阅读量与详细错误正文的 Root 可见性限制见 [现场验收](LIVE_ACCEPTANCE.zh-CN.md)。

## 范围与基线

按 [计划 R0](../../ANALYSIS_HANDOFF_AND_REPORT_SIMPLIFICATION_PLAN.zh-CN.md) 和 [独立计划审查 PASS](PLAN_REVIEW_R0.zh-CN.md) 实施。
精确改前快照为 `/tmp/scid-handoff-report-baseline-flmih_xb`，摘要见 [source-baseline.json](source-baseline.json)。
HEAD `be5da77acdbf98054e0b096fc4e940de560d4ba1` 仅标识已有工作树基点，不把此前大量 dirty 改动算成本轮。
本轮八个生产文件、两个测试文件及相关文档的差异见 [incremental.diff](incremental.diff) 和 [changed-files.json](changed-files.json)。
没有修改自动生成的 Agent 配置、执行授权、VM runner、原始科研对象、工具收据或通用生命周期。

## 已实现

1. 共用入口提供每个原件的大小、Schema、路径和每个端口一次的用途说明。目标、案例、方法和 validation_plans 有精确原字段索引；observable 只按原文相等去重，长摘录标出截断并指向完整原件。未知 Schema 仅提供索引。
2. TCAD 既有阅读视图增加项目、嵌入源码和实现审查指针，以及科学变量矩阵。默认不展开 case_parameter_bindings、哈希和物化证明明细。入口分配 12 KiB、两份展示合计最多 32 KiB，优先保留已有产物对应关系；溢出仅减少展示并标记遗漏，完整 source_bindings 仍供工具和 finalizer 使用。
3. LayeredDiagnosisReport 保留既有类型；gates 整体可选，limitations 可选，无剩余问题时可省略 remaining_contradiction/next_action。旧完整报告继续读取。claim_allowed 仍是 Agent 的显式判断；缺少数值层投影为 not_evaluable。
4. 通用、TCAD、曲线误差三个分析角色共用报告指导和工作区 patch_contract。Agent 草稿可不写重复 handoff，既有 finalizer 在封存前生成状态和正文短引用；保留不重复的旧 handoff 说明。Root 继续同时读取正文和信号。
5. Codex 首次接手/复用提示改为核对当前绑定、先读紧凑入口并按需查原件；旧记忆仍不替代证据。

## 工程证据

所有测试和安装探针串行运行，复用 512 MiB 进程树及地址空间、120 秒 CPU、150 秒单批墙钟、BLAS/OMP 单线程限制。
[checks.jsonl](checks.jsonl) 保留全部通过、失败、重试的命令、日志、耗时和峰值；没有内存或时间上限终止。
观测到的最高进程树 RSS 为 **239.3 MiB**。

| 检查 | 结果与证据 |
| --- | --- |
| 修改前基线 | 68 通过，约 146 MiB，`check-1789310824345360411.log` |
| 最终分析交付、续接、声明与引用 | **78 通过**，58.91 秒、约 151 MiB，`check-1789312714469037982.log` |
| TCAD 与 collector 分支 | **56 通过、2 项既有错误码断言失败、1 项压力测试未选择**，`check-1789311682914099105.log`；旧快照复现见下方 |
| 编译合同投影 | 三项全工具/公开 Agent/字段诊断检查通过，`check-1789312349361859246.log`；该批唯一失败是后来已修正的设计测试夹具 |
| 设计消费与平台提示 | 已封存简版→同实例设计预检/打开→原字节读取，加两项平台检查，**3 通过**，`check-1789312439497688086.log`；设计用例也包含在最终78项中 |
| 隔离安装 | 核心、TCAD、curve-score、figure 四 wheel；**50 项生产目录**编译，八个生产文件与安装包逐字匹配，三种分析经真实 local Worker stdio 提交均 completed；[installed-smoke.json](installed-smoke.json)，`check-1789312805081098837.log` |
| 文档与差异 | 中英文受影响架构段落同步；`git diff --check` 通过 |

合计 **139 个不同的定向用例通过**，不将重复运行累加为独立用例，不声称全量套件通过。
未运行全量/压力测试；hardened 不支持这些分析角色声明的 native 能力，不宣称该后端端到端通过。

## 测试过程中遇到的问题及定位

- 新测试最初把 Root 的 scheduler_signal 当作 sealed_output.handoff、漏传 provisional_roots、把同一 Artifact 同时绑两端口、把带 schema_version 的旧条目与无该字段的字典直接比较。这些是夹具错误，分别按真实接口修正。
- 删除展示中的历史 basis 副本后，旧断言改为沿 origin.pointer 读取原件并核对封存结果。直接调用旧入口辅助函数的测试暴露新参数缺少默认值，已保留原默认行为。
- 设计消费夹具缺少 ApprovalService，按既有夹具启用测试服务并复用其审批 stub；仅证明反馈传输与消费，不证明真实审批。
- 安装探针原先先用内存 Worker 打开 curve-error，再让另一 stdio 进程重新领取。该角色原本没有 tool_evidence_ports/reopen 回退；探针改为由 stdio 首次领取同一 queued Run，并在同一进程完成提交。没有为测试修改生产生命周期。
- collector 两项失败均期待旧 `input_producer_contract_changed`，实际是 `input_independent_review_incompatible`；同一历史审查继续不能授权 author。八个生产文件覆盖改前快照后，两个用例以相同差异失败，见 `check-1789311800665170184.log`。本轮保留该既有断言偏差，不改写授权规则来满足测试。
- 早期 32 KiB 分配使部分已知来源映射被展示预算挤出；最终只调整展示顺序和预算分配，当前结构测量保留全部13个对应关系及156个变量值。

## Fig4 结构测量与现场验收边界

[fig4-view-measurement.json](fig4-view-measurement.json)：已封存原计划/项目、完成 Run 的13个产物名，其他库存输入用占位内容进行离线渲染。
入口 11,844 字节，项目视图 16,867 字节，合计 **28,711 字节**；156 个值逐项匹配原计划，13 个已知来源对应全部展示，默认控制绑定明细为零，完整原件与工具映射未变。
项目视图无遗漏，入口有17项摘录/展示遗漏，均可通过原件索引追溯；这不是模型实际 token 或真实完整输入的耗时测量。

安装后已按计划完成新受控分析 Run：502.621秒、零提交拒绝，无gates简版报告9,171字节，下一轮设计预检通过。封存结论确认复用数值且未重跑TCAD或完整归约。两次本地命令错误均有类型/时间/日志位置；旁证处理记录已封存，但其正文暂未通过Root公开接口读取，现场入口大小及具体错误修复仍属观测限制。
详见 [LIVE_ACCEPTANCE.zh-CN.md](LIVE_ACCEPTANCE.zh-CN.md)。不从结构字节减少推断阅读/推理时间，不以单轮复用任务宣称普遍提速或总体 Fig4 科学目标已完成。
