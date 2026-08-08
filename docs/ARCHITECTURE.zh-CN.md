# 架构说明

简体中文 | [English](ARCHITECTURE.md)

## 核心原则

SciDiscovery 将科学创意、状态权威和外部副作用分离。主 Agent 负责选择任务，但
不能代替已配置角色生成科学输出；Worker 负责科学内容；确定性代码负责机械变换；
控制面负责身份和生命周期。

## 分层结构

### 1. 交互式主调度器

Codex 或 Claude 主进程理解用户目标、读取受限的 readiness 信号、选择最短且可
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
供主调度器使用的受限信号。

通用角色包括信息提取、假设生成、批判、证据审计、实验设计和诊断。TCAD 插件
增加 Deck 作者、审查者和修订者。

### 4. 确定性变换

以下工作不应依赖 Agent 判断，因此由代码完成：

- 拆分已审批的信息提取结果；
- 生成候选资格和知识更新记录；
- 应用受限 Deck 补丁；
- 比较完整工程并生成不可变 diff；
- 校验审查结果是否对应 exact project；
- 生成 reviewed package 和 runtime attestation；
- 执行领域评分器。

确定性变换不能调用仿真器，也不能发明物理参数。

### 5. 执行桥与领域适配器

一个经过审查的精确 payload 会生成一个 `ExecutionRequest`，人工授权与该请求
绑定。执行桥调用已配置适配器，并把外部状态映射到控制面生命周期。TCAD 适配器
可以本地运行，也可以使用 SSH transport，但不能修改科学对象或审批。

远端 Runner 使用无第三方依赖的 Python，只提供受限文件传输、后台提交、短状态/
取消和终态收集。SSH 不承担长连接作业调度。

## 人工交互

本地审批网页展示精确冻结对象。决定直接写入控制服务；对话 Agent 不能伪造决定，
也不能把聊天文本转换为审批。目前审批对象包括实例绑定、科学基础资料和执行授权。

## 通用与专用边界

| 通用核心 | 领域扩展 |
| --- | --- |
| Artifact、审批、任务、实例和执行服务 | 仿真工程 Schema |
| Root/Worker MCP 协议 | Deck 作者/审查/修订角色 |
| 通用角色 Envelope 与科学 Schema | 打包器与 runtime assertions |
| Codex/Claude 配置生成 | 工具白名单与传输通道 |
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
