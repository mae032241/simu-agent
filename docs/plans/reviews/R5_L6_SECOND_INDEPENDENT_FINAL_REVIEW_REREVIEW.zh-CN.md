# R5-L6 第二位独立最终审查复核

日期：2026-09-01  
复核者：原第二位独立最终审查者  
复核对象：第二位终审 B1/B2 返修后的当前工作树  
结论：**FAIL**

## 1. 裁决摘要

原报告的两个直接实现缺陷已经按当前实现语义闭合：

- **B1 运行闭环：PASS**。Local/Hardened 的 assignment、Codex profile 和实际 router 现在消费所选
  `WorkspaceBackend` 的同一工具投影；我在源码路径和 clean-installed wheel 路径上均完成了仅依照
  assignment 声明工具的 Hardened 提交。缺少 commit 工具的变体在 catalog、preflight 和 Run 创建处
  一致失败关闭。
- **B2 分发/Run 协议：局部 PASS**。旧静态 role 文件已经从源码分发面删除，独立构建的 wheel 只含
  且能实际加载 `roles/scheduler.md`；当前 `docs/role-result-json-protocol-v1.md` 对 submit、显式 current
  和父调度器另行调用 reviewer 的责任描述与代码一致。

但“计划已同步”的返修声明不成立。仍标记为“L6 双重独立总审查候选”的
`docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md` 在规范性正文中继续要求与当前代码、当前协议
以及同文件最新返修记录相反的 current/reviewer 行为，并且对服务端文件工具究竟属于 backend 还是
每个 OperationSpec 仍给出与 B1 实现相反的要求。

这是当前架构责任归属的实质矛盾，不是历史审查记录或用词瑕疵。故本轮仍为 **FAIL**：

- **不放行 L6**；
- **不宣布整个 R5-L 系列完成**；
- 只需做决策语料/计划的聚焦修正与复核，不需要重做 B1 实现或重跑完整 199 项。

## 2. B1 独立复核

### 2.1 静态闭环

以下路径现在形成一条可追踪的后端有效工具投影：

1. `src/scidiscovery/artifact_agent/service/local_workspace.py:74-86` 把
   `assignment_tool_names()` 纳入唯一 `WorkspaceBackend` 协议；
2. Local 在 `local_workspace.py:97-115` 返回现有 Local Operation 工具投影；
3. Hardened 在 `hardened_workspace.py:53-91` 返回普通 Worker Operation 工具投影，并在
   `supports_operation()` 中要求 create 所需的 begin/chunk/commit 三工具；
4. `src/scidiscovery/artifact_agent/service/runs.py:193-214` 用当前 Run 所选 backend 的同一投影生成
   assignment；
5. `src/scidiscovery/platforms/codex.py:436-449,452-514,526-553` 用 backend 类型的同一方法生成 child
   profile 和父进程继承 server 的 `enabled_tools`；
6. `src/scidiscovery/artifact_agent/interfaces/mcp_local_worker.py:53-72` 在 router 构造后强制其实际工具
   集与 backend 投影相等；Hardened 通过
   `mcp_hardened_worker.py:45-62` 的覆写 hook 先注册服务端文件工具，再参加同一恒等检查。

这消除了原先 assignment 无条件调用 Local 投影的分叉。router 的校验发生在实际注册之后，也没有
另建 registry、preflight 或科学生命周期。

### 2.2 正向独立运行

我没有只复述新增测试，而是另写了受限探针。探针读取真实 Hardened `assignment.json`，每次调用前
先断言工具名确实在 `assignment["tools"]` 中，然后依次调用领域工具、begin/chunk/commit 和 submit。

源码工作树探针结果：

```text
assignment_equals_profile: true
assignment_equals_router: true
required_file_tools_present: true
submit_state: completed
run_count: 1
```

随后我用 `scripts/build_git_release.py` 生成隔离 release、构建并安装 core 与 blind CSV wheels，清空
`PYTHONPATH`，再从已安装包走 `compile_installed_catalog → operation_invoke → HardenedWorkerMCPRouter`
同一流程。结果：

```text
catalog_state: queued
assignment_equals_profile: true
assignment_equals_router: true
submit_state: completed
```

因此原 B1 的可运行反例已经关闭，不再以其阻断发布。

### 2.3 负向独立运行

我从 blind CSV 作者 Operation 的工具引用中仅删除 `file_write_commit_tool`，重新编译目录并执行真实
Root catalog/preflight。结果：

```text
catalog.runtime_binding:
  process: worker
  required: [server_file_create]
  status: unavailable
preflight.admissible: false
preflight.reason_code: runtime_backend_capability_missing
run_count: 0
```

拒绝发生在 durable Run 创建前，满足当前实现所选择的 fail-closed 语义。

### 2.4 B1 尚需由计划明确的设计选择

B1 的代码现在内部一致，但当前计划没有同步接受该设计：

- `R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md:107-108` 仍规定生命周期和通用文件编辑属于 backend，
  不由领域 Operation 重复注册；
- 同文件 `:358-365` 又明确写“服务端文件编辑协议……不作为普通 Operation 必填工具”；
- 实际 `general_science_agent_operations.py:15-33`、curve/TCAD Operation 和 blind plugin 都把
  begin/chunk/commit 作为 Operation 组件引用；`HardenedWorkerBackend` 现在会在缺任一引用时拒绝该
  Operation。

当前 33 项矩阵的 `AUTH-003` 则选择“工具必须来自编译 Operation”这一侧。两种设计都可以做成单一
权威，但不能同时作为现行规范：

- 若保留当前实现，计划应明确通用文件工具是每个 Agent Operation 必须编译授权、由 backend 选择性
  投影的非领域能力；
- 若保留计划原要求，则 backend 应提供自己的通用文件传输工具，领域 Operation 不应因没有声明
  commit 而在 Hardened 上不可用。

本复核不替产品方替选架构；该未决矛盾并入第 4 节阻断。

## 3. B2 独立复核

### 3.1 role 删除和 wheel 分发：PASS

当前仓库 `roles/` 只剩 `scheduler.md`，`pyproject.toml:37-39` 也只分发这一文件。源码搜索没有发现旧
role loader；`platforms/scheduler_prompt.py` 只解析一个静态 scheduler prompt。

独立 clean release/wheel 观察为：

```text
distributed_roles:
  scidiscovery-0.1.0.data/data/share/scidiscovery/roles/scheduler.md
retired_role_hits: []
```

我把该 wheel 安装到 `/tmp` 的独立 venv，清空 `PYTHONPATH` 后调用实际 loader；加载路径位于 venv 的
`share/scidiscovery/roles/scheduler.md`，内容非空，导入的 `scidiscovery` 也不来自源码工作树。因此该
结论不是仅查看 `pyproject.toml` 得到的推断。

删除的静态科学角色由 Operation 编译资源替代；当前运行路径没有发现删除后回退到 role 名称或第二
角色注册表的行为。

### 3.2 当前 Run 协议：PASS

`docs/role-result-json-protocol-v1.md:78-93` 现在准确描述：

```text
submit → seal/validate → candidate CAS → Artifact → Run/receipt
```

并明确：

- Run 完成不自动推进 current；
- current 由后续显式 Root CAS 更新；
- reviewer 由父调度器依据编译 review edge 另行选择并调用。

这与 `RunService._complete()`、`scientific_current_select` 和 scheduler prompt 的实际责任一致。当前
production/dynamic role 面也没有重新出现 `task_evidence_sources`、collection-enabled、
`state=finalizing` 或旧 validate/finalize Worker 路由。

## 4. 剩余阻断：活动 L6 计划仍同时规定两套责任

### R1：current/reviewer 完成语义没有在计划正文同步

该计划顶部 `:1-5` 仍标记为“L6 双重独立总审查候选”，不是历史审查或已归档旧设计。但其规范正文
仍写：

- `:65-75`：唯一 RunService 要“事务性记录 current CAS 结果”并“按编译 review edge 创建 reviewer
  Run”；
- `:152-157`：完成事务同时写 Run/receipt、reviewer 待办和 head CAS，并可能记录
  `head_advance=advanced`；
- `:177-188`：唯一调用流程最后一步仍是记录 head CAS 并创建 reviewer 待办。

同一文件 `:704-715` 的最新返修记录、当前 Run 协议和实际代码却明确选择：

- submit 只完成 Artifact/Run/receipt；
- current 由显式 Root CAS 更新；
- reviewer 由父调度器另行 invoke。

我用确定性扫描复核四条旧规范语句，四条仍全部命中。新增
`tests/operations/test_baseline_role_contracts.py:29-42` 只扫描
`docs/role-result-json-protocol-v1.md`，所以不会发现活动计划中的反向要求。

### R1 的影响

这直接涉及 current 唯一权威、review 调度所有权和 submit 原子边界。按照旧正文实现会给当前架构
重新加入自动 head/reviewer 副作用；按照当前代码实现则违反仍在使用的 L6 完成计划。后续维护者无法
从当前语料判断哪一侧可被安全修改，故“当前文档真实一致”和“没有第二 current/生命周期”尚不能被
最终签字。

此外，第 2.4 节的文件工具所有权矛盾说明 B1 的代码修复虽闭环，活动计划仍未决定它是否符合原
“backend 工具不进入领域 Operation”的复杂度约束。返修记录仅追加于文件末尾，没有修订或显式废止
前面的规范条款，不能构成真正同步。

### 最小解决动作

选择并写明唯一当前设计，然后做以下最小修正之一：

1. 若当前代码/Run 协议是权威：修订计划 `:65-75,107-108,152-157,177-188,358-365`，明确显式
   current、父调度器 reviewer，以及文件工具在 Operation/backend 间的实际授权关系；
2. 若计划原正文是权威：实现相应的自动 current/reviewer 与 backend-owned file tools，并重新做跨
   边界审查。这显然不是本次返修所宣称的选择。

当前改动已经明确走第一条，故最小且符合奥卡姆原则的动作是修正文档，而不是新增状态或适配器。
同时把协议事实测试扩展到这份活动计划，或将计划明确标为被当前架构/协议完全取代并把仍有效的完成门
迁到唯一规范 owner；不能只靠文件末尾的时间线覆盖正文。

## 5. 独立检查结果

全部 Python/pytest 命令均在以下限制下运行：

```text
ulimit -v 7340032
MALLOC_ARENA_MAX=2
PYTHONDONTWRITEBYTECODE=1
```

结果：

- 聚焦 pytest（Hardened 正负、Local 投影、role 分发/协议、Hardened profile、collection）：
  **8 passed in 37.23s**；
- 源码 Hardened assignment-only 探针：通过；
- 缺 commit 的 catalog/preflight/零 Run 探针：通过；
- clean release + core wheel + blind plugin wheel + installed Hardened assignment-only：通过；
- wheel role 清单与安装后 scheduler loader：通过；
- `git diff --check`：通过；
- `bash -n deploy/install.sh deploy/reinstall.sh deploy/cleanup_legacy_services.sh
  deploy/install_ssh_tcad_runner.sh`：通过；
- `scripts/r5_current_metrics.py`：生产 Python 146 文件/50,023 行，Operation 包 8 文件/2,139 行，通用
  核心领域 token 为 0；
- 33 项 YAML：33 项，7 conformant、25 pending_review、1 known_issue；
- 活动计划责任扫描：四条旧 current/reviewer 规范全部仍在，失败。

我没有重复实现方完整 199 项。跨边界的正向、负向和已安装 wheel 证据足以复核 B1/B2；完整测试数量
不能消除活动规范的直接反例。

## 6. 非阻断限制与复杂度判断

原终审列出的限制没有因本返修改变：Local 不是技术沙箱，`SEC-002` 保持 known issue；Agent
collection 继续一致失败关闭；Hardened v1 仍为纯 MCP、TCAD 仍走 Local；真实 systemd 原地升级和
科学准确率不在本复核证据内。

B1 的实现修正本身规模小且没有引入第二 registry/preflight/lifecycle；删除无消费者 role 文件也符合
减法方向。当前唯一阻断可以用少量规范文本和一个覆盖活动计划的事实测试解决。增加兼容层、自动
reviewer 状态或第二工具注册表都会比纠正文档更复杂，不应作为返修方式。

## 7. 放行结论

| 项目 | 结论 |
| --- | --- |
| 原 B1 可运行缺陷 | PASS |
| 原 B2 旧 role 分发 | PASS |
| 原 B2 当前 Run 协议 | PASS |
| L6 活动计划与上述事实一致 | **FAIL** |
| 放行 L6 | **否** |
| 宣布整个 R5-L 系列完成 | **否** |

在活动计划修订或明确被唯一现行规范取代、并完成聚焦复核前，最终裁决保持：**FAIL**。
