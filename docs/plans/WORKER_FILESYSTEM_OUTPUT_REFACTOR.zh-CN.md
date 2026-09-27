# Worker 科学输出文件沙箱重构记录

> 已被 [Subagent 任务绑定读写机制重构](SUBAGENT_TASK_BOUND_FILE_IO_REFACTOR.zh-CN.md)
> 取代。下文保留为历史实现记录；其中 `ses_*` 原生写权限不再是当前方案。

## 结论

所有 Codex scientific worker 的主 JSON 统一改为受控文件输出：worker 直接编辑本次物化目录中的
`output/result.json`，控制面继续负责 schema validation、seal、checkpoint、finalize 和 Artifact
注册。主 JSON 不再通过 MCP begin/append/commit 参数传输。

这不是允许 subagent 互相读写目录。下游只有在上游成功 finalization 后，才会由控制面获得一个
只读 task-local input；未校验文件、checkpoint 和 rejected snapshot 都只是当前任务的 provisional
retry context。

## 边界

```text
<state>/workspaces/ses_*/
├── assignment.json               # 控制面只读
├── schema/output.schema.json     # 控制面只读
├── inputs/**                     # 控制面只读
├── deck/**                       # 仅 deck author 可写；reviewer 只读
└── output/
    ├── result.json               # 除 deck author 外的 worker 可写
    ├── bundle.json               # 仅 assignment 声明 collection 时允许
    └── collections/**            # 仅声明的附件集合
```

- `tcad_deck_author` 只写 `deck/**`；控制面从真实 deck 文件生成 `output/result.json`。
- 所有其他 Codex worker 只增加 `output/**` 写权限，框架源码、输入、schema 与控制数据继续只读。
- `tcad_deck_reviewer` 属于普通输出者，但它的 `deck/**` 明确只读且不暴露 debug。
- `worker_tcad_debug_run` 只向 deck author 暴露。
- `worker_begin_result_upload`、`worker_append_result_upload`、
  `worker_commit_result_upload` 已从公共 Worker 工具表移除，只在兼容路由保留，不能被新 Agent 发现。

## 为什么不让控制面代写所有 JSON

一般角色的 `payload` 本身就是 worker 作出的科学判断，控制面不能制造或改写；因此 worker 写规范
envelope，控制面只校验与冻结。Deck author 不同：其科学实现真源是 `.cmd/.par` 等真实文件，
控制面可以机械重建 `DeckProjectDraft` 而不制造科学内容。

## 验收标准

- [x] 所有生成的 Codex 角色使用从 `:read-only` 继承的自定义权限 profile；
- [x] 非 author 只获得 `ses_*/output/**` 写权限；
- [x] author 只获得 `ses_*/deck/**` 写权限；
- [x] 公共 Worker MCP 不枚举三项长文本上传工具；
- [x] common role prompt 要求直接写 `output/result.json`；
- [x] 既有 legacy upload 回归仍可通过兼容路由运行；
- [x] installer 的 Worker 工具探针与新公共工具数一致；
- [x] 上游直写/校验/finalize 后，下游无需读取上游 status 即可获得规范化只读 payload；
- [x] handoff 只形成独立 scheduler signal，不混入下游科学 payload；
- [x] 完整回归 `474 passed`；
- [ ] 重新安装后完成一次真实多角色 Alpha 纵向链。

## 通信审计结论

普通角色不需要复制 deck 的多文件工程协议。正式跨角色通信维持两条正交通道：

1. `payload` 与声明附件在 finalize 后注册为不可变 Artifact，供 scheduler 显式绑定为下游只读输入；
2. `handoff` 注册为独立 scheduler signal，只承担 pass/revise/blocked/inconclusive 路由。

控制面在注册前按角色 schema 规范化 payload，因此下游读取的是规范科学对象而非上游原始 envelope
字节；上游 workspace 在完成后删除。revision 通过 `revision_base`、`change_request`、`prior_signal`
等 typed usage 显式组合，不依赖聊天消息或临时文件。附件以主输出为 parent，并由 `task_outputs`
作为一个有界集合枚举。该结构已经满足上下游隔离、溯源和增量复用需求，再增加角色专用共享目录
会绕过 Artifact/usage/context-policy 边界，因此不应实施。

## 已知残余

Codex agent 权限配置是角色级静态配置，当前路径规则为 `ses_*/output/**` 或
`ses_*/deck/**`，尚不能在 spawn 时动态收窄为单个 session。控制面会把 worker process 串行绑定到
一个 assignment，并在当前 session 的 validate/finalize 边界重读文件；精确 session 权限注入作为
P1 加固，不阻塞 Alpha 闭环。
