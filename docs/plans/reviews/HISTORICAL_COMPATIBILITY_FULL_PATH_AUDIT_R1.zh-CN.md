# 历史记录兼容性全路径审查 R1

日期：2026-09-09。结论：**当前兼容修复不能通过完整路径验收；已修复读取和部分 Agent 准入，但历史记录跨轮推进仍有断点。**

## 范围与证据

审查对象为 `refactor/m7-pre-e5.2` 的当前未提交工作树，HEAD 为 `2edac5d317a74056869a567bd0daa7f556ecbc85`。工作树含大量既有修改，本次未修改运行源码、科学对象或审批状态。使用跨边界审查方法，核对读取、输入绑定、设计、展开、修订、证据来源族、人工批准、author、分析、执行及旧 Run 生命周期。

编译核心、通用科学、TCAD、曲线评分及图证据插件，形成 **50 个 Operation、258 个输入端口**的规则清单。清单不意味着每个端口都运行过端到端测试。精确审查文件摘要、端口清单、探针及日志位于 `../evidence/history-contract-compatibility-audit/`。

本次 8 项轻量探针全部通过，含义是**成功复现报告描述的现有行为，不代表修复验收通过**。运行 0.99 秒，峰值 RSS 88284 KiB，串行、3 GiB 虚拟内存上限、90 秒超时。未运行全量、压力、安装矩阵或真实 solver。上轮 41 项测试证明了其覆盖的边界，但没有覆盖下面的完整串联路径。

## F1 — P1：设计接受历史 cohort，计划展开却拒绝同一 cohort（已在实际研究发生）

位置：`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1326`、`:1337`；`src/scidiscovery/general_science_experiment_operations.py:263`。

`allow_historical` 仅对 Agent 的 `prior_signal` 生效。`science.experiment.materialize.v1` 是确定性 Transform，尽管原始目标、假设与科学依据也声明为 `prior_signal`，仍要求生产合同摘要完全匹配。

实际路径：历史假设组合接受当前独立审查，生成 `fig4_continuation_hypothesis_critic_3.output`；新设计 `fig4_continuation_experiment_intent_3.output` 完成。展开绑定同一 cohort 时，`hypothesis_portfolio` 报 `input_producer_contract_changed`。因此新设计自身合格仍无法形成正式计划。

修正方向：允许确定性展开读取精确历史 cohort 作为来源见证，继续检查新设计与原始 cohort 的父子关系、当前审查及所需批准。不可删除 cohort 来规避：当前 `_materialization_lineage` 在无 foundation 时允许省略上下文，但这样会失去正式计划的直接原始目标见证，违反本项目恢复路径要求。

## F2 — P1：重新审查可以完成，但按审查意见修订仍被历史生产合同拒绝（代码与探针确认）

位置：`mcp_root_operation_routes.py:1337`、`:1482`；`general_science_experiment_operations.py:193`；`plugins/tcad_artifact/tcad_artifact/plugin.py:466`。

计划、TCAD 项目可通过 `prior_signal` 交给新审查者。相同对象交给修订操作的 `revision_base` 时，却仍要求旧生产者摘要等于当前摘要。即使提供当前合同下、精确匹配该对象的非通过审查，阻断也发生在审查关系校验之前。

影响：升级后“读旧对象→当前审查→按意见产生新版本”的纠错路径不闭合，可能被迫整体重做。探针分别覆盖实验计划修订与 TCAD author 修订。

修正方向：区分“用旧对象作为新版本的编辑基底”与“恢复旧 Run”。前者可在结构兼容、精确新审查关系及有界修订约束下允许；后者继续禁止跨合同恢复。不能放宽旧 change_request 的当前审查要求。修订计数目前在生产摘要变化时终止回溯（`:1221`），放开基底时还须明确跨代修订预算，避免隐式重置无进展循环。

## F3 — P1：重新申请证据批准存在两层历史来源障碍（代码与局部探针确认，未在当前实例触发）

位置：`mcp_root_operation_routes.py:508`、`:513`、`:598`；`general_science_control_operations.py:211`；`general_science_components.py:316`。

第一层：批准操作不是 Agent，旧 extraction_primary 即使声明 `prior_signal` 也在通用准入被拒绝。
第二层：即使只放开第一层，`_run_output_family` 和 `_transform_output_family` 仍因生产版本/摘要变化返回 None。资格投影器要求精确完整来源族，随后仍会拒绝。

这不是要求继承旧批准，而是**请求人类对历史精确证据作一次新决定**的路径也不完整。当前实例已有 foundation 批准能被识别，不能据此推断所有升级后的资格续接都可行。

修正方向：来源事实应从冻结记录核验，不因当前提示词变化消失；当前资格另行判断。新批准仍绑定原始精确主体、完整来源族和新审查。旧 Transform 的端口/集合结构无法从冻结记录唯一证明时应报告具体缺失，不能直接按当前端口猜测，也不能以跳过完整族检查解决。

## F4 — P2：放行依据只有类型标签，尚未检查旧载荷结构兼容性（代码与探针确认）

位置：`mcp_root_operation_routes.py:1490`；`src/scidiscovery/operations/invoke.py:208`。

当前“历史兼容”只比较 schema ID、kind 与媒体类型。`_validate_input_content` 只检查端口声明的少量顶层必填字段；无此声明时不会读取载荷，也没有根据当前输入 JSON Schema 验证其结构。

探针证明：历史计划元数据匹配时可进入审查准入，随后该内容检查不会发现 `{}` 这样的不兼容对象。本次未把畸形对象投入实际 Worker；因此不声称已观察到某一种具体 Worker 失败。

影响：同一 schema ID 内字段变化可能直到任务打开、领域上下文校验或最终提交才暴露，被误认为科学缺口或 Agent 输出错误。不能把“schema 名称一致”称为结构兼容证明。

修正方向：对需要按当前结构消费的历史输入，使用已有输入 Schema 做有界结构验证，返回输入端口和字段位置。不引入自动科学迁移，不替旧记录补参数。原样背景阅读与结构化消费分别判断。

## F5 — P2：历史交接不可解析时，独立完好的载荷仍被隐藏（代码与探针确认）

位置：`src/scidiscovery/artifact_agent/interfaces/mcp_root_run_routes.py:102`；`service/run_records.py:147`。

历史 `signal_json` 若不能按当前 SchedulerSignal 解析，`value.signal` 为 None，`_sealed_output` 在读取并核验载荷之前返回 `invalid, None`。因此上轮修复并未覆盖交接格式变更导致的历史读取问题。

修正方向：独立报告载荷是否可核验、交接是否可解析。完成记录中完整封存的载荷仍可供历史阅读；缺失的交接不能伪造，也不能用于资格判断。不需要新增 Run 状态。

## F6 — P2：历史性与资格信息在不同读接口中表达不一致（静态确认）

位置：`service/runs.py:682`；`interfaces/mcp_root_instance_routes.py:149`；`service/run_assignment.py:36`。

run_status 已明确给出 historical 和可解析交接；inventory 仍通过要求当前合同的 `signal_for_output` 取交接，因此同一旧记录显示 `producer_handoff: null`。`claim_admissible` 只来自标签，不等同于当前准入。Worker 输入描述含 usage/exposure，但没有历史合同状态。

这不会直接绕过执行门，属于解释与上下文缺口：调度者或新 Worker 难以区分“没有记录”与“记录存在但不提供当前资格”。

修正方向：复用现有描述接口给出明确历史/资格语义，不恢复旧 verdict 的资格，不把生产者身份细节泄露为 Worker 控制权限。该项可晚于 F1–F4，不应借机扩张统一状态系统。

## 应保留的严格边界

- 实例内精确引用、摘要和大小核验、父子关系、当前对象约束与预算。
- 当前独立审查必须绑定同一精确主体；旧 pass 不自动转为当前 pass。
- 执行请求继续匹配当前编译审批身份、适配器、精确载荷及 UI 决定（`mcp_root_execution_routes.py:297`）。
- 旧 queued/running Run 不交给新合同 Worker；旧失败 Run 不跨合同恢复。旧 Run 超时可终结，但未超时的退休 Run 目前不能普通 record_failure；这是运行恢复范围的问题，不是科学材料可读性的放行理由。
- author 当前 `experiment_plan` 是 claim_evidence，严格拒绝退休计划属于当前政策；不能因为修好历史上下文，就宣称旧计划可直接交付执行。当前案例应继续使用新设计生成的新计划。
- 分析操作的旧结果可以走已声明的 inventory；精确 plan/package/runtime 身份仍须检查。生产者卸载或类型变化时，结构化消费仍有限制，不能声称任意历史执行都可直接重分析。

## 根因与最小修正顺序

根因是完整 Operation digest 同时被用于运行身份和历史内容兼容判断。digest 包含提示、权限、Schema、reviewer digest 与批准 provider；审查者变化也会递归改变生产者 digest（`operations/catalog.py:703`）。这适合冻结 Run 身份，却不能独自回答历史事实是否可读取、是否可作为新版本基底。

上轮按 executor_kind 放开 Agent，保留全部 Transform 严格校验，边界过粗。不要反向把所有 Transform 都放开，也不要移除提示/审查内容的 Run 指纹。

建议同一轮完成：

1. F1：打通新设计的精确 cohort 展开，保留 lineage、新审查与批准。
2. F2：打通历史对象在新审查下的修订，并明确跨代修订预算。
3. F3：核验并保留历史来源事实，区分申请新批准与继承旧批准。
4. F4/F5：加入必要的输入结构校验，分开载荷读取与交接可解析性。
5. F6：用已有状态/输入描述表达历史性，不新增状态机、迁移引擎或兼容白名单。

实施前应将端口清单按实际动作核对，而不是只按 Agent/Transform 推导。必要时只对确有需求的输入声明有限兼容策略；来源、审查、批准和执行校验仍由既有控制面执行。

## 验收必须覆盖的串联路径

- 历史假设＋当前精确审查 → 新设计 → 带完整原始 cohort 的展开 → 新计划独立审查 → author 准入。
- 历史计划/项目 → 当前非通过审查 → 修订提交新对象 → 新对象重新审查；旧审查、错主体和无进展重复请求均拒绝。
- 历史证据族 → 当前独立审计 → 新 UI 批准请求；漏来源、错来源、错摘要和继承旧审批均拒绝。
- 完成载荷与旧格式交接分别读取；结构不兼容的历史输入给出准确位置，不拖到 author 才发现。
- 原执行审批/身份负控继续拒绝；不为证明兼容而运行真实 solver。

当前实际研究的最短恢复点仍是 `fig4_continuation_experiment_intent_3.output`，无需重做已完成的设计。所有后续准入仍须在安装后通过真实控制面重验。
