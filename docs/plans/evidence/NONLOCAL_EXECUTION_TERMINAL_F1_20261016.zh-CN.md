# F1：非 local 执行器的共同终态事实

针对 [通用平台边界审查 F1](GENERIC_PLATFORM_BOUNDARY_AUDIT_20261016.zh-CN.md)；实施起点 `727f5372549148fa2c0f40c51c5bd74692478954`。本次只开发及无模型验收，不启动真实远端任务或 solver。

## 根因与修复

已注册非 local executor 的 CLI、query、lookup、collect 能够成功，history 和 Worker 却各自要求本地 `terminal.json`、POSIX returncode、cleanup 与 transport 字段。合法 opaque-package 后端没有这些原生事实，因而被错误记成 unknown。原复现保留在 `/tmp/scid-nonlocal-boundary-evidence-20261016/`；未改写该历史证据。

控制层现在在既有 execution protocol 中生成不可变 `execution-observation.json`。它绑定 accepted、frozen interface、scope、call、mechanism、external ID、completed 原件，并保留 backend proofs 与 collect descriptors 的精确副本。adapter 的 `status_details` 和 `result` 必须一致；原件、状态冲突则拒绝共同观察。共同事实是机械投影，不新增科学 verdict，也不由 Agent 编写。

host-frozen interface 声明 `terminal_evidence`。local/cov 的声明来自实际执行器类，仍验证 cleanup_confirmed、transport_complete、整数 returncode 与结果状态一致；remote 由其原生后端证据证明终态，不制造本地 process/terminal。读取时将 accepted.interface 与精确 native attempt 的 host 配置匹配，不能凭 worker 修改的 marker 或 receipt 自报类型把 local 转入 remote 分支。

共同观察的 backend proof 副本逐项绑定 completed.proofs 的原 descriptor；collect 副本保留完整 descriptor 和哈希。远端原文件可以位于 instance 外，或在投影后被后端清理；科学封存只消费 retained 副本，不重新要求远端原路径继续存在。remote 携带 `result`/`outputs` 也遵循这条规则，不以是否包含某字段推断后端。

history、Worker delivery 与正式成果收集复用共同事实。产物使用控制层保留在 W 工作树内的精确路径，保持 checkpoint 的相对路径边界；A 通过已有正式父节点产物索引读取，不接触后台原路径。search 继续只消费已封存的 known observation，科学 screened 仍由 A 决定。

query 不会在缺失共同原件时补写历史或重新 collect；已有共同原件只读验证。同步终结的 run 和显式 collect 承担投影。缺失共同原件的新 interface 保持 unknown。旧 local/cov 原件只按已有严格本地 terminal 规则兼容读取，不迁移或改写旧 sealed 科学事实。unknown 不重放。

## 反例与负控

测试复用真实注册的 `DifferentExternalIdentity` 契约夹具，接受 opaque payload、返回不同 external ID，并继续断言不存在 process.json/terminal.json。合成的 H/W/A host anchors 只用于科学封存协议，不执行模型。

- success 与 failed：真实 CLI run/query/lookup/collect → W history seal → Worker screen evidence → A 正式读取 collect 产物并作 disposition → 后继 W admission。
- remote 原生证明在 instance 外，投影后删除，仍可封存和供 A 读取；分别覆盖有/无通用 result 字段。
- 缺共同原件、accepted/interface 冲突、completed 状态、external ID、retained backend proof、retained collect 副本被改，保持 unknown 或拒绝。
- local cleanup、transport、returncode、status 不一致和伪装 adapter_result 被拒绝；旧 local 与旧 cov 本地回执仍可读。
- collect 名称路径逃逸、非 canonical 名称和重名被拒绝；管理执行器首次在后续 native attempt 配置时仍挂载正确原件，错误 attempt 不借用缺失 origin 配置。
- readonly seal validation 不调用 adapter；unknown 原件阻止第二次 submission。

## 验收证据与限制

最终受管命令、结果、文件 SHA-256、wheel 身份及资源监督记录见 [机器证据](NONLOCAL_EXECUTION_TERMINAL_F1_20261016.json)。所有 pytest 由 `scripts/run_tests.py` 的 serial_lock/run_one 监督；测试与构建期间源码冻结，和 F2 共享测试锁串行。

安装验收使用新核心 wheel 与实际 fixture plugin wheel 的 entry point，独立 venv、`python -I`、空 source pythonpath。它证明真实安装发现与共同协议，不是真实远端运行资格。无模型、无 solver、无隐藏评分或科学最优结论；没有运行全套平台矩阵。既有 `completed`、progress 与后端查询保留执行状态含义，不能将其解释为科学资格或外部目标完成。

| 最终检查 | 结果 |
| --- | --- |
| rootless execution / Worker / breadth / generic inverse / local 定向源码 | 95 passed、1 skipped，92.63s |
| 最后移除 latest-config guard，精确复核旧 calls 跨后续收尾复用 | 1 passed，0.47s |
| 新核心 wheel + 真实 fixture plugin wheel，独立安装同一 F1 用例 | 21 passed、1 skipped，10.06s；legacy cov 原件兼容由源码 lane 覆盖 |

最终 wheel 基于 F2 独立提交后的 `da7d891848bcc0d4a0617095600c36380bebfa8a` 加冻结的 F1 diff。源码检查后仅移除了最后的 latest-config 先决条件并补同一 attempt 用例，已精确复核且包含于最终 wheel 21 项通过中；没有把前一整批检查误称为最后 guard 修改后的重跑。四项最终监督均 cleanup_complete=true、无内存保护触发。`git diff --check` 通过。
