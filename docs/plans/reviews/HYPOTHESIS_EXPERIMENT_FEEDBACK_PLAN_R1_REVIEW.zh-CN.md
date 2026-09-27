# 实验反馈与 MCP 信息分级 R1 独立复审

日期：2026-09-16。总判定：**PASS（计划级）**。

| 被审对象 | SHA-256 | 结论 |
| --- | --- | --- |
| `docs/plans/HYPOTHESIS_EXPERIMENT_FEEDBACK_PLAN.zh-CN.md` | `3848e3926c644ba039e1789f76aa5a614a1bcb55b128deebae7359f502d4e1e3` | A：PASS |
| `docs/plans/MCP_RESPONSE_INFORMATION_LEVELS_PLAN.zh-CN.md` | `8e8e8b6529bc66dd4e7f1d86b5b4c5f87f52249b7d000146d7958e44129a954c` | B：PASS |
| A/B 组合路径 | 上述两个精确版本 | PASS |

基线：`90a7b3a5865eb45649f1a39221337f9d939a3d71` 加当前工作区。独立审查沿用 `scid-cross-boundary-review` 技能，只读计划及相关源码；未改计划、产品代码、旧审查或 R0 快照。本轮未运行测试、构建、科学 MCP、部署或仿真，唯一写入为本报告。

## 发现与 R0 关闭情况

**未发现需要阻止按 R1 实施的 P1/P2 计划缺陷。** 下述关闭仅针对计划中已选定的方案，不代表实现已通过。

| R0 问题 | R1 修订与源码核对 | 结论 |
| --- | --- | --- |
| P1-1 来源枚举破坏 foundation provenance，critic 遗漏 foundation | 总计划 §4.3 明确三条 hypothesis 输出 `evidence_paths=()`，保留结构验证和来源上下文校验，critic 补入 foundation；允许集合为真实 context alias 加精确 foundation provenance。`general_science_agent_operations.py:115` 已支持显式空 evidence_paths；`operation_contract.py:569` 的投影条件要求非空 evidence_paths，故该局部方案可避免新 inventory 触发不兼容枚举。`run_outputs.py:210` 仍会调用 contextual validator，不会因禁用枚举而取消来源验证。 | 关闭 |
| P1-2 REPORT_GUIDANCE 修改不进入三个分析合同身份 | 总计划 §4.4 移除 A 的 REPORT_GUIDANCE 修改，复用现有 summary 和请求 instruction；A 不再需要修改两个分析 materializer 身份。B §3.3 则明确工具行为变化更新实际 ComponentSpec，guidance 若变化更新 materializer，不再遗漏跨插件身份。 | 关闭 |
| P2-1 critic prompt 与 semantic contract 冲突 | 总计划 §4.1 明确同步 `Resources.critic_semantic_contract`，保留运行观察、模拟、实测、分析解释及资格边界。对应源码 `general_science_resources.py:127` 的规则是实际嵌入 Schema 的合同，修订位置选取正确。 | 关闭 |

这一路径不需要新的通用引用框架。实施时在现有 `_hypothesis_output` 调用及 critic 输出声明上使用已有参数、共享局部允许来源计算即可；未知引用仍由现有具体路径诊断拒绝。JSON Schema 不独立判断依赖绑定内容的 provenance 合法性，是明确且合理的职责分工。

## 工作包 A：闭环、资格及最小范围

proposal 反馈 → critic → 必要 revise → critic → design/materialize 的输入和输出衔接完整。revise 保持 key 集合与独立 change_request；新 proposal 可以变化集合但不能继承旧 critic。负结果仍是历史背景，模型缺陷、数值失败和不可辨识由 Worker 判断，不新增机械判据或强制补表。

已核对 `general_science_experiment_operations.py:34` 的既有 feedback 端口、`general_science_experiment_components.py:146` 的物化 parentage、现有 critic disposition 准入以及 `runs.py:1107` 的 completed 输出兼容逻辑。计划保留原 objective/foundation 与精确 portfolio/critic cohort，足以沿现有设计及物化路径接续；没有要求把总体目标替换为当前诊断目标。

旧 foundation 资格、changed-contract 恢复、旧原件可读性和新 review 匹配仍必须走计划 E8/E11 的真实入口验证。三个 Python 文件及 scheduler 源的 A 范围与所选方案一致，无需扩大到准入引擎或状态机。

## 工作包 B：全接口默认摘要方案

B 的覆盖符合用户“各个 MCP 接口”的要求：§1/§2 覆盖 Root、通用 Worker、安装领域工具及 stdio/daemon/proxy，以发布声明生成逐工具清单；不是仅修 execution_*。已有短回执允许保留，完整工具参数合同和显式证据读取被正确识别为必要内容，不应为凑响应大小删除。

计划与下列实际路径一致：

- `mcp_root_run_routes.py:81` 当前组合 status、bindings、native、完整结果与 signal。新增摘要并保留 output_paths/detail 有可实施的投影边界。B §3.2 明确 `[]`、非空 pointers、未指定/null 与 detail 的优先级，避免默认摘要混成完整封存结果。
- `mcp_root_operation_routes.py:217` 仅对成功 Agent preflight 返回 normalized_request；B 的例外准确保留它。invoke 保留 agent_type/profile/budget/结果名及审批 URL，足以派发，不必保留整个 Run 展开。
- `mcp_root_operation_routes.py:69` 的目录投影、`mcp_root_instance_routes.py:141` 的 inventory 和 `:286` 的有序 parents 均可在既有 facade/route 结果处做分级，不需要第二目录或新的科学状态。历史恢复改为显式 detail 已纳入 B §6。
- `mcp_root_execution_routes.py:523` 的 sync 返回 progress 并再合并 status，是已确认的冗余来源。计划保留刷新、collect、发布与重试语义，只改交付视图，范围合适。
- `analysis_tool.py:321` 已通过 `retain_calculation` 保存记录；`diagnostic_tool.py:152` 保存详细计算数据，`:190` 返回记录与图/详情位置。B 要求完整保存后再摘要、已有引用和文件可读，能保留科学证据，无需新增结果缓存服务。
- `mcp.py:57` 的 text/structuredContent 双表示确实存在。保留协议兼容、两种表示承载同一个精简业务结果，同时禁止编排重复展开，比未经证据删除 fallback 稳妥。错误通道仍由 `rpc_error` 保留其失败性质。

机器合同、错误、证据、恢复和内部消费者的必要保留条件已经写入计划，不需再增加新的框架抽象或控制流程。B0 清单和实现后的跨接口验收是本计划明确的工程交付，不把“计划已列分类”视为已经完成全工具审计。

## 实施与验收关注项（非新增修订条件）

1. **两个 Worker backend 都应出现在 B0。** `mcp_hardened_worker.py:207` 当前仍内联完整 tool_contracts；不能只检查 Local 新 assignment。按 B 已写的受控引用/按工具展开规则处理即可。旧 workspace 必须读取原合同，不能用新版 live catalog 替换。
2. **已有短工具不要顺便改取证能力。** `local_pdf_tool.py:100` 已只返回只读路径、页范围、字节数及 truncated，不返回整篇正文。Local PDF 路径可标“无需精简”；确有正文回传的路径再执行 B 的片段方案。不要仅因 `max_chars=131072` 就改一个本来已短的回执。
3. **错误首项摘要的后续详情必须实际可达。** `mcp.py:90` 的普通验证错误未必天然拥有 scoped diagnostic；不能先删其余 diagnostics 再提供不存在的引用。按 B §3.1/§3.3 补本工具最小读取路径，或按必要错误例外保留有界完整诊断。无需新增全局诊断服务。
4. **内部消费者与副作用分别验证。** UI read model 多数直接读服务，不能假定所有内部调用都经过 facade；应按 B §3.4 枚举真实调用点。`execution_outputs` 带登记语义，`lifecycle_events` 也有既有消费语义，分页不得改变它们；计划已明确保留这些行为。
5. **比较整段工作成本。** 目录详情、绑定详情、正式科学结果的额外调用有必要，但应按 B 验收第 11 项测同一决策路径的总字节和调用次数，不能只报告单次响应变小。

以上是沿现有明确方案落实的普通实现要点，不要求再写新架构计划、增加审批门禁或扩展本轮科学目标。

## A/B 组合与资源结论

B 默认隐藏 bindings 和 parent 正文后，A 必须使用 named detail 查询恢复精确来源；所需端口在按 Operation ID 展开的完整声明中可见。A 的校验输入读取正式绑定 bytes，B 的返回摘要不能替换这些 bytes。科学 signal、结论、限制与原件继续显式读取；只转交 calculation_ref 字符串不构成跨 Run 证据绑定。两份计划均明确这些规则，未发现组合上的权限或身份冲突。

主计划 E11 已区分 A 的分析合同不变与 B 的工具合同可能变化，不会误把 B 的必要 identity 更新判成无关漂移。同步修改 scheduler 源及生成合同、部署后刷新客户端合同也已包含。

串行、2 GiB 进程树、180 秒整批以及安装环境复用的约束合理。R1 已明确安装 fixture 的每子进程超时不等于整批预算；无法完成时记录未验证，不自动扩额。无需全量测试；安装和纵向链可复用。

未验证：实现后的全工具清单、真实 Worker 封存、完整安装/传输链、历史 Run 恢复、旧审批兼容、分页并发边界、UI/客户端行为、峰值资源与实际响应减量、LLM 科学行为及生产 Fig4 接续。本报告不把静态可实施性当作这些路径已通过，也不代表源码实施或部署授权。
