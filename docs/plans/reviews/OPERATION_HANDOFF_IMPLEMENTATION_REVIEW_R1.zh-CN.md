# Operation 交接实现独立工程审查 R1

日期：2026-09-09。最终结论：**PASS（限定静态工程审查）**。本次发现的 F1 已由实施者修复，审查者复核闭合；目前没有剩余阻断发现。该结论不代表测试全部完成、真实科研闭环完成或 C 已实施。

审查依据为 `scid-cross-boundary-review`。对象是工作区 `123/scidiscovery-e5.2` 对 `/tmp/scid-handoff-baseline/source.tar` 和 `manifest.json` 的本轮精确增量，不以 HEAD 或整个旧 dirty diff 为基线。计划依据为 `OPERATION_RESPONSIBILITY_HANDOFF_REPAIR_PLAN.zh-CN.md` R4。只审查 A0/A/B 及失败恢复接线；C0 未获得可信原生初始化样本，C 生产实现按计划暂停，不作为本次缺陷。

## F1：领域快照可经 deck 根链接读入未绑定来源（已闭合）

初审时 `operation_workspace.py:snapshot_workspace` 直接使用 `root / "deck"`；叶文件 `_read` 的 lstat 与 `_source_files` 的 files 根检查均不能拒绝其上一级 deck 是符号链接。新接线 `runs.py:519–523` 在失败前调用该快照器，`LocalTrustedBackend.open` 只检查工作区、assignment 和 output。

可达情形：native shell 将 deck 替换为指向另一目录的链接；目标中普通 gap.json/handoff.json 或 files 可被读取，随后通过 seal/discard 作为本 Run 的恢复草稿交给下一 Run。内容扫描不会证明来源身份，因此这是工作区来源边界缺陷。初审建议 REVISE，并及时通知实施者。

最小修复已经加入：`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:61` 的 `_deck_root` 在读取前用 lstat 拒绝缺失、链接和非目录；`snapshot_workspace:698` 与新增 gap 提交所在 `finalize_workspace:567` 均先调用。因异常发生在快照读取之前，RunService 记录 snapshot unavailable，失败隔离不保留候选；现有 discard 清除任务工作区而不追随 deck 链接删除外部目录。静态复核认为此确定场景已闭合。

已阅读新增 `test_domain_snapshot_rejects_symlinked_deck_root`：经真实 Worker submit 和 Root run_record_failure，断言提交拒绝、failed 且无恢复候选、外部 gap 字节保留。审查者没有运行该测试；运行结果由实施者验证记录负责。

## 已检查的边界

| 路径 | 静态结论 |
| --- | --- |
| 共同参考 → 实际 prompt，进展和 review exposure → 输出 context_sources | 共享前言及 TCAD role_pack 使用同源文本；新增 inventory 保持背景用途和既有总预算；指定 review 正文进入可读/context 来源，未新增权限或自动路由。 |
| author schema → payload/context validator → workspace finalizer | 完整工程形状保留；gap 是独立严格分支，校验定位存在、blocked handoff 和 missing_inputs 一致；仅 gap 跳过 readiness，参数来源约束仍保留。 |
| gap → 独立 review → 工程消费者 | reviewer 展示只读缺口；禁止 pass、execution_ready 和已实现 requirement 行，fidelity 为 unknown；compare、package、revision 的实际完整工程解析继续拒绝 gap。 |
| 失败 → snapshot → seal → discard → retry | 未接受候选采用当前领域草稿，gap 优先且损坏 JSON 可作为待修字节恢复；没有 gap 则保留源码草稿；已接受候选仍按原 digest 读取，不被后来编辑替换。恢复继续匹配原 Operation 摘要、原输入身份和尝试限制。 |
| 封存、预算、并发状态和清理 | 快照与候选受文件/字节上限，候选路径拒绝绝对路径、反斜线、空段、点段和重复；源码递归拒绝链接/非普通项；publication 扫描保留。discard 的未知扩展名 text fallback 保留 UTF-8 检查；Run 状态更新仍使用 state/last_activity CAS；快照失败有原因且走隔离清理。 |

范围内未发现其他确定新增缺陷。没有把后续定向验证、已有旧机制或未承诺的 C 实现扩成新的工程建议。

## 证据限制与候选身份

本审查仅进行文件读取、与冻结基线的文本比较及静态调用追踪；未修改源码，未运行测试、构建或安装，未调用科研工具，未创建子 Agent。实施者提供的通过数量不作为本报告独立测试结论。完整 cohort 的 gap→design、共享回归、安装入口和真实科研运行的动态证据仍由实施任务记录；科学正确性不由本报告裁定。本次源码只读快照 SHA256 如下，后续生产修改需重新判断影响：

```text
d3eed729c964b99aa4438dc1f4737b2d940064dcf07f2e00f59e80c1091cc1e6  plugins/curve_score/curve_score/science_operations.py
50565eac43f919ca22c8a34319d23033efa4b9f6d2c6891ffcf7c2575ade886f  plugins/tcad_artifact/tcad_artifact/operation_workspace.py
90b136a3a1a2b9f0eec24d7f0e75ad816c290a799fdf5d8004c515c6c8c0da78  plugins/tcad_artifact/tcad_artifact/plugin.py
0777e800ce469547ac1bfd5d9b7a039b0a3fa03541d88c375cecb224435c771e  plugins/tcad_artifact/tcad_artifact/project_packager.py
4bc2acfc958d5efb331fec19cb996c93e4c8df5bc934acfcb64795d00769df81  plugins/tcad_artifact/tcad_artifact/result_analysis.py
73f3ad1c84c5f04bc5f997b523aa842368c0f0717c96b7cf5e45361198d931c5  plugins/tcad_artifact/tcad_artifact/role_pack.py
29eeabbf9823ea0a91d8ed9f6cf2d6d0f32186c7633d89484b8a3cb39a6cdfbd  plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_author.md
69e51541b95f39fc12a50e0463814cba793144a9e5270e0a754f89043b64b67a  plugins/tcad_artifact/tcad_artifact/roles/tcad_deck_reviewer.md
b9a4bd2a32c15afb2d9ed3de57a72900ecac33b867613be1554f7268e44f9a10  plugins/tcad_artifact/tcad_artifact/transform_adapter.py
6ff5aa06f00322c70dab344c88f405d94b5cdfdfd8143552ab2e0c23204363bc  src/scidiscovery/artifact_agent/service/local_workspace.py
e02514038f80ceea0b4764e79a31996c350e8288fcc5cebaea266f601b12989c  src/scidiscovery/artifact_agent/service/runs.py
cacef13561d151f24c03564dea4589be927dd082d008c0b440f286eda8126f6a  src/scidiscovery/general_science_experiment_components.py
e66a1612abd0517651321a909e8455f24e3c0d5a0af4d0b8c6367affdea067c5  src/scidiscovery/general_science_experiment_operations.py
8b96bf1c2d96f6a309528b91f2196e48d308ab52600892df25e4e3f4c8e4a875  src/scidiscovery/operation_declaration.py
```
