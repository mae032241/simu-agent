# C0 初始化证据核定记录

日期：2026-09-09。结论：当前工程材料不足以选定可信的实际初始化证据，C 生产实现保持暂停。A0/A/B 不受此暂停影响，但它们不证明物理执行就绪。

已核对的确定事实：

- `debug_adapter.prepare` 将 development job 的 expected_outputs 清空，`prepare_submission` 拒绝非空 expected_outputs。现有调试链不能直接收集计划候选中的结构文件。
- `_earliest_diagnostic`、`local_debug_service._finish` 与初始化收据目前以终态、退出码和 diagnostic_layer 判断。正常退出不足以证明构造和初始化了物理结构。
- `project_packager._evaluate_runtime_assertion` 的 tdr_metadata 分支没有合格 provider，不可声称已有可复用读取器。
- `tests/operations/test_l4_local_tcad.py` 的成功输出是合成 fixture；已有工程记录 `TCAD_AUTHOR_R4_R5_2026-09-08.json` 的 author 字段保存状态、收据和解释限制，没有可供验证实际初始化步骤的原生输出及其完整生成/收集样本。

本轮未将测试夹具、作者打印标记或 qualified=true 收据当作可信正样本，未调用科研 Worker、私读控制面存储或额外执行求解器。此结论限定于本轮合法可读的工程材料，不声称其他地方不存在真实样本。

下一项必要输入：当前受支持 SProcess R-2020.09 的一个合法来源原生初始化正样本，以及对应源码/开发入口、能力/版本、运行收集身份。拿到后按 R4 计划 C0 决定使用日志还是一个有限原生文件，核对真实步骤、最小读取函数和 prepare/transport/collect/receipt 完整路径，并经静态复审后实施 C。

资源上限沿用计划：最多一个 8 MiB 证据文件或已有日志，不突破现有 debug 剩余预算；解析单进程、最多 10 秒且不超过任务剩余时间。反例必须包含 skipped+exit0、伪完成标记、陈旧/错来源证据及源码/声明变化。没有可信正例时不能只实现“全部拒绝”，也不能放宽成任意非空文件通过。

本轮没有修改初始化通过语义，旧标记仍只能按既有独立领域审查解释。不能据本次代码修复或静态 PASS 宣称 C 已修复、真实实验可执行、或者整轮研究已完成。
