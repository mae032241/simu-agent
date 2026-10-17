# F2：永久未提交事实不应阻断 W 如实封存

状态：生产/测试冻结，root 唯一串行单项最终通过；最终证据待独审核对。**实施者未自行运行测试**。根因来自本轮功能复审 F2；不涉及仍在设计的 F1，不更改计划完成度报告的 `73f57c6` 基线结论。

## 根因与最小修复

真实 `history.managed_calls` 消费 P2d 共同退役 validator 后，保留 `status='not_submitted'`、`completed=None`、`terminal=None` 与独立 `retirement/originals`。这是永久未提交证明，不是 completed 或 unknown。

`contracts.seal_result → checkpoint.capture → worker_delivery.capture` 原先在当前和历史两处都按 `status!='unknown'` 把该行当科学观测，且工作事实行不复制 retirement。写出 fact 后，`worker_delivery.validate` 必须拒绝其缺失 completed，导致本可如实 blocked 的 W 不能封存。

本节点只在 `worker_delivery.py` 复用现有 `known_success/known_failed/unknown/not_submitted` 分类：

- 仅 known_success/known_failed 进入 evidence；仅 unknown 进入 unknown。已验证 not_submitted 不归入其中任一集合，完整退役事实继续由 canonical host-history observation 及原 seal 保留，不新增 work-evidence 字段、schema、账或副本权威。
- known evidence 的 validator 与既有 `_candidate` 判定同样只认两种真实结果状态，不把任何未来的“非 unknown”状态泛化为观测。
- W 的 blocked 科学 finding 仍沿原 assessment 变 partial，交普通 A；伪称 observed 而没有结果仍不能交完整工作。search 原来就只让具有 exact known 结果的科学 finding 支持 screened，本节点不改科学选择或计数。
- accepted 科研机会不因永久未提交退款；不伪造完成、退出码、outputs 或外部 job ID；不改变资源释放的 P2d/ledger owner。

## 精确文件与定向负控

1. `src/scidiscovery/research_loop/worker_delivery.py`：两处 capture 选择、unknown 分支与结果校验谓词。
2. `src/scidiscovery/research_loop/history.py`：实际复测发现的同路径一行补传，把原 job 冻结的 breadth 传给 retirement 的 Records owner，不跳过 accepted 机制核验。
3. 新 `tests/research_loop/test_worker_delivery_retirement.py`：单个顺序用例，复用 `_ManagedTCADBackend` 和原小 v2 package fixture，真实 `Records.accept(mechanism='P') → TCAD retire_original → verify_retirement → history → W seal`；同用例修改 source-H 绑定要求原 Records 拒绝。
4. 本报告。独审由另一作者记录。

用例断言：无 submit/外部 ID/completed；原 observation 保持 not_submitted 和可核退役 proof；工作 evidence/unknown 均为空；W blocked 以 scientific_blocked/partial 正常封存并路由 A；改为 observed finding 不能交完整工作。随后原 A→后继 W 走历史选择分支，仍可如实 partial；A 无法把该机制判 screened，accepted count 仍 1、opportunity_unknown 为 false。只读 validate 不改原件；最后篡改 archived retirement 后原 seal 验证仍拒绝。

可信 stand-in 仅包括 transport 和 gate 依赖，沿用已有 P2d 测试边界；实际退役/归档/封存/assessment/search 为生产函数。它不证明真实 TCAD 原子 fencing、执行批准、平台身份、浏览器或 solver。没有固定 completed 成功 JSON，没有 stub capture/validate 为通过。

夹具加载仍复用现有 `tests.operations.test_runtime_plugin_configuration` 中的小 backend/package helper；该测试模块会传递 import 旧 Root/MCP/runtime。本轮不将它说成零旧体系加载，也不为消除此测试加载耦合再造一套 transport 框架；后续共用夹具归属可独立收缩。显式导入并请求 `execution_registry`，不依赖宿主刚好已安装 local entrypoint。

## 静态检查、复测与限制

实施者仅 stdlib AST/text 检查三个 Python 文件，未项目 import、pytest/collect、CLI、进程业务、HTTP、安装/build、模型或远端运行，未 Git 写入/提交。root 最小目标：

`tests/research_loop/test_worker_delivery_retirement.py::test_retired_screen_call_seals_partial_and_cannot_be_reused_as_observed`

如该用例暴露具体既有路径风险，才追加原 `test_worker_delivery.py::test_complete_findings_use_original_failed_observation_and_validate_never_rebuilds`；不扩全库、安装或远端矩阵。

已由旧代码写出的无效 work-evidence 原件不会被静默重写/删除；本节点修正新 capture，未增加旧坏快照迁移或恢复协议。这类原件若实际存在，需要另按原身份/封存边界判断修复，不冒称重新调用可自动恢复所有旧实例。

## root 初次执行与同路径增量

- 首轮单项失败发生在 fixture package 的 canonical JSON 准入，尚未进入 F2 路径。将测试的 `c.write(model_dump)` 换为与已有 P2d fixture 相同的 `canonical_json` 字节写法；独审确认只修夹具，生产未放宽。日志：`.trial/functional_reaudit_20261017/f2-source/batch-001/pytest.log`。
- 第二轮单项进入真实封存链，发现 `history.managed_calls` 虽然先使用原 job breadth 验过 accepted，随后构造 retirement 的最小 config 却漏传 breadth；`Records.accepted` 正确拒绝带机制的 call。日志：`.trial/functional_reaudit_20261017/f2-retest/batch-001/pytest.log`。这是新暴露的生产接缝遗漏，不能归作夹具失败。
- 经 root 批准，仅在该最小 config 传同一 job 的 exact frozen breadth。`history.managed_status`/archive 的直接 `verify_retirement` 不构造 Records，无同类需求；recovery/resume 与 progress 消费原完整 config，无须改写。没有兼容层、第二份绑定或新 schema。
- 同单项补 source-H hash 错配拒绝，确认原机制 validator 保持严格；仍保留后续 archived retirement 篡改拒绝。该次修正后重新冻结，root 仅重跑上述原单项，结果如下；没有扩大矩阵或重跑其他已通过项。

## root 最终定向结果

三个独占串行批次执行的是**同一个 unique 用例**；不是三个不同用例通过。日志、资源原件均保留在 `.trial/functional_reaudit_20261017/<组>/batch-001/`：

| 组 | 结果/性质 | 监督耗时 | 进程树 RSS 采样峰值 | 清理/内存止损 |
| --- | --- | --- | --- | --- |
| `f2-source` | 1 failed；canonical JSON 夹具错误，未到 F2 封存路径 | 1.925 秒 | 118317056 bytes（112.836 MiB） | cleanup_complete=true；triggers=[] |
| `f2-retest` | 1 failed；真实 history retirement config 遗漏 breadth | 1.625 秒 | 123412480 bytes（117.695 MiB） | cleanup_complete=true；triggers=[] |
| `f2-breadth-retest` | **1 passed**；pytest 1.94 秒；含当前/历史 screen、机制绑定和退役 proof 负控 | 2.211 秒 | 113655808 bytes（108.391 MiB） | cleanup_complete=true；triggers=[] |

监督总耗时 5.761 秒，三批最大采样峰值 117.695 MiB，没有内存止损，全部清理完成。实施者只读现有 `pytest.log/resource.json` 核数，未再执行该用例。采样观测不是 cgroup 硬隔离或绝对防 OOM 保证。

最终通过只证明该可信 transport/gate 夹具下的 F2 组合边界；不是全库、全部 retirement 消费者、真实 solver/平台身份/人工授权或旧坏事实迁移的资格。不累计前两次失败为新样本，不删除失败日志，不补跑安装或其他已通过测试。
