# 执行组合链 R1/R2 修复独立复审（2026-10-16）

## 结论

**PASS：原 R1、R2 两项新 P2 在本次精确范围内可关闭；未发现新的 P1/P2 阻断。** 这是限定工程验收，不代表真实远端服务、模型科学判断或所有恢复路径已通过。既有 G3 不在关闭范围。

独审仅写本文档，未改生产代码、测试或提交。使用 `scid-cross-boundary-review` 与 `scid-change-scope-checks`，完成语义审查、冻结身份和原始证据复核；复用充分证据，未另跑 pytest、模型或 solver。

## 精确身份

- 范围为 [实现 JSON](COMPOSED_EXECUTION_RESULTS_R1_R2_FIX_20261016.json) 所列 **8 文件**：5 个生产文件、1 个新 fixture、1 个新测试文件、1 个既有测试文件。独立计算的当前 SHA256 全部一致；生产文件也与 wheel 构建源快照逐字一致。未将归档修复归入本结论。
- 源基线、wheel 构建时 HEAD 为 `53798e9798f6634bd2b62ecedb2bc03e742a7411`，叠加当时共享工作树。核对时 HEAD 已为归档单独提交 `6962871b73c0158a17c5dc290b6bc079120d1492`；没有以此新 HEAD 重建 wheel 的证据或主张。
- 核心 wheel SHA256 为 `78d6f31a777901bf6b1bc8154aef1dc695b6f72387f16cd216c8e31293d60e2f`，独立计算相符。安装证据的 241 个核心文件无源字节差异；实际 fixture 来自 venv 的 `scid-composed-contract-fixture` entrypoint，其模块和隔离测试副本与冻结文件逐字一致。

## 跨边界复审

| 项目 | 代码与可达路径结论 | 实测覆盖 |
| --- | --- | --- |
| R1：opaque result 碰撞本地候选协议 | `experiments.freeze` 将显式 `result_protocol` 冻结在 host interface；history 从该绑定生成并校验 marker。默认 opaque，不依据私有字段名推断协议。三个 observer 分支共用受门控的候选解析器。 | 空/native/local-like 私有结果 × 三种 observer：共同终态→W seal→A 读取正式成果；不生成本地候选，私有原件保留。 |
| 显式坏映射 | 唯一 metric/artifact、有限数值与必要字段校验失败时给出有界 `declared_candidate_mapping_invalid`，不再因缺失映射触发 `StopIteration`；不把执行成功提升为科学合格。 | 两种坏映射 × 三分支，执行事实保留、无候选、有诊断。 |
| 本地与历史兼容 | LocalExecution 显式声明 local v1。缺 marker 的旧 row 只从精确原 host interface 读取语义；旧 `local_execution:command` v1 有窄兼容，旧远端保持 opaque；不改旧 seal。 | 既有 generic 两方案选择、目录交付与重放；旧 row 的来源解析及协议兼容断言；既有 nonlocal/local/cov 回归。 |
| R2：异步无 collect 的终态入口 | CLI `reconcile --call-id` 可发现，复用同 call 的终态冻结；不走 accept/dispatch/submit。`collect=false` 不调用 collect。既有投影校验后直接返回，不再读取后端。 | success/failed 均覆盖 unknown→后端完成→reconcile→W/A→后继 admission；collect 禁用负控、一次原提交、重复确认字节不变及后端禁读负控。 |
| 身份与只读边界 | accepted/interface/scope/mechanism/external ID/proofs 沿原共同终态校验路径约束。`query` 不创建投影。既有 `lookup` 可补写缺失 submission 绑定，不能泛称只读；本次已绑定 lookup 的记录不变。 | interface、external ID、native proof 篡改均拒绝；query 与已绑定 lookup 的前后快照一致。 |

## 证据核对

| 批次 | 原始结果及解释 |
| --- | --- |
| `/tmp/scid-composed-execution-fix-source-01/batch-001/` | `56 passed, 1 failed`，74.71s。失败属于新增 helper 假定 unknown 也有 experiments 索引；原失败日志保留。 |
| `/tmp/scid-composed-execution-fix-source-02/batch-001/` | helper 修正后 G3 与两项 async 窄复核 `3 passed`，4.76s；因此 57 个不同源码案例最终转正，不能称单批全绿或相加成 59 个不同案例。 |
| `/tmp/scid-composed-execution-fix-installed-20261016/check/` | 独立 venv、真实 entrypoint、`python -I` 隔离 CLI，`21 passed`，14.43s；无仓库 src 回退。 |

已检查原始 pytest 日志、resource.json、安装身份和 build/check/supervise 驱动；均由 `serial_lock/run_one` 管理，`cleanup_complete=true`。精确范围 `git diff --check` 无输出。完整路径及机器身份见实现 JSON 与[实现报告](COMPOSED_EXECUTION_RESULTS_R1_R2_FIX_20261016.zh-CN.md)。

## 保留限制

- **G3 仍在：** 已 sealed unknown 的 W，late reconcile 只冻结当前同 call 事实，旧 seal 字节和 unknown 结论不变；不能据此宣称旧 reservation 恢复或后继机会解锁。回归明确保留此边界。
- 后端完成由 synthetic registered fixture 驱动，H/W/A 为无模型 helper；没有真实网络后端、真实科学判断、全量套件或所有并发恢复组合验收。目录交付确认也不表示向外部服务提交。
- 本报告不关闭其他归档/provider 审查项；两项修复的通过不等于框架全局无缺陷。
