# 失败交付跨 Run 接续验证

日期：2026-09-10。检查现有未提交工作树，HEAD 为 2edac5d317a74056869a567bd0daa7f556ecbc85。本轮只增加验证证据，没有修改运行源码，没有复用原 Agent，也没有启动真实求解或新的研究 Run。

## 结论

“逻辑接续必须独立于 Agent 存活”是合适的验收要求，但当前实现未满足。当前不能宣称新 Agent 能接手本次失败现场。Agent 复用不是本次阻断的修复。

1. `plugins/tcad_artifact/tcad_artifact/operation_workspace.py:382` 的修订分支只接受 DeckProjectDraft；端口已接受项目或 ImplementationGap。隔离 Root 调用复现 preflight admissible=true，随后 invoke 异常链为 local_run_creation_failed → local workspace preparation failed → prior_project is invalid → DeckProjectDraft 缺字段/多余字段。与上一轮线上错误一致；三个关键文件与安装目录逐字节一致，见 installed-comparison.json。未读取线上内部数据库或失败 Agent 工作区，不能将复现堆栈冒充线上原始堆栈。
2. 同文件 `finalize_workspace` 的 gap 分支只返回 gap 和 handoff。探针先写入源码及模拟失败日志，再提交 gap；封存结果不含源码/日志，recovery_available=false，新审查工作区也没有这些文件。记录没有成为跨 Run 的受控输入；这不等于断言磁盘上已物理删除。
3. 同文件 `snapshot_workspace` 和 `_restore_retry_tree` 遇到 gap 时提前返回，只处理 gap/handoff，即便源码与日志已经存在。无 gap 的快照也没有收集诊断目录。因此不能把当前失败快照机制视为完整诊断接续。
4. `plugins/tcad_artifact/tcad_artifact/project_packager.py:735` 的 validate_implementation_gap 在存在 prior_project 时仍强制解析 DeckProjectDraft。第二个探针确认：即便单独打通工作区创建，新修订诚实提交缺口时仍会被同类约束拒绝。

## 定向验证

- probe.py：两个缺陷复现断言通过，1.02 秒。这意味着缺陷得到复现，不是功能验收通过。覆盖真实本地 Root → author 提交 → 新 reviewer 提交 → revision preflight/invoke 路径；测试适配器不运行 Sentaurus。通过异常 cause 链定位具体类型错配。
- controls.log：两个已有对照通过，1.91 秒：无源码缺口仍能独立审查；完整项目修订、输入约束和受控调试路径正常。说明不能简单禁止所有缺口，也不应声称所有新 Run 修订均失效。
- 首次探针 1 failed/1 passed，原因是探针遗漏必填 instruction；修正探针后复现成功。保留 probe-first-attempt.log，不隐瞒该次失败。
- 全部串行，BLAS/OMP/MKL 线程为 1，地址空间限制 3 GiB，每次超时 90 秒。最大 RSS 102260 KiB，约 100 MiB；无 swap。未运行全量测试、压力测试、真实 LLM 接续或真实 solver。
- 本轮未修改运行代码，未进行新安装。安装态证据限于三个相关文件的字节一致性，并非完整安装矩阵测试。

## 最小修复边界与后续验收

先解决记录交接，不增加存活 Agent 复用、会话注册表或新状态机：

1. 区分“尚未产生源码的输入缺口”与“已经尝试实现的失败交付”；后者应通过现有受控成果或有界快照机制保留源码、声明、对应诊断、已尝试修改和结果。尚无源码的缺口仍可提交。不能把这些记录当作通过初始化的项目。
2. 修订准入、工作区构建、提交校验统一处理该交付类型。无足够失败现场时应报告明确缺项和处理动作，不能预检通过后再泛化为创建失败，也不能让新 Agent 猜源码。
3. 新 Run 重新绑定精确版本、审查和预算；旧诊断可读但不授予新源码执行资格。更换源码后必须产生匹配的新验证证据。
4. 验收必须使用新的无历史上下文 Agent：能读到精确失败源码、对应日志和尝试记录；完成有界修复，或准确返回尚缺条件。补充源码/诊断错配、无源码缺口、预算隔离和旧成功证明不能继承的负控。

本轮验证不能确定实际 Sentaurus 退出码 1 的具体原因。需要先将精确诊断作为受控输入交付，不能由 Root 从隐藏工作区读取后转述给下一位 Agent。
