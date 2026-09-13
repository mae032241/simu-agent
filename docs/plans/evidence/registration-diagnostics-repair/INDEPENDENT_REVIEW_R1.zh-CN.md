# 重复登记与失败追溯修复：独立实现审查 R1

**结论：REVISE。** 本轮 R2 候选仍有两项可达的失败追溯缺口。它们不改变科学结论，但分别破坏“同次调用归属同一 Run”和“错误指向 Worker 实际可修改字段”的验收要求。不能将既有正例通过视为两项工程问题已经闭合。

审查日期：2026-09-13。审查者未修改生产源码或既有测试，未调用控制面、科学 Worker、真实 Run 工作区、VM、部署或科学执行。使用父级 `scid-cross-boundary-review`、`scid-change-scope-checks` 技能，并按 `karpathy-guidelines` 的最小改动原则审查。

## 阻断项

### F2 / P2：复用 Worker 的新 assignment 打开失败仍归属旧 Run

位置：`src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py:139`，同文件 `_open()` 的 302—313 行；配合 `service/runs.py` 的 `_open_exact()` 中已经选中 Run 后调用 `backend.open()` 的异常路径。

本轮 finally 将 open 计时归属设为当时的 `self._run_id`。但是 RunService 选中新 Run 后，workspace 打开失败会先把新 Run 标记 failed，再抛 `RunStateConflict`；router 只有成功返回才更新 `self._run_id`。复用时 `_open()` 的旧终态分支吞掉该异常，并返回旧 Run 的 completed。随后本轮 finally 把此次 open 的开始与结束都写入旧 Run。

独立负例用真实本地 Worker router 和 RunService 完成旧 Run、排队新 Run，只在 backend.open 对已选中新 Run 注入一个 OSError。结果为：

- `worker_open_assignment` 返回 `{"state":"completed"}`，实际新 Run 为 failed。
- 旧 Run 计时从 2 条增至 3 条，新增项是这次打开新 assignment 的调用；新 Run 计时为空。
- 新 Run 的错误分页只有 runtime_failure 的通用记录，没有原 OSError 原因或工程诊断引用；旧 Run 生命周期仍为 completed。

这使 Root 看到的新 Run 错误无法对应实际调用，Worker 收到的状态也不能用于纠错。旧代码已有的宽泛 `RunStateConflict` 回退与本轮新计时归属组合后，失败 open 仍未满足明确目标；此处不是要求增加新的生命周期。

最小修复边界：在 RunService 已选中 assignment 后，让失败携带内部归属并保留原 cause；router 用该归属记录失败与整次计时，只在确实没有新 assignment 时沿用旧终态返回。不要通过推测“当前最新 Run”找替代归属，也不要把内部身份暴露给 Worker。增加此失败分支的断言，除成功复用正例外，同时检查旧 Run 不增记录、新 Run 可读到原原因，以及终态不被重开。

### F1 / P2：派生变量错误丢失 proposal/variable 索引

位置：`src/scidiscovery/artifact_agent/schema/experiment_intent.py:462`；路径来源为 324—326 行逐项调用 `_materialize_variable()`，以及 595 行单独构造 `ComparisonVariable`。

context validator 捕获内部构造产生的 ValidationError 后直接采用该模型的相对 `path`，并把它声明成 intent payload 的规则错误。内部模型并没有外层 proposal/variable 的索引；声明 schema 为 ExperimentPortfolio 不能恢复已经丢失的构造上下文。

独立负例使用仓库已有 False 与 0 示例：intent 的变量为 intended_change、baseline_value 为 False、override 为 0。该 intent 可以解析，派生 ComparisonVariable 拒绝它。通过真实 Run 提交，返回及持久化结果均为：

```json
{
  "phase": "output_payload",
  "path": "$.payload.comparison_role",
  "rule_id": "experiment.design.intent_closure",
  "message": "intended_change variable must vary between cases"
}
```

Worker 提交的 payload 没有顶层 comparison_role；实际字段位于 `$.payload.proposals[0].variables[0].comparison_role`。新实现保留了具体原因、payload phase 和规则所有者，但提供了不存在的修改位置，多 proposal/variable 时也无法定位哪一项失败。现有派生错误测试只断言消息/规则/phase，漏过此错误。

最小修复边界：在物化构造层附带外层索引，并将派生字段定位到本次 intent 可修改的来源字段；不要在最终捕获层把内部模型位置直接当成完整输出位置。此审查不要求改变 False 与 0 的科学或数值判定规则。回归应断言完整字段路径，并验证在同一 Run 修改实际字段后可完成提交。

## 审查范围与通过的部分

审查基线是 `baseline.json` 指向的 `/tmp/scid-registration-diagnostics-before-89_k59w5`，HEAD 为 `be5da77acdbf98054e0b096fc4e940de560d4ba1`；不是整个 HEAD 工作树 diff。独立 hash 探针对 `REVIEW_MANIFEST_R2.json` 的18个当前文件及对应改前字节逐项核对，18/18匹配。文件覆盖12个生产文件、3个测试文件、3个文档文件；已读取 `INCREMENT_R2.patch` 及相关上下文。审查结果绑定 R2，不预先适用于后续修订。

已追踪的边界包括：compact intent 校验与规范化→派生完整计划→完整计划修订和审查→curve compiler；Worker 调用→Run 错误活动与生命周期→Root 摘要、分页和 scoped diagnostic_read。模型可见规则、工具输入 Schema、实例名称解析、晚提交候选保护、已封存候选重放及恢复断言均纳入检查。

- observable 自由文本重复登记和 baseline 角色重复拒绝已从本轮涉及的意图/完整计划/曲线消费者删除；可见合同同步。明确 baseline key 保留为引用；仅一个已声明 baseline/control 时补全；未知 case、变量范围内真实矛盾及歧义缺口仍拒绝。未见以程序规则替代本轮暂停的科学判断。
- `record_error_observation` 使用既有 run_activity；不更新 state、deadline、last_activity_at 或 accepted candidate。Root 按当前实例解析 Run 名，错误分页在 SQL 中固定 run_id；run_list 游标先做当前实例解析，并按稳定 binding 顺序续读。默认状态摘要保持原接口行为；旧 NULL 详情显示为 NULL。除 F2 外未发现新的归属或跨实例读取缺口。
- source_aliases 的失败定位保留原请求索引，包括重复别名；错误后仍可继续提交有限结果，不把帮助索引默认为证据。没有新数据库、Operation、执行权限或通用状态机。

## 四项旧失败的测试修改是否掩盖问题

**未发现掩盖本轮实现错误。** 已读基线重放脚本、四项失败日志、精确测试增量及原测试后半段。重放先复制隔离源码，再用快照字节覆盖基线文件；日志确认四项测试在改前版本失败。新增未被选择的测试文件不参与这四项重放。

- candidate 两个崩溃窗口改为检查 WorkerToolError 的真实结构化原因、Root 摘要和工程引用；候选摘要不可变、后续工作区不能覆盖候选、恢复后不重复注册及响应重放断言仍保留。
- status/recovery 保留数据库字节不变、拒绝 preflight 不创建 Run、错误输入恢复拒绝、原工作区保存、显式恢复及次数耗尽后不再创建 Run；改为结构化拒绝诊断，并把耗尽原因明确为 recovery_attempt_limit_reached。
- 真实进程崩溃恢复保留原进程退出码、failed 终态、工作区保全与幂等 reconciliation，晚 heartbeat 现在还检查 Root 持久化错误。
- snapshot 失败仍断言原文件保留与 recovery_pending；替换旧的“任何工程原因都不可见”断言，使用带真实路径/凭据形状的合成异常，要求原因可见但秘密与私有路径在摘要和 diagnostic_read 中均脱敏。这提高了诊断与脱敏的实际验证强度。

现有日志 `check-1789293928777036466.log` 显示该完整文件26项通过；此数字是观察既有执行证据，没有把它冒充审查者重跑结果。F1/F2 均不是靠调整这四项测试被隐藏，而是现有新增正例没有覆盖的边界。

## 验证证据与限制

审查者执行：

```text
python docs/plans/evidence/registration-diagnostics-repair/check.py python -m pytest -q docs/plans/evidence/registration-diagnostics-repair/review_probe_r1.py
```

结果：**2 failed / 1 passed**，2.38秒，进程树峰值120078336 bytes（114.5 MiB），无超时或内存终止。失败正是 F1/F2；通过项为精确候选摘要检查。日志为 `check-1789294193778350620.log`，可机器读取事实为 `review_probe_r1.json`。整个探针仅使用合成 tmp_path 工作区，经规定的512 MiB / 150秒串行检查器运行。发现相关失败后停止新增测试，并将测试槽交回实施者。

已检查实施者的安装探针：隔离环境构建并安装四个 wheel，生产模块从环境 site-packages 加载，catalog/Schema 和实际 MCP router 经过测试；`installed-files.json` 记录12个生产文件与 wheel 字节一致。这不能证明真实平台 Agent、daemon、VM、求解器或端到端科学任务通过。没有重跑全量测试，遵守本轮限定；git diff --check 的通过为实施记录陈述，此次未独立重复。Hardened 既有 workspace 限制不计为本轮缺陷。

两项缺口修正后，应冻结新的精确候选、补充受限回归及更新 wheel 一致性证据，再复审。当前 R2 不通过，且未部署。
