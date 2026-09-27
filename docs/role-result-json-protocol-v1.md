# 角色结果 JSON 协议 v1（Run 主干）

更新日期：2026-09-03
状态：当前规范

## 1. 目的

所有 Agent Operation 使用同一种文件交接方式。专业 Agent 只填写科学内容和有界交接信号；控制面
负责 Run 身份、状态、合同校验、不可变 Artifact 登记、current CAS 和编译 review edge。Agent
不得抄写或接收内部 Artifact、Run、Approval、token、session、摘要或外部执行身份。

## 2. Run 工作区

每个 Run 的私有工作区至少包含：

```text
workspace/
├── assignment.json
├── inputs/                 # 精确绑定、只读
├── schema/result.schema.json
└── output/result.json      # 唯一正式 Agent 输出
```

Agent 必须先调用 `worker_open_assignment`，再读取 assignment、结果 Schema 和其中明确列出的输入；
不得从共享项目目录递归发现额外上下文。需要长时间运行时可以调用 `worker_heartbeat` 报告存活，但它
不能延长绝对预算。完成后调用 `worker_submit_result`；只有该调用返回 completed 且 Root 的
`run_status` 为 completed，封存结果才是科学输出。聊天回复不是科学结果。

默认 `LocalTrustedBackend` 允许可信本地 Codex 在该工作区内使用编译 Operation 声明的原生工具和
领域工具。它不提供技术级原生文件隔离，因此只适用于本地开发、可逆文件和无生产凭证场景。

显式 `HardenedWorkerBackend` 不允许原生 shell、代码工具或 `view_image`；文本创建、补丁、JSON
补丁、移动和删除由该后端注册的 `worker_file_*` 工具完成。它与 Local 使用同一个 OperationSpec、
CompiledCatalog、preflight、RunService 和 Artifact/current 权威，不是第二套结果协议。

Run v1 只支持一个主输出 `output/result.json`。声明 Agent collection 输出的 Operation 会在目录中
标记为当前后端不可用，并在 preflight 失败关闭；不得写 `bundle.json` 或附件后假装已登记。确定性
Transform 仍可按自身编译端口生成多个 Artifact。集合输出若以后实现，必须扩展同一 Run 提交原语，
不能恢复旧 Task/finalize 状态机。

## 3. 统一信封

`output/result.json` 使用严格信封：

```json
{
  "schema_version": 1,
  "handoff": {
    "verdict": "pass",
    "summary": "本角色的一句话结论",
    "assumptions": [],
    "missing_inputs": [],
    "next_actions": [],
    "evidence_bundle_fingerprint_sha256": null
  },
  "payload": {}
}
```

- `payload` 由 Operation 输出端口绑定的严格 Schema、codec 和 validator 决定；
- `handoff` 只生成有界 `SchedulerSignal`，不替代详细科学内容；
- `next_actions` 是给调度 Agent 和人阅读的非约束性建议；Worker 不输出具有控制权威的后继
  Operation 名称，调度 Agent 必须根据封存科学结果与唯一编译目录自主选择行为；
- 已移除废弃的 `next_action_kind` 字段；严格合同拒绝携带此字段的旧格式；
- 裸 payload、额外字段、非规范 JSON、未声明来源、机器路径、秘密模式、未声明二进制和超限内容
  均在 Artifact 登记前拒绝；
- 校验失败时 Run 保持 running，Agent 可以修正同一候选；首次完整通过的候选摘要被唯一接受，后续
  提交不能换成不同字节；
- revision 是新的完整 Run 输出，不继承旧审查、人工决定或资格。

## 4. 角色 Payload

通用角色可以使用不同 payload，因为职责不同；统一的是文件生命周期、来源绑定和最小上下文，而
不是一个宽松科学对象。当前常用角色包括证据提取/审查、idea 提出/批评、实验设计、结果诊断、
TCAD Deck 作者和独立审查者。具体类型只来自已安装插件的 OperationSpec，角色表不是第二注册表。

论文图数字化等需要多文件证据的能力，在 Agent collection 尚未进入 Run v1 前不得通过 Agent
主输出冒充完成。插件可以把机械多文件处理实现为确定性工具或 Transform，并让 Agent 只输出科学
判断；任何正式附件仍须由同一编译合同、明确端口和不可变登记覆盖。

## 5. 控制面处理顺序

```text
worker_submit_result
→ 后端 seal 工作区
→ 校验唯一文件集与 RoleResultEnvelope
→ 执行端口 codec、validator 和上下文 validator
→ CAS 接受候选摘要
→ 幂等登记主 Artifact
→ 在控制事务中完成 Run 并写入唯一完成收据
```

后端、领域工具和 Agent 均不能登记正式 Artifact、写 Run 终态、更新 current 或创建 reviewer。
Run 完成不会自动推进 current，也不会自动创建 reviewer Run。current 只由后续显式 Root CAS 命令
更新；父调度器依据编译 review edge 另行选择并调用 reviewer Operation。下游 Agent 只获得控制面按
输入端口重新物化的精确文件，不获得上游 Run 身份或聊天。

## 6. 验收

1. Agent Operation 恰有一个严格主输出，所有输出 validator 在启动编译时闭合；
2. 生命周期只有 `worker_open_assignment`、`worker_heartbeat`、`worker_submit_result`；
3. Local/Hardened 对同一 Operation 的可用性在目录、preflight、Codex profile 和 Run 创建处一致；
4. 裸 payload、额外文件、路径逃逸、符号链接、秘密和超限输出失败关闭；
5. Artifact 不包含 handoff，调度信号不由 Agent 另行写入；
6. 旧 Task、worker session、materialize/validate/finalize 协议没有兼容路由。
