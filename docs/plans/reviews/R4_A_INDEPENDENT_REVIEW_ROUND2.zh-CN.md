# R4-A 第二轮独立复审报告

状态：独立复审完成（打回）  
审查对象：首轮七项阻塞返工、当前共享工作树、R4-A 第 5—10 轮真实 Codex 验收证据  
审查方法：跨边界闭环审查、最小复杂度审查、持久证据逐哈希核验、聚焦测试与全量测试复跑

## 结论摘要

首轮七项阻塞中，实验计划审查链、legacy role 双权威、静态 Sentaurus 合同、heartbeat、
operation-aware 快照和 finalizer 确定性六项已经闭合。参数 cohort 也已经有了领域无关的
all-or-none 与同审批准入机制，但它的 TCAD 实例化新增了一个没有正式生产者的
`parameter_uncertainty` 对象；现有参数六件套无法调用四个 TCAD Operation，只有测试用私有
`_register` 才能构造“成功”样例。同时，调度目录投影没有公开 cohort 分组和审批合同，调度器
看到的是七个互不相关的可选端口。这使参数化 TCAD 的正式路径仍不可达，是首轮阻塞 3 的
样例特化式修复，而非真实闭合。

第 10 轮真实 Codex 证据在进程与权限层面可信：报告列出的四个会话、两个父事件文件和日志摘要
均与文件内容相符；父会话只执行一次 `spawn_agent` 和等待；author/reviewer 子会话只调用各自
精确 Worker 服务，原生命令均为任务根内只读，所有写入走 Worker 文件生命周期。第 5—9 轮的
失败也保留并能解释第 10 轮的修订，没有发现通过放宽越界或原生写入检查器掩盖行为的证据。

但是，第 10 轮的无副作用 adapter 不读取 capability、sources 或 mode，也不检查 Sentaurus
语法，却返回 `diagnostic_layer="complete"`。正式 reviewer 随后把该控制凭据解释为语法就绪，
给出 `syntax_fidelity="pass"` 和 `execution_ready=true`。这超过了无副作用 fixture 能支持的
主张范围，也没有证明生产 adapter 所要求的输入槽实物解析。验收可以证明“注册工具确实被真实
Agent 调到并走完控制生命周期”，不能证明“SDevice 语法已预检或工程可执行”。当前报告把前者
与后者混在同一个通过门中，因此真实验收证据也需要收窄并重跑。

所以，R4-A 的主体方向和大部分实现已经成立，但仍有两个阻塞：一个是正式参数链不可达，一个是
真实验收对无副作用调试结果作了超范围资格解释。不能进入 R4-B。

## 独立核验范围与结果

### 代码、安装态与测试

独立执行：

- `pytest -q tests/operations/test_tcad_operation_plugin.py tests/operations/test_catalog_installed_entrypoint.py tests/operations/test_baseline_plugin_discovery.py tests/artifact_agent/test_platform_configuration.py`：`22 passed in 31.54s`；
- `pytest -q`：`175 passed in 64.59s`；
- `git diff --check`：通过；
- `python -m compileall -q src plugins/tcad_artifact/tcad_artifact tests/operations`：通过。

检查 TaskService、Worker 路由和 Codex 平台后，未发现新增按 TCAD role、context、Schema 或
`tcad_artifact` import 决策的核心分支。`tcad_artifact` wheel 只以一个
`scidiscovery.plugins` 标准入口声明四个 Agent Operation；旧 transform adapter 仍留在 R4-B
边界，未成为第二个 Agent 调度权威。

### 第 10 轮持久证据

直接核验了
`deliverables/r4-a-live-agent/run-20260829-10/qualification-report.json` 以及它列出的文件。
独立重算所得摘要与报告全部一致：

- 四个 Codex 会话：`fa3ada94…`、`613df08b…`、`55aae9bf…`、`4563d472…`；
- author/reviewer 父事件：`474a3e80…`、`bfbcd790…`；
- control/worker daemon 日志均为空文件摘要 `e3b0c442…`。

事件级复核得到：

- 两个父会话各只有一次 `spawn_agent` 和一次等待，没有 Root/Worker 工具调用，也没有代写结果；
- author 子会话只调用
  `scid_worker_tcad_deck_author_initial_v1_c78d0b59d109`，真实调用七次注册的
  `worker_tcad_debug_run`，并完成受控写入、补丁、校验和封存；
- reviewer 子会话只调用
  `scid_worker_tcad_deck_review_v1_d33588319bca`，没有 debug 能力或 debug 调用；
- 两个子会话的原生命令 workdir 均落在各自物化的任务根，命令是 `sed`、`rg`、`find`、
  `ls`、`nl` 等只读操作；没有原生重定向写入、仓库搜索或任务根逃逸；
- author 与 reviewer 是不同 Agent 类型，reviewer 读取的是已封存 author 项目，不继承 author
  工作区或临时调试文件。

持久状态进一步证明了以下父链：

```text
science.experiment.materialize.v1
→ science.object.review.v1（精确计划审查）
→ tcad.deck.author.initial.v1
→ tcad.deck.review.v1（精确项目独立审查）
```

任务、Artifact、父引用和 control 生成的预检凭据均可在该轮状态库与 CAS 中对应起来。

### 第 5—9 轮失败是否被“放宽检查器”掩盖

未发现这种证据：

- 第 5—6 轮真实暴露 reviewer/author 越出任务根搜索；第 10 轮原始会话没有重复这些行为；
- 第 7 轮权限检查已通过，但 reviewer 因 `device.tdr` 未由输入槽声明而要求修订；第 10 轮项目
  显式声明 `device_grid → device.tdr`；
- 第 8 轮只是检查器把任务根内安全的 `..` 误当逃逸。修订后的检查器按解析后路径判定，新增
  反例仍拒绝真实越界、错误 workdir 和原生写入；
- 第 9 轮因使用 initialization 而没有计划要求的 preflight；第 10 轮原始工具事件明确为
  `run_name=direct-sdevice-preflight`、`mode=preflight`；
- 第 8—10 轮 author/reviewer Operation digest 相同，第 10 轮没有为通过样例暗改 Operation
  权限闭包。

检查器本身没有被简单放宽；剩余问题是 fixture 所声称的语义强于它实际执行的检查，见阻塞 2。

## 首轮七项阻塞逐项复核

| 首轮阻塞 | 第二轮状态 | 复核结论 |
| --- | --- | --- |
| 1. 正式实验计划无法进入 TCAD author | 已闭合 | 四个 TCAD Operation 均有 `experiment_review` 端口；真实 materialize→review→author 链成功，缺失、错对象和未通过结论负例存在。 |
| 2. legacy TCAD role 仍是调度权威 | 已闭合 | TCAD 包不再发布 `agent_role_packs`；当前 `AGENTS.md`/scheduler 只调 catalog Operation 并禁止退休 role；安装态没有这两个 legacy role。 |
| 3. 参数 cohort 未迁移 | 未闭合 | 通用准入已实现，但 TCAD cohort 增加无 producer 的 `parameter_uncertainty`，正式六件套仍被拒；调度投影还隐藏 cohort 关系。 |
| 4. Sentaurus 指导未进入编译闭包 | 已闭合 | author/reviewer prompt 由角色正文、对应静态合同和 SDevice 合同拼接；资源可达且内容摘要进入 Operation digest；真实 Agent 不再依赖宿主隐式 skill。 |
| 5. 1200 秒 author 无 heartbeat | 已闭合 | author 工具含 heartbeat；可控时钟测试验证只延长 lease、不越过绝对预算；第 10 轮工具投影也包含它。 |
| 6. debug 拒绝快照绕过 snapshotter | 已闭合 | debug 调用 TaskService 的唯一 operation-aware 快照入口；拒绝快照包含 deck，新 attempt 可恢复；错误保持有界。 |
| 7. finalizer 顺序不确定 | 已闭合 | `os.walk` 目录和最终 `relative_path` 均排序；跨创建顺序测试的正式字节和摘要相同。 |

## 阻塞问题

### 阻塞 1：参数 cohort 存在不可生产对象，且其组合合同不在调度投影中

证据：

- TCAD 四个 Operation 把以下七个端口放入同一 `approved_parameters` cohort：
  `scientific_foundation`、`parameter_requirements`、`device_parameters`、`source_catalog`、
  `parameter_coverage`、`parameter_audit`、`parameter_uncertainty`，见
  `plugins/tcad_artifact/tcad_artifact/plugin.py:396`；
- Root 的通用准入在任一成员出现时要求七个成员全部存在，否则返回
  `input_cohort_incomplete`，见
  `src/scidiscovery/artifact_agent/interfaces/mcp_root.py:2618`；
- 全仓搜索中，`scidiscovery.parameter-uncertainty.v1` 没有 Operation、transform 或其他正式
  producer。唯一成功样例在 `tests/operations/test_tcad_operation_plugin.py:613` 直接调用测试
  私有 `_register`，手工写入 `{"status":"ready"}` 和预期父引用；
- 当前真实设备参数链已经产生并共同审批 foundation、requirements、parameters、catalog、
  coverage 和 audit 六个对象；`DeviceParameterSet` 本身已经承载 epistemic/tuning 不确定性信息。
  因此第七个 projection 不是缺失的关键科学输入，而是没有生命周期的派生门禁实体；
- `SchedulerPortView` 只投影端口名、描述、Schema 和基数，未投影 `cohort_id`、审批类型或可接受
  选项，见 `src/scidiscovery/operations/spec.py:263`。调度器看到七个 `min_items=0` 的独立端口，
  直到 preflight 才知道它们必须整组出现。

影响：

- 不带参数的第 10 轮可以成功，所有真实 parameter-aware TCAD 调用却不可达；
- 自动化“成功”依赖生产路径不存在的手工 Artifact，属于验收样例特化；
- 组合准入只存在于隐藏的 invocation 合同与调度 prose，违背“唯一 catalog 驱动调度”和低成本
  插件接入目标；
- 新增 `ParameterUncertaintyProjection`、Schema、validator、端口和父链 guard 没有带来新的
  可辨识科学信息，反而增加控制层负担。

最小修复要求：

1. 从 R4-A 参数 cohort 删除无正式 producer 的 `parameter_uncertainty` 投影，复用现有六件套、
   `DeviceParameterSet` 的不确定性字段以及 coverage/audit 结论；除非先证明该对象不可由现有对象
   表达，并给出同一 catalog 中可达的确定性 producer；
2. 在唯一 scheduler catalog 投影中公开最小 cohort 标识和同组审批要求，使调度器能一次绑定完整
   组；不得另建 registry、TCAD readiness 分支或 prose-only 拓扑；
3. 用正式 producer 链而非 `_register` 构造正例，证明现有六件套经同一精确审批可进入 author 和
   reviewer；部分组、混组、审查父链错误、未审批继续 fail-closed。

### 阻塞 2：无副作用 debug fixture 被解释成语法预检和执行就绪证据

证据：

- `tests/operations/live_r4_tcad_agent_qualification.py:75` 的 `_NoEffectDebugAdapter.prepare`
  明确丢弃 `capability`、`sources` 和 `mode`，只复制项目 JSON；`collect` 无条件返回
  `terminal_state="succeeded"`、`exit_code=0`、`diagnostic_layer="complete"`；
- 生产 `plugins/tcad_artifact/tcad_artifact/debug_adapter.py:170` 会按每个 `input_slot` 从精确任务
  sources 解析内容，缺失 `device_grid` 时会拒绝。第 10 轮没有绑定网格内容，fixture 因忽略
  sources 才能通过；
- Worker 工具结果诚实包含 `scientific_claim_admissible=false`，任务说明也限定“不作物理主张，
  不验证结构初始化或完整求解”；
- 但已封存 reviewer 输出称该无副作用 preflight “支持语法就绪性判断”，并给出
  `syntax_fidelity="pass"`、`execution_ready=true`；资格报告又把 `review_passed` 作为 22 项总通过
  条件。无副作用 adapter 没有执行能支持这些判断的观察。

影响：

- 第 10 轮可信地证明了 Agent 派发、工具注册、任务根、受控写入、凭据生成和独立 reviewer
  机制，但不能证明 Sentaurus 语法、真实输入槽解析或工程执行准备度；
- 临时运行结果虽然标为不可用于科学主张，却通过 control attestation→reviewer 进入正式结果，
  形成资格语义旁路；
- 若把该证据作为 R4-A 完整闭环通过依据，会混淆“模拟成功的控制集成测试”和“被实际观察支持
  的领域资格”。

最小修复要求：

1. 保留无副作用 adapter 作为 R4-A 快速集成测试，但资格报告必须显式声明它只证明工具与控制
   生命周期；不得把 fixture success 当作 Sentaurus 语法或执行就绪证据；
2. reviewer 不得以该 fixture attestation 支持 `syntax_fidelity` 或 `execution_ready`。可依据静态
   源码审查作有边界的实现判断，但必须把缺少真实 parser/solver 和网格内容列为缺失输入；
3. 增加一个与生产 preparation 合同一致的负例，证明缺失或媒体类型错误的输入槽在 adapter
   边界被拒绝。若 preflight 模式按设计只检查声明而不需要实物，则应把这一差异正式写入同一
   adapter 合同并让生产实现与 fixture 一致；
4. 重跑真实 author→debug→独立 reviewer，并让持久报告区分“控制集成通过”与“领域资格未主张”。

## 已通过的架构目标

除上述两个阻塞外，本轮没有发现以下目标的 R4-A 级缺陷：

- 四个 TCAD Agent 行为仅从 `tcad_artifact` 的单一标准插件入口进入同一个 catalog；
- OperationSpec 仍是行为闭包，workspace materializer、文件策略、finalizer、snapshotter 和 debug
  都是窄注册组件，不是 Operation 巨类；编译器拒绝未使用、重复或错误类型组件；
- 可达 prompt、Schema、语义合同、工作区钩子和 worker tool 的声明及资源摘要均参与
  compiled digest；静态 Sentaurus author/reviewer/SDevice 合同确实进入 author/reviewer 摘要；
- debug 只由三个 author Operation 声明；reviewer 无该工具，服务端还校验精确
  operation/task/attempt capability 与工具名，未发现跨插件工具授权漂移；
- TaskService 调用通用钩子并保持既有 Task/Artifact/Approval/Worker 生命周期；没有新增数据库表、
  权限状态机、重复重试状态或第二 registry；
- author→独立 reviewer 的文件交接、控制校验、封存、幂等调用、拒绝快照和新 attempt 恢复在
  被测路径上闭合；
- core-only/full 安装态成立，TCAD 插件静态导入成功；
- 未提前实现 R4-B 的 transform/effect 迁移，也未提前实现 R4-D 的审批 UI 编译合同。

## 非阻塞债务与复杂度判断

### 1. 插件目录隔离仍是受信任代码边界

钩子接口只传任务私有根、显式输入和本任务 provisional roots，没有传 ArtifactService、数据库、
仓库根或兄弟任务句柄。这证明“接口最小授权”，不证明同进程 Python 插件在恶意情况下具有 OS
级隔离。当前原型可接受，但文档应持续使用“已安装插件是受信任代码”的准确表述。

### 2. 原生工具限制是可审计提示边界，不是强沙箱

第 10 轮证明真实 Agent 遵守任务根只读约束；Codex 仍运行在 `inherited_prototype` 权限模型，
不是操作系统强制的逐 Operation 沙箱。这符合已经冻结的快速原型边界，但不能据此放行真实外部
副作用或不受信插件。

### 3. 核心增长需要在参数修复后重新核算

当前 `spec.py/catalog.py/invoke.py` 为 `339/462/430`，合计 1231 行；计划已经诚实披露相对
`320/450/430` 的 31 行增长，主要来自 cohort/审批字段、编译校验和最大尝试次数。heartbeat、
`max_attempts` 与最小 cohort 准入本身是通用闭包事实，不构成第二系统；但不可生产的 uncertainty
投影证明当前实例化有复杂度反噬。完成阻塞 1 的删除/收窄后再按 R5 的 1200 行门统一核算，不应
仅为行数压缩可读的通用校验，也不应为保存第七个对象继续扩展核心。

### 4. R4 文档存在一处过时表述

`R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md:36` 仍称 TCAD `agent_role_packs` 在 R4-A 保留，
而当前 wheel 已不再发布该入口。运行权威没有双写，属于文档债务；复审修复时应改成“旧角色
正文仅作为编译 prompt 资源保留，不作为 entry point 或调度权威”。

## 再次送审的最小门槛

1. 删除或正式生产 `parameter_uncertainty`，并用正式六件套 producer/审批链证明参数化 author 与
   reviewer 可达；
2. catalog 的调度投影公开最小 cohort/审批组信息，不新增第二目录或领域 readiness 分支；
3. 重跑真实 Codex 链，限定无副作用 adapter 的主张范围，消除 reviewer 对 fixture 的语法/执行
   就绪背书，并补输入槽 adapter 负例；
4. 聚焦测试、175 项全量回归、安装态、静态编译和差异检查继续通过；
5. 由独立审查者直接核验新的持久会话与摘要后再决定是否进入 R4-B。

## 最终判定

打回，不允许进入 R4-B
