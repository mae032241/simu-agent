# P2c TCAD managed wrapper 独立代码审查

## 结论与范围

**静态代码审查 PASS**，最终复核时 HEAD 为 `00cb132`。受审为[实施记录](P2C_MANAGED_EXECUTION_IMPLEMENTATION_20261017.zh-CN.md)列出的五个代码/配置文件：新 `managed_execution.py`、既有 `runtime_plugin.py`、插件 `pyproject.toml`、共通 `experiments.py` 的两处差异、既有 `test_runtime_plugin_configuration.py` 的五个新增用例。P3b/P4a 同期差异不在此节点范围。

审查独立于实施者，仅做文本/Git/精确调用链阅读，没有运行测试、收集、项目导入、CLI、构建安装、模型、SSH 或 solver。以下是静态正确性与负控证明目标，不是运行验收。

## 主链路

- `build_managed_runtime:493` 只接受声明的配置字段，固定不注入可信 gate；JSON gate/test/allow 路径不能启用生产。新注册 `tcad_execution:tcad` 复用原 RuntimePluginFactory，opaque/result_protocol=None，不造 command/entry/snapshot/candidate 协议。
- `prepare:167` 在本地核 descriptor/profile/ExecutionPackage 后先 `_check('prepare')`，才调用底层 adapter.prepare；不会先调用远端 capability 验证。target 来自冻结宿主 transport/config 文件身份。真实 P3 gate/resolver 尚未接入，默认在底层 prepare/upload 前 blocked。
- 准备目录分别保留原 payload descriptor 和复制后 descriptor，两者只允许 local_path 差异且字节身份相同。submit gate 仍消费同原 payload subject，不悄悄换路径取得新授权。返回 prepared.name 保留同 call；`_bound:210` 核 accepted/native_attempt/interface/prepared/原 source copy 与 gate ref。
- `submit:256` 先 lookup 原 prepared，核已知 external ID。只有当前 fresh lease 可首次提交，backend 副作用前独占写持久派发意图；重启/既有意图且 lookup None 为 unknown，不重发或退款。prepare/submit 必须同 owner receipt/admission；P2 不自写 grant/余额。
- query 不 collect。result/collect_original 通过原 gate/current remaining 收集；`_collection:334` 统一供首次、collected 已落的恢复、completed 复核使用，核 call/scope/mechanism/external/prepared/target/status/outputs 及原 call 内的 retained 路径，重验完整 manifest/log/inventory。恢复已有 collected 不再 query/recollect；cancelled 保留原 native_state，仅作工程 known_failed。

## 本轮指出并修复的边界

1. **共通终态缺证据**：原 record_observation 会直接读 completed。经 root 批准，现仅在 result 显式 unknown 且无 completed（包括无链接）时返回 None；已有 canonical completed 的矛盾仍拒绝。新调用扫描所有 known terminal 都要求 verified observation，缺证据保留原 call unknown，不能只对 cancelled 验证。
2. **收集恢复身份**：collected 已落但 completed 未落时，不能只信 collected 的 native_state/outputs 后发布成功。最终与原 terminal/backend binding 对照，并用同一完整清单校验；没有另建恢复账或绕过原 Records。
3. **本地保留预算**：初稿只给远端 collect 传 context，之后大日志 hash/copy 无截止。最终 `_proof/_copy_original/_inventory/_collection` 的分块和阶段校验共用同一个原 CollectionContext，首次/重入到 completed 发布前均检查剩余；过期保 raw/partial、返回 unknown、不造完成。明显错 size 的 manifest 在解析前拒绝，不加新容量 cap。

这些是可达代码路径问题的修补，没有动态性能或此前 OOM 根因结论。

## 五个定向负控的实际价值

| 用例 | 哪种生产缺陷会使其失败 |
| --- | --- |
| `test_managed_tcad_default_factory_blocks_before_any_backend_call:435` | 默认 factory 绕过缺 gate、先触发 backend，或接受公开 JSON gate 开关。其 backend 是可信注入替身，不代表实际 transport 已验收。 |
| `test_managed_tcad_retains_cancelled_original_without_requery:456` | 错 lookup external ID 被接受、丢 cancelled、丢 manifest/log、重复查询/收集、或原 binding 篡改未被拒绝。状态序列及预期独立列举，没有从生产 pending 集合生成答案。 |
| `test_managed_tcad_unknown_and_unverified_terminal_block_new_call:487` | 丢提交响应后重发、无 collect 权限却造 completed/放新 call，或用中性 unknown 隐藏已存在的 completed 矛盾。实际 dispatch 与 observation 仍走生产控制函数。 |
| `test_managed_tcad_collection_expiry_preserves_unknown_and_partial:517` | 本地复制无视同一 context、过期仍发布完成/再 collect、或原 raw/partial 被丢弃。受控注入只模拟截止到期，实际复制与控制消费路径保留。 |
| `test_managed_tcad_collected_crash_window_revalidates_retained_facts:540` | 恢复盲信被篡改 native_state，或恢复需重新查询/收集。模拟崩溃只停在 canonical completed 发布前，验证的正是本轮恢复窗口。 |

fake backend 提供合成 native 状态/manifest，prepare 内调用真实 P2b materializer/packager。这些确定性输入检验 wrapper 如何绑定和验证原件，不是“真实 TCAD 成功”证明；gate 语义由可信测试依赖代替，不能证明未来 P3 UI/策略/累计预算正确。没有新 Root/runtime/安装 fixture 或环境矩阵，旧测试模块原有导入不等于本次调用了旧 Root 环境。

## 保留限制

CollectionContext 是阶段/块之间的合作式截止，无法中断单次文件系统调用、JSON/Pydantic 解析及最后的原件发布。已有 completed 的完整只读核证、共通 observation 后续原件校验/复制未获得新的硬实时保证；完整 JSON 仍需要内存。没有动态 RSS、并发、文件系统隔离或实际大文件证据。

真实底层 adapter/远端返回是否正确关联原 job，仍依赖其既有受信协议；fixture 不证明 SSH、许可证或 solver。当前 source resolver/可信 gate、P3c/d 累计授权与预算、P2d retire/恢复均未完成。注册成功不允许真实 prepare/upload/submit。

另已定位供独立 P5 窄节点处理的既有 import 耦合：runtime_plugin 顶层 debug imports 和两底层 adapter 从旧 execution_bridge 导入 AdapterCapability 可加载旧 service 包。它不构成当前新执行旁路，但本节点不能宣称已彻底脱离旧栈；后续只应延迟旧工具分支 import、改用现有中立 owner，不移植旧服务。
