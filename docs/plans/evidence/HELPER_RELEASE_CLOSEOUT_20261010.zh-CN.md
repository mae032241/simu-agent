# 辅助者释放与线程角色隔离：源码节点验收

日期：2026-10-10。基准：dev `edb1bcf`。本节点收口既有未提交的 release 指令及复审发现的重用问题；不宣称原生槽位已回收。

## 接受的设计

- 辅助者使用专用 fresh 线程。基于现有历史记录拒绝新的 helper→owner、owner→helper 角色转换；正式 Worker→Worker 的既有合法复用保留，无新增状态表。
- 首次 release 只对已受信挂接、没有 owner 历史的确切 helper 返回下一步立即执行的原生 interrupt 请求；completed 也中断。框架撤权不等于原生调用成功，不等于槽位回收。
- 重复 release 不重发动作；未挂接标记清理受阻；任何 owner 历史都阻止旧辅助者清理。不得凭旧 spawn handle 猜测或重放中断，不靠墙钟比较归属。
- 历史版本已经形成的 owner 绑定保留同 Run、同真实线程的 queued/running 幂等挂接恢复；只阻止新的角色转换。completed 仍沿既有状态规则拒绝 attach。
- 控制事务与外部原生调用不原子；任意原生 followup/线程复用在本控制边界之外。动作丢失或结果未知需报告未确认，不增加重试或伪造清理完成。

这收紧了辅助者线程的使用合同，符合即用即弃约定。不是仅增加一条“核对原生科学归属”的提示：原生接口没有这种核查能力，改用框架已有绑定历史约束自己的角色转换。

## 验证与审查

由 `/root/f0_test_debt` 独立实施、`/root/hwa_plan_review` 独立审查。两轮旧方案的缺陷保留在证据中，经过设计检查点后实施本版；最终生产语义审查 PASS。

所有测试使用共享串行锁下的 `scripts/run_tests.py --lane source`，范围为 `tests/operations/test_r4_internal_helpers.py`：

- `checks-04`：新设计 7 个关键节点通过，21.990 秒。
- `checks-05`：其余 10 个关联节点通过，26.987 秒。
- 最终审查发现 legacy 精确挂接恢复被提前拒绝，修正后 `checks-06` 重跑 5 个关联节点：全部通过，16.138 秒。已通过且不受改动影响的用例未重复运行。
- 三轮均正常清理，无资源停止；限定 AST 与 `git diff --check` 通过。

以上为分组通过证据，不是最终候选一次全套通过。未运行全量、安装、真实模型或原生 interrupt/slot 资格探针；原生生命周期另由 F1a/F4 验证。

## 证据

外层工作区 `.trial/hwa_revision_20261010/helper-release/` 保存 `DESIGN-02.md`、
`REPORT.md`、`final-candidate.json`、`PATCH.final.diff` 及六轮 checks。前三轮属于已被后续设计替换的方案，不能冒充当前方案验收。
