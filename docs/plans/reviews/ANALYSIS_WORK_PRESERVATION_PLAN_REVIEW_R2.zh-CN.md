# 分析工作保全与跨轮交付计划 R2：独立工程复审

日期：2026-09-12。结论：**PASS（计划层）**。

R1 的 B1、B2、B3 均已关闭，未发现需要再次修订计划的实质阻断。R2 可以进入所列有界实施；
本结论不表示当前源码已修复，也不表示恢复链或现场科研验收已通过。

## 1. 范围与输入

本次由全新独立工程审查者复审，不是科研 Operation。使用 `scid-cross-boundary-review` 与
`karpathy-guidelines`，核对 R2、R1 审查及精确快照、限定根因证据和当前工作树相关源码。
仓库为 `123/scidiscovery-e5.2`；HEAD 为 `2edac5d317a74056869a567bd0daa7f556ecbc85`。
工作树含大量已有修改，不能仅用 HEAD 标识本次输入。R2 为 351 行，以下行号均指此次读取版本。

| 文档输入 | SHA256 |
| --- | --- |
| `docs/plans/ANALYSIS_WORK_PRESERVATION_AND_DELIVERY_PLAN.zh-CN.md` | `f5260c84d5c18502b2df55f4a645c40771f23caf9315dba43b265f2744b5c1b2` |
| `docs/plans/reviews/ANALYSIS_WORK_PRESERVATION_PLAN_REVIEW_R1.zh-CN.md` | `ff1d051263be6ea69ec4bcde3796998768e176eaba582763ee16442accf6925e` |
| `docs/plans/reviews/ANALYSIS_WORK_PRESERVATION_PLAN_R1_REVIEWED_SNAPSHOT.zh-CN.md` | `88e3d3130bd63d3f2cf8dd029d6876f703cb557c3336e52b9f572338fa9a58ba` |
| `docs/plans/evidence/operation-validation-reaudit/ANALYSIS_TIMEOUT_ROOT_CAUSE.zh-CN.md` | `2478a072a138096536c2b299bbb847839cf1db472050c84808b776a9c7d12ea0` |
| `docs/plans/evidence/operation-validation-reaudit/ANALYSIS_TIMEOUT_TIMELINE.json` | `072a9828321e44d79dcefe0013955a1de5e7aaaa7fabb9ed41d124ca06ee0f57` |

关键恢复源码输入（路径均位于 `src/scidiscovery/artifact_agent/service/`）：

| 文件 | SHA256 |
| --- | --- |
| `runs.py` | `4a87d96597f30fe5cb40599ee3b938e58608d0242dab552a3db43a348eecfaa2` |
| `local_workspace.py` | `4a5a84e96fe85a7a17e979edb878ea006ee3a70ea6ce95cb5b536118774c3fc4` |
| `run_records.py` | `9f22071e9b35bffa558bae8dee417517657cb9a63fc0b59d1d2ce711ba39cb24` |
| `run_assignment.py` | `a3b222b01c38002a0aeefd0e62eecb3a4b2d4463d2fa7172ee3096477efdd0e9` |
| `tool_evidence.py` | `9444ad800f959b5d4a809f3fb7ef4cce5f82c63228ddf23655891a318905a249` |

## 2. R1 必要项逐项复审

### B1：已关闭——未确认停写时保留原目录，子集可交付与 pending 分开表达

**计划依据：第 102–118、279、297–299、333 行。** R2 明确失败 CAS 不等于原生进程退出；
未确认停写、直接原生命令未受管或重启后无法核实时保留原目录。新 Run 只读取已封存的稳定子集，
晚于快照枚举写出的文件仍留在原目录。只有确认停写且保存范围完整，后续显式处理才允许清理。
这直接覆盖 R1 的“枚举后又完成一个单元、随后被 discard 删除”情景。

当前源码尚需修改，但现有结构能表达该方案：

- `run_records.py:96` 的 `recovery_draft` 是既有 JSON 字典；可以同时保存完整草稿清单与
  `recovery_pending`，无需增加 Run 状态或数据库迁移。
- `runs.py:1285` 的 `draft_from` 准入和 `runs.py:1294` 的验证要求来源身份、摘要及文件清单匹配，
  没有把 pending 当作草稿拒绝条件。因此可读副本与待清理原目录可以并存，精确身份检查继续有效。
- `runs.py:609` 目前见到 draft 就提前返回，`:681` 的 pending 写入会替换原 JSON，
  `:1361` 又把 pending 简化为“未保存草稿”。R2 第 115–118 行已明确要求改掉这些耦合；
  实施时须保留既有草稿身份与清单，不能用 pending-only 记录覆盖它。
- `local_workspace.py:339` 的 discard 把复制、验证和删除绑在一起（复制从 `:366` 开始，删除在 `:394`）。
  R2 已将 Local 复制与清理分离纳入修改范围；复用这段实现并增加内部保留分支即可承接该策略，
  不需要新建跨后端协议或全平台进程注册表。

`complete_snapshot_digest` 不能用来替代停写证明；R2 已明确此区别。如何组织 Local 私有函数、
停止结果和既有 JSON 内的覆盖说明属于实施细节，不构成未声明的新生命周期。
长期 pending 是本轮明确接受的保守结果，不要求增加自动垃圾清理。

### B2：已关闭——合格子集先筛选，原始日志保留，规范化副本通过同一校验

**计划依据：第 122–149、166–167、183、324–325、334 行。** R2 将候选范围收窄到本次实际使用
的文本类型及 PNG，禁写/排除字节码缓存；真实 traceback 的原字节留在原目录，规范化副本替换主机路径，
标明截断和变换。仍含秘密、编码不支持或内容不合格的文件单独遗漏，脚本与 CSV/JSON 不被静默改写。

`local_workspace.py:289` 的 seal 与 `:685`–`:689` 的 verify 确实分别检查内容，后者重新推断类型；
`:719` 的既有检查拒绝秘密、主机路径和不合格文本。R2 第 123–125 行明确两侧必须采用一致解释，
第 137–138 行明确在 seal 前逐文件筛选。因此一个 traceback 或 `.pyc` 不再必然使整个草稿失败，
也没有通过放宽正式发布检查来实现恢复。

交付边界已闭合到现有 `runs.py:1294` 验证、`local_workspace.py:164` 的只读副本复制和
`run_assignment.py:74` 的恢复入口。第 88–89 行同时点名更新 `tool_evidence.py` 的布局读取；
当前 `tool_evidence.py:414` 只识别扁平 `tool-evidence.json`，该适配是已声明改动，不能遗漏。
第 146–149 行要求真实异常与缓存经过上述链路后，数值文件仍可读取，覆盖不足与原目录保留如实呈现。

遗漏元数据不携带敏感原文，Root 技术摘要不展示日志内容；恢复材料也不升级为科学依据。
若恰好缺失必要脚本/数据，R2 明确不能声称续接成功。原日志尚未原样保存到恢复包时保留原目录，
不会由“规范化副本可读”推出“原字节可删除”。未发现新的全包阻断或新增泄露通道。

### B3：已关闭——动态剩余预算有明确来源和执行公式

**计划依据：第 158–179、192–194、305–306、338 行。** R2 取消统一 180 秒硬限制，使用
`min(请求超时, max(0, Run 剩余时间 - 提交余量))`；启动时从控制生成的绝对截止信息重新计算，
提交余量由本地命令参数调整。旧 assignment 缺少新增信息时不猜测预算，也不阻断旧任务提交。

现有 `runs.py:171` 已生成绝对截止时间，`:320` 是 assignment 生成位置；
`run_assignment.py:21` 可以承接该增量描述，无需新增 Operation/MCP 参数。
`mcp_local_worker.py:258` 的 remaining_seconds 是打开时读数，不能代替启动时重新计算；R2 已写清楚。
`plugins/tcad_artifact/tcad_artifact/result_analysis.py:549` 的 900 秒合同继续有效。
超出建议小批时长、但在剩余预算内的成功对照也已列入验收，覆盖 R1 的反例。

## 3. 保留要求与实施边界

第 242–255 行保留按完整工作单元原子落盘、绘图仅读取数值文件、绘图局部重试及按输入/方法匹配
复用检查点。第 235–238、320–323 行要求由受控 Worker 发布实际脚本新版本，并以全新 Agent
证明续接；提示词更新或同一 Agent 记忆不能代替现场交付。这些要求仍直接对应限定根因证据。

第 28–35、204–205、247–250 行没有增加科学必填字段、评分、绘图库或遥测门槛，允许有依据的部分报告。
第 78–89、278–287 行使用现有 workspace hooks、共同 finalizer 和恢复存储，Local 分析之外保持既有行为。
`operations/workspace.py:98` 的快照条目和 `:53` 的工作区描述已有承载文件及版本说明的空间。
没有必要为本轮另建状态机、通用执行器或扩大到全平台测试。

**剩余必要修订：无。** 私有函数划分、规范化实现和有界元数据字段命名可在实施时决定；
上文指出的现有代码耦合属于 R2 已声明的实现工作，不应误读为代码已经支持全部新行为。

本次只做文件检索/阅读、R1→R2 文本差异、git 状态/HEAD 与 SHA256 计算，仅新增本报告。
未运行测试（含定向 pytest）、故障注入、安装/构建、真实 Agent、求解器或拟合；
未调用控制面或 worker 工具，未读取生产未封存科学草稿或完整平台会话。
实际进程停止确认、规范化日志字节交付、局部绘图重试和安装后新 Agent 接续，仍须按 R2 的有界验收证明。
