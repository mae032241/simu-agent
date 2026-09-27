# R4-D-B 核心审批与科学资格实现第二轮独立复审

## 结论

**打回。**

首轮报告的四个直接阻塞项已经闭合：审批输入不再隐藏，编译器拒绝空 provider，RFC 6901 解析已严格化，审批合同的静态界限与请求模型一致；三个科学审批 Operation、初次文本提取和 typed intake revision 的真实正向链路也已落地。可是当前生产链仍有两处可复现的语义矛盾，并且计划明确要求的一组跨边界完成门仍只由人工拼装的 projector 快照覆盖。因此本轮不允许进入执行审批身份阶段。

## 审查范围与方法

只读审查了以下边界：

- `OperationSpec`、目录编译、provider 依赖及 consumer digest；
- approval invoke、请求/决定存储、严格 JSON Pointer 创建与历史重放；
- Root preflight、readiness 和通用 `scientific_foundation` 入口；
- 通用科学插件的三个 projector、真实提取/修订链路、参数 legacy bridge；
- producer family 的普通 transform、递归边界和 figure 完整性反例；
- 已安装目录和清洁发布目录。

独立复跑结果为：聚焦五文件组 `54 passed`，`tests/operations` 为 `198 passed`，全仓为 `232 passed`，`git diff --check` 通过。清洁发布目录的清单校验、核心模块编译/导入以及目录编译也通过；发布源码中的关键实现与当前工作树一致。基线没有 `scripts/validate_architecture_constraints.py`，本报告未宣称执行该脚本。

## 已确认闭合的首轮问题

1. **全部输入可见且有静态界限。** approval Operation 的 subject ports 必须精确等于全部输入端口；public、无输出、无 Worker authority、同源 projector 等编译门均存在。问题、选项、标签、说明、决定集合的限制也已与请求模型对齐。
2. **权威 preflight 已 provider-aware。** 编译器拒绝带审批 cohort 却没有 provider 的输入；provider 身份和合同摘要进入 consumer digest；跨插件依赖、版本、public approval 类型和资格环均由目录编译失败关闭。Root 候选级 readiness 与 invoke preflight 都调用 `are_subjects_approved_by_provider`。
3. **严格 RFC 6901 已覆盖创建与重放。** 非法 `~` 转义、数组前导零、越界及不存在路径均走同一严格解析路径。
4. **三个真实科学 provider 已注册。** `science.evidence.qualify.v1`、`science.parameters.qualify.pass.v1` 和 `science.parameters.qualify.exception.v1` 均是同一 compiled catalog 中的 public approval Operation；通用 `approval_request_create(kind="scientific_foundation")` 已拒绝。
5. **证据修订主链成立。** 测试真实经过 Task/Worker 文件生命周期、初次提取、独立 audit、split、资格审批和下游消费；typed intake revision 真实经过 patch、确定性 apply、diff、未变证据收据、新 audit、新 split 和重新资格化，缺 diff 失败关闭。
6. **没有新增运行状态机或第二注册表。** approval 仍复用既有 ApprovalService、Artifact、SchedulerBinding 与 HumanDecision；projector 和 provider edge 都来自唯一 Operation 目录。

## 阻塞项一：对象级 readiness 仍把未审批基础标为全局 qualified

这是当前最直接的跨边界不一致。

`scientific_readiness` 对每个科学 Artifact 默认赋值 `qualification="qualified"`，只检查 provisional 标签、运行失败和 Worker handoff；它没有任何 provider-bound 审批事实。随后只要存在一个未经审批的 `scientific_foundation`，该 kind 就进入 `effective_kinds`，`approved_scientific_foundation` 也会从 unresolved 中消失（`mcp_root.py:657-690,838-842`）。

候选行动一侧是正确的：`_approval_cohorts_ready` 使用候选 Operation 冻结的 provider identities 调用唯一 provider-aware 查询（`mcp_root.py:935-1015`）。所以同一个真实状态会同时报告：对象已经 `qualified`、不存在待解决的 approved foundation，但需要它的候选 Operation 又不可用。独立构造一个合法但没有任何审批决定的 foundation 即可复现这一矛盾。

这违反计划 7.2 的明确约束：对象库存不能把某种结构存在升级为全局 qualified；readiness 与 preflight 必须共享 provider-bound 事实。虽然 mutation gate 仍失败关闭，但该投影会误导调度 Agent，因此不是仅有措辞问题。

同一旧权威还以未使用公共方法的形式残留：`ApprovalService.is_subject_approved` 与 `are_subjects_approved` 仍按全局 kind/option 判定，不验证 compiled provider identity（`approvals.py:311-407`）。全仓搜索只有定义、没有调用，所以它们目前是**休眠的旧资格权威**，不是当前可达绕过；但保留它们与“删除 foundation 单对象旧资格语义”的冻结决定相冲突，也给后续调用者留下第二条错误入口。

最小修复：

1. 对象库存只报告结构/producer 状态，不能在没有候选 provider 上下文时声称“已审批 qualified”；未经 provider-bound 决定的 foundation 必须保留为待人工资格或中性结构状态，且 `approved_scientific_foundation` 不能提前消失。
2. 候选行动继续使用现有 `_approval_cohorts_ready`，不要新增全局 provider allowlist、资格缓存或第二注册表。
3. 删除两个零调用的 provider-less 查询，只保留 `are_subjects_approved_by_provider` 作为科学资格查询；历史审计读取不受影响。
4. 增加真实 readiness 回归：未审批 foundation、provider A 已审批/候选只接受 B、精确 provider 已审批三种状态，断言对象描述、unresolved、available actions 与 invoke preflight 一致。

## 阻塞项二：metadata-only 参数来源被生产 finalization 提前拒绝

参数 projector 已正确实现 `observed_source_keys.issubset(catalog_source_keys)`（`general_science_plugin.py:1019-1026`），因此未被参数 observation 引用的 catalog 条目可以作为 metadata-only 来源，并由 audit 覆盖。

但真实 legacy device-parameter bridge 在形成可供 projector 使用的冻结输出族之前，仍会进入 `TaskService._validate_device_parameter_evidence_bundle`（`tasks.py:3053-3059`）。这里要求 `observed_keys == set(catalog_by_key)`，否则直接拒绝 finalization（`tasks.py:3139-3149`）。因此一个完全符合新合同的 metadata-only catalog source 无法穿过生产 Task 生命周期，projector 单元测试的成功并不能证明生产路径可达。

这不是可校准未知量，而是同一科学对象在上游生产门和下游审批门使用了相反的集合语义。计划 7.3 明确要求未观察 catalog 项可以是 metadata-only，当前实现与冻结设计及 7.6 的“已保留正确语义”陈述不一致。

最小修复：

1. 将 finalization 的来源关系改为 observation keys 是 catalog keys 的子集；仍必须拒绝 observation 引用未知来源。
2. catalog 中每个 metadata-only source 仍须具有完整冻结来源和 lineage，并被参数 audit 覆盖；它不得贡献参数值、coverage 或独立来源计数。
3. 审核 `tasks.py:3165` 起的逐 catalog 校验，确保 metadata-only source 在 foundation/evidence-source 映射中的关系被显式验证并以领域错误失败关闭，不能因字典直接索引产生非合同异常。
4. 新增一个真实 bridge Task 的 validate/finalize → split/coverage/audit → pass/exception approval invoke 测试，而不是只调用人工构造的 `ApprovalProjectorContext`。

## 阻塞项三：计划要求的跨边界完成门尚未由真实族证明

当前四个 figure 缺项反例是在测试中人工构造 `ApprovalProjectorContext` 和 `ProducerOutputFamily`，再直接调用 projector（`test_r4_approval_operation.py:927-1147`）。它没有从真实 figure Worker bundle 经 Task collection/validation/evidence-source 映射、Root family resolver 和 `operation_invoke` 形成快照。计划 7.5 明确要求“真实 figure bundle”的四个独立反例（计划正文 `649-656`），所以当前测试只能证明 projector 对理想快照失败关闭，不能证明控制层不会错误构造或漏构造快照。

同样，普通 transform 走了真实 invoke，但递归/环负例只是直接调用私有 resolver 并手工传入 `depth=8` 或 `visited`（`test_r4_approval_operation.py:390-428`）；它没有证明一个真实 typed revision lineage 到达该边界时 Root 会拒绝。代码分支本身看起来失败关闭，但尚未满足冻结完成门的跨边界证据标准。

最小修复：

1. 至少建立一个真实 figure Task collection family，经 Root `operation_invoke` 成功创建资格请求；随后分别在 producer lineage/绑定层制造四类精确漏项并断言 Root 拒绝。已有 projector 级四参数测试可以保留为快速单元测试。
2. 用真实 typed revision lineage 覆盖递归环或超过八层二者之一；无需同时构造二者，也无需增加新的 resolver 或状态。

## 简化与目标一致性判断

主体方向仍符合轻控制面、最小授权、文件通信、通专分离和“everything is operation”：三个 projector 属于通用科学插件，控制层只提供不可变输入快照、合同编译和审批生命周期；没有出现新的审批 DSL、领域路由器或资格状态机。

本轮要求删除两个休眠旧查询、修正已有 readiness 投影和 legacy finalization、补足真实跨边界测试，都是**收缩现有表面并统一既有合同**，不需要增加实体、注册表或专用控制流。完成上述最小返工后，才应复跑同一聚焦/全仓/清洁发布检查并申请第三轮独立复审。
