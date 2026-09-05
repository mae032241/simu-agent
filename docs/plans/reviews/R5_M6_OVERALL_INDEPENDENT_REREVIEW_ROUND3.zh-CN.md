# R5-M6 整体第三次返工第三名全新独立复审

- 日期：2026-09-02
- 审查对象：当前工作树组合字节；`HEAD=404aeb14c6ebc4b08bac599db91eaee54c103f48`
  只用于定位，不能冒充精确 M6 或 B4 修复 diff
- 审查身份：未参与 M6 实现、三份历史整体终审/复审或 B3/B4 修复的第三名全新普通代码审查者
- 复审结论：**PASS**
- 阻断缺陷：**0**
- 新增非阻断缺陷：**0**
- 唯一放行判断：**仅放行 M7；不宣称 M7 或 R5-M 完成**

## 1. 结论先行

第三次返工关闭了第二名复审者发现的 B4。当前 `ExecutionService.create()` 不再让 existing-row 分支
只验证 request Artifact 后直接返回；existing-row 与 no-row 分支现在构造并消费同一个稳定
`ArtifactRegistration`、同一个 `execution:<execution_id>:request` key，并要求 registry replay 返回
同一个精确 Artifact ref。原 idempotency record 缺失、request hash/bytes、artifact id、response hash
或 registration 不一致时，错误都发生在 Execution semantic binding、Approval 和 adapter submit 之前。

本复审没有把 `263 passed` 当作故障恢复证据，而是从真实 `RootMCPRouter.operation_invoke` 重新注入
两个跨库提交窗口，并独立破坏一次性临时数据库。结果如下：

1. request Artifact 已提交而 Execution 行未插入：连续三次均保持
   `0 Execution / 1 request / 0 Approval / null binding / 0 submit`，第四次相同调用恢复为单一对象；
2. Execution 行已提交而 binding 未建立：连续三次均保持
   `1 / 1 / 0 / null / 0`，第四次恢复并绑定同一个 Execution；
3. request 五个字段、Artifact registration 十个元数据维度、缺/错幂等记录均失败关闭；随机相似
   orphan 不被扫描或收养；
4. 同请求有界并发收敛，不同请求竞争严格一胜一拒，`INSERT OR IGNORE` 不能吞掉已占位的冲突行；
5. Approval service/Root status/list、loopback 全部 GET 类别和 Execution service/Root status/list 的全库
   逻辑摘要保持不变；只有显式同源/CSRF 续期与 `execution_sync`/`execution_outputs` 发布写库；
6. M6 结构、规模、唯一目录/入口、领域中性和 33 项约束的本阶段边界均未发现新反例。

因此当前 M6 portfolio 的所有完成维度均通过。本 PASS 不覆盖或改写三份历史 FAIL；它只审查当前
组合字节，并且只授权进入 M7。

## 2. 审查对象、历史链和当前字节

当前分支为 `baseline/8765-codex`，从单一 baseline commit 起叠加完整 R5 大型未提交工作树，不存在
可由 Git 独立还原的精确 B4 commit。本复审完整读取并保留：

- `R5_M6_OVERALL_INDEPENDENT_FINAL_REVIEW.zh-CN.md`：首次 B1/B2，结论 FAIL；
- `R5_M6_OVERALL_INDEPENDENT_REREVIEW.zh-CN.md`：B3，结论 FAIL；
- `R5_M6_OVERALL_INDEPENDENT_REREVIEW_ROUND2.zh-CN.md`：B4，结论 FAIL；
- `R5_M6_OVERALL_CLOSURE_EVIDENCE.zh-CN.md`、M6 计划、最小设计宪章和 33 项约束。

历史报告是各自当时字节的有效冻结事实；本报告不删除、覆盖或回写其 verdict。当前关键字节为：

```text
261cf01e44d66dfa07d58700acb873145de2c2eca5320d52dc86dc9a931a76a4  executions.py
388e2b9f678f9f1ecb3ffa8ec5bf691df60eb2cb3ef45e336ef03846c8280c1d  mcp_root_execution_routes.py
5784566f48352df57df602044009773069bd517a1890d6e29fb83e90483cd39a  approvals.py
6b64c67de10c194036833f8289e39dfcf70b9ee75dbb1c474950bc9aa4262572  approval_ui/app.py
abccdb2231bf485f98f261cd0723d71fa8109d5c30473eb06aa06ad39ac51ee7  mcp_root_approval_routes.py
d9c53f7d41da4fd1b888ed5c5fade700c90748d3411e5a88231841d876ddc6fb  test_r4_execution_approval_identity.py
b0ede8c692a3c35ae985bc2439e382ba4bcd496a0e1f6481a2d5c14f1e92af05  test_m6a_direct_instance_management.py
3b61bfbbcb1c86d17888c71df8f48d60d8328b4a3de6ccf0a0aa02578dbfa8df  SCIENTIFIC_AGENT_CONSTRAINTS.yaml
```

## 3. A：request Artifact 已提交、Execution 行未插入

### 3.1 连续三次故障与精确恢复：PASS

探针包装真实 `ArtifactService.register()`：先让 execution request 完整登记和提交，再连续三次抛出
进程中断等价异常。每一轮后均为：

```text
Execution 0 / execution_request 1 / Approval 0 / execution binding null / submit 0
```

第四次相同 `operation_invoke` 恢复为一个 Execution、一个 request、一个 execution binding、一个
pending Approval、submit 0。四轮观测到的 `ArtifactRegistration` canonical bytes、idempotency key 和
registry 返回 ref 分别只有一个唯一值，证明恢复使用的是第一次冻结对象，不是按相似内容重建。

### 3.2 请求字段与 Artifact 元数据漂移：PASS

复审先截获 Root 将要登记的精确 request bytes、registration 和 key，再在 fresh state 中只预置一个
漂移候选。以下每项都在 Execution/binding/Approval/submit 前拒绝：

| 类别 | 独立变更维度 | 结果 |
|---|---|---|
| request | `execution_id`、executor、preparation profile、payload ref、compiled identity | 全部 `ExecutionServiceError` |
| Artifact 核心元数据 | kind、Schema id、schema version、media type、creator、parent refs、labels、confidentiality | 全部 `ExecutionServiceError` |
| Artifact 完整 registration | supersedes ref、content encoding | registration replay 得到 `IdempotencyConflictError` |

后两项虽由统一 registry replay 而不是 `_validate_request_artifact()` 的快速检查拒绝，仍在任何语义
binding 或 Approval 之前失败关闭；没有静默修复候选元数据。

### 3.3 缺/错 idempotency record 与随机孤儿：PASS

- 精确稳定 Artifact 已存在但原 key 缺 record：`ArtifactIdentityConflictError`；
- no-row 状态下分别损坏 request hash、request bytes、record artifact id、response hash：分别得到
  `IdempotencyConflictError` 或 `RegistryIntegrityError`，始终为 0 Execution/0 Approval/null binding；
- 预置 payload 完全相同但 Artifact id 为随机 `execution_request_ffff...` 的孤儿后，正常调用创建并
  引用稳定 id 派生对象；最终保留两个 request Artifact，但只有稳定对象进入 Execution/Approval，随机
  对象没有被扫描、猜测或收养。

人为破坏只发生在一次性临时 SQLite 中，并先移除 append-only trigger；它模拟离线损坏、错误恢复或
部分库替换，不是产品写入口。通过标准是失败关闭，而不是查询时修复数据库。

## 4. B：Execution 行已提交、binding 未建立

### 4.1 连续三次故障与恢复：PASS

在真实 Root Effect 路径让 `_bind_target("execution", ...)` 连续三次于 Execution 行提交后抛错。
每轮均为：

```text
Execution 1 / execution_request 1 / Approval 0 / execution binding null / submit 0
```

三轮 execution id、request id、registration、idempotency key 和 registry 返回 ref 均稳定相同。第四次
恢复绑定原 Execution，只创建一个 pending Approval，adapter submit 仍为 0。

### 4.2 B4 的原 record 缺失/损坏：PASS

在上述已有行、无 binding 状态分别执行：

- 删除 `execution:<stable execution id>:request` record；
- 保留 hash 但把 record 的 request bytes 改成 `{}`；
- 仓库精确回归另覆盖 request hash 改为错误 SHA-256。

三类重试分别以 `ArtifactIdentityConflictError`、`RegistryIntegrityError` 或
`IdempotencyConflictError` 拒绝。状态保持一个未绑定 Execution、一个 request、零 Approval、零 submit；
没有先建立 binding/Approval 再报错。

### 4.3 existing-row/no-row 恢复合同合流：PASS

`executions.py:101-116` 在分支之前构造稳定 request Artifact id、完整 `ArtifactRegistration` 和 key；
existing-row 在 `131-149` 验证冻结 request 后重放该 registration/key 并核对返回 ref；no-row 在
`150-190` 取回精确稳定 Artifact 或登记新对象，最终消费同一 registration/key。两条路径没有恢复表、
扫描器、第二 registry、补偿状态机或公共修复工具。

## 5. C：有界并发和 `INSERT OR IGNORE`

复审在单个串行探针内使用 `ThreadPoolExecutor(max_workers=2)` 和双线程 barrier；pytest 本身没有并行：

- 完全相同请求连续 5 轮：两调用都返回同一 id，每轮恰好 1 Execution、1 request Artifact；
- 同一 execution id 但 executor、profile、payload、compiled identity 或 labels 不同，每类 5 轮：每轮
  严格一个 accepted、一个 `ExecutionServiceError`，库内 request/Envelope 与胜者逐项一致；
- 另在 Artifact 登记成功后、Execution INSERT 前直接抢先插入同主键但 executor 不同的行，确认
  `INSERT OR IGNORE` 虽忽略 INSERT，随后的 reread/compare 仍以
  `execution identity is already bound to a different request` 拒绝。

总计 30 个受控并发/竞争场景未出现双成功异请求、双 Execution 或被静默吞掉的冲突。

## 6. D：查询纯读与显式写边界

### 6.1 Approval、Root 和 loopback 全部 GET 类别：PASS

探针对 state 下全部 SQLite 文件、全部非内部表和全部行生成排序逻辑摘要，并同时构造业务已过期
Approval、access token 已过期 Approval、fresh pending Approval、decided Approval 及实例/审批 binding。

摘要之间执行：

- `ApprovalService.status/list_requests/request_summary/review`；
- Root `approval_status` 和 `approval_list`；
- loopback dashboard `/`、静态 CSS/JS、`/instances`、`/instance/<id>`、pending review、subject 下载、
  decided history、业务过期 review、过期 access review 和未知 GET。

HTTP 状态依次符合 `200` 正常视图、过期 access `403`、未知路由 `404`，所有读路径前后全库逻辑摘要
完全相同。业务过期只作为有效状态投影返回，不落库；GET 不轮换 access/CSRF token。

错误 Origin 和错误 CSRF 的 refresh POST 均为 `403` 且摘要不变。正确同源、正确 CSRF 的显式 refresh
POST 为 `303`，只改变 `database/approvals.sqlite3`；刷新后 GET 为 `200` 并再次保持纯读。

### 6.2 Execution status/list 与发布：PASS

探针构造两个已 collected、已有 result Artifact 但尚无语义 result binding 的 Execution。service
`status/list_statuses` 与 Root `execution_status/execution_list` 前后全库摘要相同，均返回
`result_artifact_name=null`。

- 显式 `execution_outputs` 后只改变 `database/scheduler-bindings.sqlite3` 并发布精确 result binding；
- 为隔离 Root 发布边界，将第二个已 collected Execution 的 adapter sync 替换为无写 no-op，再显式调用
  `execution_sync`；同样只改变 scheduler binding 库并发布精确 result binding。

这与代码边界一致：status/list 只验证已有 binding，`execution_sync`/`execution_outputs` 才调用
`_publish_execution_result()`。

## 7. E：M6 组合完成门

| M6 完成门 | 第三名独立复审事实 | 判定 |
|---|---|---|
| Artifact、Run、current、Approval、Execution 各一个权威 | fresh owner/表、service 和目录唯一；A/B/C 证明部分提交不产生第二语义权威 | PASS |
| 普通探索无 cohort/approval/execution 状态成本 | 无 `input_admission` 的普通 Agent/Transform 组合回归不查询资格、不创建 Approval/Execution | PASS |
| 实例创建/选择只经精确显式用户入口 | Root 未绑定只返回短期 AEAD loopback capability；写只来自显式 UI 命令，聊天/Worker 无入口 | PASS |
| Operation 级 all-or-none/资格合同唯一 | `InputAdmissionSpec` 和 preflight-before-guard 保持唯一；隐藏集合生产命中为零 | PASS |
| producer 未来用途预测消失 | `allowed_input_usages` 及替代全局用途图生产命中为零；consumer/reviewer/revision 负例保留 | PASS |
| Effect 建立单一稳定 Approval，不自动决定/start/submit | A/B/record/orphan/并发均通过；Approval identity、subjects 和显式人工/start 边界保持 | PASS |
| 科学资格与执行授权分离 | qualification 与 `execution_authorization` 的 kind、subjects、合同和决定仍分离 | PASS |
| readiness/invoke 同源；查询纯读 | 两者消费同一 `_prepare_operation_call`；D 的全库摘要通过 | PASS |
| Root 工具、表和 Operation 字段净减少 | 26 工具、15 表、三类字段合计 41；见第 8 节 | PASS |
| 单目录、单 registry、无领域特判 | 唯一 `CompiledCatalog` 构造点、单 entry-point group、关键核心领域 token 0 | PASS |
| TCAD、普通 Agent、Local/Hardened、部署和约束不退化 | M6 组合、跨边界及完整回归通过；未以绿测替代 A—D 故障/摘要证据 | PASS |
| 奥卡姆：不以新治理修复旧治理 | B4 仅增加 existing-row 的既有 registration replay/ref compare；无新实体、状态、工具或恢复系统 | PASS |

Portfolio 没有失败维度，故整体判定 PASS。

## 8. 结构、规模、单目录和奥卡姆复算

独立 Python/AST/SQLite/TOML 探针与 `scripts/r5_current_metrics.py` 得到：

| 指标 | 当前独立结果 | 判断 |
|---|---:|---|
| Root / Local / Hardened 工具 | **26 / 26 / 26** | 相对 M0 30 净删 4 |
| fresh 五类通用事实表 | **15** | Artifact 3、Scheduler 5、Run 2、Approval 4、Execution 1 |
| `InputPortSpec` / `OutputPortSpec` / `OperationSpec` | **12 / 17 / 12** | 合计 41；相对 M6 前 45 净减 4 |
| Operation ABI | **11** | 无旧字段双读 |
| 生产 Python | **141 文件 / 46,970 行** | 相对 M0 146 / 50,023 净减 5 / 3,053 |
| `src/scidiscovery/operations` | **8 文件 / 2,100 行** | 未超过 8 / 2,103 门 |
| `catalog.py` | **734 行** | 未超过 738 门 |
| 默认五插件 | **186 components / 43 Operations** | 编译后仍为 43 个唯一 Operation |

生产 AST 中只有 `src/scidiscovery/operations/catalog.py:708` 一个 `CompiledCatalog(...)` 构造点。根包
与四个插件 `pyproject.toml` 共五个声明文件全部只用 `scidiscovery.plugins`；可选图证据插件也使用
同一组。`allowed_input_usages`、`allowed_port_sets`、`_PARAMETER_COHORT_PORTS`、三个退役实例工具和
`execution_approval_request_create` 在生产 Python 中均为零命中。当前度量脚本的关键通用核心领域 token
命中为 0。

第三次返工后生产规模相对 Round 2 的 46,959 行只增加 11 行，正是 existing-row registration replay
和返回 ref 核对；没有增加生产文件、表、Root 工具、Operation 字段、catalog 构造、领域分支或后台
状态机。该修复复用既有 Artifact 权威，符合本阶段奥卡姆门。

## 9. 33 项约束复核

约束 YAML 精确为 33 个唯一 id，assessment 分布保持 `conformant=7`、`pending_review=25`、
`known_issue=1`。本报告不因测试通过把 pending 自动晋级。

- `AUTH-001`：A/B 的稳定唯一对象和 record 损坏失败关闭，不再存在已知的 B4 第二事实入口；
- `IMM-002`：请求五字段、compiled identity、Artifact registration 和 key/ref 全部参加重放验证；
- `CQRS-001`：Approval/Root/loopback/Execution 的服务与页面查询全库摘要纯读；
- `CQRS-002`：两处部分提交均由同一显式命令幂等完成，record 不完整时不推进后果；
- `RES-002`：连续故障、同/异请求并发和恢复均有界；
- `HIL-001/002`、`EFF-001/002`：自动 Effect 只建立待决定请求，不自动决定/start/submit；科学资格与执行
  授权分离，未知提交规则未被 B4 修复改写；
- `PLG-001/002`、`TOP-002`、`ROLE-001/002`、`MIG-001`：单目录、同一 preflight/invoke、领域中性和不
  收养随机旧对象保持；
- `SEC-002` 的 Local 原生工具隔离仍是唯一 `known_issue`，原样保留。本 PASS 不声称技术隔离已完成；
- 真实生产升级、远端 solver 长任务和失联恢复仍属于 `MIG-002`/M7 等后续资格，未被本地测试外推。

未发现由 M6 或 B4 返工引入的 33 项约束反例。

## 10. 串行验证记录

所有 pytest 单进程串行运行，统一设置：

```bash
ulimit -Sv 7340032
export MALLOC_ARENA_MAX=2
export PYTHONDONTWRITEBYTECODE=1
python -m pytest -q -p no:cacheprovider --tb=short ...
```

未使用 `xdist` 或并行 pytest。仅 C 的单个确定性竞争探针按测试目的使用两个有界线程。

### 10.1 精确审批/执行集合

```bash
python -m pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_m6a_direct_instance_management.py
```

结果：`21 passed in 13.58s`；外层 elapsed `13.97s`；MAXRSS `100,200 KiB`；exit 0。

### 10.2 M6 组合与 UI 扩展

```bash
python -m pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_m6a_direct_instance_management.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_r4_approval_ui_renderer.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_architecture_constraint_matrix.py \
  tests/artifact_agent/test_artifact_audit.py
```

结果：`62 passed in 59.09s`；外层 elapsed `59.45s`；MAXRSS `106,172 KiB`；exit 0。

### 10.3 跨边界扩展

```bash
python -m pytest -q -p no:cacheprovider --tb=short \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_l5_hardened_run_backend.py \
  tests/operations/test_l6_runtime_capabilities.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m3_transform_equivalence.py \
  tests/operations/test_l2_local_run.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/artifact_agent/test_deploy_scripts.py
```

结果：`116 passed in 76.20s`；外层 elapsed `74.85s`；MAXRSS `124,496 KiB`；exit 0。

### 10.4 当前完整回归

```bash
python -m pytest -q -p no:cacheprovider --tb=short
```

结果：`263 passed in 114.05s`；外层 elapsed `112.94s`；MAXRSS `139,080 KiB`；exit 0。

### 10.5 独立探针和静态命令

所有内联探针均使用同一 `ulimit`、arena 和禁止字节码环境，并从当前源码真实 Root/service 入口运行：

| 命令/探针 | 精确结果 |
|---|---|
| `PYTHONPATH=src:... python - <<'PY'`，A/B 故障、漂移、record、orphan 矩阵 | 两个窗口各连续 3 次后恢复；15 个字段/元数据漂移、no-row 5 类缺/错 record、existing-row 2 类 record 错误全部拒绝；随机 orphan 未收养 |
| `PYTHONPATH=src:... python - <<'PY'`，并发与 INSERT 冲突 | 同请求 5 轮收敛；五类异请求各 5 轮一胜一拒；抢先冲突行被 reread/compare 拒绝 |
| `PYTHONPATH=src:... python - <<'PY'`，全库逻辑摘要 | Approval/Root/全部 GET 与 Execution status/list 零变化；refresh 只改 Approval DB；outputs/sync 只改 binding DB |
| `python scripts/r5_current_metrics.py` + 独立 AST/SQLite/TOML/Schema 探针 | 141/46,970、8/2,100、catalog 734、26/26/26、15 表、12/17/12、ABI 11、186/43、单 catalog、33/33 |
| `git diff --check HEAD` | exit 0，无 whitespace error |

独立探针有四次仅属于 harness 的前置修正：第一次用 `except ... as item` 后继续访问被 Python 清除的
异常局部变量；第一次 Execution 摘要夹具让两个执行复用固定 `external_run_id`；第一次入口探针误把
五个声明文件预期为六个；第一次 fresh 表探针把 `artifact_agent.sqlite3` 写成连字符文件名。四者均
发生在对应产品断言前；改用 holder、有界唯一 external id、实际 TOML 文件集合和真实数据库文件名后，
原矩阵完整通过。它们未修改仓库字节，也没有被隐藏或计作产品失败。

## 11. 剩余边界与唯一放行结论

本轮没有运行真实远端 solver、真实生产升级、长时失联执行或 M7 的真实 Agent 纵向矩阵。这些是计划
明确保留给 M7 的资格门，不能由本地 `263 passed` 外推，也不阻断“进入 M7”本身。`SEC-002` known
issue 和 25 项 `pending_review` 均保持原状态。

**R5-M6 整体第三次返工第三名全新独立复审 PASS；当前唯一授权是仅放行 M7。**

三份历史 FAIL 必须继续保留。本报告不宣称 M7 已完成，不宣称 R5-M 已完成，也不授权跳过 M7 的安装、
真实 Agent/TCAD、外部 Effect、部署回滚、科学/安全负例或两位最终独立审查门。
