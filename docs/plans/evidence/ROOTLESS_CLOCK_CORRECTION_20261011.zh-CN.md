# 真实第 2 场：时钟校正误停与修复

## 现场事实

冻结候选 `19f3e9f`，安装包、启动器和题目身份已核对，两场均准备为 600 万 token、3600 秒启用时长、最多 24 节点，GPT-6.1-sol / high / default。既有 live02 计第 1 场，未新增替代场次。

第 2 场只启动了 H；未封存，未进入 W，正式实验为 0。原生轨迹最后观测到总 token 79,327，未缓存输入加输出 22,751。原生 turn 未正常终结，控制层末态用量为 unknown，不能将其显示的 0 当成实际零消耗。

`native.py` 的运行中预算检查触发 `Control clock moved backwards; consumption is not refundable`，native 被 SIGTERM，返回 -15，普通进程组清理记录为 `observed_group_cleaned`。整组停止，第 3 场未调用模型。

## 根因

账本只有一个 advance 事件，未发生多个写入者追加竞争。同一 boot 内，诊断采样显示墙钟前进约 109.280575 秒，BOOTTIME 前进约 109.700350 秒，二者相差 0.419776 秒。代码中 `wall + .02 < elapsed` 将墙钟相对单调时钟的校正判为不可接受的时间回退。现场足以确认两种时钟不同步，不能据此确定宿主用了哪一种时钟校正服务。

已有 BOOTTIME 锚点的运行区间应只由同 boot 的 BOOTTIME 计算。UTC 用作审计时间标签；UTC 回拨和校正不能退款，也不应导致健康任务被杀。仍须拒绝跨 boot、单调时钟倒退、账本身份或顺序篡改；无单调锚点的旧 elapsed 实例维持其原有限制。

## 验收与后续

- 修复执行：独立 n1_runtime；独立复审：n_plan_review。
- 预算与运行恢复定向回归 38 项通过（5.47 秒）；精确重放现场时钟差，UTC 回拨不退款，负 BOOTTIME、跨 boot 与账本篡改仍拒绝。另补旧 elapsed 加账本后的回拨拒绝兼容负例，snapshot / transition / amend 三条路径保持拒绝且不改账本；最终独审 PASS，见 [review.md](rootless-clock-correction-20261011/review.md)。
- 独立安装包 CLI 零模型 6 节点验证通过：历史精确转交、候选四栏、恢复不重放、active 计时与预算修订均通过。安装包 SHA `2319f0b3bec9f289542cc8e0ce660ea9b9887f1e6ed1cd82ecab4ab03ba439b8`。
- 保留本场实例及完整轨迹，不重置预算、不覆盖失败记录、不自动补跑。
- 第 3 场仍是原授权的最后一场。若使用修复后的候选，单独冻结版本并注明与第 2 场不同；不再宣称两场是同版本重复实验。
- 本次未检验 H→W→A、候选历史、暂停恢复或真实科学质量。

现场小型证据见 [summary.json](rootless-clock-correction-20261011/summary.json)。完整模型轨迹保留在工作区 `.trial/rootless-n1n2-cov-20261011/case-02/`，不送回科研角色。
