# N6a：全角色节点预算

范围：N6a 节点预算防护，最终源码与安装门禁独审通过；不启动真实模型、不修改 N5 实例。

## 接线与边界

`prepare --node-budget-policy` 只接受恰有 H/W/A/E、每角色恰有正整数 `max_observed_tokens` 和正有限 `max_seconds` 的 JSON；无生产默认数值。操作者明确冻结数值及其测量依据或试用假设。总额度不足容纳本节点有效阈值时不接受新意图；W 两维分别与现有 search policy 取小值。

接受时在原 `native-intent.json` 写一个 `budget_slice`，绑定 job、角色、同 boot 推进起点、角色有效阈值及共享边界；真正 Popen 前重查，在完成用量事件和运行轮询中检查停止。W 的原资格、修复计数与报告复用同一锚点，未增加另一个消费起点。未启用该字段的旧实例继续原 search_slice 路径；既有冻结实例的协议 8 schema/view/job 字节不改；新实例只增加 settings 中的宿主策略及执行 intent 的预算锚点。

input+output 是观测 token，cached 已包含于 input，不重加。一个迟到完成事件可以大幅超过阈值，事件前也可能完全缺量。推进时间包括 runner 启动、轮询、停止与清理；角色阈值触发终止，不保证零 overshoot 或账单硬 cap。缺量、boot 失配、未知执行、清理未知仍保留原失败且拒重放，不封存硬停止输出为成功。

活动或未知执行时原 budget-amend 入口拒修订；合法终态后修订只改变总边界，原消费、角色策略、意图及已存终态报告不变。用户 pause 仍只阻下一节点，已接受工作继续计时。相同接受节点恢复不产生新锚点或新提交。

本提交不开放 delivery policy、reserve planner、closeout、交付 A 或 adapter。停止状态不表示已交 A、已提交或科学目标完成。

## 验证状态

- 首门禁 65 passed / 4 failed：两个失败夹具错误越过未封存 W，两个预期错误地读取 reason 而非真实 status 拒码。生产挡执行/拒科学洞行为正确。
- 修订 fixture 并追加预算修订负例后，父代理共享串行门禁 72 passed。
- 全部 `tests/research_loop`：312 passed /122.74s；之后仅追加接受前预算拒绝的精确诊断及负例，相关两文件最终85 passed /17.15s，未重复整套回归。
- wheel 安装后确定性 H→E→H→W→A、同锚点/重启/终态修订、时间/token硬停、准入拒绝及旧策略路径全部通过；0真实模型调用。
- 首次安装验证脚本错误期待硬停止exit0，实际CLI正确返回2；修正脚本后fresh result2通过，原失败记录保留。
- 外层证据：`.trial/n6a-checks-20261012/{first,second,rootless,final,source-freeze.json}`；安装：`.trial/n6a-installed-20261012/result2/`，含源码/wheel/安装模块哈希与逐命令记录。没有原实例写入。
- [最终独立源码与安装证据审查PASS](ROOTLESS_N6A_REVIEW_20261012.md)；不授予N6b交付资格。
