# 迁移验证暴露问题：三文件修复独立静态审查

结论：**三文件修复静态 PASS，无剩余阻断。** 本文不记录复测成功；root 正负责唯一串行动态复测，结果另立动态报告。独审没有运行任何测试、收集、项目 import、业务 CLI、安装、模型或服务器。

## 修复前的真实证据

- `.trial/p_migration_validation_20261017/p3/batch-005/pytest.log`：**5 failed、3 passed**。五项失败均在 `execution_resume.resume` 提前调用 `Records.directory(call_id)` 时遇到 `Original execution call unavailable`；其中一项因此遮蔽了本应检查的 contradictory prepare 错误。这是生产目录生命周期错误，不能归为测试预期问题。
- `.trial/p_migration_validation_20261017/p2_process/batch-001/pytest.log`：**1 failed、14 passed**。`seal_and_read` 无条件读取 `row['outputs']`，对合法 unknown 历史投影触发 KeyError。这是测试 helper 错用合同；当前 `lineage` 对无 verified execution 的原调用只投影身份、unknown 与限制，不承诺 outputs/result。

以上计数来自 root 已保存的修复前日志，不是本独审执行结果，也不代表其他资格通过。

## 精确差异与判定

1. `src/scidiscovery/research_loop/execution_resume.py`：撤掉授权前无条件现存目录要求；仅在已有 intent/possibly-prepared 分支检查预期路径 canonical，缺 accepted 仍返回 unknown，有 accepted 才调用原严格 `Records.directory`。未放宽 Records 全局合同、预建目录或伪造 accepted。fresh 路径仍要求原 positive pending-set，执行原权限/机会/余额检查，按 reserve → intent → prepare → accept 推进；原 call/reservation 身份与未知提交不重放规则保留。
2. `tests/research_loop/test_native_execution_inputs.py`：现有成功回归明确断言恢复前无 call 目录、成功后严格目录存在；现有 intent 中断回归断言无目录时仍 unknown、不 submit。只强化本次故障前提和负控，没有修改 fixture 伪造准备结果或增加矩阵。
3. `tests/research_loop/test_composed_execution_results.py`：helper 仅在确切 unknown 且无 result_status 时允许缺 outputs；保留终态 outputs 的直接索引与字节检查，未用 `.get(..., [])` 隐藏错误。late reconcile 用例另核 exact call、单一行、无 completed/terminal/execution/outputs/observation，以及后续 canonical 成功不改旧 seal、fact 和已冻结 A 页面字节。该修复没有生产行为变化。

独立核对上述三文件 Git diff、两份修复前失败日志及直接相关 Records/lineage 合同，限定 `git diff --check` 无报错。没有扩大到其他生产节点或测试套件。三个文件保持作者冻结版本，本文是本轮唯一文档写入。

## 第一次复测后的可选字段断言修正

root 随后报告迟批文件 **7 passed、1 failed**，剩余失败是测试直接读取 `old_job['history']['execution_recoveries']` 的 KeyError；composed 原失败单项已由 root 复测通过。这里仅记录 root 反馈，动态日志及最终计数另见其验证报告，不是本独审运行结果，也不宣称迟批文件已全通过。

定点源码确认 `lineage.py:490` 仅在 recovery refs 非空时发布 `execution_recoveries`，`history.py:689` 消费缺字段为原空 prefix。测试现改为两条严格断言：`recovery.prefix(root,7)==[]` 与 `'execution_recoveries' not in old_job['history']`；没有 `.get` 默认值掩盖错误，也没有改变生产 schema。用例末尾旧 job 原始字节不变断言仍保留。因此本次单项测试修正亦**静态 PASS**；若错误引入恢复 ref、提前发布该字段或改写旧 job，仍会失败。限定 diff 空白检查无报错，独审未执行复测。

## 资格边界

允许 root 对受影响用例按既定资源约束串行复测；本静态 PASS 不替代复测。合成 backend/native 身份边界、真实平台/solver、跨 boot、并发和掉电资格仍以各原报告及实际证据为准，不能由本次小修复推导通过。
