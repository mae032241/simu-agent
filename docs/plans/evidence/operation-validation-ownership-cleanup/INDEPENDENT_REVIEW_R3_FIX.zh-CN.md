# R3 修复后的独立工程复审

2026-09-13。**结论：通过当前工程源码复审；无未闭合 P1/P2/P3。**

按用户要求，新建不继承父会话历史的独立审查者，对 [精确基线](REVIEW_R3_FIX_BASELINE.json) 至 [最终文件清单](REVIEW_R3_FIX_VERIFICATION.json) 复审。其只读核对315项基线快照和20/20个最终文件摘要（17生产、3测试），没有修改源码、运行测试或访问生产实例。主代理保存本报告；下列判断来自独立审查者的最终答复，不将测试通过数替代审查结论。

## 审查中发现并闭合

- P2：初版 calculation_reference_aliases 按记录字节合并，不同 Run 的局部 attempt_key 可以重名。MCP 对照确认误接受。最终通过受控 manifest、唯一 artifact_ref 和完整记录归一，后续 calculation_sources 验证保留；不同来源混用拒绝，同一当前、历史及恢复收据的双表示接受。
- P3：_execution_timing 在缺少开始时间时丢失已知结束时间。现独立保留合法时间字段，不虚构 elapsed。
- 原 handoff 错误已准确指向 $.deck.handoff.summary，runtime-failure 作者兼容 runner 实际导出的 charset 日志媒体类型。

## 日志与范围判断

作者轮询和 Root execution_sync 可获得同 job 的受限日志尾部及实际 elapsed；终态作者保留时间与受控日志读取路径。读取限两个2048字节片段、64个顶层条目，防止读取 symlink/FIFO，复用原脱敏器。旧 status-only 适配器保留 fallback，纯 status 查询不增加远端读取。

未新增角色、Operation、门禁、预算或 Agent 的 server 文件读取权限。finalizer 没有扩张科学文件读取职责；多文件增量对应既有日志传递链各层，未发现需要扩大架构的理由。

审查者实际阅读主代理执行的最终 [26 passed](check-1789267992598962851.log) 与 [84 passed](check-1789268051058413290.log) 日志。26项包含收据正负对照和四条日志路径。串行峰值约229.2 MiB，低于512 MiB；分组存在重叠，不累加统计。

## 证据限制

SSH 路径使用隔离传输夹具；未验证生产部署、真实 VM、实际 Python 3.6 解释器或 Sentaurus 运行。此结论是源码审查通过，不是部署或科学结果通过。失败交接中的 attestation 是合成 fixture，作者基底项目则经原 Worker 路径封存。
