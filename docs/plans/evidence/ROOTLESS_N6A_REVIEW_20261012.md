# N6a节点预算独立源码审查

结论：PASS，未发现剩余阻断。审查者/root/n0_baseline，未实施本次生产/测试或安装夹具，未运行测试/模型、未修改生产代码或原实例。使用cross-boundary审查，范围为实际CLI→controller→intent/runner→native Popen/停止/清理→封存→重启/预算修订与installed wheel。

基准b8d4fff3ae58e1cb93ef662d549858d876d41e2d。6文件冻结 .trial/n6a-checks-20261012/source-freeze.json SHA256 9c552b1fe32d1c2c4677f20d3ee73f76d82ad5764f4359404f2fa13f76c4454d，全部6项逐一一致。另审N6a证据doc SHA256 02c2fb7c4ebc6c6a8a55315954288bd4a079300500824c4a83db8424fd4aa73b。完整相关diff、原周边runtime/search/contracts与新test_node_budget.py均已读；git diff --check clean。

## 实际不变量

- 显式H/W/A/E node policy校验四role/两数值，无默认值或旧settings改写；controller准入、accept_node和真实Popen前重查同一共享边界。
- 真运行循环基于completed usage/推进时间阈值停止；input+output，cached不重复计。一次迟滞事件大幅超额、无completed usage及轮询/清理迟滞均明确，不冒称账单硬cap。
- 单一budget_slice冻结任务/角色/有效阈值/boot/advance起点/共享总边界；W新策略取原search与node两维最小值，search统计只临时映射同一锚点。旧无字段路径继续原search_slice；W成功后的统计仍有原dispatch，不因intent少旧字段丢统计。
- 原budget-amend只能无live/unknown时生效；新accept绑定修订后的共享边界，旧accepted锚点/终态报告/原用量不改。用户pause不停止/退款accepted原任务；controller重启重接原runner/同intent，硬停无seal/无伪A交接/无重放。
- 无usage/boot/完整性/cleanup未知拒继续，原schema/科学协议8及已有冻结job/view未修改。
- N6a没有delivery/reserve/closeout/adapter或半接线入口，只授予节点保护工程资格，既有route/N3/N4/global预算仍保留。

## 发现关闭与夹具判读

曾发现build耗时后二次accept拒绝尚无intent却报告retained intent。最终专用NodeBudgetUnavailable只在accept预算拒绝抛出，controller精准捕获返回budget unavailable，不吞其他ValueError/权限/identity异常。新负例真实build后推进55秒，验证无intent/无Popen、prepared job保留且重启不改。此发现关闭。

首4fixture失败为错误API/范围：失败W不可project越过未seal洞、node拒码在status不是reason。修订没有放松保护；失败W仍断言硬拒，另加成功W原统计。新夹具涵盖四role各token/time真实子进程、无completed usage、cache口径、late Popen拒绝、身份/boot失配、restart surviving runner、unknown不能amend、终态amend保原用量/报告、旧policy兼容。

## 亲阅证据

- 首65pass/4fail保留，第二72pass。
- .trial/n6a-checks-20261012/rootless/batch-001/pytest.log：312 passed /122.74s；其后仅typed诊断生产增量及对应负例。
- final/batch-001/pytest.log：85 passed /17.15s。未重跑全部313项，不声称最终全套再次绿。
- 安装首script期待hardstop exit0而实际正确exit2，失败log留存；修正fixture后fresh result2 PASS。
- .trial/n6a-installed-20261012/result2/result.json：实际CLI fake H→E→H→W→A共50token，single-anchor/restart/amend、真实time/token硬停无seal/无重放、fullcap拒绝和无node-policy旧路径均通过；0模型。
- wheel SHA256 fcff1084e0b8d104282b783c8b317a8a25949355ea7eb586cae12d32b4b32290；亲核全部11模块源文件、wheel ZIP字节、venv site-packages及module-bindings一致。已读check.py/build_check.py和最终命令结果，没有手装src替代安装入口。

限制：没有真实LLM在途成本验证，不保证零超额、预算内A收口或实际提交；没有授N6b资格/原N5恢复或扩额。可提交N6a，并以其commit为N6b串行实现基线；N6b仍须完整交付门禁和独审。
