# F2 永久未提交与 W 交付：独立审查

结论：**静态 PASS，可运行单项回归。** 基线 `73f57c6`；初审 `worker_delivery.py`、新 `test_worker_delivery_retirement.py` 和实施账，随后因实际失败加入 `history.py` 一行同 owner 修复，最终四文件。F1 来源/贡献闭环不在本修复范围，仍未实现。

## 生产修复

原缺陷见 `THIN_FUNCTIONAL_REAUDIT_20261017.zh-CN.md` F2。当前/历史 capture 均仅让 known_success/known_failed 进入科学 evidence，只有 unknown 进入 unknown；not_submitted 继续留在共同 history observation 的 retirement/originals，不制造 completed，不伪装成失败观察，不增加工作事实 schema。`validate` 与 `_candidate` 同步使用明确结果状态，而非泛化“非 unknown”。

capture 之前仍调用原 `history.managed_calls` 或历史 `validate_managed`，不跳过永久退役的共同原件验证。blocked finding 走既有 partial → A，observed finding 仍需实际结果；accepted 科研机会/资源 owner 不变，没有退款、清空计数或改变审批/派发行为。

## 回归可证伪性

单项用例实际经过 `Records.accept → TCAD retire_original → verify_retirement → history → W seal/assessment`，继而走后继 W 的历史分支与 A/search：验证无 submit/外部 ID/completed、原 proof 保留、blocked 可封存、退役不能充当 observed/screened、机会仍计一次且不是 unknown、篡改退役原件仍拒绝。若仍用旧 `status!='unknown'`，原 W seal 会抛异常，本用例因此能证伪根因；没有 mock 掉 capture/validate。

已核显式导入并请求 `execution_registry`，避免依赖宿主已安装 entrypoint；owner proof 位于原 record，可由实际 history 原件 loader 归档。transport/gate 使用可信 DI，不证明实际 TCAD 原子 fence、执行批准或科学身份。复用 operations 测试 helper 会传递 import 旧 Root/MCP/runtime，已在实施账如实保留该加载耦合；本小修复不为消除此限制另造测试框架。

旧版本已发布的无效 work-evidence 不会被静默重写；本节点修正新 capture，不宣称所有既有坏实例可自动恢复。

建议 root 首先只运行 `tests/research_loop/test_worker_delivery_retirement.py::test_retired_screen_call_seals_partial_and_cannot_be_reused_as_observed`；若暴露具体相邻风险再扩必要既有用例。不要求安装/全量/模型/solver。审查者只做文本/调用链与限定 diff 空白检查，无测试、收集、import、业务执行或 Git 写入。

## 首次定向失败后的夹具修复复审

root 首次单项日志 `.trial/functional_reaudit_20261017/f2-source/batch-001/pytest.log` 记录1 failed，1.50秒：在 `wrapper.prepare → project_packager.validate_execution_package_json:1344` 拒绝 fixture 的非 canonical JSON，尚未进入退役/工作交付路径。作者仅改测试，导入既有 `schema.common.canonical_json` 并用其原字节写包，与原 `_managed_tcad_case` 的写法一致。静态复核 PASS，未修改/放宽生产校验；允许 root 只重跑失败项。此处不预报复测结果，审查者仍未执行测试。

## 第二次失败后的实际 owner 修复复审

`.trial/functional_reaudit_20261017/f2-retest/batch-001/pytest.log` 记录1 failed，1.33秒：真正到达 `seal → checkpoint → worker_delivery → history.managed_calls → retirement → Records.accepted`。`history.py:242` 构造 retirement 最小 config 漏掉 breadth，带机制绑定的 accepted 因 `Unexpected scientific call binding` 被正确拒绝。这是生产消费者遗漏，不能记为测试 fixture 问题。

root 批准的增量仅在该 config 补入同一已冻结 job 的 `(job.get('search') or {}).get('breadth')`，与同函数前面的 `breadth.check_binding` 使用同一 owner；不从 accepted 反推授权，不跳过严格校验。已核直接 history/archive validator 不经此 Records 构造、其他原完整 config 路径不要求扩改。

同一用例追加 source-H SHA 错配的 config，要求 `Records.accepted` 仍抛精确 `IntegrityError`，没有改写原 accepted/proof 或降低身份约束。定点静态 PASS，可再次只运行原单项；本报告尚未以未执行的复测声明动态通过。

## 最终单项动态证据核对

root 第三次日志 `.trial/functional_reaudit_20261017/f2-breadth-retest/batch-001/pytest.log` 为 **1 passed，1.94秒**；对应 resource 为 returncode0、监管2.211秒、RSS113,655,808 bytes、cleanup_complete=true、triggers为空。它实际通过前述 retire → 当前 W封存 → 后继 W历史 → A不能screen → proof篡改拒绝链，去重仅 **1个用例**，不是三次独立保护。

已只读核对此前两次 resource：监管1.925、1.625秒；三批总监管5.761秒、峰值123,412,480 bytes（117.695MiB），全部cleanup_complete=true、memory_stop_triggers=[]。两次失败原证据保留：一次 fixture编码错误，一次真实 breadth 生产接缝遗漏。采样不等于硬内存保证。

最终结论：**静态 PASS，所选真实控制链回归通过，可提交四文件修复及本独审证据。** 没有运行安装、模型、真实 transport/solver或全套测试；不能据此关闭F1或旧无效work-evidence的迁移限制。所有动态均由root唯一运行，审查者未执行测试。
