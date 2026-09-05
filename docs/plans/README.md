# SciDiscovery 决策语料索引

本目录保存完整的工程计划和独立审查历史。当前执行入口只有下列八项；其他文件是可追溯的历史
证据，不是并行待办、兼容规范或第二状态权威。

## 当前执行链

- [R5-M L 后生产代码奥卡姆裁剪计划](R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md)：
  M0—M7.5 已完成；安装矩阵、真实通用/TCAD/修订/Effect/恢复纵向链、科学—控制负例、物理报告和
  全量 `286 passed` 均有独立证据。两位 M7.5 独立终审者分别从正确性/跨边界与简化目标/33 项约束
  审查，均为 PASS、阻断 0；R5-M 已关闭。历史 FAIL、无收据 Run 和 `SEC-002 known_issue` 原样保留。
- [OperationSpec 中心的最小重构总计划](OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md)：
  以8765版本为行为基线，用一个插件入口和一个启动期编译目录组织多角色 Agent、确定性能力、
  领域工具和轻量门禁；阶段状态以该文件第26节为权威。
- [R5-N 调度行动权威简化](R5_N_SCHEDULER_ACTION_AUTHORITY_SIMPLIFICATION.zh-CN.md)：
  当前纠偏任务的唯一实施记录；具体 Operation 由调度 Agent 从唯一编译目录选择，Worker 只提交
  封存科学结果和非约束性建议。旧 `next_action_kind/accepts_actions` 字段仅作兼容元数据，其类型化
  路由行为已经撤销；旧假设契约保留为历史证据，不再是当前运行规范。
- [R5 下一轮真实端到端缺陷账本](R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md)：
  当前 M7 真实 Fig.4 端到端实验的唯一活动缺陷与实施入口。E5.2 安装态回归新增 E5.3：请求 Agent
  错误承担轴端点规范化与跟踪阈值设定，真实输出出现纵轴反转和生产者自定义验收门槛；完整科学链
  暂停在独立图审查 `blocked`，E6 未放行。下一轮只解耦科学图证意图与确定性算法请求，不重写调度器。
- [R5 E5.2 图曲线共享定量与校验合同闭合计划](R5_E5_2_FIGURE_QUANTITATIVE_AND_VALIDATION_CONTRACT_REPAIR_PLAN.zh-CN.md)：
  真实 Fig.4 回归推翻 E5.1 的“共享引用不可定量”语义，并暴露 Worker 可见来源合同、Python checker
  和 EvidenceAudit verdict 的错位。本文是当前 E5 返工子计划；保持 ABI 16，只连接已有
  `usage/evidence_paths`、修正 `coincident_overlap` 与局部 finding 传播，并要求真实 Worker 首次提交
  和独立审查通过后才恢复端到端主线。其代码与集成审查历史仍有效，但安装态真实回归发现的新轴
  端点／跟踪职责缺陷由上述活动账本 E5.3 接管，E5.2 不再单独授权进入完整科学链。
- [R5-H 最小收口实施记录](R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md)：
  记录当前边界、所有权、复杂度减法和 H0—H7 阶段门。
- [R5-S 生产代码裁剪与控制面简化计划](R5_S_PRODUCTION_CODE_SIMPLIFICATION_PLAN.zh-CN.md)：
  S0、S1 已通过；旧 S2 默认路径因内部协议仍过重而暂停。
- [R5-L 最小默认运行主干计划](R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md)：
  当前已完成方案；以 LocalTrustedBackend 为默认，以 HardenedWorkerBackend 保留按需文件保护；
  L0—L6 已实现并通过两位独立最终审查者复核。

## 当前审查见证

下列报告解释方案如何被放行，不是新的执行入口或并行状态权威：

- [端到端前最小闭合计划首轮独立审查](reviews/R5_PRE_E2E_MINIMAL_CLOSURE_PLAN_INDEPENDENT_REVIEW.zh-CN.md)：
  结论 FAIL、阻断 2；发现初版四操作拓扑无法进入现有 Intake/资格链，也不能建立可编译 review edge。
- [端到端前最小闭合计划第二轮独立复审](reviews/R5_PRE_E2E_MINIMAL_CLOSURE_PLAN_INDEPENDENT_REREVIEW.zh-CN.md)：
  确认单输出图 `ScientificIntake` 生产者及其精确审查边关闭两项阻断，结论 PASS、阻断 0；只放行
  E0/E1，后续阶段仍须按计划逐段实现、测试和独立审查。
- [端到端前最小范围独立审查](reviews/R5_PRE_E2E_MINIMAL_SCOPE_INDEPENDENT_REVIEW.zh-CN.md)：
  第三版删除 UI、精细诊断和部署再开发后，确认剩余六项均为 Fig.4 闭环或承重约束所需，五 Operation
  是当前执行合同下最小可组合拓扑；结论 PASS、阻断 0，只放行 E0/E1。

- [R5-N 调度行动权威独立终审](reviews/R5_N_SCHEDULER_ACTION_AUTHORITY_INDEPENDENT_FINAL_REVIEW.zh-CN.md)：
  确认三个旧字段只作兼容元数据、ABI保持13、错误提示不阻断科学提交且不存在第二路由权威；结论
  PASS、阻断0，只授权关闭R5-N源码与规范修改。

- [假设审查与后续行动契约修订](HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_REVISION.zh-CN.md)：
  历史实施与审查记录；其中有限修订、精确来源和问题指纹继续有效，机器类型化路由部分已被 R5-N
  取代。

- [假设审查与后续行动契约首轮独立审查](reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND1.zh-CN.md)：
  结论 FAIL；发现证据来源可替换、假设改名可绕过无进展检测两个阻断。历史结论原样保留。
- [假设审查与后续行动契约第二轮独立复审](reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND2.zh-CN.md)：
  结论 FAIL；发现 audit 与 foundation 可错配、同一基线可产生 sibling revision 两个更深阻断。
  后续候选已按 exact audit 父链和 Run 事务单后继规则返工。
- [假设审查与后续行动契约第三轮独立复审](reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND3.zh-CN.md)：
  结论 FAIL；发现同名、不同请求的 `create_revision` 被 Root 误当作幂等，造成 preflight/invoke
  漂移。后续候选已把完整请求指纹与创建目标收敛为共用函数。
- [假设审查与后续行动契约第四轮独立复审](reviews/HYPOTHESIS_REVIEW_AND_ROUTING_CONTRACT_INDEPENDENT_REVIEW_ROUND4.zh-CN.md)：
  结论 PASS、阻断 0；独立验证 exact audit/source、完整请求幂等、并发单后继、失败重试、两级修订
  上限和六路行动边界。只放行当前源码契约，不替代部署和真实科学闭环验收。

- [R5-M0 基线与候选账本独立审查](reviews/R5_M0_BASELINE_AND_CANDIDATE_LEDGER_INDEPENDENT_REVIEW.zh-CN.md)：
  独立复算生产树、目录、后端、Root、数据库和消费者分类后结论 PASS；只放行 M1，并要求先保护离线
  完整性审计、再删除重复事件。
- [R5-M1 首轮实现审查](reviews/R5_M1_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md)：
  其余删除通过，但发现旧 v1 Artifact 库带惰性事件表时无法重启，结论 FAIL，未放行 M2。
- [R5-M1 返工后独立复审](reviews/R5_M1_IMPLEMENTATION_INDEPENDENT_REREVIEW.zh-CN.md)：
  用真实旧 migration 和八类 Schema 漂移探针确认只容忍精确旧事件结构，结论 PASS，仅放行 M2。
- [R5-M2-01 首轮实现审查](reviews/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md)：
  单包与机械展开方向合理，但真实 Run 复现审查拓扑闭环、旧 Task 来源/父链假设和来源别名漏绑，
  结论 FAIL，未放行 M2-02。
- [R5-M2-01 返工后独立复审](reviews/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REREVIEW.zh-CN.md)：
  真实纵向正例、六类负例和领域中性 Transform review 探针确认三项阻断关闭，结论 PASS，仅放行
  M2-02。
- [R5-M2-02 实现证据](evidence/R5_M2_02_CURVE_DIAGNOSIS_BOUNDARY_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  确定性曲线分析与绘图迁入一个 support Transform，诊断 Agent 收敛为单输入单输出；全量回归通过，
  插件净删一个生产文件和 46 行，未扩张核心。
- [R5-M2-02 独立审查](reviews/R5_M2_02_CURVE_DIAGNOSIS_BOUNDARY_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md)：
  真实入口污染、双图摘要和知识更新探针均通过，结论 PASS；只放行 M2-03，不宣称 M2 完成。
- [R5-M2-03 实现证据](evidence/R5_M2_03_OPTIONAL_FIGURE_PLUGIN_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  消费者账本确认论文图 Agent 不属于 TCAD 默认闭环；默认目录移除两个不可运行 Agent，显式可选
  插件仍复用原确定性实现，全量 `222 passed`，等待独立审查。
- [R5-M2-03 独立审查](reviews/R5_M2_03_OPTIONAL_FIGURE_PLUGIN_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md)：
  独立复算目录、消费者、干净 wheel、安装、后端能力与 33 项结构后结论 PASS；M2 完成，仅放行 M3。
- [R5-M3 实现证据](evidence/R5_M3_TRANSFORM_ADAPTER_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  删除四类旧 profile adapter 和二次输出包装，只保留一个编译 Transform 调用器与插件窄函数；四种
  M2 目录摘要保持不变，生产代码净减 621 行；首轮审查要求的全 22 项 M2/M3 双进程等价门与 9 个
  guard 正负例已补齐，正在等待新的独立复审。
- [R5-M3 首轮独立审查](reviews/R5_M3_TRANSFORM_ADAPTER_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md)：
  结论 FAIL，结构方向通过但缺少 M2/M3 全 22 项可执行等价证据；M4 未放行。M2 精确生产源码已
  封存于 `../../archive/r5-m2-transform-oracle/`。
- [R5-M3 返工独立复审](reviews/R5_M3_TRANSFORM_ADAPTER_REMOVAL_INDEPENDENT_REREVIEW.zh-CN.md)：
  精确 M2 oracle、22 项双进程行为清单、9 个 guard 正负例、语义修订绑定和生产来源均独立复验通过；
  结论 PASS，仅放行 M4。
- [R5-M4 实现证据](evidence/R5_M4_SCIENTIFIC_SEMANTIC_BRIDGE_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  删除没有真实消费者的知识 reducer、两个专用状态 Schema 和默认科学晋级桥；保留诊断、current、
  不可变 Artifact 与实验意图的确定性机械物化。完整串行回归 `227 passed`。
- [R5-M4 独立审查](reviews/R5_M4_SCIENTIFIC_SEMANTIC_BRIDGE_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md)：
  独立复核冻结 M2 消费者、20 个保留 Transform、9 个 guard 与实验所有权边界后结论 PASS；仅放行
  M5，不宣称 R5-M 完成。
- [R5-M5 实现证据](evidence/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  公共文件工具和通用 Schema 收敛到唯一提供者，可选论文图形成三 Operation 完整纵向插件，TCAD、
  Hardened 与 portable 改为按选择惰性加载；默认组件 209→186。首审发现论文图 bundle 的审查消费
  未闭合，现已按既有 review admission/parentage 合同返工，等待全新独立复审。
- [R5-M5 首轮独立审查](reviews/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_INDEPENDENT_REVIEW.zh-CN.md)：
  结论 FAIL；真实 Root 证明论文图 bundle 在没有独立 evidence audit 时仍可预检通过，M6 未放行。
- [R5-M5 返工独立复审](reviews/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_INDEPENDENT_REREVIEW.zh-CN.md)：
  真实 Local audit/Root 五类正负路径、M3 oracle 和29项防退化均通过，结论 PASS；仅放行 M6，
  `SEC-002` 仍为已知限制。
- [R5-M6-A 实现证据](evidence/R5_M6A_DIRECT_INSTANCE_MANAGEMENT_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  删除实例/会话伪审批，改为无状态加密本地 capability 与单事务直接绑定；退役审批只读，真实待办用
  稳定 keyset 分页保留。
- [R5-M6-A 独立复审](reviews/R5_M6A_DIRECT_INSTANCE_MANAGEMENT_INDEPENDENT_REREVIEW.zh-CN.md)：
  两轮额外负控关闭 capability 泄露、旧决定写入、LIMIT 遮蔽和 OFFSET/过期竞态，结论 PASS；仅放行
  M6-B。
- [R5-M6-B 实现证据](evidence/R5_M6B_OPERATION_INPUT_ADMISSION_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  端口重复资格字段收敛为每个 Operation 最多一个准入值；首次审查发现 guard 仍保留第二成员权威，
  现已删除隐藏集合并把通用成员检查前移到 guard 之前，等待复审。
- [R5-M6-B 首次独立审查](reviews/R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REVIEW.zh-CN.md)：
  真实声明/guard 漂移探针确认 materialize 与 TCAD 仍有隐藏 all-or-none 集合，结论 FAIL；未放行
  M6-C/M6-D/M7。
- [R5-M6-B 独立复审](reviews/R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REREVIEW.zh-CN.md)：
  bomb guard、两种 materialize 形状、revise/TCAD 部分组和真实 pass/exception 探针确认第二成员
  权威已删除，结论 PASS；仅放行 M6-C。
- [R5-M6-C 实现证据](evidence/R5_M6C_PRODUCER_TOPOLOGY_REMOVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  删除生产者未来用途清单并保留精确 producer/reviewer/revision 边；consumer-only 新用途不改变
  producer 摘要，完整回归 `255 passed`。
- [R5-M6-C 独立审查](reviews/R5_M6C_PRODUCER_TOPOLOGY_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md)：
  独立用途删除扫描、producer 四类漂移、七类审批执行器负例、consumer-only 扩展和完整回归均通过；
  结论 PASS，仅放行 M6-D，M7 未放行。
- [R5-M6-D 实现证据](evidence/R5_M6D_EFFECT_AUTO_APPROVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md)：
  Effect 调用自动建立精确待决定审批并删除公开二步工具；首次审查的双请求恢复和 subject 顺序缺口
  已以稳定 Execution 身份和编译期 tuple 规则返工。
- [R5-M6-D 首次独立审查](reviews/R5_M6D_EFFECT_AUTO_APPROVAL_INDEPENDENT_REVIEW.zh-CN.md)：
  随机审批身份在提交/绑定窗口产生双权威，反向 subject 合同到 start 才失败，结论 FAIL。
- [R5-M6-D 独立复审](reviews/R5_M6D_EFFECT_AUTO_APPROVAL_INDEPENDENT_REREVIEW.zh-CN.md)：
  五次故障重放仍单请求、反向合同零运行写入拒绝、字段篡改与完整 `257 passed` 均通过；结论 PASS，
  仅放行 M6 整体回归与独立终审，M7 未放行。
- [R5-M6 整体首次终审](reviews/R5_M6_OVERALL_INDEPENDENT_FINAL_REVIEW.zh-CN.md)：
  发现 Execution 创建/绑定窗口可累积随机孤儿，且 Approval/Execution 查询仍含隐藏写入，结论 FAIL；
  当前两项已返工并由下一轮独立复审确认转绿，历史结论仍保留。
- [R5-M6 整体第一次返工复审](reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW.zh-CN.md)：
  首次 B1/B2 转绿，但发现 request Artifact 已提交、Execution 行未插入时无法重放，结论 FAIL；当前
  已按精确稳定 Artifact 身份完成第二次返工并由下一轮确认 B3 转绿。
- [R5-M6 整体第二次返工复审](reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW_ROUND2.zh-CN.md)：
  B3 与先前反例转绿，但发现已有 Execution 行的恢复未核对原 Artifact 幂等记录，结论 FAIL；当前
  第三次返工已让两条恢复分支重放同一登记。
- [R5-M6 整体第三次返工复审](reviews/R5_M6_OVERALL_INDEPENDENT_REREVIEW_ROUND3.zh-CN.md)：
  两个提交窗口、字段/元数据/幂等记录负例、并发、查询纯度、结构门与完整 `263 passed` 均独立通过；
  结论 PASS，仅放行 M7，不宣称 M7 或 R5-M 完成。
- [R5-M7.1 安装与运行矩阵独立复审](reviews/R5_M7_1_INSTALLATION_RUNTIME_MATRIX_INDEPENDENT_REREVIEW.zh-CN.md)：
  干净安装、插件组合、本地 Worker 启动和真实 Run 闭环复验 PASS，仅放行 M7.2。
- [R5-M7.2 通用独立 Codex 闭环复审](reviews/R5_M7_2_GENERIC_CODEX_EXEC_CLOSURE_INDEPENDENT_REVIEW.zh-CN.md)：
  不同独立 `codex exec` 调用、精确 Worker 工具、原子收据、Root 状态与封存 Artifact 交叉
  复核 PASS；仅放行 TCAD 作者→领域调试→独立 Deck 审查子链。
- [R5-M7.2 trusted-local 启动边界复审](reviews/R5_M7_2_TRUSTED_LOCAL_GUARD_INDEPENDENT_REREVIEW.zh-CN.md)：
  TCAD 作者越界失败与 WSL OOM 后，以官方 Hook 契约、sticky 提交门、严格 receipt v4 和 4 GiB
  进程树聚合熔断完成返工；独立复审 PASS，只放行全新根上的单 Worker 串行调试运行。
- [R5-M7.2 软恢复独立终审](reviews/R5_M7_2_SOFT_RECOVERY_INDEPENDENT_FINAL_REVIEW.zh-CN.md)：
  独立复算恢复草稿/Schema 的真实使用、领域工具重验、零格式拒绝和恢复树总次数上限，PASS、阻断 0。
- [R5-M7.3 科学—控制边界独立审查](reviews/R5_M7_3_SCIENCE_CONTROL_BOUNDARY_INDEPENDENT_REVIEW.zh-CN.md)：
  复核未知外部提交的权威查回、恶意来源不扩权和输出封存边界，PASS、阻断 0。
- [R5-M7.4 物理报告返工独立复审](reviews/R5_M7_4_FINAL_PHYSICAL_REPORT_INDEPENDENT_REREVIEW.zh-CN.md)：
  关闭首审四项计量/口径错误，独立复算默认目录、生产树和 33 项状态，PASS、阻断 0。
- [R5-M7.5 正确性独立终审](reviews/R5_M7_5_CORRECTNESS_INDEPENDENT_FINAL_REVIEW.zh-CN.md) 与
  [简化目标独立终审](reviews/R5_M7_5_SIMPLIFICATION_INDEPENDENT_FINAL_REVIEW.zh-CN.md)：
  两者均为 PASS、阻断 0；共同授权关闭 M7.5、M7 与 R5-M，不扩大强隔离、真实远端或科学通用性主张。

- [R5-L 第二轮独立架构审查](reviews/R5_L_MINIMAL_DEFAULT_RUNTIME_INDEPENDENT_REVIEW_ROUND2.zh-CN.md)：
  关闭唯一 Run 权威、递归 current、恢复草稿、TCAD 工具上下文、安全和加固防腐六类阻断；只证明
  计划可实施，不证明代码已迁移。
- [R5-S S1 独立实现审查](reviews/R5_S1_PRODUCTION_BOUNDARY_INDEPENDENT_REVIEW.zh-CN.md)：
  216→208生产来源差异、安装/发布隔离和独立回归通过，只授权 S2。
- [R5-S S2 第三轮设计审查](reviews/R5_S2_PROTOCOL_DESIGN_INDEPENDENT_REVIEW_ROUND3.zh-CN.md)：
  两轮打回后证明旧可靠控制器内的大文件传输、生命周期投影、跨 daemon 恢复和 checkpoint 边界
  可以闭合；该结论不再授权其成为默认运行主干。

## 历史决策语料

- `R0_*`—`R5_*`：8765基线、OperationSpec 编译、统一调用、插件迁移和各阶段实施记录；
- `SCIENTIFIC_*`、`TCAD_*`、`CURVE_*`、`WORKER_*`：8765时期的科学资格、TCAD、曲线和 Worker
  专项整改依据；
- `reviews/`：各候选在当时字节和测试边界下的独立审查，后续版本不得继承旧 verdict；
- `general-ai-scientist/` 与 `archive/`（若存在）：已停止或被最小架构取代的方案语料。

历史文件继续原位保存，可按文件名或正文检索。它们不进入精简源发布包，也不得仅因被保留就恢复
旧注册表、固定科研流程、第二 current、兼容入口或过重控制规则。

## 维护规则

1. 新阶段只在当前执行链中保留一个总计划、一个实施记录、一个局部方案和一个当前通过门；
2. 阶段通过必须同时有自动化证据和未参与实现的独立审查；
3. 新审查只授权其明确写出的下一阶段，修订对象不得继承旧审查结论；
4. 计划描述设计和施工，架构事实以当前代码、架构文档和33项约束为准；
5. 不为整理文档增加运行时 Registry、版本状态、兼容路由或发布时动态发现。
