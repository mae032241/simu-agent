# R5 E3 审批投影等价独立跨边界审查

日期：2026-09-05

结论：**PASS**  
阻断项：**0**  
是否放行 E4：**是，仅放行计划既定的 E4 部署组合与真实入口验证。**

## 1. 审查边界与方法

本次审查者未参与 E3 实现。审查仅覆盖活动计划
`R5_NEXT_ITERATION_LIVE_DEFECTS.zh-CN.md` 的 E3、实施证据
`R5_PRE_E2E_E3_APPROVAL_PROJECTION_EQUIVALENCE.zh-CN.md`，以及下列精确相关实现和测试：

- `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py`
- `src/scidiscovery/operations/invoke.py`
- `src/scidiscovery/general_science_control_operations.py`
- `src/scidiscovery/general_science_components.py`
- `tests/operations/test_m2_parameter_package.py`
- `tests/operations/test_m5_figure_review_closure.py`
- 与审批身份、人审边界、输入准入相关的既有聚焦回归

当前工作树包含大量早于 E3 的未提交与未跟踪改动，因此无法把 `HEAD` 差异误称为仅含 E3 的干净
提交差异。本审查以计划冻结的 E3 修改边界、实现证据和上述精确路径为对象；未把全仓生产文件数
159 的旧阈值失败归因于 E3，也未扩展审查到 UI、部署、全仓裁剪或 E4 实现。

## 2. 关键结论

### 2.1 preflight 与 invoke 共用同一审批投影路径

`operation_preflight` 在完成通用 Operation 绑定与准入后，对 approval executor 调用
`_prepare_approval_projection(bound)`。`_invoke_approval_operation` 在任何 Approval 创建之前再次调用
同一函数，并直接使用该函数返回的同一类型 `ReviewDocument` 与精确 subject snapshots。

在 Operation 调用路由内，projector 组件查找和执行只剩这一处；没有为 preflight 复制 projector
规则，也没有新建第二个审批规则表。外部执行授权仍位于原有独立执行路由，未被本次改动混入科学
资格审批。

### 2.2 invoke 保留写前复核，preflight 保持逻辑只读

调用顺序是：重新解析精确绑定、重新执行已有输入准入、重新读取不可变 Artifact、恢复 producer
family、重新运行 projector，然后才计算 Approval 指纹、选择创建目标并调用
`approvals.create_request`。因此 preflight 的成功不替代 invoke 的写前复核。

共享准备函数只使用 Artifact `read/catalog/get_by_id`、binding `list`、已完成 Run 查询和编译目录
读取；本轮没有把 Approval 创建、绑定、决定或后果写入该函数。负例还以 Approval 总数前后不变验证
了 preflight 与失败 invoke 的零 Approval 写入。

### 2.3 producer family 正反例覆盖了本次缺陷

实测覆盖以下失败关闭边界：

- 参数多输出家族额外加入无关冻结来源；
- 用 Schema 相同但父链不同的对象替换家族成员；
- 图证据完整冻结来源族缺少 curve table；
- 图证据冻结来源被替换；
- 把同一 split 的 `problem_frame` 错绑到 `scientific_foundation` 端口。

这些错误绑定均在 preflight 被拒绝；具有调用断言的负例在 invoke 再次被同一 projector 拒绝，且未
创建 Approval。正确的参数多输出 producer family 和正确的单主输出图 Intake（其冻结来源包含完整
图附件族）均在 preflight 通过，并在 invoke 创建 pending Approval。因此，零输出 sibling 与多输出
sibling 两种 producer 形态、以及图证据多附件来源形态均有正例覆盖。

### 2.4 审批身份、选项和后果未改变

E3 未修改 OperationSpec、ApprovalContract、projector 实现、审批服务、Schema 或 UI。invoke 仍从
同一编译 `approval_identity` 构造 `CompiledApprovalIdentity`，仍从同一合同生成选项、问题和 kind，
仍把同一投影文档纳入请求指纹。扩展的人审与审批身份回归全部通过，未发现科学资格与执行授权合并、
聊天代写决定或 revision 继承旧决定的变化。

## 3. 独立执行的验证

所有测试串行执行，并设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`；未使用并行测试。

```text
pytest -q \
  tests/operations/test_m2_parameter_package.py \
  tests/operations/test_m5_figure_review_closure.py

8 passed in 3.01s
peak RSS: 104596 KiB
```

```text
pytest -q \
  tests/operations/test_invoke_preflight.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_r4_approval_ui_renderer.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_m2_parameter_package.py \
  tests/operations/test_m5_figure_review_closure.py

43 passed in 8.26s
peak RSS: 111184 KiB
```

此外：

- `tests/operations/test_architecture_constraint_matrix.py`：`1 passed`；
- 相关 Python 文件 `py_compile`：通过；
- 精确相关路径 `git diff --check`：通过。

## 4. 架构与奥卡姆判断

本次修改直接闭合 `TOP-002` 暴露的“预检通过、调用才因 projector 失败”断裂，同时不改变
`AUTH-003` 的编译 Operation 权威、`ROLE-001/002` 的科学内容归属、`HIL-001/002` 的人工决定边界、
`PLG-001/002` 的插件边界或 `CQRS-001` 的查询纯读要求。

新增内容仅是一个私有共享准备函数及针对原缺陷的正负回归；没有新增公共实体、状态、注册表、数据库
字段、MCP、错误码或 UI 分支。该复杂度与消除两条漂移路径的收益相称，未发现针对 Fig.4 名称的核心
分支或新的隐藏写入，符合本阶段的最小修改原则。

## 5. 非阻断限制

- 当前 projector 失败仍统一表现为 `approval_projector_failed`；这是计划明确延期的诊断精细度，
  不影响同一精确绑定的 preflight/invoke 等价。
- 审批页科学信息层次仍是 `UI-001` 已知问题；E3 未宣称修复，也不能把本次 PASS 解读为 UI 验收。
- 本次是源码和测试入口审查，不代替 E4 的 clean wheel、真实安装脚本、服务与插件组合验证。
- 全仓生产文件数旧阈值失败并非 E3 新增或恶化；本阶段不据此扩大为全仓裁剪。

## 6. 放行决定

E3 的既定目标已闭合，阻断项为零。**允许进入 E4**。放行范围严格限于活动计划中已经定义的部署
组合与真实入口验证；不得借本结论提前宣称 E5 真实 Agent、人工审批或完整端到端科学实验已经通过。
