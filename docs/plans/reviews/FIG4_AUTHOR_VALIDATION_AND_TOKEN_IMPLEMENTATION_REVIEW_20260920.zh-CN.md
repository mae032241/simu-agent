# Fig4 作者诊断交付与 token 整改：独立实施审查

结论：**REVISE，仅一处 P2：作者修订工作区的历史诊断导航指向恢复前路径。** 本轮未发现 P0/P1；来源锚、非最终快照、身份兼容、最终封装预算和 WP2–WP4 增量未发现其他阻断。修正这一处导航及对应窄断言即可复核，不要求新机制或重跑科研。

## 审查绑定与范围

实际仓库为 `123/scidiscovery-e5.2`。遵循适用 AGENTS、scid-cross-boundary-review 及 karpathy-guidelines；以实施前工作树归档为基线，没有把整个 HEAD dirty diff 当作本轮修改。

- 批准计划 SHA256：`a036aa9716f422b52cce46362cc5400195459f43fbedf0e77923dca8befef14a`；原计划 PASS 仅说明设计充分。
- 基线：`docs/plans/evidence/author-token-r4-20260920/before.json`、`before.tar.gz`；记录 HEAD 为 `943c4626f8490530e9318eb9fbb409d2670908b9`。
- 最终 `incremental.patch` SHA256：`c0ee52666aa456b2813f69144195841c9b4573d087904e1c1160eb8420633b73`。
- 最终 `incremental-files.json` SHA256：`526c9d80ba4cc8c1236cae3e26dd9781c38c02121f395559acc7c98166037b11`。
- `final-candidate.json` SHA256：`9355b7892b695ccb38e2d930a89c488224b27a78dc8cc41ca51d9cfab03b2671`。

独立核验上述三个最终文件的 hash；清单 33 个文件当前字节全部匹配 after hash，所有非新增文件的 before hash 均匹配 before 归档。最后 `collection_complete=false` 证明不计入采用预算的过滤及其回归已纳入当前源码审查。

本次只读源码、角色文档、增量与已有证据；未运行测试、模型、科研 MCP、solver 或部署，唯一写入为本报告。

## P2：作者历史附件的导航与实际恢复位置不一致

紧确位置：`plugins/tcad_artifact/tcad_artifact/operation_workspace.py:539–540`。新增 `development_diagnostic_paths` 无条件按 `deck/{item.relative_path}` 构建；但同文件 `:459` 调用的 `_restore_attempt` 在 `:290–294` 对 `author=True` 的报告改名为 `reports/history/{canonical_sha256(item.content)}_{basename}`。

可达场景：一个成功项目已经封存 `reports/evolution/coarse_pre`、`reports/diagnostic-evolution.json` 和模式报告；以该项目创建作者修订 Run。恢复函数将这些附件放到历史目录，manifest 却仍指向 `deck/reports/evolution/coarse_pre`、`deck/reports/initialization.json` 等旧位置。作者按返回入口读取时得到不存在的路径；若本 Run 随后产生同名模式报告，该导航会指向当前报告而非所导航的历史原件。原始附件仍在磁盘，不涉及字节丢失或最终来源校验绕过，但违反计划“旧附件只读可达、导航给准确入口”的交付要求，也会引入无效读取及历史/当前材料混淆。

独立 reviewer 的 `author=False` 路径没有改名，因此现有 `test_delivery_seals_selected_bytes_and_restores_independent_reviewer` 能通过，不能覆盖此作者修订分支。

最小修正：使 manifest 使用 `_restore_attempt` 实际采用的路径映射，保留历史报告与当前完成证明分离；不要为修导航将历史模式报告恢复到当前证明路径。补一个成功项目→作者修订工作区的窄断言：每个返回入口存在、字节等于对应附件且只读；后续当前模式报告不能替换该历史导航所指对象。无需新增附件协议或身份层。

## 其余边界的审查结果

**WP1 来源与提交。** `local_debug_service._finish` 对 collector 原始 bytes 和控制生成报告形成字节身份，进程内 `finalization_records` 存不可变 JSON bytes；完成条件同时要求终态、exit、diagnostic_layer 和所选原件齐全。`mcp_local_worker.py:316–321` 从内部状态传记录，`runs.py:615,1161,1309` 将其送到 finalizer；`WorkspaceFinalizationRequest` 冻结 mapping/tuple，MCP 输入没有记录参数。`operation_workspace.py:652–677` 核对 Run、Operation、诊断项目/声明身份及文件实际长度/hash。作者同时改报告和输出、缺锚或跨 Run 不能凭工作区文件恢复可信证明。记录在模式报告完整写入后才建立。

`finalize_workspace:787–788` 仅最终提交核对受控记录；`runs.validate_candidate:648` 使用 `final_submission=False`，首次及后续开发快照不会因尚无封存记录而被新门阻止。完成后重复 submit 沿原 completed 分支；此变更没有把快照当已接受候选。

**WP1 身份与封装。** `project_packager` 的 wrap serializer 在附件缺省时省略字段；`project_debug_sha256` 显式排除附件，完整项目/package 则保留附件。`transform_adapter.py:207–216` 将附件带回确定性重建比较，生产 tar/job 仍由原有源码/输入/输出字段构建。reviewer 恢复附件后将树设为只读，默认 project metadata 去掉正文；其跨 Run 正常路径成立。上列 P2 仅影响作者历史导航。

**WP1 字节预算。** `_delivery_budget:380–411` 使用已物化 envelope、已有 handoff、当前其他模式的成功证明及编码值合计，跳过失败、同模式被替代及旧项目证明；256 KiB 加逐输出预留、六倍文本最坏编码预算产生有限 development 额度。`debug_adapter.prepare` 只收紧复制出的 development job；服务 `_start` 在 submit/预约前预算检查，同名轮询不进入 `_start`。最终 `finalize_workspace:838–842` 重新检查完整实际 envelope。前置估计不构成保证，真实 collector 超限仍进入失败/缺口路径；没有增加成果限额或自动重算。

**WP2 精确结果身份。** `mcp_root_execution_routes.py:486–501` 返回本次 `_publish_execution_result` 的名称，响应分页投影保留该名称或 null。`output_recovery._inspect` 只对精确的 undeclared-input 错误给出绑定新 Run 的修复说明，不改变 frozen inputs、不搜索最新结果。

**WP3 已授权原件导航。** `reference_access.py:445–446,580–589` 在当前 source 授权成功且错误为 producer/manifest 配对缺失时提供已有工作区入口；保持原错误码/正文，既有 reserve/settle、policy 和 source 校验仍在。assignment 只声明 unknown，无扫描、无新缓存，其他错误不会被解释为永久缺失。

**WP4 有界视图与调用完整性。** execution summary 以完整 tail hash 合并相同来源片段，保留不同组的片段、原 detail 指针及省略数；detail 返回原响应。Agent invoke 保留身份、冻结 execution_profile、期限和 detail 入口，其他执行类型保持原返回；终态失败不走成功裁剪，真实 invocation 异常仍由原错误路径传递。角色文档继续区分初始化事实、演化观察与独立科学判断，没有新增数值机械门或执行权限。

## 已有验证证据与限制

读取新增/修改测试及实施状态记录：WP1 最终批次 119 passed；WP2–WP4 联合 169 passed、6 failed，其中新增断言期望修正与 tar 隔离另有 2 passed；新增安装与最终预算回归各 1 passed。实施证据将其余 5 个源失败和 5 个安装失败记录为 before 复现，未冒称全绿。本审查未重跑这些测试，数字只陈述已有证据，不替代上述语义审查。

现有新增安装检查覆盖安装包 Schema、结果名称路由投影和只读内部参数；不是完整 installed author→finalizer→reviewer 工作流证明。源级跨 Run、篡改负控及正负观察测试提供相应窄证据；均不能证明模型会提前识别反例或真实 SProcess 行为有效。

原生首个 Root-before-1 在 791796 KiB（773.24 MiB）触发 768 MiB 守卫，exit 86，未完成有效 usage/输出；后续模型全部停止。**作者行为收益和 token 稳定收益仍未证实**。本报告不将缺测升级为新增机制需求，也不授权提限、重试、部署或科研执行。

修正唯一 P2 后只需针对该路径和新冻结增量独立复核；未完成的原生测量、真实 solver/Fig4 连续边界与 J 验证继续保留原限制。
