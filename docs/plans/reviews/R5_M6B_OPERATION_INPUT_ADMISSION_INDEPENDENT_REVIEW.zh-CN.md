# R5-M6B 操作级输入准入合同独立审查

日期：2026-09-01  
审查者：未参与实现的普通代码独立审查者  
结论：**FAIL**

## 1. 阶段结论

R5-M6B 当前不能通过。`InputPortSpec` 上四个重复字段已经删除，新的
`InputAdmissionSpec`、编译提供者身份、Root 的统一消费路径以及
`member_ports`/`approval_subject_ports` 的区分本身均正确；但生产路径仍有第二套
all-or-none 输入准入事实，而且它在 Root 的操作级合同之前执行。实施证据所称“每个 Operation
只有一个准入值”“不再重聚合合同”尚未成立。

本结论不放行 M6-C、M6-D 或 M7。修复只允许停留在 M6-B，并需重新独立审查。

## 2. 阻断问题

### B1：生产 guard 仍拥有并执行第二套输入成员集合，Scheduler 看不到完整准入合同

计划要求把 cohort 事实收敛到 Operation 的一个不可变准入值，并要求编译器与 Root 消费同一
编译结果（`R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md:365-376`）；实施证据进一步声明
`member_ports` 是 all-or-none 的唯一表达、领域插件只保留一个值，Root 不再重建合同
（实施证据 `:16-26`、`:39-52`）。当前生产代码与该声明不一致：

1. `science.experiment.materialize.v1` 的 Operation 声明使用 `_FOUNDATION_ADMISSION`，其
   `member_ports` 只有 `scientific_foundation`（
   `general_science_experiment_operations.py:250-317`）。但同一 Operation 的
   `experiment_lineage` guard 又以 `allowed_port_sets` 单独规定：要么只有必需的
   `experiment_design_intent`，要么必须同时出现 foundation、objective、hypothesis、critic 四项
   可选上下文（`general_science_experiment_components.py:219-244`）。这就是未进入
   `InputAdmissionSpec` 的第二份 all-or-none 准入合同。
2. 可执行探针读取 Scheduler projection，得到的 `input_admission.member_ports` 仅为
   `('scientific_foundation',)`；对“intent + objective”这一部分上下文绑定，实际 preflight 却返回
   `guard_rejected / experiment_lineage`。因此公开 Operation 级准入投影没有表达实际 blocker。
3. `science.experiment.revise.v1` 已声明四端口 `_REVISION_SCIENCE_ADMISSION`
   （`general_science_experiment_operations.py:20-32,205-213`），但
   `experiment_science_cohort` 的 parentage 对仍会在部分集合上先行拒绝
   （`general_science_experiment_components.py:208-217`）。通用 `preflight_operation` 在
   `invoke.py:211-215` 先运行 guard；Root 直到
   `mcp_root_operation_routes.py:934-962` 才执行 `_validate_compiled_input_admission`。所以部分 cohort
   的有效运行权威仍是 guard，而不是新的 Operation 级合同。
4. TCAD 也保留与 `DECK_PARAMETER_ADMISSION.member_ports` 完全相同的
   `_PARAMETER_COHORT_PORTS`（`tcad_artifact/plugin.py:127-166` 对比 `:383-405`）。guard 每次调用仍
   重新构造 `present` 集合并用这份独立元组决定何时执行 lineage 检查。编译器只验证
   `InputAdmissionSpec` 自身，不校验该 guard 元组与 `member_ports` 同步；两者漂移可正常编译，且
   Scheduler 只投影前者。

影响：同一输入组合的成员事实仍有两个维护点；声明与 guard 漂移时，启动编译不能失败关闭；调度器
看到的 Operation 级准入合同不足以解释实际拒绝；运行时仍重聚合成员集合。这直接违反 M6-B 的单一
事实源目标，也不满足 AUTH-003 的同一编译合同和模型可见合同要求。虽然当前 preflight 与 invoke
都经过 `_prepare_operation_call`，因而对同一绑定会得到相同结论，但这不能弥补准入权威重复。

最小修复边界：让 all-or-none 只由 `InputAdmissionSpec.member_ports` 表达；guard 只检查完整绑定上的
科学 parentage，不再拥有 `allowed_port_sets` 或重复 cohort 元组，并保证中央成员检查先于需要完整
cohort 的 lineage guard。`science.experiment.materialize.v1` 的四项可选上下文也必须进入公开的
Operation 级成员合同。不得为此增加第二个准入对象、注册表、状态或领域特判。

## 3. 已确认正确的部分

- 当前 ABI 为 10，准入声明与冻结 provider identity 均进入 Operation digest；ABI9 兼容读取只出现
  在 `tests/operations/m3_transform_equivalence_runner.py` 的冻结 M2 oracle 分支，生产编译器和 Root
  没有历史双路径。
- 默认 core/general/curve/TCAD 目录实测为 42 个 Operation，其中恰有 12 个
  `input_admission` 消费者；未发现 M6-B 新增数据库表、注册表、服务或运行状态。
- `InputPortSpec` 已不再包含 cohort/approval 四字段；Scheduler 端口视图也没有复制这些字段。
- 编译器覆盖端口存在、重复、subject/member 子集、单值成员、provider 安装与依赖、provider kind、
  接受选项和嵌套资格 provider；声明或 provider 身份变化进入摘要。
- Root 的 `operation_preflight` 与 `operation_invoke` 均唯一调用 `_prepare_operation_call`
  （`mcp_root_operation_routes.py:125-132`），没有第二个 Root 调用入口。
- Root 只把 `approval_subject_ports` 对应 refs 交给 ApprovalService
  （`mcp_root_operation_routes.py:1004-1044`）。ApprovalService 要求这些 refs 全部包含在同一个、身份
  精确匹配的 provider 决定中，同时允许该完整审批请求含有额外 family subjects；这正确实现了
  subject 子集语义。TCAD 的 `parameter_uncertainty` 是 member 但不是 subject。
- 独立的真实服务探针分别以 `science.parameters.qualify.pass.v1 / approve` 和
  `science.parameters.qualify.exception.v1 / approve_with_exception` 建立决定，两条 TCAD Deck Root
  preflight 均返回 admissible；provider 决定含额外 subject 时仍只要求声明子集，符合设计。
- 无 `input_admission` 的普通 Operation 在 `_validate_compiled_input_admission` 立即返回，不查询
  ApprovalService，也不创建准入状态。

## 4. 测试与检查

所有 pytest 命令串行运行，先执行 `ulimit -v 7340032`（7 GiB），禁用 bytecode 与 pytest cache，
临时目录位于 `/tmp`。

- M6-B spec/catalog/Root/投影/人工策略聚焦集：`61 passed in 37.05s`。
- installed entry point、参数包、通用 Transform、Local TCAD、M3 adapter 删除、冻结 M2 oracle、
  M6-B 与 ABI 边界集：`42 passed in 75.02s`。
- 33 项权威矩阵结构：`1 passed in 0.05s`。
- TCAD pass/exception 真实 ApprovalService→Root 探针：两条均 admissible。
- 隐藏准入负探针：Scheduler 仅报告 foundation member，但部分实验上下文由
  `experiment_lineage` 返回 `guard_rejected`，稳定复现 B1。
- `git diff --check`：通过。

技能建议的 `scripts/validate_architecture_constraints.py` 在当前仓库不存在；因此运行了仓库实际拥有的
`tests/operations/test_architecture_constraint_matrix.py`。未运行全量套件：跨边界聚焦集和冻结 oracle
均已通过，但 B1 已由生产代码和目标入口探针确定复现，全量绿色也不能消除该语义阻断。

## 5. 33 项约束与阶段门

33 项权威文档的 assessment 未被本审查擅自晋级。M6-B 相关结论如下：

- AUTH-001、HIL-001/HIL-002：Approval/HumanDecision 仍是唯一决定权威，资格与执行授权未合并；无
  新状态权威。
- TOP-002：readiness 与 invoke 共享同一 `_prepare_operation_call`，当前绑定结论一致。
- AUTH-003、ROLE-002：阻断。实际 all-or-none 合同没有完全收敛到 Operation 级
  `input_admission`，guard 仍持有不可由编译器互证的第二份成员事实。
- PLG-001/PLG-002：未见 core 按 TCAD/plugin 名分支；问题位于插件自身重复合同，不是核心领域泄漏。
- RES-002：本次验证保持 7 GiB 虚拟内存上限。
- SEC-002 继续保持 `known_issue`，本阶段没有提供改变其状态的证据。

因此 R5-M6B 完成门未满足。**结论为 FAIL；M6-C、M6-D、M7 均不放行。**
