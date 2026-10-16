# 执行组合链 R1/R2 修复证据（2026-10-16）

状态：实现与定向无模型验收完成；冻结后交独立审查。本报告不代表独立审查通过，未提交或 push。

## 身份与范围

源基线和 wheel 构建时 HEAD 均为 `53798e9798f6634bd2b62ecedb2bc03e742a7411`，叠加当时工作树改动；其他执行者的归档改动也在该 wheel 的源码快照中。构建完成后，归档单独提交 `6962871`，执行侧文件未变；没有声称以新 HEAD 重建 wheel。完整 wheel 源快照在 installed 证据根 `source/`，241 个核心文件与实际安装逐字相同。执行侧精确 8 文件 SHA 见同名 JSON，不能把共享工作树全部 diff 归给本修复。

根因来自 `GENERIC_EXECUTION_COMPOSED_REAUDIT_20261016.zh-CN.md`，原 probe 保留在 `/tmp/scid-composed-execution-reaudit-20261016/`。本轮只修执行侧两项，不改归档/provider。

## 实现

- R1：执行器可声明 `result_protocol`，由控制层在 host interface 冻结；默认 opaque。LocalExecution 明确声明 `scidiscovery.local-result.v1`。该声明与终态证据协议正交，私有 `result`/`candidate` 字段不会触发候选解释。history 由精确 host interface 生成 marker，读封存事实不加载插件。
- 三个 observer 分支都使用同一候选解析器。显式声明的坏 metric/artifact 映射产生有界 `declared_candidate_mapping_invalid` 诊断，保留执行事实和原始私有结果，不注册候选或宣称科学合格。
- 历史兼容只对已冻结的精确 `local_execution:command` v1 绑定补充读取语义，缺协议的远端保持 opaque。旧 sealed row 缺新 marker 时，交付来源从原 host interface 解析；不改写旧 seal。
- R2：CLI help 与 ManagedExecutionInterface 契约公开 `reconcile --call-id`。该显式动作复用原共同终态投影路径，验证同一 accepted/interface/scope/mechanism/external ID/proofs；不 accept、submit 或获取 dispatch lease。`query` 保持只读；本轮已绑定的 `lookup` 不改变记录，既有 `lookup` 补写缺失 submission 绑定的能力不变。未声明 collect 的后端不调用 collect；有既存投影时校验并复用字节，不重查询后端。

## 定向验收

全部测试在仓库 `serial_lock`/`run_one` 与默认资源限制下执行，无并行 pytest、模型或 solver。

| 批次 | 结果 | 原始证据 |
| --- | --- | --- |
| source01：新 composed + generic inverse + 既有 nonlocal observation | 56 passed / 1 failed，74.71s；唯一失败是新增 helper 假定 unknown 也有 experiments 索引 | `/tmp/scid-composed-execution-fix-source-01/batch-001/pytest.log` |
| source02：修正 helper 后只复核 G3 + 2 async，加入 CLI help 可发现断言 | 3 passed，4.76s | `/tmp/scid-composed-execution-fix-source-02/batch-001/pytest.log` |
| fresh wheel：独立 venv、真实 registered entrypoint、隔离 CLI | 21 passed，14.43s | `/tmp/scid-composed-execution-fix-installed-20261016/check/pytest.log` |

因此源码共 57 个不同案例转正，未抹掉首批失败日志。所有 resource.json 均 `cleanup_complete=true`；installed build/check 监督用时分别 3.698s / 15.018s。各批 resource.json 与上述日志同目录，source01/02 另有 result.json。installed 根保留 build.py/check.py/supervise.py、wheelhouse、installed-identity.json 和构建源快照。

核心 wheel SHA256：`78d6f31a777901bf6b1bc8154aef1dc695b6f72387f16cd216c8e31293d60e2f`。真实 fixture 分发为 `scid-composed-contract-fixture`，工厂来自该 venv site-packages；CLI 使用隔离解释器，不从仓库 src 回退。

已覆盖：opaque 的空/native/local-like 私有结果在三种 observer 下 known→W seal→A 成果字节读取；显式坏候选的两种形状在三分支给有界诊断；异步 success/failed 的初始 unknown、只读 query 与已绑定 lookup 记录不变、collect=false 拒绝与 reconcile 转正、无 process/terminal 假回执、A 解读后后继 admission、重复 reconcile 字节不变且禁后端查询、同 call 不增提交；accepted interface、external ID 和 native proof 篡改拒绝。既有 generic inverse 两候选选择/目录交付/精确重放与旧 row 缺 marker 来源解析通过；既有 nonlocal/local/cov 终态及篡改回归通过。

## 保留边界

G3 未修：原 W 已 sealed unknown 后 late reconcile 可冻结当前原 call 事实，但不追加新的科学输入，也不重写旧 seal。回归只证明旧 seal 字节及 unknown 结论保持；不能把它报告为旧 reservation 已恢复或后继机会已解锁。before-seal reconcile 的正常后继 admission 与该限制分别验证。

这里的 backend 完成由 synthetic registered fixture 事件驱动，H/W/A 为无模型 sealed helper；不是实际远端服务或模型科学判断。没有全量扩测、真实 solver/付费模型/网络服务验收。目录交付确认只证明目录成果已交付，不代表外部服务提交。
