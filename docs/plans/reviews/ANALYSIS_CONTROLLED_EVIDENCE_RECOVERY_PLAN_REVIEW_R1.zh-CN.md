# 分析角色内受控检查与补收集计划独立审查 R1

结论：**PASS（计划审查）**。没有发现必须先修订 R1 才能开始其 P0 的阻断问题。目标、权限收敛和证据交付方向符合要求；以下三个非阻断建议应落实到 P0 合同冻结和后续实现清单。这个结论不表示新增能力已经实现、测试通过或可部署。

## 审查对象与边界

- 审查日期：2026-09-10。
- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
- 输入：`docs/plans/ANALYSIS_CONTROLLED_EVIDENCE_RECOVERY_PLAN.zh-CN.md`，R1。
- 输入 SHA256：`cf54d6f0fca8a06ffcae09897d43265e986e8b9a32f480b9633bcafd2dc182ce`。
- 当前 HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。
- 基线是已有大量未提交修改的当前工作树，包含未跟踪的计划文件；没有把 HEAD 差异整体当成本提案的实现。
- 已阅读父仓库和目标仓库 `AGENTS.md`，以及父仓库 `.agents/skills/scid-cross-boundary-review/SKILL.md`。此次是明确授权的工程计划及源码审查，不执行科研调度流程。
- **未运行测试，未启动 solver，未访问科研控制面或活实例，未核实 VM 文件是否仍在。** 阅读了相关测试源码。只新增本报告，没有实施或修改计划及其他文件。

## 结论依据

1. **目标准确。** 计划第 1、3 节明确取消独立恢复 Operation，仅给现有 `tcad.result.analyze.v1` 增加两个有界工具；原 Execution、原 manifest 和失败事实保持不变。映射由分析者提出，工具只做执行范围、字节、路径及对应声明检查；需要改源码或物理方案时回到已有 author/design 行动。这符合“现有角色有纠错手段”的要求。
2. **实际故障链核对成立。** `worker.py:73-105,115-138` 和 `remote_runner_py36.py:442-468,560-589` 确实先等待求解、再按序收集，必需项缺失会停止循环并可能将 0 改成 97。`result_analysis.py:209-219,285-318` 确实存在 manifest/路径身份、PLX 媒体、整体失败和完整性检查；仅下载新文件不能使这些检查自动理解恢复来源。
3. **同轮闭环有明确工程范围。** 现有 `OperationToolContext` 只读绑定输入；`analysis_tool.py:221-245` 的评分读取也只走 `read_input`。`run_outputs.py:85-97` 仅接受 `result.json`，`runs.py:1021-1055` 只注册主结果。计划第 5 节逐项要求持久接收索引、受控别名、共同解析器、候选指纹、完成后发布和失败恢复，直接覆盖这些断点，而非把下载等同正式证据。
4. **输入与输出职责分开。** 计划第 4.1、6 节把下一 Run 的恢复证据准入放在该 Run 的 preflight，同轮接收放在工具边界；输出校验只验证引用、重放和结论。该边界与当前 `validate_analysis_inputs` 和 `analysis_context` 的职责分离相容。需要重新读取本地不可变字节做输出重放，不等于重新判断输入资格；完整性错误仍属于工程故障。
5. **兼容要求合理。** 旧记录的 solver 结果保持 unknown，旧收集失败不会强迫有限报告变成失败；真实求解失败和审计失败不会被补收集抹除。可选服务与 author 原 required service 分开，历史合同不按新 digest 重新验收。这些要求在计划中均明确，不需要靠审查者补造科学判据。

## 非阻断建议

### N1：P0 应点名集合能力的两个准入门，以及安装投影

**位置：** 计划第 5 节、P2 和第 8 节；源码 `service/local_workspace.py:103-113`、`service/runs.py:118-121`、`interfaces/mcp_root_operation_routes.py:100-105`、`platforms/codex.py:513-514`。

**触发：** 给 TCAD 分析添加可选 `OutputPortSpec.collection`，仅实现证据保存和输出校验，但沿用现有后端能力判定。

**影响：** `LocalTrustedBackend` 对任何 collection 返回不支持；即使放开这一层，`RunService.schedule` 仍有独立拒绝。Root 和平台配置生成复用后端判定，因此新分析可能无法出现在可运行的安装配置中，甚至无恢复需求的分析也无法创建 Run。

**最小修正：** 在 P0 精确文件清单中列明这两个门及其投影调用方，仅允许显式声明的“受信任工具附属证据集合”；未声明角色与任意 Agent 集合继续保持旧限制。用安装生成入口和实际 Run 创建入口验证“无工具调用的普通分析”和“启用受控集合的分析”均可到达 Worker。

**为何不阻断：** R1 已明确 P2 实现显式集合能力、第 8 节允许必要 workspace 修改、P4 验证 Root/Worker 安装投影。这里补充的是已承诺路径上的精确硬门，不要求新增方案。

### N2：跨轮恢复应覆盖 parentage guard 与旧 runtime_attestation 的范围

**位置：** 计划第 4.1、5、6 节；源码 `result_analysis.py:40-78`、`service/executions.py:510-518`、`service/runs.py:1037-1039`。

**触发：** 下一分析 Run 同时绑定原 runtime manifest、分析 Run 发布的恢复文件及恢复清单；可选地仍绑定原执行的 runtime_attestation。

**影响：** 现有 `analysis_parentage` 要求每个 solver output 与原 manifest 的 `parent_refs` 完全相等，还要求 audit 包含所有绑定输出。原执行输出来自 `(request_ref, payload_ref)`，新分析工具成果需要携带恢复来源，不能简单继承旧执行产物身份。只修改字节校验器的 manifest 匹配，会在更早的 guard 被拒绝；反过来整体取消 guard 会失去原执行身份保护。旧 audit 也不能因此被解释成已经审过后来恢复的字节。

**最小修正：** P0 明确恢复清单如何证明原执行与原项目关系，guard 仅对经该清单验证的恢复文件接受对应父链；原有直接产物仍走原分支。旧 audit 的效力保持其原覆盖范围，失败事实继续保留。贯通用例同时包含“无 audit”“绑定原 audit”和“同字节异执行”三个分支，不新增重新审计阶段。

**为何不阻断：** R1 已要求 preflight 按恢复凭据核对来源、不得继承旧资格、不得清除 audit 失败，并将整个 `result_analysis.py` 列入实施范围。建议把其中易漏的 guard 单独写入 P0 对照表。

### N3：跨轮重放合同应明确旧工具别名与新输入别名的对应方式

**位置：** 计划第 4.1、第 5 节第 3、6 项及验收矩阵“completed 后启动全新 Agent”；源码 `operations/invoke.py:162-174`、`curve_score/analysis_tool.py:76-83,221-239`、`result_analysis.py:281-303`。

**触发：** 第一轮计算记录使用 `tool_evidence_001`；下一轮把发布文件绑定到 `solver_outputs`，运行时生成 `solver_outputs_001` 等输入别名，然后尝试复核上一轮记录。

**影响：** 计算请求和摘要映射都按别名查找，文件字节相同不会自动让旧别名在新 Run 有效。若实现只重新绑定文件而没有恢复清单中的对应关系，下一 Agent 可以重新计算，但不能按原记录的引用直接重放；若无条件保留旧别名，又可能与当前 Run 的工具证据命名空间冲突。

**最小修正：** 在恢复清单中冻结原证据别名到精确发布 Artifact 的对应关系；新 Run 仅将已明确绑定且通过准入的 Artifact 暴露给重放解析器，并明确名称冲突策略。区分“验证原计算记录”和“生成使用新别名的新计算记录”，两者均不得篡改旧记录。P0 的新 Agent 用例应至少复核一条第一轮真实生成的计算记录，而非只检查新文件可读。

**为何不阻断：** R1 已要求评分、引用、动态 schema 与重放使用同一解析器，并承诺跨轮重放。具体别名规则本来就在 P0 冻结范围；这里给出真实调用链上的验收触发条件。

## 最小性判断与后续验证范围

没有发现比本计划更小、同时仍满足“同 Run 检查—接收—评分/引用—提交—下一 Agent 接手”的完整替代实现。仅修收集循环只能改善未来执行，不能恢复既有成果；仅增加下载工具不能给评分和提交建立可信来源；重新打开旧 Execution 或重写原 manifest 会改变历史事实。

复用已有 Artifact/CAS、候选接受、输出集合声明及失败保全是合理方向。实施应维持单个 TCAD 调用者、单个报告主结果和一种工具附属证据接缝，不由此建设任意多输出 Agent、通用上传系统或新的调度阶段。optional service 的合同扩展只解决分析工具可能离线的问题，不能改变 author 必需服务。

已阅读的关键测试源码包括 `test_collector_analysis_handoff.py`、`test_tcad_result_analysis.py`、`test_result_analysis_tool.py` 与 `test_analysis_input_descriptors.py`。现有夹具包含生产收集/注册/准入/Worker 提交路径以及有限分析、同字节异执行等负例，适合按计划扩展；本次没有执行它们，不能声称其当前通过。

尚未验证的实施风险是新 RPC 的实际传输与 Python 3.6 兼容、持久索引及候选提交的并发一致性、安装后的工具投影，以及原案例文件的现实可恢复性。这些已属于 R1 的后续验收范围，不是本报告给出的实现正确性保证。
