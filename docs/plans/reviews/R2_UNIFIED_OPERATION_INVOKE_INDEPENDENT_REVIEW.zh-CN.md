# R2 统一 Operation 预检与行为创建入口独立审查

审查结论：**打回**。

R2 已经建立了有价值的调用骨架，也保持了零新表、单一编译目录和既有生命周期权威；但它还没有
把 `OperationSpec` 的行为闭包变成真实 Worker/Effect 执行边界。当前可公开调用和派发的 Agent
任务仍使用旧角色 prompt、旧 Codex 角色级联网/工作区/工具配置；spec 中的模型、prompt、workspace、
资源和大部分资源上限只是进入 Task 的描述性摘要。写入前的 current/审批谓词也没有原子闭合，
Effect 的实际输出与审批 UI 甚至不同于编译过的 spec。上述问题会让后续 TCAD `worker_tool`
插件仍需修改核心静态工具表，或在权限摘要之外继续走旧旁路。

因此本报告**不允许进入 R3**。只允许在 R2 内修复并重新独立审查；测试绿色不能替代实际执行层
的最小授权和行为闭包。

审查基线：`baseline/8765-codex@404aeb14c6ebc4b08bac599db91eaee54c103f48`，
叠加已通过的 R0、R1 和当前未提交 R2 工作树。审查者只新增本报告，没有修改生产代码、测试、
Manifest、README 或主计划。

## 一、阻塞问题

### 1. Agent 的权限摘要没有成为 Codex 原生执行边界

这是本轮最高优先级阻断。

- `operations/invoke.py:320-368` 确实生成了 `TaskOperationAuthority`，并且对未实现的声明式
  `worker_tool` 和受限网络失败关闭；`tasks.py:1081-1111` 也把 capability 放入 assignment，
  并在 Worker MCP 调用时服务端拒绝未授权 capability。这一部分是正确的基础。
- 但 `task_prepare_dispatch` 仍只返回旧角色名作为 `agent_type`
  （`mcp_root.py:1997-2001`）。Codex 配置仍按角色一次性生成：`platforms/codex.py:142-173`
  明确写入 `web_search = "live"`、`view_image = true` 和旧角色 prompt；
  `platforms/codex.py:184-195` 把整个共享 `worker_workspace_root` 授给 Worker；
  `platforms/codex.py:230-271` 仍按角色暴露几乎全部静态 Worker tools。
- `TaskOperationAuthority.model`、`workspace_directories`、`network_mode`、`max_files`、
  `memory_mb` 目前除持久化和摘要外没有执行消费者。`TaskService.materialize_assignment`
  仍硬编码 `inputs/schema/output`（`tasks.py:1385-1403`），也没有生成 operation 级 Codex
  sandbox/config。
- `WorkerMCPRouter.list_tools()` 在 claim 前仍返回全部 `WORKER_TOOLS`
  （`mcp_worker.py:276-281`）。claim 后的服务端 capability 拒绝能防住已映射 MCP 调用，但防不住
  Codex 原生网页搜索、图片、共享根读取、命令或子 Agent；这些能力没有经过
  `TaskService.require_worker_capability`。

仓库自己的 R0 安装态特征测试继续确认旧配置为 `web_search=live`、共享工作区根和角色级工具并集；
本轮全量测试通过意味着该旧行为仍真实存在，不是文档残留。R2 安装态测试只证明伪造
`worker_run_analysis` 被服务端拒绝，没有启动一个真实 Codex Agent，也没有让真实 Agent 从实际
可见工具中调用一个已声明插件工具并完成受控文件 finalize/reconcile。

这直接违反“每个子 Agent 的输入、路径、工具、网络和资源权限从 compiled operation 派生，默认
拒绝”的总完成标准。它也不能支撑已冻结的 TCAD 目标：Sentaurus 手册检索、项目文件读写、静态
验证和调试诊断应是同一 TCAD 插件登记的 `worker_tool` 子组件，由 `tcad.deck.author` 显式引用；
但当前 `_agent_authority` 对任何 `template.tools` 直接返回
`worker_tool_binding_unavailable`（`invoke.py:328-331`），而 Worker 路由仍是核心静态
`WORKER_TOOLS`/`_TOOL_CAPABILITY` 表。新增一个领域工具仍必须修改核心。

最小修复门：

1. 派发必须消费任务中冻结的 operation authority，生成本次 task/attempt 专用 Codex 配置；
2. prompt、model、只读资源、精确任务路径、原生读写/补丁/命令/图片/网络和领域工具都由同一
   compiled catalog 的逻辑 tool components 投影；普通 Worker 默认不能 spawn 子 Agent；
3. 未声明工具既不出现在真实 Agent 可见清单中，伪造调用又被服务端或沙箱按同一权限摘要拒绝；
4. 网络 `none` 必须在执行环境关闭；restricted 网络必须落实域名和请求数，而不只是写入字段；
5. broker 恢复和同 attempt 重连必须重新使用同一权限摘要与任务私有根；
6. 增加真实 Codex Agent 安装态验收：调用一个已登记测试 `worker_tool`，经 controlled file
   lifecycle 完成 validate/finalize/reconcile，同时对未声明工具、兄弟路径和网络做负例。

### 2. Agent 路径仍由旧 role 合同决定行为，`OperationSpec` 不是实际行为闭包

内置 Agent spec 声明了 `test_prompt`、`architecture-test-model`、workspace、输出 validator 和
operation 端口（`builtin_plugin.py:188-213`）；真正 executor component 却只返回
`AgentExecutorPlan(role="critic")`（`builtin_plugin.py:45-46`）。随后：

- `_agent_operation_plan` 从旧 `TaskService.resolve_output_profile(role, profile)` 取得输出合同
  （`mcp_root.py:1339-1365`）；
- `_invoke_agent_operation` 再调用旧 `task_schedule`（`mcp_root.py:1304-1337`）；
- `open_runtime` 继续从 `load_roles()` 装载旧角色 prompt、JSON Schema、collection 和 context
  profile（`runtime.py:88-105`）；
- 派发只返回 `critic`，真实 Codex 使用 critic prompt，而不是 spec 已编译的
  `ARCHITECTURE_TEST_PROMPT`；声明的 model 也没有传给派发层；
- Agent 输出只做旧 role contract 兼容比较，spec 的 validator、codec、prompt resource 与
  workspace component 没有成为实际任务合同。

`not_for="Scientific work or production dispatch"` 只是 catalog 文案，不是门禁；当前
`builtin.test.agent` 可以由公开 `operation_invoke` 创建并由公开 `task_prepare_dispatch` 派发。
因此不能把上述差异归类为“测试 fixture 无生产影响”。如果一个第三方 Agent spec 编译成功但其
prompt、model、workspace 或 validator 与旧角色不同，R2 会静默执行另一种行为。

此外，Transform 路径只把原始 bytes 交给 component，声明的 input/output codec 没有运行；只有
输出 validator 被调用。R2 必须对尚未实现的组件语义整体失败关闭，不能让“编译成功”被解释为
“可按另一套旧合同调用”。

最小修复门：Agent 任务的 Worker-visible prompt、model、schema/validator、资源、工作区和输出
限制必须来自 exact `CompiledOperation`；旧 role 可以作为窄 agent implementation 被复用，但不能
再成为隐藏的行为元数据权威。不能完整执行的 codec/collection/tool/resource 组合应在 preflight
给出稳定不可调用原因，而不是被忽略。

### 3. invoke 的锁不能关闭 current/输入/审批竞态，精确绑定可能在写入前失效

`operation_preflight` 和 `operation_invoke` 都调用 `_prepare_operation_call` 是正确方向；
`operation_invoke` 也持有一个 facade 级 `_create_lock`（`mcp_root.py:1252-1260`）。但该锁不是
current/approval/binding 权威的数据库锁或 CAS：

- `_prepare_operation_call` 在 `mcp_root.py:2566-2608` 先读取 current lineages、语义 binding 和
  Artifact；
- Agent/Transform/Effect 随后只把 `artifact_name` 传给旧创建方法，这些方法再次解析名字，而不
  断言解析出的 ref 等于 `BoundInput.artifact.ref`；
- `SchedulerBindingService.select_scientific_object` 在自己的 SQLite transaction 中写 current
  （`scheduler_bindings.py:1030-1057`），不取得 Root facade 的 `_create_lock`；UI/其他 facade/其他
  进程也不共享这个 Python `RLock`；
- task 写入前没有再次读取并比较 current/review/approval receipt，也没有绑定谓词版本或 CAS。

独立并发探针在 `_prepare_operation_call` 成功后、`TaskService.schedule` 前切换 current：

```text
thread_alive= False
failure= []
created= True
result_kind= agent
```

也就是 `require_current=True` 的调用在 current 已改变后仍创建了任务。现有测试只覆盖“先完成
preflight、再改变 current、最后重新调用 invoke”；它证明 invoke 不复用上一次结果，却没有覆盖
invoke 自身的检查—写入窗口。

同时，Root 构造 `InvocationArtifact` 时从未填充 `independently_reviewed` 和 `human_approved`
（`mcp_root.py:2598-2606`），两者永久使用 dataclass 默认 `False`。所以任何
`require_review`/`require_approval` 端口当前只能永久拒绝，既没有消费既有 receipt，也没有审批变化
竞态测试。R2.8 声称覆盖“输入/current/审批变化”不成立。

最小修复门：下游创建服务必须消费 `BoundOperationCall` 中的精确 Artifact refs，不能再次按语义名
漂移解析；current/review/approval 等可变谓词必须在与创建提交可线性化的权威边界内重验，或使用
明确的版本/CAS 前置条件。至少增加 input rebind、current concurrent switch、approval/review
receipt revoke/change 的真实并发负例。

### 4. Effect 的编译输出和审批合同没有进入现有 Execution/Approval 生命周期

Effect 没有绕过执行授权：`execution_start` 仍要求既有 Approval，UI 决定仍是唯一人类权威。这一点
是正确的。但 spec 的行为与真实请求不一致：

- built-in Effect 声明输出 kind/schema 为
  `architecture_test_effect_request / scidiscovery.architecture-test.v1`，审批 question 为
  `Allow this no-effect architecture test request?`，一个 subject port；
- `ExecutionService.create` 实际固定生成
  `execution_request / scidiscovery.execution-request`（`executions.py:81-110`）；
- `execution_approval_request_create` 完全忽略 compiled `ApprovalContract` 和 projector，固定显示
  “是否授权执行页面中展示的这一份冻结 TCAD 工程？”，并绑定 request + payload 两个 subjects
  （`mcp_root.py:2432-2476`）。

独立实际探针结果：

```text
declared_output= architecture_test_effect_request scidiscovery.architecture-test.v1
actual_request= execution_request scidiscovery.execution-request
declared_question= Allow this no-effect architecture test request?
actual_question= 是否授权执行页面中展示的这一份冻结 TCAD 工程？
declared_subject_port_count= 1
actual_subject_count= 2
status= pending
```

这不是单纯的 R4 美化欠账：审批者看到的科学/执行对象、问题和 cohort 与编译摘要不同，catalog
对调度器宣称的 output 也从未产生。Operation 谱系标签虽写入了实际 ExecutionRequest，但不能弥补
行为闭包错误。

最小修复门：Effect spec 必须准确声明现有 ExecutionRequest 与可执行 payload 的输出/subject
语义，并由同一 compiled `ApprovalContract` 生成现有 ApprovalRequest；projector 只能生成安全只读
投影，决定、nonce、exact subject 和执行状态仍归旧 Approval/Execution 服务。若 R2 明确暂不实现
projector，也必须对声明了非既有固定合同的 Effect 失败关闭，不能显示错误 TCAD 文案。

### 5. R2 新增错误边界仍会泄漏普通 Unicode 编码异常

`preflight_operation` 对 Agent instruction 直接调用 `instruction.encode("utf-8")`
（`invoke.py:128-129`），没有把普通数据编码失败映射为 `OperationInvocationError`。独立负例：

```text
instruction="\ud800"
UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' ...
```

这会让 `operation_preflight` 失去稳定 `reason_code`。修复时应只捕获普通 `Exception` 并转换为精确
reason code；`KeyboardInterrupt`/`SystemExit` 必须继续原样逃出。Agent/effect/transform component
现有边界均使用 `except Exception`，没有吞掉 `BaseException`，这一点保持正确。

## 二、已通过或方向正确的部分

### 1. 单一 catalog 装配：通过

`open_runtime` 在打开服务前调用一次缓存的 `compile_installed_catalog()`，并把同一对象传给
`TaskService` 和 `ArtifactAgentRuntime`（`runtime.py:60-114,156-170`）；Root router 再接收该对象。
安装态测试用对象身份断言覆盖了 runtime、TaskService 和 Root，没有发现第二个运行时目录。

### 2. 没有新状态机、表或迁移：通过

- 没有 `OperationRun`、operation table、migration 或持久化 catalog；
- `TaskOperationAuthority` 作为冻结字段嵌入既有 `AgentTask` Artifact，不拥有独立表、服务或状态；
- Agent/Transform/Effect 分别复用既有 Task、Artifact transform、Execution/Approval 生命周期；
- SQLite schema 前后不变测试通过；代码搜索未发现新增 DDL/migration；
- 没有新增 qualification、current、readiness 或候选权威。

### 3. operation 身份、幂等和恢复摘要：主体正确

- Agent fingerprint 包含 operation id/version/digest 与 authority digest；Transform/Effect fingerprint
  包含 operation id/version/digest；三类产物有 operation 谱系标签；
- Agent task Artifact、primary/collection output 和 scheduler signal 都携带 operation/authority 标签；
- `TaskService._require_current_operation` 在 dispatch、claim、assignment、输出校验/finalize 等现有
  合同入口检查已安装 operation version/digest；目录缺失或漂移时失败关闭；
- task 重试不改变 authority，下一次 dispatch 仍会重新检查 operation digest。

但恢复后真实 Codex 权限是否与 authority 相同尚未实现和实测，不能据此把阻塞 1 判为通过。

### 4. 精确输入与服务端 MCP 工具负例：部分通过

端口缺失/多余、cardinality、重复 Artifact、schema、media、item/total bytes、current 与非空参数
均有纯 preflight；Agent usage 新增了现有 `TaskInput` 有限集合预检。任务内 `source_name` 从 port
稳定生成，TaskService 的输入读取只允许本任务绑定，`handoff_only` 仍不可读。claim 后，已映射的
Worker MCP 调用会用任务 authority 做服务端拒绝。

但原生 Codex 工具、共享路径、网络和动态插件工具未进入同一执行边界，且存在阻塞 3 的绑定竞态，
所以本项不能整体通过。

### 5. 组件计划预检与复用：通过其有限范围

Agent/Effect component plan 在 `_prepare_operation_call` 中执行并缓存进 `BoundOperationCall`；invoke
不再次运行 Agent/effect component 来产生另一份计划。Effect bridge payload validation 在写入前再次
执行属于安全重验。组件普通异常转换为稳定 invocation 原因，控制异常不被捕获。

这只证明 plan DTO 的复用，不证明 prompt/tool/UI 等完整组件语义已经执行；后者由阻塞 1、2、4
覆盖。

### 6. `scientific_inventory`：通过

新方法只列最新科学 Artifact、显式 current、claim-admissible 标签和 producer handoff；没有调用
`ready_capabilities`，也不返回候选或领域排序。旧 `scientific_readiness` 仍存在作为阶段性对照，
新 operation 路径没有读取它的 `suggested_capabilities`。

### 7. 旧创建工具：R2 阶段可暂时接受，但必须有删除门

旧 `task_schedule`、`artifact_transform`、`execution_request_create` 仍公开；operation 路径通过隐藏
参数复用它们，没有新建第四个生命周期权威。按主计划 R2 允许保留一个阶段对照，因此本轮不因
“入口数量”单独打回。

但是当前新入口仍由旧行为元数据决定合同，已经超出“仅复用生命周期”的允许范围；这是阻塞 2、4，
不能用过渡期双入口解释。R5 必须删除公开旧创建入口和旧注册选择权威，不能永久并存。

## 三、33 项约束与复杂度判断

### 通过的约束

- Artifact/CAS 不可变性、父链、Task/Approval/Execution 单一状态权威未退化；
- Worker 科学内容仍来自 Worker，Transform 和 Effect 没有生成科学结论；
- Effect start 仍需真实 UI 决定，chat 没有变成人类审批；
- 没有新增科学图、候选器、领域 workflow、资格/current 副本或持久化 operation 状态；
- 安装插件仍只有 `scidiscovery.plugins` 一个新入口，compiled catalog 同源冻结。

### 未通过的约束

- 默认拒绝最小授权只存在于 Task 摘要和部分 Worker MCP 调用，没有成为真实 Codex 原生工具、
  网络和文件系统边界；
- spec 声明的 prompt/model/workspace/tool/resource/output/review 没有完整决定实际行为；
- preflight 与写入之间的 current/approval/输入谓词不是线性一致；
- 新领域 `worker_tool` 仍需要修改核心静态工具表，尚未形成一次注册编译即可使用的真实扩展缝；
- 没有真实 Agent 端到端证据证明插件工具可见、可调用、可 finalize，而未声明工具不可见且不可
  伪造。

### 复杂度预算

```text
spec.py     299 行
catalog.py  400 行
invoke.py   432 行
合计       1131 行（低于 1200 行总预算）
```

新增数据库表数为 0，新增通用科学实体数为 0，entry-point group 为 1，catalog 为 1；这些预算通过。
但 `mcp_root.py` 相对基线增加约 399 行，旧创建入口和领域化准入仍全部保留。R2 可暂时接受胶水增长，
却不能继续通过 Root 私有分支逐个补 Agent/Effect/工具特例；阻塞修复应建立一个通用 operation-bound
派发/工具投影缝，并在 R3-R5 删除旧 role/profile/工具表，而不是增加第三套权限映射。

## 四、独立执行证据

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider tests/operations
50 passed in 33.75s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider
80 passed in 35.26s

sha256sum -c --quiet MANIFEST.sha256
通过（写入本报告前）

python scripts/build_git_release.py \
  --source . --output /tmp/scid-r2-independent-release.dLw0Pg --force
tracked source files: 232；发行目录与 tar.gz 成功生成

sha256sum -c --quiet \
  /tmp/scid-r2-independent-release.dLw0Pg/MANIFEST.sha256
通过

git diff --check 404aeb1 -- \
  pyproject.toml src/scidiscovery tests/operations tests/fixtures docs/plans MANIFEST.sha256
通过

wc -l src/scidiscovery/operations/spec.py \
      src/scidiscovery/operations/catalog.py \
      src/scidiscovery/operations/invoke.py
299 / 400 / 432
```

安装态专项测试确实从 clean release wheel 发现三个 built-in operations，并覆盖同一 catalog 对象、
Agent 创建、一个 Worker MCP 伪造调用拒绝、digest drift、Transform 幂等、Effect 待审批和 operation
谱系。Manifest 和发行证据可信。

未运行 `scripts/validate_architecture_constraints.py`，因为 8765 基线没有该文件，不能声称其通过。
未运行真实 Sentaurus solver，R2 不要求真实外部副作用。更重要的是，当前没有真实 Codex Agent
operation/tool/finalize/recovery E2E，也没有真实浏览器读取 compiled ApprovalContract 的证据；这两项
不是环境原因，而是当前实现尚未提供相应执行路径。

## 五、R2 下一轮复审门

下一轮必须至少提供以下独立可重复证据后，才可能把结论改为“通过”：

1. 一个安装态测试插件登记 Agent operation、prompt、model、workspace 和至少一个
   `worker_tool`；不修改 Root、TaskService、Worker 静态 allowlist 或 Codex 角色表即可启动；
2. 真实 Codex Agent 只看到该 operation 的工具与任务私有路径，调用已声明工具，写入
   `output/result.json`，完成 validate/finalize/reconcile；
3. 同一真实链路证明未声明 MCP/原生工具不可见，伪造调用服务端拒绝，网络 `none` 实际关闭，
   兄弟任务/共享根不可读，普通 Worker 不能 spawn 子 Agent；
4. 恢复或 broker 重连后使用同一 operation/authority digest、同一工具集和同一任务私有根；
5. current、input rebind、review/approval receipt 在检查—提交窗口改变时写入失败关闭；
6. Agent prompt/model/schema/validator/resources 来自 exact compiled operation，不从角色名补行为；
7. Effect 的实际 ExecutionRequest、exact subject cohort、question/options/projector 与 compiled
   ApprovalContract 一致，同时 UI 仍是唯一决定路径；
8. 非法 Unicode instruction 得到稳定 reason code，`KeyboardInterrupt/SystemExit` 仍逃出；
9. 重新通过专项、全量、Manifest、干净发行、零 DDL 和 299/400/500 行数门。

只有上述阻断关闭且没有新增第二权限注册表、第二审批状态机或领域核心特判，独立审查才会允许
进入 R3。
