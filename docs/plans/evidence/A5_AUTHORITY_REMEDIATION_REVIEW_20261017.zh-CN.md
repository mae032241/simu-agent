# A5 有限验收汇总独立核对

结论：**汇总证据静态核对 PASS，可提交文档。** 基线 `70226ed`；审查 [A5 报告](A5_AUTHORITY_REMEDIATION_ACCEPTANCE_20261017.zh-CN.md)、[机器结果](A5_AUTHORITY_REMEDIATION_TARGETED_RESULTS_20261017.json)、plans README、修复计划及主迁移计划的状态同步。动态执行者为 root；本独审没有运行测试。

## 原日志与统计

对 `.trial/authority_remediation_20261017/` 七个组的 `result.json`、`batch-001/resource.json` 和 `pytest.log` 逐项比较：targets、summary、返回码、监督耗时、RSS、cleanup 和 memory triggers 与提交汇总一致；资源配置与原 `resources.json` 相同，无差异。

- A4：4 source +4 process，通过 8 个用例。
- A2：5 source、初次 process 4 通过/1 fixture 失败、失败项修补后 1 通过，最终 10 个用例；初始失败记录保留，生产校验未放宽。
- A3：4 source +3 process，通过 7 个目标。
- 执行通过数为 **25**，另有 **1** 次初始 fixture 失败；A2/A3 重复 ordinary A 1 项及正式成功/重叠/未知身份 3 项，故不同用例最终通过数为 **8+10+7−4=21**，没有把重跑累加为新用例。
- 七批监督耗时合计 **36.492 秒**，峰值 **149008384 bytes（142.10546875 MiB）**；全部正常退出、cleanup_complete=true、memory_stop_triggers 为空。不是 cgroup 或绝对防 OOM 证明。

这是按节点增量验证：A3 改共享输入合同后补测了本次相关 7 项；不能说全部 21 项或全库都在最终 HEAD 重新跑过。没有因此要求重复已通过组或全局测试。

## 状态与资格边界

提交号 a6ca5a5/0a49e06/804f7a7/70226ed 与 A0/A1 文档、A4、A2、A3 对应一致。A0/A1 是可信 Worker 软边界说明；定向运行证据属于 A2–A4 实现，不是 A1 强隔离验收。

报告保留必要限制：身份分离不证明观点独立，默认输入去锚定不是盲评；global+subject 不是科学支持集完整性保证；export-only 无真实 adapter 提交；工程预留不续原 call，启动前过期仍 unknown/no-replay；旧冻结合同不静默升级。模型、solver、真实浏览器、跨宿主可写恢复和旧入口完整退役资格没有被此次结果替代。

README 已按审查建议明确区分“软边界文档已独审提交”与“A2–A4 实现已独审及定向验收”，并定点核对落盘，未把 A1 文档记成动态安全验证。其余计划入链与有限验收口径一致。

仅对已存日志进行只读文本/标准库 JSON 计算与限定 Git diff/空白检查，无报错；未启动 pytest/collect、项目 import、业务 CLI、安装、模型、服务器或远端作业，未修改生产/测试。唯一写入为本报告。允许 root 提交最后状态文档，不产生额外计算授权。
