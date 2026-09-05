# R5-M6D“Effect 自动建立审批请求”独立审查

日期：2026-09-02

审查者身份：未参与实现的普通代码独立审查者；本次不作为科学 Operation Worker，未调用
instance/control/worker 工具，也未修改生产代码、测试、计划或实施证据。

## 1. 结论

**FAIL。** 正常路径、公开旧工具删除、精确 URL、合同漂移失败关闭和既有 TCAD/普通 Agent/资格
回归均通过，但当前实现存在两个实质阻断：

1. 审批请求提交与语义绑定之间的崩溃窗口不具备请求级幂等性。故障后重试会为同一个
   ExecutionRequest 创建第二个可决定、可授权的 ApprovalRequest；
2. 编译器允许 Effect 的 `subject_ports` 采用任意声明顺序，自动审批也遵循该顺序，但
   `ExecutionService.authorize()` 又硬编码为 `(request_ref, payload_ref)`。一个已成功编译、调用并由
   人工决定的合同可以在 `execution_start` 才永久失败。

- 阻断项：**2 项**，见第 3 节。
- 非阻断项：没有发现需要本阶段追加的生产代码改进项；有两项审计边界说明，见第 9 节。
- 33 项约束：阻断项分别破坏 `AUTH-001/IMM-002/HIL-001/CQRS-002/RES-002` 和
  `AUTH-003/ROLE-002/PLG-002` 的阶段完成要求；`SEC-002` 继续保持既有 `known_issue`，本次没有把它
  误写为已关闭。
- **放行判断：不放行 M6 整体回归、M6 终审、M7 或任何后续阶段。修复必须留在 M6-D，并由新的
  未参与实现者复审。**

绿色测试不能覆盖上述针对精确崩溃窗口和允许合同形状的反例，因此不能把本候选条件通过。

## 2. 审查基线、范围与方法

审查仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent`

- 分支：`baseline/8765-codex`；
- `HEAD`：`404aeb14c6ebc4b08bac599db91eaee54c103f48`；
- 工作树：包含 R5 前序阶段的大量修改、删除和未跟踪文件。M6-D 并非独立 Git commit，不能把
  `git diff HEAD` 的整个 R5 累积差异冒充 M6-D 专属补丁；
- 实际审查对象：M6-D 证据所指当前文件字节、Effect 的
  `operation_preflight → operation_invoke → ExecutionService → ApprovalService → loopback UI →
  execution_start/sync` 路径、Root/MCP/平台/安装工具面，以及必要的崩溃和插件合同反例。

规范依据：

1. `docs/plans/R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md` 的 M6-D、M6 完成门、33 项阶段门和
   自动停止条件；
2. `docs/plans/evidence/R5_M6D_EFFECT_AUTO_APPROVAL_IMPLEMENTATION_EVIDENCE.zh-CN.md`；
3. `docs/ARCHITECTURE.zh-CN.md`；
4. `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
5. `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml`；
6. 当前生产代码、插件声明、测试插件、平台生成器、部署入口和测试。

审查完整遵循 `scid-cross-boundary-review`、`scid-find-simplifications`、
`scid-change-scope-checks` 和 `karpathy-guidelines`：先锁定单一权威及真实安装路径，再检查旁路、
崩溃恢复、插件卸载和重复状态，最后以最小可信回归加目标反例决定阶段结论。

关键受审文件摘要：

| 文件 | SHA-256 |
|---|---|
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_execution_routes.py` | `2b76215c07276c155a1769d09a33622d6fe1feddddfbf8ae9a0f95ea033ea7a0` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root_approval_routes.py` | `abccdb2231bf485f98f261cd0723d71fa8109d5c30473eb06aa06ad39ac51ee7` |
| `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` | `e2d8876bde41af24f6dd302da106a3ae9a229a67eca51d6491af57168b88b81a` |
| `src/scidiscovery/platforms/codex.py` | `f5737759e490c963737ecd14abf4cc1a26befde9d04892c989c3242b44c76c9c` |
| `deploy/install.sh` | `8475b5a5a4b816b07c7e34ce1f89b9a09731e365ae721cf44a47f0ebe5a43d03` |
| `tests/operations/test_r4_execution_approval_identity.py` | `47bf76b3cc35fa2f36f1596cc4486d63bb9c6d61d5602180211e3bbc7662b6c5` |
| `tests/operations/test_baseline_effect_lifecycle.py` | `a800f44971982a7b7a6db3894f506b516da9f5c190e74e0e7a2cfd7b1eb4dbd9` |

## 3. 阻断发现

### B1：审批已提交、绑定失败后的重试创建第二个可授权请求

严重性：**阻断 / 权威与恢复缺陷**。

最紧位置：

- `mcp_root_execution_routes.py::_ensure_execution_approval()`：先生成随机
  `approval_id = f"apr_{uuid.uuid4().hex}"`；
- 同一函数随后调用 `ApprovalService.create_request()`，并以
  `idempotency_key=f"execution-approval:{approval_id}"` 提交 ApprovalRequest；
- 只有审批服务独立提交完成后，才调用 `SchedulerBindingService.bind()` 建立
  `<execution-name>.approval` 语义绑定。

可达场景：磁盘故障、数据库锁错误、进程中止或绑定服务异常发生在 `create_request()` 已提交、
`_bind()` 尚未完成的窗口。Execution 绑定已经存在，但 Approval 绑定不存在。下一次相同
`operation_invoke` 会正确找到原 Execution，却因为没有 Approval 绑定而重新生成随机 approval id 和
新的随机相关幂等键。旧请求不会被找到或复用。

独立内联故障注入结果：

```text
approval rows after injected bind failure/retry: 2
distinct idempotency keys: 2
dashboard-visible pending before decision: 2
unbound orphan authorized execution: yes
```

探针只在 `/tmp` 临时运行时中令第一次 `namespace="approval"` 的 `_bind()` 抛错；没有修改产品文件。
第一次失败后数据库已有一个 pending ApprovalRequest、Execution 语义绑定已存在、Approval 语义绑定
不存在。恢复 `_bind()` 并重放完全相同的 `operation_invoke` 后，审批表中有两个不同 approval id、
两个不同 idempotency key。两个请求的 subjects、question、options、compiled identity 和
ReviewDocument 全部相同，且都出现在 loopback UI dashboard；仅随机 approval id、manifest 和 nonce
不同。

这不只是“不可达 CAS 垃圾”。探针通过第一个未绑定请求的真实访问 token 完成人工决定，并将该
approval id 直接传给当前唯一 `ExecutionService.authorize()`；服务接受它并把同一个 Execution 推进为
`authorized`。因此两个请求在服务授权边界都具有真实权威，语义绑定只是 Root 默认选择其中一个，
并没有使另一个不可授权。

影响：

- 违反 M6-D“自动创建且仅创建一个 exact ApprovalRequest”和“重复调用幂等”；
- 违反 M6 完成门中 Approval 只有一个权威；
- 人工可能在 dashboard 看到两个相同执行授权，其中一个显示为“未绑定研究实例”；
- 重试不是有界恢复，而是在每次相同窗口故障后继续累积新的可决定请求；
- 实施证据第 3、5 节关于幂等与单一请求的结论只覆盖了无故障重放，不能支持崩溃窗口声明。

最小修复方向不是增加表、状态机、清理任务或兼容层。可从 Execution 的不可变身份、精确 subjects 和
compiled identity 派生稳定 approval id/幂等键；重试时让 `ApprovalService.create_request()` 返回同一个
已提交 launch，再补做同一语义绑定。修复还应新增“create 已提交、bind 失败、进程级重试”回归，并
证明 dashboard 和 `ExecutionService.authorize()` 只存在一个候选权威。

### B2：编译 subject 顺序与执行授权端的硬编码顺序不一致

严重性：**阻断 / 编译合同与消费端不一致**。

最紧位置：

- `operations/catalog.py::_validate_review_graph()` 对 external Effect 只检查
  `set(review.approval.subject_ports) == {input_port, output_port}`，因此顺序是合法合同的一部分且可自由
  声明；
- `mcp_root_execution_routes.py::_compiled_execution_approval()` 按编译合同 tuple 的原顺序建立
  `subject_refs`、projector context、ReviewDocument 和 ApprovalRequest；
- `service/executions.py::ExecutionService.authorize()` 又固定要求
  `exact_subjects = (request_ref, payload_ref)`，不读取当前 compiled `subject_ports`。

独立插件反例把测试 Effect 的已编译 subjects 从 `(request, payload)` 改为 `(payload, request)`，并
提供与这一声明一致的 projector。目录编译、`operation_invoke`、精确 UI 投影和人工决定全部成功，
但显式 `execution_start` 得到：

```text
reversed compiled subject order: catalog accepted; invoke+UI decision succeeded;
execution_start failed closed: human decision does not bind the exact request and payload
```

adapter submit 次数仍为 0、Execution 保持 `created`，所以这是安全的失败关闭，而不是越权执行；但它
仍是实质合同缺陷：目录把 Operation 编译为可调用 Effect，用户对精确编译合同完成授权，生命周期末端
却消费另一份隐藏顺序规则。新插件无需违反任何公开 ABI 即可落入永久死路。

最小修复有两个可审计选择：

1. 若产品规范要求 request 必须先于 payload，则在唯一目录编译器明确要求
   `subject_ports == (output.name, input.name)`，使畸形合同在任何 Execution/Approval 创建前失败；
2. 若声明顺序是合法 ABI，则把同一编译顺序传到授权校验，删除 `ExecutionService` 的隐藏固定 tuple。

二者都不需要新状态、表、注册表或 ABI 字段；不能以插件名、TCAD 或测试 Operation 特判修复。

## 4. 其余十项重点核验

### 4.1 正常自动创建和无故障幂等：局部 PASS，但被 B1 否决整体结论

普通路径中，`operation_invoke` 创建 ExecutionRequest 后立即进入私有
`_ensure_execution_approval()`；相同请求无故障重放复用同一 execution binding 和 approval binding。
聚焦测试验证第二次调用返回同一审批，adapter submit 次数为 0。

该证据只能证明“已有正确 binding”的重放，不能证明提交/绑定中间故障的幂等，故本项不能作为
M6-D 完成证据。

### 4.2 旧公开两步工具和第二入口：PASS

- `ROOT_TOOLS` 当前 26 个且唯一，`execution_approval_request_create` 不在其中；
- `RootMCPRouter` 对旧名返回 `unknown root tool`；
- `src/`、`plugins/` 中不存在同名方法、RootTool、路由字典、别名或转发器；
- `SCHEDULER_TOOLS` 直接投影当前 `ROOT_TOOLS`，新生成 Codex profile 的 26 个 Root tools 中没有旧名；
- `deploy/install.sh` 中旧名称只存在于退役负集合和安装探针，clean stage 与真实 MCP tools/list 都要求
  它不可达；
- 测试中的旧名称只用于负例。

工作区现有 `.codex/config.toml` 是 `.gitignore` 明确排除、时间早于 R5-M6-D 的本机生成文件，其中仍
有旧 allowlist 文本；它不是源码、发布输入或可调用服务路由。平台初始化器和安装事务会重新生成并
校验当前列表。此本机环境漂移不构成第二生产入口，但 M6 整体回归前应按正常安装流程重新生成，不能
把该旧文件作为 M6-D 成功证据。

### 4.3 request-specific URL、loopback 和 Worker 隔离：PASS

- `ApprovalService.status()` 保存并返回该请求自己的
  `/review/<approval_id>?token=<access_token>`；Root 只在 pending 时拼接 `approval_base_url`；
- installed 生命周期测试逐字验证返回值等于 `http://127.0.0.1:8766 + launch.review_path`，不是审批首页；
- 生产 systemd control unit 固定传入 `http://127.0.0.1:@APPROVAL_PORT@`，UI unit 固定绑定
  `127.0.0.1`；端口还经过 `1..65535` 校验；
- Worker assignment、Local/Hardened Worker MCP 和 Operation Agent profile 中没有 review URL、
  Approval/Execution id 或 access token；只有 Root scheduler prompt 获得并展示 URL。

### 4.4 不自动决定、不自动 start/sync，查询不推进本路径状态：PASS

自动调用结束时 Approval 为 `pending`、Execution 为 `created`。未做 UI 决定时
`execution_start` 拒绝，adapter submit 为 0；代码中 `_invoke_compiled_effect()` 不调用
`record_ui_decision`、`execution_start`、adapter submit 或 `execution_sync`。本路径创建的执行审批没有
`expires_at`，重复 `approval_status`/`execution_status` 不改变其 pending/created 逻辑状态。

科学资格审批与执行授权仍是不同 ApprovalContract 和不同决定；没有自动合并后果。

### 4.5 当前编译合同、labels、subjects、投影和 identity：正常顺序 PASS，顺序泛化由 B2 阻断

`_current_execution_contract()` 从冻结 ExecutionRequest 的 compiled identity 反查当前唯一 catalog，
逐项核对 operation id/version/digest、approval-contract digest、executor、preparation profile 和
ExecutionRequest Artifact labels。`_compiled_execution_approval()` 再读取当前 contract 的 question、
options、subject ports 和 projector，以精确 Artifact 快照生成有界 `ReviewDocument`。

`_ensure_execution_approval()` 对已有 binding 逐项比较 kind、subjects、question、options、compiled
identity 和 review document；错误 binding 的独立内联负例得到
`stored execution approval differs from the compiled contract`，且没有再增加审批行。

当前三个生产/测试 Effect 都声明 request 在前、payload 在后，因此正常生产声明闭合；但编译器公开
接受的其他顺序不闭合，见 B2。

### 4.6 漂移、卸载、错误 identity/subjects、历史和 revision：PASS

- 当前合同漂移或插件卸载时，`_current_execution_contract()` 在 start 前失败；
- ExecutionRequest 缺 compiled identity 的历史对象失败；
- 错误 ApprovalRequest compiled identity 无法授权；
- 已有错误 subjects/question/options/document/identity binding 在自动确保阶段失败；
- 新 payload 以 `on_conflict="create_revision"` 创建新的 Execution revision 和新的 pending approval，旧
  revision 决定不继承；
- 未决定的新 revision 无法 start，adapter submit 保持 0。

这里的失败关闭不能抵消 B1：B1 产生的是两个都与当前合同完全相同的有效请求，所以“错误 binding
拒绝”分支不会去重它们。

### 4.7 中途失败和错误 binding：FAIL

错误已有 binding 会诚实失败且不继续创建，已经通过内联负例；但审批服务提交后、binding 前的中途
失败会在重试时创建第二个权威，故整体为 FAIL，详见 B1。

### 4.8 净复杂度、表/状态/ABI：结构 PASS，运行权威因 B1 失败

- Root tools 从 M6-C 的 27 个净减为 26 个；
- `OPERATION_ABI_VERSION` 保持 `11`，`OperationSpec` 仍为 12 个字段；
- M6-D 没有修改 schema/storage/service migration，没有新增数据库表、Execution/Approval 状态、
  注册表、守护进程或第二 Operation 入口；
- 当前 `catalog.py` 734 行、operations 包 8 文件/2100 行，未突破既有门；
- 当前生产 Python 141 文件/46,718 行。

但 B1 会在现有 `approval_requests` 表中为一次逻辑授权创建多条权威记录，所以“没有新表”不能证明
“没有重复状态”。结构净减成立，运行时单一权威完成门不成立。

### 4.9 TCAD、普通 Agent 和 qualification 防退化：PASS

跨边界 108 项集合覆盖当前目录编译、负例、Local/Hardened 能力、运行时插件、真实 Local TCAD、
Effect 身份、平台配置和部署入口；另 14 项覆盖普通 Local Agent Run、独立 review/人工资格、M6-B
Operation 级 admission 和 33 项结构。两组均通过。

没有发现 M6-D 把 review URL 或执行身份传给 Worker，也没有把科学资格与外部执行授权合并。

### 4.10 定向补丁与更小实现：主路径无领域特判，但恢复实现还不是最小正确闭包

当前私有 `_ensure_execution_approval()` 是合理的单一自动入口；旧公共方法和别名已删除，代码没有按
TCAD、曲线、Schema 或测试名分支。失败原因不是“自动创建思路过大”，而是随机审批身份没有绑定到
已有不可变 Execution 请求。稳定派生身份和一个请求级重放负例，比新增恢复状态机、清理器、表或
补偿事务更小。B2 也只需统一编译期顺序规则或让授权端消费同一 tuple。

## 5. 跨边界权威图

| 边界 | 预期唯一权威 | 当前结果 |
|---|---|---|
| Operation 声明 → catalog | `ApprovalContract` + compiled identity | 正常合同 PASS；顺序约束不闭合，B2 |
| preflight → invoke | 同一 `BoundOperationCall` / Effect plan | PASS |
| Execution 创建 | `ExecutionService` + execution semantic binding | 本阶段正常路径 PASS |
| Execution → Approval 自动闭包 | exact request/payload + compiled contract | 正常路径 PASS；提交/绑定恢复 FAIL，B1 |
| Approval 展示 | compiled projector → bounded `ReviewDocument` | PASS |
| 人工决定 | request-specific loopback UI | PASS；B1 会展示两个有效请求 |
| 决定 → execution_start | exact decision + compiled identity + subjects | 正常顺序 PASS；允许的反向合同 FAIL，B2 |
| start → sync/collect | 唯一 Execution lifecycle + adapter | 既有回归 PASS |
| Worker 边界 | 无 Approval/Execution/token 身份 | PASS |
| 平台/安装 | 当前 ROOT_TOOLS 投影和真实 MCP probe | PASS |

## 6. 33 项架构约束复核

本次不擅自把 registry 中的 `pending_review` 晋级为 `conformant`；只判断 M6-D 是否满足当前阶段门。

- **B1 退化/未满足：**
  - `AUTH-001`：一个逻辑 Execution 出现两个可被 `ExecutionService.authorize()` 接受的审批事实；
  - `IMM-002`：相同完整请求在恢复窗口不是幂等，而是因随机 approval id 得到不同指纹；
  - `HIL-001`：UI 可让人对两个外观相同的 exact 请求分别决定，语义 owner 不能消除旧请求的授权能力；
  - `CQRS-002`：显式创建命令的后果不能在不确定提交后幂等重放；
  - `RES-002`：相同窗口每失败一次即可再增加一个请求，恢复数量无固定上限。
- **B2 退化/未满足：**
  - `AUTH-003/ROLE-002`：catalog、invoke、projector、UI 决定和 authorize 没有消费同一完整合同；
  - `PLG-002`：符合公开 Effect 编译规则的新插件可编译、可审批但不可执行。
- **未见本阶段退化：** Artifact/current、科学内容所有权、确定性 Transform、科学资格与执行授权分离、
  adapter 状态分离、未知提交恢复、领域所有权、Worker 最小上下文、UI 安全渲染和发布代际。
- `SEC-002` 仍为 Local spawn_agent 的既有 `known_issue`；本阶段没有扩大或虚假关闭它。

`tests/operations/test_architecture_constraint_matrix.py` 确认 registry 仍恰有 33 个唯一稳定 id 且字段完整，
但结构测试不可能发现 B1/B2 的生命周期组合缺陷。

## 7. 独立命令与结果

除只读 `git`/`rg`/`wc`/`sha256sum`/metrics 外，所有 Python 和 pytest 均设置：

```bash
ulimit -Sv 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

没有使用 xdist 或其他并行 pytest。

### 7.1 Effect 与身份聚焦回归

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py
```

结果：`7 passed in 39.21s`。

### 7.2 跨边界、TCAD、平台和部署回归

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_l6_runtime_capabilities.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/artifact_agent/test_deploy_scripts.py
```

结果：`108 passed in 46.86s`。

### 7.3 普通 Agent、资格准入和 33 项结构

```bash
pytest -q -p no:cacheprovider \
  tests/operations/test_l2_local_run.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_architecture_constraint_matrix.py
```

结果：`14 passed in 2.20s`。

### 7.4 三个独立内联反例

1. **审批提交后 binding 故障与重试：**结果为 2 个审批行、2 个幂等键、2 个 dashboard pending，
   未绑定旧请求可真实 authorize；反例成立，M6-D FAIL。
2. **反向 compiled subject 顺序：**目录、invoke、UI 决定成功，`execution_start` 以
   `human decision does not bind the exact request and payload` 失败；反例成立，M6-D FAIL。
3. **已有错误 approval binding：**重放以
   `stored execution approval differs from the compiled contract` 失败，审批行数不再增长；该负例通过。

反向顺序探针第一稿沿用了只理解 request-first 的原测试 projector，因此在 projector 处按预期失败，
不能证明授权端问题；随后以同一公开组件协议替换为 reverse-aware projector 后重跑，得到上述有效
跨边界反例。报告不把第一稿探针错误冒充产品测试失败。

### 7.5 工具面、ABI、规模和静态检查

独立 Python 探针结果：

```text
root_tools=26 unique
generated_platform_tools=26
retired_tool_absent
operation_abi=11
OperationSpec_fields=12
```

`scripts/r5_current_metrics.py` 结果关键项：production Python `141 files / 46,718 lines`；operations
package `8 files / 2,100 lines`；`catalog.py` 734 行。

其他结果：

- `git diff --check HEAD`：通过；
- 同名 public method/RootTool/route/alias 在 `src/`、`plugins/`：零命中；
- `deploy/install.sh` 两处旧名均为退役负集合；
- 生产 systemd control/UI 配置均只指向或绑定 `127.0.0.1`；
- Worker/assignment 路径对 review URL、approval/execution id 和 token：零命中。

### 7.6 未运行完整回归

没有独立重跑完整 `pytest -q`。原因不是资源或环境问题，而是最小可信目标反例已经复现阶段阻断；按
变更范围检查规则，相关失败必须先调查，继续用全量绿色数量不能改变 FAIL，也不能替代缺失的崩溃
恢复回归。实施证据报告的 `256 passed` 作为实现者证据存在，但本审查不把它冒充独立全量结果。

修复 B1/B2 后的新独立复审应先使两个反例转绿，再按跨多个生命周期边界的风险重新运行完整 7 GiB
串行回归。

## 8. 奥卡姆审计与修复边界

保留的高置信简化判断：

1. 自动审批属于 Effect invoke 的行为闭包；恢复公开二步工具不是修复，它会重新引入遗漏步骤和重复
   合同组装；
2. 不需要新审批恢复表、outbox 状态、定时清理器、第二 binding registry 或兼容 API；稳定派生的
   approval identity/idempotency key 可复用现有 ApprovalService 重放合同；
3. `ExecutionService.authorize()` 的 exact subject 校验是承重安全边界，不能删除。应统一其输入顺序
   权威，或把唯一合法顺序提前固化到 catalog；
4. 当前 `_ensure_execution_approval()` 对错误现有 binding 的逐字段比较保护真实不变量，不应为修复
   B1 而放宽；
5. 修复不得按 TCAD、architecture fixture、Schema 名或 approval kind 增加特判，也不得提高 ABI、
   新增 Operation 字段或建立第二合同投影。

回滚边界：B1 可局限在 Effect 审批身份/重放及其回归；B2 可局限在 catalog 的 Effect 合同验证或
authorization 的 compiled subject 投影。两者均应独立可验证。

## 9. 非阻断审计边界

1. 当前为跨多个 R5 阶段的大型未提交工作树，不存在可复现的 M6-C→M6-D Git commit diff。本报告以
   当前关键文件 SHA-256、M6-D 证据指向的调用链、真实平台生成器、安装入口和独立反例固定受审字节。
   这不减轻 B1/B2。
2. 没有运行真实浏览器、真实远端 solver 或长时失联恢复。M6-D 改的是请求自动闭包而非 renderer、
   solver 算法或远端 adapter；当前 installed UI lifecycle、Local TCAD 和执行桥回归已通过。即使补跑
   这些昂贵门，也不能否定已经在真实服务边界复现的两个阻断。

## 10. 最终放行

R5-M6-D **FAIL**。

当前不放行任何后续工作。只允许在 M6-D 内修复：

1. 同一不可变 Execution 的 ApprovalRequest 在提交/绑定故障后仍严格复用同一身份、同一请求和同一
   人工决定入口；
2. catalog、projector、ApprovalRequest、HumanDecision 与 `ExecutionService.authorize()` 对 subject
   顺序只有一个可审计权威；
3. 新增两个目标回归并由未参与实现者复审；
4. 复审通过后，才可放行 **M6 整体回归与终审**。即使未来复审 PASS，也不得由 M6-D 报告直接放行
   M7。
