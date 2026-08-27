# 架构说明

简体中文 | [English](ARCHITECTURE.md)

## 核心原则

SciDiscovery 将科学创意、状态权威和外部副作用分离。主 Agent 负责选择任务，但
不能代替已配置角色生成科学输出；Worker 负责科学内容；确定性代码负责机械变换；
控制面负责身份和生命周期。

## 分层结构

### 1. 交互式主调度器

Codex 主进程理解用户目标、读取受限的 readiness 信号、选择最短且可
辩护的角色拓扑，并派发就绪任务。它只使用语义名称，不接触内部 Artifact、任务、
审批、会话、执行或远端运行 ID。

### 2. SciDiscovery 控制面

控制服务负责：

- 内容寻址、不可变 Artifact 及来源关系；
- ResearchInstance 范围内的语义名称绑定；
- 任务创建、Assignment Instance、尝试次数、租约和终态；
- 上下文 profile 与 `full`、`on_demand`、`handoff_only` 暴露级别；
- 精确人工审批和进程到实例的绑定；
- 执行请求和返回结果的注册。

控制面不判断科学真伪，也不编写仿真 Deck。

#### 科学资格内核 v2

新建 ResearchInstance 使用一套 fail-closed 的唯一权威模型：

- 工作开始前由 `OperationIntent` 准入精确、不可变的请求；
  `OperationReceipt` 发布完整可消费结果，永久失败或取消则由
  `OperationTerminalRecord` 闭合。
- `ScientificReviewIntent` 冻结一组精确、可见的审批对象；本地 UI 决定被解释为
  `ScientificReviewOutcome`。只有 accepted outcome 才能签发实例级
  `QualificationReceipt`，撤销采用 append-only 记录。
- `ActiveHead` 是 current 对象的唯一权威。revision 顺序、完成时间、label、parent
  关系和历史审批都不能隐式把对象变成 current。
- 外部执行使用持久 effect outbox 和明确的 unknown 状态；提交结果不确定时只能
  reconciliation，不能自动重提。
- readiness 与真正授权共用同一合同 preflight，检查精确 Receipt、Qualification、
  head snapshot、参数 uncertainty 和 adapter 可用性。

每次语义发布都能由不可变请求 fingerprint 恢复。维护可达性覆盖 Intent、Receipt、
Review、Qualification、ActiveHead、reservation 和 effect outbox。v2 实例存在任一
未闭合、可恢复操作时，关闭动作会在同一个数据库事务内被拒绝。

控制协议版本属于 ResearchInstance。迁移得到的 v1 实例只读并拒绝新的科学变更；
需要在新建 v2 实例中重新资格化，不能静默继承旧权威。

### 3. 科学 Worker

每个角色只接收一份去身份化 Assignment，其中包含任务本地输入别名、资源限制和
精确 JSON Schema。Worker 只能读取被分配的文件和工具，并返回统一的
`RoleResultEnvelope`：

```json
{
  "schema_version": 1,
  "handoff": {
    "verdict": "pass",
    "summary": "受限调度信号",
    "assumptions": [],
    "missing_inputs": [],
    "next_actions": []
  },
  "payload": {}
}
```

`payload` 使用角色专用 Schema。控制面校验并注册 payload，再从 `handoff` 生成
供主调度器使用的受限信号。对于 scientific-paper-evidence bundle，handoff 必须绑定
最终 staged collection 字节的确定性 fingerprint；控制面从已验证的最终
manifest/report 投影 figure 摘要、ambiguity 和固定 audit 动作，不再信任可滞后的提取
过程文字。

`worker_materialize_assignment` 返回明确的本地路径，Worker 使用原生文件和检索
能力只读查看。所有变更通过当前 session 绑定的 MCP 文件服务完成：局部修订应用
带上下文校验的 unified diff，新建文件采用有上限的分块写入，并且只能命中角色声明
的任务相对路径。随后由 validate/finalize 冻结受控文件树。

通用角色包括信息提取、假设生成、批判、证据审计、实验设计和诊断。TCAD 插件
增加一个同时承担初始编写与受限修订的 Deck author，以及独立代码 reviewer。

对带精确 SProcess capability 和 experiment plan 的新任务，author 只可修改
`deck/files/**` 与简短 handoff。`deck/project.json`、case/global bindings、单位、源码
locator、realization manifest、raw-output 合同、capability identity、arguments 和资源策略
均为控制层只读投影。版本化 TCAD materializer 从 exact plan、capability 和当前源码生成
规范工程，并在 validate/debug 前返回带 case、变量、文件和行号的 reason-code finding。
完整注释不能充当可执行 binding，scorer/diagnosis 控制量不会进入 deck 合同。

### 4. 确定性变换

以下工作不应依赖 Agent 判断，因此由代码完成：

- 拆分已审批的信息提取结果；
- 生成候选资格和知识更新记录；
- 将 worker 编写的紧凑 `ExperimentDesignIntent`（基准值与少量 case override）
  确定性展开为完整严格的 `ExperimentPortfolio`，统一生成 case settings、比较
  expectations、factor 清单、case 数量和绑定输入哈希的物化报告；
- 冻结 author 的受控工程文件树并比较完整修订；
- 从 exact TCAD 源码物化 case bindings、单位、manifest、locator、raw-output 合同和
  source digest；
- 比较完整工程并生成不可变 diff；
- 校验审查结果是否对应 exact project；
- 记录 source-bound bounded preflight attestation；reviewer 不复制 capability digest、
  不逐行重填 manifest，也不自行声明 syntax qualification；
- 生成同时绑定 `SolverCapability` 摘要和精确实验计划的
  `tcad.reviewed-deck-package.v2`，并在执行前拒绝缺失科学case控制绑定的工程；
- 从 reviewed package 物化可信 realization snapshot，并比较控制等价性；
- 校验类型化 `StudyExecutionPlan` 的 case 覆盖和 SProcess→SDevice DAG；
- 按 ArtifactRef 校验、暂存二进制输入，并生成分层 runtime attestation；
- 执行领域评分器。

确定性变换不能调用仿真器，也不能发明物理参数。
Intent 只是临时科学对象，不能被选择为 current experiment plan。只有物化后的
完整 portfolio 才能进入 deck 编写、评分、打包或诊断。历史完整 portfolio 继续
兼容；新 experiment designer 任务默认使用紧凑合同。

直接 SProcess/SDevice deck 的职责止于 solver 代码和原始 TDR/PLX/PLT/log 输出，
不得重采样曲线、应用证据 mask、计算派生指标、判断阈值或生成科学结论。执行桥只
校验生命周期和原始输出的不可变完整性；版本化领域 scorer 负责执行后确定性计算；
diagnostician 负责解释。上下文 finalization validator 会把 deck author/reviewer 输出
与其 exact project 输入交叉校验，含 unsupported 或后处理职责的 deck 不能先获得正式
pass、再拖到 package 阶段才失败。Package 会对 exact source/plan/capability 重跑
materializer，并要求同一 source digest 的 preflight pass 与独立代码/物理 review pass。

### 5. 执行桥与领域适配器

一个经过审查的精确 payload 会生成一个 `ExecutionRequest`，人工授权与该请求
绑定。执行桥调用已配置适配器，并把外部状态映射到控制面生命周期。TCAD 适配器
可以本地运行，也可以使用 SSH transport，但不能修改科学对象或审批。

生产 TCAD adapter 只接受 reviewed package v2。package、JobSpec 和 runner policy
绑定同一 capability 摘要；executable、固定参数、环境、solver kind 或发行版证据
发生漂移时，runner 在启动求解器前失败关闭。SDevice 的 TDR 等二进制输入只通过
内容寻址 ArtifactRef 和精确 slot 暂存，不内嵌进 Worker JSON。

远端 Runner 使用无第三方依赖的 Python，只提供受限文件传输、后台提交、短状态/
取消和终态收集。SSH 不承担长连接作业调度。

## 人工交互

本地审批网页展示精确冻结对象。决定直接写入控制服务；对话 Agent 不能伪造决定，
也不能把聊天文本转换为审批。目前审批对象包括实例绑定、科学基础资料和执行授权。

网页不是由 AI 动态生成。Agent/Worker 只产生经过 Schema 校验的结构化 Artifact；
`approval_ui/render.py` 中的固定 Python 渲染器按白名单 Schema 选择视图、转义内容并
生成 HTML。未知结构只能进入受限的通用树/下载视图，不能提交 HTML、JavaScript 或
模板代码。

定量证据提取、修订和独立审计属于一个临时证据链，中间版本不逐项要求人工审批。
只有审计接受、修订关闭后的最终 ScientificFoundation、提取结果、全部附件和最终
审计报告组成一次科学证据审批。会触发外部副作用的执行授权仍独立审批。

审批首页同时列出 ResearchInstance。实例详情展示该实例全部历史审批状态、最终选项、
理由和决定时间。删除实例需要打开详情页预览影响范围、输入完整实例名并提交一次性
令牌；运行中的任务/执行会阻止删除。删除会撤销会话并清理实例绑定、专属任务、审批、
执行及专属 Artifact 注册；其他实例仍引用的对象保留。Artifact 注册与删除共用跨
进程文件锁；只有没有任何保留注册引用同一摘要时，专属 CAS 字节才会被解除链接。
异常中断留下的孤儿字节仍可由离线 orphan 扫描发现。

## 通用与专用边界

| 通用核心 | 领域扩展 |
| --- | --- |
| Artifact、审批、任务、实例和执行服务 | 仿真工程 Schema |
| Root/Worker MCP 协议 | 合并后的 Deck 编写/修订角色与独立代码审查角色 |
| 通用角色 Envelope 与科学 Schema | solver 工程与 reviewed-package 校验 |
| Codex 配置生成 | 工具白名单与传输通道 |
| 上下文隔离与网页证据冻结 | 领域评分器或基线变换 |

领域插件不得复制控制面的身份或生命周期状态。

## 持久化与迁移

运行数据位于源码目录之外，默认在 `/var/lib/scidiscovery`。SQLite 保存注册表和
生命周期，CAS 保存不可变内容；服务密钥位于 `/etc/scidiscovery`。生成的平台配置
包含机器绝对路径，因此每台设备必须重新生成。

源码迁移与科学状态迁移相互独立。可选的 ActiveResearchBundle 只导出显式选择、
去身份化的科学 Artifact，不恢复任务、审批、会话或执行状态。

## 信任边界

- Worker prompt 和 JSON 校验提高正确性，但不是安全边界。
- 控制面绑定身份、不可变输入和状态变更。
- 本地审批网页将人工决定绑定到精确对象。
- 领域执行策略限制 executable、arguments、environment、资源和输入目录。
- 科学接受仍然需要证据、预注册检查以及独立结果诊断。
