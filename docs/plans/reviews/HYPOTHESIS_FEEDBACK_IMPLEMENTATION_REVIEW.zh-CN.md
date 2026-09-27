# 假设反馈与 MCP 信息分级实施独立审查

日期：2026-09-16。结论：**A PASS；B PASS；A/B 组合 PASS（静态实施审查）**。

当前受审源码未发现尚未关闭的 P1/P2 阻断问题。本轮发现的三项 B 问题已由实施者修改，审查者重新读取修复后的源码确认关闭。本结论不代表安装验证、真实 LLM 科学行为、部署或生产 Fig4 接续已经通过。

## 审查对象与边界

基线为 `90a7b3a5865eb45649f1a39221337f9d939a3d71`，加实施前保存的工作区差异。已读取 `evidence/hypothesis-feedback-implementation/baseline.diff`、`baseline-hashes.json`，排除原有工作台和 session 生命周期修改；本次仅审查 A/B 增量及其实际消费者。对重叠文件，关注此次新增的查询投影、分页和生命周期事件限量，不重新归责原有 UI/session 变更。

| 计划 | SHA-256 |
| --- | --- |
| `HYPOTHESIS_EXPERIMENT_FEEDBACK_PLAN.zh-CN.md` | `3848e3926c644ba039e1789f76aa5a614a1bcb55b128deebae7359f502d4e1e3` |
| `MCP_RESPONSE_INFORMATION_LEVELS_PLAN.zh-CN.md` | `8e8e8b6529bc66dd4e7f1d86b5b4c5f87f52249b7d000146d7958e44129a954c` |

同时读取 R1 独立计划审查，使用 `scid-cross-boundary-review` 技能。审查者未运行 pytest、构建、浏览器、科学 MCP、仿真或部署，未修改产品代码。唯一写入为本报告。测试源码用于核对负控是否触及真实边界，不将测试作者可直接读本地文件的权限等同于 Worker 权限。

## 本轮发现与关闭

### B-1：执行摘要遗漏实际工程错误（P2，已关闭）

初始实现的 `interfaces/mcp_response_views.py:execution_summary` 只保留常见 `error/diagnostics` 键，但 `execution_bridge.py:sync` 将 adapter 状态读取异常保存在顶层 `observation_error`，其中包含具体错误和 scoped diagnostic。`service/executions.py:observation` 也用该字段报告观测记录损坏。默认 status/sync 因而可能展示旧状态和空 progress，隐藏本次读取失败。

同一缺陷还影响 collection 的 `record_error`、`progress_error`、`stop_record_error`、`observation_error`、`stop_observation_error`。这些名称均来自真实 collection 服务，不能用仅含虚构 `error` 字段的 fixture 证明保留完整错误。

修复后的 `mcp_response_views.py:27` 保留上述字段、诊断引用和 stop reason，并保持 progress 缺失与显式 null 的区别。已静态检查新增 `test_observation_and_collection_failures_are_not_hidden_by_summary`：通过真实 effect adapter 的 `status_details` 抛出超时，再走 Root sync/status 核对，不只直接测试投影函数。**源码层关闭**。

### B-2：Hardened 返回不可读取的合同路径（P2，已关闭）

初始实现把 `mcp_hardened_worker.py:207` 的 `tool_contracts` 改成 Local 使用的文件路径。Hardened backend 明确禁用 native shell/file tools，现有 Worker MCP 也没有任意文件读取工具；生成指引 `platforms/codex.py:_hardened_worker_instruction` 仍要求从 open reply 读取完整合同。因此这个路径不能替代原有受控合同交付，尤其不能解决平台把参数类型压缩为 unknown 的场景。

实施者恢复 Hardened 原有内联 `tool_contracts`，Local 新旧 workspace 继续使用可读取的冻结文件路径。未添加新工具、扩大权限或改变所有 Operation 的生命周期合同。测试按 backend 区别取得合同；Hardened 不再用测试进程的 `Path.read_bytes()` 冒充模型读取能力。

这是合理的必要合同例外，符合 B 的“完整工具参数不能删除”和“无读取通道不能先精简”原则。B0 清单已明确例外，**不能宣称 Hardened 的合同也已默认缩短**。**源码层关闭**。

### B-3：图形预览隐藏已有的 unresolved 状态（P2，已关闭）

初始 `figure_worker_tool.py:_preview` 只返回哈希、图路径和详情路径，既有 `validation_report.source_status` 的 qualified/unresolved 区别及核心计数全部进入详情。预览有未解决的来源身份问题时，默认返回不再暴露这一状态。

修复后的 `figure_worker_tool.py:134` 直接保留 `integrity_status`、`source_status`、`validated_artifact_count` 和五项现成计数。完整 materialized request、validation report 与图引用仍先写入只读 details 文件。未推导新的科学 verdict，未改 digitizer 或资格算法。**源码层关闭**。

## A：反馈合同与科学职能

已追踪 proposal → critic → revise → critic → design/materialize 的声明、模型可见合同、提交 validator 和既有 cohort 守卫。

- 三条 hypothesis 操作共用有界可选 feedback 端口，采用 on_demand/evidence_inventory；previous_hypotheses 只用于新 proposal/critic 的比较，不被伪装成 correction base。原必需输入、foundation 审批与输出上限保持。
- 三条输出显式 `evidence_paths=()`，避免仅含本轮 alias 的通用枚举提前拒绝旧 foundation provenance。`run_outputs.py` 仍按已声明 context_sources 交付真实绑定 bytes 并调用 contextual validator；未知来源仍被拒绝。
- proposal/revise/critic 共享允许来源计算：真实可读绑定 alias 加精确 foundation provenance。critic 补入 foundation，与 prompt 和内嵌 semantic contract 一致。没有将 completed/negative analysis 自动升级为实测事实。
- revision 保留原 objective 和 hypothesis key 集合；新 proposal 可调整集合但不继承旧 critic。design/materialize 继续使用原 objective/foundation 与新的匹配 portfolio/critic；未新增控制层科学判据或第二来源注册表。
- 修改过的两个 contextual validator 更新 configuration_identity；新增声明与 prompt 进入既有编译身份。已读取变更 digest 记录，其变化范围可由 A 的 hypothesis 合同和 B 的领域工具解释；没有为反馈环修改执行状态机或审批合同。

`test_hypothesis_feedback_flow.py` 覆盖实际 preflight、normalized invoke、Worker 写入/封存、错误来源、revision key 负控、错绑旧 critic 及 materialize。它是工程 fixture，不能证明模型会正确解释反例、数值失败或不可辨识。

## B：默认投影、原件与消费者

已核对 Root 29 项声明与共享投影、通用/领域 Worker 19 项及生命周期 3 项，并读取 [逐接口审计清单](../evidence/mcp-response-levels/TOOL_AUDIT.zh-CN.md)。

Root 展示参数仅在 MCP 路由读取，未混入 OperationCallInput 或 immutable fingerprint。preflight 的 normalized_request 保持完整；Agent invoke 仍交付精确类型、profile、名称及恢复预算。operation_catalog 默认分页摘要，按 operation_id/detail 获取同一编译声明；artifact detail 保留有序 parents/null alias。

run_status 的非空 output_paths、空列表和 detail/full 优先级与参数说明一致。默认 /summary 片段明确标记 excerpt，指定 pointer 不再被二次截短；完整原件仍来自原服务。execution 日志仅从默认投影移除，detail 读取既有 observation，不重新求解。lifecycle 限量发生在持久观察游标更新之前，未交付事件不会被提前消费。

分析计算先通过原 tool evidence 保存完整 CalculationRecord，随后返回指标摘要与可读 calculation_path；诊断详情及原图继续可读。TCAD debug 和文件目录检查分别保存任务内详情，再返回有界状态/候选。Local legacy 合同从 `_compiled` 的同身份校验取得，写入受控只读文件，没有把旧 workspace 替换成新 live 合同。相关领域工具的 Component identity 已更新。

Python facade、审批 UI、轨迹和归档继续取得底层完整返回；MCPRouter 应用输出投影，stdio/daemon/proxy 的 text 与 structuredContent 保留协议兼容。普通错误没有被统一截断或改成成功。显式取证、normalized_request、无法再展开的具体诊断、Hardened 合同属于必要大小例外。

## 组合结论与验证限制

新 feedback 端口可从选定 Operation 的 detail 看见。scheduler 源明确用 run_status(detail, output_paths=[]) 和 artifact_catalog(detail) 恢复原绑定及父链，再向 critic/revise/design 补绑相关原件。摘要未成为 evidence 或改变 admission；只有 calculation_ref 字符串也未被当作跨 Run 传递原件。**组合路径 PASS**。

已阅读现有 `checks.jsonl` 与测试源码；记录包含开发过程的通过及失败，不在本报告中统称“全绿”。首次静态审查时安装测试、最终资源记录与体积对照仍由实施者补齐；随后取得的工程测试证据见文末补核。本报告不代替其最终验收记录。

仍未由本审查独立运行验证：安装包/生成客户端的最终状态、旧合同真实审批兼容、旧 Run 恢复、传输端到端、并发分页变化、最终修改后的测试结果与资源/整段调用总量，以及三类真实 LLM 行为验收。部署应按既有规则处理活动 Run 和客户端合同刷新；本报告未授权或执行部署。

## 最终静态复核锚点

以下是关闭发现后直接读取文件所得 SHA-256，界定本报告的关键源码版本；后续修改需要重新评估受影响结论。

| 文件 | SHA-256 |
| --- | --- |
| `src/scidiscovery/general_science_agent_operations.py` | `45a4ee0308e4f44d13abdadf438f06c54f66cf3dbb92f56d8c3afab606976504` |
| `src/scidiscovery/general_science_components.py` | `555d601612a27ab86da5f753562049f79093c5084b082f0e279975f43c155d98` |
| `src/scidiscovery/general_science_resources.py` | `700fefb6d2394a3105c64adad38827e75bcf2ce41a23fb9ee396f7a327915944` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_response_views.py` | `ddcef5c8689c01e4a7b0b2fc5dd9c1c9d3968543725b5d8c22556677cea222bd` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` | `7579a053f70e205164875e52832f858c8a0d3ee95ac08f6a5deca6d192369f3c` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_hardened_worker.py` | `0434ccf48931b468c7cb3f8afbbc53f604343c5e07155e9b5ca0f3d3e118e7ac` |
| `plugins/curve_figure_evidence/curve_figure_evidence/figure_worker_tool.py` | `3be0206fd9130c13b3b4a996993067e941203c4fedb8ff86eaa3dc92eb049a36` |

## 最后补核：恢复引用与已完成工程证据

同日追加，只读源码、测试和既有日志，未运行测试或构建。**A、B、组合路径的静态 PASS 结论保持。**

`mcp_response_views.py:run_summary` 增加保留 `draft_from`。该字段由 `mcp_root_run_routes.py:185` 从当前实例绑定取得，值是已有 Run 的短语义名或 null；不包含未封存草稿正文，也不改变恢复准入、预算或 immutable request。`test_root_draft_routes.py:79` 的既有消费者明确读取 invoke 回执中的这个引用，保留它符合精确恢复要求。

重新核对上表七个文件的 SHA-256：其余六项未变化；在内存中只移除新加入的 `draft_from` 白名单项，所得文件哈希精确回到原审查值 `22736a5f73373b729641974f089704988198e28b276302523aaaa38e271182cb`。因此该关键投影文件自首次 PASS 后的变化确为这一项；上表已更新为最终哈希。

已直接读取 `checks.jsonl` 及以下三个日志尾部，确认实施者的工程验证结果：

| 验证批次 | 日志 | 结果及外层监控 |
| --- | --- | --- |
| `test_analysis_tool_installed.py` | `check-1789537847232248791.log` | 12 passed；整批 59.9 秒；进程树峰值 228,626,432 bytes，约 218 MiB；exit_code=0 |
| 新反馈、历史兼容、profile/恢复预算 | `check-1789537959904074089.log` | 15 passed；整批 15.12 秒；exit_code=0 |
| Root 投影、draft 恢复、TCAD/figure、UI 与审批身份 | `check-1789537825093684057.log` | 37 passed；整批 12.09 秒；exit_code=0 |

上述均为实施者运行、审查者读取留存记录确认的工程测试；本审查未独立重跑。它们补足相应安装/恢复路径的工程证据，不证明三类真实 LLM 科学行为验收通过，也不代表部署或生产科学接续完成。
