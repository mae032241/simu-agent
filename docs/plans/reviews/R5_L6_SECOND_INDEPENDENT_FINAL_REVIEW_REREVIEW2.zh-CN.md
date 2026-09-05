# R5-L6 第二位独立终审第三次聚焦复核

日期：2026-09-01  
审查者：第二位独立最终审查者（未参与实现）  
审查对象：当前工作树中 L0—L6 最终候选；本轮聚焦上一轮唯一阻断——活动计划与实际 `RunService`、current、reviewer 及文件工具授权边界的冲突  
结论：**PASS**

## 1. 最终裁决

本轮未发现阻断项。上一轮报告
`R5_L6_SECOND_INDEPENDENT_FINAL_REVIEW_REREVIEW.zh-CN.md` 指出的活动计划责任冲突已经实质关闭，且修订后的规范、生产代码、Run 协议、33 项约束登记和聚焦回归相互一致。

据此：

- **放行 R5-L6；**
- **放行 R5-L0—L6 整个 L 系列按既定目标完成；**
- 该 PASS 不把已公开的原型限制改写为已关闭能力，也不等同于正式生产安全认证或科学准确率认证。

## 2. 上一轮阻断的关闭证据

### 2.1 submit、current 与 reviewer 已成为三个清晰动作

活动计划现在在所有承重位置给出一致职责：

- `docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md:68-82` 把 `RunService` 限定为合同校验、Artifact 登记、Run 终态、完成收据和提交时 currentness 观察，并明确禁止其更新 current 或自动创建 reviewer；
- 同文件 `:94-95` 已删除“Operation 声明推进一个 head”的残留，改为 Operation 不声明提交时自动推进 head，调度器需要选择 current 时另行执行精确 Root CAS；
- 同文件 `:154-164` 明确 `head_advance` 只是输入谱系状态报告，提交事务不更新 `CurrentBinding`；current 选择与 reviewer 调用均发生在父调度器读取完成状态之后；
- 同文件 `:184-195` 的唯一调用流程止于 Artifact、Run 完成和 receipt，随后才是按需 Root CAS 或 reviewer Operation 调用；
- 同文件 `:300-302`、`:378` 和 `:463-465` 分别在审查说明、旧职责处置和自动停止条件中重复固定同一边界。

生产实现与此一致：

- `src/scidiscovery/artifact_agent/service/runs.py:735-767` 在完成事务中只重检 current anchors、写 `stale_rejected|not_requested` receipt；未写 current，也未创建 reviewer Run；
- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py:159-162` 将 current 读取与显式 `scientific_current_select` CAS 暴露为独立 Root 动作；
- `src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py:234-244` 的选择操作绑定精确预期旧 ref；
- `src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:424-447` 只从编译 Operation 投影 reviewer edge，后续 reviewer 仍通过正常 Operation 调用，不是 submit 副作用；
- `docs/role-result-json-protocol-v1.md:78-93` 的正式协议也止于 Artifact/Run/receipt，并明确 current 与 reviewer 的后续显式职责。

因此没有第二个 current 写入点、第二个 reviewer 生命周期，也没有用 `head_advance` 兼容字段暗中恢复旧 Task 行为。

### 2.2 文件工具的实现所有权与授权所有权已分开

`docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md:107-110` 现在准确区分：

- 通用生命周期/文件工具的**实现**属于 backend；
- 工具身份只由内置插件登记一次；
- 每个 Agent `OperationSpec` 必须显式引用获准使用的工具；
- backend 只能投影“已授权且自己可实现”的交集，不能隐式增补。

同文件 `:217-220` 的“写文件实现细节不泄漏到 OperationSpec”指编辑机制和会话实现，而不是取消工具授权声明；结合上述明确条款，不再构成责任冲突。

生产链路只有一个投影来源：

- `WorkspaceBackend.assignment_tool_names`：`src/scidiscovery/artifact_agent/service/local_workspace.py:74-86`；
- Local/Hardened 分别从现有 Operation 工具投影派生：同文件 `:111-115`、`hardened_workspace.py:87-91`；
- Run assignment 消费 backend 投影：`runs.py:194-213`；
- Codex profile 消费同一 backend 投影：`src/scidiscovery/platforms/codex.py:440-449`；
- Worker router 构造后强制与投影集合恒等：`mcp_local_worker.py:52-72`；
- Hardened 在 begin/chunk/commit 任一缺失时把 `server_file_create` 判为不支持：`hardened_workspace.py:72-85`。

这关闭了最初 B1，同时没有引入第二工具注册表、第二 preflight 或 backend 私有授权白名单。

### 2.3 防回退测试覆盖了本次真实缺陷

`tests/operations/test_baseline_role_contracts.py:29-62` 同时固定当前 Run 协议与活动计划事实，并把此前出现过的自动 current/reviewer、RunService 承担全部职责、工具无需 Operation 显式引用和“声明推进一个 head”等旧语句列为退役事实。

该测试以精确文本作防回退哨兵，不能替代语义审查；本轮已另外对计划中所有 `current/head/reviewer/review edge` 命中作人工通读，并与上述生产路径逐点对照，未发现同义改写后的冲突。

中英文入口文档也已对齐实际分发面：`README.md:35-42` 与 `README.zh-CN.md:27-36` 都把根目录 `roles/` 定义为交互式根调度器提示，并明确科学 Worker 角色由插件 `OperationSpec` 编译生成；它们不再把已删除的静态通用科学角色描述为当前目录内容。

## 3. 33 项约束与最终证据一致性

`docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 当前恰有 33 项：

- 7 项 `conformant`；
- 25 项 `pending_review`；
- 1 项 `known_issue`。

其中 `AUTH-003`（`:18-23`）准确记录 assignment/profile/router 同源及 Hardened 缺创建工具时 Run 前拒绝；`ROLE-002`（`:90-95`）准确记录同一 Operation 合同贯穿生命周期和旧角色合同退出。计数与
`docs/plans/evidence/R5_L6_OLD_PATH_REMOVAL_AND_FINAL_MATRIX.zh-CN.md:90-102` 一致，没有把 pending 或 `SEC-002` 粉饰为全部 conformant。

本轮静态扫描还确认 `src/` 与 `plugins/` 对 `TaskService`、`TaskToken`、`legacy_task`、`WorkerTaskAccess`、`task_ref`、`task_private`、`mcp_worker_daemon`、`mcp_worker_proxy`、`worker_socket` 为零命中。旧中央运行权威没有因本次文档修订重新出现。

## 4. 独立验证

所有本轮测试均使用：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
```

执行：

```text
python -m pytest -q \
  tests/operations/test_baseline_role_contracts.py \
  tests/operations/test_l5_hardened_run_backend.py \
  tests/operations/test_l2_run_invariants.py::test_recursive_current_uses_producer_receipts_and_commit_rechecks_head \
  tests/operations/test_l2_run_invariants.py::test_root_current_is_explicit_unqualified_compare_and_set \
  tests/operations/test_l3_review_and_human_policy.py::test_review_gate_requires_a_passing_review_of_the_exact_revision \
  tests/operations/test_l3_review_and_human_policy.py::test_default_local_exploration_has_no_qualification_or_approval_state
```

结果：`18 passed in 39.17s`。

另行通过：

- 活动计划退役/现行事实确定性扫描；
- 33 项 YAML 数量与状态分布断言；
- 旧中央运行权威生产符号扫描；
- `git diff --check`。

实现方报告新增计划事实测试后完整矩阵为 `200 passed`；本审查没有重复该全量数字，也不以其替代上述独立聚焦验证。

## 5. 阻断项

**无。**

## 6. 非阻断限制

1. `SEC-002` 仍是 `known_issue`：LocalTrustedBackend 的 Codex 原生文件边界依赖可信本地环境和提示约束，不是技术沙箱；生产秘密或不可逆操作必须使用适合的隔离后端。
2. Agent collection output v1 仍未实现；当前正确行为是在 catalog/preflight 失败关闭，而不是宣称支持。
3. Hardened v1 是纯 MCP 后端，不支持需要原生 shell、代码或 `view_image` 的 Operation；TCAD 当前只走 Local。这是公开能力边界，不是第二框架。
4. 本轮未进行真实 systemd 主机升级、远程执行或 TCAD 求解，也不判断科学结论准确率；相关 L6 自动化与先前独立审查证据仍是这些面的主要依据。
5. 活动计划末尾仍记录上一阶段 `199 passed`，而补充事实测试后的最新实现方全量报告为 `200 passed`。前者是当时 B1/B2 返修节点的历史结果，不影响当前语义或本轮独立结果；后续归档可把本报告和最新数字追加到审查流水账。

## 7. 复杂度与奥卡姆判断

**通过。** 当前结构没有为了关闭审查问题增加针对性旁路：

- 行为仍只由一个 `OperationSpec → CompiledOperation` 目录授权；
- Local 与 Hardened 只是一个窄 `WorkspaceBackend` 后面的两个部署实现；
- assignment、Codex profile 和 router 共享一个 backend 工具投影；
- submit、current CAS、reviewer invoke 是三个显式动作，没有第二生命周期；
- 旧 Task/token/中央 Worker/静态角色兼容路径继续删除；
- TCAD 与曲线能力仍归插件，通用核心没有新增领域名称分支。

这比恢复旧 Task 可靠控制器、在 backend 内暗建权限表或让 submit 自动串联 current/review 更小、更可检验，也符合本 L 系列“最小默认主干、可选 Hardened 后端”的目标。

## 8. 放行结论

**PASS：放行 L6，并确认 R5-L0—L6 整个 L 系列完成。**

此放行严格以当前已声明范围为准；第 6 节限制继续有效，尤其不得把 LocalTrustedBackend 描述为技术隔离沙箱，也不得把未实现的 collection 输出描述为可用能力。
