# R2 基础权限子智能体快速闭环独立审查（第二轮）

日期：2026-08-28
审查基线：`baseline/8765-codex@404aeb14c6ebc4b08bac599db91eaee54c103f48`
审查对象：叠加已通过 R0、R1 后的当前 R2 工作树，以及持久化真实运行证据
`.scidiscovery-state/r2-live-prototype-run6/`。
第二轮审查结论：**通过**。

R2 的快速闭环目标已经真实实现：run6 确有父调度智能体调用 `spawn_agent`、专属 operation
子智能体领取既有任务、读取已绑定输入、调用注册领域工具、经受控文件接口写入、校验和封存，
最终任务进入 `completed`。OperationSpec、单一 CompiledCatalog 和既有 Task/Transform/Execution
生命周期之间没有再插入 `OperationRun` 或平行注册表。提示词白名单也已被诚实限定为原型行为
约束，外部副作用仍由原有执行审批硬门控制。

第一轮的三个放行条件均已闭合：安装后探针现在从同一已安装 catalog 精确校验新配置；主计划已
把提示词行为约束与下一版平台安全隔离拆开；代码预算在 1200 行总额不变的前提下按实际职责
一次性重配，当前三个模块均在新分项上限内。第二轮未发现可复现阻塞，**允许进入 R3**。

## 一、第一轮三个放行条件的第二轮核验

### 1. 安装后的 Codex 框架探针：已闭合

`src/scidiscovery/platforms/codex.py:114-140,148-170` 现在会为每个已编译 Agent operation 同时
生成一个 operation 角色和一个供 `spawn_agent` 继承的 Worker MCP server。run6 的实际配置因此
包含两个 MCP server（Root 和 `scid_worker_builtin_test_agent_3c8ec9aa590d`）以及九个角色（八个
旧角色加一个 operation 角色）。这与原型实现和
`tests/artifact_agent/test_platform_configuration.py:24-73` 的断言一致。

新增的 `validate_installation_profile()`（`src/scidiscovery/platforms/codex.py:194-277`）使用同一
installed `CompiledCatalog` 派生并精确检查：

- 一个 Root MCP 与每个 Agent operation 对应的稳定命名 Worker MCP 集合；
- Root MCP 的启用状态、Python 路径、Root 工具清单；
- 每个 operation Worker MCP 的角色、环境和精确工具清单；
- 旧角色与 compiled operation 角色的精确并集；
- scheduler prompt 以及嵌套/外部 workspace 的 profile 放置边界。

`deploy/install.sh:757-775` 在安装后真实导入并调用该函数，不再维护一套“1 MCP、仅旧角色”的
平行判据。目标回归
`tests/artifact_agent/test_platform_configuration.py:137-156` 对当前内置 catalog 得到精确
`(2 MCP, 9 agents)`，独立执行通过。

除正例外，第二轮还独立对生成配置做了两个最小篡改负例：

- 删除 operation Worker server 时，返回
  `installed Codex MCP set differs from catalog`；
- 把 `worker_fixture_inspect` 替换为未注册工具时，返回
  `installed Codex Worker MCP profile is invalid`。

因此安装探针不是仅放宽数量，而是对 catalog 驱动的集合、角色和工具执行失败关闭。第一轮条件
已关闭。

### 2. R2.14 原型口径与下一版硬隔离：已拆分

主计划 `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md:1054-1065` 已正确声明，首版允许
子智能体继承父会话基础 MCP、sandbox 和 skill，编译 prompt 只是可审计行为约束；同一条现在
只要求本原型确实能够证明的事项：真实 spawn、编译角色匹配、父会话本次零 Worker 调用、
注册工具成功、逐任务服务端拒绝、受控输出完成以及 Effect 外部副作用硬门。

原来混在 R2.14 中的未声明工具平台级不可见性、原生网络关闭/受限、兄弟路径隔离、恢复后授权
摘要与工具集不漂移，已移至 R2.18（主计划 `:1073-1077`），并明确写为“不是 R2 提示词原型能够
证明的安全性质”。实施记录 `docs/plans/R2_UNIFIED_OPERATION_INVOKE_IMPLEMENTATION.zh-CN.md:187-207`
继续诚实限定真实 TCAD、生产凭据、网络写入和不可逆动作不得依赖本原型放行。

两套口径不再互相冒充，第一轮条件已关闭。

### 3. 复杂度预算：总额不变的一次性职责重配合理，已闭合

实施记录 `docs/plans/R2_UNIFIED_OPERATION_INVOKE_IMPLEMENTATION.zh-CN.md:90-96` 已更新为当前可重复
测量值：

```text
spec.py     311
catalog.py  436
invoke.py   421
合计       1168
```

主计划 `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md:559-565` 保持总额 1200 不变，把
分项从 `300/400/500` 一次性重配为 `320/450/430`。调整理由与职责对应：原估算遗漏了
`spec.py` 的原生工具策略和领域工具协议声明、`catalog.py` 的这些协议及审查端口闭包启动失败
检查；`invoke.py` 因复用既有生命周期少用预算，回收额度后仍保留 9 行余量。计划同时冻结“不得
再次挪用”，任何后续超限必须先证明不能通过复用或删除兼容分支解决。

第二轮没有发现为了满足行数而应删除却被保留的平行职责：工具策略属于冻结行为声明，协议和引用
闭包属于启动期编译器，调用桥仍只负责运行期绑定；把前两者挪到新模块或 invoke 会增加注册/解释
断裂。这里不是用压缩格式规避预算，而是在总额不扩张的前提下按已经实现的单一职责校正初始
估算。当前三项分别低于 320/450/430，上述第一轮条件已关闭。

## 二、已经通过的实质性检查

### 1. run6 是真实子智能体闭环，不是 Python 直调或响应桩

`qualification-report.json` 的 SHA-256 独立复核为
`e62e17c0ae6a2c2910fae0ef18bbfbc2c252c5c0772271e64c59c41cde48009a`。报告的九项结构化检查均为
真。原始事件进一步确认：

- `codex-events.jsonl:7-8` 有状态为完成且带接收线程的真实 `spawn_agent`；
- 子 rollout 的 `session_meta` 使用精确
  `agent_role=op_builtin_test_agent_3c8ec9aa590d`；
- 子 rollout 依次实际调用 `worker_claim_task`、`worker_materialize_assignment`、
  `worker_read_input`、`worker_fixture_inspect`、三步受控文件写入、
  `worker_validate_output_file` 和 `worker_finalize_file`；
- 领域工具成功收据为 `operation_tool_succeeded:worker_fixture_inspect`；
- 校验后的 payload 精确为
  `{"input_seen":true,"tool_result":"fixture-inspected:registered-domain-tool"}`，任务最终为
  `completed`；
- 父事件流没有 `worker_*` MCP 调用。

run2、run3、run4 的失败目录和失败报告仍保存在同一持久状态根中，没有被 run6 覆盖或改写为
成功；实施记录也明确区分了各次失败原因。

### 2. OperationSpec/catalog 仍是唯一新能力入口

- `src/scidiscovery/operations/spec.py` 中的 OperationSpec 仍是冻结声明，没有执行方法和可变状态；
- `src/scidiscovery/operations/catalog.py` 只从 `scidiscovery.plugins` 编译一个不可变
  `CompiledCatalog`，私有组件索引与公开 operation 映射同属一个对象；
- `src/scidiscovery/artifact_agent/runtime.py:73` 启动期编译一次并把同一对象注入 Root 与
  TaskService；
- `operations/invoke.py` 只做输入绑定与 Agent/Transform/Effect 三座桥，分别复用既有 Task、
  Artifact transform、Execution/Approval 权威；
- 搜索未发现新增 `OperationRun`、operation 表、平行任务状态机、第二个插件 entry-point group
  或运行期可变 operation registry。

现阶段仍保留旧创建入口作为 R2 对照，符合主计划的阶段性决定；它们不能在 R3—R5 继续吸收新
功能。

### 3. 提示词边界没有冒充安全隔离，真实副作用仍有硬门

`src/scidiscovery/platforms/codex.py:45-66` 和实施记录第 10 节均明确写出：父会话暴露 operation
Worker MCP 是 Codex 0.150.1 的原型继承办法，Root 调度者不得调用，子智能体只能按所选 spec
使用；这不是平台强制隔离。真实 TCAD、生产凭据、网络写入和不可逆动作没有因此获得授权。

服务端仍在 claim 后按 `TaskOperationAuthority` 对 capability 和精确工具名逐次校验
（`src/scidiscovery/artifact_agent/service/tasks.py:1415-1469`，
`src/scidiscovery/artifact_agent/interfaces/mcp_worker.py:310-316,383-389`）。外部执行仍需冻结的 UI
决定；`tests/operations/test_baseline_effect_lifecycle.py:123-192` 验证未决定前 adapter 提交次数为
零，真实 UI 授权后才提交一次。

需要保留的风险表述是：父会话和各子会话在配置层能看到所有 Agent operation 的 Worker MCP，
“本次没有越权”不等于“技术上无法越权”；另一个子智能体也可能尝试领取同角色任务。服务端
逐任务验权与外部审批降低后果，却不能等价替代进程级最小授权。因此这一实现只对隔离的、无真实
副作用的 R2 架构验收可接受，不能用于真实科学/TCAD 执行放行。

### 4. 下一版本精确 Worker 代码保持隔离，没有提前扩张当前权威

`src/scidiscovery/artifact_agent/service/agent_dispatch.py` 与
`src/scidiscovery/platforms/codex_worker.py` 没有接入默认 Root/runtime；当前真实闭环仍走既有
`task_prepare_dispatch → spawn_agent`。精确 capability 复用现有 Task 状态和活动记录，没有新增
另一套完成判定或恢复进度。

签名 capability 与 token SHA 绑定 proxy/authority，没有向令牌数据库添加列或执行 R2 新的
`ALTER TABLE`。`tests/operations/test_worker_exact_dispatch.py:251-270` 冻结并核对原始
`dispatch_capabilities`、`worker_sessions` 列集合。该代码规模不小，但用户已明确要求保留为下一版
加固基座，且它既不接默认路径也不改变当前 schema，现阶段不构成第二权威。后续启用前仍须单独
审查认证注入、原生工具隔离、broker 恢复和进程生命周期。

### 5. 33 项约束与轻量插件目标没有发生新的实质退化

本轮没有新增科学世界图、候选枚举器、固定科研 DAG、资格/current 副本、审批状态副本或插件
专用调度器；科研判断仍由调度/科学智能体承担，控制面只冻结输入、授权、校验、谱系和副作用。
Artifact 不可变性、角色间文件交接、独立审查责任、人工决定权威、确定性变换边界和执行幂等均
由既有回归继续覆盖。

但这里不能写成“33 项已经由一个验证器全部证明通过”：仓库仍没有该验证脚本，实施记录
`docs/plans/R2_UNIFIED_OPERATION_INVOKE_IMPLEMENTATION.zh-CN.md:104-106` 已诚实说明。本报告只能
确认当前 R2 diff 未发现新的权威/谱系/状态机退化；生产级子智能体最小权限仍是明确延后的缺口，
不能用本原型豁免总完成标准。

## 三、测试与变更范围

独立执行结果：

```text
pytest -q tests/artifact_agent/test_platform_configuration.py::
  test_codex_installation_profile_probe_uses_the_compiled_catalog   1 passed
pytest -q tests/operations    63 passed
pytest -q                     94 passed
git diff --check <基线>       通过
```

测试覆盖 spec/catalog 负例、三类 invoke、输入/current 竞态、谱系和幂等、动态领域工具服务端拒绝、
Codex operation 配置、catalog 驱动的安装 profile probe、可选精确派发、Effect UI 门及 8765 回归。
第二轮还以独立临时生成配置执行了“缺失 Worker server”和“工具清单篡改”两个探针负例，均由
目标验证函数拒绝。没有运行真实系统级 `deploy/install.sh` 事务，因为它需要 systemd、服务账户
和安装根写权限；其安装后 Python 判据已由同一公开函数和目标回归执行，shell 已确认直接调用该
函数，不再复制判据。

## 四、紧凑证据审计

### 证据源

| 键 | 来源 | 用途 |
| --- | --- | --- |
| S1 | `.scidiscovery-state/r2-live-prototype-run6/qualification-report.json` 及其列出的原始事件/rollout | 真实运行、角色、工具、文件生命周期和最终状态 |
| S2 | `src/scidiscovery/operations/`、`builtin_plugin.py`、`artifact_agent/runtime.py`、Root/Worker/Task/Execution 实现 | 注册、调用、授权与状态权威 |
| S3 | `src/scidiscovery/platforms/codex.py` 与 run6 生成的 `.codex/` | 父权限继承、operation 角色和 Worker MCP 实现 |
| S4 | `validate_installation_profile()`、`deploy/install.sh:757-775` 与平台配置目标测试 | catalog 驱动的安装后探针 |
| S5 | 两份 R2 计划/实施记录 | 冻结目标、原型例外、下一版安全门和复杂度预算 |
| S6 | 目标测试、`tests/operations/`、全仓 pytest、run2—run4 持久目录 | 自动化回归与失败保存 |

### 核查行

| 核查问题 | 结论 | 证据 |
| --- | --- | --- |
| run6 是否真实 spawn 并完成注册工具、受控写入、校验和封存 | 通过 | S1、S3 |
| 是否新增 OperationRun、平行 registry 或状态机 | 通过 | S2 |
| 提示词白名单是否被冒充为安全隔离 | 通过，但仅限原型口径 | S3、S5 |
| 外部副作用和逐任务 Worker 调用是否仍有服务端硬门 | 通过 | S2、S6 |
| 父权限继承是否适合真实 TCAD/生产执行 | 不适合，当前明确禁止 | S1、S3、S5 |
| 可选精确 Worker 是否接入默认 Root或修改数据库 schema | 未发现 | S2、S6 |
| 安装后的实际配置及篡改负例能否由同源部署探针正确判定 | 通过 | S3、S4、S6 |
| 原型行为约束与下一版平台安全门是否已分离 | 通过 | S3、S5 |
| 复杂度预算记录是否与当前源码一致且总额未扩张 | 通过 | S2、S5 |
| 失败 run2—run4 是否诚实保留 | 通过 | S1、S6 |

## 五、第二轮最终结论

**通过。允许进入 R3。**

第一轮三个条件都有源码、文档和回归证据闭合，第二轮没有发现新的当前阶段阻塞。R3 可以开始，
但本结论不扩大 R2 原型权限：父会话继承 Worker MCP 仍只是首版行为约束方案，不构成生产级最小
授权。R2.18 冻结的平台级工具不可见、网络和兄弟路径隔离、恢复不漂移，仍须在下一版精确 Worker
启用前单独实现和审查；真实 TCAD、生产凭据、网络写入及不可逆动作不得据本报告放行。

本轮修复没有改变 operation 编译摘要、Worker 调用路径或 run6 所执行的 Agent operation，因此
不要求为文档口径和安装后验证函数重跑 run6。后续若这些行为发生变化，原有真实运行证据不能
自动继承。
