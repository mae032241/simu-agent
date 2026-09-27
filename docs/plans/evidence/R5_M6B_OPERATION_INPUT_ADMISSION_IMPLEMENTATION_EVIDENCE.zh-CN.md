# R5-M6B 操作级输入准入合同实施证据

状态：首次独立审查打回后的单一权威返工已通过全新独立复审；仅放行 M6-C

## 1. 本阶段回答的问题

旧实现把同一资格规则复制到多个 `InputPortSpec`：每个端口分别声明 cohort、审批种类、接受决定和
提供者 Operation。编译器先把这些字段重新聚合，Root 在每次调用时又聚合一遍。这形成三个事实来源，
也迫使领域插件在每个端口重复同一合同。

M6-B 只折叠这组重复声明，不新增资格服务、状态机、数据库表或注册表，也不改变 Approval 本身的
权威。

## 2. 最小实现

新增一个无状态值对象 `InputAdmissionSpec`。每个 Operation 最多有一个可选的
`input_admission`，只表达：

- `cohort_id`：稳定诊断标识；
- `member_ports`：只要任一出现就必须全部出现的输入端口；
- `approval_subject_ports`：其中必须共享同一资格决定的精确子集；
- `approval_kind`、`accepted_options`、`accepted_provider_operations`：可选资格合同。

`member_ports` 与 `approval_subject_ports` 被明确区分。例如 TCAD Deck 的
`parameter_uncertainty` 是 all-or-none 成员，但不是资格审批 subject；实验修订的四个可选科学上下文
必须同时提供，但只有 `scientific_foundation` 是资格 subject。

相应删除 `InputPortSpec` 的四个重复字段：

- `cohort_id`；
- `approval_kind`；
- `accepted_approval_options`；
- `accepted_approval_operations`。

启动期编译器一次性验证端口存在、无重复、subject 是 member 子集、member 为单值端口、提供者依赖、
审批种类、可接受决定以及提供者不得再次依赖资格。编译结果把提供者冻结为带 Operation 摘要和审批合同
摘要的身份元组；该身份与准入声明共同进入 Operation 摘要。ABI 从 9 提升为 10。

通用 `preflight_operation` 在运行任何领域 guard 前，直接按编译 Operation 的 `member_ports`
执行唯一的 all-or-none 检查。Root 不再扫描端口、重复检查成员或重建合同，只消费同一
`compiled.spec.input_admission` 的审批部分和 `compiled.approval_providers`。没有声明准入的普通探索
Operation 不发生成员或资格状态成本。

## 3. 已迁移的真实场景

默认四插件目录共 42 个 Operation，其中 12 个声明操作级准入：

- 6 个单 foundation 通用科学消费者；
- 实验修订与实验物化复用同一个四成员可选科学上下文合同；
- 1 个 TCAD 参数不确定性投影；
- 3 个 TCAD Deck 作者及 1 个独立 Deck 审查者。

相同 foundation 合同复用一个不可变值；实验修订与物化复用一个四成员值；参数投影和 Deck 参数组
各自只有一个值。领域插件不再逐端口复制资格提供者和决定列表。

## 4. 失败关闭与行为证据

新增测试覆盖：

- 未知 member、非 member subject、非单值 member；
- 未安装提供者、提供者不支持的决定、递归资格提供者；
- 准入值变化必然改变 Operation 摘要；
- Scheduler 投影只在 Operation 级暴露一份合同，端口视图不再重复字段；
- Root 对部分 cohort 拒绝，对缺失资格拒绝；
- Root 传给 ApprovalService 的 subject 精确等于声明子集，TCAD 的 all-or-none 非 subject 成员不会
  被错误加入审批；
- 部分成员在任何领域 guard 前由通用预检返回 `input_cohort_incomplete`；guard 只检查完整绑定的科学
  parentage，不再持有 `allowed_port_sets` 或重复 cohort 元组。

冻结 M2 源码等价测试仍需同时运行旧 ABI9 与当前 ABI10。测试运行器只在检测到旧
`OperationSpec` 不含 `input_admission` 时读取旧端口字段；该兼容分支只存在于离线 oracle 测试，
生产编译器和 Root 没有历史双路径。

## 5. 已执行验证

```text
pytest -q \
  tests/operations/test_spec.py \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_l3_review_and_human_policy.py
61 passed in 37.05s

首次审查返工后：

pytest -q \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_l3_review_and_human_policy.py
59 passed in 2.13s

pytest -q \
  tests/operations/test_catalog_installed_entrypoint.py \
  tests/operations/test_m2_parameter_package.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_m3_transform_adapter_removal.py \
  tests/operations/test_m3_transform_equivalence.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_spec.py \
  tests/operations/test_architecture_constraint_matrix.py
43 passed in 74.82s
```

同时通过 Python 语法编译与 `git diff --check`。所有测试串行执行，并将进程虚拟内存限制为 7 GiB。

## 6. 明确保留的边界

- ApprovalRequest、HumanDecision 和提供者身份校验仍是科学资格的唯一权威，本阶段没有简化其决定
  语义；
- Error reason 继续保留 `input_cohort_*` 名称，避免把内部重构伪装成新的运行行为；
- 每个 Operation 只支持一个准入值，这是当前 12 个真实消费者所需的最小模型；没有为未来多组场景
  预先增加列表、求解器或第二注册表；
- M6-C、M6-D 尚未执行，M7 未放行。

## 7. 首次独立审查与返工

首次独立审查结论为 FAIL。审查者通过 Scheduler 投影与真实 preflight 漂移探针确认：

1. `science.experiment.materialize.v1` 公开合同只声明 foundation，但
   `experiment_lineage.allowed_port_sets` 另藏四上下文 all-or-none；
2. 实验修订的部分成员会先被 parentage guard 拒绝，成员权威没有先于 guard；
3. TCAD guard 的 `_PARAMETER_COHORT_PORTS` 与 Deck `member_ports` 完全重复，且编译器无法互证。

返工没有添加机制，而是删除第二权威：

- all-or-none 检查移到通用 `preflight_operation`，并保证先于所有 guard；
- Root 删除重复成员检查，只保留需要 ApprovalService 的资格查询；
- materialize 改为公开的四成员合同，与 experiment revise 复用同一个不可变值；
- 删除 `RequiredParentage.allowed_port_sets` 和 TCAD `_PARAMETER_COHORT_PORTS`；实验/TCAD guard 只在
  完整绑定上检查具体父链。

首次报告见
`reviews/R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REVIEW.zh-CN.md`。该报告明确未放行 M6-C；
全新复审见
`reviews/R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REREVIEW.zh-CN.md`，结论 PASS；仅放行
M6-C，不放行 M6-D 或 M7。
