# 按任务类型明确 W 工作单元（2026-10-14）

基线：`b7c73ae`。本轮复用既有分片与复核机制，不新增循环状态机。

## 实际根因与边界

既有控制层支持同一 W stage 连续受管实验及 `stage_intent=continue` 分片。
最终 W 封存才路由 A；不是每次实验派 A。科学 `review` / `decision`、控制层
复核、未知执行与预算条件均有现有出口，不能通过强行覆盖 W 意图来省交接。

当前模型入口对工作单元描述笼统。improve 已允许持续尝试，却容易被派发的
单个“证明改善”的问题收窄为候选验证。本修订在入口明确任务类型，仍保留
用户原文、H 范围及 A 的具体问题，不能把强制验证降为建议。

## 设计

新 W job 按已有冻结 action 保存一段 scientific_work_unit 科学说明：

- screen：浅度覆盖所分配机制，以有区分力的试验得到发现或明确障碍；
- improve：同一机制内结果驱动的一段搜索，中间候选不等于阶段完成；
- validate：解决具体的必要验证与选择证据缺口；
- repair：修复已知失败，不凭此重开机制探索或重放未知提交。

任务 question 和 native prompt 读取同一冻结说明。模型无新增输出字段、
计数、文件引用或簿记工作。旧 job 未含该字段时不回填；冻结说明不随未来
常量变动而改写。默认和自定义角色指导、原始指令及直接证据仍保留。

正常连续工作复用现有执行/续接；科学障碍、范围变化或选择决策交 A。
控制层复核与共享预算继续优先。仅已配置且具恢复资格的工作可请求分片。

## 验收

生产仅在 guidance.py 添加四种短说明，contracts.py 冻结及投影该说明，native.py
用其替代通用完成说明。未改角色输出 schema、路由、准入、预算及分片权限。

- 新 wheel / 安装 / 实际 CLI fake-native 检查 PASS，0 模型请求。
- 安装包首批 **39 passed (25.66s)**：原指引、对称选择、收口回放，以及真实
  internal runner 分片、普通分片不消耗异常修复额度、控制层投资边界、停止后
  再检查复核条件、未知用量不续接、已知失败同线程恢复且不重放执行。
- 证据位于外层 `.trial/macro-role-installed-20261012/artifacts-task-unit-01-20261014/`。
- 新工作单元入口回归 **7 passed**：四种 action 的真实 native stdin 与 science-task 同源；improve 三次正常分片，无中间 A、无中间封存、原受管调用只查询，累计预算不重置；自定义/旧说明保持；无 action 不猜类型。
- 为下一场真实验收补跑 rootless fragment/resume namespace：**7 passed (19.94s)**。
- 三批合计 **53 passed**。初版新夹具因预算绑定缺失及空 question 索引失败（7 failed），已修为真实 native 前驱与真实 A 原指令，不放宽生产校验；保留失败日志。
- 追加证据目录：`artifacts-task-unit-finaltests-20261014` 与 `artifacts-task-unit-namespace-20261014`。
- 独立复审见 `TASK_UNIT_CONTINUATION_REVIEW_20261014.zh-CN.md`。

用户随后授权一场新版 cov 真实测试，沿用 600 万 token / 60 分钟。该场应在提交后启动，独立记录，不混入本次零模型验收。

未跑全量测试、真实模型、浏览器或 TCAD。无模型测试只能验证送达、冻结与
控制路径，不能证明科学搜索质量或实际 token 效率已经改善。
