# 用户文本接入计划 R2 独立工程复审

结论：**PASS**。本次未发现需要再次修订计划的实际阻断。R1 唯一阻断已在 R2 的实施范围和完整入口验收中闭合，可以按本计划进入最小实施。**计划通过不等于实现已通过、安装已验证或现场续接已验收。**

审查日期：2026-09-14。

审查对象：`docs/plans/USER_TEXT_CONTEXT_INGRESS_PLAN.zh-CN.md` R2，SHA256 `7b4f194326912bc3c697cbfec5d8dc9f3d8cba461ee0bcd82217962ab6d543c0`。审查开始和结束均核对一致。

源码参照：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`，HEAD `096a13fd89aacf2d4e73f77e87ab3174e5f89ec3` 加现有未提交工作树。既有 handoff 代码、文档和测试改动仅作为当前背景，不计作本轮实现。R1 送审快照及 R0/R1 报告作为历史对象读取，没有改写其结论。

本次按 `scid-cross-boundary-review` 和 `karpathy-guidelines` 做只读静态追踪，阅读了相关当前架构、设计宪章与约束。没有运行测试、构建、安装或求解器，没有调用科学或生产控制工具，没有读取生产 state 或 Worker 私有目录，没有改动仓库或派生 Agent。唯一写入为此临时报告。

## 1. R1 阻断的独立核对

R1 指出的路径真实存在：

1. Root 在 `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1099` 调用 `completed_for_output`，随后构造 `InvocationArtifact` 并进行入口预检。
2. `src/scidiscovery/artifact_agent/service/runs.py:132` 明确从权威记录重建输入；`:136` 已加载 producer，`:137` 新建另一组 `InvocationArtifact`。
3. `runs.py:148` 再次调用 `preflight_operation`；`src/scidiscovery/operations/invoke.py:218` 调用 guards。`science.evidence.revise-from-critic.v1` 在 `general_science_agent_operations.py:607` 声明 `evidence_revision_cohort`，其当前来源推断位于 `general_science_components.py:108`。

只在 Root 增加 `producer_inputs` 会在第 2 步丢失它，导致两次预检不一致。R2 的第 81、83 行现已明确要求 Root 与 `RunService.schedule` **各自**从已有 producer 记录投影原有序绑定；第 135 行将 `runs.py` 列入实际修改责任，第 140 行同步文件范围。权威重建和再次预检均保留，未改成信任上游对象。

R2 A4（第 153 行）也明确要求通过实际 Root `preflight → invoke`，分别验证无说明和仅 intake audit 携带说明的原合法 cohort 均可排队；同时要求遗漏/替换原来源仍失败，缺少 producer 元数据有定位诊断且不得回退到全部父节点。这覆盖了 R1 的具体可达失败，包括无说明回归，不再以纯 guard 或入口预检成功替代调度成功。

所需数据已经存在于持久化 Run 绑定，两个现有构造位置也已执行 producer 查询。因此该修正可以只补非持久化投影及其消费，不需要新数据库字段、全历史扫描或恢复算法。R1 阻断在计划层面闭合。

## 2. 其余关键边界复核

| 边界 | 静态核对与结论 |
| --- | --- |
| 原文登记与身份 | 现有 `service/intake.py:68` 可直接注册字节；`mcp_root_instance_routes.py:215` 已提供指纹、创建锁、语义绑定及 revision 路径。R2 的固定来源元数据与原始 UTF-8 分离，保留实际调用身份。8,192 个有效 Unicode 码点最多占 32,768 UTF-8 字节，公开字符边界与端口容量一致。无需临时项目文件或科学预处理结果。 |
| 单一声明与安装入口 | `operation_declaration.py:177` 的共享构造器覆盖其调用者；TCAD author/review 和 parameter 的直接构造处确实需要显式接入共同助手，R2 已列明。`platforms/codex.py:38` 的 `SCHEDULER_TOOLS` 从 Root 工具声明生成；A8 要求实际安装入口验证，未增加第二工具白名单。25 个公开 Agent 的最终覆盖仍由实施阶段的编译目录矩阵验证。 |
| 无说明引用兼容 | `operation_contract.py:562` 的来源枚举触发取决于可见 `evidence_inventory`，新增 `prior_signal` 不自行激活它。`general_science_components.py:133` 已将 foundation 自有来源键纳入 hypothesis 引用。R2 保留该行为，并为已存在 context validator 的输出添加可选实际别名；A2/A3 的正负控与真实风险一致。 |
| 参数正式来源 | `parameter_operations.py:402` 当前用“其余 sources”作为来源，`:576` 与 `:638` 当前将全部父链等同于正式集合。R2 已定点要求改为原 producer 端口绑定，保持完整父链、原顺序、清单、扩展对象、审查成员和来源别名。`service/run_outputs.py:217` 已同时提供来源 bytes 与 `ValidationSources.binding_descriptors`，无需修改 validator 签名或新增来源注册表。 |
| 资格所需 producer family | `mcp_root_operation_routes.py:522` 为实际输入取得 producer family；`:567` 的 Agent family 已具有精确 producer 查询，`:598` 的 `evidence_sources` 用途过滤不含 `prior_signal`。新增投影可服务提取与审查两个来源 cohort，同时保持 Transform 扩展路径。R2 没有以删除父链检查替代正式集合校验。 |
| 容量与输入约束 | `operations/invoke.py:171` 起逐项计入完整输入预算并拒绝重复 Artifact。独立 0—4 条 `user_context` 与增加 131,072 字节聚合上限可保留已有四项 `current_progress` 容量。R2 明确保留原逐项边界，并对超限报错，不隐式挤出历史或改写原文。 |
| 新 Agent 可读 | `run_assignment.py:44` 的输入投影可由现有 bound Artifact 标签取得单个来源字段；`runs.py:302` 将所有非 `handoff_only` 输入作为 bytes 交给 backend，`:332` 使用同一 assignment，`local_workspace.py:154` 原样写入。`analysis_workspace.py:177` 已先索引原件再生成可选节选，原文无需能解析成 JSON。R2 P3/A6 要求原文路径、真实来源和重新打开新 assignment，符合现有读取边界。 |
| 恢复与合同变化 | `runs.py:1348` 要求活动 Run 使用原完整合同；`:1436` 的 `draft_from` 支持同 Operation 的新合同/输入并保留实例、后端、草稿和尝试预算检查；`:1597` 的 `resume_from` 保留相同 digest 和有序输入限制。`mcp_root_operation_routes.py:1601` 起另行支持兼容的已封存同版本成果。R2 正确区分这三者，并要求部署前处理活动 Run，无需统一升级 Operation.version 或迁移所有旧成果。 |
| 科学与控制分工 | 新说明是可读可引用的原始用户信息。控制层处理字节、来源、绑定、资源和完整性；科研 Agent 判断采纳、证据力度、范围及缺口。说明不替代独立 `change_request`、资格或 UI 决策。R2 不新增科学真假分类、机械采纳证明、自动流程或第二状态权威。 |

## 3. 实施时保留的具体条件

以下均由 R2 现有要求覆盖，不构成本轮新增修订项：

- `producer_inputs=None` 与已知空序列保持不同。只为精确已完成生产者建立所需投影，保留输出身份及父链完整性；不要把 `completed_for_output` 的工具附属输出回查分支泛化为任何状态都可获得正式 producer 元数据。该方法位于 `runs.py:764`，原 `ProducerOutputFamily` 路径已有主输出核对。
- 完整父链可能包含受控工具证据父节点（`runs.py:1237`），因此一般输出不能机械要求所有 parent 恰好等于端口投影。R2 已要求保留原工具和 Transform 家族路径，不建立通用依赖图。
- 分析入口有显示预算；`analysis_workspace.py:60` 可能省略后续索引，TCAD 在 `analysis_bindings.py:173` 仅预留 12 KiB 首读空间。实现 A6 时应保留指向完整 assignment 输入索引的有界导航，并确保用户说明可从那里到达；无需提高全部展示预算或复制全文。
- `preflight_operation` 在 `operations/invoke.py:130` 要求包含全部声明端口；Root 在 `mcp_root_operation_routes.py:1130` 已为空可选端口补键。现有手建纯函数测试 map 可能需要添加空 `user_context`，属于受影响夹具的最小调整；不需要放宽 binder。
- guard、validator 或 projector callable 行为修改须同步现有 `configuration_identity`。声明与资源摘要仍由原编译器负责，不能假定 Python 函数体自动进入全部身份。

## 4. 验收范围与限制

未观察或运行 R2 的实现验收；因此本报告不宣称 A1—A10 已通过，也不继承此前 handoff 改进的测试结果。实施后仍应按计划提供无说明负控、引用与来源资格完整链路、真实 `preflight → invoke`、满槽预算、assignment 读取、恢复、隔离安装入口、独立实现审查和最小现场续接证据。

本轮没有必要增加独立摘要 Agent、新 Schema/表/状态机、普遍来源分类器、一般历史重资格机制或运行算法重构。R2 的范围足够具体，关键跨边界消费者已有明确责任和验证入口；可进入所列最小实施。
