# 完整记录容量与紧凑视图混用：根因及修复

基线：`4c074ad`。状态：实现与定向验收进行中，未宣称真实模型复测通过。

## 真实失败链

cov rerun 的 W002 已完成 25 次受管执行。封存时 observer 形成 297,940 字节的完整记录，超过内部 256,000 字节门槛。控制层将容量异常降级为 unavailable，持久化了空 contexts；原始 accepted/completed/model 文件仍在，managed_calls 也仍在。

后继 A 的候选表能看见实验，但交付解析依赖丢失的 contexts，无法绑定所选 run-13 的原件。审计尚未执行，A 却反复收到 unavailable，最终以 closeout_budget_unavailable 结束。这是控制层丢失绑定，不是模型应补填引用，也不是科学审计不合格。

## 修复规则

- 完整科学输出、观察记录、引用清单、执行回执、归档清单和恢复记录不受展示字节数或累计条数限制。
- 哈希、原件复制使用流式处理。完整 JSON 保持原有文件格式；本轮不声称任意大 JSON 的内存消耗恒定。
- 紧凑视图继续有界，明确标注省略并保留原件读取入口。视图过大不拒绝科学封存。
- 显式用户存储配额、执行预算、插件合同额度仍生效；新薄实例默认无隐式输出存储上限。旧冻结授权不改写。
- 身份、路径、来源限制、原件哈希、未知执行不重放等校验继续生效。
- 相同原件与适配器下的审计工程失败，不反复派 A 消耗预算；保留可恢复诊断。科学不合格与工程未能执行分开。

## 扫描覆盖

1. 薄链：history、checkpoint、lineage、selection、worker_delivery、continuation、managed_wait、协议终态校验。
2. 执行与交付：受管输入/回执、local/cov 适配器、候选审计、通用交付、内部 JSON 通道与 launcher。
3. 旧体系仍使用的公共服务：完整证据 proof、工具尝试/计算结果、scientific_usage 的完整 owner 与可选缓存、执行收集检查点、任务工作区及 deadline 读取。
4. 实例归档：完整 DB 记录与文件清单、恢复临时区、TCAD debug ledger/inventory 和原件验证。

可选缓存超过缓存额度时走原件校验；不能将缓存容量异常变成科学证据拒绝。外实例归属未知时的保守保留、显式读取资源预算与真实执行配额不等于展示上限，不随本轮删除。

## 验收要求

- 25 次真实受管调用生成超过旧上限的快照；A/重启读回完整绑定，改动原件仍拒绝。
- 大科学输出、多个成果、超过旧文件/候选/引用数量的完整记录可封存读取。
- 页面省略不影响记录；显式配额及路径/哈希/身份负控仍拒绝。
- 独立启动的适配器、安装包入口与源码路径一致。
- 保留初次回归发现的导入遗漏和过期测试断言，不把失败隐藏成全程通过。

详细审查：[外侧完整记录审查](FULL_RECORD_CAPACITY_OUTER_REVIEW_20261016.zh-CN.md)。各节点最终测试与提交记录在通过独审后补充。

## 外侧与恢复验收记录

- 首批外侧 83 passed / 3 failed：三项旧断言要求容量拒绝，更新为完整保留和封存成功；旧失败日志保留。
- `/tmp/scid-full-record-root-r2-20261016`：137 passed / 9 failed，196.758 秒，峰值 RSS 367,271,936，清理完成。引用、归档、managed wait 和大记录主体通过；失败分为新增fixture缺合法计算字段、两项旧容量期待/损坏JSON诊断，以及六项旧角色schema fixture。
- `/tmp/scid-full-record-root-r3-20261016`：12 passed / 1 failed，8.491 秒。损坏JSON仍拒绝，错误规范为 ScientificProvenanceError；显式 bytes/time 预算仍拒绝。剩一项新增测试错误地忽略控制层自动补的 derived_from。
- `/tmp/scid-full-record-root-r4-20261016`：1 passed，1.784 秒。改为真实 retain_calculation→publish→accept→manifest 路径，20,000项完整计算结果落库/读回，summary回包不复制完整数组，原来源关联保留。
- `test_worker_resume` 旧fixture补齐已存在的W/A必需字段及screen的blocked结论；没有放松36 token/2次派发等断言。六项旧失败与三项新大session/头记录负控已分别转正，详恢复fixture报告。

协议18升级前的冻结schema含implementation_selection.maxItems=16；续接只额外接受这一确切旧形状，原文件不改写。其他schema字段漂移仍拒绝。此处理只解除旧框架存储门槛，不重置预算或恢复其他旧协议。

活体计量的每轮读取预算与发现覆盖仍有界，终态用量可由原生turn.completed补全；本轮不宣称大session的实时计量覆盖已增强。领域执行载荷合同（例如TCAD源文件/物料槽）是单次执行能力约束，另有明确规格，不作为跨历史存储上限删除。

未运行全量平台矩阵、新真实模型或远端solver；源码定向、独立审查与安装包验证分别列证据。技能提到的 scripts/validate_architecture_constraints.py 在当前分支不存在，未伪造该门禁通过。

## 安装版收口

`/tmp/scid-full-record-installed-20261016-r3`：干净core/TCAD/curve wheel，288个安装包文件与冻结源码逐字一致；隔离解释器、无源码PYTHONPATH，10 passed（14.54秒），监督14.854秒、峰值RSS267,268,096、清理完成。覆盖通用目录交付、大manifest、独立cov observer和完整记录公共接口。

安装准备前两次分别被临时脚本错误依赖pandas metadata、复制了陈旧build/lib所阻止；原始日志保留。清洁源目录构建后逐字身份门禁通过，未降低门禁、未改生产实现来迁就测试。独立结论见外侧审查报告末节。
