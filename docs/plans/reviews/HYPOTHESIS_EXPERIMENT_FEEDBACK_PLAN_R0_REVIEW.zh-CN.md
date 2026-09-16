# 实验反馈进入假设演化计划 R0 独立工程审查

日期：2026-09-16。结论：**REVISE**。

被审文件：`docs/plans/HYPOTHESIS_EXPERIMENT_FEEDBACK_PLAN.zh-CN.md`。
SHA-256：`02489e0e0384475e23ec95d4f9be50a55d479ca056fae4dacffcb320f6692388`。
源码 HEAD：`90a7b3a5865eb45649f1a39221337f9d939a3d71`；另有会话生命周期、工作台和测试的未提交修改，本审查未修改这些文件。

独立审查者未参与计划编写。按 `scid-cross-boundary-review` 技能核对当前源码，只读检查及两次内存静态探针；未运行 pytest、构建、科学 MCP、部署或求解器。唯一写入为本报告。

## 发现

### P1-1：新增可选反馈会收紧所有调用的来源枚举，计划未解决旧 foundation 引用和 critic 基础来源的兼容

计划位置：第 3 节第 51 行，第 4.3 节第 97–99 行，第 7.1 节 E1/E3（第 149–151 行）。

`operation_contract.py:561` 的 `_evidence_source_projection_version` 根据**声明中存在**可读 `evidence_inventory` 启用投影，不以本次是否绑定反馈为条件。当前三条 hypothesis 操作均不启用此投影；按计划加端口后，即使没有绑定反馈，也会启用 `evidence-source-enum.v2`。`operation_contract.py:545` 只把 `context_sources` 中实际绑定 alias 放入枚举；`run_outputs.py:297` 在运行时用同一 Schema 验证。

这有两项可达后果：

- proposal/revise 目前由 `general_science_components.py:138` 明确允许 foundation 自带 `evidence.source_key` 和条目中的 `evidence_keys`。这些 provenance key 并非当前任务输入 alias；例如 foundation 内的 `source`，在旧输出的 `evidence[].source_key` 中合法，新 Schema 会先拒绝，根本到不了保留该能力的 contextual validator。无反馈初次提案与合法旧稿局部纠错均受影响。
- critic 当前 `context_sources` 只有 `hypothesis_portfolio`（外加声明器加入的 `user_context`），见 `general_science_agent_operations.py:433`。只追加计划列出的新端口仍遗漏已绑定、可读的 `scientific_foundation`。critic 新报告连直接引用 `scientific_foundation` 都会被拒绝，违背第 4.1 节“基础和反馈都是可查来源”。

内存探针只给三份现有 OperationSpec 追加一个可选反馈端口，结果全部从 `projection_before=None` 变为 `projection_after=evidence-source-enum.v2`；源码确认允许集合来自输入 alias，不读取 foundation provenance。探针不代表整条 Worker 链已验证。

最小修订：把这两个兼容问题列为明确交付，不只要求“新反馈 alias 能提交”。critic 把 `scientific_foundation` 纳入引用上下文；proposal/revise 在计划阶段选定兼容策略，使 Schema 与 validator 对 foundation provenance 的接受集合一致。若选择以后只写 `scientific_foundation` 加 locator，须明确这是新输出引用规则变化，处理 revision 旧稿中的合法引用，并修订“原提交方式继续可用”的承诺；不能在保留旧来源合法性承诺的同时直接启用仅 alias 的枚举。若保留现有 provenance 能力，需要把必要的投影适配文件纳入范围，避免全局放宽来源校验。E1/E3 增加无反馈、foundation provenance、critic 直接引用 foundation、未知来源拒绝四类负正控，并经过真正提交入口。

### P1-2：共享 REPORT_GUIDANCE 变化不进入现有 compiled identity，计划漏列两个组件身份所有者

计划位置：第 4.4 节第 107 行，第 5 节第 119–120 行，第 6 节第 135 行，第 7.1 节 E11。

`analysis_workspace.py:251` 把 `REPORT_GUIDANCE` 写入工作区，属于 Worker 实际可见合同。然而它不是被编译器直接散列的 prompt resource。通用分析通过 `science_operations.py:1032` 的 `analysis_materializer` 引用它；TCAD 的 `analysis_bindings.py:175` 再调用该 materializer，自身身份在 `result_analysis.py:584`。两处 configuration_identity 当前均为 `analysis.user-context-origin:v1`。

内存探针编译 CORE/GENERAL/CURVE/TCAD catalog，仅在内存给 `REPORT_GUIDANCE` 追加一条指令后再次编译。`science.result.diagnose.v1`、`science.result.diagnose.curve-error.v1`、`tcad.result.analyze.v1` 的 digest **全部未变**。编译器 `operations/catalog.py:758` 散列组件声明及 resource digest，不自动散列 Python 函数体或此字符串。

照第 6 节列出的文件改报告指引，无法兑现“prompt 变化必须进入 compiled contract digest”；同 digest 下可能出现不同工作区指令，旧恢复合同也无法识别该变化。

最小修订：要么将这个非核心闭环必需的报告文案调整移出本补丁；要么显式追加 `plugins/curve_score/curve_score/science_operations.py` 与 `plugins/tcad_artifact/tcad_artifact/result_analysis.py` 两处 materializer identity 更新。无需新增注册表或修改恢复协议。E11 应分别证明三个分析 Operation digest 变化，以及无关执行/审批身份不变；不能只测 hypothesis 的声明变化。

### P2-1：critic 的模型可见 semantic contract 仍要求事实只能位于旧 foundation

计划位置：第 4.1 节第 79–85 行，第 6 节 P1。

计划明确修改 `CRITIC_PROMPT`，但没有明确同步 `Resources.critic_semantic_contract`。后者 `general_science_resources.py:133` 仍规定：`The critic checks that factual premises stay inside the already qualified foundation and that inferences remain explicit.` `operation_contract.py:498` 将这条规则嵌入输出 Schema 的 `x-scidiscovery-semantic-constraints`，因此并不是未使用的旧文档。

只按明确列出的 prompt 改法实施时，critic 同时看到“允许绑定的新运行观察”和“事实前提必须在已批准 foundation”两套规则。有效新反馈仍可能被判成缺基础证据，重新进入补 intake 的旧循环，削弱本计划的核心目标。

最小修订：明确同时修改这条 semantic contract，允许引用本次绑定的运行观察，并保留模拟、实测、分析解释及旧 foundation 资格的区分。相关 prompt、Schema 内语义规则和验收断言使用同一规则；无需新增科学判据校验器、强制证据表或通过门槛。

## 对计划五项问题的回答

1. **功能闭环方向正确，尚未可直接实施。** propose/critic/revise 的可选反馈可补齐关键缺口；既有 design feedback、匹配 critic disposition、materialize 精确 parentage 足以继续下一轮。必须修复上述引用及语义缺口；不需要新增 Operation 或强制固定 DAG。
2. **目前仍存在“可读却不可引用”。** P1-1 是实际跨层缺口。保持输入准入归 preflight、输出只验证输出的方向正确；本审查不建议在提交时重查资格或加全输入集合相等门禁。
3. **控制与历史边界设计合理。** `review_admission.py:23` 把 evidence_inventory 当背景；`InputPortSpec.require_current` 默认 false；`runs.py:1107` 对 completed 输出按版本及输出类型兼容读取。设计和物化仍有精确 cohort/parentage；proposal 不继承旧 critic 的结论。旧 foundation 审批不应因消费者端口变化被取消，这一要求应保留，但尚未实际重放历史审批对象。P1-2 必须补齐合同身份。
4. **没有看到不必要的强制填表。** 维持可选 assessments/gates、允许保持候选、区分数值失败及不可辨识、保留 revision key 守卫均合理。48 MiB 是输入总上限而非默认提示长度；revise 的各端口独立最大值合计可能高于总上限，按现有总字节检查拒绝是正常约束，不应为“端口全填满”扩大预算。
5. **验收方向充分，安装成本需实施前细化。** E2/E3/E6/E7 的一条真实封存纵向链与 E10 的安装入口检查值得保留；无需全量套件。B1/B2/B3 应继续独立报告科学行为结果，不将合成材料当生产证据。

## 测试、资源与未验证项

本审查只执行只读查询和轻量 Python 内存探针，两次探针工具观察墙钟分别约 0.23 秒和 1.30 秒，未测得峰值内存，不声称满足完整验收资源预算。未创建 Run 或 Artifact。

建议明确 E10 的具体节点和安装复用方式：`tests/operations/conftest.py:58` 的 session fixture 即使只选一条 installed 测试，仍构建核心、多个插件及测试 fixture wheel；第 99 行的循环对每次构建单独给 180 秒。它自身不等价于计划要求的整批 180 秒或进程树 2 GiB 上限。串行和总预算合理，但应由外部监控对整个 pytest/构建子进程树落实，并复用一次构建结果；预算不够时记录未验证，不自动加额，也不为本计划另造大测试基础设施。这是执行细化建议，不据此认定现有 fixture 必然超额。

未验证：实现后的 preflight/invoke/实际 Worker 提交；旧合同生产对象的审批兼容与恢复重放；隔离 wheel 和生成 Agent 配置；真实 LLM 行为；生产 Fig4 接续；运行时峰值内存。当前不存在实现，因此本报告不提供实现 PASS 或科学有效性结论。

修订上述三项后可复审计划；本结论不授权源码实施或部署。
