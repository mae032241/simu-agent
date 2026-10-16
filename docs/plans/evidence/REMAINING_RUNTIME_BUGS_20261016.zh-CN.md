# 剩余 runtime 缺陷窄审计（2026-10-16）

受审：`123/scidiscovery-e5.2`，HEAD `70afb76004b0532e5cd26f9bfd93529660785853` 加当前 B1/B2/B3 未提交修复。只读生产源，未修改、commit、push。应用外层 `scid-cross-boundary-review` 和 `scid-change-scope-checks`；未重报已修 B1/B2/B3、旧 history/guidance 测试失配或产品能力缺口。

## R1 — P2：首轮 H 建任务异常被未绑定 engineering 局部变量遮蔽

- 精确位置：`src/scidiscovery/research_loop/controller.py:456`；局部导入在同函数 `:431` 和后续 audit 分支，使整个 `_run` 的 `engineering` 都成为局部变量；首轮 H 不执行这些赋值。
- 触发条件：第一次 W/audit 导入之前，`contracts.build_job` 抛出任意异常。真实输入校验、I/O 失败都可触发。正常成功路径不触发。
- 因果复现：全新 prepare，真实 `contracts.build_job(root,1,'H',[])` 建好保留 job；仅改变节点自己的 `inputs/global/objective.md` 副本（冻结的原 global 不变）。直接再次 `build_job` 给出 `ValueError('Bound input copy changed')`；实际 `controller.run(root)` 同一代码路径却给出 `UnboundLocalError("cannot access local variable 'engineering' where it is not associated with a value")`，其 `__context__` 恰为原 ValueError。
- 影响：输入损坏/环境故障的首个异常类型与诊断被控制器自身异常替换；CLI 返回非结构化栈错误。不能据此声称正常 H→W→A 必然失败、证据被篡改成功或重复 native 请求。
- 最小修复：使用模块顶部已有 engineering 绑定，删 `_run` 内两处重复局部 import，或在函数入口无条件绑定；保留原输入拒绝。回归检查异常来源（预期诊断仍可见）及正常 H 路径。

## R2 — P2：可证明无执行的建任务故障也将 active 预算留在 advance

- 精确位置：`controller.py:214–215` 的 `run` 没有异常收口；`:438` 已开启 advance，`:453` 的建任务异常在 `_finish` 之外逃逸。`budget.py:157–169` 对最后的 advance 事件持续累计至下一次 snapshot。
- 同一复现实际保存：`clock_phase='advance'`，`ledger_events=1`，`native_intents=[]`。整个探针无 native subprocess/实验/交付动作。`run` 已释放 host writer 后仍无 paused 事件，亦无 runner 可以执行 `_complete_clock`。
- 与 R1 独立：即使删局部导入让原 ValueError 正常传播，`run` 仍没有 finally/except 调用 `budget.inactive`，计时仍留 advance。这里不存在“未知 native 工作仍在运行，所以不能停表”的必要条件。
- 影响：遇这种明确发生在 native 提交前的错误后，操作者排障的空闲时间继续消耗 active 预算；足够久后，即使修复副本，原额度也可能已耗尽。未通过等待100秒实际耗尽，本结论依据实际保留的 advance 事实与 snapshot 累计算法；未声称会退款或越权扩额。
- 最小修复：在仍持 host writer 时，对未处理异常执行预算收口并重新抛出原异常；复用 `budget.inactive` 的执行未知/存活检查，确有未知执行时继续 advance。不要无条件 paused，也不要重置原消费。另对 `closeout()` 同类逃逸路径作定向检查后决定是否共用入口处理。

## 证据与限制

- 探针 `/tmp/scid-controller-engineering-probe-20261016.py`；实际结果 `/tmp/scid-controller-engineering-probe-20261016/result.json`（完整异常因果栈和预算 snapshot）。
- supervisor `/tmp/scid-controller-engineering-supervise-20261016.py`；资源 `/tmp/scid-controller-engineering-resource-20261016/resource.json`，测试日志同目录。
- 与 B2 执行者先协调后使用仓库 `serial_lock` + `run_one`。returncode=0，0.165秒，RSS高水位25,853,952 bytes，cleanup_complete=true。只启动探针 Python，没有模型、solver、外部提交或旧场。完成后已通知释放锁。
- `git diff --check -- src/scidiscovery/research_loop/controller.py src/scidiscovery/research_loop/native.py` 通过。
- 已读 controller 普通/closeout 异常分支、native outcome→wait/seal、runtime runner/watchdog/owner身份、budget admission/continuation/step/closeout ledger、contracts build/seal/validate 与 execution continuation chain。没有再找到达到同等确证门槛的新恢复/预算重置/重复外部提交缺陷；此句不是全库 PASS。未运行全套pytest、installed wheel、真实模型/solver、主机重启或平台/UI场。
- 冻结 SHA256：controller `77f555aa4d6993ba3f25e9135488c4cc962511a0157c60b8e1e83007fa7f9e48`；native `5ececc9fe925865a9fac1204d43149aed25edd1bbbe2cf7f7aa77fe5e020af29`；runtime `ddacca632029a5981f6e6c7f090fb6b29436afdf462a240afc22c3d5718f5125`；budget `0fbb41cf0a53f4555ad56ee1db9e6176e2421acbf9a86e5b0756e294bea3e751`。
