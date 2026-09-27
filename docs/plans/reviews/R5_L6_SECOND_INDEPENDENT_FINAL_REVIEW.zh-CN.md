# R5-L6 第二位独立最终审查

日期：2026-09-01  
审查者：第二位独立最终审查者（未参与 L0—L6 实现）  
审查对象：当前工作树中的 R5-L0—L6 累计重构候选  
结论：**FAIL**

## 1. 最终决定

本候选已经实质完成了大部分结构性减法：生产路径中可见一个
`scidiscovery.plugins` 入口、一个 `CompiledCatalog`、一个 `RunService`，默认 Local 与可选
Hardened 共用同一 Artifact/Run/current 权威；旧 Task/token/中央 Worker 的可执行入口没有在我追踪的
生产主干中重新出现，TCAD 专用实现也位于插件。

但当前候选仍有两个发布阻断，其中第一个是可运行的跨边界合同错误，而不是文案问题：

1. Hardened 的 `assignment.json` 声明了 Local 工具投影，与同一 Run 的 Hardened profile/router
   实际工具集不一致；
2. 当前且随 wheel 分发的 Worker 协议仍描述已经撤回的 collection/finalizing/Task 来源，并且当前
   Run 协议文档描述了实现并未发生的 reviewer 待办/current 完成事务。

因此：

- **不放行 L6**；
- **不宣布整个 R5-L 系列完成**；
- 第一位复审者的 PASS 不足以覆盖本次独立复现的新反例；
- 修复后应重新做一次聚焦复审，不需要重做框架或重新跑全部 196 项。

## 2. 审查边界与方法

我独立阅读了：

- `docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md`；
- `docs/plans/evidence/R5_L6_OLD_PATH_REMOVAL_AND_FINAL_MATRIX.zh-CN.md`；
- 当前中英文 `docs/ARCHITECTURE*`、设计宪章和 33 项约束 YAML；
- L0—L6 相关首轮、复审和第二次复审报告。

既有审查结论只用于定位待验证边界，不作为通过证据。我另外追踪了 catalog 编译、Root
preflight/invoke、Run 创建/提交、Local/Hardened Worker、Codex profile、current CAS、review edge、
部署安装/回滚和 TCAD 插件入口，并运行了受限测试和两个独立运行探针。

当前仓库相对 `404aeb1` 是累计的大型 dirty worktree；本报告评的是审查时实际工作树，不把未提交状态
本身判为失败，也不推断未提供的生产部署事实。

## 3. 阻断项

### B1：Hardened assignment 与实际授权工具集分叉

**可复现事实**

`src/scidiscovery/artifact_agent/service/run_assignment.py:8,15-49` 在生成所有 Run 的
`assignment.json` 时，无条件调用 `operation_local_worker_tool_names()`。调用者
`src/scidiscovery/artifact_agent/service/runs.py:193-213` 没有向 assignment 编译传入后端或后端的有效
工具投影。

与此同时：

- `src/scidiscovery/platforms/codex.py:481-495` 对 Local 使用
  `operation_local_worker_tool_names()`，对 Hardened 使用 `operation_worker_tool_names()`；
- `src/scidiscovery/artifact_agent/interfaces/mcp_hardened_worker.py:33-58` 在 Hardened router 中注册
  服务端 `worker_file_*` 工具；
- `src/scidiscovery/operations/tooling.py:131-168` 明确把普通 Worker 投影和 Local 原生等价投影定义为
  两个不同集合。

我用外置 blind CSV 插件创建一个真实 Hardened Run，打开其物化 assignment，并比较 assignment 与
router。结果为：

```text
write_protocol: server_file_tools
assignment_tools:
  worker_csv_summarize
  worker_heartbeat
  worker_open_assignment
  worker_submit_result
router_only:
  worker_file_write_begin
  worker_file_write_chunk
  worker_file_write_commit
assignment_only: []
```

这三个缺失工具恰是该纯 MCP Worker 创建 `output/result.json` 的唯一写路径，不是可选便利工具。
`docs/role-result-json-protocol-v1.md:24-34` 又要求 Worker 读取 assignment 中明确列出的输入/能力，并说明
Hardened 必须通过 `worker_file_*` 写文件，因此模型可见合同内部自相矛盾。

**为什么现有通过项没有发现它**

- `tests/operations/test_l2_run_invariants.py:413-431` 对
  `assignment["tools"] == router.list_tools()` 的恒等性只覆盖 Local；
- `tests/artifact_agent/test_platform_configuration.py:276-305` 只证明 Hardened profile 等于
  `operation_worker_tool_names()`；
- `tests/operations/test_l5_hardened_run_backend.py:150-162` 直接由测试代码调用文件工具完成 Run，没有
  检查 materialized assignment 的声明。

三个局部测试各自为真，但恰好没有检查 assignment/profile/router 三者在 Hardened 上的闭环。L6
证据文档把“纯 MCP Hardened”列为通过，因此上游汇总与原始运行观察不一致。

**影响判断**

这是 `AUTH-003` 和 `ROLE-002` 的反例：OperationSpec 虽仍是原始声明，但运行后端的有效能力经过两条
未统一的投影路径到达 assignment 与 profile/router。它不会建立第二个科学状态机，却会让严格遵守
assignment 的 Worker 缺少完成任务所需的授权工具，已经越过最终发布的失败关闭边界。

**最小解决动作**

让所选 backend 只计算一次“该 Run 的有效工具投影”，并让 catalog runtime binding、preflight、
Codex profile、assignment 和 router 消费同一个不可变结果；不要新增后端注册表。至少增加：

1. Local 与 Hardened 各自的 `assignment tools == profile enabled_tools == router list_tools` 恒等性测试；
2. 一个只依照物化 assignment 所列工具完成 Hardened Run 的测试；
3. 缺少任一必需服务端文件工具时，在 Run 创建前失败关闭的负例。

### B2：现行/分发协议仍保留已撤回语义，并陈述不存在的完成副作用

**可复现事实 A：随 wheel 分发的旧 Worker 合同残留**

`pyproject.toml:37-39` 把 `roles/*.md` 安装到 `share/scidiscovery/roles`。其中当前
`roles/common.md` 仍包含：

- `roles/common.md:41-45`：`task_evidence_sources` 和“later task”；
- `roles/common.md:46-50,106-107`：collection-enabled assignment/output mount；
- `roles/common.md:111-113`：恢复可进入 `state=finalizing`，随后仅可再次 submit；
- `roles/common.md:116`：仍称“validation or finalization”两阶段拒绝。

但 Run v1 在 `src/scidiscovery/artifact_agent/service/runs.py:93-96` 对任何 Agent collection 输出直接
拒绝，`src/scidiscovery/artifact_agent/service/run_records.py:64-93` 没有 finalizing 状态或 Task
身份；当前规范 `docs/role-result-json-protocol-v1.md:36-39,95-100` 也明确说 collection 不可用且旧
finalize 协议没有兼容路由。

该文件没有被当前 Operation prompt 加载，这避免了即时生产分派故障；但它仍是明确打包的、名为
“roles”的现行分发面。若它已无消费者，继续打包是死表面；若仍有消费者，则会给出错误生命周期。
两种解释都不满足“旧兼容路径确实删除、当前合同真实一致”的 L6 完成门。

**可复现事实 B：当前 Run 协议虚构 reviewer/current 完成步骤**

`docs/role-result-json-protocol-v1.md:78-90` 声称 `worker_submit_result` 最后会“在控制事务中完成
Run、记录 current CAS 结果和 reviewer 待办”。实际
`src/scidiscovery/artifact_agent/service/runs.py:727-800` 只重检已冻结 current anchors、绑定输出并把
Run 更新为 completed；`head_advance` 只有 `stale_rejected` 或 `not_requested`。显式 current 写入在
`src/scidiscovery/artifact_agent/interfaces/mcp_root_instance_routes.py:224-249` 的独立 Root CAS 命令中。
`_complete()` 也没有创建 reviewer Run 或 reviewer 待办。

我完成一个声明 review edge 的 blind CSV 作者 Run 后直接观察到：

```text
run_count_after_author_submit: 1
operations: [blind.csv.observe.v1]
receipt_head_advance: not_requested
current_selection_count: 0
```

独立审查能力和显式 current 本身仍然存在；错误在于当前规范把“可由父调度器随后选择 reviewer”写成
了“submit 事务创建 reviewer 待办”，并把显式 current CAS 写成完成事务的一部分。

**影响判断**

这不是纯措辞瑕疵。`roles/common.md` 是安装产物，且当前协议是 Worker/调度者理解唯一生命周期的规范。
它们共同使“已删除 finalizing/collection 兼容路径”和“当前文档真实一致”无法成立，并掩盖了 review
实际由谁、何时调度的责任边界。

**最小解决动作**

1. 若 `roles/common.md` 已退休，从 data-files 删除并删除该文件；若仍需保留，则完整改写为 Run v1，
   删除 Task/collection/finalizing/finalization 语义，并准确区分 Local 与 Hardened 文件协议；
2. 把当前 Run 协议的完成序列改为实现事实：完成事务登记 Artifact/Run/receipt，current 只由显式
   Root CAS 更新，reviewer 由父调度器依据编译 review edge 另行调用；若产品意图确实是自动 reviewer
   待办，则应实现并测试该单一权威，而不能只留文档；
3. 对 production、dynamic-entry、当前文档和分发 data-files 增加退休词零命中/允许清单检查，历史
   `docs/plans` 单独排除。

## 4. 已独立确认成立的主结构

以下结论有代码与运行证据支持，但不能抵消 B1/B2：

1. **唯一插件入口与目录**：`src/scidiscovery/operations/catalog.py:21,36-98` 定义唯一
   `scidiscovery.plugins` 入口和一个不可变 `CompiledCatalog`；public/support/internal/all 是同一目录
   的过滤投影，没有发现第二注册表。
2. **默认主干是轻量 Run**：`src/scidiscovery/artifact_agent/runtime.py:46-94` 只按 `local|hardened`
   选择一个 workspace backend，并为两者构造同一 `RunService`。没有 Runtime 中的 TaskService/token
   双写。
3. **Hardened 是后端而非第二科学框架**：
   `src/scidiscovery/artifact_agent/service/hardened_workspace.py:1-32,75-159` 复用 Local workspace，只
   增加每 Run 的 transport lease/文件围栏；Artifact、Run 终态、review/current 不在该 SQLite
   transport 表中。
4. **Run/current/review 的核心边界仍在**：Run 只有 queued/running/completed/failed；status/list 是
   纯读；提交通过候选 CAS、Artifact 幂等登记和控制事务完成。递归 current guard 位于唯一
   `RunCurrentGuard`，显式 current 使用 scheduler binding CAS。review edge 经编译合同验证，普通探索
   不强加 qualification 或 approval。
5. **TCAD 插件边界**：对 `src/scidiscovery/**/*.py` 的 TCAD/Sentaurus/SDevice/SProcess/deck 扫描为
   零命中；`scripts/r5_current_metrics.py` 也报告 `generic_core_domain_tokens.count = 0`。TCAD 代码、
   role、workspace hook、debug 和 Effect 位于 `plugins/tcad_artifact`。
6. **旧中央服务与部署选择**：默认 systemd 模板没有中央 Worker unit；安装器使用同一
   `SCID_WORKER_BACKEND` 驱动 daemon/profile/验证。旧 `scidiscovery-worker.service` 只在升级删除、
   卸载与事务回滚路径出现。相关 selector、旧 unit 删除/恢复和默认无中央服务测试通过。
7. **Agent collection v1 失败关闭**：Local/Hardened capability、catalog、preflight、profile 和 Run
   创建均拒绝带 collection 输出的 Agent Operation；本轮相应正负测试通过。B2 指出的是分发合同仍
   反向宣称可用，不是否认运行时已经失败关闭。
8. **33 项矩阵没有伪装全绿**：当前 YAML 精确为 33 项：7 `conformant`、25
   `pending_review`、1 `known_issue`。`SEC-002` 仍诚实标为 known issue。不过 `AUTH-003` 与
   `ROLE-002` 的证据叙述应在 B1 修复后更新；它们当前虽为 pending_review，却不能据既有测试宣称
   “同一投影已闭环”。

## 5. 独立测试结果

所有命令都在同一 shell 中先执行：

```text
ulimit -v 7340032
export MALLOC_ARENA_MAX=2
export PYTHONDONTWRITEBYTECODE=1
```

### 5.1 聚焦跨边界 pytest

选择的文件覆盖 catalog 编译/负例/干净 entry point、L1 投影、L2 Run/current/恢复、L3 review/人工
政策、L4 TCAD Local、L5 Hardened、L6 领域中性与 collection、runtime plugin 配置、平台 profile、
部署升级与回滚：

```text
141 passed, 1 failed in 59.06s
```

唯一 pytest 失败是
`test_ssh_runner_installer_cleans_up_without_scope_error`：断言时源码树中存在被 Git 忽略的
`plugins/tcad_artifact/tcad_artifact/__pycache__/remote_runner_py36.cpython-312.pyc`。该断言检查源码树
洁净度，而同一测试中的 SSH 打包、远端文件和配置断言此前均已通过。由于本审查禁止修改测试/生产
树，我没有删除该缓存后重跑，也不把这次非隔离的树状态包装成测试通过；它作为非阻断测试环境限制
保留。其余 141 项全部通过。

### 5.2 独立探针与静态检查

- Hardened assignment/profile/router 工具恒等性探针：**失败**，稳定复现 B1 的三个 router-only
  文件工具；
- 作者 submit 后 reviewer/current 观察探针：确认仅一个作者 Run、无 current、
  `head_advance=not_requested`，复现 B2 文档差异；
- `git diff --check`：通过；
- `bash -n deploy/install.sh deploy/install_ssh_tcad_runner.sh deploy/cleanup_legacy.sh`：通过；
- `scripts/r5_current_metrics.py`：生产 Python 146 文件/50,004 行，Operation 包 8 文件/2,139 行，
  通用核心领域 token 计数 0；
- 33 项 YAML 结构计数：33，状态分布 7/25/1。

测试通过数只说明已选择路径没有其他回归；B1 是测试矩阵未表达的跨边界反例，所以不能以 141 或既有
196 项通过覆盖。

## 6. 非阻断限制

以下限制被当前文档或矩阵明确披露，单独不阻断本轮，但不得在发布说明中升级为已解决：

1. LocalTrustedBackend 依赖可信本地用户和提示约束，原生工具隔离不是技术沙箱；`SEC-002` 继续为
   `known_issue`。
2. Agent collection 输出尚未实现；当前只能接受运行时一致失败关闭。确定性 Transform 多输出不受此
   限制。
3. Hardened v1 只承载纯 MCP Operation；TCAD 因原生代码/查看需求仍只支持 Local。
4. 本轮没有在真实 systemd 主机上执行旧版本原地升级/失败回滚，只验证了安装入口和事务测试；
   `MIG-002` 保持 pending_review 是正确的。
5. 审批 UI 可读性仍是产品缺陷；本轮不评价科学结论准确率、求解器物理正确性或跨领域优越性。
6. pytest 的源码树 pyc 污染使一个清洁度断言无法独立重现为通过；应在隔离副本或 clean wheel 环境
   重跑，但它不是本报告 FAIL 的依据。

## 7. 复杂度与奥卡姆判断

从控制结构看，L0—L6 的总体方向符合奥卡姆目标：旧六个 R0 核心责任的聚合规模从 13,657 行降到
3,401 行；TaskService、角色注册表、中央 Worker、在线兼容清理没有被改名包裹在默认主干；
Hardened 的私有 lease 是有真实并发消费者的传输状态，不是第二科学生命周期。行数只作结构观测，
不作为正确性证明。

当前两个阻断也说明尚未完成最后一刀减法：

- B1 来源于“同一有效工具集”被 Local assignment 与 backend profile/router 分别投影；
- B2 来源于一个已无当前运行消费者却仍打包的旧通用角色合同，以及一段超前于实现的流程文档。

最符合奥卡姆原则的修复不是增加 adapter、兼容层或新 registry，而是消除重复投影、删除或改正死合同，
再用两条跨后端恒等性测试封口。

## 8. 放行条件

聚焦复审只需确认：

1. B1 的 Hardened assignment/profile/router 工具集对每个可运行 Operation 完全相等，且真实
   Hardened Worker 能只依据 assignment 完成提交；
2. B2 的打包角色合同与当前 Run 协议不再包含 Task/collection/finalizing 的假能力，review/current
   责任描述与代码一致；
3. `AUTH-003`、`ROLE-002` 和 L6 证据表相应更新，不把旧通过项继续当作新反例的证明；
4. 在隔离临时副本中重跑受影响的 Hardened、platform、部署与协议扫描测试。

在这些条件完成并经独立复核前，最终裁决保持：**L6 FAIL，R5-L 未完成。**
