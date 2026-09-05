# R5-M6B 操作级输入准入合同独立复审

日期：2026-09-01  
复审者：未参与实现或返工的普通代码独立复审者  
结论：**PASS**

## 1. 阶段结论

首次独立审查的唯一阻断 B1 已关闭。当前生产路径中，all-or-none 成员事实只由编译
`OperationSpec.input_admission.member_ports` 表达，通用 `preflight_operation` 在任何领域 guard
之前执行该结构检查；实验与 TCAD guard 只检查完整绑定后的具体父链。Root 不再检查或重聚合成员
集合，只消费编译合同的资格 subject、provider identity 和可接受决定。

本报告只判定 R5-M6B 返工通过，不把 M6 整阶段写成完成，也不改变 33 项权威矩阵的 assessment。
**仅放行M6-C；不放行 M6-D 或 M7。**

## 2. 复审范围与判据

完整阅读并交叉核对：

- `R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 的 M6-B 要求和 M6 完成门；
- `R5_M6B_OPERATION_INPUT_ADMISSION_IMPLEMENTATION_EVIDENCE.zh-CN.md`；
- 首次 FAIL 报告 `R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REVIEW.zh-CN.md`；
- 当前 `SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 33 项权威、最小设计宪章、当前架构和比较评估；
- spec、catalog 编译、Scheduler 投影、通用 invoke/preflight、Root 路由、实验声明与 guard、TCAD
  声明与 guard、ApprovalService、M6-B 回归和冻结 M2 oracle。

仓库基线为 `baseline/8765-codex@404aeb1` 叠加大范围未提交工作树，且 M6-B 文件不是一个可由 Git
单独还原的提交 diff。因此本复审没有猜测远端 base，而是以首次 FAIL 报告记录的旧路径作为 B1
反例，以当前工作树生产代码、目标入口探针和现有冻结 oracle 判断返工。这一限制不影响 B1 当前能否
复现，但意味着本报告不是整个脏工作树的总审查。

## 3. 首次 B1 关闭证据

### 3.1 中央 all-or-none 是唯一运行权威，并先于 guard

`src/scidiscovery/operations/invoke.py:185-229` 先完成端口结构绑定，然后直接读取
`spec.input_admission.member_ports`，对非空真子集返回 `input_cohort_incomplete`，之后才调用
`_run_guards`。检查没有按 Operation、Schema 或插件名称分支。

漂移探针把 materialize、revise 和 TCAD 的实际 guard 临时替换为“调用即抛错”的 bomb guard，再
提交部分 cohort。三条路径均稳定返回中央 `input_cohort_incomplete`，没有出现 `guard_failed` 或
`guard_rejected`，证明执行顺序不是测试名称或当前 guard 偶然行为。

### 3.2 experiment materialize 公开且只接受两种结构形状

`src/scidiscovery/general_science_experiment_operations.py:20-32` 定义一个四成员不可变合同：

1. `scientific_foundation`；
2. `research_objective`；
3. `hypothesis_portfolio`；
4. `critic_review`。

`science.experiment.materialize.v1` 在同文件 `:251-317` 的四个端口均为可选，并直接绑定上述合同；
Scheduler projection 实测公开完全相同的四个 `member_ports`。目标入口探针确认：

- 纯 engineering：只绑定 `experiment_design_intent`，通过结构与 lineage；
- 部分 scientific：`intent + objective` 在 guard 前以 `input_cohort_incomplete` 拒绝；
- 完整 scientific：四上下文与 intent 全部具有精确父链时通过；
- 完整但错误父链：仍由 `experiment_lineage` 以 `guard_rejected` 拒绝。

`src/scidiscovery/general_science_experiment_components.py:91-110` 的 materialize guard 已不再拥有
`allowed_port_sets`。它只在完整 scientific 形状上验证 intent、objective、portfolio、critic 与
foundation 的精确父链；无 foundation 的 engineering 形状显式通过。

### 3.3 experiment revise 的部分组先由中央合同拒绝

`science.experiment.revise.v1` 在
`src/scidiscovery/general_science_experiment_operations.py:133-219` 复用同一个四成员合同。带必需
`prior_draft/change_request` 但只带 objective 的探针，在 bomb guard 未执行前返回
`input_cohort_incomplete / scientific_foundation`。`RequiredParentage` 当前只有父链 pairs，没有旧
`allowed_port_sets` 或第二成员集合。

### 3.4 TCAD 删除重复成员元组，guard 只检查完整绑定父链

`plugins/tcad_artifact/tcad_artifact/plugin.py:375-397` 是 Deck 参数组唯一成员声明；全仓生产源码中已
不存在 `_PARAMETER_COHORT_PORTS`。同文件 `:127-158` 的 guard 不再构造或比较 all-or-none 成员
集合，只验证 audit 覆盖的精确参数 refs、foundation 对 audit 的父链，以及 uncertainty projection
的三个精确 parents。部分 TCAD 参数组也在 bomb guard 前由中央合同拒绝。

guard 中出现的端口名称服务于父链关系，不构成第二份“允许哪些结构形状”的集合。当前声明与 guard
可以分别由结构负例和错误 lineage 负例解释，不再存在首次报告所指出、编译器不可见的第二
all-or-none。

### 3.5 Root 只查资格，不再重复成员检查

Root 在 `mcp_root_operation_routes.py:934-962` 先调用通用 `preflight_operation`，随后才进入输入资格
验证。`_validate_compiled_input_admission`（`:1004-1040`）不再计算 missing member：无 admission
立即返回；无任何 member 立即返回；结构完整后只按编译的 `approval_subject_ports`、kind、options
和 `approval_providers` 查询 ApprovalService。

`operation_preflight` 与 `operation_invoke` 仍唯一共享 `_prepare_operation_call`
（`:125-132`），因此同一精确绑定没有 readiness/invoke 双路径。

## 4. 防退化结论

- 默认 core/general/curve/TCAD 编译目录实测仍为 42 个 Operation，其中恰有 12 个
  `input_admission` 消费者。
- `InputPortSpec` 已无旧 cohort/approval 四字段，Scheduler 端口投影也不复制这些字段。
- 当前 ABI 为 10，Operation 声明与冻结 provider identities 都进入 compiled digest。
- 旧 ABI9 的 `cohort_id`、`accepted_approval_options` 读取只存在于
  `tests/operations/m3_transform_equivalence_runner.py:1085-1106` 的封存 M2 oracle 兼容分支；生产
  `src/` 和插件没有旧 ABI 双路径。
- 真实 ApprovalService→Root 探针分别用
  `science.parameters.qualify.pass.v1 / approve` 与
  `science.parameters.qualify.exception.v1 / approve_with_exception` 建立决定，两条均通过。
- 上述决定故意包含全部七个 Deck member；Root 只查询声明的前六个
  `approval_subject_ports`，证明 `parameter_uncertainty` 是 all-or-none member 但不是资格 subject，
  provider 决定允许包含额外 family subject。
- 一个无 `input_admission` 的普通 Agent Operation 经过 Root 资格函数时对 ApprovalService 为零调用；
  既有普通探索集成测试仍证明不会建立 approval 绑定或记录。
- 未发现 M6-B 新增数据库表、注册表、服务、运行状态或核心领域名称分支。

## 5. 本地验证

所有 pytest 和自定义 Python 探针均串行执行，先设置 `ulimit -v 7340032`（7 GiB）；禁用 bytecode 和
pytest cache，临时状态只写 `/tmp`。

```text
pytest -q \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_l3_review_and_human_policy.py
59 passed in 2.79s

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
43 passed in 73.73s

独立内存漂移与真实 ApprovalService 探针
PASS in 1.07s

git diff --check
git diff --no-index --check /dev/null \
  docs/plans/reviews/R5_M6B_OPERATION_INPUT_ADMISSION_INDEPENDENT_REREVIEW.zh-CN.md
PASS
```

独立探针最初两次搭建分别因直接 Python 未设置插件 `PYTHONPATH`、以及把“普通操作”误筛为当前四插件
中不存在的 `consequence=explore` 而退出；两者均在未改生产代码的情况下修正。最终成功探针使用显式
插件路径和无 admission 的普通 Agent，并覆盖本报告所列全部断言。这两个 harness 设置错误不是产品
失败，也没有被重跑伪装为首次成功。

未运行全量 pytest：M6-B 的共享 spec/catalog/preflight/Root、真实安装入口、Local TCAD、冻结旧
ABI oracle、33 项矩阵和目标漂移负例已由上述 102 项与独立探针覆盖。未运行真实科学 Agent、真实
solver 或人工浏览器决定；它们不能由本次结构合同复审外推，但不是 M6-B 完成门。

## 6. 33 项约束与阶段门

当前权威矩阵仍是 33 个唯一 id，状态保持 7 `conformant`、25 `pending_review`、1 `known_issue`；本
报告不修改或晋级 assessment。

- AUTH-003、ROLE-002：本轮受影响的 catalog、Scheduler projection、preflight、Root 资格查询和
  provider identity 现在消费同一编译 Operation 合同；首次隐藏成员权威已删除。
- TOP-002：preflight/invoke 继续共享同一 `_prepare_operation_call`，部分 cohort 负例在共同入口
  给出相同中央 reason。
- AUTH-001、HIL-001/HIL-002：Approval/HumanDecision 仍是资格决定权威，聊天没有写决定路径，资格
  与执行授权没有合并。
- PLG-001/PLG-002：中央检查领域中性；实验与 TCAD 只声明自身合同和 lineage guard，没有核心插件名
  白名单。
- RES-002：本轮验证保持 7 GiB 虚拟内存上限。
- SEC-002 保持 `known_issue`，没有被 M6-B 结构测试改写为已解决。

M6-B 自身完成门已满足；但 M6-C、M6-D 尚未实施，因此 M6 整阶段完成门仍未满足。

## 7. 非阻断观察

`mcp_root_operation_routes.py:1005` 的 docstring 仍写“all-or-none/approval contract”，而该函数当前只
承担资格部分；真正 all-or-none 已在通用 preflight。它没有形成运行权威或行为漂移，不阻断 M6-B，
可在后续触碰该函数时收窄措辞，避免读者误解 Root 仍执行成员检查。

## 8. 最终判定

首次 B1 无法在当前工作树复现，返工以删除重复权威和调整执行顺序关闭问题，没有引入替代注册表、
状态或领域特判。**R5-M6B：PASS。仅放行M6-C；M6-D、M7 不放行。**
