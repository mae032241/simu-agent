# R4-A 第三轮独立复审报告

状态：独立复审完成（打回）  
审查对象：第二轮两个阻塞的返工、当前共享工作树、R4-A 第 11 轮真实 Codex 证据  
审查方法：跨边界闭环审查、最小复杂度审查、持久证据逐摘要核验、聚焦与全量测试独立复跑

## 结论摘要

第二轮报告提出的两个阻塞已经在实现层闭合：

1. `parameter_uncertainty` 现在由同一个 compiled catalog 中的确定性 support Operation
   `science.parameter.uncertainty.v1` 正式产生；严格 Schema、coverage 父链、输出父引用、TCAD
   cohort 父链和调度投影均已闭合。测试实际执行
   `coverage → uncertainty → 精确 cohort 审批 → TCAD author`，不再私有注册第七对象；
2. 第 11 轮架构夹具不再假装运行 Sentaurus parser。它生成的控制凭据为
   `diagnostic_layer=runtime`、`qualified=false`；资格报告明确把语法、输入槽解析和执行就绪标为
   `not_claimed`；独立 reviewer 返回 `blocked / unknown / false`。生产
   `TCADDevelopmentDebugBridge` 对缺失槽和错误媒体类型均有失败关闭反例。

首轮七项阻塞也没有发现回归。独立复跑聚焦 54 项、全仓 177 项、静态编译和差异检查均通过；
第 11 轮报告列出的四个 Codex 会话、两个父事件文件和两个空日志摘要全部与实算值相符。真实
author/reviewer 只调用各自精确 Worker 服务，原生命令均为任务根内只读，正式 author→reviewer
交接使用封存 Artifact，reviewer 没有调试能力。

但是，原始父会话证据暴露了一个新的跨边界阻塞：author 子 Agent 的 completion chat 包含
`state/workspaces/ses_...` 绝对路径、内部 session 身份和工程内容摘要；父调度会话把这些内容原样
复制进 `author-parent-final.txt`。reviewer 父会话也直接转述 child chat 中的科学结论。临时
`AGENTS.md` 明确禁止父调度器保留或传递内部 session 身份，并要求 child 返回后只从受控
`task_status` 和已封存输出使用结果。当前 qualification checker 只证明父会话没有调用 Worker，
没有证明它没有把未受控 chat 当作用户可见结果旁路。

正式 author→reviewer 调度本身由外层 harness 查询 `task_status`，所以该缺陷没有污染第 11 轮的
reviewer 输入；但它会向用户暴露可变任务工作区并绕过唯一结果权威，违反文件通信、内部身份不
外泄和“只使用封存结果”的约束。第 11 轮因此不能作为完整的真实父子通信通过证据。

本轮仍需打回，但修复范围已经很小：不需要改 OperationSpec、TCAD 插件或生命周期，只需关闭
父会话 completion chat 的身份/内容旁路，增加检查并重跑持久证据。

## 一、第二轮阻塞 1：正式参数不确定性链已闭合

### 1. 正式 producer 位于唯一 compiled catalog

`src/scidiscovery/general_transform_operations.py:750` 声明
`science.parameter.uncertainty.v1`：

- 所属插件是既有 `general_science`；
- `catalog_scope="support"`；
- executor 是确定性 transform；
- 精确消费 `parameter_requirements`、`device_parameters` 和 `parameter_coverage`；
- 只产生 `scidiscovery.parameter-uncertainty.v1`；
- 不审批、不选择科学值，也不引入外部副作用。

独立编译探针确认：

```text
plugin=general_science
scope=support
executor=transform
operation_digest=306d93fe79935aa725f145b79c279b4f9a9e260b5d85220f0b8575b17be4d59c
```

core 安装态为 15 个 public、14 个 support；full 安装后另增加四个 TCAD public Operation，仍是
同一个 catalog，不存在 uncertainty 私有目录或第二 registry。

### 2. Schema、科学含义和父链是闭合的

`src/scidiscovery/artifact_agent/schema/device_parameters.py:374` 定义四类结果：

- `fixed`；
- `bounded_tunable`；
- `blocking_unbounded`；
- `deferred_unused`。

严格模型校验唯一 parameter key、整体状态与 blocker 一致；有界调参必须同时具有基线和至少两个
离散候选，其他类型不能携带候选。确定性投影还检查 requirements、parameter set、coverage 的
对象键一致、coverage 精确覆盖、单位一致和 requirement 的 assumption policy；无界 required
参数必定产生 blocker，不能靠 prose 推断出连续范围。

`parameter_uncertainty_lineage` 要求 coverage 的父引用包含精确 requirements 和 parameter set；
通用 transform 注册输出时又把三个有序输入全部写入输出父引用。TCAD 的
`parameter_cohort_guard` 进一步要求 uncertainty 的父引用严格等于当前 cohort 中的精确
requirements、parameters、coverage。因此，相同 Schema 的相似投影或另一参数代次不能混入。

### 3. 调度投影已公开组合准入事实

`SchedulerPortView` 现在投影：

- `cohort_id`；
- `approval_kind`；
- `accepted_approval_options`。

实际 catalog 投影显示七个参数端口同属 `approved_parameters`；六个科学基础对象共同要求
`scientific_foundation` 审批，接受 `approve` 或 `approve_with_exception`；确定性 uncertainty
投影本身不重复要求第二次人审。Root 仍对六个精确审批主体执行同组批准校验，插件 guard 再把
第七个投影绑定到其中三个父对象。这里没有第二审批事实或第二 qualification 状态。

### 4. 正式可达测试成立

`tests/operations/test_tcad_operation_plugin.py:646` 的链路实际通过统一 Root API：

```text
science.parameter.coverage.v1
→ science.parameter.uncertainty.v1
→ 对 foundation/requirements/parameters/catalog/coverage/audit 的精确同组审批
→ tcad.deck.author.initial.v1
```

测试仍用私有 helper 准备尚未迁移的上游提取/审查 fixture，但不再用它伪造
`parameter_uncertainty`；coverage 和 uncertainty 都由正式 `operation_invoke` 产生。author 的
成功又间接验证了两级父链 guard。部分 cohort 和未审批 cohort 的负例继续失败关闭。

第二轮阻塞 1 判定：已闭合。

## 二、第二轮阻塞 2：无副作用调试的主张范围已闭合

### 1. 第 11 轮夹具不再产生假资格

`tests/operations/live_r4_tcad_agent_qualification.py:74` 的
`_ArchitectureOnlyDebugAdapter`：

- 校验 `mode` 必须是 `preflight`；
- 校验 project 与 capability 的 profile、solver kind 和 capability digest；
- 不模拟 parser/solver；
- 收集时返回 `diagnostic_layer="runtime"`、空输出和“未运行 Sentaurus parser”的明确摘要。

由既有控制逻辑生成的 `ProjectPreflightAttestation` 因此为 `qualified=false`，没有再把“工具生命
周期成功”转换为“solver 预检成功”。

### 2. 独立 reviewer 正确失败关闭

第 11 轮正式 reviewer 输出为：

```text
verdict=blocked
syntax_fidelity=unknown
execution_ready=false
```

reviewer 明确说明静态阅读不能替代 parser-backed evidence，并只对有边界的实现结构和数值序列
作静态判断。资格报告将：

- `architecture_integration` 标为 `pass`；
- `sentaurus_syntax`、`input_slot_resolution`、`execution_readiness` 标为 `not_claimed`；
- `scientific_claim_admissible` 标为 `false`。

这里的顶层 `verdict=pass` 只表示 23 个架构集成检查全真，不再表示 TCAD 工程科学或运行资格。

### 3. 生产 bridge 的输入槽反例成立

`tests/operations/test_tcad_operation_plugin.py:393` 直接调用生产
`TCADDevelopmentDebugBridge.prepare`：

- 声明 `device_grid` 而 sources 为空时，拒绝为 `no exact task input`；
- 提供同名但 `text/plain` 的 source 时，拒绝为 `media type differs`。

因此第 11 轮 fixture 没有验证的真实输入槽解析由生产边界负例单独覆盖，资格报告也没有冒领该
能力。

第二轮阻塞 2 判定：已闭合。

## 三、第 11 轮持久证据核验

直接核验文件：
`deliverables/r4-a-live-agent/run-20260829-11/qualification-report.json`。

实算摘要全部匹配报告：

- qualification report：`70bb134c56381d4a433b6adc9aa24d2db5ae3a33f8c98ac5df22ad1cd7111de1`；
- 四个 Codex 会话：`3b65f82a…`、`d3a640ea…`、`7abda16a…`、`463c01d3…`；
- author/reviewer 父事件：`940217bd…`、`1569b72d…`；
- control/worker daemon 日志均为空文件摘要 `e3b0c442…`。

原始事件与持久状态证明：

- 两个父会话各调用一次 `spawn_agent` 和一次 wait，没有 Root/Worker 调用；
- author 只调用
  `mcp__scid_worker_tcad_deck_author_initial_v1_f5f264f9f4b8`；
- reviewer 只调用
  `mcp__scid_worker_tcad_deck_review_v1_339f4e3cab03`，没有 debug tool；
- author 的四次 debug receipt 均存在，精确参数为
  `run_name=direct-sdevice-preflight`、`mode=preflight`；
- 所有原生 `exec_command` 均以各自 `state/workspaces/ses_*` 为 workdir，命令仅为 `sed`、
  `find`、`rg --files`、`ls`、`nl` 等只读检查；没有原生写入或任务根逃逸；
- author、计划 reviewer、TCAD reviewer 三个 Task 均在持久数据库中为 `completed/finalized`；
- TCAD reviewer 消费的是已封存 author Artifact，不读取 author session 或 debug 临时输出。

这些证据足以证明真实 spawn、精确 Worker server、领域工具可调用、任务根原生只读和独立
reviewer 文件交接。

## 四、新阻塞：父会话把 completion chat 变成内部身份与结果旁路

### 可复现证据

临时项目的 `AGENTS.md:43` 明确规定：

> 父调度器不得请求、保留、复制、推断或传递内部 record、hash、token、session 或 external-run
> identity。

同一文件约在 `:176` 又规定：child 返回后必须读取 `task_status`，只有 control 报告 completed
时才使用任务输出或有界 signal。

但原始证据中：

- author child completion chat 列出
  `.../state/workspaces/ses_099a075367ac4713a40029af63bae3e2/deck/...` 四个绝对路径，包含内部
  session identity；
- `author-parent-final.txt` 把这些绝对路径和“生成了哪些文件、完成了哪种预检”的 child 摘要
  原样复制给用户；
- reviewer child completion chat 直接给出 `blocked` 及其科学理由，
  `reviewer-parent-final.txt` 在没有读取受控 `task_status` 的情况下直接转述；
- `_run_parent` 的固定 prompt 只禁止父会话调用 Root/Worker 和代做，没有要求忽略 child chat；
- qualification 的 23 项检查只验证父会话没有 Worker 调用，没有检查 parent final 是否包含
  `state/workspaces`、`ses_*`、任务内部路径或 child 科学内容。

### 影响

正式外层 harness 确实随后查询了 `task_status`，并以封存 Artifact 调度 reviewer，所以本次
author→reviewer 输入未被旁路污染。但是用户在此之前已经收到一条未经 control 查询的 chat
结果，并得到可直接打开的任务工作区路径。该路径不是不可变 Artifact，也不是稳定语义名；工作区
可能处于重试、被清理或与正式输出不同。

因此当前真实证据同时存在两条结果传播面：

```text
正式：Worker 文件 → validate/finalize → Artifact → task_status → downstream Operation
旁路：child completion chat → parent final → 用户
```

旁路不能获得审批或 downstream admission，但会破坏“Agent 间文件交接、内部身份不外泄、用户只
接收受控状态”的设计承诺，并可能诱使用户根据未封存内容行动。这不是措辞风格问题，而是结果
权威和最小上下文边界问题。

### 最小修复要求

不需要新增状态、Schema 或注册表：

1. `_run_parent` 的真实验收 prompt 明确要求 wait 后不得复制 child completion 的路径、身份、
   科学摘要或 verdict；父 final 只能输出一个固定的有界生命周期信号；
2. compiled Worker 通用提示补充：formal output 完成后，chat completion 只报告“已完成受控
   提交”，不得列出任务根、session、内部文件路径或重述科学 payload；
3. qualification checker 对 parent final 和 parent events 增加反例：出现 `state/workspaces/`、
   `ses_`、`tsk_`、`art_`、内部绝对路径或 child payload 摘要时失败；同时保留“父会话只
   spawn/wait”的检查；
4. 重跑持久证据。外层 harness 继续从 `task_status` 和封存 Artifact 取得 author/reviewer 结果，
   不能从 parent final 取得科学结论。

## 五、首轮七项阻塞与架构目标回归

| 检查项 | 第三轮判断 | 证据 |
| --- | --- | --- |
| 正式实验计划审查端口 | 无回归 | materialize→精确 plan review→TCAD author 正负测试仍通过。 |
| legacy TCAD role 双权威 | 无回归 | TCAD 包不发布 `agent_role_packs`；调度说明只使用四个 catalog Operation。 |
| 参数 cohort | 原阻塞已闭合 | 正式 uncertainty producer、调度投影、审批和父链均成立。 |
| 静态 Sentaurus 合同 | 无回归 | author/reviewer/SDevice 合同仍是可达 prompt resource 并进入 digest。 |
| author heartbeat | 无回归 | author 工具含 heartbeat；lease/absolute budget 测试通过。 |
| operation-aware snapshot | 无回归 | debug 拒绝走通用快照入口，新 attempt 恢复测试通过。 |
| finalizer 确定性 | 无回归 | 目录和最终路径双排序，跨创建顺序字节与摘要一致。 |

同时确认：

- TCAD 四个 Agent Operation 仍只从 `tcad_artifact` 的一个标准插件入口注册；
- OperationSpec 仍是不可变行为闭包，workspace、file policy、finalizer、snapshotter 和 debug 是
  窄注册组件，不是巨型 Operation 类；
- TaskService、Worker router 和 Codex 平台未新增 TCAD role/context/Schema/import 分派；
- 没有新增数据库表、第二 Task/Approval/Qualification 状态机或第二 catalog；
- uncertainty 是有科学含义、可重算且有父链的确定性 Artifact，不是新的 current/qualification
  权威；
- 未提前实现 R4-B 的 TCAD transform/effect 迁移或 R4-D 的 UI 合同。

## 六、独立测试结果

- 聚焦测试：`54 passed in 34.11s`；
- 全仓：`177 passed in 65.43s`；
- `python -m compileall -q src plugins/tcad_artifact/tcad_artifact tests/operations`：通过；
- `git diff --check`：通过；
- core-only、architecture fixture、full 安装态和插件静态导入测试：通过。

测试全绿不抵消第四节由原始父事件和 final 文件直接证明的通信旁路。

## 七、非阻塞债务与简化判断

### 1. 核心复杂度预算仍需 R5 收敛

当前 `spec.py/catalog.py/invoke.py` 为 `348/462/430`，合计 1240 行；R5 完成门仍要求不超过
1200。新增 cohort 调度投影和确定性 uncertainty producer 是可解释的闭包事实，没有形成第二
系统；本轮不为凑行数删除必要校验，但 R5 必须通过删除旧重量实现净下降。

### 2. 实施记录中的数字已过时

`R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md` 仍写 `spec.py=339`，当前实数为 348。文档还应明确
`public=15/support=14` 指 core 安装；full 安装另有四个 TCAD public Operation。此项不改变运行
权威，但送下一轮审查前应修正。

### 3. 第 11 轮 author 指令有一句歧义

持久 instruction 连成“没有该工具由架构夹具实现……提供网格内容”，而该轮实际上没有绑定网格
内容，报告也明确不声称 input slot resolution。应改为“该工具由架构夹具实现……没有提供网格
内容”。生产 bridge 负例已经覆盖真实槽解析，因此该文字错误不单独构成实现阻塞。

### 4. 上游参数 fixture 尚未全部改成真实 legacy Worker 产物

参数链测试仍用 helper 准备 foundation、requirements、parameters、catalog 和 audit，因为这两个
设备参数 Agent bridge 尚在计划明确的 legacy 边界。测试已经真实执行本轮要求的
coverage→uncertainty→批准 cohort→author，故不构成本轮阻塞；R4 后续迁移 bridge 时仍需一条
完整真实 Worker 链，不能把当前 fixture 宣称成参数提取端到端实证。

### 5. 任务根限制仍是原型行为约束

第 11 轮证明 Agent 实际遵守了任务根只读约束，但 `inherited_prototype` 不是 OS 级逐 Operation
沙箱。此边界已经在 R2 冻结，本轮没有扩大其主张范围；真实凭据和不可逆外部副作用仍不能因此
放行。

## 八、再次送审的最小门槛

1. 关闭 completion chat→parent final 的内部身份和科学内容旁路；
2. 新增 parent final 正负检查，并持久重跑 author→debug→独立 reviewer；
3. 新一轮报告继续明确架构夹具不声称语法、输入槽解析、执行就绪或科学资格；
4. 聚焦、全仓、安装态、compileall 和 diff 检查继续通过；
5. 独立审查者直接核验新会话和父事件后，方可进入 R4-B。

## 最终判定

打回，不允许进入 R4-B
