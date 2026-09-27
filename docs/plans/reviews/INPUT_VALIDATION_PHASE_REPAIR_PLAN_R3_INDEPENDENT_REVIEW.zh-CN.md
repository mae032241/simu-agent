# 输入校验职责修订计划 R3 独立工程复审

日期：2026-09-10。结论：**REVISE**，剩余一项阻断，属于 R2 F2 的保全范围边界；不要求扩大为全系统重构。

审查对象为 `docs/plans/INPUT_VALIDATION_PHASE_REPAIR_PLAN.zh-CN.md`，SHA256：`6f4c61afa2373ec4b526c817f0a0d6d2ac307e4b4ff6bbb3897b571133a06618`。对照 R2 独立审查 F1—F4，实际读取 Root 路由、Run 服务、backend、assignment、TCAD workspace hook 和目录投影源码。本次仅新增本报告，未改计划或源码、未测试、未编译、未部署、未访问科学实例状态、未启动子 Agent。

## 基线与判断范围

HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。工作树已有大量未提交修改，不能将本结论理解为对干净 HEAD 的结论。读取时 `git diff --stat -- src plugins` 显示 50 个已跟踪文件改动、2288 行增加、2657 行删除，另有未跟踪源码。本次重点源码 SHA256 如下，可将源码事实与其他并行改动区分：

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/artifact_agent/service/runs.py` | `b51f5e78c51c253ff20b26ef064a28ff2a0269c0af4998abb3bb05adb323b404` |
| `src/scidiscovery/artifact_agent/service/local_workspace.py` | `6ff5aa06f00322c70dab344c88f405d94b5cdfdfd8143552ab2e0c23204363bc` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` | `63cfa155d8f63d7d0b68ac311aa56b2031fc649435609e5ed47d9d3f6ce5916f` |
| `plugins/tcad_artifact/tcad_artifact/operation_workspace.py` | `b129cbc5e2dd20adc29e3249320291db1e71096aec8b65dc836ea73a1edf01d0` |
| `src/scidiscovery/operations/spec.py` | `90b1352c086111c86b3e3248ef30795e11deaedaedfa8ef083f92a6938c6bebc` |
| `src/scidiscovery/operations/invoke.py` | `11f1e0793960f4e05628a4dab48a34b09c0af3a7fddcbbd62ce78ee10fe9b149` |

使用上层 `scid-cross-boundary-review` 与 `scid-find-simplifications` 技能，并读取当前架构、科学设计宪章、约束矩阵和比较评估；其中历史审计的 conformant/pending 状态不作为当前源码已通过的证据。

R3 的第一准则、P0 全可达规则分类、单一 input_validation 声明和提交零调用边界正确。输出可核对引用证据；输入准入漏检和框架故障不能要求作者无效改稿。宏观覆盖由迁移表与共享入口承担，正确 validator 无需重写。恢复材料不产生科学资格，当前性变化与完成交付分离，符合用户要求。

## F2-R3 / 高 / 阻断：通用 seal 成功不能证明 author 的完整交付已保全

**计划位置：**P3 第 78、80 行，P3b 第 96—104 行。计划冻结预算并禁止合同失配时调用新 hook 是正确决策，但只说明预算和通用隔离/封存，没有决定此时保全的文件范围及何时允许清理整个工作区。第 102 行保护的是预算缺失或 seal/discard 失败；它没有明确覆盖“seal 成功，但只保存了旧的 output 文件”。

**实际源码：**

- `local_workspace.py:234` 的 `seal(snapshot=None)` 从 `workspace.output_directory` 枚举文件（`:252`），不包含其他任务工作文件；冻结 max_files/max_bytes 不会改变这一范围。
- `operation_workspace.py:343` 将 author 工程放在 `workspace/deck`；`:728` 的 snapshotter 显式采集 deck/handoff、declarations、源文件和报告。现有两条保全路径并不等价。
- `runs.py:830` 的 `_finalize_workspace` 把 finalizer 结果写入 output；预览也走该路径（`:734`）。因此 output/result.json 可能存在，但只是某次较早预览的版本。
- `local_workspace.py:317` 的 discard 复制指定 candidate 后，在 `:377` 清理整个 quarantine 工作区。它不会证明候选包含 deck 最新内容。`operation_workspace.py:215` 的 `_restore_retry_tree` 可消费原始 deck，说明这些文件有实际恢复消费者。

**可达场景：**author 已预览生成 result.json，随后继续修改 deck 源码或声明；当前 Operation 被替换或移除。P3b 禁止使用新 finalizer/snapshotter，转而调用通用 seal。seal 对旧 result.json 可以成功，随后 discard 保存这一候选并删除包含最新 deck 的工作区。系统可能显示 recovery available，恢复得到的却是较早工程版本。另一种情况是 output 为空，seal 报错；R3 已覆盖后者，不能据此证明前者安全。

**必须在计划阶段补的最小决策：**合同不可用时，只有能证明封存范围覆盖待保全交付，才允许删除整个工作区。对存在领域工作文件、无法证明覆盖的情况，即使 output 封存成功也须保留原工作区或隔离副本，并记录保全未完成；不能将一个可验证的 output 摘要等同于完整交付保全。可以沿计划已有的匹配旧环境/明确工程修复完成受控封存后，再允许 draft_from 接手。若要在合同缺失时自动完成原始工程保全，则需在创建时冻结最小受控范围并由通用 backend 按该范围复制；不需要保存完整目录或执行新插件代码。最小方案是先明确保留规则，不必新增草稿服务。

**实施验收事实：**增加“预览 A → 修改 deck 为 B → 移除/替换合同 → submit/显式失败/重启”用例，验证 B 的原始源码和声明可取回；旧 result.json 封存成功不得触发删除 B。另覆盖无 output 和隔离中断。无需运行求解器。此验收应与 R3 原有 seal/discard 故障测试并列，不能只测抛异常路径。

## R2 F1—F4 闭合情况

| 原问题 | R3 判断 | 理由 |
| --- | --- | --- |
| F1 修复后恢复与精确 resume 冲突 | 计划决策已闭合 | draft_from 与 resume 互斥；同实例、同 Operation ID、同 backend，允许新 digest/新输入；来源和受控摘要进入请求身份；新合同重新准入、独立验收；两类边共同计数并受原链冻结上限约束。 |
| F2 合同失配阻止保全 | 部分闭合，仍阻断 | 窄合同错误、冻结预算、旧记录 pending、failed 重启补救和 CAS 分流已经明确；仍需上述文件范围/清理条件决策。 |
| F3 错误直接入口与准入归属 | 已闭合 | 第 57—60 行定位真实 schedule，并明确共享内容/绑定检查，不复制 Root cohort/approval 等政策权威。 |
| F4 目录投影冲突 | 已闭合 | 第 51 行明确 SchedulerOperationView/scheduler_operation_view → catalog → Root；新增 input_validation，不覆盖既有 InputAdmissionSpec。 |

## 实施时核验，不另增计划阻断

1. **实际 Root 指纹入口名称需校正。**第 90 行写 `_agent_call/_agent_invocation_request`，当前源码无此符号；实际是 `mcp_root_operation_routes.py::_prepare_local_run:270` 构造 Root 指纹，`_invoke_local_run:239` 调 schedule，Run 自身另在 `runs.py:173` 计算 request_digest。来源与受控 draft_digest 要同时贯穿这两层。R3 已明确要求完整请求指纹，这属于实施定位纠正，不需再设计一种机制。
2. **草稿验证不能只验字符串和目录名。**现有 `_recovery_digest:1096` 只取摘要字符串，`backend.prepare:157` 只检查目录并复制。R3 已要求摘要可验证，实施必须对真实文件重算，并在直接 schedule 中验证实例/来源、同 backend capabilities 及目标支持能力，不能只依赖 Root。两类恢复边混合分支、并发创建和原链上限均应验证；不能只测线性 happy path。
3. **保全状态与可接续状态需同源但区分含义。**当前 `recovery_available:1022` 仍要求 `_compiled` 匹配和严格 resume。实施 P3/P5 时不能直接沿用该布尔值代表 draft_from；必须如实投影“文件已保全、严格 resume 不可用但新合同可草稿接续”以及“隔离未完成”。R3 已承诺来源/可用性投影，故这是实现验收，不增加第三类恢复机制。
4. **schedule 的权威绑定重建需真实负例。**当前 `schedule:111` 接受 BoundOperationCall 的媒体、别名和引用，`:131` 只 verify，随后 freeze 和插入 Run。P1 必须在副作用前利用权威 Artifact 元数据校验端口、来源、大小和新 input_validation；手造正确对象的测试不能证明防绕过。原 Root 政策仍由 `_validate_operation_input_admission:1115` 拥有，不扩大成本为复制所有政策到 service。
5. **原候选复用要绑定精确版本。**当前 accepted_candidate_digest 是通过验收后的标记；不能为实现提前保全而提前设置它，也不能随意选 candidates 中某目录。R3 第 78、104 行已经要求候选关联和 CAS/发布分流，实施应证明校验器故障前封存的版本不会被故障路径再次快照替换。
6. **旧记录约束应如实报告。**无可信旧预算的记录先保留、报告 pending 是合理 fail-closed 决策；这不等于旧记录已恢复。P6 完成时仍要按实例外的工程兼容验收列出实际可接续与尚待修复材料，不能以新记录测试通过宣称所有旧记录已解除阻塞。

以上均不要求在计划审查时执行测试、编译目录或读取科学存储。完成唯一阻断的保全范围决策后，可按现有 P0—P6 做最小实现；独立计划通过与实现、安装入口、恢复故障测试通过应继续分别记录。
