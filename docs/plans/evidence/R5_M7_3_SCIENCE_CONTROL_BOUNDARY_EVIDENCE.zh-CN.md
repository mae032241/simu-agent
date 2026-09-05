# R5-M M7.3 科学内容与控制权限边界证据

日期：2026-09-03  
状态：独立复审 PASS、阻断 0；M7.3 已完成  
适用计划：`R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 第 12.3 节

## 1. 本阶段要证明什么

M7.3 不增加一套安全状态机。它只验证现有最小运行主干仍守住以下硬边界：输入内容不能改变编译
权限；控制层不补科学参数、不替 Agent 形成诊断；current、独立审查和 revision 身份不可混用；
外部提交结果未知时只能权威查回；结果封存拒绝路径逃逸和明显的发布污染。

默认 Local 仍是可信本地软隔离。下述证据不主张操作系统层阻止 Agent 读取宿主文件或访问网络，
`SEC-002` 继续是已知问题。

## 2. 独立预审发现的真实缺口

独立边界预审指出：原调用顺序为 `adapter.submit()` 后再写本地 `record_submission()`。若外部已接受
但响应丢失，或本地登记失败，Execution 仍停在 `authorized`，重试可能再次产生副作用。TCAD 控制端
虽然碰巧按任务摘要幂等，但通用 `ExecutionAdapter` 没有强制这一事实，因此原实现不满足
`EFF-002`。

本次没有增加 `submission_unknown` 状态、后台恢复器、数据库表或 Root 工具，而是收紧原有适配器
边界：

1. `submit` 的合同明确要求按同一冻结描述符幂等；
2. 所有 Effect 适配器必须实现只读 `lookup_submission`，启动时缺失即拒绝；
3. `ExecutionBridge.start` 每次先查回；只有权威返回不存在才提交，查询错误则在副作用前失败；
4. 查到既有任务后只登记其外部编号，不再次提交；
5. `record_submission` 对同一外部编号允许幂等重放，对不同编号仍失败关闭。

TCAD 本地 socket、命令/SSH transport 和 Python 3.6 远端 runner 均实现同一查回合同。socket 服务复用
已有 `submissions.job_sha256` 唯一键，远端 runner 复用已有由任务摘要导出的稳定运行目录；没有新增
领域状态。

## 3. 计划条目与可执行证据

| 要求 | 实现边界 | 主要测试 |
|---|---|---|
| 不可信论文/网页不能扩大工具、网络、审批或执行权限 | assignment 与 Codex profile 只投影启动时编译的 Operation；来源正文只是冻结输入字节 | `test_untrusted_input_content_cannot_expand_compiled_run_authority`、目录权限负例 |
| 缺失参数不由控制层补值 | preflight 严格验证端口、Schema 和参数；参数不确定性由科学记录保留 | `test_preflight_rejects_unknown_ports_schema_parameters_and_claim_gates`、`test_parameter_uncertainty_projection_blocks_unbounded_and_preserves_bounded_tuning` |
| Metric 不生成诊断或结论 | 确定性曲线分析只产生可复算分析包；诊断由单独 Agent Operation 输出 | `test_curve_analysis_transform_and_single_file_agent_complete_real_run`、篡改负例 |
| stale current 拒绝 | invoke 冻结 current，提交时再以 CAS 检查精确 head | `test_recursive_current_uses_producer_receipts_and_commit_rechecks_head` |
| 混合 cohort 拒绝 | 实验设计只接受同一科学基础族的精确父链 | `test_experiment_design_rejects_mixed_foundation_cohorts` |
| 错误 reviewer、旧 revision verdict 拒绝 | review edge 编译 exact reviewer/port/codec；revision 创建新对象且不继承旧 verdict | `test_direct_revision_still_rejects_a_different_reviewer_contract`、`test_review_gate_requires_a_passing_review_of_the_exact_revision` |
| 提交未知不盲目重发 | Effect 适配器统一执行权威查回后再幂等提交 | `test_unknown_submission_is_recovered_by_lookup_without_resubmit` 两个故障窗口、`test_unavailable_submission_lookup_fails_before_external_submit`、缺 lookup 启动拒绝 |
| 输出封存拒绝路径与内容污染 | Local 输出只接受工作区内普通文件，并执行已有秘密、宿主路径、媒体/二进制发布检查 | `test_tool_projection_identity_independent_path_and_publication_gate`、TCAD 三个符号链接负例 |

恶意来源用例实际把“启用 web、审批、执行和 TCAD 调试工具”的文字放进绑定 CSV。Worker 仍只获得
该 Operation 的工具投影，生成的 profile 仍为 `web_search = "disabled"`，Approval 和 Execution
列表保持为空。这只证明内容不能改变框架编译权限，不把 Local 原生能力描述成技术沙箱。

## 4. 故障窗口状态表

| 情形 | 查回结果 | 是否调用 submit | 本地结果 |
|---|---|---:|---|
| 首次提交，权威确认不存在 | `None` | 是，按冻结描述符幂等 | 登记返回的外部编号 |
| 外部接受后响应丢失 | 重启后返回既有编号 | 否 | 从 `authorized` 登记为 `submitted` |
| 外部返回后本地登记失败 | 重启后返回既有编号 | 否 | 从 `authorized` 登记为 `submitted` |
| 查回暂不可用 | 抛错 | 否 | 保持 `authorized`，等待显式重试 |
| 已登记同一外部编号 | 不要求新副作用 | 否 | `record_submission` 幂等返回 |
| 已登记但外部编号不同 | 不适用 | 否 | 状态冲突，失败关闭 |

两个故障窗口均断言适配器实际提交计数始终为 1；查回不可用的用例断言提交计数为 0。

## 5. 验证结果

执行命令：

```text
PYTHONPATH=src python -m pytest -q -p no:cacheprovider \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_invoke_preflight.py \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_m2_curve_analysis_boundary.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_l4_local_tcad.py
```

结果：`82 passed in 16.59s`；峰值常驻内存 `120640 KiB`，无 swap。此前适配器/运行时聚焦组合为
`40 passed in 49.70s`，峰值常驻内存 `124140 KiB`。`compileall` 与 `git diff --check` 通过。

## 6. 复杂度与范围结论

- 新增的是一个适配器只读方法和一条通用调用顺序，没有新增控制实体、运行状态、表、注册表或
  调度分支；
- 核心不知道 TCAD 名称、任务格式或远端协议；领域插件只负责把稳定提交摘要映射到已有领域任务；
- current、review、approval、Execution 和 Artifact 的原权威没有改变；
- Local 软隔离没有被测试数量包装成强隔离资格，`SEC-002` 保持 `known_issue`；
- 新的独立复审已运行 82 项聚焦回归并明确 PASS、阻断 0；M7.3 已关闭并放行 M7.4。
