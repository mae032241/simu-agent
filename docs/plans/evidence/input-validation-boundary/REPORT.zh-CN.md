# 输入与输出校验职责修复：交付报告

安装后更新：真实历史执行进入新分析时，Root 丢失历史 review 的封存判定，创建前预检仍被拒绝，线上验收未通过。定位与未覆盖场景见 [真实记录验证](LIVE_VALIDATION.zh-CN.md)。下文保留此前本地实现与测试结论，不将其扩大为线上通过。

后续修订入口：[历史判定与分析准入最小修订计划 R2](../../HISTORICAL_SIGNAL_ADMISSION_MINIMAL_REPAIR_PLAN.zh-CN.md)，已纳入跨模块审查发现，[R2 计划复审](HISTORICAL_SIGNAL_PLAN_R2_REVIEW.zh-CN.md) PASS；[R2 源码与本地验收已完成](../historical-signal-r2/REPORT.zh-CN.md)，待正式安装后完成线上验证。

2026-09-10。R4 计划范围内的实现与定向工程验证完成，独立静态审查 PASS。尚未部署或执行线上科研验收。

核心变化是明确责任：创建前的共享 preflight 检查输入；提交与预览仅验收输出及其相对冻结证据的真实性；控制层保护运行完整性。已确认的纯输入规则从输出路径迁出，目录、Worker 可见合同与实际准入使用同一声明。

如果输出解析实际暴露准入漏检，记录 admission_defect 并保全成果，不再把它当作作者可修输出错误。合同变化时不会调用新 hook 清理旧工作区，也不会把旧 result.json 当作最新源码已完整保存的证明。原合同 resume 保持严格；修复后可通过新 Run 的 draft_from 接续已受控保全的草稿。

TCAD 分析分开绑定求解器产品和诊断日志；缺产物、执行失败及无评分仍能提交有限结论。非通过审查可报告被审项目的参数问题，作者和通过审查仍须满足真实实现要求。

证据包括创建前拒绝与提交零输入 checker 调用、框架故障保全与重启、最新作者源码跨合同接续、生产 collector 到正式分析提交，以及封存分析进入下一轮设计。真实 wheel 和 installed Root/Worker 合同投影也已验证。测试串行，恢复后总进程树预算 512 MiB，已记录峰值约 163 MiB；没有全量或压力测试。

- [实施与定向测试记录](EXECUTION_RECORD.zh-CN.md)：逐组结果、原始日志及未验收边界。
- [迁移清单](MIGRATION_INVENTORY.zh-CN.md)：50 项动态目录的检查职责。
- [独立实现审查](FINAL_CODE_REVIEW.zh-CN.md)：发现、修复复核及静态 PASS。
- [兼容影响矩阵](COMPATIBILITY_MATRIX.zh-CN.md)：相对已部署版 20 项合同变化、30 项不变，ABI 不变。

下一步可进入安装与线上现有产物验证。安装前需处理受影响的 queued/running Run；新旧合同不可混用，历史读取不自动更新资格。本报告证明工程路径，不声称真实科研目标已经完成。
